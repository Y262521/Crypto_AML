import { BrowserRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Sidebar } from './components/Sidebar'
import { AlertsPanel } from './components/AlertsPanel'
import { connectAlertsSocket } from './lib/alertsSocket'
import { fetchAlerts } from './lib/endpoints'
import type { AlertItem } from './types/api'

const Dashboard = lazy(() => import('./views/Dashboard').then((m) => ({ default: m.Dashboard })))
const PlaceholderPage = lazy(() => import('./views/PlaceholderPage').then((m) => ({ default: m.PlaceholderPage })))
const WatchlistPage = lazy(() => import('./views/Watchlist').then((m) => ({ default: m.WatchlistPage })))
const AlertSettingsPage = lazy(() => import('./views/AlertSettings').then((m) => ({ default: m.AlertSettingsPage })))
const GraphPage = lazy(() => import('./views/Graph').then((m) => ({ default: m.GraphPage })))
const BatchPage = lazy(() => import('./views/Batch').then((m) => ({ default: m.BatchPage })))
const TeamsPage = lazy(() => import('./views/Teams').then((m) => ({ default: m.TeamsPage })))
const ReportPage = lazy(() => import('./views/Report').then((m) => ({ default: m.ReportPage })))
const AuditPage = lazy(() => import('./views/Audit').then((m) => ({ default: m.AuditPage })))
const IndexerStatusPage = lazy(() => import('./views/IndexerStatus').then((m) => ({ default: m.IndexerStatusPage })))
const OrganizationPage = lazy(() => import('./views/Organization').then((m) => ({ default: m.OrganizationPage })))
const ReportBuilderPage = lazy(() => import('./views/ReportBuilder').then((m) => ({ default: m.ReportBuilderPage })))
const SimulatorPage = lazy(() => import('./views/Simulator').then((m) => ({ default: m.SimulatorPage })))
const ScreeningPage = lazy(() => import('./views/Screening').then((m) => ({ default: m.ScreeningPage })))

const PageLoader = () => (
  <div className="flex items-center justify-center h-48">
    <div className="flex flex-col items-center gap-3">
      <div className="h-8 w-8 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
      <span className="text-sm text-gray-500">Loading…</span>
    </div>
  </div>
)

function AppShell() {
  const navigate = useNavigate()
  const [panelOpen, setPanelOpen] = useState(false)
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [loadingAlerts, setLoadingAlerts] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const unreadCount = useMemo(() => alerts.filter((a) => !a.read).length, [alerts])

  useEffect(() => {
    const load = async () => {
      setLoadingAlerts(true)
      try {
        const data = await fetchAlerts()
        setAlerts(data)
      } finally {
        setLoadingAlerts(false)
      }
    }
    load().catch(() => {})
  }, [])

  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_ALERTS_WS_URL ?? process.env.VITE_ALERTS_WS_URL
    if (!url) return
    return connectAlertsSocket({
      url,
      onAlert: (a) => setAlerts((prev) => [a, ...prev]),
    })
  }, [])

  // Detect sidebar collapsed state from CSS variable / media query
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1024px)')
    setSidebarCollapsed(mq.matches)
    const handler = (e: MediaQueryListEvent) => setSidebarCollapsed(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  const onMarkAllRead = () => setAlerts((prev) => prev.map((a) => ({ ...a, read: true })))

  const onOpenAlert = (a: AlertItem) => {
    setAlerts((prev) => prev.map((x) => (x.id === a.id ? { ...x, read: true } : x)))
    setPanelOpen(false)
    navigate(`/address/${a.chain}/${a.address}`)
  }

  return (
    <div className="min-h-screen" style={{ background: '#0b0b10' }}>
      <Sidebar unreadCount={unreadCount} onOpenAlerts={() => setPanelOpen(true)} />

      {/* Main content — sidebar controls padding via #main-content */}
      <div
        id="main-content"
        className="transition-all duration-300"
        style={{ paddingTop: 'var(--header-height)' }}
      >
        {/* Inner content with max-width and padding */}
        <main className="min-h-screen">
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/address/:chain/:address" element={<Dashboard />} />
              <Route path="/graph/:chain/:address" element={<GraphPage />} />
              <Route path="/watchlist" element={<WatchlistPage />} />
              <Route path="/alerts" element={<AlertSettingsPage />} />
              <Route path="/batch" element={<BatchPage />} />
              <Route path="/teams" element={<TeamsPage />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/indexer-status" element={<IndexerStatusPage />} />
              <Route path="/organization" element={<OrganizationPage />} />
              <Route path="/report-builder" element={<ReportBuilderPage />} />
              <Route path="/simulator" element={<SimulatorPage />} />
              <Route path="/reports/:chain/:address" element={<ReportPage />} />
              <Route path="/screening" element={<ScreeningPage />} />
              <Route path="/screening/:chain/:address" element={<ScreeningPage />} />
              <Route path="/reports" element={<PlaceholderPage title="Reports" />} />
              <Route path="*" element={<PlaceholderPage title="Not Found" />} />
            </Routes>
          </Suspense>
        </main>
      </div>

      <AlertsPanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        alerts={alerts}
        loading={loadingAlerts}
        onMarkAllRead={onMarkAllRead}
        onOpenAlert={onOpenAlert}
      />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <AppShell />
      </ErrorBoundary>
    </BrowserRouter>
  )
}
