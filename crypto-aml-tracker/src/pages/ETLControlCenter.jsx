/**
 * ETL Control Center
 *
 * A single-purpose dashboard for monitoring the blockchain ingestion and
 * ETL pipeline. Zero mock data — every value comes from the backend APIs
 * or is mapped to an explicit empty-state label.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { getEtlStatus, getEtlHistory, getEtlErrors, getDatabasesHealth } from '../services/etlService';
import ChainFilter from '../components/chain/ChainFilter';

// ── constants ─────────────────────────────────────────────────────────────────

const POLL_MS           = 30_000;
const HISTORY_PAGE_SIZE = 10;
const ERRORS_PAGE_SIZE  = 10;

const STAGE_ORDER = ['extract', 'normalize', 'load', 'store', 'ready'];
const STAGE_LABELS = {
  extract:   'Extract',
  normalize: 'Normalize',
  load:      'Load',
  store:     'Store',
  ready:     'Ready for Analysis',
};

const SUPPORTED_CHAINS = [
  'ethereum', 'bnb', 'polygon', 'arbitrum', 'base', 'solana',
  'bitcoin', 'litecoin', 'dogecoin', 'bitcoin_cash'
];

// ── palette helpers ───────────────────────────────────────────────────────────

const STATUS_COLOR = {
  success: { dot: '#22c55e', text: '#4ade80', bg: 'rgba(34,197,94,0.10)',   border: 'rgba(34,197,94,0.25)'  },
  running: { dot: '#facc15', text: '#fde047', bg: 'rgba(250,204,21,0.10)',  border: 'rgba(250,204,21,0.25)' },
  failed:  { dot: '#ef4444', text: '#f87171', bg: 'rgba(239,68,68,0.10)',   border: 'rgba(239,68,68,0.25)'  },
  idle:    { dot: '#64748b', text: '#94a3b8', bg: 'rgba(100,116,139,0.08)', border: 'rgba(100,116,139,0.2)' },
  never:   { dot: '#64748b', text: '#94a3b8', bg: 'rgba(100,116,139,0.08)', border: 'rgba(100,116,139,0.2)' },
  offline: { dot: '#ef4444', text: '#f87171', bg: 'rgba(239,68,68,0.10)',   border: 'rgba(239,68,68,0.25)'  },
  online:  { dot: '#22c55e', text: '#4ade80', bg: 'rgba(34,197,94,0.10)',   border: 'rgba(34,197,94,0.25)'  },
};

const stageColor = (status) => {
  if (status === 'success') return '#22c55e';
  if (status === 'running') return '#facc15';
  if (status === 'failed')  return '#ef4444';
  return '#475569';
};

const statusPalette = (s) => STATUS_COLOR[s] || STATUS_COLOR.idle;

// ── formatting ────────────────────────────────────────────────────────────────

const fmtTs = (iso) => {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch { return iso; }
};

const fmtDuration = (seconds) => {
  if (seconds == null) return null;
  const s = Math.round(seconds);
  if (s === 0)  return '< 1s';
  if (s < 60)   return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
};

const fmtNum = (n) => {
  if (n == null) return null;
  return Number(n).toLocaleString();
};

const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '');

// ── sub-components ────────────────────────────────────────────────────────────

function EmptyState({ label = 'No data yet' }) {
  return <span style={{ color: '#475569', fontStyle: 'italic', fontSize: '12px' }}>{label}</span>;
}

function StatusBadge({ status, label }) {
  const p = statusPalette(status);
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '5px',
      padding: '3px 10px', borderRadius: '999px',
      background: p.bg, border: `1px solid ${p.border}`,
      fontSize: '11px', fontWeight: '700', color: p.text,
      textTransform: 'uppercase', letterSpacing: '0.07em',
    }}>
      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: p.dot, flexShrink: 0 }} />
      {label || capitalize(status)}
    </span>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{
      background: 'linear-gradient(145deg,#101D32,#0D1628)',
      border: '1px solid rgba(201,168,76,0.12)',
      borderRadius: '14px',
      padding: '20px 22px',
      ...style,
    }}>
      {children}
    </div>
  );
}

function CardLabel({ children }) {
  return (
    <div style={{ fontSize: '10px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>
      {children}
    </div>
  );
}

function MetricRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '12px', padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      <span style={{ fontSize: '11px', color: '#64748b' }}>{label}</span>
      <span style={{ fontSize: '12px', fontWeight: '600', color: '#cbd5e1', wordBreak: 'break-all', textAlign: 'right' }}>
        {value ?? <EmptyState label="No data yet" />}
      </span>
    </div>
  );
}

function SectionHeading({ children }) {
  return (
    <div style={{ fontSize: '11px', fontWeight: '700', color: '#C9A84C', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: '12px' }}>
      {children}
    </div>
  );
}

// ── Pipeline Stepper ──────────────────────────────────────────────────────────

function PipelineStepper({ stages = [], onSelect }) {
  const [expanded, setExpanded] = useState(null);

  const stageMap = {};
  for (const s of stages) {
    const key = (s.name || '').toLowerCase().replace(/\s.*/, '');
    stageMap[key] = s;
  }

  return (
    <Card style={{ padding: '22px 24px' }}>
      <SectionHeading>Pipeline Flow</SectionHeading>
      <div style={{ display: 'flex', alignItems: 'stretch', gap: 0, overflowX: 'auto', paddingBottom: '4px' }}>
        {STAGE_ORDER.map((key, i) => {
          const stage = stageMap[key] || { name: STAGE_LABELS[key], status: 'idle' };
          const color = stageColor(stage.status);
          const isLast = i === STAGE_ORDER.length - 1;
          const isExpanded = expanded === key;

          return (
            <div key={key} style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1, minWidth: '90px', position: 'relative' }}>
                <button
                  onClick={() => { setExpanded(isExpanded ? null : key); if (onSelect) onSelect(stage); }}
                  title={`${STAGE_LABELS[key]} — ${stage.status}`}
                  style={{
                    width: '42px', height: '42px', borderRadius: '50%',
                    background: `radial-gradient(circle, ${color}33 0%, ${color}11 100%)`,
                    border: `2px solid ${color}`, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '16px',
                    boxShadow: stage.status === 'running' ? `0 0 12px ${color}88` : 'none',
                    transition: 'box-shadow 0.3s',
                  }}
                >
                  {stage.status === 'success' && <span style={{ color }}>✓</span>}
                  {stage.status === 'running' && <span style={{ color }}>◎</span>}
                  {stage.status === 'failed'  && <span style={{ color }}>✕</span>}
                  {(stage.status === 'idle' || stage.status === 'never') && <span style={{ color }}>○</span>}
                </button>

                <div style={{ fontSize: '10px', fontWeight: '700', color: '#94a3b8', marginTop: '6px', textAlign: 'center', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
                  {STAGE_LABELS[key]}
                </div>
                <div style={{ marginTop: '3px' }}>
                  <StatusBadge status={stage.status} />
                </div>

                {isExpanded && stage.detail && (
                  <div style={{
                    position: 'absolute', top: '64px', left: '50%', transform: 'translateX(-50%)',
                    background: '#0d1628', border: '1px solid rgba(201,168,76,0.2)',
                    borderRadius: '10px', padding: '10px 14px', zIndex: 10,
                    minWidth: '180px', boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                  }}>
                    {Object.entries(stage.detail).map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', fontSize: '11px', color: '#94a3b8', padding: '2px 0' }}>
                        <span>{k.replaceAll('_', ' ')}</span>
                        <span style={{ color: '#e2c97e', fontWeight: '700' }}>{fmtNum(v) ?? <EmptyState />}</span>
                      </div>
                    ))}
                  </div>
                )}
                {isExpanded && !stage.detail && (
                  <div style={{
                    position: 'absolute', top: '64px', left: '50%', transform: 'translateX(-50%)',
                    background: '#0d1628', border: '1px solid rgba(201,168,76,0.15)',
                    borderRadius: '10px', padding: '8px 14px', zIndex: 10,
                    fontSize: '11px', color: '#475569', fontStyle: 'italic',
                    whiteSpace: 'nowrap', boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                  }}>
                    No metrics available
                  </div>
                )}
              </div>

              {!isLast && (
                <div style={{
                  width: '28px', height: '2px',
                  background: `linear-gradient(90deg, ${color}, ${stageColor((stageMap[STAGE_ORDER[i + 1]] || {}).status)})`,
                  flexShrink: 0, marginBottom: '28px',
                }} />
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ── History Table ─────────────────────────────────────────────────────────────

const paginationBtnStyle = (disabled) => ({
  padding: '5px 12px', borderRadius: '8px', fontSize: '11px', fontWeight: '600',
  background: disabled ? 'rgba(255,255,255,0.03)' : 'rgba(201,168,76,0.08)',
  color: disabled ? '#334155' : '#C9A84C',
  border: `1px solid ${disabled ? 'rgba(255,255,255,0.06)' : 'rgba(201,168,76,0.2)'}`,
  cursor: disabled ? 'not-allowed' : 'pointer',
});

function HistoryTable({ items, total, page, onPage, onSelect }) {
  const totalPages = Math.max(1, Math.ceil(total / HISTORY_PAGE_SIZE));
  const cols = [
    { key: 'run_id',                  label: 'Run ID',     width: '160px' },
    { key: 'chain_target',            label: 'Chain',      width: '80px'  },
    { key: 'start_time',              label: 'Start',      width: '140px' },
    { key: 'end_time',                label: 'End',        width: '140px' },
    { key: 'duration_seconds',        label: 'Duration',   width: '80px'  },
    { key: 'status',                  label: 'Status',     width: '100px' },
  ];

  return (
    <div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
          <thead>
            <tr style={{ background: '#132240' }}>
              {cols.map(c => (
                <th key={c.key} style={{ padding: '9px 12px', textAlign: 'left', fontSize: '10px', fontWeight: '800', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', whiteSpace: 'nowrap', width: c.width }}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr>
                <td colSpan={cols.length} style={{ padding: '32px', textAlign: 'center', color: '#475569', fontStyle: 'italic', fontSize: '13px' }}>
                  No historical runs yet
                </td>
              </tr>
            )}
            {items.map((row, idx) => (
              <tr
                key={row.run_id || idx}
                onClick={() => onSelect && onSelect(row)}
                style={{ background: idx % 2 === 0 ? '#0d1628' : '#101d32', cursor: 'pointer', transition: 'background 0.12s', borderBottom: '1px solid rgba(201,168,76,0.06)' }}
                onMouseEnter={e => e.currentTarget.style.background = '#132240'}
                onMouseLeave={e => e.currentTarget.style.background = idx % 2 === 0 ? '#0d1628' : '#101d32'}
              >
                <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: '#C9A84C', maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.run_id}>
                  {row.run_id ? row.run_id.slice(0, 16) + '…' : <EmptyState />}
                </td>
                <td style={{ padding: '10px 12px', color: '#94a3b8', textTransform: 'capitalize' }}>{row.chain_target || <EmptyState label="Unavailable" />}</td>
                <td style={{ padding: '10px 12px', color: '#94a3b8', whiteSpace: 'nowrap' }}>{fmtTs(row.start_time) || <EmptyState label="Unavailable" />}</td>
                <td style={{ padding: '10px 12px', color: '#94a3b8', whiteSpace: 'nowrap' }}>{fmtTs(row.end_time) || (row.status === 'running' ? <span style={{ color: '#facc15', fontStyle: 'italic', fontSize: '12px' }}>Running…</span> : <EmptyState label="Unavailable" />)}</td>
                <td style={{ padding: '10px 12px', color: '#94a3b8' }}>
                  {row.status === 'running'
                    ? <span style={{ color: '#facc15', fontStyle: 'italic', fontSize: '12px' }}>Running…</span>
                    : row.duration_seconds != null
                      ? fmtDuration(row.duration_seconds)
                      : <EmptyState label="Unavailable" />}
                </td>
                <td style={{ padding: '10px 12px' }}>
                  <StatusBadge status={row.status === 'completed' ? 'success' : row.status || 'idle'} label={row.status || 'Idle'} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', borderTop: '1px solid rgba(201,168,76,0.08)' }}>
        <span style={{ fontSize: '11px', color: '#475569' }}>{total} total runs — page {page} of {totalPages}</span>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button disabled={page <= 1} onClick={() => onPage(page - 1)} style={paginationBtnStyle(page <= 1)}>← Prev</button>
          <button disabled={page >= totalPages} onClick={() => onPage(page + 1)} style={paginationBtnStyle(page >= totalPages)}>Next →</button>
        </div>
      </div>
    </div>
  );
}

// ── Error Console ─────────────────────────────────────────────────────────────

const SEVERITY_STYLE = {
  fatal:    { bg: 'rgba(239,68,68,0.14)', border: 'rgba(239,68,68,0.35)', text: '#f87171' },
  critical: { bg: 'rgba(239,68,68,0.10)', border: 'rgba(239,68,68,0.25)', text: '#fca5a5' },
  warning:  { bg: 'rgba(251,191,36,0.10)', border: 'rgba(251,191,36,0.25)', text: '#fde047' },
  info:     { bg: 'rgba(96,165,250,0.08)',  border: 'rgba(96,165,250,0.2)',  text: '#93c5fd' },
};

function ErrorConsole({ items, total, page, onPage, onSelect }) {
  const totalPages = Math.max(1, Math.ceil(total / ERRORS_PAGE_SIZE));
  return (
    <div>
      {items.length === 0 && (
        <div style={{ padding: '32px', textAlign: 'center', color: '#22c55e', fontSize: '13px' }}>
          ✓ No pipeline exceptions recorded
        </div>
      )}
      {items.map((err, idx) => {
        const style = SEVERITY_STYLE[err.severity] || SEVERITY_STYLE.info;
        return (
          <div
            key={err.error_id || idx}
            onClick={() => onSelect && onSelect(err)}
            style={{
              display: 'grid', gridTemplateColumns: '140px 70px 90px 1fr 160px',
              gap: '12px', padding: '12px 16px',
              background: idx % 2 === 0 ? '#0a1220' : '#0d1628',
              borderLeft: `3px solid ${style.border}`,
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              cursor: 'pointer', alignItems: 'start', transition: 'background 0.12s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = '#132240'}
            onMouseLeave={e => e.currentTarget.style.background = idx % 2 === 0 ? '#0a1220' : '#0d1628'}
          >
            <div style={{ fontSize: '11px', color: '#64748b', whiteSpace: 'nowrap' }}>
              {fmtTs(err.timestamp) || <EmptyState label="No data yet" />}
            </div>
            <div>
              <span style={{ fontSize: '10px', fontWeight: '800', padding: '2px 7px', borderRadius: '999px', background: style.bg, border: `1px solid ${style.border}`, color: style.text, textTransform: 'uppercase' }}>
                {err.severity || 'info'}
              </span>
            </div>
            <div style={{ fontSize: '11px', color: '#94a3b8' }}>{err.phase || <EmptyState />}</div>
            <div style={{ fontSize: '12px', color: '#cbd5e1', lineHeight: '1.5' }}>{err.message || <EmptyState />}</div>
            <div style={{ fontSize: '10px', color: '#64748b', textAlign: 'right', wordBreak: 'break-word' }}>
              {err.recovery_state ? err.recovery_state.replaceAll('_', ' ') : <EmptyState label="No data yet" />}
            </div>
          </div>
        );
      })}
      {total > ERRORS_PAGE_SIZE && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 16px', borderTop: '1px solid rgba(201,168,76,0.08)' }}>
          <span style={{ fontSize: '11px', color: '#475569' }}>{total} total — page {page} of {totalPages}</span>
          <div style={{ display: 'flex', gap: '6px' }}>
            <button disabled={page <= 1} onClick={() => onPage(page - 1)} style={paginationBtnStyle(page <= 1)}>← Prev</button>
            <button disabled={page >= totalPages} onClick={() => onPage(page + 1)} style={paginationBtnStyle(page >= totalPages)}>Next →</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Detail Drawer ─────────────────────────────────────────────────────────────

function DetailDrawer({ item, onClose }) {
  if (!item) return null;
  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0,
      width: '420px', maxWidth: '90vw', background: '#080f1e',
      borderLeft: '1px solid rgba(201,168,76,0.2)',
      zIndex: 200, display: 'flex', flexDirection: 'column',
      boxShadow: '-8px 0 40px rgba(0,0,0,0.6)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid rgba(201,168,76,0.14)' }}>
        <span style={{ fontSize: '13px', fontWeight: '700', color: '#C9A84C' }}>Record Detail</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '18px', lineHeight: 1 }}>×</button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
        <pre style={{ margin: 0, fontSize: '11px', lineHeight: '1.65', color: '#94a3b8', whiteSpace: 'pre-wrap', wordBreak: 'break-all', background: '#0a1220', padding: '14px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.06)' }}>
          {JSON.stringify(item, null, 2)}
        </pre>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ETLControlCenter() {
  const [status,   setStatus]   = useState(null);
  const [history,  setHistory]  = useState({ items: [], total: 0 });
  const [errors,   setErrors]   = useState({ items: [], total: 0 });

  const [statusLoading, setStatusLoading] = useState(true);
  const [histLoading,   setHistLoading]   = useState(true);
  const [errLoading,    setErrLoading]    = useState(true);

  const [statusErr,  setStatusErr]  = useState(null);
  const [histErr,    setHistErr]    = useState(null);
  const [errConsErr, setErrConsErr] = useState(null);

  const [histPage,  setHistPage]  = useState(1);
  const [errPage,   setErrPage]   = useState(1);
  const [selectedChain, setSelectedChain] = useState('all');
  const [detailItem,    setDetailItem]    = useState(null);
  const [refreshedAt,   setRefreshedAt]   = useState(null);

  // Refs so the polling interval always sees the latest page/chain values
  const histPageRef     = useRef(histPage);
  const errPageRef      = useRef(errPage);
  const selectedChainRef = useRef(selectedChain);
  const intervalRef     = useRef(null);

  useEffect(() => { histPageRef.current      = histPage;      }, [histPage]);
  useEffect(() => { errPageRef.current       = errPage;       }, [errPage]);
  useEffect(() => { selectedChainRef.current = selectedChain; }, [selectedChain]);

  // ── fetch functions ───────────────────────────────────────────────────────

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getEtlStatus();
      setStatus(data);
      setStatusErr(null);
    } catch (e) {
      setStatusErr(e.message);
    } finally {
      setStatusLoading(false);
    }
  }, []);

  const fetchHistory = useCallback(async (page, chain) => {
    setHistLoading(true);
    try {
      const c = (chain ?? selectedChainRef.current) !== 'all'
        ? (chain ?? selectedChainRef.current)
        : undefined;
      const data = await getEtlHistory({
        limit:  HISTORY_PAGE_SIZE,
        offset: ((page ?? histPageRef.current) - 1) * HISTORY_PAGE_SIZE,
        chain:  c,
      });
      setHistory(data);
      setHistErr(null);
    } catch (e) {
      setHistErr(e.message);
    } finally {
      setHistLoading(false);
    }
  }, []);

  const fetchErrors = useCallback(async (page) => {
    setErrLoading(true);
    try {
      const data = await getEtlErrors({
        limit:  ERRORS_PAGE_SIZE,
        offset: ((page ?? errPageRef.current) - 1) * ERRORS_PAGE_SIZE,
      });
      setErrors(data);
      setErrConsErr(null);
    } catch (e) {
      setErrConsErr(e.message);
    } finally {
      setErrLoading(false);
    }
  }, []);

  const refreshAll = useCallback(() => {
    fetchStatus();
    fetchHistory(histPageRef.current, selectedChainRef.current);
    fetchErrors(errPageRef.current);
    setRefreshedAt(new Date());
  }, [fetchStatus, fetchHistory, fetchErrors]);

  // Initial load + stable polling interval
  useEffect(() => {
    refreshAll();
    intervalRef.current = setInterval(refreshAll, POLL_MS);
    return () => clearInterval(intervalRef.current);
  }, [refreshAll]);

  useEffect(() => { fetchHistory(histPage, selectedChain); }, [histPage, selectedChain, fetchHistory]);
  useEffect(() => { fetchErrors(errPage);                  }, [errPage, fetchErrors]);

  // ── derived data ──────────────────────────────────────────────────────────

  const activeChains = SUPPORTED_CHAINS;

  const summary       = status?.last_run_summary || {};
  const activityState = status?.activity_state   || 'idle';

  const activityLabel = {
    running: 'Running',
    success: 'Completed',
    failed:  'Failed',
    idle:    'Idle',
    never:   'Idle',
  }[activityState] ?? capitalize(activityState);

  // ── render ────────────────────────────────────────────────────────────────

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', position: 'relative' }}>

      {/* Header */}
      <div style={{ background: 'linear-gradient(135deg, #0d1b2e 0%, #0f2744 100%)', borderRadius: '16px', padding: '28px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ fontSize: '22px', fontWeight: '700', color: '#fff' }}>⛓ ETL Control Center</div>
          <div style={{ fontSize: '13px', color: '#4b5e72', marginTop: '6px' }}>Blockchain ingestion and pipeline operational status</div>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <ChainFilter
            selectedChain={selectedChain}
            onChainChange={setSelectedChain}
            countKey="etl_run_count"
            label=""
          />
          <button
            onClick={refreshAll}
            style={{ padding: '8px 16px', borderRadius: '10px', fontSize: '12px', fontWeight: '700', background: 'rgba(201,168,76,0.1)', color: '#C9A84C', border: '1px solid rgba(201,168,76,0.25)', cursor: 'pointer' }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(201,168,76,0.18)'}
            onMouseLeave={e => e.currentTarget.style.background = 'rgba(201,168,76,0.1)'}
          >
            ↺ Refresh
          </button>
          {refreshedAt && (
            <span style={{ fontSize: '10px', color: '#475569' }}>Updated {fmtTs(refreshedAt.toISOString())}</span>
          )}
        </div>
      </div>

      {/* Hero Status Panel */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
        <Card>
          <CardLabel>Pipeline State</CardLabel>
          {statusLoading
            ? <EmptyState label="Loading…" />
            : statusErr
              ? <EmptyState label="Unavailable" />
              : <StatusBadge status={activityState === 'success' ? 'success' : activityState} label={activityLabel} />
          }
        </Card>

        <Card>
          <CardLabel>Last Successful Run</CardLabel>
          <div style={{ fontSize: '13px', fontWeight: '600', color: '#4ade80', marginTop: '2px' }}>
            {status?.last_success_at
              ? fmtTs(status.last_success_at)
              : <EmptyState label="Waiting for first successful run" />
            }
          </div>
        </Card>

        <Card>
          <CardLabel>Last Failed Run</CardLabel>
          <div style={{ fontSize: '13px', fontWeight: '600', color: '#f87171', marginTop: '2px' }}>
            {status?.last_failed_at ? fmtTs(status.last_failed_at) : <EmptyState label="No data yet" />}
          </div>
        </Card>

        <Card>
          <CardLabel>Active Chain</CardLabel>
          <div style={{ fontSize: '14px', fontWeight: '700', color: '#E2C97E', marginTop: '2px', textTransform: 'capitalize' }}>
            {status?.active_chain || <EmptyState label="Idle" />}
          </div>
        </Card>

        <Card>
          <CardLabel>Next Scheduled Run</CardLabel>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#94a3b8', marginTop: '2px' }}>
            {status?.next_run_at ? fmtTs(status.next_run_at) : <EmptyState label="Not scheduled" />}
          </div>
          {status?.schedule && <div style={{ fontSize: '10px', color: '#475569', marginTop: '4px' }}>{status.schedule}</div>}
        </Card>

        <Card>
          <CardLabel>Lifetime Runs</CardLabel>
          <div style={{ fontSize: '22px', fontWeight: '800', color: '#E2C97E', lineHeight: 1 }}>
            {status?.total_runs != null
              ? fmtNum(status.total_runs)
              : <EmptyState label="Waiting for first run" />
            }
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            {status?.runs_today != null && status.runs_today > 0
              ? `${status.runs_today} today`
              : status?.total_runs > 0 ? '0 today' : ''}
          </div>
        </Card>
      </div>

      {/* Supported Networks Group */}
      <div>
        <SectionHeading>Supported Networks</SectionHeading>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
          <Card>
            <CardLabel>Account based</CardLabel>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
              {['Ethereum', 'BNB Chain', 'Polygon', 'Arbitrum', 'Base', 'Solana'].map(c => (
                <span key={c} style={{ padding: '4px 10px', background: 'rgba(96,165,250,0.1)', color: '#60A5FA', border: '1px solid rgba(96,165,250,0.2)', borderRadius: '6px', fontSize: '11px', fontWeight: '600' }}>{c}</span>
              ))}
            </div>
          </Card>
          <Card>
            <CardLabel>UTXO Chains</CardLabel>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
              {['Bitcoin', 'Litecoin', 'Dogecoin', 'Bitcoin Cash'].map(c => (
                <span key={c} style={{ padding: '4px 10px', background: 'rgba(251,146,60,0.1)', color: '#FB923C', border: '1px solid rgba(251,146,60,0.2)', borderRadius: '6px', fontSize: '11px', fontWeight: '600' }}>{c}</span>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* Pipeline Stepper */}
      {!statusLoading && !statusErr && (
        <PipelineStepper stages={status?.stages || []} onSelect={setDetailItem} />
      )}
      {statusErr && (
        <Card>
          <div style={{ color: '#f87171', fontSize: '12px' }}>Pipeline status unavailable: {statusErr}</div>
        </Card>
      )}

      {/* Ingestion Metrics */}
      <div>
        <SectionHeading>Ingestion Metrics</SectionHeading>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px' }}>

          <Card>
            <CardLabel>🔍 Extraction Phase</CardLabel>
            <MetricRow label="Blocks extracted"    value={fmtNum(summary.blocks_extracted)} />
            <MetricRow label="Transactions loaded" value={fmtNum(summary.transactions_loaded)} />
            <MetricRow label="Last run at"         value={fmtTs(status?.last_run_at)} />
            <MetricRow label="Active chain"        value={status?.active_chain ? capitalize(status.active_chain) : null} />
          </Card>

          <Card>
            <CardLabel>⚙ Transform &amp; Normalize</CardLabel>
            <MetricRow label="Records normalized"  value={fmtNum(
              summary.records_normalized != null
                ? summary.records_normalized
                : summary.transactions_loaded
            )} />
            <MetricRow
              label="Run status"
              value={
                summary.error
                  ? 'Failed'
                  : activityState === 'success' ? 'Completed'
                  : activityState === 'running' ? 'Running'
                  : activityState === 'failed'  ? 'Failed'
                  : null
              }
            />
            <MetricRow label="Neo4j edges written" value={fmtNum(summary.neo4j_edges)} />
            <MetricRow
              label="Decode errors"
              value={summary.error ? summary.error : activityState === 'success' ? '0' : null}
            />
          </Card>

          <Card>
            <CardLabel>📥 Load &amp; Storage</CardLabel>
            <MetricRow label="Records written to MySQL" value={fmtNum(summary.transactions_loaded)} />
            <MetricRow label="Clusters found"           value={fmtNum(summary.clusters_found)} />
            <MetricRow label="Placement alerts"         value={fmtNum(summary.placements_found)} />
            <MetricRow label="Layering alerts"          value={fmtNum(summary.layering_alerts)} />
          </Card>

        </div>
      </div>

      {/* Historical Run Log */}
      <Card style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '18px 22px 14px', borderBottom: '1px solid rgba(201,168,76,0.10)' }}>
          <SectionHeading>Historical Run Log</SectionHeading>
        </div>
        {histLoading
          ? <div style={{ padding: '24px', color: '#475569', fontSize: '12px' }}>Loading…</div>
          : histErr
            ? <div style={{ padding: '24px', color: '#f87171', fontSize: '12px' }}>Failed to load history: {histErr}</div>
            : <HistoryTable items={history.items} total={history.total} page={histPage} onPage={setHistPage} onSelect={setDetailItem} />
        }
      </Card>

      {/* Exception & Error Console */}
      <Card style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '18px 22px 14px', borderBottom: '1px solid rgba(201,168,76,0.10)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <SectionHeading>Exception &amp; Error Console</SectionHeading>
          {errors.total > 0 && (
            <span style={{ fontSize: '10px', fontWeight: '700', padding: '2px 8px', borderRadius: '999px', background: 'rgba(239,68,68,0.12)', color: '#f87171', border: '1px solid rgba(239,68,68,0.25)' }}>
              {errors.total} record{errors.total !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '140px 70px 90px 1fr 160px', gap: '12px', padding: '8px 16px', background: '#0a1220', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
          {['Timestamp', 'Severity', 'Phase', 'Message', 'Recovery'].map(h => (
            <div key={h} style={{ fontSize: '10px', fontWeight: '800', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{h}</div>
          ))}
        </div>
        {errLoading
          ? <div style={{ padding: '24px', color: '#475569', fontSize: '12px' }}>Loading…</div>
          : errConsErr
            ? <div style={{ padding: '24px', color: '#f87171', fontSize: '12px' }}>Failed to load errors: {errConsErr}</div>
            : <ErrorConsole items={errors.items} total={errors.total} page={errPage} onPage={setErrPage} onSelect={setDetailItem} />
        }
      </Card>

      {/* Detail Drawer */}
      {detailItem && (
        <>
          <div onClick={() => setDetailItem(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 199 }} />
          <DetailDrawer item={detailItem} onClose={() => setDetailItem(null)} />
        </>
      )}
    </div>
  );
}
