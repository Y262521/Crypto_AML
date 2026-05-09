/**
 * Pagination — server-side pagination controls.
 */
export default function Pagination({ page, limit, total, onPage, onLimit }) {
    const totalPages = Math.max(1, Math.ceil(total / limit));
    const btn = (disabled) => ({
        padding: '6px 14px', borderRadius: '7px', border: '1px solid #e2e8f0',
        background: disabled ? '#f1f5f9' : '#fff',
        color: disabled ? '#94a3b8' : '#334155',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontSize: '12px', fontWeight: '600',
    });

    return (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderTop: '1px solid #f1f5f9', background: '#fff', borderRadius: '0 0 12px 12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button style={btn(page === 0)} disabled={page === 0} onClick={() => onPage(0)}>«</button>
                <button style={btn(page === 0)} disabled={page === 0} onClick={() => onPage(page - 1)}>‹ Prev</button>
                <span style={{ fontSize: '12px', color: '#64748b', padding: '0 8px' }}>
                    Page <b>{page + 1}</b> of <b>{totalPages}</b>
                </span>
                <button style={btn(page >= totalPages - 1)} disabled={page >= totalPages - 1} onClick={() => onPage(page + 1)}>Next ›</button>
                <button style={btn(page >= totalPages - 1)} disabled={page >= totalPages - 1} onClick={() => onPage(totalPages - 1)}>»</button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '11px', color: '#94a3b8' }}>Rows per page</span>
                <select value={limit} onChange={e => { onLimit(parseInt(e.target.value)); onPage(0); }}
                    style={{ padding: '5px 8px', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '12px', cursor: 'pointer' }}>
                    {[25, 50, 100, 200].map(n => <option key={n} value={n}>{n}</option>)}
                </select>
                <span style={{ fontSize: '11px', color: '#94a3b8' }}>Total: {total}</span>
            </div>
        </div>
    );
}
