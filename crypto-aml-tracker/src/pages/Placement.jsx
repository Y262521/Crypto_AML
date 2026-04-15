import { startTransition, useEffect, useState } from 'react';

import Loader from '../components/common/Loader';
import {
    getPlacementDetail,
    getPlacements,
    getPlacementSummary,
    runPlacementAnalysis,
} from '../services/transactionService';

const cardStyle = {
    background: '#fff',
    borderRadius: '18px',
    border: '1px solid #dbe5f1',
    boxShadow: '0 18px 40px rgba(15, 23, 42, 0.05)',
};

const SummaryCard = ({ label, value, sub, accent }) => (
    <div style={{
        ...cardStyle,
        padding: '20px 22px',
        minWidth: '180px',
        flex: 1,
        background: accent
            ? `linear-gradient(160deg, ${accent}08 0%, #ffffff 48%)`
            : '#fff',
    }}>
        <div style={{ fontSize: '11px', fontWeight: '700', letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748b' }}>
            {label}
        </div>
        <div style={{ fontSize: '30px', fontWeight: '800', color: '#0f172a', marginTop: '10px' }}>
            {value}
        </div>
        {sub ? <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px', lineHeight: 1.5 }}>{sub}</div> : null}
    </div>
);

const badgeStyle = (tone = 'slate') => {
    const tones = {
        red: { color: '#991b1b', background: '#fee2e2', border: '#fecaca' },
        amber: { color: '#92400e', background: '#fef3c7', border: '#fcd34d' },
        blue: { color: '#1d4ed8', background: '#dbeafe', border: '#bfdbfe' },
        emerald: { color: '#166534', background: '#dcfce7', border: '#86efac' },
        slate: { color: '#334155', background: '#e2e8f0', border: '#cbd5e1' },
    };
    const resolved = tones[tone] || tones.slate;
    return {
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '5px 10px',
        borderRadius: '999px',
        fontSize: '11px',
        fontWeight: '700',
        color: resolved.color,
        background: resolved.background,
        border: `1px solid ${resolved.border}`,
        whiteSpace: 'nowrap',
    };
};

const scoreColor = (score) => {
    if (score >= 85) return { track: '#fee2e2', fill: '#dc2626', text: '#991b1b' };
    if (score >= 70) return { track: '#fef3c7', fill: '#f59e0b', text: '#92400e' };
    if (score >= 55) return { track: '#dbeafe', fill: '#2563eb', text: '#1d4ed8' };
    return { track: '#e2e8f0', fill: '#64748b', text: '#334155' };
};

const ScoreBar = ({ label, value, suffix = '' }) => {
    const pct = Math.max(0, Math.min(100, Number(value || 0)));
    const color = scoreColor(pct);
    return (
        <div style={{ display: 'grid', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', fontWeight: '700', color: '#475569' }}>{label}</span>
                <span style={{ fontSize: '13px', fontWeight: '800', color: color.text }}>{pct.toFixed(1)}{suffix}</span>
            </div>
            <div style={{ height: '10px', borderRadius: '999px', background: color.track, overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: color.fill, borderRadius: '999px' }} />
            </div>
        </div>
    );
};

const behaviorTone = (behavior) => {
    if (behavior === 'structuring' || behavior === 'smurfing') return 'red';
    if (behavior === 'micro_funding') return 'amber';
    if (behavior === 'funneling') return 'blue';
    if (behavior === 'immediate_utilization') return 'emerald';
    return 'slate';
};

const truncate = (value, maxLength = 18) => {
    if (!value) return '—';
    if (value.length <= maxLength) return value;
    return `${value.slice(0, maxLength - 3)}...`;
};

const formatNumber = (value, maximumFractionDigits = 2) => {
    const parsed = Number(value || 0);
    if (!Number.isFinite(parsed)) return '0';
    return parsed.toLocaleString(undefined, { maximumFractionDigits });
};

const TracePath = ({ path }) => (
    <div style={{
        ...cardStyle,
        padding: '16px 18px',
        display: 'grid',
        gap: '14px',
        background: 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
    }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                <span style={badgeStyle('blue')}>Trace #{path.path_index}</span>
                <span style={badgeStyle('slate')}>Score {formatNumber(path.score * 100, 1)}</span>
                <span style={badgeStyle(path.terminal_reason === 'no_incoming' ? 'emerald' : 'amber')}>
                    {path.terminal_reason?.replaceAll('_', ' ') || 'trace'}
                </span>
            </div>
            <div style={{ fontSize: '12px', color: '#64748b' }}>
                Root {truncate(path.root_entity_id, 22)}
            </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', overflowX: 'auto', paddingBottom: '2px' }}>
            {path.nodes.map((node, index) => (
                <div key={`${path.path_index}-${node.entity_id}-${index}`} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{
                        minWidth: '180px',
                        padding: '14px 16px',
                        borderRadius: '16px',
                        border: '1px solid #dbe5f1',
                        background: index === 0
                            ? 'linear-gradient(160deg, #dcfce7 0%, #ffffff 80%)'
                            : index === path.nodes.length - 1
                                ? 'linear-gradient(160deg, #fee2e2 0%, #ffffff 80%)'
                                : 'linear-gradient(160deg, #dbeafe 0%, #ffffff 80%)',
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center' }}>
                            <span style={badgeStyle(node.entity_type === 'cluster' ? 'blue' : 'slate')}>
                                {node.entity_type === 'cluster' ? 'Cluster' : 'Address'}
                            </span>
                            <span style={{ fontSize: '11px', color: '#64748b' }}>
                                {node.address_count || node.addresses?.length || 0} addr
                            </span>
                        </div>
                        <div style={{ fontSize: '13px', fontWeight: '800', color: '#0f172a', marginTop: '12px', fontFamily: 'monospace' }}>
                            {truncate(node.entity_id, 26)}
                        </div>
                        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '8px', lineHeight: 1.5 }}>
                            {(node.addresses || []).slice(0, 2).join(', ') || 'No addresses available'}
                        </div>
                    </div>
                    {index < path.nodes.length - 1 ? (
                        <div style={{ fontSize: '22px', color: '#94a3b8', flexShrink: 0 }}>→</div>
                    ) : null}
                </div>
            ))}
        </div>
    </div>
);

export default function Placement() {
    const [summary, setSummary] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [detail, setDetail] = useState(null);
    const [loading, setLoading] = useState(true);
    const [detailLoading, setDetailLoading] = useState(false);
    const [running, setRunning] = useState(false);
    const [error, setError] = useState(null);
    const [search, setSearch] = useState('');
    const [behaviorFilter, setBehaviorFilter] = useState('All');

    const loadPage = async () => {
        setLoading(true);
        setError(null);
        try {
            const [summaryData, listData] = await Promise.all([
                getPlacementSummary(),
                getPlacements(),
            ]);
            setSummary(summaryData);
            const nextAlerts = listData.items || [];
            setAlerts(nextAlerts);
            setSelectedId(current => {
                if (current && nextAlerts.some(item => item.entity_id === current)) {
                    return current;
                }
                return nextAlerts[0]?.entity_id || null;
            });
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadPage();
    }, []);

    useEffect(() => {
        if (!selectedId) {
            setDetail(null);
            return;
        }
        setDetailLoading(true);
        getPlacementDetail(selectedId)
            .then(data => setDetail(data))
            .catch(err => setError(err.message))
            .finally(() => setDetailLoading(false));
    }, [selectedId]);

    const allBehaviors = Array.from(new Set(alerts.flatMap(alert => alert.behaviors || []))).sort();
    const filteredAlerts = alerts.filter(alert => {
        const q = search.trim().toLowerCase();
        const matchesSearch = !q
            || alert.entity_id?.toLowerCase().includes(q)
            || (alert.addresses || []).some(address => address?.toLowerCase().includes(q))
            || (alert.reasons || []).some(reason => reason?.toLowerCase().includes(q));
        const matchesBehavior = behaviorFilter === 'All' || (alert.behaviors || []).includes(behaviorFilter);
        return matchesSearch && matchesBehavior;
    });

    const handleRunAnalysis = async () => {
        setRunning(true);
        try {
            await runPlacementAnalysis();
            await loadPage();
        } catch (err) {
            setError(err.message);
        } finally {
            setRunning(false);
        }
    };

    if (loading) return <Loader />;
    if (error) return <div style={{ color: '#b91c1c', padding: '1rem' }}>Error: {error}</div>;

    const summaryBody = summary?.summary || {};
    const selectedAlert = filteredAlerts.find(alert => alert.entity_id === selectedId) || filteredAlerts[0] || null;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
            <div style={{
                ...cardStyle,
                padding: '26px 28px',
                background: 'linear-gradient(135deg, #0f172a 0%, #1d4ed8 48%, #38bdf8 100%)',
                color: '#fff',
                overflow: 'hidden',
                position: 'relative',
            }}>
                <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(circle at top right, rgba(255,255,255,0.22), transparent 38%)' }} />
                <div style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', gap: '20px', flexWrap: 'wrap' }}>
                    <div>
                        <div style={{ fontSize: '12px', fontWeight: '700', letterSpacing: '0.08em', textTransform: 'uppercase', opacity: 0.86 }}>
                            Placement Detection
                        </div>
                        <div style={{ fontSize: '32px', fontWeight: '800', marginTop: '12px', maxWidth: '760px' }}>
                            Earliest suspicious entity discovery for Ethereum fund ingress.
                        </div>
                        <div style={{ fontSize: '14px', lineHeight: 1.7, marginTop: '12px', color: 'rgba(255,255,255,0.86)', maxWidth: '760px' }}>
                            Cluster-first placement analysis validates existing clusters, detects placement-stage behaviors, traces suspicious flows upstream, scores origins, assigns labels, and surfaces actionable POIs.
                        </div>
                    </div>
                    <div style={{ display: 'grid', gap: '10px', alignContent: 'start' }}>
                        <button
                            onClick={handleRunAnalysis}
                            disabled={running}
                            style={{
                                padding: '11px 16px',
                                borderRadius: '12px',
                                border: '1px solid rgba(255,255,255,0.24)',
                                background: running ? 'rgba(255,255,255,0.18)' : '#fff',
                                color: running ? '#dbeafe' : '#0f172a',
                                cursor: running ? 'not-allowed' : 'pointer',
                                fontWeight: '800',
                                fontSize: '13px',
                            }}
                        >
                            {running ? 'Running analysis...' : 'Run Placement Analysis'}
                        </button>
                        <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.82)' }}>
                            Latest run: {summary?.generated_at || 'No completed run'}
                        </div>
                    </div>
                </div>
            </div>

            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                <SummaryCard
                    label="Placement Alerts"
                    value={formatNumber(summaryBody.placements || 0, 0)}
                    sub="High-confidence origin candidates in the latest completed run."
                    accent="#dc2626"
                />
                <SummaryCard
                    label="Actionable POIs"
                    value={formatNumber(summaryBody.pois || 0, 0)}
                    sub="Alert subset that cleared the POI action threshold."
                    accent="#2563eb"
                />
                <SummaryCard
                    label="Behavior Hits"
                    value={formatNumber(Object.values(summaryBody.behaviors || {}).reduce((total, count) => total + Number(count || 0), 0), 0)}
                    sub="Placement-stage behaviors detected across clusters and fallback addresses."
                    accent="#f59e0b"
                />
                <SummaryCard
                    label="Validated Entities"
                    value={formatNumber(summaryBody.cluster_entities || 0, 0)}
                    sub="Cluster-first entities analyzed before address fallback."
                    accent="#16a34a"
                />
            </div>

            <div style={{ ...cardStyle, padding: '16px 18px', display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
                <input
                    type="text"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search by entity, address, or reason..."
                    style={{
                        flex: 1,
                        minWidth: '240px',
                        borderRadius: '12px',
                        border: '1px solid #cbd5e1',
                        background: '#fff',
                        padding: '11px 14px',
                        fontSize: '13px',
                    }}
                />
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {['All', ...allBehaviors].map(behavior => (
                        <button
                            key={behavior}
                            type="button"
                            onClick={() => setBehaviorFilter(behavior)}
                            style={{
                                padding: '8px 12px',
                                borderRadius: '999px',
                                border: behaviorFilter === behavior ? '1px solid #0f172a' : '1px solid #dbe5f1',
                                background: behaviorFilter === behavior ? '#0f172a' : '#fff',
                                color: behaviorFilter === behavior ? '#fff' : '#334155',
                                cursor: 'pointer',
                                fontSize: '12px',
                                fontWeight: '700',
                            }}
                        >
                            {behavior === 'All' ? 'All Behaviors' : behavior.replaceAll('_', ' ')}
                        </button>
                    ))}
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 420px) minmax(0, 1fr)', gap: '20px', minHeight: '680px' }}>
                <div style={{ ...cardStyle, padding: '14px', display: 'grid', gap: '12px', alignContent: 'start' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <div style={{ fontSize: '12px', fontWeight: '800', color: '#0f172a', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                                Alerts
                            </div>
                            <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                                {filteredAlerts.length} visible of {alerts.length} total alerts
                            </div>
                        </div>
                    </div>

                    {filteredAlerts.length === 0 ? (
                        <div style={{ padding: '28px 18px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                            No placement alerts match the current filters.
                        </div>
                    ) : filteredAlerts.map(alert => {
                        const active = alert.entity_id === (selectedAlert?.entity_id || selectedId);
                        return (
                            <button
                                key={alert.entity_id}
                                type="button"
                                onClick={() => startTransition(() => setSelectedId(alert.entity_id))}
                                style={{
                                    textAlign: 'left',
                                    borderRadius: '16px',
                                    border: active ? '1px solid #1d4ed8' : '1px solid #dbe5f1',
                                    background: active ? 'linear-gradient(160deg, #eff6ff 0%, #ffffff 70%)' : '#fff',
                                    padding: '16px',
                                    cursor: 'pointer',
                                    display: 'grid',
                                    gap: '12px',
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start' }}>
                                    <div style={{ minWidth: 0 }}>
                                        <div style={{ fontSize: '12px', color: '#64748b', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                                            {alert.entity_type === 'cluster' ? 'Cluster Alert' : 'Address Fallback'}
                                        </div>
                                        <div style={{ fontSize: '13px', fontWeight: '800', color: '#0f172a', fontFamily: 'monospace', marginTop: '7px' }}>
                                            {truncate(alert.entity_id, 28)}
                                        </div>
                                    </div>
                                    <span style={badgeStyle(alert.risk_score >= 85 ? 'red' : alert.risk_score >= 70 ? 'amber' : 'blue')}>
                                        Risk {formatNumber(alert.risk_score, 1)}
                                    </span>
                                </div>

                                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                    {(alert.behaviors || []).map(behavior => (
                                        <span key={`${alert.entity_id}-${behavior}`} style={badgeStyle(behaviorTone(behavior))}>
                                            {behavior.replaceAll('_', ' ')}
                                        </span>
                                    ))}
                                </div>

                                <div style={{ fontSize: '12px', color: '#334155', lineHeight: 1.6 }}>
                                    {alert.reason || 'No reason supplied'}
                                </div>

                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                                    <div style={{ fontSize: '12px', color: '#64748b' }}>
                                        {alert.address_count} addresses
                                        {alert.poi ? ` · POI ${alert.poi.poi_id}` : ''}
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#1d4ed8', fontWeight: '700' }}>
                                        Confidence {formatNumber((alert.confidence || 0) * 100, 1)}
                                    </div>
                                </div>
                            </button>
                        );
                    })}
                </div>

                <div style={{ ...cardStyle, padding: '20px', display: 'grid', gap: '18px', alignContent: 'start' }}>
                    {!selectedAlert ? (
                        <div style={{ padding: '28px 18px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                            No placement alert selected.
                        </div>
                    ) : detailLoading || !detail ? (
                        <Loader />
                    ) : (
                        <>
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                                <div>
                                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                        <span style={badgeStyle(detail.placement.entity_type === 'cluster' ? 'blue' : 'slate')}>
                                            {detail.placement.entity_type === 'cluster' ? 'Cluster First' : 'Address Fallback'}
                                        </span>
                                        <span style={badgeStyle(detail.placement.poi ? 'emerald' : 'slate')}>
                                            {detail.placement.poi ? 'Actionable POI' : 'Monitor'}
                                        </span>
                                        <span style={badgeStyle(detail.placement.validation_status === 'validated' ? 'emerald' : detail.placement.validation_status === 'enhanced' ? 'amber' : 'slate')}>
                                            {detail.placement.validation_status}
                                        </span>
                                    </div>
                                    <div style={{ fontSize: '24px', fontWeight: '800', color: '#0f172a', marginTop: '14px' }}>
                                        {detail.placement.entity_id}
                                    </div>
                                    <div style={{ fontSize: '13px', color: '#64748b', marginTop: '8px', lineHeight: 1.7, maxWidth: '860px' }}>
                                        {(detail.placement.reasons || []).join(' • ')}
                                    </div>
                                </div>
                                <div style={{ minWidth: '220px', display: 'grid', gap: '12px' }}>
                                    <ScoreBar label="Risk Score" value={detail.placement.risk_score} />
                                    <ScoreBar label="Confidence" value={(detail.placement.confidence || 0) * 100} />
                                </div>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
                                <div style={{ ...cardStyle, padding: '16px', background: '#f8fafc' }}>
                                    <ScoreBar label="Behavior Score" value={(detail.placement.behavior_score || 0) * 100} />
                                </div>
                                <div style={{ ...cardStyle, padding: '16px', background: '#f8fafc' }}>
                                    <ScoreBar label="Graph Position Score" value={(detail.placement.graph_position_score || 0) * 100} />
                                </div>
                                <div style={{ ...cardStyle, padding: '16px', background: '#f8fafc' }}>
                                    <ScoreBar label="Temporal Score" value={(detail.placement.temporal_score || 0) * 100} />
                                </div>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '18px' }}>
                                <div style={{ ...cardStyle, padding: '18px', display: 'grid', gap: '12px' }}>
                                    <div style={{ fontSize: '12px', fontWeight: '800', color: '#0f172a', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                                        Behavior Evidence
                                    </div>
                                    {(detail.behaviors || []).length === 0 ? (
                                        <div style={{ fontSize: '12px', color: '#64748b' }}>No behavior evidence stored for this alert.</div>
                                    ) : (detail.behaviors || []).map(behavior => (
                                        <div key={behavior.behavior_type} style={{
                                            borderRadius: '16px',
                                            border: '1px solid #dbe5f1',
                                            padding: '14px',
                                            display: 'grid',
                                            gap: '8px',
                                        }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
                                                <span style={badgeStyle(behaviorTone(behavior.behavior_type))}>
                                                    {behavior.behavior_type.replaceAll('_', ' ')}
                                                </span>
                                                <span style={{ fontSize: '12px', color: '#1d4ed8', fontWeight: '800' }}>
                                                    Confidence {formatNumber((behavior.confidence_score || 0) * 100, 1)}
                                                </span>
                                            </div>
                                            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                                                {Object.entries(behavior.metrics || {}).slice(0, 4).map(([key, value]) => (
                                                    <div key={key} style={{ ...badgeStyle('slate'), fontWeight: '600' }}>
                                                        {key.replaceAll('_', ' ')}: {String(value)}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <div style={{ display: 'grid', gap: '18px' }}>
                                    <div style={{ ...cardStyle, padding: '18px', display: 'grid', gap: '12px' }}>
                                        <div style={{ fontSize: '12px', fontWeight: '800', color: '#0f172a', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                                            Labels
                                        </div>
                                        {(detail.labels || []).length === 0 ? (
                                            <div style={{ fontSize: '12px', color: '#64748b' }}>No labels assigned.</div>
                                        ) : detail.labels.map(label => (
                                            <div key={`${label.label}-${label.source}`} style={{ display: 'grid', gap: '6px' }}>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
                                                    <span style={badgeStyle(label.label === 'placement_origin' ? 'red' : label.label === 'suspicious_receiver' ? 'amber' : 'blue')}>
                                                        {label.label.replaceAll('_', ' ')}
                                                    </span>
                                                    <span style={{ fontSize: '12px', color: '#64748b' }}>
                                                        {formatNumber((label.confidence_score || 0) * 100, 1)}
                                                    </span>
                                                </div>
                                                <div style={{ fontSize: '12px', color: '#334155', lineHeight: 1.6 }}>
                                                    {label.explanation}
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    <div style={{ ...cardStyle, padding: '18px', display: 'grid', gap: '12px', background: detail.poi ? 'linear-gradient(160deg, #ecfdf5 0%, #ffffff 80%)' : '#fff' }}>
                                        <div style={{ fontSize: '12px', fontWeight: '800', color: '#0f172a', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                                            POI
                                        </div>
                                        {!detail.poi ? (
                                            <div style={{ fontSize: '12px', color: '#64748b' }}>
                                                This alert is below the POI action threshold.
                                            </div>
                                        ) : (
                                            <>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
                                                    <span style={badgeStyle('emerald')}>{detail.poi.poi_id}</span>
                                                    <span style={badgeStyle('red')}>Risk {formatNumber(detail.poi.risk_score, 1)}</span>
                                                </div>
                                                <div style={{ fontSize: '13px', fontWeight: '700', color: '#0f172a' }}>
                                                    {detail.poi.reason}
                                                </div>
                                                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                                    {(detail.poi.linked_behaviors || []).map(behavior => (
                                                        <span key={behavior} style={badgeStyle(behaviorTone(behavior))}>
                                                            {behavior.replaceAll('_', ' ')}
                                                        </span>
                                                    ))}
                                                </div>
                                            </>
                                        )}
                                    </div>
                                </div>
                            </div>

                            <div style={{ display: 'grid', gap: '12px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '800', color: '#0f172a', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                                    Address Coverage
                                </div>
                                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                    {(detail.placement.addresses || []).map(address => (
                                        <a
                                            key={address}
                                            href={`https://etherscan.io/address/${address}`}
                                            target="_blank"
                                            rel="noreferrer"
                                            style={{
                                                ...badgeStyle('slate'),
                                                textDecoration: 'none',
                                                fontFamily: 'monospace',
                                            }}
                                        >
                                            {address}
                                        </a>
                                    ))}
                                </div>
                            </div>

                            <div style={{ display: 'grid', gap: '12px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '800', color: '#0f172a', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                                    Trace Paths
                                </div>
                                {(detail.trace_paths || []).length === 0 ? (
                                    <div style={{ fontSize: '12px', color: '#64748b' }}>No trace paths were stored for this alert.</div>
                                ) : detail.trace_paths.map(path => (
                                    <TracePath key={`${path.root_entity_id}-${path.path_index}`} path={path} />
                                ))}
                            </div>

                            <div style={{ display: 'grid', gap: '12px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '800', color: '#0f172a', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                                    Linked Transactions
                                </div>
                                <div style={{ ...cardStyle, overflow: 'hidden' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                        <thead>
                                            <tr style={{ background: '#f8fafc' }}>
                                                {['Tx Hash', 'From', 'To', 'Value', 'Timestamp'].map(header => (
                                                    <th key={header} style={{
                                                        textAlign: 'left',
                                                        padding: '12px 14px',
                                                        fontSize: '11px',
                                                        fontWeight: '800',
                                                        color: '#475569',
                                                        letterSpacing: '0.08em',
                                                        textTransform: 'uppercase',
                                                        borderBottom: '1px solid #dbe5f1',
                                                    }}>
                                                        {header}
                                                    </th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {(detail.linked_transactions || []).length === 0 ? (
                                                <tr>
                                                    <td colSpan={5} style={{ padding: '18px', fontSize: '12px', color: '#64748b', textAlign: 'center' }}>
                                                        No linked transactions were resolved from the stored evidence.
                                                    </td>
                                                </tr>
                                            ) : detail.linked_transactions.map(tx => (
                                                <tr key={tx.tx_hash}>
                                                    <td style={{ padding: '12px 14px', fontSize: '12px', borderBottom: '1px solid #eef2f7', fontFamily: 'monospace' }}>
                                                        <a href={`https://etherscan.io/tx/${tx.tx_hash}`} target="_blank" rel="noreferrer" style={{ color: '#2563eb', textDecoration: 'none' }}>
                                                            {truncate(tx.tx_hash, 18)}
                                                        </a>
                                                    </td>
                                                    <td style={{ padding: '12px 14px', fontSize: '12px', borderBottom: '1px solid #eef2f7', fontFamily: 'monospace' }}>
                                                        {truncate(tx.from_address, 18)}
                                                    </td>
                                                    <td style={{ padding: '12px 14px', fontSize: '12px', borderBottom: '1px solid #eef2f7', fontFamily: 'monospace' }}>
                                                        {truncate(tx.to_address, 18)}
                                                    </td>
                                                    <td style={{ padding: '12px 14px', fontSize: '12px', borderBottom: '1px solid #eef2f7', color: '#166534', fontWeight: '700' }}>
                                                        {formatNumber(tx.value_eth, 6)} ETH
                                                    </td>
                                                    <td style={{ padding: '12px 14px', fontSize: '12px', borderBottom: '1px solid #eef2f7', color: '#64748b' }}>
                                                        {tx.timestamp || '—'}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
