/**
 * Entity Intelligence Workspace
 *
 * Reusable contextual investigation panel for addresses and clusters.
 * Opens as a full-screen overlay without navigating away from the current page.
 *
 * Layout:
 *   [Header]
 *   [Main content area] | [Right sidebar — vertical tabs]
 *
 * Tabs (right sidebar):
 *   - Overview
 *   - Market Value  (IMPLEMENTED)
 *   - Profit Ratio
 *   - Exchange Flow
 *   - Holder Wave
 *   - Address Network
 *   ─────────────────
 *   - All Addresses  (shows the full MarketValueIndex)
 */

import { useState, useEffect } from 'react';
import MvrvAnalysis from './MvrvAnalysis';
import MarketValueIndex from '../../pages/MarketValueIndex';

const TAB_SIDEBAR_WIDTH = 160;

const EntityIntelligenceWorkspace = ({
    entityId,
    entityType = 'cluster', // 'cluster' or 'address'
    sourcePage,
    initialTab = 'market-value',
    onClose,
    onNavigateToGraph,
}) => {
    const [activeTab, setActiveTab] = useState(initialTab);
    const [activeEntityId, setActiveEntityId] = useState(entityId);
    const [activeEntityType, setActiveEntityType] = useState(entityType);
    const [entityData, setEntityData] = useState(null);
    const [loading, setLoading] = useState(true);

    // Sync tab when caller changes initialTab
    useEffect(() => {
        setActiveTab(initialTab);
    }, [initialTab]);

    // Sync entity when caller changes entityId/entityType
    useEffect(() => {
        setActiveEntityId(entityId);
        setActiveEntityType(entityType);
    }, [entityId, entityType]);

    useEffect(() => {
        const loadEntityData = async () => {
            setLoading(true);
            try {
                setEntityData({ id: activeEntityId, type: activeEntityType, name: null });
            } catch (err) {
                console.error('Failed to load entity data:', err);
            } finally {
                setLoading(false);
            }
        };
        if (activeEntityId) loadEntityData();
    }, [activeEntityId, activeEntityType]);

    const tabs = [
        { id: 'overview',         label: 'Overview',         icon: '📊', implemented: false },
        { id: 'market-value',     label: 'MVRV',             icon: '◈',  implemented: true  },
        { id: 'profit-ratio',     label: 'Profit Ratio',     icon: '📈', implemented: false },
        { id: 'exchange-flow',    label: 'Exchange Flow',    icon: '⇄',  implemented: false },
        { id: 'holder-wave',      label: 'Holder Wave',      icon: '〜', implemented: false },
        { id: 'address-network',  label: 'Address Network',  icon: '🕸', implemented: false },
    ];

    // Special "index" tab — not part of the entity tabs array
    const isIndexView = activeTab === 'all-addresses';

    const displayName = entityData?.name
        || (activeEntityId?.length > 20 ? `${activeEntityId.slice(0, 10)}...${activeEntityId.slice(-8)}` : activeEntityId);

    return (
        <div style={{
            position: 'fixed',
            inset: 0,
            width: '100vw',
            height: '100vh',
            background: 'linear-gradient(180deg, #0D1628 0%, #0A1020 100%)',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
        }}>
            {/* ── Header ── */}
            <div style={{
                padding: '20px 28px',
                borderBottom: '1px solid rgba(201,168,76,0.12)',
                background: 'linear-gradient(135deg, #0d1b2e 0%, #0f2744 100%)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                gap: '16px',
                flexShrink: 0,
            }}>
                <div style={{ flex: 1 }}>
                    <div style={{
                        fontSize: '11px',
                        fontWeight: '700',
                        letterSpacing: '0.1em',
                        textTransform: 'uppercase',
                        color: '#64748b',
                        marginBottom: '6px',
                    }}>
                        {activeEntityType === 'cluster' ? '🔗 Wallet Cluster' : '💼 Address'} Intelligence
                    </div>

                    {isIndexView ? (
                        <div style={{ fontSize: '18px', fontWeight: '700', color: '#E2D9C8' }}>
                            Market Value Index — All Addresses
                        </div>
                    ) : (
                        <>
                            <div style={{
                                fontSize: '18px',
                                fontWeight: '700',
                                color: '#E2D9C8',
                                fontFamily: 'monospace',
                                marginBottom: '3px',
                            }}>
                                {displayName}
                            </div>
                            <div style={{ fontSize: '12px', color: '#8A9DB5' }}>
                                Contextual investigation from {sourcePage || 'unknown'}
                            </div>
                        </>
                    )}
                </div>

                <button
                    onClick={onClose}
                    style={{
                        background: 'rgba(255,255,255,0.08)',
                        border: '1px solid rgba(255,255,255,0.15)',
                        borderRadius: '8px',
                        color: '#E2D9C8',
                        fontSize: '20px',
                        lineHeight: 1,
                        cursor: 'pointer',
                        padding: '8px 12px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'all 0.2s',
                        flexShrink: 0,
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(239,68,68,0.15)';
                        e.currentTarget.style.borderColor = 'rgba(239,68,68,0.3)';
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.08)';
                        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)';
                    }}
                >
                    ✕
                </button>
            </div>

            {/* ── Body: content + right tab sidebar ── */}
            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

                {/* Main content */}
                <div style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: '24px 32px',
                    background: '#0F1829',
                }}>
                    {isIndexView ? (
                        <MarketValueIndex
                            onOpenWorkspace={(addr, type, src, tab) => {
                                setActiveEntityId(addr);
                                setActiveEntityType(type || 'address');
                                setActiveTab(tab || 'market-value');
                            }}
                            onNavigateToGraph={onNavigateToGraph}
                        />
                    ) : loading ? (
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            height: '100%',
                            color: '#8A9DB5',
                        }}>
                            Loading entity data…
                        </div>
                    ) : activeTab === 'market-value' ? (
                        <MvrvAnalysis
                            key={`mvrv-${activeEntityType}-${activeEntityId}`}
                            entityId={activeEntityId}
                            entityType={activeEntityType}
                        />
                    ) : activeTab === 'overview' ? (
                        <PlaceholderTab icon="📊" label="Overview" description="Entity summary and key metrics will be displayed here" />
                    ) : (
                        <PlaceholderTab
                            icon="🔒"
                            label={tabs.find(t => t.id === activeTab)?.label ?? activeTab}
                            description="This intelligence mechanism is under development"
                        />
                    )}
                </div>

                {/* ── Right tab sidebar ── */}
                <div style={{
                    width: `${TAB_SIDEBAR_WIDTH}px`,
                    minWidth: `${TAB_SIDEBAR_WIDTH}px`,
                    background: '#0A1020',
                    borderLeft: '1px solid rgba(201,168,76,0.12)',
                    display: 'flex',
                    flexDirection: 'column',
                    padding: '16px 8px',
                    gap: '4px',
                    overflowY: 'auto',
                }}>
                    <div style={{
                        fontSize: '9px',
                        fontWeight: '700',
                        color: '#4B5E72',
                        letterSpacing: '0.12em',
                        textTransform: 'uppercase',
                        padding: '0 8px 8px',
                    }}>
                        Analysis
                    </div>

                    {tabs.map(tab => {
                        const isActive = activeTab === tab.id;
                        return (
                            <TabButton
                                key={tab.id}
                                label={tab.label}
                                icon={tab.icon}
                                isActive={isActive}
                                disabled={!tab.implemented}
                                onClick={() => tab.implemented && setActiveTab(tab.id)}
                            />
                        );
                    })}

                    {/* Divider */}
                    <div style={{
                        margin: '10px 8px',
                        borderTop: '1px solid rgba(201,168,76,0.1)',
                    }} />

                    {/* All Addresses shortcut */}
                    <TabButton
                        label="All Addresses"
                        icon="◈"
                        isActive={isIndexView}
                        disabled={false}
                        accent
                        onClick={() => setActiveTab('all-addresses')}
                    />
                </div>
            </div>
        </div>
    );
};

