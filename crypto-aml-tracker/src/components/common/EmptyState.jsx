/**
 * EmptyState — shown when filters return no results.
 */
export default function EmptyState({ onClearFilters, hasFilters }) {
    return (
        <div style={{
            padding: '48px 24px', textAlign: 'center',
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px',
        }}>
            <div style={{ fontSize: '36px' }}>🔍</div>
            <div style={{ fontSize: '15px', fontWeight: '700', color: '#475569' }}>
                No matching entities found
            </div>
            {hasFilters && (
                <>
                    <div style={{ fontSize: '12px', color: '#94a3b8', maxWidth: '320px', lineHeight: 1.6 }}>
                        Try adjusting your filters:
                    </div>
                    <ul style={{ fontSize: '12px', color: '#64748b', textAlign: 'left', margin: 0, paddingLeft: '20px', lineHeight: 1.8 }}>
                        <li>Expand the date range</li>
                        <li>Reduce algorithm / behavior filters</li>
                        <li>Lower the minimum risk score</li>
                    </ul>
                    <button onClick={onClearFilters} style={{
                        marginTop: '8px', padding: '8px 20px', borderRadius: '8px',
                        border: '1px solid #e2e8f0', background: '#fff',
                        color: '#475569', fontSize: '12px', fontWeight: '600', cursor: 'pointer',
                    }}>
                        Clear All Filters
                    </button>
                </>
            )}
            {!hasFilters && (
                <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                    No data available. Run the ETL pipeline to generate results.
                </div>
            )}
        </div>
    );
}
