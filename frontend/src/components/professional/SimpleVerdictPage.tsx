import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  ExternalLink,
  Plus,
} from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/cn';
import { fetchSimplifiedVerdict } from '@/api/professional';
import { useProModeStore } from '@/store/professional';
import { usePortfolioStore } from '@/store/portfolio';
import { EducationTooltip } from './EducationTooltip';

const VERDICT_COLORS: Record<string, string> = {
  STRONG_BUY: 'bg-green-500/15 text-green-400 border-green-500/30',
  BUY: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  WATCH: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  AVOID: 'bg-red-500/15 text-red-400 border-red-500/30',
};

function MetricRow({
  label,
  value,
  metricKey,
}: {
  label: string;
  value: string;
  metricKey: string;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border/30 py-1.5 last:border-0">
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-text-muted">{label}</span>
        <EducationTooltip metricKey={metricKey} metricLabel={label} compact />
      </div>
      <span className="font-mono text-xs font-medium text-text-primary">
        {value}
      </span>
    </div>
  );
}

export function SimpleVerdictPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const [showDetails, setShowDetails] = useState(false);
  const addNotification = useProModeStore((s) => s.addNotification);
  const addToPortfolio = usePortfolioStore((s) => s.addSymbol);

  const {
    data: verdict,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['verdict', symbol],
    queryFn: () => fetchSimplifiedVerdict(symbol!),
    enabled: !!symbol,
    staleTime: 60_000,
  });

  const handleAddToWatchlist = () => {
    if (!symbol) return;
    addToPortfolio(symbol);
    addNotification({
      type: 'target_hit',
      symbol,
      title: 'Added to Watchlist',
      message: `${symbol} added to your watchlist from One-Click Verdict`,
      read: false,
    });
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl animate-pulse space-y-4 p-6">
        <div className="h-6 w-24 rounded bg-surface-tertiary" />
        <div className="h-16 w-64 rounded bg-surface-tertiary" />
        <div className="h-48 w-full rounded bg-surface-tertiary" />
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6 text-center">
          <AlertCircle className="mx-auto mb-2 h-8 w-8 text-red-400" />
          <h3 className="mb-1 text-lg font-semibold text-text-primary">
            Could not analyze {symbol}
          </h3>
          <p className="mb-4 text-sm text-text-muted">
            Analysis may be unavailable for this ticker. Try again or pick
            another.
          </p>
          <div className="flex justify-center gap-2">
            <button
              onClick={() => refetch()}
              className="rounded-lg bg-accent/10 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/20"
            >
              Retry
            </button>
            <button
              onClick={() => navigate('/pro')}
              className="rounded-lg border border-border px-4 py-2 text-sm text-text-muted transition-colors hover:text-text-primary"
            >
              Back to Brief
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!verdict) return null;

  const verdictColor = VERDICT_COLORS[verdict.action] || VERDICT_COLORS.WATCH;

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      {/* Back button */}
      <button
        onClick={() => navigate('/pro')}
        className="inline-flex items-center gap-1 text-xs text-text-muted transition-colors hover:text-accent"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to Morning Brief
      </button>

      {/* Verdict header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <h1 className="font-display text-2xl font-semibold tracking-tight text-text-primary">
              {verdict.symbol}
            </h1>
            <span
              data-testid="verdict-badge"
              className={cn(
                'rounded-full border px-3 py-1 text-sm font-bold',
                verdictColor
              )}
            >
              {verdict.action}
            </span>
          </div>
          <p className="text-sm text-text-muted">{verdict.verdictSummary}</p>
        </div>
        <div data-testid="conviction-score" className="text-right">
          <div className="text-2xl font-bold text-text-primary">
            {verdict.conviction}/10
          </div>
          <div className="text-2xs text-text-muted">
            Conviction
            <EducationTooltip
              metricKey="rsi"
              metricLabel="Conviction Score"
              compact
            />
          </div>
        </div>
      </div>

      {/* Key metrics */}
      <div className="bg-surface-secondary rounded-lg border border-border p-4">
        <h3 className="mb-3 text-sm font-semibold text-text-primary">
          Key Metrics
        </h3>
        <div className="grid grid-cols-2 gap-x-6">
          {Object.entries(verdict.keyMetrics)
            .slice(0, 8)
            .map(([key, value]) => (
              <MetricRow
                key={key}
                label={key
                  .replace(/_/g, ' ')
                  .replace(/\b\w/g, (l) => l.toUpperCase())}
                value={
                  typeof value === 'number'
                    ? value > 1000
                      ? `$${(value / 1e9).toFixed(1)}B`
                      : value.toFixed(2)
                    : String(value)
                }
                metricKey={key}
              />
            ))}
        </div>
      </div>

      {/* Entry / Stop / Targets */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-surface-secondary rounded-lg border border-border p-3 text-center">
          <span className="mb-1 block text-xs text-text-muted">Entry Zone</span>
          <span className="font-mono text-lg font-bold text-text-primary">
            ${verdict.entryZone}
          </span>
        </div>
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-center">
          <span className="mb-1 block text-xs text-text-muted">Stop Loss</span>
          <span className="font-mono text-lg font-bold text-red-400">
            ${verdict.stopLoss.toFixed(2)}
          </span>
          <EducationTooltip metricKey="rsi" metricLabel="Stop Loss" compact />
        </div>
        <div className="rounded-lg border border-green-500/20 bg-green-500/5 p-3 text-center">
          <span className="mb-1 block text-xs text-text-muted">Target</span>
          <span className="font-mono text-lg font-bold text-green-400">
            ${verdict.targets[0]?.toFixed(2) || '--'}
            {verdict.targets.length > 1 && '+'}
          </span>
        </div>
      </div>

      {/* Position size */}
      {verdict.positionSize && (
        <div
          data-testid="position-size"
          className="rounded-lg border border-accent/20 bg-accent/5 p-4"
        >
          <div className="mb-2 flex items-center gap-2">
            <h3 className="text-sm font-semibold text-text-primary">
              Position Size
            </h3>
            <EducationTooltip metricKey="position-sizing" compact />
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <span className="text-2xs block text-text-muted">Shares</span>
              <span className="font-mono text-lg font-bold text-text-primary">
                {verdict.positionSize.shares.toLocaleString()}
              </span>
            </div>
            <div>
              <span className="text-2xs block text-text-muted">Amount</span>
              <span className="font-mono text-lg font-bold text-text-primary">
                ${verdict.positionSize.amount.toLocaleString()}
              </span>
            </div>
            <div>
              <span className="text-2xs block text-text-muted">Risk</span>
              <span className="font-mono text-lg font-bold text-text-primary">
                {verdict.positionSize.riskPct.toFixed(1)}%
              </span>
            </div>
          </div>
          <p className="text-2xs mt-2 text-center text-text-muted">
            Capped by: {verdict.positionSize.cappedBy}
          </p>
        </div>
      )}

      {/* Max hold days — shows when trade plan has a time stop */}
      {verdict.maxHoldDays && (
        <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-4 py-2 text-center">
          <span className="mb-0.5 block text-xs text-text-muted">Max Hold</span>
          <span className="text-sm font-semibold text-yellow-400">
            {verdict.maxHoldDays} days
          </span>
          <span className="text-2xs ml-2 text-text-muted">
            re-evaluate at expiry
          </span>
        </div>
      )}

      {/* Show Details expander */}
      <div className="overflow-hidden rounded-lg border border-border">
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="bg-surface-secondary/50 hover:bg-surface-secondary flex w-full items-center justify-between px-4 py-3 transition-colors"
        >
          <span className="text-sm font-semibold text-text-primary">
            Show Details
          </span>
          {showDetails ? (
            <ChevronDown className="h-4 w-4 text-text-muted" />
          ) : (
            <ChevronRight className="h-4 w-4 text-text-muted" />
          )}
        </button>
        {showDetails && (
          <div className="space-y-4 border-t border-border px-4 py-3">
            <p className="text-xs text-text-muted">
              Detailed analysis available on the full Ticker Analysis page.
            </p>
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex gap-3">
        <button
          onClick={handleAddToWatchlist}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-accent-light"
        >
          <Plus className="h-4 w-4" />
          Add to Watchlist
        </button>
        <button
          onClick={() => navigate(`/ticker/${symbol}`)}
          className="flex items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm text-text-muted transition-colors hover:border-accent/30 hover:text-accent"
        >
          <ExternalLink className="h-4 w-4" />
          Deep Analysis →
        </button>
      </div>
    </div>
  );
}
