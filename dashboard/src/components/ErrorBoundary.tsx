import React from 'react';
import { AlertTriangle, RefreshCw, Orbit } from 'lucide-react';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  errorMessage: string;
  errorStack: string;
}

/**
 * Global error boundary — wraps the entire <App />.
 * On any uncaught React render exception, renders a friendly fallback
 * instead of a blank white page or raw browser error.
 */
export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, errorMessage: '', errorStack: '' };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      errorMessage: error?.message ?? 'An unknown error occurred.',
      errorStack: error?.stack ?? '',
    };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log to console for debugging — no user-visible console noise
    console.error('[ErrorBoundary] Uncaught render error:', error, info.componentStack);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    this.setState({ hasError: false, errorMessage: '', errorStack: '' });
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="min-h-screen bg-[#030712] text-slate-100 flex items-center justify-center p-6">
        <div className="max-w-lg w-full text-center space-y-8">
          {/* Icon */}
          <div className="relative mx-auto w-24 h-24">
            <div className="absolute inset-0 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
              <AlertTriangle className="h-10 w-10 text-rose-400" />
            </div>
            <div className="absolute -top-1 -right-1">
              <Orbit className="h-6 w-6 text-rose-400/40 animate-spin" style={{ animationDuration: '4s' }} />
            </div>
          </div>

          {/* Heading */}
          <div className="space-y-2">
            <h1 className="text-2xl font-black tracking-widest uppercase text-slate-100">
              Something Went Wrong
            </h1>
            <p className="text-sm text-slate-400 max-w-sm mx-auto leading-relaxed">
              The dashboard encountered an unexpected error and could not render. 
              Your data is safe — try reloading the page to recover.
            </p>
          </div>

          {/* Error detail (collapsed, monospace) */}
          {this.state.errorMessage && (
            <div className="text-left bg-[#0b0f1e]/80 border border-rose-500/20 rounded-lg p-4 space-y-1">
              <span className="text-[10px] font-semibold text-rose-400 uppercase tracking-wider font-mono block">
                Error Details
              </span>
              <p className="text-xs text-rose-300/80 font-mono break-all leading-relaxed">
                {this.state.errorMessage}
              </p>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={this.handleReload}
              className="flex items-center justify-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-all active:scale-95 shadow-lg shadow-indigo-500/20"
            >
              <RefreshCw className="h-4 w-4" />
              Reload Dashboard
            </button>
            <button
              onClick={this.handleReset}
              className="flex items-center justify-center gap-2 px-6 py-3 bg-transparent border border-slate-700 hover:border-slate-500 text-slate-300 hover:text-slate-100 text-sm font-medium rounded-lg transition-all"
            >
              Try to Recover
            </button>
          </div>

          {/* Footer note */}
          <p className="text-[10px] text-slate-600 font-mono">
            TESS Transit Detection Pipeline Dashboard — Uncaught exception in React render tree
          </p>
        </div>
      </div>
    );
  }
}
