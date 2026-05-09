/**
 * FilterBar — shared filter controls for Placement and Layering pages.
 * All filters use AND logic.
 */
export default function FilterBar({
    search, onSearch,
    dateFrom, onDateFrom,
    dateTo, onDateTo,
    typeFilter, onTypeFilter, typeOptions, typeLabel,
    minScore, onMinScore,
    onClear,
    resultCount, totalCount,
}) {
    const inp = {
        padding: '7px 10px', borderRadius: '8px', border: '1px solid #e2e8f0',
        fontSize: '12px', outline: 'none', background: '#fff', color: '#0f172a',
    };
    const hasFilters = search || dateFrom || dateTo || (typeFilter && typeFilter !== 'All') || minScore > 0;

    return (
        <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '12px 16px', display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            {/* Search */}
            <input type="text" placeholder="Search entity, address, reason…"
                value={search} onChange={e => onSearch(e.target.value)}
                style={{ ...inp, minWidth: '220px', flex: 1 }} />

            {/* Date range */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '11px', color: '#64748b', whiteSpace: 'nowrap' }}>From</span>
                <input type="date" value={dateFrom} onChange={e => onDateFrom(e.target.value)} style={inp} />
                <span style={{ fontSize: '11px', color: '#64748b' }}>To</span>
                <input type="date" value={dateTo} onChange={e => onDateTo(e.target.value)} style={inp} />
            </div>

            {/* Type/algorithm filter */}
            {typeOptions && (
                <select value={typeFilter} onChange={e => onTypeFilter(e.target.value)}
                    style={{ ...inp, cursor: 'pointer' }}>
                    <option value="All">All {typeLabel || 'Types'}</option>
                    {typeOptions.map(o => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
                </select>
            )}

            {/* Min score */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '11px', color: '#64748b', whiteSpace: 'nowrap' }}>Min score</span>
                <input type="number" min="0" max="100" step="5" value={minScore}
                    onChange={e => onMinScore(parseInt(e.target.value) || 0)}
                    style={{ ...inp, width: '60px' }} />
            </div>

            {/* Clear */}
            {hasFilters && (
                <button onClick={onClear} style={{
                    padding: '7px 14px', borderRadius: '8px', border: '1px solid #fecaca',
                    background: '#fff5f5', color: '#dc2626', fontSize: '11px', fontWeight: '600', cursor: 'pointer',
                }}>✕ Clear</button>
            )}

            {/* Result count */}
            {resultCount !== undefined && (
                <span style={{ fontSize: '11px', color: '#94a3b8', marginLeft: 'auto', whiteSpace: 'nowrap' }}>
                    {resultCount}{totalCount !== undefined && totalCount !== resultCount ? ` / ${totalCount}` : ''} results
                </span>
            )}
        </div>
    );
}
