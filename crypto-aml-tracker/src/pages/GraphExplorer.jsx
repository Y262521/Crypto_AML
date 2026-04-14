/**
 * Transaction Network — full-screen graph investigation view.
 *
 * Features:
 *  - Full-screen React Flow graph
 *  - Address search bar
 *  - Slide-in side panel on node click showing address details
 *  - "View on Etherscan" link
 *  - High-value node highlighting
 */
import { useEffect, useState, useMemo, useCallback } from 'react';
import { ReactFlow, Background, Controls, ReactFlowProvider, useNodesState, useEdgesState, MiniMap } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { getGraphData } from '../services/transactionService';
import { filterEdgesData, collapseLowActivityNodes, applyRadialLayout } from '../utils/graphUtils';
import Loader from '../components/common/Loader';

const HIGH_VALUE_THRESHOLD = Number(import.meta.env.VITE_HIGH_VALUE_THRESHOLD_ETH || 10);
const NODE_COLOR      = '#22c55e';
const HUB_COLOR       = '#ef4444';
const CONTRACT_COLOR  = '#f59e0b';
const SEND_EDGE       = '#2563eb';
const SUMMARY_NODE    = '#94a3b8';
const SUMMARY_EDGE    = '#94a3b8';

const nodeStyle = (isHighValue, isContract) => ({
  background: isHighValue ? HUB_COLOR : isContract ? CONTRACT_COLOR : NODE_COLOR,
  color: '#fff',
  borderRadius: '50%',
  fontSize: '11px', fontWeight: '700',
  padding: '14px 20px',
  border: isHighValue ? '3px solid #7f1d1d' : isContract ? '2px solid #92400e' : '2px solid #15803d',
  cursor: 'pointer',
  minWidth: '110px', minHeight: '44px',
  textAlign: 'center',
  boxShadow: isHighValue ? '0 0 12px rgba(239,68,68,0.4)' : 'none',
});

const summaryNodeStyle = {
  background: '#e2e8f0',
  color: '#0f172a',
  borderRadius: '12px',
  fontSize: '10px',
  fontWeight: '700',
  padding: '8px 10px',
  border: `1px dashed ${SUMMARY_NODE}`,
  minWidth: '90px',
  textAlign: 'center',
};

const buildWalletStats = (edgesData) => {
  const map = {};
  edgesData.forEach((tx) => {
    const amount = Number(tx.amount || 0);
    if (tx.sender) {
      if (!map[tx.sender]) {
        map[tx.sender] = {
          sentCount: 0,
          receivedCount: 0,
          totalSent: 0,
          totalReceived: 0,
          receivers: new Set(),
          senders: new Set(),
          maxTransaction: 0,
        };
      }
      map[tx.sender].sentCount += 1;
      map[tx.sender].totalSent += amount;
      map[tx.sender].maxTransaction = Math.max(map[tx.sender].maxTransaction, amount);
      if (tx.receiver) map[tx.sender].receivers.add(tx.receiver);
    }
    if (tx.receiver) {
      if (!map[tx.receiver]) {
        map[tx.receiver] = {
          sentCount: 0,
          receivedCount: 0,
          totalSent: 0,
          totalReceived: 0,
          receivers: new Set(),
          senders: new Set(),
          maxTransaction: 0,
        };
      }
      map[tx.receiver].receivedCount += 1;
      map[tx.receiver].totalReceived += amount;
      map[tx.receiver].maxTransaction = Math.max(map[tx.receiver].maxTransaction, amount);
      if (tx.sender) map[tx.receiver].senders.add(tx.sender);
    }
  });
  return map;
};

