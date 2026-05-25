/**
 * Valuation mode utilities — shared across MVRV and MVA components.
 * Supports USD mode (requires price data) and ETH mode (always available).
 */

import { useState, useCallback } from 'react';

export const MODES = { USD: 'USD', ETH: 'ETH' };

/**
 * Format a value according to the current valuation mode.
 * @param {number} usdValue   - value in USD
 * @param {number} ethValue   - value in ETH units
 * @param {'USD'|'ETH'} mode
 * @param {number} [decimals] - decimal places for ETH (default 4)
 */
export function fmtValue(usdValue, ethValue, mode, decimals = 4) {
  if (mode === MODES.ETH) {
    const v = Number(ethValue || 0);
    if (!Number.isFinite(v)) return '0 Ξ';
    if (v === 0) return '0 Ξ';
    if (Math.abs(v) < 1e-6) return v.toExponential(2) + ' Ξ';
    return v.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: decimals }) + ' Ξ';
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(usdValue || 0);
}

/**
 * Format a PnL value with sign prefix.
 */
export function fmtPnl(usdValue, ethValue, mode, decimals = 4) {
  const v = mode === MODES.ETH ? Number(ethValue || 0) : Number(usdValue || 0);
  const prefix = v > 0 ? '+' : '';
  return prefix + fmtValue(usdValue, ethValue, mode, decimals);
}

/**
 * Return the numeric value for the current mode.
 */
export function modeValue(usdValue, ethValue, mode) {
  return mode === MODES.ETH ? Number(ethValue || 0) : Number(usdValue || 0);
}

/**
 * Hook: manages valuation mode state with localStorage persistence.
 */
export function useValuationMode(defaultMode = MODES.USD) {
  const stored = typeof localStorage !== 'undefined'
    ? localStorage.getItem('mvrv_valuation_mode')
    : null;
  const [mode, setModeState] = useState(
    stored === MODES.ETH || stored === MODES.USD ? stored : defaultMode
  );

  const setMode = useCallback((m) => {
    setModeState(m);
    try { localStorage.setItem('mvrv_valuation_mode', m); } catch {}
  }, []);

  return [mode, setMode];
}

/**
 * ValuationToggle component — renders the USD | ETH pill toggle.
 */
export function ValuationToggle({ mode, onChange, style }) {
  const btnBase = {
    padding: '6px 14px',
    fontSize: '11px',
    fontWeight: '700',
    borderRadius: '7px',
    cursor: 'pointer',
    transition: 'all 0.15s',
    border: 'none',
    letterSpacing: '0.06em',
  };
  const active = {
    background: 'rgba(201,168,76,0.20)',
    color: '#C9A84C',
    boxShadow: 'inset 0 0 0 1px rgba(201,168,76,0.45)',
  };
  const inactive = {
    background: 'transparent',
    color: '#4B5E72',
    boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.07)',
  };

  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '2px',
      background: 'rgba(10,16,32,0.7)',
      borderRadius: '10px',
      padding: '3px',
      border: '1px solid rgba(201,168,76,0.14)',
      ...style,
    }}>
      <span style={{ fontSize: '10px', color: '#4B5E72', fontWeight: '700', paddingLeft: '6px', paddingRight: '4px', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        Display
      </span>
      {[MODES.USD, MODES.ETH].map(m => (
        <button
          key={m}
          onClick={() => onChange(m)}
          style={{ ...btnBase, ...(mode === m ? active : inactive) }}
        >
          {m === MODES.USD ? '$ USD' : 'Ξ ETH'}
        </button>
      ))}
    </div>
  );
}
