// NBE Theme — Layering Stage Alerts
import { useDeferredValue, useEffect, useRef, useState } from 'react';
import Loader from '../components/common/Loader';
import { getLayeringAlerts, getLayeringRuns, getLayeringSummary } from '../services/transactionService';

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

const METHOD_LABELS = {
    peeling_chain: 'Peeling chains',
    mixing_interaction: 'Mixing & anonymity tool interaction',
    bridge_hopping: 'Cross-chain & bridge hopping',
    shell_wallet_network: 'Shell wallet networks',
    high_depth_transaction_chaining: 'High-depth transaction chaining',
};

const formatMethod = (value) => METHOD_LABELS[value] || (value || '').replaceAll('_', ' ');

const cardStyle = {
    background: 'linear-gradient(145deg, #101D32, #0D1628)',
    border: '1px solid rgba(201,168,76,0.12)',
    borderRadius: '14px',
    padding: '18px 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    minWidth: '160px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
};

const toneForMethod = (method) => {
    if (method === 'peeling_chain') return '#b91c1c';
    if (method === 'mixing_interaction') return '#92400e';
    if (method === 'bridge_hopping') return '#0369a1';
    if (method === 'shell_wallet_network') return '#166534';
    if (method === 'high_depth_transaction_chaining') return '#312e81';
    return '#334155';
};

const paletteForMethod = (method) => {
    if (method === 'peeling_chain') return { background: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)', color: '#F87171' };
    if (method === 'mixing_interaction') return { background: 'rgba(251,191,36,0.12)', border: 'rgba(251,191,36,0.3)', color: '#FBBF24' };
    if (method === 'bridge_hopping') return { background: 'rgba(96,165,250,0.12)', border: 'rgba(96,165,250,0.3)', color: '#60A5FA' };
    if (method === 'shell_wallet_network') return { background: 'rgba(74,222,128,0.10)', border: 'rgba(74,222,128,0.25)', color: '#4ADE80' };
    if (method === 'high_depth_transaction_chaining') return { background: 'rgba(167,139,250,0.12)', border: 'rgba(167,139,250,0.3)', color: '#A78BFA' };
    return { background: 'rgba(201,168,76,0.08)', border: 'rgba(201,168,76,0.25)', color: '#C9A84C' };
};

const getHighlightedMethods = (alert) => {
    const methodScores = alert.method_scores || {};
    const rankedMethods = Array.from(
        new Set([
            ...(alert.methods || []),
            ...Object.keys(methodScores),
        ]),
    )
        .filter(Boolean)
        .map((method) => ({
            method,
            score: Number(methodScores[method] || 0),
        }))
        .sort((left, right) => {
            if (right.score !== left.score) return right.score - left.score;
            return left.method.localeCompare(right.method);
        });

    if (rankedMethods.length <= 1) return rankedMethods;

    const primary = rankedMethods[0];
    const secondary = rankedMethods[1];
    const scale = primary.score > 1 ? 10 : 1;
    const hasStrongSecondary = secondary.score >= scale * 0.45 && secondary.score >= primary.score * 0.72;

    return hasStrongSecondary ? rankedMethods.slice(0, 2) : rankedMethods.slice(0, 1);
};

