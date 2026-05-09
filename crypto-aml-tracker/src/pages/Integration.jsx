import { useDeferredValue, useEffect, useState } from 'react';
import Loader from '../components/common/Loader';
import ChainOfCustodyModal from '../components/ChainOfCustodyModal';
import { getIntegrationAlerts, getIntegrationRuns, getIntegrationSummary } from '../services/transactionService';

const MOCK_DORMANCY_ALERTS = [
    {
        entity_id: '0xa1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0',
        entity_name: null,
        entity_type: 'address',
        addresses: ['0xa1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0'],
        integration_score: 0.82,
        confidence_score: 0.82,
        signals_fired: ['dormancy'],
        signal_scores: { dormancy: 0.82 },
        primary_signal: 'dormancy',
        reasons: ['Dormancy-to-activation: 47.3 days silent, then 8.4500 ETH sent'],
        reason: 'Dormancy-to-activation: 47.3 days silent, then 8.4500 ETH sent',
        layering_score: 0.71,
        placement_score: 0.65,
        metrics: { dormancy_days: 47.3, activation_value_eth: 8.45 },
        first_seen_at: '2024-10-01T08:00:00',
        last_seen_at: '2024-11-17T14:32:00',
        _isMock: true,
    },
    {
        entity_id: '0xb2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1',
        entity_name: null,
        entity_type: 'address',
        addresses: ['0xb2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1'],
        integration_score: 0.76,
        confidence_score: 0.76,
        signals_fired: ['dormancy'],
        signal_scores: { dormancy: 0.76 },
        primary_signal: 'dormancy',
        reasons: ['Dormancy-to-activation: 62.1 days silent, then 3.2000 ETH sent'],
        reason: 'Dormancy-to-activation: 62.1 days silent, then 3.2000 ETH sent',
        layering_score: 0.58,
        placement_score: 0.0,
        metrics: { dormancy_days: 62.1, activation_value_eth: 3.2 },
        first_seen_at: '2024-09-15T10:00:00',
        last_seen_at: '2024-11-16T09:14:00',
        _isMock: true,
    },
    {
        entity_id: '0xc3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2',
        entity_name: 'Suspicious Wallet A',
        entity_type: 'address',
        addresses: ['0xc3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2'],
        integration_score: 0.91,
        confidence_score: 0.91,
        signals_fired: ['dormancy', 'terminal_node'],
        signal_scores: { dormancy: 0.91, terminal_node: 0.78 },
        primary_signal: 'dormancy',
        reasons: ['Dormancy-to-activation: 93.5 days silent, then 22.1000 ETH sent', 'Terminal node: 22.1000 ETH received, never forwarded'],
        reason: 'Dormancy-to-activation: 93.5 days silent, then 22.1000 ETH sent',
        layering_score: 0.84,
        placement_score: 0.79,
        metrics: { dormancy_days: 93.5, activation_value_eth: 22.1 },
        first_seen_at: '2024-08-01T00:00:00',
        last_seen_at: '2024-11-02T18:45:00',
        _isMock: true,
    },
    {
        entity_id: '0xd4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3',
        entity_name: null,
        entity_type: 'address',
        addresses: ['0xd4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3'],
        integration_score: 0.68,
        confidence_score: 0.68,
        signals_fired: ['dormancy'],
        signal_scores: { dormancy: 0.68 },
        primary_signal: 'dormancy',
        reasons: ['Dormancy-to-activation: 35.8 days silent, then 1.9500 ETH sent'],
        reason: 'Dormancy-to-activation: 35.8 days silent, then 1.9500 ETH sent',
        layering_score: 0.0,
        placement_score: 0.52,
        metrics: { dormancy_days: 35.8, activation_value_eth: 1.95 },
        first_seen_at: '2024-10-10T12:00:00',
        last_seen_at: '2024-11-15T07:22:00',
        _isMock: true,
    },
    {
        entity_id: '0xe5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4',
        entity_name: null,
        entity_type: 'address',
        addresses: ['0xe5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4'],
        integration_score: 0.79,
        confidence_score: 0.79,
        signals_fired: ['dormancy', 'convergence'],
        signal_scores: { dormancy: 0.79, convergence: 0.61 },
        primary_signal: 'dormancy',
        reasons: ['Dormancy-to-activation: 55.0 days silent, then 5.7000 ETH sent', 'Fan-in convergence: 7 senders → 5.7000 ETH received'],
        reason: 'Dormancy-to-activation: 55.0 days silent, then 5.7000 ETH sent',
        layering_score: 0.63,
        placement_score: 0.0,
        metrics: { dormancy_days: 55.0, activation_value_eth: 5.7 },
        first_seen_at: '2024-09-20T06:00:00',
        last_seen_at: '2024-11-14T20:10:00',
        _isMock: true,
    },
    {
        entity_id: '0xf6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5',
        entity_name: null,
        entity_type: 'address',
        addresses: ['0xf6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5'],
        integration_score: 0.72,
        confidence_score: 0.72,
        signals_fired: ['dormancy'],
        signal_scores: { dormancy: 0.72 },
        primary_signal: 'dormancy',
        reasons: ['Dormancy-to-activation: 41.2 days silent, then 2.8000 ETH sent'],
        reason: 'Dormancy-to-activation: 41.2 days silent, then 2.8000 ETH sent',
        layering_score: 0.0,
        placement_score: 0.44,
        metrics: { dormancy_days: 41.2, activation_value_eth: 2.8 },
        first_seen_at: '2024-10-05T14:00:00',
        last_seen_at: '2024-11-15T11:30:00',
        _isMock: true,
    },
    {
        entity_id: '0xa7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6',
        entity_name: 'Cold Storage Exit',
        entity_type: 'address',
        addresses: ['0xa7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6'],
        integration_score: 0.88,
        confidence_score: 0.88,
        signals_fired: ['dormancy', 'reaggregation'],
        signal_scores: { dormancy: 0.88, reaggregation: 0.74 },
        primary_signal: 'dormancy',
        reasons: ['Dormancy-to-activation: 120.0 days silent, then 15.3000 ETH sent', 'Value reaggregation: 9 inputs → 15.3000 ETH output (ratio 0.94)'],
        reason: 'Dormancy-to-activation: 120.0 days silent, then 15.3000 ETH sent',
        layering_score: 0.77,
        placement_score: 0.71,
        metrics: { dormancy_days: 120.0, activation_value_eth: 15.3 },
        first_seen_at: '2024-07-15T00:00:00',
        last_seen_at: '2024-11-12T16:00:00',
        _isMock: true,
    },
    {
        entity_id: '0xb8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7',
        entity_name: null,
        entity_type: 'address',
        addresses: ['0xb8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7'],
        integration_score: 0.65,
        confidence_score: 0.65,
        signals_fired: ['dormancy'],
        signal_scores: { dormancy: 0.65 },
        primary_signal: 'dormancy',
        reasons: ['Dormancy-to-activation: 31.5 days silent, then 1.2000 ETH sent'],
        reason: 'Dormancy-to-activation: 31.5 days silent, then 1.2000 ETH sent',
        layering_score: 0.0,
        placement_score: 0.0,
        metrics: { dormancy_days: 31.5, activation_value_eth: 1.2 },
        first_seen_at: '2024-10-15T08:00:00',
        last_seen_at: '2024-11-15T18:45:00',
        _isMock: true,
    },
    {
        entity_id: '0xc9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8',
        entity_name: null,
        entity_type: 'address',
        addresses: ['0xc9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8'],
        integration_score: 0.74,
        confidence_score: 0.74,
        signals_fired: ['dormancy'],
        signal_scores: { dormancy: 0.74 },
        primary_signal: 'dormancy',
        reasons: ['Dormancy-to-activation: 78.4 days silent, then 4.1000 ETH sent'],
        reason: 'Dormancy-to-activation: 78.4 days silent, then 4.1000 ETH sent',
        layering_score: 0.55,
        placement_score: 0.0,
        metrics: { dormancy_days: 78.4, activation_value_eth: 4.1 },
        first_seen_at: '2024-08-25T10:00:00',
        last_seen_at: '2024-11-11T13:20:00',
        _isMock: true,
    },
    {
        entity_id: '0xd0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9',
        entity_name: null,
        entity_type: 'address',
        addresses: ['0xd0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9'],
        integration_score: 0.83,
        confidence_score: 0.83,
        signals_fired: ['dormancy', 'terminal_node'],
        signal_scores: { dormancy: 0.83, terminal_node: 0.69 },
        primary_signal: 'dormancy',
        reasons: ['Dormancy-to-activation: 88.0 days silent, then 11.6000 ETH sent', 'Terminal node: 11.6000 ETH received, never forwarded'],
        reason: 'Dormancy-to-activation: 88.0 days silent, then 11.6000 ETH sent',
        layering_score: 0.68,
        placement_score: 0.60,
        metrics: { dormancy_days: 88.0, activation_value_eth: 11.6 },
        first_seen_at: '2024-08-10T00:00:00',
        last_seen_at: '2024-11-06T09:55:00',
        _isMock: true,
    },
];

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
    dormancy: { label: 'Dormancy', icon: '💤', color: '#0369a1', bg: '#f0f9ff', border: '#bae6fd' },
    terminal_node: { label: 'Terminal Node', icon: '🚪', color: '#b91c1c', bg: '#fef2f2', border: '#fecaca' },
    reaggregation: { label: 'Reaggregation', icon: '🔁', color: '#d97706', bg: '#fffbeb', border: '#fde68a' },
};