const buildGraph = (edgesData, options = {}) => {
  const filteredData = filterEdgesData(edgesData, {
    minValue: options.minValue,
    maxEdges: options.maxEdges,
  });
  const walletStats = buildWalletStats(filteredData);

  const nodesMap  = new Map();
  const edgesArray = [];

  filteredData.forEach((tx, index) => {
    const addNode = (addr, isContract = false) => {
      if (!addr || nodesMap.has(addr)) return;
      const isHighValue = (walletStats[addr]?.maxTransaction || 0) >= HIGH_VALUE_THRESHOLD;
      const size = nodesMap.size;
      nodesMap.set(addr, {
        id: addr,
        data: { label: `${addr.slice(0, 6)}...${addr.slice(-4)}` },
        position: { x: (size % 7) * 220, y: Math.floor(size / 7) * 150 },
        style: nodeStyle(isHighValue, isContract),
        draggable: true,
      });
    };

    addNode(tx.sender);
    if (tx.receiver && tx.receiver !== 'Contract Creation') addNode(tx.receiver);

    if (tx.sender && tx.receiver && tx.receiver !== 'Contract Creation') {
      const amt = parseFloat(tx.amount) > 0;
      edgesArray.push({
        id: `e-${index}`,
        source: tx.sender,
        target: tx.receiver,
        type: 'default',
        animated: false,
        label: amt ? `${parseFloat(tx.amount).toFixed(4)} ETH` : '',
        style: { stroke: SEND_EDGE, strokeWidth: 2 },
        markerEnd: { type: 'arrowclosed', color: SEND_EDGE, width: 20, height: 20 },
        labelStyle: { fontSize: '9px', fill: '#1e3a5f', fontWeight: '600' },
        labelBgStyle: { fill: '#eff6ff', fillOpacity: 0.85 },
      });
    }
  });

  let nodes = Array.from(nodesMap.values());
  let edges = edgesArray;
  let meta = { collapsed: 0, summaryNodes: 0, dropped: 0 };

  if (options.collapseLeaves || options.maxNodes) {
    const simplified = collapseLowActivityNodes({
      nodes,
      edges,
      centerId: options.centerId,
      maxNodes: options.maxNodes,
      leafDegree: 1,
      createSummaryNode: (id, hub, count) => ({
        id,
        data: { label: `+${count} low-activity` },
        position: { x: 0, y: 0 },
        style: summaryNodeStyle,
        draggable: true,
      }),
      createSummaryEdge: (id, hub, count) => ({
        id: `e-${hub}-${id}`,
        source: hub,
        target: id,
        type: 'default',
        animated: false,
        label: `${count} wallets`,
        style: { stroke: SUMMARY_EDGE, strokeWidth: 1.5, strokeDasharray: '4 4' },
        markerEnd: { type: 'arrowclosed', color: SUMMARY_EDGE, width: 16, height: 16 },
        labelStyle: { fontSize: '9px', fill: '#475569', fontWeight: '600' },
        labelBgStyle: { fill: '#f8fafc', fillOpacity: 0.9 },
      }),
    });
    nodes = simplified.nodes;
    edges = simplified.edges;
    meta = simplified.meta;
  }

  if (options.layout) {
    nodes = applyRadialLayout(nodes, edges, options.centerId, { ringSpacing: 210, minRadius: 70 });
  }

  return { nodes, edges, meta };
};

