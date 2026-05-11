import { useEffect, useMemo, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Bell, LayoutDashboard, FileText, Menu, Star, Users, Layers, X, ShieldCheck } from 'lucide-react'
import { GlobalSearchBar } from './GlobalSearch'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/watchlist', label: 'Watchlist', icon: Star },
  { to: '/screening', label: 'Screening', icon: FileText },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/batch', label: 'Batch', icon: Layers },
  { to: '/teams', label: 'Teams', icon: Users },
  { to: '/audit', label: 'Audit', icon: FileText },
  { to: '/indexer-status', label: 'Indexer', icon: FileText },
  { to: '/organization', label: 'Org', icon: FileText },
  { to: '/report-builder', label: 'Report Builder', icon: FileText },
  { to: '/simulator', label: 'Simulator', icon: FileText },
  { to: '/reports', label: 'Reports', icon: FileText },
] as const

type Props = {
  unreadCount?: number
  onOpenAlerts?: () => void
}

export function Navbar({ unreadCount = 0, onOpenAlerts }: Props) {
  const [open, setOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  const activeLabel = useMemo(() => {
    const hit = navItems.find((n) => n.to === location.pathname)
    return hit?.label ?? 'Dashboard'
  }, [location.pathname])

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-black/30 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 sm:h-10 sm:w-10">
            <ShieldCheck className="h-5 w-5 text-white sm:h-6 sm:w-6" />
          </div>
          <div className="hidden flex-col sm:flex">
            <span className="text-lg font-bold leading-none text-white tracking-tight">
              Crypto<span className="text-violet-400">Shield</span>
            </span>
            <span className="text-[10px] font-medium text-gray-500 uppercase tracking-widest mt-0.5">
              Intelligence Platform
            </span>
          </div>
          <div className="flex flex-col sm:hidden">
            <span className="text-sm font-bold leading-none text-white tracking-tight">
              Crypto<span className="text-violet-400">Shield</span>
            </span>
            <div className="text-[10px] text-gray-400">{activeLabel}</div>
          </div>
        </div>

        <div className="hidden flex-1 justify-center px-2 md:flex">
          <GlobalSearchBar />
        </div>

        <nav className="hidden items-center gap-2 md:flex">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                [
                  'inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition',
                  isActive
                    ? 'border border-white/15 bg-white/[0.06] text-white'
                    : 'text-gray-300 hover:bg-white/[0.05] hover:text-white',
                ].join(' ')
              }
              end={item.to === '/'}
            >
              <span className="relative">
                <item.icon className="h-4 w-4" />
                {item.to === '/alerts' && unreadCount > 0 ? (
                  <span className="absolute -right-2.5 -top-2.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                ) : null}
              </span>
              {item.label}
            </NavLink>
          ))}

          <button
            type="button"
            className="btn-ghost ml-2"
            onClick={onOpenAlerts}
            aria-label="Open alerts panel"
          >
            <span className="relative">
              <Bell className="h-4 w-4" />
              {unreadCount > 0 ? (
                <span className="absolute -right-2.5 -top-2.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              ) : null}
            </span>
          </button>
        </nav>

        <div className="flex items-center gap-2 md:hidden">
          <button type="button" className="btn-ghost" onClick={onOpenAlerts} aria-label="Open alerts panel">
            <span className="relative">
              <Bell className="h-4 w-4" />
              {unreadCount > 0 ? (
                <span className="absolute -right-2.5 -top-2.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              ) : null}
            </span>
          </button>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? 'Close menu' : 'Open menu'}
          >
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {open ? (
        <div className="border-t border-white/10 bg-black/40 md:hidden overflow-y-auto max-h-[calc(100vh-60px)]">
          <div className="mx-auto w-full max-w-7xl px-4 py-4 flex flex-col gap-6">
            <div className="w-full">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-2 px-1">Quick Search</div>
              <GlobalSearchBar />
            </div>

            <div className="grid gap-2">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-1 px-1">Navigation</div>
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    [
                      'flex items-center justify-between rounded-xl border px-4 py-3 text-sm transition',
                      isActive
                        ? 'border-white/15 bg-white/[0.06] text-white'
                        : 'border-white/10 bg-white/[0.03] text-gray-300 hover:bg-white/[0.06] hover:text-white',
                    ].join(' ')
                  }
                >
                  <span className="flex items-center gap-2">
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </span>
                </NavLink>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </header>
  )
}

