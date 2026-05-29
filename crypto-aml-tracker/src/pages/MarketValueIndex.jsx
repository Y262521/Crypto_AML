/**
 * MVRV Index — all pipeline addresses with full MVRV analytics.
 * Columns: Address, Entity Label, Market Value, Realized Value, MVRV Ratio,
 *          Unrealized PnL (%), Unrealized PnL ($), Avg Cost Basis, Realized PnL,
 *          ETH (Ξ), Last Activity, Method
 */

import { useCallback, useEffect, useState } from 'react';
import {
  useValuationMode,
  ValuationToggle,
  fmtValue,
  fmtPnl,
  MODES,
} from '../utils/valuationMode.jsx';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
const PAGE_SIZE = 15;

const fmt$ = (n) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(n || 0);

const fmtEth = (n) => {
  const v = Number(n);
  if (!Number.isFinite(v) || v === 0) return '0';
  if (v < 1e-4) return v.toExponential(2);
  return v.toLocaleString('en-US', { maximumFractionDigits: 4 });
};

const fmtTime = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return '—'; }
};

const ratioColor = (r) => {
  if (!r || r === 0) return '#64748B';
  if (r >= 1.5)  return '#4ADE80';
  if (r >= 1.0)  return '#86EFAC';
  if (r >= 0.7)  return '#FCA5A5';
  return '#F87171';
};

const pnlColor = (v) => (v > 0 ? '#4ADE80' : v < 0 ? '#F87171' : '#64748B');

const LABEL_COLORS = {
  'Whale':         { bg: 'rgba(139,92,246,0.15)', text: '#A78BFA' },
  'High Value':    { bg: 'rgba(201,168,76,0.15)',  text: '#C9A84C' },
  'Large Cluster': { bg: 'rgba(59,130,246,0.15)',  text: '#60A5FA' },
  'Cluster':       { bg: 'rgba(59,130,246,0.10)',  text: '#93C5FD' },
  'Individual':    { bg: 'rgba(100,116,139,0.12)', text: '#94A3B8' },
};

const labelStyle = (label) => {
  const c = LABEL_COLORS[label] || { bg: 'rgba(100,116,139,0.12)', text: '#94A3B8' };
  return {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: '6px',
    fontSize: '10px',
    fontWeight: '700',
    background: c.bg,
    color: c.text,
    whiteSpace: 'nowrap',
  };
};

const SORT_OPTIONS = [
  { value: 'market_value_usd',   label: 'Market Value ↓' },
  { value: 'mvrv_ratio',         label: 'MVRV Ratio ↓' },
  { value: 'unrealized_pnl_usd', label: 'Unrealized PnL ↓' },
  { value: 'realized_pnl_usd',   label: 'Realized PnL ↓' },
  { value: 'eth_total_units',    label: 'ETH Holdings ↓' },
  { value: 'updated_at',         label: 'Last Activity ↓' },
];

