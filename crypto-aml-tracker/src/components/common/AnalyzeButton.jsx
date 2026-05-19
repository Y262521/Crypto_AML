/**
 * Analyze Button with Dropdown
 * Reusable button that shows 5 analysis options
 */

import { useState } from 'react';

const AnalyzeButton = ({ entityId, entityType, onSelectAnalysis }) => {
    const [showMenu, setShowMenu] = useState(false);

    const analysisOptions = [
        { id: 'market-value', label: 'Market Value', icon: '💰', available: true },
        { id: 'profit-ratio', label: 'Profit Ratio', icon: '📈', available: false },
        { id: 'exchange-flow', label: 'Exchange Flow', icon: '🔄', available: false },
        { id: 'holder-wave', label: 'Holder Wave', icon: '🌊', available: false },
        { id: 'address-network', label: 'Address Network', icon: '🕸️', available: false },
    ];

    return (
        <div style={{ position: 'relative' }}>
            <button
                onClick={() => setShowMenu(!showMenu)}
                style={{
                    padding: '8px 16px',
                    background: 'linear-gradient(135deg, rgba(201,168,76,0.15), rgba(201,168,76,0.08))',
                    border: '1px solid rgba(201,168,76,0.3)',
                    borderRadius: '8px',
                    color: '#C9A84C',
                    fontSize: '12px',
                    fontWeight: '700',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    width: '100%',
                    justifyContent: 'center',
                }}
            >
                🔍 Analyze
            </button>

            {showMenu && (
                <>
                    <div
                        style={{ position: 'fixed', inset: 0, zIndex: 998 }}
                        onClick={() => setShowMenu(false)}
                    />
                    <div style={{
                        position: 'absolute',
                        top: '100%',
                        right: 0,
                        marginTop: '4px',
                        background: 'linear-gradient(145deg, #101D32, #0D1628)',
                        border: '1px solid rgba(201,168,76,0.25)',
                        borderRadius: '10px',
                        boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
                        minWidth: '240px',
                        zIndex: 999,
                        overflow: 'hidden',
                    }}>
                        {analysisOptions.map((option, i) => (
                            <button
                                key={option.id}
                                onClick={() => {
                                    if (option.available) {
                                        setShowMenu(false);
                                        onSelectAnalysis(entityId, entityType, option.id);
                                    }
                                }}
                                disabled={!option.available}
                                style={{
                                    width: '100%',
                                    padding: '12px 16px',
                                    background: option.available ? 'rgba(201,168,76,0.05)' : 'rgba(255,255,255,0.02)',
                                    border: 'none',
                                    borderBottom: i < analysisOptions.length - 1 ? '1px solid rgba(201,168,76,0.08)' : 'none',
                                    cursor: option.available ? 'pointer' : 'not-allowed',
                                    textAlign: 'left',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '10px',
                                    opacity: option.available ? 1 : 0.4,
                                    transition: 'background 0.2s',
                                }}
                                onMouseEnter={(e) => {
                                    if (option.available) {
                                        e.currentTarget.style.background = 'rgba(201,168,76,0.12)';
                                    }
                                }}
                                onMouseLeave={(e) => {
                                    if (option.available) {
                                        e.currentTarget.style.background = 'rgba(201,168,76,0.05)';
                                    }
                                }}
                            >
                                <span style={{ fontSize: '18px' }}>{option.icon}</span>
                                <span style={{
                                    fontSize: '13px',
                                    fontWeight: '600',
                                    color: option.available ? '#E2D9C8' : '#4B5E72',
                                }}>
                                    {option.label}
                                </span>
                                {!option.available && (
                                    <span style={{
                                        marginLeft: 'auto',
                                        fontSize: '9px',
                                        padding: '2px 6px',
                                        background: 'rgba(255,255,255,0.1)',
                                        borderRadius: '4px',
                                        color: '#6B7E94',
                                    }}>
                                        SOON
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
};

export default AnalyzeButton;
