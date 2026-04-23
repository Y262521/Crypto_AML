import { useDeferredValue, useEffect, useState } from 'react';
import Loader from '../components/common/Loader';
import { getLayeringAlerts, getLayeringRuns, getLayeringSummary, getLayeringDetail } from '../services/transactionService';

const formatNumber = (value, maximumFractionDigits = 2) => {
    const parsed = Number(value || 0);
    if (!Number.isFinite(parsed)) return '0';
    return parsed.toLocaleString(undefined, { maximumFractionDigits });
};

const truncate = (value, maxLength = 18) => {
    if (!value) return '—';
    if (value.length <= maxLength) return value;
    return `${value.slice(0, maxLength - 3)}...`;
};

const formatMethod = (value) => (value || '').replaceAll('_', ' ');

const displayDetectorScore = (v) => {
    if (v === null || v === undefined) return '0';
    const num = Number(v);
    if (!Number.isFinite(num)) return String(v);
    if (num <= 1) return `${Math.round(num * 100)}%`;
    return String(num);
};

const humanizeLayeringReason = (reasons = [], primaryMethod = '') => {
    if (!reasons || reasons.length === 0) {
        if (primaryMethod) return `Flagged by ${formatMethod(primaryMethod)} detector.`;
        return 'Flagged by layering detection heuristics.';
    }
    const map = {
        'repeated_shaved_transfers': 'Repeated small transfers that appear to shave funds across many addresses.',
        'mixing_interaction': 'Interaction with mixing services or anonymity tools.',
        'bridge_hopping': 'Funds routed through bridge contracts to obscure origin.',
        'shell_wallet_network': 'Clustered shell wallets exhibiting rapid forwarding behavior.',
        'high_depth_transaction_chaining': 'Long forwarding chains indicating deep transaction hops.',
    };
    const readable = reasons.map((r) => {
        const key = Object.keys(map).find((k) => r?.toLowerCase().includes(k.toLowerCase()));
        return key ? map[key] : null;
    }).filter(Boolean);
    if (readable.length > 0) return readable[0];
    return reasons[0]?.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase()) || 'Flagged by layering detection heuristics.';
};

const cardStyle = {
    background: '#ffffff',
    border: '1px solid #e2e8f0',
    borderRadius: '14px',
    padding: '18px 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    minWidth: '160px',
};

const toneForMethod = (method) => {
    if (method === 'peeling_chain') return '#b91c1c';
    if (method === 'mixing_interaction') return '#92400e';
    if (method === 'bridge_hopping') return '#0369a1';
    if (method === 'shell_wallet_network') return '#166534';
    if (method === 'high_depth_transaction_chaining') return '#312e81';
    return '#334155';
};

