export type AddressSummary = {
  totalReceived: number | string
  totalSent: number | string
  balance: number | string
  transactionCount: number
  unit: string
  entityLabel?: string
}

export type TransactionItem = {
  hash: string
  from: string
  to: string
  amount: number | string
  date: string
  type?: string
}

export type TransactionsResponse = {
  items: TransactionItem[]
  page: number
  limit: number
  total: number
}

export type RiskFactor = {
  id?: string
  title: string
  severity: 'Low' | 'Medium' | 'High'
  description?: string
  transactionQuery?: string
}

export type RiskResponse = {
  score: number
  level?: 'LOW' | 'MEDIUM' | 'HIGH' | string
  classification?: 'safe' | 'suspicious' | 'high risk' | string
  recommendation?: string
  factors: RiskFactor[]
}

export type WatchlistItem = {
  id: string
  address: string
  chain: string
  name?: string
  category?: string
  source?: string
  confidence?: number
  reviewerNotes?: string
  riskScore?: number
  lastActivity?: string
  alerts_enabled: boolean
}

export type AlertItem = {
  id: string
  type: 'risk_increase' | 'flagged_interaction' | 'large_transaction'
  title: string
  message?: string
  address: string
  chain: string
  createdAt: string
  read: boolean
}

export type AlertSettings = {
  telegram?: { botToken?: string; chatId?: string }
  discord?: { webhookUrl?: string }
  email?: { address?: string }
  rules?: {
    minimumAmount?: number
    minimumRiskScore?: number
    flaggedInteractionEnabled?: boolean
  }
}

export type GraphNode = {
  id: string
  address: string
  riskScore?: number
  flagged?: boolean
  entityLabel?: string
}

export type GraphEdge = {
  id: string
  source: string
  target: string
  amount?: number | string
}

export type GraphResponse = {
  center: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export type TimeseriesPoint = {
  ts: string
  balance?: number
  inflow?: number
  outflow?: number
  txCount?: number
}

export type TimeseriesResponse = {
  range: string
  points: TimeseriesPoint[]
  topCounterparties?: Array<{ address: string; volume: number }>
}

export type DappProtocol = {
  id: string
  name: 'Uniswap' | 'Aave' | 'Curve' | 'Compound' | 'OpenSea' | string
  txCount: number
  totalVolume: number
  firstInteraction?: string
  lastInteraction?: string
  risk: 'Low' | 'Medium' | 'High'
}

export type DappsResponse = {
  protocols: DappProtocol[]
  flaggedInteractions?: Array<{ protocol: string; counterparty: string; reason: string }>
}

export type ApprovalItem = {
  token: string
  spender: string
  allowance: string
  approvalDate: string
  revokeRisk: 'Low' | 'Medium' | 'High'
  unlimited?: boolean
}

export type ApprovalsResponse = {
  items: ApprovalItem[]
}

export type BatchAnalyzeResult = {
  address: string
  name?: string
  chain?: string
  riskScore?: number
  transactionCount?: number
  status: 'queued' | 'processing' | 'done' | 'failed' | string
  error?: string
}

export type BatchAnalyzeResponse = {
  results: BatchAnalyzeResult[]
}

export type Team = {
  id: string
  name: string
  description?: string
  role: 'Viewer' | 'Analyst' | 'Admin'
}

export type TeamActivityItem = {
  id: string
  createdAt: string
  actor: string
  action: string
  meta?: Record<string, unknown>
}

export type TxComment = {
  id: string
  hash: string
  message: string
  createdAt: string
  author: string
  mentions?: string[]
  flagged?: boolean
}

export type ScreeningResponse = {
  matched: boolean
  reasons: string[]
  source: string
  categories: {
    scam: string[]
    phishing: string[]
    mixer: string[]
    ransomware: string[]
    stolenFunds: string[]
    darknet: string[]
  }
  entityLabel: 'exchange' | 'smart contract' | 'smart_contract' | 'bot' | 'mixer' | 'user_wallet' | string
  confidence: number
  stats: {
    txCount24h: number
    uniqueCounterparties: number
    repeatedInteractions: number
  }
}

export type ClusterWallet = {
  wallet: string
  interactions: number
  direction: string
  volume: number
  clusterScore: number
}

export type ClustersResponse = {
  root: string
  chain: string
  clusterSignals: {
    repeatedFlows: number
    fanOut: number
    bidirectionalLinks: number
  }
  relatedWallets: ClusterWallet[]
  inferredClusters: Array<{
    id: string
    type: string
    size: number
    risk: 'Low' | 'Medium' | 'High' | string
  }>
}

