import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Notice } from './Notice'

interface ErrorBoundaryProps {
  /** What was being drawn, for the message shown to the user. */
  label: string
  children: ReactNode
}

interface ErrorBoundaryState {
  failed: boolean
}

/** Keeps one broken panel (for example the map chunk failing to load) from blanking the app. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { failed: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`${this.props.label} failed to render`, error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="boundary">
        <Notice
          tone="error"
          action={
            <button type="button" className="button button--quiet" onClick={() => window.location.reload()}>
              Reload
            </button>
          }
        >
          The {this.props.label} could not be shown. Reload the page to try again.
        </Notice>
      </div>
    )
  }
}
