import { useState, useEffect, useCallback, useRef } from 'react'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import GraphExplorer from './pages/GraphExplorer'
import Layering from './pages/Layering'
import Placement from './pages/Placement'
import Integration from './pages/Integration'
import Clusters from './pages/Clusters'
import LandingPage from './pages/LandingPage'
import ComingSoon from './pages/ComingSoon'
import { getLatestTransactions } from './services/transactionService'
import { DEFAULT_PAGE, buildPathForPage, getGraphAddressFromSearch, getPageFromPathname } from './utils/navigation'

const POLL_INTERVAL_MS = 30 * 60 * 1000
const TX_BATCH_SIZE = 200

const getInitialPage = () => typeof window === 'undefined' ? DEFAULT_PAGE : getPageFromPathname(window.location.pathname)
const getInitialInvestigateAddress = () => typeof window === 'undefined' ? '' : getGraphAddressFromSearch(window.location.search)

function App() {
  const [workspace, setWorkspace] = useState(null)
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
    if (append) { setTxLoadingMore(true) } else { setTxLoading(true); setTxError(null) }
    try {
      const data = await getLatestTransactions({ limit: TX_BATCH_SIZE, offset, sortBy: 'amount_desc' })
      const nextItems = data.items || []
      setTransactions(prev => append ? [...prev, ...nextItems] : nextItems)
      setTxTotal(data.total || nextItems.length)
      if (!append) setGraphVersion(v => v + 1)
      setLastUpdated(new Date())
    } catch (err) { setTxError(err.message) }
    finally { if (append) setTxLoadingMore(false); else setTxLoading(false) }
  }, [])

  useEffect(() => {
    fetchTransactions()
    intervalRef.current = setInterval(fetchTransactions, POLL_INTERVAL_MS)
    return () => clearInterval(intervalRef.current)
  }, [fetchTransactions])

  useEffect(() => {
    const sync = () => { setActivePage(getPageFromPathname(window.location.pathname)); setInvestigate(getGraphAddressFromSearch(window.location.search)) }
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
  }, [])

  const navigate = useCallback((page, { address = '' } = {}) => {
    const nextAddress = page === 'graph' ? address : ''
    const nextUrl = buildPathForPage(page, nextAddress)
    const currentUrl = `${window.location.pathname}${window.location.search}`
    if (currentUrl !== nextUrl) window.history.pushState({}, '', nextUrl)
    setActivePage(getPageFromPathname(window.location.pathname))
    setInvestigate(nextAddress)
  }, [])

  const handleLoadMore = useCallback(() => {
    if (txLoadingMore || transactions.length >= txTotal) return
    fetchTransactions({ append: true, offset: transactions.length })
  }, [fetchTransactions, transactions.length, txLoadingMore, txTotal])

  const handleInvestigate = (address) => navigate('graph', { address })
  const handleAddressClick = (address) => navigate('graph', { address })

  return (
    <div style={{ display:'flex', width:'100vw', height:'100vh', overflow:'hidden', background:'#0F1829' }}>

      {/* Landing page */}
      {workspace === null && (
        <div style={{ width:'100vw', height:'100vh', overflowY:'auto' }}>
          <LandingPage
            onEnterAML={() => { setWorkspace('aml'); navigate('feed') }}
            onEnterCluster={() => { setWorkspace('cluster'); navigate('coming-soon') }}
          />
        </div>
      )}

      {/* AML Workspace */}
      {workspace === 'aml' && (
        <>
          <Sidebar activePage={activePage} onNavigate={(page) => navigate(page)} onHome={() => setWorkspace(null)} />
          <main style={{ flex:1, padding:'24px', overflowY: activePage === 'graph' ? 'hidden' : 'auto', overflowX:'hidden', minWidth:0, height:'100vh', boxSizing:'border-box', display:'flex', flexDirection:'column', background:'#0F1829' }}>
            {activePage === 'feed'
              ? <Dashboard transactions={transactions} loading={txLoading} loadingMore={txLoadingMore} error={txError} onInvestigate={handleInvestigate} onLoadMore={handleLoadMore} lastUpdated={lastUpdated} totalTransactions={txTotal} />
              : activePage === 'graph'
                ? <GraphExplorer initialAddress={investigateAddress} graphVersion={graphVersion} lastUpdated={lastUpdated} />
                : activePage === 'placement'
                  ? <Placement onNavigateToGraph={(address) => navigate('graph', { address })} />
                  : activePage === 'layering'
                    ? <Layering onNavigateToGraph={(address) => navigate('graph', { address })} />
                    : activePage === 'clusters'
                      ? <Clusters onAddressClick={handleAddressClick} />
                      : activePage === 'integration'
                        ? <Integration onNavigateToGraph={(address) => navigate('graph', { address })} />
                        : null
            }
          </main>
        </>
      )}

      {/* Wallet Analysis Workspace — Coming Soon */}
      {workspace === 'cluster' && (
        <div style={{ width:'100vw', height:'100vh' }}>
          <ComingSoon onBack={() => setWorkspace(null)} />
        </div>
      )}
    </div>
  )
}

export default App
