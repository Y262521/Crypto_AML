import { startTransition, useDeferredValue, useEffect, useState } from 'react';

import Loader from '../components/common/Loader';
import {
    getPlacementDetail,
    getPlacements,
    getPlacementSummary,
} from '../services/transactionService';

const palette = {
    ink: '#0b1220',
    inkSoft: '#55636f',
    line: '#e6e9ec',
    lineStrong: '#d1d6db',
    surface: '#ffffff',
    surfaceSoft: '#f6f9fb',
    surfaceMuted: '#f0f4f7',
    accent: '#0f6578',
    accentSoft: '#e6f6f8',
    accentStrong: '#063b47',
    success: '#1f8a4f',
    successSoft: '#e8f6ec',
    warning: '#b36b00',
    warningSoft: '#fff4e6',
    danger: '#b33a3a',
    dangerSoft: '#fdecea',
    slate: '#5c6b76',
    slateSoft: '#e9eef1',
};

const _BANNED = new Set(['funneling', 'funnel', 'immediate_utilization', 'immediate-utilization', 'immediate utilization']);

const DOMINANT_GAP = 0.15;
const DOMINANT_RATIO = 0.82;
const BALANCED_GAP = 0.06;
const BALANCED_RATIO = 0.94;

const cardStyle = {
    background: palette.surface,
    borderRadius: '24px',
    border: `1px solid ${palette.line}`,
    boxShadow: '0 18px 44px rgba(30, 42, 47, 0.06)',
};

const sectionTitleStyle = {
    fontSize: '11px',
    fontWeight: '800',
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
    color: palette.inkSoft,
};

const SummaryCard = ({ label, value, sub, tone = 'accent' }) => {
    const tones = {
        accent: { border: palette.accent, background: palette.accentSoft, text: palette.accentStrong },
        danger: { border: palette.danger, background: palette.dangerSoft, text: palette.danger },
        warning: { border: palette.warning, background: palette.warningSoft, text: palette.warning },
        success: { border: palette.success, background: palette.successSoft, text: palette.success },
    };
    const resolved = tones[tone] || tones.accent;
    return (
        <div style={{
            ...cardStyle,
            minWidth: '210px',
            flex: 1,
            padding: '18px 20px',
            background: `linear-gradient(180deg, ${resolved.background} 0%, ${palette.surface} 100%)`,
        }}>
            <div style={sectionTitleStyle}>{label}</div>
            <div style={{ fontSize: '31px', fontWeight: '800', color: palette.ink, marginTop: '12px' }}>
                {value}
            </div>
            {sub ? (
                <div style={{ fontSize: '12px', lineHeight: 1.6, color: palette.inkSoft, marginTop: '8px' }}>
                    {sub}
                </div>
            ) : null}
            <div style={{
                marginTop: '16px',
                height: '3px',
                width: '68px',
                borderRadius: '999px',
                background: resolved.border,
            }} />
        </div>
    );
};

const badgeStyle = (tone = 'slate') => {
    const tones = {
        accent: { color: palette.accentStrong, background: palette.accentSoft, border: '#c5d8df' },
        danger: { color: palette.danger, background: palette.dangerSoft, border: '#e2c3bd' },
        warning: { color: palette.warning, background: palette.warningSoft, border: '#e4d1b1' },
        success: { color: palette.success, background: palette.successSoft, border: '#c7d8c9' },
        slate: { color: palette.slate, background: palette.slateSoft, border: '#d8dfe3' },
    };
    const resolved = tones[tone] || tones.slate;
    return {
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '6px 10px',
        borderRadius: '999px',
        fontSize: '11px',
        fontWeight: '700',
        color: resolved.color,
        background: resolved.background,
        border: `1px solid ${resolved.border}`,
        whiteSpace: 'nowrap',
    };
};

const behaviorTone = (behavior) => {
    if (behavior === 'structuring') return 'danger';
    if (behavior === 'smurfing') return 'warning';
    if (behavior === 'micro_funding') return 'accent';
    return 'slate';
};

