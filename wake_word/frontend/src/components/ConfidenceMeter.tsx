import { InferenceScores } from '../hooks/useInference'

interface Props {
  scores: InferenceScores | null
  wakeFlash: boolean
  listening: boolean
  backend: string
}

export default function ConfidenceMeter({ scores, wakeFlash, listening, backend }: Props) {
  const wakePct = scores ? Math.round(scores.wake_word * 100) : 0
  const bgPct = scores ? Math.round(scores.background * 100) : 0

  return (
    <div className={`card transition-all ${wakeFlash ? 'ring-2 ring-nevo-wake shadow-nevo-wake/30 shadow-lg' : ''}`}>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">Live Detection | זיהוי חי</h2>
        <span className="text-xs text-nevo-muted">
          {listening ? `● ${backend}` : '○ idle'}
        </span>
      </div>

      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span>Wake Word | היי נבו</span>
            <span className={wakePct > 80 ? 'text-nevo-wake font-bold' : ''}>{wakePct}%</span>
          </div>
          <div className="h-4 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full bg-nevo-wake transition-all duration-150 rounded-full"
              style={{ width: `${wakePct}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <span>Background | רקע</span>
            <span>{bgPct}%</span>
          </div>
          <div className="h-4 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full bg-nevo-muted transition-all duration-150 rounded-full"
              style={{ width: `${bgPct}%` }}
            />
          </div>
        </div>
      </div>

      {wakeFlash && (
        <div className="mt-4 text-center text-nevo-wake font-bold text-xl animate-pulse">
          WAKE DETECTED! | זוהה!
        </div>
      )}
    </div>
  )
}
