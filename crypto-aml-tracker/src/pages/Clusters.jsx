import { startTransition, useEffect, useState } from 'react';
import { ReactFlow, ReactFlowProvider, Background, Controls } from '@xyflow/react';
import {
    createOwnerListEntry,
    getClusters,
    getClustersSummary,
    getGraphData,
    runClustering,
} from '../services/transactionService';
import { filterEdgesData, applyRadialLayout } from '../utils/graphUtils';
import Loader from '../components/common/Loader';

const EMPTY_OWNER_FORM = {
    full_name: '',
    entity_type: 'individual',
    list_category: 'watchlist',
    known_addresses: '',
    blockchain_network: 'ethereum',
    specifics: '',
    street_address: '',
    locality: '',
    city: '',
    administrative_area: '',
    postal_code: '',
    country: 'Ethiopia',
    source_reference: 'Owner Registry Intake',
    notes: '',
};

const LABEL_STYLES = {
    matched: { color: '#166534', background: '#dcfce7', border: '1px solid #86efac' },
    unlabeled: { color: '#475569', background: '#e2e8f0', border: '1px solid #cbd5e1' },
    conflict: { color: '#92400e', background: '#fef3c7', border: '1px solid #fcd34d' },
};

const StatCard = ({ label, value, sub, color }) => (
    <div style={{
        background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0',
        padding: '18px 22px', flex: 1, minWidth: '160px',
    }}>
        <div style={{ fontSize: '24px', fontWeight: '700', color: color || '#0f172a' }}>{value}</div>
        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>{label}</div>
        {sub && <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>{sub}</div>}
    </div>
);

const StatusPill = ({ status }) => {
    const safeStatus = status || 'unlabeled';
    const style = LABEL_STYLES[safeStatus] || LABEL_STYLES.unlabeled;
    const label = safeStatus === 'matched'
        ? 'Matched'
        : safeStatus === 'conflict'
            ? 'Conflict'
            : 'Unknown / Unlabeled';

    return (
        <span style={{
            ...style,
            borderRadius: '999px',
            display: 'inline-flex',
            alignItems: 'center',
            padding: '4px 10px',
            fontSize: '10px',
            fontWeight: '700',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
        }}>
            {label}
        </span>
    );
};

const FormField = ({ label, children, hint }) => (
    <label style={{ display: 'grid', gap: '8px' }}>
        <span style={{ fontSize: '12px', fontWeight: '700', color: '#334155' }}>{label}</span>
        {children}
        {hint ? <span style={{ fontSize: '11px', color: '#64748b' }}>{hint}</span> : null}
    </label>
);

const inputStyle = {
    width: '100%',
    borderRadius: '12px',
    border: '1px solid #cbd5e1',
    background: '#fff',
    color: '#0f172a',
    padding: '12px 14px',
    fontSize: '13px',
    boxSizing: 'border-box',
};

const formatEth = (value) => {
    const num = Number(value || 0);
    if (!Number.isFinite(num)) return '0';
    return num.toLocaleString(undefined, { maximumFractionDigits: 6 });
};

const formatOwner = (owner, labelStatus) => {
    if (owner?.full_name) return owner.full_name;
    if (labelStatus === 'conflict') return 'Owner match conflict';
    return 'Unknown / Unlabeled';
};

const formatLocation = (owner, labelStatus) => {
    if (owner) {
        const parts = [
            owner.specifics,
            owner.street_address,
            owner.locality,
            owner.city,
            owner.administrative_area,
            owner.postal_code,
            owner.country,
        ].filter(Boolean);
        return parts.length ? parts.join(', ') : 'Address not recorded';
    }
    if (labelStatus === 'conflict') {
        return 'Multiple owner-list matches found for this cluster.';
    }
    return 'No owner-list address match yet.';
};

const truncate = (value, maxLength = 24) => {
    if (!value || value.length <= maxLength) return value || '—';
    return `${value.slice(0, maxLength - 3)}...`;
};

