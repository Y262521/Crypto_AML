import { useDeferredValue, useEffect, useState } from 'react';
import Loader from '../components/common/Loader';
import AnalyzeButton from '../components/common/AnalyzeButton';
import ChainBadge from '../components/chain/ChainBadge';
import ChainFilter from '../components/chain/ChainFilter';
import ChainOfCustodyModal from '../components/ChainOfCustodyModal';
import { getIntegrationAlerts, getIntegrationRuns, getIntegrationSummary } from '../services/transactionService';

const formatNumber = (value, maximumFractionDigits = 2) => {
    const parsed = Number(value || 0);
    if (!Number.isFinite(parsed)) return '0';
    return parsed.toLocaleString(undefined, { maximumFractionDigits });
};

const truncate = (value, maxLength = 20) => {
    if (!value) return '—';
    if (value.length <= maxLength) return value;
    return `${value.slice(0, 8)}...${value.slice(-6)}`;
};

const SIGNAL_META = {
    convergence: { label: 'Convergence', icon: '🔀', color: '#7c3aed', bg: '#f5f3ff', border: '#ddd6fe' },
    dormancy: { label: 'Dormancy', icon: '💤', color: '#0369a1', bg: 'rgba(96,165,250,0.12)', border: 'rgba(96,165,250,0.3)' },
    terminal_node: { label: 'Terminal Node', icon: '🚪', color: '#b91c1c', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)' },
    reaggregation: { label: 'Reaggregation', icon: '🔁', color: '#d97706', bg: 'rgba(251,191,36,0.12)', border: 'rgba(251,191,36,0.3)' },
};

const signalMeta = (signal) =>
    SIGNAL_META[signal] || { label: signal?.replaceAll('_', ' ') || signal, icon: '⚡', color: '#8A9DB5', bg: 'rgba(255,255,255,0.06)', border: 'rgba(255,255,255,0.12)' };

const scoreColor = (score) => {
    if (score >= 0.70) return { text: '#b91c1c', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)' };
    if (score >= 0.50) return { text: '#d97706', bg: 'rgba(251,191,36,0.12)', border: 'rgba(251,191,36,0.3)' };
    return { text: '#4ADE80', bg: 'rgba(74,222,128,0.10)', border: 'rgba(74,222,128,0.25)' };
};

const humanizeReason = (reasons = [], primarySignal = '') => {
    if (!reasons || reasons.length === 0) {
        if (primarySignal) return `Flagged for ${signalMeta(primarySignal).label} pattern.`;
        return 'Flagged by integration detection algorithm.';
    }
    return reasons[0];
};