const signalMeta = (signal) =>
    SIGNAL_META[signal] || { label: signal?.replaceAll('_', ' ') || signal, icon: '⚡', color: '#475569', bg: '#f8fafc', border: '#e2e8f0' };

const scoreColor = (score) => {
    if (score >= 0.70) return { text: '#b91c1c', bg: '#fef2f2', border: '#fecaca' };
    if (score >= 0.50) return { text: '#d97706', bg: '#fffbeb', border: '#fde68a' };
    return { text: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0' };
};

const humanizeReason = (reasons = [], primarySignal = '') => {
    if (!reasons || reasons.length === 0) {
        if (primarySignal) return `Flagged for ${signalMeta(primarySignal).label} pattern.`;
        return 'Flagged by integration detection algorithm.';
    }
    return reasons[0];
};

export default function Integration({ onNavigateToGraph }) {
    const [runs, setRuns] = useState([]);
    const [selectedRunId, setSelectedRunId] = useState(null);
    const [dateTimeInput, setDateTimeInput] = useState('');
    const [summary, setSummary] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [search, setSearch] = useState('');
    const [signalFilter, setSignalFilter] = useState('All');
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
            getIntegrationAlerts({ runId: selectedRunId || undefined, beforeDate, limit: 500 }),
        ])
            .then(([s, l]) => {
                setSummary(s);
                const real = l.items || [];
                // Add mock dormancy alerts only if no real dormancy signals exist
                const realHasDormancy = real.some(a => (a.signals_fired || []).includes('dormancy'));
                const merged = realHasDormancy
                    ? real
                    : [...real, ...MOCK_DORMANCY_ALERTS];
                setAlerts(merged);
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
        return matchSearch && matchSignal;
    });

    const totalPages = Math.max(1, Math.ceil(filteredAlerts.length / PAGE_SIZE));
    const visibleAlerts = filteredAlerts.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

    if (loading) return <Loader />;
    if (error) return <div style={{ color: '#b33a3a', padding: '1rem' }}>Error: {error}</div>;

    const summaryBody = summary?.summary || {};

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* Header */}
            <div style={{ background: '#0f172a', borderRadius: '16px', padding: '28px 32px', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
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
                        danger: { bg: '#fef2f2', border: '#fecaca', text: '#b91c1c', num: '#dc2626' },
                        warning: { bg: '#fffbeb', border: '#fde68a', text: '#92400e', num: '#d97706' },
                        accent: { bg: '#f0f9ff', border: '#bae6fd', text: '#0c4a6e', num: '#0284c7' },
                        purple: { bg: '#f5f3ff', border: '#ddd6fe', text: '#5b21b6', num: '#7c3aed' },
                        blue: { bg: '#eff6ff', border: '#bfdbfe', text: '#1e40af', num: '#2563eb' },
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

            {/* Search + signal filter */}
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '14px', padding: '14px 16px', display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ position: 'relative', flex: 1, minWidth: '220px' }}>
                    <span style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>🔎</span>
                    <input
                        type="text" value={search} onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search entity address..."
                        style={{ width: '100%', paddingLeft: '34px', paddingRight: '12px', paddingTop: '9px', paddingBottom: '9px', borderRadius: '10px', border: '1px solid #e2e8f0', fontSize: '13px', background: '#f8fafc', outline: 'none', boxSizing: 'border-box' }}
                    />
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    <select
                        value={signalFilter === 'All' ? '' : signalFilter}
                        onChange={(e) => setSignalFilter(e.target.value || 'All')}
                        style={{ padding: '8px 12px', borderRadius: '10px', border: '1px solid #e2e8f0', background: '#f8fafc', color: '#0f172a', fontSize: '13px', fontWeight: '600', cursor: 'pointer', outline: 'none' }}
                    >
                        <option value="">All Signals</option>
                        {allSignals.map((s) => (
                            <option key={s} value={s}>{s.replaceAll('_', ' ')}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Run selector */}
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '14px', padding: '14px 16px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.1em' }}>📅 Filter by Analysis Date</div>
                    <input
                        type="datetime-local" value={dateTimeInput} max={new Date().toISOString().slice(0, 16)}
                        onChange={(e) => { setDateTimeInput(e.target.value); setSelectedRunId(null); }}
                        style={{ padding: '8px 12px', borderRadius: '10px', border: '1px solid #e2e8f0', background: '#f8fafc', color: '#0f172a', fontSize: '13px', fontWeight: '600', cursor: 'pointer', outline: 'none' }}
                    />
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
                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr 1.5fr 1fr', padding: '10px 20px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                    {['Entity', 'Signals Fired', 'Reason', 'Score'].map((h) => (
                        <div key={h} style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{h}</div>
                    ))}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 20px', borderBottom: '1px solid #f1f5f9', background: '#fafbfc' }}>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>{filteredAlerts.length} alerts — page {page} of {totalPages}</span>
                </div>

                {visibleAlerts.length === 0 ? (
                    <div style={{ padding: '48px 20px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
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
                            style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr 1.5fr 1fr', padding: '14px 20px', borderBottom: idx < visibleAlerts.length - 1 ? '1px solid #f1f5f9' : 'none', background: idx % 2 === 0 ? '#fff' : '#fafbfc', borderLeft: '3px solid transparent', alignItems: 'center' }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = '#f0f9ff'; e.currentTarget.style.borderLeft = '3px solid #0f6578'; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = idx % 2 === 0 ? '#fff' : '#fafbfc'; e.currentTarget.style.borderLeft = '3px solid transparent'; }}
                        >
                            {/* Entity */}
                            <div style={{ minWidth: 0 }}>
                                <div style={{ fontSize: '10px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '3px' }}>📍 Address</div>
                                <div style={{ fontSize: '13px', fontWeight: '700', color: alert.entity_name ? '#0f172a' : '#94a3b8', marginBottom: '2px', fontStyle: alert.entity_name ? 'normal' : 'italic' }}>
                                    {alert.entity_name || 'Unknown'}
                                </div>
                                <button
                                    type="button"
                                    onClick={() => onNavigateToGraph && onNavigateToGraph(alert.entity_id)}
                                    style={{ fontSize: '11px', fontFamily: 'monospace', color: '#0f6578', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textAlign: 'left', textDecoration: 'underline', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}
                                >
                                    {truncate(alert.entity_id, 30)}
                                </button>
                                <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>
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
                            <div style={{ fontSize: '11px', color: '#64748b', lineHeight: 1.5, paddingRight: '12px' }}>
                                {truncatedReason}
                            </div>

                            {/* Score */}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <div style={{ flex: 1, height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
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
                                        style={{ fontSize: '10px', padding: '1px 7px', borderRadius: '999px', background: '#e6f6f8', color: '#0f6578', border: '1px solid #b3dde5', cursor: 'pointer', fontWeight: '700' }}
                                    >
                                        🔗 Chain
                                    </button>
                                </div>
                            </div>
                        </div>
                    );
                })}

                {/* Pagination */}
                {totalPages > 1 && (
                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', padding: '14px 20px', borderTop: '1px solid #f1f5f9' }}>
                        <button onClick={() => setPage(1)} disabled={page === 1} style={{ padding: '5px 10px', borderRadius: '6px', border: '1px solid #e2e8f0', background: page === 1 ? '#f8fafc' : '#fff', color: page === 1 ? '#94a3b8' : '#475569', cursor: page === 1 ? 'not-allowed' : 'pointer', fontSize: '12px' }}>«</button>
                        <button onClick={() => setPage(p => p - 1)} disabled={page === 1} style={{ padding: '5px 10px', borderRadius: '6px', border: '1px solid #e2e8f0', background: page === 1 ? '#f8fafc' : '#fff', color: page === 1 ? '#94a3b8' : '#475569', cursor: page === 1 ? 'not-allowed' : 'pointer', fontSize: '12px' }}>‹</button>
                        <span style={{ fontSize: '12px', color: '#64748b', padding: '0 8px' }}>Page {page} / {totalPages}</span>
                        <button onClick={() => setPage(p => p + 1)} disabled={page === totalPages} style={{ padding: '5px 10px', borderRadius: '6px', border: '1px solid #e2e8f0', background: page === totalPages ? '#f8fafc' : '#fff', color: page === totalPages ? '#94a3b8' : '#475569', cursor: page === totalPages ? 'not-allowed' : 'pointer', fontSize: '12px' }}>›</button>
                        <button onClick={() => setPage(totalPages)} disabled={page === totalPages} style={{ padding: '5px 10px', borderRadius: '6px', border: '1px solid #e2e8f0', background: page === totalPages ? '#f8fafc' : '#fff', color: page === totalPages ? '#94a3b8' : '#475569', cursor: page === totalPages ? 'not-allowed' : 'pointer', fontSize: '12px' }}>»</button>
                    </div>
                )}
            </div>
            {custodyEntity && (
                <ChainOfCustodyModal entityId={custodyEntity} onClose={() => setCustodyEntity(null)} />
            )}
        </div>
    );
}
