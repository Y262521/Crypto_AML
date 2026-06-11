/**
 * ETL Control Center — API service layer.
 *
 * All functions throw on non-OK HTTP responses so callers can
 * display explicit error states without masking failures.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

const ETL_BASE = `${API_BASE}/etl`;
const DB_BASE  = `${API_BASE}/databases`;

async function _get(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`[${res.status}] ${text || res.statusText}`);
  }
  return res.json();
}

/** Live pipeline activity state, scheduler context, and per-stage health. */
export const getEtlStatus = () => _get(`${ETL_BASE}/status`);

/**
 * Paginated historical ETL run log.
 * @param {{ limit?: number, offset?: number, chain?: string }} opts
 */
export const getEtlHistory = ({ limit = 50, offset = 0, chain } = {}) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (chain) params.set('chain', chain);
  return _get(`${ETL_BASE}/history?${params}`);
};

/**
 * Pipeline error records.
 * @param {{ limit?: number, offset?: number }} opts
 */
export const getEtlErrors = ({ limit = 50, offset = 0 } = {}) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return _get(`${ETL_BASE}/errors?${params}`);
};

/** Connectivity, record counts, and latency for each database engine. */
export const getDatabasesHealth = () => _get(`${DB_BASE}/health`);
