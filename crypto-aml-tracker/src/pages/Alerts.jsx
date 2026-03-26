import { useEffect, useState } from 'react';
import { getAlerts } from '../services/transactionService';
import Loader from '../components/common/Loader';

const CLUSTER_COLORS = {
    'Multi-Signal': { bg: '#fef2f2', border: '#fca5a5', text: '#991b1b' },
    'High Value': { bg: '#fff7ed', border: '#fdba74', text: '#9a3412' },
    'Fan-Out': { bg: '#fdf4ff', border: '#d8b4fe', text: '#6b21a8' },
    'High Velocity': { bg: '#eff6ff', border: '#93c5fd', text: '#1e40af' },
    'Contract Call': { bg: '#f0fdf4', border: '#86efac', text: '#166534' },
    'New Counterparty + High Value': { bg: '#fefce8', border: '#fde047', text: '#854d0e' },
};

const riskColor = (label) => {
    if (label === 'High') return { color: '#dc2626', background: '#fee2e2' };
    if (label === 'Medium') return { color: '#d97706', background: '#fef3c7' };
    return { color: '#16a34a', background: '#dcfce7' };
};

const th = {
    textAlign: 'left', padding: '10px 14px',
    borderBottom: '2px solid #e2e8f0',
    color: '#475569', fontSize: '11px', fontWeight: '600',
    textTransform: 'uppercase', letterSpacing: '0.05em',
};
const td = {
    padding: '10px 14px', borderBottom: '1px solid #f1f5f9',
    fontSize: '12px', color: '#334155', fontFamily: 'monospace',
};

const CLUSTER_ORDER = [
    'Multi-Signal', 'High Value', 'Fan-Out',
    'High Velocity', 'New Counterparty + High Value', 'Contract Call',
];

export default function Alerts({ onAddressClick }) {
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [filter, setFilter] = useState('All');

    useEffect(() => {
        getAlerts()
            .then(data => { setAlerts(data); setLoading(false); })
            .catch(err => { setError(err.message); setLoading(false); });
    }, []);

    if (loading) return <Loader />;
    if (error) return <div style={{ color: '#ef4444', padding: '1rem' }}>Error: {error}</div>;

    const filtered = filter === 'All' ? alerts : alerts.filter(a => a.clusterName === filter);

    // Summary counts per cluster
    const summary = {};
    alerts.forEach(a => {
        summary[a.clusterName] = (summary[a.clusterName] || 0) + 1;
    });

    return (
        <div>
            {/* Summary cards */}
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '20px' }}>
                {CLUSTER_ORDER.filter(c => summary[c]).map(cluster => {
                    const colors = CLUSTER_COLORS[cluster] || { bg: '#f8fafc', border: '#e2e8f0', text: '#334155' };
                    return (
                        <div key={cluster}
                            onClick={() => setFilter(filter === cluster ? 'All' : cluster)}
                            style={{
                                background: colors.bg, border: `1px solid ${colors.border}`,
                                borderRadius: '10px', padding: '12px 16px', cursor: 'pointer',
                                minWidth: '140px', opacity: filter !== 'All' && filter !== cluster ? 0.5 : 1,
                            }}>
                            <div style={{ fontSize: '22px', fontWeight: '700', color: colors.text }}>
                                {summary[cluster]}
                            </div>
                            <div style={{ fontSize: '11px', color: colors.text, marginTop: '2px' }}>
                                {cluster}
                            </div>
                        </div>
                    );
                })}
                <div
                    onClick={() => setFilter('All')}
                    style={{
                        background: '#f8fafc', border: '1px solid #e2e8f0',
                        borderRadius: '10px', padding: '12px 16px', cursor: 'pointer',
                        minWidth: '140px', opacity: filter === 'All' ? 1 : 0.5,
                    }}>
                    <div style={{ fontSize: '22px', fontWeight: '700', color: '#334155' }}>
                        {alerts.length}
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Total Alerts</div>
                </div>
            </div>

            {/* Alerts table */}
            <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
                    <thead>
                        <tr style={{ background: '#e2e8f0' }}>
                            <th style={{ ...th, width: '14%' }}>Tx Hash</th>
                            <th style={{ ...th, width: '18%' }}>Sender</th>
                            <th style={{ ...th, width: '18%' }}>Receiver</th>
                            <th style={{ ...th, width: '10%' }}>Amount</th>
                            <th style={{ ...th, width: '10%' }}>Risk</th>
                            <th style={{ ...th, width: '16%' }}>Cluster</th>
                            <th style={{ ...th, width: '14%' }}>Reasons</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.length === 0
                            ? <tr><td colSpan={7} style={{ ...td, textAlign: 'center', padding: '32px', color: '#64748b' }}>
                                No alerts found
                            </td></tr>
                            : filtered.map((alert, i) => {
                                const rc = riskColor(alert.riskLabel);
                                const cc = CLUSTER_COLORS[alert.clusterName] || { bg: '#f8fafc', border: '#e2e8f0', text: '#334155' };
                                return (
                                    <tr key={alert.hash || i}
                                        onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
                                        onMouseLeave={e => e.currentTarget.style.background = ''}>
                                        <td style={{ ...td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            <a href={`https://etherscan.io/tx/${alert.hash}`} target="_blank" rel="noreferrer"
                                                style={{ color: '#3b82f6', textDecoration: 'none' }} title={alert.hash}>
                                                {alert.hash ? `${alert.hash.slice(0, 8)}...${alert.hash.slice(-6)}` : '—'}
                                            </a>
                                        </td>
                                        <td style={{ ...td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            <span onClick={() => onAddressClick && onAddressClick(alert.sender)}
                                                style={{ cursor: 'pointer' }}
                                                title={alert.sender}
                                                onMouseEnter={e => e.target.style.textDecoration = 'underline'}
                                                onMouseLeave={e => e.target.style.textDecoration = 'none'}>
                                                {alert.sender}
                                            </span>
                                        </td>
                                        <td style={{ ...td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            <span onClick={() => onAddressClick && onAddressClick(alert.receiver)}
                                                style={{ cursor: 'pointer' }}
                                                title={alert.receiver}
                                                onMouseEnter={e => e.target.style.textDecoration = 'underline'}
                                                onMouseLeave={e => e.target.style.textDecoration = 'none'}>
                                                {alert.receiver}
                                            </span>
                                        </td>
                                        <td style={{ ...td, color: '#16a34a' }}>{alert.amount} ETH</td>
                                        <td style={td}>
                                            <span style={{ ...rc, padding: '2px 8px', borderRadius: '999px', fontSize: '11px', fontWeight: '600', fontFamily: 'sans-serif' }}>
                                                {alert.riskScore} {alert.riskLabel}
                                            </span>
                                        </td>
                                        <td style={td}>
                                            <span style={{
                                                background: cc.bg, color: cc.text, border: `1px solid ${cc.border}`,
                                                padding: '2px 8px', borderRadius: '999px', fontSize: '11px', fontWeight: '600', fontFamily: 'sans-serif',
                                                whiteSpace: 'nowrap',
                                            }}>
                                                {alert.clusterName}
                                            </span>
                                        </td>
                                        <td style={{ ...td, fontSize: '11px', color: '#64748b' }}>
                                            {(alert.reasons || []).join(', ')}
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
}
