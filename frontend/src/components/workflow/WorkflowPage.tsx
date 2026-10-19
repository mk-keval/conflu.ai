import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useMarketRegime, useSectorRotation } from '@/hooks/useMarketRegime';
import { analyzePortfolio } from '@/api/workflow';
import type { PortfolioResponse, SymbolAllocation } from '@/api/workflow';
import { usePortfolioStore } from '@/store/portfolio';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Gauge,
  Search,
  BarChart3,
  Plus,
  X,
  Loader2,
  AlertTriangle,
  ChevronRight,
  Brain,
  PieChart,
  CalendarCheck2,
  Target,
  BookOpen,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatPrice } from '@/lib/format';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { DailyRoutine } from './DailyRoutine';
import { AdherenceDashboard } from './AdherenceDashboard';
import { ExpectancyMeter } from './ExpectancyMeter';
import { OpenPositionsTracker } from './OpenPositionsTracker';
import { JournalTab } from './JournalTab';

type TabId = 'market' | 'dashboard' | 'routine' | 'watchlist' | 'portfolio' | 'adherence' | 'journal';

const TABS: { id: TabId; label: string; icon: typeof Gauge }[] = [
  { id: 'market', label: 'Market Context', icon: Gauge },
  { id: 'dashboard', label: 'Dashboard', icon: Target },
  { id: 'journal', label: 'Journal', icon: BookOpen },
  { id: 'routine', label: 'Daily Routine', icon: CalendarCheck2 },
  { id: 'watchlist', label: 'Watchlist', icon: Search },
  { id: 'portfolio', label: 'Portfolio', icon: PieChart },
  { id: 'adherence', label: 'Skill Score', icon: Target },
];

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

function actionColor(action: string): string {
  if (action === 'STRONG BUY' || action === 'BUY')
    return 'text-green-500 bg-green-500/10 border-green-500/30';
  if (action === 'ACCUMULATE')
    return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30';
  if (action === 'WATCH')
    return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30';
  if (action === 'HOLD')
    return 'text-orange-400 bg-orange-400/10 border-orange-400/30';
  if (action === 'REDUCE' || action === 'AVOID')
    return 'text-red-400 bg-red-400/10 border-red-400/30';
  return 'text-text-muted bg-surface-tertiary/50 border-border/50';
}

function convictionLabel(c: number): string {
  if (c >= 8) return 'Very High';
  if (c >= 6) return 'High';
  if (c >= 4) return 'Moderate';
  if (c >= 2) return 'Low';
  return 'Very Low';
}

// ── Mini Ticker Card ──

function TickerCard({ analysis }: { analysis: SymbolAllocation }) {
  return (
    <div className="rounded-xl border border-border/50 bg-surface/30 p-4 transition-colors hover:border-accent/30">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-lg font-bold text-text-primary">
          {analysis.symbol}
        </span>
        <span
          className={cn(
            'rounded-full border px-2 py-0.5 text-[10px] font-semibold',
            actionColor(analysis.action)
          )}
        >
          {analysis.action}
        </span>
      </div>
      <div className="mb-2 flex items-center gap-2 text-xs text-text-muted">
        <span>c:{analysis.conviction}/10</span>
        <span className="text-text-muted/40">·</span>
        <span
          className={cn(
            'font-medium',
            analysis.conviction >= 6
              ? 'text-green-500'
              : analysis.conviction >= 4
                ? 'text-yellow-400'
                : 'text-text-muted'
          )}
        >
          {convictionLabel(analysis.conviction)}
        </span>
      </div>
      {analysis.sector && (
        <div className="text-[11px] text-text-muted">{analysis.sector}</div>
      )}
      {analysis.price != null && (
        <div className="mt-1 text-xs text-text-muted">
          {formatPrice(analysis.price)}
        </div>
      )}
      {analysis.suggested_pct != null && analysis.suggested_pct > 0 && (
        <div className="mt-3 flex items-center justify-between border-t border-border/30 pt-2 text-xs">
          <span className="text-text-muted">Position</span>
          <span className="font-semibold text-text-primary">
            {analysis.suggested_pct}%
          </span>
        </div>
      )}
    </div>
  );
}

