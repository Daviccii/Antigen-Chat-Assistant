import React, { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function SettingsView({ model, setModel, online }) {
  const [aiStatus, setAiStatus] = useState(null)

  useEffect(() => {
    api.aiStatus()
      .then(setAiStatus)
      .catch(() => setAiStatus({ error: 'Failed to fetch AI status' }))
  }, [])

  return (
    <>
      <header className="header">
        <div>
          <div className="eyebrow">AI WORKSPACE</div>
          <h1>Settings</h1>
        </div>
      </header>

      <main className="settings-panel">
        <section className="settings-section">
          <h2>Connection</h2>
          <div className="settings-row">
            <span>Backend</span>
            <span className={online ? 'ok' : 'bad'}>{online ? 'Connected — localhost:8000' : 'Not reachable'}</span>
          </div>
          {aiStatus && (
            <>
              <div className="settings-row">
                <span>Ollama</span>
                <span className={aiStatus.ollama?.reachable ? 'ok' : 'bad'}>
                  {aiStatus.ollama?.reachable ? 'Connected — localhost:11434' : 'Not reachable'}
                </span>
              </div>
              {aiStatus.ollama?.reachable && aiStatus.ollama?.models?.length > 0 && (
                <div className="settings-row">
                  <span>Available Models</span>
                  <span>{aiStatus.ollama.models.join(', ')}</span>
                </div>
              )}
            </>
          )}
        </section>

        <section className="settings-section">
          <h2>Model</h2>
          <p className="settings-hint">
            OpenAI models need billing set up on your OpenAI account. "Local" models run free via
            Ollama on your own machine — install it, run <code>ollama pull llama3.2</code>, and it
            works with no API key.
          </p>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            <optgroup label="OpenAI (paid)">
              <option value="gpt-4o-mini">gpt-4o-mini</option>
              <option value="gpt-4o">gpt-4o</option>
              <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
            </optgroup>
            <optgroup label="Local via Ollama (free)">
              {aiStatus?.ollama?.reachable && aiStatus?.ollama?.models?.length > 0 ? (
                aiStatus.ollama.models.map(ollamaModel => (
                  <option key={ollamaModel} value={`ollama:${ollamaModel}`}>
                    {ollamaModel} (local)
                  </option>
                ))
              ) : (
                <>
                  <option value="ollama:llama3.2">llama3.2 (local)</option>
                  <option value="ollama:qwen2.5:3b">qwen2.5:3b (local)</option>
                </>
              )}
            </optgroup>
          </select>
        </section>

        <section className="settings-section">
          <h2>Coming later</h2>
          <ul className="roadmap-list">
            <li>Voice input / output</li>
            <li>Approved skills &amp; plugins</li>
            <li>Automation &amp; system control</li>
            <li>Multi-user &amp; permissions</li>
          </ul>
        </section>
      </main>
    </>
  )
}