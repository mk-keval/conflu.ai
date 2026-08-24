import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw, ChevronDown, ChevronUp, AlertCircle, Sun } from 'lucide-react';
import { cn } from '@/lib/cn';
import { fetchMorningBrief } from '@/api/professional';
import { useProModeStore } from '@/store/professional';
import { TickerCard } from './TickerCard';
import { MarketInternalsStrip } from './MarketInternalsStrip';
import { SectorHeatmapMini } from './SectorHeatmapMini';
import { SectorFocusCard } from '@/components/sector-rotation/SectorFocusCard';
import { EducationTooltip } from './EducationTooltip';
import type { ScreenSection } from '@/types/professional';

const REGIME_COLORS: Record<string, string> = {
  strong_trend: 'bg-green-500/15 text-green-400 border-green-500/30',
  ranging: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  high_vol: 'bg-red-500/15 text-red-400 border-red-500/30',
  risk_on: 'bg-green-500/15 text-green-400 border-green-500/30',
  risk_off: 'bg-red-500/15 text-red-400 border-red-500/30',
  neutral: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  // Raw regime labels (from /api/v1/market/regime — used when no override)
  Exuberance: 'bg-green-500/15 text-green-400 border-green-500/30',
  'Risk-On': 'bg-green-500/15 text-green-400 border-green-500/30',
  Neutral: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  Cautious: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  'Risk-Off': 'bg-red-500/15 text-red-400 border-red-500/30',
  Crisis: 'bg-red-600/15 text-red-500 border-red-600/30',
};

function ScreenSectionView({
  section,
  expanded,
  onAddToWatchlist,
  onToggleExpand,
}: {
  section: ScreenSection;
  expanded: boolean;
  onAddToWatchlist: (symbol: string) => void;
  onToggleExpand: () => void;
}) {
  const visibleTickers = expanded ? section.tickers : section.tickers.slice(0, 3);

  return (
    <div className="rounded-lg border border-border bg-surface-secondary/50 overflow-hidden">
      {/* Section header */}
      <div className="flex items-center justify-between px-4 py-3 bg-surface-tertiary/30">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-text-primary">
            {section.screenLabel || section.screenName}
          </span>
          <span className="text-2xs px-1.5 py-0.5 rounded-full bg-accent/10 text-accent font-mono">
            {(section.regimeMatchScore * 100).toFixed(0)}% match
          </span>
        </div>
        {section.tickers.length > 3 && (
          <button
            onClick={onToggleExpand}
            className="flex items-center gap-1 text-xs text-text-muted hover:text-accent transition-colors"
          >
            {expanded ? (
              <>Show less <ChevronUp className="h-3 w-3" /></>
            ) : (
              <>See more ({section.tickers.length - 3} more) <ChevronDown className="h-3 w-3" /></>
            )}
          </button>
        )}
      </div>

      {/* Tickers grid */}
      <div className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {visibleTickers.map((ticker) => (
            <TickerCard
              key={ticker.symbol}
              ticker={ticker}
              onAddToWatchlist={onAddToWatchlist}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export function MorningBriefPage() {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const addNotification = useProModeStore((s) => s.addNotification);

  const { data: brief, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['morning-brief'],
    queryFn: fetchMorningBrief,
    staleTime: 5 * 60 * 1000, // 5 min
    retry: 2,
  });

  const handleAddToWatchlist = (symbol: string) => {
    addNotification({
      type: 'morning_brief',
      symbol,
      title: 'Added to Watchlist',
      message: `${symbol} added from Morning Brief`,
      read: false,
    });
  };

  const toggleSection = (name: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [name]: !prev[name],
    }));
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="p-6 max-w-7xl mx-auto space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-surface-tertiary rounded" />
        <div className="h-12 w-full bg-surface-tertiary rounded" />
        <div className="h-32 w-full bg-surface-tertiary rounded" />
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-64 bg-surface-tertiary rounded" />
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6 text-center">
          <AlertCircle className="h-8 w-8 text-red-400 mx-auto mb-2" />
          <h3 className="text-lg font-semibold text-text-primary mb-1">
            Morning Brief Unavailable
          </h3>
          <p className="text-sm text-text-muted mb-4">
            The brief generates at 6 AM ET on market days. Data may be refreshing.
          </p>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent/10 text-accent text-sm font-medium hover:bg-accent/20 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (!brief || !brief.screenSections?.length) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="rounded-lg border border-border bg-surface-secondary/50 p-8 text-center">
          <Sun className="h-12 w-12 text-accent mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-text-primary mb-1">
            No Morning Brief Yet
          </h3>
          <p className="text-sm text-text-muted">
            Your first morning brief will generate at 6 AM ET tomorrow.
            Check back then for your daily market snapshot.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-text-primary">Morning Brief</h1>
          <p className="text-xs text-text-muted">
            {new Date(brief.generatedAt).toLocaleDateString('en-US', {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })}
            {' '}· Data as of 4 PM close · Prices live pre-market
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-text-muted hover:text-accent hover:bg-surface-tertiary transition-colors disabled:opacity-50"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', isFetching && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Regime badge */}
      <div className="flex items-center gap-3">
        <div
          data-testid="regime-badge"
          className={cn(
            'inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-semibold',
            REGIME_COLORS[brief.regime] || REGIME_COLORS.neutral
          )}
        >
          {brief.regime.replace(/_/g, ' ').toUpperCase()}
        </div>
        <span className="text-sm text-text-muted">{brief.regimeDescription}</span>
        <EducationTooltip metricKey="market_regime" metricLabel="Market Regime" compact />
      </div>

      {/* Market Internals */}
      <MarketInternalsStrip internals={brief.marketInternals} />

      {/* Sector Rotation */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-text-primary">Sector Rotation</h2>
          <EducationTooltip metricKey="sector_rotation" metricLabel="Sector Rotation" compact />
        </div>
        <SectorFocusCard compact />
        <SectorHeatmapMini sectors={brief.sectors} />
      </div>

      {/* Screen sections */}
      <div className="space-y-4">
        <h2 className="text-sm font-semibold text-text-primary">
          Top Picks — {brief.screenSections.reduce((sum, s) => sum + s.tickers.length, 0)} tickers
        </h2>
        {brief.screenSections.map((section) => (
          <ScreenSectionView
            key={section.screenName}
            section={section}
            expanded={!!expandedSections[section.screenName]}
            onAddToWatchlist={handleAddToWatchlist}
            onToggleExpand={() => toggleSection(section.screenName)}
          />
        ))}
      </div>
    </div>
  );
}
