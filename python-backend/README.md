# Python FastAPI Backend

这是 `ai-code-helper` 的第二阶段 Python 后端。当前目标是提供产品化聊天基础能力：登录注册、JWT 登录态、SQLite 持久化会话、消息历史和兼容原 `/api/ai/chat` 的 SSE 流式聊天。

## 接口兼容关系

原 Java 后端核心接口：

```text
GET /api/ai/chat?memoryId=...&message=...
```

当前 Python 后端保留这个 legacy 调用；新前端优先使用：

```text
GET /api/ai/chat?conversationId=...&message=...
Authorization: Bearer <token>
```

响应仍然是 `text/event-stream`：

```text
data: xxx

data: [DONE]
```

## 创建 .env

```bash
copy .env.example .env
```

示例配置：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-plus
TEMPERATURE=0.7
MAX_MEMORY_MESSAGES=10
DATABASE_URL=sqlite:///./data/app.db
JWT_SECRET_KEY=change-this-jwt-secret-key-min-32-bytes
JWT_EXPIRE_MINUTES=10080
```

`OPENAI_BASE_URL` 用于兼容 OpenAI-compatible API，例如通义千问 DashScope、DeepSeek、OpenAI 等。不要提交真实 API Key。

## 安装依赖

```bash
cd D:\agent\python-backend
pip install -r requirements.txt
```

## 初始化数据库

应用启动时会自动创建 SQLite 表。也可以手动执行：

```bash
python -m app.db.init_db
```

默认数据库文件位置：

```text
D:\agent\python-backend\data\app.db
```

## 构建 RAG 索引

Java 项目的 Markdown 知识库已迁移到：

```text
D:\agent\python-backend\data\docs
```

默认使用 Chroma 本地向量库，索引保存到：

```text
D:\agent\python-backend\data\vector_index
```

构建索引：

```bash
cd D:\agent\python-backend
python -m app.rag.build_index
```

RAG 参数与原 Java 配置保持一致：

```env
RAG_ENABLED=true
RAG_DOCS_DIR=./data/docs
RAG_INDEX_DIR=./data/vector_index
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200
RAG_TOP_K=5
RAG_SCORE_THRESHOLD=0.75
EMBEDDING_MODEL=text-embedding-v4
```

关闭 RAG：

```env
RAG_ENABLED=false
```

关闭后 `/api/ai/chat` 会继续普通流式聊天，不会检索本地知识库。

## 启动后端

```bash
cd D:\agent\python-backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 验证 health

```text
GET http://localhost:8000/api/health
```

## 注册用户

```bash
curl -X POST http://localhost:8000/api/auth/register ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"zhangsan\",\"password\":\"123456\"}"
```

## 登录

```bash
curl -X POST http://localhost:8000/api/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"zhangsan\",\"password\":\"123456\"}"
```

响应中的 `data.token` 用于后续接口：

```text
Authorization: Bearer <token>
```

## 创建新对话

```bash
curl -X POST http://localhost:8000/api/conversations ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer <token>" ^
  -d "{\"title\":\"新对话\"}"
```

## 查询会话列表

```bash
curl http://localhost:8000/api/conversations ^
  -H "Authorization: Bearer <token>"
```

## 查询历史消息

```bash
curl http://localhost:8000/api/conversations/1/messages ^
  -H "Authorization: Bearer <token>"
```

## 测试持久化聊天 SSE

浏览器、前端或支持流式响应的客户端请求：

```text
GET http://localhost:8000/api/ai/chat?conversationId=1&message=你好
Authorization: Bearer <token>
```

## 测试 RAG 命中

先构建索引：

```bash
python -m app.rag.build_index
```

然后调用调试检索接口：

```bash
curl "http://localhost:8000/api/rag/search?query=如何学习Java" ^
  -H "Authorization: Bearer <token>"
```

返回中会包含：

- `source`
- `score`
- `content_preview`

也可以直接在聊天中询问“如何学习 Java”“有哪些程序员面试建议”等问题；如果命中知识库，检索 context 会注入模型 prompt，但不会写入 `Message` 表。

