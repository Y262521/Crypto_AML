import { BrowserRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Navbar } from './components/Navbar'
import { AlertsPanel } from './components/AlertsPanel'
import { connectAlertsSocket } from './lib/alertsSocket'
import { fetchAlerts } from './lib/endpoints'
import type { AlertItem } from './types/api'

const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })))
const PlaceholderPage = lazy(() => import('./pages/PlaceholderPage').then((m) => ({ default: m.PlaceholderPage })))
const WatchlistPage = lazy(() => import('./pages/Watchlist').then((m) => ({ default: m.WatchlistPage })))
const AlertSettingsPage = lazy(() => import('./pages/AlertSettings').then((m) => ({ default: m.AlertSettingsPage })))
const GraphPage = lazy(() => import('./pages/Graph').then((m) => ({ default: m.GraphPage })))
const BatchPage = lazy(() => import('./pages/Batch').then((m) => ({ default: m.BatchPage })))
const TeamsPage = lazy(() => import('./pages/Teams').then((m) => ({ default: m.TeamsPage })))
const ReportPage = lazy(() => import('./pages/Report').then((m) => ({ default: m.ReportPage })))
const AuditPage = lazy(() => import('./pages/Audit').then((m) => ({ default: m.AuditPage })))
const IndexerStatusPage = lazy(() => import('./pages/IndexerStatus').then((m) => ({ default: m.IndexerStatusPage })))
const OrganizationPage = lazy(() => import('./pages/Organization').then((m) => ({ default: m.OrganizationPage })))
const ReportBuilderPage = lazy(() => import('./pages/ReportBuilder').then((m) => ({ default: m.ReportBuilderPage })))
const SimulatorPage = lazy(() => import('./pages/Simulator').then((m) => ({ default: m.SimulatorPage })))
const ScreeningPage = lazy(() => import('./pages/Screening').then((m) => ({ default: m.ScreeningPage })))

function AppShell() {
  const navigate = useNavigate()
  const [panelOpen, setPanelOpen] = useState(false)
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [loadingAlerts, setLoadingAlerts] = useState(false)

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
    const url = import.meta.env.VITE_ALERTS_WS_URL
    if (!url) return
    return connectAlertsSocket({
      url,
      onAlert: (a) => setAlerts((prev) => [a, ...prev]),
    })
  }, [])

  const onMarkAllRead = () => {
    setAlerts((prev) => prev.map((a) => ({ ...a, read: true })))
  }

  const onOpenAlert = (a: AlertItem) => {
    setAlerts((prev) => prev.map((x) => (x.id === a.id ? { ...x, read: true } : x)))
    setPanelOpen(false)
    navigate(`/address/${a.chain}/${a.address}`)
  }

  return (
    <div className="min-h-screen bg-[#0F0F0F]">
      <Navbar unreadCount={unreadCount} onOpenAlerts={() => setPanelOpen(true)} />
      <main>
        <Suspense
          fallback={
            <div className="mx-auto w-full max-w-7xl px-4 py-6">
              <div className="glass p-6 text-sm text-gray-400">Loading page...</div>
            </div>
          }
        >
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

      <AlertsPanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        alerts={alerts}
        loading={loadingAlerts}
        onMarkAllRead={onMarkAllRead}
        onOpenAlert={onOpenAlert}
      />

      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'rgba(17,17,17,0.9)',
            color: 'rgba(229,231,235,0.95)',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: '14px',
            backdropFilter: 'blur(10px)',
          },
        }}
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
