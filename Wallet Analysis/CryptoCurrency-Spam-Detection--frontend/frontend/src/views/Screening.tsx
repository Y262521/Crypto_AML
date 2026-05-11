import { useCallback, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AddressSearch } from '../components/AddressSearch'
import type { ChainId } from '../lib/chains'
import { isValidEvmAddress } from '../lib/address'
import { ScreeningPanel } from '../components/ScreeningPanel'
import { ClustersPanel } from '../components/ClustersPanel'
import toast from 'react-hot-toast'

export function ScreeningPage() {
  const navigate = useNavigate()
  const params = useParams()
  const [chain, setChain] = useState<ChainId>((params.chain as ChainId) || 'ethereum')
  const [addressInput, setAddressInput] = useState(params.address || '')
  const [activeAddress, setActiveAddress] = useState(params.address || '')
  const [loading, setLoading] = useState(false)

  const onSearch = useCallback(async () => {
    const addr = addressInput.trim()
    if (!isValidEvmAddress(addr)) {
      toast.error('Invalid EVM address')
      return
    }
    setLoading(true)
    setActiveAddress(addr)
    navigate(`/screening/${chain}/${addr}`)
    setLoading(false)
  }, [addressInput, chain, navigate])

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div>
          <div className="page-header">Wallet Screening</div>
          <div className="page-subheader">Screen addresses against flagged databases</div>
        </div>
        <AddressSearch
          value={addressInput}
          onChange={setAddressInput}
          onSearch={onSearch}
          loading={loading}
          chain={chain}
          onChangeChain={setChain}
        />

        {activeAddress ? (
          <>
            <ScreeningPanel address={activeAddress} chain={chain} />
            <ClustersPanel address={activeAddress} chain={chain} />
          </>
        ) : (
          <div className="glass p-6 text-sm text-gray-400">Enter a wallet address to start screening.</div>
        )}
      </div>
    </div>
  )
}
