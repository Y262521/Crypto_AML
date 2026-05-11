import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Beaker, Save, Mail, CheckCircle, Info } from 'lucide-react'
import { fetchAlertSettings, saveAlertSettings } from '../lib/endpoints'
import { api } from '../lib/api'
import type { AlertSettings } from '../types/api'
import { Skeleton } from '../components/Skeleton'

const PROVIDER_INFO = {
  resend: { label: 'Resend', color: 'text-emerald-300', bg: 'border-emerald-400/20 bg-emerald-500/10' },
  gmail: { label: 'Gmail', color: 'text-blue-300', bg: 'border-blue-400/20 bg-blue-500/10' },
  smtp: { label: 'SMTP', color: 'text-violet-300', bg: 'border-violet-400/20 bg-violet-500/10' },
  none: { label: 'Not configured', color: 'text-gray-400', bg: 'border-gray-400/20 bg-gray-500/10' },
}

export function AlertSettingsPage() {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testingEmail, setTestingEmail] = useState(false)
  const [settings, setSettings] = useState<AlertSettings>({})
  const [emailProvider, setEmailProvider] = useState<'resend' | 'gmail' | 'smtp' | 'none'>('none')
  const [testEmailAddr, setTestEmailAddr] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const s = await fetchAlertSettings() as any
      setSettings(s ?? {})
      setEmailProvider(s?.emailProvider ?? 'none')
    } catch {
      toast.error('Failed to load alert settings')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const save = useCallback(async (extra?: { test?: 'telegram' | 'discord' | 'email' }) => {
    setSaving(true)
    try {
      const next = await saveAlertSettings({ ...(settings ?? {}), ...(extra ?? {}) }) as any
      setSettings(next ?? settings)
      setEmailProvider(next?.emailProvider ?? emailProvider)
      toast.success(extra?.test ? 'Test sent (if configured)' : 'Settings saved')
    } catch {
      toast.error(extra?.test ? 'Test failed' : 'Save failed')
    } finally {
      setSaving(false)
    }
  }, [settings, emailProvider])

  const sendTestEmail = useCallback(async () => {
    const addr = testEmailAddr.trim() || (settings.email as any)?.address
    if (!addr) { toast.error('Enter an email address to test'); return }
    setTestingEmail(true)
    try {
      const res = await api.post('/api/v1/alerts/test-email', { to: addr })
      const data = res.data as any
      if (data?.success) {
        toast.success(`Test email sent via ${data.provider} to ${addr}`)
      } else {
        toast.error(`Email failed (${data?.provider ?? 'unknown'}): ${data?.error ?? 'check server logs'}`)
      }
    } catch (e: any) {
      toast.error(e?.response?.data?.message ?? 'Test email request failed')
    } finally {
      setTestingEmail(false)
    }
  }, [testEmailAddr, settings])

  const rules = settings.rules ?? {}
  const telegram = settings.telegram ?? {}
  const discord = settings.discord ?? {}
  const email = settings.email ?? {}
  const providerInfo = PROVIDER_INFO[emailProvider]

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="page-header">Alert Settings</div>
            <div className="page-subheader">Configure notification channels and rules</div>
          </div>
          <button type="button" className="btn-primary" onClick={() => save()} disabled={saving || loading}>
            <Save className="h-4 w-4" />
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>

        {loading ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="glass p-4">
                <Skeleton className="h-5 w-40" />
                <Skeleton className="mt-4 h-10 w-full" />
                <Skeleton className="mt-3 h-10 w-full" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">

            {/* Telegram */}
            <div className="glass glass-hover p-4">
              <div className="text-sm font-semibold text-gray-100">Telegram</div>
              <div className="mt-1 text-xs text-gray-400">Bot Token + Chat ID. Create a bot via @BotFather.</div>
              <div className="mt-4 grid gap-3">
                <input className="input" placeholder="Bot Token (e.g. 123456:ABC-DEF…)"
                  value={telegram.botToken ?? ''}
                  onChange={(e) => setSettings((s) => ({ ...s, telegram: { ...(s.telegram ?? {}), botToken: e.target.value } }))} />
                <input className="input" placeholder="Chat ID (e.g. -100123456789)"
                  value={telegram.chatId ?? ''}
                  onChange={(e) => setSettings((s) => ({ ...s, telegram: { ...(s.telegram ?? {}), chatId: e.target.value } }))} />
                <div className="flex justify-end">
                  <button type="button" className="btn-ghost" onClick={() => save({ test: 'telegram' })} disabled={saving}>
                    <Beaker className="h-4 w-4" /> Test
                  </button>
                </div>
              </div>
            </div>

            {/* Discord */}
            <div className="glass glass-hover p-4">
              <div className="text-sm font-semibold text-gray-100">Discord</div>
              <div className="mt-1 text-xs text-gray-400">Server → Channel settings → Integrations → Webhooks.</div>
              <div className="mt-4 grid gap-3">
                <input className="input" placeholder="Webhook URL (https://discord.com/api/webhooks/…)"
                  value={discord.webhookUrl ?? ''}
                  onChange={(e) => setSettings((s) => ({ ...s, discord: { ...(s.discord ?? {}), webhookUrl: e.target.value } }))} />
                <div className="flex justify-end">
                  <button type="button" className="btn-ghost" onClick={() => save({ test: 'discord' })} disabled={saving}>
                    <Beaker className="h-4 w-4" /> Test
                  </button>
                </div>
              </div>
            </div>

            {/* Email */}
            <div className="glass glass-hover p-4">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="text-sm font-semibold text-gray-100">Email</div>
                  <div className="mt-1 text-xs text-gray-400">Destination address for alert emails.</div>
                </div>
                <span className={`rounded-full border px-2 py-0.5 text-xs ${providerInfo.bg} ${providerInfo.color}`}>
                  {providerInfo.label}
                </span>
              </div>

              {emailProvider === 'none' ? (
                <div className="mt-3 rounded-xl border border-amber-400/20 bg-amber-500/5 p-3 text-xs text-amber-200">
                  <div className="flex items-center gap-2 font-semibold mb-1">
                    <Info className="h-3.5 w-3.5" /> No email provider configured
                  </div>
                  <div className="text-amber-200/70 font-mono space-y-0.5 mt-1">
                    <div className="text-emerald-300">RESEND_API_KEY=re_xxxx</div>
                    <div className="text-gray-400">or</div>
                    <div className="text-blue-300">GMAIL_USER=you@gmail.com</div>
                    <div className="text-blue-300">GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx</div>
                  </div>
                </div>
              ) : (
                <div className={`mt-3 rounded-xl border p-2 text-xs flex items-center gap-2 ${providerInfo.bg} ${providerInfo.color}`}>
                  <CheckCircle className="h-3.5 w-3.5" /> Sending via {providerInfo.label}
                </div>
              )}

              <div className="mt-4 grid gap-3">
                <input className="input" placeholder="Recipient email address"
                  value={(email as any).address ?? ''}
                  onChange={(e) => setSettings((s) => ({ ...s, email: { ...(s.email ?? {}), address: e.target.value } }))} />
                <div className="flex gap-2">
                  <input className="input flex-1" placeholder="Test to (leave blank to use above)"
                    value={testEmailAddr} onChange={(e) => setTestEmailAddr(e.target.value)} />
                  <button type="button" className="btn-ghost shrink-0" onClick={sendTestEmail}
                    disabled={testingEmail || emailProvider === 'none'}>
                    <Mail className="h-4 w-4" />
                    {testingEmail ? 'Sending…' : 'Send test'}
                  </button>
                </div>
              </div>
            </div>

            {/* Alert rules */}
            <div className="glass glass-hover p-4">
              <div className="text-sm font-semibold text-gray-100">Alert rules</div>
              <div className="mt-1 text-xs text-gray-400">Thresholds and toggles</div>
              <div className="mt-4 grid gap-3">
                <div className="grid gap-2">
                  <label className="text-xs font-medium text-gray-400">Minimum amount</label>
                  <input className="input" inputMode="decimal" placeholder="e.g. 10"
                    value={rules.minimumAmount ?? ''}
                    onChange={(e) => setSettings((s) => ({ ...s, rules: { ...(s.rules ?? {}), minimumAmount: e.target.value === '' ? undefined : Number(e.target.value) } }))} />
                </div>
                <div className="grid gap-2">
                  <label className="text-xs font-medium text-gray-400">Minimum risk score</label>
                  <input className="input" inputMode="numeric" placeholder="e.g. 70"
                    value={rules.minimumRiskScore ?? ''}
                    onChange={(e) => setSettings((s) => ({ ...s, rules: { ...(s.rules ?? {}), minimumRiskScore: e.target.value === '' ? undefined : Number(e.target.value) } }))} />
                </div>
                <label className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-gray-200">
                  <span>
                    Flagged interaction alerts
                    <div className="mt-1 text-xs text-gray-500">Notify on high-risk counterparties/mixers.</div>
                  </span>
                  <input type="checkbox" className="h-4 w-4 accent-violet-500"
                    checked={Boolean(rules.flaggedInteractionEnabled)}
                    onChange={(e) => setSettings((s) => ({ ...s, rules: { ...(s.rules ?? {}), flaggedInteractionEnabled: e.target.checked } }))} />
                </label>
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  )
}
