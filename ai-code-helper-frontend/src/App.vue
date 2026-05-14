<template>
  <div class="app">
    <section v-if="!user" class="auth-page">
      <form class="auth-card" @submit.prevent="handleAuthSubmit">
        <div class="auth-brand">
          <div class="auth-logo">AI</div>
          <h1>AI 编程小助手</h1>
          <p>登录后继续你的学习与求职对话</p>
        </div>

        <div class="auth-tabs">
          <button
            type="button"
            :class="{ active: authMode === 'login' }"
            @click="switchAuthMode('login')"
          >
            登录
          </button>
          <button
            type="button"
            :class="{ active: authMode === 'register' }"
            @click="switchAuthMode('register')"
          >
            注册
          </button>
        </div>

        <label class="field">
          <span>用户名</span>
          <input
            v-model.trim="authForm.username"
            autocomplete="username"
            placeholder="请输入用户名"
            :disabled="authLoading"
          />
        </label>

        <label class="field">
          <span>密码</span>
          <input
            v-model="authForm.password"
            type="password"
            autocomplete="current-password"
            placeholder="至少 6 位"
            :disabled="authLoading"
          />
        </label>

        <div v-if="authError" class="form-error">{{ authError }}</div>

        <button class="primary-button" type="submit" :disabled="authLoading">
          {{ authLoading ? '处理中...' : authMode === 'login' ? '登录' : '注册并登录' }}
        </button>
      </form>
    </section>

    <section v-else class="chat-shell">
      <aside class="sidebar">
        <div class="sidebar-header">
          <div class="app-mark">AI</div>
          <div>
            <h1>AI 编程小助手</h1>
            <p>学习路线 · 面试准备 · 代码答疑</p>
          </div>
        </div>

        <button class="new-chat-button" @click="createNewChat">
          <span>+</span>
          新对话
        </button>

        <div class="conversation-list">
          <div
            v-for="conversation in conversations"
            :key="conversation.id"
            class="conversation-row"
            :class="{ active: conversation.id === currentConversationId }"
          >
            <button class="conversation-item" @click="selectConversation(conversation.id)">
              <span class="conversation-title">{{ conversation.title }}</span>
              <span class="conversation-time">{{ formatConversationTime(conversation) }}</span>
            </button>
            <button
              class="conversation-delete"
              title="删除对话"
              @click.stop="removeConversation(conversation.id)"
            >
              ×
            </button>
          </div>
        </div>
      </aside>

      <main class="chat-main">
        <header class="topbar">
          <div>
            <h2>{{ currentConversationTitle }}</h2>
            <p>历史消息已保存到本地 SQLite 数据库</p>
          </div>
          <div class="user-area">
            <span>{{ user.username }}</span>
            <button @click="handleLogout">退出登录</button>
          </div>
        </header>

        <div class="messages-container" ref="messagesContainer">
          <div v-if="messages.length === 0 && !isStreaming" class="empty-state">
            <h3>开始一段新对话</h3>
            <p>可以问我编程学习路线、项目准备、简历优化或面试题。</p>
          </div>

          <ChatMessage
            v-for="message in messages"
            :key="message.id"
            :message="message.content"
            :is-user="message.isUser"
            :timestamp="message.timestamp"
            :sources="message.sources"
          />

          <div v-if="isStreaming" class="chat-message ai-message streaming-message">
            <div class="message-avatar">
              <div class="avatar ai-avatar">AI</div>
            </div>
            <div class="message-content">
              <div class="message-bubble">
                  <div class="ai-typing-content">
                  <div class="ai-response-text message-markdown" v-html="currentAiResponseRendered"></div>
                  <div v-if="currentAiSources.length" class="stream-source-panel">
                    <button
                      class="stream-source-toggle"
                      type="button"
                      @click="streamSourcesExpanded = !streamSourcesExpanded"
                    >
                      📚 参考来源（可展开）
                    </button>
                    <div v-if="streamSourcesExpanded" class="stream-source-list">
                      <div
                        v-for="source in currentAiSources"
                        :key="source.index + source.text"
                        class="stream-source-item"
                      >
                        <span class="stream-source-index">[{{ source.index }}]</span>
                        <template v-if="source.url">
                          <span>{{ sourceTextWithoutUrl(source) }}</span>
                          <a :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.url }}</a>
                        </template>
                        <template v-else>
                          <span>{{ source.text }}</span>
                        </template>
                      </div>
                    </div>
                  </div>
                  <LoadingDots />
                </div>
              </div>
            </div>
          </div>
        </div>

        <ChatInput
          :disabled="isStreaming || !currentConversationId"
          :streaming="isStreaming"
          @send-message="sendMessage"
          @stop-generation="stopGeneration"
          placeholder="请输入你的编程问题..."
        />
      </main>
    </section>

    <div v-if="errorMessage" class="toast">
      {{ errorMessage }}
    </div>
  </div>