export default function Layering({ onNavigateToGraph }) {
    const [runs, setRuns] = useState([]);
    const [selectedRunId, setSelectedRunId] = useState(null);
    const [summary, setSummary] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [search, setSearch] = useState('');
    const [methodFilter, setMethodFilter] = useState('All');
    const [page, setPage] = useState(1);
    const PAGE_SIZE = 10;
    const [detectionsMap, setDetectionsMap] = useState({});

    const deferredSearch = useDeferredValue(search);

    useEffect(() => { setPage(1); }, [deferredSearch, methodFilter]);

    useEffect(() => {
        getLayeringRuns()
            .then((data) => {
                setRuns(data || []);
                if (data && data.length > 0) {
                    setSelectedRunId(data[0].id);
                }
            })
            .catch((err) => setError(err.message));
    }, []);

    useEffect(() => {
        setLoading(true);
        setError(null);
        Promise.all([
            getLayeringSummary(selectedRunId || undefined),
            getLayeringAlerts({
                runId: selectedRunId || undefined,
            }),
        ])
            .then(([summaryResponse, alertsResponse]) => {
                setSummary(summaryResponse);
                setAlerts(alertsResponse.items || []);
            })
            .catch((err) => setError(err.message))
            .finally(() => setLoading(false));
    }, [selectedRunId]);

    const allMethods = Array.from(new Set(alerts.flatMap((alert) => alert.methods || []))).sort();
    const filteredAlerts = alerts.filter((alert) => {
        const query = deferredSearch.trim().toLowerCase();
        const matchSearch = !query
            || alert.entity_id?.toLowerCase().includes(query)
            || (alert.addresses || []).some((address) => address?.toLowerCase().includes(query));
        const matchMethod = methodFilter === 'All' || (alert.methods || []).includes(methodFilter);
        return matchSearch && matchMethod;
    });

    const totalPages = Math.max(1, Math.ceil(filteredAlerts.length / PAGE_SIZE));
    const visibleAlerts = filteredAlerts.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

    useEffect(() => {
        let mounted = true;
        const ids = visibleAlerts.map(a => a.entity_id).filter(Boolean);
        if (ids.length === 0) {
            setDetectionsMap({});
            return;
        }
        Promise.all(ids.map(id => getLayeringDetail(id, selectedRunId)
            .then(r => ({ id, detections: r.detections || [] }))
            .catch(() => ({ id, detections: [] }))
        ))
            .then((results) => {
                if (!mounted) return;
                const map = {};
                results.forEach((item) => { map[item.id] = item.detections || []; });
                setDetectionsMap(map);
            });
        return () => { mounted = false; };
    }, [visibleAlerts, selectedRunId]);

    if (loading) return <Loader />;
    if (error) return <div style={{ color: '#b33a3a', padding: '1rem' }}>Error: {error}</div>;

    const summaryBody = summary?.summary || {};

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{
                background: '#0f172a',
                borderRadius: '16px',
                padding: '28px 32px',
                color: '#ffffff',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                gap: '16px',
                flexWrap: 'wrap',
            }}>
                <div>
                    <div style={{ fontSize: '24px', fontWeight: 700 }}>Layering Stage Alerts</div>
                    <div style={{ fontSize: '13px', color: '#cbd5e1', marginTop: '6px' }}>
                        Deterministic graph and flow heuristics triggered after placement-stage seeding.
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    <select
                        value={selectedRunId || ''}
                        onChange={(e) => setSelectedRunId(e.target.value || null)}
                        style={{ padding: '10px 12px', borderRadius: '10px', border: '1px solid #334155', background: '#0b1220', color: '#fff' }}
                    >
                        {runs.length === 0 ? <option value="">No runs</option> : null}
                        {runs.map((run) => (
                            <option key={run.id} value={run.id}>
                                {run.id}
                            </option>
                        ))}
                    </select>

                </div>
            </div>

            <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
                <div style={cardStyle}>
                    <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Seeds</div>
                    <div style={{ fontSize: '26px', fontWeight: 700, color: '#0f172a' }}>{formatNumber(summaryBody.seeds_analyzed || 0, 0)}</div>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>Placement seeds analyzed</div>
                </div>
                <div style={cardStyle}>
                    <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Alerts</div>
                    <div style={{ fontSize: '26px', fontWeight: 700, color: '#0f172a' }}>{formatNumber(summaryBody.alerts || 0, 0)}</div>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>Final layering alerts</div>
                </div>
                <div style={cardStyle}>
                    <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Bridge Pairs</div>
                    <div style={{ fontSize: '26px', fontWeight: 700, color: '#0f172a' }}>{formatNumber(summaryBody.bridge_pairs || 0, 0)}</div>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>Matched bridge hop records</div>
                </div>
                <div style={cardStyle}>
                    <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Avg Confidence</div>
                    <div style={{ fontSize: '26px', fontWeight: 700, color: '#0f172a' }}>{formatNumber(summaryBody.average_alert_confidence || 0)}</div>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>Across final alerts</div>
                </div>
            </div>

            <div style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '14px',
                padding: '18px 20px',
                display: 'flex',
                gap: '12px',
                flexWrap: 'wrap',
                alignItems: 'center',
            }}>
                <input
                    type="text"
                    placeholder="Search entity or address"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    style={{ minWidth: '260px', flex: '1 1 260px', padding: '10px 12px', borderRadius: '10px', border: '1px solid #cbd5e1' }}
                />
                <select
                    value={methodFilter}
                    onChange={(e) => setMethodFilter(e.target.value)}
                    style={{ padding: '10px 12px', borderRadius: '10px', border: '1px solid #cbd5e1' }}
                >
                    <option value="All">All methods</option>
                    {allMethods.map((method) => (
                        <option key={method} value={method}>
                            {formatMethod(method)}
                        </option>
                    ))}
                </select>
                <div style={{ marginLeft: 'auto', fontSize: '12px', color: '#64748b' }}>
                    Showing {formatNumber(filteredAlerts.length, 0)} alerts
                </div>
            </div>

            <div style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '14px',
                overflow: 'hidden',
            }}>
                <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '1040px' }}>
                        <thead>
                            <tr style={{ background: '#f8fafc', textAlign: 'left' }}>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#475569' }}>Entity</th>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#475569' }}>Methods</th>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#475569' }}>Detectors</th>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#475569' }}>Confidence</th>

                                <th style={{ padding: '14px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#475569' }}>Placement Seed</th>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#475569' }}>Evidence</th>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#475569' }}>Reason</th>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#475569' }}>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredAlerts.length === 0 ? (
                                <tr>
                                    <td colSpan="9" style={{ padding: '28px 16px', textAlign: 'center', color: '#64748b' }}>
                                        No layering alerts match the current filters.
                                    </td>
                                </tr>
                            ) : visibleAlerts.map((alert) => (
                                <tr key={alert.entity_id}>
                                    <td style={{ padding: '16px', borderBottom: '1px solid #e2e8f0', verticalAlign: 'top' }}>
                                        <div style={{ fontWeight: 600, color: '#0f172a' }}>{truncate(alert.entity_id, 22)}</div>
                                        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                                            {alert.address_count} address{alert.address_count === 1 ? '' : 'es'}
                                        </div>
                                    </td>
                                    <td style={{ padding: '16px', borderBottom: '1px solid #e2e8f0', verticalAlign: 'top' }}>
                                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                            {(alert.methods || []).map((method) => (
                                                <span
                                                    key={method}
                                                    style={{
                                                        padding: '4px 8px',
                                                        borderRadius: '999px',
                                                        background: '#eff6ff',
                                                        color: toneForMethod(method),
                                                        fontSize: '12px',
                                                        fontWeight: 600,
                                                    }}
                                                >
                                                    {formatMethod(method)}
                                                </span>
                                            ))}
                                        </div>
                                    </td>

                                    <td style={{ padding: '16px', borderBottom: '1px solid #e2e8f0', verticalAlign: 'top', minWidth: '140px' }}>
                                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                            {(detectionsMap[alert.entity_id] || []).map((d, i) => (
                                                <span key={`${d.detector_type}-${i}`} style={{ padding: '4px 8px', borderRadius: '999px', background: '#f8fafc', color: toneForMethod(d.detector_type), fontSize: '11px', fontWeight: 700 }}>
                                                    {formatMethod(d.detector_type)} {displayDetectorScore(d.confidence_score)}
                                                </span>
                                            ))}
                                            {!(detectionsMap[alert.entity_id] || []).length && (
                                                <span style={{ fontSize: '11px', color: '#94a3b8' }}>no detections</span>
                                            )}
                                        </div>
                                    </td>

                                    <td style={{ padding: '16px', borderBottom: '1px solid #e2e8f0', fontWeight: 600 }}>
                                        {formatNumber(alert.confidence)}
                                    </td>

                                    <td style={{ padding: '16px', borderBottom: '1px solid #e2e8f0' }}>
                                        <div>{formatNumber(alert.placement_score)}</div>
                                        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                                            seed conf {formatNumber(alert.placement_confidence)}
                                        </div>
                                    </td>
                                    <td style={{ padding: '16px', borderBottom: '1px solid #e2e8f0' }}>
                                        <div>{formatNumber(alert.evidence_count || 0, 0)} evidence items</div>
                                        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                                            {formatNumber((alert.supporting_tx_hashes || []).length, 0)} linked txs
                                        </div>
                                    </td>
                                    <td style={{ padding: '16px', borderBottom: '1px solid #e2e8f0', maxWidth: '300px', color: '#334155' }}>
                                        {(humanizeLayeringReason(alert.reasons, alert.primary_method) || '—')}
                                    </td>
                                    <td style={{ padding: '16px', borderBottom: '1px solid #e2e8f0' }}>
                                        <button
                                            onClick={() => onNavigateToGraph((alert.addresses || [])[0] || alert.entity_id)}
                                            style={{
                                                padding: '8px 12px',
                                                borderRadius: '8px',
                                                border: '1px solid #1d4ed8',
                                                background: '#eff6ff',
                                                color: '#1d4ed8',
                                                cursor: 'pointer',
                                                fontWeight: 600,
                                            }}
                                        >
                                            Investigate
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {totalPages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', padding: '14px 20px', borderTop: '1px solid #f1f5f9', background: '#fafbfc' }}>
                    {[
                        { label: '«', action: () => setPage(1), disabled: page === 1 },
                        { label: '‹ Back', action: () => setPage(p => Math.max(1, p - 1)), disabled: page === 1 },
                        null,
                        { label: 'Next ›', action: () => setPage(p => Math.min(totalPages, p + 1)), disabled: page === totalPages },
                        { label: '»', action: () => setPage(totalPages), disabled: page === totalPages },
                    ].map((btn) =>
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
    );
}
