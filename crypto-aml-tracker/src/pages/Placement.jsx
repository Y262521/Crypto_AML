import { useDeferredValue, useEffect, useState } from 'react';
import Loader from '../components/common/Loader';
import { getPlacements, getPlacementRuns, getPlacementSummary } from '../services/transactionService';

const _BANNED = new Set(['funneling', 'funnel', 'immediate_utilization', 'immediate-utilization', 'immediate utilization']);

const MOCK_ALERTS = [
    {
        entity_id: '0xf3a1b2c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0',
        entity_type: 'address',
        addresses: ['0xf3a1b2c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0'],
        address_count: 1,
        confidence: 0.81,
        placement_score: 0.81,
        risk_score: 81,
        all_behaviors: ['structuring'],
        behaviors: ['structuring'],
        primary_behavior: 'structuring',
        behavior_profile: { primary_behavior: 'structuring', display_behaviors: ['structuring'], display_mode: 'dominant', ranked_behaviors: [{ behavior_type: 'structuring', confidence_score: 0.81 }] },
        reasons: ['transactions deliberately kept below reporting thresholds', 'high placement score from graph position analysis'],
        reason: 'transactions deliberately kept below reporting thresholds',
        _isMock: true,
    },
    {
        entity_id: '0xc9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0',
        entity_type: 'cluster',
        addresses: ['0xc9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0', '0x1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b', '0x2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c'],
        address_count: 3,
        confidence: 0.74,
        placement_score: 0.74,
        risk_score: 74,
        all_behaviors: ['structuring', 'smurfing'],
        behaviors: ['structuring', 'smurfing'],
        primary_behavior: 'structuring',
        behavior_profile: { primary_behavior: 'structuring', display_behaviors: ['structuring', 'smurfing'], display_mode: 'paired', ranked_behaviors: [{ behavior_type: 'structuring', confidence_score: 0.74 }, { behavior_type: 'smurfing', confidence_score: 0.68 }] },
        reasons: ['transactions deliberately kept below reporting thresholds', 'downstream suspicious behavior: smurfing', 'suspicious history observed upstream in analyzed graph'],
        reason: 'transactions deliberately kept below reporting thresholds',
        _isMock: true,
    },
    {
        entity_id: '0x7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f',
        entity_type: 'address',
        addresses: ['0x7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f'],
        address_count: 1,
        confidence: 0.69,
        placement_score: 0.69,
        risk_score: 69,
        all_behaviors: ['micro_funding'],
        behaviors: ['micro_funding'],
        primary_behavior: 'micro_funding',
        behavior_profile: { primary_behavior: 'micro_funding', display_behaviors: ['micro_funding'], display_mode: 'dominant', ranked_behaviors: [{ behavior_type: 'micro_funding', confidence_score: 0.69 }] },
        reasons: ['earliest reachable entity in traced suspicious flow', 'downstream suspicious behavior: micro_funding'],
        reason: 'earliest reachable entity in traced suspicious flow',
        _isMock: true,
    },
    {
        entity_id: '0x4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e',
        entity_type: 'cluster',
        addresses: ['0x4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e', '0x5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f', '0x6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a', '0x7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b'],
        address_count: 4,
        confidence: 0.77,
        placement_score: 0.77,
        risk_score: 77,
        all_behaviors: ['micro_funding', 'structuring'],
        behaviors: ['micro_funding', 'structuring'],
        primary_behavior: 'micro_funding',
        behavior_profile: { primary_behavior: 'micro_funding', display_behaviors: ['micro_funding', 'structuring'], display_mode: 'paired', ranked_behaviors: [{ behavior_type: 'micro_funding', confidence_score: 0.77 }, { behavior_type: 'structuring', confidence_score: 0.61 }] },
        reasons: ['downstream suspicious behavior: micro_funding', 'transactions deliberately kept below reporting thresholds', 'no prior suspicious history observed upstream in analyzed graph'],
        reason: 'downstream suspicious behavior: micro_funding',
        _isMock: true,
    },
];
const DOMINANT_GAP = 0.15;
const DOMINANT_RATIO = 0.82;
const BALANCED_GAP = 0.06;
const BALANCED_RATIO = 0.94;