</template>

<script>
import ChatMessage from './components/ChatMessage.vue'
import ChatInput from './components/ChatInput.vue'
import LoadingDots from './components/LoadingDots.vue'
import {
  createConversation,
  deleteConversation,
  getConversationMessages,
  getConversations,
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
  streamConversationChat
} from './api/chatApi.js'
import { formatTime } from './utils/index.js'
import { parseAssistantMessage } from './utils/sourceParser.js'
import { marked } from 'marked'

const TOKEN_STORAGE_KEY = 'ai-code-helper-token'

export default {
  name: 'App',
  components: {
    ChatMessage,
    ChatInput,
    LoadingDots
  },
  data() {
    return {
      token: window.localStorage.getItem(TOKEN_STORAGE_KEY) || '',
      user: null,
      authMode: 'login',
      authForm: {
        username: '',
        password: ''
      },
      authError: '',
      authLoading: false,
      appLoading: false,
      conversations: [],
      currentConversationId: null,
      messages: [],
      isSending: false,
      isStreaming: false,
      currentAiResponse: '',
      currentAiSourcesFromStream: [],
      currentAssistantMessageId: null,
      streamSourcesExpanded: false,
      streamController: null,
      activeStreamConversationId: null,
      errorMessage: ''
    }
  },
  computed: {
    currentConversationTitle() {
      const conversation = this.conversations.find((item) => item.id === this.currentConversationId)
      return conversation ? conversation.title : '新对话'
    },
    currentAiResponseRendered() {
      if (!this.currentAiResponse) return ''
      marked.setOptions({
        breaks: true,
        gfm: true,
        sanitize: false
      })
      return marked(this.parsedCurrentAiResponse.body)
    },
    parsedCurrentAiResponse() {
      return parseAssistantMessage(this.currentAiResponse, this.currentAiSourcesFromStream)
    },
    currentAiSources() {
      return this.parsedCurrentAiResponse.sources
    }
  },
  methods: {
    async bootstrap() {
      if (!this.token) return
      this.appLoading = true
      try {
        this.user = await getCurrentUser(this.token)
        await this.loadConversations()
      } catch (error) {
        this.handleAuthExpired()
      } finally {
        this.appLoading = false
      }
    },

    switchAuthMode(mode) {
      this.authMode = mode
      this.authError = ''
    },

    async handleAuthSubmit() {
      this.authError = ''
      if (!this.authForm.username.trim()) {
        this.authError = '用户名不能为空'
        return
      }
      if (this.authForm.password.length < 6) {
        this.authError = '密码长度至少 6 位'
        return
      }

      this.authLoading = true
      try {
        const payload = {
          username: this.authForm.username.trim(),
          password: this.authForm.password
        }
        const data = this.authMode === 'login'
          ? await loginUser(payload)
          : await registerUser(payload)

        this.token = data.token
        this.user = data.user
        window.localStorage.setItem(TOKEN_STORAGE_KEY, this.token)
        this.authForm.password = ''
        await this.loadConversations()
      } catch (error) {
        this.authError = error.message || '操作失败，请稍后重试'
      } finally {
        this.authLoading = false
      }
    },

    async loadConversations() {
      this.conversations = await getConversations(this.token)
      if (this.conversations.length === 0) {
        await this.createNewChat()
        return
      }

      const firstConversation = this.conversations[0]
      this.currentConversationId = firstConversation.id
      await this.loadMessages(firstConversation.id)
    },

    async createNewChat() {
      this.abortCurrentStream({ keepPartial: true })
      try {
        const conversation = await createConversation(this.token, '新对话')
        this.conversations = [
          conversation,
          ...this.conversations.filter((item) => item.id !== conversation.id)
        ]
        this.currentConversationId = conversation.id
        this.messages = []
        this.currentAiResponse = ''
        this.currentAiSourcesFromStream = []
      } catch (error) {
        this.handleRequestError(error, '创建新对话失败')
      }
    },

    async selectConversation(conversationId) {
      if (conversationId === this.currentConversationId) return
      this.abortCurrentStream({ keepPartial: true })
      this.currentConversationId = conversationId
      this.currentAiResponse = ''
      this.currentAiSourcesFromStream = []
      await this.loadMessages(conversationId)
    },

    async loadMessages(conversationId) {
      try {
        const messages = await getConversationMessages(this.token, conversationId)
        if (conversationId !== this.currentConversationId) return
        this.messages = messages.map(this.normalizeMessage)
        this.scrollToBottom()
      } catch (error) {
        this.handleRequestError(error, '加载历史消息失败')
      }
    },

    async removeConversation(conversationId) {
      this.abortCurrentStream({ keepPartial: true })
      try {
        await deleteConversation(this.token, conversationId)
        this.conversations = this.conversations.filter((item) => item.id !== conversationId)
        if (conversationId === this.currentConversationId) {
          this.messages = []
          const nextConversation = this.conversations[0]
          if (nextConversation) {
            this.currentConversationId = nextConversation.id
            await this.loadMessages(nextConversation.id)
          } else {
            await this.createNewChat()
          }
        }
      } catch (error) {
        this.handleRequestError(error, '删除对话失败')
      }
    },

    async sendMessage(message) {
      if (!this.user || !this.currentConversationId || this.isSending) return

      const conversationId = this.currentConversationId
      const userMessage = {
        id: `local-user-${Date.now()}`,
        content: message,
        isUser: true,
        timestamp: new Date()
      }
      this.messages.push(userMessage)
      this.scrollToBottom()

      this.abortCurrentStream({ keepPartial: true })
      const controller = new AbortController()
      this.streamController = controller
      this.activeStreamConversationId = conversationId
      this.isSending = true
      this.isStreaming = true
      this.currentAiResponse = ''
      this.currentAiSourcesFromStream = []
      this.streamSourcesExpanded = false
      this.currentAssistantMessageId = `local-assistant-${Date.now()}`
      this.errorMessage = ''

      let assistantText = ''
      try {
        await streamConversationChat({
          token: this.token,
          conversationId,
          message,
          signal: controller.signal,
          onMessage: (chunk) => {
            if (this.activeStreamConversationId !== conversationId) return
            assistantText += chunk
            this.currentAiResponse = assistantText
            this.scrollToBottom()
          },
          onSources: (sources) => {
            if (this.activeStreamConversationId !== conversationId) return
            this.currentAiSourcesFromStream = sources
            this.scrollToBottom()
          }
        })

        if (this.activeStreamConversationId === conversationId && assistantText.trim()) {
          this.messages.push({
            id: `local-assistant-${Date.now()}`,
            content: assistantText.trim(),
            isUser: false,
            timestamp: new Date(),
            sources: this.currentAiSourcesFromStream.length
              ? this.currentAiSourcesFromStream
              : parseAssistantMessage(assistantText.trim()).sources
          })
          await this.refreshConversations()
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          this.handleRequestError(error, '聊天失败')
        }
      } finally {
        if (this.activeStreamConversationId === conversationId) {
          this.finishStreamingState()
        }
      }
    },

    async refreshConversations() {
      try {
        const conversations = await getConversations(this.token)
        this.conversations = conversations
      } catch (error) {
        this.handleRequestError(error, '刷新会话列表失败')
      }
    },

    normalizeMessage(message) {
      return {
        id: message.id,
        content: message.content,
        isUser: message.role === 'user',
        timestamp: message.createdAt || new Date(),
        sources: message.sources || message.toolSources || message.tool_sources || []
      }
    },

    stopGeneration() {
      this.abortCurrentStream({ keepPartial: true })
    },

    abortCurrentStream({ keepPartial = false } = {}) {
      if (keepPartial) {
        this.commitPartialAssistantMessage()
      }
      if (this.streamController) {
        this.streamController.abort()
      }
      this.finishStreamingState()
    },

    commitPartialAssistantMessage() {
      const content = this.currentAiResponse.trim()
      if (!content || !this.activeStreamConversationId) return
      if (this.activeStreamConversationId !== this.currentConversationId) return

      this.messages.push({
        id: this.currentAssistantMessageId || `local-assistant-${Date.now()}`,
        content,
        isUser: false,
        timestamp: new Date(),
        sources: this.currentAiSourcesFromStream.length
          ? this.currentAiSourcesFromStream
          : parseAssistantMessage(content).sources
      })
      this.scrollToBottom()
    },

    finishStreamingState() {
      this.streamController = null
      this.activeStreamConversationId = null
      this.isSending = false
      this.isStreaming = false
      this.currentAiResponse = ''
      this.currentAiSourcesFromStream = []
      this.currentAssistantMessageId = null
      this.streamSourcesExpanded = false
    },

    async handleLogout() {
      this.abortCurrentStream({ keepPartial: true })
      try {
        if (this.token) {
          await logoutUser(this.token)
        }
      } catch (error) {
        console.warn('退出登录接口调用失败:', error)
      }
      this.clearSession()
    },

    handleAuthExpired() {
      this.clearSession()
      this.authError = '登录状态已失效，请重新登录'
    },

    clearSession() {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY)
      this.token = ''
      this.user = null
      this.conversations = []
      this.currentConversationId = null
      this.messages = []
      this.currentAiResponse = ''
      this.currentAiSourcesFromStream = []
      this.currentAssistantMessageId = null
      this.streamSourcesExpanded = false
    },

    handleRequestError(error, fallbackMessage) {
      if (error.status === 401) {
        this.handleAuthExpired()
        return
      }
      this.errorMessage = error.message || fallbackMessage
      setTimeout(() => {
        this.errorMessage = ''
      }, 5000)
    },

    formatConversationTime(conversation) {
      if (!conversation) return ''
      return formatTime(conversation.updatedAt || conversation.createdAt)
    },

    sourceTextWithoutUrl(source) {
      return source.text.replace(source.url, '').replace(/\s*-\s*$/, '').trim()
    },

    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$refs.messagesContainer
        if (container) {
          container.scrollTop = container.scrollHeight
        }
      })
    }
  },

  mounted() {
    this.bootstrap()
  },

  beforeUnmount() {
    this.abortCurrentStream()
  }
}
</script>

