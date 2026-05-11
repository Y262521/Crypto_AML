import { ArrowDownLeft, ArrowUpRight, Coins, Hash } from 'lucide-react'
import type { AddressSummary } from '../types/api'
import { Skeleton } from './Skeleton'

type Props = {
  data?: AddressSummary
  loading?: boolean
}

function formatNum(value: number | string) {
  const n = typeof value === 'string' ? Number(value) : value
  if (!Number.isFinite(n)) return String(value)
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 6 }).format(n)
}

export function SummaryCards({ data, loading }: Props) {
  if (loading) {
    return (
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="glass p-4">
            <div className="flex items-start justify-between gap-3">
              <Skeleton className="h-10 w-10 rounded-2xl" />
              <Skeleton className="h-4 w-24" />
            </div>
            <Skeleton className="mt-6 h-8 w-40" />
            <Skeleton className="mt-2 h-4 w-20" />
          </div>
        ))}
      </div>
    )
  }

  if (!data) return null

  const unit = data.unit

  const cards = [
    {
      title: 'Total received',
      value: `${formatNum(data.totalReceived)} ${unit}`,
      icon: ArrowDownLeft,
      iconClass: 'text-emerald-300',
      bgClass: 'bg-emerald-400/10',
      borderClass: 'border-emerald-400/20',
    },
    {
      title: 'Total sent',
      value: `${formatNum(data.totalSent)} ${unit}`,
      icon: ArrowUpRight,
      iconClass: 'text-rose-300',
      bgClass: 'bg-rose-400/10',
      borderClass: 'border-rose-400/20',
    },
    {
      title: 'Current balance',
      value: `${formatNum(data.balance)} ${unit}`,
      icon: Coins,
      iconClass: 'text-sky-300',
      bgClass: 'bg-sky-400/10',
      borderClass: 'border-sky-400/20',
    },
    {
      title: 'Transaction count',
      value: new Intl.NumberFormat().format(data.transactionCount),
      icon: Hash,
      iconClass: 'text-violet-300',
      bgClass: 'bg-violet-400/10',
      borderClass: 'border-violet-400/20',
    },
  ] as const

  return (
    <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <div key={c.title} className="glass glass-hover p-4">
          <div className="flex items-start justify-between gap-3">
            <div className={`rounded-2xl border p-2 ${c.bgClass} ${c.borderClass}`}>
              <c.icon className={`h-5 w-5 ${c.iconClass}`} />
            </div>
            <div className="text-xs text-gray-400">{c.title}</div>
          </div>
          <div className="mt-5 text-2xl font-semibold text-gray-100 break-all">{c.value}</div>
          <div className="mt-1 text-xs text-gray-500">Last updated: just now</div>
        </div>
      ))}
    </div>
  )
}

