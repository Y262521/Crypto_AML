import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ChainId } from '../lib/chains'
import { fetchAddressAnomalies } from '../lib/endpoints'
import { Brain, MessageSquareText, ShieldBan, Clock } from 'lucide-react'
import toast from 'react-hot-toast'
import { Skeleton } from './Skeleton'

type Props = { address: string; chain: ChainId }

function sevPill(score: number) {
  if (score >= 80) return 'border-rose-400/20 bg-rose-500/10 text-rose-200'
  if (score >= 50) return 'border-amber-400/20 bg-amber-500/10 text-amber-200'
  return 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200'
}

export function AnomalyPanel({ address, chain }: Props) {
  const [autoBlock, setAutoBlock] = useState(false)
  const [selected, setSelected] = useState<any | null>(null)

  const q = useQuery({
    queryKey: ['anomalies', chain, address],
    queryFn: () => fetchAddressAnomalies(address, chain),
    enabled: Boolean(address),
  })

  const anomalies = useMemo(() => {
    const d = q.data as any
    return Array.isArray(d?.anomalies) ? d.anomalies : Array.isArray(d) ? d : []
  }, [q.data])

  const timeline = useMemo(() => {
    const d = q.data as any
    return Array.isArray(d?.timeline) ? d.timeline : []
  }, [q.data])

  const explain = (a: any) => {
    setSelected(a)
    if (typeof window !== 'undefined') {
      toast.success('Explanation loaded')
    }
  }

  return (
    <div className="grid gap-4">
      <div className="glass glass-hover p-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-100">
              <Brain className="h-4 w-4 text-violet-300" />
              AI anomaly detection
            </div>
            <div className="mt-1 text-xs text-gray-400">Velocity spikes, dormant wakeups, cycles, timing patterns.</div>
          </div>
          <label className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-gray-200">
            <ShieldBan className="h-4 w-4 text-rose-300" />
            Auto-block severe
            <input
              type="checkbox"
              className="h-4 w-4 accent-violet-500"
              checked={autoBlock}
              onChange={(e) => setAutoBlock(e.target.checked)}
            />
          </label>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass p-4">
          <div className="text-sm font-semibold text-gray-100">Detected anomalies</div>
          <div className="mt-3 grid gap-2">
            {q.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)
            ) : anomalies.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 text-sm text-gray-400">
                No anomalies returned.
              </div>
            ) : (
              anomalies.map((a: any, idx: number) => (
                <div key={`${a.id ?? a.title ?? 'anomaly'}-${idx}`} className="glass glass-hover flex items-start justify-between gap-4 p-4">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-gray-100">{a.title ?? a.type ?? 'Anomaly'}</div>
                    <div className="mt-1 text-xs text-gray-400">{a.description ?? '—'}</div>
                    <div className="mt-2 text-xs text-gray-500">
                      Confidence: {a.confidencePct ?? a.confidence ?? '—'}%
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <span className={`rounded-full border px-3 py-1 text-xs ${sevPill(Number(a.severityScore ?? 0))}`}>
                      Sev {a.severityScore ?? 0}/100
                    </span>
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() => explain(a)}
                    >
                      <MessageSquareText className="h-4 w-4" />
                      Explain
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="glass p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-100">
            <Clock className="h-4 w-4 text-violet-300" />
            Timeline
          </div>
          <div className="mt-3 grid gap-2">
            {q.isLoading ? (
              Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)
            ) : timeline.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 text-sm text-gray-400">
                No timeline entries.
              </div>
            ) : (
              timeline.map((t: any, idx: number) => (
                <div key={t.id ?? idx} className="rounded-2xl border border-white/10 bg-white/[0.02] p-3">
                  <div className="text-sm text-gray-200">{t.title ?? t.type ?? 'Event'}</div>
                  <div className="mt-1 text-xs text-gray-500">
                    {t.ts ? new Date(t.ts).toLocaleString() : '—'}
                  </div>
                </div>
              ))
            )}
          </div>

          {selected ? (
            <div className="mt-4 rounded-2xl border border-white/10 bg-black/40 p-3">
              <div className="text-xs font-semibold text-gray-100">Explanation</div>
              <div className="mt-2 text-xs text-gray-300">{String(selected.explanation ?? 'No explanation provided.')}</div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

