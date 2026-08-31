import { useEffect, useRef, useState, useCallback } from 'react'
import { wsUrl } from '../api'

export interface InferenceScores {
  background: number
  wake_word: number
  is_wake: boolean
}

export interface TranscriptEvent {
  transcript: string
  reply: string | null
  duration_sec: number
  source: string
}

export function useInference() {
  const [listening, setListening] = useState(false)
  const [scores, setScores] = useState<InferenceScores | null>(null)
  const [wakeFlash, setWakeFlash] = useState(false)
  const [transcript, setTranscript] = useState<TranscriptEvent | null>(null)
  const [transcribing, setTranscribing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [backend, setBackend] = useState<string>('')

  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const stop = useCallback(() => {
    processorRef.current?.disconnect()
    audioCtxRef.current?.close()
    streamRef.current?.getTracks().forEach(t => t.stop())
    wsRef.current?.close()
    processorRef.current = null
    audioCtxRef.current = null
    streamRef.current = null
    wsRef.current = null
    setListening(false)
  }, [])

  const start = useCallback(async () => {
    setError(null)
    try {
      const ws = new WebSocket(wsUrl('/ws/inference'))
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve()
        ws.onerror = () => reject(new Error('WebSocket connection failed'))
      })

      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data)
        if (msg.event === 'ready') {
          setBackend(msg.data.backend)
        } else if (msg.event === 'inference') {
          setScores(msg.data)
        } else if (msg.event === 'wake_detected') {
          setWakeFlash(true)
          setTimeout(() => setWakeFlash(false), 1500)
        } else if (msg.event === 'transcribing') {
          setTranscribing(true)
        } else if (msg.event === 'transcript') {
          setTranscribing(false)
          setTranscript(msg.data)
        } else if (msg.event === 'error') {
          setError(msg.data.message)
        }
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const audioCtx = new AudioContext({ sampleRate: 16000 })
      audioCtxRef.current = audioCtx

      const source = audioCtx.createMediaStreamSource(stream)
      const processor = audioCtx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return
        const input = e.inputBuffer.getChannelData(0)
        const int16 = new Int16Array(input.length)
        for (let i = 0; i < input.length; i++) {
          int16[i] = Math.max(-32768, Math.min(32767, input[i] * 32768))
        }
        ws.send(int16.buffer)
      }

      source.connect(processor)
      processor.connect(audioCtx.destination)
      setListening(true)
    } catch (err) {
      setError(String(err))
      stop()
    }
  }, [stop])

  useEffect(() => () => stop(), [stop])

  return { listening, scores, wakeFlash, transcript, transcribing, error, backend, start, stop }
}

export function useEventStream(onEvent: (event: string, data: unknown) => void) {
  useEffect(() => {
    const ws = new WebSocket(wsUrl('/ws/events'))
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      onEvent(msg.event, msg.data)
    }
    return () => ws.close()
  }, [onEvent])
}
