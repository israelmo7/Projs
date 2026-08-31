const API_BASE = import.meta.env.VITE_API_URL || ''

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/api/health`)
  return res.json()
}

export async function fetchMetrics() {
  const res = await fetch(`${API_BASE}/api/model/metrics`)
  return res.json()
}

export async function fetchModelInfo() {
  const res = await fetch(`${API_BASE}/api/model/info`)
  return res.json()
}

export async function fetchDeviceStatus() {
  const res = await fetch(`${API_BASE}/api/device/status`)
  return res.json()
}

export async function fetchPipelineStatus() {
  const res = await fetch(`${API_BASE}/api/pipeline/status`)
  return res.json()
}

export async function runPipeline(skipTts = true, skipBootstrap = false) {
  const res = await fetch(`${API_BASE}/api/pipeline/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ skip_tts: skipTts, skip_bootstrap: skipBootstrap }),
  })
  return res.json()
}

export async function fetchDemoScript() {
  const res = await fetch(`${API_BASE}/api/demo/script`)
  return res.json()
}

export function wsUrl(path: string) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = import.meta.env.VITE_WS_HOST || window.location.host
  return `${proto}://${host}${path}`
}
