// 配置 API 基础 URL
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

function authHeaders(token) {
    return token ? { Authorization: `Bearer ${token}` } : {}
}

async function parseJsonResponse(response) {
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
        const message = data.detail || data.message || `请求失败：${response.status}`
        const error = new Error(message)
        error.status = response.status
        throw error
    }
    return data.data
}

async function requestJson(path, options = {}) {
    const { token, headers, ...rest } = options
    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...rest,
        headers: {
            'Content-Type': 'application/json',
            ...authHeaders(token),
            ...headers
        }
    })
    return parseJsonResponse(response)
}

export function registerUser(payload) {
    return requestJson('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify(payload)
    })
}

export function loginUser(payload) {
    return requestJson('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify(payload)
    })
}

export function getCurrentUser(token) {
    return requestJson('/api/auth/me', { token })
}

export function logoutUser(token) {
    return requestJson('/api/auth/logout', {
        method: 'POST',
        token
    })
}

export function getConversations(token) {
    return requestJson('/api/conversations', { token })
}

export function createConversation(token, title = '新对话') {
    return requestJson('/api/conversations', {
        method: 'POST',
        token,
        body: JSON.stringify({ title })
    })
}

export function getConversationMessages(token, conversationId) {
    return requestJson(`/api/conversations/${conversationId}/messages`, { token })
}

export function deleteConversation(token, conversationId) {
    return requestJson(`/api/conversations/${conversationId}`, {
        method: 'DELETE',
        token
    })
}

export async function streamConversationChat({
    token,
    conversationId,
    message,
    signal,
    onMessage,
    onSources,
    onDone
}) {
    const params = new URLSearchParams({
        conversationId,
        message
    })
    const response = await fetch(`${API_BASE_URL}/api/ai/chat?${params}`, {
        method: 'GET',
        headers: authHeaders(token),
        signal
    })

    if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        const error = new Error(data.detail || data.message || `聊天请求失败：${response.status}`)
        error.status = response.status
        throw error
    }
    if (!response.body) {
        throw new Error('浏览器不支持流式响应')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    const handleEvent = (eventText) => {
        const eventName = eventText
            .split(/\r?\n/)
            .find((line) => line.startsWith('event:'))
            ?.slice(6)
            .trim() || 'message'
        const data = eventText
            .split(/\r?\n/)
            .filter((line) => line.startsWith('data:'))
            .map((line) => line.slice(5).replace(/^ /, ''))
            .join('\n')

        if (!data) return
        if (eventName === 'sources') {
            const payload = JSON.parse(data)
            onSources && onSources(Array.isArray(payload.sources) ? payload.sources : [])
            return
        }
        if (data === '[DONE]') {
            onDone && onDone()
            return 'done'
        }
        onMessage && onMessage(data)
    }

    while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        let boundaryIndex = buffer.indexOf('\n\n')

        while (boundaryIndex !== -1) {
            const eventText = buffer.slice(0, boundaryIndex)
            buffer = buffer.slice(boundaryIndex + 2)
            const result = handleEvent(eventText)
            if (result === 'done') return
            boundaryIndex = buffer.indexOf('\n\n')
        }
    }

    if (buffer.trim()) {
        handleEvent(buffer)
    }
    onDone && onDone()
}

/**
 * 检查后端服务是否可用
 * @returns {Promise<boolean>} 返回服务是否可用
 */
export async function checkServiceHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/health`, {
            timeout: 5000
        })
        return response.status === 200
    } catch (error) {
        console.error('服务健康检查失败:', error)
        return false
    }
}
