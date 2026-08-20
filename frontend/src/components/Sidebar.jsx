import { ChatIcon, MemoryIcon, SettingsIcon, PlusIcon, MicIcon } from '../icons.jsx'

export default function Sidebar({
  view,
  setView,
  online,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  user,
  onLogout,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-mark">A</span>
        <div>
          <div className="brand-name">Antigen</div>
          <div className="brand-sub">
            <span className={`dot ${online ? 'dot-on' : 'dot-off'}`} />
            {online ? 'Local assistant' : 'Backend offline'}
          </div>
        </div>
      </div>

      <nav className="nav">
        <button className={`nav-item ${view === 'chat' ? 'active' : ''}`} onClick={() => setView('chat')}>
          <ChatIcon /> Chat
        </button>
        <button className={`nav-item ${view === 'voice' ? 'active' : ''}`} onClick={() => setView('voice')}>
          <MicIcon /> Voice
        </button>
        <button className={`nav-item ${view === 'memory' ? 'active' : ''}`} onClick={() => setView('memory')}>
          <MemoryIcon /> Memory
        </button>
        <button className={`nav-item ${view === 'settings' ? 'active' : ''}`} onClick={() => setView('settings')}>
          <SettingsIcon /> Settings
        </button>
      </nav>

      {(view === 'chat' || view === 'voice') && (
        <>
          <button className="new-chat" onClick={onNewChat}>
            <PlusIcon /> New chat
          </button>

          <div className="conv-label">Conversations</div>
          <div className="conv-list">
            {conversations.length === 0 && <div className="conv-empty">No conversations yet</div>}
            {conversations.map((c) => (
              <button
                key={c.id}
                className={`conv-item ${c.id === activeConversationId ? 'active' : ''}`}
                onClick={() => onSelectConversation(c.id)}
              >
                <div className="conv-title">{c.title || `Conversation #${c.id}`}</div>
                <div className="conv-sub">{c.last_message ? c.last_message.slice(0, 48) : 'Empty'}</div>
              </button>
            ))}
          </div>
        </>
      )}

      {user && (
        <div className="owner-block">
          <div className="owner-info">
            <span className="owner-avatar">{(user.display_name || user.username || '?')[0].toUpperCase()}</span>
            <div>
              <div className="owner-name">{user.display_name || user.username}</div>
              <div className="owner-role">{user.role === 'OWNER' ? 'Owner' : 'User'}</div>
            </div>
          </div>
          <button className="logout-btn" onClick={onLogout}>
            Log out
          </button>
        </div>
      )}
    </aside>
  )
}