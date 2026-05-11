import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { Skeleton } from '../components/Skeleton'
import { api } from '../lib/api'

function toCsv(rows: any[]) {
  const header = ['timestamp', 'actor', 'action', 'resource', 'meta']
  const lines = [header.join(',')]
  for (const r of rows) {
    lines.push(
      [
        r.timestamp ?? r.createdAt ?? '',
        r.actor ?? '',
        r.action ?? '',
        r.resource ?? '',
        JSON.stringify(r.meta ?? {}).replaceAll(',', ' '),
      ].join(','),
    )
  }
  return lines.join('\n')
}

export function AuditPage() {
  const q = useQuery({
    queryKey: ['audit-log'],
    queryFn: async () => {
      const res = await api.get(`/api/v1/audit`)
      return res.data
    },
  })

  const rows = useMemo(() => {
    const data = q.data as any
    return Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : []
  }, [q.data])

  const exportCsv = () => {
    const csv = toCsv(rows)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'audit-log.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="page-header">Audit Log</div>
            <div className="page-subheader">Track all user actions and system events</div>
          </div>
          <button type="button" className="btn-ghost" onClick={exportCsv} disabled={rows.length === 0}>
            <Download className="h-4 w-4" />
            Export CSV
          </button>
        </div>

        <div className="glass w-full overflow-hidden">
          <div className="w-full overflow-x-auto">
            <table className="min-w-[980px] w-full text-left text-sm">
              <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-gray-400">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Resource</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {q.isLoading ? (
                  Array.from({ length: 10 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 4 }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-4 w-40" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : rows.length === 0 ? (
                  <tr>
                    <td className="px-4 py-10 text-center text-sm text-gray-400" colSpan={4}>
                      No audit entries.
                    </td>
                  </tr>
                ) : (
                  rows.map((r: any, idx: number) => (
                    <tr key={r.id ?? idx} className="hover:bg-white/[0.02]">
                      <td className="px-4 py-3 text-gray-300">
                        {new Date(r.timestamp ?? r.createdAt ?? Date.now()).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-gray-200">{r.actor ?? '—'}</td>
                      <td className="px-4 py-3 text-gray-200">{r.action ?? '—'}</td>
                      <td className="px-4 py-3 text-gray-300">{r.resource ?? '—'}</td>
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

