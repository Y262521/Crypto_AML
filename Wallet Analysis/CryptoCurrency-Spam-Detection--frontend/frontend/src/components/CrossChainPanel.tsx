import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchAddressCrossChain } from '../lib/endpoints'
import { ArrowLeftRight, GitMerge, PieChart } from 'lucide-react'
import { ResponsiveContainer, PieChart as RPie, Pie, Cell, Tooltip, Sankey } from 'recharts'
import { Skeleton } from './Skeleton'

type Props = { address: string }

const COLORS = ['#7c3aed', '#34d399', '#fbbf24', '#fb7185', '#38bdf8', '#a855f7']

export function CrossChainPanel({ address }: Props) {
  const [chainFilter, setChainFilter] = useState<string>('all')
  const q = useQuery({
    queryKey: ['cross-chain', address],
    queryFn: () => fetchAddressCrossChain(address),
    enabled: Boolean(address),
  })

  const data = (q.data ?? {}) as any
  const balances = useMemo(() => (Array.isArray(data?.balances) ? data.balances : []), [data?.balances])
  const bridges = useMemo(() => (Array.isArray(data?.bridges) ? data.bridges : []), [data?.bridges])
  const flows = useMemo(() => (data?.flows ?? null) as any, [data?.flows])

  const pie = useMemo(
    () =>
      balances
        .filter((b: any) => chainFilter === 'all' || b.chain === chainFilter)
        .map((b: any) => ({ name: b.chain, value: b.value ?? 0 })),
    [balances, chainFilter],
  )

  return (
    <div className="grid gap-4">
      <div className="glass glass-hover p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-100">
              <ArrowLeftRight className="h-4 w-4 text-violet-300" />
              Cross-chain tracking
            </div>
            <div className="mt-1 text-xs text-gray-400">Unified activity across chains + bridge detection.</div>
          </div>
          <select
            value={chainFilter}
            onChange={(e) => setChainFilter(e.target.value)}
            className="h-9 rounded-xl border border-white/10 bg-[#0B0B0B] px-3 text-xs text-white outline-none transition focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
          >
            <option value="all">All chains</option>
            {balances.map((b: any) => (
              <option key={b.chain} value={b.chain}>
                {b.chain}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-100">
            <PieChart className="h-4 w-4 text-violet-300" />
            Cross-chain balance summary
          </div>
          <div className="mt-3 h-56">
            {q.isLoading ? (
              <Skeleton className="h-full w-full rounded-2xl" />
            ) : pie.length === 0 ? (
              <div className="flex h-full items-center justify-center rounded-2xl border border-white/10 bg-white/[0.02] text-sm text-gray-400">
                No balances returned.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <RPie>
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(0,0,0,0.85)',
                      border: '1px solid rgba(255,255,255,0.12)',
                      borderRadius: 12,
                    }}
                  />
                  <Pie data={pie} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85}>
                    {pie.map((_x: unknown, idx: number) => (
                      <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                    ))}
                  </Pie>
                </RPie>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="glass p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-100">
            <GitMerge className="h-4 w-4 text-violet-300" />
            Bridge usage
          </div>
          <div className="mt-3 grid gap-2">
            {q.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)
            ) : bridges.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 text-sm text-gray-400">
                No bridge events returned.
              </div>
            ) : (
              bridges.map((b: any, idx: number) => (
                <div key={b.id ?? idx} className="glass glass-hover flex items-center justify-between gap-3 p-4">
                  <div>
                    <div className="text-sm font-semibold text-gray-100">{b.bridge ?? 'Bridge'}</div>
                    <div className="mt-1 text-xs text-gray-400">
                      {b.sourceChain ?? '—'} → {b.destinationChain ?? '—'} • {b.amount ?? '—'} •{' '}
                      {b.date ? new Date(b.date).toLocaleString() : '—'}
                    </div>
                  </div>
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-gray-200">
                    {b.bridge ?? '—'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="glass p-4">
        <div className="text-sm font-semibold text-gray-100">Cross-chain flow</div>
        <div className="mt-1 text-xs text-gray-400">Sankey visualization of fund movement.</div>
        <div className="mt-3 h-72">
          {q.isLoading ? (
            <Skeleton className="h-full w-full rounded-2xl" />
          ) : flows ? (
            <ResponsiveContainer width="100%" height="100%">
              <Sankey data={flows} nodePadding={30} nodeWidth={12} linkCurvature={0.5} />
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center rounded-2xl border border-white/10 bg-white/[0.02] text-sm text-gray-400">
              No flow data returned.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

