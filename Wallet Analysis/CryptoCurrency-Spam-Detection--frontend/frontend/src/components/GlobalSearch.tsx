import { useMemo, useState } from 'react'
import { Search, SlidersHorizontal, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { globalSearch } from '../lib/endpoints'
import { Modal } from './Modal'
import { useForm } from 'react-hook-form'

type Filters = {
  minAmount?: number
  maxAmount?: number
  preset?: '24h' | '7d' | '30d' | 'custom'
  startDate?: string
  endDate?: string
  minRisk?: number
  maxRisk?: number
  txType?: 'any' | 'incoming' | 'outgoing'
  chain?: string
  flaggedOnly?: boolean
}

export function GlobalSearchBar({ compact = false }: { compact?: boolean }) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const { register, handleSubmit, reset, watch } = useForm<Filters>({
    defaultValues: { preset: '7d', txType: 'any' },
  })

  const enabled = q.trim().length >= 3
  const chain = watch('chain')

  const query = useQuery({
    queryKey: ['search', q.trim(), chain ?? ''],
    queryFn: () => globalSearch({ q: q.trim(), chain: chain || undefined }),
    enabled,
  })

  const results = useMemo(() => {
    const data = query.data as any
    return Array.isArray(data?.results) ? data.results : []
  }, [query.data])

  const onApply = handleSubmit(() => {
    setOpen(false)
  })

  return (
    <div className={['relative w-full', compact ? '' : 'max-w-xl'].join(' ')}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className="input pl-10 pr-20"
        placeholder="Search addresses, tx, watchlist, comments…"
      />
      <div className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-2">
        {q ? (
          <button type="button" className="btn-ghost h-8 px-2 py-0" onClick={() => setQ('')} aria-label="Clear search">
            <X className="h-4 w-4" />
          </button>
        ) : null}
        <button type="button" className="btn-ghost h-8 px-2 py-0" onClick={() => setOpen(true)} aria-label="Open filters">
          <SlidersHorizontal className="h-4 w-4" />
        </button>
      </div>

      {enabled ? (
        <div className="absolute left-0 right-0 top-full z-30 mt-2 overflow-hidden rounded-2xl border border-white/10 bg-black/70 backdrop-blur-xl">
          <div className="border-b border-white/10 px-4 py-2 text-xs text-gray-400">
            {query.isFetching ? 'Searching…' : `${results.length} results`}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {query.isFetching ? (
              <div className="px-4 py-3 text-sm text-gray-400">Loading…</div>
            ) : results.length === 0 ? (
              <div className="px-4 py-3 text-sm text-gray-400">No results.</div>
            ) : (
              results.slice(0, 12).map((r: any, idx: number) => (
                <div key={r.id ?? idx} className="px-4 py-3 text-sm text-gray-200 hover:bg-white/[0.04]">
                  <div className="font-semibold text-gray-100">{r.title ?? r.type ?? 'Result'}</div>
                  {r.subtitle ? <div className="mt-1 text-xs text-gray-400">{r.subtitle}</div> : null}
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}

      <Modal title="Advanced filters" open={open} onClose={() => setOpen(false)}>
        <form onSubmit={onApply} className="grid gap-4">
          <div className="grid gap-2">
            <label className="text-xs font-medium text-gray-400">Date preset</label>
            <select
              {...register('preset')}
              className="h-10 rounded-xl border border-white/10 bg-[#0B0B0B] px-3 text-sm text-white outline-none transition focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
            >
              <option value="24h">Last 24h</option>
              <option value="7d">Last 7d</option>
              <option value="30d">Last 30d</option>
              <option value="custom">Custom</option>
            </select>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">Min amount</label>
              <input {...register('minAmount', { valueAsNumber: true })} className="input" placeholder="0" />
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">Max amount</label>
              <input {...register('maxAmount', { valueAsNumber: true })} className="input" placeholder="1000" />
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">Min risk</label>
              <input {...register('minRisk', { valueAsNumber: true })} className="input" placeholder="0" />
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">Max risk</label>
              <input {...register('maxRisk', { valueAsNumber: true })} className="input" placeholder="100" />
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">Tx type</label>
              <select
                {...register('txType')}
                className="h-10 rounded-xl border border-white/10 bg-[#0B0B0B] px-3 text-sm text-white outline-none transition focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
              >
                <option value="any">Any</option>
                <option value="incoming">Incoming</option>
                <option value="outgoing">Outgoing</option>
              </select>
            </div>
            <label className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-gray-200">
              <span>Flagged only</span>
              <input type="checkbox" className="h-4 w-4 accent-violet-500" {...register('flaggedOnly')} />
            </label>
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-medium text-gray-400">Chain</label>
            <input {...register('chain')} className="input" placeholder="e.g. ethereum" />
          </div>

          <div className="flex justify-end gap-2">
            <button type="button" className="btn-ghost" onClick={() => reset()}>
              Reset
            </button>
            <button type="submit" className="btn-primary">
              Apply
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

