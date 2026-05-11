import { useQuery } from '@tanstack/react-query'
import type { ChainId } from '../lib/chains'
import { fetchAddressSanctions } from '../lib/endpoints'
import { ShieldCheck, ShieldX } from 'lucide-react'

type Props = {
  address: string
  chain: ChainId
}

export function ComplianceBadge({ address, chain }: Props) {
  const q = useQuery({
    queryKey: ['sanctions', chain, address],
    queryFn: () => fetchAddressSanctions(address, chain),
    enabled: Boolean(address),
  })

  const data = (q.data ?? {}) as any
  const hit = Boolean(data?.sanctioned)
  const score = typeof data?.complianceScore === 'number' ? data.complianceScore : null

  return (
    <div className="group relative inline-flex">
      <div
        className={[
          'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs',
          hit ? 'border-rose-400/20 bg-rose-500/10 text-rose-200' : 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
        ].join(' ')}
      >
        {hit ? <ShieldX className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
        {hit ? 'OFAC Match' : 'OFAC Clear'}
        {score !== null ? <span className="text-gray-200/80">• Compliance {score}/100</span> : null}
      </div>

      <div className="pointer-events-none absolute left-0 top-full z-20 mt-2 w-[320px] opacity-0 transition group-hover:opacity-100">
        <div className="glass border-white/12 bg-black/70 p-3 text-left">
          <div className="text-xs font-semibold text-gray-100">Compliance details</div>
          <div className="mt-2 text-xs text-gray-300">
            {q.isLoading ? 'Checking…' : data?.message ? String(data.message) : 'No additional details.'}
          </div>
        </div>
      </div>
    </div>
  )
}