const focusTone = (mode) => {
    if (mode === 'balanced') return 'accent';
    if (mode === 'paired') return 'warning';
    return 'danger';
};


const truncate = (value, maxLength = 18) => {
    if (!value) return '—';
    if (value.length <= maxLength) return value;
    return `${value.slice(0, maxLength - 3)}...`;
};

const formatNumber = (value, maximumFractionDigits = 2) => {
    const parsed = Number(value || 0);
    if (!Number.isFinite(parsed)) return '0';
    return parsed.toLocaleString(undefined, { maximumFractionDigits });
};

const formatBehaviorLabel = (behavior) => (behavior || '').replaceAll('_', ' ');

const selectBehaviorHighlights = (rankedBehaviors) => {
    if (!rankedBehaviors.length) {
        return { mode: 'none', highlighted: [] };
    }
    if (rankedBehaviors.length === 1) {
        return { mode: 'dominant', highlighted: rankedBehaviors.slice(0, 1) };
    }

    const topScore = Number(rankedBehaviors[0].confidence_score || 0);
    const secondScore = Number(rankedBehaviors[1].confidence_score || 0);
    if (
        topScore - secondScore >= DOMINANT_GAP
        || secondScore <= topScore * DOMINANT_RATIO
    ) {
        return { mode: 'dominant', highlighted: rankedBehaviors.slice(0, 1) };
    }

    if (rankedBehaviors.length === 2) {
        return { mode: 'paired', highlighted: rankedBehaviors.slice(0, 2) };
    }

    const thirdScore = Number(rankedBehaviors[2].confidence_score || 0);
    if (
        topScore - thirdScore <= BALANCED_GAP
        && thirdScore >= topScore * BALANCED_RATIO
    ) {
        return { mode: 'balanced', highlighted: rankedBehaviors.slice(0, 3) };
    }
    return { mode: 'paired', highlighted: rankedBehaviors.slice(0, 2) };
};

const resolveBehaviorProfile = (behaviorProfile, allBehaviors = [], detailBehaviors = []) => {
    const detailRanking = [...detailBehaviors]
        .sort((left, right) => {
            const scoreGap = Number(right.confidence_score || 0) - Number(left.confidence_score || 0);
            if (scoreGap !== 0) return scoreGap;
            return String(left.behavior_type || '').localeCompare(String(right.behavior_type || ''));
        })
        .map((behavior) => ({
            behavior_type: behavior.behavior_type,
            confidence_score: Number(behavior.confidence_score || 0),
            evidence_entity_id: null,
            source: 'origin',
        }));

    const rankedBehaviors = Array.isArray(behaviorProfile?.ranked_behaviors) && behaviorProfile.ranked_behaviors.length
        ? behaviorProfile.ranked_behaviors
        : detailRanking;
    const derived = selectBehaviorHighlights(rankedBehaviors);
    const highlighted = Array.isArray(behaviorProfile?.display_behaviors) && behaviorProfile.display_behaviors.length
        ? behaviorProfile.display_behaviors
            .map((behaviorType) => rankedBehaviors.find((item) => item.behavior_type === behaviorType) || {
                behavior_type: behaviorType,
                confidence_score: 0,
                evidence_entity_id: null,
                source: 'origin',
            })
            .filter(Boolean)
        : derived.highlighted;

    return {
        primaryBehavior: behaviorProfile?.primary_behavior || highlighted[0]?.behavior_type || allBehaviors[0] || null,
        mode: behaviorProfile?.display_mode || derived.mode,
        highlighted,
        rankedBehaviors,
    };
};

