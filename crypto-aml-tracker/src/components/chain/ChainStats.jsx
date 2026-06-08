/**
 * ChainStats
 * Shows a compact per-chain transaction count summary as clickable chips.
 * Fetches from GET /api/chains/stats.
 */
import React, { useEffect, useState } from 'react';
import ChainBadge, { CHAIN_META } from './ChainBadge';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

export default function ChainStats({ onChainClick, selectedChain = 'all' }) {
    const [stats, setStats] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        setLoading(true);
        fetch(`${API_BASE}/chains/stats`)
            .then(r => r.ok ? r.json() : null)
            .then(data => { if (data?.chains) setStats(data.chains); })
            .catch(() => { })
            .finally(() => setLoading(false));
    }, []);

    if (loading || stats.length === 0) return null;

    return (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', color: '#4B5E72', fontWeight: '600', marginRight: '2px' }}>
                Live data:
            </span>
            {stats.map(chain => {
                const isSelected = selectedChain === chain.chain_name;
                const meta = CHAIN_META[chain.chain_name] || {};
                return (
                    <button
                        key={chain.chain_name}
                        onClick={() => onChainClick?.(isSelected ? 'all' : chain.chain_name)}
                        title={`${chain.display_name}: ${(chain.tx_count || 0).toLocaleString()} transactions`}
                        style={{
                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                            padding: '3px 9px',
                            background: isSelected ? (meta.bg || 'rgba(201,168,76,0.08)') : 'rgba(255,255,255,0.03)',
                            border: `1px solid ${isSelected ? ((meta.color || '#C9A84C') + '55') : 'rgba(201,168,76,0.12)'}`,
                            borderRadius: '20px',
                            cursor: 'pointer', outline: 'none', transition: 'all 0.15s',
                        }}
                    >
                        <ChainBadge chain={chain.chain_name} size="xs" />
                        <span style={{ fontSize: '10px', color: '#4B5E72', fontFamily: 'monospace' }}>
                            {(chain.tx_count || 0).toLocaleString()}
                        </span>
                    </button>
                );
            })}
        </div>
    );
}
