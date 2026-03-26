import { useEffect, useState } from 'react';
import {
    PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
    BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts';
import { getAnalytics } from '../services/transactionService';
import Loader from '../components/common/Loader';

const RISK_COLORS = { Low: '#22c55e', Medium: '#f59e0b', High: '#ef4444' };
const CLUSTER_COLORS = [
    '#ef4444', '#f97316', '#a855f7', '#3b82f6', '#06b6d4', '#84cc16',
];

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

export default function Analytics() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        getAnalytics()
            .then(d => { setData(d); setLoading(false); })
            .catch(e => { setError(e.message); setLoading(false); });
    }, []);

    if (loading) return <Loader />;
    if (error) return <div style={{ color: '#ef4444', padding: '1rem' }}>Error: {error}</div>;
    if (!data) return null;

    const flaggedPct = data.totalTransactions > 0
        ? ((data.totalFlagged / data.totalTransactions) * 100).toFixed(1)
        : 0;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* Stat cards */}
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                <StatCard label="Total Transactions" value={data.totalTransactions.toLocaleString()} />
                <StatCard label="Flagged Transactions" value={data.totalFlagged.toLocaleString()}
                    sub={`${flaggedPct}% of total`} color="#ef4444" />
                <StatCard label="Total ETH Volume" value={`${data.totalEth.toLocaleString()} ETH`}
                    color="#3b82f6" />
                <StatCard label="Clean Transactions"
                    value={(data.totalTransactions - data.totalFlagged).toLocaleString()}
                    color="#22c55e" />
            </div>

            {/* Row 1: Risk distribution + Cluster breakdown */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

                <ChartCard title="Risk Score Distribution">
                    <ResponsiveContainer width="100%" height={260}>
                        <PieChart>
                            <Pie data={data.riskDistribution} dataKey="value" nameKey="name"
                                cx="50%" cy="50%" outerRadius={90} label={({ name, percent }) =>
                                    `${name} ${(percent * 100).toFixed(0)}%`
                                }>
                                {data.riskDistribution.map((entry) => (
                                    <Cell key={entry.name} fill={RISK_COLORS[entry.name] || '#94a3b8'} />
                                ))}
                            </Pie>
                            <Tooltip formatter={(v) => [`${v} txns`, '']} />
                            <Legend />
                        </PieChart>
                    </ResponsiveContainer>
                </ChartCard>

                <ChartCard title="AML Cluster Breakdown">
                    {data.clusterBreakdown.length === 0
                        ? <div style={{ color: '#94a3b8', padding: '60px 0', textAlign: 'center' }}>
                            No flagged clusters detected
                        </div>
                        : <ResponsiveContainer width="100%" height={260}>
                            <PieChart>
                                <Pie data={data.clusterBreakdown} dataKey="value" nameKey="name"
                                    cx="50%" cy="50%" outerRadius={90}
                                    label={({ name, percent }) => `${(percent * 100).toFixed(0)}%`}>
                                    {data.clusterBreakdown.map((entry, i) => (
                                        <Cell key={entry.name} fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip formatter={(v) => [`${v} txns`, '']} />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                    }
                </ChartCard>
            </div>

            {/* Row 2: Amount buckets + Top senders */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

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

                <ChartCard title="Top 10 Most Active Senders">
                    <ResponsiveContainer width="100%" height={260}>
                        <BarChart data={data.topSenders} layout="vertical"
                            margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis type="number" tick={{ fontSize: 11 }} />
                            <YAxis type="category" dataKey="address" tick={{ fontSize: 10 }} width={90} />
                            <Tooltip
                                formatter={(v) => [`${v} txns`, 'Count']}
                                labelFormatter={(label) => {
                                    const item = data.topSenders.find(s => s.address === label);
                                    return item ? item.full : label;
                                }}
                            />
                            <Bar dataKey="count" fill="#a855f7" radius={[0, 4, 4, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </ChartCard>
            </div>

        </div>
    );
}
