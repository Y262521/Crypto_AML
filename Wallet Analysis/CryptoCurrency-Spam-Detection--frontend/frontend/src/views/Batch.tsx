import { useCallback, useMemo, useRef, useState } from 'react'
import Papa from 'papaparse'
import toast from 'react-hot-toast'
import { Download, UploadCloud } from 'lucide-react'
import { batchAnalyzeCsv } from '../lib/endpoints'
import type { BatchAnalyzeResult } from '../types/api'
import { Skeleton } from '../components/Skeleton'

type CsvRow = { address: string; name?: string; chain?: string }

function toCsv(results: BatchAnalyzeResult[]) {
  const header = ['address', 'name', 'chain', 'riskScore', 'transactionCount', 'status', 'error']
  const lines = [header.join(',')]
  for (const r of results) {
    lines.push(
      [
        r.address ?? '',
        (r.name ?? '').replaceAll(',', ' '),
        r.chain ?? '',
        r.riskScore ?? '',
        r.transactionCount ?? '',
        r.status ?? '',
        (r.error ?? '').replaceAll(',', ' '),
      ].join(','),
    )
  }
  return lines.join('\n')
}

export function BatchPage() {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [rows, setRows] = useState<CsvRow[]>([])
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<BatchAnalyzeResult[]>([])

  const onPick = () => inputRef.current?.click()

  const parse = useCallback((f: File) => {
    setResults([])
    Papa.parse<CsvRow>(f, {
      header: true,
      skipEmptyLines: true,
      complete: (res) => {
        const data = (res.data ?? []).slice(0, 500)
        setRows(data)
      },
      error: () => toast.error('Failed to parse CSV'),
    })
  }, [])

  const onFile = useCallback(
    (f: File | null) => {
      if (!f) return
      setFile(f)
      parse(f)
    },
    [parse],
  )

  const tooMany = rows.length > 500
  const limitedRows = useMemo(() => rows.slice(0, 500), [rows])

  const analyze = useCallback(async () => {
    if (!file) {
      toast.error('Upload a CSV first')
      return
    }
    if (tooMany) {
      toast.error('Max 500 addresses per batch')
      return
    }
    setLoading(true)
    const t = toast.loading('Analyzing…')
    try {
      const res = await batchAnalyzeCsv(file)
      setResults(res.results ?? [])
      toast.success('Batch complete', { id: t })
    } catch {
      toast.error('Batch analyze failed', { id: t })
    } finally {
      setLoading(false)
    }
  }, [file, tooMany])

  const exportResults = () => {
    const csv = toCsv(results)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'batch-results.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div>
          <div className="page-header">Batch Analysis</div>
          <div className="page-subheader">Analyze up to 500 addresses from a CSV file</div>
        </div>

        <div className="glass glass-hover p-4">
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0] ?? null)}
          />

          <div
            className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/15 bg-white/[0.02] p-10 text-center"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              const f = e.dataTransfer.files?.[0]
              if (f) onFile(f)
            }}
          >
            <UploadCloud className="h-8 w-8 text-violet-300" />
            <div className="mt-3 text-sm font-semibold text-gray-100">Drag & drop CSV here</div>
            <div className="mt-1 text-xs text-gray-400">Format: address, name, chain</div>
            <button type="button" className="btn-primary mt-5" onClick={onPick}>
              Choose file
            </button>
            {file ? <div className="mt-3 text-xs text-gray-500">{file.name}</div> : null}
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs text-gray-400">
              Preview: <span className="text-gray-200">{limitedRows.length}</span> rows
              {rows.length > 500 ? <span className="text-rose-300"> (showing first 500)</span> : null}
            </div>
            <button type="button" className="btn-primary" onClick={analyze} disabled={loading || !file}>
              {loading ? 'Processing…' : 'Analyze batch'}
            </button>
          </div>
        </div>

        <div className="glass w-full overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/10 p-4">
            <div className="text-sm font-semibold text-gray-100">Preview</div>
          </div>
          <div className="w-full overflow-x-auto">
            <table className="min-w-[900px] w-full text-left text-sm">
              <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-gray-400">
                <tr>
                  <th className="px-4 py-3">Address</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Chain</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {limitedRows.length === 0 ? (
                  <tr>
                    <td className="px-4 py-10 text-center text-sm text-gray-400" colSpan={3}>
                      Upload a CSV to preview.
                    </td>
                  </tr>
                ) : (
                  limitedRows.map((r, idx) => (
                    <tr key={idx} className="hover:bg-white/[0.02]">
                      <td className="px-4 py-3 font-mono text-xs text-gray-200">{r.address}</td>
                      <td className="px-4 py-3 text-gray-200">{r.name ?? '—'}</td>
                      <td className="px-4 py-3 text-gray-300">{r.chain ?? '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="glass w-full overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/10 p-4">
            <div className="text-sm font-semibold text-gray-100">Results</div>
            <button type="button" className="btn-ghost" onClick={exportResults} disabled={results.length === 0}>
              <Download className="h-4 w-4" />
              Export CSV
            </button>
          </div>
          <div className="w-full overflow-x-auto">
            <table className="min-w-[1100px] w-full text-left text-sm">
              <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-gray-400">
                <tr>
                  <th className="px-4 py-3">Address</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Risk Score</th>
                  <th className="px-4 py-3">Tx Count</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {loading ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 5 }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-4 w-32" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : results.length === 0 ? (
                  <tr>
                    <td className="px-4 py-10 text-center text-sm text-gray-400" colSpan={5}>
                      Run batch analysis to see results.
                    </td>
                  </tr>
                ) : (
                  results.map((r, idx) => (
                    <tr key={`${r.address}-${idx}`} className="hover:bg-white/[0.02]">
                      <td className="px-4 py-3 font-mono text-xs text-gray-200">{r.address}</td>
                      <td className="px-4 py-3 text-gray-200">{r.name ?? '—'}</td>
                      <td className="px-4 py-3 text-gray-200">{typeof r.riskScore === 'number' ? r.riskScore : '—'}</td>
                      <td className="px-4 py-3 text-gray-200">{typeof r.transactionCount === 'number' ? r.transactionCount : '—'}</td>
                      <td className="px-4 py-3 text-gray-300">{r.status}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

