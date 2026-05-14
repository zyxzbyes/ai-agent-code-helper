const REFERENCE_HEADING_RE = /(^|\n)\s*(?:-{3,}\s*\n)?\s*(?:📚\s*)?参考来源\s*[:：]?\s*/m
const INLINE_CITATION_RE = /\s*\[(\d{1,3})\]/g
const DETAILED_SOURCE_RE = /\[(\d{1,3})\]\s*([^\[]+)/g
const URL_RE = /(https?:\/\/[^\s)）]+)/

export function parseAssistantMessage(message, explicitSources = []) {
  const text = String(message || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim()
  const normalizedSources = normalizeSources(explicitSources)
  if (!text) {
    return {
      body: '',
      sources: normalizedSources
    }
  }

  const match = REFERENCE_HEADING_RE.exec(text)
  if (!match) {
    return {
      body: stripInlineCitations(text),
      sources: normalizedSources
    }
  }

  const headingIndex = match.index + (match[1] ? match[1].length : 0)
  const body = text.slice(0, headingIndex).trim()
  const sourceText = text.slice(match.index + match[0].length).trim()
  const sources = normalizedSources.length ? normalizedSources : extractSources(sourceText)

  return {
    body: stripInlineCitations(body),
    sources
  }
}

export function normalizeSources(rawSources = []) {
  if (!Array.isArray(rawSources)) return []

  return rawSources
    .map((source, index) => {
      if (typeof source === 'string') {
        return normalizeSourceItem({
          index: index + 1,
          text: source
        })
      }

      if (!source || typeof source !== 'object') return null

      const sourceText = source.text ||
        source.source ||
        source.title ||
        source.name ||
        source.fileName ||
        source.file_name ||
        ''
      const url = source.url || source.link || source.href || ''

      return normalizeSourceItem({
        index: source.index || source.number || index + 1,
        text: url ? `${sourceText} - ${url}` : sourceText
      })
    })
    .filter(Boolean)
}

function extractSources(sourceText) {
  const sources = []
  const normalized = String(sourceText || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  let match

  while ((match = DETAILED_SOURCE_RE.exec(normalized)) !== null) {
    const source = normalizeSourceItem({
      index: match[1],
      text: match[2]
    })
    if (source) {
      sources.push(source)
    }
  }

  return sources
}

function stripInlineCitations(text) {
  return text
    .replace(INLINE_CITATION_RE, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function normalizeSourceItem(source) {
  const index = String(source.index || '').trim()
  const text = String(source.text || '').replace(/\s+/g, ' ').trim()

  if (!index || !text || isPureReferenceText(text)) {
    return null
  }

  const urlMatch = URL_RE.exec(text)
  return {
    index,
    text,
    url: urlMatch ? urlMatch[1] : ''
  }
}

function isPureReferenceText(text) {
  const normalized = String(text || '').replace(/\s+/g, '')
  if (!normalized) return true
  return /^(\[\d{1,3}\])+$/.test(normalized) || /^\d{1,3}$/.test(normalized)
}
