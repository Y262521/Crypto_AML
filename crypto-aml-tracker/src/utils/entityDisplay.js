/**
 * Entity display resolution — enforces attribution priority:
 * 1. owner_list.full_name
 * 2. entity label
 * 3. cluster ID (short)
 * 4. address (tooltip only)
 */

export function resolveEntityName(entity) {
    if (!entity) return 'Unknown Entity';
    // Priority 1: owner full name
    if (entity.owner?.full_name) return entity.owner.full_name;
    if (entity.full_name)        return entity.full_name;
    // Priority 2: label
    if (entity.label_name)       return entity.label_name;
    if (entity.display_name && entity.display_name !== 'Unknown') return entity.display_name;
    // Priority 3: cluster ID (short, not raw address)
    const eid = entity.entity_id || entity.cluster_id || entity.id || '';
    if (eid && !eid.startsWith('0x')) return shortId(eid);
    // Priority 4: address as last resort (truncated)
    if (eid) return `${eid.slice(0, 8)}…${eid.slice(-6)}`;
    return 'Unknown Entity';
}

export function shortId(id) {
    if (!id) return '—';
    if (id.length <= 16) return id;
    return `${id.slice(0, 10)}…${id.slice(-6)}`;
}

export function entityColor(entity) {
    if (entity?.is_poi || entity?.poi)                          return '#dc2626'; // red
    const score = parseFloat(entity?.risk_score || entity?.placement_score || 0);
    if (score >= 0.8)                                           return '#dc2626'; // red
    if (score >= 0.5)                                           return '#d97706'; // orange
    return '#334155'; // neutral
}

export function entityBg(entity) {
    if (entity?.is_poi || entity?.poi)                          return '#fee2e2';
    const score = parseFloat(entity?.risk_score || entity?.placement_score || 0);
    if (score >= 0.8)                                           return '#fee2e2';
    if (score >= 0.5)                                           return '#fef3c7';
    return '#f8fafc';
}

export function poiBadge(entity) {
    if (entity?.is_poi || entity?.poi) {
        return { show: true, label: '🔴 POI', color: '#dc2626', bg: '#fee2e2' };
    }
    const score = parseFloat(entity?.risk_score || entity?.placement_score || 0);
    if (score >= 0.8) return { show: true, label: '🔴 HIGH RISK', color: '#dc2626', bg: '#fee2e2' };
    if (score >= 0.5) return { show: true, label: '🟠 ELEVATED', color: '#d97706', bg: '#fef3c7' };
    return { show: false };
}
