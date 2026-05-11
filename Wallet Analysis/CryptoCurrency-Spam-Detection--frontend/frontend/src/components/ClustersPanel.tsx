import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchAddressClusters } from '../lib/endpoints'
import type { ChainId } from '../lib/chains'
import { Skeleton } from './Skeleton'
import { shortenAddress } from '../lib/address'
import CytoscapeComponent from 'react-cytoscapejs'

type Props = {
  address: string
  chain: ChainId
}

export function ClustersPanel({ address, chain }: Props) {
  const [minScore, setMinScore] = useState(0)
  const [minVolume, setMinVolume] = useState(0)
  const [direction, setDirection] = useState<'all' | 'incoming-dominant' | 'outgoing-dominant' | 'bidirectional'>('all')

  const q = useQuery({
    queryKey: ['clusters', chain, address],
    queryFn: () => fetchAddressClusters(address, chain),
    enabled: Boolean(address),
  })

  const rows = q.data?.relatedWallets ?? []
  const summary = q.data?.clusterSignals
  const filteredRows = useMemo(
    () =>
      rows.filter(
        (r) =>
          r.clusterScore >= minScore &&
          r.volume >= minVolume &&
          (direction === 'all' || r.direction === direction),
      ),
    [rows, minScore, minVolume, direction],
  )
  const elements = [
    { data: { id: address, label: 'Root' } },
    ...filteredRows.slice(0, 20).map((r) => ({ data: { id: r.wallet, label: shortenAddress(r.wallet), score: r.clusterScore } })),
    ...filteredRows.slice(0, 20).map((r, i) => ({
      data: { id: `${address}-${r.wallet}-${i}`, source: address, target: r.wallet, label: String(r.interactions) },
    })),
  ]

  return (
    <div className="grid gap-4">
      <div className="glass glass-hover p-4">
        <div className="text-sm font-semibold text-gray-100">Address clustering</div>
        <div className="mt-1 text-xs text-gray-400">Behavioral grouping from repeated flows and bidirectional links.</div>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <div className="grid gap-1">
            <label className="text-[11px] text-gray-500">Min cluster score</label>
            <input type="number" min={0} max={100} value={minScore} onChange={(e) => setMinScore(Number(e.target.value || 0))} className="input h-9" />
          </div>
          <div className="grid gap-1">
            <label className="text-[11px] text-gray-500">Min volume</label>
            <input type="number" min={0} value={minVolume} onChange={(e) => setMinVolume(Number(e.target.value || 0))} className="input h-9" />
          </div>
          <div className="grid gap-1">
            <label className="text-[11px] text-gray-500">Direction</label>
            <select value={direction} onChange={(e) => setDirection(e.target.value as any)} className="h-9 rounded-xl border border-white/10 bg-[#0B0B0B] px-3 text-xs text-white">
              <option value="all">all</option>
              <option value="incoming-dominant">incoming-dominant</option>
              <option value="outgoing-dominant">outgoing-dominant</option>
              <option value="bidirectional">bidirectional</option>
            </select>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {q.isLoading ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-2xl" />)
        ) : (
          <>
            <div className="glass p-4">
              <div className="text-xs text-gray-500">Repeated flows</div>
              <div className="mt-2 text-2xl font-semibold text-gray-100">{summary?.repeatedFlows ?? 0}</div>
            </div>
            <div className="glass p-4">
              <div className="text-xs text-gray-500">Fan-out nodes</div>
              <div className="mt-2 text-2xl font-semibold text-gray-100">{summary?.fanOut ?? 0}</div>
            </div>
            <div className="glass p-4">
              <div className="text-xs text-gray-500">Bidirectional links</div>
              <div className="mt-2 text-2xl font-semibold text-gray-100">{summary?.bidirectionalLinks ?? 0}</div>
            </div>
          </>
        )}
      </div>

      <div className="glass overflow-hidden">
        <div className="border-b border-white/10 p-4 text-sm font-semibold text-gray-100">Cluster topology</div>
        <div className="h-[320px] w-full">
          {q.isLoading ? (
            <div className="p-4"><Skeleton className="h-full w-full rounded-2xl" /></div>
          ) : filteredRows.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-gray-400">No topology data.</div>
          ) : (
            <CytoscapeComponent
              elements={elements}
              style={{ width: '100%', height: '100%' }}
              layout={{ name: 'cose', fit: true, animate: false, padding: 20 }}
              stylesheet={[
                {
                  selector: 'node',
                  style: {
                    label: 'data(label)',
                    'font-size': 10,
                    color: '#E5E7EB',
                    'background-color': '#7c3aed',
                    'border-width': 1,
                    'border-color': 'rgba(255,255,255,0.25)',
                  },
                },
                {
                  selector: 'edge',
                  style: {
                    width: 1.2,
                    'line-color': 'rgba(255,255,255,0.25)',
                    label: 'data(label)',
                    'font-size': 8,
                    color: 'rgba(229,231,235,0.7)',
                  },
                },
              ]}
            />
          )}
        </div>
      </div>

      <div className="glass overflow-hidden">
        <div className="border-b border-white/10 p-4 text-sm font-semibold text-gray-100">Related wallets</div>
        <div className="w-full overflow-x-auto">
          <table className="min-w-[900px] w-full text-left text-sm">
            <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-gray-400">
              <tr>
                <th className="px-4 py-3">Wallet</th>
                <th className="px-4 py-3">Interactions</th>
                <th className="px-4 py-3">Direction</th>
                <th className="px-4 py-3">Volume</th>
                <th className="px-4 py-3">Cluster score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {q.isLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 5 }).map((__, j) => (
                      <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-28" /></td>
                    ))}
                  </tr>
                ))
              ) : filteredRows.length === 0 ? (
                <tr>
                  <td className="px-4 py-10 text-center text-gray-400" colSpan={5}>No cluster relations found.</td>
                </tr>
              ) : (
                filteredRows.map((r) => (
                  <tr key={r.wallet} className="hover:bg-white/[0.02]">
                    <td className="px-4 py-3 font-mono text-xs text-gray-200">{shortenAddress(r.wallet, 12, 8)}</td>
                    <td className="px-4 py-3 text-gray-200">{r.interactions}</td>
                    <td className="px-4 py-3 text-gray-300">{r.direction}</td>
                    <td className="px-4 py-3 text-gray-300">{r.volume.toFixed(4)}</td>
                    <td className="px-4 py-3 text-gray-100">{r.clusterScore}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
