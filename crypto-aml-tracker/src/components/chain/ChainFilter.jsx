/**
 * ChainFilter — Dropdown menu variant
 * Replaces the pill-button filter with a grouped <select> dropdown.
 * Groups chains by type: EVM / UTXO / Account-Based
 */
import React, { useEffect, useState } from 'react';
import { CHAIN_META } from './ChainBadge';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

const S = {
    border: 'rgba(201,168,76,0.18)',
    gold: '#C9A84C',
    textPrimary: '#E2D9C8',
    textSecondary: '#8A9DB5',
    textMuted: '#4B5E72',
    surface: 'rgba(10,16,32,0.9)',
    bg: 'rgba(201,168,76,0.06)',
};

// Static chain groups — shown even if no live data yet
const CHAIN_GROUPS = [
    {
        label: 'Account based',
        chains: [
            { chain_name: 'ethereum', display_name: 'Ethereum', native_asset: 'ETH' },
            { chain_name: 'bnb', display_name: 'BNB Chain', native_asset: 'BNB' },
            { chain_name: 'polygon', display_name: 'Polygon', native_asset: 'POL' },
            { chain_name: 'arbitrum', display_name: 'Arbitrum', native_asset: 'ETH' },
            { chain_name: 'base', display_name: 'Base', native_asset: 'ETH' },
            { chain_name: 'solana', display_name: 'Solana', native_asset: 'SOL' },
        ],
    },
    {
        label: 'UTXO Chains',
        chains: [
            { chain_name: 'bitcoin', display_name: 'Bitcoin', native_asset: 'BTC' },
            { chain_name: 'litecoin', display_name: 'Litecoin', native_asset: 'LTC' },
            { chain_name: 'dogecoin', display_name: 'Dogecoin', native_asset: 'DOGE' },
            { chain_name: 'bitcoin_cash', display_name: 'Bitcoin Cash', native_asset: 'BCH' },
        ],
    },
];

export default function ChainFilter({
    selectedChain = 'all',
    onChainChange,
    compact = false,
    label = 'Chain',
    countKey = 'tx_count',
    style = {},
}) {
    const [activeCounts, setActiveCounts] = useState({});

    // Fetch per-chain stats from /api/chains/stats
    useEffect(() => {
        fetch(`${API_BASE}/chains/stats`)
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                if (data?.chains) {
                    const counts = {};
                    data.chains.forEach(c => { counts[c.chain_name] = c[countKey] || 0; });
                    setActiveCounts(counts);
                }
            })
            .catch(() => { });
    }, []);

    const meta = CHAIN_META[selectedChain] || {};
    const selectedLabel = selectedChain === 'all'
        ? 'All Chains'
        : CHAIN_GROUPS
            .flatMap(g => g.chains)
            .find(c => c.chain_name === selectedChain)?.display_name || selectedChain;

    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            ...style,
        }}>
            {label && (
                <span style={{
                    fontSize: '11px',
                    fontWeight: '700',
                    color: S.textMuted,
                    textTransform: 'uppercase',
                    letterSpacing: '0.07em',
                    whiteSpace: 'nowrap',
                }}>
                    {label}
                </span>
            )}

            <div style={{ position: 'relative', display: 'inline-block' }}>
                {/* Color dot showing selected chain color */}
                {selectedChain !== 'all' && (
                    <span style={{
                        position: 'absolute',
                        left: '10px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        background: meta.color || S.gold,
                        pointerEvents: 'none',
                        zIndex: 1,
                    }} />
                )}

                <select
                    value={selectedChain}
                    onChange={e => onChainChange?.(e.target.value)}
                    style={{
                        appearance: 'none',
                        WebkitAppearance: 'none',
                        paddingLeft: selectedChain !== 'all' ? '26px' : '12px',
                        paddingRight: '28px',
                        paddingTop: compact ? '6px' : '8px',
                        paddingBottom: compact ? '6px' : '8px',
                        background: S.surface,
                        border: `1px solid ${selectedChain !== 'all' ? (meta.color + '55' || S.border) : S.border}`,
                        borderRadius: '9px',
                        color: selectedChain !== 'all' ? (meta.color || S.gold) : S.textPrimary,
                        fontSize: compact ? '12px' : '13px',
                        fontWeight: '600',
                        cursor: 'pointer',
                        outline: 'none',
                        minWidth: '160px',
                        boxShadow: selectedChain !== 'all'
                            ? `0 0 0 1px ${(meta.color || S.gold) + '33'}`
                            : 'none',
                        transition: 'all 0.15s',
                    }}
                >
                    <option value="all">All Chains</option>

                    {CHAIN_GROUPS.map(group => (
                        <optgroup key={group.label} label={group.label}>
                            {group.chains.map(chain => {
                                const count = activeCounts[chain.chain_name];
                                const suffix = count != null ? ` (${count.toLocaleString()})` : '';
                                return (
                                    <option key={chain.chain_name} value={chain.chain_name}>
                                        {chain.display_name} · {chain.native_asset}{suffix}
                                    </option>
                                );
                            })}
                        </optgroup>
                    ))}
                </select>

                {/* Custom chevron arrow */}
                <span style={{
                    position: 'absolute',
                    right: '10px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    pointerEvents: 'none',
                    color: S.textMuted,
                    fontSize: '10px',
                }}>
                    ▾
                </span>
            </div>
        </div>
    );
}
