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
    ? price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : price.toFixed(2);
}

export function TickerCard({ ticker, onAddToWatchlist }: TickerCardProps) {
  const navigate = useNavigate();

  const changeColor = ticker.premarketChangePct !== null
    ? ticker.premarketChangePct > 0
      ? CHANGE_COLORS.positive
      : ticker.premarketChangePct < 0
        ? CHANGE_COLORS.negative
        : CHANGE_COLORS.neutral
    : CHANGE_COLORS.neutral;

  const ChangeIcon = ticker.premarketChangePct !== null && ticker.premarketChangePct > 0
    ? TrendingUp
    : ticker.premarketChangePct !== null && ticker.premarketChangePct < 0
      ? TrendingDown
      : Minus;

  const verdictColor = VERDICT_COLORS[ticker.verdict] || VERDICT_COLORS.WATCH;

  return (
    <div
      data-testid="ticker-card"
      className="rounded-lg border border-border/60 bg-surface-secondary p-3 hover:border-accent/30 transition-all duration-150 group"
    >
      {/* Header: Symbol + Verdict badge */}
      <div className="flex items-center justify-between mb-2">
        <span className="font-bold text-text-primary text-sm">{ticker.symbol}</span>
        <span className={cn(
          'text-2xs font-semibold px-2 py-0.5 rounded-full border',
          verdictColor
        )}>
          {ticker.verdict}
        </span>
      </div>

      {/* Screen name + score */}
      <div className="flex items-center gap-2 mb-2 text-2xs text-text-muted">
        <span>{ticker.screenName}</span>
        <span className="opacity-50">|</span>
        <span>Score: {ticker.screenScore.toFixed(1)}</span>
      </div>

      {/* Pre-market price */}
      <div className="flex items-center gap-1.5 mb-2">
        {ticker.livePrice !== null ? (
          <>
            <span className="text-sm font-mono font-medium text-text-primary">
              ${formatPrice(ticker.livePrice)}
            </span>
            {ticker.premarketChangePct !== null && (
              <span className={cn('flex items-center gap-0.5 text-xs font-mono', changeColor)}>
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
        <div className="flex flex-wrap gap-1 mb-3">
          {Object.entries(ticker.educationHints).slice(0, 3).map(([key]) => (
            <EducationTooltip key={key} metricKey={key} compact />
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={() => navigate(`/pro/ticker/${ticker.symbol}`)}
          className="flex-1 px-2 py-1.5 rounded-md bg-accent/10 text-accent text-xs font-medium hover:bg-accent/20 transition-colors"
        >
          <ExternalLink className="h-3 w-3 inline mr-1" />
          Analyze
        </button>
        {onAddToWatchlist && (
          <button
            onClick={() => onAddToWatchlist(ticker.symbol)}
            className="px-2 py-1.5 rounded-md border border-border/60 text-text-muted text-xs hover:text-accent hover:border-accent/30 transition-colors"
          >
            + Add
          </button>
        )}
      </div>
    </div>
  );
}