function ReasonPreview({ text, onExpand }) {
    const containerRef = useRef(null);
    const measureRef = useRef(null);
    const [preview, setPreview] = useState(text || '—');
    const [isTruncated, setIsTruncated] = useState(false);

    useEffect(() => {
        const container = containerRef.current;
        const measure = measureRef.current;
        const value = String(text || '').trim();

        if (!value) {
            setPreview('—');
            setIsTruncated(false);
            return undefined;
        }

        if (!container || !measure) {
            setPreview(value);
            setIsTruncated(false);
            return undefined;
        }

        const recalculate = () => {
            const width = container.clientWidth;
            if (!width) return;

            const computed = window.getComputedStyle(container);
            const fontSize = Number.parseFloat(computed.fontSize) || 14;
            const lineHeight = computed.lineHeight === 'normal'
                ? fontSize * 1.5
                : Number.parseFloat(computed.lineHeight) || fontSize * 1.5;
            const maxHeight = lineHeight * 2;

            measure.style.width = `${width}px`;
            measure.style.font = computed.font;
            measure.style.fontFamily = computed.fontFamily;
            measure.style.fontSize = computed.fontSize;
            measure.style.fontWeight = computed.fontWeight;
            measure.style.letterSpacing = computed.letterSpacing;
            measure.style.lineHeight = computed.lineHeight;
            measure.style.whiteSpace = 'normal';
            measure.style.wordBreak = 'break-word';
            measure.style.overflowWrap = 'anywhere';

            measure.textContent = value;
            if (measure.scrollHeight <= maxHeight + 1) {
                setPreview(value);
                setIsTruncated(false);
                return;
            }

            let low = 0;
            let high = value.length;
            let best = '';

            while (low <= high) {
                const mid = Math.floor((low + high) / 2);
                const candidate = value.slice(0, mid).trimEnd();
                measure.textContent = `${candidate}...`;

                if (measure.scrollHeight <= maxHeight + 1) {
                    best = candidate;
                    low = mid + 1;
                } else {
                    high = mid - 1;
                }
            }

            setPreview(best);
            setIsTruncated(true);
        };

        recalculate();

        if (typeof ResizeObserver === 'undefined') {
            window.addEventListener('resize', recalculate);
            return () => window.removeEventListener('resize', recalculate);
        }

        const observer = new ResizeObserver(() => recalculate());
        observer.observe(container);
        return () => observer.disconnect();
    }, [text]);

    return (
        <>
            <div
                ref={containerRef}
                style={{
                    color: '#C8B98A',
                    lineHeight: 1.5,
                    fontSize: '14px',
                    overflowWrap: 'anywhere',
                }}
            >
                {preview}
                {isTruncated ? (
                    <button
                        type="button"
                        onClick={onExpand}
                        aria-label="See full reason"
                        title="See full reason"
                        style={{
                            font: 'inherit',
                            color: '#0f6578',
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: 0,
                            textDecoration: 'underline',
                        }}
                    >
                        ...
                    </button>
                ) : null}
            </div>
            <div
                ref={measureRef}
                aria-hidden="true"
                style={{
                    position: 'fixed',
                    top: '-9999px',
                    left: '-9999px',
                    visibility: 'hidden',
                    pointerEvents: 'none',
                    zIndex: -1,
                }}
            />
        </>
    );
}

