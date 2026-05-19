/**
 * MVRV Analysis (Market Value to Realized Value)
 *
 * On-chain cost-basis intelligence component.
 * Displays MVRV ratio, unrealized/realized PnL, asset holdings, and intelligence flags.
 */

import { useState, useEffect, useMemo, useCallback, useId } from 'react';
import {
  ComposedChart, PieChart, Pie, Cell,
  Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

// ─── colour tokens ────────────────────────────────────────────────────────────
const C = {
  gold:      '#C9A84C',
  green:     '#4ADE80',
  red:       '#F87171',
  blue:      '#627EEA',
  purple:    '#8B5CF6',
  textPri:   '#E2D9C8',
  textSec:   '#8A9DB5',
  textMuted: '#4B5E72',
  cardBg:    'linear-gradient(145deg, #101D32, #0D1628)',
  cardBorder:'1px solid rgba(201,168,76,0.12)',
};

// ─── helpers ──────────────────────────────────────────────────────────────────
const fmt$ = (v) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(v || 0);

const fmtNum = (v, d = 4) =>
  new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0, maximumFractionDigits: d,
  }).format(v || 0);

const fmtRatio = (v) =>
  v == null ? '—' : Number(v).toFixed(3);

const pnlColor = (v) => (v > 0 ? C.green : v < 0 ? C.red : C.textSec);

const mvrvColor = (r) => {
  if (r == null) return C.gold;
  if (r > 1)    return C.green;
  if (r < 1)    return C.red;
  return C.gold;
};

const mvrvLabel = (r) => {
  if (r == null) return 'No Data';
  if (r > 1)    return 'Profit Zone';
  if (r < 1)    return 'Loss Zone';
  return 'Break-Even';
};

// Clamp ratio to [0, 3] for the gauge bar (3+ shown as full)
const gaugePercent = (r) => Math.min(Math.max((r || 0) / 3, 0), 1) * 100;

// ─── sub-components ───────────────────────────────────────────────────────────

