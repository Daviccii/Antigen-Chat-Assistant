import React, { useState, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar.jsx'
import ChatView from './components/ChatView.jsx'
import VoiceView from './components/VoiceView.jsx'
import MemoryView from './components/MemoryView.jsx'
import SettingsView from './components/SettingsView.jsx'
import Login from './pages/Login.jsx'
import { useAuth } from './auth/AuthContext.jsx'
import { api } from './api.js'

export default function App() {
  const { isLoading, isAuthenticated, user, logout } = useAuth()

  const [view, setView] = useState('chat')
  const [online, setOnline] = useState(false)
  const [conversations, setConversations] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [model, setModel] = useState(() => localStorage.getItem('antigen_model') || 'ollama:llama3.2')

  useEffect(() => {
    localStorage.setItem('antigen_model', model)
  }, [model])

  // Poll backend health every 15s so the sidebar status stays accurate.
  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        await api.health()
        if (!cancelled) setOnline(true)
      } catch {
        if (!cancelled) setOnline(false)
      }
    }
    check()
    const id = setInterval(check, 15000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  const refreshConversations = useCallback(() => {
    if (!isAuthenticated) return
    api
      .listConversations()
      .then((data) => setConversations(data.items))
      .catch(() => {})
  }, [isAuthenticated])

  useEffect(() => {
    refreshConversations()
  }, [refreshConversations])

  function handleNewChat() {
    setConversationId(null)
    setView('chat')
  }

  // Still checking localStorage / validating a saved token — avoid flashing
  // the login screen before we know the answer.
  if (isLoading) {
    return (
      <div className="shell">
        <div className="main">
          <div className="empty" style={{ margin: 'auto' }}>
            Loading Antigen…
          </div>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Login />
  }

  return (
    <div className="shell">
      <Sidebar
        view={view}
        setView={setView}
        online={online}
        conversations={conversations}
        activeConversationId={conversationId}
        onSelectConversation={setConversationId}
        onNewChat={handleNewChat}
        user={user}
        onLogout={logout}
      />
      <div className="main">
        {view === 'chat' && (
          <ChatView
            conversationId={conversationId}
            setConversationId={setConversationId}
            model={model}
            onConversationsChanged={refreshConversations}
          />
        )}
        {view === 'voice' && (
          <VoiceView
            conversationId={conversationId}
            setConversationId={setConversationId}
            model={model}
            onConversationsChanged={refreshConversations}
          />
        )}
        {view === 'memory' && <MemoryView />}
        {view === 'settings' && <SettingsView model={model} setModel={setModel} online={online} />}
      </div>
    </div>
  )
}