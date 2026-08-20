import { useState, useEffect } from 'react'
import { api } from '../api.js'
import { SearchIcon, PlusIcon } from '../icons.jsx'

export default function MemoryView() {
  const [memories, setMemories] = useState([])
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('keyword') // 'keyword' | 'semantic'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [showAdd, setShowAdd] = useState(false)
  const [newType, setNewType] = useState('note')
  const [newContent, setNewContent] = useState('')
  const [saving, setSaving] = useState(false)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      if (mode === 'semantic' && query.trim()) {
        const data = await api.semanticSearchMemories(query.trim())
        setMemories(data.items)
      } else {
        const data = await api.listMemories(query.trim() || undefined)
        setMemories(data.items)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleSearchSubmit(e) {
    e.preventDefault()
    load()
  }

  async function handleAdd(e) {
    e.preventDefault()
    if (!newContent.trim()) return
    setSaving(true)
    try {
      await api.createMemory(newType, newContent.trim())
      setNewContent('')
      setShowAdd(false)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    try {
      await api.deleteMemory(id)
      setMemories((prev) => prev.filter((m) => m.id !== id))
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <header className="header">
        <div>
          <div className="eyebrow">AI WORKSPACE</div>
          <h1>Memory</h1>
        </div>
        <button className="primary-btn" onClick={() => setShowAdd((s) => !s)}>
          <PlusIcon /> Add memory
        </button>
      </header>

      <main className="memory-panel">
        {showAdd && (
          <form className="memory-add" onSubmit={handleAdd}>
            <select value={newType} onChange={(e) => setNewType(e.target.value)}>
              <option value="note">note</option>
              <option value="fact">fact</option>
              <option value="task">task</option>
              <option value="preference">preference</option>
            </select>
            <input
              type="text"
              placeholder="What should Antigen remember?"
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
            />
            <button type="submit" disabled={saving || !newContent.trim()}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </form>
        )}

        <form className="memory-search" onSubmit={handleSearchSubmit}>
          <SearchIcon />
          <input
            type="text"
            placeholder={mode === 'semantic' ? 'Search by meaning…' : 'Search memories…'}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="mode-toggle">
            <button type="button" className={mode === 'keyword' ? 'active' : ''} onClick={() => setMode('keyword')}>
              Keyword
            </button>
            <button type="button" className={mode === 'semantic' ? 'active' : ''} onClick={() => setMode('semantic')}>
              Smart
            </button>
          </div>
          <button type="submit" className="primary-btn small">
            Search
          </button>
        </form>

        {error && <div className="error">⚠ {error}</div>}
        {loading && <div className="empty">Loading…</div>}
        {!loading && memories.length === 0 && <div className="empty">No memories found.</div>}

        <div className="memory-list">
          {memories.map((m) => (
            <div key={m.id} className="memory-card">
              <div className="memory-card-top">
                <span className="memory-type">{m.type}</span>
                {m.distance != null && <span className="memory-distance">match {(1 - m.distance).toFixed(2)}</span>}
                <button className="memory-delete" onClick={() => handleDelete(m.id)}>
                  ✕
                </button>
              </div>
              <p>{m.content}</p>
              {m.tags && <div className="memory-tags">{m.tags}</div>}
            </div>
          ))}
        </div>
      </main>
    </>
  )
}