import { useEffect, useState, useCallback } from 'react';
import { ReactFlow, Background, Controls, ReactFlowProvider, useNodesState, useEdgesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { getChainOfCustody, postIntegrationFeedback } from '../services/transactionService';

const STAGE_COLORS = {
    placement: { bg: '#fef2f2', border: '#fecaca', text: '#b91c1c', node: '#dc2626' },
    layering: { bg: '#fffbeb', border: '#fde68a', text: '#92400e', node: '#d97706' },
    integration: { bg: '#f0f9ff', border: '#bae6fd', text: '#0c4a6e', node: '#0f6578' },
    unknown: { bg: '#f8fafc', border: '#e2e8f0', text: '#475569', node: '#94a3b8' },
};

const stageIcon = { placement: '🛡', layering: '⧉', integration: '💰' };

// Match exact colors from GraphExplorer (Transaction Network page)
const NODE_COLOR = '#22c55e';   // green — normal wallet
const HUB_COLOR = '#ef4444';   // red   — high-value / highlighted
const SEND_EDGE = '#2563eb';   // blue  — transaction direction

const truncAddr = (addr) => addr ? `${addr.slice(0, 8)}...${addr.slice(-6)}` : '—';

const ScoreBar = ({ score, color }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <div style={{ flex: 1, height: '5px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
            <div style={{ width: `${Math.round(score * 100)}%`, height: '100%', background: color, borderRadius: '3px' }} />
        </div>
        <span style={{ fontSize: '11px', fontWeight: '700', color, minWidth: '32px' }}>{Math.round(score * 100)}%</span>
    </div>
);

const buildGraphFromEdges = (edges, addresses) => {
    const addrSet = new Set(addresses.map(a => a.toLowerCase()));
    const nodesMap = new Map();
    const edgesArr = [];

    const getStage = (addr) => {
        // Heuristic: label nodes by which stage they appear in
        return 'unknown';
    };

    edges.forEach((edge, i) => {
        const src = edge.source?.toLowerCase();
        const tgt = edge.target?.toLowerCase();
        if (!src || !tgt) return;

        [src, tgt].forEach((addr, idx) => {
            if (!nodesMap.has(addr)) {
                const isHighlighted = addrSet.has(addr);
                const size = nodesMap.size;
                nodesMap.set(addr, {
                    id: addr,
                    data: { label: truncAddr(addr) },
                    position: { x: (size % 5) * 220, y: Math.floor(size / 5) * 140 },
                    style: {
                        background: isHighlighted ? HUB_COLOR : NODE_COLOR,
                        color: '#fff',
                        borderRadius: '50%',
                        fontSize: '11px',
                        fontWeight: isHighlighted ? '700' : '600',
                        padding: '14px 20px',
                        border: isHighlighted ? '3px solid #7f1d1d' : '2px solid #15803d',
                        minWidth: '110px',
                        minHeight: '44px',
                        textAlign: 'center',
                        cursor: 'grab',
                    },
                    draggable: true,
                });
            }
        });

        edgesArr.push({
            id: `e-${i}`,
            source: src,
            target: tgt,
            type: 'default',
            animated: addrSet.has(src) || addrSet.has(tgt),
            label: edge.value_eth > 0 ? `${Number(edge.value_eth).toFixed(4)} ETH` : '',
            style: { stroke: SEND_EDGE, strokeWidth: 2 },
            markerEnd: { type: 'arrowclosed', color: SEND_EDGE, width: 20, height: 20 },
            labelStyle: { fontSize: '10px', fill: '#1e3a5f', fontWeight: '600' },
            labelBgStyle: { fill: '#eff6ff', fillOpacity: 0.8 },
        });
    });

    return { nodes: Array.from(nodesMap.values()), edges: edgesArr };
};

const GraphPanel = ({ edges, addresses }) => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edgesState, setEdges, onEdgesChange] = useEdgesState([]);

    useEffect(() => {
        if (!edges?.length) return;
        const { nodes: n, edges: e } = buildGraphFromEdges(edges, addresses);
        setNodes(n);
        setEdges(e);
    }, [edges, addresses, setNodes, setEdges]);

    if (!edges?.length) {
        return (
            <div style={{ padding: '24px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
                No Neo4j graph data available for this entity.
            </div>
        );
    }

    return (
        <div style={{ width: '100%', height: '320px', background: '#f9fafb', borderRadius: '10px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
            <ReactFlow
                nodes={nodes} edges={edgesState}
                onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
                fitView fitViewOptions={{ padding: 0.2 }}
            >
                <Background />
                <Controls />
            </ReactFlow>
        </div>
    );
};

export default function ChainOfCustodyModal({ entityId, onClose }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [feedbackSent, setFeedbackSent] = useState(false);
    const [feedbackResult, setFeedbackResult] = useState(null);

    useEffect(() => {
        if (!entityId) return;
        setLoading(true);
        getChainOfCustody(entityId)
            .then(setData)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, [entityId]);

    const handleFeedback = async () => {
        if (!data?.integration) return;
        try {
            const result = await postIntegrationFeedback(entityId, {
                integration_score: data.integration.integration_score,
                signals_fired: data.integration.signals_fired,
                feedback_type: 'confirmed_exit_path',
            });
            setFeedbackResult(result);
            setFeedbackSent(true);
        } catch (e) {
            setFeedbackResult({ status: 'error', reason: e.message });
            setFeedbackSent(true);
        }
    };

    return (
        <div style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '20px',
        }} onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div style={{
                background: '#fff', borderRadius: '16px', width: '100%', maxWidth: '900px',
                maxHeight: '90vh', overflow: 'auto', boxShadow: '0 25px 60px rgba(0,0,0,0.4)',
            }}>
                {/* Header */}
                <div style={{ background: '#0f172a', borderRadius: '16px 16px 0 0', padding: '20px 24px', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <div style={{ fontSize: '16px', fontWeight: '700' }}>🔗 Chain of Custody</div>
                        <div style={{ fontSize: '11px', color: '#cbd5e1', marginTop: '3px', fontFamily: 'monospace' }}>{truncAddr(entityId)}</div>
                    </div>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#cbd5e1', fontSize: '20px', cursor: 'pointer' }}>✕</button>
                </div>

                <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {loading && <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>Loading chain of custody...</div>}
                    {error && <div style={{ color: '#b91c1c', padding: '12px', background: '#fef2f2', borderRadius: '8px' }}>Error: {error}</div>}

                    {data && !loading && (
                        <>
                            {/* Stage pipeline indicator */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                {['placement', 'layering', 'integration'].map((stage, i) => {
                                    const found = data.stages_found.includes(stage);
                                    const c = STAGE_COLORS[stage];
                                    return (
                                        <div key={stage} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            <div style={{
                                                padding: '6px 14px', borderRadius: '999px', fontSize: '12px', fontWeight: '700',
                                                background: found ? c.bg : '#f8fafc',
                                                border: `1px solid ${found ? c.border : '#e2e8f0'}`,
                                                color: found ? c.text : '#94a3b8',
                                                opacity: found ? 1 : 0.5,
                                            }}>
                                                {stageIcon[stage]} {stage.charAt(0).toUpperCase() + stage.slice(1)}
                                                {found && <span style={{ marginLeft: '6px', fontSize: '10px' }}>✓</span>}
                                            </div>
                                            {i < 2 && <span style={{ color: '#94a3b8', fontSize: '16px' }}>→</span>}
                                        </div>
                                    );
                                })}
                                <div style={{ marginLeft: 'auto', fontSize: '12px', fontWeight: '700', color: data.overall_risk >= 0.7 ? '#b91c1c' : data.overall_risk >= 0.5 ? '#d97706' : '#16a34a' }}>
                                    Overall Risk: {Math.round(data.overall_risk * 100)}%
                                </div>
                            </div>

                            {/* Three stage cards */}
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
                                {[
                                    { key: 'placement', label: 'Placement', scoreKey: 'placement_score', detailKey: 'behaviors' },
                                    { key: 'layering', label: 'Layering', scoreKey: 'layering_score', detailKey: 'methods' },
                                    { key: 'integration', label: 'Integration', scoreKey: 'integration_score', detailKey: 'signals_fired' },
                                ].map(({ key, label, scoreKey, detailKey }) => {
                                    const stage = data[key];
                                    const c = STAGE_COLORS[key];
                                    if (!stage) {
                                        return (
                                            <div key={key} style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '16px', opacity: 0.5 }}>
                                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#94a3b8' }}>{stageIcon[key]} {label}</div>
                                                <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '8px' }}>Not detected</div>
                                            </div>
                                        );
                                    }
                                    const score = stage[scoreKey] || 0;
                                    const details = stage[detailKey] || [];
                                    const reasons = stage.reasons || [];
                                    return (
                                        <div key={key} style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: '12px', padding: '16px' }}>
                                            <div style={{ fontSize: '12px', fontWeight: '700', color: c.text, marginBottom: '8px' }}>{stageIcon[key]} {label}</div>
                                            <ScoreBar score={score} color={c.node} />
                                            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '8px' }}>
                                                {details.slice(0, 3).map(d => (
                                                    <span key={d} style={{ fontSize: '10px', padding: '2px 7px', borderRadius: '999px', background: '#fff', color: c.text, border: `1px solid ${c.border}`, fontWeight: '600' }}>
                                                        {String(d).replaceAll('_', ' ')}
                                                    </span>
                                                ))}
                                            </div>
                                            {reasons[0] && (
                                                <div style={{ fontSize: '11px', color: c.text, marginTop: '8px', lineHeight: 1.4, opacity: 0.85 }}>
                                                    {reasons[0].length > 80 ? reasons[0].slice(0, 80) + '...' : reasons[0]}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Neo4j graph */}
                            <div>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#475569', marginBottom: '8px' }}>
                                    🕸 Transaction Network ({data.neo4j_edges?.length || 0} edges)
                                </div>
                                <ReactFlowProvider>
                                    <GraphPanel edges={data.neo4j_edges || []} addresses={data.addresses || []} />
                                </ReactFlowProvider>
                            </div>

                            {/* Feedback loop button */}
                            {data.integration && !feedbackSent && (
                                <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '14px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div>
                                        <div style={{ fontSize: '12px', fontWeight: '700', color: '#15803d' }}>🔄 Feedback Loop</div>
                                        <div style={{ fontSize: '11px', color: '#166534', marginTop: '2px' }}>
                                            Integration confirmed exit — boost placement score to improve future detection
                                        </div>
                                    </div>
                                    <button onClick={handleFeedback} style={{ padding: '8px 16px', background: '#0f6578', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: '700' }}>
                                        Apply Feedback
                                    </button>
                                </div>
                            )}
                            {feedbackSent && feedbackResult && (
                                <div style={{ background: feedbackResult.status === 'error' ? '#fef2f2' : '#f0fdf4', border: `1px solid ${feedbackResult.status === 'error' ? '#fca5a5' : '#bbf7d0'}`, borderRadius: '10px', padding: '12px 16px', fontSize: '12px', color: feedbackResult.status === 'error' ? '#b91c1c' : '#15803d' }}>
                                    {feedbackResult.status === 'feedback_applied'
                                        ? `✓ Feedback applied — placement score boosted from ${Math.round(feedbackResult.original_placement_score * 100)}% to ${Math.round(feedbackResult.boosted_placement_score * 100)}%`
                                        : feedbackResult.status === 'skipped'
                                            ? `ℹ Skipped: ${feedbackResult.reason}`
                                            : `✗ Error: ${feedbackResult.reason}`
                                    }
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