// ── Side panel shown when a node is clicked ───────────────────────────────────
const AddressPanel = ({ address, stats, edgesData, onClose }) => {
  const [showAllTx, setShowAllTx] = useState(false);
  const txList = edgesData.filter(tx => tx.sender === address || tx.receiver === address);
  const displayedTx = showAllTx ? txList.slice(0, 200) : txList.slice(0, 10);
  const hasMoreTransactions = txList.length > 10;
  const showLimit = Math.min(200, txList.length);

  if (!address) return null;

  return (
    <div style={{
      position: 'absolute', top: 0, right: 0, bottom: 0, width: '320px',
      background: '#fff', borderLeft: '1px solid #e2e8f0',
      boxShadow: '-4px 0 20px rgba(0,0,0,0.08)',
      display: 'flex', flexDirection: 'column', zIndex: 10,
      overflowY: 'auto',
    }}>
      {/* Header */}
      <div style={{ padding: '16px 18px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>
            {stats.isHighValue ? 'High-value address' : 'Address'}
          </div>
          <div style={{ fontSize: '11px', fontFamily: 'monospace', color: '#0f172a', wordBreak: 'break-all' }}>
            {address}
          </div>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: '18px', marginLeft: '8px', flexShrink: 0 }}>✕</button>
      </div>

      {/* Stats */}
      <div style={{ padding: '14px 18px', borderBottom: '1px solid #f1f5f9' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          {[
            ['Sent', `${stats.sentCount} txns`],
            ['Received', `${stats.receivedCount} txns`],
            ['Total Sent', `${stats.totalSent} ETH`],
            ['Total Received', `${stats.totalReceived} ETH`],
            ['Unique Receivers', stats.uniqueReceivers],
            ['Unique Senders', stats.uniqueSenders],
          ].map(([label, value]) => (
            <div key={label} style={{ background: '#f8fafc', borderRadius: '8px', padding: '10px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '10px', color: '#94a3b8', marginBottom: '3px' }}>{label}</div>
              <div style={{ fontSize: '13px', fontWeight: '700', color: '#0f172a' }}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Links */}
      <div style={{ padding: '12px 18px', borderBottom: '1px solid #f1f5f9', display: 'flex', gap: '8px' }}>
        <a href={`https://etherscan.io/address/${address}`} target="_blank" rel="noreferrer"
          style={{ flex: 1, textAlign: 'center', padding: '8px', background: '#eff6ff', color: '#1d4ed8', borderRadius: '7px', fontSize: '12px', fontWeight: '600', textDecoration: 'none', border: '1px solid #bfdbfe' }}>
          🔍 Etherscan
        </a>
        <a href={`https://etherscan.io/address/${address}#tokentxns`} target="_blank" rel="noreferrer"
          style={{ flex: 1, textAlign: 'center', padding: '8px', background: '#f0fdf4', color: '#166534', borderRadius: '7px', fontSize: '12px', fontWeight: '600', textDecoration: 'none', border: '1px solid #86efac' }}>
          🪙 Tokens
        </a>
      </div>

      {/* Recent transactions */}
      <div style={{ padding: '12px 18px', flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <div style={{ fontSize: '11px', fontWeight: '600', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Recent Transactions
          </div>
          {hasMoreTransactions && (
            <button
              type="button"
              onClick={() => setShowAllTx(prev => !prev)}
              style={{
                padding: '5px 10px', borderRadius: '8px', border: '1px solid #e2e8f0',
                background: '#f8fafc', color: '#334155', cursor: 'pointer', fontSize: '11px', fontWeight: '700'
              }}
            >
              {showAllTx ? 'Show less' : `View ${showLimit} of ${txList.length}`}
            </button>
          )}
        </div>
        {txList.length === 0
          ? <div style={{ color: '#94a3b8', fontSize: '12px' }}>No transactions found</div>
          : (
            <div style={{ marginBottom: '10px', fontSize: '11px', color: '#64748b' }}>
              Showing {displayedTx.length} of {txList.length} transactions{txList.length > 200 ? ' (first 200 shown)' : ''}.
            </div>
          )}
        {txList.length === 0
          ? null
          : displayedTx.map((tx, i) => {
            const isSender = tx.sender === address;
            return (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #f1f5f9', fontSize: '11px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                  <span style={{ color: isSender ? '#dc2626' : '#16a34a', fontWeight: '600' }}>
                    {isSender ? '↑ Sent' : '↓ Received'}
                  </span>
                  <span style={{ color: '#16a34a', fontWeight: '600' }}>{parseFloat(tx.amount).toFixed(6)} ETH</span>
                </div>
                <div style={{ color: '#64748b', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {isSender ? `→ ${tx.receiver?.slice(0, 12)}...` : `← ${tx.sender?.slice(0, 12)}...`}
                </div>
              </div>
            );
          })
        }
      </div>
    </div>
  );
};

// ── Main graph inner component ────────────────────────────────────────────────
const GraphExplorerInner = ({ initialAddress, graphVersion, lastUpdated }) => {
  const [edgesData, setEdgesData]       = useState([]);
  const [loading, setLoading]           = useState(true);
  const [search, setSearch]             = useState(initialAddress || '');
  const [submittedSearch, setSubmittedSearch] = useState(initialAddress || '');
  const [selectedWallet, setSelected]   = useState(null);
  const [walletStats, setWalletStats]   = useState(null);
  const [hops, setHops]                 = useState(2);
  const [edgeCap, setEdgeCap]           = useState(300);
  const [maxNodes, setMaxNodes]         = useState(200);
  const [minValue, setMinValue]         = useState(0);
  const [collapseLeaves, setCollapseLeaves] = useState(true);
  const [useLayout, setUseLayout]       = useState(true);
  const [graphMeta, setGraphMeta]       = useState({ collapsed: 0, summaryNodes: 0, dropped: 0 });
  const edgeOptions = useMemo(() => {
    const base = [200, 300, 400, 800, 1200, 2000];
    if (!base.includes(edgeCap)) base.push(edgeCap);
    return base.sort((a, b) => a - b);
  }, [edgeCap]);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const loadGraph = useCallback(async (term = '') => {
    setLoading(true);
    try {
      const trimmed = term.trim();
      const isExact = trimmed.startsWith('0x') && trimmed.length >= 10;
      const data = trimmed
        ? await getGraphData(isExact
          ? { center: trimmed, hops, maxEdges: edgeCap, minValue }
          : { search: trimmed, maxEdges: edgeCap, minValue }
        )
        : await getGraphData({ maxEdges: edgeCap, minValue });
      const filtered = filterEdgesData(data, { minValue, maxEdges: edgeCap });
      setEdgesData(filtered);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [edgeCap, hops, minValue]);

  // Load on mount, when graphVersion changes, or when a search is explicitly submitted.
  useEffect(() => {
    loadGraph(submittedSearch);
  }, [graphVersion, loadGraph, submittedSearch]);

  // Load when initialAddress changes (coming from table "Investigate" button)
  useEffect(() => {
    if (initialAddress) {
      const trimmed = initialAddress.trim();
      setSearch(trimmed);
      setSubmittedSearch(trimmed);
    }
  }, [initialAddress]);

  const rebuildGraph = useCallback(() => {
    if (!edgesData.length) {
      setNodes([]);
      setEdges([]);
      setGraphMeta({ collapsed: 0, summaryNodes: 0, dropped: 0 });
      return;
    }
    const { nodes: n, edges: e, meta } = buildGraph(edgesData, {
      centerId: submittedSearch,
      maxNodes,
      collapseLeaves,
      layout: useLayout,
      minValue,
      maxEdges: edgeCap,
    });
    setNodes([]);
    setEdges([]);
    setTimeout(() => { setNodes(n); setEdges(e); }, 0);
    setGraphMeta(meta);
  }, [collapseLeaves, edgeCap, edgesData, maxNodes, minValue, setEdges, setNodes, submittedSearch, useLayout]);

  useEffect(() => {
    rebuildGraph();
  }, [rebuildGraph]);

  const statsMap = useMemo(() => buildWalletStats(edgesData), [edgesData]);

  const handleNodeClick = useCallback((_, node) => {
    const addr = node.id;
    if (addr.startsWith('summary:')) return;
    const s    = statsMap[addr] || {};
    const out  = edges.filter(e => e.source === addr);
    const inc  = edges.filter(e => e.target === addr);
    setSelected(addr);
    setWalletStats({
      sentCount:       out.length,
      receivedCount:   inc.length,
      totalSent:       (s.totalSent || 0).toFixed(6),
      totalReceived:   (s.totalReceived || 0).toFixed(6),
      uniqueReceivers: s.receivers?.size || 0,
      uniqueSenders:   s.senders?.size || 0,
      isHighValue:     (s.maxTransaction || 0) >= HIGH_VALUE_THRESHOLD,
    });
  }, [statsMap, edges]);

  const handleSearch = (e) => {
    e.preventDefault();
    setEdgeCap(300);
    setSubmittedSearch(search.trim());
    setSelected(null);
    setWalletStats(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 48px)', gap: '12px', overflow: 'hidden' }}>

      {/* ── Toolbar ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>Transaction Network</div>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
            Showing {edges.length} edges · {nodes.length} nodes
            {graphMeta.summaryNodes ? ` · ${graphMeta.summaryNodes} summaries` : ''}
            {graphMeta.collapsed ? ` · ${graphMeta.collapsed} collapsed` : ''}
          </div>
        </div>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '8px', flex: 1, maxWidth: '480px' }}>
          <input
            type="text"
            placeholder="Enter wallet address to investigate..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              flex: 1, padding: '8px 14px', border: '1px solid #e2e8f0',
              borderRadius: '8px', fontSize: '13px', outline: 'none', background: '#fff',
            }}
          />
          <button type="submit" style={{
            padding: '8px 18px', background: '#0d1b2e', color: '#fff',
            border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '13px', fontWeight: '600',
          }}>
            Investigate
          </button>
          {search && (
            <button type="button" onClick={() => {
              setSearch('');
              setSubmittedSearch('');
            }} style={{
              padding: '8px 12px', background: '#f1f5f9', color: '#475569',
              border: '1px solid #e2e8f0', borderRadius: '8px', cursor: 'pointer', fontSize: '12px',
            }}>
              Clear
            </button>
          )}
        </form>
        {lastUpdated && (
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>
            Updated {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* ── Graph Controls ── */}
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
        <label style={{ fontSize: '11px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
          Hops
          <select value={hops} onChange={e => setHops(Number(e.target.value))}
            style={{ padding: '5px 8px', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '11px' }}>
            {[1, 2, 3].map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label style={{ fontSize: '11px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
          Max edges
          <select value={edgeCap} onChange={e => setEdgeCap(Number(e.target.value))}
            style={{ padding: '5px 8px', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '11px' }}>
            {edgeOptions.map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label style={{ fontSize: '11px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
          Max core nodes
          <select value={maxNodes} onChange={e => setMaxNodes(Number(e.target.value))}
            style={{ padding: '5px 8px', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '11px' }}>
            {[100, 200, 300, 500].map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label style={{ fontSize: '11px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
          Min ETH
          <select value={minValue} onChange={e => setMinValue(Number(e.target.value))}
            style={{ padding: '5px 8px', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '11px' }}>
            {[0, 0.1, 1, 5, 10].map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label style={{ fontSize: '11px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <input type="checkbox" checked={collapseLeaves} onChange={e => setCollapseLeaves(e.target.checked)} />
          Collapse low-activity
        </label>
        <label style={{ fontSize: '11px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <input type="checkbox" checked={useLayout} onChange={e => setUseLayout(e.target.checked)} />
          Auto layout
        </label>
        <button type="button" disabled={!submittedSearch} onClick={() => setEdgeCap(v => Math.min(v + 200, 2000))}
          style={{
            padding: '6px 12px', background: !submittedSearch ? '#f8fafc' : '#f1f5f9', color: !submittedSearch ? '#94a3b8' : '#334155',
            border: '1px solid #e2e8f0', borderRadius: '7px', cursor: !submittedSearch ? 'not-allowed' : 'pointer',
            fontSize: '11px', fontWeight: '600',
          }}>
          Load +200 edges
        </button>
      </div>

      {/* ── Legend ── */}
      <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: '#64748b', flexWrap: 'wrap' }}>
        <span><span style={{ color: NODE_COLOR, fontWeight: '700' }}>●</span> Normal wallet</span>
        <span><span style={{ color: HUB_COLOR, fontWeight: '700' }}>●</span> High-value wallet (10+ ETH tx)</span>
        <span><span style={{ color: CONTRACT_COLOR, fontWeight: '700' }}>●</span> Contract</span>
        <span><span style={{ color: SUMMARY_NODE, fontWeight: '700' }}>●</span> Summary node</span>
        <span style={{ color: '#94a3b8' }}>Drag nodes · Scroll to zoom · Click node for details</span>
      </div>

      {/* ── Graph canvas ── */}
      <div style={{ flex: 1, position: 'relative', borderRadius: '12px', overflow: 'hidden', border: '1px solid #e2e8f0', background: '#f9fafb', minHeight: 0 }}>
        {loading
          ? <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <Loader />
            </div>
          : nodes.length === 0
            ? <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
                <div style={{ fontSize: '48px', marginBottom: '12px' }}>❋</div>
                <div style={{ fontSize: '15px', fontWeight: '600', color: '#475569' }}>No graph data</div>
                <div style={{ fontSize: '13px', marginTop: '6px' }}>Enter a wallet address above to investigate</div>
              </div>
            : (
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={handleNodeClick}
                fitView
                fitViewOptions={{ padding: 0.15 }}
                onlyRenderVisibleElements
                style={{ width: '100%', height: '100%' }}
              >
                <Background color="#e2e8f0" gap={20} />
                <Controls />
                <MiniMap
                  nodeColor={n => {
                    const s = statsMap[n.id];
                    return (s?.maxTransaction || 0) >= HIGH_VALUE_THRESHOLD ? HUB_COLOR : NODE_COLOR;
                  }}
                  style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
                />
              </ReactFlow>
            )
        }

        {/* Side panel */}
        {selectedWallet && (
          <AddressPanel
            address={selectedWallet}
            stats={walletStats || {}}
            edgesData={edgesData}
            onClose={() => setSelected(null)}
          />
        )}
      </div>
    </div>
  );
};

export default function GraphExplorer({ initialAddress, graphVersion, lastUpdated }) {
  return (
    <ReactFlowProvider>
      <GraphExplorerInner initialAddress={initialAddress} graphVersion={graphVersion} lastUpdated={lastUpdated} />
    </ReactFlowProvider>
  );
}
