import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Play, ShieldCheck, ShieldAlert, ShieldX, Fuel, AlertTriangle } from 'lucide-react'
import { simulateTransaction } from '../lib/endpoints'
import { CHAINS } from '../lib/chains'

type Form = {
  from: string
  to: string
  amount: string
  chain: string
  data?: string
}

type SimResult = {
  success: boolean
  from: string
  to: string
  amount: number
  chain: string
  gasEstimate?: number
  gasCostEth?: number
  riskFlags: string[]
  toRiskScore: number
  fromRiskScore: number
  recommendation: 'safe' | 'caution' | 'block'
  details: string
  simulatedAt: string
}

const REC_CONFIG = {
  safe: { icon: ShieldCheck, color: 'text-emerald-300', bg: 'border-emerald-400/20 bg-emerald-500/5', label: 'Safe to proceed' },
  caution: { icon: ShieldAlert, color: 'text-amber-300', bg: 'border-amber-400/20 bg-amber-500/5', label: 'Proceed with caution' },
  block: { icon: ShieldX, color: 'text-rose-300', bg: 'border-rose-400/20 bg-rose-500/5', label: 'Transaction blocked' },
}

export function SimulatorPage() {
  const { register, handleSubmit } = useForm<Form>({ defaultValues: { chain: 'ethereum', amount: '0' } })
  const [history, setHistory] = useState<SimResult[]>([])

  const mutation = useMutation({
    mutationFn: (payload: { from: string; to: string; amount: number; chain: string; data?: string }) =>
      simulateTransaction(payload),
    onSuccess: (data: SimResult) => {
      if (data.recommendation === 'safe') toast.success('Simulation complete — safe')
      else if (data.recommendation === 'caution') toast('Simulation complete — caution advised', { icon: '⚠️' })
      else toast.error('Simulation complete — transaction blocked')
      setHistory(prev => [data, ...prev].slice(0, 20))
    },
    onError: () => toast.error('Simulation failed'),
  })

  const onSubmit = handleSubmit(f => {
    if (!f.from.trim() || !f.to.trim()) { toast.error('From and To addresses are required'); return }
    mutation.mutate({ from: f.from.trim(), to: f.to.trim(), amount: parseFloat(f.amount) || 0, chain: f.chain, data: f.data?.trim() || undefined })
  })

  const result = mutation.data as SimResult | undefined

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div>
          <div className="page-header">Transaction Simulator</div>
          <div className="page-subheader">Simulate before sending — get risk analysis, gas estimate, and a safety recommendation.</div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="glass p-4">
            <div className="text-sm font-semibold text-gray-100 mb-3">Transaction details</div>
            <form className="grid gap-3" onSubmit={onSubmit}>
              <div>
                <label className="mb-1 block text-xs text-gray-400">From address</label>
                <input className="input" placeholder="0x… (sender)" {...register('from', { required: true })} />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">To address</label>
                <input className="input" placeholder="0x… (recipient)" {...register('to', { required: true })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-gray-400">Amount</label>
                  <input className="input" type="number" step="any" min="0" placeholder="0.0" {...register('amount')} />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-gray-400">Chain</label>
                  <select className="input" {...register('chain')}>
                    {CHAINS.filter(c => c.id !== 'bitcoin').map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">Call data (optional)</label>
                <input className="input" placeholder="0x… (hex encoded)" {...register('data')} />
              </div>
              <button type="submit" className="btn-primary" disabled={mutation.isPending}>
                <Play className="h-4 w-4" />
                {mutation.isPending ? 'Simulating…' : 'Simulate transaction'}
              </button>
            </form>
          </div>

          <div className="glass p-4">
            <div className="text-sm font-semibold text-gray-100 mb-3">Simulation result</div>
            {mutation.isPending ? (
              <div className="flex h-48 items-center justify-center text-sm text-gray-400">Running simulation…</div>
            ) : result ? (
              <div className="flex flex-col gap-3">
                {(() => {
                  const cfg = REC_CONFIG[result.recommendation]
                  const Icon = cfg.icon
                  return (
                    <div className={`rounded-2xl border p-4 ${cfg.bg}`}>
                      <div className={`flex items-center gap-2 font-semibold ${cfg.color}`}><Icon className="h-5 w-5" />{cfg.label}</div>
                      <div className="mt-1 text-sm text-gray-300">{result.details}</div>
                    </div>
                  )
                })()}

                <div className="grid grid-cols-2 gap-3">
                  {[{ label: 'Sender risk', score: result.fromRiskScore }, { label: 'Recipient risk', score: result.toRiskScore }].map(({ label, score }) => (
                    <div key={label} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                      <div className="text-xs text-gray-400">{label}</div>
                      <div className={`mt-1 text-2xl font-bold ${score >= 60 ? 'text-rose-300' : score >= 30 ? 'text-amber-300' : 'text-emerald-300'}`}>{score}</div>
                    </div>
                  ))}
                </div>

                {result.gasEstimate && (
                  <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm">
                    <Fuel className="h-4 w-4 text-amber-300" />
                    <span className="text-gray-300">
                      Gas: <span className="text-gray-100">{result.gasEstimate.toLocaleString()} units</span>
                      {result.gasCostEth !== undefined && <span className="ml-2 text-gray-400">≈ {result.gasCostEth.toFixed(6)} ETH</span>}
                    </span>
                  </div>
                )}

                {result.riskFlags.length > 0 && (
                  <div className="rounded-xl border border-rose-400/20 bg-rose-500/5 p-3">
                    <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-rose-300">
                      <AlertTriangle className="h-3.5 w-3.5" />Risk flags ({result.riskFlags.length})
                    </div>
                    <ul className="space-y-1">
                      {result.riskFlags.map((flag, i) => <li key={i} className="text-xs text-rose-200/80">• {flag}</li>)}
                    </ul>
                  </div>
                )}

                <div className="text-xs text-gray-500">Simulated at {new Date(result.simulatedAt).toLocaleString()}</div>
              </div>
            ) : (
              <div className="flex h-48 items-center justify-center text-sm text-gray-500">Fill in the form and click Simulate.</div>
            )}
          </div>
        </div>

        {history.length > 0 && (
          <div className="glass p-4">
            <div className="text-sm font-semibold text-gray-100">Simulation history</div>
            <div className="mt-3 grid gap-2">
              {history.map((h, i) => {
                const cfg = REC_CONFIG[h.recommendation]
                const Icon = cfg.icon
                return (
                  <div key={i} className="glass glass-hover flex items-center justify-between gap-3 p-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm">
                        <Icon className={`h-4 w-4 shrink-0 ${cfg.color}`} />
                        <span className="truncate font-mono text-xs text-gray-300">{h.from.slice(0, 10)}… → {h.to.slice(0, 10)}…</span>
                        <span className="text-xs text-gray-400">{h.amount} on {h.chain}</span>
                      </div>
                      <div className="mt-0.5 text-xs text-gray-500">{new Date(h.simulatedAt).toLocaleString()}</div>
                    </div>
                    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs ${cfg.bg} ${cfg.color}`}>{h.recommendation}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
