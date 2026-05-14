from dataclasses import dataclass, field
import json
import logging
from typing import Any

from app.core.config import settings
from app.rag.retriever import format_context, retrieve
from app.tools.interview_question import format_interview_questions, search_interview_questions
from app.tools.web_search import format_web_search_results, search_web_with_debug


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentToolResult:
    tool_name: str
    query: str
    content: str
    source_count: int
    metadata: dict[str, Any]
    sources: list[str] = field(default_factory=list)

    @property
    def has_sources(self) -> bool:
        return bool(self.content.strip()) and self.source_count > 0

    def to_tool_message_content(self) -> str:
        return json.dumps(
            {
                "tool_name": self.tool_name,
                "query": self.query,
                "source_count": self.source_count,
                "sources": self.sources,
                "metadata": self.metadata,
                "content": self.content,
                "instruction": (
                    "如果你使用了此工具内容回答，正文中可以用 [1]、[2] 引用；"
                    "回答末尾必须输出“参考来源：”并列出用到的编号来源。"
                ),
            },
            ensure_ascii=False,
        )


AGENT_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": (
                "Search the local project knowledge base. Use this for questions about Java learning, "
                "programming study guidance, local docs, or knowledge already likely covered by the project documents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's semantic search query for the local knowledge base.",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "interview_question_search",
            "description": (
                "Search mianshiya.com for interview questions. Use this for interview questions, "
                "frequent questions, 八股, 面经, campus recruitment, or social recruitment interview preparation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Interview-question search keyword, such as Java, Redis, MySQL, or the user's full question.",
                    }
                },
                "required": ["keyword"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web through BigModel MCP Web Search, with DuckDuckGo fallback. Use this for latest, "
                "real-time, current, today, news, official website, release, price, or version questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The web search query.",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]


def execute_agent_tool(tool_name: str, arguments: dict[str, Any]) -> AgentToolResult:
    if tool_name == "rag_search":
        return rag_search(str(arguments.get("query", "")))
    if tool_name == "interview_question_search":
        return interview_question_search(str(arguments.get("keyword", "")))
    if tool_name == "web_search":
        return web_search(str(arguments.get("query", "")))
    return AgentToolResult(
        tool_name=tool_name,
        query="",
        content="",
        source_count=0,
        metadata={"error": f"unknown tool: {tool_name}"},
    )


def rag_search(query: str) -> AgentToolResult:
    clean_query = query.strip()
    if not settings.rag_enabled or not clean_query:
        return AgentToolResult("rag_search", clean_query, "", 0, {"enabled": settings.rag_enabled})

    try:
        chunks = retrieve(clean_query)
    except Exception as exc:
        logger.warning("Agent rag_search failed: %s", exc)
        return AgentToolResult("rag_search", clean_query, "", 0, {"error": str(exc)})

    sources = [f"{chunk.file_name}#chunk-{chunk.chunk_index}" for chunk in chunks]
    return AgentToolResult(
        tool_name="rag_search",
        query=clean_query,
        content=format_context(chunks),
        source_count=len(chunks),
        metadata={"source_type": "rag"},
        sources=sources,
    )


def interview_question_search(keyword: str) -> AgentToolResult:
    clean_keyword = keyword.strip()
    if not clean_keyword:
        return AgentToolResult("interview_question_search", clean_keyword, "", 0, {})

    try:
        questions = search_interview_questions(clean_keyword, limit=10)
    except Exception as exc:
        logger.warning("Agent interview_question_search failed: %s", exc)
        return AgentToolResult("interview_question_search", clean_keyword, "", 0, {"error": str(exc)})

    sources = [f"{question.title} - {question.url}" for question in questions]
    return AgentToolResult(
        tool_name="interview_question_search",
        query=clean_keyword,
        content=format_interview_questions(questions),
        source_count=len(questions),
        metadata={"source_type": "interview_question"},
        sources=sources,
    )


def web_search(query: str) -> AgentToolResult:
    clean_query = query.strip()
    if not clean_query:
        return AgentToolResult("web_search", clean_query, "", 0, {})

    try:
        search_response = search_web_with_debug(clean_query)
    except Exception as exc:
        logger.warning("Agent web_search failed: %s", exc)
        return AgentToolResult("web_search", clean_query, "", 0, {"error": str(exc)})

    source_types = sorted({item.source_type for item in search_response.results})
    sources = [f"{item.title} - {item.url} ({item.source_type})" for item in search_response.results]
    source_dates = [
        {
            "title": item.title,
            "url": item.url,
            "date": item.date or "UNKNOWN",
            "source_type": item.source_type,
        }
        for item in search_response.results
    ]
    return AgentToolResult(
        tool_name="web_search",
        query=clean_query,
        content=format_web_search_results(search_response.results),
        source_count=len(search_response.results),
        metadata={
            "source_type": ",".join(source_types),
            "source_dates": source_dates,
            "fallback_reason": search_response.debug.fallback_reason,
            "mcp_status": search_response.debug.as_dict(),
        },
        sources=sources,
    )