export default function MarketValueIndex({ onOpenWorkspace, onNavigateToGraph }) {
  const [items,     setItems]     = useState([]);
  const [total,     setTotal]     = useState(0);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);
  const [query,     setQuery]     = useState('');
  const [debounced, setDebounced] = useState('');
  const [page,      setPage]      = useState(0);
  const [sortCol,   setSortCol]   = useState('market_value_usd');
  const [sortOrder, setSortOrder] = useState('desc');

  const [valMode, setValMode] = useValuationMode();

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim().toLowerCase()), 280);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => { setPage(0); }, [debounced, sortCol, sortOrder]);

  const offset     = page * PAGE_SIZE;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const canPrev    = page > 0;
  const canNext    = (page + 1) * PAGE_SIZE < total;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        limit:  String(PAGE_SIZE),
        offset: String(offset),
        sort:   sortCol,
        order:  sortOrder,
      });
      if (debounced) params.set('q', debounced);
      const res = await fetch(`${API_BASE}/mvrv/directory?${params}`);
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const body = await res.json();
      setItems(body.items || []);
      setTotal(Number(body.total) || 0);
    } catch (e) {
      setError(e.message || 'Failed to load');
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [debounced, offset, sortCol, sortOrder]);

  useEffect(() => { load(); }, [load]);

  const openRow = (addr, e) => {
    if (!onOpenWorkspace) return;
    if (e.target.closest('button,a')) return;
    onOpenWorkspace(addr, 'address', 'MVRV Index', 'market-value');
  };

  const toggleSort = (col) => {
    if (sortCol === col) {
      setSortOrder(o => o === 'desc' ? 'asc' : 'desc');
    } else {
      setSortCol(col);
      setSortOrder('desc');
    }
  };

  const SortTh = ({ label, col, align = 'right' }) => {
    const active = sortCol === col;
    return (
      <th
        onClick={() => toggleSort(col)}
        style={{
          textAlign: align,
          padding: '12px 14px',
          color: active ? '#C9A84C' : '#64748B',
          fontSize: '10px', fontWeight: 800,
          letterSpacing: '0.1em', textTransform: 'uppercase',
          borderBottom: '1px solid rgba(201,168,76,0.1)',
          whiteSpace: 'nowrap', cursor: 'pointer', userSelect: 'none',
        }}
      >
        {label}
        <span style={{ marginLeft: '4px', opacity: active ? 1 : 0.3 }}>
          {active ? (sortOrder === 'desc' ? '↓' : '↑') : '↕'}
        </span>
      </th>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', minHeight: 0 }}>

      {/* ── Header ── */}
      <header style={{
        display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end',
        justifyContent: 'space-between', gap: '16px',
        padding: '22px 26px', borderRadius: '18px',
        border: '1px solid rgba(201,168,76,0.18)',
        background: 'linear-gradient(125deg, rgba(201,168,76,0.09), rgba(10,16,32,0.92))',
        boxShadow: '0 18px 48px rgba(0,0,0,0.35)',
      }}>
        <div>
          <div style={{ fontSize: '10px', fontWeight: 800, color: '#8A9DB5', letterSpacing: '0.16em', textTransform: 'uppercase' }}>
            Intelligence · Full Ledger
          </div>
          <h1 style={{ margin: '8px 0 0', fontSize: '22px', fontWeight: 800, color: '#E2C97E', letterSpacing: '-0.03em' }}>
            MVRV Index
          </h1>
          <p style={{ margin: '10px 0 0', maxWidth: '680px', fontSize: '13px', color: '#94A3B8', lineHeight: 1.55 }}>
            Every address in the AML pipeline ranked by{' '}
            <strong style={{ color: '#C9A84C' }}>MVRV ratio</strong> (Market Value ÷ Realized Value).
            {' '}<span style={{ color: '#4ADE80' }}>Green &gt; 1</span> = unrealized profit ·{' '}
            <span style={{ color: '#F87171' }}>Red &lt; 1</span> = unrealized loss.
            Click any row to open the full MVRV workspace.
          </p>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
          {/* Valuation mode toggle */}
          <ValuationToggle mode={valMode} onChange={setValMode} />

          {/* Sort selector */}
          <select
            value={`${sortCol}:${sortOrder}`}
            onChange={(e) => {
              const [col, ord] = e.target.value.split(':');
              setSortCol(col);
              setSortOrder(ord);
            }}
            style={{
              padding: '9px 12px', borderRadius: '10px',
              border: '1px solid rgba(201,168,76,0.22)',
              background: '#0A1020', color: '#E2D9C8',
              fontSize: '12px', outline: 'none', cursor: 'pointer',
            }}
          >
            {SORT_OPTIONS.map(o => (
              <option key={o.value + ':desc'} value={`${o.value}:desc`}>{o.label}</option>
            ))}
          </select>

          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter 0x…"
            style={{
              width: 'min(260px, 88vw)', padding: '10px 14px',
              borderRadius: '10px', border: '1px solid rgba(201,168,76,0.22)',
              background: '#0A1020', color: '#E2D9C8', fontSize: '13px', outline: 'none',
            }}
          />
          <button
            type="button" onClick={load}
            style={{
              padding: '10px 18px', borderRadius: '10px',
              border: '1px solid rgba(201,168,76,0.35)',
              background: 'rgba(201,168,76,0.12)', color: '#E2C97E',
              fontWeight: 700, fontSize: '12px', cursor: 'pointer',
            }}
          >
            ⟳ Refresh
          </button>
        </div>
      </header>

      {error && (
        <div style={{ padding: '14px 18px', borderRadius: '12px', border: '1px solid rgba(248,113,113,0.35)', background: 'rgba(248,113,113,0.08)', color: '#FCA5A5', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {/* ── Table card ── */}
      <div style={{
        flex: 1, minHeight: '420px', borderRadius: '16px',
        border: '1px solid rgba(201,168,76,0.12)',
        background: 'linear-gradient(180deg, #101D32, #0A1020)',
        overflow: 'hidden', display: 'flex', flexDirection: 'column',
      }}>
        {/* Table toolbar */}
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid rgba(201,168,76,0.1)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          flexWrap: 'wrap', gap: '10px',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: '#C9A84C' }}>
              Addresses · MVRV Analysis
            </span>
            <span style={{ fontSize: '10px', color: '#64748B' }}>
              Page {page + 1} of {totalPages}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', color: '#64748B' }}>
              {loading ? 'Loading…' : total === 0 ? '0 addresses' : `${offset + 1}–${offset + items.length} of ${total}`}
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              {[
                { label: '← Prev', disabled: !canPrev || loading, onClick: () => setPage(p => Math.max(0, p - 1)) },
                { label: 'Next →', disabled: !canNext || loading, onClick: () => setPage(p => p + 1) },
              ].map(btn => (
                <button
                  key={btn.label} type="button"
                  disabled={btn.disabled} onClick={btn.onClick}
                  style={{
                    padding: '8px 16px', borderRadius: '8px',
                    border: '1px solid rgba(201,168,76,0.25)',
                    background: btn.disabled ? 'rgba(30,41,59,0.5)' : 'rgba(201,168,76,0.1)',
                    color: btn.disabled ? '#475569' : '#E2C97E',
                    fontWeight: 700, fontSize: '12px',
                    cursor: btn.disabled ? 'not-allowed' : 'pointer',
                  }}
                >
                  {btn.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Scrollable table */}
        <div style={{ overflow: 'auto', flex: 1 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: '#070d18', position: 'sticky', top: 0, zIndex: 1 }}>
                <th style={{ textAlign: 'left', padding: '12px 14px', color: '#64748B', fontSize: '10px', fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', borderBottom: '1px solid rgba(201,168,76,0.1)', whiteSpace: 'nowrap' }}>
                  Address / Label
                </th>
                <SortTh label={valMode === MODES.ETH ? 'Market Value (Ξ)' : 'Market Value'}    col="market_value_usd" />
                <SortTh label={valMode === MODES.ETH ? 'Realized Value (Ξ)' : 'Realized Value'}  col="market_value_usd" />
                <SortTh label="MVRV Ratio"      col="mvrv_ratio" />
                <SortTh label="Unreal. PnL %"   col="unrealized_pnl_usd" />
                <SortTh label={valMode === MODES.ETH ? 'Unreal. PnL (Ξ)' : 'Unreal. PnL $'}   col="unrealized_pnl_usd" />
                <SortTh label={valMode === MODES.ETH ? 'Realized PnL (Ξ)' : 'Realized PnL'}    col="realized_pnl_usd" />
                <SortTh label="ETH (Ξ)"         col="eth_total_units" />
                <SortTh label="Last Activity"   col="updated_at" />
                <th style={{ textAlign: 'right', padding: '12px 14px', color: '#64748B', fontSize: '10px', fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', borderBottom: '1px solid rgba(201,168,76,0.1)', whiteSpace: 'nowrap' }}>
                  Method
                </th>
              </tr>
            </thead>
            <tbody>
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={10} style={{ padding: '48px 20px', textAlign: 'center', color: '#64748B' }}>
                    No addresses found. Run the ETL pipeline or adjust your filter.
                  </td>
                </tr>
              )}
              {loading && items.length === 0 && (
                <tr>
                  <td colSpan={10} style={{ padding: '48px 20px', textAlign: 'center', color: '#64748B' }}>
                    Loading…
                  </td>
                </tr>
              )}
              {items.map((row, idx) => {
                const ratio   = row.mvrv_ratio || 0;
                const upnl    = row.unrealized_pnl_usd || 0;
                const upnlPct = row.unrealized_pnl_pct || 0;
                const rpnl    = row.realized_pnl_usd || 0;
                const hasSnap = row.mvrv_snapshot_at != null;

                // Per-row ETH conversion using eth_total_units as the ETH proxy for market_value_usd
                const ethUnits  = Number(row.eth_total_units) || 0;
                const mvUsd     = Number(row.market_value_usd) || 0;
                const ethPerUsd = mvUsd > 0 && ethUnits > 0 ? ethUnits / mvUsd : 0;
                const rowToEth  = (usd) => ethPerUsd > 0 ? usd * ethPerUsd : 0;
                const rowFv     = (usd) => fmtValue(usd, rowToEth(usd), valMode);
                const rowFp     = (usd) => fmtPnl(usd, rowToEth(usd), valMode);

                return (
                  <tr
                    key={row.address}
                    onClick={(e) => openRow(row.address, e)}
                    style={{
                      background: idx % 2 === 0 ? 'rgba(13,22,40,0.55)' : 'rgba(16,29,50,0.35)',
                      borderBottom: '1px solid rgba(201,168,76,0.05)',
                      cursor: onOpenWorkspace ? 'pointer' : 'default',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(201,168,76,0.05)'}
                    onMouseLeave={e => e.currentTarget.style.background = idx % 2 === 0 ? 'rgba(13,22,40,0.55)' : 'rgba(16,29,50,0.35)'}
                  >
                    {/* Address + label + actions */}
                    <td style={{ padding: '12px 14px', fontFamily: 'ui-monospace, monospace', color: '#E2D9C8', minWidth: '200px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                        <span style={{ fontSize: '12px' }}>
                          {row.address.slice(0, 10)}…{row.address.slice(-8)}
                        </span>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
                          <span style={labelStyle(row.entity_label || 'Individual')}>
                            {row.entity_label || 'Individual'}
                          </span>
                          {onOpenWorkspace && (
                            <button
                              type="button"
                              onClick={() => onOpenWorkspace(row.address, 'address', 'MVRV Index', 'market-value')}
                              style={{ padding: '2px 8px', fontSize: '10px', fontWeight: 700, borderRadius: '5px', border: '1px solid rgba(201,168,76,0.35)', background: 'rgba(201,168,76,0.1)', color: '#E2C97E', cursor: 'pointer' }}
                            >
                              MVRV
                            </button>
                          )}
                          {onNavigateToGraph && (
                            <button
                              type="button"
                              onClick={() => onNavigateToGraph(row.address)}
                              style={{ padding: '2px 8px', fontSize: '10px', fontWeight: 700, borderRadius: '5px', border: '1px solid rgba(148,163,184,0.35)', background: 'transparent', color: '#94A3B8', cursor: 'pointer' }}
                            >
                              Graph
                            </button>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Market Value */}
                    <td style={{ padding: '12px 14px', textAlign: 'right', color: '#C9A84C', fontWeight: 700, whiteSpace: 'nowrap' }}>
                      {rowFv(row.market_value_usd)}
                    </td>

                    {/* Realized Value */}
                    <td style={{ padding: '12px 14px', textAlign: 'right', color: hasSnap ? '#627EEA' : '#4B5E72', whiteSpace: 'nowrap' }}>
                      {hasSnap ? rowFv(row.realized_value_usd) : '—'}
                    </td>

                    {/* MVRV Ratio — dimensionless, same in both modes */}
                    <td style={{ padding: '12px 14px', textAlign: 'right', fontWeight: 700, fontFamily: 'monospace', color: hasSnap && ratio != null ? ratioColor(ratio) : '#4B5E72', whiteSpace: 'nowrap' }}>
                      {hasSnap && ratio != null ? ratio.toFixed(3) : '—'}
                    </td>

                    {/* Unrealized PnL % */}
                    <td style={{ padding: '12px 14px', textAlign: 'right', color: hasSnap ? pnlColor(upnlPct) : '#4B5E72', whiteSpace: 'nowrap' }}>
                      {hasSnap ? `${upnlPct >= 0 ? '+' : ''}${upnlPct.toFixed(2)}%` : '—'}
                    </td>

                    {/* Unrealized PnL $ / Ξ */}
                    <td style={{ padding: '12px 14px', textAlign: 'right', color: hasSnap ? pnlColor(upnl) : '#4B5E72', fontWeight: 600, whiteSpace: 'nowrap' }}>
                      {hasSnap ? rowFp(upnl) : '—'}
                    </td>

                    {/* Realized PnL */}
                    <td style={{ padding: '12px 14px', textAlign: 'right', color: hasSnap ? pnlColor(rpnl) : '#4B5E72', whiteSpace: 'nowrap' }}>
                      {hasSnap ? rowFp(rpnl) : '—'}
                    </td>

                    {/* ETH — highlighted as primary column in ETH mode */}
                    <td style={{ padding: '12px 14px', textAlign: 'right', color: valMode === MODES.ETH ? '#C9A84C' : '#93A8FF', fontWeight: valMode === MODES.ETH ? 700 : 400, whiteSpace: 'nowrap' }}>
                      {fmtEth(row.eth_total_units)} Ξ
                    </td>

                    {/* Last Activity */}
                    <td style={{ padding: '12px 14px', textAlign: 'right', color: '#64748B', whiteSpace: 'nowrap', fontSize: '11px' }}>
                      {fmtTime(row.updated_at)}
                    </td>

                    {/* Accounting Method */}
                    <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                      {hasSnap ? (
                        <span style={{
                          display: 'inline-block', padding: '2px 7px',
                          borderRadius: '5px', fontSize: '10px', fontWeight: 700,
                          background: 'rgba(139,92,246,0.12)', color: '#A78BFA',
                        }}>
                          {row.accounting_method || 'FIFO'}
                        </span>
                      ) : (
                        <span style={{ color: '#4B5E72', fontSize: '11px' }}>—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
