import { useEffect, useState } from 'react';
import {
    PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
    BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts';
import { getAnalytics, getClustersSummary, getClusters } from '../services/transactionService';
import Loader from '../components/common/Loader';

const RISK_COLORS = { Low: '#22c55e', Medium: '#f59e0b', High: '#ef4444' };

const LABEL_COLORS = {
    possible_layering:      '#ef4444',
    possible_mixer:         '#a855f7',
    exchange_like_behavior: '#3b82f6',
    coordinated_activity:   '#f97316',
    token_flow_cluster:     '#22c55e',
    shared_counterparties:  '#eab308',
};

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
    const [clusterSummary, setClusterSummary] = useState(null);
    const [topClusters, setTopClusters] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        Promise.all([
            getAnalytics(),
            getClustersSummary().catch(() => null),
            getClusters().catch(() => []),
        ]).then(([d, cs, clusters]) => {
            setData(d);
            setClusterSummary(cs);
            setTopClusters((clusters || []).slice(0, 5));
            setLoading(false);
        }).catch(e => { setError(e.message); setLoading(false); });
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

            {/* Row 1: Risk distribution (full width) */}
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

            {/* Row 3: Clustering Summary */}
            {clusterSummary && (
                <>
                    {/* Divider */}
                    <div style={{ borderTop: '2px solid #e2e8f0', paddingTop: '4px' }}>
                        <div style={{ fontSize: '15px', fontWeight: '700', color: '#0f172a', marginBottom: '14px' }}>
                            Address Clustering Summary
                        </div>
                    </div>

                    {/* Cluster stat cards */}
                    <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                        <StatCard label="Total Clusters" value={clusterSummary.total} color="#0f172a" />
                        <StatCard label="High Risk Clusters" value={clusterSummary.high_risk} color="#ef4444"
                            sub="risk score ≥ 70" />
                        <StatCard label="Medium Risk Clusters" value={clusterSummary.medium_risk} color="#d97706"
                            sub="risk score 40–69" />
                        <StatCard label="Low Risk Clusters" value={clusterSummary.low_risk} color="#16a34a"
                            sub="risk score < 40" />
                    </div>

                    {/* Cluster risk donut + top clusters table */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

                        <ChartCard title="Cluster Risk Distribution">
                            <ResponsiveContainer width="100%" height={260}>
                                <PieChart>
                                    <Pie
                                        data={[
                                            { name: 'High', value: clusterSummary.high_risk },
                                            { name: 'Medium', value: clusterSummary.medium_risk },
                                            { name: 'Low', value: clusterSummary.low_risk },
                                        ]}
                                        dataKey="value" nameKey="name"
                                        cx="50%" cy="50%" innerRadius={55} outerRadius={90}
                                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                    >
                                        <Cell fill="#ef4444" />
                                        <Cell fill="#f59e0b" />
                                        <Cell fill="#22c55e" />
                                    </Pie>
                                    <Tooltip formatter={(v) => [`${v} clusters`, '']} />
                                    <Legend />
                                </PieChart>
                            </ResponsiveContainer>
                        </ChartCard>

                        <ChartCard title="Top 5 Highest Risk Clusters">
                            {topClusters.length === 0
                                ? <div style={{ color: '#94a3b8', padding: '60px 0', textAlign: 'center' }}>
                                    No clusters available — run clustering first
                                </div>
                                : <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', paddingTop: '4px' }}>
                                    {topClusters.map((c, i) => {
                                        const score = c.risk_score ?? 0;
                                        const barColor = score >= 70 ? '#ef4444' : score >= 40 ? '#f59e0b' : '#22c55e';
                                        const label = score >= 70 ? 'High' : score >= 40 ? 'Medium' : 'Low';
                                        return (
                                            <div key={c.cluster_id} style={{
                                                display: 'flex', alignItems: 'center', gap: '10px',
                                                padding: '8px 10px', borderRadius: '8px',
                                                background: '#f8fafc', border: '1px solid #e2e8f0',
                                            }}>
                                                <div style={{
                                                    width: '22px', height: '22px', borderRadius: '50%',
                                                    background: barColor, color: '#fff',
                                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                    fontSize: '11px', fontWeight: '700', flexShrink: 0,
                                                }}>{i + 1}</div>
                                                <div style={{ flex: 1, minWidth: 0 }}>
                                                    <div style={{ fontFamily: 'monospace', fontSize: '11px', color: '#475569', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                        {c.cluster_id}
                                                    </div>
                                                    <div style={{ display: 'flex', gap: '4px', marginTop: '3px', flexWrap: 'wrap' }}>
                                                        {(c.labels || []).slice(0, 2).map(l => (
                                                            <span key={l} style={{
                                                                fontSize: '10px', padding: '1px 6px', borderRadius: '999px',
                                                                background: '#e0f2fe', color: '#0369a1', fontWeight: '600',
                                                            }}>{l.replace(/_/g, ' ')}</span>
                                                        ))}
                                                    </div>
                                                </div>
                                                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                                                    <div style={{ fontSize: '15px', fontWeight: '700', color: barColor }}>{score}</div>
                                                    <div style={{ fontSize: '10px', color: '#94a3b8' }}>{label}</div>
                                                </div>
                                                {/* Score bar */}
                                                <div style={{ width: '60px', height: '6px', background: '#e2e8f0', borderRadius: '3px', flexShrink: 0 }}>
                                                    <div style={{ width: `${score}%`, height: '100%', background: barColor, borderRadius: '3px' }} />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            }
                        </ChartCard>
                    </div>

                    {/* Heuristic label breakdown */}
                    {topClusters.length > 0 && (() => {
                        const labelCounts = {};
                        topClusters.forEach(c => (c.labels || []).forEach(l => {
                            labelCounts[l] = (labelCounts[l] || 0) + 1;
                        }));
                        const labelData = Object.entries(labelCounts)
                            .map(([name, value]) => ({ name: name.replace(/_/g, ' '), value, fill: LABEL_COLORS[name] || '#94a3b8' }))
                            .sort((a, b) => b.value - a.value);
                        return (
                            <ChartCard title="Cluster Label Breakdown (Top 5 Clusters)">
                                <ResponsiveContainer width="100%" height={200}>
                                    <BarChart data={labelData} margin={{ top: 5, right: 10, left: 0, bottom: 40 }}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                        <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-20} textAnchor="end" interval={0} />
                                        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                                        <Tooltip formatter={(v) => [`${v} clusters`, 'Count']} />
                                        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                                            {labelData.map((entry, i) => (
                                                <Cell key={i} fill={entry.fill} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        );
                    })()}
                </>
            )}

        </div>
    );
}
