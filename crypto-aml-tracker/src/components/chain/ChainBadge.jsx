/**
 * ChainBadge
 * Displays a compact colored pill showing chain name + asset.
 * Used inline on every address, transaction, alert, and cluster row.
 */
import React from 'react';

const CHAIN_META = {
    ethereum: { label: 'ETH', color: '#627EEA', bg: 'rgba(98,126,234,0.15)' },
    bnb: { label: 'BNB', color: '#F3BA2F', bg: 'rgba(243,186,47,0.15)' },
    polygon: { label: 'POL', color: '#8247E5', bg: 'rgba(130,71,229,0.15)' },
    arbitrum: { label: 'ARB', color: '#28A0F0', bg: 'rgba(40,160,240,0.15)' },
    base: { label: 'BASE', color: '#0052FF', bg: 'rgba(0,82,255,0.15)' },
    bitcoin: { label: 'BTC', color: '#F7931A', bg: 'rgba(247,147,26,0.15)' },
    litecoin: { label: 'LTC', color: '#BFBBBB', bg: 'rgba(191,187,187,0.15)' },
    dogecoin: { label: 'DOGE', color: '#C2A633', bg: 'rgba(194,166,51,0.15)' },
    bitcoin_cash: { label: 'BCH', color: '#8DC351', bg: 'rgba(141,195,81,0.15)' },
    solana: { label: 'SOL', color: '#9945FF', bg: 'rgba(153,69,255,0.15)' },
};

const TYPE_STYLE = {
    EVM: { label: 'Account based', color: '#60A5FA' },
    UTXO: { label: 'UTXO', color: '#FB923C' },
    ACCOUNT_BASED: { label: 'Account based', color: '#A78BFA' },
};

export default function ChainBadge({
    chain,           // chain_name string e.g. "ethereum"
    blockchainType,  // optional: "EVM" | "UTXO" | "ACCOUNT_BASED"
    showType = false,
    size = 'sm',     // 'xs' | 'sm' | 'md'
    style = {},
}) {
    const meta = CHAIN_META[chain?.toLowerCase?.()] || {
        label: chain?.toUpperCase?.()?.slice(0, 4) || '?',
        color: '#888',
        bg: 'rgba(136,136,136,0.15)',
    };
    const typeInfo = TYPE_STYLE[blockchainType] || null;

    const padding = size === 'xs' ? '2px 6px' : size === 'md' ? '4px 10px' : '3px 8px';
    const fontSize = size === 'xs' ? '10px' : size === 'md' ? '13px' : '11px';

    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: '4px',
            padding, fontSize, fontWeight: '700', fontFamily: 'sans-serif',
            color: meta.color,
            background: meta.bg,
            border: `1px solid ${meta.color}33`,
            borderRadius: '6px',
            whiteSpace: 'nowrap',
            ...style,
        }}>
            {meta.label}
            {showType && typeInfo && (
                <span style={{
                    fontSize: '9px', fontWeight: '600', color: typeInfo.color,
                    background: 'rgba(0,0,0,0.2)', borderRadius: '4px',
                    padding: '1px 4px',
                }}>
                    {typeInfo.label}
                </span>
            )}
        </span>
    );
}

/** Tiny helper: just the chain color */
export function chainColor(chain) {
    return (CHAIN_META[chain?.toLowerCase?.()]?.color) || '#888';
}

/** Get all known chain names */
export function knownChains() {
    return Object.keys(CHAIN_META);
}

export { CHAIN_META, TYPE_STYLE };
