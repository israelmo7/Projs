import { useEffect, useState } from 'react'
import { fetchDeviceStatus } from '../api'

interface DeviceStatus {
  connected: boolean
  last_packet_at: number | null
  last_wake_at: number | null
  packet_count: number
  device_ip: string | null
  streaming: boolean
}

export default function DeviceMonitor() {
  const [status, setStatus] = useState<DeviceStatus | null>(null)

  useEffect(() => {
    const poll = async () => {
      try {
        setStatus(await fetchDeviceStatus())
      } catch { /* backend offline */ }
    }
    poll()
    const id = setInterval(poll, 2000)
    return () => clearInterval(id)
  }, [])

  const fmt = (ts: number | null) =>
    ts ? new Date(ts * 1000).toLocaleTimeString('he-IL') : '—'

  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4">ESP32 Device | מכשיר</h2>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <Stat label="Status" value={status?.connected ? 'Connected' : 'Waiting...'} highlight={status?.connected} />
        <Stat label="IP" value={status?.device_ip ?? '—'} />
        <Stat label="Packets" value={String(status?.packet_count ?? 0)} />
        <Stat label="Streaming" value={status?.streaming ? 'Yes' : 'No'} />
        <Stat label="Last Wake" value={fmt(status?.last_wake_at ?? null)} />
        <Stat label="Last Packet" value={fmt(status?.last_packet_at ?? null)} />
      </div>

      <p className="text-nevo-muted text-xs mt-4">
        UDP port 5555 · Flash firmware and configure secrets.h with this host IP
      </p>
    </div>
  )
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="bg-white/5 rounded-lg p-3">
      <div className="text-nevo-muted text-xs">{label}</div>
      <div className={highlight ? 'text-nevo-accent font-semibold' : ''}>{value}</div>
    </div>
  )
}
