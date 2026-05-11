type Props = {
  className?: string
}

export function Skeleton({ className }: Props) {
  return (
    <div
      className={[
        'animate-pulse rounded-xl border border-white/5 bg-white/[0.04]',
        className ?? '',
      ].join(' ')}
    />
  )
}

