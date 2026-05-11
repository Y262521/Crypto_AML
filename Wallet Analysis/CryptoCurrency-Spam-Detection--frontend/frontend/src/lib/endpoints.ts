import type {
  AddressSummary,
  RiskResponse,
  TransactionsResponse,
  WatchlistItem,
  AlertItem,
  AlertSettings,
  GraphResponse,
  TimeseriesResponse,
  DappsResponse,
  ApprovalsResponse,
  BatchAnalyzeResponse,
  Team,
  TeamActivityItem,
  TxComment,
  ScreeningResponse,
  ClustersResponse,
} from '../types/api'
import { api } from './api'
import type { ChainId } from './chains'

export async function fetchAddressSummary(
  address: string,
  chain: ChainId,
): Promise<AddressSummary> {
  const res = await api.get<AddressSummary>(`/api/v1/address/${address}/summary`, {
    params: { chain },
  })
  return normalizeSummary(res.data, chain)
}

export type FetchTransactionsParams = {
  page: number
  limit: number
  startDate?: string
  endDate?: string
}

export async function fetchAddressTransactions(
  address: string,
  params: FetchTransactionsParams & { chain: ChainId },
): Promise<TransactionsResponse> {
  const res = await api.get<TransactionsResponse>(
    `/api/v1/address/${address}/transactions`,
    { params },
  )
  return normalizeTransactions(res.data, params.page, params.limit)
}

export async function fetchAddressRisk(address: string, chain: ChainId): Promise<RiskResponse> {
  const res = await api.get<RiskResponse>(`/api/v1/address/${address}/risk`, { params: { chain } })
  return {
    score: Number(res.data?.score ?? 0),
    factors: Array.isArray(res.data?.factors) ? res.data.factors : [],
  }
}

export async function fetchWatchlist(): Promise<WatchlistItem[]> {
  const res = await api.get<WatchlistItem[]>(`/api/v1/watchlist`)
  return Array.isArray(res.data) ? res.data : []
}

export async function addToWatchlist(payload: {
  address: string
  chain: ChainId
  name?: string
  category?: string
  source?: string
  confidence?: number
  reviewerNotes?: string
}): Promise<WatchlistItem> {
  const res = await api.post<WatchlistItem>(`/api/v1/watchlist`, payload)
  return res.data
}

export async function removeWatchlistItem(id: string): Promise<void> {
  await api.delete(`/api/v1/watchlist/${id}`)
}

export async function updateWatchlistItem(
  id: string,
  payload: Partial<{
    name: string
    alerts_enabled: boolean
    category: string
    source: string
    confidence: number
    reviewerNotes: string
  }>,
): Promise<WatchlistItem> {
  const res = await api.patch<WatchlistItem>(`/api/v1/watchlist/${id}`, payload)
  return res.data
}

export async function fetchAlerts(): Promise<AlertItem[]> {
  const res = await api.get<AlertItem[]>(`/api/v1/alerts`)
  return Array.isArray(res.data) ? res.data : []
}

export async function fetchAlertSettings(): Promise<AlertSettings> {
  const res = await api.get<AlertSettings>(`/api/v1/alerts/settings`)
  return res.data ?? {}
}

export async function saveAlertSettings(payload: AlertSettings & { test?: 'telegram' | 'discord' | 'email' }): Promise<AlertSettings> {
  const res = await api.post<AlertSettings>(`/api/v1/alerts/settings`, payload)
  return res.data ?? {}
}

export async function fetchAddressGraph(params: {
  address: string
  chain: ChainId
  depth: number
  minAmount: number
  startDate?: string
  endDate?: string
}): Promise<GraphResponse> {
  const res = await api.get<GraphResponse>(`/api/v1/address/${params.address}/graph`, {
    params: {
      chain: params.chain,
      depth: params.depth,
      minAmount: params.minAmount,
      startDate: params.startDate,
      endDate: params.endDate,
    },
  })
  return res.data
}

export async function fetchAddressTimeseries(params: {
  address: string
  chain: ChainId
  range: string
  startDate?: string
  endDate?: string
}): Promise<TimeseriesResponse> {
  const res = await api.get<TimeseriesResponse>(`/api/v1/address/${params.address}/timeseries`, {
    params: { chain: params.chain, range: params.range, startDate: params.startDate, endDate: params.endDate },
  })
  return res.data
}

export async function fetchAddressDapps(address: string, chain: ChainId): Promise<DappsResponse> {
  const res = await api.get<DappsResponse>(`/api/v1/address/${address}/dapps`, { params: { chain } })
  return res.data
}

