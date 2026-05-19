import { useState, useEffect, useCallback, useRef } from 'react'
import './styles/nbe-theme.css'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import GraphExplorer from './pages/GraphExplorer'
import Layering from './pages/Layering'
import Placement from './pages/Placement'
import Integration from './pages/Integration'
import MarketValueIndex from './pages/MarketValueIndex'
import Clusters from './pages/Clusters'
import Analytics from './pages/Analytics'
import RiskIntelligence from './pages/RiskIntelligence'
import ComingSoon from './pages/ComingSoon'
import EntityIntelligenceWorkspace from './components/intelligence/EntityIntelligenceWorkspace'
import AnalysisMenu from './components/intelligence/AnalysisMenu'
import { getLatestTransactions } from './services/transactionService'
import { DEFAULT_PAGE, buildPathForPage, getGraphAddressFromSearch, getPageFromPathname } from './utils/navigation'

const POLL_INTERVAL_MS = 30 * 60 * 1000
const TX_BATCH_SIZE = 200

const getInitialPage = () => typeof window === 'undefined' ? DEFAULT_PAGE : getPageFromPathname(window.location.pathname)
const getInitialInvestigateAddress = () => typeof window === 'undefined' ? '' : getGraphAddressFromSearch(window.location.search)

function App() {
  const [workspace, setWorkspace] = useState('aml')
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
  
  // Entity Intelligence Workspace state
  const [entityWorkspace, setEntityWorkspace] = useState(null) // { entityId, entityType, sourcePage, analysisType }
  
  // Analysis Menu state
  const [analysisMenu, setAnalysisMenu] = useState(null) // { entityId, entityType, position }

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
  
  // Show analysis menu when clicking an entity
  const showAnalysisMenu = useCallback((entityId, entityType, event) => {
    event.preventDefault();
    event.stopPropagation();
    
    // Get click position
    const x = event.clientX;
    const y = event.clientY;
    
    // Adjust position if menu would go off screen
    const adjustedX = x + 400 > window.innerWidth ? x - 400 : x;
    const adjustedY = y + 500 > window.innerHeight ? y - 500 : y;
    
    setAnalysisMenu({
      entityId,
      entityType,
      position: { x: adjustedX, y: adjustedY }
    });
  }, []);
  
  // Close analysis menu
  const closeAnalysisMenu = useCallback(() => {
    setAnalysisMenu(null);
  }, []);
  
  // Handle analysis selection from menu
  const handleAnalysisSelect = useCallback((analysisType) => {
    if (!analysisMenu) return;
    
    // Get current page name
    const pageNames = {
      'feed': 'Dashboard',
      'graph': 'Graph Explorer',
      'placement': 'Placement',
      'layering': 'Layering',
      'integration': 'Integration',
      'market-value': 'Market Value Index',
      'clusters': 'Clusters',
      'analytics': 'Analytics',
      'risk': 'Risk Intelligence'
    };
    
    const sourcePage = pageNames[activePage] || 'Unknown';
    
    // Open workspace with selected analysis
    setEntityWorkspace({
      entityId: analysisMenu.entityId,
      entityType: analysisMenu.entityType,
      sourcePage,
      analysisType
    });
    
    // Close menu
    setAnalysisMenu(null);
  }, [analysisMenu, activePage]);
  
  // Open Entity Intelligence Workspace (legacy - for backward compatibility)
  const openEntityWorkspace = useCallback((entityId, entityType, sourcePage, analysisType = 'market-value') => {
    setEntityWorkspace({ entityId, entityType, sourcePage, analysisType })
  }, [])
  
  const closeEntityWorkspace = useCallback(() => {
    setEntityWorkspace(null)
  }, [])
  
  const walletWorkspaceUrl = import.meta.env.VITE_WALLET_ANALYSIS_URL
    || `http://${window.location.hostname}:3000`

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden', background: '#0F1829' }}>

      {/* AML Workspace */}
      {workspace === 'aml' && (
        <>
          <Sidebar activePage={activePage} onNavigate={(page) => navigate(page)} onHome={() => navigate('feed')} />
          <main style={{ flex: 1, padding: '24px', overflowY: activePage === 'graph' ? 'hidden' : 'auto', overflowX: 'hidden', minWidth: 0, height: '100vh', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', background: '#0F1829' }}>
            {activePage === 'feed'
              ? <Dashboard transactions={transactions} loading={txLoading} loadingMore={txLoadingMore} error={txError} onInvestigate={handleInvestigate} onLoadMore={handleLoadMore} lastUpdated={lastUpdated} totalTransactions={txTotal} />
              : activePage === 'graph'
                ? <GraphExplorer initialAddress={investigateAddress} graphVersion={graphVersion} lastUpdated={lastUpdated} />
                : activePage === 'placement'
                  ? <Placement onNavigateToGraph={(address) => navigate('graph', { address })} onShowAnalysisMenu={showAnalysisMenu} onOpenWorkspace={openEntityWorkspace} />
                  : activePage === 'layering'
                    ? <Layering onNavigateToGraph={(address) => navigate('graph', { address })} onShowAnalysisMenu={showAnalysisMenu} onOpenWorkspace={openEntityWorkspace} />
                    : activePage === 'clusters'
                      ? <Clusters onAddressClick={handleAddressClick} onShowAnalysisMenu={showAnalysisMenu} />
                      : activePage === 'integration'
                        ? <Integration onNavigateToGraph={(address) => navigate('graph', { address })} onShowAnalysisMenu={showAnalysisMenu} onOpenWorkspace={openEntityWorkspace} />
                        : activePage === 'market-value'
                          ? <MarketValueIndex onOpenWorkspace={openEntityWorkspace} onNavigateToGraph={(address) => navigate('graph', { address })} />
                          : activePage === 'analytics'
                          ? <Analytics />
                          : activePage === 'risk'
                            ? <RiskIntelligence />
                            : null
            }
          </main>
          
          {/* Analysis Menu */}
          {analysisMenu && (
            <AnalysisMenu
              entityId={analysisMenu.entityId}
              entityType={analysisMenu.entityType}
              position={analysisMenu.position}
              onSelect={handleAnalysisSelect}
              onClose={closeAnalysisMenu}
            />
          )}
          
          {/* Entity Intelligence Workspace */}
          {entityWorkspace && (
            <EntityIntelligenceWorkspace
              entityId={entityWorkspace.entityId}
              entityType={entityWorkspace.entityType}
              sourcePage={entityWorkspace.sourcePage}
              initialTab={entityWorkspace.analysisType}
              onClose={closeEntityWorkspace}
              onNavigateToGraph={(address) => {
                closeEntityWorkspace();
                navigate('graph', { address });
              }}
            />
          )}
        </>
      )}

      {/* Wallet Analysis Workspace — embedded iframe */}
      {workspace === 'cluster' && (
        <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', background: '#0F1829' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 20px', borderBottom: '1px solid rgba(201,168,76,0.14)', background: '#0A1020', flexShrink: 0 }}>
            <button
              onClick={() => {
                setWorkspace('aml')
                navigate('feed')
              }}
              style={{ padding: '6px 14px', background: 'rgba(201,168,76,0.08)', border: '1px solid rgba(201,168,76,0.2)', borderRadius: '7px', color: '#C9A84C', fontSize: '12px', fontWeight: '600', cursor: 'pointer' }}
            >
              ← Home
            </button>
            <span style={{ fontSize: '12px', color: '#64748B' }}>Wallet Analysis Workspace</span>
          </div>
          <iframe
            src={walletWorkspaceUrl}
            style={{ flex: 1, border: 'none', width: '100%' }}
            title="Wallet Analysis Workspace"
          />
        </div>
      )}
    </div>
  )
}

export default App
