import { useEffect, useRef, useState, useCallback } from 'react';
import { useMarketStore } from '@/store/market';
import { fetchMarketRegime } from '@/api/sectorRotation';
import { cn } from '@/lib/cn';
import { TrendingUp, TrendingDown, Activity, ChevronDown, AlertCircle, RefreshCw } from 'lucide-react';

function scoreToColor(score: number): string {
  if (score >= 80) return 'bg-green-500';
  if (score >= 65) return 'bg-green-400';
  if (score >= 50) return 'bg-yellow-400';
  if (score >= 35) return 'bg-orange-400';
  if (score >= 20) return 'bg-red-400';
  return 'bg-red-600';
}

function scoreToTextColor(score: number): string {
  if (score >= 65) return 'text-green-400';
  if (score >= 50) return 'text-yellow-400';
  if (score >= 35) return 'text-orange-400';
  return 'text-red-400';
}

function regimeIcon(label: string): React.ReactNode {
  const l = label.toLowerCase();
  if (l.includes('exuberance') || l.includes('risk-on')) {
    return <TrendingUp className="h-3.5 w-3.5" />;
  }
  if (l.includes('crisis') || l.includes('risk-off')) {
    return <TrendingDown className="h-3.5 w-3.5" />;
  }
  return <Activity className="h-3.5 w-3.5" />;
}

export function RegimeBar() {
  const { regime, isLoading, error, setRegime, setIsLoading, setError } = useMarketStore();
  const [expanded, setExpanded] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadRegime = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await fetchMarketRegime();
      setRegime(data);
      setFetchError(null); // Clear any previous fetch errors
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Regime fetch failed';
      // On background refresh error: keep showing stale data, just store the error
      if (regime) {
        setFetchError(msg);
      } else {
        setError(msg);
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [setRegime, setIsLoading, setError, regime]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await loadRegime();
  }, [loadRegime]);

  // Fetch on mount and every 1 hr — daily data only changes at market close
  useEffect(() => {
    loadRegime();
    intervalRef.current = setInterval(loadRegime, 3_600_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Close panel on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setExpanded(false);
      }
    }
    if (expanded) {
      document.addEventListener('mousedown', handleClick);
      return () => document.removeEventListener('mousedown', handleClick);
    }
  }, [expanded]);

  // ── First load: regime data not yet available ──
  if (!regime && isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-text-muted">
        <Activity className="h-3.5 w-3.5 animate-pulse" />
        <span>Regime: Loading...</span>
      </div>
    );
  }

  // ── Error before first successful load ──
  if (!regime && error) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-loss">
        <AlertCircle className="h-3.5 w-3.5" />
        <span>Regime unavailable</span>
      </div>
    );
  }

  // ── No data at all ──
  if (!regime) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-text-muted">
        <Activity className="h-3.5 w-3.5" />
        <span>Regime: —</span>
      </div>
    );
  }

  // ── Data available: always show pill button even if stale ──
  const { composite_score, regime_label, regime_color } = regime;

  return (
    <div ref={panelRef} className="relative">
      {/* Pill button */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => setExpanded(!expanded)}
          className={cn(
            'flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold transition-all duration-150',
            'border border-border/60 hover:border-border hover:bg-surface-hover'
          )}
          title={`Market Regime: ${regime_label} (${composite_score}/100)`}
        >
          <span className={cn('flex items-center gap-1', scoreToTextColor(composite_score))}>
            {regimeIcon(regime_label)}
            <span>{composite_score.toFixed(0)}</span>
          </span>

          {/* Mini score bar */}
          <div className="h-1.5 w-12 overflow-hidden rounded-full bg-border">
            <div
              className={cn('h-full rounded-full transition-all duration-500', scoreToColor(composite_score))}
              style={{ width: `${composite_score}%` }}
            />
          </div>

          <span className="text-text-muted max-w-[80px] truncate">{regime_label}</span>
          {/* "As of" timestamp — daily data reference */}
          {regime.timestamp && (
            <span className="text-[10px] text-text-muted/50 tabular-nums whitespace-nowrap">
              {new Date(regime.timestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
            </span>
          )}
          <ChevronDown
            className={cn(
              'h-3 w-3 text-text-muted transition-transform duration-150',
              expanded && 'rotate-180'
            )}
          />
        </button>
        {/* Manual refresh button */}
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className={cn(
            'p-1 rounded-full text-text-muted hover:text-text-primary hover:bg-surface-hover transition-colors',
            isRefreshing && 'animate-spin opacity-50 cursor-wait'
          )}
          title="Refresh market regime"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Stale indicator tooltip */}
      {fetchError && !expanded && (
        <div className="absolute -right-1 -top-1">
          <AlertCircle className="h-3 w-3 text-warning" />
        </div>
      )}

      {/* Expanded detail panel */}
      {expanded && (
        <div className="absolute right-0 top-full z-50 mt-2 w-72 rounded-xl border border-border bg-surface shadow-xl backdrop-blur-sm">
          <div className="border-b border-border px-4 py-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">
                Market Regime
              </span>
              <span className="text-xs text-text-muted">
                {new Date(regime.timestamp).toLocaleTimeString()}
              </span>
            </div>
            {fetchError && (
              <div className="mt-1 flex items-center gap-1 text-[11px] text-warning">
                <AlertCircle className="h-3 w-3" />
                <span>Stale data — refresh failed</span>
              </div>
            )}
            <div className="mt-2 flex items-center gap-3">
              <span
                className="text-2xl font-bold"
                style={{ color: regime_color }}
              >
                {composite_score.toFixed(0)}
              </span>
              <div className="flex-1">
                <div className="h-2 w-full overflow-hidden rounded-full bg-border">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${composite_score}%`,
                      backgroundColor: regime_color,
                    }}
                  />
                </div>
              </div>
              <span className="text-sm font-bold" style={{ color: regime_color }}>
                {regime_label}
              </span>
            </div>
          </div>

          {/* Sub-indicators */}
          <div className="space-y-1 px-4 py-2.5">
            {[
              { key: 'vix', label: 'VIX', indicator: regime.vix },
              { key: 'risk_appetite', label: 'Risk Appetite', indicator: regime.risk_appetite },
              { key: 'sector_breadth', label: 'Sector Breadth', indicator: regime.sector_breadth },
              { key: 'safe_haven', label: 'Safe Haven', indicator: regime.safe_haven },
              { key: 'yield_curve', label: 'Yield Curve', indicator: regime.yield_curve },
            ].map(({ key, label, indicator }) => (
              <div key={key} className="flex items-center justify-between py-0.5">
                <div className="flex items-center gap-1.5">
                  <div
                    className={cn(
                      'h-1.5 w-1.5 rounded-full',
                      indicator.score >= 50 ? 'bg-green-400' : 'bg-red-400'
                    )}
                  />
                  <span className="text-xs text-text-muted">{label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      'text-xs font-semibold tabular-nums',
                      indicator.score >= 50 ? 'text-green-400' : 'text-red-400'
                    )}
                  >
                    {indicator.score.toFixed(0)}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Quick interpretation */}
          <div className="border-t border-border px-4 py-2">
            <p className="text-[11px] leading-relaxed text-text-muted">
              {composite_score >= 65
                ? 'Favorable environment for risk assets. Consider adding equity exposure.'
                : composite_score >= 50
                  ? 'Mixed signals. Maintain balanced positioning with room to adjust.'
                  : composite_score >= 35
                    ? 'Caution warranted. Reduce risk exposure and add defensive positions.'
                    : 'High-stress market. Prioritize capital preservation and hedges.'}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
