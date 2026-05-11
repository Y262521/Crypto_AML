import type { ReactNode } from 'react'
import { X } from 'lucide-react'

type Props = {
  title: string
  open: boolean
  onClose: () => void
  children: ReactNode
}

export function Modal({ title, open, onClose, children }: Props) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="glass w-full max-w-xl overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/10 p-4">
            <div className="text-sm font-semibold text-gray-100">{title}</div>
            <button type="button" className="btn-ghost" onClick={onClose} aria-label="Close modal">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="p-4">{children}</div>
        </div>
      </div>
    </div>
  )
}