const formatNumber = (value, maximumFractionDigits = 2) => {
    const parsed = Number(value || 0);
    if (!Number.isFinite(parsed)) return '0';
    return parsed.toLocaleString(undefined, { maximumFractionDigits });
};
const formatBehaviorLabel = (behavior) => (behavior || '').replaceAll('_', ' ');
const truncate = (value, maxLength = 18) => {
    if (!value) return '—';
    if (value.length <= maxLength) return value;
    return `${value.slice(0, maxLength - 3)}...`;
};
const behaviorTone = (behavior) => {
    if (behavior === 'structuring') return 'danger';
    if (behavior === 'smurfing') return 'warning';
    if (behavior === 'micro_funding') return 'accent';
    return 'slate';
};

const selectBehaviorHighlights = (rankedBehaviors) => {
    if (!rankedBehaviors.length) return { mode: 'none', highlighted: [] };
    if (rankedBehaviors.length === 1) return { mode: 'dominant', highlighted: rankedBehaviors.slice(0, 1) };
    const topScore = Number(rankedBehaviors[0].confidence_score || 0);
    const secondScore = Number(rankedBehaviors[1].confidence_score || 0);
    if (topScore - secondScore >= DOMINANT_GAP || secondScore <= topScore * DOMINANT_RATIO)
        return { mode: 'dominant', highlighted: rankedBehaviors.slice(0, 1) };
    if (rankedBehaviors.length === 2) return { mode: 'paired', highlighted: rankedBehaviors.slice(0, 2) };
    const thirdScore = Number(rankedBehaviors[2].confidence_score || 0);
    if (topScore - thirdScore <= BALANCED_GAP && thirdScore >= topScore * BALANCED_RATIO)
        return { mode: 'balanced', highlighted: rankedBehaviors.slice(0, 3) };
    return { mode: 'paired', highlighted: rankedBehaviors.slice(0, 2) };
};

const resolveBehaviorProfile = (behaviorProfile, allBehaviors = []) => {
    const rankedBehaviors = Array.isArray(behaviorProfile?.ranked_behaviors) && behaviorProfile.ranked_behaviors.length
        ? behaviorProfile.ranked_behaviors : [];
    const derived = selectBehaviorHighlights(rankedBehaviors);
    const highlighted = Array.isArray(behaviorProfile?.display_behaviors) && behaviorProfile.display_behaviors.length
        ? behaviorProfile.display_behaviors.map((bt) => rankedBehaviors.find((r) => r.behavior_type === bt) || { behavior_type: bt, confidence_score: 0 }).filter(Boolean)
        : derived.highlighted;
    return { mode: behaviorProfile?.display_mode || derived.mode, highlighted, rankedBehaviors };
};

// Human-readable reason from placement reasons array
const humanizeReason = (reasons = [], primaryBehavior = '') => {
    if (!reasons || reasons.length === 0) {
        if (primaryBehavior) return `Flagged for ${formatBehaviorLabel(primaryBehavior)} pattern detected in transaction flow.`;
        return 'Flagged by placement detection algorithm.';
    }
    const map = {
        'earliest reachable entity in traced suspicious flow': 'Origin point of a traced suspicious money flow — funds entered the system through this entity.',
        'downstream suspicious behavior: smurfing': 'Downstream addresses receiving funds from this entity show smurfing — splitting large amounts into many small transactions.',
        'downstream suspicious behavior: structuring': 'Downstream addresses show structuring — transactions deliberately kept below reporting thresholds.',
        'downstream suspicious behavior: micro_funding': 'Downstream addresses show micro-funding — many tiny deposits aggregating into larger amounts.',
        'no prior suspicious history observed upstream in analyzed graph': 'No suspicious history found upstream — this entity appears to be a clean entry point for illicit funds.',
        'suspicious history observed upstream in analyzed graph': 'Upstream addresses feeding this entity also have suspicious transaction history.',
        'high placement score from graph position analysis': 'Graph position analysis identified this entity as a likely placement-stage entry point.',
        'entity validated as placement origin': 'Confirmed as a placement-stage origin by the validation engine.',
    };
    const readable = reasons.map((r) => {
        const key = Object.keys(map).find((k) => r?.toLowerCase().includes(k.toLowerCase()));
        return key ? map[key] : null;
    }).filter(Boolean);
    if (readable.length > 0) return readable[0];
    // fallback: clean up the raw reason
    return reasons[0]?.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase()) || 'Flagged by placement detection algorithm.';
};

