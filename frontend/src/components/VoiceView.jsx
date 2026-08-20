import { useState, useRef, useEffect } from 'react'
import { api, transcribeAudio, speakText, streamChat } from '../api.js'
import { useAuth } from '../auth/AuthContext.jsx'

// Tune these if it cuts you off too early/late, or never stops listening —
// depends a lot on your mic and room noise.
const SILENCE_THRESHOLD = 10 // amplitude (0-128) below which we call it silence
const SILENCE_DURATION_MS = 1300 // how long silence must hold before we consider you done talking
const MAX_LISTEN_MS = 20000 // hard cap so a misfire can't listen forever
const MAX_CONSECUTIVE_FAILURES = 3 // stop auto-retrying after this many mic/transcription errors in a row

export default function VoiceView({ conversationId, setConversationId, model, onConversationsChanged }) {
  const { user } = useAuth()
  const displayName = user?.display_name || user?.username || 'there'
  const greeting = `Hey ${displayName}, I'm listening. What do you need?`

  const [messages, setMessages] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [active, setActive] = useState(false) // is the conversation loop running
  const [phase, setPhase] = useState('idle') // idle | greeting | listening | transcribing | thinking | speaking
  const [error, setError] = useState(null)
  const [voices, setVoices] = useState([])
  const [voice, setVoice] = useState(() => localStorage.getItem('antigen_voice') || '')

  const bottomRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const audioCtxRef = useRef(null)
  const rafRef = useRef(null)
  const audioElRef = useRef(null)
  // Mirrors `active` for use inside async callbacks/closures where the
  // React state value would otherwise be stale by the time they run.
  const activeRef = useRef(false)
  const consecutiveFailuresRef = useRef(0)

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
  }, [messages, phase])

  useEffect(() => {
    api
      .listVoices()
      .then((data) => {
        setVoices(data.voices || [])
        setVoice((current) => current || data.default || '')
      })
      .catch(() => {
        // No big deal if this fails — default voice on the backend still works.
      })
  }, [])

  useEffect(() => {
    if (voice) localStorage.setItem('antigen_voice', voice)
  }, [voice])

  useEffect(() => {
    return () => {
      stopListening()
      audioElRef.current?.pause()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function speak(text) {
    return new Promise((resolve, reject) => {
      setPhase('speaking')
      speakText(text, voice)
        .then((blob) => {
          const url = URL.createObjectURL(blob)
          const audioEl = new Audio(url)
          audioElRef.current = audioEl
          audioEl.onended = () => {
            URL.revokeObjectURL(url)
            resolve()
          }
          audioEl.onerror = () => {
            URL.revokeObjectURL(url)
            reject(new Error('Playback failed'))
          }
          return audioEl.play()
        })
        .catch(reject)
    })
  }

  async function sendAndRespond(text) {
    setMessages((prev) => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '' }])
    setPhase('thinking')

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
      onConversationsChanged?.()
      if (reply) {
        await speak(reply)
      }
    } catch (err) {
      setError(err.message || 'Something went wrong talking to the backend.')
      setMessages((prev) => prev.slice(0, -1))
    }

    if (activeRef.current) {
      startListening()
    } else {
      setPhase('idle')
    }
  }

  function retryListeningOrGiveUp(message) {
    consecutiveFailuresRef.current += 1
    if (consecutiveFailuresRef.current >= MAX_CONSECUTIVE_FAILURES) {
      setError(message || "Having trouble hearing you — stopping so it doesn't loop forever. Check your mic and try again.")
      setActive(false)
      activeRef.current = false
      setPhase('idle')
      return
    }
    if (activeRef.current) startListening()
    else setPhase('idle')
  }

  function startListening() {
    setError(null)
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        const AudioCtx = window.AudioContext || window.webkitAudioContext
        const audioCtx = new AudioCtx()
        const source = audioCtx.createMediaStreamSource(stream)
        const analyser = audioCtx.createAnalyser()
        analyser.fftSize = 512
        source.connect(analyser)
        const data = new Uint8Array(analyser.frequencyBinCount)

        const recorder = new MediaRecorder(stream)
        chunksRef.current = []
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunksRef.current.push(e.data)
        }

        recorder.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop())
          try {
            audioCtx.close()
          } catch {
            // already closed — fine
          }

          const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
          if (blob.size < 1000) {
            // Basically silence the whole time — not a failure, just nothing
            // said. Go back to listening without counting against the retry cap.
            if (activeRef.current) startListening()
            else setPhase('idle')
            return
          }

          setPhase('transcribing')
          try {
            const { text } = await transcribeAudio(blob)
            if (text && text.trim()) {
              consecutiveFailuresRef.current = 0
              await sendAndRespond(text.trim())
            } else if (activeRef.current) {
              startListening()
            } else {
              setPhase('idle')
            }
          } catch (err) {
            retryListeningOrGiveUp(err.message || 'Could not transcribe that.')
          }
        }

        mediaRecorderRef.current = recorder
        audioCtxRef.current = audioCtx
        recorder.start()
        setPhase('listening')

        let hasSpoken = false
        let silenceStart = null
        const startTime = Date.now()

        function tick() {
          analyser.getByteTimeDomainData(data)
          let maxDev = 0
          for (let i = 0; i < data.length; i++) {
            const dev = Math.abs(data[i] - 128)
            if (dev > maxDev) maxDev = dev
          }

          if (maxDev > SILENCE_THRESHOLD) {
            hasSpoken = true
            silenceStart = null
          } else if (hasSpoken) {
            if (silenceStart === null) {
              silenceStart = Date.now()
            } else if (Date.now() - silenceStart > SILENCE_DURATION_MS) {
              recorder.stop()
              return
            }
          }

          if (Date.now() - startTime > MAX_LISTEN_MS) {
            recorder.stop()
            return
          }

          rafRef.current = requestAnimationFrame(tick)
        }
        rafRef.current = requestAnimationFrame(tick)
      })
      .catch(() => {
        setError('Could not access the microphone. Check your browser permissions.')
        setActive(false)
        activeRef.current = false
        setPhase('idle')
      })
  }

  function stopListening() {
    cancelAnimationFrame(rafRef.current)
    try {
      audioCtxRef.current?.close()
    } catch {
      // already closed — fine
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      // Detach onstop first so ending the recording here doesn't also
      // trigger the auto-transcribe-and-send flow.
      mediaRecorderRef.current.onstop = null
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current.stream?.getTracks().forEach((t) => t.stop())
    }
  }

  async function handleStart() {
    setActive(true)
    activeRef.current = true
    consecutiveFailuresRef.current = 0
    setPhase('greeting')
    try {
      await speak(greeting)
    } catch {
      // If playback fails, just move on to listening anyway.
    }
    if (activeRef.current) startListening()
  }

  function handleStop() {
    setActive(false)
    activeRef.current = false
    stopListening()
    audioElRef.current?.pause()
    setPhase('idle')
  }

  const phaseLabel = {
    idle: 'Tap to start talking',
    greeting: 'Antigen is greeting you…',
    listening: 'Listening…',
    transcribing: 'Making out what you said…',
    thinking: 'Thinking…',
    speaking: 'Speaking…',
  }[phase]

  return (
    <>
      <header className="header">
        <div>
          <div className="eyebrow">VOICE MODE</div>
          <h1>Talk to Antigen</h1>
        </div>
        {voices.length > 0 && (
          <select
            className="voice-select"
            value={voice}
            onChange={(e) => setVoice(e.target.value)}
            title="Choose Antigen's voice"
          >
            {voices.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        )}
      </header>

      <main className="log voice-log">
        {loadingHistory && <div className="empty">Loading conversation…</div>}

        {!loadingHistory && messages.length === 0 && phase === 'idle' && (
          <div className="empty">Tap the mic below to start a conversation.</div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`row ${m.role}`}>
            {m.role === 'assistant' && <span className="avatar assistant-avatar">A</span>}
            <div className="bubble-wrap">
              <span className="who">{m.role === 'user' ? 'You' : 'Antigen'}</span>
              <p className="text">{m.content}</p>
            </div>
            {m.role === 'user' && <span className="avatar user-avatar">U</span>}
          </div>
        ))}

        {error && <div className="error">⚠ {error}</div>}
        <div ref={bottomRef} />
      </main>

      <div className="voice-stage">
        <button
          className={`voice-orb phase-${phase}`}
          onClick={active ? handleStop : handleStart}
          title={active ? 'End conversation' : 'Start talking to Antigen'}
        >
          {active ? '■' : '🎤'}
        </button>
        <div className="voice-status">{phaseLabel}</div>
        {active && (
          <button className="greeting-btn" onClick={handleStop}>
            End conversation
          </button>
        )}
      </div>
    </>
  )
}