const BACKEND_URL = 'http://localhost:4000/api/transactions';
const CLUSTER_URL = 'http://localhost:4000/api/clusters';

export const getLatestTransactions = async () => {
  const res = await fetch(BACKEND_URL);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const refreshTransactions = async () => {
  const res = await fetch(`${BACKEND_URL}/refresh`, { method: 'POST' });
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getGraphData = async (search = '') => {
  const url = search
    ? `${BACKEND_URL}/graph?search=${encodeURIComponent(search)}`
    : `${BACKEND_URL}/graph`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return await res.json();
};

export const getAlerts = async () => {
  const res = await fetch(`${BACKEND_URL}/alerts`);
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
