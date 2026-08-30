// Use environment variable for API base URL, fallback to localhost for development
// In production when served from same origin, use empty string for relative URLs
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

// In-memory token, mirrored to localStorage by AuthContext. Kept here (not
// re-read from localStorage on every call) so a logout takes effect
// instantly without racing a pending request.
let authToken = null
let onUnauthorized = null

export function setToken(token) {
  authToken = token
}

// AuthContext registers a callback here so that any request which comes
// back 401 (expired/invalid token) can immediately clear client-side auth
// state, instead of leaving the UI stuck showing a logged-in view.
export function setOnUnauthorized(fn) {
  onUnauthorized = fn
}

async function req(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  if (res.status === 401) {
    onUnauthorized?.()
  }

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      detail = body.detail || body.message || detail
    } catch {
      // ignore — no JSON body
    }
    throw new Error(detail)
  }
  return res.json()
}

function authHeaders() {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {}
}

async function handleVoiceResponse(res) {
  if (res.status === 401) {
    onUnauthorized?.()
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      detail = body.detail || body.message || detail
    } catch {
      // ignore — no JSON body
    }
    throw new Error(detail)
  }
  return res
}

// Uploads a recorded audio blob and returns the transcribed text.
// Not routed through req() because this needs a multipart body, not JSON.
export async function transcribeAudio(blob) {
  const form = new FormData()
  form.append('audio', blob, 'recording.webm')
  const res = await fetch(`${API_BASE}/voice/transcribe`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })
  const ok = await handleVoiceResponse(res)
  return ok.json() // { text }
}

// Sends text to be spoken and returns an audio Blob (audio/wav).
// Not routed through req() because the response is binary, not JSON.
export async function speakText(text, voice) {
  const res = await fetch(`${API_BASE}/voice/speak`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ text, voice: voice || undefined }),
  })
  const ok = await handleVoiceResponse(res)
  return ok.blob()
}

// Sends a chat message and streams the reply back token-by-token via
// onDelta(deltaText, fullTextSoFar), instead of waiting for the whole
// reply to generate before returning anything. Not routed through req()
// because the response body is a stream of NDJSON lines, not one JSON blob.
export async function streamChat(message, conversationId, model, onDelta) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ message, conversation_id: conversationId, model }),
  })

  if (res.status === 401) {
    onUnauthorized?.()
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      detail = body.detail || body.message || detail
    } catch {
      // ignore — no JSON body
    }
    throw new Error(detail)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let fullText = ''
  let resultConversationId = conversationId

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let newlineIndex
    while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, newlineIndex).trim()
      buffer = buffer.slice(newlineIndex + 1)
      if (!line) continue

      const chunk = JSON.parse(line)
      if (chunk.error) {
        throw new Error(chunk.error)
      }
      if (chunk.delta) {
        fullText += chunk.delta
        onDelta(chunk.delta, fullText)
      }
      if (chunk.done) {
        resultConversationId = chunk.conversation_id
      }
    }
  }

  return { conversationId: resultConversationId, reply: fullText }
}

export const api = {
  health: () => req('/health'),

  aiStatus: () => req('/ai/status'),

  // Auth endpoints
  register: (username, password, displayName, email) =>
    req('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, display_name: displayName, email }),
    }),

  login: (username, password) =>
    req('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  getMe: () => req('/auth/me'),

  sendChat: (message, conversationId, model) =>
    req('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId, model }),
    }),

  listConversations: () => req('/conversations?page=1&page_size=50'),

  getConversation: (id) => req(`/conversations/${id}`),

  deleteConversation: (id) => req(`/conversations/${id}`, { method: 'DELETE' }),

  listMemories: (search) =>
    req(`/memories?page=1&page_size=50${search ? `&search=${encodeURIComponent(search)}` : ''}`),

  createMemory: (type, content, tags) =>
    req('/memories', { method: 'POST', body: JSON.stringify({ type, content, tags }) }),

  deleteMemory: (id) => req(`/memories/${id}`, { method: 'DELETE' }),

  semanticSearchMemories: (query) =>
    req('/memories/semantic_search', { method: 'POST', body: JSON.stringify({ query }) }),

  listVoices: () => req('/voice/voices'),
}