import type { ReactNode } from 'react'
import { Component } from 'react'
import { RefreshCcw, TriangleAlert } from 'lucide-react'

type Props = {
  children: ReactNode
}

type State = {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error) {
    // Keep minimal: allow console for debugging in dev
    // eslint-disable-next-line no-console
    console.error(error)
  }

  private retry = () => {
    this.setState({ hasError: false, error: undefined })
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="mx-auto flex min-h-[60vh] w-full max-w-3xl items-center justify-center px-4">
        <div className="glass w-full p-6 text-left">
          <div className="flex items-start gap-4">
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
              <TriangleAlert className="h-6 w-6 text-rose-300" />
            </div>
            <div className="flex-1">
              <div className="text-lg font-semibold text-gray-100">Something went wrong</div>
              <div className="mt-1 text-sm text-gray-400">
                Please try again. If this keeps happening, check your API connection and refresh.
              </div>
              <div className="mt-5 flex flex-wrap gap-3">
                <button type="button" className="btn-primary" onClick={this.retry}>
                  <RefreshCcw className="h-4 w-4" />
                  Retry
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => window.location.reload()}
                >
                  Reload page
                </button>
              </div>
              {this.state.error?.message ? (
                <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-gray-400">
                  {this.state.error.message}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    )
  }
}

