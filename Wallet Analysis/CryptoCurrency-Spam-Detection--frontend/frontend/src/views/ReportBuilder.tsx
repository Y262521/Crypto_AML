import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { GripVertical, Plus, Save, Send } from 'lucide-react'
import { postCustomReport } from '../lib/endpoints'

type BlockType =
  | 'address_summary'
  | 'risk'
  | 'transactions'
  | 'graph'
  | 'compliance'
  | 'custom_text'
  | 'charts'

type Block = { id: string; type: BlockType; title: string; config?: Record<string, unknown> }

type Form = {
  templateName: string
  schedule?: 'none' | 'daily' | 'weekly' | 'monthly'
  recipients?: string
  logoUrl?: string
  primaryColor?: string
  addresses: string
}

export function ReportBuilderPage() {
  const [blocks, setBlocks] = useState<Block[]>([
    { id: 'b1', type: 'address_summary', title: 'Address summary' },
    { id: 'b2', type: 'risk', title: 'Risk score & factors' },
    { id: 'b3', type: 'transactions', title: 'Transaction table' },
  ])

  const { register, handleSubmit } = useForm<Form>({
    defaultValues: { templateName: 'Spam Detection Report', schedule: 'none', primaryColor: '#7c3aed' },
  })

  const mutation = useMutation({
    mutationFn: (payload: unknown) => postCustomReport(payload),
    onSuccess: () => toast.success('Report request submitted'),
    onError: () => toast.error('Failed to submit report request'),
  })

  const addBlock = (type: BlockType) => {
    const id = `b_${Math.random().toString(36).slice(2)}`
    const title =
      type === 'custom_text'
        ? 'Custom text'
        : type === 'charts'
          ? 'Charts'
          : type === 'compliance'
            ? 'Compliance statement'
            : type.replaceAll('_', ' ')
    setBlocks((prev) => [...prev, { id, type, title }])
  }

  const removeBlock = (id: string) => setBlocks((prev) => prev.filter((b) => b.id !== id))

  const payload = useMemo(() => ({ blocks }), [blocks])

  const onSubmit = handleSubmit((f) => {
    const addresses = f.addresses
      .split('\n')
      .map((x) => x.trim())
      .filter(Boolean)
      .slice(0, 10)
    mutation.mutate({
      templateName: f.templateName,
      schedule: f.schedule,
      recipients: f.recipients,
      branding: { logoUrl: f.logoUrl, primaryColor: f.primaryColor },
      addresses,
      blocks,
    })
  })

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="page-header">Report Builder</div>
            <div className="page-subheader">Create custom compliance reports</div>
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn-ghost">
              <Save className="h-4 w-4" />
              Save template
            </button>
            <button type="button" className="btn-primary" onClick={onSubmit} disabled={mutation.isPending}>
              <Send className="h-4 w-4" />
              Generate
            </button>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-12">
          <div className="glass lg:col-span-4">
            <div className="border-b border-white/10 p-4 text-sm font-semibold text-gray-100">Blocks</div>
            <div className="grid gap-2 p-4">
              {(
                [
                  ['address_summary', 'Address summary'],
                  ['risk', 'Risk'],
                  ['transactions', 'Transactions'],
                  ['graph', 'Graph'],
                  ['compliance', 'Compliance'],
                  ['custom_text', 'Custom text'],
                  ['charts', 'Charts'],
                ] as Array<[BlockType, string]>
              ).map(([t, label]) => (
                <button key={t} type="button" className="btn-ghost justify-between" onClick={() => addBlock(t)}>
                  <span className="flex items-center gap-2">
                    <Plus className="h-4 w-4" />
                    {label}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="lg:col-span-8">
            <form onSubmit={onSubmit} className="grid gap-4">
              <div className="glass p-4">
                <div className="text-sm font-semibold text-gray-100">Template settings</div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <input className="input" placeholder="Template name" {...register('templateName')} />
                  <select
                    className="h-10 rounded-xl border border-white/10 bg-[#0B0B0B] px-3 text-sm text-white outline-none transition focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
                    {...register('schedule')}
                  >
                    <option value="none">No schedule</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                  <input className="input" placeholder="Recipients (comma-separated)" {...register('recipients')} />
                  <input className="input" placeholder="Logo URL" {...register('logoUrl')} />
                  <input className="input" placeholder="Primary color (hex)" {...register('primaryColor')} />
                </div>
                <div className="mt-4 grid gap-2">
                  <label className="text-xs font-medium text-gray-400">Addresses (max 10, one per line)</label>
                  <textarea className="input h-28 resize-none py-3" {...register('addresses')} placeholder="0x...\n0x..." />
                </div>
              </div>

              <div className="glass overflow-hidden">
                <div className="border-b border-white/10 p-4">
                  <div className="text-sm font-semibold text-gray-100">Layout</div>
                  <div className="mt-1 text-xs text-gray-400">Reorder/remove blocks as needed.</div>
                </div>
                <div className="grid gap-2 p-4">
                  {blocks.map((b) => (
                    <div key={b.id} className="glass glass-hover flex items-center justify-between gap-3 p-4">
                      <div className="flex min-w-0 items-center gap-3">
                        <GripVertical className="h-4 w-4 text-gray-500" />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-gray-100">{b.title}</div>
                          <div className="mt-1 text-xs text-gray-400">{b.type}</div>
                        </div>
                      </div>
                      <button type="button" className="btn-ghost" onClick={() => removeBlock(b.id)}>
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="glass p-4">
                <div className="text-xs text-gray-400">Payload preview</div>
                <pre className="mt-2 max-h-48 overflow-auto rounded-xl border border-white/10 bg-black/40 p-3 text-xs text-gray-300">
{JSON.stringify(payload, null, 2)}
                </pre>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}

