from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from typing import Any

from openai import OpenAI

from app.agents.prompt import SYSTEM_PROMPT
from app.agents.toolkit import AGENT_TOOL_SCHEMAS, AgentToolResult, execute_agent_tool
from app.core.config import settings


logger = logging.getLogger(__name__)


@dataclass
class AgentPreparedMessages:
    messages: list[dict[str, Any]]
    selected_tools: list[str] = field(default_factory=list)
    fallback_tools: list[str] = field(default_factory=list)
    used_tools: list[str] = field(default_factory=list)
    tool_results: list[AgentToolResult] = field(default_factory=list)
    used_langgraph: bool = False

    @property
    def has_tool_sources(self) -> bool:
        return any(result.has_sources for result in self.tool_results)

    @property
    def tool_sources_count(self) -> int:
        return sum(len(result.sources) for result in self.tool_results)


class ToolCallingAgent:
    def __init__(self, client: OpenAI) -> None:
        self._client = client

    def prepare_messages(self, history_messages: list[dict[str, Any]], user_message: str) -> AgentPreparedMessages:
        initial_messages = [
            {"role": "system", "content": self._build_agent_system_prompt()},
            *history_messages,
            {"role": "user", "content": user_message},
        ]
        return self._run_with_langgraph_if_available(initial_messages)

    def _run_with_langgraph_if_available(self, initial_messages: list[dict[str, Any]]) -> AgentPreparedMessages:
        try:
            from langgraph.graph import END, StateGraph
        except Exception:
            return self._run_sequential(initial_messages, used_langgraph=False)

        try:
            def select_tools(state: dict[str, Any]) -> dict[str, Any]:
                assistant_message = self._select_tools(state["messages"])
                return {"messages": [*state["messages"], assistant_message]}

            def execute_tools(state: dict[str, Any]) -> dict[str, Any]:
                return self._execute_tool_calls(state)

            def should_execute_tools(state: dict[str, Any]) -> str:
                if _get_tool_calls(state["messages"][-1]):
                    return "execute_tools"
                return END

            graph = StateGraph(dict)
            graph.add_node("select_tools", select_tools)
            graph.add_node("execute_tools", execute_tools)
            graph.set_entry_point("select_tools")
            graph.add_conditional_edges("select_tools", should_execute_tools)
            graph.add_edge("execute_tools", END)

            compiled = graph.compile()
            state = compiled.invoke(
                {
                    "messages": initial_messages,
                    "used_tools": [],
                    "tool_results": [],
                }
            )
            return self._build_prepared_messages(state, initial_messages, used_langgraph=True)
        except Exception as exc:
            logger.warning("LangGraph agent flow unavailable, fallback to sequential tool calling: %s", exc)
            return self._run_sequential(initial_messages, used_langgraph=False)

    def _run_sequential(self, initial_messages: list[dict[str, Any]], used_langgraph: bool) -> AgentPreparedMessages:
        state = {
            "messages": [*initial_messages, self._select_tools(initial_messages)],
            "used_tools": [],
            "tool_results": [],
        }
        if _get_tool_calls(state["messages"][-1]):
            state = self._execute_tool_calls(state)
        return self._build_prepared_messages(state, initial_messages, used_langgraph=used_langgraph)

    def _select_tools(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=settings.model_name,
            messages=messages,
            temperature=0,
            tools=AGENT_TOOL_SCHEMAS,
            tool_choice="auto",
            stream=False,
        )
        if not response.choices:
            return {"role": "assistant", "content": ""}
        return _message_to_dict(response.choices[0].message)

    def _execute_tool_calls(self, state: dict[str, Any]) -> dict[str, Any]:
        messages = list(state["messages"])
        used_tools = list(state.get("used_tools", []))
        tool_results = list(state.get("tool_results", []))

        for tool_call in _get_tool_calls(messages[-1]):
            function = tool_call.get("function", {})
            tool_name = str(function.get("name", ""))
            arguments = _parse_arguments(function.get("arguments", "{}"))
            result = execute_agent_tool(tool_name, arguments)
            used_tools.append(tool_name)
            tool_results.append(result)
            _log_tool_result(result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", tool_name),
                    "name": tool_name,
                    "content": result.to_tool_message_content(),
                }
            )

        return {
            "messages": messages,
            "used_tools": used_tools,
            "tool_results": tool_results,
        }

    def _build_prepared_messages(
        self,
        state: dict[str, Any],
        initial_messages: list[dict[str, Any]],
        used_langgraph: bool,
    ) -> AgentPreparedMessages:
        used_tools = list(state.get("used_tools", []))
        tool_results = list(state.get("tool_results", []))
        selected_tools = _collect_selected_tools(state.get("messages", []))
        fallback_tools: list[str] = []

        if not selected_tools:
            fallback_tool = _select_fallback_tool(_get_user_message(initial_messages))
            if fallback_tool:
                result = _execute_fallback_tool(fallback_tool, _get_user_message(initial_messages))
                fallback_tools.append(fallback_tool)
                used_tools.append(fallback_tool)
                tool_results.append(result)

        return AgentPreparedMessages(
            messages=self._build_final_messages(initial_messages, tool_results),
            selected_tools=selected_tools,
            fallback_tools=fallback_tools,
            used_tools=used_tools,
            tool_results=tool_results,
            used_langgraph=used_langgraph,
        )

    def _build_final_messages(
        self,
        initial_messages: list[dict[str, Any]],
        tool_results: list[AgentToolResult],
    ) -> list[dict[str, Any]]:
        conversation_messages = initial_messages[1:]
        return [
            {"role": "system", "content": self._build_final_system_prompt(tool_results)},
            *conversation_messages,
        ]

    def _build_agent_system_prompt(self) -> str:
        return f"""{SYSTEM_PROMPT}

你现在处于工具选择阶段，只负责判断是否需要调用工具，不负责生成最终回答。
请根据用户问题自主判断是否需要调用工具，而不是仅凭固定关键词。

可用工具：
1. rag_search(query)：检索本地知识库。强烈适合：学习路线、编程学习、Java 学习、学习计划、简历、面试准备、项目文档、知识库资料类问题。
2. interview_question_search(keyword)：检索面试鸭面试题。强烈适合：面试题、高频题、八股、面经、校招、社招面试、题库检索。
3. web_search(query)：联网搜索。强烈适合：最新、实时、今天、当前、近期、新闻、官网、发布、价格、版本、查一下、搜索。

决策要求：
1. 可以不调用工具，也可以调用一个或多个工具。
2. 如果用户问题需要实时信息，优先调用 web_search。
3. 如果用户问题明显是面试题检索，优先调用 interview_question_search。
4. 如果用户问题适合本地知识库，调用 rag_search。
5. 没有必要使用工具时可以不调用工具。
6. 绝对不要为了生成参考来源而调用工具；只在工具确实能改善回答时调用。
7. 不要生成最终回答，不要编造参考来源。"""

    def _build_final_system_prompt(self, tool_results: list[AgentToolResult]) -> str:
        tool_context = _format_tool_context(tool_results)
        tool_sources = _format_numbered_sources(tool_results)
        current_date = _current_date()
        source_dates = _format_source_dates(tool_results)
        if not tool_sources:
            return f"""{SYSTEM_PROMPT}

CURRENT_DATE={current_date}
NO_SOURCES=true

最终回答规则：
1. 本次回答没有任何后端真实工具来源。
2. 严禁输出“参考来源”。
3. 严禁输出 [1]、[2]、[3] 这类引用编号。
4. 严禁编造文件名、工具名、URL、chunk 信息或任何来源。
5. 当前日期只能使用 CURRENT_DATE，禁止自行猜测今天日期。
6. 禁止输出“截至今天（XXXX年XX月XX日）”“今天（XXXX年XX月XX日）”“当前日期是...”。
7. 如需表达今天，只能写“截至 {current_date}”。
8. 正常直接回答用户问题即可。"""

        return f"""{SYSTEM_PROMPT}

CURRENT_DATE={current_date}
NO_SOURCES=false

最终回答规则：
1. 本次回答有后端真实工具来源。
2. 参考来源必须完全来自 TOOL_SOURCES，禁止编造、扩写或改写来源。
3. 正文中可以使用 [1]、[2] 这样的编号引用。
4. 回答末尾必须输出“参考来源：”，并只列出实际使用过的 TOOL_SOURCES 编号。
5. 不要暴露原始 JSON 字段、工具内部字段或未使用的来源。
6. 时间表达必须以 CURRENT_DATE 为准。
7. 不要把搜索结果发布日期直接写成“今天”。
8. 只有 SOURCE_DATE == CURRENT_DATE 时，才能把该来源称为“今天”。
9. 当前日期只能使用 CURRENT_DATE，禁止自行猜测今天日期。
10. 禁止输出“截至今天（XXXX年XX月XX日）”“今天（XXXX年XX月XX日）”“当前日期是...”。
11. 如需表达今天，只能写“截至 {current_date}”。
12. 如果 SOURCE_DATE != CURRENT_DATE，请使用“近期”“最近”“过去一周”或“来源日期”，而不是“今天”。
13. 如果 SOURCE_DATE=UNKNOWN 或无法确定来源日期，不要输出任何具体日期，只使用“近期”“最近”“过去一周”等模糊时间表达。
14. 严禁出现“今天（非 CURRENT_DATE 日期）”这类当前日期与来源日期冲突的表述。

TOOL_CONTEXT:
{tool_context}

TOOL_SOURCES:
{tool_sources}

SOURCE_DATE:
{source_dates}"""


