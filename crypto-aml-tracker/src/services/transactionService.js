const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:4001/api';
const BACKEND_URL = `${API_BASE_URL}/transactions`;
const CLUSTER_URL = `${API_BASE_URL}/clusters`;
const PLACEMENT_URL = `${API_BASE_URL}/placement`;
const LAYERING_URL = `${API_BASE_URL}/layering`;

export const getLatestTransactions = async ({ limit = 200, offset = 0, sortBy = 'amount_desc' } = {}) => {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    sort_by: sortBy,
  });
  const res = await fetch(`${BACKEND_URL}?${params.toString()}`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const refreshTransactions = async () => {
  const res = await fetch(`${BACKEND_URL}/refresh`, { method: 'POST' });
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getGraphData = async (options = '') => {
  if (typeof options === 'string') {
    const url = options
      ? `${BACKEND_URL}/graph?search=${encodeURIComponent(options)}`
      : `${BACKEND_URL}/graph`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Backend error: ${res.status}`);
    return await res.json();
  }

  const params = new URLSearchParams();
  if (options.search) params.set('search', options.search);
  if (options.center) params.set('center', options.center);
  if (options.hops !== undefined) params.set('hops', String(options.hops));
  if (options.maxEdges !== undefined) params.set('max_edges', String(options.maxEdges));
  if (options.minValue !== undefined) params.set('min_value', String(options.minValue));

  const url = params.toString()
    ? `${BACKEND_URL}/graph?${params.toString()}`
    : `${BACKEND_URL}/graph`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getAnalytics = async () => {
  const res = await fetch(`${BACKEND_URL}/analytics`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getClusters = async () => {
  const res = await fetch(CLUSTER_URL);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getClustersSummary = async () => {
  const res = await fetch(`${CLUSTER_URL}/summary`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const runClustering = async () => {
  const res = await fetch(`${CLUSTER_URL}/run`, { method: 'POST' });
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const createOwnerListEntry = async (payload) => {
  const res = await fetch(`${CLUSTER_URL}/owner-list`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (res.status === 409) {
    // Return the conflict payload with a _status marker so callers can branch
    const body = await res.json();
    return { _status: 409, ...body };
  }

  if (!res.ok) {
    let message = `Backend error: ${res.status}`;
    try {
      const error = await res.json();
      if (error?.detail) {
        message = typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail);
      }
    } catch {
      // Ignore non-JSON failures and keep the HTTP status message.
    }
    throw new Error(message);
  }

  return await res.json();
};

export const getOwnerByAddress = async (address) => {
  const res = await fetch(`${CLUSTER_URL}/owner-by-address/${encodeURIComponent(address)}`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getPlacements = async ({ limit = 50, minConfidence = 0, runId = null, beforeDate = null } = {}) => {
  const params = new URLSearchParams({
    limit: String(limit),
    min_confidence: String(minConfidence),
  });
  if (runId) params.set('run_id', runId);
  if (beforeDate) params.set('before_date', beforeDate);
  const res = await fetch(`${PLACEMENT_URL}?${params.toString()}`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getPlacementRuns = async () => {
  const res = await fetch(`${PLACEMENT_URL}/runs`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getPlacementSummary = async () => {
  const res = await fetch(`${PLACEMENT_URL}/summary`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getPlacementDetail = async (entityId) => {
  const res = await fetch(`${PLACEMENT_URL}/${encodeURIComponent(entityId)}`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getLayeringAlerts = async ({ limit = 50, minConfidence = 0, runId = null } = {}) => {
  const params = new URLSearchParams({
    limit: String(limit),
    min_confidence: String(minConfidence),
  });
  if (runId) params.set('run_id', runId);
  const res = await fetch(`${LAYERING_URL}?${params.toString()}`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getLayeringRuns = async () => {
  const res = await fetch(`${LAYERING_URL}/runs`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getLayeringSummary = async (runId = null) => {
  const url = runId
    ? `${LAYERING_URL}/summary?run_id=${encodeURIComponent(runId)}`
    : `${LAYERING_URL}/summary`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getLayeringDetail = async (entityId, runId = null) => {
  const params = new URLSearchParams();
  if (runId) params.set('run_id', runId);
  const url = params.toString()
    ? `${LAYERING_URL}/${encodeURIComponent(entityId)}?${params.toString()}`
    : `${LAYERING_URL}/${encodeURIComponent(entityId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

const INTEGRATION_URL = `${API_BASE_URL}/integration`;

export const getIntegrationAlerts = async ({ limit = 200, minScore = 0, runId = null, beforeDate = null, signal = null } = {}) => {
  const params = new URLSearchParams({ limit: String(limit), minScore: String(minScore) });
  if (runId) params.set('run_id', runId);
  if (beforeDate) params.set('beforeDate', beforeDate);
  if (signal) params.set('signal', signal);
  const res = await fetch(`${INTEGRATION_URL}/?${params.toString()}`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getIntegrationRuns = async () => {
  const res = await fetch(`${INTEGRATION_URL}/runs`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getIntegrationSummary = async (runId = null) => {
  const url = runId
    ? `${INTEGRATION_URL}/summary?run_id=${encodeURIComponent(runId)}`
    : `${INTEGRATION_URL}/summary`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};


export const getChainOfCustody = async (entityId) => {
  const res = await fetch(`${API_BASE_URL}/chain-of-custody/${encodeURIComponent(entityId)}`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const postIntegrationFeedback = async (entityId, payload) => {
  const res = await fetch(`${API_BASE_URL}/chain-of-custody/${encodeURIComponent(entityId)}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};
