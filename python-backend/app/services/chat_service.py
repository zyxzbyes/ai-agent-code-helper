from collections.abc import Iterator
from dataclasses import dataclass, field
import logging
import re
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.agents.memory import append_assistant_message, append_user_message, get_history
from app.agents.prompt import SYSTEM_PROMPT
from app.agents.toolkit import AgentToolResult
from app.agents.tool_calling_agent import AgentPreparedMessages
from app.agents.tool_calling_agent import ToolCallingAgent
from app.core.config import settings
from app.db.models import User
from app.services import conversation_service


logger = logging.getLogger(__name__)
URL_RE = re.compile(r"https?://[^\s)）]+")
CURRENT_DATE_RE = re.compile(r"^CURRENT_DATE=(\d{4}-\d{2}-\d{2})", re.MULTILINE)
TODAY_WITH_DATE_RE = re.compile(
    r"(?:截至今天|今天)\s*[（(]\s*("
    r"20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?|"
    r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}"
    r")\s*[）)]"
)


@dataclass(frozen=True)
class ChatStreamEvent:
    type: str
    content: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)


class ChatService:
    def __init__(self) -> None:
        self._client = self._build_client()
        self._agent = ToolCallingAgent(self._client) if self._client is not None else None

    def stream_chat(self, memory_id: int, message: str) -> Iterator[ChatStreamEvent]:
        user_message = message.strip()
        if not user_message:
            yield ChatStreamEvent(type="content", content="请输入有效的问题。")
            return

        if self._client is None:
            yield ChatStreamEvent(type="content", content="模型服务未配置：请在 python-backend/.env 中设置 OPENAI_API_KEY。")
            return

        if self._agent is None:
            yield ChatStreamEvent(type="content", content="模型服务未配置：请在 python-backend/.env 中设置 OPENAI_API_KEY。")
            return

        history_messages = get_history(memory_id)
        prepared = self._prepare_messages(
            history_messages=history_messages,
            user_message=user_message,
            conversation_id=None,
            memory_id=memory_id,
        )

        assistant_parts: list[str] = []

        try:
            current_date = _extract_final_current_date(prepared.messages)
            _log_final_prompt(prepared.messages, current_date)
            sanitizer = _FinalDateSanitizer(current_date)
            stream = self._client.chat.completions.create(
                model=settings.model_name,
                messages=prepared.messages,
                temperature=settings.temperature,
                stream=True,
            )

            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    safe_content = sanitizer.feed(content)
                    if safe_content:
                        assistant_parts.append(safe_content)
                        yield ChatStreamEvent(type="content", content=safe_content)

            tail_content = sanitizer.flush()
            if tail_content:
                assistant_parts.append(tail_content)
                yield ChatStreamEvent(type="content", content=tail_content)

            assistant_message = "".join(assistant_parts).strip()
            append_user_message(memory_id, user_message)
            append_assistant_message(memory_id, assistant_message)
            yield ChatStreamEvent(type="sources", sources=_build_source_payload(prepared.tool_results))
        except Exception as exc:
            yield ChatStreamEvent(type="content", content=f"模型调用失败：{exc}")

    def stream_conversation_chat(
        self,
        db: Session,
        user: User,
        conversation_id: int,
        message: str,
    ) -> Iterator[ChatStreamEvent]:
        user_message = message.strip()
        if not user_message:
            yield ChatStreamEvent(type="content", content="请输入有效的问题。")
            return

        conversation = conversation_service.get_owned_conversation(db, user, conversation_id)

        if self._client is None:
            yield ChatStreamEvent(type="content", content="模型服务未配置：请在 python-backend/.env 中设置 OPENAI_API_KEY。")
            return

        history = conversation_service.get_recent_messages(
            db=db,
            conversation=conversation,
            limit=settings.max_memory_messages,
        )
        if self._agent is None:
            yield ChatStreamEvent(type="content", content="模型服务未配置：请在 python-backend/.env 中设置 OPENAI_API_KEY。")
            return

        history_messages = [{"role": item.role, "content": item.content} for item in history]
        prepared = self._prepare_messages(
            history_messages=history_messages,
            user_message=user_message,
            conversation_id=conversation_id,
            memory_id=None,
        )

        assistant_parts: list[str] = []

        try:
            current_date = _extract_final_current_date(prepared.messages)
            _log_final_prompt(prepared.messages, current_date)
            sanitizer = _FinalDateSanitizer(current_date)
            stream = self._client.chat.completions.create(
                model=settings.model_name,
                messages=prepared.messages,
                temperature=settings.temperature,
                stream=True,
            )

            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    safe_content = sanitizer.feed(content)
                    if safe_content:
                        assistant_parts.append(safe_content)
                        yield ChatStreamEvent(type="content", content=safe_content)

            tail_content = sanitizer.flush()
            if tail_content:
                assistant_parts.append(tail_content)
                yield ChatStreamEvent(type="content", content=tail_content)

            assistant_message = "".join(assistant_parts).strip()
            conversation_service.finalize_chat_messages(
                db=db,
                conversation=conversation,
                user_message=user_message,
                assistant_message=assistant_message,
            )
            yield ChatStreamEvent(type="sources", sources=_build_source_payload(prepared.tool_results))
        except Exception as exc:
            yield ChatStreamEvent(type="content", content=f"模型调用失败：{exc}")

    def _build_client(self) -> OpenAI | None:
        if not settings.openai_api_key.strip():
            return None

        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url.strip():
            client_kwargs["base_url"] = settings.openai_base_url.strip()
        return OpenAI(**client_kwargs)

    def _prepare_messages(
        self,
        history_messages: list[dict],
        user_message: str,
        conversation_id: int | None,
        memory_id: int | None,
    ) -> AgentPreparedMessages:
        if self._agent is None:
            logger.info(
                "Agent chat request conversationId=%s memoryId=%s user_message=%r used_langgraph=%s selected_tools=%s fallback_tools=%s used_tools=%s tool_sources_count=%s",
                conversation_id,
                memory_id,
                user_message,
                False,
                [],
                [],
                [],
                0,
            )
            return _plain_prepared_messages(history_messages, user_message)

        try:
            prepared = self._agent.prepare_messages(history_messages, user_message)
            logger.info(
                "Agent chat request conversationId=%s memoryId=%s user_message=%r used_langgraph=%s selected_tools=%s fallback_tools=%s used_tools=%s tool_sources_count=%s",
                conversation_id,
                memory_id,
                user_message,
                prepared.used_langgraph,
                prepared.selected_tools,
                prepared.fallback_tools,
                prepared.used_tools,
                prepared.tool_sources_count,
            )
            return prepared
        except Exception as exc:
            logger.warning("Agent tool selection failed, fallback to normal chat: %s", exc)
            logger.info(
                "Agent chat request conversationId=%s memoryId=%s user_message=%r used_langgraph=%s selected_tools=%s fallback_tools=%s used_tools=%s tool_sources_count=%s",
                conversation_id,
                memory_id,
                user_message,
                False,
                [],
                [],
                [],
                0,
            )
            return _plain_prepared_messages(history_messages, user_message)


