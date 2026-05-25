/**
 * Market Value Analysis (MVA)
 *
 * On-chain portfolio intelligence component.
 * Displays current wealth, asset allocation, holdings, and intelligence flags.
 * Supports USD and ETH valuation modes via the shared ValuationToggle.
 */

import { useState, useEffect, useMemo, useId } from 'react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  Line, XAxis, YAxis, CartesianGrid, Area, ComposedChart,
} from 'recharts';
import {
  useValuationMode,
  ValuationToggle,
  fmtValue,
  MODES,
} from '../../utils/valuationMode.jsx';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

const MarketValueAnalysis = ({ entityId, entityType }) => {
  const [data,          setData]          = useState(null);
  const [history,       setHistory]       = useState([]);
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState(null);
  const [sortConfig,    setSortConfig]    = useState({ key: 'value_usd', direction: 'desc' });
  const [allocationViz, setAllocationViz] = useState('timeline');
  const chartGradientId = `mvaGold_${useId().replace(/:/g, '')}`;

  const [valMode, setValMode] = useValuationMode();

  // ── ETH price estimate for valuation mode conversions ──────────────────────
  const ethPriceEst = useMemo(() => {
    if (!data) return 3000;
    const ethAsset = (data.assets || []).find(
      a => a.token_symbol === 'ETH' || a.token_symbol === 'WETH'
    );
    const ethBal = ethAsset?.balance || 0;
    const mv = data.summary?.total_value_usd || 0;
    if (ethBal > 0 && mv > 0) return mv / ethBal;
    return 3000;
  }, [data]);

  const toEth = (usd) => (ethPriceEst > 0 ? usd / ethPriceEst : 0);
  const fv    = (usd) => fmtValue(usd, toEth(usd), valMode);

  // ── Chart rows ─────────────────────────────────────────────────────────────
  const chartRows = useMemo(() => {
    const summary = data?.summary;
    const h = history || [];
    const safeTime = (ts, idx) => {
      const n = Date.parse(ts);
      return Number.isFinite(n) ? n : Date.now() - idx * 3_600_000;
    };
    const mapRow = (row, i) => ({
      ...row,
      t:      safeTime(row.timestamp, i),
      total:  Number(row.total_value_usd ?? 0),
      ethUsd: Number(row.eth_value_usd ?? 0),
      stUsd:  Number(row.stablecoin_value_usd ?? 0),
    });
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
      const t1 = t0 < r.t ? r.t : t0 + 3_600_000;
      return [{ ...r, t: t0 }, { ...r, t: t1 }];
    }
    if (!summary) return [];
    const v    = Number(summary.total_value_usd ?? 0);
    const ethU = Number(summary.eth_value_usd ?? 0);
    const stU  = Number(summary.stablecoin_value_usd ?? 0);
    let tEnd = safeTime(summary.updated_at, 0);
    if (!Number.isFinite(tEnd)) tEnd = Date.now();
    const tStart = tEnd - 48 * 3_600_000;
    return [
      { t: tStart, total: v, ethUsd: ethU, stUsd: stU },
      { t: tEnd,   total: v, ethUsd: ethU, stUsd: stU },
    ];
  }, [data, history]);

  const chartYDomain = useMemo(() => {
    if (!chartRows.length) return [0, 1];
    const m = Math.max(
      ...chartRows.flatMap(r => [Number(r.total) || 0, Number(r.ethUsd) || 0, Number(r.stUsd) || 0]),
      0,
    );
    if (m <= 0) return [0, 1];
    return [0, m + Math.max(m * 0.08, 1)];
  }, [chartRows]);

  // ── Data fetch ─────────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      setError(null);
      setHistory([]);
      setData(null);
      try {
        const endpoint = entityType === 'cluster'
          ? `${API_BASE}/mva/cluster/${encodeURIComponent(entityId)}`
          : `${API_BASE}/mva/address/${encodeURIComponent(entityId)}`;
        const mvaRes = await fetch(endpoint);
        if (!mvaRes.ok) throw new Error('Failed to fetch MVA data');
        const mvaJson = await mvaRes.json();
        if (cancelled) return;
        setData(mvaJson);

        const histRes = await fetch(
          `${API_BASE}/mva/history/${encodeURIComponent(entityId)}?entity_type=${encodeURIComponent(entityType)}&days=30`,
        );
        if (histRes.ok && !cancelled) {
          const histJson = await histRes.json();
          setHistory(histJson.history || []);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    return () => { cancelled = true; };
  }, [entityId, entityType]);

  const formatCurrency = (value) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency', currency: 'USD',
      minimumFractionDigits: 2, maximumFractionDigits: 2,
    }).format(value || 0);

  const formatNumber = (value, decimals = 4) =>
    new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 0, maximumFractionDigits: decimals,
    }).format(value || 0);

  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc',
    }));
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px', color: '#8A9DB5' }}>
        Loading portfolio data...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <div style={{ color: '#F87171', fontSize: '14px', marginBottom: '8px' }}>⚠️ Error loading portfolio data</div>
        <div style={{ color: '#4B5E72', fontSize: '12px' }}>{error}</div>
      </div>
    );
  }

  if (!data) return null;

  const { summary, assets, allocation, flags } = data;

  const pieData = [
    { name: 'ETH',        value: allocation.eth_percent,        color: '#627EEA' },
    { name: 'Stablecoins',value: allocation.stablecoin_percent, color: '#26A17B' },
    { name: 'Other ERC20',value: allocation.other_erc20_percent,color: '#8B5CF6' },
    { name: 'DeFi',       value: allocation.defi_percent,       color: '#F59E0B' },
  ].filter(item => item.value > 0);

  const pieDisplayData = pieData.length > 0
    ? pieData
    : [{ name: 'No on-chain book yet', value: 100, color: 'rgba(71,85,105,0.55)' }];

  const histLen  = history.length;
  const bookUsd  = Number(summary.total_value_usd ?? 0);
  const sortedAssets = [...assets].sort((a, b) => {
    const aVal = a[sortConfig.key];
    const bVal = b[sortConfig.key];
    const mod  = sortConfig.direction === 'asc' ? 1 : -1;
    return aVal > bVal ? mod : -mod;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Valuation mode toggle */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <ValuationToggle mode={valMode} onChange={setValMode} />
      </div>

      {/* Portfolio Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <SummaryCard
          label={valMode === MODES.ETH ? 'Total Portfolio Value (Ξ)' : 'Total Portfolio Value'}
          value={fv(summary.total_value_usd)}
          icon="💰" color="#C9A84C"
        />
        <SummaryCard
          label={valMode === MODES.ETH ? 'ETH Holdings (Ξ)' : 'ETH Holdings'}
          value={fv(summary.eth_value_usd)}
          icon="⟠" color="#627EEA"
        />
        <SummaryCard
          label={valMode === MODES.ETH ? 'Stablecoin Holdings (Ξ)' : 'Stablecoin Holdings'}
          value={fv(summary.stablecoin_value_usd)}
          icon="💵" color="#26A17B"
        />
        <SummaryCard label="Wallets in Cluster" value={summary.wallet_count} icon="👛" color="#8A9DB5" />
        <SummaryCard label="Tokens Held"        value={summary.token_count}  icon="🪙" color="#8B5CF6" />
      </div>

      {/* Chart + Intelligence Flags */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
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
                Market pulse
              </div>
              <div style={{ fontSize: '15px', fontWeight: '700', color: '#E2C97E', marginTop: '5px', letterSpacing: '-0.02em' }}>
                {allocationViz === 'timeline' ? 'Ups & downs through time' : 'Allocation landscape'}
              </div>
            </div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-end' }}>
              <span style={{ fontSize: '9px', color: '#64748B', fontWeight: '700', letterSpacing: '0.08em', textTransform: 'uppercase' }}>View</span>
              <select
                value={allocationViz}
                onChange={(e) => setAllocationViz(e.target.value)}
                style={{
                  cursor: 'pointer', padding: '8px 36px 8px 12px', borderRadius: '10px',
                  border: '1px solid rgba(201,168,76,0.28)', backgroundColor: '#0A1020',
                  color: '#E8DFD0', fontSize: '12px', fontWeight: '600',
                  minWidth: '210px', outline: 'none',
                }}
              >
                <option value="timeline">Pulse — {valMode === MODES.ETH ? 'Ξ over time' : 'USD over time'}</option>
                <option value="pie">Slices — mix by %</option>
              </select>
            </label>
          </div>

          {allocationViz === 'timeline' ? (
            chartRows.length > 0 ? (
              <>
                <p style={{ fontSize: '11px', color: '#6B7E94', margin: '0 0 12px', lineHeight: 1.55 }}>
                  {histLen >= 2
                    ? 'Snapshots from the last 30 days.'
                    : histLen === 1
                      ? 'One history point on file; flat segment drawn for axis clarity.'
                      : bookUsd <= 0
                        ? 'Flat line at 0 — no tokens synced yet.'
                        : 'Live book value shown until more history accumulates.'}
                </p>
                <ResponsiveContainer width="100%" height={272}>
                  <ComposedChart data={chartRows} margin={{ top: 6, right: 10, left: 0, bottom: 2 }}>
                    <defs>
                      <linearGradient id={chartGradientId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%"   stopColor="#C9A84C" stopOpacity={0.62} />
                        <stop offset="45%"  stopColor="#627EEA" stopOpacity={0.22} />
                        <stop offset="100%" stopColor="#0D1628" stopOpacity={0}    />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="5 10" stroke="rgba(201,168,76,0.08)" vertical={false} />
                    <XAxis
                      type="number" dataKey="t" domain={['dataMin', 'dataMax']}
                      stroke="#4B5E72" tick={{ fontSize: 10, fill: '#8A9DB5' }}
                      tickFormatter={(ts) => {
                        const d = new Date(ts);
                        return Number.isFinite(d.getTime()) ? `${d.getMonth() + 1}/${d.getDate()}` : '—';
                      }}
                    />
                    <YAxis
                      domain={chartYDomain} stroke="#4B5E72"
                      tick={{ fontSize: 10, fill: '#8A9DB5' }}
                      tickFormatter={(v) => {
                        if (valMode === MODES.ETH) {
                          const eth = toEth(v);
                          if (eth >= 1e6) return `${(eth/1e6).toFixed(1)}MΞ`;
                          if (eth >= 1e3) return `${(eth/1e3).toFixed(0)}kΞ`;
                          return `${eth.toFixed(2)}Ξ`;
                        }
                        if (v >= 1e6) return `$${(v/1e6).toFixed(1)}M`;
                        if (v >= 1e3) return `$${(v/1e3).toFixed(0)}k`;
                        return `$${Math.round(v * 100) / 100}`;
                      }}
                      width={52}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'rgba(8,14,26,0.96)',
                        border: '1px solid rgba(201,168,76,0.3)',
                        borderRadius: '10px', color: '#F4EFE6', fontSize: '12px',
                      }}
                      labelFormatter={(ts) => {
                        const d = new Date(ts);
                        return Number.isFinite(d.getTime())
                          ? d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                          : '—';
                      }}
                      formatter={(val, name) => {
                        const map = { total: 'Total', ethUsd: 'ETH book', stUsd: 'Stables' };
                        const label   = map[name] || name;
                        const display = valMode === MODES.ETH
                          ? fmtValue(val, toEth(val), MODES.ETH)
                          : formatCurrency(val);
                        return [display, label];
                      }}
                    />
                    <Area
                      type="linear" dataKey="total" name="total"
                      stroke="#C9A84C" strokeWidth={2.4}
                      fill={`url(#${chartGradientId})`}
                      connectNulls
                      dot={chartRows.length <= 4 ? { r: 4, strokeWidth: 2, fill: '#C9A84C', stroke: '#0D1628' } : false}
                      activeDot={{ r: 6 }} isAnimationActive={false}
                    />
                    <Line type="linear" dataKey="ethUsd" name="ethUsd" stroke="#93A8FF" strokeWidth={1.8} dot={false} strokeDasharray="5 6" connectNulls isAnimationActive={false} />
                    <Line type="linear" dataKey="stUsd"  name="stUsd"  stroke="#4ADE80" strokeWidth={1.8} dot={false} strokeDasharray="3 6" connectNulls isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px 16px', justifyContent: 'center', marginTop: '10px', fontSize: '10px', color: '#8A9DB5' }}>
                  <span><span style={{ color: '#C9A84C', fontWeight: 800 }}>■ </span>{valMode === MODES.ETH ? 'Total (Ξ)' : 'Total USD'}</span>
                  <span><span style={{ color: '#93A8FF' }}>╌ </span>{valMode === MODES.ETH ? 'ETH book (Ξ)' : 'ETH book'}</span>
                  <span><span style={{ color: '#4ADE80' }}>╌ </span>{valMode === MODES.ETH ? 'Stablecoins (Ξ)' : 'Stablecoins'}</span>
                </div>
              </>
            ) : (
              <div style={{ textAlign: 'center', color: '#4B5E72', padding: '56px 16px', lineHeight: 1.65, fontSize: '13px' }}>
                No portfolio summary available for this entity.
              </div>
            )
          ) : (
            <ResponsiveContainer width="100%" height={272}>
              <PieChart>
                <Pie
                  data={pieDisplayData} cx="50%" cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: ${Number(value).toFixed(1)}%`}
                  outerRadius={88} innerRadius={28}
                  dataKey="value" paddingAngle={2} isAnimationActive={false}
                >
                  {pieDisplayData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} stroke="rgba(10,16,32,0.85)" strokeWidth={1} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#0D1628', border: '1px solid rgba(201,168,76,0.22)', borderRadius: '8px', color: '#E2D9C8' }}
                  formatter={(value) => `${Number(value).toFixed(2)}%`}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Intelligence Flags */}
        <div style={{
          background: 'linear-gradient(145deg, #101D32, #0D1628)',
          borderRadius: '16px',
          border: '1px solid rgba(201,168,76,0.12)',
          padding: '24px',
        }}>
          <div style={{ fontSize: '14px', fontWeight: '700', color: '#C9A84C', marginBottom: '16px' }}>
            Intelligence Flags
          </div>
          {flags.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {flags.map((flag, idx) => <FlagCard key={idx} flag={flag} />)}
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: '#4B5E72', padding: '48px 0' }}>
              No flags detected
            </div>
          )}
        </div>
      </div>

      {/* Asset Holdings Table */}
      <div style={{
        background: 'linear-gradient(145deg, #101D32, #0D1628)',
        borderRadius: '16px',
        border: '1px solid rgba(201,168,76,0.12)',
        overflow: 'hidden',
      }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid rgba(201,168,76,0.08)' }}>
          <div style={{ fontSize: '14px', fontWeight: '700', color: '#C9A84C' }}>
            Asset Holdings
            {entityType === 'address' && entityId && (
              <span style={{ marginLeft: '12px', fontSize: '11px', color: '#8A9DB5', fontWeight: '400' }}>
                • Showing data for selected address
              </span>
            )}
          </div>
        </div>

        {assets.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#0A1020', borderBottom: '1px solid rgba(201,168,76,0.08)' }}>
                  <TableHeader label="Token"       sortKey="token_symbol"    sortConfig={sortConfig} onSort={handleSort} />
                  <TableHeader label="Contract" />
                  <TableHeader label="Balance"     sortKey="balance"         sortConfig={sortConfig} onSort={handleSort} align="right" />
                  <TableHeader label={valMode === MODES.ETH ? 'Value (Ξ)' : 'USD Value'} sortKey="value_usd" sortConfig={sortConfig} onSort={handleSort} align="right" />
                  <TableHeader label="Portfolio %" sortKey="portfolio_percent" sortConfig={sortConfig} onSort={handleSort} align="right" />
                </tr>
              </thead>
              <tbody>
                {sortedAssets.map((asset, idx) => (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: idx < sortedAssets.length - 1 ? '1px solid rgba(201,168,76,0.05)' : 'none',
                      background: idx % 2 === 0 ? '#0D1628' : '#101D32',
                    }}
                  >
                    <td style={{ padding: '14px 24px', color: '#E2D9C8', fontSize: '13px', fontWeight: '600' }}>
                      {asset.token_symbol}
                    </td>
                    <td style={{ padding: '14px 24px', color: '#6B7E94', fontSize: '12px', fontFamily: 'monospace' }}>
                      {asset.token_contract
                        ? `${asset.token_contract.slice(0, 10)}...${asset.token_contract.slice(-8)}`
                        : '—'}
                    </td>
                    <td style={{ padding: '14px 24px', color: '#8A9DB5', fontSize: '13px', textAlign: 'right' }}>
                      {formatNumber(asset.balance)}
                    </td>
                    <td style={{ padding: '14px 24px', color: '#C9A84C', fontSize: '13px', fontWeight: '600', textAlign: 'right' }}>
                      {fv(asset.value_usd)}
                    </td>
                    <td style={{ padding: '14px 24px', color: '#8A9DB5', fontSize: '13px', textAlign: 'right' }}>
                      {asset.portfolio_percent.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: '48px', textAlign: 'center', color: '#4B5E72' }}>
            No assets found
          </div>
        )}
      </div>
    </div>
  );
};

// ── Sub-components ────────────────────────────────────────────────────────────

const SummaryCard = ({ label, value, icon, color }) => (
  <div style={{
    background: 'linear-gradient(145deg, #101D32, #0D1628)',
    borderRadius: '14px',
    border: '1px solid rgba(201,168,76,0.12)',
    padding: '20px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
  }}>
    <div style={{ fontSize: '24px', marginBottom: '8px' }}>{icon}</div>
    <div style={{ fontSize: '20px', fontWeight: '700', color, marginBottom: '4px', wordBreak: 'break-all' }}>
      {value}
    </div>
    <div style={{ fontSize: '11px', color: '#8A9DB5', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
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
      <div style={{ fontSize: '11px', color: '#8A9DB5', lineHeight: '1.5' }}>{flag.description}</div>
    </div>
  );
};

const TableHeader = ({ label, sortKey, sortConfig, onSort, align = 'left' }) => {
  const isSorted = sortConfig?.key === sortKey;
  const canSort  = !!sortKey;
  return (
    <th
      onClick={() => canSort && onSort(sortKey)}
      style={{
        padding: '12px 24px', fontSize: '11px', fontWeight: '800',
        color: '#6B7E94', textTransform: 'uppercase', letterSpacing: '0.1em',
        textAlign: align, cursor: canSort ? 'pointer' : 'default', userSelect: 'none',
      }}
    >
      {label}
      {canSort && (
        <span style={{ marginLeft: '6px', opacity: isSorted ? 1 : 0.3 }}>
          {isSorted && sortConfig.direction === 'desc' ? '↓' : '↑'}
        </span>
      )}
    </th>
  );
};

export default MarketValueAnalysis;