<style scoped>
.app {
  height: 100vh;
  overflow: hidden;
  background: #f6f7f9;
  color: #1f2933;
}

:global(html),
:global(body),
:global(#app) {
  height: 100%;
  overflow: hidden;
}

:global(body) {
  margin: 0;
}

.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: #eef2f6;
}

.auth-card {
  width: min(420px, 100%);
  background: #fff;
  border: 1px solid #dce3ea;
  border-radius: 8px;
  padding: 28px;
  box-shadow: 0 18px 42px rgba(31, 41, 51, 0.12);
}

.auth-brand {
  text-align: center;
  margin-bottom: 22px;
}

.auth-logo,
.app-mark {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #2563eb;
  color: #fff;
  font-weight: 700;
}

.auth-brand h1,
.sidebar-header h1 {
  margin: 12px 0 6px;
  font-size: 22px;
}

.auth-brand p,
.sidebar-header p,
.topbar p {
  margin: 0;
  color: #697586;
  font-size: 13px;
}

.auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 18px;
}

.auth-tabs button,
.user-area button,
.conversation-delete {
  border: 1px solid #d5dde5;
  background: #fff;
  color: #344054;
  border-radius: 6px;
  cursor: pointer;
}

.auth-tabs button {
  padding: 10px 0;
  font-weight: 600;
}