## 测试面试题搜索工具

面试题搜索工具会抓取面试鸭搜索结果，返回题目标题和 URL。接口需要登录：

```bash
curl "http://localhost:8000/api/tools/interview/search?keyword=Java" ^
  -H "Authorization: Bearer <token>"
```

返回字段：

- `title`
- `url`

聊天中如果用户问题明显包含以下关键词，会优先触发该工具：

- 面试题
- 高频题
- 八股
- 面经
- 校招
- 社招面试

例如：

```text
Java 高频面试题有哪些？
Redis 八股题帮我整理一下
校招 Java 面经怎么准备？
```

工具结果只注入模型 prompt，不会写入 `Message` 表；最终仍只保存用户问题和 AI 回复。非面试题类问题仍优先走 RAG，RAG 不命中则普通聊天。

## BigModel MCP Web Search 配置

原 Java 项目使用 BigModel MCP Web Search。Python 当前阶段已接入 BigModel MCP Web Search client，并保留 DuckDuckGo 作为 fallback。

配置项：

```env
WEB_SEARCH_ENABLED=true
BIGMODEL_API_KEY=
MCP_WEB_SEARCH_URL=https://open.bigmodel.cn/api/mcp/web_search_prime/mcp
WEB_SEARCH_TOP_K=5
```

调用方式：

- 优先使用 `MCP_WEB_SEARCH_URL` 发起 JSON-RPC MCP 请求。
- 请求头使用 `Authorization: Bearer <BIGMODEL_API_KEY>`。
- MCP 返回结果会统一整理为 `title`、`url`、`snippet`、`source_type=mcp`。
- 如果未配置 `BIGMODEL_API_KEY`、MCP 连接失败、工具调用失败或无可用搜索结果，会自动 fallback 到 DuckDuckGo。
- DuckDuckGo 返回结果统一为 `title`、`url`、`snippet`、`source_type=duckduckgo`。

关闭联网搜索：

```env
WEB_SEARCH_ENABLED=false
```

## 测试 Web Search 调试接口

接口需要登录：

```bash
curl "http://localhost:8000/api/tools/web/search?query=Python 3.13 最新特性" ^
  -H "Authorization: Bearer <token>"
```

返回字段：

- `title`
- `url`
- `snippet`
- `source_type`

`source_type=mcp` 表示本次结果来自 BigModel MCP Web Search；`source_type=duckduckgo` 表示 MCP 不可用或未命中后使用了 DuckDuckGo fallback。

排查 MCP fallback 原因时可以加 `debug=true`：

```bash
curl "http://localhost:8000/api/tools/web/search?query=Python 3.13 最新特性&debug=true" ^
  -H "Authorization: Bearer <token>"
```

调试响应会额外返回：

- `fallback_reason`
- `mcp_status.initialize_status`
- `mcp_status.tools_list_status`
- `mcp_status.tools_call_status`
- `mcp_status.mcp_session_id_received`
- `mcp_status.available_tools`
- `mcp_status.selected_tool`
- `mcp_status.input_schema`
- `mcp_status.call_args_used`
- `mcp_status.raw_content_preview`
- `mcp_status.parse_path`

后端日志也会输出 MCP 配置、状态码、是否拿到 `Mcp-Session-Id` 和 fallback 原因。API Key 只显示前 6 位和后 4 位，中间打码。

## 聊天中触发联网搜索

当用户问题明显需要实时信息、最新资料或联网查询时，会触发 Web Search。关键词包括：

- 最新
- 实时
- 联网
- 搜索
- 查一下
- 今天
- 当前
- 近期
- 新闻
- 官网
- 发布
- 价格
- 版本

例如：

```text
帮我查一下 Python 3.13 最新特性
今天 OpenAI 有什么新闻？
某个框架最新版本是多少？
```

## Agent 工具调用

当前聊天服务已从后端关键词路由升级为 Agent 化工具调用。主流程优先使用 LangGraph 编排：

