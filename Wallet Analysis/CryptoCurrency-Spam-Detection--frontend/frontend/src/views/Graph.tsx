import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import cytoscape from 'cytoscape'
import toast from 'react-hot-toast'
import { Download, Filter, RefreshCcw } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import type { ChainId } from '../lib/chains'
import { CHAINS, getChainMeta } from '../lib/chains'
import { fetchAddressGraph } from '../lib/endpoints'
import DatePicker from 'react-datepicker'

type Cy = cytoscape.Core

function riskColor(score?: number, flagged?: boolean) {
  if (flagged) return '#a855f7'
  const s = typeof score === 'number' ? score : 0
  if (s <= 29) return '#34d399'
  if (s <= 69) return '#fbbf24'
  return '#fb7185'
}

export function GraphPage() {
  const params = useParams()
  const navigate = useNavigate()
  const cyRef = useRef<Cy | null>(null)

  const address = (params.address as string | undefined) ?? ''
  const [chain, setChain] = useState<ChainId>('ethereum')

  const [minAmount, setMinAmount] = useState(0)
  const [depth, setDepth] = useState(2)
  const [startDate, setStartDate] = useState<Date | null>(null)
  const [endDate, setEndDate] = useState<Date | null>(null)
  const [loading, setLoading] = useState(false)

  const [graph, setGraph] = useState<{ nodes: any[]; edges: any[] } | null>(null)

  const chainMeta = useMemo(() => getChainMeta(chain), [chain])

  const load = useCallback(async () => {
    if (!address) return
    setLoading(true)
    try {
      const res = await fetchAddressGraph({
        address,
        chain,
        depth,
        minAmount,
        startDate: startDate ? startDate.toISOString() : undefined,
        endDate: endDate ? endDate.toISOString() : undefined,
      })

      const nodes = (res.nodes ?? []).map((n) => ({
        data: {
          id: n.id,
          label: n.address,
          riskScore: n.riskScore ?? 0,
          flagged: Boolean(n.flagged),
          entityLabel: n.entityLabel
        },
        style: {
          backgroundColor: riskColor(n.riskScore, n.flagged),
          shape: n.entityLabel === 'smart contract' ? 'hexagon' :
            n.entityLabel === 'exchange' ? 'rectangle' :
              n.entityLabel === 'bot' ? 'diamond' :
                'ellipse'
        },
      }))
      const edges = (res.edges ?? []).map((e) => ({
        data: { id: e.id, source: e.source, target: e.target, label: e.amount != null ? String(e.amount) : '' },
      }))

      setGraph({ nodes, edges })
      toast.success('Graph loaded')
    } catch {
      toast.error('Failed to load graph')
    } finally {
      setLoading(false)
    }
  }, [address, chain, depth, endDate, minAmount, startDate])

  useEffect(() => {
    load()
  }, [load])

  const elements = useMemo(() => {
    if (!graph) return []
    return [...graph.nodes, ...graph.edges]
  }, [graph])

  const exportPng = () => {
    const cy = cyRef.current
    if (!cy) return
    const png = cy.png({ full: true, scale: 2, bg: '#0f0f0f' })
    const a = document.createElement('a')
    a.href = png
    a.download = `graph-${chain}-${address}.png`
    a.click()
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-2xl font-semibold text-gray-100">Graph (Link Analysis)</div>
            <div className="mt-1 text-sm text-gray-400">
              Center: <span className="font-mono text-gray-200">{address}</span> • {chainMeta.name}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-ghost" onClick={load} disabled={loading}>
              <RefreshCcw className={['h-4 w-4', loading ? 'animate-spin' : ''].join(' ')} />
              Reload
            </button>
            <button type="button" className="btn-primary" onClick={exportPng} disabled={!graph}>
              <Download className="h-4 w-4" />
              Export PNG
            </button>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-12">
          <div className="glass lg:col-span-3">
            <div className="flex items-center justify-between border-b border-white/10 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-100">
                <Filter className="h-4 w-4 text-violet-300" />
                Filters
              </div>
            </div>
            <div className="grid gap-4 p-4 text-sm">
              <div className="grid gap-2">
                <label className="text-xs font-medium text-gray-400">Chain</label>
                <select
                  value={chain}
                  onChange={(e) => setChain(e.target.value as ChainId)}
                  className="h-10 rounded-xl border border-white/10 bg-[#0B0B0B] px-3 text-sm text-white outline-none transition focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
                >
                  {CHAINS.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.symbol})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid gap-2">
                <label className="text-xs font-medium text-gray-400">Min amount</label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={minAmount}
                  onChange={(e) => setMinAmount(Number(e.target.value))}
                />
                <div className="text-xs text-gray-400">{minAmount.toFixed(2)}</div>
              </div>

              <div className="grid gap-2">
                <label className="text-xs font-medium text-gray-400">Max hops</label>
                <select
                  value={depth}
                  onChange={(e) => setDepth(Number(e.target.value))}
                  className="h-10 rounded-xl border border-white/10 bg-[#0B0B0B] px-3 text-sm text-white outline-none transition focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
                >
                  {[1, 2, 3].map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid gap-2">
                <label className="text-xs font-medium text-gray-400">Start</label>
                <DatePicker selected={startDate} onChange={setStartDate} className="input" />
              </div>
              <div className="grid gap-2">
                <label className="text-xs font-medium text-gray-400">End</label>
                <DatePicker selected={endDate} onChange={setEndDate} className="input" />
              </div>

              <button type="button" className="btn-primary w-full" onClick={load} disabled={loading}>
                Apply
              </button>

              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs text-gray-400">
                Node colors: green/yellow/red by risk score, purple = flagged.
              </div>
            </div>
          </div>

          <div className="glass lg:col-span-9">
            <div className="h-[70vh] w-full">
              {elements.length === 0 ? (
                <div className="flex h-full items-center justify-center text-sm text-gray-400">
                  No graph data yet.
                </div>
              ) : (
                <CytoscapeComponent
                  key={elements.length}
                  cy={(cy: Cy) => {
                    cyRef.current = cy
                    cy.on('tap', 'node', (evt: cytoscape.EventObject) => {
                      const id = evt.target.id()
                      if (!id) return
                      navigate(`/graph/${chain}/${id}`)
                    })
                  }}
                  elements={elements}
                  style={{ width: '100%', height: '100%' }}
                  layout={{ name: 'cose', animate: false, fit: true, padding: 30 }}
                  stylesheet={[
                    {
                      selector: 'node',
                      style: {
                        label: 'data(label)',
                        color: '#E5E7EB',
                        'font-size': 10,
                        'text-valign': 'center',
                        'text-wrap': 'wrap',
                        'text-max-width': 80,
                        'border-width': 1,
                        'border-color': 'rgba(255,255,255,0.15)',
                      },
                    },
                    {
                      selector: 'edge',
                      style: {
                        width: 1.5,
                        'line-color': 'rgba(255,255,255,0.18)',
                        'target-arrow-shape': 'triangle',
                        'target-arrow-color': 'rgba(255,255,255,0.18)',
                        label: 'data(label)',
                        color: 'rgba(229,231,235,0.6)',
                        'font-size': 9,
                        'curve-style': 'bezier',
                      },
                    },
                  ]}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

