import { TranscriptEvent } from '../hooks/useInference'

interface Props {
  transcript: TranscriptEvent | null
  transcribing: boolean
  external?: TranscriptEvent | null
}

export default function TranscriptPanel({ transcript, transcribing, external }: Props) {
  const active = external ?? transcript

  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4">Transcript | תמלול</h2>

      {transcribing && (
        <div className="text-nevo-accent animate-pulse mb-3">Transcribing with Whisper...</div>
      )}

      {active ? (
        <div className="space-y-3">
          <div className="bg-white/5 rounded-lg p-4">
            <div className="text-xs text-nevo-muted mb-1">
              {active.source === 'esp32' ? 'ESP32' : 'Browser'} · {active.duration_sec.toFixed(1)}s
            </div>
            <p className="text-lg leading-relaxed">{active.transcript}</p>
          </div>
          {active.reply && (
            <div className="bg-nevo-accent/10 border border-nevo-accent/20 rounded-lg p-4">
              <div className="text-xs text-nevo-accent mb-1">AI Reply</div>
              <p>{active.reply}</p>
            </div>
          )}
        </div>
      ) : (
        <p className="text-nevo-muted text-sm">
          Say &quot;היי נבו&quot; to trigger wake word detection and transcription.
        </p>
      )}
    </div>
  )
}
