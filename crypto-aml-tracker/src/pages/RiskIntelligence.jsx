/**
 * Risk Intelligence Page
 * Interactive multi-factor risk analysis with simulation (safe mode).
 */
import { useEffect, useState } from 'react';
import Loader from '../components/common/Loader';

const API = 'http://localhost:4000/api/risk';

const riskColor = (score) => {
    const s = parseFloat(score) || 0;
    if (s >= 0.8) return '#dc2626';
    if (s >= 0.6) return '#d97706';
    if (s >= 0.4) return '#f59e0b';
    if (s >= 0.2) return '#16a34a';
    return '#94a3b8';
};

const riskLabel = (score) => {
    const s = parseFloat(score) || 0;
    if (s >= 0.8) return 'CRITICAL';
    if (s >= 0.6) return 'HIGH';
    if (s >= 0.4) return 'MEDIUM';
    if (s >= 0.2) return 'LOW';
    return 'MINIMAL';
};

const FACTOR_LABELS = {
    label:       'Label Risk',
    behavior:    'Behavioral Risk',
    propagation: 'Propagation Risk',
    temporal:    'Temporal Risk',
    exposure:    'Exposure Risk',
};

const FACTOR_COLORS = {
    label:       '#dc2626',
    behavior:    '#d97706',
    propagation: '#7c3aed',
    temporal:    '#0891b2',
    exposure:    '#059669',
};

const LABEL_OPTIONS = ['sanctioned', 'scam', 'mixer', 'darknet', 'ransomware', 'hack', 'high_risk', 'watchlist'];
const BEHAVIOR_OPTIONS = ['loop_detection', 'coordinated_cashout', 'peeling_chain', 'smurfing', 'bridge_hopping', 'mixing_interaction'];

const th = {
    textAlign: 'left', padding: '10px 14px',
    borderBottom: '2px solid #e2e8f0',
    color: '#475569', fontSize: '11px', fontWeight: '600',
    textTransform: 'uppercase', background: '#f1f5f9',
};
const td = { padding: '10px 14px', borderBottom: '1px solid #f1f5f9', fontSize: '12px', color: '#334155' };

