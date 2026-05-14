from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
import re
from typing import Any
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

from app.core.config import settings


DUCKDUCKGO_HTML_URL = "https://duckduckgo.com/html/"
MCP_PROTOCOL_VERSION = "2025-03-26"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    source_type: str
    date: str = ""


@dataclass
class WebSearchDebugInfo:
    web_search_enabled: bool
    mcp_web_search_url: str
    bigmodel_api_key: str
    initialize_status: int | None = None
    initialized_notification_status: int | None = None
    tools_list_status: int | None = None
    tools_call_status: int | None = None
    mcp_session_id_received: bool = False
    available_tools: list[str] = field(default_factory=list)
    selected_tool: str | None = None
    input_schema: dict[str, Any] | None = None
    call_args_used: dict[str, Any] | None = None
    raw_content_preview: str = ""
    parse_path: str = ""
    fallback_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "WEB_SEARCH_ENABLED": self.web_search_enabled,
            "MCP_WEB_SEARCH_URL": self.mcp_web_search_url,
            "BIGMODEL_API_KEY": self.bigmodel_api_key,
            "initialize_status": self.initialize_status,
            "initialized_notification_status": self.initialized_notification_status,
            "tools_list_status": self.tools_list_status,
            "tools_call_status": self.tools_call_status,
            "mcp_session_id_received": self.mcp_session_id_received,
            "available_tools": self.available_tools,
            "selected_tool": self.selected_tool,
            "input_schema": self.input_schema,
            "call_args_used": self.call_args_used,
            "raw_content_preview": self.raw_content_preview,
            "parse_path": self.parse_path,
        }


@dataclass
class WebSearchResponse:
    results: list[WebSearchResult]
    debug: WebSearchDebugInfo


def search_web(query: str, limit: int | None = None) -> list[WebSearchResult]:
    return search_web_with_debug(query=query, limit=limit).results


def search_web_with_debug(query: str, limit: int | None = None) -> WebSearchResponse:
    debug = WebSearchDebugInfo(
        web_search_enabled=settings.web_search_enabled,
        mcp_web_search_url=settings.mcp_web_search_url.strip(),
        bigmodel_api_key=_mask_api_key(settings.bigmodel_api_key),
    )
    _log_mcp_debug("config", debug)

    if not settings.web_search_enabled:
        debug.fallback_reason = "web_search_disabled"
        _log_mcp_debug("disabled", debug)
        return WebSearchResponse(results=[], debug=debug)

    search_query = query.strip()
    if not search_query:
        debug.fallback_reason = "empty_query"
        _log_mcp_debug("empty_query", debug)
        return WebSearchResponse(results=[], debug=debug)

    result_limit = limit or settings.web_search_top_k
    try:
        mcp_results = _search_bigmodel_mcp(search_query, result_limit, debug)
        if mcp_results:
            debug.fallback_reason = None
            _log_mcp_debug("mcp_success", debug)
            return WebSearchResponse(results=mcp_results, debug=debug)
        if not debug.fallback_reason:
            debug.fallback_reason = "mcp_returned_no_results"
    except Exception as exc:
        debug.fallback_reason = f"mcp_error: {exc}"
        logger.warning("BigModel MCP Web Search failed, fallback to DuckDuckGo: %s", exc)

    _log_mcp_debug("fallback", debug)
    return WebSearchResponse(results=_search_duckduckgo(search_query, result_limit), debug=debug)


def _search_bigmodel_mcp(query: str, limit: int, debug: WebSearchDebugInfo) -> list[WebSearchResult]:
    if not settings.bigmodel_api_key.strip():
        debug.fallback_reason = "missing_bigmodel_api_key"
        return []
    if not settings.mcp_web_search_url.strip():
        debug.fallback_reason = "missing_mcp_web_search_url"
        return []

    client = BigModelMcpClient(
        endpoint=settings.mcp_web_search_url.strip(),
        api_key=settings.bigmodel_api_key.strip(),
        debug=debug,
    )
    return client.search(query=query, limit=limit)


