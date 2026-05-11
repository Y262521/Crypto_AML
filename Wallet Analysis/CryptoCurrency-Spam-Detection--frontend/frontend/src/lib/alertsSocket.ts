import type { AlertItem } from '../types/api'

export type AlertsSocketOptions = {
  url: string
  onAlert: (a: AlertItem) => void
  onStatus?: (s: 'connecting' | 'open' | 'closed' | 'error') => void
}

// API-ready websocket listener (expects JSON AlertItem messages)
export function connectAlertsSocket(opts: AlertsSocketOptions) {
  let ws: WebSocket | null = null
  let timeout: any = null
  let isClosed = false
  let hasLoggedConnectionError = false

  function connect() {
    if (isClosed) return
    
    ws = new WebSocket(opts.url)
    opts.onStatus?.('connecting')

    ws.addEventListener('open', () => {
      console.log('WebSocket connected to', opts.url)
      hasLoggedConnectionError = false
      opts.onStatus?.('open')
    })

    ws.addEventListener('close', () => {
      opts.onStatus?.('closed')
      if (!isClosed) {
        // Retry connection after 3 seconds
        timeout = setTimeout(connect, 3000)
      }
    })

    ws.addEventListener('error', (err) => {
      // Only log errors if we aren't intentionally closing the connection
      if (!isClosed) {
        // Browser WebSocket error events rarely contain actionable detail.
        // Log once per reconnect cycle to avoid noisy console spam.
        if (!hasLoggedConnectionError) {
          console.warn('WebSocket connection issue, retrying...', opts.url)
          hasLoggedConnectionError = true
        }
        opts.onStatus?.('error')
      }
    })

    ws.addEventListener('message', (ev) => {
      if (isClosed) return
      try {
        const data = JSON.parse(String(ev.data)) as AlertItem
        if (data && typeof data.id === 'string') opts.onAlert(data)
      } catch {
        // ignore malformed messages
      }
    })
  }

  // Small delay to allow React StrictMode cleanup to run if it's a double-mount
  timeout = setTimeout(connect, 50)

  return () => {
    isClosed = true
    if (timeout) clearTimeout(timeout)
    if (ws) {
      // Only close if it's actually open or connecting
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close()
      }
    }
  }
}

