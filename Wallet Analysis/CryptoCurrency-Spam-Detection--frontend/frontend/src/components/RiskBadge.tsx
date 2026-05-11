import { ShieldAlert, ShieldCheck, ShieldHalf } from 'lucide-react'
import type { RiskFactor } from '../types/api'

type Props = {
  score: number
  factors: RiskFactor[]
}

function clampScore(x: number) {
  if (!Number.isFinite(x)) return 0
  return Math.max(0, Math.min(100, Math.round(x)))
}

function colorFor(score: number) {
  if (score <= 29) return { label: 'Low', cls: 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200' }
  if (score <= 69) return { label: 'Medium', cls: 'border-amber-400/20 bg-amber-500/10 text-amber-200' }
  return { label: 'High', cls: 'border-rose-400/20 bg-rose-500/10 text-rose-200' }
}

export function RiskBadge({ score, factors }: Props) {
  const s = clampScore(score)
  const c = colorFor(s)
  const Icon = s <= 29 ? ShieldCheck : s <= 69 ? ShieldHalf : ShieldAlert

  return (
    <div className="group relative inline-flex">
      <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${c.cls}`}>
        <Icon className="h-3.5 w-3.5" />
        Risk {s}/100 • {c.label}
      </div>

      <div className="pointer-events-none absolute left-0 top-full z-20 mt-2 w-[320px] opacity-0 transition group-hover:opacity-100">
        <div className="glass border-white/12 bg-black/70 p-3 text-left">
          <div className="text-xs font-semibold text-gray-100">Risk factors</div>
          <div className="mt-2 space-y-2">
            {factors.length === 0 ? (
              <div className="text-xs text-gray-400">No factors provided by API.</div>
            ) : (
              factors.slice(0, 6).map((f, idx) => (
                <div key={f.id ?? `${f.title}-${idx}`} className="text-xs text-gray-200">
                  <span className="text-gray-100">{f.title}</span>
                  {f.description ? <span className="text-gray-400"> — {f.description}</span> : null}
                </div>
              ))
            )}
          </div>
          {factors.length > 6 ? (
            <div className="mt-2 text-[11px] text-gray-500">+ {factors.length - 6} more…</div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