.auth-tabs button.active {
  background: #e8f0ff;
  border-color: #2563eb;
  color: #1d4ed8;
}

.field {
  display: block;
  margin-bottom: 14px;
}

.field span {
  display: block;
  margin-bottom: 6px;
  color: #344054;
  font-size: 13px;
  font-weight: 600;
}

.field input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #d5dde5;
  border-radius: 6px;
  padding: 12px;
  outline: none;
  font-size: 14px;
}

.field input:focus {
  border-color: #2563eb;
}

.primary-button,
.new-chat-button {
  border: none;
  border-radius: 6px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
  font-weight: 700;
}

.primary-button {
  width: 100%;
  padding: 12px;
}

.primary-button:disabled,
.new-chat-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-error {
  margin-bottom: 12px;
  padding: 10px;
  border-radius: 6px;
  background: #fff1f2;
  color: #be123c;
  font-size: 13px;
}

.chat-shell {
  height: 100vh;
  display: flex;
  overflow: hidden;
}

.sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #111827;
  color: #fff;
  padding: 16px;
}

.sidebar-header {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 18px;
}

.sidebar-header h1 {
  color: #fff;
  font-size: 16px;
  margin: 0 0 4px;
}

.sidebar-header p {
  color: #9ca3af;
}

.new-chat-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 11px 12px;
  margin-bottom: 14px;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.conversation-row {
  display: grid;
  grid-template-columns: 1fr 32px;
  gap: 6px;
  border-radius: 6px;
}