const buildPreviewGraph = (edgesData, centerId) => {
    const filtered = filterEdgesData(edgesData, { minValue: 0, maxEdges: 80 });
    const nodesMap = new Map();
    const edges = [];

    filtered.forEach((tx, index) => {
        const sender = tx.sender;
        const receiver = tx.receiver;
        if (!sender || !receiver) return;

        const labelFor = (address) => `${address.slice(0, 6)}...${address.slice(-4)}`;

        if (!nodesMap.has(sender)) {
            nodesMap.set(sender, {
                id: sender,
                data: { label: labelFor(sender) },
                position: { x: 0, y: 0 },
                style: {
                    background: '#22c55e', color: '#fff', borderRadius: '50%',
                    padding: '12px 18px', fontSize: '11px', fontWeight: '700',
                    border: sender === centerId ? '3px solid #1d4ed8' : '2px solid #15803d',
                },
            });
        }
        if (!nodesMap.has(receiver)) {
            nodesMap.set(receiver, {
                id: receiver,
                data: { label: labelFor(receiver) },
                position: { x: 0, y: 0 },
                style: {
                    background: '#0ea5e9', color: '#fff', borderRadius: '50%',
                    padding: '12px 18px', fontSize: '11px', fontWeight: '700',
                    border: '2px solid #0284c7',
                },
            });
        }

        edges.push({
            id: `e-${index}`,
            source: sender,
            target: receiver,
            type: 'default',
            animated: false,
            label: `${Number(tx.amount || 0).toFixed(4)} ETH`,
            style: { stroke: '#2563eb', strokeWidth: 1.8 },
            markerEnd: { type: 'arrowclosed', color: '#2563eb', width: 16, height: 16 },
            labelStyle: { fontSize: '9px', fill: '#1e3a5f', fontWeight: '600' },
            labelBgStyle: { fill: '#eff6ff', fillOpacity: 0.9 },
        });
    });

    const nodes = Array.from(nodesMap.values());
    const positioned = nodes.length
        ? applyRadialLayout(nodes, edges, centerId, { ringSpacing: 180, minRadius: 80 })
        : nodes;
    return { nodes: positioned, edges };
};

const getActivityHighlights = (activity, riskLevel) => {
    const highlights = [];
    const totalFlow = (activity.total_in || 0) + (activity.total_out || 0);
    if ((activity.total_tx_count || 0) > 80) {
        highlights.push('High transaction density between members');
    } else if ((activity.total_tx_count || 0) > 20) {
        highlights.push('Moderate internal transaction activity');
    } else {
        highlights.push('Low internal transaction activity');
    }

    if (totalFlow > 50) {
        highlights.push('Large internal ETH movement');
    } else if (totalFlow > 5) {
        highlights.push('Moderate ETH activity inside the cluster');
    }

    if (riskLevel && riskLevel !== 'normal') {
        highlights.push(`Risk level flagged: ${riskLevel}`);
    }

    return highlights;
};

