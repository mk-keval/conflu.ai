import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useMarketRegime, useSectorRotation } from '@/hooks/useMarketRegime';
import { fetchMarketEvents, fetchMarketNarrative } from '@/api/market';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Search,
  BarChart3,
  Calendar,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { TermLink } from '@/components/learn/TermLink';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';

function regimeColor(score: number): string {
  if (score >= 65) return 'text-green-400';
  if (score >= 50) return 'text-yellow-400';
  if (score >= 35) return 'text-orange-400';
  return 'text-red-400';
}

function regimeBg(score: number): string {
  if (score >= 65) return 'bg-green-500';
  if (score >= 50) return 'bg-yellow-400';
  if (score >= 35) return 'bg-orange-400';
  return 'bg-red-500';
}

function importanceColor(imp: string): string {
  if (imp === 'high') return 'text-red-400 bg-red-400/10';
  if (imp === 'medium') return 'text-yellow-400 bg-yellow-400/10';
  return 'text-text-muted bg-surface-tertiary/50';
}

function DashboardContent() {
  const navigate = useNavigate();

  // ── Fetch all dashboard data in parallel ──
  const { data: regime } = useMarketRegime();

  const { data: sectorRotation } = useSectorRotation();

  const { data: eventsData } = useQuery({
    queryKey: ['market-events'],
    queryFn: fetchMarketEvents,
    staleTime: 86_400_000, // 24h
  });

  const { data: narrativeData } = useQuery({
    queryKey: ['market-narrative'],
    queryFn: fetchMarketNarrative,
    staleTime: 3_600_000,
  });

  const events = eventsData?.events ?? [];
  const narrative = narrativeData?.narrative ?? '';
  const sectors = sectorRotation?.sectors ?? [];
  // Sort sectors by 1D change so "Leading"/"Lagging" match the Sector Rotation page's "Top Gainers"
  const sortedByChange = [...sectors].sort(
    (a, b) => (b.change_1d ?? 0) - (a.change_1d ?? 0)
  );
  const leaders = sortedByChange.slice(0, 4).map((s) => s.symbol);
  const laggards = sortedByChange
    .slice(-4)
    .map((s) => s.symbol)
    .reverse();
  const comp = regime?.composite_score ?? null;
  const label = regime?.regime_label ?? null;
  const vixVal = regime?.vix?.value ?? null;

  // Regime-based strategy hint
  const strategyHint = (() => {
    if (!label) return '';
    if (label === 'Exuberance' || label === 'Risk-On')
      return 'Trend/momentum screeners recommended';
    if (label === 'Neutral') return 'Quality/value screeners preferred';
    if (label === 'Cautious')
      return 'Defensive/mean-reversion screeners suggested';
    if (label === 'Risk-Off') return 'Oversold bounce & distribution screeners';
    if (label === 'Crisis') return 'Avoid new positions — capital preservation';
    return '';
  })();

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="border-b border-border bg-surface/50 px-4 py-3">
        <h1 className="flex items-center gap-2 font-display text-xl font-semibold tracking-tight text-text-primary">
          <Activity className="h-5 w-5 text-accent" />
          Dashboard
        </h1>
        <p className="text-sm text-text-muted">
          Market context at a glance — then choose your focus
        </p>
      </div>

      <div className="mx-auto w-full max-w-6xl flex-1 space-y-4 p-4">
        {/* ── Narrative ── */}
        {narrative && (
          <div className="rounded-lg border border-accent/10 bg-accent/5 px-4 py-3 text-sm leading-relaxed text-text-secondary">
            {narrative}
          </div>
        )}

        {/* ── Regime Cards ── */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {/* Composite Score */}
          <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Market Regime
            </div>
            {comp != null ? (
              <>
                <div className={cn('text-lg font-bold', regimeColor(comp))}>
                  <TermLink text={label ?? ''} />
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-border">
                  <div
                    className={cn('h-full rounded-full', regimeBg(comp))}
                    style={{ width: `${comp}%` }}
                  />
                </div>
                <div className="mt-1 text-xs text-text-muted">
                  {comp.toFixed(0)}/100
                </div>
              </>
            ) : (
              <div className="text-sm text-text-muted">Loading...</div>
            )}
          </div>

          {/* VIX */}
          <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              VIX
            </div>
            {vixVal != null ? (
              <>
                <div
                  className={cn(
                    'text-lg font-bold',
                    vixVal > 25
                      ? 'text-red-400'
                      : vixVal > 18
                        ? 'text-yellow-400'
                        : 'text-green-500'
                  )}
                >
                  {vixVal.toFixed(1)}
                </div>
                <div className="mt-1 text-xs text-text-muted">
                  {vixVal > 25
                    ? 'Elevated — caution'
                    : vixVal > 18
                      ? 'Moderate'
                      : 'Low — favorable'}
                </div>
              </>
            ) : (
              <div className="text-sm text-text-muted">Loading...</div>
            )}
          </div>

          {/* Strategy */}
          <div className="rounded-xl border border-border/50 bg-surface/20 p-4 md:col-span-2">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Suggested Strategy
            </div>
            <p className="text-sm font-medium text-text-primary">
              {strategyHint || 'Loading...'}
            </p>
          </div>
        </div>

        {/* ── Sector Rotation ── */}
        <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
              <BarChart3 className="h-4 w-4 text-accent" />
              Sector Rotation
            </h2>
            <button
              onClick={() => navigate('/sector-rotation')}
              className="flex items-center gap-1 text-xs text-accent hover:text-accent/80"
            >
              Full view <ChevronRight className="h-3 w-3" />
            </button>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* Leaders */}
            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-green-500">
                Leading
              </p>
              <div className="space-y-1.5">
                {leaders.slice(0, 4).map((sym) => {
                  const s = sectors.find((x) => x.symbol === sym);
                  const change = s?.change_1d ?? 0;
                  return (
                    <div
                      key={sym}
                      className="flex items-center justify-between text-sm"
                    >
                      <span className="flex items-center gap-2">
                        <TrendingUp className="h-3.5 w-3.5 text-green-500" />
                        <span className="text-text-primary">
                          {s?.name || sym}
                        </span>
                      </span>
                      <span
                        className={cn(
                          'font-mono text-xs',
                          change >= 0 ? 'text-green-500' : 'text-red-400'
                        )}
                      >
                        {change >= 0 ? '+' : ''}
                        {change.toFixed(1)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Laggards */}
            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-red-400">
                Lagging
              </p>
              <div className="space-y-1.5">
                {laggards.slice(0, 4).map((sym) => {
                  const s = sectors.find((x) => x.symbol === sym);
                  const change = s?.change_1d ?? 0;
                  return (
                    <div
                      key={sym}
                      className="flex items-center justify-between text-sm"
                    >
                      <span className="flex items-center gap-2">
                        <TrendingDown className="h-3.5 w-3.5 text-red-400" />
                        <span className="text-text-primary">
                          {s?.name || sym}
                        </span>
                      </span>
                      <span
                        className={cn(
                          'font-mono text-xs',
                          change >= 0 ? 'text-green-500' : 'text-red-400'
                        )}
                      >
                        {change >= 0 ? '+' : ''}
                        {change.toFixed(1)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* ── Quick Actions ── */}
        <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Search className="h-4 w-4 text-accent" />
            Start Here
          </h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <QuickActionButton
              icon={<Search className="h-4 w-4" />}
              label="Run Screener"
              sub="Browse all configs"
              onClick={() => navigate('/screener')}
            />
            <QuickActionButton
              icon={<BarChart3 className="h-4 w-4" />}
              label="Sector Rotation"
              sub="See leading/lagging"
              onClick={() => navigate('/sector-rotation')}
            />
            <QuickActionButton
              icon={<TrendingUp className="h-4 w-4" />}
              label="Swing Desk"
              sub="Full workflow"
              onClick={() => navigate('/workflow')}
            />
            <QuickActionButton
              icon={<Activity className="h-4 w-4" />}
              label="Ticker Analysis"
              sub="Deep dive any symbol"
              onClick={() => navigate('/ticker')}
            />
          </div>
        </div>

        {/* ── Upcoming Events ── */}
        {events.length > 0 && (
          <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
              <Calendar className="h-4 w-4 text-accent" />
              Upcoming Events
            </h2>
            <div className="divide-y divide-border/30">
              {events.slice(0, 5).map((event, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between py-2 first:pt-0 last:pb-0"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        'rounded px-1.5 py-0.5 text-[10px] font-semibold',
                        importanceColor(event.importance)
                      )}
                    >
                      {event.importance === 'high' ? 'HIGH' : 'MED'}
                    </span>
                    <div>
                      <div className="text-sm text-text-primary">
                        {event.title}
                      </div>
                      <div className="text-xs text-text-muted">
                        {event.description}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div
                      className={cn(
                        'font-mono text-sm font-bold',
                        event.days_until <= 3
                          ? 'text-orange-400'
                          : event.days_until <= 7
                            ? 'text-yellow-400'
                            : 'text-text-muted'
                      )}
                    >
                      {event.days_until}d
                    </div>
                    <div className="text-[10px] text-text-muted">
                      {event.date}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function QuickActionButton({
  icon,
  label,
  sub,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  sub: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-1 rounded-xl border border-border/50 bg-surface/30 p-4 text-center transition-colors hover:border-accent/30 hover:bg-surface/50"
    >
      <span className="text-accent">{icon}</span>
      <span className="text-sm font-medium text-text-primary">{label}</span>
      <span className="text-[10px] text-text-muted">{sub}</span>
    </button>
  );
}

export function DashboardPage() {
  return (
    <ErrorBoundary>
      <DashboardContent />
    </ErrorBoundary>
  );
}
