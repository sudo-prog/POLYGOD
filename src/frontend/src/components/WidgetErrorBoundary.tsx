import { ErrorBoundary, FallbackProps } from 'react-error-boundary';

function WidgetError({ error, resetErrorBoundary }: FallbackProps) {
  const errorMessage = error instanceof Error ? error.message : String(error);
  return (
    <div
      style={{
        padding: 16,
        border: '1px solid var(--pg-red)',
        borderRadius: 12,
        color: 'var(--pg-red)',
      }}
    >
      <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>WIDGET ERROR — {errorMessage}</p>
      <button
        onClick={resetErrorBoundary}
        style={{ marginTop: 8, fontFamily: 'var(--font-mono)', fontSize: 10 }}
      >
        RETRY
      </button>
    </div>
  );
}

export function WidgetErrorBoundary({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary FallbackComponent={WidgetError} onReset={() => window.location.reload()}>
      {children}
    </ErrorBoundary>
  );
}
