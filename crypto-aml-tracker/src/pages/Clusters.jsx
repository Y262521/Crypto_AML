import { useEffect, useState } from 'react';
import { getClusters, getClustersSummary } from '../services/transactionService';
import Loader from '../components/common/Loader';

const LABEL_COLORS = {
    possible_layering:           { bg: '#fef2f2', border: '#fca5a5', text: '#991b1b' },
    possible_mixer:              { bg: '#fdf4ff', border: '#d8b4fe', text: '#6b21a8' },
    exchange_like_behavior:      { bg: '#eff6ff', border: '#93c5fd', text: '#1e40af' },
    coordinated_activity:        { bg: '#fff7ed', border: '#fdba74', text: '#9a3412' },
    token_flow_cluster:          { bg: '#f0fdf4', border: '#86efac', text: '#166534' },
    shared_counterparties:       { bg: '#fefce8', border: '#fde047', text: '#854d0e' },
    // Advanced
    peel_chain_layering:         { bg: '#fef2f2', border: '#f87171', text: '#7f1d1d' },
    rapid_layering:              { bg: '#fff1f2', border: '#fda4af', text: '#881337' },
    dense_transaction_community: { bg: '#f0f9ff', border: '#7dd3fc', text: '#0c4a6e' },
    address_poisoning_attack:    { bg: '#fdf4ff', border: '#c084fc', text: '#581c87' },
    dusting_surveillance:        { bg: '#fffbeb', border: '#fcd34d', text: '#78350f' },
    normal:                      { bg: '#f8fafc', border: '#e2e8f0', text: '#475569' },
};

const riskColor = (score) => {
    if (score >= 70) return { color: '#dc2626', background: '#fee2e2' };
    if (score >= 40) return { color: '#d97706', background: '#fef3c7' };
    return { color: '#16a34a', background: '#dcfce7' };
};

const riskLabel = (score) => score >= 70 ? 'High' : score >= 40 ? 'Medium' : 'Low';

const StatCard = ({ label, value, color }) => (
    <div style={{
        background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0',
        padding: '18px 22px', flex: 1, minWidth: '140px',
    }}>
        <div style={{ fontSize: '26px', fontWeight: '700', color: color || '#0f172a' }}>{value}</div>
        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>{label}</div>
    </div>
);

