import { useMemo, useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { RefreshCcw, Activity, Cpu, Layers } from 'lucide-react'
import { fetchIndexerStatus, triggerReindex } from '../lib/endpoints'
import { Skeleton } from '../components/Skeleton'
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts'
import toast from 'react-hot-toast'

export function IndexerStatusPage() {
  const [reindexAddress, setReindexAddress] = useState('')
  const [reindexRange, setReindexRange] = useState('')

  const q = useQuery({
    queryKey: ['indexer-status'],
    queryFn: fetchIndexerStatus,
    refetchInterval: 15_000,
  })

  const reindexMutation = useMutation({
    mutationFn: () => triggerReindex({ address: reindexAddress, blockRange: reindexRange || undefined }),
    onSuccess: (data: any) => {
      toast.success(data?.message ?? 'Reindex queued')
      setReindexAddress('')
      setReindexRange('')
    },
    onError: () => toast.error('Failed to queue reindex'),
  })

  const status = (q.data ?? {}) as any
  const chains = Array.isArray(status?.chains) ? status.chains : []
  const perf = Array.isArray(status?.performance) ? status.performance : []

  const chartData = useMemo(() => perf.map((p: any) => ({
    t: p.ts ? new Date(p.ts).toLocaleTimeString() : '',
    blocksPerMin: p.blocksPerMinute ?? 0,
    latencyMs: p.avgLatencyMs ?? 0,
    queueDepth: p.queueDepth ?? 0,
  })), [perf])

  const healthyCount = chains.filter((c: any) => c.healthy).length

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="page-header">Indexer Status</div>
            <div className="page-subheader">Real-time chain sync, health, and performance.</div>
          </div>
          <button type="button" className="btn-ghost" onClick={() => q.refetch()}>
            <RefreshCcw className={['h-4 w-4', q.isFetching ? 'animate-spin' : ''].join(' ')} />
            Refresh
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="glass p-4">
            <div className="flex items-center gap-2 text-xs text-gray-400"><Activity className="h-4 w-4 text-emerald-400" />Healthy chains</div>
            <div className="mt-2 text-2xl font-bold text-gray-100">
              {q.isLoading ? <Skeleton className="h-8 w-16" /> : `${healthyCount} / ${chains.length}`}
            </div>
          </div>
          <div className="glass p-4">
            <div className="flex items-center gap-2 text-xs text-gray-400"><Cpu className="h-4 w-4 text-violet-400" />Avg latency</div>
            <div className="mt-2 text-2xl font-bold text-gray-100">
              {q.isLoading ? <Skeleton className="h-8 w-16" /> : perf.length > 0 ? `${perf[perf.length - 1]?.avgLatencyMs ?? 0} ms` : '—'}
            </div>
          </div>
          <div className="glass p-4">
            <div className="flex items-center gap-2 text-xs text-gray-400"><Layers className="h-4 w-4 text-amber-400" />Queue depth</div>
            <div className="mt-2 text-2xl font-bold text-gray-100">
              {q.isLoading ? <Skeleton className="h-8 w-16" /> : perf.length > 0 ? (perf[perf.length - 1]?.queueDepth ?? 0) : '0'}
            </div>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="glass p-4">
            <div className="text-sm font-semibold text-gray-100">Chain health</div>
            <div className="mt-3 grid gap-3 max-h-96 overflow-y-auto pr-1">
              {q.isLoading ? (
                Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)
              ) : chains.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 text-sm text-gray-400">No chain status returned.</div>
              ) : (
                chains.map((c: any) => (
                  <div key={c.chain} className="glass glass-hover flex items-center justify-between gap-3 p-4">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold capitalize text-gray-100">{c.chain}</div>
                      <div className="mt-1 text-xs text-gray-400">
                        Block: {c.currentBlock ? c.currentBlock.toLocaleString() : '—'} •
                        Indexed: {c.lastIndexedBlock ? c.lastIndexedBlock.toLocaleString() : '—'} •
                        Behind: {c.behind ? c.behind.toLocaleString() : '0'}
                        {c.latencyMs !== undefined ? ` • ${c.latencyMs}ms` : ''}
                      </div>
                    </div>
                    <span className={['shrink-0 rounded-full border px-3 py-1 text-xs', c.healthy ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200' : 'border-rose-400/20 bg-rose-500/10 text-rose-200'].join(' ')}>
                      {c.healthy ? 'Healthy' : 'Degraded'}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="glass p-4">
            <div className="text-sm font-semibold text-gray-100">Performance</div>
            <div className="mt-1 text-xs text-gray-400">Blocks/min, latency, queue depth over time.</div>
            <div className="mt-3 h-64">
              {q.isLoading ? (
                <Skeleton className="h-full w-full rounded-2xl" />
              ) : chartData.length === 0 ? (
                <div className="flex h-full items-center justify-center text-sm text-gray-500">Performance data accumulates after first refresh.</div>
              ) : (
                <ResponsiveContainer width="100%" height={256}>
                  <LineChart data={chartData}>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    <XAxis dataKey="t" tick={{ fill: 'rgba(229,231,235,0.6)', fontSize: 11 }} tickLine={false} />
                    <YAxis tick={{ fill: 'rgba(229,231,235,0.6)', fontSize: 11 }} tickLine={false} />
                    <Tooltip contentStyle={{ background: 'rgba(0,0,0,0.85)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 12 }} />
                    <Line type="monotone" dataKey="blocksPerMin" name="Blocks/min" stroke="#34d399" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="queueDepth" name="Queue depth" stroke="#fbbf24" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="latencyMs" name="Latency (ms)" stroke="#fb7185" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>

        <div className="glass p-4">
          <div className="text-sm font-semibold text-gray-100">Manual reindex</div>
          <div className="mt-1 text-xs text-gray-400">Queue a reindex job for a specific address and optional block range.</div>
          <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <input className="input" placeholder="Address (0x…)" value={reindexAddress} onChange={e => setReindexAddress(e.target.value)} />
            <input className="input" placeholder="Block range (e.g. 19000000-19010000)" value={reindexRange} onChange={e => setReindexRange(e.target.value)} />
            <button
              type="button"
              className="btn-primary"
              disabled={!reindexAddress.trim() || reindexMutation.isPending}
              onClick={() => reindexMutation.mutate()}
            >
              {reindexMutation.isPending ? 'Queuing…' : 'Reindex'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