function OwnerListModal({
    open,
    form,
    submitting,
    error,
    onClose,
    onChange,
    onSubmit,
}) {
    if (!open) return null;

    return (
        <div style={{ position: 'fixed', inset: 0, zIndex: 70, display: 'grid', placeItems: 'center', padding: '24px' }}>
            <div
                onClick={onClose}
                style={{ position: 'absolute', inset: 0, background: 'rgba(15, 23, 42, 0.56)' }}
            />
            <div style={{
                position: 'relative',
                width: 'min(760px, 100%)',
                maxHeight: 'calc(100vh - 48px)',
                overflow: 'hidden',
                borderRadius: '28px',
                background: '#f8fafc',
                boxShadow: '0 30px 120px rgba(15, 23, 42, 0.35)',
                border: '1px solid rgba(148, 163, 184, 0.24)',
            }}>
                <div style={{
                    padding: '24px 28px',
                    background: 'linear-gradient(135deg, #0f172a 0%, #1d4ed8 52%, #38bdf8 100%)',
                    color: '#fff',
                }}>
                    <div style={{ fontSize: '12px', fontWeight: '700', letterSpacing: '0.08em', textTransform: 'uppercase', opacity: 0.85 }}>
                        Owner Registry
                    </div>
                    <div style={{ fontSize: '26px', fontWeight: '700', marginTop: '10px' }}>
                        Add Entity / Owner
                    </div>
                    <div style={{ fontSize: '13px', marginTop: '8px', maxWidth: '560px', lineHeight: '1.6', color: 'rgba(255,255,255,0.88)' }}>
                        Save a verified address owner into the MySQL owner list and relabel any cluster that contains the supplied blockchain address.
                    </div>
                </div>

                <form onSubmit={onSubmit} style={{ padding: '26px 28px 28px', overflowY: 'auto', maxHeight: 'calc(100vh - 210px)' }}>
                    <div style={{ display: 'grid', gap: '18px' }}>
                        {error ? (
                            <div style={{
                                borderRadius: '16px',
                                background: '#fef2f2',
                                border: '1px solid #fecaca',
                                color: '#b91c1c',
                                padding: '14px 16px',
                                fontSize: '13px',
                            }}>
                                {error}
                            </div>
                        ) : null}

                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
                            <FormField label="Owner / Entity Name">
                                <input
                                    value={form.full_name}
                                    onChange={(e) => onChange('full_name', e.target.value)}
                                    style={inputStyle}
                                    placeholder="e.g. Dawit Alemu"
                                    required
                                />
                            </FormField>
                            <FormField label="Entity Type">
                                <select
                                    value={form.entity_type}
                                    onChange={(e) => onChange('entity_type', e.target.value)}
                                    style={inputStyle}
                                >
                                    <option value="individual">Individual</option>
                                    <option value="organization">Organization</option>
                                </select>
                            </FormField>
                            <FormField label="List Category">
                                <select
                                    value={form.list_category}
                                    onChange={(e) => onChange('list_category', e.target.value)}
                                    style={inputStyle}
                                >
                                    <option value="watchlist">Watchlist</option>
                                    <option value="sanction">Sanction</option>
                                    <option value="exchange">Exchange</option>
                                    <option value="merchant">Merchant</option>
                                    <option value="other">Other</option>
                                </select>
                            </FormField>
                            <FormField label="Blockchain Network">
                                <input
                                    value={form.blockchain_network}
                                    onChange={(e) => onChange('blockchain_network', e.target.value)}
                                    style={inputStyle}
                                    placeholder="ethereum"
                                    required
                                />
                            </FormField>
                        </div>

                        <FormField label="Known Blockchain Addresses" hint="Use one address per line or separate them with commas.">
                            <textarea
                                value={form.known_addresses}
                                onChange={(e) => onChange('known_addresses', e.target.value)}
                                rows={4}
                                style={{ ...inputStyle, resize: 'vertical' }}
                                placeholder={'0x...\n0x...'}
                                required
                            />
                        </FormField>

                        <div style={{
                            display: 'grid',
                            gap: '16px',
                            padding: '18px',
                            borderRadius: '20px',
                            background: 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
                            border: '1px solid #e2e8f0',
                        }}>
                            <div style={{ fontSize: '13px', fontWeight: '700', color: '#0f172a' }}>International Address</div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
                                <FormField label="Specifics">
                                    <input
                                        value={form.specifics}
                                        onChange={(e) => onChange('specifics', e.target.value)}
                                        style={inputStyle}
                                        placeholder="Apartment, suite, compound, office"
                                    />
                                </FormField>
                                <FormField label="Street Address">
                                    <input
                                        value={form.street_address}
                                        onChange={(e) => onChange('street_address', e.target.value)}
                                        style={inputStyle}
                                        placeholder="Street and number"
                                    />
                                </FormField>
                                <FormField label="Locality / District">
                                    <input
                                        value={form.locality}
                                        onChange={(e) => onChange('locality', e.target.value)}
                                        style={inputStyle}
                                        placeholder="District or sub-city"
                                    />
                                </FormField>
                                <FormField label="City">
                                    <input
                                        value={form.city}
                                        onChange={(e) => onChange('city', e.target.value)}
                                        style={inputStyle}
                                        placeholder="City"
                                        required
                                    />
                                </FormField>
                                <FormField label="Administrative Area">
                                    <input
                                        value={form.administrative_area}
                                        onChange={(e) => onChange('administrative_area', e.target.value)}
                                        style={inputStyle}
                                        placeholder="State, region, province"
                                    />
                                </FormField>
                                <FormField label="Postal Code">
                                    <input
                                        value={form.postal_code}
                                        onChange={(e) => onChange('postal_code', e.target.value)}
                                        style={inputStyle}
                                        placeholder="Postal code"
                                    />
                                </FormField>
                                <FormField label="Country">
                                    <input
                                        value={form.country}
                                        onChange={(e) => onChange('country', e.target.value)}
                                        style={inputStyle}
                                        placeholder="Country"
                                        required
                                    />
                                </FormField>
                                <FormField label="Source Reference">
                                    <input
                                        value={form.source_reference}
                                        onChange={(e) => onChange('source_reference', e.target.value)}
                                        style={inputStyle}
                                        placeholder="List source, case file, sanction entry"
                                    />
                                </FormField>
                            </div>
                        </div>

                        <FormField label="Notes">
                            <textarea
                                value={form.notes}
                                onChange={(e) => onChange('notes', e.target.value)}
                                rows={3}
                                style={{ ...inputStyle, resize: 'vertical' }}
                                placeholder="Additional context about the owner, entity, or case."
                            />
                        </FormField>

                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
                            <div style={{ fontSize: '11px', color: '#64748b', lineHeight: '1.5' }}>
                                Saving a record will immediately run the labeling function against any cluster containing the submitted address.
                            </div>
                            <div style={{ display: 'flex', gap: '10px' }}>
                                <button
                                    type="button"
                                    onClick={onClose}
                                    style={{
                                        padding: '11px 16px',
                                        borderRadius: '12px',
                                        border: '1px solid #cbd5e1',
                                        background: '#fff',
                                        color: '#334155',
                                        fontSize: '13px',
                                        fontWeight: '700',
                                        cursor: 'pointer',
                                    }}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={submitting}
                                    style={{
                                        padding: '11px 18px',
                                        borderRadius: '12px',
                                        border: 'none',
                                        background: submitting ? '#94a3b8' : '#0f172a',
                                        color: '#fff',
                                        fontSize: '13px',
                                        fontWeight: '700',
                                        cursor: submitting ? 'not-allowed' : 'pointer',
                                    }}
                                >
                                    {submitting ? 'Saving…' : 'Save and Relabel'}
                                </button>
                            </div>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    );
}

