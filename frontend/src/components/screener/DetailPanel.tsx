import { useEffect, useRef } from 'react';
import {
  X,
  TrendingUp,
  TrendingDown,
  Target,
  AlertTriangle,
  Play,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatPrice, formatPct, changePct } from '@/lib/format';
import { fetchDeepAnalysis } from '@/api/screener';
import type { TVScoredTicker, TVDeepAnalysisRequest } from '@/types/screener';
import { useQuery } from '@tanstack/react-query';

interface DetailPanelProps {
  ticker: TVScoredTicker | null;
  onClose: () => void;
}

const BREAKDOWN_FACTORS = [
  { key: 'trend', label: 'Trend', color: 'text-info' },
  { key: 'momentum', label: 'Momentum', color: 'text-accent' },
  { key: 'volume', label: 'Volume', color: 'text-warning' },
  { key: 'quality', label: 'Quality', color: 'text-purple-400' },
  { key: 'fundamental', label: 'Fundamental', color: 'text-cyan-400' },
];

function ScoreBar({
  score,
  label,
  color,
}: {
  score: number;
  label: string;
  color: string;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-text-secondary">{label}</span>
        <span className={cn('font-mono font-medium', color)}>
          {score.toFixed(1)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: `${Math.max(0, Math.min(100, score))}%`,
            backgroundColor:
              score >= 70 ? '#22C55E' : score >= 40 ? '#F59E0B' : '#EF4444',
          }}
        />
      </div>
    </div>
  );
}

function PriceLevel({
  label,
  value,
  color,
  icon,
}: {
  label: string;
  value: number;
  color: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border/50 bg-surface/50 p-3">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded border border-border bg-surface">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs uppercase tracking-wide text-text-muted">
          {label}
        </p>
        <p className={cn('font-mono text-price font-semibold', color)}>
          {formatPrice(value)}
        </p>
      </div>
    </div>
  );
}