def _message_to_dict(message: Any) -> dict[str, Any]:
    if hasattr(message, "model_dump"):
        return message.model_dump(exclude_none=True)
    if hasattr(message, "dict"):
        return message.dict(exclude_none=True)
    return {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", ""),
    }


def _get_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    tool_calls = message.get("tool_calls") or []
    if not isinstance(tool_calls, list):
        return []
    return [tool_call for tool_call in tool_calls if isinstance(tool_call, dict)]


def _collect_selected_tools(messages: list[dict[str, Any]]) -> list[str]:
    selected_tools: list[str] = []
    for message in messages:
        for tool_call in _get_tool_calls(message):
            function = tool_call.get("function", {})
            tool_name = str(function.get("name", "")).strip()
            if tool_name:
                selected_tools.append(tool_name)
    return selected_tools


def _parse_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if not isinstance(arguments, str):
        return {}
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _get_user_message(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _select_fallback_tool(user_message: str) -> str | None:
    if _contains_any(user_message, ("面试题", "高频题", "八股", "面经", "校招", "社招面试")):
        return "interview_question_search"
    if _contains_any(user_message, ("最新", "今天", "当前", "新闻", "官网", "版本", "价格", "发布", "查一下")):
        return "web_search"
    if _contains_any(user_message, ("学习路线", "编程学习", "Java 学习", "简历", "面试准备")):
        return "rag_search"
    return None


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text.lower() for keyword in keywords)


