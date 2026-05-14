# 简历描述建议

## 项目描述

AI 编程小助手是一个面向编程学习与求职面试场景的智能问答系统，基于 Vue 3 + FastAPI + LangGraph Agent 构建，支持登录注册、多轮会话持久化、RAG 知识库检索、面试题搜索、MCP Web Search、流式回答和参考来源展示。项目由原 Spring Boot + LangChain4j 架构分阶段迁移到 Python Agent 架构，并保留前端兼容和用户体验。

## 主要工作

1. 负责将原 Java Spring Boot + LangChain4j 后端迁移为 Python FastAPI 后端，保持 `/api/ai/chat` SSE 接口兼容。
2. 设计并实现 JWT 登录注册、SQLite 会话列表、消息持久化和多用户数据隔离。
3. 基于 LangGraph 构建 Agent 工作流，将 RAG、面试题搜索、Web Search 封装为模型可自主调用的工具。
4. 接入 Chroma 向量库和 OpenAI-compatible embedding，实现本地知识库 RAG 检索。
5. 接入 BigModel MCP Web Search，并实现 DuckDuckGo fallback 和 MCP 调试信息输出。
6. 优化前端流式聊天体验，使用 fetch ReadableStream 支持 Authorization header、停止生成和 SSE sources 事件。
7. 设计参考来源折叠展示方案，解决模型无工具结果时编造引用的问题。
8. 增加 Guardrail 输入安全防护，对攻击、恶意软件、入侵等危险输入进行拦截。
9. 修复 Web Search 日期幻觉和 UTC 时间序列化问题，提升生产可用性。

## 可量化表达

- 完成 10+ 个后端接口和 3 类 Agent 工具能力迁移。
- 支持 0/1/多工具自主调用，并保留流式响应。
- 支持服务重启后会话和消息不丢失。
- 支持 MCP 失败时自动 fallback，提升联网搜索稳定性。
