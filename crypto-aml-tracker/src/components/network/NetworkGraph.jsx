import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { ReactFlow, Background, Controls, ReactFlowProvider, useNodesState, useEdgesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { getGraphData } from '../../services/transactionService';

const SUSPICIOUS_THRESHOLD = 3;
const NODE_COLOR = '#22c55e';
const SUSPICIOUS_COLOR = '#ef4444';
const SEND_EDGE = '#2563eb';

const nodeStyle = (isSuspicious) => ({
  background: isSuspicious ? SUSPICIOUS_COLOR : NODE_COLOR,
  color: '#fff',
  borderRadius: '50%',
  fontSize: '12px',
  fontWeight: '600',
  padding: '16px 24px',
  border: isSuspicious ? '3px solid #7f1d1d' : '2px solid #15803d',
  cursor: 'grab',
  minWidth: '120px',
  minHeight: '50px',
  textAlign: 'center',
});

const WalletPopup = ({ wallet, data, onClose }) => {
  if (!wallet) return null;
  return (
    <div style={{
      position: 'absolute', top: '80px', right: '20px', zIndex: 1000,
      background: '#fff', borderRadius: '12px', padding: '16px 20px',
      boxShadow: '0 4px 24px rgba(0,0,0,0.15)', minWidth: '260px',
      border: '1px solid #e5e7eb',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <strong style={{ fontSize: '14px' }}>{data.isSuspicious ? '⚠️ Suspicious Wallet' : '👛 Wallet'}</strong>
        <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '16px', color: '#6b7280' }}>✕</button>
      </div>
      <div style={{ fontSize: '11px', color: '#6b7280', wordBreak: 'break-all', marginBottom: '12px', background: '#f3f4f6', padding: '6px 8px', borderRadius: '6px' }}>
        {wallet}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
        {[['Sent', `${data.sentCount} txns`], ['Received', `${data.receivedCount} txns`],
        ['Total Sent', `${data.totalSent} ETH`], ['Unique Receivers', data.uniqueReceivers]
        ].map(([label, value]) => (
          <div key={label} style={{ background: '#f9fafb', borderRadius: '8px', padding: '8px', border: '1px solid #e5e7eb' }}>
            <div style={{ fontSize: '10px', color: '#9ca3af', marginBottom: '2px' }}>{label}</div>
            <div style={{ fontSize: '13px', fontWeight: '600', color: '#111827' }}>{value}</div>
          </div>
        ))}
      </div>
      <a href={`https://etherscan.io/address/${wallet}`} target="_blank" rel="noreferrer"
        style={{ color: '#3b82f6', fontSize: '13px', textDecoration: 'none', fontWeight: 500 }}>
        🔍 View on Etherscan →
      </a>
    </div>
  );
};

const buildGraph = (edgesData) => {
  const senderMap = {};
  edgesData.forEach(tx => {
    if (tx.sender) {
      if (!senderMap[tx.sender]) senderMap[tx.sender] = new Set();
      senderMap[tx.sender].add(tx.receiver);
    }
  });

  const nodesMap = new Map();
  const edgesArray = [];

  edgesData.forEach((tx, index) => {
    if (tx.sender && !nodesMap.has(tx.sender)) {
      const isSuspicious = (senderMap[tx.sender]?.size || 0) >= SUSPICIOUS_THRESHOLD;
      const size = nodesMap.size;
      nodesMap.set(tx.sender, {
        id: tx.sender,
        data: { label: `${isSuspicious ? '⚠️ ' : ''}${tx.sender.slice(0, 6)}...${tx.sender.slice(-4)}` },
        position: { x: (size % 6) * 240, y: Math.floor(size / 6) * 160 },
        style: nodeStyle(isSuspicious),
        draggable: true,
      });
    }
    if (tx.receiver && tx.receiver !== 'Contract Creation' && !nodesMap.has(tx.receiver)) {
      const size = nodesMap.size;
      nodesMap.set(tx.receiver, {
        id: tx.receiver,
        data: { label: `${tx.receiver.slice(0, 6)}...${tx.receiver.slice(-4)}` },
        position: { x: (size % 6) * 240, y: Math.floor(size / 6) * 160 },
        style: nodeStyle(false),
        draggable: true,
      });
    }
    if (tx.sender && tx.receiver && tx.receiver !== 'Contract Creation') {
      const amt = parseFloat(tx.amount) > 0;
      edgesArray.push({
        id: `e-${index}`,
        source: tx.sender,
        target: tx.receiver,
        type: 'default',
        animated: false,
        label: amt ? `${tx.amount} ETH` : '',
        style: { stroke: SEND_EDGE, strokeWidth: 2.5 },
        markerEnd: { type: 'arrowclosed', color: SEND_EDGE, width: 25, height: 25 },
        labelStyle: { fontSize: '10px', fill: '#1e3a5f', fontWeight: '600' },
        labelBgStyle: { fill: '#eff6ff', fillOpacity: 0.8 },
      });
    }
  });

  return { nodes: Array.from(nodesMap.values()), edges: edgesArray };
};

const NetworkGraphInner = ({ graphVersion, onRefresh, searchAddress: initialSearch, onSearchChange }) => {
  const [edgesData, setEdgesData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedWallet, setSelectedWallet] = useState(null);
  const [walletStats, setWalletStats] = useState(null);

  // search is fully controlled by parent via searchAddress prop
  const search = initialSearch || '';

  const handleSearchChange = (val) => {
    if (onSearchChange) onSearchChange(val);
  };

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const loadGraph = useCallback(async (searchTerm = '') => {
    try {
      const data = await getGraphData(searchTerm);
      setEdgesData(data);
      const { nodes: n, edges: e } = buildGraph(data);
      setNodes([]);
      setEdges([]);
      setTimeout(() => {
        setNodes(n);
        setEdges(e);
      }, 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [setNodes, setEdges]);

  // Reload graph whenever graphVersion changes (driven by parent fetch)
  useEffect(() => {
    setLoading(true);
    loadGraph('');
  }, [graphVersion, loadGraph]);

  // When search changes, fetch graph data filtered by that address
  useEffect(() => {
    if (search) {
      setLoading(true);
      loadGraph(search);
    }
  }, [search, loadGraph]);

  const handleRefresh = async () => {
    setRefreshing(true);
    if (onRefresh) {
      await onRefresh();
    } else {
      await loadGraph('');
    }
  };

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
    const s = statsMap[addr] || {};
    // Count edges in the actual graph for this node
    const incomingEdges = edges.filter(e => e.target === addr);
    const outgoingEdges = edges.filter(e => e.source === addr);
    setSelectedWallet(addr);
    setWalletStats({
      sentCount: outgoingEdges.length,
      receivedCount: incomingEdges.length,
      totalSent: (s.totalSent || 0).toFixed(6),
      uniqueReceivers: outgoingEdges.length,
      isSuspicious: (s.receivers?.size || 0) >= SUSPICIOUS_THRESHOLD,
    });
  }, [statsMap, edges]);

  // No frontend filtering needed — backend handles search
  const filteredNodes = nodes;
  const filteredEdges = edges;

  if (loading) return <div style={{ padding: '2rem' }}>Loading graph from Neo4j...</div>;

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', alignItems: 'center' }}>
        <input type="text" placeholder="Search wallet address..." value={search}
          onChange={e => handleSearchChange(e.target.value)}
          style={{ flex: 1, padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '13px' }} />
        <button onClick={handleRefresh} disabled={refreshing}
          style={{ padding: '8px 16px', background: '#0e032bff', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
          {refreshing ? 'Fetching...' : ' Refresh'}
        </button>
      </div>
      <div style={{ display: 'flex', gap: '16px', marginBottom: '8px', fontSize: '12px', flexWrap: 'wrap' }}>
        <span><span style={{ color: NODE_COLOR }}>●</span> Wallet (drag to move)</span>
        <span><span style={{ color: SUSPICIOUS_COLOR }}>●</span> ⚠️ Suspicious</span>
        <span><span style={{ color: SEND_EDGE }}>→</span> Blue = transaction direction</span>
        <span style={{ color: '#6b7280' }}>Click node for details</span>
      </div>
      {filteredNodes.length === 0
        ? <div style={{ padding: '2rem', color: '#666' }}>No results{search ? ` for "${search}"` : ''}.</div>
        : (
          <div style={{ width: '100%', height: '600px', border: '1px solid #ddd', borderRadius: '8px', background: '#f9fafb' }}>
            <ReactFlow
              nodes={filteredNodes}
              edges={filteredEdges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={handleNodeClick}
              fitView
              fitViewOptions={{ padding: 0.2 }}
            >
              <Background />
              <Controls />
            </ReactFlow>
            <WalletPopup wallet={selectedWallet} data={walletStats || {}} onClose={() => setSelectedWallet(null)} />
          </div>
        )
      }
    </div>
  );
};

const NetworkGraph = ({ graphVersion, onRefresh, searchAddress, onSearchChange }) => (
  <ReactFlowProvider>
    <NetworkGraphInner graphVersion={graphVersion} onRefresh={onRefresh} searchAddress={searchAddress} onSearchChange={onSearchChange} />
  </ReactFlowProvider>
);

export default NetworkGraph;
