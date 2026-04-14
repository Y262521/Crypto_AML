import { useEffect, useState } from 'react';
import { ReactFlow, ReactFlowProvider, Background, Controls } from '@xyflow/react';
import { getClusters, getClustersSummary, getGraphData, runClustering } from '../services/transactionService';
import { filterEdgesData, applyRadialLayout } from '../utils/graphUtils';
import Loader from '../components/common/Loader';

const StatCard = ({ label, value, sub, color }) => (
    <div style={{
        background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0',
        padding: '18px 22px', flex: 1, minWidth: '160px',
    }}>
        <div style={{ fontSize: '24px', fontWeight: '700', color: color || '#0f172a' }}>{value}</div>
        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>{label}</div>
        {sub && <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>{sub}</div>}
    </div>
);

const formatEth = (value) => {
    const num = Number(value || 0);
    if (!Number.isFinite(num)) return '0';
    return num.toLocaleString(undefined, { maximumFractionDigits: 6 });
};

const formatOwner = (owner) => {
    if (!owner) return '—';
    return owner.full_name || '—';
};

const formatLocation = (owner) => {
    if (!owner) return '—';
    const parts = [
        owner.specifics,
        owner.street_address,
        owner.locality,
        owner.city,
        owner.administrative_area,
        owner.postal_code,
        owner.country
    ].filter(Boolean);
    return parts.length ? parts.join(', ') : '—';
};

const truncate = (value, maxLength = 24) => {
    if (!value || value.length <= maxLength) return value || '—';
    return `${value.slice(0, maxLength - 3)}...`;
};

const buildPreviewGraph = (edgesData, centerId) => {
    const filtered = filterEdgesData(edgesData, { minValue: 0, maxEdges: 80 });
    const nodesMap = new Map();
    const edges = [];

    filtered.forEach((tx, index) => {
        const sender = tx.sender;
        const receiver = tx.receiver;
        if (!sender || !receiver) return;

        const labelFor = (address) => `${address.slice(0, 6)}...${address.slice(-4)}`;

        if (!nodesMap.has(sender)) {
            nodesMap.set(sender, {
                id: sender,
                data: { label: labelFor(sender) },
                position: { x: 0, y: 0 },
                style: {
                    background: '#22c55e', color: '#fff', borderRadius: '50%',
                    padding: '12px 18px', fontSize: '11px', fontWeight: '700',
                    border: sender === centerId ? '3px solid #1d4ed8' : '2px solid #15803d',
                },
            });
        }
        if (!nodesMap.has(receiver)) {
            nodesMap.set(receiver, {
                id: receiver,
                data: { label: labelFor(receiver) },
                position: { x: 0, y: 0 },
                style: {
                    background: '#0ea5e9', color: '#fff', borderRadius: '50%',
                    padding: '12px 18px', fontSize: '11px', fontWeight: '700',
                    border: '2px solid #0284c7',
                },
            });
        }

        edges.push({
            id: `e-${index}`,
            source: sender,
            target: receiver,
            type: 'default',
            animated: false,
            label: `${Number(tx.amount || 0).toFixed(4)} ETH`,
            style: { stroke: '#2563eb', strokeWidth: 1.8 },
            markerEnd: { type: 'arrowclosed', color: '#2563eb', width: 16, height: 16 },
            labelStyle: { fontSize: '9px', fill: '#1e3a5f', fontWeight: '600' },
            labelBgStyle: { fill: '#eff6ff', fillOpacity: 0.9 },
        });
    });

    const nodes = Array.from(nodesMap.values());
    const positioned = nodes.length ? applyRadialLayout(nodes, edges, centerId, { ringSpacing: 180, minRadius: 80 }) : nodes;
    return { nodes: positioned, edges };
};

const getActivityHighlights = (activity, riskLevel) => {
    const highlights = [];
    const totalFlow = (activity.total_in || 0) + (activity.total_out || 0);
    if ((activity.total_tx_count || 0) > 80) {
        highlights.push('High transaction density between members');
    } else if ((activity.total_tx_count || 0) > 20) {
        highlights.push('Moderate internal transaction activity');
    } else {
        highlights.push('Low internal transaction activity');
    }

    if (totalFlow > 50) {
        highlights.push('Large internal ETH movement');
    } else if (totalFlow > 5) {
        highlights.push('Moderate ETH activity inside the cluster');
    }

    if (riskLevel && riskLevel !== 'normal') {
        highlights.push(`Risk level flagged: ${riskLevel}`);
    }

    return highlights;
};