export default function Layering({ onNavigateToGraph }) {
    const [runs, setRuns] = useState([]);
    const [selectedRunId, setSelectedRunId] = useState(null);
    const [dateTimeInput, setDateTimeInput] = useState('');
    const [summary, setSummary] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [search, setSearch] = useState('');
    const [methodFilter, setMethodFilter] = useState('All');
    const [page, setPage] = useState(1);
    const PAGE_SIZE = 10;
    const [reasonPopup, setReasonPopup] = useState(null);
    const deferredSearch = useDeferredValue(search);

    useEffect(() => {
        getLayeringRuns()
            .then((data) => {
                setRuns(data || []);
                if (data && data.length > 0) {
                    setSelectedRunId(data[0].id);
                    if (data[0].completed_at) {
                        const dt = new Date(data[0].completed_at);
                        const pad = (n) => String(n).padStart(2, '0');
                        setDateTimeInput(`${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`);
                    }
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

    useEffect(() => {
        setPage(1);
    }, [deferredSearch, methodFilter, selectedRunId]);

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
        if (page > totalPages) {
            setPage(totalPages);
        }
    }, [page, totalPages]);

    if (loading) return <Loader />;
    if (error) return <div style={{ color: '#b33a3a', padding: '1rem' }}>Error: {error}</div>;

    const summaryBody = summary?.summary || {};

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{
                background: 'linear-gradient(135deg, #0D1628 0%, #132240 60%, #0F1E38 100%)',
                border: '1px solid rgba(201,168,76,0.12)',
                borderRadius: '16px',
                padding: '28px 32px',
                color: '#E2D9C8',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                gap: '16px',
                flexWrap: 'wrap',
                boxShadow: '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(201,168,76,0.08)',
            }}>
                <div>
                    <div style={{ fontSize: '24px', fontWeight: 700, color: '#C8B98A' }}>Layering Stage Alerts</div>
                    <div style={{ fontSize: '13px', color: '#8A9DB5', marginTop: '6px' }}>
                        Deterministic graph and flow heuristics triggered after placement-stage seeding.
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                </div>
            </div>

            <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
                <div style={cardStyle}>
                    <div style={{ fontSize: '12px', color: '#6B7E94', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Seeds</div>
                    <div style={{ fontSize: '26px', fontWeight: 700, color: '#E2D9C8' }}>{formatNumber(summaryBody.seeds_analyzed || 0, 0)}</div>
                    <div style={{ fontSize: '12px', color: '#6B7E94' }}>Placement seeds analyzed</div>
                </div>
                <div style={cardStyle}>
                    <div style={{ fontSize: '12px', color: '#6B7E94', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Alerts</div>
                    <div style={{ fontSize: '26px', fontWeight: 700, color: '#E2D9C8' }}>{formatNumber(summaryBody.alerts || 0, 0)}</div>
                    <div style={{ fontSize: '12px', color: '#6B7E94' }}>Final layering alerts</div>
                </div>
                <div style={cardStyle}>
                    <div style={{ fontSize: '12px', color: '#6B7E94', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Bridge Pairs</div>
                    <div style={{ fontSize: '26px', fontWeight: 700, color: '#E2D9C8' }}>{formatNumber(summaryBody.bridge_pairs || 0, 0)}</div>
                    <div style={{ fontSize: '12px', color: '#6B7E94' }}>Matched bridge hop records</div>
                </div>
            </div>

            <div style={{
                background: 'linear-gradient(145deg,#101D32,#0D1628)',
                border: '1px solid rgba(201,168,76,0.12)',
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
                    style={{ minWidth: '260px', flex: '1 1 260px', padding: '10px 12px', borderRadius: '10px', border: '1px solid rgba(201,168,76,0.15)', background: 'rgba(10,16,32,0.8)', color: '#E2D9C8', outline: 'none' }}
                />
                <select
                    value={methodFilter}
                    onChange={(e) => setMethodFilter(e.target.value)}
                    style={{ padding: '10px 12px', borderRadius: '10px', border: '1px solid rgba(201,168,76,0.15)', background: 'rgba(10,16,32,0.8)', color: '#E2D9C8', outline: 'none', cursor: 'pointer' }}
                >
                    <option value="All">All methods</option>
                    {allMethods.map((method) => (
                        <option key={method} value={method}>
                            {formatMethod(method)}
                        </option>
                    ))}
                </select>
                <div style={{ marginLeft: 'auto', fontSize: '12px', color: '#6B7E94' }}>
                    Showing {formatNumber(filteredAlerts.length, 0)} alerts
                </div>
            </div>

            {/* Date/time picker with available runs */}
            <div style={{ background: 'linear-gradient(145deg,#101D32,#0D1628)', border: '1px solid rgba(201,168,76,0.12)', borderRadius: '14px', padding: '14px 16px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div style={{ fontSize: '11px', fontWeight: '700', color: '#6B7E94', textTransform: 'uppercase', letterSpacing: '0.1em' }}>📅 Filter by Analysis Date</div>
                    <input
                        type="datetime-local"
                        value={dateTimeInput}
                        max={new Date().toISOString().slice(0, 16)}
                        onChange={(e) => {
                            const val = e.target.value;
                            setDateTimeInput(val);
                            if (!val || runs.length === 0) return;
                            const picked = new Date(val).getTime();
                            const candidates = runs.filter((r) => r.completed_at && new Date(r.completed_at).getTime() <= picked);
                            if (candidates.length > 0) {
                                setSelectedRunId(candidates[0].id);
                            } else {
                                setSelectedRunId(runs[runs.length - 1].id);
                            }
                        }}
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
                                const run = runs.find((r) => r.completed_at && new Date(r.completed_at).toISOString().slice(0, 16) === inputVal);
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

            <div style={{
                background: 'linear-gradient(145deg,#101D32,#0D1628)',
                border: '1px solid rgba(201,168,76,0.12)',
                borderRadius: '14px',
                overflow: 'hidden',
            }}>
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '12px 16px',
                    borderBottom: '1px solid rgba(201,168,76,0.10)',
                    background: 'rgba(255,255,255,0.02)',
                    flexWrap: 'wrap',
                }}>
                    <div style={{ fontSize: '12px', color: '#6B7E94' }}>
                        {formatNumber(filteredAlerts.length, 0)} alerts, page {page} of {totalPages}
                    </div>
                </div>
                <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '980px', background: 'transparent' }}>
                        <thead>
                            <tr style={{ background: 'rgba(201,168,76,0.04)', textAlign: 'left' }}>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid rgba(201,168,76,0.10)', fontSize: '12px', color: '#8A9DB5' }}>Entity</th>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid rgba(201,168,76,0.10)', fontSize: '12px', color: '#8A9DB5' }}>Methods</th>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid rgba(201,168,76,0.10)', fontSize: '12px', color: '#8A9DB5' }}>Placement Seed</th>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid rgba(201,168,76,0.10)', fontSize: '12px', color: '#8A9DB5' }}>Evidence</th>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid rgba(201,168,76,0.10)', fontSize: '12px', color: '#8A9DB5' }}>Reason</th>
                                <th style={{ padding: '14px 16px', borderBottom: '1px solid rgba(201,168,76,0.10)', fontSize: '12px', color: '#8A9DB5' }}>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredAlerts.length === 0 ? (
                                <tr>
                                    <td colSpan="6" style={{ padding: '28px 16px', textAlign: 'center', color: '#6B7E94' }}>
                                        No layering alerts match the current filters.
                                    </td>
                                </tr>
                            ) : visibleAlerts.map((alert) => (
                                <tr key={alert.entity_id}
                                    style={{ background: 'transparent' }}
                                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(201,168,76,0.04)'}
                                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                >
                                    <td style={{ padding: '16px', borderBottom: '1px solid rgba(201,168,76,0.10)', verticalAlign: 'top' }}>
                                        <div style={{ fontWeight: 700, color: alert.entity_name ? '#E2D9C8' : '#4B5E72', fontStyle: alert.entity_name ? 'normal' : 'italic', marginBottom: '2px' }}>
                                            {alert.entity_name || 'Unknown'}
                                        </div>
                                        <div style={{ fontSize: '11px', fontFamily: 'monospace', color: '#6B7E94' }}>{truncate(alert.entity_id, 22)}</div>
                                        <div style={{ fontSize: '12px', color: '#4B5E72', marginTop: '4px' }}>
                                            {alert.address_count} address{alert.address_count === 1 ? '' : 'es'}
                                        </div>
                                    </td>
                                    <td style={{ padding: '16px', borderBottom: '1px solid rgba(201,168,76,0.10)', verticalAlign: 'top' }}>
                                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                            {getHighlightedMethods(alert).map(({ method }, index) => {
                                                const palette = paletteForMethod(method);
                                                return (
                                                    <span
                                                        key={method}
                                                        style={{
                                                            padding: '4px 10px',
                                                            borderRadius: '999px',
                                                            background: palette.background,
                                                            color: palette.color,
                                                            border: `1px solid ${palette.border}`,
                                                            fontSize: '12px',
                                                            fontWeight: index === 0 ? 800 : 700,
                                                            opacity: index === 0 ? 1 : 0.5,
                                                        }}
                                                    >
                                                        {formatMethod(method)}
                                                    </span>
                                                );
                                            })}
                                        </div>
                                    </td>
                                    <td style={{ padding: '16px', borderBottom: '1px solid rgba(201,168,76,0.10)', color: '#E2D9C8' }}>
                                        <div>{formatNumber(alert.placement_score)}</div>
                                        <div style={{ fontSize: '12px', color: '#6B7E94', marginTop: '4px' }}>
                                            seed conf {formatNumber(alert.placement_confidence)}
                                        </div>
                                    </td>
                                    <td style={{ padding: '16px', borderBottom: '1px solid rgba(201,168,76,0.10)', color: '#E2D9C8' }}>
                                        <div>{formatNumber(alert.evidence_count || 0, 0)} evidence items</div>
                                        <div style={{ fontSize: '12px', color: '#6B7E94', marginTop: '4px' }}>
                                            {formatNumber((alert.supporting_tx_hashes || []).length, 0)} linked txs
                                        </div>
                                    </td>
                                    <td style={{ padding: '16px', borderBottom: '1px solid rgba(201,168,76,0.10)', maxWidth: '340px' }}>
                                        <ReasonPreview
                                            text={alert.reason}
                                            onExpand={() => setReasonPopup({ entityId: alert.entity_id, reason: alert.reason })}
                                        />
                                    </td>
                                    <td style={{ padding: '16px', borderBottom: '1px solid rgba(201,168,76,0.10)' }}>
                                        <button
                                            onClick={() => onNavigateToGraph((alert.addresses || [])[0] || alert.entity_id)}
                                            style={{
                                                padding: '8px 12px',
                                                borderRadius: '8px',
                                                border: '1px solid rgba(201,168,76,0.25)',
                                                background: 'rgba(201,168,76,0.08)',
                                                color: '#C9A84C',
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
                {totalPages > 1 ? (
                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', padding: '14px 20px', borderTop: '1px solid rgba(201,168,76,0.08)', background: 'rgba(255,255,255,0.02)', flexWrap: 'wrap' }}>
                        {[
                            { label: '« First', action: () => setPage(1), disabled: page === 1 },
                            { label: '‹ Prev', action: () => setPage((current) => Math.max(1, current - 1)), disabled: page === 1 },
                            null,
                            { label: 'Next ›', action: () => setPage((current) => Math.min(totalPages, current + 1)), disabled: page === totalPages },
                            { label: 'Last »', action: () => setPage(totalPages), disabled: page === totalPages },
                        ].map((button) => (
                            button === null ? (
                                <span key="counter" style={{ fontSize: '12px', color: '#6B7E94', minWidth: '90px', textAlign: 'center' }}>
                                    {page} / {totalPages}
                                </span>
                            ) : (
                                <button
                                    key={button.label}
                                    type="button"
                                    onClick={button.action}
                                    disabled={button.disabled}
                                    style={{
                                        padding: '6px 14px',
                                        borderRadius: '8px',
                                        border: '1px solid rgba(201,168,76,0.12)',
                                        background: button.disabled ? 'transparent' : 'rgba(201,168,76,0.06)',
                                        color: button.disabled ? '#4B5E72' : '#C9A84C',
                                        fontSize: '12px',
                                        fontWeight: '700',
                                        cursor: button.disabled ? 'not-allowed' : 'pointer',
                                    }}
                                >
                                    {button.label}
                                </button>
                            )
                        ))}
                    </div>
                ) : null}
            </div>

            {reasonPopup ? (
                <>
                    <div
                        style={{ position: 'fixed', inset: 0, background: 'rgba(15, 23, 42, 0.32)', zIndex: 999 }}
                        onClick={() => setReasonPopup(null)}
                    />
                    <div
                        style={{
                            position: 'fixed',
                            top: 0,
                            right: 0,
                            bottom: 0,
                            width: '420px',
                            maxWidth: '100%',
                            background: 'linear-gradient(145deg,#101D32,#0D1628)',
                            zIndex: 1000,
                            boxShadow: '-8px 0 32px rgba(0,0,0,0.15)',
                            display: 'flex',
                            flexDirection: 'column',
                        }}
                    >
                        <div style={{ padding: '20px 24px', borderBottom: '1px solid rgba(201,168,76,0.10)', background: 'linear-gradient(135deg,#0D1628,#132240)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                                <div>
                                    <div style={{ fontSize: '11px', fontWeight: 800, color: '#C9A84C', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>
                                        Layering Reason
                                    </div>
                                    <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#E2D9C8', wordBreak: 'break-all' }}>
                                        {reasonPopup.entityId}
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => setReasonPopup(null)}
                                    style={{ border: '1px solid rgba(201,168,76,0.12)', background: 'rgba(201,168,76,0.06)', borderRadius: '8px', padding: '4px 10px', cursor: 'pointer', fontSize: '14px', color: '#C9A84C', flexShrink: 0 }}
                                >
                                    ✕
                                </button>
                            </div>
                        </div>
                        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
                            <div style={{ padding: '14px 16px', borderRadius: '12px', background: 'rgba(201,168,76,0.04)', border: '1px solid rgba(201,168,76,0.12)', color: '#E2D9C8', lineHeight: 1.7 }}>
                                {reasonPopup.reason}
                            </div>
                        </div>
                    </div>
                </>
            ) : null}
        </div>
    );
}
