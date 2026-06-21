import { useEffect, useRef, useCallback } from 'react';
import type { IChartApi, Time } from 'lightweight-charts';

/**
 * Synchronizes visible time range across multiple chart instances.
 * The first chart in the map acts as the "master" — its visible range
 * changes are propagated to all slave charts.
 */
export function useSynchronizedCharts(
  chartRefs: Map<string, IChartApi>
): void {
  const syncingRef = useRef(false);
  const rafRef = useRef<number | null>(null);

  const syncTimeRange = useCallback(
    (sourceKey: string, range: { from: Time; to: Time }) => {
      if (syncingRef.current) return;
      syncingRef.current = true;

      if (rafRef.current) cancelAnimationFrame(rafRef.current);

      rafRef.current = requestAnimationFrame(() => {
        chartRefs.forEach((chart, key) => {
          if (key === sourceKey) return;
          try {
            chart.timeScale().setVisibleRange({
              from: range.from,
              to: range.to,
            });
          } catch {
            // Ignore errors during sync
          }
        });
        syncingRef.current = false;
      });
    },
    [chartRefs]
  );

  useEffect(() => {
    if (chartRefs.size < 2) return;

    // Find the master chart (first entry)
    const masterEntry = Array.from(chartRefs.entries())[0];
    if (!masterEntry) return;
    const [masterKey, masterChart] = masterEntry;

    // Time range change callback
    const timeRangeCb: Parameters<
      ReturnType<IChartApi['timeScale']>['subscribeVisibleTimeRangeChange']
    >[0] = (range) => {
      if (range) {
        syncTimeRange(masterKey, {
          from: range.from as Time,
          to: range.to as Time,
        });
      }
    };

    masterChart.timeScale().subscribeVisibleTimeRangeChange(timeRangeCb);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      try {
        masterChart
          .timeScale()
          .unsubscribeVisibleTimeRangeChange(timeRangeCb);
      } catch {
        // Ignore errors during unsubscribe
      }
    };
  }, [chartRefs, syncTimeRange]);
}