export default function Clusters({ onAddressClick }) {
    const [clusters, setClusters] = useState([]);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedCluster, setSelectedCluster] = useState(null);
    const [running, setRunning] = useState(false);
    const [showAllAddresses, setShowAllAddresses] = useState(false);
    const [preview, setPreview] = useState({ nodes: [], edges: [] });
    const [previewLoading, setPreviewLoading] = useState(false);
    const [previewError, setPreviewError] = useState(null);

    const loadData = () => {
        setLoading(true);
        setError(null);
        Promise.all([getClusters(), getClustersSummary()])
            .then(([c, s]) => { setClusters(c); setSummary(s); setLoading(false); })
            .catch(err => { setError(err.message); setLoading(false); });
    };

    useEffect(() => {
        loadData();
    }, []);

    useEffect(() => {
        if (!selectedCluster) {
            setShowAllAddresses(false);
            setPreview({ nodes: [], edges: [] });
            setPreviewError(null);
            return;
        }

        const centerAddress = selectedCluster.addresses?.[0]?.address || selectedCluster.addresses?.[0];
        if (!centerAddress) {
            setPreview({ nodes: [], edges: [] });
            return;
        }

        setPreviewLoading(true);
        setPreviewError(null);
        getGraphData({ center: centerAddress, maxEdges: 80, minValue: 0 })
            .then((data) => {
                setPreview(buildPreviewGraph(data, centerAddress));
            })
            .catch((err) => {
                setPreviewError(err.message || 'Unable to load cluster preview.');
                setPreview({ nodes: [], edges: [] });
            })
            .finally(() => setPreviewLoading(false));
    }, [selectedCluster]);

    const handleRunClustering = async () => {
        setRunning(true);
        setError(null);
        try {
            await runClustering();
            loadData();
        } catch (err) {
            setError(err.message);
        } finally {
            setRunning(false);
        }
    };

    const closeDrawer = () => setSelectedCluster(null);
    const openClusterDrawer = (cluster) => setSelectedCluster(cluster);

    const evidenceHeaderText = selectedCluster
        ? `Behavior observed from ${selectedCluster.addresses?.length ?? 0} cluster addresses.`
        : '';

    if (loading) return <Loader />;
    if (error) return (
        <div style={{ padding: '2rem', color: '#64748b' }}>
            <div style={{ fontSize: '16px', marginBottom: '8px', color: '#ef4444' }}>
                Could not load clusters.
            </div>
            <div style={{ fontSize: '13px' }}>{error}</div>
        </div>
    );

    const th = {
        textAlign: 'left', padding: '10px 14px',
        borderBottom: '2px solid #e2e8f0',
        color: '#475569', fontSize: '11px', fontWeight: '600',
        textTransform: 'uppercase', letterSpacing: '0.05em',
    };
    const td = { padding: '10px 14px', borderBottom: '1px solid #f1f5f9', fontSize: '12px', color: '#334155' };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>

            {/* Header + actions */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                <div>
                    <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>Wallet Clusters</div>
                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                        {clusters.length} clusters · behavioral ownership grouping
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                    <button onClick={loadData} style={{
                        padding: '8px 14px', borderRadius: '8px', border: '1px solid #e2e8f0',
                        background: '#fff', color: '#334155', fontSize: '12px', fontWeight: '600',
                        cursor: 'pointer',
                    }}>Refresh</button>
                    <button onClick={handleRunClustering} disabled={running} style={{
                        padding: '8px 16px', borderRadius: '8px', border: 'none',
                        background: running ? '#94a3b8' : '#0d1b2e', color: '#fff',
                        fontSize: '12px', fontWeight: '600', cursor: running ? 'not-allowed' : 'pointer',
                    }}>{running ? 'Clustering…' : 'Run Clustering'}</button>
                </div>
            </div>

            {/* Summary cards */}
            {summary && (
                <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
                    <StatCard label="Total Clusters" value={summary.total} />
                    <StatCard label="Top Internal Flow" value={summary.top_by_balance?.[0]?.cluster_id || '—'}
                        sub={summary.top_by_balance?.[0] ? `${formatEth(summary.top_by_balance[0].total_balance)} ETH` : ''} />
                    <StatCard label="Top Size" value={summary.top_by_size?.[0]?.cluster_id || '—'}
                        sub={summary.top_by_size?.[0] ? `${summary.top_by_size[0].cluster_size} addresses` : ''} />
                </div>
            )}

            {/* Clusters table */}
            <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                {clusters.length === 0 ? (
                    <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
                        No clusters available yet. Run clustering to generate ownership groups.
                    </div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
                        <thead>
                            <tr style={{ background: '#e2e8f0' }}>
                                <th style={{ ...th, width: '20%' }}>Cluster ID</th>
                                <th style={{ ...th, width: '18%' }}>Owner</th>
                                <th style={{ ...th, width: '28%' }}>Location</th>
                                <th style={{ ...th, width: '12%' }}>Members</th>
                                <th style={{ ...th, width: '22%' }}>Total Balance</th>
                            </tr>
                        </thead>
                        <tbody>
                            {clusters.map((c) => {
                                const memberCount = c.addresses?.length ?? c.cluster_size ?? 0;
                                return (
                                    <tr key={c.cluster_id}
                                        onClick={() => openClusterDrawer(c)}
                                        style={{ cursor: 'pointer' }}
                                        onMouseEnter={(e) => { e.currentTarget.style.background = '#f8fafc'; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.background = ''; }}>
                                        <td style={{ ...td, fontFamily: 'monospace', fontSize: '11px' }} title={c.cluster_id}>
                                            {`${c.cluster_id.slice(0, 10)}...${c.cluster_id.slice(-6)}`}
                                        </td>
                                        <td style={td}>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); openClusterDrawer(c); }}
                                                style={{
                                                    background: 'transparent', border: 'none', padding: 0, margin: 0,
                                                    color: '#1d4ed8', fontWeight: '600', cursor: 'pointer',
                                                    textAlign: 'left', fontSize: '12px'
                                                }}
                                                title={formatLocation(c.owner)}
                                            >
                                                {formatOwner(c.owner)}
                                            </button>
                                        </td>
                                        <td style={{ ...td, fontSize: '11px', color: '#64748b' }} title={formatLocation(c.owner)}>
                                            {truncate(formatLocation(c.owner), 45)}
                                        </td>
                                        <td style={td}>{memberCount}</td>
                                        <td style={{ ...td, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <span style={{ fontWeight: '700', color: '#0f172a' }}>{formatEth(c.total_balance)} ETH</span>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); openClusterDrawer(c); }}
                                                style={{
                                                    border: '1px solid #e2e8f0', borderRadius: '8px', padding: '6px 10px',
                                                    background: '#fff', color: '#334155', fontSize: '11px', fontWeight: '600',
                                                    cursor: 'pointer'
                                                }}
                                            >
                                                View
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>

            {selectedCluster && (
                <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', justifyContent: 'flex-end', pointerEvents: 'auto' }}>
                    <div
                        onClick={closeDrawer}
                        style={{ position: 'absolute', inset: 0, background: 'rgba(15, 23, 42, 0.26)' }}
                    />
                    <aside style={{ position: 'relative', width: 'min(560px,100%)', maxWidth: '560px', height: '100%', background: '#fff', boxShadow: '-24px 0 80px rgba(15, 23, 42, 0.18)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                        <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '16px' }}>
                            <div>
                                <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>Cluster details</div>
                                <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>Cluster ID: {selectedCluster.cluster_id}</div>
                            </div>
                            <button onClick={closeDrawer} style={{ border: 'none', background: 'transparent', color: '#475569', fontSize: '14px', fontWeight: '700', cursor: 'pointer' }}>Close</button>
                        </div>
                        <div style={{ padding: '24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '24px' }}>
                            <section style={{ display: 'grid', gap: '14px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Owner Profile</div>
                                <div>
                                    <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>{formatOwner(selectedCluster.owner)}</div>
                                    <div style={{ marginTop: '8px', color: '#64748b', fontSize: '13px', lineHeight: '1.6' }}>
                                        {formatLocation(selectedCluster.owner)}
                                    </div>
                                </div>
                                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                                    <div style={{ padding: '12px 14px', borderRadius: '14px', background: '#f8fafc', border: '1px solid #e2e8f0', minWidth: '140px' }}>
                                        <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>Members</div>
                                        <div style={{ fontSize: '16px', fontWeight: '700', color: '#0f172a' }}>{selectedCluster.addresses?.length ?? selectedCluster.cluster_size}</div>
                                    </div>
                                    <div style={{ padding: '12px 14px', borderRadius: '14px', background: '#f8fafc', border: '1px solid #e2e8f0', minWidth: '140px' }}>
                                        <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>Total Balance</div>
                                        <div style={{ fontSize: '16px', fontWeight: '700', color: '#0f172a' }}>{formatEth(selectedCluster.total_balance)} ETH</div>
                                    </div>
                                    <div style={{ padding: '12px 14px', borderRadius: '14px', background: '#f8fafc', border: '1px solid #e2e8f0', minWidth: '140px' }}>
                                        <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>Internal Flow</div>
                                        <div style={{ fontSize: '16px', fontWeight: '700', color: '#0f172a' }}>{formatEth(selectedCluster.activity.total_in)} in / {formatEth(selectedCluster.activity.total_out)} out</div>
                                    </div>
                                </div>
                            </section>

                            <section style={{ display: 'grid', gap: '12px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Activity / Behavior</div>
                                <div style={{ display: 'grid', gap: '10px', padding: '16px', borderRadius: '16px', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                                    {getActivityHighlights(selectedCluster.activity, selectedCluster.risk_level).map((line, idx) => (
                                        <div key={idx} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                                            <div style={{ width: '6px', height: '6px', marginTop: '8px', borderRadius: '50%', background: '#0f172a' }} />
                                            <div style={{ fontSize: '13px', color: '#334155', lineHeight: '1.5' }}>{line}</div>
                                        </div>
                                    ))}
                                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>Total transactions: {selectedCluster.activity.total_tx_count}</div>
                                </div>
                            </section>

                            <section style={{ display: 'grid', gap: '14px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Address List</div>
                                {selectedCluster.addresses?.length ? (
                                    <div style={{ display: 'grid', gap: '10px' }}>
                                        {(showAllAddresses ? selectedCluster.addresses : selectedCluster.addresses.slice(0, 5)).map((item) => (
                                            <div key={item.address} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px', padding: '14px', borderRadius: '14px', border: '1px solid #e2e8f0', background: '#fff' }}>
                                                <div>
                                                    <div style={{ fontFamily: 'monospace', fontSize: '12px', color: '#0f172a' }} title={item.address}>{truncate(item.address, 28)}</div>
                                                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                                                        {formatEth(item.total_in)} in · {formatEth(item.total_out)} out
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={() => onAddressClick && onAddressClick(item.address)}
                                                    style={{ border: '1px solid #e2e8f0', borderRadius: '10px', padding: '8px 12px', background: '#f8fafc', color: '#0f172a', fontSize: '11px', fontWeight: '600', cursor: 'pointer' }}
                                                >
                                                    Graph
                                                </button>
                                            </div>
                                        ))}
                                        {selectedCluster.addresses.length > 5 && (
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
                                                <div style={{ fontSize: '11px', color: '#64748b' }}>
                                                    {showAllAddresses
                                                        ? `Showing all ${selectedCluster.addresses.length} addresses`
                                                        : `Showing 5 of ${selectedCluster.addresses.length} addresses`}
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={(e) => { e.stopPropagation(); setShowAllAddresses((prev) => !prev); }}
                                                    style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '6px 10px', background: '#fff', color: '#334155', fontSize: '11px', fontWeight: '600', cursor: 'pointer' }}
                                                >
                                                    {showAllAddresses ? 'Show less' : `Show all ${selectedCluster.addresses.length}`}
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div style={{ padding: '16px', borderRadius: '16px', background: '#f8fafc', border: '1px solid #e2e8f0', color: '#64748b' }}>
                                        No addresses are attached to this cluster yet.
                                    </div>
                                )}
                            </section>

                            <section style={{ display: 'grid', gap: '14px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Graph Preview</div>
                                <div style={{ padding: '18px', borderRadius: '18px', border: '1px solid #e2e8f0', background: '#f8fafc', minHeight: '260px', position: 'relative' }}>
                                    {previewLoading ? (
                                        <div style={{ display: 'grid', placeItems: 'center', height: '100%', color: '#64748b', fontSize: '13px' }}>
                                            Loading cluster preview…
                                        </div>
                                    ) : previewError ? (
                                        <div style={{ display: 'grid', placeItems: 'center', height: '100%', color: '#ef4444', fontSize: '13px', padding: '12px', textAlign: 'center' }}>
                                            {previewError}
                                        </div>
                                    ) : preview.nodes.length ? (
                                        <ReactFlowProvider>
                                            <div style={{ width: '100%', height: '260px', borderRadius: '18px', overflow: 'hidden' }}>
                                                <ReactFlow
                                                    nodes={preview.nodes}
                                                    edges={preview.edges}
                                                    nodesDraggable={false}
                                                    nodesConnectable={false}
                                                    elementsSelectable={false}
                                                    zoomOnScroll={false}
                                                    panOnScroll={false}
                                                    fitView
                                                    fitViewOptions={{ padding: 0.12 }}
                                                    style={{ width: '100%', height: '100%', background: '#ffffff' }}
                                                >
                                                    <Background gap={20} color="#e2e8f0" />
                                                    <Controls showInteractive={false} />
                                                </ReactFlow>
                                            </div>
                                        </ReactFlowProvider>
                                    ) : (
                                        <div style={{ display: 'grid', placeItems: 'center', height: '100%', color: '#64748b', fontSize: '13px' }}>
                                            No preview available for this cluster yet.
                                        </div>
                                    )}
                                </div>
                                {selectedCluster.addresses?.[0] && (
                                    <button
                                        type="button"
                                        onClick={() => onAddressClick && onAddressClick(selectedCluster.addresses[0].address)}
                                        style={{ marginTop: '8px', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '10px 14px', background: '#fff', color: '#0f172a', fontSize: '12px', fontWeight: '700', cursor: 'pointer' }}
                                    >
                                        Open full graph around {truncate(selectedCluster.addresses[0].address, 20)}
                                    </button>
                                )}
                            </section>

                            <section style={{ display: 'grid', gap: '14px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Evidence</div>
                                <div style={{ fontSize: '11px', color: '#64748b' }}>{evidenceHeaderText}</div>
                                {selectedCluster.evidence?.length ? (
                                    <div style={{ display: 'grid', gap: '12px' }}>
                                        {selectedCluster.evidence.map((item, idx) => (
                                            <div key={`${item.heuristic_name}-${idx}`} style={{ padding: '16px', borderRadius: '16px', background: '#fff', border: '1px solid #e2e8f0' }}>
                                                <div style={{ fontSize: '13px', fontWeight: '700', color: '#0f172a' }}>{item.heuristic_name.replace(/_/g, ' ')}</div>
                                                <div style={{ fontSize: '12px', color: '#475569', marginTop: '6px' }}>{item.evidence_text}</div>
                                                {item.observed_address_sample?.length ? (
                                                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '8px' }}>
                                                        {`Sample addresses: ${item.observed_address_sample.map((a) => `${a.slice(0, 8)}...${a.slice(-6)}`).join(', ')}`}
                                                    </div>
                                                ) : null}
                                                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '8px' }}>Confidence: {item.confidence.toFixed(2)}</div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div style={{ padding: '16px', borderRadius: '16px', background: '#f8fafc', border: '1px solid #e2e8f0', color: '#64748b' }}>
                                        No behavioral evidence detected for this cluster.
                                    </div>
                                )}
                            </section>
                        </div>
                    </aside>
                </div>
            )}
        </div>
    );
}
