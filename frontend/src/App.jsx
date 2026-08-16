import React, { useMemo, useState } from 'react'

function extractAssistantMessage(payload) {
  if (!payload) return ''
  if (typeof payload === 'string') return payload

  const directCandidates = [
    payload?.assistant_message,
    payload?.message,
    payload?.content,
    payload?.data?.choices?.[0]?.message?.content,
  ]

  for (const candidate of directCandidates) {
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
  }

  if (payload?.error || payload?.detail) {
    return typeof payload.error === 'string'
      ? payload.error
      : typeof payload.detail === 'string'
        ? payload.detail
        : ''
  }

  if (payload?.data?.error?.message) {
    return payload.data.error.message
  }

  return ''
}

const starterMessages = [
  { id: 1, role: 'assistant', content: 'Hello! I am Antigen. Ask me anything about your workspace or memories.' },
  { id: 2, role: 'user', content: 'Show me a polished interface for this app.' },
]

const conversations = [
  { id: 1, title: 'Product planning', preview: 'Summarize the launch checklist', active: true },
  { id: 2, title: 'Memory notes', preview: 'Search previous decisions', active: false },
  { id: 3, title: 'Settings', preview: 'Tune AI behavior', active: false },
]

export default function App() {
  const [messages, setMessages] = useState(starterMessages)
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [view, setView] = useState('chat')

  const isChatView = view === 'chat'
  const isSettingsView = view === 'settings'
  const isMemoryView = view === 'memory'

  async function send() {
    if (!text.trim()) return

    const nextUserMessage = { id: Date.now(), role: 'user', content: text }
    const nextMessages = [...messages, nextUserMessage]
    setMessages(nextMessages)
    setText('')
    setLoading(true)

    try {
      console.log('Sending chat request', { messages: nextMessages })
      const resp = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: nextMessages }),
      })

      const responseText = await resp.text()
      let data = null
      try {
        data = responseText ? JSON.parse(responseText) : null
      } catch (parseError) {
        console.error('Failed to parse chat response JSON', parseError)
        data = { error: responseText }
      }

      console.log('Chat response received', data)

      if (!resp.ok) {
        const detail = data?.detail || data?.error || responseText || `Request failed with status ${resp.status}`
        setMessages((m) => [...m, { id: Date.now() + 1, role: 'assistant', content: `Error: ${detail}` }])
        return
      }

      const assistant = extractAssistantMessage(data)
      if (!assistant) {
        setMessages((m) => [...m, { id: Date.now() + 2, role: 'assistant', content: 'Error: The backend returned no assistant message.' }])
      } else {
        setMessages((m) => [...m, { id: Date.now() + 3, role: 'assistant', content: assistant }])
      }
    } catch (e) {
      console.error('Chat request threw an exception', e)
      setMessages((m) => [...m, { id: Date.now() + 4, role: 'assistant', content: 'Error: ' + String(e) }])
    } finally {
      setLoading(false)
    }
  }

  const headerTitle = useMemo(() => {
    if (isSettingsView) return 'Settings'
    if (isMemoryView) return 'Memory'
    return 'Antigen Chat'
  }, [isSettingsView, isMemoryView])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">A</div>
          <div>
            <h2>Antigen</h2>
            <p>Local assistant</p>
          </div>
        </div>

        <nav className="nav-list">
          <button className={isChatView ? 'nav-item active' : 'nav-item'} onClick={() => setView('chat')}>
            <span>💬</span> Chat
          </button>
          <button className={isMemoryView ? 'nav-item active' : 'nav-item'} onClick={() => setView('memory')}>
            <span>🧠</span> Memory
          </button>
          <button className={isSettingsView ? 'nav-item active' : 'nav-item'} onClick={() => setView('settings')}>
            <span>⚙️</span> Settings
          </button>
        </nav>

        <div className="conversation-list">
          <div className="list-title">Conversations</div>
          {conversations.map((item) => (
            <button key={item.id} className="conversation-item">
              <strong>{item.title}</strong>
              <span>{item.preview}</span>
            </button>
          ))}
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">AI workspace</p>
            <h1>{headerTitle}</h1>
          </div>
          <div className="topbar-actions">
            <button className="ghost-button">🌙</button>
            <button className="ghost-button">⏺</button>
          </div>
        </header>

        {isChatView ? (
          <>
            <section className="chat-window">
              {messages.map((message) => (
                <div key={message.id} className={`message-row ${message.role === 'user' ? 'user' : 'assistant'}`}>
                  <div className="avatar">{message.role === 'user' ? 'U' : 'A'}</div>
                  <div className="bubble">
                    <div className="message-meta">{message.role === 'user' ? 'You' : 'Antigen'}</div>
                    <div>{message.content}</div>
                  </div>
                </div>
              ))}
              {loading && (
                <div className="message-row assistant">
                  <div className="avatar">A</div>
                  <div className="bubble typing">
                    <span /> <span /> <span />
                  </div>
                </div>
              )}
            </section>

            <form className="composer" onSubmit={(e) => { e.preventDefault(); send() }}>
              <button type="button" className="icon-button">🎙️</button>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Ask Antigen anything..."
                rows={1}
              />
              <button type="submit" className="send-button" disabled={loading}>
                {loading ? '…' : 'Send'}
              </button>
            </form>
          </>
        ) : null}

        {isMemoryView ? (
          <section className="content-card">
            <h2>Memory center</h2>
            <p>Store, review, and retrieve important notes from your assistant.</p>
            <div className="memory-list">
              <div className="memory-item">
                <strong>Weekly review</strong>
                <span>Remember to check the budget report on Friday.</span>
              </div>
              <div className="memory-item">
                <strong>Launch note</strong>
                <span>Prioritize onboarding improvements before release.</span>
              </div>
            </div>
          </section>
        ) : null}

        {isSettingsView ? (
          <section className="content-card">
            <h2>Settings</h2>
            <p>Personalize the agent experience for your workflow.</p>
            <div className="settings-grid">
              <div className="setting-card">
                <h3>Theme</h3>
                <p>Dark mode is enabled by default.</p>
              </div>
              <div className="setting-card">
                <h3>Voice</h3>
                <p>Microphone input is ready for quick prompts.</p>
              </div>
              <div className="setting-card">
                <h3>Memory</h3>
                <p>Save useful context for future conversations.</p>
              </div>
            </div>
          </section>
        ) : null}
      </main>
    </div>
  )
}