// ── Main Workflow Page ──

function WorkflowContent() {
  const navigate = useNavigate();

  // ── Watchlist state — synced with portfolio store ──
  const [watchlistInput, setWatchlistInput] = useState('');
  const portfolioStore = usePortfolioStore();
  const [watchlist, setWatchlist] = useState<string[]>(() =>
    portfolioStore.items.map((i) => i.symbol)
  );

  // Sync watchlist changes back to portfolio store
  useEffect(() => {
    for (const sym of watchlist) {
      if (!portfolioStore.hasSymbol(sym)) portfolioStore.addSymbol(sym);
    }
  }, [watchlist]);

  // ── Portfolio results ──
  const [portfolioResult, setPortfolioResult] =
    useState<PortfolioResponse | null>(null);

  // ── Active desktop tab ──
  const [activeTab, setActiveTab] = useState<TabId>('market');

  // ── Market regime ──
  const { data: regime } = useMarketRegime();

  // ── Sector rotation ──
  const { data: sectorRotation } = useSectorRotation();

  // ── Portfolio analysis query ──
  const portfolioQuery = useQuery({
    queryKey: ['portfolio-analysis', watchlist],
    queryFn: () => analyzePortfolio(watchlist),
    enabled: watchlist.length > 0,
    staleTime: 60_000,
    retry: 1,
  });

  // Update portfolio result when query succeeds
  useEffect(() => {
    if (portfolioQuery.data) {
      setPortfolioResult(portfolioQuery.data);
    }
  }, [portfolioQuery.data]);

  const addToWatchlist = useCallback(() => {
    const sym = watchlistInput.trim().toUpperCase();
    if (sym && !watchlist.includes(sym) && watchlist.length < 10) {
      setWatchlist((prev) => [...prev, sym]);
      setWatchlistInput('');
    }
  }, [watchlistInput, watchlist]);

  const removeFromWatchlist = useCallback((sym: string) => {
    setWatchlist((prev) => prev.filter((s) => s !== sym));
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') addToWatchlist();
  };

  const regimeScore = regime?.composite_score ?? null;
  const regimeLabel = regime?.regime_label ?? null;
  const sectors = sectorRotation?.sectors ?? [];
  // Sort by 1D change so "Leading"/"Lagging" match the metric shown next to them
  const sortedByChange = [...sectors].sort(
    (a, b) => (b.change_1d ?? 0) - (a.change_1d ?? 0)
  );
  const leaders = sortedByChange.slice(0, 3).map((s) => s.symbol);
  const laggards = sortedByChange
    .slice(-3)
    .map((s) => s.symbol)
    .reverse();

  // Strategy hint based on regime
  const strategyHint = (() => {
    if (!regimeLabel) return '';
    if (regimeLabel === 'Exuberance' || regimeLabel === 'Risk-On')
      return 'Trend/momentum bias — favor breakout screeners';
    if (regimeLabel === 'Neutral')
      return 'Quality/value bias — favor high-conviction stack';
    if (regimeLabel === 'Cautious')
      return 'Defensive bias — favor low-vol, mean-reversion screeners';
    if (regimeLabel === 'Risk-Off')
      return 'Capital preservation — favor oversold bounce screeners';
    if (regimeLabel === 'Crisis')
      return 'Avoid new positions — focus on existing risk management';
    return '';
  })();

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border bg-surface/50 px-4 py-3">
        <h1 className="flex items-center gap-2 font-display text-xl font-semibold tracking-tight text-text-primary">
          <Activity className="h-5 w-5 text-accent" />
          Swing Trading Desk
        </h1>
        <p className="text-sm text-text-muted">
          Institutional workflow — market context → daily routine → screen →
          analyze → portfolio
        </p>
      </div>

      <div className="flex min-h-0 flex-1">
        {/* ── Sidebar tab rail ── */}
        <nav className="hidden w-48 shrink-0 flex-col gap-1 border-r border-border bg-surface/40 p-3 md:flex">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors',
                  isActive
                    ? 'border border-accent/30 bg-accent/10 text-accent'
                    : 'border border-transparent text-text-muted hover:bg-surface/40 hover:text-text-primary'
                )}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        {/* ── Mobile tab bar ── */}
        <div className="flex gap-1 overflow-x-auto border-b border-border bg-surface/40 px-2 py-2 md:hidden">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs transition-colors',
                  isActive
                    ? 'border border-accent/30 bg-accent/10 text-accent'
                    : 'border border-transparent text-text-muted'
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* ── Active panel ── */}
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto flex h-full w-full max-w-6xl flex-col space-y-4 p-4">
            {/* ── Tab: Market Context ── */}
            {activeTab === 'market' && (
              <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                    <Gauge className="h-4 w-4 text-accent" />
                    Market Pulse
                  </h2>
                  {regimeScore != null && (
                    <span
                      className={cn(
                        'rounded-full border px-2 py-0.5 text-xs font-medium',
                        regimeColor(regimeScore)
                      )}
                    >
                      {regimeLabel} · {regimeScore.toFixed(0)}/100
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  {/* Regime bar */}
                  {regimeScore != null && (
                    <div className="space-y-1">
                      <div className="h-2 overflow-hidden rounded-full bg-border">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            regimeBg(regimeScore)
                          )}
                          style={{ width: `${regimeScore}%` }}
                        />
                      </div>
                      <p className="text-xs text-text-muted">{strategyHint}</p>
                    </div>
                  )}

                  {/* Sector leaders */}
                  {leaders.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-green-500">
                        Leading Sectors
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {leaders.map((sym) => {
                          const s = sectors.find((x) => x.symbol === sym);
                          return (
                            <span
                              key={sym}
                              className="inline-flex items-center gap-1 rounded-full bg-green-500/5 px-2 py-0.5 text-xs text-green-500"
                            >
                              <TrendingUp className="h-3 w-3" />
                              {s?.name || sym}{' '}
                              {s?.change_1d != null
                                ? `${s.change_1d > 0 ? '+' : ''}${s.change_1d.toFixed(1)}%`
                                : ''}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Sector laggards */}
                  {laggards.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-red-400">
                        Lagging Sectors
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {laggards.map((sym) => {
                          const s = sectors.find((x) => x.symbol === sym);
                          return (
                            <span
                              key={sym}
                              className="inline-flex items-center gap-1 rounded-full bg-red-400/5 px-2 py-0.5 text-xs text-red-400"
                            >
                              <TrendingDown className="h-3 w-3" />
                              {s?.name || sym}{' '}
                              {s?.change_1d != null
                                ? `${s.change_1d > 0 ? '+' : ''}${s.change_1d.toFixed(1)}%`
                                : ''}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* ── Tab: Daily Routine ── */}
            {activeTab === 'routine' && <DailyRoutine />}

            {/* ── Tab: Watchlist ── */}
            {activeTab === 'watchlist' && (
              <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                    <Search className="h-4 w-4 text-accent" />
                    Ticker Watchlist
                  </h2>
                  <span className="text-xs text-text-muted">
                    {watchlist.length}/10
                  </span>
                </div>

                <div className="mb-3 flex items-center gap-2">
                  <input
                    value={watchlistInput}
                    onChange={(e) => setWatchlistInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Add ticker symbol (e.g. AMZN)"
                    className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted focus:border-accent/50"
                    maxLength={10}
                  />
                  <button
                    onClick={addToWatchlist}
                    disabled={!watchlistInput.trim() || watchlist.length >= 10}
                    className="btn-primary gap-1.5 px-3 py-2 text-sm disabled:opacity-40"
                  >
                    <Plus className="h-4 w-4" />
                    Add
                  </button>
                </div>

                {watchlist.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {watchlist.map((sym) => (
                      <span
                        key={sym}
                        className="inline-flex items-center gap-1.5 rounded-full border border-accent/20 bg-accent/10 px-3 py-1 text-sm font-medium text-accent"
                      >
                        {sym}
                        <button
                          onClick={() => removeFromWatchlist(sym)}
                          className="transition-colors hover:text-loss"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-text-muted">
                    Add 2–10 tickers to analyze as a portfolio
                  </p>
                )}

                {/* Analyze button */}
                {watchlist.length >= 2 && (
                  <div className="mt-4 flex items-center gap-2">
                    <button
                      onClick={() => portfolioQuery.refetch()}
                      disabled={portfolioQuery.isFetching}
                      className="btn-primary gap-2"
                    >
                      {portfolioQuery.isFetching ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <BarChart3 className="h-4 w-4" />
                      )}
                      {portfolioQuery.isFetching
                        ? 'Analyzing...'
                        : `Analyze Portfolio (${watchlist.length})`}
                    </button>
                    {portfolioQuery.isError && (
                      <span className="flex items-center gap-1 text-xs text-red-400">
                        <AlertTriangle className="h-3 w-3" />
                        Analysis failed — check symbols are valid
                      </span>
                    )}
                  </div>
                )}
              </section>
            )}

            {/* ── Tab: Portfolio ── */}
            {activeTab === 'portfolio' && (
              <>
                {/* ── Step 3: Results ── */}
                {portfolioResult && portfolioResult.analyses.length > 0 && (
                  <>
                    {/* Ticker Cards */}
                    <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
                      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
                        <Brain className="h-4 w-4 text-accent" />
                        Analysis Results
                      </h2>
                      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                        {portfolioResult.analyses.map((a) => (
                          <TickerCard key={a.symbol} analysis={a} />
                        ))}
                      </div>
                    </section>

                    {/* Portfolio Summary */}
                    <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
                      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
                        <PieChart className="h-4 w-4 text-accent" />
                        Portfolio Summary
                      </h2>

                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                        {/* Combined Beta */}
                        {portfolioResult.combined_beta != null && (
                          <div className="rounded-lg border border-border/30 bg-surface/30 p-3">
                            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                              Combined Beta
                            </div>
                            <div
                              className={cn(
                                'text-lg font-bold',
                                portfolioResult.combined_beta > 1
                                  ? 'text-orange-400'
                                  : portfolioResult.combined_beta > 0.8
                                    ? 'text-green-500'
                                    : 'text-text-muted'
                              )}
                            >
                              {portfolioResult.combined_beta.toFixed(2)}
                            </div>
                            <div className="mt-0.5 text-[10px] text-text-muted">
                              {portfolioResult.combined_beta > 1
                                ? 'Above market risk'
                                : portfolioResult.combined_beta > 0.8
                                  ? 'Near market'
                                  : 'Below market risk'}
                            </div>
                          </div>
                        )}

                        {/* Portfolio Volatility */}
                        {portfolioResult.portfolio_volatility != null && (
                          <div className="rounded-lg border border-border/30 bg-surface/30 p-3">
                            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                              Portfolio Volatility
                            </div>
                            <div className="text-lg font-bold text-text-primary">
                              {portfolioResult.portfolio_volatility.toFixed(1)}%
                            </div>
                            <div className="mt-0.5 text-[10px] text-text-muted">
                              Annualized (equal weight)
                            </div>
                          </div>
                        )}

                        {/* Position Size */}
                        {portfolioResult.equal_risk_pct != null && (
                          <div className="rounded-lg border border-border/30 bg-surface/30 p-3">
                            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                              Per-Position Size
                            </div>
                            <div className="text-lg font-bold text-text-primary">
                              {portfolioResult.equal_risk_pct}%
                            </div>
                            <div className="mt-0.5 text-[10px] text-text-muted">
                              Equal risk allocation
                            </div>
                          </div>
                        )}

                        {/* Sector Allocation */}
                        {Object.keys(portfolioResult.sector_allocation).length >
                          0 && (
                          <div className="rounded-lg border border-border/30 bg-surface/30 p-3">
                            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                              Sector Allocation
                            </div>
                            <div className="space-y-1">
                              {Object.entries(
                                portfolioResult.sector_allocation
                              ).map(([sector, pct]) => (
                                <div
                                  key={sector}
                                  className="flex items-center justify-between text-xs"
                                >
                                  <span className="text-text-primary">
                                    {sector}
                                  </span>
                                  <span className="font-mono text-text-muted">
                                    {pct.toFixed(0)}%
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* High Correlation Warnings */}
                      {portfolioResult.high_correlation_pairs.length > 0 && (
                        <div className="mt-4 rounded-lg border border-red-400/20 bg-red-400/5 p-3">
                          <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-red-400">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            High Correlation Warning
                          </div>
                          <p className="text-xs text-text-muted">
                            These pairs have correlation {'>'} 0.7 — they may
                            move together, reducing diversification:
                          </p>
                          <div className="mt-1 flex flex-wrap gap-2">
                            {portfolioResult.high_correlation_pairs.map(
                              (pair) => (
                                <span
                                  key={`${pair.a}-${pair.b}`}
                                  className="rounded-full bg-red-400/5 px-2 py-0.5 text-xs text-red-400"
                                >
                                  {pair.a} × {pair.b} (r={pair.r.toFixed(2)})
                                </span>
                              )
                            )}
                          </div>
                        </div>
                      )}

                      {/* Correlation Matrix */}
                      {portfolioResult.correlation_matrix.length > 0 && (
                        <div className="mt-4">
                          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                            Correlation Matrix
                          </p>
                          <div className="overflow-x-auto">
                            <table className="text-xs">
                              <thead>
                                <tr className="text-text-muted">
                                  <th className="pb-1 pr-3 text-left">Pair</th>
                                  <th className="pb-1 text-right">r</th>
                                </tr>
                              </thead>
                              <tbody>
                                {portfolioResult.correlation_matrix.map(
                                  (pair) => {
                                    const absR = Math.abs(pair.r);
                                    const corrColor =
                                      absR > 0.7
                                        ? 'text-red-400'
                                        : absR > 0.4
                                          ? 'text-yellow-400'
                                          : 'text-green-500';
                                    return (
                                      <tr
                                        key={`${pair.a}-${pair.b}`}
                                        className="border-b border-border/20"
                                      >
                                        <td className="py-1 pr-3 text-text-primary">
                                          {pair.a} × {pair.b}
                                        </td>
                                        <td
                                          className={cn(
                                            'py-1 text-right font-mono',
                                            corrColor
                                          )}
                                        >
                                          {pair.r.toFixed(3)}
                                        </td>
                                      </tr>
                                    );
                                  }
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </section>

                    {/* Action: Go to ticker analysis */}
                    <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
                      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
                        <ChevronRight className="h-4 w-4 text-accent" />
                        Next Steps
                      </h2>
                      <div className="flex flex-wrap gap-2">
                        {portfolioResult.analyses.map((a) => (
                          <button
                            key={a.symbol}
                            onClick={() => navigate(`/ticker/${a.symbol}`)}
                            className="flex items-center gap-1.5 rounded-lg border border-accent/20 bg-accent/5 px-3 py-2 text-xs text-accent transition-colors hover:bg-accent/10"
                          >
                            Full analysis: {a.symbol}
                            <ChevronRight className="h-3 w-3" />
                          </button>
                        ))}
                      </div>
                    </section>
                  </>
                )}

                {/* Loading state */}
                {portfolioQuery.isFetching && (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-accent" />
                    <span className="ml-3 text-sm text-text-muted">
                      Analyzing portfolio...
                    </span>
                  </div>
                )}
              </>
            )}

            {/* ── Tab: Dashboard (Expectancy + Open Positions) ── */}
            {activeTab === 'dashboard' && (
              <>
                <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
                  <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
                    <Target className="h-4 w-4 text-accent" />
                    Dashboard — Expectancy & Open Positions
                  </h2>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <ExpectancyMeter />
                    <OpenPositionsTracker />
                  </div>
                </section>
              </>
            )}

            {/* ── Tab: Journal (SQLite of record — D-68) ── */}
            {activeTab === 'journal' && <JournalTab />}

            {/* ── Tab: Skill Score (Adherence Dashboard) ── */}
            {activeTab === 'adherence' && <AdherenceDashboard />}
          </div>
        </div>
      </div>
    </div>
  );
}

export function WorkflowPage() {
  return (
    <ErrorBoundary>
      <WorkflowContent />
    </ErrorBoundary>
  );
}
