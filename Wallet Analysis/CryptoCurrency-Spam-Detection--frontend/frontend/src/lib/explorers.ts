import type { ChainId } from './chains'

export function explorerTxUrl(_chain: ChainId, txHash: string): string {
  // API-ready: backend can return chain-specific explorer URLs later.
  // Default to Etherscan (works for Ethereum mainnet).
  return `https://etherscan.io/tx/${txHash}`
}