/* ── Small helpers ── */

function TabButton({ label, icon, isActive, disabled, accent, onClick }) {
    const [hovered, setHovered] = useState(false);

    const activeColor  = accent ? '#C9A84C' : '#C9A84C';
    const hoverBg      = 'rgba(201,168,76,0.07)';
    const activeBg     = 'rgba(201,168,76,0.13)';
    const disabledColor = '#3A4E62';

    return (
        <button
            onClick={onClick}
            disabled={disabled}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '5px',
                padding: '10px 6px',
                borderRadius: '10px',
                border: isActive
                    ? '1px solid rgba(201,168,76,0.3)'
                    : '1px solid transparent',
                background: isActive ? activeBg : hovered && !disabled ? hoverBg : 'transparent',
                color: disabled ? disabledColor : isActive ? activeColor : hovered ? '#C9A84C' : '#8A9DB5',
                fontSize: '10px',
                fontWeight: isActive ? '700' : '500',
                cursor: disabled ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s',
                textAlign: 'center',
                lineHeight: 1.3,
                opacity: disabled ? 0.45 : 1,
                position: 'relative',
            }}
        >
            {/* Active indicator bar on the left */}
            {isActive && (
                <div style={{
                    position: 'absolute',
                    left: 0,
                    top: '20%',
                    height: '60%',
                    width: '3px',
                    borderRadius: '0 3px 3px 0',
                    background: '#C9A84C',
                }} />
            )}
            <span style={{ fontSize: '16px', lineHeight: 1 }}>{icon}</span>
            <span>{label}</span>
            {disabled && <span style={{ fontSize: '9px', color: '#3A4E62' }}>🔒</span>}
        </button>
    );
}

function PlaceholderTab({ icon, label, description }) {
    return (
        <div style={{ color: '#8A9DB5', textAlign: 'center', padding: '48px' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>{icon}</div>
            <div style={{ fontSize: '16px', fontWeight: '600', marginBottom: '8px' }}>
                {label} Coming Soon
            </div>
            <div style={{ fontSize: '13px', color: '#4B5E72' }}>{description}</div>
        </div>
    );
}

export default EntityIntelligenceWorkspace;
