import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import toast from 'react-hot-toast'
import type { ChainId } from '../lib/chains'
import { fetchAddressTimeseries } from '../lib/endpoints'
import type { TimeseriesPoint, TimeseriesResponse } from '../types/api'
import { Skeleton } from './Skeleton'
import DatePicker from 'react-datepicker'

type Props = {
  address: string
  chain: ChainId
}

function fmtDay(ts: string) {
  try {
    return new Date(ts).toISOString().slice(5, 10)
  } catch {
    return ts
  }
}

export function AnalyticsTab({ address, chain }: Props) {
  const [range, setRange] = useState<'30d' | '90d' | '180d'>('30d')
  const [startDate, setStartDate] = useState<Date | null>(null)
  const [endDate, setEndDate] = useState<Date | null>(null)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<TimeseriesResponse | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchAddressTimeseries({
        address,
        chain,
        range,
        startDate: startDate ? startDate.toISOString() : undefined,
        endDate: endDate ? endDate.toISOString() : undefined,
      })
      setData(res)
    } catch {
      toast.error('Failed to load analytics')
    } finally {
      setLoading(false)
    }
  }, [address, chain, endDate, range, startDate])

  useEffect(() => {
    load()
  }, [load])

  const points = useMemo(() => {
    const p = (data?.points ?? []) as TimeseriesPoint[]
    return p.map((x) => ({
      ...x,
      day: fmtDay(x.ts),
      inflow: x.inflow ?? 0,
      outflow: x.outflow ?? 0,
      balance: x.balance ?? 0,
      txCount: x.txCount ?? 0,
    }))
  }, [data?.points])

  const top = useMemo(() => (data?.topCounterparties ?? []).slice(0, 5), [data?.topCounterparties])

  // calendar heatmap (simple)
  const heat = useMemo(() => {
    const last = points.slice(-84) // ~12 weeks
    const max = Math.max(1, ...last.map((p) => p.txCount ?? 0))
    return { last, max }
  }, [points])

  return (
    <div className="grid gap-4">
      <div className="glass glass-hover p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-sm font-semibold text-gray-100">Time-series analytics</div>
            <div className="mt-1 text-xs text-gray-400">Date range applies to all charts.</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              value={range}
              onChange={(e) => setRange(e.target.value as any)}
              className="h-9 rounded-xl border border-white/10 bg-[#0B0B0B] px-3 text-xs text-white outline-none transition focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
            >
              <option value="30d">30d</option>
              <option value="90d">90d</option>
              <option value="180d">180d</option>
            </select>
            <div className="w-40">
              <DatePicker selected={startDate} onChange={setStartDate} className="input" placeholderText="Start" />
            </div>
            <div className="w-40">
              <DatePicker selected={endDate} onChange={setEndDate} className="input" placeholderText="End" />
            </div>
            <button type="button" className="btn-primary" onClick={load} disabled={loading}>
              {loading ? 'Loading…' : 'Reload'}
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass glass-hover p-4">
          <div className="text-sm font-semibold text-gray-100">Balance over time</div>
          <div className="mt-3 h-56 min-h-[224px]">
            {loading ? (
              <Skeleton className="h-full w-full rounded-2xl" />
            ) : (
              <ResponsiveContainer width="100%" height={224}>
                <LineChart data={points}>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                  <XAxis dataKey="day" tick={{ fill: 'rgba(229,231,235,0.6)', fontSize: 12 }} tickLine={false} />
                  <YAxis tick={{ fill: 'rgba(229,231,235,0.6)', fontSize: 12 }} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(0,0,0,0.85)',
                      border: '1px solid rgba(255,255,255,0.12)',
                      borderRadius: 12,
                    }}
                  />
                  <Line type="monotone" dataKey="balance" stroke="rgb(124, 58, 237)" strokeWidth={2} dot />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="glass glass-hover p-4">
          <div className="text-sm font-semibold text-gray-100">Inflow / Outflow velocity</div>
          <div className="mt-3 h-56 min-h-[224px]">
            {loading ? (
              <Skeleton className="h-full w-full rounded-2xl" />
            ) : (
              <ResponsiveContainer width="100%" height={224}>
                <AreaChart data={points}>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                  <XAxis dataKey="day" tick={{ fill: 'rgba(229,231,235,0.6)', fontSize: 12 }} tickLine={false} />
                  <YAxis tick={{ fill: 'rgba(229,231,235,0.6)', fontSize: 12 }} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(0,0,0,0.85)',
                      border: '1px solid rgba(255,255,255,0.12)',
                      borderRadius: 12,
                    }}
                  />
                  <Area type="monotone" dataKey="inflow" stroke="#34d399" fill="rgba(52,211,153,0.25)" />
                  <Area type="monotone" dataKey="outflow" stroke="#fb7185" fill="rgba(251,113,133,0.25)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="glass glass-hover p-4">
          <div className="text-sm font-semibold text-gray-100">Concentration metrics</div>
          <div className="mt-1 text-xs text-gray-400">Top 5 counterparties by volume</div>
          <div className="mt-3 h-56 min-h-[224px]">
            {loading ? (
              <Skeleton className="h-full w-full rounded-2xl" />
            ) : (
              <ResponsiveContainer width="100%" height={224}>
                <BarChart data={top.map((c) => ({ ...c, label: c.address.slice(0, 8) + '…' }))} layout="vertical">
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" horizontal={false} />
                  <XAxis type="number" tick={{ fill: 'rgba(229,231,235,0.6)', fontSize: 12 }} tickLine={false} />
                  <YAxis type="category" dataKey="label" tick={{ fill: 'rgba(229,231,235,0.6)', fontSize: 12 }} width={80} />
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(0,0,0,0.85)',
                      border: '1px solid rgba(255,255,255,0.12)',
                      borderRadius: 12,
                    }}
                  />
                  <Bar dataKey="volume" fill="rgba(124, 58, 237, 0.75)" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="glass glass-hover p-4">
          <div className="text-sm font-semibold text-gray-100">Transaction heatmap</div>
          <div className="mt-1 text-xs text-gray-400">Calendar-style frequency (derived from timeseries).</div>
          <div className="mt-4 grid grid-cols-14 gap-2">
            {heat.last.map((p, idx) => {
              const v = p.txCount ?? 0
              const a = Math.min(1, v / heat.max)
              return (
                <div
                  key={idx}
                  title={`${p.ts}: ${v} tx`}
                  className="h-4 w-full rounded"
                  style={{
                    background: `rgba(124, 58, 237, ${0.12 + 0.75 * a})`,
                    border: '1px solid rgba(255,255,255,0.08)',
                  }}
                />
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

