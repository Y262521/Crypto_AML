/**
 * Transaction Table — NBE Institutional Theme
 */
import { useState } from 'react';
import Loader from '../components/common/Loader';

const PAGE_SIZE = 20;
const HIGH_VALUE_THRESHOLD = Number(import.meta.env.VITE_HIGH_VALUE_THRESHOLD_ETH || 10);

// ── NBE color tokens ──────────────────────────────────────────
const S = {
  surface1: '#0D1628',
  surface2: '#101D32',
  surface3: '#132240',
  border: 'rgba(201,168,76,0.12)',
  borderHov: 'rgba(201,168,76,0.30)',
  gold: '#C9A84C',
  goldSoft: '#B8963E',
  goldGlow: 'rgba(201,168,76,0.08)',
  goldGlowMd: 'rgba(201,168,76,0.14)',
  textPrimary: '#E2D9C8',
  textSecondary: '#8A9DB5',
  textMuted: '#4B5E72',
  textGold: '#C8B98A',
};

const riskStyle = (label) => {
  if (label === 'High') return { color: '#F87171', background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.28)' };
  if (label === 'Medium') return { color: '#FBBF24', background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.28)' };
  return { color: '#4ADE80', background: 'rgba(74,222,128,0.10)', border: '1px solid rgba(74,222,128,0.25)' };
};

const scoreFromAmount = (amount) => {
  const value = Number(amount || 0);
  if (!Number.isFinite(value) || HIGH_VALUE_THRESHOLD <= 0) return 0;
  const ratio = value / HIGH_VALUE_THRESHOLD;
  if (ratio >= 2) return 100;
  if (ratio >= 1) return Math.round((75 + 25 * (ratio - 1)) * 10) / 10;
  return Math.round(Math.min(75, 75 * ratio) * 10) / 10;
};
const labelFromAmount = (amount) => {
  const s = scoreFromAmount(amount);
  if (s > 75) return 'High';
  if (s > 40) return 'Medium';
  return 'Low';
};

const RISK_FILTERS = ['All', 'High', 'Medium', 'Low'];

const th = {
  textAlign: 'left', padding: '11px 16px',
  borderBottom: `1px solid rgba(201,168,76,0.10)`,
  color: '#4B5E72', fontSize: '11px', fontWeight: '700',
  textTransform: 'uppercase', letterSpacing: '0.07em',
  background: 'rgba(201,168,76,0.04)',
};
const td = {
  padding: '10px 16px',
  borderBottom: '1px solid rgba(201,168,76,0.06)',
  fontSize: '12px', color: '#8A9DB5', fontFamily: 'monospace',
};

