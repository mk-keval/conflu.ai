import { useNavigate } from 'react-router-dom';
import { TrendingUp, TrendingDown, Minus, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatPct } from '@/lib/format';
import { EducationTooltip } from './EducationTooltip';
import type { TickerBrief } from '@/types/professional';

interface TickerCardProps {
  ticker: TickerBrief;
  onAddToWatchlist?: (symbol: string) => void;
}

const VERDICT_COLORS: Record<string, string> = {
  STRONG_BUY: 'bg-green-500/15 text-green-400 border-green-500/30',
  BUY: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  WATCH: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  AVOID: 'bg-red-500/15 text-red-400 border-red-500/30',
};

const CHANGE_COLORS = {
  positive: 'text-green-400',
  negative: 'text-red-400',
  neutral: 'text-text-muted',
};

function formatPrice(price: number): string {
  return price >= 1000
    ? price.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    : price.toFixed(2);
}

export function TickerCard({ ticker, onAddToWatchlist }: TickerCardProps) {
  const navigate = useNavigate();

  const changeColor =
    ticker.premarketChangePct !== null
      ? ticker.premarketChangePct > 0
        ? CHANGE_COLORS.positive
        : ticker.premarketChangePct < 0
          ? CHANGE_COLORS.negative
          : CHANGE_COLORS.neutral
      : CHANGE_COLORS.neutral;

  const ChangeIcon =
    ticker.premarketChangePct !== null && ticker.premarketChangePct > 0
      ? TrendingUp
      : ticker.premarketChangePct !== null && ticker.premarketChangePct < 0
        ? TrendingDown
        : Minus;

  const verdictColor = VERDICT_COLORS[ticker.verdict] || VERDICT_COLORS.WATCH;

  return (
    <div
      data-testid="ticker-card"
      className="bg-surface-secondary group rounded-lg border border-border/60 p-3 transition-all duration-150 hover:border-accent/30"
    >
      {/* Header: Symbol + Verdict badge */}
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-bold text-text-primary">
          {ticker.symbol}
        </span>
        <span
          className={cn(
            'text-2xs rounded-full border px-2 py-0.5 font-semibold',
            verdictColor
          )}
        >
          {ticker.verdict}
        </span>
      </div>

      {/* Screen name + score */}
      <div className="text-2xs mb-2 flex items-center gap-2 text-text-muted">
        <span>{ticker.screenName}</span>
        <span className="opacity-50">|</span>
        <span>Score: {ticker.screenScore.toFixed(1)}</span>
      </div>

      {/* Pre-market price */}
      <div className="mb-2 flex items-center gap-1.5">
        {ticker.livePrice !== null ? (
          <>
            <span className="font-mono text-sm font-medium text-text-primary">
              ${formatPrice(ticker.livePrice)}
            </span>
            {ticker.premarketChangePct !== null && (
              <span
                className={cn(
                  'flex items-center gap-0.5 font-mono text-xs',
                  changeColor
                )}
              >
                <ChangeIcon className="h-3 w-3" />
                {formatPct(ticker.premarketChangePct)}
              </span>
            )}
          </>
        ) : (
          <span className="text-xs text-text-muted">Price unavailable</span>
        )}
      </div>

      {/* Education hints */}
      {Object.keys(ticker.educationHints).length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1">
          {Object.entries(ticker.educationHints)
            .slice(0, 3)
            .map(([key]) => (
              <EducationTooltip key={key} metricKey={key} compact />
            ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={() => navigate(`/pro/ticker/${ticker.symbol}`)}
          className="flex-1 rounded-md bg-accent/10 px-2 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-accent/20"
        >
          <ExternalLink className="mr-1 inline h-3 w-3" />
          Analyze
        </button>
        {onAddToWatchlist && (
          <button
            onClick={() => onAddToWatchlist(ticker.symbol)}
            className="rounded-md border border-border/60 px-2 py-1.5 text-xs text-text-muted transition-colors hover:border-accent/30 hover:text-accent"
          >
            + Add
          </button>
        )}
      </div>
    </div>
  );
}
