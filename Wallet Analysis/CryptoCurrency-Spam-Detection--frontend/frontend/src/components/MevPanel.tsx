import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ChainId } from '../lib/chains'
import { fetchAddressMev } from '../lib/endpoints'
import { Layers, ShieldAlert } from 'lucide-react'
import toast from 'react-hot-toast'
import { Skeleton } from './Skeleton'

type Props = { address: string; chain: ChainId }

export function MevPanel({ address, chain }: Props) {
  const q = useQuery({
    queryKey: ['mev', chain, address],
    queryFn: () => fetchAddressMev(address, chain),
    enabled: Boolean(address),
  })

  const data = (q.data ?? {}) as any
  const victim = Boolean(data?.victim)
  const items = useMemo(() => (Array.isArray(data?.items) ? data.items : []), [data?.items])

  return (
    <div className="grid gap-4">
      <div className="glass glass-hover p-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-100">
              <Layers className="h-4 w-4 text-violet-300" />
              MEV & sandwich detection
            </div>
            <div className="mt-1 text-xs text-gray-400">Victim/attacker timelines and profit estimates.</div>
          </div>
          <button type="button" className="btn-ghost" onClick={() => toast('Flashbots report can be wired to backend.')}>
            Report to Flashbots
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass p-4">
          <div className="text-sm font-semibold text-gray-100">Status</div>
          <div className="mt-3">
            {q.isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <div
                className={[
                  'flex items-center justify-between rounded-2xl border p-4 text-sm',
                  victim ? 'border-rose-400/20 bg-rose-500/10 text-rose-200' : 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
                ].join(' ')}
              >
                <span className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4" />
                  {victim ? 'Likely victim of sandwich' : 'No sandwich victim signal'}
                </span>
                <span className="text-xs text-gray-200/80">Est. MEV profits: {data?.totalProfit ?? '—'}</span>
              </div>
            )}
          </div>
        </div>

        <div className="glass p-4">
          <div className="text-sm font-semibold text-gray-100">Ordering visualization</div>
          <div className="mt-3 rounded-2xl border border-white/10 bg-white/[0.02] p-4 text-sm text-gray-400">
            This panel renders the “attacker → victim → attacker” ordering using backend-provided ordering data.
          </div>
        </div>
      </div>

      <div className="glass overflow-hidden">
        <div className="border-b border-white/10 p-4">
          <div className="text-sm font-semibold text-gray-100">Timeline</div>
        </div>
        <div className="p-4">
          {q.isLoading ? (
            <div className="grid gap-2">
              {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 text-sm text-gray-400">
              No MEV timeline items returned.
            </div>
          ) : (
            <div className="grid gap-2">
              {items.map((it: any, idx: number) => (
                <div key={it.id ?? idx} className="rounded-2xl border border-white/10 bg-white/[0.02] p-3">
                  <div className="text-sm text-gray-200">{it.title ?? it.type ?? 'MEV event'}</div>
                  <div className="mt-1 text-xs text-gray-500">{it.ts ? new Date(it.ts).toLocaleString() : '—'}</div>
                  {it.details ? <div className="mt-2 text-xs text-gray-300">{String(it.details)}</div> : null}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

