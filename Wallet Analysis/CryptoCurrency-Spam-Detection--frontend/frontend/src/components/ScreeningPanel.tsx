import { useQuery } from '@tanstack/react-query'
import { ShieldAlert, ShieldCheck } from 'lucide-react'
import type { ChainId } from '../lib/chains'
import { fetchAddressScreening } from '../lib/endpoints'
import { Skeleton } from './Skeleton'

type Props = {
  address: string
  chain: ChainId
}

export function ScreeningPanel({ address, chain }: Props) {
  const q = useQuery({
    queryKey: ['screening', chain, address],
    queryFn: () => fetchAddressScreening(address, chain),
    enabled: Boolean(address),
  })

  const data = q.data
  const matched = Boolean(data?.matched)

  return (
    <div className="glass glass-hover p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-100">Wallet screening</div>
          <div className="mt-1 text-xs text-gray-400">Curated datastore match + entity labeling.</div>
        </div>
        <div
          className={[
            'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs',
            matched ? 'border-rose-400/20 bg-rose-500/10 text-rose-200' : 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
          ].join(' ')}
        >
          {matched ? <ShieldAlert className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
          {matched ? 'Match found' : 'No match'}
        </div>
      </div>

      {q.isLoading ? (
        <div className="mt-4 grid gap-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-3 text-sm">
            <div className="text-xs text-gray-500">Entity label</div>
            <div className="mt-1 font-semibold text-gray-100">{data?.entityLabel ?? 'user_wallet'}</div>
            <div className="mt-1 text-xs text-gray-400">Confidence: {Math.round((data?.confidence ?? 0) * 100)}%</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-3 text-sm">
            <div className="text-xs text-gray-500">Source</div>
            <div className="mt-1 font-semibold text-gray-100">{data?.source ?? 'none'}</div>
            <div className="mt-1 text-xs text-gray-400">
              {data?.reasons?.length ? data.reasons.join(', ') : 'No matching labels'}
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-3 text-xs text-gray-300 sm:col-span-2">
            <div className="font-semibold text-gray-100">Category matches</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {(['scam', 'phishing', 'mixer', 'ransomware', 'stolenFunds', 'darknet'] as const).map((k) => (
                <span key={k} className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1">
                  {k}: {data?.categories?.[k]?.length ?? 0}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
