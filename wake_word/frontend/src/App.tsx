import { useEffect, useState, useCallback } from 'react'
import { fetchHealth, fetchDemoScript } from './api'
import { useInference, useEventStream, TranscriptEvent } from './hooks/useInference'
import ConfidenceMeter from './components/ConfidenceMeter'
import DeviceMonitor from './components/DeviceMonitor'
import TrainingLab from './components/TrainingLab'
import TranscriptPanel from './components/TranscriptPanel'

export default function App() {
  const { listening, scores, wakeFlash, transcript, transcribing, error, backend, start, stop } = useInference()
  const [health, setHealth] = useState<Record<string, unknown> | null>(null)
  const [demoScript, setDemoScript] = useState<{ browser: string[]; esp32: string[] } | null>(null)
  const [externalTranscript, setExternalTranscript] = useState<TranscriptEvent | null>(null)

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null))
    fetchDemoScript().then(setDemoScript).catch(() => {})
  }, [])

  const onEvent = useCallback((event: string, data: unknown) => {
    if (event === 'transcript' || event === 'wake_detected') {
      const d = data as TranscriptEvent & { transcript?: string }
      if (d.transcript) setExternalTranscript(d as TranscriptEvent)
    }
  }, [])

  useEventStream(onEvent)

  return (
    <div className="min-h-screen p-4 md:p-8 max-w-7xl mx-auto">
      <header className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-nevo-accent/20 flex items-center justify-center text-nevo-accent text-xl font-bold">N</div>
          <div>
            <h1 className="text-2xl font-bold">Nevo Wake Word</h1>
            <p className="text-nevo-muted text-sm">Custom Hebrew wake word · Edge ML · Full Stack Demo</p>
          </div>
        </div>
        <div className="flex gap-2 text-xs">
          <Badge ok={!!health?.model_loaded}>Model</Badge>
          <Badge ok={health?.status === 'ok'}>API</Badge>
          <Badge ok={(health?.ws_clients as number) > 0}>WebSocket</Badge>
        </div>
      </header>

      {/* Architecture diagram */}
      <div className="card mb-6 text-sm text-nevo-muted">
        <strong className="text-white">Pipeline:</strong>{' '}
        TTS → Augment → Energy+ZCR Features → Conv1D → INT8 TFLite → ESP32 / Browser → Whisper
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <ConfidenceMeter scores={scores} wakeFlash={wakeFlash} listening={listening} backend={backend} />

          <div className="card">
            <div className="flex gap-3">
              {!listening ? (
                <button className="btn-primary flex-1" onClick={start}>Start Listening | התחל</button>
              ) : (
                <button className="btn-secondary flex-1" onClick={stop}>Stop | עצור</button>
              )}
            </div>
            {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
          </div>

          <TranscriptPanel transcript={transcript} transcribing={transcribing} external={externalTranscript} />
        </div>

        <div className="space-y-6">
          <DeviceMonitor />
          <TrainingLab />

          {demoScript && (
            <div className="card text-sm">
              <h2 className="font-semibold mb-3">Demo Script | תסריט הדגמה</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <DemoList title="Browser Mode" steps={demoScript.browser} />
                <DemoList title="ESP32 Mode" steps={demoScript.esp32} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Badge({ ok, children }: { ok?: boolean; children: React.ReactNode }) {
  return (
    <span className={`px-2 py-0.5 rounded-full ${ok ? 'bg-nevo-accent/20 text-nevo-accent' : 'bg-white/5 text-nevo-muted'}`}>
      {children}
    </span>
  )
}

function DemoList({ title, steps }: { title: string; steps: string[] }) {
  return (
    <div>
      <h3 className="text-nevo-accent text-xs font-semibold mb-2">{title}</h3>
      <ol className="list-decimal list-inside space-y-1 text-nevo-muted">
        {steps.map((s, i) => <li key={i}>{s}</li>)}
      </ol>
    </div>
  )
}
