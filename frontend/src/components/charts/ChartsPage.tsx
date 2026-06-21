import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchOHLCV, fetchIndicators } from '@/api/data';
import { useChartStore } from '@/store/chart';
import { useWS } from '@/ws/WebSocketProvider';
import { indicatorChannel } from '@/ws/channels';
import { STALE_TIMES } from '@/lib/constants';
import { useSynchronizedCharts } from '@/hooks/useSynchronizedCharts';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { SymbolSearch } from './SymbolSearch';
import { ChartToolbar } from './ChartToolbar';
import { ChartPane } from './ChartPane';
import { ChartSkeleton } from './ChartSkeleton';
import { IndicatorPanel } from './IndicatorPanel';
import type { IChartApi } from 'lightweight-charts';
import type { WSMessage, WSIndicatorUpdate } from '@/types/ws';

function ChartsContent() {
  const { selectedSymbol, activeTimeframes, activeIndicators } = useChartStore();
  const chartRefs = useRef<Map<string, IChartApi>>(new Map());
  const { subscribe, unsubscribe, onMessage } = useWS();
  const queryClient = useQueryClient();

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

  // OHLCV queries for each timeframe
  const ohlcvQueries = useMemo(
    () =>
      activeTimeframes.map((tf) => ({
        queryKey: ['ohlcv', selectedSymbol, { timeframe: tf }] as const,
        queryFn: () => fetchOHLCV(selectedSymbol, tf),
        staleTime: STALE_TIMES.ohlcv,
      })),
    [selectedSymbol, activeTimeframes]
  );

  const ohlcvResults = ohlcvQueries.map((q) => useQuery(q));

  // Indicator queries for each active indicator on the first timeframe
  const indicatorQueries = useMemo(
    () =>
      activeIndicators.map((ind) => ({
        queryKey: ['indicators', selectedSymbol, { timeframe: activeTimeframes[0], indicators: ind }] as const,
        queryFn: () => fetchIndicators(selectedSymbol, activeTimeframes[0], ind),
        staleTime: STALE_TIMES.indicators,
      })),
    [selectedSymbol, activeTimeframes, activeIndicators]
  );

  const indicatorResults = indicatorQueries.map((q) => useQuery(q));

  // Build indicator data map
  const indicatorData = useMemo(() => {
    const map: Record<string, { symbol: string; timeframe: string; indicators: Record<string, Array<{ timestamp: string; value: number }>> }> = {};
    for (const result of indicatorResults) {
      if (result.data) {
        map[activeTimeframes[0]] = result.data;
      }
    }
    return map;
  }, [indicatorResults, activeTimeframes]);

  // WS subscription for indicators
  useEffect(() => {
    const channels = activeIndicators.map((ind) =>
      indicatorChannel(selectedSymbol, ind)
    );
    channels.forEach((ch) => subscribe(ch));
    return () => channels.forEach((ch) => unsubscribe(ch));
  }, [selectedSymbol, activeIndicators, subscribe, unsubscribe]);

  // Handle WS indicator updates
  useEffect(() => {
    const unsub = onMessage((message: WSMessage) => {
      if (message.type === 'indicator_update') {
        const update = message as WSIndicatorUpdate;
        // Update the query cache with new indicator data
        queryClient.setQueryData(
          ['indicators', update.data.symbol, { timeframe: activeTimeframes[0], indicators: update.data.indicator }],
          (oldData: unknown) => oldData // Keep existing data, WS provides real-time point
        );
      }
    });
    return unsub;
  }, [onMessage, queryClient, activeTimeframes]);

  const isLoading = ohlcvResults.some((r) => r.isLoading);

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
        <div className="flex items-center gap-3 border-b border-dark-600 px-4 py-3">
          <SymbolSearch />
          <ChartToolbar />
        </div>
        <div className="grid grid-cols-2 gap-4 overflow-auto p-4">
          {activeTimeframes.map((tf, i) => {
            const ohlcvData = ohlcvResults[i]?.data || [];
            return (
              <ChartPane
                key={tf}
                timeframe={tf}
                symbol={selectedSymbol}
                isMaster={i === 0}
                candles={ohlcvData}
                indicators={indicatorData[tf]?.indicators || {}}
                onChartReady={handleChartReady}
              />
            );
          })}
        </div>
      </div>
      <IndicatorPanel
        symbol={selectedSymbol}
        indicatorValues={
          indicatorResults.reduce(
            (acc, r) => {
              if (r.data) {
                Object.entries(r.data.indicators).forEach(([key, points]) => {
                  if (points.length > 0) {
                    acc[key] = points[points.length - 1].value;
                  }
                });
              }
              return acc;
            },
            {} as Record<string, number | null>
          )
        }
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
