import { useMemo } from 'react'
import { Bell, CheckCheck, X } from 'lucide-react'
import { Skeleton } from './Skeleton'
import type { AlertItem } from '../types/api'
import { shortenAddress } from '../lib/address'
import { getChainMeta } from '../lib/chains'

type Props = {
  open: boolean
  onClose: () => void
  alerts: AlertItem[]
  loading?: boolean
  onMarkAllRead: () => void
  onOpenAlert: (a: AlertItem) => void
}

function typeLabel(type: AlertItem['type']) {
  if (type === 'risk_increase') return { label: 'Risk increase', cls: 'border-amber-400/20 bg-amber-500/10 text-amber-200' }
  if (type === 'flagged_interaction') return { label: 'Flagged interaction', cls: 'border-rose-400/20 bg-rose-500/10 text-rose-200' }
  return { label: 'Large transaction', cls: 'border-sky-400/20 bg-sky-500/10 text-sky-200' }
}

export function AlertsPanel({
  open,
  onClose,
  alerts,
  loading,
  onMarkAllRead,
  onOpenAlert,
}: Props) {
  const unread = useMemo(() => alerts.filter((a) => !a.read).length, [alerts])

  return (
    <div className={['fixed inset-0 z-50', open ? '' : 'pointer-events-none'].join(' ')}>
      <div
        className={[
          'absolute inset-0 bg-black/60 transition-opacity',
          open ? 'opacity-100' : 'opacity-0',
        ].join(' ')}
        onClick={onClose}
      />

      <aside
        className={[
          'absolute right-0 top-0 h-full w-full max-w-md border-l border-white/10 bg-black/40 backdrop-blur-xl transition-transform',
          open ? 'translate-x-0' : 'translate-x-full',
        ].join(' ')}
      >
        <div className="flex items-center justify-between border-b border-white/10 p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-2">
              <Bell className="h-5 w-5 text-violet-300" />
            </div>
            <div>
              <div className="text-sm font-semibold text-gray-100">Alerts</div>
              <div className="mt-1 text-xs text-gray-400">{unread} unread</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" className="btn-ghost" onClick={onMarkAllRead} disabled={alerts.length === 0}>
              <CheckCheck className="h-4 w-4" />
              Mark as read
            </button>
            <button type="button" className="btn-ghost" onClick={onClose} aria-label="Close alerts panel">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="h-[calc(100%-72px)] overflow-y-auto p-4">
          {loading ? (
            <div className="grid gap-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="glass p-4">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="mt-3 h-4 w-64" />
                  <Skeleton className="mt-2 h-4 w-32" />
                </div>
              ))}
            </div>
          ) : alerts.length === 0 ? (
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 text-sm text-gray-400">
              No alerts yet.
            </div>
          ) : (
            <div className="grid gap-3">
              {alerts.map((a) => {
                const t = typeLabel(a.type)
                return (
                  <button
                    key={a.id}
                    type="button"
                    className={[
                      'glass glass-hover w-full p-4 text-left',
                      a.read ? 'opacity-80' : 'ring-1 ring-violet-400/15',
                    ].join(' ')}
                    onClick={() => onOpenAlert(a)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-gray-100">{a.title}</div>
                        <div className="mt-1 text-xs text-gray-400">
                          {getChainMeta(a.chain as any).name} • {shortenAddress(a.address, 10, 8)}
                        </div>
                      </div>
                      <div className={`shrink-0 rounded-full border px-3 py-1 text-[11px] ${t.cls}`}>
                        {t.label}
                      </div>
                    </div>
                    {a.message ? <div className="mt-3 text-xs text-gray-300">{a.message}</div> : null}
                    <div className="mt-3 text-[11px] text-gray-500">
                      {a.createdAt ? new Date(a.createdAt).toLocaleString() : '—'}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}

