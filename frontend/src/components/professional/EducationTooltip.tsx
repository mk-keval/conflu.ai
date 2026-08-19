import { useState, useRef, useCallback, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { HelpCircle, Sparkles, Loader2 } from 'lucide-react';
import { explainMetric } from '@/api/professional';
import { cn } from '@/lib/cn';

interface EducationTooltipProps {
  metricKey: string;
  metricLabel?: string;
  metricValue?: string;
  symbol?: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
  compact?: boolean;
  children?: React.ReactNode;
}

/** Static fallback explanations for common metrics. */
const STATIC_EXPLANATIONS: Record<string, { what: string; why: string }> = {
  pe_ratio: {
    what: 'Price-to-Earnings ratio — how much you pay for $1 of earnings.',
    why: 'Lower is cheaper; higher means the market expects growth.',
  },
  rsi: {
    what: 'Relative Strength Index — momentum on a scale of 0-100.',
    why: 'Above 70 = overbought (pullback likely). Below 30 = oversold (bounce possible).',
  },
  atr_pct: {
    what: 'Average True Range % — how much the stock moves daily on average.',
    why: 'Higher = more volatility (wider stops needed). Lower = calmer (tight stops work).',
  },
  beta: {
    what: 'How much the stock moves compared to the S&P 500.',
    why: 'Above 1.5 = aggressive (amplifies market moves). Below 0.8 = defensive.',
  },
  market_cap: {
    what: 'Total dollar value of all shares outstanding.',
    why: 'Large caps (>$10B) are stable. Small caps (<$2B) are riskier but can grow faster.',
  },
  volume_ratio: {
    what: "Today's trading volume vs the 10-day average.",
    why: 'Above 1.5 = unusual activity. Above 3 = major event.',
  },
  change_1w: {
    what: 'Price change over the last week (5 trading days).',
    why: 'Confirms momentum: a stock up over a week has more conviction than a one-day pop.',
  },
  market_regime: {
    what: 'Overall market mood, scored 0-100 from VIX, risk appetite, sector breadth, safe haven flows, and yield curve.',
    why: 'High = favorable for buying. Low = defensive. It tells you whether to lean aggressive or cautious.',
  },
  sector_rotation: {
    what: 'How money is moving between industry sectors (tech, health, energy, etc.).',
    why: 'Follows the economic cycle. Buying the sector where money is flowing increases your odds.',
  },
  vix: {
    what: 'VIX — the market\'s "fear gauge." Measures how much volatility investors expect in the next 30 days.',
    why: 'Below 15 = calm. Above 30 = panic. High VIX usually means stocks are under pressure.',
  },
  advance_decline_ratio: {
    what: 'How many sectors rose today vs how many fell.',
    why: 'Above 1 = more winners than losers (healthy market). Below 1 = broad selling.',
  },
  dollar_index: {
    what: 'US Dollar strength vs a basket of major currencies.',
    why: 'Rising dollar can pressure commodities and international revenue. Falling dollar often helps gold and foreign sales.',
  },
  sp500_futures: {
    what: 'S&P 500 index level — tracks the 500 largest US companies.',
    why: 'The benchmark for "how is the overall market doing." Up = risk appetite, down = caution.',
  },
  nasdaq_futures: {
    what: 'Nasdaq index level — tracks big tech and growth stocks.',
    why: 'More volatile than the S&P. Tells you how the tech-heavy part of the market is doing.',
  },
};

export function EducationTooltip({
  metricKey,
  metricLabel,
  metricValue,
  symbol,
  position = 'top',
  compact = false,
  children,
}: EducationTooltipProps) {
  const [open, setOpen] = useState(false);
  const [showEnhanced, setShowEnhanced] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);

  const staticInfo = STATIC_EXPLANATIONS[metricKey];

  const { data: enhanced, isFetching } = useQuery({
    queryKey: ['professional', 'education', metricKey, symbol],
    queryFn: () => explainMetric(metricKey, symbol),
    enabled: showEnhanced && !!metricKey,
    staleTime: 24 * 60 * 60 * 1000, // 24h cache
  });

  const handleToggle = useCallback(() => {
    setOpen((prev) => !prev);
    setShowEnhanced(false);
  }, []);

  const handleExplainMore = useCallback(() => {
    setShowEnhanced(true);
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (
        tooltipRef.current &&
        !tooltipRef.current.contains(e.target as Node) &&
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
        setShowEnhanced(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        setShowEnhanced(false);
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open]);

  const positionClasses: Record<string, string> = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  return (
    <span className="relative inline-flex items-center">
      {children ? (
        <span ref={triggerRef} onClick={handleToggle} className="cursor-pointer">
          {children}
        </span>
      ) : (
        <button
          ref={triggerRef as React.Ref<HTMLButtonElement>}
          onClick={handleToggle}
          className={cn(
            'inline-flex items-center justify-center rounded-full transition-colors',
            compact ? 'h-3.5 w-3.5' : 'h-4 w-4',
            'text-text-muted hover:text-accent hover:bg-accent/10'
          )}
          aria-label={`Learn about ${metricLabel || metricKey}`}
        >
          <HelpCircle className={compact ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
        </button>
      )}

      {open && (
        <div
          ref={tooltipRef}
          role="tooltip"
          className={cn(
            'absolute z-50 w-72 p-3 rounded-lg border border-border bg-surface shadow-xl',
            'text-sm text-text-primary backdrop-blur-sm',
            'animate-in fade-in duration-100',
            positionClasses[position]
          )}
        >
          {/* Metric label */}
          <div className="font-semibold text-xs text-accent uppercase tracking-wider mb-1">
            {metricLabel || metricKey.replace(/_/g, ' ')}
            {metricValue && (
              <span className="text-text-primary ml-1 normal-case font-mono">
                = {metricValue}
              </span>
            )}
          </div>

          {/* Static explanation */}
          {staticInfo && !showEnhanced && (
            <>
              <p className="text-text-primary mb-1">{staticInfo.what}</p>
              <p className="text-text-muted text-xs">{staticInfo.why}</p>
              <button
                onClick={handleExplainMore}
                className="mt-2 inline-flex items-center gap-1 text-xs text-accent hover:text-accent-light transition-colors"
              >
                <Sparkles className="h-3 w-3" />
                Explain more
              </button>
            </>
          )}

          {/* Enhanced explanation (LLM) */}
          {showEnhanced && (
            <>
              {isFetching ? (
                <div className="flex items-center gap-2 text-text-muted py-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Getting deeper explanation...
                </div>
              ) : enhanced ? (
                <>
                  <p className="text-text-primary mb-1">{enhanced.plainEnglish}</p>
                  {enhanced.valueContext && (
                    <p className="text-text-muted text-xs mt-1 italic">
                      {enhanced.valueContext}
                    </p>
                  )}
                  {enhanced.actionable && (
                    <p className="text-accent text-xs mt-2 font-medium">
                      💡 {enhanced.actionable}
                    </p>
                  )}
                  <span className="block text-2xs text-text-muted mt-1">
                    Source: {enhanced.source === 'llm' ? 'AI-enhanced' : 'template'}
                  </span>
                </>
              ) : (
                <p className="text-text-muted text-xs">
                  No additional explanation available.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </span>
  );
}
