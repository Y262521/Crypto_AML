import { useState, useEffect, useCallback, useRef } from 'react'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import GraphExplorer from './pages/GraphExplorer'
import Analytics from './pages/Analytics'
import Layering from './pages/Layering'
import Placement from './pages/Placement'
import Integration from './pages/Integration'
import Clusters from './pages/Clusters'
import { getLatestTransactions } from './services/transactionService'
import {
  DEFAULT_PAGE,
  buildPathForPage,
  getGraphAddressFromSearch,
  getPageFromPathname,
} from './utils/navigation'

const POLL_INTERVAL_MS = 30 * 60 * 1000  // 30 minutes
const TX_BATCH_SIZE = 200

const getInitialPage = () => (
  typeof window === 'undefined'
    ? DEFAULT_PAGE
    : getPageFromPathname(window.location.pathname)
)

const getInitialInvestigateAddress = () => (
  typeof window === 'undefined'
    ? ''
    : getGraphAddressFromSearch(window.location.search)
)

function App() {
  const [activePage, setActivePage] = useState(getInitialPage)
  const [transactions, setTransactions] = useState([])
  const [txLoading, setTxLoading] = useState(true)
  const [txLoadingMore, setTxLoadingMore] = useState(false)
  const [txError, setTxError] = useState(null)
  const [txTotal, setTxTotal] = useState(0)
  const [graphVersion, setGraphVersion] = useState(0)
  const [investigateAddress, setInvestigate] = useState(getInitialInvestigateAddress)
  const [lastUpdated, setLastUpdated] = useState(null)
  const intervalRef = useRef(null)

  const fetchTransactions = useCallback(async ({ append = false, offset = 0 } = {}) => {
    if (append) {
      setTxLoadingMore(true)
    } else {
      setTxLoading(true)
      setTxError(null)
    }
    try {
      const data = await getLatestTransactions({
        limit: TX_BATCH_SIZE,
        offset,
        sortBy: 'amount_desc',
      })
      const nextItems = data.items || []
      setTransactions(prev => append ? [...prev, ...nextItems] : nextItems)
      setTxTotal(data.total || nextItems.length)
      if (!append) {
        setGraphVersion(v => v + 1)
      }
      setLastUpdated(new Date())
    } catch (err) {
      setTxError(err.message)
    } finally {
      if (append) {
        setTxLoadingMore(false)
      } else {
        setTxLoading(false)
      }
    }
  }, [])

  // Initial fetch + 30-minute auto-poll
  useEffect(() => {
    fetchTransactions()
    intervalRef.current = setInterval(fetchTransactions, POLL_INTERVAL_MS)
    return () => clearInterval(intervalRef.current)
  }, [fetchTransactions])

  useEffect(() => {
    const syncFromLocation = () => {
      setActivePage(getPageFromPathname(window.location.pathname))
      setInvestigate(getGraphAddressFromSearch(window.location.search))
    }

    window.addEventListener('popstate', syncFromLocation)
    return () => window.removeEventListener('popstate', syncFromLocation)
  }, [])

  const navigate = useCallback((page, { address = '' } = {}) => {
    const nextAddress = page === 'graph' ? address : ''
    const nextUrl = buildPathForPage(page, nextAddress)
    const currentUrl = `${window.location.pathname}${window.location.search}`

    if (currentUrl !== nextUrl) {
      window.history.pushState({}, '', nextUrl)
    }

    setActivePage(getPageFromPathname(window.location.pathname))
    setInvestigate(nextAddress)
  }, [])

  const handleLoadMoreTransactions = useCallback(() => {
    if (txLoadingMore || transactions.length >= txTotal) return
    fetchTransactions({ append: true, offset: transactions.length })
  }, [fetchTransactions, transactions.length, txLoadingMore, txTotal])

  // Called when user clicks "Investigate" on a transaction row
  const handleInvestigate = (address) => {
    navigate('graph', { address })
  }

  // Called when user clicks an address in Clusters
  const handleAddressClick = (address) => {
    navigate('graph', { address })
  }

  return (
    <div style={{
      display: 'flex',
      width: '100vw',
      height: '100vh',
      overflow: 'hidden',
      background: '#f8fafc',
    }}>
      <Sidebar
        activePage={activePage}
        onNavigate={(page) => navigate(page, { address: page === 'graph' ? investigateAddress : '' })}
      />
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
            loadingMore={txLoadingMore}
            error={txError}
            onInvestigate={handleInvestigate}
            onLoadMore={handleLoadMoreTransactions}
            lastUpdated={lastUpdated}
            totalTransactions={txTotal}
          />
          : activePage === 'graph'
            ? <GraphExplorer
              initialAddress={investigateAddress}
              graphVersion={graphVersion}
              lastUpdated={lastUpdated}
            />
            : activePage === 'analytics'
              ? <Analytics />
              : activePage === 'placement'
                ? <Placement onNavigateToGraph={(address) => navigate('graph', { address })} />
                : activePage === 'layering'
                  ? <Layering onNavigateToGraph={(address) => navigate('graph', { address })} />
                  : activePage === 'integration'
                    ? <Integration onNavigateToGraph={(address) => navigate('graph', { address })} />
                    : activePage === 'clusters'
                      ? <Clusters onAddressClick={handleAddressClick} />
                      : null
        }
      </main>
    </div>
  )
}

export default App
