import { useEffect, useCallback, useState } from 'react';
import { useSectorRotationStore } from '@/store/sectorRotation';
import { fetchSectorRotation } from '@/api/sectorRotation';
import { SectorHeatMap } from './SectorHeatMap';
import { SectorDetailCard } from './SectorDetailCard';
import { RotationFlows } from './RotationFlows';
import { EducationPanel } from './EducationPanel';
import { cn } from '@/lib/cn';
import { RefreshCw, RotateCcw, Activity, TrendingUp, BookOpen, AlertTriangle, Layers } from 'lucide-react';

type Tab = 'heatmap' | 'flows' | 'learn';

export function SectorRotationPage() {
  const {
    sectors,
    setSectors,
    selectedSector,
    setSelectedSector,
    timeframe,
    setTimeframe,
    isLoading,
    setIsLoading,
    error,
    setError,
    rotationPhase,
    setRotationPhase,
    marketRegime,
    setMarketRegime,
  } = useSectorRotationStore();

  const [activeTab, setActiveTab] = useState<Tab>('heatmap');
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchSectorRotation();
      setSectors(data.sectors);
      setRotationPhase(data.rotation_phase);
      setMarketRegime(data.market_regime);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sector rotation data');
    } finally {
      setIsLoading(false);
      setLastUpdated(new Date().toLocaleTimeString());
    }
  }, [setSectors, setRotationPhase, setMarketRegime, setIsLoading, setError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const changeKey = timeframe === '1D' ? 'change_1d' : 'change_1w';
  const flowSignalKey = timeframe === '1D' ? 'flow_signal' as const : 'flow_signal_1w' as const;
  const flowStrengthKey = timeframe === '1D' ? 'flow_strength' as const : 'flow_strength_1w' as const;
  const sortedUp = [...sectors].sort((a, b) => ((b[changeKey] ?? 0)) - (a[changeKey] ?? 0));
  const sortedDown = [...sectors].sort((a, b) => ((a[changeKey] ?? 0)) - (b[changeKey] ?? 0));
  // Compute timeframe-aware leaders/laggards from same metric as Top 3
  const frameLeaders = sortedUp.slice(0, 3).map(s => s.symbol);
  const frameLaggards = sortedDown.slice(0, 3).map(s => s.symbol);

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-text-primary">
            Sector Rotation
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Track smart money flows across 11 sectors. Identify rotation patterns and positioning.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Timeframe toggle */}
          <div className="flex overflow-hidden rounded-lg border border-border bg-surface">
            {(['1D', '1W'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={cn(
                  'px-3 py-1.5 text-xs font-semibold transition-colors',
                  timeframe === tf
                    ? 'bg-accent text-white'
                    : 'text-text-muted hover:text-text-primary hover:bg-surface-hover'
                )}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Last updated */}
          {lastUpdated && (
            <span className="text-xs text-text-muted/60 tabular-nums whitespace-nowrap">
              Updated {lastUpdated}
            </span>
          )}

          {/* Refresh now */}
          <button
            onClick={loadData}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-text-primary hover:bg-surface-hover transition-colors disabled:opacity-50"
          >
            <RotateCcw className={cn('h-3 w-3', isLoading && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-loss/30 bg-loss/5 px-4 py-3">
          <AlertTriangle className="h-4 w-4 text-loss" />
          <span className="text-sm text-loss">{error}</span>
          <button onClick={loadData} className="ml-auto text-sm font-semibold text-accent hover:underline">Retry</button>
        </div>
      )}

      {/* Metrics row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="flex items-center gap-2 text-xs text-text-muted mb-1">
            <Layers className="h-3.5 w-3.5" /> Rotation Phase
          </div>
          <div className="text-sm font-bold text-text-primary capitalize">
            {rotationPhase?.replace(/_/g, ' ') || 'Analyzing...'}
          </div>
          <div className="mt-0.5 text-[10px] text-text-muted/60">trailing 1W basis</div>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="flex items-center gap-2 text-xs text-text-muted mb-1">
            <Activity className="h-3.5 w-3.5" /> Market Regime
          </div>
          <div className="text-sm font-bold text-text-primary capitalize">
            {marketRegime?.replace(/_/g, ' ') || 'Analyzing...'}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="flex items-center gap-2 text-xs text-text-muted mb-1">
            <TrendingUp className="h-3.5 w-3.5" /> Top Gainers
          </div>
          <div className="text-sm font-bold text-gain">
            {frameLeaders.length > 0 ? frameLeaders.join(' · ') : '—'}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="flex items-center gap-2 text-xs text-text-muted mb-1">
            <TrendingUp className="h-3.5 w-3.5 rotate-180" /> Top Losers
          </div>
          <div className="text-sm font-bold text-loss">
            {frameLaggards.length > 0 ? frameLaggards.join(' · ') : '—'}
          </div>
        </div>
      </div>

      {/* Top/Bottom performers — now skips the summary cards since the metrics row shows the same */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-surface p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-muted">
            Top 3 — {timeframe === '1D' ? 'Today' : 'This Week'}
          </h3>
          <div className="space-y-2">
            {sortedUp.slice(0, 3).map((s, i) => (
              <div key={s.symbol} className="flex items-center gap-3">
                <span className={cn(
                  'w-5 text-xs font-bold',
                  i === 0 ? 'text-accent' : i === 1 ? 'text-text-primary' : 'text-text-muted'
                )}>{i + 1}</span>
                <span className="flex-1 text-sm font-semibold text-text-primary">{s.symbol} — {s.name}</span>
                  <div className="flex items-center gap-2">
                  <span className={cn(
                    'h-1.5 w-1.5 rounded-full',
                    (s[flowSignalKey] === 'inflow' && s[flowStrengthKey] > 30) ? 'bg-gain animate-pulse' :
                    s[flowSignalKey] === 'inflow' ? 'bg-gain' :
                    s[flowSignalKey] === 'outflow' ? 'bg-loss' : 'bg-text-muted/30'
                  )}
                    title={s[flowSignalKey] === 'inflow' ? 'Smart money inflow' : s[flowSignalKey] === 'outflow' ? 'Smart money outflow' : 'Neutral'}
                  />
                  <span className="text-sm font-bold text-gain tabular-nums">
                    +{(((s[changeKey] ?? 0)).toFixed(2))}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-muted">
            Bottom 3 — {timeframe === '1D' ? 'Today' : 'This Week'}
          </h3>
          <div className="space-y-2">
            {sortedDown.slice(0, 3).map((s, i) => (
              <div key={s.symbol} className="flex items-center gap-3">
                <span className="w-5 text-xs font-bold text-text-muted">{i + 1}</span>
                <span className="flex-1 text-sm font-semibold text-text-primary">{s.symbol} — {s.name}</span>
                <div className="flex items-center gap-2">
                  <span className={cn(
                    'h-1.5 w-1.5 rounded-full',
                    (s[flowSignalKey] === 'inflow' && s[flowStrengthKey] > 30) ? 'bg-gain animate-pulse' :
                    s[flowSignalKey] === 'inflow' ? 'bg-gain' :
                    s[flowSignalKey] === 'outflow' ? 'bg-loss' : 'bg-text-muted/30'
                  )}
                    title={s[flowSignalKey] === 'inflow' ? 'Smart money inflow' : s[flowSignalKey] === 'outflow' ? 'Smart money outflow' : 'Neutral'}
                  />
                  <span className="text-sm font-bold text-loss tabular-nums">
                    {((s[changeKey] ?? 0)).toFixed(2)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex border-b border-border">
        {([
          { key: 'heatmap', label: 'Heatmap', icon: <Layers className="h-4 w-4" /> },
          { key: 'flows', label: 'Rotation Flows', icon: <TrendingUp className="h-4 w-4" /> },
          { key: 'learn', label: 'Learn', icon: <BookOpen className="h-4 w-4" /> },
        ] as const).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'flex items-center gap-2 border-b-2 px-5 py-3 text-sm font-semibold transition-colors',
              activeTab === tab.key
                ? 'border-accent text-accent'
                : 'border-transparent text-text-muted hover:text-text-primary hover:border-border'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {isLoading && sectors.length === 0 ? (
        <div className="flex h-64 items-center justify-center">
          <RefreshCw className="h-8 w-8 animate-spin text-text-muted" />
        </div>
      ) : (
        <>
          {activeTab === 'heatmap' && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <SectorHeatMap
                  timeframe={timeframe}
                  onSectorClick={(sym) => setSelectedSector(selectedSector === sym ? null : sym)}
                />
              </div>
              <div className="space-y-4">
                {selectedSector && (
                  <SectorDetailCard
                    symbol={selectedSector}
                    onClose={() => setSelectedSector(null)}
                  />
                )}
                {!selectedSector && (
                  <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-border bg-surface/50">
                    <p className="text-center text-sm text-text-muted">
                      Click a sector card<br />for detailed analysis
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'flows' && (
            <RotationFlows timeframe={timeframe} />
          )}

          {activeTab === 'learn' && (
            <EducationPanel />
          )}
        </>
      )}
    </div>
  );
}
