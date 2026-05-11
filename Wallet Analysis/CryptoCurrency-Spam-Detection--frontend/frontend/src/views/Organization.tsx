import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchOrganizationKeys,
  createOrganizationKey,
  deleteOrganizationKey,
  revokeOrganizationKey,
} from '../lib/endpoints'
import { Skeleton } from '../components/Skeleton'
import { ResponsiveContainer, AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts'
import { KeyRound, Plus, TriangleAlert, Trash2, Ban, Copy, Check } from 'lucide-react'
import toast from 'react-hot-toast'

type ApiKey = {
  id: string
  name: string
  key: string
  permissions: 'read' | 'write' | 'admin'
  tier: 'free' | 'pro' | 'enterprise'
  isActive: boolean
  expiresAt: string | null
  lastUsedAt: string | null
  callCount: number
  createdAt: string
}

const TIER_COLORS: Record<string, string> = {
  free: 'border-gray-400/20 bg-gray-500/10 text-gray-300',
  pro: 'border-violet-400/20 bg-violet-500/10 text-violet-200',
  enterprise: 'border-amber-400/20 bg-amber-500/10 text-amber-200',
}

const PERM_COLORS: Record<string, string> = {
  read: 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
  write: 'border-blue-400/20 bg-blue-500/10 text-blue-200',
  admin: 'border-rose-400/20 bg-rose-500/10 text-rose-200',
}

export function OrganizationPage() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyPerms, setNewKeyPerms] = useState<'read' | 'write' | 'admin'>('read')
  const [newKeyTier, setNewKeyTier] = useState<'free' | 'pro' | 'enterprise'>('free')
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [newKeyValue, setNewKeyValue] = useState<string | null>(null)

  const q = useQuery({ queryKey: ['org-keys'], queryFn: () => fetchOrganizationKeys() })

  const data = (q.data ?? {}) as any
  const keys: ApiKey[] = Array.isArray(data?.keys) ? data.keys : []
  const usage = Array.isArray(data?.usage) ? data.usage : []

  const createMutation = useMutation({
    mutationFn: () =>
      createOrganizationKey({ name: newKeyName, permissions: newKeyPerms, tier: newKeyTier }),
    onSuccess: (created: any) => {
      qc.invalidateQueries({ queryKey: ['org-keys'] })
      setNewKeyValue(created.key)
      setNewKeyName('')
      setShowCreate(false)
      toast.success('API key created')
    },
    onError: () => toast.error('Failed to create key'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteOrganizationKey(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['org-keys'] }); toast.success('Key deleted') },
    onError: () => toast.error('Failed to delete key'),
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeOrganizationKey(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['org-keys'] }); toast.success('Key revoked') },
    onError: () => toast.error('Failed to revoke key'),
  })

  const copyKey = (id: string, key: string) => {
    navigator.clipboard.writeText(key).then(() => {
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
      toast.success('Copied to clipboard')
    })
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div>
          <div className="page-header">Organization</div>
          <div className="page-subheader">API keys, usage analytics, and webhooks</div>
        </div>

        {newKeyValue && (
          <div className="glass border border-emerald-400/20 bg-emerald-500/5 p-4">
            <div className="text-sm font-semibold text-emerald-200">New API key — copy it now, it won't be shown again</div>
            <div className="mt-2 flex items-center gap-2">
              <code className="flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs text-emerald-300 break-all">
                {newKeyValue}
              </code>
              <button type="button" className="btn-ghost shrink-0" onClick={() => copyKey('new', newKeyValue)}>
                {copiedId === 'new' ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
            <button type="button" className="mt-3 text-xs text-gray-400 hover:text-gray-200" onClick={() => setNewKeyValue(null)}>
              Dismiss
            </button>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="glass p-4">
            <div className="flex items-end justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-gray-100">
                  <KeyRound className="h-4 w-4 text-violet-300" />
                  API keys
                </div>
                <div className="mt-1 text-xs text-gray-400">Read / Write / Admin + expiration.</div>
              </div>
              <button type="button" className="btn-primary" onClick={() => setShowCreate(v => !v)}>
                <Plus className="h-4 w-4" />
                Create key
              </button>
            </div>

            {showCreate && (
              <div className="mt-4 grid gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <div className="text-sm font-semibold text-gray-100">New API key</div>
                <input
                  className="input"
                  placeholder="Key name (e.g. Production)"
                  value={newKeyName}
                  onChange={e => setNewKeyName(e.target.value)}
                />
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="mb-1 block text-xs text-gray-400">Permissions</label>
                    <select className="input" value={newKeyPerms} onChange={e => setNewKeyPerms(e.target.value as any)}>
                      <option value="read">Read</option>
                      <option value="write">Write</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-gray-400">Tier</label>
                    <select className="input" value={newKeyTier} onChange={e => setNewKeyTier(e.target.value as any)}>
                      <option value="free">Free</option>
                      <option value="pro">Pro</option>
                      <option value="enterprise">Enterprise</option>
                    </select>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={!newKeyName.trim() || createMutation.isPending}
                    onClick={() => createMutation.mutate()}
                  >
                    {createMutation.isPending ? 'Creating…' : 'Create'}
                  </button>
                  <button type="button" className="btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
                </div>
              </div>
            )}

            <div className="mt-4 w-full overflow-x-auto">
              <table className="min-w-[600px] w-full text-left text-sm">
                <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-gray-400">
                  <tr>
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">Permissions</th>
                    <th className="px-4 py-3">Tier</th>
                    <th className="px-4 py-3">Calls</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {q.isLoading ? (
                    Array.from({ length: 3 }).map((_, i) => (
                      <tr key={i}>{Array.from({ length: 5 }).map((__, j) => (
                        <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                      ))}</tr>
                    ))
                  ) : keys.length === 0 ? (
                    <tr>
                      <td className="px-4 py-10 text-center text-sm text-gray-400" colSpan={5}>
                        No API keys yet. Create one above.
                      </td>
                    </tr>
                  ) : (
                    keys.map(k => (
                      <tr key={k.id} className={['hover:bg-white/[0.02]', !k.isActive ? 'opacity-50' : ''].join(' ')}>
                        <td className="px-4 py-3">
                          <div className="text-gray-100">{k.name}</div>
                          <div className="mt-0.5 font-mono text-xs text-gray-500">{k.key}</div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`rounded-full border px-2 py-0.5 text-xs ${PERM_COLORS[k.permissions] ?? ''}`}>{k.permissions}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`rounded-full border px-2 py-0.5 text-xs ${TIER_COLORS[k.tier] ?? ''}`}>{k.tier}</span>
                        </td>
                        <td className="px-4 py-3 text-gray-300">{k.callCount.toLocaleString()}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1">
                            <button type="button" title="Copy" className="rounded-lg p-1.5 text-gray-400 hover:bg-white/[0.06] hover:text-gray-100" onClick={() => copyKey(k.id, k.key)}>
                              {copiedId === k.id ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                            </button>
                            {k.isActive && (
                              <button type="button" title="Revoke" className="rounded-lg p-1.5 text-gray-400 hover:bg-amber-500/10 hover:text-amber-300" onClick={() => revokeMutation.mutate(k.id)}>
                                <Ban className="h-3.5 w-3.5" />
                              </button>
                            )}
                            <button type="button" title="Delete" className="rounded-lg p-1.5 text-gray-400 hover:bg-rose-500/10 hover:text-rose-300" onClick={() => deleteMutation.mutate(k.id)}>
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="glass p-4">
            <div className="text-sm font-semibold text-gray-100">Usage analytics</div>
            <div className="mt-1 text-xs text-gray-400">API calls per day (last 30 days).</div>
            <div className="mt-3 h-56">
              {q.isLoading ? (
                <Skeleton className="h-full w-full rounded-2xl" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={usage}>
                    <defs>
                      <linearGradient id="calls" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="rgb(124,58,237)" stopOpacity={0.45} />
                        <stop offset="100%" stopColor="rgb(124,58,237)" stopOpacity={0.05} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    <XAxis dataKey="day" tick={{ fill: 'rgba(229,231,235,0.6)', fontSize: 11 }} tickLine={false} />
                    <YAxis tick={{ fill: 'rgba(229,231,235,0.6)', fontSize: 11 }} tickLine={false} />
                    <Tooltip contentStyle={{ background: 'rgba(0,0,0,0.85)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 12 }} />
                    <Area type="monotone" dataKey="calls" stroke="rgb(124,58,237)" fill="url(#calls)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
            {data?.rateLimitWarning ? (
              <div className="mt-4 rounded-2xl border border-amber-400/20 bg-amber-500/10 p-4 text-sm text-amber-200">
                <div className="flex items-center gap-2 font-semibold"><TriangleAlert className="h-4 w-4" />Rate limit warning</div>
                <div className="mt-1 text-xs text-amber-200/70">{String(data.rateLimitWarning)}</div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="glass p-4">
          <div className="text-sm font-semibold text-gray-100">Webhooks</div>
          <div className="mt-1 text-xs text-gray-400">Configure event delivery and secrets.</div>
          <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto]">
            <input className="input" placeholder="Webhook URL (https://…)" />
            <button type="button" className="btn-primary">Test webhook</button>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {['address.update', 'alert.triggered', 'risk.change', 'watchlist.match'].map(event => (
              <label key={event} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-gray-200">
                <span>{event}</span>
                <input type="checkbox" className="h-4 w-4 accent-violet-500" defaultChecked={event.startsWith('alert')} />
              </label>
            ))}
          </div>
          <div className="mt-3 grid gap-2">
            <label className="text-xs font-medium text-gray-400">Webhook secret</label>
            <input className="input" type="password" placeholder="••••••••" />
          </div>
        </div>
      </div>
    </div>
  )
}
