'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import dynamic from 'next/dynamic'
import { useState } from 'react'
import { Toaster } from 'react-hot-toast'

const App = dynamic(() => import('./App'), { ssr: false })

export function NextClientApp() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
            staleTime: 15_000,
          },
        },
      }),
  )

  return (
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'rgba(17,17,17,0.9)',
            color: 'rgba(229,231,235,0.95)',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: '14px',
            backdropFilter: 'blur(10px)',
          },
        }}
      />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
