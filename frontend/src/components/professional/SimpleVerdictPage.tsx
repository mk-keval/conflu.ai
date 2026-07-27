import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ChevronDown, ChevronRight, AlertCircle, ExternalLink, Plus } from 'lucide-react';
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

function MetricRow({ label, value, metricKey }: { label: string; value: string; metricKey: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-text-muted">{label}</span>
        <EducationTooltip metricKey={metricKey} metricLabel={label} compact />
      </div>
      <span className="text-xs font-mono font-medium text-text-primary">{value}</span>
    </div>
  );
}

export function SimpleVerdictPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const [showDetails, setShowDetails] = useState(false);
  const addNotification = useProModeStore((s) => s.addNotification);
  const addToPortfolio = usePortfolioStore((s) => s.addSymbol);

  const { data: verdict, isLoading, isError, refetch } = useQuery({
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
      <div className="p-6 max-w-3xl mx-auto animate-pulse space-y-4">
        <div className="h-6 w-24 bg-surface-tertiary rounded" />
        <div className="h-16 w-64 bg-surface-tertiary rounded" />
        <div className="h-48 w-full bg-surface-tertiary rounded" />
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6 text-center">
          <AlertCircle className="h-8 w-8 text-red-400 mx-auto mb-2" />
          <h3 className="text-lg font-semibold text-text-primary mb-1">
            Could not analyze {symbol}
          </h3>
          <p className="text-sm text-text-muted mb-4">
            Analysis may be unavailable for this ticker. Try again or pick another.
          </p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => refetch()}
              className="px-4 py-2 rounded-lg bg-accent/10 text-accent text-sm font-medium hover:bg-accent/20 transition-colors"
            >
              Retry
            </button>
            <button
              onClick={() => navigate('/pro')}
              className="px-4 py-2 rounded-lg border border-border text-text-muted text-sm hover:text-text-primary transition-colors"
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
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      {/* Back button */}
      <button
        onClick={() => navigate('/pro')}
        className="inline-flex items-center gap-1 text-xs text-text-muted hover:text-accent transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to Morning Brief
      </button>

      {/* Verdict header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-bold text-text-primary">{verdict.symbol}</h1>
            <span
              data-testid="verdict-badge"
              className={cn(
                'px-3 py-1 rounded-full border text-sm font-bold',
                verdictColor
              )}
            >
              {verdict.action}
            </span>
          </div>
          <p className="text-sm text-text-muted">{verdict.verdictSummary}</p>
        </div>
        <div
          data-testid="conviction-score"
          className="text-right"
        >
          <div className="text-2xl font-bold text-text-primary">{verdict.conviction}/10</div>
          <div className="text-2xs text-text-muted">
            Conviction
            <EducationTooltip metricKey="rsi" metricLabel="Conviction Score" compact />
          </div>
        </div>
      </div>

      {/* Key metrics */}
      <div className="rounded-lg border border-border bg-surface-secondary p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3">Key Metrics</h3>
        <div className="grid grid-cols-2 gap-x-6">
          {Object.entries(verdict.keyMetrics).slice(0, 8).map(([key, value]) => (
            <MetricRow
              key={key}
              label={key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
              value={typeof value === 'number'
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
        <div className="rounded-lg border border-border bg-surface-secondary p-3 text-center">
          <span className="text-xs text-text-muted block mb-1">Entry Zone</span>
          <span className="text-lg font-mono font-bold text-text-primary">
            ${verdict.entryZone}
          </span>
        </div>
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-center">
          <span className="text-xs text-text-muted block mb-1">Stop Loss</span>
          <span className="text-lg font-mono font-bold text-red-400">
            ${verdict.stopLoss.toFixed(2)}
          </span>
          <EducationTooltip metricKey="rsi" metricLabel="Stop Loss" compact />
        </div>
        <div className="rounded-lg border border-green-500/20 bg-green-500/5 p-3 text-center">
          <span className="text-xs text-text-muted block mb-1">Target</span>
          <span className="text-lg font-mono font-bold text-green-400">
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
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-sm font-semibold text-text-primary">Position Size</h3>
            <EducationTooltip metricKey="position-sizing" compact />
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <span className="text-2xs text-text-muted block">Shares</span>
              <span className="text-lg font-mono font-bold text-text-primary">
                {verdict.positionSize.shares.toLocaleString()}
              </span>
            </div>
            <div>
              <span className="text-2xs text-text-muted block">Amount</span>
              <span className="text-lg font-mono font-bold text-text-primary">
                ${verdict.positionSize.amount.toLocaleString()}
              </span>
            </div>
            <div>
              <span className="text-2xs text-text-muted block">Risk</span>
              <span className="text-lg font-mono font-bold text-text-primary">
                {verdict.positionSize.riskPct.toFixed(1)}%
              </span>
            </div>
          </div>
          <p className="text-2xs text-text-muted text-center mt-2">
            Capped by: {verdict.positionSize.cappedBy}
          </p>
        </div>
      )}

      {/* Show Details expander */}
      <div className="rounded-lg border border-border overflow-hidden">
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="flex items-center justify-between w-full px-4 py-3 bg-surface-secondary/50 hover:bg-surface-secondary transition-colors"
        >
          <span className="text-sm font-semibold text-text-primary">Show Details</span>
          {showDetails ? <ChevronDown className="h-4 w-4 text-text-muted" /> : <ChevronRight className="h-4 w-4 text-text-muted" />}
        </button>
        {showDetails && (
          <div className="px-4 py-3 border-t border-border space-y-4">
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
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-accent text-white text-sm font-semibold hover:bg-accent-light transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add to Watchlist
        </button>
        <button
          onClick={() => navigate(`/ticker/${symbol}`)}
          className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-border text-text-muted text-sm hover:text-accent hover:border-accent/30 transition-colors"
        >
          <ExternalLink className="h-4 w-4" />
          Deep Analysis →
        </button>
      </div>
    </div>
  );
}
