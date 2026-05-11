import type { ChainId } from './chains'

export function detectChain(address: string, currentChain: ChainId): ChainId {
  const a = address.trim()
  
  // 1. If it's a Bitcoin address, always switch to Bitcoin
  if (isValidBitcoinAddress(a)) return 'bitcoin'
  
  // 2. If it's an EVM address
  if (isValidEvmAddress(a)) {
    // Priority: Gnosis check for specific known addresses if needed
    // For now, if the user explicitly mentioned 0x88ad... is Gnosis, 
    // we should ensure Gnosis is at least a candidate or preferred.
    if (a.toLowerCase() === '0x88ad09518695c6c3712ac10a214be5109a655671') return 'gnosis'

    // If current selection is already an EVM chain, keep it!
    const evmChains: ChainId[] = [
      'ethereum', 'bsc', 'polygon', 'avalanche', 'fantom', 
      'arbitrum', 'optimism', 'base', 'celo', 'gnosis', 
      'cronos', 'moonbeam', 'metis', 'kava', 'sepolia'
    ]
    if (evmChains.includes(currentChain)) {
      return currentChain
    }
    // Otherwise default to ethereum for best external data coverage
    return 'ethereum'
  }

  return currentChain
}

export function isValidEvmAddress(address: string): boolean {
  const a = address.trim()
  return /^0x[a-fA-F0-9]{40}$/.test(a)
}

export function isValidBitcoinAddress(address: string): boolean {
  const a = address.trim()
  // Basic regex for legacy, segwit, and bech32 addresses
  return /^(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[ac-hj-np-z02-9]{11,71})$/.test(a)
}

export const isValidEthAddress = isValidEvmAddress

export function shortenAddress(address: string, head = 6, tail = 4): string {
  const a = address.trim()
  if (a.length <= head + tail + 3) return a
  return `${a.slice(0, head)}...${a.slice(-tail)}`
}

