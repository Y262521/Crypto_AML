/**
 * Transaction Network — full-screen graph investigation view.
 *
 * Features:
 *  - Full-screen React Flow graph
 *  - Address search bar
 *  - Slide-in side panel on node click showing address details
 *  - "View on Etherscan" link
 *  - Suspicious node highlighting
 */
import { useEffect, useState, useMemo, useCallback } from 'react';
import { ReactFlow, Background, Controls, ReactFlowProvider, useNodesState, useEdgesState, MiniMap } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { getGraphData } from '../services/transactionService';
import Loader from '../components/common/Loader';

const SUSPICIOUS_THRESHOLD = 3;
const NODE_COLOR      = '#22c55e';
const SUSPICIOUS_COLOR = '#ef4444';
const CONTRACT_COLOR  = '#f59e0b';
const SEND_EDGE       = '#2563eb';

const nodeStyle = (isSuspicious, isContract) => ({
  background: isSuspicious ? SUSPICIOUS_COLOR : isContract ? CONTRACT_COLOR : NODE_COLOR,
  color: '#fff',
  borderRadius: '50%',
  fontSize: '11px', fontWeight: '700',
  padding: '14px 20px',
  border: isSuspicious ? '3px solid #7f1d1d' : isContract ? '2px solid #92400e' : '2px solid #15803d',
  cursor: 'pointer',
  minWidth: '110px', minHeight: '44px',
  textAlign: 'center',
  boxShadow: isSuspicious ? '0 0 12px rgba(239,68,68,0.4)' : 'none',
});

const buildGraph = (edgesData) => {
  const senderMap = {};
  edgesData.forEach(tx => {
    if (tx.sender) {
      if (!senderMap[tx.sender]) senderMap[tx.sender] = new Set();
      senderMap[tx.sender].add(tx.receiver);
    }
  });

  const nodesMap  = new Map();
  const edgesArray = [];

  edgesData.forEach((tx, index) => {
    const addNode = (addr, isContract = false) => {
      if (!addr || nodesMap.has(addr)) return;
      const isSuspicious = (senderMap[addr]?.size || 0) >= SUSPICIOUS_THRESHOLD;
      const size = nodesMap.size;
      nodesMap.set(addr, {
        id: addr,
        data: { label: `${isSuspicious ? '⚠️ ' : ''}${addr.slice(0, 6)}...${addr.slice(-4)}` },
        position: { x: (size % 7) * 220, y: Math.floor(size / 7) * 150 },
        style: nodeStyle(isSuspicious, isContract),
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

  return { nodes: Array.from(nodesMap.values()), edges: edgesArray };
};

// ── Side panel shown when a node is clicked ───────────────────────────────────
const AddressPanel = ({ address, stats, edgesData, onClose }) => {
  if (!address) return null;

  const txList = edgesData.filter(tx => tx.sender === address || tx.receiver === address).slice(0, 10);

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
            {stats.isSuspicious ? '⚠️ Suspicious Address' : '👛 Address'}
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
            ['Unique Receivers', stats.uniqueReceivers],
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
        <div style={{ fontSize: '11px', fontWeight: '600', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px' }}>
          Recent Transactions
        </div>
        {txList.length === 0
          ? <div style={{ color: '#94a3b8', fontSize: '12px' }}>No transactions found</div>
          : txList.map((tx, i) => {
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
  const [selectedWallet, setSelected]   = useState(null);
  const [walletStats, setWalletStats]   = useState(null);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const loadGraph = useCallback(async (term = '') => {
    setLoading(true);
    try {
      const data = await getGraphData(term);
      setEdgesData(data);
      const { nodes: n, edges: e } = buildGraph(data);
      setNodes([]);
      setEdges([]);
      setTimeout(() => { setNodes(n); setEdges(e); }, 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges]);

  // Load on mount / when graphVersion changes (auto-poll)
  useEffect(() => { loadGraph(search); }, [graphVersion]);

  // Load when initialAddress changes (coming from table "Investigate" button)
  useEffect(() => {
    if (initialAddress) {
      setSearch(initialAddress);
      loadGraph(initialAddress);
    }
  }, [initialAddress]);

  const statsMap = useMemo(() => {
    const map = {};
    edgesData.forEach(tx => {
      if (tx.sender) {
        if (!map[tx.sender]) map[tx.sender] = { sentCount: 0, receivedCount: 0, totalSent: 0, receivers: new Set() };
        map[tx.sender].sentCount++;
        map[tx.sender].totalSent += parseFloat(tx.amount) || 0;
        if (tx.receiver) map[tx.sender].receivers.add(tx.receiver);
      }
      if (tx.receiver) {
        if (!map[tx.receiver]) map[tx.receiver] = { sentCount: 0, receivedCount: 0, totalSent: 0, receivers: new Set() };
        map[tx.receiver].receivedCount++;
      }
    });
    return map;
  }, [edgesData]);

  const handleNodeClick = useCallback((_, node) => {
    const addr = node.id;
    const s    = statsMap[addr] || {};
    const out  = edges.filter(e => e.source === addr);
    const inc  = edges.filter(e => e.target === addr);
    setSelected(addr);
    setWalletStats({
      sentCount:       out.length,
      receivedCount:   inc.length,
      totalSent:       (s.totalSent || 0).toFixed(6),
      uniqueReceivers: out.length,
      isSuspicious:    (s.receivers?.size || 0) >= SUSPICIOUS_THRESHOLD,
    });
  }, [statsMap, edges]);

  const handleSearch = (e) => {
    e.preventDefault();
    loadGraph(search);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 48px)', gap: '12px', overflow: 'hidden' }}>

      {/* ── Toolbar ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>Transaction Network</div>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
            {edgesData.length} edges · {nodes.length} addresses
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
            <button type="button" onClick={() => { setSearch(''); loadGraph(''); }} style={{
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

      {/* ── Legend ── */}
      <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: '#64748b', flexWrap: 'wrap' }}>
        <span><span style={{ color: NODE_COLOR, fontWeight: '700' }}>●</span> Normal wallet</span>
        <span><span style={{ color: SUSPICIOUS_COLOR, fontWeight: '700' }}>●</span> ⚠️ Suspicious (3+ receivers)</span>
        <span><span style={{ color: CONTRACT_COLOR, fontWeight: '700' }}>●</span> Contract</span>
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
                style={{ width: '100%', height: '100%' }}
              >
                <Background color="#e2e8f0" gap={20} />
                <Controls />
                <MiniMap
                  nodeColor={n => {
                    const s = statsMap[n.id];
                    return (s?.receivers?.size || 0) >= SUSPICIOUS_THRESHOLD ? SUSPICIOUS_COLOR : NODE_COLOR;
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
