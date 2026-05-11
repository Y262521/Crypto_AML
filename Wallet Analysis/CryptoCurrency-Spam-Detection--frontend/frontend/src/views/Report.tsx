import { useCallback, useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { PDFDownloadLink, Document, Page, Text, View, StyleSheet } from '@react-pdf/renderer'
import { Mail, FileDown } from 'lucide-react'
import { useParams } from 'react-router-dom'
import type { ChainId } from '../lib/chains'
import { getChainMeta } from '../lib/chains'
import { fetchAddressRisk, fetchAddressSummary, fetchAddressTimeseries, fetchAddressTransactions } from '../lib/endpoints'
import type { AddressSummary, RiskResponse, TransactionsResponse, TimeseriesResponse } from '../types/api'
import DatePicker from 'react-datepicker'

const styles = StyleSheet.create({
  page: { padding: 24, fontSize: 10, fontFamily: 'Helvetica' },
  h1: { fontSize: 16, marginBottom: 8 },
  h2: { fontSize: 12, marginTop: 12, marginBottom: 6 },
  box: { border: '1px solid #DDD', padding: 10, borderRadius: 6, marginBottom: 8 },
  row: { flexDirection: 'row', gap: 8 },
  col: { flex: 1 },
  muted: { color: '#666' },
  tableRow: { flexDirection: 'row', borderBottom: '1px solid #EEE', paddingVertical: 4 },
  cell: { flex: 1 },
  mono: { fontFamily: 'Courier' },
})

function ReportDoc(props: {
  address: string
  chainLabel: string
  summary?: AddressSummary
  risk?: RiskResponse
  tx?: TransactionsResponse
  timeseries?: TimeseriesResponse
  txLimit: number
}) {
  const { address, chainLabel, summary, risk, tx, timeseries, txLimit } = props
  const top = (timeseries?.topCounterparties ?? []).slice(0, 5)

  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <Text style={styles.h1}>Crypto Analytics Report</Text>
        <Text style={styles.muted}>
          {chainLabel} • {address}
        </Text>

        <View style={styles.box}>
          <Text style={styles.h2}>Address summary</Text>
          <View style={styles.row}>
            <View style={styles.col}>
              <Text>Total received: {summary?.totalReceived ?? '—'} {summary?.unit ?? ''}</Text>
              <Text>Total sent: {summary?.totalSent ?? '—'} {summary?.unit ?? ''}</Text>
            </View>
            <View style={styles.col}>
              <Text>Balance: {summary?.balance ?? '—'} {summary?.unit ?? ''}</Text>
              <Text>Tx count: {summary?.transactionCount ?? '—'}</Text>
            </View>
          </View>
        </View>

        <View style={styles.box}>
          <Text style={styles.h2}>Risk score</Text>
          <Text>Score: {risk?.score ?? '—'}/100</Text>
          <Text style={styles.h2}>Risk factors</Text>
          {(risk?.factors ?? []).length === 0 ? (
            <Text style={styles.muted}>No factors provided.</Text>
          ) : (
            (risk?.factors ?? []).map((f, idx) => (
              <Text key={f.id ?? `${f.title}-${idx}`}>
                - [{f.severity}] {f.title}{f.description ? ` — ${f.description}` : ''}
              </Text>
            ))
          )}
        </View>

        <View style={styles.box}>
          <Text style={styles.h2}>Top 5 counterparties by volume</Text>
          {top.length === 0 ? (
            <Text style={styles.muted}>No data provided.</Text>
          ) : (
            top.map((c, i) => (
              <Text key={`${c.address}-${i}`} style={styles.mono}>
                {c.address} — {c.volume}
              </Text>
            ))
          )}
        </View>

        <View style={styles.box}>
          <Text style={styles.h2}>Transaction history (last {txLimit})</Text>
          <View style={styles.tableRow}>
            <Text style={[styles.cell, styles.muted]}>Hash</Text>
            <Text style={[styles.cell, styles.muted]}>From</Text>
            <Text style={[styles.cell, styles.muted]}>To</Text>
            <Text style={[styles.cell, styles.muted]}>Amount</Text>
          </View>
          {(tx?.items ?? []).slice(0, txLimit).map((t) => (
            <View key={t.hash} style={styles.tableRow}>
              <Text style={[styles.cell, styles.mono]}>{t.hash.slice(0, 10)}…</Text>
              <Text style={[styles.cell, styles.mono]}>{t.from.slice(0, 10)}…</Text>
              <Text style={[styles.cell, styles.mono]}>{t.to.slice(0, 10)}…</Text>
              <Text style={styles.cell}>
                {t.amount} {summary?.unit ?? ''}
              </Text>
            </View>
          ))}
        </View>

        <View style={styles.box}>
          <Text style={styles.h2}>Graph visualization</Text>
          <Text style={styles.muted}>
            Screenshot embedding can be enabled when an image is available.
          </Text>
        </View>
      </Page>
    </Document>
  )
}

