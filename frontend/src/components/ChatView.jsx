import { useState, useRef, useEffect } from 'react'
import { api, transcribeAudio, speakText, streamChat, uploadAttachment } from '../api.js'
import { SendIcon, MicIcon } from '../icons.jsx'
import { useAuth } from '../auth/AuthContext.jsx'

function PaperclipIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
    </svg>
  )
}

// One row per file type your backend classifies files into, purely for
// the little emoji badge on each attachment chip.
const FILE_TYPE_ICON = {
  IMAGE: '🖼️',
  PDF: '📄',
  DOCX: '📝',
  SPREADSHEET: '📊',
  AUDIO: '🎵',
  VIDEO: '🎥',
  CODE: '💻',
  OTHER: '📎',
}

export default function ChatView({ conversationId, setConversationId, model, onConversationsChanged }) {
  const { user } = useAuth()
  const displayName = user?.display_name || user?.username || 'there'
  const greeting = `Hey ${displayName}, good to have you back. What are we working on?`

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [error, setError] = useState(null)

  // Voice state
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [speakReplies, setSpeakReplies] = useState(false)
  const [speaking, setSpeaking] = useState(false)

  // Attachment state — each entry is { localId, id, filename, file_type,
  // status: 'uploading' | 'ready' | 'error', error }. `id` is only set
  // once the upload finishes and the backend has assigned it a row.
  const [attachments, setAttachments] = useState([])

  const bottomRef = useRef(null)
  const textareaRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const audioElRef = useRef(null)
  const fileInputRef = useRef(null)

  // Load history whenever the selected conversation changes.
  useEffect(() => {
    if (!conversationId) {
      setMessages([])
      return
    }
    setLoadingHistory(true)
    api
      .getConversation(conversationId)
      .then((data) => setMessages(data.messages))
      .catch((err) => setError(err.message))
      .finally(() => setLoadingHistory(false))
    setAttachments([])
  }, [conversationId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  // Stop any in-flight recording/audio if the component unmounts mid-way.
  useEffect(() => {
    return () => {
      mediaRecorderRef.current?.stream?.getTracks().forEach((t) => t.stop())
      audioElRef.current?.pause()
    }
  }, [])

  const hasPendingUploads = attachments.some((a) => a.status === 'uploading')

  async function sendMessage(overrideText) {
    const text = (overrideText ?? input).trim()
    if ((!text && attachments.length === 0) || sending || hasPendingUploads) return

    const attachmentIds = attachments.filter((a) => a.status === 'ready' && a.id).map((a) => a.id)

    setError(null)
    // Push the user message plus an empty assistant placeholder that fills
    // in live as tokens stream in — this is what makes replies feel instant
    // instead of waiting for the whole thing to generate first.
    setMessages((prev) => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '' }])
    setInput('')
    setSending(true)

    try {
      const { conversationId: newConvId, reply } = await streamChat(
        text,
        conversationId,
        model,
        (delta) => {
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            next[next.length - 1] = { ...last, content: last.content + delta }
            return next
          })
        },
        attachmentIds
      )
      setConversationId(newConvId)
      setAttachments([])
      onConversationsChanged()
      if (speakReplies && reply) {
        playReply(reply).catch(() => {})
      }
    } catch (err) {
      setError(err.message || 'Something went wrong talking to the backend.')
      // Drop the empty placeholder bubble since nothing actually came back.
      setMessages((prev) => prev.slice(0, -1))
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  // ---------------- Attachments ----------------

  function handleAttachClick() {
    fileInputRef.current?.click()
  }

  function handleFileChange(e) {
    const files = Array.from(e.target.files || [])
    e.target.value = '' // allow re-selecting the same file later
    files.forEach(uploadOneFile)
  }

  async function uploadOneFile(file) {
    const localId = `local-${Date.now()}-${Math.random().toString(36).slice(2)}`
    setAttachments((prev) => [
      ...prev,
      { localId, filename: file.name, file_type: null, status: 'uploading', error: null },
    ])

    try {
      const record = await uploadAttachment(file, conversationId)
      setAttachments((prev) =>
        prev.map((a) =>
          a.localId === localId
            ? { ...a, id: record.id, filename: record.filename, file_type: record.file_type, status: 'ready' }
            : a
        )
      )
    } catch (err) {
      setAttachments((prev) =>
        prev.map((a) =>
          a.localId === localId ? { ...a, status: 'error', error: err.message || 'Upload failed' } : a
        )
      )
    }
  }

  function removeAttachment(localId) {
    const target = attachments.find((a) => a.localId === localId)
    setAttachments((prev) => prev.filter((a) => a.localId !== localId))
    // Best-effort cleanup on the backend — the chip is already gone either way.
    if (target?.id) {
      api.deleteAttachment(target.id).catch(() => {})
    }
  }

  // ---------------- Voice input ----------------

  async function startRecording() {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setTranscribing(true)
        try {
          const { text } = await transcribeAudio(blob)
          // Land the words in the composer rather than auto-sending, so you
          // can glance at what it heard before it goes out.
          setInput((prev) => (prev ? `${prev} ${text}` : text))
        } catch (err) {
          setError(err.message || 'Could not transcribe that recording.')
        } finally {
          setTranscribing(false)
        }
      }

      mediaRecorderRef.current = recorder
      recorder.start()
      setRecording(true)
    } catch (err) {
      setError('Could not access the microphone. Check your browser permissions.')
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop()
    setRecording(false)
  }

  function handleMicClick() {
    if (recording) {
      stopRecording()
    } else {
      startRecording()
    }
  }

  // ---------------- Voice output ----------------

  function playReply(text) {
    return new Promise((resolve, reject) => {
      setSpeaking(true)
      speakText(text, localStorage.getItem('antigen_voice') || undefined)
        .then((blob) => {
          const url = URL.createObjectURL(blob)
          const audioEl = new Audio(url)
          audioElRef.current = audioEl
          audioEl.onended = () => {
            setSpeaking(false)
            URL.revokeObjectURL(url)
            resolve()
          }
          audioEl.onerror = () => {
            setSpeaking(false)
            URL.revokeObjectURL(url)
            reject(new Error('Audio playback failed'))
          }
          return audioEl.play()
        })
        .catch((err) => {
          setSpeaking(false)
          setError(err.message || 'Could not play the spoken reply.')
          reject(err)
        })
    })
  }

  // Speaks the greeting (a real click, so autoplay policies allow it), then
  // starts recording once it's done — so the mic doesn't pick up Antigen's
  // own voice as input.
  async function handleTalkClick() {
    if (speakReplies) {
      try {
        await playReply(greeting)
      } catch {
        // Playback failing shouldn't block them from just talking anyway.
      }
    }
    startRecording()
  }

  return (
    <>
      <header className="header">
        <div>
          <div className="eyebrow">AI WORKSPACE</div>
          <h1>Antigen Chat</h1>
        </div>
        <button
          className={`speak-toggle ${speakReplies ? 'active' : ''}`}
          onClick={() => setSpeakReplies((v) => !v)}
          title={speakReplies ? 'Antigen will speak replies aloud' : 'Replies are text-only'}
        >
          {speakReplies ? '🔊 Voice on' : '🔈 Voice off'}
        </button>
      </header>

      <main className="log">
        {loadingHistory && <div className="empty">Loading conversation…</div>}

        {!loadingHistory && messages.length === 0 && (
          <div className="row assistant">
            <span className="avatar assistant-avatar">A</span>
            <div className="bubble-wrap">
              <span className="who">Antigen</span>
              <p className="text">{greeting}</p>
              <div className="greeting-actions">
                <button className="greeting-btn" onClick={handleTalkClick} disabled={recording || transcribing}>
                  🎤 Talk to me
                </button>
                <button className="greeting-btn" onClick={() => textareaRef.current?.focus()}>
                  ⌨️ Type instead
                </button>
              </div>
            </div>
          </div>
        )}

        {messages.map((m, i) => {
          const isLivePlaceholder = sending && i === messages.length - 1 && m.role === 'assistant' && m.content === ''
          return (
            <div key={i} className={`row ${m.role}`}>
              {m.role === 'assistant' && <span className="avatar assistant-avatar">A</span>}
              <div className="bubble-wrap">
                <span className="who">{m.role === 'user' ? 'You' : 'Antigen'}</span>
                <p className={`text ${isLivePlaceholder ? 'pending' : ''}`}>
                  {isLivePlaceholder ? 'thinking…' : m.content}
                </p>
              </div>
              {m.role === 'user' && <span className="avatar user-avatar">U</span>}
            </div>
          )
        })}

        {speaking && <div className="empty" style={{ marginTop: 0 }}>🔊 speaking…</div>}

        {error && <div className="error">⚠ {error}</div>}

        <div ref={bottomRef} />
      </main>

      {attachments.length > 0 && (
        <div className="attachment-preview-row">
          {attachments.map((a) => (
            <div key={a.localId} className={`attachment-chip ${a.status}`}>
              <span className="attachment-chip-icon">{FILE_TYPE_ICON[a.file_type] || '📎'}</span>
              <span className="attachment-chip-name" title={a.filename}>{a.filename}</span>
              {a.status === 'uploading' && <span className="attachment-chip-status">uploading…</span>}
              {a.status === 'error' && <span className="attachment-chip-status error" title={a.error}>failed</span>}
              <button
                className="attachment-chip-remove"
                onClick={() => removeAttachment(a.localId)}
                title="Remove attachment"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <footer className="composer">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          hidden
          onChange={handleFileChange}
          accept=".jpg,.jpeg,.png,.webp,.gif,.heic,.pdf,.docx,.xlsx,.xls,.csv,.mp3,.wav,.m4a,.ogg,.mp4,.mov,.webm,.mkv,.py,.js,.jsx,.ts,.tsx,.java,.c,.cpp,.go,.rs,.rb,.php,.sql,.json,.yaml,.yml,.html,.css,.sh,.md,.txt"
        />
        <button
          className="attach-btn"
          onClick={handleAttachClick}
          disabled={transcribing}
          title="Attach a file"
        >
          <PaperclipIcon />
        </button>
        <button
          className={`mic-btn ${recording ? 'recording' : ''}`}
          onClick={handleMicClick}
          disabled={transcribing}
          title={recording ? 'Stop recording' : 'Record a voice message'}
        >
          <MicIcon />
        </button>
        <textarea
          ref={textareaRef}
          value={transcribing ? 'Transcribing…' : input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Antigen anything…"
          rows={1}
          disabled={transcribing}
        />
        <button
          className="send-btn"
          onClick={() => sendMessage()}
          disabled={sending || transcribing || hasPendingUploads || (!input.trim() && attachments.length === 0)}
        >
          Send <SendIcon />
        </button>
      </footer>
    </>
  )
}