export default function Dashboard({
  transactions, loading, loadingMore, error,
  onInvestigate, onLoadMore, lastUpdated, totalTransactions = 0,
}) {
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [riskFilter, setRisk] = useState('All');

  if (loading) return <Loader />;
  if (error) return <div style={{ color: '#F87171', padding: '1.5rem' }}>Error: {error}</div>;

  const filtered = transactions.filter(tx => {
    const derived = labelFromAmount(tx.amount);
    const matchRisk = riskFilter === 'All' || derived === riskFilter;
    const q = search.toLowerCase();
    const matchSearch = !q || tx.hash?.toLowerCase().includes(q)
      || tx.sender?.toLowerCase().includes(q)
      || tx.receiver?.toLowerCase().includes(q);
    return matchRisk && matchSearch;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visiblePage = Math.min(page, totalPages - 1);
  const pageTxs = filtered.slice(visiblePage * PAGE_SIZE, (visiblePage + 1) * PAGE_SIZE);

  const navBtn = (disabled) => ({
    padding: '7px 18px',
    background: disabled ? 'transparent' : S.goldGlowMd,
    color: disabled ? S.textMuted : S.textGold,
    border: `1px solid ${disabled ? 'rgba(255,255,255,0.06)' : S.borderHov}`,
    borderRadius: '8px', cursor: disabled ? 'not-allowed' : 'pointer',
    fontSize: '12px', fontWeight: '700', transition: 'all 0.15s',
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Header */}
      <div style={{
        background: `linear-gradient(135deg, ${S.surface1} 0%, ${S.surface3} 100%)`,
        border: `1px solid ${S.border}`,
        borderRadius: '16px', padding: '24px 28px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(201,168,76,0.08)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px',
      }}>
        <div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: S.textGold }}>Transaction Ledger</div>
          <div style={{ fontSize: '12px', color: S.textSecondary, marginTop: '4px' }}>
            {transactions.length.toLocaleString()} of {(totalTransactions || transactions.length).toLocaleString()} transactions
            {' · ordered by highest ETH amount'}
            {filtered.length !== transactions.length && ` · ${filtered.length.toLocaleString()} visible`}
          </div>
        </div>
        {lastUpdated && (
          <span style={{ fontSize: '11px', color: S.textMuted }}>
            Updated {lastUpdated.toLocaleTimeString()} · auto-refreshes every 30 min
          </span>
        )}
      </div>

      {/* Toolbar */}
      <div style={{
        background: `linear-gradient(145deg, ${S.surface2}, ${S.surface1})`,
        border: `1px solid ${S.border}`, borderRadius: '14px',
        padding: '12px 16px', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap',
      }}>
        <input
          type="text" placeholder="Search by address or tx hash..."
          value={search} onChange={e => { setSearch(e.target.value); setPage(0); }}
          style={{
            flex: 1, minWidth: '240px', padding: '8px 12px',
            background: 'rgba(10,16,32,0.8)', border: `1px solid rgba(201,168,76,0.18)`,
            borderRadius: '8px', fontSize: '13px', outline: 'none',
            color: S.textPrimary,
          }}
        />
        <div style={{ display: 'flex', gap: '6px' }}>
          {RISK_FILTERS.map(f => (
            <button key={f} onClick={() => { setRisk(f); setPage(0); }} style={{
              padding: '7px 14px', borderRadius: '7px', fontSize: '12px', fontWeight: '700',
              cursor: 'pointer', transition: 'all 0.15s',
              background: riskFilter === f ? S.goldGlowMd : 'transparent',
              color: riskFilter === f ? S.textGold : S.textSecondary,
              border: `1px solid ${riskFilter === f ? S.borderHov : 'rgba(255,255,255,0.08)'}`,
            }}>{f}</button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div style={{
        background: `linear-gradient(180deg, ${S.surface2} 0%, ${S.surface1} 100%)`,
        border: `1px solid ${S.border}`, borderRadius: '14px', overflow: 'hidden',
        boxShadow: '0 8px 32px rgba(0,0,0,0.35)',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <thead>
            <tr>
              <th style={{ ...th, width: '16%' }}>Tx Hash</th>
              <th style={{ ...th, width: '22%' }}>From</th>
              <th style={{ ...th, width: '22%' }}>To</th>
              <th style={{ ...th, width: '11%' }}>Amount</th>
              <th style={{ ...th, width: '15%' }}>Timestamp</th>
              <th style={{ ...th, width: '9%' }}>Risk</th>
              <th style={{ ...th, width: '5%' }}></th>
            </tr>
          </thead>
          <tbody>
            {pageTxs.length === 0
              ? <tr><td colSpan={7} style={{ ...td, textAlign: 'center', color: S.textMuted, padding: '48px' }}>
                No transactions match your filters.
              </td></tr>
              : pageTxs.map((tx, idx) => {
                const score = scoreFromAmount(tx.amount);
                const label = labelFromAmount(tx.amount);
                const rc = riskStyle(label);
                return (
                  <tr key={tx.hash}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(201,168,76,0.04)'}
                    onMouseLeave={e => e.currentTarget.style.background = idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)'}
                    style={{ background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}
                  >
                    <td style={{ ...td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <a href={`https://etherscan.io/tx/${tx.hash}`} target="_blank" rel="noreferrer"
                        style={{ color: '#60A5FA', textDecoration: 'none' }} title={tx.hash}>
                        {tx.hash ? `${tx.hash.slice(0, 8)}...${tx.hash.slice(-6)}` : '—'}
                      </a>
                    </td>
                    <td style={{ ...td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={tx.sender}>
                      <span onClick={() => onInvestigate(tx.sender)}
                        style={{ color: S.goldSoft, textDecoration: 'underline', cursor: 'pointer', textUnderlineOffset: '2px' }}>
                        {tx.sender}
                      </span>
                    </td>
                    <td style={{ ...td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={tx.receiver}>
                      <span onClick={() => onInvestigate(tx.receiver)}
                        style={{ color: S.goldSoft, textDecoration: 'underline', cursor: 'pointer', textUnderlineOffset: '2px' }}>
                        {tx.receiver}
                      </span>
                    </td>
                    <td style={{ ...td, color: '#4ADE80', fontWeight: '700' }}>{tx.amount} ETH</td>
                    <td style={{ ...td, fontSize: '11px', color: '#C9A84C' }}>{tx.timestamp}</td>
                    <td style={td}>
                      <span style={{ ...rc, padding: '3px 8px', borderRadius: '999px', fontSize: '11px', fontWeight: '700', fontFamily: 'sans-serif' }}>
                        {score} {label}
                      </span>
                    </td>
                    <td style={{ ...td, textAlign: 'center' }}>
                      <button onClick={() => onInvestigate(tx.sender)} title={`Investigate ${tx.sender}`}
                        style={{
                          padding: '4px 10px', background: S.goldGlow, color: S.gold,
                          border: `1px solid rgba(201,168,76,0.22)`, borderRadius: '6px',
                          cursor: 'pointer', fontSize: '11px', fontWeight: '700',
                        }}>🔍</button>
                    </td>
                  </tr>
                );
              })
            }
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button style={navBtn(visiblePage === 0)} disabled={visiblePage === 0} onClick={() => setPage(p => p - 1)}>← Back</button>
        <span style={{ fontSize: '13px', color: S.textSecondary }}>
          Page <strong style={{ color: S.textGold }}>{visiblePage + 1}</strong> of <strong style={{ color: S.textGold }}>{totalPages}</strong>
          <span style={{ marginLeft: '10px', color: S.textMuted, fontSize: '12px' }}>
            ({visiblePage * PAGE_SIZE + 1}–{Math.min((visiblePage + 1) * PAGE_SIZE, filtered.length)} of {filtered.length})
          </span>
        </span>
        <button style={navBtn(visiblePage >= totalPages - 1)} disabled={visiblePage >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next →</button>
      </div>

      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <button
          onClick={onLoadMore}
          disabled={loadingMore || transactions.length >= totalTransactions}
          style={{
            padding: '9px 20px',
            background: (loadingMore || transactions.length >= totalTransactions) ? 'transparent' : S.goldGlowMd,
            color: (loadingMore || transactions.length >= totalTransactions) ? S.textMuted : S.textGold,
            border: `1px solid ${(loadingMore || transactions.length >= totalTransactions) ? 'rgba(255,255,255,0.06)' : S.borderHov}`,
            borderRadius: '8px', cursor: (loadingMore || transactions.length >= totalTransactions) ? 'not-allowed' : 'pointer',
            fontSize: '12px', fontWeight: '700',
          }}
        >
          {transactions.length >= totalTransactions ? 'All transactions loaded' : loadingMore ? 'Loading more...' : 'Load More From Database'}
        </button>
      </div>
    </div>
  );
}
