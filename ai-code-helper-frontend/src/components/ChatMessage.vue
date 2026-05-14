<template>
  <div class="chat-message" :class="{ 'user-message': isUser, 'ai-message': !isUser }">
    <div class="message-avatar">
      <div class="avatar" :class="{ 'user-avatar': isUser, 'ai-avatar': !isUser }">
        {{ isUser ? '我' : 'AI' }}
      </div>
    </div>
    <div class="message-content">
      <div class="message-bubble">
        <!-- 用户消息使用普通文本 -->
        <pre v-if="isUser" class="message-text">{{ message }}</pre>
        <!-- AI回复使用Markdown渲染 -->
        <template v-else>
          <div class="message-markdown" v-html="renderedMessage"></div>
          <div v-if="parsedMessage.sources.length" class="source-panel">
            <button class="source-toggle" type="button" @click="sourcesExpanded = !sourcesExpanded">
              📚 参考来源（可展开）
            </button>
            <div v-if="sourcesExpanded" class="source-list">
              <div
                v-for="source in parsedMessage.sources"
                :key="source.index + source.text"
                class="source-item"
              >
                <span class="source-index">[{{ source.index }}]</span>
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
        </template>
      </div>
      <div class="message-time">{{ formatTime(timestamp) }}</div>
    </div>
  </div>
</template>

<script>
import { formatTime } from '../utils/index.js'
import { parseAssistantMessage } from '../utils/sourceParser.js'
import { marked } from 'marked'

export default {
  name: 'ChatMessage',
  props: {
    message: {
      type: String,
      required: true
    },
    isUser: {
      type: Boolean,
      default: false
    },
    timestamp: {
      type: [Date, String],
      default: () => new Date()
    },
    sources: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      sourcesExpanded: false
    }
  },
  computed: {
    parsedMessage() {
      if (this.isUser) {
        return {
          body: this.message,
          sources: []
        }
      }
      return parseAssistantMessage(this.message, this.sources)
    },
    renderedMessage() {
      if (this.isUser) {
        return this.message
      }
      // 配置marked选项
      marked.setOptions({
        breaks: true, // 支持换行
        gfm: true, // 支持GitHub风格的Markdown
        sanitize: false, // 不过滤HTML（根据需要可以开启）
        highlight: function(code, lang) {
          // 可以在这里添加代码高亮功能
          return code
        }
      })
      return marked(this.parsedMessage.body)
    }
  },
  methods: {
    formatTime,
    sourceTextWithoutUrl(source) {
      return source.text.replace(source.url, '').replace(/\s*-\s*$/, '').trim()
    }
  }
}
</script>

<style scoped>
.chat-message {
  display: flex;
  margin-bottom: 20px;
  padding: 0 20px;
}

.user-message {
  justify-content: flex-end;
  flex-direction: row;
}

.user-message .message-avatar {
  order: 2;
}

.user-message .message-content {
  order: 1;
}

.ai-message {
  justify-content: flex-start;
  flex-direction: row;
}

.ai-message .message-avatar {
  order: 1;
}

.ai-message .message-content {
  order: 2;
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
  color: white;
}

.user-avatar {
  background-color: #007bff;
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
  position: relative;
  word-wrap: break-word;
  word-break: break-word;
}

.user-message .message-bubble {
  background-color: #007bff;
  color: white;
  border-bottom-right-radius: 4px;
}

.ai-message .message-bubble {
  background-color: #f1f3f4;
  color: #333;
  border-bottom-left-radius: 4px;
}

.message-text {
  font-family: inherit;
  font-size: 14px;
  line-height: 1.4;
  white-space: pre-wrap;
  margin: 0;
}

/* Markdown样式 */
.message-markdown {
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
}

.message-markdown h1,
.message-markdown h2,
.message-markdown h3,
.message-markdown h4,
.message-markdown h5,
.message-markdown h6 {
  margin: 0.5em 0;
  font-weight: bold;
}

.message-markdown h1 { font-size: 1.5em; }
.message-markdown h2 { font-size: 1.3em; }
.message-markdown h3 { font-size: 1.2em; }
.message-markdown h4 { font-size: 1.1em; }
.message-markdown h5 { font-size: 1em; }
.message-markdown h6 { font-size: 0.9em; }

.message-markdown p {
  margin: 0.5em 0;
}

.message-markdown ul,
.message-markdown ol {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.message-markdown li {
  margin: 0.2em 0;
}

.message-markdown code {
  background-color: rgba(0, 0, 0, 0.1);
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.9em;
}

.user-message .message-markdown code {
  background-color: rgba(255, 255, 255, 0.2);
}

.message-markdown pre {
  background-color: rgba(0, 0, 0, 0.1);
  padding: 1em;
  border-radius: 5px;
  overflow-x: auto;
  margin: 0.5em 0;
}

.user-message .message-markdown pre {
  background-color: rgba(255, 255, 255, 0.2);
}

.message-markdown pre code {
  background-color: transparent;
  padding: 0;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.9em;
}

.message-markdown blockquote {
  border-left: 4px solid #ccc;
  padding-left: 1em;
  margin: 0.5em 0;
  font-style: italic;
  color: #666;
}

.user-message .message-markdown blockquote {
  border-left-color: rgba(255, 255, 255, 0.5);
  color: rgba(255, 255, 255, 0.8);
}

.message-markdown a {
  color: #007bff;
  text-decoration: underline;
}

.user-message .message-markdown a {
  color: #b3d9ff;
}

.message-markdown table {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5em 0;
}

.message-markdown th,
.message-markdown td {
  border: 1px solid #ddd;
  padding: 0.5em;
  text-align: left;
}

.message-markdown th {
  background-color: #f2f2f2;
  font-weight: bold;
}

.user-message .message-markdown th {
  background-color: rgba(255, 255, 255, 0.2);
}

.message-markdown hr {
  border: none;
  border-top: 1px solid #ddd;
  margin: 1em 0;
}

.source-panel {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #d8dee6;
}

.source-toggle {
  border: none;
  background: transparent;
  color: #475467;
  padding: 0;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.source-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 100%;
}

.source-item {
  color: #475467;
  font-size: 12px;
  line-height: 1.45;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.source-index {
  font-weight: 600;
  margin-right: 4px;
}

.source-item a {
  color: #2563eb;
  text-decoration: underline;
  overflow-wrap: anywhere;
}

.user-message .message-markdown hr {
  border-top-color: rgba(255, 255, 255, 0.3);
}

.message-time {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
  padding: 0 4px;
}

.user-message .message-time {
  text-align: right;
}

.ai-message .message-time {
  text-align: left;
}

@media (max-width: 768px) {
  .message-content {
    max-width: 85%;
  }
  
  .chat-message {
    padding: 0 10px;
  }
}
</style> 