export async function fetchAddressApprovals(address: string, chain: ChainId): Promise<ApprovalsResponse> {
  const res = await api.get<ApprovalsResponse>(`/api/v1/address/${address}/approvals`, { params: { chain } })
  return res.data
}

export async function batchAnalyzeCsv(file: File): Promise<BatchAnalyzeResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await api.post<BatchAnalyzeResponse>(`/api/v1/batch/analyze`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function fetchTeams(): Promise<Team[]> {
  const res = await api.get<Team[]>(`/api/v1/teams`)
  return Array.isArray(res.data) ? res.data : []
}

export async function inviteToTeam(teamId: string, email: string): Promise<void> {
  await api.post(`/api/v1/teams/${teamId}/invite`, { email })
}

export async function fetchTeamActivity(teamId: string): Promise<TeamActivityItem[]> {
  const res = await api.get<TeamActivityItem[]>(`/api/v1/teams/${teamId}/activity`)
  return Array.isArray(res.data) ? res.data : []
}

export async function postTransactionComment(hash: string, payload: { message: string; mentions?: string[]; flagged?: boolean }): Promise<TxComment> {
  const res = await api.post<TxComment>(`/api/v1/transactions/${hash}/comment`, payload)
  return res.data
}

export async function fetchAddressAnomalies(address: string, chain: ChainId) {
  const res = await api.get(`/api/v1/address/${address}/anomalies`, { params: { chain } })
  return res.data
}

export async function fetchAddressCrossChain(address: string) {
  const res = await api.get(`/api/v1/address/${address}/cross-chain`)
  return res.data
}

export async function fetchAddressMev(address: string, chain: ChainId) {
  const res = await api.get(`/api/v1/address/${address}/mev`, { params: { chain } })
  return res.data
}

export async function fetchAddressSanctions(address: string, chain: ChainId) {
  const res = await api.get(`/api/v1/address/${address}/sanctions`, { params: { chain } })
  return res.data
}

export async function fetchAddressScreening(address: string, chain: ChainId): Promise<ScreeningResponse> {
  const res = await api.get<ScreeningResponse>(`/api/v1/address/${address}/screening`, { params: { chain } })
  return res.data
}

export async function fetchAddressClusters(address: string, chain: ChainId): Promise<ClustersResponse> {
  const res = await api.get<ClustersResponse>(`/api/v1/address/${address}/clusters`, { params: { chain } })
  return res.data
}

export async function fetchIndexerStatus() {
  const res = await api.get(`/api/v1/indexer/status`)
  return res.data
}

export async function triggerReindex(payload: { address: string; blockRange?: string }) {
  const res = await api.post(`/api/v1/indexer/reindex`, payload)
  return res.data
}

export async function fetchOrganizationKeys(userId?: string) {
  const res = await api.get(`/api/v1/organization/keys`, { params: userId ? { userId } : {} })
  return res.data
}

export async function createOrganizationKey(payload: {
  name: string
  permissions?: 'read' | 'write' | 'admin'
  tier?: 'free' | 'pro' | 'enterprise'
  expiresAt?: string
}) {
  const res = await api.post(`/api/v1/organization/keys`, payload)
  return res.data
}

export async function deleteOrganizationKey(id: string) {
  const res = await api.delete(`/api/v1/organization/keys/${id}`)
  return res.data
}

export async function revokeOrganizationKey(id: string) {
  const res = await api.post(`/api/v1/organization/keys/${id}/revoke`)
  return res.data
}

export async function fetchTeamPresence(teamId: string) {
  const res = await api.get(`/api/v1/teams/${teamId}/presence`)
  return res.data
}

export async function postCustomReport(payload: unknown) {
  const res = await api.post(`/api/v1/reports/custom`, payload)
  return res.data
}

export async function simulateTransaction(payload: {
  from: string
  to: string
  amount: number
  chain?: string
  data?: string
}) {
  const res = await api.post(`/api/v1/simulate/transaction`, payload)
  return res.data
}

export async function globalSearch(params: { q: string; chain?: string }) {
  const res = await api.get(`/api/v1/search`, { params })
  return res.data
}

function normalizeSummary(input: AddressSummary, unit: string): AddressSummary {
  return {
    totalReceived: input?.totalReceived ?? 0,
    totalSent: input?.totalSent ?? 0,
    balance: input?.balance ?? 0,
    transactionCount: Number(input?.transactionCount ?? 0),
    unit: input?.unit ?? unit,
  }
}

function normalizeTransactions(
  input: TransactionsResponse,
  page: number,
  limit: number,
): TransactionsResponse {
  return {
    items: Array.isArray(input?.items) ? input.items : [],
    page: Number(input?.page ?? page),
    limit: Number(input?.limit ?? limit),
    total: Number(input?.total ?? 0),
  }
}

