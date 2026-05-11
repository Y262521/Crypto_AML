'use client'

import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Star,
  ShieldCheck,
  Bell,
  Layers,
  Users,
  FileText,
  Activity,
  Building2,
  FileBarChart2,
  Cpu,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
} from 'lucide-react'
import { GlobalSearchBar } from './GlobalSearch'

const NAV_SECTIONS = [
  {
    label: 'Analysis',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
      { to: '/watchlist', label: 'Watchlist', icon: Star },
      { to: '/screening', label: 'Screening', icon: ShieldCheck },
      { to: '/batch', label: 'Batch Analysis', icon: Layers },
      { to: '/simulator', label: 'Simulator', icon: Cpu },
    ],
  },
  {
    label: 'Monitoring',
    items: [
      { to: '/alerts', label: 'Alerts', icon: Bell, badge: true },
      { to: '/graph', label: 'Graph', icon: Activity, hidden: true }, // accessed via address
    ],
  },
  {
    label: 'Reports',
    items: [
      { to: '/report-builder', label: 'Report Builder', icon: FileBarChart2 },
      { to: '/reports', label: 'Reports', icon: FileText },
    ],
  },
  {
    label: 'Admin',
    items: [
      { to: '/teams', label: 'Teams', icon: Users },
      { to: '/audit', label: 'Audit Log', icon: FileText },
      { to: '/indexer-status', label: 'Indexer', icon: Activity },
      { to: '/organization', label: 'Organization', icon: Building2 },
    ],
  },
]

type Props = {
  unreadCount?: number
  onOpenAlerts?: () => void
}

export function Sidebar({ unreadCount = 0, onOpenAlerts }: Props) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  // Collapse sidebar on small screens by default
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1024px)')
    const handler = (e: MediaQueryListEvent) => {
      if (e.matches) setCollapsed(true)
    }
    if (mq.matches) setCollapsed(true)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  // Sync collapsed state to document so main content can offset correctly
  useEffect(() => {
    const el = document.getElementById('main-content')
    if (!el) return
    if (collapsed) {
      el.style.paddingLeft = '64px'
    } else {
      el.style.paddingLeft = '240px'
    }
  }, [collapsed])

  const sidebarContent = (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div className={[
        'flex items-center border-b border-white/[0.07] transition-all duration-300',
        collapsed ? 'justify-center px-0 py-3' : 'gap-3 px-4 py-3',
      ].join(' ')}>
        <div className={[
          'shrink-0 rounded-full overflow-hidden bg-[#0d1b2e] border border-white/10',
          collapsed ? 'h-9 w-9' : 'h-10 w-10',
        ].join(' ')}>
          <img
            src="/logo.jpg"
            alt="National Bank of Ethiopia"
            className="h-full w-full object-cover"
            onError={(e) => {
              // Fallback to icon if image not found
              const target = e.currentTarget
              target.style.display = 'none'
              const parent = target.parentElement
              if (parent) {
                parent.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-amber-400 m-auto mt-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>'
              }
            }}
          />
        </div>
        {!collapsed && (
          <div className="min-w-0 animate-fade-in">
            <div className="text-sm font-bold leading-tight text-white tracking-tight">
              Wallet<span className="text-amber-400">Analysis</span>
            </div>
            <div className="text-[10px] text-gray-500 uppercase tracking-widest mt-0.5">
              NBE Intelligence
            </div>
          </div>
        )}
      </div>

      {/* Search — only when expanded */}
      {!collapsed && (
        <div className="px-3 py-3 border-b border-white/[0.07] animate-fade-in">
          <GlobalSearchBar compact />
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-3 scrollbar-hide">
        {NAV_SECTIONS.map((section) => {
          const visibleItems = section.items.filter((i) => !i.hidden)
          if (visibleItems.length === 0) return null
          return (
            <div key={section.label} className="mb-1">
              {!collapsed && (
                <div className="nav-section-label">{section.label}</div>
              )}
              {visibleItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={'end' in item ? item.end : false}
                  className={({ isActive }) =>
                    [
                      'nav-item mx-2 mb-0.5',
                      isActive ? 'active' : '',
                      collapsed ? 'justify-center px-0 py-2.5' : '',
                    ].join(' ')
                  }
                  title={collapsed ? item.label : undefined}
                >
                  <span className="relative shrink-0 nav-icon">
                    <item.icon className="h-4 w-4" />
                    {'badge' in item && item.badge && unreadCount > 0 && (
                      <span className="absolute -right-2 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[9px] font-bold text-white">
                        {unreadCount > 99 ? '99+' : unreadCount}
                      </span>
                    )}
                  </span>
                  {!collapsed && (
                    <span className="truncate">{item.label}</span>
                  )}
                </NavLink>
              ))}
            </div>
          )
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-white/[0.07] p-2">
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className={[
            'nav-item w-full',
            collapsed ? 'justify-center px-0' : '',
          ].join(' ')}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed
            ? <ChevronRight className="h-4 w-4" />
            : <><ChevronLeft className="h-4 w-4" /><span className="text-xs">Collapse</span></>
          }
        </button>
      </div>
    </div>
  )

  return (
    <>
      {/* ── Desktop sidebar ─────────────────────────────────────────────────── */}
      <aside
        className={[
          'hidden lg:flex flex-col fixed left-0 top-0 h-screen z-30 transition-all duration-300',
          'border-r border-white/[0.07]',
          collapsed ? 'w-16' : 'w-60',
        ].join(' ')}
        style={{ background: '#0a0a0f' }}
      >
        {sidebarContent}
      </aside>

      {/* ── Mobile top bar ──────────────────────────────────────────────────── */}
      <header className="lg:hidden fixed top-0 left-0 right-0 z-40 flex items-center justify-between gap-3 border-b border-white/[0.07] px-4 py-3"
        style={{ background: 'rgba(10,10,15,0.95)', backdropFilter: 'blur(20px)', height: 'var(--header-height)' }}>
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-full overflow-hidden bg-[#0d1b2e] border border-white/10 shrink-0">
            <img
              src="/logo.jpg"
              alt="NBE"
              className="h-full w-full object-cover"
              onError={(e) => { e.currentTarget.style.display = 'none' }}
            />
          </div>
          <div>
            <div className="text-sm font-bold text-white leading-tight">
              Wallet<span className="text-amber-400">Analysis</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="btn-ghost p-2" onClick={onOpenAlerts}>
            <span className="relative">
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span className="absolute -right-2 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[9px] font-bold text-white">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </span>
          </button>
          <button type="button" className="btn-ghost p-2" onClick={() => setMobileOpen((v) => !v)}>
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </header>

      {/* ── Mobile drawer ───────────────────────────────────────────────────── */}
      {mobileOpen && (
        <>
          <div
            className="lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <aside
            className="lg:hidden fixed left-0 top-0 h-screen w-72 z-50 border-r border-white/[0.07] animate-slide-in"
            style={{ background: '#0a0a0f' }}
          >
            {sidebarContent}
          </aside>
        </>
      )}
    </>
  )
}