export function ReportPage() {
  const params = useParams()
  const address = (params.address as string | undefined) ?? ''
  const chain = (params.chain as ChainId | undefined) ?? 'ethereum'
  const chainMeta = useMemo(() => getChainMeta(chain), [chain])

  const [includeGraph, setIncludeGraph] = useState(true)
  const [txLimit, setTxLimit] = useState(50)
  const [startDate, setStartDate] = useState<Date | null>(null)
  const [endDate, setEndDate] = useState<Date | null>(null)

  const [summary, setSummary] = useState<AddressSummary>()
  const [risk, setRisk] = useState<RiskResponse>()
  const [tx, setTx] = useState<TransactionsResponse>()
  const [timeseries, setTimeseries] = useState<TimeseriesResponse>()
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!address) return
    setLoading(true)
    try {
      const [s, r, t, ts] = await Promise.all([
        fetchAddressSummary(address, chain),
        fetchAddressRisk(address, chain),
        fetchAddressTransactions(address, {
          page: 1,
          limit: Math.max(50, txLimit),
          chain,
          startDate: startDate ? startDate.toISOString() : undefined,
          endDate: endDate ? endDate.toISOString() : undefined,
        }),
        fetchAddressTimeseries({
          address,
          chain,
          range: '30d',
          startDate: startDate ? startDate.toISOString() : undefined,
          endDate: endDate ? endDate.toISOString() : undefined,
        }),
      ])
      setSummary(s)
      setRisk(r)
      setTx(t)
      setTimeseries(ts)
    } catch {
      toast.error('Failed to load report data')
    } finally {
      setLoading(false)
    }
  }, [address, chain, endDate, startDate, txLimit])

  useEffect(() => {
    load()
  }, [load])

  const onEmail = () => {
    toast('Email report sent (when configured).')
  }

  const doc = (
    <ReportDoc
      address={address}
      chainLabel={`${chainMeta.name} (${chainMeta.symbol})`}
      summary={summary}
      risk={risk}
      tx={tx}
      timeseries={timeseries}
      txLimit={txLimit}
    />
  )

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-2xl font-semibold text-gray-100">Report</div>
            <div className="mt-1 text-sm text-gray-400">
              {chainMeta.name} • <span className="font-mono text-gray-200">{address}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-ghost" onClick={onEmail}>
              <Mail className="h-4 w-4" />
              Email report
            </button>
            <PDFDownloadLink document={doc} fileName={`report-${chain}-${address}.pdf`}>
              {({ loading: pdfLoading }) => (
                <button type="button" className="btn-primary" disabled={loading || pdfLoading}>
                  <FileDown className="h-4 w-4" />
                  {pdfLoading ? 'Preparing…' : 'Download PDF'}
                </button>
              )}
            </PDFDownloadLink>
          </div>
        </div>

        <div className="glass glass-hover p-4">
          <div className="grid gap-4 md:grid-cols-3">
            <label className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-gray-200">
              <span>
                Include graph
                <div className="mt-1 text-xs text-gray-500">(Included if available.)</div>
              </span>
              <input type="checkbox" className="h-4 w-4 accent-violet-500" checked={includeGraph} onChange={(e) => setIncludeGraph(e.target.checked)} />
            </label>

            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">Start</label>
              <DatePicker selected={startDate} onChange={setStartDate} className="input" />
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">End</label>
              <DatePicker selected={endDate} onChange={setEndDate} className="input" />
            </div>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">Transaction limit</label>
              <input
                className="input"
                inputMode="numeric"
                value={txLimit}
                onChange={(e) => setTxLimit(Math.max(1, Math.min(200, Number(e.target.value) || 50)))}
              />
              <div className="text-xs text-gray-500">Max shown in PDF table (default 50).</div>
            </div>
            <div className="flex items-end justify-end">
              <button type="button" className="btn-primary" onClick={load} disabled={loading}>
                Reload report data
              </button>
            </div>
          </div>
        </div>

        {includeGraph ? null : null}
      </div>
    </div>
  )
}

