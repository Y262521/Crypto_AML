export type ChainId =
  | 'ethereum'
  | 'bsc'
  | 'polygon'
  | 'avalanche'
  | 'fantom'
  | 'arbitrum'
  | 'optimism'
  | 'base'
  | 'celo'
  | 'gnosis'
  | 'cronos'
  | 'moonbeam'
  | 'metis'
  | 'kava'
  | 'bitcoin'
  | 'sepolia'

export type ChainMeta = {
  id: ChainId
  name: string
  symbol: string
  type: 'L1' | 'L2'
}

export const CHAINS: ChainMeta[] = [
  { id: 'ethereum', name: 'Ethereum', symbol: 'ETH', type: 'L1' },
  { id: 'bsc', name: 'BNB Chain', symbol: 'BNB', type: 'L1' },
  { id: 'polygon', name: 'Polygon', symbol: 'MATIC', type: 'L2' },
  { id: 'avalanche', name: 'Avalanche', symbol: 'AVAX', type: 'L1' },
  { id: 'fantom', name: 'Fantom', symbol: 'FTM', type: 'L1' },
  { id: 'arbitrum', name: 'Arbitrum', symbol: 'ETH', type: 'L2' },
  { id: 'optimism', name: 'Optimism', symbol: 'ETH', type: 'L2' },
  { id: 'base', name: 'Base', symbol: 'ETH', type: 'L2' },
  { id: 'celo', name: 'Celo', symbol: 'CELO', type: 'L1' },
  { id: 'gnosis', name: 'Gnosis', symbol: 'xDAI', type: 'L1' },
  { id: 'cronos', name: 'Cronos', symbol: 'CRO', type: 'L1' },
  { id: 'moonbeam', name: 'Moonbeam', symbol: 'GLMR', type: 'L1' },
  { id: 'metis', name: 'Metis', symbol: 'METIS', type: 'L2' },
  { id: 'kava', name: 'Kava', symbol: 'KAVA', type: 'L1' },
  { id: 'bitcoin', name: 'Bitcoin', symbol: 'BTC', type: 'L1' },
  { id: 'sepolia', name: 'Sepolia', symbol: 'ETH', type: 'L1' },
]

export function getChainMeta(id: ChainId): ChainMeta {
  const hit = CHAINS.find((c) => c.id === id)
  return hit ?? CHAINS[0]
}

