import { Loader2, Search } from 'lucide-react'
import { isValidEvmAddress, isValidBitcoinAddress, detectChain } from '../lib/address'
import type { ChainId } from '../lib/chains'
import { CHAINS } from '../lib/chains'
import { useEffect } from 'react'

type Props = {
  value: string
  onChange: (next: string) => void
  onSearch: () => void
  loading?: boolean
  chain: ChainId
  onChangeChain: (next: ChainId) => void
}

export function AddressSearch({
  value,
  onChange,
  onSearch,
  loading,
  chain,
  onChangeChain,
}: Props) {
  useEffect(() => {
    const detected = detectChain(value, chain)
    if (detected !== chain) {
      onChangeChain(detected)
    }
  }, [value, chain, onChangeChain])

  const isValid = isValidEvmAddress(value) || isValidBitcoinAddress(value)
  const chainMeta = CHAINS.find((c) => c.id === chain) ?? CHAINS[0]

  return (
    <div className="glass glass-hover w-full p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="flex-1">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <label className="block text-xs font-medium text-gray-400">Address</label>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <label className="text-xs text-gray-500">Chain</label>
              <select
                value={chain}
                onChange={(e) => onChangeChain(e.target.value as ChainId)}
                className="h-9 rounded-xl border border-white/10 bg-[#0B0B0B] px-3 text-xs text-white outline-none transition hover:border-white/20 focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
              >
                {CHAINS.map((c) => (
                  <option key={c.id} value={c.id} className="bg-[#1A1A1A]">
                    {c.name} ({c.symbol})
                  </option>
                ))}
              </select>
            </div>
          </div>
          <input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && isValid && !loading && onSearch()}
            className="input"
            placeholder="Enter address (0x... or Bitcoin address)"
            spellCheck={false}
            autoCapitalize="none"
            autoCorrect="off"
          />
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="pill">
              Validation:{' '}
              <span className={isValid ? 'text-emerald-300' : 'text-gray-400'}>
                {isValid ? `Valid (${chainMeta.symbol})` : 'Not valid yet'}
              </span>
            </span>
            <span className="pill">
              Tip: paste an address and press <span className="text-gray-200">Search</span>
            </span>
          </div>
        </div>

        <button
          type="button"
          className="btn-primary w-full md:w-auto h-11 px-8"
          onClick={onSearch}
          disabled={loading || !isValid}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>
    </div>
  )
}

