import { useState, useEffect, useCallback, useRef } from 'react'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import GraphExplorer from './pages/GraphExplorer'
import Alerts from './pages/Alerts'
import Analytics from './pages/Analytics'
import Clusters from './pages/Clusters'
import { getLatestTransactions } from './services/transactionService'

const POLL_INTERVAL_MS = 30 * 60 * 1000  // 30 minutes

function App() {
  const [activePage, setActivePage]         = useState('feed')
  const [transactions, setTransactions]     = useState([])
  const [txLoading, setTxLoading]           = useState(true)
  const [txError, setTxError]               = useState(null)
  const [graphVersion, setGraphVersion]     = useState(0)
  const [investigateAddress, setInvestigate] = useState('')  // address to pre-load in graph
  const [lastUpdated, setLastUpdated]       = useState(null)
  const intervalRef = useRef(null)

  const fetchTransactions = useCallback(async () => {
    setTxLoading(true)
    setTxError(null)
    try {
      const data = await getLatestTransactions()
      setTransactions(data)
      setGraphVersion(v => v + 1)
      setLastUpdated(new Date())
    } catch (err) {
      setTxError(err.message)
    } finally {
      setTxLoading(false)
    }
  }, [])

  // Initial fetch + 30-minute auto-poll
  useEffect(() => {
    fetchTransactions()
    intervalRef.current = setInterval(fetchTransactions, POLL_INTERVAL_MS)
    return () => clearInterval(intervalRef.current)
  }, [fetchTransactions])

  // Called when user clicks "Investigate" on a transaction row
  const handleInvestigate = (address) => {
    setInvestigate(address)
    setActivePage('graph')
  }

  // Called when user clicks an address in Alerts/Clusters
  const handleAddressClick = (address) => {
    setInvestigate(address)
    setActivePage('graph')
  }

  return (
    <div style={{
      display: 'flex',
      width: '100vw',
      height: '100vh',
      overflow: 'hidden',
      background: '#f8fafc',
    }}>
      <Sidebar activePage={activePage} onNavigate={setActivePage} />
      <main style={{
        flex: 1,
        padding: '24px',
        overflowY: activePage === 'graph' ? 'hidden' : 'auto',
        overflowX: 'hidden',
        minWidth: 0,
        height: '100vh',
        boxSizing: 'border-box',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {activePage === 'feed'
          ? <Dashboard
              transactions={transactions}
              loading={txLoading}
              error={txError}
              onInvestigate={handleInvestigate}
              lastUpdated={lastUpdated}
            />
          : activePage === 'graph'
            ? <GraphExplorer
                initialAddress={investigateAddress}
                graphVersion={graphVersion}
                lastUpdated={lastUpdated}
              />
            : activePage === 'alerts'
              ? <Alerts onAddressClick={handleAddressClick} />
              : activePage === 'analytics'
                ? <Analytics />
                : activePage === 'clusters'
                  ? <Clusters onAddressClick={handleAddressClick} />
                  : null
        }
      </main>
    </div>
  )
}

export default App