```text
用户问题 + 历史消息
  -> 模型自主判断是否调用工具
  -> 执行 0 个、1 个或多个工具
  -> 工具结果进入最终回答上下文
  -> 继续使用 /api/ai/chat SSE 流式输出
```

Agent 工具列表：

- `rag_search(query)`：检索本地 Chroma 知识库。
- `interview_question_search(keyword)`：检索面试鸭面试题。
- `web_search(query)`：优先 BigModel MCP Web Search，失败时 DuckDuckGo fallback。

如果当前环境未安装 `langgraph` 或 LangGraph 编排不可用，后端会自动 fallback 到顺序 tool-calling 流程，不影响聊天可用性。判断工具是否被调用可以查看后端日志：

```text
Agent chat request conversationId=1 memoryId=None user_message='Java 编程学习路线是什么？' used_langgraph=True selected_tools=['rag_search'] fallback_tools=[] used_tools=['rag_search'] tool_sources_count=5
Agent tool called: rag_search source_count=5 sources=['xxx.md#chunk-0'] source_type=rag
```

如果模型自主未选择工具，但问题命中明确规则，会触发 fallback 工具：

```text
Agent fallback tool called: rag_search reason=selected_tools_empty
```

最终回答的引用由后端真实 `tool_sources_count` 控制：如果 `tool_sources_count=0`，最终 prompt 会传入 `NO_SOURCES=true`，禁止模型输出“参考来源”、引用编号、文件名、工具名或伪造 URL。

测试建议：

- `Java 编程学习路线是什么？`：通常会调用 `rag_search`。
- `Java 高频面试题有哪些？`：通常会调用 `interview_question_search`。
- `今天 OpenAI 有什么新闻？`：通常会调用 `web_search`，配置有效 BigModel key 时 `source_type` 优先为 `mcp`。
- `帮我制定三个月 Java 学习计划。`：模型可选择不调用工具或少量调用 RAG。

## 引用来源展示规则

RAG、面试题工具、Web Search 都会将来源以编号形式注入模型 prompt：

- RAG：`[1] source 文件名#chunk-index`
- interviewQuestionSearch：`[1] title - url`
- Web Search：`[1] title - url`

模型可以在正文中使用 `[1]`、`[2]` 引用。只要使用了 RAG、工具或 Web Search，回答末尾必须输出：

```text
参考来源：
[1] xxx
[2] xxx
```

这些 context/raw result 不会写入 `Message` 表，只保存用户问题和 AI 最终回复。

## 验证刷新后历史仍然存在

1. 前端登录。
2. 创建或选择一个对话并发送消息。
3. 刷新浏览器页面。
4. 前端会用本地 JWT 调用 `/api/auth/me`，再加载 `/api/conversations` 和消息历史。

## 验证后端重启后历史仍然存在

1. 发送几条消息。
2. 停止并重启 `uvicorn`。
3. 重新打开前端或重新登录。
4. 会话列表和消息会从 SQLite `data/app.db` 恢复。

## 当前已完成

- FastAPI 后端
- CORS
- health 接口
- 注册 / 登录 / 当前用户 / 退出接口
- JWT Bearer 鉴权
- SQLite + SQLAlchemy 持久化
- 会话列表、创建、删除、消息查询
- `/api/ai/chat` SSE 兼容接口
- OpenAI-compatible 流式模型调用
- `conversationId` 持久化消息历史
- legacy `memoryId` 进程内会话兼容
- RAG 文档加载、切分、embedding、Chroma 索引和检索
- `/api/rag/search` 登录态调试检索接口
- 本地工具 `interviewQuestionSearch`
- `/api/tools/interview/search` 登录态调试接口
- BigModel MCP Web Search
- DuckDuckGo Web Search fallback
- `/api/tools/web/search` 登录态调试接口
- RAG / interviewQuestionSearch / Web Search 统一引用编号和“参考来源”输出约束

## 当前未完成

- Guardrail
- LangGraph checkpointer
- 生产部署
