/**
 * Transaction Table — standalone ledger view.
 *
 * Features:
 *  - Full-width paginated table (20 rows/page)
 *  - Search by address or tx hash
 *  - Filter by risk level
 *  - "Investigate →" button on each row → opens graph page for that address
 */
import { useState, useEffect } from 'react';
import Loader from '../components/common/Loader';

const PAGE_SIZE = 20;

const th = {
  textAlign: 'left', padding: '11px 16px',
  borderBottom: '2px solid #e2e8f0',
  color: '#475569', fontSize: '11px', fontWeight: '600',
  textTransform: 'uppercase', letterSpacing: '0.05em',
  background: '#f1f5f9',
};
const td = {
  padding: '10px 16px', borderBottom: '1px solid #f1f5f9',
  fontSize: '12px', color: '#334155', fontFamily: 'monospace',
};

const riskColor = (label) => {
  if (label === 'High')   return { color: '#dc2626', background: '#fee2e2', border: '1px solid #fca5a5' };
  if (label === 'Medium') return { color: '#d97706', background: '#fef3c7', border: '1px solid #fde68a' };
  return { color: '#16a34a', background: '#dcfce7', border: '1px solid #86efac' };
};

const navBtn = (disabled) => ({
  padding: '7px 18px',
  background: disabled ? '#f1f5f9' : '#0d1b2e',
  color: disabled ? '#94a3b8' : '#fff',
  border: '1px solid ' + (disabled ? '#e2e8f0' : '#0d1b2e'),
  borderRadius: '7px',
  cursor: disabled ? 'not-allowed' : 'pointer',
  fontSize: '12px', fontWeight: '600',
});

const RISK_FILTERS = ['All', 'High', 'Medium', 'Low'];

export default function Dashboard({ transactions, loading, error, onInvestigate, lastUpdated }) {
  const [page, setPage]         = useState(0);
  const [search, setSearch]     = useState('');
  const [riskFilter, setRisk]   = useState('All');

  // Reset page when data or filters change
  useEffect(() => { setPage(0); }, [transactions, search, riskFilter]);

  if (loading) return <Loader />;
  if (error)   return <div style={{ color: '#ef4444', padding: '1.5rem' }}>Error: {error}</div>;

  // Filter
  const filtered = transactions.filter(tx => {
    const matchRisk   = riskFilter === 'All' || tx.riskLabel === riskFilter;
    const q           = search.toLowerCase();
    const matchSearch = !q || tx.hash?.toLowerCase().includes(q)
      || tx.sender?.toLowerCase().includes(q)
      || tx.receiver?.toLowerCase().includes(q);
    return matchRisk && matchSearch;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageTxs    = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>Transaction Ledger</div>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
            {filtered.length} transactions
            {riskFilter !== 'All' && ` · filtered by ${riskFilter} risk`}
            {search && ` · matching "${search}"`}
          </div>
        </div>
        {lastUpdated && (
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>
            Updated {lastUpdated.toLocaleTimeString()} · auto-refreshes every 30 min
          </span>
        )}
      </div>

      {/* ── Toolbar: search + risk filter ── */}
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Search by address or tx hash..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            flex: 1, minWidth: '240px', padding: '8px 12px',
            border: '1px solid #e2e8f0', borderRadius: '8px',
            fontSize: '13px', outline: 'none', background: '#fff',
          }}
        />
        <div style={{ display: 'flex', gap: '6px' }}>
          {RISK_FILTERS.map(f => (
            <button key={f} onClick={() => setRisk(f)} style={{
              padding: '7px 14px', borderRadius: '7px', fontSize: '12px', fontWeight: '600',
              cursor: 'pointer',
              background: riskFilter === f ? '#0d1b2e' : '#fff',
              color: riskFilter === f ? '#fff' : '#475569',
              border: '1px solid ' + (riskFilter === f ? '#0d1b2e' : '#e2e8f0'),
            }}>{f}</button>
          ))}
        </div>
      </div>

      {/* ── Table ── */}
      <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <thead>
            <tr>
              <th style={{ ...th, width: '16%' }}>Tx Hash</th>
              <th style={{ ...th, width: '22%' }}>From (Sender)</th>
              <th style={{ ...th, width: '22%' }}>To (Receiver)</th>
              <th style={{ ...th, width: '11%' }}>Amount</th>
              <th style={{ ...th, width: '15%' }}>Timestamp</th>
              <th style={{ ...th, width: '9%' }}>Risk</th>
              <th style={{ ...th, width: '5%' }}></th>
            </tr>
          </thead>
          <tbody>
            {pageTxs.length === 0
              ? <tr><td colSpan={7} style={{ ...td, textAlign: 'center', color: '#94a3b8', padding: '48px' }}>
                  No transactions match your filters.
                </td></tr>
              : pageTxs.map(tx => {
                const label = tx.riskLabel || 'Low';
                const score = tx.riskScore ?? 0;
                const rc    = riskColor(label);
                return (
                  <tr key={tx.hash}
                    onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}>
                    <td style={{ ...td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <a href={`https://etherscan.io/tx/${tx.hash}`} target="_blank" rel="noreferrer"
                        style={{ color: '#3b82f6', textDecoration: 'none' }} title={tx.hash}>
                        {tx.hash ? `${tx.hash.slice(0, 8)}...${tx.hash.slice(-6)}` : '—'}
                      </a>
                    </td>
                    <td style={{ ...td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={tx.sender}>{tx.sender}</td>
                    <td style={{ ...td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={tx.receiver}>{tx.receiver}</td>
                    <td style={{ ...td, color: '#16a34a', fontWeight: '600' }}>{tx.amount} ETH</td>
                    <td style={{ ...td, fontSize: '11px' }}>{tx.timestamp}</td>
                    <td style={td}>
                      <span style={{
                        ...rc, padding: '3px 8px', borderRadius: '999px',
                        fontSize: '11px', fontWeight: '700', fontFamily: 'sans-serif',
                      }}>
                        {score} {label}
                      </span>
                    </td>
                    <td style={{ ...td, textAlign: 'center' }}>
                      <button
                        onClick={() => onInvestigate(tx.sender)}
                        title={`Investigate ${tx.sender} in graph`}
                        style={{
                          padding: '4px 10px', background: '#eff6ff', color: '#1d4ed8',
                          border: '1px solid #bfdbfe', borderRadius: '6px',
                          cursor: 'pointer', fontSize: '11px', fontWeight: '600',
                          whiteSpace: 'nowrap',
                        }}>
                        🔍
                      </button>
                    </td>
                  </tr>
                );
              })
            }
          </tbody>
        </table>
      </div>

      {/* ── Pagination ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button style={navBtn(page === 0)} disabled={page === 0} onClick={() => setPage(p => p - 1)}>
          ← Back
        </button>
        <span style={{ fontSize: '13px', color: '#64748b' }}>
          Page <strong>{page + 1}</strong> of <strong>{totalPages}</strong>
          <span style={{ marginLeft: '10px', color: '#94a3b8', fontSize: '12px' }}>
            ({page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length})
          </span>
        </span>
        <button style={navBtn(page >= totalPages - 1)} disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>
          Next →
        </button>
      </div>

    </div>
  );
}
