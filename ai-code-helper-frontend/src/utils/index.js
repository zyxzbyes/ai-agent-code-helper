const MEMORY_ID_STORAGE_KEY = 'ai-code-helper-memory-id'

/**
 * 生成聊天室ID
 * @returns {number} 适合int范围的聊天室ID
 */
export function generateMemoryId() {
    // 使用当前时间戳的后9位，确保在int范围内
    return Math.floor(Date.now() % 1000000000)
}

/**
 * 获取已保存的聊天室ID；没有可用ID时创建并保存一个新的。
 * @returns {number} 聊天室ID
 */
export function getOrCreateMemoryId() {
    const storedMemoryId = window.localStorage.getItem(MEMORY_ID_STORAGE_KEY)
    const parsedMemoryId = Number.parseInt(storedMemoryId, 10)
    
    if (Number.isInteger(parsedMemoryId) && parsedMemoryId > 0) {
        return parsedMemoryId
    }
    
    const memoryId = generateMemoryId()
    saveMemoryId(memoryId)
    return memoryId
}

/**
 * 保存聊天室ID。
 * @param {number} memoryId 聊天室ID
 */
export function saveMemoryId(memoryId) {
    window.localStorage.setItem(MEMORY_ID_STORAGE_KEY, String(memoryId))
}

/**
 * 清除已保存的聊天室ID，新会话逻辑可复用该函数。
 */
export function clearMemoryId() {
    window.localStorage.removeItem(MEMORY_ID_STORAGE_KEY)
}

/**
 * 格式化时间
 * @param {Date} date 日期对象
 * @returns {string} 格式化后的时间字符串
 */
export function formatTime(value) {
    const date = parseApiDate(value)
    if (!date) return ''

    const now = new Date()
    const diff = Math.max(0, now - date)
    
    if (diff < 60000) { // 1分钟内
        return '刚刚'
    } else if (diff < 3600000) { // 1小时内
        return `${Math.floor(diff / 60000)}分钟前`
    } else if (diff < 86400000) { // 1天内
        return `${Math.floor(diff / 3600000)}小时前`
    } else {
        return date.toLocaleDateString()
    }
}

export function parseApiDate(value) {
    if (!value) return null
    if (value instanceof Date) {
        return Number.isNaN(value.getTime()) ? null : value
    }

    if (typeof value === 'string') {
        const trimmed = value.trim()
        if (!trimmed) return null
        const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed)
        const normalized = hasTimezone ? trimmed : `${trimmed}Z`
        const parsed = new Date(normalized)
        return Number.isNaN(parsed.getTime()) ? null : parsed
    }

    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? null : parsed
}

/**
 * 防抖函数
 * @param {Function} func 要防抖的函数
 * @param {number} wait 等待时间
 * @returns {Function} 防抖后的函数
 */
export function debounce(func, wait) {
    let timeout
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout)
            func(...args)
        }
        clearTimeout(timeout)
        timeout = setTimeout(later, wait)
    }
} 