export function DetailPanel({ ticker, onClose }: DetailPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Fetch deep analysis when ticker changes
  const {
    data: analysis,
    isLoading,
    error,
    refetch: refetchAnalysis,
  } = useQuery({
    queryKey: ['deep-analysis', ticker?.symbol],
    queryFn: async () => {
      if (!ticker) return null;
      const req: TVDeepAnalysisRequest = {
        symbol: ticker.symbol,
        timeframe: '1D',
        include_backtest: true,
        include_risk: true,
        tv_data: ticker.tv_data,
      };
      return fetchDeepAnalysis(req);
    },
    enabled: !!ticker,
    staleTime: 60_000,
  });

  // Animate in
  useEffect(() => {
    if (panelRef.current) {
      panelRef.current.style.transform = 'translateX(100%)';
      requestAnimationFrame(() => {
        if (panelRef.current) {
          panelRef.current.style.transform = 'translateX(0)';
        }
      });
    }
  }, [ticker]);

  // Animate out on close
  const handleClose = () => {
    if (panelRef.current) {
      panelRef.current.style.transform = 'translateX(100%)';
      setTimeout(onClose, 200);
    } else {
      onClose();
    }
  };

  if (!ticker) return null;

  const change = ticker.tv_data?.change ?? 0;
  const price = ticker.tv_data?.close ?? 0;
  const changePctVal = price !== change ? (changePct(price, change) ?? 0) : 0;
  const isGain = change >= 0;

  return (
    <div
      className="fixed inset-0 z-50 flex"
      onClick={handleClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="detail-panel-title"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-200"
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        ref={panelRef}
        className="relative flex w-full max-w-lg flex-col border-l border-border bg-surface shadow-xl transition-transform duration-200 ease-out"
        style={{ transform: 'translateX(0)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-3">
            <h2
              id="detail-panel-title"
              className="text-lg font-semibold text-text-primary"
            >
              {ticker.symbol}
            </h2>
            <span
              className={cn(
                'badge px-2 py-0.5 text-xs font-medium',
                isGain ? 'badge-green' : 'badge-red'
              )}
            >
              {formatPct(changePctVal)}
            </span>
          </div>
          <button
            onClick={handleClose}
            className="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
            aria-label="Close detail panel"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 space-y-6 overflow-y-auto p-4">
          {/* Price & Change */}
          <div className="flex items-center gap-4">
            <div className="font-mono text-3xl font-bold tabular-nums text-text-primary">
              {formatPrice(ticker.entry)}
            </div>
            <div
              className={cn(
                'flex items-center gap-2 font-mono text-price',
                isGain ? 'text-gain' : 'text-loss'
              )}
            >
              {isGain ? (
                <TrendingUp className="h-5 w-5" />
              ) : (
                <TrendingDown className="h-5 w-5" />
              )}
              <span>
                {isGain ? '+' : ''}
                {change.toFixed(2)} ({formatPct(changePctVal)})
              </span>
            </div>
          </div>

          {/* Score & Rating */}
          <div className="flex items-center gap-4 rounded-lg border border-border/50 bg-surface/50 p-4">
            <div className="flex flex-col items-center gap-1">
              <span className="font-mono text-3xl font-bold tabular-nums text-text-primary">
                {ticker.score.toFixed(1)}
              </span>
              <span className="text-xs text-text-muted">Confluence Score</span>
            </div>
            <div className="h-12 w-px bg-border" />
            <div className="flex flex-col items-center gap-1">
              <span
                className={cn(
                  'badge px-3 py-1 text-sm font-medium',
                  ticker.rating === 'A+'
                    ? 'badge-green'
                    : ticker.rating === 'A'
                      ? 'badge-green'
                      : ticker.rating === 'B+'
                        ? 'badge-neutral'
                        : ticker.rating === 'B'
                          ? 'badge-neutral'
                          : 'badge-red'
                )}
              >
                {ticker.rating}
              </span>
              <span className="text-xs text-text-muted">Rating</span>
            </div>
            <div className="h-12 w-px bg-border" />
            <div className="flex flex-col items-center gap-1">
              <span className="font-mono text-xl font-bold tabular-nums text-text-primary">
                {ticker.risk_reward.toFixed(2)}
              </span>
              <span className="text-xs text-text-muted">R:R</span>
            </div>
          </div>

          {/* Confluence Breakdown */}
          <div>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              Confluence Breakdown
            </h3>
            <div className="space-y-3">
              {BREAKDOWN_FACTORS.map((factor) => {
                const score = ticker.breakdown?.[factor.key] ?? 0;
                return (
                  <ScoreBar
                    key={factor.key}
                    score={score}
                    label={factor.label}
                    color={factor.color}
                  />
                );
              })}
            </div>
          </div>

          {/* Why This Score */}
          {ticker.rationale && ticker.rationale.length > 0 && (
            <div>
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
                Why This Score
              </h3>
              <ul className="space-y-1.5">
                {ticker.rationale.map((point, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-xs text-text-secondary"
                  >
                    <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-text-muted/30" />
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Entry / Stop / Targets */}
          <div>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              Trade Levels
            </h3>
            <div className="space-y-2">
              <PriceLevel
                label="Entry"
                value={ticker.entry}
                color="text-info"
                icon={<Target className="h-4 w-4 text-info" />}
              />
              <PriceLevel
                label="Stop Loss"
                value={ticker.stop_loss}
                color="text-loss"
                icon={<AlertTriangle className="h-4 w-4 text-loss" />}
              />
              {ticker.targets && ticker.targets.length > 0 && (
                <>
                  {ticker.targets.slice(0, 3).map((target, idx) => (
                    <PriceLevel
                      key={idx}
                      label={`Target ${idx + 1}`}
                      value={target}
                      color="text-accent"
                      icon={<Target className="h-4 w-4 text-accent" />}
                    />
                  ))}
                </>
              )}
            </div>
          </div>

          {/* Deep Analysis */}
          <div className="border-t border-border pt-4">
            <button
              onClick={() => refetchAnalysis()}
              disabled={isLoading}
              className="btn-primary w-full gap-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  <span>Deep Analysis</span>
                </>
              )}
            </button>

            {analysis && (
              <div className="mt-4 space-y-3 text-sm">
                {/* Show fund warning at screener level */}
                {ticker.probable_fund && (
                  <div className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-warning">
                    <strong>⚠️ Fund Detected:</strong>{' '}
                    {ticker.probable_fund_reason}
                  </div>
                )}
                {/* Show OHLCV-unavailable banner */}
                {analysis.has_ohlcv === false && (
                  <div className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-warning">
                    <strong>Limited Data:</strong> No historical OHLCV available
                    for {ticker.symbol}. Values estimated from TV screener data.
                  </div>
                )}

                <p className="text-text-secondary">
                  <strong>Confluence Score:</strong>{' '}
                  <span className="font-mono text-text-primary">
                    {analysis.confluence_score.toFixed(1)}
                  </span>
                </p>

                {analysis.has_ohlcv === false && analysis.tv_fallback && (
                  <>
                    <p className="text-text-secondary">
                      <strong>TV Rating:</strong>{' '}
                      <span className="font-mono text-text-primary">
                        {analysis.tv_fallback.rating}
                      </span>
                    </p>
                    <p className="text-text-secondary">
                      <strong>TV R:R:</strong>{' '}
                      <span className="font-mono text-text-primary">
                        {analysis.tv_fallback.risk_reward.toFixed(2)}
                      </span>
                    </p>
                  </>
                )}

                {analysis.backtest && (
                  <p className="text-text-secondary">
                    <strong>Backtest Win Rate:</strong>{' '}
                    <span className="font-mono text-text-primary">
                      {(analysis.backtest.win_rate as number)?.toFixed(1) ??
                        'N/A'}
                      %
                    </span>
                  </p>
                )}
                {analysis.risk && (
                  <p className="text-text-secondary">
                    <strong>Risk Score:</strong>{' '}
                    <span className="font-mono text-text-primary">
                      {(analysis.risk.score as number)?.toFixed(1) ?? 'N/A'}
                    </span>
                  </p>
                )}
              </div>
            )}

            {error && (
              <div className="mt-3 rounded-lg border border-loss/30 bg-loss-bg p-3 text-sm text-loss">
                Failed to load deep analysis. Click to retry.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
