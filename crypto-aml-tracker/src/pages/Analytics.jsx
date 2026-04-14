import { useEffect, useState } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { getAnalytics, getClustersSummary } from '../services/transactionService';
import Loader from '../components/common/Loader';

const StatCard = ({ label, value, sub, color }) => (
    <div style={{
        background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0',
        padding: '20px 24px', flex: 1, minWidth: '160px',
    }}>
        <div style={{ fontSize: '28px', fontWeight: '700', color: color || '#0f172a' }}>{value}</div>
        <div style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>{label}</div>
        {sub && <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>{sub}</div>}
    </div>
);

const ChartCard = ({ title, children }) => (
    <div style={{
        background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0',
        padding: '20px 24px',
    }}>
        <div style={{ fontSize: '14px', fontWeight: '600', color: '#0f172a', marginBottom: '16px' }}>
            {title}
        </div>
        {children}
    </div>
);

const formatEth = (value) => {
    const num = Number(value || 0);
    if (!Number.isFinite(num)) return '0';
    return num.toLocaleString(undefined, { maximumFractionDigits: 6 });
};

export default function Analytics() {
    const [data, setData] = useState(null);
    const [clusterSummary, setClusterSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        Promise.all([
            getAnalytics(),
            getClustersSummary().catch(() => null),
        ]).then(([d, cs]) => {
            setData(d);
            setClusterSummary(cs);
            setLoading(false);
        }).catch(e => { setError(e.message); setLoading(false); });
    }, []);

    if (loading) return <Loader />;
    if (error) return <div style={{ color: '#ef4444', padding: '1rem' }}>Error: {error}</div>;
    if (!data) return null;

    const highValuePct = data.totalTransactions > 0
        ? ((data.highValueTransactions / data.totalTransactions) * 100).toFixed(1)
        : 0;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* Stat cards */}
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                <StatCard label="Total Transactions" value={data.totalTransactions.toLocaleString()} />
                <StatCard label="High-Value Transactions" value={data.highValueTransactions.toLocaleString()}
                    sub={`${highValuePct}% of total`} color="#ef4444" />
                <StatCard label="Total ETH Volume" value={`${formatEth(data.totalEth)} ETH`} color="#3b82f6" />
                <StatCard label="Total Clusters"
                    value={clusterSummary?.total?.toLocaleString() || '—'} color="#22c55e" />
            </div>

            {/* Amount distribution */}
            <ChartCard title="Transaction Amount Distribution (ETH)">
                <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={data.amountBuckets} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="range" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 12 }} />
                        <Tooltip formatter={(v) => [`${v} txns`, 'Count']} />
                        <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                </ResponsiveContainer>
            </ChartCard>

            {/* Top clusters */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                <ChartCard title="Top Clusters by Balance">
                    {(data.topClustersByBalance || []).length === 0
                        ? <div style={{ color: '#94a3b8', padding: '40px 0', textAlign: 'center' }}>
                            No clusters yet — run clustering to populate this view.
                        </div>
                        : <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {data.topClustersByBalance.map((c, i) => (
                                <div key={c.cluster_id} style={{
                                    display: 'flex', alignItems: 'center', gap: '10px',
                                    padding: '8px 10px', borderRadius: '8px',
                                    background: '#f8fafc', border: '1px solid #e2e8f0',
                                }}>
                                    <div style={{
                                        width: '22px', height: '22px', borderRadius: '50%',
                                        background: '#3b82f6', color: '#fff',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        fontSize: '11px', fontWeight: '700', flexShrink: 0,
                                    }}>{i + 1}</div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ fontFamily: 'monospace', fontSize: '11px', color: '#475569', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {c.cluster_id}
                                        </div>
                                        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '3px' }}>
                                            {c.cluster_size} addresses
                                        </div>
                                    </div>
                                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                                        <div style={{ fontSize: '13px', fontWeight: '700', color: '#16a34a' }}>
                                            {formatEth(c.total_balance)} ETH
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    }
                </ChartCard>

                <ChartCard title="Top Clusters by Size">
                    {(data.topClustersBySize || []).length === 0
                        ? <div style={{ color: '#94a3b8', padding: '40px 0', textAlign: 'center' }}>
                            No clusters yet — run clustering to populate this view.
                        </div>
                        : <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {data.topClustersBySize.map((c, i) => (
                                <div key={c.cluster_id} style={{
                                    display: 'flex', alignItems: 'center', gap: '10px',
                                    padding: '8px 10px', borderRadius: '8px',
                                    background: '#f8fafc', border: '1px solid #e2e8f0',
                                }}>
                                    <div style={{
                                        width: '22px', height: '22px', borderRadius: '50%',
                                        background: '#0f172a', color: '#fff',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        fontSize: '11px', fontWeight: '700', flexShrink: 0,
                                    }}>{i + 1}</div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ fontFamily: 'monospace', fontSize: '11px', color: '#475569', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {c.cluster_id}
                                        </div>
                                        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '3px' }}>
                                            Balance: {formatEth(c.total_balance)} ETH
                                        </div>
                                    </div>
                                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                                        <div style={{ fontSize: '13px', fontWeight: '700', color: '#0f172a' }}>
                                            {c.cluster_size} addresses
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    }
                </ChartCard>
            </div>

        </div>
    );
}
