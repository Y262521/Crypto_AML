import React from 'react';
import NetworkGraph from '../components/network/NetworkGraph';
import Loader from '../components/common/Loader';

const th = {
  textAlign: 'left', padding: '12px 16px',
  borderBottom: '2px solid #e2e8f0',
  color: '#475569', fontSize: '12px', fontWeight: '600',
  textTransform: 'uppercase', letterSpacing: '0.05em',
};
const td = {
  padding: '11px 16px', borderBottom: '1px solid #f1f5f9',
  fontSize: '12px', color: '#334155', fontFamily: 'monospace',
};

const riskColor = (label) => {
  if (label === 'High') return { color: '#dc2626', background: '#fee2e2' };
  if (label === 'Medium') return { color: '#d97706', background: '#fef3c7' };
  return { color: '#16a34a', background: '#dcfce7' };
};

const Dashboard = ({ activePage, transactions, loading, error, onRefresh, graphVersion, onAddressClick, searchAddress, onSearchChange }) => {
  if (loading) return <Loader />;
  if (error) return <div style={{ color: '#ef4444', padding: '1rem' }}>Error: {error}</div>;

  if (activePage === 'graph') {
    return <NetworkGraph graphVersion={graphVersion} onRefresh={onRefresh} searchAddress={searchAddress} onSearchChange={onSearchChange} />;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
        <button onClick={onRefresh} style={{
          padding: '8px 18px', background: '#0e032b', color: '#fff',
          border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '13px',
        }}>
          Refresh
        </button>
      </div>
      <div style={{
        background: '#fff', borderRadius: '12px',
        border: '1px solid #e2e8f0', overflow: 'hidden',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <thead>
            <tr style={{ background: '#e2e8f0' }}>
              <th style={{ ...th, width: '18%' }}>Tx Hash</th>
              <th style={{ ...th, width: '22%' }}>From (Sender)</th>
              <th style={{ ...th, width: '22%' }}>To (Receiver)</th>
              <th style={{ ...th, width: '12%' }}>Amount</th>
              <th style={{ ...th, width: '16%' }}>Timestamp</th>
              <th style={{ ...th, width: '10%' }}>Risk Score</th>
            </tr>
          </thead>
          <tbody>
            {transactions.length === 0
              ? <tr><td colSpan={6} style={{ ...td, textAlign: 'center', color: '#475569', padding: '32px' }}>No transactions found</td></tr>
              : transactions.map(tx => {
                const label = tx.riskLabel || 'Low';
                const score = tx.riskScore ?? 0;
                const rc = riskColor(label);
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
                    <td style={{ ...td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <span
                        onClick={() => onAddressClick(tx.sender)}
                        title={`Click to search in graph: ${tx.sender}`}
                        style={{ cursor: 'pointer', color: '#0f172a' }}
                        onMouseEnter={e => e.target.style.textDecoration = 'underline'}
                        onMouseLeave={e => e.target.style.textDecoration = 'none'}
                      >{tx.sender}</span>
                    </td>
                    <td style={{ ...td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <span
                        onClick={() => onAddressClick(tx.receiver)}
                        title={`Click to search in graph: ${tx.receiver}`}
                        style={{ cursor: 'pointer', color: '#0f172a' }}
                        onMouseEnter={e => e.target.style.textDecoration = 'underline'}
                        onMouseLeave={e => e.target.style.textDecoration = 'none'}
                      >{tx.receiver}</span>
                    </td>
                    <td style={{ ...td, color: '#16a34a' }}>{tx.amount} ETH</td>
                    <td style={td}>{tx.timestamp}</td>
                    <td style={td}>
                      <span style={{
                        ...rc, padding: '2px 8px', borderRadius: '999px',
                        fontSize: '11px', fontWeight: '600', fontFamily: 'sans-serif',
                      }}>
                        {score} {label}
                      </span>
                    </td>
                  </tr>
                );
              })
            }
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Dashboard;
