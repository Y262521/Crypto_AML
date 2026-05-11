import { useCallback, useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { MailPlus, Users } from 'lucide-react'
import { fetchTeamActivity, fetchTeams, inviteToTeam } from '../lib/endpoints'
import type { Team, TeamActivityItem } from '../types/api'
import { Skeleton } from '../components/Skeleton'

export function TeamsPage() {
  const [teams, setTeams] = useState<Team[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<Team | null>(null)
  const [activity, setActivity] = useState<TeamActivityItem[]>([])
  const [loadingActivity, setLoadingActivity] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchTeams()
      setTeams(data)
      setSelected((prev) => prev ?? data[0] ?? null)
    } catch {
      toast.error('Failed to load teams')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const loadActivity = useCallback(async (teamId: string) => {
    setLoadingActivity(true)
    try {
      const data = await fetchTeamActivity(teamId)
      setActivity(data)
    } catch {
      toast.error('Failed to load activity')
    } finally {
      setLoadingActivity(false)
    }
  }, [])

  useEffect(() => {
    if (selected) loadActivity(selected.id)
  }, [loadActivity, selected])

  const canInvite = selected?.role === 'Admin'

  const onInvite = useCallback(async () => {
    if (!selected) return
    if (!inviteEmail.trim()) {
      toast.error('Enter an email')
      return
    }
    try {
      await inviteToTeam(selected.id, inviteEmail.trim())
      toast.success('Invite sent')
      setInviteEmail('')
      loadActivity(selected.id).catch(() => {})
    } catch {
      toast.error('Invite failed')
    }
  }, [inviteEmail, loadActivity, selected])

  const rolePill = useMemo(() => {
    const r = selected?.role ?? 'Viewer'
    if (r === 'Admin') return 'border-violet-400/20 bg-violet-500/10 text-violet-200'
    if (r === 'Analyst') return 'border-sky-400/20 bg-sky-500/10 text-sky-200'
    return 'border-white/10 bg-white/[0.03] text-gray-300'
  }, [selected?.role])

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div>
          <div className="page-header">Teams</div>
          <div className="page-subheader">Manage team members and activity</div>
        </div>

        <div className="grid gap-4 lg:grid-cols-12">
          <div className="glass lg:col-span-4">
            <div className="flex items-center gap-2 border-b border-white/10 p-4">
              <Users className="h-4 w-4 text-violet-300" />
              <div className="text-sm font-semibold text-gray-100">Your teams</div>
            </div>
            <div className="grid gap-2 p-4">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)
              ) : teams.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 text-sm text-gray-400">
                  No teams returned by API.
                </div>
              ) : (
                teams.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className={[
                      'glass glass-hover w-full p-4 text-left',
                      selected?.id === t.id ? 'ring-1 ring-violet-400/20' : '',
                    ].join(' ')}
                    onClick={() => setSelected(t)}
                  >
                    <div className="text-sm font-semibold text-gray-100">{t.name}</div>
                    <div className="mt-1 text-xs text-gray-400">{t.description ?? '—'}</div>
                    <div className="mt-3">
                      <span className={`rounded-full border px-3 py-1 text-xs ${t.role === 'Admin' ? 'border-violet-400/20 bg-violet-500/10 text-violet-200' : t.role === 'Analyst' ? 'border-sky-400/20 bg-sky-500/10 text-sky-200' : 'border-white/10 bg-white/[0.03] text-gray-300'}`}>
                        {t.role}
                      </span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="lg:col-span-8">
            {selected ? (
              <div className="flex flex-col gap-4">
                <div className="glass p-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="text-sm font-semibold text-gray-100">{selected.name}</div>
                      <div className="mt-1 text-xs text-gray-400">{selected.description ?? '—'}</div>
                    </div>
                    <span className={`rounded-full border px-3 py-1 text-xs ${rolePill}`}>{selected.role}</span>
                  </div>

                  <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto]">
                    <input
                      className="input"
                      placeholder={canInvite ? 'Invite user by email…' : 'Only Admins can invite users'}
                      value={inviteEmail}
                      disabled={!canInvite}
                      onChange={(e) => setInviteEmail(e.target.value)}
                    />
                    <button type="button" className="btn-primary" onClick={onInvite} disabled={!canInvite}>
                      <MailPlus className="h-4 w-4" />
                      Invite
                    </button>
                  </div>
                </div>

                <div className="glass overflow-hidden">
                  <div className="border-b border-white/10 p-4">
                    <div className="text-sm font-semibold text-gray-100">Activity feed</div>
                    <div className="mt-1 text-xs text-gray-400">Who added what, who commented, who changed risk.</div>
                  </div>
                  <div className="p-4">
                    {loadingActivity ? (
                      <div className="grid gap-2">
                        {Array.from({ length: 6 }).map((_, i) => (
                          <Skeleton key={i} className="h-10 w-full" />
                        ))}
                      </div>
                    ) : activity.length === 0 ? (
                      <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 text-sm text-gray-400">
                        No activity returned by API.
                      </div>
                    ) : (
                      <div className="grid gap-2">
                        {activity.map((a) => (
                          <div key={a.id} className="rounded-2xl border border-white/10 bg-white/[0.02] p-3">
                            <div className="text-sm text-gray-200">
                              <span className="font-semibold text-gray-100">{a.actor}</span> {a.action}
                            </div>
                            <div className="mt-1 text-xs text-gray-500">
                              {a.createdAt ? new Date(a.createdAt).toLocaleString() : '—'}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="glass p-6 text-sm text-gray-400">Select a team.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