def _plain_prepared_messages(history_messages: list[dict], user_message: str) -> AgentPreparedMessages:
    return AgentPreparedMessages(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *history_messages,
            {"role": "user", "content": user_message},
        ],
        selected_tools=[],
        fallback_tools=[],
        used_tools=[],
        tool_results=[],
        used_langgraph=False,
    )


def _build_source_payload(tool_results: list[AgentToolResult]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for result in tool_results:
        for source in result.sources:
            item = _parse_source_item(source)
            if item:
                item["index"] = len(payload) + 1
                payload.append(item)
    return payload


def _parse_source_item(source: str) -> dict[str, Any] | None:
    text = str(source or "").strip()
    if not text:
        return None

    match = URL_RE.search(text)
    if not match:
        return {"title": text}

    url = match.group(0)
    title = text[: match.start()].strip()
    title = re.sub(r"\s*-\s*$", "", title).strip()
    if not title:
        title = url
    return {"title": title, "url": url}


class _FinalDateSanitizer:
    def __init__(self, current_date: str) -> None:
        self.current_date = current_date
        self._pending = ""

    def feed(self, text: str) -> str:
        self._pending += text
        if len(self._pending) <= 48:
            return ""

        emit_text = self._pending[:-48]
        self._pending = self._pending[-48:]
        return _sanitize_final_answer_dates(emit_text, self.current_date)

    def flush(self) -> str:
        emit_text = self._pending
        self._pending = ""
        return _sanitize_final_answer_dates(emit_text, self.current_date)


def _extract_final_current_date(messages: list[dict]) -> str:
    system_prompt = _final_system_prompt(messages)
    match = CURRENT_DATE_RE.search(system_prompt)
    return match.group(1) if match else ""


def _log_final_prompt(messages: list[dict], current_date: str) -> None:
    system_prompt = _final_system_prompt(messages)
    preview = system_prompt.replace("\r\n", "\n").replace("\r", "\n")[:1200]
    logger.info("FINAL_CURRENT_DATE=%s", current_date)
    logger.info("FINAL_SYSTEM_PROMPT_PREVIEW=%s", preview)


def _final_system_prompt(messages: list[dict]) -> str:
    if not messages:
        return ""
    first_message = messages[0]
    if first_message.get("role") != "system":
        return ""
    return str(first_message.get("content", ""))


def _sanitize_final_answer_dates(text: str, current_date: str) -> str:
    if not text or not current_date:
        return text
    return TODAY_WITH_DATE_RE.sub(f"截至 {current_date}", text)


chat_service = ChatService()
