type Props = {
  title: string
}

export function PlaceholderPage({ title }: Props) {
  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-8">
      <div className="page-header mb-1">{title}</div>
      <div className="page-subheader mb-6">Coming soon.</div>
      <div className="glass p-8 text-sm text-gray-500">
        This section is under construction.
      </div>
    </div>
  )
}
