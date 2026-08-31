import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { fetchMetrics, fetchModelInfo, fetchPipelineStatus, runPipeline } from '../api'

export default function TrainingLab() {
  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null)
  const [modelInfo, setModelInfo] = useState<Record<string, unknown> | null>(null)
  const [pipeline, setPipeline] = useState<Record<string, unknown> | null>(null)
  const [running, setRunning] = useState(false)

  const refresh = async () => {
    try {
      setMetrics(await fetchMetrics())
      setModelInfo(await fetchModelInfo())
      setPipeline(await fetchPipelineStatus())
    } catch { /* offline */ }
  }

  useEffect(() => { refresh() }, [])

  useEffect(() => {
    if (pipeline?.state !== 'running') return
    const id = setInterval(async () => {
      const s = await fetchPipelineStatus()
      setPipeline(s)
      if (s.state === 'completed' || s.state === 'failed') {
        setRunning(false)
        refresh()
      }
    }, 2000)
    return () => clearInterval(id)
  }, [pipeline?.state])

  const handleRun = async () => {
    setRunning(true)
    await runPipeline(true, true)
    setPipeline(await fetchPipelineStatus())
  }

  const history = metrics?.history as Record<string, number[]> | undefined
  const chartData = history?.val_accuracy?.map((acc, i) => ({
    epoch: i + 1,
    accuracy: +(acc * 100).toFixed(1),
    loss: +(history.val_loss[i]).toFixed(3),
  })) ?? []

  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">Training Lab | אימון</h2>
        <button className="btn-primary text-sm" onClick={handleRun} disabled={running}>
          {running ? 'Training...' : 'Retrain Model'}
        </button>
      </div>

      {pipeline?.state === 'running' && (
        <div className="mb-4">
          <div className="text-sm text-nevo-accent">{String(pipeline.current_step)}</div>
          <div className="h-2 bg-white/5 rounded-full mt-1">
            <div className="h-full bg-nevo-accent rounded-full transition-all" style={{ width: `${(pipeline.progress as number) * 100}%` }} />
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-3 text-sm mb-4">
        <MiniStat label="Val Accuracy" value={metrics?.val_accuracy ? `${((metrics.val_accuracy as number) * 100).toFixed(1)}%` : '—'} />
        <MiniStat label="TFLite Size" value={metrics?.tflite_size_kb ? `${metrics.tflite_size_kb} KB` : '—'} />
        <MiniStat label="Strategy" value={String(metrics?.tflite_strategy ?? '—')} />
      </div>

      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={chartData}>
            <XAxis dataKey="epoch" stroke="#8899aa" fontSize={11} />
            <YAxis stroke="#8899aa" fontSize={11} domain={[0, 100]} />
            <Tooltip contentStyle={{ background: '#1a2332', border: 'none' }} />
            <Line type="monotone" dataKey="accuracy" stroke="#00d4aa" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      )}

      {modelInfo && (
        <p className="text-xs text-nevo-muted mt-2">
          H5: {String(modelInfo.h5_size_kb ?? '—')} KB · TFLite: {String(modelInfo.tflite_size_kb ?? '—')} KB · Backend: {String(modelInfo.backend ?? '—')}
        </p>
      )}
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white/5 rounded-lg p-2 text-center">
      <div className="text-nevo-muted text-xs">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  )
}