export default function Clusters({ onAddressClick }) {
    const [clusters, setClusters] = useState([]);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [expanded, setExpanded] = useState(null);
    const [filter, setFilter] = useState('All');

    useEffect(() => {
        Promise.all([getClusters(), getClustersSummary()])
            .then(([c, s]) => { setClusters(c); setSummary(s); setLoading(false); })
            .catch(err => { setError(err.message); setLoading(false); });
    }, []);

    if (loading) return <Loader />;
    if (error) return (
        <div style={{ padding: '2rem', color: '#64748b' }}>
            <div style={{ fontSize: '16px', marginBottom: '8px', color: '#ef4444' }}>
                Could not load clusters.
            </div>
            <div style={{ fontSize: '13px' }}>
                Run the clustering engine first:
            </div>
            <pre style={{ background: '#f1f5f9', padding: '12px', borderRadius: '8px', marginTop: '8px', fontSize: '12px' }}>
                cd AML{'\n'}
                source venv/bin/activate{'\n'}
                python -m aml_pipeline.clustering.run_clustering --persist
            </pre>
        </div>
    );

    const FILTERS = ['All', 'High', 'Medium', 'Low'];
    const filtered = filter === 'All'
        ? clusters
        : clusters.filter(c => riskLabel(c.risk_score) === filter);

    const th = {
        textAlign: 'left', padding: '10px 14px',
        borderBottom: '2px solid #e2e8f0',
        color: '#475569', fontSize: '11px', fontWeight: '600',
        textTransform: 'uppercase', letterSpacing: '0.05em',
    };
    const td = { padding: '10px 14px', borderBottom: '1px solid #f1f5f9', fontSize: '12px', color: '#334155' };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* Summary cards */}
            {summary && (
                <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
                    <StatCard label="Total Clusters" value={summary.total} />
                    <StatCard label="High Risk" value={summary.high_risk} color="#dc2626" />
                    <StatCard label="Medium Risk" value={summary.medium_risk} color="#d97706" />
                    <StatCard label="Low Risk" value={summary.low_risk} color="#16a34a" />
                </div>
            )}

            {/* Filter tabs */}
            <div style={{ display: 'flex', gap: '8px' }}>
                {FILTERS.map(f => (
                    <button key={f} onClick={() => setFilter(f)} style={{
                        padding: '6px 16px', borderRadius: '999px', border: '1px solid #e2e8f0',
                        background: filter === f ? '#0d1b2e' : '#fff',
                        color: filter === f ? '#fff' : '#475569',
                        cursor: 'pointer', fontSize: '12px', fontWeight: '500',
                    }}>{f}</button>
                ))}
            </div>

            {/* Clusters table */}
            <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                {filtered.length === 0
                    ? <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
                        No clusters found.
                    </div>
                    : <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
                        <thead>
                            <tr style={{ background: '#e2e8f0' }}>
                                <th style={{ ...th, width: '16%' }}>Cluster ID</th>
                                <th style={{ ...th, width: '8%' }}>Size</th>
                                <th style={{ ...th, width: '10%' }}>Risk</th>
                                <th style={{ ...th, width: '28%' }}>Labels</th>
                                <th style={{ ...th, width: '10%' }}>ETH Vol.</th>
                                <th style={{ ...th, width: '28%' }}>Explanation</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((c) => {
                                const rc = riskColor(c.risk_score);
                                const isOpen = expanded === c.cluster_id;
                                return [
                                    <tr key={c.cluster_id}
                                        onClick={() => setExpanded(isOpen ? null : c.cluster_id)}
                                        style={{ cursor: 'pointer' }}
                                        onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
                                        onMouseLeave={e => e.currentTarget.style.background = ''}>
                                        <td style={{ ...td, fontFamily: 'monospace', fontSize: '11px' }}>
                                            {isOpen ? '▼ ' : '▶ '}{c.cluster_id}
                                        </td>
                                        <td style={td}>{c.addresses?.length ?? 0}</td>
                                        <td style={td}>
                                            <span style={{ ...rc, padding: '2px 8px', borderRadius: '999px', fontSize: '11px', fontWeight: '600', fontFamily: 'sans-serif' }}>
                                                {c.risk_score} {riskLabel(c.risk_score)}
                                            </span>
                                        </td>
                                        <td style={td}>
                                            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                                {(c.labels || []).map(l => {
                                                    const lc = LABEL_COLORS[l] || LABEL_COLORS.normal;
                                                    return (
                                                        <span key={l} style={{
                                                            background: lc.bg, color: lc.text, border: `1px solid ${lc.border}`,
                                                            padding: '1px 7px', borderRadius: '999px', fontSize: '10px', fontWeight: '600',
                                                        }}>{l.replace(/_/g, ' ')}</span>
                                                    );
                                                })}
                                            </div>
                                        </td>
                                        <td style={{ ...td, color: '#16a34a' }}>
                                            {c.indicators?.total_eth_volume ?? '—'}
                                        </td>
                                        <td style={{ ...td, fontSize: '11px', color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {c.explanation}
                                        </td>
                                    </tr>,
                                    isOpen && (
                                        <tr key={`${c.cluster_id}-detail`}>
                                            <td colSpan={6} style={{ padding: '0 14px 14px 14px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', paddingTop: '12px' }}>
                                                    {/* Addresses */}
                                                    <div>
                                                        <div style={{ fontSize: '11px', fontWeight: '600', color: '#475569', marginBottom: '6px', textTransform: 'uppercase' }}>
                                                            Member Addresses ({c.addresses?.length})
                                                        </div>
                                                        <div style={{ maxHeight: '160px', overflowY: 'auto' }}>
                                                            {(c.addresses || []).map(addr => (
                                                                <div key={addr} style={{ fontFamily: 'monospace', fontSize: '11px', padding: '3px 0', borderBottom: '1px solid #f1f5f9' }}>
                                                                    <span
                                                                        onClick={(e) => { e.stopPropagation(); onAddressClick && onAddressClick(addr); }}
                                                                        style={{ cursor: 'pointer', color: '#3b82f6' }}
                                                                        title="Click to view in graph"
                                                                    >{addr}</span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                    {/* Indicators */}
                                                    <div>
                                                        <div style={{ fontSize: '11px', fontWeight: '600', color: '#475569', marginBottom: '6px', textTransform: 'uppercase' }}>
                                                            Behavioural Indicators
                                                        </div>
                                                        {Object.entries(c.indicators || {}).map(([k, v]) => (
                                                            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', padding: '3px 0', borderBottom: '1px solid #f1f5f9' }}>
                                                                <span style={{ color: '#64748b' }}>{k.replace(/_/g, ' ')}</span>
                                                                <span style={{ fontWeight: '600', color: '#0f172a' }}>{String(v)}</span>
                                                            </div>
                                                        ))}
                                                        <div style={{ marginTop: '10px', fontSize: '11px', fontWeight: '600', color: '#475569', textTransform: 'uppercase' }}>
                                                            Heuristics Fired
                                                        </div>
                                                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '4px' }}>
                                                            {(c.heuristics_fired || []).map(h => (
                                                                <span key={h} style={{ background: '#e0f2fe', color: '#0369a1', padding: '2px 8px', borderRadius: '999px', fontSize: '10px', fontWeight: '600' }}>
                                                                    {h.replace(/_/g, ' ')}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                </div>
                                                <div style={{ marginTop: '10px', fontSize: '12px', color: '#475569', fontStyle: 'italic' }}>
                                                    {c.explanation}
                                                </div>
                                            </td>
                                        </tr>
                                    )
                                ];
                            })}
                        </tbody>
                    </table>
                }
            </div>
        </div>
    );
}
