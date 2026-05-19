/**
 * Analysis Menu Component
 * 
 * Dropdown menu that appears when clicking an address/cluster.
 * Shows 5 on-chain intelligence analysis options.
 */

import { useState, useEffect, useRef } from 'react';

const AnalysisMenu = ({ 
    entityId, 
    entityType = 'address',
    position = { x: 0, y: 0 },
    onSelect,
    onClose 
}) => {
    const menuRef = useRef(null);

    const analysisOptions = [
        {
            id: 'market-value',
            label: 'Market Value Analysis',
            icon: '💰',
            description: 'Portfolio value and asset holdings',
            implemented: true,
        },
        {
            id: 'profit-ratio',
            label: 'Profit Ratio Analysis',
            icon: '📈',
            description: 'Realized and unrealized gains',
            implemented: false,
        },
        {
            id: 'exchange-flow',
            label: 'Exchange Net Flow',
            icon: '🔄',
            description: 'Deposits and withdrawals to exchanges',
            implemented: false,
        },
        {
            id: 'holder-wave',
            label: 'Holder Wave Analysis',
            icon: '🌊',
            description: 'Holding patterns and movements',
            implemented: false,
        },
        {
            id: 'address-network',
            label: 'Active Address Edge Network',
            icon: '🕸️',
            description: 'Network usage and connections',
            implemented: false,
        },
    ];

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                onClose();
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [onClose]);

    // Close on Escape key
    useEffect(() => {
        const handleEscape = (event) => {
            if (event.key === 'Escape') {
                onClose();
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [onClose]);

    const handleSelect = (analysisId, implemented) => {
        if (implemented) {
            onSelect(analysisId);
        }
    };

    return (
        <div
            ref={menuRef}
            style={{
                position: 'fixed',
                top: `${position.y}px`,
                left: `${position.x}px`,
                zIndex: 2000,
                background: 'linear-gradient(145deg, #101D32, #0D1628)',
                border: '1px solid rgba(201,168,76,0.25)',
                borderRadius: '12px',
                boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
                minWidth: '320px',
                maxWidth: '400px',
                overflow: 'hidden',
            }}
        >
            {/* Header */}
            <div style={{
                padding: '16px 20px',
                borderBottom: '1px solid rgba(201,168,76,0.12)',
                background: 'rgba(201,168,76,0.05)',
            }}>
                <div style={{
                    fontSize: '11px',
                    fontWeight: '700',
                    color: '#8A9DB5',
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    marginBottom: '6px',
                }}>
                    {entityType === 'cluster' ? '🔗 Cluster' : '💼 Address'} Intelligence
                </div>
                <div style={{
                    fontSize: '12px',
                    fontFamily: 'monospace',
                    color: '#C9A84C',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                }}>
                    {entityId}
                </div>
            </div>

            {/* Analysis Options */}
            <div style={{ padding: '8px' }}>
                {analysisOptions.map((option, idx) => (
                    <button
                        key={option.id}
                        onClick={() => handleSelect(option.id, option.implemented)}
                        disabled={!option.implemented}
                        style={{
                            width: '100%',
                            padding: '12px 16px',
                            marginBottom: idx < analysisOptions.length - 1 ? '4px' : 0,
                            background: option.implemented 
                                ? 'rgba(201,168,76,0.05)' 
                                : 'rgba(255,255,255,0.02)',
                            border: '1px solid rgba(201,168,76,0.12)',
                            borderRadius: '8px',
                            cursor: option.implemented ? 'pointer' : 'not-allowed',
                            textAlign: 'left',
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: '12px',
                            transition: 'all 0.2s',
                            opacity: option.implemented ? 1 : 0.5,
                        }}
                        onMouseEnter={(e) => {
                            if (option.implemented) {
                                e.currentTarget.style.background = 'rgba(201,168,76,0.12)';
                                e.currentTarget.style.borderColor = 'rgba(201,168,76,0.3)';
                            }
                        }}
                        onMouseLeave={(e) => {
                            if (option.implemented) {
                                e.currentTarget.style.background = 'rgba(201,168,76,0.05)';
                                e.currentTarget.style.borderColor = 'rgba(201,168,76,0.12)';
                            }
                        }}
                    >
                        <div style={{ fontSize: '24px', lineHeight: 1 }}>
                            {option.icon}
                        </div>
                        <div style={{ flex: 1 }}>
                            <div style={{
                                fontSize: '13px',
                                fontWeight: '700',
                                color: option.implemented ? '#E2D9C8' : '#4B5E72',
                                marginBottom: '4px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                            }}>
                                {option.label}
                                {!option.implemented && (
                                    <span style={{
                                        fontSize: '9px',
                                        padding: '2px 6px',
                                        background: 'rgba(255,255,255,0.1)',
                                        borderRadius: '4px',
                                        color: '#6B7E94',
                                    }}>
                                        COMING SOON
                                    </span>
                                )}
                            </div>
                            <div style={{
                                fontSize: '11px',
                                color: '#6B7E94',
                                lineHeight: '1.4',
                            }}>
                                {option.description}
                            </div>
                        </div>
                    </button>
                ))}
            </div>

            {/* Footer */}
            <div style={{
                padding: '12px 20px',
                borderTop: '1px solid rgba(201,168,76,0.08)',
                background: 'rgba(0,0,0,0.2)',
                fontSize: '10px',
                color: '#4B5E72',
                textAlign: 'center',
            }}>
                Press ESC to close • Click outside to dismiss
            </div>
        </div>
    );
};

export default AnalysisMenu;
