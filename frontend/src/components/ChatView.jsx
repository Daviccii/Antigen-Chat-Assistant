import { useState, useRef, useEffect } from 'react'
import { api, transcribeAudio, speakText, streamChat } from '../api.js'
import { SendIcon, MicIcon } from '../icons.jsx'
import { useAuth } from '../auth/AuthContext.jsx'

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

  const bottomRef = useRef(null)
  const textareaRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const audioElRef = useRef(null)

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

  async function sendMessage(overrideText) {
    const text = (overrideText ?? input).trim()
    if (!text || sending) return

    setError(null)
    // Push the user message plus an empty assistant placeholder that fills
    // in live as tokens stream in — this is what makes replies feel instant
    // instead of waiting for the whole thing to generate first.
    setMessages((prev) => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '' }])
    setInput('')
    setSending(true)

    try {
      const { conversationId: newConvId, reply } = await streamChat(text, conversationId, model, (delta) => {
        setMessages((prev) => {
          const next = [...prev]
          const last = next[next.length - 1]
          next[next.length - 1] = { ...last, content: last.content + delta }
          return next
        })
      })
      setConversationId(newConvId)
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

      <footer className="composer">
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
        <button className="send-btn" onClick={() => sendMessage()} disabled={sending || transcribing || !input.trim()}>
          Send <SendIcon />
        </button>
      </footer>
    </>
  )
}