// ── Simple bar chart (no recharts) ────────────────────────────────────────────
function BreakdownBars({ breakdown, simBreakdown }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {Object.entries(FACTOR_LABELS).map(([key, label]) => {
                const val = Math.round((breakdown?.[key] || 0) * 100);
                const sim = simBreakdown ? Math.round((simBreakdown[key] || 0) * 100) : null;
                const color = FACTOR_COLORS[key];
                return (
                    <div key={key}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <span style={{ fontSize: '11px', color: '#475569', fontWeight: '600' }}>{label}</span>
                            <span style={{ fontSize: '11px', fontWeight: '700', color }}>
                                {val}%{sim !== null && sim !== val ? <span style={{ color: '#7c3aed', marginLeft: '6px' }}>→ {sim}%</span> : null}
                            </span>
                        </div>
                        <div style={{ height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden', position: 'relative' }}>
                            <div style={{ width: `${val}%`, height: '100%', background: color, borderRadius: '4px', transition: 'width 0.4s ease' }} />
                            {sim !== null && (
                                <div style={{ position: 'absolute', top: 0, left: 0, width: `${sim}%`, height: '100%', background: '#7c3aed', borderRadius: '4px', opacity: 0.4 }} />
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

// ── Risk Gauge ────────────────────────────────────────────────────────────────
function RiskGauge({ score }) {
    const s = parseFloat(score) || 0;
    const pct = Math.round(s * 100);
    const color = riskColor(s);
    const r = 54;
    const circ = 2 * Math.PI * r;
    const offset = circ - (pct / 100) * circ;
    return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
            <svg width="130" height="130" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r={r} fill="none" stroke="#e2e8f0" strokeWidth="12" />
                <circle cx="60" cy="60" r={r} fill="none" stroke={color} strokeWidth="12"
                    strokeDasharray={circ} strokeDashoffset={offset}
                    strokeLinecap="round" transform="rotate(-90 60 60)"
                    style={{ transition: 'stroke-dashoffset 0.5s ease' }} />
                <text x="60" y="55" textAnchor="middle" fontSize="22" fontWeight="800" fill={color}>{pct}</text>
                <text x="60" y="70" textAnchor="middle" fontSize="9" fill="#94a3b8">RISK SCORE</text>
            </svg>
            <span style={{ fontSize: '12px', fontWeight: '700', color, letterSpacing: '0.06em' }}>
                {riskLabel(s)}
            </span>
        </div>
    );
}

// ── Simulation Panel ──────────────────────────────────────────────────────────
function SimulationPanel({ entity, onSimulate }) {
    const [addLabel, setAddLabel]     = useState('');
    const [toggleBeh, setToggleBeh]   = useState('');
    const [wBehavior, setWBehavior]   = useState(0.25);
    const [simulating, setSimulating] = useState(false);
    const [result, setResult]         = useState(null);

    const run = async () => {
        setSimulating(true); setResult(null);
        const override = {};
        if (addLabel)           override.add_label        = addLabel;
        if (toggleBeh)          override.toggle_behavior   = toggleBeh;
        if (wBehavior !== 0.25) override.weight_behavior   = wBehavior;
        try {
            const res = await fetch(`${API}/simulate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ entity_id: entity.entity_id, override }),
            });
            const data = await res.json();
            setResult(data);
            if (data.new_breakdown) onSimulate(data.new_breakdown);
        } catch (e) {
            setResult({ error: e.message });
        } finally {
            setSimulating(false);
        }
    };

    const inp = {
        width: '100%', padding: '8px 10px', borderRadius: '8px',
        border: '1px solid #e2e8f0', fontSize: '12px', boxSizing: 'border-box',
        background: '#fff', outline: 'none',
    };

    return (
        <div style={{ background: '#f8fafc', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ fontSize: '11px', fontWeight: '700', color: '#7c3aed', textTransform: 'uppercase', letterSpacing: '0.05em' }}>⚗ Simulation (Safe Mode)</div>
            <div style={{ fontSize: '11px', color: '#94a3b8' }}>Changes are not saved to the database.</div>

            <div>
                <label style={{ fontSize: '11px', fontWeight: '600', color: '#475569', display: 'block', marginBottom: '4px' }}>Add Label</label>
                <select style={inp} value={addLabel} onChange={e => setAddLabel(e.target.value)}>
                    <option value="">— none —</option>
                    {LABEL_OPTIONS.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
            </div>

            <div>
                <label style={{ fontSize: '11px', fontWeight: '600', color: '#475569', display: 'block', marginBottom: '4px' }}>Toggle Behavior</label>
                <select style={inp} value={toggleBeh} onChange={e => setToggleBeh(e.target.value)}>
                    <option value="">— none —</option>
                    {BEHAVIOR_OPTIONS.map(b => <option key={b} value={b}>{b.replace(/_/g, ' ')}</option>)}
                </select>
            </div>

            <div>
                <label style={{ fontSize: '11px', fontWeight: '600', color: '#475569', display: 'block', marginBottom: '4px' }}>
                    Behavior Weight: <b>{wBehavior.toFixed(2)}</b>
                </label>
                <input type="range" min="0" max="0.5" step="0.05" value={wBehavior}
                    onChange={e => setWBehavior(parseFloat(e.target.value))}
                    style={{ width: '100%' }} />
            </div>

            <button onClick={run} disabled={simulating} style={{
                padding: '9px', borderRadius: '8px', border: 'none',
                background: simulating ? '#e2e8f0' : '#7c3aed',
                color: simulating ? '#94a3b8' : '#fff',
                fontSize: '12px', fontWeight: '600', cursor: simulating ? 'not-allowed' : 'pointer',
            }}>
                {simulating ? 'Simulating…' : 'Run Simulation'}
            </button>

            {result && !result.error && (
                <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', padding: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {/* Delta message */}
                    <div style={{
                        padding: '8px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: '700',
                        background: (result.difference || 0) > 0 ? '#fee2e2' : '#dcfce7',
                        color: (result.difference || 0) > 0 ? '#dc2626' : '#16a34a',
                    }}>
                        {(result.difference || 0) > 0
                            ? `Risk increased by +${Math.round((result.difference || 0) * 100)} points`
                            : `Risk decreased by ${Math.round((result.difference || 0) * 100)} points`
                        }
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: '11px', color: '#64748b' }}>New Score</span>
                        <span style={{ fontSize: '13px', fontWeight: '700', color: riskColor(result.new_risk_score) }}>
                            {Math.round((result.new_risk_score || 0) * 100)} / 100
                        </span>
                    </div>
                    {/* Changed factors */}
                    {result.changed_factors && Object.keys(result.changed_factors).length > 0 && (
                        <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: '6px' }}>
                            <div style={{ fontSize: '10px', color: '#94a3b8', marginBottom: '4px' }}>Changed factors:</div>
                            {Object.entries(result.changed_factors).map(([k, delta]) => (
                                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                                    <span style={{ color: '#475569', textTransform: 'capitalize' }}>{k}</span>
                                    <span style={{ fontWeight: '600', color: delta > 0 ? '#dc2626' : '#16a34a' }}>
                                        {delta > 0 ? '+' : ''}{Math.round(delta * 100)}%
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                    {result.would_be_poi && (
                        <div style={{ background: '#fee2e2', color: '#dc2626', padding: '6px 10px', borderRadius: '6px', fontSize: '11px', fontWeight: '600' }}>
                            ⚠ Would trigger POI designation
                        </div>
                    )}
                </div>
            )}
            {result?.error && <div style={{ color: '#dc2626', fontSize: '11px' }}>{result.error}</div>}
        </div>
    );
}

// ── Connected Risky Entities Panel ───────────────────────────────────────────
function ConnectedPanel({ entityId }) {
    const [connected, setConnected] = useState([]);
    const [loading, setLoading]     = useState(true);

    useEffect(() => {
        if (!entityId) return;
        setLoading(true);
        fetch(`${API}/entities/${entityId}/connected?top_n=5`)
            .then(r => r.json())
            .then(d => { setConnected(Array.isArray(d) ? d : []); setLoading(false); })
            .catch(() => setLoading(false));
    }, [entityId]);

    return (
        <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '16px 20px' }}>
            <div style={{ fontSize: '11px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '12px' }}>
                Connected Risky Entities
            </div>
            {loading ? (
                <div style={{ fontSize: '11px', color: '#94a3b8' }}>Loading...</div>
            ) : connected.length === 0 ? (
                <div style={{ fontSize: '11px', color: '#cbd5e1', fontStyle: 'italic' }}>No connected risky entities found.</div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {connected.map(c => (
                        <div key={c.entity_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 10px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                            <div>
                                <div style={{ fontFamily: 'monospace', fontSize: '10px', color: '#475569' }}>{c.entity_id?.slice(0, 18)}…</div>
                                <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '2px' }}>{c.tx_volume_eth} ETH volume</div>
                            </div>
                            <span style={{ fontSize: '12px', fontWeight: '700', color: riskColor(c.risk_score) }}>
                                {Math.round(c.risk_score * 100)}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
export default function RiskIntelligence() {
    const [entities, setEntities]         = useState([]);
    const [loading, setLoading]           = useState(true);
    const [error, setError]               = useState(null);
    const [selected, setSelected]         = useState(null);
    const [simBreakdown, setSimBreakdown] = useState(null);
    const [running, setRunning]           = useState(false);
    const [runMsg, setRunMsg]             = useState('');
    const [filter, setFilter]             = useState('all');
    const [search, setSearch]             = useState('');
    const [mockEnabled, setMockEnabled]   = useState(false);
    const [mockLoading, setMockLoading]   = useState(false);

    const load = () => {
        setLoading(true);
        fetch(`${API}/entities?limit=200`)
            .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
            .then(d => { setEntities(Array.isArray(d) ? d : []); setLoading(false); })
            .catch(e => { setError(e.message); setLoading(false); });
    };

    // Check mock status on mount
    useEffect(() => {
        fetch(`${API}/mock-status`)
            .then(r => r.json())
            .then(d => setMockEnabled(!!d.mock_enabled))
            .catch(() => {});
    }, []);

    useEffect(() => { load(); }, []);

    const handleToggleMock = async () => {
        setMockLoading(true);
        try {
            const method = mockEnabled ? 'DELETE' : 'POST';
            const res = await fetch(`${API}/mock-data`, { method });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setMockEnabled(data.mock_enabled);
            load(); // refresh entity list
        } catch (e) {
            console.error('Mock toggle failed:', e.message);
        } finally {
            setMockLoading(false);
        }
    };

    const handleRun = async () => {
        setRunning(true); setRunMsg('');
        try {
            const r = await fetch(`${API}/run`, { method: 'POST' });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            setRunMsg('Running...');
            const poll = setInterval(async () => {
                try {
                    const sr = await fetch(`${API}/status`);
                    const sd = await sr.json();
                    if (sd.status === 'success' || sd.status === 'failed') {
                        clearInterval(poll);
                        setRunning(false);
                        setRunMsg(sd.status === 'success'
                            ? `Done — ${sd.summary?.poi_count || 0} POIs identified`
                            : `Failed: ${sd.summary?.error}`);
                        if (sd.status === 'success') load();
                    }
                } catch (_) {}
            }, 2000);
        } catch (e) { setRunning(false); setRunMsg(`Error: ${e.message}`); }
    };

    const filtered = entities
        .filter(e => {
            if (filter === 'poi')  return e.is_poi;
            if (filter === 'high') return (parseFloat(e.risk_score) || 0) >= 0.5;
            return true;
        })
        .filter(e => !search ||
            (e.display_name || '').toLowerCase().includes(search.toLowerCase()) ||
            (e.entity_id || '').toLowerCase().includes(search.toLowerCase())
        );

    if (loading) return <Loader />;

    if (error) return (
        <div style={{ padding: '2rem', color: '#ef4444' }}>
            <div style={{ fontWeight: '700', marginBottom: '8px' }}>Could not load risk data</div>
            <div style={{ fontSize: '13px' }}>{error}</div>
            <div style={{ fontSize: '12px', color: '#64748b', marginTop: '8px' }}>
                Make sure the backend is running and risk scoring has been triggered at least once.
            </div>
            <button onClick={load} style={{ marginTop: '12px', padding: '8px 16px', borderRadius: '8px', border: 'none', background: '#0d1b2e', color: '#fff', cursor: 'pointer', fontSize: '12px' }}>
                Retry
            </button>
        </div>
    );

    const poiCount = entities.filter(e => e.is_poi).length;
    const mockPoiCount = entities.filter(e => e.is_poi && e._is_mock).length;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', height: '100%', minHeight: 0, overflow: 'hidden' }}>

            {/* Mock POI toggle banner */}
            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 16px', borderRadius: '10px',
                background: mockEnabled ? '#fef3c7' : '#f8fafc',
                border: `1px solid ${mockEnabled ? '#fcd34d' : '#e2e8f0'}`,
                flexShrink: 0,
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '13px' }}>{mockEnabled ? '🧪' : '🔬'}</span>
                    <div>
                        <span style={{ fontSize: '12px', fontWeight: '700', color: mockEnabled ? '#92400e' : '#475569' }}>
                            Mock POI Data
                        </span>
                        <span style={{ fontSize: '11px', color: mockEnabled ? '#b45309' : '#94a3b8', marginLeft: '8px' }}>
                            {mockEnabled
                                ? `Active — ${mockPoiCount} mock POI${mockPoiCount !== 1 ? 's' : ''} injected (in-memory only, no DB writes)`
                                : 'Disabled — showing real data only'}
                        </span>
                    </div>
                </div>
                <button
                    onClick={handleToggleMock}
                    disabled={mockLoading}
                    style={{
                        padding: '6px 14px', borderRadius: '8px', fontSize: '11px', fontWeight: '700',
                        cursor: mockLoading ? 'not-allowed' : 'pointer',
                        border: `1px solid ${mockEnabled ? '#fca5a5' : '#bbf7d0'}`,
                        background: mockEnabled ? '#fee2e2' : '#f0fdf4',
                        color: mockEnabled ? '#dc2626' : '#16a34a',
                        transition: 'all 0.15s',
                    }}
                >
                    {mockLoading ? '…' : mockEnabled ? 'Disable Mock Data' : 'Enable Mock Data'}
                </button>
            </div>

            {/* Main content */}
            <div style={{ display: 'flex', gap: '20px', flex: 1, minHeight: 0, overflow: 'hidden' }}>

            {/* LEFT: Entity list */}
            <div style={{ width: '360px', minWidth: '360px', display: 'flex', flexDirection: 'column', gap: '12px', overflow: 'hidden' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexShrink: 0 }}>
                    <div>
                        <div style={{ fontSize: '16px', fontWeight: '700', color: '#0f172a' }}>Risk Intelligence</div>
                        <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                            {entities.length} entities · {poiCount} POI{poiCount !== 1 ? 's' : ''}
                            {mockEnabled && mockPoiCount > 0 && (
                                <span style={{ color: '#b45309', marginLeft: '4px' }}>({mockPoiCount} mock)</span>
                            )}
                        </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                        <button onClick={handleRun} disabled={running} style={{
                            padding: '7px 14px', borderRadius: '8px', border: 'none',
                            background: running ? '#e2e8f0' : '#0d1b2e',
                            color: running ? '#94a3b8' : '#fff',
                            fontSize: '11px', fontWeight: '600', cursor: running ? 'not-allowed' : 'pointer',
                        }}>{running ? '⟳ Scoring...' : '⟳ Run Scoring'}</button>
                        {runMsg && <span style={{ fontSize: '10px', color: '#64748b' }}>{runMsg}</span>}
                    </div>
                </div>

                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                    {[['all', 'All'], ['poi', '🔴 POI'], ['high', 'High Risk']].map(([f, l]) => (
                        <button key={f} onClick={() => setFilter(f)} style={{
                            padding: '5px 12px', borderRadius: '999px', border: '1px solid #e2e8f0',
                            background: filter === f ? '#0d1b2e' : '#fff',
                            color: filter === f ? '#fff' : '#475569',
                            fontSize: '11px', fontWeight: '500', cursor: 'pointer',
                        }}>{l}</button>
                    ))}
                    <input type="text" placeholder="Search…" value={search} onChange={e => setSearch(e.target.value)}
                        style={{ marginLeft: 'auto', padding: '5px 10px', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '11px', outline: 'none', width: '110px' }} />
                </div>

                <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflowY: 'auto', flex: 1 }}>
                    {filtered.length === 0 ? (
                        <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8', fontSize: '12px' }}>
                            No entities found. Click "Run Scoring" to calculate risk scores.
                        </div>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr>
                                    <th style={{ ...th, width: '45%' }}>Entity</th>
                                    <th style={{ ...th, width: '25%' }}>Score</th>
                                    <th style={{ ...th, width: '30%' }}>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map(e => {
                                    const score = parseFloat(e.risk_score) || 0;
                                    const isSelected = selected?.entity_id === e.entity_id;
                                    return (
                                        <tr key={e.entity_id}
                                            onClick={() => { setSelected(e); setSimBreakdown(null); }}
                                            style={{ cursor: 'pointer', background: isSelected ? '#eff6ff' : '' }}
                                            onMouseEnter={ev => { if (!isSelected) ev.currentTarget.style.background = '#f8fafc'; }}
                                            onMouseLeave={ev => { if (!isSelected) ev.currentTarget.style.background = ''; }}>
                                            <td style={td}>
                                                <div style={{ fontWeight: '600', color: '#0f172a', fontSize: '11px', marginBottom: '2px' }}>
                                                    {(e.display_name || '').slice(0, 22)}
                                                    {e._is_mock && (
                                                        <span style={{ marginLeft: '5px', fontSize: '9px', fontWeight: '700', color: '#b45309', background: '#fef3c7', border: '1px solid #fcd34d', padding: '1px 5px', borderRadius: '4px', verticalAlign: 'middle' }}>
                                                            MOCK
                                                        </span>
                                                    )}
                                                </div>
                                                <div style={{ fontFamily: 'monospace', fontSize: '10px', color: '#94a3b8' }}>
                                                    {(e.entity_id || '').slice(0, 16)}…
                                                </div>
                                            </td>
                                            <td style={td}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                                                    <div style={{ width: '36px', height: '5px', borderRadius: '3px', background: '#e2e8f0', overflow: 'hidden' }}>
                                                        <div style={{ width: `${Math.round(score * 100)}%`, height: '100%', background: riskColor(score) }} />
                                                    </div>
                                                    <span style={{ fontSize: '11px', fontWeight: '700', color: riskColor(score) }}>
                                                        {Math.round(score * 100)}
                                                    </span>
                                                </div>
                                            </td>
                                            <td style={td}>
                                                {e.is_poi
                                                    ? <span style={{ background: '#fee2e2', color: '#dc2626', padding: '2px 7px', borderRadius: '999px', fontSize: '10px', fontWeight: '700' }}>🔴 POI</span>
                                                    : <span style={{ color: '#94a3b8', fontSize: '10px' }}>{riskLabel(score)}</span>
                                                }
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>

            {/* RIGHT: Detail */}
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {!selected ? (
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '10px', color: '#94a3b8' }}>
                        <div style={{ fontSize: '40px' }}>⚡</div>
                        <div style={{ fontSize: '14px', fontWeight: '600', color: '#475569' }}>Select an entity to analyze</div>
                        <div style={{ fontSize: '12px' }}>Click any row to view risk breakdown and run simulations</div>
                    </div>
                ) : (
                    <>
                        {/* Header */}
                        <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '20px 24px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <div style={{ flex: 1 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '6px' }}>
                                        <span style={{ fontSize: '16px', fontWeight: '700', color: '#0f172a' }}>{selected.display_name}</span>
                                        {selected.is_poi && (
                                            <span style={{ background: '#fee2e2', color: '#dc2626', padding: '3px 10px', borderRadius: '999px', fontSize: '11px', fontWeight: '700' }}>
                                                🔴 HIGH RISK / POI
                                            </span>
                                        )}
                                    </div>
                                    <div style={{ fontFamily: 'monospace', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>{selected.entity_id}</div>
                                    {selected.poi_reason && (
                                        <div style={{ fontSize: '11px', color: '#dc2626' }}>{selected.poi_reason}</div>
                                    )}
                                    <div style={{ display: 'flex', gap: '16px', marginTop: '10px' }}>
                                        <div style={{ fontSize: '11px', color: '#64748b' }}>
                                            Balance: <b>{parseFloat(selected.total_balance || 0).toFixed(4)} ETH</b>
                                        </div>
                                        {selected.country && (
                                            <div style={{ fontSize: '11px', color: '#64748b' }}>Country: <b>{selected.country}</b></div>
                                        )}
                                        {selected.list_category && (
                                            <div style={{ fontSize: '11px', color: '#64748b' }}>
                                                Category: <b style={{ textTransform: 'capitalize' }}>{selected.list_category}</b>
                                            </div>
                                        )}
                                    </div>
                                </div>
                                <RiskGauge score={selected.risk_score} />
                            </div>
                        </div>

                        {/* Breakdown + Simulation */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: '16px' }}>
                            <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '20px 24px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#0f172a', marginBottom: '16px' }}>
                                    Risk Factor Breakdown
                                    {simBreakdown && <span style={{ color: '#7c3aed', fontSize: '11px', marginLeft: '8px' }}>(simulation overlay active)</span>}
                                </div>
                                <BreakdownBars breakdown={selected.risk_breakdown || {}} simBreakdown={simBreakdown} />

                                {/* Weights legend */}
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '16px', paddingTop: '12px', borderTop: '1px solid #f1f5f9' }}>
                                    {[['label', '35%'], ['behavior', '25%'], ['propagation', '20%'], ['temporal', '10%'], ['exposure', '10%']].map(([k, w]) => (
                                        <div key={k} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                                            <div style={{ width: '8px', height: '8px', borderRadius: '2px', background: FACTOR_COLORS[k] }} />
                                            <span style={{ fontSize: '10px', color: '#64748b' }}>{FACTOR_LABELS[k]} <b>({w})</b></span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <SimulationPanel entity={selected} onSimulate={setSimBreakdown} />
                        </div>

                        {/* Connected + Addresses */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                            <ConnectedPanel entityId={selected.entity_id} />
                            <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '16px 20px' }}>
                                <div style={{ fontSize: '11px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '10px' }}>
                                    Member Addresses ({(selected.addresses || []).length})
                                </div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxHeight: '120px', overflowY: 'auto' }}>
                                    {(selected.addresses || []).map(addr => (
                                        <div key={addr} style={{ fontFamily: 'monospace', fontSize: '10px', color: '#334155', background: '#f8fafc', border: '1px solid #e2e8f0', padding: '4px 8px', borderRadius: '6px' }}>
                                            {addr}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
        </div>
    );
}
