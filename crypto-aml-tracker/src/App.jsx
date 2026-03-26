import { useState, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Alerts from './pages/Alerts'
import Analytics from './pages/Analytics'
import { getLatestTransactions, refreshTransactions } from './services/transactionService'

function App() {
  const [activePage, setActivePage] = useState('feed')
  const [transactions, setTransactions] = useState([])
  const [txLoading, setTxLoading] = useState(true)
  const [txError, setTxError] = useState(null)
  const [graphVersion, setGraphVersion] = useState(0)
  const [searchAddress, setSearchAddress] = useState('')

  const fetchTransactions = useCallback(async () => {
    setTxLoading(true)
    setTxError(null)
    try {
      const data = await getLatestTransactions()
      setTransactions(data)
      setGraphVersion(v => v + 1)
    } catch (err) {
      setTxError(err.message)
    } finally {
      setTxLoading(false)
    }
  }, [])

  const handleRefresh = useCallback(async () => {
    setTxLoading(true)
    setTxError(null)
    try {
      const data = await refreshTransactions()
      setTransactions(data)
      setGraphVersion(v => v + 1)
    } catch (err) {
      setTxError(err.message)
    } finally {
      setTxLoading(false)
    }
  }, [])

  useEffect(() => { fetchTransactions() }, [fetchTransactions])

  const handleAddressClick = (address) => {
    setSearchAddress(address)
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
        overflowY: 'auto',
        overflowX: 'hidden',
        minWidth: 0,
      }}>
        {activePage === 'alerts'
          ? <Alerts onAddressClick={handleAddressClick} />
          : activePage === 'analytics'
            ? <Analytics />
            : <Dashboard
              activePage={activePage}
              transactions={transactions}
              loading={txLoading}
              error={txError}
              onRefresh={handleRefresh}
              graphVersion={graphVersion}
              onAddressClick={handleAddressClick}
              searchAddress={searchAddress}
              onSearchChange={setSearchAddress}
            />
        }
      </main>
    </div>
  )
}

export default App
