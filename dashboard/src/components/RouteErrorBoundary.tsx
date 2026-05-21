import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface Props {
  /** Bumping this key (e.g. with the current pathname) resets the boundary. */
  resetKey: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Catches render-time errors in a route subtree and shows a recovery message
 * instead of leaving the React tree wedged (which is what makes the browser
 * back button appear broken — the previous Suspense never re-mounts).
 * The boundary auto-resets when `resetKey` changes (per route navigation).
 */
export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Route error:', error, info);
  }

  componentDidUpdate(prevProps: Props) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <main className="min-h-screen bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">
          <div className="mx-auto max-w-2xl px-6 py-20">
            <h1 className="mb-4 font-mono text-xs uppercase tracking-wider text-trace-down">
              This page errored
            </h1>
            <p className="mb-6 text-base text-signal-white/70">
              Something broke while rendering this view. The console has the details.
            </p>
            <pre className="mb-6 overflow-x-auto rounded-sm border border-signal-white/10 bg-rack-black/60 p-4 font-mono text-xs text-signal-white/60">
              {this.state.error.message}
            </pre>
            <Link
              to="/"
              className="inline-block rounded-sm border border-signal-white/20 px-4 py-2 font-mono text-xs uppercase tracking-wider text-signal-white/80 transition-colors hover:border-signal-white/40 hover:text-signal-white"
            >
              Back to console
            </Link>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}