export default function Integration({ onNavigateToGraph, onOpenWorkspace }) {
    const [runs, setRuns] = useState([]);
    const [selectedRunId, setSelectedRunId] = useState(null);
    const [dateTimeInput, setDateTimeInput] = useState('');
    const [summary, setSummary] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [search, setSearch] = useState('');
    const [signalFilter, setSignalFilter] = useState('All');
    const [chainFilter, setChainFilter] = useState('all');
    const [page, setPage] = useState(1);
    const PAGE_SIZE = 10;
    const deferredSearch = useDeferredValue(search);
    const [custodyEntity, setCustodyEntity] = useState(null);

    // Load runs on mount
    useEffect(() => {
        getIntegrationRuns()
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

    // Load summary + alerts when run changes
    useEffect(() => {
        setLoading(true);
        const beforeDate = dateTimeInput ? dateTimeInput.slice(0, 10) : null;
        Promise.all([
            getIntegrationSummary(selectedRunId || undefined),
            getIntegrationAlerts({ runId: selectedRunId || undefined, beforeDate, limit: 10000 }),
        ])
            .then(([s, l]) => {
                setSummary(s);
                setAlerts(l.items || []);
            })
            .catch((e) => setError(e.message))
            .finally(() => setLoading(false));
    }, [selectedRunId, dateTimeInput]);

    useEffect(() => { setPage(1); }, [deferredSearch, signalFilter]);

    const allSignals = Array.from(
        new Set(alerts.flatMap((a) => a.signals_fired || []))
    ).sort();

    const filteredAlerts = alerts.filter((alert) => {
        const q = deferredSearch.trim().toLowerCase();
        const matchSearch = !q || alert.entity_id?.toLowerCase().includes(q);
        const matchSignal = signalFilter === 'All' || (alert.signals_fired || []).includes(signalFilter);
        const alertChain = alert.chain_name || alert.chain || null;
        const matchChain = chainFilter === 'all' || (alertChain !== null && alertChain === chainFilter);
        return matchSearch && matchSignal && matchChain;
    });

    const totalPages = Math.max(1, Math.ceil(filteredAlerts.length / PAGE_SIZE));
    const visibleAlerts = filteredAlerts.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

    if (loading) return <Loader />;
    if (error) return <div style={{ color: '#b33a3a', padding: '1rem' }}>Error: {error}</div>;

    const summaryBody = summary?.summary || {};

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* Header */}
            <div style={{ background: 'linear-gradient(135deg,#0D1628,#132240)', border: '1px solid rgba(201,168,76,0.12)', borderRadius: '16px', padding: '28px 32px', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
                <div>
                    <div style={{ fontSize: '24px', fontWeight: '700' }}>Integration Stage Alerts</div>
                    <div style={{ fontSize: '13px', color: '#cbd5e1', marginTop: '6px' }}>
                        Flagged entities at the final money-laundering integration stage — funds re-entering the legitimate economy.
                    </div>
                </div>
            </div>

            {/* Summary cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px' }}>
                {[
                    { label: 'Integration Alerts', value: formatNumber(summaryBody.alerts || 0, 0), icon: '⚠️', tone: 'danger', sub: 'Entities above threshold' },
                    { label: 'High Confidence', value: formatNumber(summaryBody.high_confidence_alerts || 0, 0), icon: '🔴', tone: 'danger', sub: 'Score ≥ 70%' },
                    { label: 'Convergence', value: formatNumber(summaryBody.convergence_signals || 0, 0), icon: '🔀', tone: 'purple', sub: 'Fan-in detected' },
                    { label: 'Dormancy', value: formatNumber(summaryBody.dormancy_signals || 0, 0), icon: '💤', tone: 'blue', sub: 'Cooling-off pattern' },
                    { label: 'Terminal Exits', value: formatNumber(summaryBody.terminal_signals || 0, 0), icon: '🚪', tone: 'warning', sub: 'Exit points found' },
                    { label: 'Reaggregation', value: formatNumber(summaryBody.reaggregation_signals || 0, 0), icon: '🔁', tone: 'accent', sub: 'Fund reassembly' },
                ].map(({ label, value, icon, tone, sub }) => {
                    const c = {
                        danger: { bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)', text: '#b91c1c', num: '#dc2626' },
                        warning: { bg: 'rgba(251,191,36,0.12)', border: 'rgba(251,191,36,0.3)', text: '#92400e', num: '#d97706' },
                        accent: { bg: 'rgba(96,165,250,0.12)', border: 'rgba(96,165,250,0.3)', text: '#0c4a6e', num: '#0284c7' },
                        purple: { bg: 'rgba(167,139,250,0.10)', border: 'rgba(167,139,250,0.25)', text: '#A78BFA', num: '#A78BFA' },
                        blue: { bg: 'rgba(96,165,250,0.10)', border: 'rgba(96,165,250,0.25)', text: '#60A5FA', num: '#60A5FA' },
                    }[tone];
                    return (
                        <div key={label} style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: '14px', padding: '16px 18px' }}>
                            <div style={{ fontSize: '11px', fontWeight: '700', color: c.text, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{icon} {label}</div>
                            <div style={{ fontSize: '30px', fontWeight: '800', color: c.num, marginTop: '6px', lineHeight: 1 }}>{value}</div>
                            <div style={{ fontSize: '11px', color: c.text, marginTop: '4px', opacity: 0.8 }}>{sub}</div>
                        </div>
                    );
                })}
            </div>

            {/* Chain filter dropdown */}
            <div style={{ background: 'linear-gradient(145deg,#101D32,#0D1628)', border: '1px solid rgba(201,168,76,0.12)', borderRadius: '14px', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                <ChainFilter
                    selectedChain={chainFilter}
                    onChainChange={(c) => { setChainFilter(c); setPage(1); }}
                    compact
                    label="Filter by Chain"
                />
                {chainFilter !== 'all' && (
                    <button onClick={() => { setChainFilter('all'); setPage(1); }}
                        style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '7px', padding: '5px 10px', cursor: 'pointer', fontSize: '11px', color: '#4B5E72' }}>
                        Clear
                    </button>
                )}
            </div>

            {/* Search + signal filter */}
            <div style={{ background: 'linear-gradient(145deg,#101D32,#0D1628)', border: '1px solid rgba(201,168,76,0.12)', borderRadius: '14px', padding: '14px 16px', display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ position: 'relative', flex: 1, minWidth: '220px' }}>
                    <span style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>🔎</span>
                    <input
                        type="text" value={search} onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search entity address..."
                        style={{ width: '100%', paddingLeft: '34px', paddingRight: '12px', paddingTop: '9px', paddingBottom: '9px', borderRadius: '10px', border: '1px solid rgba(201,168,76,0.12)', fontSize: '13px', background: 'rgba(201,168,76,0.04)', outline: 'none', boxSizing: 'border-box' }}
                    />
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    <select
                        value={signalFilter === 'All' ? '' : signalFilter}
                        onChange={(e) => setSignalFilter(e.target.value || 'All')}
                        style={{ padding: '8px 12px', borderRadius: '10px', border: '1px solid rgba(201,168,76,0.12)', background: 'rgba(201,168,76,0.04)', color: '#E2D9C8', fontSize: '13px', fontWeight: '600', cursor: 'pointer', outline: 'none' }}
                    >
                        <option value="">All Signals</option>
                        {allSignals.map((s) => (
                            <option key={s} value={s}>{s.replaceAll('_', ' ')}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Run selector */}
            <div style={{ background: 'linear-gradient(145deg,#101D32,#0D1628)', border: '1px solid rgba(201,168,76,0.12)', borderRadius: '14px', padding: '14px 16px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div style={{ fontSize: '11px', fontWeight: '700', color: '#6B7E94', textTransform: 'uppercase', letterSpacing: '0.1em' }}>📅 Filter by Analysis Date</div>
                    <input
                        type="datetime-local" value={dateTimeInput} max={new Date().toISOString().slice(0, 16)}
                        onChange={(e) => { setDateTimeInput(e.target.value); setSelectedRunId(null); }}
                        style={{ padding: '8px 12px', borderRadius: '10px', border: '1px solid rgba(201,168,76,0.12)', background: 'rgba(201,168,76,0.04)', color: '#E2D9C8', fontSize: '13px', fontWeight: '600', cursor: 'pointer', outline: 'none' }}
                    />
                    <div style={{ fontSize: '11px', color: '#4B5E72' }}>Shows the run closest to the selected date</div>
                </div>
                {runs.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1 }}>
                        <div style={{ fontSize: '11px', fontWeight: '700', color: '#6B7E94', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Available Runs</div>
                        <select
                            value={dateTimeInput}
                            onChange={(e) => {
                                const inputVal = e.target.value;
                                setDateTimeInput(inputVal);
                                const run = runs.find(r => r.completed_at && new Date(r.completed_at).toISOString().slice(0, 16) === inputVal);
                                if (run) setSelectedRunId(run.id);
                            }}
                            style={{ padding: '8px 12px', borderRadius: '10px', border: '1px solid rgba(201,168,76,0.12)', background: 'rgba(201,168,76,0.04)', color: '#E2D9C8', fontSize: '13px', fontWeight: '600', cursor: 'pointer', outline: 'none', maxWidth: '320px' }}
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
            <div style={{ background: 'linear-gradient(145deg,#101D32,#0D1628)', border: '1px solid rgba(201,168,76,0.12)', borderRadius: '16px', overflow: 'hidden' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr 1.5fr 1fr 120px', padding: '10px 20px', background: '#132240', borderBottom: '1px solid rgba(201,168,76,0.10)' }}>
                    {['Entity', 'Signals Fired', 'Reason', 'Score', 'Analyze'].map((h) => (
                        <div key={h} style={{ fontSize: '11px', fontWeight: '800', color: '#6B7E94', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{h}</div>
                    ))}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 20px', borderBottom: '1px solid rgba(201,168,76,0.06)', background: '#101D32' }}>
                    <span style={{ fontSize: '12px', color: '#4B5E72' }}>{filteredAlerts.length} alerts — page {page} of {totalPages}</span>
                </div>

                {visibleAlerts.length === 0 ? (
                    <div style={{ padding: '48px 20px', textAlign: 'center', color: '#4B5E72', fontSize: '13px' }}>
                        {alerts.length === 0
                            ? 'No integration alerts found. Run the ETL pipeline to generate integration analysis.'
                            : 'No alerts match the current filters.'}
                    </div>
                ) : visibleAlerts.map((alert, idx) => {
                    const sc = scoreColor(alert.integration_score || 0);
                    const signals = alert.signals_fired || [];
                    const reason = humanizeReason(alert.reasons, alert.primary_signal);
                    const truncatedReason = reason.length > 80 ? reason.slice(0, 80) + '...' : reason;

                    return (
                        <div
                            key={alert.entity_id}
                            style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr 1.5fr 1fr 120px', padding: '14px 20px', borderBottom: idx < visibleAlerts.length - 1 ? '1px solid rgba(201,168,76,0.06)' : 'none', background: idx % 2 === 0 ? '#0D1628' : '#101D32', borderLeft: '3px solid transparent', alignItems: 'center' }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = '#132240'; e.currentTarget.style.borderLeft = '3px solid rgba(201,168,76,0.4)'; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = idx % 2 === 0 ? '#0D1628' : '#101D32'; e.currentTarget.style.borderLeft = '3px solid transparent'; }}
                        >
                            {/* Entity */}
                            <div style={{ minWidth: 0 }}>
                                <div style={{ fontSize: '10px', fontWeight: '700', color: '#4B5E72', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '3px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    📍 Address
                                    <ChainBadge chain={alert.chain_name || 'ethereum'} size="xs" />
                                </div>
                                <div style={{ fontSize: '13px', fontWeight: '700', color: alert.entity_name ? '#0f172a' : '#94a3b8', marginBottom: '2px', fontStyle: alert.entity_name ? 'normal' : 'italic' }}>
                                    {alert.entity_name || 'Unknown'}
                                </div>
                                <button
                                    type="button"
                                    onClick={() => onNavigateToGraph && onNavigateToGraph(alert.entity_id)}
                                    style={{ fontSize: '11px', fontFamily: 'monospace', color: '#C9A84C', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textAlign: 'left', textDecoration: 'underline', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}
                                >
                                    {truncate(alert.entity_id, 30)}
                                </button>
                                <div style={{ fontSize: '11px', color: '#4B5E72', marginTop: '2px' }}>
                                    {alert.layering_score > 0 && <span style={{ marginRight: '8px' }}>Layering: {formatNumber(alert.layering_score * 100, 0)}%</span>}
                                    {alert.placement_score > 0 && <span>Placement: {formatNumber(alert.placement_score * 100, 0)}%</span>}
                                </div>
                            </div>

                            {/* Signals */}
                            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                {signals.map((sig, i) => {
                                    const meta = signalMeta(sig);
                                    const sigScore = alert.signal_scores?.[sig] || 0;
                                    return (
                                        <span
                                            key={sig}
                                            title={`${meta.label}: ${formatNumber(sigScore * 100, 0)}%`}
                                            style={{
                                                fontSize: '10px', fontWeight: i === 0 ? '800' : '600',
                                                padding: '2px 7px', borderRadius: '999px',
                                                background: meta.bg, color: meta.color,
                                                border: `1px solid ${meta.border}`,
                                                opacity: i === 0 ? 1 : 0.75,
                                            }}
                                        >
                                            {meta.icon} {meta.label}
                                        </span>
                                    );
                                })}
                            </div>

                            {/* Reason */}
                            <div style={{ fontSize: '11px', color: '#6B7E94', lineHeight: 1.5, paddingRight: '12px' }}>
                                {truncatedReason}
                            </div>

                            {/* Score */}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                                        <div style={{ width: `${Math.round((alert.integration_score || 0) * 100)}%`, height: '100%', background: sc.text, borderRadius: '3px' }} />
                                    </div>
                                    <span style={{ fontSize: '12px', fontWeight: '800', color: sc.text, minWidth: '36px' }}>
                                        {formatNumber((alert.integration_score || 0) * 100, 0)}%
                                    </span>
                                </div>
                                <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                                    <span style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '999px', background: sc.bg, color: sc.text, border: `1px solid ${sc.border}`, fontWeight: '700' }}>
                                        {(alert.integration_score || 0) >= 0.70 ? 'HIGH' : (alert.integration_score || 0) >= 0.50 ? 'MEDIUM' : 'LOW'}
                                    </span>
                                    <button
                                        type="button"
                                        onClick={() => setCustodyEntity(alert.entity_id)}
                                        style={{ fontSize: '10px', padding: '1px 7px', borderRadius: '999px', background: 'rgba(201,168,76,0.10)', color: '#C9A84C', border: '1px solid rgba(201,168,76,0.25)', cursor: 'pointer', fontWeight: '700' }}
                                    >
                                        🔗 Chain
                                    </button>
                                </div>
                            </div>

                            {/* Analyze Button */}
                            <AnalyzeButton
                                entityId={alert.entity_id}
                                entityType={alert.entity_type}
                                onSelectAnalysis={(id, type, analysisType) => {
                                    if (onOpenWorkspace) {
                                        onOpenWorkspace(id, type, 'Integration', analysisType);
                                    }
                                }}
                            />
                        </div>
                    );
                })}

                {/* Pagination */}
                {totalPages > 1 && (
                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', padding: '14px 20px', borderTop: '1px solid rgba(201,168,76,0.08)' }}>
                        <button onClick={() => setPage(1)} disabled={page === 1} style={{ padding: '5px 10px', borderRadius: '6px', border: '1px solid rgba(201,168,76,0.12)', background: 'transparent', color: page === 1 ? '#4B5E72' : '#C9A84C', cursor: page === 1 ? 'not-allowed' : 'pointer', fontSize: '12px' }}>«</button>
                        <button onClick={() => setPage(p => p - 1)} disabled={page === 1} style={{ padding: '5px 10px', borderRadius: '6px', border: '1px solid rgba(201,168,76,0.12)', background: 'transparent', color: page === 1 ? '#4B5E72' : '#C9A84C', cursor: page === 1 ? 'not-allowed' : 'pointer', fontSize: '12px' }}>‹</button>
                        <span style={{ fontSize: '12px', color: '#6B7E94', padding: '0 8px' }}>Page {page} / {totalPages}</span>
                        <button onClick={() => setPage(p => p + 1)} disabled={page === totalPages} style={{ padding: '5px 10px', borderRadius: '6px', border: '1px solid rgba(201,168,76,0.12)', background: 'transparent', color: page === totalPages ? '#4B5E72' : '#C9A84C', cursor: page === totalPages ? 'not-allowed' : 'pointer', fontSize: '12px' }}>›</button>
                        <button onClick={() => setPage(totalPages)} disabled={page === totalPages} style={{ padding: '5px 10px', borderRadius: '6px', border: '1px solid rgba(201,168,76,0.12)', background: 'transparent', color: page === totalPages ? '#4B5E72' : '#C9A84C', cursor: page === totalPages ? 'not-allowed' : 'pointer', fontSize: '12px' }}>»</button>
                    </div>
                )}
            </div>
            {custodyEntity && (
                <ChainOfCustodyModal entityId={custodyEntity} onClose={() => setCustodyEntity(null)} />
            )}
        </div>
    );
}
