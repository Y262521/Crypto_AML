import '../index.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Wallet Analysis',
  description: 'Wallet Analysis — Blockchain Intelligence Platform',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
