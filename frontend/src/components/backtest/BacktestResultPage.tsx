import { useParams, Navigate } from 'react-router-dom';
import { BacktestResult } from './BacktestResult';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';

export function BacktestResultPage() {
  const { runId } = useParams<{ runId: string }>();

  if (!runId) {
    return <Navigate to="/backtest" replace />;
  }

  return (
    <ErrorBoundary>
      <BacktestResult runId={runId} />
    </ErrorBoundary>
  );
}