class BigModelMcpClient:
    def __init__(self, endpoint: str, api_key: str, debug: WebSearchDebugInfo) -> None:
        self.endpoint = endpoint
        self.debug = debug
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Protocol-Version": MCP_PROTOCOL_VERSION,
            }
        )
        self.session_id: str | None = None
        self._request_id = 1

    def search(self, query: str, limit: int) -> list[WebSearchResult]:
        self._initialize()
        tools = self._list_tools()
        tool = self._pick_search_tool(tools)
        if not tool:
            self.debug.fallback_reason = "mcp_tools_list_empty"
            return []

        self.debug.selected_tool = str(tool.get("name", ""))
        self.debug.input_schema = _get_input_schema(tool)
        logger.info(
            "BigModel MCP selected_tool=%s inputSchema=%s",
            self.debug.selected_tool,
            self.debug.input_schema,
        )

        arguments = self._build_call_arguments(tool, query, limit)
        self.debug.call_args_used = _safe_debug_arguments(arguments)
        try:
            result = self._call_tool(self.debug.selected_tool, arguments)
            self.debug.raw_content_preview = _preview_raw_content(result)
            parsed, parse_path = _extract_results_with_path(result, source_type="mcp", limit=limit)
            self.debug.parse_path = parse_path
            if parsed:
                return parsed
            self.debug.fallback_reason = "mcp_tool_returned_no_results"
        except Exception as exc:
            self.debug.fallback_reason = f"mcp_tools_call_failed args={list(arguments.keys())}: {exc}"
            logger.warning("BigModel MCP tools/call failed with args %s: %s", list(arguments.keys()), exc)

        return []

    def _legacy_search(self, query: str, limit: int, tool: dict[str, Any]) -> list[WebSearchResult]:
        for arguments in self._legacy_candidate_arguments(tool, query):
            try:
                result = self._call_tool(self.debug.selected_tool, arguments)
                self.debug.call_args_used = _safe_debug_arguments(arguments)
                self.debug.raw_content_preview = _preview_raw_content(result)
                parsed, parse_path = _extract_results_with_path(result, source_type="mcp", limit=limit)
                self.debug.parse_path = parse_path
                if parsed:
                    return parsed
                self.debug.fallback_reason = f"mcp_tool_returned_no_results args={list(arguments.keys())}"
            except Exception as exc:
                self.debug.fallback_reason = f"mcp_tools_call_failed args={list(arguments.keys())}: {exc}"
                logger.warning("BigModel MCP tools/call failed with args %s: %s", list(arguments.keys()), exc)
                continue

        return []

    def _initialize(self) -> None:
        response = self._rpc(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "ai-code-helper-python", "version": "0.1.0"},
            },
            status_attr="initialize_status",
        )
        _ = response
        self._notification("notifications/initialized", {})

    def _list_tools(self) -> list[dict[str, Any]]:
        response = self._rpc("tools/list", {}, status_attr="tools_list_status")
        result = response.get("result", response)
        tools = result.get("tools", []) if isinstance(result, dict) else []
        if not isinstance(tools, list):
            return []

        self.debug.available_tools = [str(tool.get("name", "")) for tool in tools if isinstance(tool, dict)]
        if self.debug.available_tools:
            logger.info("BigModel MCP available tools: %s", self.debug.available_tools)
        return [tool for tool in tools if isinstance(tool, dict)]

    def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = self._rpc(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
            status_attr="tools_call_status",
        )
        return response.get("result", response)

    def _rpc(self, method: str, params: dict[str, Any], status_attr: str) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }
        response = self.session.post(self.endpoint, json=payload, timeout=20)
        setattr(self.debug, status_attr, response.status_code)
        logger.info("BigModel MCP %s HTTP status: %s", method, response.status_code)
        self._capture_session_id(response)
        response.raise_for_status()
        data = self._parse_response(response)
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(str(data["error"]))
        return data if isinstance(data, dict) else {}

    def _notification(self, method: str, params: dict[str, Any]) -> None:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        response = self.session.post(self.endpoint, json=payload, timeout=20)
        self.debug.initialized_notification_status = response.status_code
        logger.info("BigModel MCP %s HTTP status: %s", method, response.status_code)
        self._capture_session_id(response)
        if response.status_code not in {200, 202, 204}:
            response.raise_for_status()

    def _capture_session_id(self, response: requests.Response) -> None:
        session_id = response.headers.get("Mcp-Session-Id") or response.headers.get("mcp-session-id")
        if session_id:
            self.debug.mcp_session_id_received = True
            logger.info("BigModel MCP session id received: true")
        if session_id and session_id != self.session_id:
            self.session_id = session_id
            self.session.headers.update({"Mcp-Session-Id": session_id})

    def _parse_response(self, response: requests.Response) -> dict[str, Any] | list[Any]:
        content_type = response.headers.get("content-type", "")
        text = response.text.strip()
        if "text/event-stream" in content_type:
            events = _parse_sse_json_events(text)
            return events[-1] if events else {}
        if not text:
            return {}
        return response.json()

    def _next_id(self) -> int:
        request_id = self._request_id
        self._request_id += 1
        return request_id

    def _pick_search_tool(self, tools: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not tools:
            return None

        for tool in tools:
            if str(tool.get("name", "")) in {"webSearchPrime", "web_search_prime"}:
                return tool

        logger.info("BigModel MCP webSearchPrime not found, available tools: %s", self.debug.available_tools)
        for tool in tools:
            name = str(tool.get("name", ""))
            if "web" in name.lower() and "search" in name.lower():
                return tool
        for tool in tools:
            name = str(tool.get("name", ""))
            if "search" in name.lower():
                return tool
        return tools[0]

    def _build_call_arguments(self, tool: dict[str, Any], query: str, limit: int) -> dict[str, Any]:
        schema = _get_input_schema(tool)
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        property_names = list(properties.keys()) if isinstance(properties, dict) else []
        arguments: dict[str, Any] = {}

        query_key = _select_schema_key(property_names, ("search_query", "query", "q", "keywords", "search_intent"))
        if query_key:
            arguments[query_key] = query
        else:
            arguments["search_query"] = query

        limit_key = _select_schema_key(property_names, ("top_k", "count", "limit"))
        if limit_key:
            arguments[limit_key] = limit

        return arguments

    def _legacy_candidate_arguments(self, tool: dict[str, Any], query: str) -> list[dict[str, Any]]:
        return [
            {"search_query": query},
            {"query": query},
        ]


def _search_duckduckgo(query: str, limit: int) -> list[WebSearchResult]:
    response = requests.get(
        f"{DUCKDUCKGO_HTML_URL}?q={quote_plus(query)}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=8,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[WebSearchResult] = []
    seen_urls: set[str] = set()

    for result in soup.select(".result"):
        link = result.select_one(".result__a")
        if link is None:
            continue

        title = link.get_text(" ", strip=True)
        href = _normalize_duckduckgo_url(link.get("href", "").strip())
        snippet_el = result.select_one(".result__snippet")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

        if not title or not href or href in seen_urls:
            continue

        results.append(
            WebSearchResult(
                title=title,
                url=href,
                snippet=snippet,
                source_type="duckduckgo",
                date=_extract_date({"title": title, "content": snippet}),
            )
        )
        seen_urls.add(href)

        if len(results) >= limit:
            break

    return results


def _normalize_duckduckgo_url(url: str) -> str:
    if not url:
        return ""

    parsed = urlparse(url)
    if parsed.path == "/l/":
        uddg = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(uddg)
    return url


def _parse_sse_json_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        data_lines = []
        for line in block.split("\n"):
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if not data_lines:
            continue
        data_text = "\n".join(data_lines)
        if data_text == "[DONE]":
            continue
        try:
            event = json.loads(data_text)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _extract_results(payload: Any, source_type: str, limit: int) -> list[WebSearchResult]:
    results, _ = _extract_results_with_path(payload, source_type=source_type, limit=limit)
    return results


def _extract_results_with_path(payload: Any, source_type: str, limit: int) -> tuple[list[WebSearchResult], str]:
    candidates = _collect_search_candidates(payload)
    results: list[WebSearchResult] = []
    seen_urls: set[str] = set()

    for item in candidates:
        title = str(item.get("title") or item.get("name") or item.get("headline") or "").strip()
        url = str(item.get("url") or item.get("link") or item.get("href") or "").strip()
        snippet = str(
            item.get("snippet")
            or item.get("summary")
            or item.get("description")
            or item.get("content")
            or ""
        ).strip()
        source_date = _extract_date(item)

        if not title and snippet:
            title = snippet[:60]
        if not url:
            continue
        if not title:
            title = url
        if url in seen_urls:
            continue

        results.append(WebSearchResult(title=title, url=url, snippet=snippet, source_type=source_type, date=source_date))
        seen_urls.add(url)

        if len(results) >= limit:
            break

    parse_path = " -> ".join(_last_parse_paths[:8]) if _last_parse_paths else "no_candidates"
    return results, parse_path


def _collect_search_candidates(payload: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    _last_parse_paths.clear()

    def visit(value: Any, path: str) -> None:
        if isinstance(value, str):
            parsed = _try_json(value)
            if parsed is not None:
                visit(parsed, f"{path}|json")
            return

        if isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")
            return

        if not isinstance(value, dict):
            return

        if any(key in value for key in ("url", "link", "href")):
            candidates.append(value)
            _last_parse_paths.append(path)

        if value.get("type") == "text" and isinstance(value.get("text"), str):
            parsed = _try_json(value["text"])
            if parsed is not None:
                visit(parsed, f"{path}.text|json")

        for key in (
            "result",
            "results",
            "items",
            "data",
            "content",
            "text",
            "structuredContent",
            "structured_content",
            "output",
            "web_search",
            "search_results",
            "webpages",
            "web_results",
            "documents",
            "pages",
        ):
            if key in value:
                visit(value[key], f"{path}.{key}")

    visit(payload, "$")
    return candidates


_last_parse_paths: list[str] = []


def _get_input_schema(tool: dict[str, Any]) -> dict[str, Any]:
    schema = tool.get("inputSchema") or tool.get("input_schema") or {}
    return schema if isinstance(schema, dict) else {}


def _select_schema_key(property_names: list[str], candidates: tuple[str, ...]) -> str | None:
    exact = {name.lower(): name for name in property_names}
    for candidate in candidates:
        if candidate.lower() in exact:
            return exact[candidate.lower()]
    for candidate in candidates:
        candidate_lower = candidate.lower()
        for property_name in property_names:
            name_lower = property_name.lower()
            if candidate_lower == name_lower or candidate_lower in name_lower:
                return property_name
    return None


def _safe_debug_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in arguments.items():
        safe[key] = value if key.lower() not in {"api_key", "token", "authorization"} else "***"
    return safe


def _preview_raw_content(payload: Any, max_length: int = 1200) -> str:
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except TypeError:
        text = str(payload)
    return text[:max_length]


DATE_FIELD_NAMES = (
    "date",
    "source_date",
    "published_date",
    "publish_date",
    "pub_date",
    "published_at",
    "publish_time",
    "time",
    "datetime",
)


def _extract_date(item: dict[str, Any]) -> str:
    for field_name in DATE_FIELD_NAMES:
        value = item.get(field_name)
        normalized = _normalize_date(value)
        if normalized:
            return normalized

    combined = " ".join(
        str(item.get(key, ""))
        for key in ("title", "snippet", "summary", "description", "content")
        if item.get(key)
    )
    return _normalize_date(combined)


def _normalize_date(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""

    iso_match = re.search(r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b", text)
    if iso_match:
        return _format_date_parts(iso_match.group(1), iso_match.group(2), iso_match.group(3))

    chinese_match = re.search(r"(20\d{2})\s*年\s*(0?[1-9]|1[0-2])\s*月\s*(0?[1-9]|[12]\d|3[01])\s*日?", text)
    if chinese_match:
        return _format_date_parts(chinese_match.group(1), chinese_match.group(2), chinese_match.group(3))

    compact_match = re.search(r"\b(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\b", text)
    if compact_match:
        return _format_date_parts(compact_match.group(1), compact_match.group(2), compact_match.group(3))

    return ""


def _format_date_parts(year: str, month: str, day: str) -> str:
    try:
        return datetime(int(year), int(month), int(day)).date().isoformat()
    except ValueError:
        return ""


def _try_json(text: str) -> Any | None:
    stripped = text.strip()
    if not stripped or stripped[0] not in '[{"':
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _mask_api_key(api_key: str) -> str:
    key = api_key.strip()
    if not key:
        return "not_set"
    if len(key) <= 10:
        return f"{key[:2]}****{key[-2:]}"
    return f"{key[:6]}****{key[-4:]}"


def _log_mcp_debug(stage: str, debug: WebSearchDebugInfo) -> None:
    logger.info(
        "BigModel MCP debug stage=%s WEB_SEARCH_ENABLED=%s MCP_WEB_SEARCH_URL=%s "
        "BIGMODEL_API_KEY=%s initialize_status=%s tools_list_status=%s "
        "tools_call_status=%s mcp_session_id_received=%s fallback_reason=%s",
        stage,
        debug.web_search_enabled,
        debug.mcp_web_search_url,
        debug.bigmodel_api_key,
        debug.initialize_status,
        debug.tools_list_status,
        debug.tools_call_status,
        debug.mcp_session_id_received,
        debug.fallback_reason,
    )


def format_web_search_results(results: list[WebSearchResult]) -> str:
    if not results:
        return ""

    lines = []
    for index, result in enumerate(results, start=1):
        snippet = f"\n   摘要：{result.snippet}" if result.snippet else ""
        source_date = f"\n   SOURCE_DATE：{result.date}" if result.date else "\n   SOURCE_DATE：UNKNOWN"
        lines.append(
            f"[{index}] {result.title} - {result.url}\n"
            f"   来源类型：{result.source_type}{source_date}{snippet}"
        )
    return "\n".join(lines)
