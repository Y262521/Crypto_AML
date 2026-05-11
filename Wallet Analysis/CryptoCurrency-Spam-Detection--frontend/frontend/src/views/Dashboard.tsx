import { useCallback, useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { AddressSearch } from '../components/AddressSearch'
import { DateRangeFilter } from '../components/DateRangeFilter'
import { EmptyState } from '../components/EmptyState'
import { RiskBadge } from '../components/RiskBadge'
import { RiskBreakdownPanel } from '../components/RiskBreakdownPanel'
import { SummaryCards } from '../components/SummaryCards'
import { TransactionTable } from '../components/TransactionTable'
import { VolumeChart } from '../components/VolumeChart'
import { AnalyticsTab } from '../components/AnalyticsTab'
import { DappsPanel } from '../components/DappsPanel'
import { AnomalyPanel } from '../components/AnomalyPanel'
import { MevPanel } from '../components/MevPanel'
import { CrossChainPanel } from '../components/CrossChainPanel'
import { ComplianceBadge } from '../components/ComplianceBadge'
import { ScreeningPanel } from '../components/ScreeningPanel'
import { ClustersPanel } from '../components/ClustersPanel'
import { isValidEvmAddress, isValidBitcoinAddress, detectChain } from '../lib/address'
import type { ChainId } from '../lib/chains'
import { getChainMeta } from '../lib/chains'
import { fetchAddressRisk, fetchAddressSummary, fetchAddressTransactions } from '../lib/endpoints'
import type { AddressSummary, RiskFactor, RiskResponse, TransactionsResponse } from '../types/api'
import { useNavigate, useParams } from 'react-router-dom'

const DEFAULT_LIMIT = 1000

function toYyyyMmDd(d: Date | null): string | undefined {
  if (!d) return undefined
  const x = new Date(d)
  if (Number.isNaN(x.getTime())) return undefined
  return x.toISOString().slice(0, 10)
}

export function Dashboard() {
  const navigate = useNavigate()
  const params = useParams()
  const [addressInput, setAddressInput] = useState('')
  const [activeAddress, setActiveAddress] = useState<string | null>(null)
  const [chain, setChain] = useState<ChainId>('ethereum')

  const [summary, setSummary] = useState<AddressSummary | undefined>(undefined)
  const [tx, setTx] = useState<TransactionsResponse | undefined>(undefined)
  const [risk, setRisk] = useState<RiskResponse | undefined>(undefined)

  const [loadingSummary, setLoadingSummary] = useState(false)
  const [loadingTx, setLoadingTx] = useState(false)
  const [loadingRisk, setLoadingRisk] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [txFilter, setTxFilter] = useState<string | undefined>(undefined)
  const [tab, setTab] = useState<'overview' | 'analytics' | 'dapps' | 'anomalies' | 'crosschain' | 'mev' | 'clusters'>('overview')

  const [page, setPage] = useState(1)
  const [limit] = useState(DEFAULT_LIMIT)
  const [startDate, setStartDate] = useState<Date | null>(null)
  const [endDate, setEndDate] = useState<Date | null>(null)

  const chainMeta = useMemo(() => getChainMeta(chain), [chain])
  const unit = summary?.unit ?? chainMeta.symbol

  useEffect(() => {
    const addr = typeof params.address === 'string' ? params.address : null
    const ch = typeof params.chain === 'string' ? (params.chain as ChainId) : null
    if (addr && ch) {
      setChain(ch)
      setAddressInput(addr)
      loadAll(addr, { page: 1, chain: ch }).catch(() => {
        // handled in loadAll
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.address, params.chain])

  const loadAll = useCallback(
    async (
      addr: string,
      opts?: { page?: number; start?: Date | null; end?: Date | null; chain?: ChainId },
    ) => {
      setError(null)
      setActiveAddress(addr)
      setTxFilter(undefined)
      setTab('overview')

      const p = opts?.page ?? 1
      const start = opts?.start ?? startDate
      const end = opts?.end ?? endDate

      setLoadingSummary(true)
      setLoadingTx(true)
      setLoadingRisk(true)
      try {
        const resolvedChain = opts?.chain ?? chain
        setChain(resolvedChain)
        const [sRes, tRes, rRes] = await Promise.allSettled([
          fetchAddressSummary(addr, resolvedChain),
          fetchAddressTransactions(addr, {
            page: p,
            limit,
            chain: resolvedChain,
            startDate: toYyyyMmDd(start),
            endDate: toYyyyMmDd(end),
          }),
          fetchAddressRisk(addr, resolvedChain),
        ])

        const errors: string[] = []
        let loadedAny = false

        if (sRes.status === 'fulfilled') {
          setSummary(sRes.value)
          loadedAny = true
        } else {
          errors.push(`summary: ${sRes.reason instanceof Error ? sRes.reason.message : 'request failed'}`)
        }

        if (tRes.status === 'fulfilled') {
          setTx(tRes.value)
          setPage(tRes.value.page)
          loadedAny = true
        } else {
          errors.push(`transactions: ${tRes.reason instanceof Error ? tRes.reason.message : 'request failed'}`)
        }

        if (rRes.status === 'fulfilled') {
          setRisk(rRes.value)
          loadedAny = true
        } else {
          errors.push(`risk: ${rRes.reason instanceof Error ? rRes.reason.message : 'request failed'}`)
        }

        navigate(`/address/${resolvedChain}/${addr}`, { replace: true })

        if (!loadedAny) {
          setError(errors.join(' | ') || 'Request failed')
          toast.error('Failed to load data')
        } else if (errors.length > 0) {
          setError(`Partial data loaded (${errors.join(' | ')})`)
          toast('Partial data loaded')
        } else {
          toast.success('Loaded address data')
        }
      } finally {
        setLoadingSummary(false)
        setLoadingTx(false)
        setLoadingRisk(false)
      }
    },
    [chain, endDate, limit, startDate],
  )

  const onSearch = useCallback(async () => {
    const addr = addressInput.trim()
    const targetChain = detectChain(addr, chain)
    
    if (!isValidEvmAddress(addr) && !isValidBitcoinAddress(addr)) {
      toast.error('Invalid address format.')
      return
    }

    setChain(targetChain) // Update the dropdown state
    toast(`Fetching address on ${getChainMeta(targetChain).name}…`)
    await loadAll(addr, { page: 1, chain: targetChain })
  }, [addressInput, chain, loadAll])

  const onRecalculateRisk = useCallback(async () => {
    if (!activeAddress) return
    setLoadingRisk(true)
    try {
      const r = await fetchAddressRisk(activeAddress, chain)
      setRisk(r)
      toast.success('Risk updated')
    } catch {
      toast.error('Failed to recalculate risk')
    } finally {
      setLoadingRisk(false)
    }
  }, [activeAddress, chain])

  const onSelectRiskFactor = useCallback((factor: RiskFactor) => {
    const q = factor.transactionQuery ?? factor.title
    setTxFilter(q)
    toast.success('Filtered transactions')
  }, [])

  const onApplyDates = useCallback(async () => {
    if (!activeAddress) return
    toast.success('Applying date filter')
    await loadAll(activeAddress, { page: 1, start: startDate, end: endDate, chain })
  }, [activeAddress, chain, endDate, loadAll, startDate])

  const onClearDates = useCallback(async () => {
    setStartDate(null)
    setEndDate(null)
    if (!activeAddress) return
    toast('Cleared date filters')
    await loadAll(activeAddress, { page: 1, start: null, end: null, chain })
  }, [activeAddress, chain, loadAll])

  const onPrev = useCallback(async () => {
    if (!activeAddress) return
    const nextPage = Math.max(1, page - 1)
    setLoadingTx(true)
    try {
      const t = await fetchAddressTransactions(activeAddress, {
        page: nextPage,
        limit,
        chain,
        startDate: toYyyyMmDd(startDate),
        endDate: toYyyyMmDd(endDate),
      })
      setTx(t)
      setPage(t.page)
    } catch (e: unknown) {
      toast.error('Failed to load previous page')
    } finally {
      setLoadingTx(false)
    }
  }, [activeAddress, chain, endDate, limit, page, startDate])

  const onNext = useCallback(async () => {
    if (!activeAddress) return
    const nextPage = page + 1
    setLoadingTx(true)
    try {
      const t = await fetchAddressTransactions(activeAddress, {
        page: nextPage,
        limit,
        chain,
        startDate: toYyyyMmDd(startDate),
        endDate: toYyyyMmDd(endDate),
      })
      setTx(t)
      setPage(t.page)
    } catch (e: unknown) {
      toast.error('Failed to load next page')
    } finally {
      setLoadingTx(false)
    }
  }, [activeAddress, chain, endDate, limit, page, startDate])

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <div className="page-header">Wallet Analysis</div>
          <div className="page-subheader">Search and analyze blockchain wallet addresses</div>
        </div>

        <AddressSearch
          value={addressInput}
          onChange={setAddressInput}
          onSearch={onSearch}
          loading={loadingSummary || loadingTx}
          chain={chain}
          onChangeChain={setChain}
        />

        {!activeAddress ? (
          <EmptyState />
        ) : (
          <>
            <div className="glass glass-hover flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
              <div className="min-w-0">
                <div className="text-xs text-gray-500">Address</div>
                <div className="mt-1 truncate font-mono text-sm text-gray-100">{activeAddress}</div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="pill">
                    Chain: <span className="text-gray-200">{chainMeta.name}</span>
                  </span>
                  {summary?.entityLabel && (
                    <span className={[
                      'pill font-bold uppercase',
                      summary.entityLabel === 'exchange' ? 'bg-sky-500/20 text-sky-300' :
                      summary.entityLabel === 'smart contract' ? 'bg-violet-500/20 text-violet-300' :
                      summary.entityLabel === 'bot' ? 'bg-amber-500/20 text-amber-300' :
                      summary.entityLabel === 'mixer' ? 'bg-rose-500/20 text-rose-300' :
                      summary.entityLabel === 'ransomware' ? 'bg-red-600/20 text-red-400' :
                      'bg-emerald-500/20 text-emerald-300'
                    ].join(' ')}>
                      {summary.entityLabel}
                    </span>
                  )}
                  {risk ? <RiskBadge score={risk.score} factors={risk.factors} /> : null}
                  <ComplianceBadge address={activeAddress} chain={chain} />
                </div>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row sm:w-auto w-full">
                <button
                  type="button"
                  className="btn-ghost flex-1 sm:flex-none"
                  onClick={() => navigate('/watchlist')}
                >
                  Add to Watchlist
                </button>
                <button
                  type="button"
                  className="btn-ghost flex-1 sm:flex-none"
                  onClick={() => navigate(`/graph/${chain}/${activeAddress}`)}
                >
                  Open Graph
                </button>
                <button
                  type="button"
                  className="btn-primary flex-1 sm:flex-none"
                  onClick={() => navigate(`/reports/${chain}/${activeAddress}`)}
                >
                  Generate PDF Report
                </button>
              </div>
            </div>

            {error ? (
              <div className="glass border border-rose-400/20 bg-rose-500/5 p-4">
                <div className="text-sm font-semibold text-rose-200">Couldn’t load data</div>
                <div className="mt-1 text-sm text-rose-200/70">{error}</div>
                <div className="mt-4">
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => loadAll(activeAddress, { page: 1 })}
                  >
                    Retry
                  </button>
                </div>
              </div>
            ) : null}

            <SummaryCards data={summary} loading={loadingSummary} />

            <RiskBreakdownPanel
              factors={risk?.factors ?? []}
              onSelectFactor={onSelectRiskFactor}
              onRecalculate={onRecalculateRisk}
              loading={loadingRisk}
            />

            <ScreeningPanel address={activeAddress} chain={chain} />

            <div className="glass glass-hover p-1 sm:p-2 overflow-x-auto scrollbar-hide">
              <div className="flex flex-nowrap sm:flex-wrap gap-1 sm:gap-2 min-w-max sm:min-w-0">
                {[
                  { id: 'overview', label: 'Overview' },
                  { id: 'analytics', label: 'Analytics' },
                  { id: 'dapps', label: 'DApps' },
                  { id: 'anomalies', label: 'Anomalies' },
                  { id: 'crosschain', label: 'Cross-chain' },
                  { id: 'mev', label: 'MEV' },
                  { id: 'clusters', label: 'Clusters' },
                ].map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className={[
                      'rounded-xl border px-4 py-2 text-sm transition',
                      tab === (t.id as any)
                        ? 'border-white/15 bg-white/[0.06] text-white'
                        : 'border-white/10 bg-white/[0.03] text-gray-300 hover:bg-white/[0.06] hover:text-white',
                    ].join(' ')}
                    onClick={() => setTab(t.id as any)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {tab === 'overview' ? (
              <>
                <div className="grid gap-4 lg:grid-cols-3">
                  <div className="lg:col-span-2">
                    <DateRangeFilter
                      startDate={startDate}
                      endDate={endDate}
                      onChangeStart={setStartDate}
                      onChangeEnd={setEndDate}
                      onApply={onApplyDates}
                      onClear={onClearDates}
                      disabled={loadingTx || loadingSummary}
                    />
                  </div>
                  <div className="lg:col-span-1">
                    <VolumeChart items={tx?.items ?? []} unit={unit} loading={loadingTx} />
                  </div>
                </div>

                <TransactionTable
              chain={chain}
              unit={unit}
              items={tx?.items ?? []}
              loading={loadingTx}
              filterQuery={txFilter}
              onClearFilterQuery={() => setTxFilter(undefined)}
              page={tx?.page ?? page}
              limit={tx?.limit ?? limit}
              total={tx?.total ?? 0}
              startDate={startDate}
              endDate={endDate}
              onPrev={onPrev}
              onNext={onNext}
              onClearDates={onClearDates}
            />
              </>
            ) : tab === 'analytics' ? (
              <AnalyticsTab address={activeAddress} chain={chain} />
            ) : tab === 'dapps' ? (
              <DappsPanel address={activeAddress} chain={chain} onFilterTransactions={setTxFilter} />
            ) : tab === 'anomalies' ? (
              <AnomalyPanel address={activeAddress} chain={chain} />
            ) : tab === 'crosschain' ? (
              <CrossChainPanel address={activeAddress} />
            ) : tab === 'clusters' ? (
              <ClustersPanel address={activeAddress} chain={chain} />
            ) : (
              <MevPanel address={activeAddress} chain={chain} />
            )}
          </>
        )}
      </div>
    </div>
  )
}

