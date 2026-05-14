# AI 编程小助手 - 前端项目

这是基于 Vue 3 + Vite 的 AI 编程小助手前端。第二阶段已经加入登录注册、会话列表、历史消息加载和流式聊天。

## 配置后端地址

复制或创建 `.env`：

```env
VITE_API_BASE_URL=http://localhost:8000
```

`.env.example` 已提供同样的示例值。

## 安装依赖

```bash
cd D:\agent\ai-code-helper-master\ai-code-helper-frontend
npm install
```

## 启动前端

```bash
npm run dev
```

默认访问：

```text
http://localhost:3000
```

## 构建

```bash
npm run build
```

## 功能说明

- 未登录时显示登录 / 注册卡片。
- 登录或注册成功后，JWT token 会保存到 `localStorage`。
- 已登录时进入聊天主界面。
- 左侧显示“新对话”按钮和历史对话列表。
- 点击历史对话会加载该会话的消息。
- 发送消息使用 `fetch + ReadableStream` 请求后端 SSE，并通过 `Authorization: Bearer <token>` 鉴权。
- 后端返回的 `data:` SSE 片段会被前端解析，不会在页面显示 `data:` 或 `[DONE]`。
- 刷新页面后会通过 `/api/auth/me` 恢复登录态，并重新加载当前用户自己的会话列表。

## 后端依赖

请先启动 Python 后端：

```bash
cd D:\agent\python-backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 新对话和历史对话

- 点击“新对话”会调用 `POST /api/conversations`。
- 发送消息时会调用 `GET /api/ai/chat?conversationId=...&message=...`。
- 关闭或刷新浏览器后，只要 token 仍有效，就会继续显示该用户自己的历史对话。