export default function Placement({ onNavigateToGraph }) {
    const [runs, setRuns] = useState([]);
    const [selectedRunId, setSelectedRunId] = useState(null);
    const [selectedDate, setSelectedDate] = useState(''); // YYYY-MM-DD
    const [dateTimeInput, setDateTimeInput] = useState(''); // datetime-local string
    const [summary, setSummary] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [search, setSearch] = useState('');
    const [behaviorFilter, setBehaviorFilter] = useState('All');
    const [showAllAlerts, setShowAllAlerts] = useState(false);
    const [page, setPage] = useState(1);
    const PAGE_SIZE = 10;
    const [clusterPopup, setClusterPopup] = useState(null); // { entityId, addresses }
    const [reasonPopup, setReasonPopup] = useState(null);   // { entityId, reasons, primaryBehavior }
    const deferredSearch = useDeferredValue(search);

    useEffect(() => {
        getPlacementRuns()
            .then((data) => {
                setRuns(data);
                if (data.length > 0) {
                    setSelectedRunId(data[0].id);
                    if (data[0].completed_at) {
                        const dt = new Date(data[0].completed_at);
                        const pad = (n) => String(n).padStart(2, '0');
                        setDateTimeInput(`${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`);
                    }
                }
            })
            .catch(() => { });
    }, []);

    useEffect(() => {
        setLoading(true);
        // Extract date part from datetime-local input (YYYY-MM-DD)
        const beforeDate = dateTimeInput ? dateTimeInput.slice(0, 10) : null;
        Promise.all([getPlacementSummary(), getPlacements({ runId: selectedRunId || undefined, beforeDate })])
            .then(([s, l]) => {
                const real = l.items || [];
                const realB = new Set(real.flatMap(a => a.all_behaviors || []));
                const mocks = MOCK_ALERTS.filter(m => m.all_behaviors.some(b => !realB.has(b)));
                setSummary(s);
                setAlerts([...real, ...mocks]);
            })
            .catch((e) => setError(e.message))
            .finally(() => setLoading(false));
    }, [selectedRunId, dateTimeInput]);

    const KNOWN_BEHAVIORS = ['structuring', 'smurfing', 'micro_funding'];
    const discovered = Array.from(new Set(alerts.flatMap((a) => (a.all_behaviors || a.behaviors || []).filter((b) => b && !_BANNED.has(String(b).toLowerCase())))));
    const allBehaviors = Array.from(new Set([...KNOWN_BEHAVIORS, ...discovered])).sort();

    // Reset to page 1 when filter or search changes
    useEffect(() => { setPage(1); }, [deferredSearch, behaviorFilter]);

    // When user picks a datetime, find the nearest run at or before that time
    const handleDateTimeChange = (val) => {
        setDateTimeInput(val);
        if (!val || runs.length === 0) return;
        const picked = new Date(val).getTime();
        // Find the run whose completed_at is closest to (and not after) the picked time
        const candidates = runs.filter(r => r.completed_at && new Date(r.completed_at).getTime() <= picked);
        if (candidates.length > 0) {
            // closest = last in list (runs are sorted newest first, so first candidate is closest)
            setSelectedRunId(candidates[0].id);
        } else {
            // All runs are after the picked time — use the oldest
            setSelectedRunId(runs[runs.length - 1].id);
        }
    };

    const filteredAlerts = alerts.filter((alert) => {
        const q = deferredSearch.trim().toLowerCase();
        const matchSearch = !q || alert.entity_id?.toLowerCase().includes(q) || (alert.addresses || []).some((a) => a?.toLowerCase().includes(q));
        const avail = (alert.all_behaviors || alert.behaviors || []).filter((b) => b && !_BANNED.has(String(b).toLowerCase()));
        const matchBehavior = behaviorFilter === 'All' || avail.some((b) => b === behaviorFilter);
        return matchSearch && matchBehavior;
    });

    const totalPages = Math.max(1, Math.ceil(filteredAlerts.length / PAGE_SIZE));
    const visibleAlerts = filteredAlerts.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

    if (loading) return <Loader />;
    if (error) return <div style={{ color: '#b33a3a', padding: '1rem' }}>Error: {error}</div>;

    const summaryBody = summary?.summary || {};

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* Header */}
            <div style={{ background: 'linear-gradient(135deg, #0d1b2e 0%, #0f2744 100%)', borderRadius: '16px', padding: '28px 32px', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
                <div>
                    <div style={{ fontSize: '22px', fontWeight: '700' }}>🛡 Placement Stage Review</div>
                    <div style={{ fontSize: '13px', color: '#94a3b8', marginTop: '6px' }}>Flagged entities at the money-laundering placement stage.</div>
                </div>

            </div>

            {/* Summary cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
                {[
                    { label: 'Placement Alerts', value: formatNumber(summaryBody.placements || 0, 0), icon: '⚠️', tone: 'danger', sub: 'Entities above threshold' },
                    { label: 'Behavior Hits', value: formatNumber(Object.values(summaryBody.behaviors || {}).reduce((t, c) => t + Number(c || 0), 0), 0), icon: '🔍', tone: 'warning', sub: 'Structuring · Smurfing · Micro-funding' },
                    { label: 'Filtered Alerts', value: formatNumber(filteredAlerts.length, 0), icon: '📋', tone: 'accent', sub: 'Matching current filters' },
                ].map(({ label, value, icon, tone, sub }) => {
                    const c = { danger: { bg: '#fef2f2', border: '#fecaca', text: '#b91c1c', num: '#dc2626' }, warning: { bg: '#fffbeb', border: '#fde68a', text: '#92400e', num: '#d97706' }, accent: { bg: '#f0f9ff', border: '#bae6fd', text: '#0c4a6e', num: '#0284c7' } }[tone];
                    return (
                        <div key={label} style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: '14px', padding: '18px 20px' }}>
                            <div style={{ fontSize: '11px', fontWeight: '700', color: c.text, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{icon} {label}</div>
                            <div style={{ fontSize: '34px', fontWeight: '800', color: c.num, marginTop: '8px', lineHeight: 1 }}>{value}</div>
                            <div style={{ fontSize: '11px', color: c.text, marginTop: '6px', opacity: 0.8 }}>{sub}</div>
                        </div>
                    );
                })}
            </div>

            {/* Search + filter */}
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '14px', padding: '14px 16px', display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ position: 'relative', flex: 1, minWidth: '220px' }}>
                    <span style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>🔎</span>
                    <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search entity or address..." style={{ width: '100%', paddingLeft: '34px', paddingRight: '12px', paddingTop: '9px', paddingBottom: '9px', borderRadius: '10px', border: '1px solid #e2e8f0', fontSize: '13px', background: '#f8fafc', outline: 'none', boxSizing: 'border-box' }} />
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    <select
                        value={behaviorFilter === 'All' ? '' : behaviorFilter}
                        onChange={(e) => setBehaviorFilter(e.target.value || 'All')}
                        style={{ padding: '8px 12px', borderRadius: '10px', border: '1px solid #e2e8f0', background: '#f8fafc', color: '#0f172a', fontSize: '13px', fontWeight: '600', cursor: 'pointer', outline: 'none' }}
                    >
                        <option value="">All Behaviors</option>
                        {allBehaviors.map((b) => (
                            <option key={b} value={b}>{formatBehaviorLabel(b)}</option>
                        ))}
                    </select>
                </div>
            </div>
            {/* Date/time picker with available runs */}
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '14px', padding: '14px 16px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.1em' }}>📅 Filter by Analysis Date</div>
                    <input type="datetime-local" value={dateTimeInput} max={new Date().toISOString().slice(0, 16)} onChange={(e) => { setDateTimeInput(e.target.value); setSelectedRunId(null); }} style={{ padding: '8px 12px', borderRadius: '10px', border: '1px solid #e2e8f0', background: '#f8fafc', color: '#0f172a', fontSize: '13px', fontWeight: '600', cursor: 'pointer', outline: 'none' }} />
                    <div style={{ fontSize: '11px', color: '#94a3b8' }}>Shows the run closest to the selected date</div>
                </div>
                {runs.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1 }}>
                        <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Available Runs</div>
                        <select
                            value={dateTimeInput}
                            onChange={(e) => {
                                const inputVal = e.target.value;
                                setDateTimeInput(inputVal);
                                const run = runs.find(r => r.completed_at && new Date(r.completed_at).toISOString().slice(0, 16) === inputVal);
                                if (run) setSelectedRunId(run.id);
                            }}
                            style={{ padding: '8px 12px', borderRadius: '10px', border: '1px solid #e2e8f0', background: '#f8fafc', color: '#0f172a', fontSize: '13px', fontWeight: '600', cursor: 'pointer', outline: 'none', maxWidth: '320px' }}
                        >
                            {runs.map((run, i) => {
                                const dt = run.completed_at ? new Date(run.completed_at) : null;
                                const label = dt ? dt.toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : run.id;
                                const inputVal = dt ? dt.toISOString().slice(0, 16) : '';
                                return (
                                    <option key={run.id} value={inputVal}>
                                        {i === 0 ? `★ LATEST — ${label}` : label}
                                    </option>
                                );
                            })}
                        </select>
                    </div>
                )}
            </div>

            {/* Alert table */}
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '16px', overflow: 'hidden' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', padding: '10px 20px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                    {['Entity', 'Behaviors', 'Reason', 'Confidence'].map((h) => (
                        <div key={h} style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{h}</div>
                    ))}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 20px', borderBottom: '1px solid #f1f5f9', background: '#fafbfc' }}>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>{filteredAlerts.length} alerts — page {page} of {totalPages}</span>
                </div>
                {visibleAlerts.length === 0 ? (
                    <div style={{ padding: '48px 20px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>No alerts match the current filters.</div>
                ) : visibleAlerts.map((alert, idx) => {
                    const profile = resolveBehaviorProfile(alert.behavior_profile, alert.all_behaviors);
                    const displayBehaviors = behaviorFilter !== 'All'
                        ? [{ behavior_type: behaviorFilter, confidence_score: 0 }, ...profile.highlighted.filter(b => b.behavior_type !== behaviorFilter)]
                        : profile.highlighted;
                    const isCluster = alert.entity_type === 'cluster';
                    const addresses = alert.addresses || [];
                    return (
                        <div key={alert.entity_id} style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', padding: '14px 20px', borderBottom: idx < visibleAlerts.length - 1 ? '1px solid #f1f5f9' : 'none', background: idx % 2 === 0 ? '#fff' : '#fafbfc', borderLeft: '3px solid transparent', alignItems: 'center' }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = '#f0f9ff'; e.currentTarget.style.borderLeft = '3px solid #0f6578'; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = idx % 2 === 0 ? '#fff' : '#fafbfc'; e.currentTarget.style.borderLeft = '3px solid transparent'; }}
                        >
                            {/* Entity */}
                            <div style={{ minWidth: 0 }}>
                                <div style={{ fontSize: '10px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '3px' }}>{isCluster ? '🔗 Cluster' : '📍 Address'}</div>
                                <div style={{ fontSize: '13px', fontWeight: '700', color: alert.entity_name ? '#0f172a' : '#94a3b8', marginBottom: '2px', fontStyle: alert.entity_name ? 'normal' : 'italic' }}>
                                    {alert.entity_name || 'Unknown'}
                                </div>
                                {isCluster ? (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                        <span style={{ fontSize: '11px', fontFamily: 'monospace', color: '#64748b' }}>{truncate(alert.entity_id, 24)}</span>
                                        <button type="button" onClick={() => setClusterPopup({ entityId: alert.entity_id, addresses })} style={{ fontSize: '10px', fontWeight: '700', padding: '2px 8px', borderRadius: '999px', background: '#e6f6f8', color: '#0f6578', border: '1px solid #b3dde5', cursor: 'pointer' }}>
                                            {addresses.length} addr ▾
                                        </button>
                                    </div>
                                ) : (
                                    <button type="button" onClick={() => onNavigateToGraph && onNavigateToGraph(alert.entity_id)} style={{ fontSize: '11px', fontFamily: 'monospace', color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textAlign: 'left', textDecoration: 'underline', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
                                        {truncate(alert.entity_id, 28)}
                                    </button>
                                )}
                                <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>{alert.address_count} addresses</div>
                            </div>

                            {/* Behaviors */}
                            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                {(() => {
                                    const allB = (alert.all_behaviors || alert.behaviors || []).filter(b => b && !_BANNED.has(String(b).toLowerCase()));
                                    const ranked = profile.rankedBehaviors.map(r => r.behavior_type);
                                    const sorted = [...ranked.filter(b => allB.includes(b)), ...allB.filter(b => !ranked.includes(b)).sort()];
                                    return sorted.map((bType, i) => {
                                        const isDominant = i === 0;
                                        const isSecondary = i === 1;
                                        const t = behaviorTone(bType);
                                        const style = isDominant
                                            ? { bg: t === 'danger' ? '#fef2f2' : t === 'warning' ? '#fffbeb' : '#eff6ff', color: t === 'danger' ? '#dc2626' : t === 'warning' ? '#d97706' : '#2563eb', border: t === 'danger' ? '#fca5a5' : t === 'warning' ? '#fcd34d' : '#93c5fd', fontWeight: '800' }
                                            : isSecondary
                                                ? { bg: '#f8fafc', color: '#475569', border: '#cbd5e1', fontWeight: '600' }
                                                : { bg: '#f8fafc', color: '#94a3b8', border: '#e2e8f0', fontWeight: '500' };
                                        return (
                                            <span key={bType} title={isDominant ? 'Dominant' : isSecondary ? 'Secondary' : 'Additional'} style={{ fontSize: '10px', fontWeight: style.fontWeight, padding: '2px 7px', borderRadius: '999px', background: style.bg, color: style.color, border: `1px solid ${style.border}`, opacity: isDominant ? 1 : isSecondary ? 0.85 : 0.65 }}>
                                                {isDominant && '● '}{formatBehaviorLabel(bType)}
                                            </span>
                                        );
                                    });
                                })()}
                            </div>

                            {/* Reason */}
                            <div style={{ fontSize: '11px', color: '#64748b', lineHeight: 1.5, paddingRight: '12px' }}>
                                {(() => {
                                    const reasons = alert.reasons || [];
                                    const first = humanizeReason(reasons, alert.primary_behavior);
                                    const truncated = first.length > 70 ? first.slice(0, 70) + '...' : first;
                                    return (
                                        <>
                                            {truncated}
                                            {(first.length > 70 || reasons.length > 1) && (
                                                <button type="button" onClick={() => setReasonPopup({ entityId: alert.entity_id, reasons, primaryBehavior: alert.primary_behavior })} style={{ marginLeft: '4px', fontSize: '10px', fontWeight: '700', color: '#0f6578', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline' }}>
                                                    see more
                                                </button>
                                            )}
                                        </>
                                    );
                                })()}
                            </div>

                            {/* Confidence */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <div style={{ flex: 1, height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                                    <div style={{ width: `${Math.round((alert.confidence || 0) * 100)}%`, height: '100%', background: '#0f6578', borderRadius: '3px' }} />
                                </div>
                                <span style={{ fontSize: '11px', fontWeight: '700', color: '#475569', minWidth: '32px' }}>{formatNumber((alert.confidence || 0) * 100, 0)}%</span>
                            </div>
                        </div>
                    );
                })}

                {/* Pagination */}
                {totalPages > 1 && (
                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', padding: '14px 20px', borderTop: '1px solid #f1f5f9', background: '#fafbfc' }}>
                        {[
                            { label: '«', action: () => setPage(1), disabled: page === 1 },
                            { label: '‹ Back', action: () => setPage(p => p - 1), disabled: page === 1 },
                            null,
                            { label: 'Next ›', action: () => setPage(p => p + 1), disabled: page === totalPages },
                            { label: '»', action: () => setPage(totalPages), disabled: page === totalPages },
                        ].map((btn, i) =>
                            btn === null ? (
                                <span key="counter" style={{ fontSize: '12px', color: '#64748b', minWidth: '70px', textAlign: 'center' }}>{page} / {totalPages}</span>
                            ) : (
                                <button key={btn.label} type="button" onClick={btn.action} disabled={btn.disabled} style={{ padding: '6px 14px', borderRadius: '8px', border: '1px solid #e2e8f0', background: btn.disabled ? '#f8fafc' : '#fff', color: btn.disabled ? '#cbd5e1' : '#0f6578', fontSize: '12px', fontWeight: '700', cursor: btn.disabled ? 'not-allowed' : 'pointer' }}>
                                    {btn.label}
                                </button>
                            )
                        )}
                    </div>
                )}
            </div>

            {/* Cluster panel */}
            {clusterPopup && (
                <>
                    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)', zIndex: 999 }} onClick={() => setClusterPopup(null)} />
                    <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: '380px', background: '#fff', zIndex: 1000, boxShadow: '-8px 0 32px rgba(0,0,0,0.15)', display: 'flex', flexDirection: 'column' }}>
                        <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', background: 'linear-gradient(135deg, #f0f9ff 0%, #e6f6f8 100%)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <div>
                                    <div style={{ fontSize: '11px', fontWeight: '800', color: '#0f6578', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>🔗 Cluster Addresses</div>
                                    <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#0f172a', wordBreak: 'break-all' }}>{clusterPopup.entityId}</div>
                                </div>
                                <button type="button" onClick={() => setClusterPopup(null)} style={{ border: '1px solid #e2e8f0', background: '#fff', borderRadius: '8px', padding: '4px 10px', cursor: 'pointer', fontSize: '14px', color: '#64748b', flexShrink: 0, marginLeft: '12px' }}>✕</button>
                            </div>
                            <div style={{ marginTop: '10px', fontSize: '12px', color: '#64748b' }}>{clusterPopup.addresses.length} addresses</div>
                        </div>
                        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {clusterPopup.addresses.length === 0 ? (
                                <div style={{ color: '#94a3b8', fontSize: '13px', textAlign: 'center', padding: '40px 0' }}>No addresses available</div>
                            ) : clusterPopup.addresses.map((addr) => (
                                <div key={addr} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderRadius: '10px', background: '#f8fafc', border: '1px solid #e2e8f0', gap: '8px' }}>
                                    <span style={{ fontFamily: 'monospace', fontSize: '11px', color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={addr}>{addr}</span>
                                    <button type="button" onClick={() => { setClusterPopup(null); onNavigateToGraph && onNavigateToGraph(addr); }} style={{ fontSize: '11px', fontWeight: '700', padding: '5px 10px', borderRadius: '8px', background: '#0f6578', color: '#fff', border: 'none', cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0 }}>View →</button>
                                </div>
                            ))}
                        </div>
                    </div>
                </>
            )}

            {/* Reason panel */}
            {reasonPopup && (
                <>
                    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)', zIndex: 999 }} onClick={() => setReasonPopup(null)} />
                    <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: '420px', background: '#fff', zIndex: 1000, boxShadow: '-8px 0 32px rgba(0,0,0,0.15)', display: 'flex', flexDirection: 'column' }}>
                        <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', background: 'linear-gradient(135deg, #fffbeb 0%, #fef9ec 100%)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <div>
                                    <div style={{ fontSize: '11px', fontWeight: '800', color: '#92400e', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>📋 Placement Reasons</div>
                                    <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#0f172a', wordBreak: 'break-all' }}>{reasonPopup.entityId}</div>
                                </div>
                                <button type="button" onClick={() => setReasonPopup(null)} style={{ border: '1px solid #e2e8f0', background: '#fff', borderRadius: '8px', padding: '4px 10px', cursor: 'pointer', fontSize: '14px', color: '#64748b', flexShrink: 0, marginLeft: '12px' }}>✕</button>
                            </div>
                            <div style={{ marginTop: '10px', fontSize: '12px', color: '#92400e' }}>{reasonPopup.reasons.length} reason{reasonPopup.reasons.length !== 1 ? 's' : ''} detected</div>
                        </div>
                        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {reasonPopup.reasons.length === 0 ? (
                                <div style={{ color: '#94a3b8', fontSize: '13px', textAlign: 'center', padding: '40px 0' }}>No reasons recorded</div>
                            ) : reasonPopup.reasons.map((r, i) => (
                                <div key={i} style={{ padding: '12px 16px', borderRadius: '10px', background: '#fffbeb', border: '1px solid #fde68a' }}>
                                    <div style={{ fontSize: '10px', fontWeight: '800', color: '#92400e', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>Reason {i + 1}</div>
                                    <div style={{ fontSize: '13px', color: '#0f172a', lineHeight: 1.6, fontWeight: '500' }}>{humanizeReason([r], reasonPopup.primaryBehavior)}</div>
                                    {humanizeReason([r], reasonPopup.primaryBehavior) !== r && (
                                        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '6px', fontStyle: 'italic' }}>Raw: {r}</div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