export default function Clusters({ onAddressClick }) {
    const [clusters, setClusters] = useState([]);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedCluster, setSelectedCluster] = useState(null);
    const [running, setRunning] = useState(false);
    const [showAllAddresses, setShowAllAddresses] = useState(false);
    const [preview, setPreview] = useState({ nodes: [], edges: [] });
    const [previewLoading, setPreviewLoading] = useState(false);
    const [previewError, setPreviewError] = useState(null);
    const [ownerModalOpen, setOwnerModalOpen] = useState(false);
    const [ownerSubmitting, setOwnerSubmitting] = useState(false);
    const [ownerForm, setOwnerForm] = useState(EMPTY_OWNER_FORM);
    const [ownerFormError, setOwnerFormError] = useState(null);
    const [ownerSuccess, setOwnerSuccess] = useState(null);

    const loadData = () => {
        setLoading(true);
        setError(null);
        Promise.all([getClusters(), getClustersSummary()])
            .then(([clusterRows, summaryRow]) => {
                setClusters(clusterRows);
                setSummary(summaryRow);
                setLoading(false);
            })
            .catch((err) => {
                setError(err.message);
                setLoading(false);
            });
    };

    useEffect(() => {
        loadData();
    }, []);

    useEffect(() => {
        if (!selectedCluster) {
            setShowAllAddresses(false);
            setPreview({ nodes: [], edges: [] });
            setPreviewError(null);
            return;
        }

        const centerAddress = selectedCluster.addresses?.[0]?.address || selectedCluster.addresses?.[0];
        if (!centerAddress) {
            setPreview({ nodes: [], edges: [] });
            return;
        }

        setPreviewLoading(true);
        setPreviewError(null);
        getGraphData({ center: centerAddress, maxEdges: 80, minValue: 0 })
            .then((data) => {
                setPreview(buildPreviewGraph(data, centerAddress));
            })
            .catch((err) => {
                setPreviewError(err.message || 'Unable to load cluster preview.');
                setPreview({ nodes: [], edges: [] });
            })
            .finally(() => setPreviewLoading(false));
    }, [selectedCluster]);

    const handleRunClustering = async () => {
        setRunning(true);
        setError(null);
        setOwnerSuccess(null);
        try {
            await runClustering();
            setSelectedCluster(null);
            startTransition(() => loadData());
        } catch (err) {
            setError(err.message);
        } finally {
            setRunning(false);
        }
    };

    const openOwnerModal = (prefillAddress = '') => {
        setOwnerForm({
            ...EMPTY_OWNER_FORM,
            known_addresses: prefillAddress || '',
        });
        setOwnerFormError(null);
        setOwnerSuccess(null);
        setOwnerModalOpen(true);
    };

    const closeOwnerModal = () => {
        if (ownerSubmitting) return;
        setOwnerModalOpen(false);
        setOwnerForm(EMPTY_OWNER_FORM);
        setOwnerFormError(null);
    };

    const handleOwnerFieldChange = (field, value) => {
        setOwnerForm((current) => ({ ...current, [field]: value }));
    };

    const handleOwnerSubmit = async (event) => {
        event.preventDefault();
        setOwnerSubmitting(true);
        setOwnerFormError(null);
        setError(null);

        const payload = {
            ...ownerForm,
            known_addresses: ownerForm.known_addresses
                .split(/\n|,/)
                .map((item) => item.trim())
                .filter(Boolean),
        };

        try {
            const result = await createOwnerListEntry(payload);
            const relabelSummary = result.relabel_summary || {};
            const matchedClusters = relabelSummary.matched_clusters || 0;
            const relabelled = relabelSummary.clusters_relabelled || 0;

            setOwnerModalOpen(false);
            setOwnerForm(EMPTY_OWNER_FORM);
            setSelectedCluster(null);
            setOwnerSuccess(
                `Owner list entry saved. Relabelled ${relabelled} cluster${relabelled === 1 ? '' : 's'}; ${matchedClusters} cluster${matchedClusters === 1 ? '' : 's'} matched the new address.`,
            );
            startTransition(() => loadData());
        } catch (err) {
            setOwnerFormError(err.message || 'Unable to save the owner record.');
        } finally {
            setOwnerSubmitting(false);
        }
    };

    const closeDrawer = () => setSelectedCluster(null);
    const openClusterDrawer = (cluster) => setSelectedCluster(cluster);

    const evidenceHeaderText = selectedCluster
        ? `Behavior observed from ${selectedCluster.addresses?.length ?? 0} cluster addresses.`
        : '';

    if (loading) return <Loader />;
    if (error) return (
        <div style={{ padding: '2rem', color: '#64748b' }}>
            <div style={{ fontSize: '16px', marginBottom: '8px', color: '#ef4444' }}>
                Could not load clusters.
            </div>
            <div style={{ fontSize: '13px' }}>{error}</div>
        </div>
    );

    const th = {
        textAlign: 'left', padding: '10px 14px',
        borderBottom: '2px solid #e2e8f0',
        color: '#475569', fontSize: '11px', fontWeight: '600',
        textTransform: 'uppercase', letterSpacing: '0.05em',
    };
    const td = { padding: '10px 14px', borderBottom: '1px solid #f1f5f9', fontSize: '12px', color: '#334155' };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <OwnerListModal
                open={ownerModalOpen}
                form={ownerForm}
                submitting={ownerSubmitting}
                error={ownerFormError}
                onClose={closeOwnerModal}
                onChange={handleOwnerFieldChange}
                onSubmit={handleOwnerSubmit}
            />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                <div>
                    <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>Wallet Clusters</div>
                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                        {clusters.length} clusters · owner-list driven labeling
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button onClick={() => openOwnerModal()} style={{
                        padding: '8px 14px', borderRadius: '8px', border: '1px solid #bfdbfe',
                        background: '#eff6ff', color: '#1d4ed8', fontSize: '12px', fontWeight: '700',
                        cursor: 'pointer',
                    }}>Add Owner / Entity</button>
                    <button onClick={loadData} style={{
                        padding: '8px 14px', borderRadius: '8px', border: '1px solid #e2e8f0',
                        background: '#fff', color: '#334155', fontSize: '12px', fontWeight: '600',
                        cursor: 'pointer',
                    }}>Refresh</button>
                    <button onClick={handleRunClustering} disabled={running} style={{
                        padding: '8px 16px', borderRadius: '8px', border: 'none',
                        background: running ? '#94a3b8' : '#0d1b2e', color: '#fff',
                        fontSize: '12px', fontWeight: '600', cursor: running ? 'not-allowed' : 'pointer',
                    }}>{running ? 'Clustering…' : 'Run Clustering'}</button>
                </div>
            </div>

            {ownerSuccess ? (
                <div style={{
                    borderRadius: '14px',
                    background: '#ecfdf5',
                    border: '1px solid #a7f3d0',
                    color: '#166534',
                    padding: '14px 16px',
                    fontSize: '13px',
                }}>
                    {ownerSuccess}
                </div>
            ) : null}

            {summary && (
                <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
                    <StatCard label="Total Clusters" value={summary.total} />
                    <StatCard label="Matched Labels" value={summary.matched} color="#166534" />
                    <StatCard label="Unknown / Unlabeled" value={summary.unlabeled} color="#475569" />
                    <StatCard label="Top Internal Flow" value={summary.top_by_balance?.[0]?.cluster_id || '—'}
                        sub={summary.top_by_balance?.[0] ? `${formatEth(summary.top_by_balance[0].total_balance)} ETH` : ''} />
                    <StatCard label="Top Size" value={summary.top_by_size?.[0]?.cluster_id || '—'}
                        sub={summary.top_by_size?.[0] ? `${summary.top_by_size[0].cluster_size} addresses` : ''} />
                </div>
            )}

            <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                {clusters.length === 0 ? (
                    <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
                        No clusters available yet. Run clustering to generate ownership groups.
                    </div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
                        <thead>
                            <tr style={{ background: '#e2e8f0' }}>
                                <th style={{ ...th, width: '18%' }}>Cluster ID</th>
                                <th style={{ ...th, width: '22%' }}>Owner</th>
                                <th style={{ ...th, width: '26%' }}>Location</th>
                                <th style={{ ...th, width: '12%' }}>Members</th>
                                <th style={{ ...th, width: '22%' }}>Total Balance</th>
                            </tr>
                        </thead>
                        <tbody>
                            {clusters.map((cluster) => {
                                const memberCount = cluster.addresses?.length ?? cluster.cluster_size ?? 0;
                                return (
                                    <tr
                                        key={cluster.cluster_id}
                                        onClick={() => openClusterDrawer(cluster)}
                                        style={{ cursor: 'pointer' }}
                                        onMouseEnter={(event) => { event.currentTarget.style.background = '#f8fafc'; }}
                                        onMouseLeave={(event) => { event.currentTarget.style.background = ''; }}
                                    >
                                        <td style={{ ...td, fontFamily: 'monospace', fontSize: '11px' }} title={cluster.cluster_id}>
                                            {`${cluster.cluster_id.slice(0, 10)}...${cluster.cluster_id.slice(-6)}`}
                                        </td>
                                        <td style={td}>
                                            <button
                                                onClick={(event) => { event.stopPropagation(); openClusterDrawer(cluster); }}
                                                style={{
                                                    background: 'transparent', border: 'none', padding: 0, margin: 0,
                                                    color: cluster.label_status === 'matched' ? '#1d4ed8' : '#334155',
                                                    fontWeight: '700', cursor: 'pointer',
                                                    textAlign: 'left', fontSize: '12px',
                                                }}
                                                title={formatLocation(cluster.owner, cluster.label_status)}
                                            >
                                                {formatOwner(cluster.owner, cluster.label_status)}
                                            </button>
                                            <div style={{ marginTop: '8px' }}>
                                                <StatusPill status={cluster.label_status} />
                                            </div>
                                        </td>
                                        <td style={{ ...td, fontSize: '11px', color: '#64748b' }} title={formatLocation(cluster.owner, cluster.label_status)}>
                                            {truncate(formatLocation(cluster.owner, cluster.label_status), 52)}
                                        </td>
                                        <td style={td}>{memberCount}</td>
                                        <td style={{ ...td, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <span style={{ fontWeight: '700', color: '#0f172a' }}>{formatEth(cluster.total_balance)} ETH</span>
                                            <button
                                                onClick={(event) => { event.stopPropagation(); openClusterDrawer(cluster); }}
                                                style={{
                                                    border: '1px solid #e2e8f0', borderRadius: '8px', padding: '6px 10px',
                                                    background: '#fff', color: '#334155', fontSize: '11px', fontWeight: '600',
                                                    cursor: 'pointer',
                                                }}
                                            >
                                                View
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>

            {selectedCluster && (
                <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', justifyContent: 'flex-end', pointerEvents: 'auto' }}>
                    <div
                        onClick={closeDrawer}
                        style={{ position: 'absolute', inset: 0, background: 'rgba(15, 23, 42, 0.26)' }}
                    />
                    <aside style={{ position: 'relative', width: 'min(560px,100%)', maxWidth: '560px', height: '100%', background: '#fff', boxShadow: '-24px 0 80px rgba(15, 23, 42, 0.18)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                        <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '16px' }}>
                            <div>
                                <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>Cluster details</div>
                                <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>Cluster ID: {selectedCluster.cluster_id}</div>
                            </div>
                            <button onClick={closeDrawer} style={{ border: 'none', background: 'transparent', color: '#475569', fontSize: '14px', fontWeight: '700', cursor: 'pointer' }}>Close</button>
                        </div>
                        <div style={{ padding: '24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '24px' }}>
                            <section style={{ display: 'grid', gap: '14px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Owner Profile</div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'start', flexWrap: 'wrap' }}>
                                    <div>
                                        <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>
                                            {formatOwner(selectedCluster.owner, selectedCluster.label_status)}
                                        </div>
                                        <div style={{ marginTop: '8px', color: '#64748b', fontSize: '13px', lineHeight: '1.6' }}>
                                            {formatLocation(selectedCluster.owner, selectedCluster.label_status)}
                                        </div>
                                    </div>
                                    <StatusPill status={selectedCluster.label_status} />
                                </div>
                                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                                    <div style={{ padding: '12px 14px', borderRadius: '14px', background: '#f8fafc', border: '1px solid #e2e8f0', minWidth: '140px' }}>
                                        <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>Members</div>
                                        <div style={{ fontSize: '16px', fontWeight: '700', color: '#0f172a' }}>{selectedCluster.addresses?.length ?? selectedCluster.cluster_size}</div>
                                    </div>
                                    <div style={{ padding: '12px 14px', borderRadius: '14px', background: '#f8fafc', border: '1px solid #e2e8f0', minWidth: '140px' }}>
                                        <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>Total Balance</div>
                                        <div style={{ fontSize: '16px', fontWeight: '700', color: '#0f172a' }}>{formatEth(selectedCluster.total_balance)} ETH</div>
                                    </div>
                                    <div style={{ padding: '12px 14px', borderRadius: '14px', background: '#f8fafc', border: '1px solid #e2e8f0', minWidth: '140px' }}>
                                        <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>Internal Flow</div>
                                        <div style={{ fontSize: '16px', fontWeight: '700', color: '#0f172a' }}>{formatEth(selectedCluster.activity.total_in)} in / {formatEth(selectedCluster.activity.total_out)} out</div>
                                    </div>
                                </div>
                                <div style={{ display: 'grid', gap: '10px', padding: '16px', borderRadius: '16px', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                                    <div style={{ fontSize: '12px', color: '#334155' }}>
                                        <strong>Matched address:</strong> {selectedCluster.matched_owner_address || 'No address match recorded'}
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#334155' }}>
                                        <strong>Entity type:</strong> {selectedCluster.owner?.entity_type || 'Not assigned'}
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#334155' }}>
                                        <strong>List category:</strong> {selectedCluster.owner?.list_category || 'Not assigned'}
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#334155' }}>
                                        <strong>Source:</strong> {selectedCluster.owner?.source_reference || 'Not recorded'}
                                    </div>
                                    {selectedCluster.owner?.notes ? (
                                        <div style={{ fontSize: '12px', color: '#334155', lineHeight: '1.6' }}>
                                            <strong>Notes:</strong> {selectedCluster.owner.notes}
                                        </div>
                                    ) : null}
                                </div>
                                <div>
                                    <button
                                        type="button"
                                        onClick={() => openOwnerModal(selectedCluster.addresses?.[0]?.address || '')}
                                        style={{
                                            border: '1px solid #bfdbfe',
                                            borderRadius: '10px',
                                            padding: '10px 14px',
                                            background: '#eff6ff',
                                            color: '#1d4ed8',
                                            fontSize: '12px',
                                            fontWeight: '700',
                                            cursor: 'pointer',
                                        }}
                                    >
                                        Add / Update Owner Record
                                    </button>
                                </div>
                            </section>

                            <section style={{ display: 'grid', gap: '12px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Activity / Behavior</div>
                                <div style={{ display: 'grid', gap: '10px', padding: '16px', borderRadius: '16px', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                                    {getActivityHighlights(selectedCluster.activity, selectedCluster.risk_level).map((line, idx) => (
                                        <div key={idx} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                                            <div style={{ width: '6px', height: '6px', marginTop: '8px', borderRadius: '50%', background: '#0f172a' }} />
                                            <div style={{ fontSize: '13px', color: '#334155', lineHeight: '1.5' }}>{line}</div>
                                        </div>
                                    ))}
                                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>Total transactions: {selectedCluster.activity.total_tx_count}</div>
                                </div>
                            </section>

                            <section style={{ display: 'grid', gap: '14px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Address List</div>
                                {selectedCluster.addresses?.length ? (
                                    <div style={{ display: 'grid', gap: '10px' }}>
                                        {(showAllAddresses ? selectedCluster.addresses : selectedCluster.addresses.slice(0, 5)).map((item) => (
                                            <div key={item.address} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px', padding: '14px', borderRadius: '14px', border: '1px solid #e2e8f0', background: '#fff' }}>
                                                <div>
                                                    <div style={{ fontFamily: 'monospace', fontSize: '12px', color: '#0f172a' }} title={item.address}>{truncate(item.address, 28)}</div>
                                                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                                                        {formatEth(item.total_in)} in · {formatEth(item.total_out)} out
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={() => onAddressClick && onAddressClick(item.address)}
                                                    style={{ border: '1px solid #e2e8f0', borderRadius: '10px', padding: '8px 12px', background: '#f8fafc', color: '#0f172a', fontSize: '11px', fontWeight: '600', cursor: 'pointer' }}
                                                >
                                                    Graph
                                                </button>
                                            </div>
                                        ))}
                                        {selectedCluster.addresses.length > 5 && (
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
                                                <div style={{ fontSize: '11px', color: '#64748b' }}>
                                                    {showAllAddresses
                                                        ? `Showing all ${selectedCluster.addresses.length} addresses`
                                                        : `Showing 5 of ${selectedCluster.addresses.length} addresses`}
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={(event) => { event.stopPropagation(); setShowAllAddresses((prev) => !prev); }}
                                                    style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '6px 10px', background: '#fff', color: '#334155', fontSize: '11px', fontWeight: '600', cursor: 'pointer' }}
                                                >
                                                    {showAllAddresses ? 'Show less' : `Show all ${selectedCluster.addresses.length}`}
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div style={{ padding: '16px', borderRadius: '16px', background: '#f8fafc', border: '1px solid #e2e8f0', color: '#64748b' }}>
                                        No addresses are attached to this cluster yet.
                                    </div>
                                )}
                            </section>

                            <section style={{ display: 'grid', gap: '14px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Graph Preview</div>
                                <div style={{ padding: '18px', borderRadius: '18px', border: '1px solid #e2e8f0', background: '#f8fafc', minHeight: '260px', position: 'relative' }}>
                                    {previewLoading ? (
                                        <div style={{ display: 'grid', placeItems: 'center', height: '100%', color: '#64748b', fontSize: '13px' }}>
                                            Loading cluster preview…
                                        </div>
                                    ) : previewError ? (
                                        <div style={{ display: 'grid', placeItems: 'center', height: '100%', color: '#ef4444', fontSize: '13px', padding: '12px', textAlign: 'center' }}>
                                            {previewError}
                                        </div>
                                    ) : preview.nodes.length ? (
                                        <ReactFlowProvider>
                                            <div style={{ width: '100%', height: '260px', borderRadius: '18px', overflow: 'hidden' }}>
                                                <ReactFlow
                                                    nodes={preview.nodes}
                                                    edges={preview.edges}
                                                    nodesDraggable={false}
                                                    nodesConnectable={false}
                                                    elementsSelectable={false}
                                                    zoomOnScroll={false}
                                                    panOnScroll={false}
                                                    fitView
                                                    fitViewOptions={{ padding: 0.12 }}
                                                    style={{ width: '100%', height: '100%', background: '#ffffff' }}
                                                >
                                                    <Background gap={20} color="#e2e8f0" />
                                                    <Controls showInteractive={false} />
                                                </ReactFlow>
                                            </div>
                                        </ReactFlowProvider>
                                    ) : (
                                        <div style={{ display: 'grid', placeItems: 'center', height: '100%', color: '#64748b', fontSize: '13px' }}>
                                            No preview available for this cluster yet.
                                        </div>
                                    )}
                                </div>
                                {selectedCluster.addresses?.[0] ? (
                                    <button
                                        type="button"
                                        onClick={() => onAddressClick && onAddressClick(selectedCluster.addresses[0].address)}
                                        style={{ marginTop: '8px', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '10px 14px', background: '#fff', color: '#0f172a', fontSize: '12px', fontWeight: '700', cursor: 'pointer' }}
                                    >
                                        Open full graph around {truncate(selectedCluster.addresses[0].address, 20)}
                                    </button>
                                ) : null}
                            </section>

                            <section style={{ display: 'grid', gap: '14px' }}>
                                <div style={{ fontSize: '12px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Evidence</div>
                                <div style={{ fontSize: '11px', color: '#64748b' }}>{evidenceHeaderText}</div>
                                {selectedCluster.evidence?.length ? (
                                    <div style={{ display: 'grid', gap: '12px' }}>
                                        {selectedCluster.evidence.map((item, idx) => (
                                            <div key={`${item.heuristic_name}-${idx}`} style={{ padding: '16px', borderRadius: '16px', background: '#fff', border: '1px solid #e2e8f0' }}>
                                                <div style={{ fontSize: '13px', fontWeight: '700', color: '#0f172a' }}>{item.heuristic_name.replace(/_/g, ' ')}</div>
                                                <div style={{ fontSize: '12px', color: '#475569', marginTop: '6px' }}>{item.evidence_text}</div>
                                                {item.observed_address_sample?.length ? (
                                                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '8px' }}>
                                                        {`Sample addresses: ${item.observed_address_sample.map((address) => `${address.slice(0, 8)}...${address.slice(-6)}`).join(', ')}`}
                                                    </div>
                                                ) : null}
                                                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '8px' }}>Confidence: {item.confidence.toFixed(2)}</div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div style={{ padding: '16px', borderRadius: '16px', background: '#f8fafc', border: '1px solid #e2e8f0', color: '#64748b' }}>
                                        No behavioral evidence detected for this cluster.
                                    </div>
                                )}
                            </section>
                        </div>
                    </aside>
                </div>
            )}
        </div>
    );
}
