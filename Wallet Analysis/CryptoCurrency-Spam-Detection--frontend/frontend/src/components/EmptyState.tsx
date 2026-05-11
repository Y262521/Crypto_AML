import { Search } from 'lucide-react'

export function EmptyState() {
  return (
    <div className="glass mx-auto w-full max-w-4xl p-8">
      <div className="flex flex-col items-center text-center">
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
          <Search className="h-6 w-6 text-violet-300" />
        </div>
        <div className="mt-4 text-lg font-semibold text-gray-100">Search an address</div>
        <div className="mt-1 max-w-xl text-sm text-gray-400">
          Enter an ETH address (starts with <span className="text-gray-200">0x</span>, 42
          chars) or a BTC address (starts with <span className="text-gray-200">bc1</span>,{' '}
          <span className="text-gray-200">1</span>, or <span className="text-gray-200">3</span>)
          to load summary metrics and transaction history.
        </div>
      </div>
    </div>
  )
}