const SummaryCard = ({ label, value, icon, color, sub }) => (
  <div style={{
    background: C.cardBg,
    borderRadius: '14px',
    border: C.cardBorder,
    padding: '20px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
  }}>
    <div style={{ fontSize: '22px', marginBottom: '8px' }}>{icon}</div>
    <div style={{ fontSize: '18px', fontWeight: '700', color: color || C.gold, marginBottom: '4px', wordBreak: 'break-all' }}>
      {value}
    </div>
    {sub && (
      <div style={{ fontSize: '11px', color: pnlColor(sub.raw), marginBottom: '2px', fontWeight: '600' }}>
        {sub.label}
      </div>
    )}
    <div style={{ fontSize: '11px', color: C.textSec, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
      {label}
    </div>
  </div>
);

const FlagCard = ({ flag }) => {
  const palette = {
    info:    { bg: 'rgba(96,165,250,0.10)',  border: 'rgba(96,165,250,0.25)',  text: '#60A5FA' },
    warning: { bg: 'rgba(251,191,36,0.10)',  border: 'rgba(251,191,36,0.25)',  text: '#FBBF24' },
    danger:  { bg: 'rgba(239,68,68,0.10)',   border: 'rgba(239,68,68,0.25)',   text: '#F87171' },
  };
  const p = palette[flag.severity] || palette.info;
  return (
    <div style={{ background: p.bg, border: `1px solid ${p.border}`, borderRadius: '10px', padding: '12px 16px' }}>
      <div style={{ fontSize: '12px', fontWeight: '700', color: p.text, marginBottom: '4px' }}>{flag.label}</div>
      <div style={{ fontSize: '11px', color: C.textSec, lineHeight: '1.5' }}>{flag.description}</div>
    </div>
  );
};

const TableHeader = ({ label, sortKey, sortConfig, onSort, align = 'left' }) => {
  const active = sortConfig?.key === sortKey;
  return (
    <th
      onClick={() => sortKey && onSort && onSort(sortKey)}
      style={{
        padding: '12px 20px',
        fontSize: '11px', fontWeight: '800',
        color: active ? C.gold : '#6B7E94',
        textTransform: 'uppercase', letterSpacing: '0.1em',
        textAlign: align,
        cursor: sortKey ? 'pointer' : 'default',
        userSelect: 'none',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
      {sortKey && (
        <span style={{ marginLeft: '5px', opacity: active ? 1 : 0.3 }}>
          {active && sortConfig.direction === 'desc' ? '↓' : '↑'}
        </span>
      )}
    </th>
  );
};

// ─── MVRV Gauge ───────────────────────────────────────────────────────────────

const MvrvGauge = ({ ratio }) => {
  const pct   = gaugePercent(ratio);
  const color = mvrvColor(ratio);
  const label = mvrvLabel(ratio);

  return (
    <div style={{ textAlign: 'center', padding: '8px 0 4px' }}>
      {/* Big ratio number */}
      <div style={{ fontSize: '52px', fontWeight: '800', color, lineHeight: 1, letterSpacing: '-0.03em' }}>
        {fmtRatio(ratio)}
      </div>
      {/* Zone label */}
      <div style={{
        fontSize: '12px', fontWeight: '700', color,
        textTransform: 'uppercase', letterSpacing: '0.12em',
        marginTop: '6px', marginBottom: '18px',
      }}>
        {label}
      </div>

      {/* Gauge bar */}
      <div style={{ position: 'relative', margin: '0 auto', maxWidth: '320px' }}>
        {/* Track */}
        <div style={{
          height: '10px', borderRadius: '6px',
          background: 'rgba(255,255,255,0.07)',
          border: '1px solid rgba(255,255,255,0.08)',
          overflow: 'hidden',
        }}>
          {/* Fill */}
          <div style={{
            height: '100%',
            width: `${pct}%`,
            borderRadius: '6px',
            background: `linear-gradient(90deg, ${color}88, ${color})`,
            transition: 'width 0.6s ease',
          }} />
        </div>
        {/* Scale labels */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '5px', fontSize: '10px', color: C.textMuted }}>
          <span>0</span>
          <span>1 (break-even)</span>
          <span>2</span>
          <span>3+</span>
        </div>
        {/* Break-even tick */}
        <div style={{
          position: 'absolute',
          left: `${(1 / 3) * 100}%`,
          top: 0,
          width: '2px',
          height: '10px',
          background: C.gold,
          opacity: 0.6,
          transform: 'translateX(-50%)',
        }} />
      </div>
    </div>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────

const MvrvAnalysis = ({ entityId, entityType }) => {
  const [data,        setData]        = useState(null);
  const [history,     setHistory]     = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);
  const [refreshing,  setRefreshing]  = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [sortConfig,  setSortConfig]  = useState({ key: 'market_value_usd', direction: 'desc' });
  const [chartView,   setChartView]   = useState('timeline'); // 'timeline' | 'pie'
  const [method,      setMethod]      = useState('FIFO');     // FIFO | LIFO | HIFO

  const gradId = `mvrvGrad_${useId().replace(/:/g, '')}`;

  // ── fetch helpers ────────────────────────────────────────────────────────────
  const fetchData = useCallback(async (signal) => {
    const endpoint =
      entityType === 'cluster'
        ? `${API_BASE}/mvrv/cluster/${encodeURIComponent(entityId)}?method=${method}`
        : `${API_BASE}/mvrv/address/${encodeURIComponent(entityId)}?method=${method}`;

    const res = await fetch(endpoint, { signal });
    if (!res.ok) throw new Error(`MVRV fetch failed: ${res.status}`);
    return res.json();
  }, [entityId, entityType, method]);

  const fetchHistory = useCallback(async (signal) => {
    const res = await fetch(
      `${API_BASE}/mvrv/history/${encodeURIComponent(entityId)}?entity_type=${encodeURIComponent(entityType)}&days=30`,
      { signal },
    );
    if (!res.ok) return [];
    const j = await res.json();
    return j.history || [];
  }, [entityId, entityType]);

  // ── initial + interval load ──────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    const ac = new AbortController();

    const run = async () => {
      setLoading(true);
      setError(null);
      setData(null);
      setHistory([]);
      try {
        const [mvrv, hist] = await Promise.all([
          fetchData(ac.signal),
          fetchHistory(ac.signal),
        ]);
        if (cancelled) return;
        setData(mvrv);
        setHistory(hist);
        setLastRefresh(new Date());
      } catch (err) {
        if (!cancelled && err.name !== 'AbortError') setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    run();

    // Auto-refresh every 60 s
    const timer = setInterval(() => {
      if (!cancelled) run();
    }, 60_000);

    return () => {
      cancelled = true;
      ac.abort();
      clearInterval(timer);
    };
  }, [fetchData, fetchHistory]);

  // ── manual refresh ───────────────────────────────────────────────────────────
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await fetch(
        `${API_BASE}/mvrv/refresh/${encodeURIComponent(entityId)}?method=${method}`,
        { method: 'POST' },
      );
      // Re-fetch after triggering refresh
      const ac = new AbortController();
      const [mvrv, hist] = await Promise.all([
        fetchData(ac.signal),
        fetchHistory(ac.signal),
      ]);
      setData(mvrv);
      setHistory(hist);
      setLastRefresh(new Date());
    } catch (err) {
      // silently ignore refresh errors — data may still be stale
    } finally {
      setRefreshing(false);
    }
  };

  // ── sort ─────────────────────────────────────────────────────────────────────
  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc',
    }));
  };

  // ── chart data ───────────────────────────────────────────────────────────────
  const chartRows = useMemo(() => {
    const safeTime = (ts, idx) => {
      const n = Date.parse(ts);
      return Number.isFinite(n) ? n : Date.now() - idx * 3_600_000;
    };

    const mapRow = (row, i) => ({
      ...row,
      t:   safeTime(row.timestamp, i),
      mv:  Number(row.market_value_usd  ?? 0),
      rv:  Number(row.realized_value_usd ?? 0),
      rat: Number(row.mvrv_ratio         ?? 0),
    });

    const h = history || [];

    if (h.length >= 2) {
      const rows = h.map(mapRow);
      for (let i = 1; i < rows.length; i++) {
        if (rows[i].t <= rows[i - 1].t) rows[i] = { ...rows[i], t: rows[i - 1].t + 60_000 };
      }
      return rows;
    }

    if (h.length === 1) {
      const r = mapRow(h[0], 0);
      const t0 = r.t - 72 * 3_600_000;
      return [{ ...r, t: t0 }, { ...r }];
    }

    // Fallback: synthesise two points from summary
    const s = data?.summary;
    if (!s) return [];
    const mv  = Number(s.market_value_usd   ?? 0);
    const rv  = Number(s.realized_value_usd ?? 0);
    const rat = Number(s.mvrv_ratio         ?? 0);
    let tEnd = Date.parse(s.updated_at);
    if (!Number.isFinite(tEnd)) tEnd = Date.now();
    const tStart = tEnd - 48 * 3_600_000;
    return [
      { t: tStart, mv, rv, rat },
      { t: tEnd,   mv, rv, rat },
    ];
  }, [data, history]);

  const [mvDomain, ratDomain] = useMemo(() => {
    if (!chartRows.length) return [[0, 1], [0, 2]];
    const maxMv  = Math.max(...chartRows.map(r => Math.max(r.mv || 0, r.rv || 0)), 0);
    const maxRat = Math.max(...chartRows.map(r => r.rat || 0), 0);
    const mvHead  = Math.max(maxMv  * 0.1, 1);
    const ratHead = Math.max(maxRat * 0.1, 0.2);
    return [
      [0, maxMv  + mvHead],
      [0, maxRat + ratHead],
    ];
  }, [chartRows]);

  // ── pie data ─────────────────────────────────────────────────────────────────
  const pieData = useMemo(() => {
    const assets = data?.assets || [];
    const slices = assets
      .filter(a => (a.portfolio_percent || 0) > 0)
      .map(a => ({
        name:  a.token_symbol || 'Unknown',
        value: Number(a.portfolio_percent || 0),
        color: a.token_symbol === 'ETH' ? C.blue
             : a.token_symbol === 'USDC' || a.token_symbol === 'USDT' ? '#26A17B'
             : C.purple,
      }));
    return slices.length > 0
      ? slices
      : [{ name: 'No holdings', value: 100, color: 'rgba(71,85,105,0.55)' }];
  }, [data]);

  // ── sorted assets ─────────────────────────────────────────────────────────────
  const sortedAssets = useMemo(() => {
    const assets = data?.assets || [];
    return [...assets].sort((a, b) => {
      const av = a[sortConfig.key] ?? 0;
      const bv = b[sortConfig.key] ?? 0;
      const m  = sortConfig.direction === 'asc' ? 1 : -1;
      return av > bv ? m : av < bv ? -m : 0;
    });
  }, [data, sortConfig]);

  // ── loading / error states ───────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px', color: C.textSec }}>
        Loading MVRV data…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <div style={{ color: C.red, fontSize: '14px', marginBottom: '8px' }}>⚠️ Error loading MVRV data</div>
        <div style={{ color: C.textMuted, fontSize: '12px' }}>{error}</div>
      </div>
    );
  }

  if (!data) return null;

  const { summary, assets, flags } = data;
  const ratio       = summary?.mvrv_ratio ?? null;
  const entityLabel = data?.entity_label || null;

  // ── render ───────────────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* ── Header bar: live indicator + refresh ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Pulsing green dot */}
          <span style={{
            display: 'inline-block', width: '9px', height: '9px', borderRadius: '50%',
            background: C.green,
            boxShadow: `0 0 0 3px ${C.green}33`,
            animation: 'mvrv-pulse 2s ease-in-out infinite',
          }} />
          <style>{`
            @keyframes mvrv-pulse {
              0%, 100% { box-shadow: 0 0 0 3px ${C.green}33; }
              50%       { box-shadow: 0 0 0 7px ${C.green}11; }
            }
          `}</style>
          <span style={{ fontSize: '11px', color: C.textSec }}>
            Live · auto-refresh every 60 s
            {lastRefresh && (
              <span style={{ marginLeft: '8px', color: C.textMuted }}>
                · last: {lastRefresh.toLocaleTimeString()}
              </span>
            )}
          </span>
        </div>

        {/* Accounting method selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '10px', color: C.textMuted, fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Method
          </span>
          {['FIFO', 'LIFO', 'HIFO'].map(m => (
            <button
              key={m}
              onClick={() => setMethod(m)}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                border: method === m ? '1px solid rgba(201,168,76,0.5)' : '1px solid rgba(255,255,255,0.08)',
                background: method === m ? 'rgba(201,168,76,0.15)' : 'transparent',
                color: method === m ? C.gold : C.textMuted,
                fontSize: '11px', fontWeight: '700',
                cursor: 'pointer', transition: 'all 0.15s',
              }}
            >
              {m}
            </button>
          ))}
        </div>

        <button
          onClick={handleRefresh}
          disabled={refreshing}
          style={{
            padding: '8px 18px',
            borderRadius: '10px',
            border: `1px solid rgba(201,168,76,0.35)`,
            background: refreshing ? 'rgba(201,168,76,0.05)' : 'rgba(201,168,76,0.10)',
            color: C.gold,
            fontSize: '12px', fontWeight: '700',
            cursor: refreshing ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s',
          }}
        >
          {refreshing ? '⟳ Refreshing…' : '⟳ Refresh'}
        </button>      </div>

      {/* ── MVRV Ratio hero card ── */}
      <div style={{
        background: C.cardBg,
        borderRadius: '16px',
        border: C.cardBorder,
        padding: '28px 32px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ fontSize: '11px', fontWeight: '800', color: '#5C6B82', letterSpacing: '0.16em', textTransform: 'uppercase' }}>
            MVRV Ratio
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            {entityLabel && (
              <span style={{
                padding: '3px 10px', borderRadius: '6px', fontSize: '11px', fontWeight: '700',
                background: 'rgba(201,168,76,0.12)', color: C.gold,
              }}>
                {entityLabel}
              </span>
            )}
            <span style={{
              padding: '3px 10px', borderRadius: '6px', fontSize: '11px', fontWeight: '700',
              background: 'rgba(139,92,246,0.12)', color: '#A78BFA',
            }}>
              {method}
            </span>
          </div>
        </div>
        <MvrvGauge ratio={ratio} />
      </div>

      {/* ── Summary cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
        <SummaryCard
          label="Market Value"
          value={fmt$(summary.market_value_usd)}
          icon="📈"
          color={C.gold}
        />
        <SummaryCard
          label="Realized Value"
          value={fmt$(summary.realized_value_usd)}
          icon="🏦"
          color={C.blue}
        />
        <SummaryCard
          label="Unrealized PnL"
          value={fmt$(summary.unrealized_pnl_usd)}
          icon={summary.unrealized_pnl_usd >= 0 ? '🟢' : '🔴'}
          color={pnlColor(summary.unrealized_pnl_usd)}
        />
        <SummaryCard
          label="Realized PnL"
          value={fmt$(summary.realized_pnl_usd)}
          icon={summary.realized_pnl_usd >= 0 ? '✅' : '❌'}
          color={pnlColor(summary.realized_pnl_usd)}
        />
        <SummaryCard
          label="Net PnL"
          value={fmt$(summary.net_pnl_usd)}
          icon="💹"
          color={pnlColor(summary.net_pnl_usd)}
        />
        <SummaryCard
          label="Tx Count"
          value={fmtNum(summary.tx_count_total, 0)}
          icon="🔁"
          color={C.textSec}
        />
        <SummaryCard
          label="MVRV Ratio"
          value={fmtRatio(ratio)}
          icon="⚖️"
          color={mvrvColor(ratio)}
        />
      </div>

      {/* ── Chart + Intelligence Flags ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>

        {/* Chart panel */}
        <div style={{
          background: 'linear-gradient(155deg, #101D32 0%, #0D1628 50%, #081020 100%)',
          borderRadius: '16px',
          border: '1px solid rgba(201,168,76,0.14)',
          padding: '22px 24px 20px',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.035)',
        }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', marginBottom: '12px' }}>
            <div>
              <div style={{ fontSize: '9px', fontWeight: '800', color: '#5C6B82', letterSpacing: '0.16em', textTransform: 'uppercase' }}>
                Cost-basis pulse
              </div>
              <div style={{ fontSize: '15px', fontWeight: '700', color: '#E2C97E', marginTop: '5px', letterSpacing: '-0.02em' }}>
                {chartView === 'timeline' ? 'MV vs RV over time' : 'Portfolio allocation'}
              </div>
            </div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-end' }}>
              <span style={{ fontSize: '9px', color: '#64748B', fontWeight: '700', letterSpacing: '0.08em', textTransform: 'uppercase' }}>View</span>
              <select
                value={chartView}
                onChange={(e) => setChartView(e.target.value)}
                style={{
                  cursor: 'pointer',
                  padding: '8px 36px 8px 12px',
                  borderRadius: '10px',
                  border: '1px solid rgba(201,168,76,0.28)',
                  backgroundColor: '#0A1020',
                  color: '#E8DFD0',
                  fontSize: '12px', fontWeight: '600',
                  minWidth: '210px',
                  outline: 'none',
                  boxShadow: '0 0 0 1px rgba(201,168,76,0.06)',
                }}
              >
                <option value="timeline">Timeline — MV vs RV</option>
                <option value="pie">Pie — allocation %</option>
              </select>
            </label>
          </div>

          {chartView === 'timeline' ? (
            chartRows.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={272}>
                  <ComposedChart data={chartRows} margin={{ top: 6, right: 48, left: 0, bottom: 2 }}>
                    <defs>
                      <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%"   stopColor={C.gold}   stopOpacity={0.55} />
                        <stop offset="100%" stopColor="#0D1628"  stopOpacity={0}    />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="5 10" stroke="rgba(201,168,76,0.08)" vertical={false} />
                    <XAxis
                      type="number" dataKey="t"
                      domain={['dataMin', 'dataMax']}
                      stroke="#4B5E72"
                      tick={{ fontSize: 10, fill: C.textSec }}
                      tickFormatter={(ts) => {
                        const d = new Date(ts);
                        return Number.isFinite(d.getTime()) ? `${d.getMonth() + 1}/${d.getDate()}` : '—';
                      }}
                    />
                    {/* Left Y: USD values */}
                    <YAxis
                      yAxisId="usd"
                      domain={mvDomain}
                      stroke="#4B5E72"
                      tick={{ fontSize: 10, fill: C.textSec }}
                      tickFormatter={(v) => v >= 1e6 ? `${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `${(v/1e3).toFixed(0)}k` : `${Math.round(v)}`}
                      width={52}
                    />
                    {/* Right Y: MVRV ratio */}
                    <YAxis
                      yAxisId="ratio"
                      orientation="right"
                      domain={ratDomain}
                      stroke="#4B5E72"
                      tick={{ fontSize: 10, fill: C.purple }}
                      tickFormatter={(v) => v.toFixed(2)}
                      width={44}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'rgba(8,14,26,0.96)',
                        border: '1px solid rgba(201,168,76,0.3)',
                        borderRadius: '10px',
                        color: '#F4EFE6',
                        fontSize: '12px',
                      }}
                      labelFormatter={(ts) => {
                        const d = new Date(ts);
                        return Number.isFinite(d.getTime())
                          ? d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                          : '—';
                      }}
                      formatter={(val, name) => {
                        const map = { mv: 'Market Value', rv: 'Realized Value', rat: 'MVRV Ratio' };
                        const isRatio = name === 'rat';
                        return [isRatio ? Number(val).toFixed(4) : fmt$(val), map[name] || name];
                      }}
                    />
                    {/* Market Value — gold area */}
                    <Area
                      yAxisId="usd"
                      type="linear" dataKey="mv" name="mv"
                      stroke={C.gold} strokeWidth={2.4}
                      fill={`url(#${gradId})`}
                      connectNulls dot={false} activeDot={{ r: 5 }}
                      isAnimationActive={false}
                    />
                    {/* Realized Value — blue dashed */}
                    <Line
                      yAxisId="usd"
                      type="linear" dataKey="rv" name="rv"
                      stroke={C.blue} strokeWidth={1.8}
                      strokeDasharray="6 5"
                      dot={false} connectNulls
                      isAnimationActive={false}
                    />
                    {/* MVRV Ratio — purple, right axis */}
                    <Line
                      yAxisId="ratio"
                      type="linear" dataKey="rat" name="rat"
                      stroke={C.purple} strokeWidth={1.6}
                      dot={false} connectNulls
                      isAnimationActive={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px 16px', justifyContent: 'center', marginTop: '10px', fontSize: '10px', color: C.textSec }}>
                  <span><span style={{ color: C.gold,   fontWeight: 800 }}>■ </span>Market Value</span>
                  <span><span style={{ color: C.blue  }}>╌ </span>Realized Value</span>
                  <span><span style={{ color: C.purple }}>— </span>MVRV Ratio (right axis)</span>
                </div>
              </>
            ) : (
              <div style={{ textAlign: 'center', color: C.textMuted, padding: '56px 16px', fontSize: '13px' }}>
                No history data available yet.
              </div>
            )
          ) : (
            <ResponsiveContainer width="100%" height={272}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%" cy="50%"
                  outerRadius={88} innerRadius={28}
                  dataKey="value"
                  paddingAngle={2}
                  labelLine={false}
                  label={({ name, value }) => `${name}: ${Number(value).toFixed(1)}%`}
                  isAnimationActive={false}
                >
                  {pieData.map((entry, i) => (
                    <Cell key={`cell-${i}`} fill={entry.color} stroke="rgba(10,16,32,0.85)" strokeWidth={1} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: '#0D1628',
                    border: '1px solid rgba(201,168,76,0.22)',
                    borderRadius: '8px',
                    color: C.textPri,
                  }}
                  formatter={(v) => `${Number(v).toFixed(2)}%`}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Intelligence Flags */}
        <div style={{
          background: C.cardBg,
          borderRadius: '16px',
          border: C.cardBorder,
          padding: '24px',
        }}>
          <div style={{ fontSize: '14px', fontWeight: '700', color: C.gold, marginBottom: '16px' }}>
            Intelligence Flags
          </div>
          {flags && flags.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {flags.map((flag, idx) => (
                <FlagCard key={idx} flag={flag} />
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: C.textMuted, padding: '48px 0' }}>
              No flags detected
            </div>
          )}
        </div>
      </div>

      {/* ── Asset Holdings Table ── */}
      <div style={{
        background: C.cardBg,
        borderRadius: '16px',
        border: C.cardBorder,
        overflow: 'hidden',
      }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid rgba(201,168,76,0.08)' }}>
          <div style={{ fontSize: '14px', fontWeight: '700', color: C.gold }}>
            Asset Holdings
            {entityType === 'address' && entityId && (
              <span style={{ marginLeft: '12px', fontSize: '11px', color: C.textSec, fontWeight: '400' }}>
                · Showing data for selected address
              </span>
            )}
          </div>
        </div>

        {sortedAssets.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#0A1020', borderBottom: '1px solid rgba(201,168,76,0.08)' }}>
                  <TableHeader label="Token"          sortKey="token_symbol"      sortConfig={sortConfig} onSort={handleSort} />
                  <TableHeader label="Balance"        sortKey="balance"           sortConfig={sortConfig} onSort={handleSort} align="right" />
                  <TableHeader label="Market Value"   sortKey="market_value_usd"  sortConfig={sortConfig} onSort={handleSort} align="right" />
                  <TableHeader label="Cost Basis"     sortKey="cost_basis_usd"    sortConfig={sortConfig} onSort={handleSort} align="right" />
                  <TableHeader label="Unrealized PnL" sortKey="unrealized_pnl_usd"    sortConfig={sortConfig} onSort={handleSort} align="right" />
                  <TableHeader label="Portfolio %"    sortKey="portfolio_percent"  sortConfig={sortConfig} onSort={handleSort} align="right" />
                </tr>
              </thead>
              <tbody>
                {sortedAssets.map((asset, idx) => {
                  const upnl = asset.unrealized_pnl_usd ?? 0;
                  return (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: idx < sortedAssets.length - 1 ? '1px solid rgba(201,168,76,0.05)' : 'none',
                        background: idx % 2 === 0 ? '#0D1628' : '#101D32',
                      }}
                    >
                      {/* Token */}
                      <td style={{ padding: '14px 20px', color: C.textPri, fontSize: '13px', fontWeight: '600' }}>
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background: asset.token_symbol === 'ETH' ? 'rgba(98,126,234,0.15)' : 'rgba(139,92,246,0.12)',
                          color: asset.token_symbol === 'ETH' ? C.blue : C.purple,
                          fontSize: '12px', fontWeight: '700',
                        }}>
                          {asset.token_symbol || '?'}
                        </span>
                      </td>
                      {/* Balance */}
                      <td style={{ padding: '14px 20px', color: C.textSec, fontSize: '13px', textAlign: 'right' }}>
                        {fmtNum(asset.balance)}
                      </td>
                      {/* Market Value */}
                      <td style={{ padding: '14px 20px', color: C.gold, fontSize: '13px', fontWeight: '600', textAlign: 'right' }}>
                        {fmt$(asset.market_value_usd)}
                      </td>
                      {/* Cost Basis */}
                      <td style={{ padding: '14px 20px', color: C.blue, fontSize: '13px', textAlign: 'right' }}>
                        {fmt$(asset.cost_basis_usd)}
                      </td>
                      {/* Unrealized PnL */}
                      <td style={{ padding: '14px 20px', color: pnlColor(upnl), fontSize: '13px', fontWeight: '600', textAlign: 'right' }}>
                        {upnl >= 0 ? '+' : ''}{fmt$(upnl)}
                      </td>
                      {/* Portfolio % */}
                      <td style={{ padding: '14px 20px', color: C.textSec, fontSize: '13px', textAlign: 'right' }}>
                        {Number(asset.portfolio_percent || 0).toFixed(2)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: '48px', textAlign: 'center', color: C.textMuted }}>
            No assets found
          </div>
        )}
      </div>

    </div> // end root flex column
  );
};

export default MvrvAnalysis;
