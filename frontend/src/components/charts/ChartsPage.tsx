import { useCallback, useMemo, useRef } from 'react';
import { useQuery, useQueries } from '@tanstack/react-query';
import { fetchOHLCV, fetchIndicators } from '@/api/data';
import { useChartStore } from '@/store/chart';
import { STALE_TIMES } from '@/lib/constants';
import { useSynchronizedCharts } from '@/hooks/useSynchronizedCharts';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { SymbolSearch } from './SymbolSearch';
import { ChartToolbar } from './ChartToolbar';
import { ChartPane } from './ChartPane';
import { ChartSkeleton } from './ChartSkeleton';
import { IndicatorPanel } from './IndicatorPanel';
import type { IChartApi } from 'lightweight-charts';

function ChartsContent() {
  const { selectedSymbol, activeTimeframes, activeIndicators } = useChartStore();
  const chartRefs = useRef<Map<string, IChartApi>>(new Map());

  const handleChartReady = useCallback(
    (tf: string, chart: IChartApi) => {
      chartRefs.current.set(tf, chart);
      // Trigger sync when all charts are registered
      if (chartRefs.current.size === activeTimeframes.length) {
        // Charts are ready for sync
      }
    },
    [activeTimeframes.length]
  );

  useSynchronizedCharts(chartRefs.current);

  // OHLCV queries for each timeframe — useQueries handles dynamic array safely
  const ohlcvResults = useQueries({
    queries: useMemo(
      () =>
        activeTimeframes.map((tf) => ({
          queryKey: ['ohlcv', selectedSymbol, { timeframe: tf }] as const,
          queryFn: () => fetchOHLCV(selectedSymbol, tf),
          staleTime: STALE_TIMES.ohlcv,
        })),
      [selectedSymbol, activeTimeframes]
    ),
  });

  // Single indicator query for all active indicators (backend supports comma-separated)
  const indicatorQuery = useQuery({
    queryKey: ['indicators', selectedSymbol, { timeframe: activeTimeframes[0], indicators: activeIndicators }] as const,
    queryFn: () => fetchIndicators(selectedSymbol, activeTimeframes[0], activeIndicators.join(',')),
    staleTime: STALE_TIMES.indicators,
    enabled: activeIndicators.length > 0,
  });

  // Collect any indicator errors
  const indicatorErrors = useMemo(() => {
    if (indicatorQuery.isError && activeIndicators.length > 0) {
      return activeIndicators.map((ind) => ind.toUpperCase());
    }
    return [];
  }, [indicatorQuery.isError, activeIndicators]);

  // Build indicator data map
  const indicatorData = useMemo(() => {
    const map: Record<string, { symbol: string; timeframe: string; indicators: Record<string, Array<{ timestamp: string; value: number }>> }> = {};
    if (indicatorQuery.data) {
      map[activeTimeframes[0]] = indicatorQuery.data;
    }
    return map;
  }, [indicatorQuery.data, activeTimeframes]);

  // WS indicator updates disabled — backend uses REST-only for now

  // Detect timeframes that returned no OHLCV data
  const emptyTimeframes = useMemo(() => {
    return activeTimeframes.filter((_, i) => {
      const r = ohlcvResults[i];
      return r?.isSuccess && (!r.data || r.data.length === 0);
    });
  }, [ohlcvResults, activeTimeframes]);

  // True when every timeframe returned zero candles (likely invalid symbol)
  const symbolNotFound = useMemo(
    () => ohlcvResults.length > 0 && emptyTimeframes.length === activeTimeframes.length,
    [emptyTimeframes, activeTimeframes, ohlcvResults.length],
  );

  const isLoading = ohlcvResults.some((r) => r.isLoading);

  // Compute latest indicator values for the panel — MUST be top-level, not inside JSX
  const indicatorValues = useMemo(() => {
    const acc: Record<string, number | null> = {};
    if (indicatorQuery.data) {
      Object.entries(indicatorQuery.data.indicators).forEach(([key, points]) => {
        if (points.length > 0) {
          acc[key] = points[points.length - 1].value;
        }
      });
    }
    return acc;
  }, [indicatorQuery.data]);

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 p-4">
        {activeTimeframes.map((tf) => (
          <ChartSkeleton key={tf} />
        ))}
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <div className="flex flex-1 flex-col">
        <div className="flex items-center gap-3 border-b border-border bg-surface/30 px-4 py-3">
          <SymbolSearch />
          <ChartToolbar />
        </div>
        {symbolNotFound && (
          <div className="mx-4 mt-4 flex items-center gap-2 rounded border border-loss/30 bg-loss/5 px-3 py-2 text-xs text-loss">
            <span className="font-medium">Symbol not found:</span>
            <span>{selectedSymbol} — no data available. Check the ticker or try a different symbol.</span>
          </div>
        )}
        {indicatorErrors.length > 0 && (
          <div className="mx-4 mt-4 flex items-center gap-2 rounded border border-loss/30 bg-loss/5 px-3 py-2 text-xs text-loss">
            <span className="font-medium">Indicator error:</span>
            <span>{indicatorErrors.join(', ')} — data unavailable</span>
          </div>
        )}
        <div className="grid grid-cols-2 gap-4 overflow-auto p-4">
          {activeTimeframes.map((tf, i) => {
            const ohlcvData = ohlcvResults[i]?.data || [];
            const isEmpty = ohlcvResults[i]?.isSuccess && (!ohlcvData || ohlcvData.length === 0);
            return (
              <div key={tf} className="relative">
                {isEmpty && (
                  <div className="absolute inset-0 z-10 flex items-center justify-center rounded border border-dark-600 bg-dark-900/80">
                    <span className="text-xs text-dark-400">No data for {tf}</span>
                  </div>
                )}
                <ChartPane
                  timeframe={tf}
                  symbol={selectedSymbol}
                  candles={ohlcvData}
                  indicators={indicatorData[tf]?.indicators || {}}
                  onChartReady={handleChartReady}
                />
              </div>
            );
          })}
        </div>
      </div>
      <IndicatorPanel
        symbol={selectedSymbol}
        indicatorValues={indicatorValues}
      />
    </div>
  );
}

export function ChartsPage() {
  return (
    <ErrorBoundary>
      <ChartsContent />
    </ErrorBoundary>
  );
}
