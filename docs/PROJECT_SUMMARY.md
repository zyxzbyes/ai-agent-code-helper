# 项目总结

## 项目亮点

- 完成 Java Spring Boot + LangChain4j 到 Python FastAPI + LangGraph 的分阶段迁移。
- 保持原 `/api/ai/chat` 流式接口兼容，同时扩展登录、会话和消息持久化。
- 使用 LangGraph Agent 让模型自主选择 RAG、面试题搜索和 Web Search 工具。
- 通过 SQLite 保存多用户会话历史，支持刷新和服务重启后恢复。
- 实现 BigModel MCP Web Search，并提供 DuckDuckGo fallback。
- 前端支持 fetch streaming、停止生成和参考来源折叠展示。
- 针对“今天”时间幻觉注入动态 `CURRENT_DATE`，并增加输出后处理。
- 统一 UTC ISO 8601 时间返回，修复跨时区相对时间显示问题。

## 技术难点与解决方案

### 1. SSE 流式输出与鉴权

EventSource 不方便携带 Authorization header，因此前端改用 fetch + ReadableStream，同时后端保留 `text/event-stream` 格式。

### 2. Agent 虚假参考来源

将工具选择 prompt 和最终回答 prompt 分离。只有后端真实工具结果存在时，才给最终回答注入 `TOOL_SOURCES`；否则注入 `NO_SOURCES=true`。

### 3. MCP 返回结构解析

BigModel MCP Web Search 的结果可能位于 `content[].text` 中，并存在双层 JSON 字符串。后端实现递归解析，并输出 `parse_path` 辅助排查。

### 4. Web Search 日期幻觉

最终 prompt 动态注入 `CURRENT_DATE` 和 `SOURCE_DATE`，并对错误“今天（日期）”表达做后处理，避免模型混淆来源日期和当前日期。

### 5. 时间时区问题

后端新写入时间使用 timezone-aware UTC datetime，历史 naive datetime 序列化时按 UTC 补 `Z`。前端兼容带时区和无时区 ISO 字符串。

### 6. 多工具结果展示

后端将 sources 通过 SSE `event: sources` 单独发送；前端将来源折叠展示，避免污染 AI 正文。