const describeBehaviorFocus = ({ mode, rankedBehaviors, highlighted }) => {
    if (!rankedBehaviors.length) {
        return 'No scored behavior evidence was saved for this alert.';
    }
    if (mode === 'dominant' && rankedBehaviors.length > 1) {
        const lead = (Number(rankedBehaviors[0].confidence_score || 0) - Number(rankedBehaviors[1].confidence_score || 0)) * 100;
        return `${formatBehaviorLabel(rankedBehaviors[0].behavior_type)} leads by ${formatNumber(lead, 1)} pts, so only the strongest placement signal is surfaced.`;
    }
    if (mode === 'paired' && highlighted.length >= 2) {
        return `${formatBehaviorLabel(highlighted[0].behavior_type)} and ${formatBehaviorLabel(highlighted[1].behavior_type)} remain close enough to review together.`;
    }
    if (mode === 'balanced' && highlighted.length >= 3) {
        const spread = (Number(rankedBehaviors[0].confidence_score || 0) - Number(rankedBehaviors[2].confidence_score || 0)) * 100;
        return `The top three signals stay within ${formatNumber(spread, 1)} pts, so all three are shown together.`;
    }
    return `${formatBehaviorLabel(rankedBehaviors[0].behavior_type)} is the primary signal for this alert.`;
};


