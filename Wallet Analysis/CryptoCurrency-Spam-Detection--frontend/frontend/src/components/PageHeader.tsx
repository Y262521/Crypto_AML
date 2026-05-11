import type { ReactNode } from 'react'

type Props = {
  title: string
  subtitle?: string
  actions?: ReactNode
}

export function PageHeader({ title, subtitle, actions }: Props) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between mb-6">
      <div>
        <h1 className="page-header">{title}</h1>
        {subtitle && <p className="page-subheader">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2 mt-2 sm:mt-0">{actions}</div>}
    </div>
  )
}