.conversation-row.active {
  background: rgba(255, 255, 255, 0.1);
}

.conversation-item {
  min-width: 0;
  border: none;
  background: transparent;
  color: #e5e7eb;
  text-align: left;
  padding: 10px 8px;
  cursor: pointer;
}

.conversation-title {
  display: block;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 14px;
}

.conversation-time {
  display: block;
  color: #9ca3af;
  font-size: 12px;
  margin-top: 3px;
}

.conversation-delete {
  width: 28px;
  height: 28px;
  align-self: center;
  background: transparent;
  color: #9ca3af;
  border-color: transparent;
}

.conversation-delete:hover {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.24);
}

.chat-main {
  min-width: 0;
  flex: 1;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f6f7f9;
}

.topbar {
  min-height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 24px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.topbar h2 {
  margin: 0 0 4px;
  font-size: 18px;
}

.user-area {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
}

.user-area button {
  padding: 7px 10px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  width: 100%;
  box-sizing: border-box;
  padding: 24px 0;
}

.messages-container :deep(.chat-message),
.streaming-message {
  width: min(900px, 100%);
  box-sizing: border-box;
  margin-left: auto;
  margin-right: auto;
}

.empty-state {
  margin: 20vh auto 0;
  text-align: center;
  color: #667085;
}

.empty-state h3 {
  margin-bottom: 8px;
  color: #1f2933;
}

.streaming-message {
  display: flex;
  margin-bottom: 20px;
  padding: 0 20px;
}

.message-avatar {
  display: flex;
  align-items: flex-start;
  margin: 0 10px;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: bold;
  color: #fff;
}

.ai-avatar {
  background-color: #6c757d;
}

.message-content {
  max-width: 70%;
  min-width: 100px;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 18px;
  word-wrap: break-word;
  word-break: break-word;
  background-color: #f1f3f4;
  color: #333;
  border-bottom-left-radius: 4px;
}

.ai-typing-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-response-text {
  font-size: 14px;
  line-height: 1.5;
}

.stream-source-panel {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #d8dee6;
}

.stream-source-toggle {
  border: none;
  background: transparent;
  color: #475467;
  padding: 0;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.stream-source-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 100%;
}

.stream-source-item {
  color: #475467;
  font-size: 12px;
  line-height: 1.45;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.stream-source-index {
  font-weight: 600;
  margin-right: 4px;
}

.stream-source-item a {
  color: #2563eb;
  text-decoration: underline;
  overflow-wrap: anywhere;
}

.toast {
  position: fixed;
  top: 18px;
  left: 50%;
  transform: translateX(-50%);
  max-width: min(520px, calc(100vw - 32px));
  background: #b42318;
  color: #fff;
  padding: 10px 14px;
  border-radius: 6px;
  z-index: 10;
  box-shadow: 0 10px 28px rgba(180, 35, 24, 0.24);
}

@media (max-width: 768px) {
  .chat-shell {
    flex-direction: column;
  }

  .sidebar {
    width: auto;
    max-height: 230px;
  }

  .topbar {
    padding: 12px;
  }

  .messages-container {
    padding: 16px 0;
  }
}
</style>
