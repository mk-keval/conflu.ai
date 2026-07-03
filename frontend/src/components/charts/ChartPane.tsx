import { useRef, useEffect } from 'react';
import { createChart, type IChartApi, type ISeriesApi, type UTCTimestamp, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import { useResizeObserver } from '@/hooks/useResizeObserver';
import { useChartStore } from '@/store/chart';
import type { OHLCVCandle, IndicatorPoint } from '@/types/data';
import { INDICATOR_COLORS } from '@/lib/constants';

interface ChartPaneProps {
  timeframe: string;
  symbol: string;
  isMaster: boolean;
  candles: OHLCVCandle[];
  indicators: Record<string, IndicatorPoint[]>;
  onChartReady: (tf: string, chart: IChartApi) => void;
}

export function ChartPane({
  timeframe,
  symbol,
  isMaster,
  candles,
  indicators,
  onChartReady,
}: ChartPaneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const indicatorSeriesRef = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());
  const { activeIndicators } = useChartStore();

  const size = useResizeObserver(containerRef);

  // Create chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: size.width || 600,
      height: isMaster ? 400 : 300,
      layout: {
        background: { color: '#1a1a2e' },
        textColor: '#d1d4dc',
      },
      grid: {
        vertLines: { color: '#2a2a3e' },
        horzLines: { color: '#2a2a3e' },
      },
      crosshair: { mode: 0 }, // CrosshairMode.Normal
      timeScale: {
        borderColor: '#2a2a3e',
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: '#2a2a3e',
      },
    });

    chartRef.current = chart;
    onChartReady(timeframe, chart);

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22C55E',
      downColor: '#EF4444',
      borderVisible: false,
      wickUpColor: '#22C55E',
      wickDownColor: '#EF4444',
    });
    candleSeriesRef.current = candleSeries;

    // Volume series (separate pane)
    chart.addSeries(HistogramSeries, {
      color: '#60A5FA',
      priceFormat: { type: 'volume' },
    });

    return () => {
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      indicatorSeriesRef.current.clear();
    };
  }, [timeframe]); // Only recreate on timeframe change

  // Resize
  useEffect(() => {
    if (chartRef.current && size.width > 0) {
      chartRef.current.resize(size.width, isMaster ? 400 : 300);
    }
  }, [size.width, isMaster]);

  // Update candles — ensure ASC order by time
  useEffect(() => {
    if (!candleSeriesRef.current || candles.length === 0) return;

    const mappedCandles = [...candles]
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
      .map((c) => ({
        time: Math.floor(new Date(c.timestamp).getTime() / 1000) as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));

    candleSeriesRef.current.setData(mappedCandles);
  }, [candles]);

  // Update indicators
  useEffect(() => {
    if (!chartRef.current) return;

    const currentSeries = indicatorSeriesRef.current;

    // Add/update indicator series
    for (const indicatorName of activeIndicators) {
      const points = indicators[indicatorName];
      if (!points || points.length === 0) {
        // Remove if no data
        const series = currentSeries.get(indicatorName);
        if (series) {
          chartRef.current.removeSeries(series);
          currentSeries.delete(indicatorName);
        }
        continue;
      }

      const color = INDICATOR_COLORS[indicatorName as keyof typeof INDICATOR_COLORS] || '#7B68EE';

      let series = currentSeries.get(indicatorName);
      if (!series) {
        series = chartRef.current.addSeries(LineSeries, {
          color,
          lineWidth: indicatorName.startsWith('ema') ? 1 : 2,
          priceScaleId: indicatorName === 'rsi' ? 'rsi-scale' : undefined,
        });
        currentSeries.set(indicatorName, series);
      }

      const mappedData = [...points]
        .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        .map((p) => ({
          time: Math.floor(new Date(p.timestamp).getTime() / 1000) as UTCTimestamp,
          value: p.value,
        }));
      series.setData(mappedData);
    }

    // Remove indicator series that are no longer active
    currentSeries.forEach((series, name) => {
      if (!activeIndicators.includes(name)) {
        chartRef.current?.removeSeries(series);
        currentSeries.delete(name);
      }
    });
  }, [indicators, activeIndicators]);

  return (
    <div className="rounded border border-dark-600 bg-dark-900">
      <div className="flex items-center justify-between border-b border-dark-600 px-3 py-1.5">
        <span className="text-xs font-medium text-dark-200">{symbol} — {timeframe}</span>
      </div>
      <div ref={containerRef} />
    </div>
  );
}
