import { useCallback, useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { Modal } from '../components/Modal'
import { Skeleton } from '../components/Skeleton'
import { isValidEvmAddress, shortenAddress } from '../lib/address'
import type { ChainId } from '../lib/chains'
import { CHAINS, getChainMeta } from '../lib/chains'
import {
  addToWatchlist,
  fetchWatchlist,
  removeWatchlistItem,
  updateWatchlistItem,
} from '../lib/endpoints'
import type { WatchlistItem } from '../types/api'

export function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)

  const [address, setAddress] = useState('')
  const [chain, setChain] = useState<ChainId>('ethereum')
  const [name, setName] = useState('')
  const [category, setCategory] = useState('scam')
  const [source, setSource] = useState('internal_watchlist')
  const [confidence, setConfidence] = useState(80)
  const [reviewerNotes, setReviewerNotes] = useState('')
  const [bulk, setBulk] = useState('')
  const [editOpen, setEditOpen] = useState(false)
  const [editing, setEditing] = useState<WatchlistItem | null>(null)
  const [editName, setEditName] = useState('')
  const [editCategory, setEditCategory] = useState('scam')
  const [editSource, setEditSource] = useState('')
  const [editConfidence, setEditConfidence] = useState(80)
  const [editReviewerNotes, setEditReviewerNotes] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchWatchlist()
      setItems(data)
    } catch {
      toast.error('Failed to load watchlist')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const onAddSingle = useCallback(async () => {
    const a = address.trim()
    if (!isValidEvmAddress(a)) {
      toast.error('Invalid address')
      return
    }
    try {
      const created = await addToWatchlist({
        address: a,
        chain,
        name: name.trim() || undefined,
        category,
        source: source.trim() || undefined,
        confidence,
        reviewerNotes: reviewerNotes.trim() || undefined,
      })
      setItems((prev) => [created, ...prev])
      toast.success('Added to watchlist')
      setAddress('')
      setName('')
      setReviewerNotes('')
      setOpen(false)
    } catch {
      toast.error('Failed to add watchlist item')
    }
  }, [address, chain, name, category, source, confidence, reviewerNotes])

  const bulkAddresses = useMemo(() => {
    return bulk
      .split('\n')
      .map((x) => x.trim())
      .filter(Boolean)
  }, [bulk])

  const onBulkImport = useCallback(async () => {
    if (bulkAddresses.length === 0) {
      toast.error('Paste at least one address')
      return
    }
    const invalid = bulkAddresses.filter((a) => !isValidEvmAddress(a))
    if (invalid.length > 0) {
      toast.error(`Invalid addresses: ${invalid.slice(0, 3).join(', ')}${invalid.length > 3 ? '…' : ''}`)
      return
    }

    const t = toast.loading('Importing…')
    try {
      const created: WatchlistItem[] = []
      for (const a of bulkAddresses) {
        const item = await addToWatchlist({ address: a, chain })
        created.push(item)
      }
      setItems((prev) => [...created.reverse(), ...prev])
      toast.success(`Imported ${created.length} addresses`, { id: t })
      setBulk('')
      setOpen(false)
    } catch {
      toast.error('Bulk import failed', { id: t })
    }
  }, [bulkAddresses, chain])

  const onToggleAlerts = useCallback(async (item: WatchlistItem) => {
    const next = !item.alerts_enabled
    try {
      const updated = await updateWatchlistItem(item.id, { alerts_enabled: next })
      setItems((prev) => prev.map((x) => (x.id === item.id ? updated : x)))
      toast.success(next ? 'Alerts enabled' : 'Alerts disabled')
    } catch {
      toast.error('Failed to update')
    }
  }, [])

  const onRemove = useCallback(async (item: WatchlistItem) => {
    const t = toast.loading('Removing…')
    try {
      await removeWatchlistItem(item.id)
      setItems((prev) => prev.filter((x) => x.id !== item.id))
      toast.success('Removed', { id: t })
    } catch {
      toast.error('Failed to remove', { id: t })
    }
  }, [])

  const onOpenEdit = useCallback((item: WatchlistItem) => {
    setEditing(item)
    setEditName(item.name ?? '')
    setEditCategory(item.category ?? 'scam')
    setEditSource(item.source ?? '')
    setEditConfidence(Math.max(0, Math.min(100, Number(item.confidence ?? 80))))
    setEditReviewerNotes(item.reviewerNotes ?? '')
    setEditOpen(true)
  }, [])

  const onSaveEdit = useCallback(async () => {
    if (!editing) return
    try {
      const updated = await updateWatchlistItem(editing.id, {
        name: editName.trim() || undefined,
        category: editCategory,
        source: editSource.trim() || undefined,
        confidence: editConfidence,
        reviewerNotes: editReviewerNotes.trim() || undefined,
      })
      setItems((prev) => prev.map((x) => (x.id === editing.id ? updated : x)))
      setEditOpen(false)
      setEditing(null)
      toast.success('Watchlist entry updated')
    } catch {
      toast.error('Failed to update watchlist entry')
    }
  }, [editing, editName, editCategory, editSource, editConfidence, editReviewerNotes])

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="page-header">Watchlist</div>
            <div className="page-subheader">Monitor addresses and receive alerts</div>
          </div>
          <button type="button" className="btn-primary" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" />
            Add / Import
          </button>
        </div>

        <div className="glass w-full overflow-hidden">
          <div className="w-full overflow-x-auto">
            <table className="min-w-[980px] w-full text-left text-sm">
              <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-gray-400">
                <tr>
                  <th className="px-4 py-3">Address</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Chain</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Confidence</th>
                  <th className="px-4 py-3">Risk Score</th>
                  <th className="px-4 py-3">Last Activity</th>
                  <th className="px-4 py-3">Alert Toggle</th>
                  <th className="px-4 py-3">Remove</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {loading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 10 }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-4 w-32" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : items.length === 0 ? (
                  <tr>
                    <td className="px-4 py-10 text-center text-sm text-gray-400" colSpan={10}>
                      No watchlist items yet.
                    </td>
                  </tr>
                ) : (
                  items.map((item) => (
                    <tr key={item.id} className="hover:bg-white/[0.02]">
                      <td className="px-4 py-3 font-mono text-xs text-gray-200">
                        {shortenAddress(item.address, 12, 8)}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          className="inline-flex items-center gap-2 text-gray-200 hover:text-white"
                          onClick={() => onOpenEdit(item)}
                        >
                          {item.name?.trim() ? item.name : <span className="text-gray-500">Unnamed</span>}
                          <Pencil className="h-3.5 w-3.5 text-gray-500" />
                        </button>
                      </td>
                      <td className="px-4 py-3 text-gray-300">
                        {getChainMeta(item.chain as ChainId).name}
                      </td>
                      <td className="px-4 py-3 text-gray-300">{item.category ?? '—'}</td>
                      <td className="px-4 py-3 text-gray-300">{item.source ?? '—'}</td>
                      <td className="px-4 py-3 text-gray-300">
                        {typeof item.confidence === 'number' ? `${item.confidence}%` : '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-200">
                        {typeof item.riskScore === 'number' ? item.riskScore : '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-300">
                        {item.lastActivity ? new Date(item.lastActivity).toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          className={[
                            'rounded-full border px-3 py-1 text-xs transition',
                            item.alerts_enabled
                              ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200'
                              : 'border-white/10 bg-white/[0.03] text-gray-300 hover:bg-white/[0.06] hover:text-white',
                          ].join(' ')}
                          onClick={() => onToggleAlerts(item)}
                        >
                          {item.alerts_enabled ? 'Enabled' : 'Disabled'}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          className="inline-flex items-center gap-2 rounded-xl border border-rose-400/20 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-200 transition hover:bg-rose-500/15"
                          onClick={() => onRemove(item)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <Modal title="Add to Watchlist" open={open} onClose={() => setOpen(false)}>
        <div className="grid gap-4">
          <div className="grid gap-2">
            <label className="text-xs font-medium text-gray-400">Chain</label>
            <select
              value={chain}
              onChange={(e) => setChain(e.target.value as ChainId)}
              className="h-10 rounded-xl border border-white/10 bg-white/[0.03] px-3 text-sm text-gray-100 outline-none transition focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
            >
              {CHAINS.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.symbol}) • {c.type}
                </option>
              ))}
            </select>
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-medium text-gray-400">Address</label>
            <input value={address} onChange={(e) => setAddress(e.target.value)} className="input" placeholder="0x…" />
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-medium text-gray-400">Custom name (optional)</label>
            <input value={name} onChange={(e) => setName(e.target.value)} className="input" placeholder="e.g. Treasury" />
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="h-10 rounded-xl border border-white/10 bg-white/[0.03] px-3 text-sm text-gray-100 outline-none transition focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
              >
                <option value="scam">scam</option>
                <option value="phishing">phishing</option>
                <option value="mixer">mixer</option>
                <option value="stolen-funds">stolen-funds</option>
                <option value="darknet">darknet</option>
              </select>
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">Confidence (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                value={confidence}
                onChange={(e) => setConfidence(Number(e.target.value))}
                className="input"
              />
            </div>
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-medium text-gray-400">Source</label>
            <input value={source} onChange={(e) => setSource(e.target.value)} className="input" placeholder="Etherscan / Internal DB / Analyst" />
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-medium text-gray-400">Reviewer notes</label>
            <textarea
              value={reviewerNotes}
              onChange={(e) => setReviewerNotes(e.target.value)}
              className="mt-1 w-full rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm text-gray-100 outline-none transition focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
              rows={3}
              placeholder="Analyst notes..."
            />
          </div>

          <div className="flex justify-end gap-2">
            <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="button" className="btn-primary" onClick={onAddSingle}>
              Add
            </button>
          </div>

          <div className="border-t border-white/10 pt-4">
            <div className="text-sm font-semibold text-gray-100">Bulk import</div>
            <div className="mt-1 text-xs text-gray-400">One address per line.</div>
            <textarea
              value={bulk}
              onChange={(e) => setBulk(e.target.value)}
              className="mt-3 w-full rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm text-gray-100 outline-none transition focus:border-violet-400/60 focus:ring-2 focus:ring-violet-400/20"
              rows={5}
              placeholder="0xabc...\n0xdef...\n0x123..."
            />
            <div className="mt-3 flex justify-end">
              <button type="button" className="btn-primary" onClick={onBulkImport}>
                Import
              </button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal title="Edit watchlist entry" open={editOpen} onClose={() => setEditOpen(false)}>
        <div className="grid gap-3">
          <div className="grid gap-2">
            <label className="text-xs font-medium text-gray-400">Name</label>
            <input value={editName} onChange={(e) => setEditName(e.target.value)} className="input" />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">Category</label>
              <select value={editCategory} onChange={(e) => setEditCategory(e.target.value)} className="h-10 rounded-xl border border-white/10 bg-white/[0.03] px-3 text-sm text-gray-100">
                <option value="scam">scam</option>
                <option value="phishing">phishing</option>
                <option value="mixer">mixer</option>
                <option value="stolen-funds">stolen-funds</option>
                <option value="darknet">darknet</option>
              </select>
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-medium text-gray-400">Confidence (%)</label>
              <input type="number" min={0} max={100} value={editConfidence} onChange={(e) => setEditConfidence(Number(e.target.value))} className="input" />
            </div>
          </div>
          <div className="grid gap-2">
            <label className="text-xs font-medium text-gray-400">Source</label>
            <input value={editSource} onChange={(e) => setEditSource(e.target.value)} className="input" />
          </div>
          <div className="grid gap-2">
            <label className="text-xs font-medium text-gray-400">Reviewer notes</label>
            <textarea value={editReviewerNotes} onChange={(e) => setEditReviewerNotes(e.target.value)} className="w-full rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm text-gray-100" rows={4} />
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-ghost" onClick={() => setEditOpen(false)}>Cancel</button>
            <button type="button" className="btn-primary" onClick={onSaveEdit}>Save</button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