const TracePath = ({ path }) => (
    <div style={{
        ...cardStyle,
        padding: '16px 18px',
        display: 'grid',
        gap: '14px',
        background: `linear-gradient(180deg, ${palette.surface} 0%, ${palette.surfaceSoft} 100%)`,
    }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                <span style={badgeStyle('accent')}>Trace #{path.path_index}</span>
                <span style={badgeStyle('slate')}>Score {formatNumber(path.score * 100, 1)}</span>
                <span style={badgeStyle(path.terminal_reason === 'no_incoming' ? 'success' : 'warning')}>
                    {path.terminal_reason?.replaceAll('_', ' ') || 'trace'}
                </span>
            </div>
            <div style={{ fontSize: '12px', color: palette.inkSoft }}>
                Root {truncate(path.root_entity_id, 22)}
            </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', overflowX: 'auto', paddingBottom: '2px' }}>
            {path.nodes.map((node, index) => (
                <div key={`${path.path_index}-${node.entity_id}-${index}`} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{
                        minWidth: '190px',
                        padding: '14px 16px',
                        borderRadius: '18px',
                        border: `1px solid ${palette.line}`,
                        background: index === 0
                            ? palette.successSoft
                            : index === path.nodes.length - 1
                                ? palette.dangerSoft
                                : palette.accentSoft,
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center' }}>
                            <span style={badgeStyle(node.entity_type === 'cluster' ? 'accent' : 'slate')}>
                                {node.entity_type === 'cluster' ? 'Cluster' : 'Address'}
                            </span>
                            <span style={{ fontSize: '11px', color: palette.inkSoft }}>
                                {node.address_count || node.addresses?.length || 0} addr
                            </span>
                        </div>
                        <div style={{ fontSize: '13px', fontWeight: '800', color: palette.ink, marginTop: '12px', fontFamily: 'monospace' }}>
                            {truncate(node.entity_id, 26)}
                        </div>
                        <div style={{ fontSize: '12px', color: palette.inkSoft, marginTop: '8px', lineHeight: 1.5 }}>
                            {(node.addresses || []).slice(0, 2).join(', ') || 'No addresses available'}
                        </div>
                    </div>
                    {index < path.nodes.length - 1 ? (
                        <div style={{ fontSize: '22px', color: palette.inkSoft, flexShrink: 0 }}>→</div>
                    ) : null}
                </div>
            ))}
        </div>
    </div>
);

export default function Placement() {
    const [summary, setSummary] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [detail, setDetail] = useState(null);
    const [loading, setLoading] = useState(true);
    const [detailLoading, setDetailLoading] = useState(false);
    const [error, setError] = useState(null);
    const [search, setSearch] = useState('');
    const [behaviorFilter, setBehaviorFilter] = useState('All');
    const [expandedAlerts, setExpandedAlerts] = useState({});
    const [showAllAlerts, setShowAllAlerts] = useState(false);
    const deferredSearch = useDeferredValue(search);

    const loadPage = async () => {
        setLoading(true);
        setError(null);
        try {
            const [summaryData, listData] = await Promise.all([
                getPlacementSummary(),
                getPlacements(),
            ]);
            const nextAlerts = listData.items || [];
            setSummary(summaryData);
            setAlerts(nextAlerts);
            setSelectedId((current) => {
                if (current && nextAlerts.some((item) => item.entity_id === current)) {
                    return current;
                }
                return nextAlerts[0]?.entity_id || null;
            });
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadPage();
    }, []);

    useEffect(() => {
        if (!selectedId) {
            setDetail(null);
            return;
        }
        setDetailLoading(true);
        getPlacementDetail(selectedId)
            .then((data) => setDetail(data))
            .catch((err) => setError(err.message))
            .finally(() => setDetailLoading(false));
    }, [selectedId]);

    const KNOWN_BEHAVIORS = ['structuring', 'smurfing', 'micro_funding'];
    const discovered = Array.from(
        new Set(
            alerts.flatMap((alert) => (alert.all_behaviors || alert.behaviors || []).filter(b => b && !_BANNED.has(String(b).toLowerCase())))
        )
    );
    const allBehaviors = Array.from(new Set([...KNOWN_BEHAVIORS, ...discovered])).sort();

    const filteredAlerts = alerts.filter((alert) => {
        const query = deferredSearch.trim().toLowerCase();
        const matchesSearch = !query
            || alert.entity_id?.toLowerCase().includes(query)
            || (alert.addresses || []).some((address) => address?.toLowerCase().includes(query))
            || (alert.reasons || []).some((reason) => reason?.toLowerCase().includes(query));
        const availableBehaviors = (alert.all_behaviors || alert.behaviors || []).filter(b => b && !_BANNED.has(String(b).toLowerCase()));
        const matchesBehavior = behaviorFilter === 'All' || availableBehaviors.includes(behaviorFilter);
        return matchesSearch && matchesBehavior;
    });
    const visibleAlerts = showAllAlerts ? filteredAlerts : filteredAlerts.slice(0, 6);

    const toggleAlertAddresses = (entityId) => {
        setExpandedAlerts((current) => ({ ...current, [entityId]: !current[entityId] }));
    };

    if (loading) return <Loader />;
    if (error) return <div style={{ color: palette.danger, padding: '1rem' }}>Error: {error}</div>;

    const summaryBody = summary?.summary || {};
    const selectedAlert = filteredAlerts.find((alert) => alert.entity_id === selectedId) || filteredAlerts[0] || null;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '22px', color: palette.ink }}>
            <div style={{
                padding: '24px',
                background: '#0d1b2e',
                border: '1px solid #1e2d45',
                borderRadius: '12px',
                color: '#f7fff5ff',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
            }}>
                <div>
                    <div style={{ fontSize: '20px', fontWeight: '600', margin: 0 }}>
                        Placement Stage Review
                    </div>
                    <div style={{ fontSize: '14px', marginTop: '6px', color: '#94a3b8', maxWidth: '600px' }}>
                        Review placement-stage deposit activity and detected behavioral patterns across flagged entities.
                    </div>
                </div>


            </div>

            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                <SummaryCard
                    label="Placement Alerts"
                    value={formatNumber(summaryBody.placements || 0, 0)}
                    sub="Origin entities that scored above the latest placement threshold."
                    tone="danger"
                />
                <SummaryCard
                    label="Behavior Hits"
                    value={formatNumber(Object.values(summaryBody.behaviors || {}).reduce((total, count) => total + Number(count || 0), 0), 0)}
                    sub="Detected structuring, smurfing, and micro-funding hits across the latest run."
                    tone="warning"
                />
            </div>

            <div style={{ ...cardStyle, padding: '16px 18px', background: palette.surfaceSoft, display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
                <input
                    type="text"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search by entity, address, or reason..."
                    style={{
                        flex: 1,
                        minWidth: '240px',
                        borderRadius: '14px',
                        border: `1px solid ${palette.lineStrong}`,
                        background: palette.surface,
                        padding: '12px 14px',
                        fontSize: '13px',
                        color: palette.ink,
                    }}
                />
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {['All', ...allBehaviors].map((behavior) => (
                        <button
                            key={behavior}
                            type="button"
                            onClick={() => setBehaviorFilter(behavior)}
                            style={{
                                padding: '8px 12px',
                                borderRadius: '999px',
                                border: behaviorFilter === behavior ? `1px solid ${palette.accentStrong}` : `1px solid ${palette.line}`,
                                background: behaviorFilter === behavior ? palette.accentStrong : palette.surface,
                                color: behaviorFilter === behavior ? '#f7f3ec' : palette.inkSoft,
                                cursor: 'pointer',
                                fontSize: '12px',
                                fontWeight: '700',
                            }}
                        >
                            {behavior === 'All' ? 'All Behaviors' : formatBehaviorLabel(behavior)}
                        </button>
                    ))}
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px', alignItems: 'start' }}>
                <div style={{ ...cardStyle, padding: '14px', display: 'grid', gap: '12px', alignContent: 'start' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
                        <div>
                            <div style={sectionTitleStyle}>Alerts</div>
                            <div style={{ fontSize: '12px', color: palette.inkSoft, marginTop: '6px' }}>
                                {visibleAlerts.length} visible of {filteredAlerts.length} filtered alerts
                            </div>
                        </div>
                        {filteredAlerts.length > 6 ? (
                            <button
                                type="button"
                                onClick={() => setShowAllAlerts((current) => !current)}
                                style={{
                                    border: 'none',
                                    background: 'transparent',
                                    color: palette.accent,
                                    fontSize: '12px',
                                    fontWeight: '800',
                                    cursor: 'pointer',
                                    padding: 0,
                                }}
                            >
                                {showAllAlerts ? 'Show less alerts' : `See ${filteredAlerts.length - 6} more`}
                            </button>
                        ) : null}
                    </div>

                    {visibleAlerts.length === 0 ? (
                        <div style={{ padding: '28px 18px', textAlign: 'center', color: palette.inkSoft, fontSize: '13px' }}>
                            No placement alerts match the current filters.
                        </div>
                    ) : visibleAlerts.map((alert) => {
                        const active = alert.entity_id === (selectedAlert?.entity_id || selectedId);
                        const alertBehaviorProfile = resolveBehaviorProfile(
                            alert.behavior_profile,
                            alert.all_behaviors,
                        );
                        const compactModeLabel = alertBehaviorProfile.mode === 'balanced'
                            ? 'Balanced view'
                            : alertBehaviorProfile.mode === 'paired'
                                ? 'Paired view'
                                : 'Dominant view';

                        return (
                            <button
                                key={alert.entity_id}
                                type="button"
                                onClick={() => startTransition(() => setSelectedId(alert.entity_id))}
                                style={{
                                    textAlign: 'left',
                                    borderRadius: '20px',
                                    border: active ? `1px solid ${palette.accent}` : `1px solid ${palette.line}`,
                                    background: active
                                        ? `linear-gradient(180deg, ${palette.accentSoft} 0%, ${palette.surface} 82%)`
                                        : palette.surface,
                                    padding: '16px',
                                    cursor: 'pointer',
                                    display: 'grid',
                                    gap: '12px',
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start' }}>
                                    <div style={{ minWidth: 0 }}>
                                        <div style={{ ...sectionTitleStyle, color: active ? palette.accentStrong : palette.inkSoft }}>
                                            {alert.entity_type === 'cluster' ? 'Cluster Alert' : 'Address Fallback'}
                                        </div>
                                        <div style={{ fontSize: '14px', fontWeight: '800', color: palette.ink, fontFamily: 'monospace', marginTop: '8px' }}>
                                            {truncate(alert.entity_id, 32)}
                                        </div>
                                    </div>
                                    <span style={badgeStyle(alert.risk_score >= 85 ? 'danger' : alert.risk_score >= 70 ? 'warning' : 'accent')}>
                                        Risk {formatNumber(alert.risk_score, 1)}
                                    </span>
                                </div>

                                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                                    <span style={badgeStyle(focusTone(alertBehaviorProfile.mode))}>{compactModeLabel}</span>
                                    {alertBehaviorProfile.highlighted.map((behavior) => (
                                        <span key={`${alert.entity_id}-${behavior.behavior_type}`} style={badgeStyle(behaviorTone(behavior.behavior_type))}>
                                            {formatBehaviorLabel(behavior.behavior_type)}
                                        </span>
                                    ))}
                                </div>

                                <div style={{ fontSize: '12px', color: palette.inkSoft, lineHeight: 1.6 }}>
                                    {describeBehaviorFocus(alertBehaviorProfile)}
                                </div>

                                <div style={{ fontSize: '12px', color: palette.ink, lineHeight: 1.6 }}>
                                    {alert.reason || 'No reason supplied'}
                                </div>

                                {(alert.addresses || []).length ? (
                                    <div style={{ display: 'grid', gap: '10px' }}>
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                            {((expandedAlerts[alert.entity_id] ? alert.addresses : (alert.addresses || []).slice(0, 5)) || []).map((address) => (
                                                <span
                                                    key={address}
                                                    title={address}
                                                    style={{
                                                        ...badgeStyle('slate'),
                                                        fontFamily: 'monospace',
                                                        maxWidth: '100%',
                                                        overflow: 'hidden',
                                                        textOverflow: 'ellipsis',
                                                    }}
                                                >
                                                    {truncate(address, 18)}
                                                </span>
                                            ))}
                                        </div>
                                        {(alert.addresses || []).length > 5 ? (
                                            <button
                                                type="button"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    toggleAlertAddresses(alert.entity_id);
                                                }}
                                                style={{
                                                    border: 'none',
                                                    background: 'transparent',
                                                    color: palette.accent,
                                                    fontSize: '12px',
                                                    fontWeight: '800',
                                                    cursor: 'pointer',
                                                    padding: 0,
                                                    textAlign: 'left',
                                                }}
                                            >
                                                {expandedAlerts[alert.entity_id] ? 'Show less' : 'See more'}
                                            </button>
                                        ) : null}
                                    </div>
                                ) : null}

                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                                    <div style={{ fontSize: '12px', color: palette.inkSoft }}>
                                        {alert.address_count} addresses
                                    </div>
                                    <div style={{ fontSize: '12px', color: palette.accentStrong, fontWeight: '800' }}>
                                        Confidence {formatNumber((alert.confidence || 0) * 100, 1)}
                                    </div>
                                </div>
                            </button>
                        );
                    })}
                </div>

                <div style={{ ...cardStyle, padding: '20px', display: 'grid', gap: '18px', alignContent: 'start' }}>
                    {!selectedAlert ? (
                        <div style={{ padding: '28px 18px', textAlign: 'center', color: palette.inkSoft, fontSize: '13px' }}>
                            No placement alert selected.
                        </div>
                    ) : detailLoading || !detail ? (
                        <Loader />
                    ) : (
                        <>
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                <span style={badgeStyle(detail.placement.entity_type === 'cluster' ? 'accent' : 'slate')}>
                                    {detail.placement.entity_type === 'cluster' ? 'Cluster First' : 'Address Fallback'}
                                </span>
                                <span style={badgeStyle(detail.placement.validation_status === 'validated' ? 'success' : detail.placement.validation_status === 'enhanced' ? 'warning' : 'slate')}>
                                    {detail.placement.validation_status}
                                </span>
                            </div>
                            <div style={{ fontSize: '26px', fontWeight: '800', color: palette.ink, marginTop: '14px' }}>
                                {detail.placement.entity_id}
                            </div>
                            <div style={{ fontSize: '13px', color: palette.inkSoft, marginTop: '10px', lineHeight: 1.7 }}>
                                {(detail.placement.reasons || []).join(' • ')}
                            </div>







                            <div style={{ display: 'grid', gap: '12px' }}>
                                <div style={sectionTitleStyle}>Trace Paths</div>
                                {(detail.trace_paths || []).length === 0 ? (
                                    <div style={{ fontSize: '12px', color: palette.inkSoft }}>
                                        No trace paths were stored for this alert.
                                    </div>
                                ) : detail.trace_paths.map((path) => (
                                    <TracePath key={`${path.root_entity_id}-${path.path_index}`} path={path} />
                                ))}
                            </div>


                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
