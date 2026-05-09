/**
 * Global filter store — persists filter state across page navigation.
 *
 * Strategy:
 *  1. Module-level object (_store) survives React re-renders and page navigation
 *     within the same SPA session.
 *  2. sessionStorage is used as a secondary layer so filters survive a manual
 *     browser refresh within the same tab session but are cleared when the tab
 *     is closed (intentional — analysts start fresh each session).
 *
 * Filter combination logic: AND — all active filters must match simultaneously.
 */

const DEFAULTS = {
    placement: {
        search:   '',
        dateFrom: '',
        dateTo:   '',
        behavior: 'All',
        minScore: 0,
        page:     0,
        limit:    50,
    },
    layering: {
        search:   '',
        dateFrom: '',
        dateTo:   '',
        method:   'All',
        minScore: 0,
        page:     0,
        limit:    50,
    },
};

function _loadFromSession(module) {
    try {
        const raw = sessionStorage.getItem(`aml_filters_${module}`);
        if (!raw) return null;
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

function _saveToSession(module, state) {
    try {
        sessionStorage.setItem(`aml_filters_${module}`, JSON.stringify(state));
    } catch {
        // sessionStorage unavailable — silently ignore
    }
}

const _store = {
    placement: { ...DEFAULTS.placement, ...(_loadFromSession('placement') || {}) },
    layering:  { ...DEFAULTS.layering,  ...(_loadFromSession('layering')  || {}) },
};

export function getFilters(module) {
    return { ..._store[module] };
}

export function setFilters(module, updates) {
    _store[module] = { ..._store[module], ...updates };
    _saveToSession(module, _store[module]);
}

export function resetFilters(module) {
    _store[module] = { ...DEFAULTS[module] };
    try { sessionStorage.removeItem(`aml_filters_${module}`); } catch { /* ignore */ }
}