def _execute_fallback_tool(tool_name: str, user_message: str) -> AgentToolResult:
    arguments = {"query": user_message}
    if tool_name == "interview_question_search":
        arguments = {"keyword": user_message}
    result = execute_agent_tool(tool_name, arguments)
    logger.info("Agent fallback tool called: %s reason=selected_tools_empty", tool_name)
    _log_tool_result(result)
    return result


def _log_tool_result(result: AgentToolResult) -> None:
    logger.info(
        "Agent tool called: %s source_count=%s sources=%s source_type=%s metadata=%s",
        result.tool_name,
        result.source_count,
        result.sources,
        result.metadata.get("source_type", ""),
        result.metadata,
    )


def _format_tool_context(tool_results: list[AgentToolResult]) -> str:
    parts = []
    for result in tool_results:
        if result.content.strip() and result.sources:
            parts.append(
                f"工具：{result.tool_name}\n查询：{result.query}\n来源数量：{len(result.sources)}\n内容：\n{result.content}"
            )
    return "\n\n---\n\n".join(parts)


def _format_numbered_sources(tool_results: list[AgentToolResult]) -> str:
    sources = []
    for result in tool_results:
        sources.extend(result.sources)
    return "\n".join(f"[{index}] {source}" for index, source in enumerate(sources, start=1))


def _format_source_dates(tool_results: list[AgentToolResult]) -> str:
    lines = []
    source_index = 1
    for result in tool_results:
        source_dates = result.metadata.get("source_dates", [])
        if isinstance(source_dates, list) and source_dates:
            for item in source_dates:
                date_value = "UNKNOWN"
                if isinstance(item, dict):
                    date_value = str(item.get("date") or "UNKNOWN")
                lines.append(f"[{source_index}] {date_value}")
                source_index += 1
            continue

        for _source in result.sources:
            lines.append(f"[{source_index}] UNKNOWN")
            source_index += 1

    return "\n".join(lines) if lines else "NONE"


def _current_date() -> str:
    return datetime.now().date().isoformat()
