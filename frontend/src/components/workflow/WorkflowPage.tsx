import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useMarketRegime, useSectorRotation } from '@/hooks/useMarketRegime';
import { analyzePortfolio } from '@/api/workflow';
import type { PortfolioResponse, SymbolAllocation } from '@/api/workflow';
import { usePortfolioStore } from '@/store/portfolio';
import {
  TrendingUp, TrendingDown, Activity, Gauge, Search, BarChart3,
  Plus, X, Loader2, AlertTriangle, ChevronRight,
  Brain, PieChart,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatPrice } from '@/lib/format';
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

function actionColor(action: string): string {
  if (action === 'STRONG BUY' || action === 'BUY') return 'text-green-500 bg-green-500/10 border-green-500/30';
  if (action === 'ACCUMULATE') return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30';
  if (action === 'WATCH') return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30';
  if (action === 'HOLD') return 'text-orange-400 bg-orange-400/10 border-orange-400/30';
  if (action === 'REDUCE' || action === 'AVOID') return 'text-red-400 bg-red-400/10 border-red-400/30';
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
    <div className="rounded-xl border border-border/50 bg-surface/30 p-4 hover:border-accent/30 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <span className="text-lg font-bold text-text-primary">{analysis.symbol}</span>
        <span className={cn('text-[10px] font-semibold px-2 py-0.5 rounded-full border', actionColor(analysis.action))}>
          {analysis.action}
        </span>
      </div>
      <div className="flex items-center gap-2 text-xs text-text-muted mb-2">
        <span>c:{analysis.conviction}/10</span>
        <span className="text-text-muted/40">·</span>
        <span className={cn('font-medium', analysis.conviction >= 6 ? 'text-green-500' : analysis.conviction >= 4 ? 'text-yellow-400' : 'text-text-muted')}>
          {convictionLabel(analysis.conviction)}
        </span>
      </div>
      {analysis.sector && (
        <div className="text-[11px] text-text-muted">{analysis.sector}</div>
      )}
      {analysis.price != null && (
        <div className="text-xs text-text-muted mt-1">{formatPrice(analysis.price)}</div>
      )}
      {analysis.suggested_pct != null && analysis.suggested_pct > 0 && (
        <div className="mt-3 border-t border-border/30 pt-2 flex items-center justify-between text-xs">
          <span className="text-text-muted">Position</span>
          <span className="font-semibold text-text-primary">{analysis.suggested_pct}%</span>
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
  const [portfolioResult, setPortfolioResult] = useState<PortfolioResponse | null>(null);

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
  const sortedByChange = [...sectors].sort((a, b) => ((b.change_1d ?? 0)) - ((a.change_1d ?? 0)));
  const leaders = sortedByChange.slice(0, 3).map(s => s.symbol);
  const laggards = sortedByChange.slice(-3).map(s => s.symbol).reverse();

  // Strategy hint based on regime
  const strategyHint = (() => {
    if (!regimeLabel) return '';
    if (regimeLabel === 'Exuberance' || regimeLabel === 'Risk-On') return 'Trend/momentum bias — favor breakout screeners';
    if (regimeLabel === 'Neutral') return 'Quality/value bias — favor high-conviction stack';
    if (regimeLabel === 'Cautious') return 'Defensive bias — favor low-vol, mean-reversion screeners';
    if (regimeLabel === 'Risk-Off') return 'Capital preservation — favor oversold bounce screeners';
    if (regimeLabel === 'Crisis') return 'Avoid new positions — focus on existing risk management';
    return '';
  })();

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="border-b border-border bg-surface/50 px-4 py-3">
        <h1 className="font-display text-xl font-semibold tracking-tight text-text-primary flex items-center gap-2">
          <Activity className="h-5 w-5 text-accent" />
          Swing Trading Desk
        </h1>
        <p className="text-sm text-text-muted">Institutional workflow — market context → screen → analyze → portfolio</p>
      </div>

      <div className="flex-1 space-y-4 p-4 max-w-6xl mx-auto w-full">

        {/* ── Step 1: Market Context ── */}
        <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <Gauge className="h-4 w-4 text-accent" />
              Market Pulse
            </h2>
            {regimeScore != null && (
              <span className={cn('text-xs font-medium px-2 py-0.5 rounded-full border', regimeColor(regimeScore))}>
                {regimeLabel} · {regimeScore.toFixed(0)}/100
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Regime bar */}
            {regimeScore != null && (
              <div className="space-y-1">
                <div className="h-2 rounded-full bg-border overflow-hidden">
                  <div className={cn('h-full rounded-full transition-all', regimeBg(regimeScore))}
                    style={{ width: `${regimeScore}%` }} />
                </div>
                <p className="text-xs text-text-muted">{strategyHint}</p>
              </div>
            )}

            {/* Sector leaders */}
            {leaders.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold uppercase text-green-500 tracking-wider mb-1.5">Leading Sectors</p>
                <div className="flex flex-wrap gap-1.5">
                  {leaders.map((sym) => {
                    const s = sectors.find((x) => x.symbol === sym);
                    return (
                      <span key={sym} className="inline-flex items-center gap-1 text-xs text-green-500 bg-green-500/5 px-2 py-0.5 rounded-full">
                        <TrendingUp className="h-3 w-3" />
                        {s?.name || sym} {s?.change_1d != null ? `${s.change_1d > 0 ? '+' : ''}${s.change_1d.toFixed(1)}%` : ''}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Sector laggards */}
            {laggards.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold uppercase text-red-400 tracking-wider mb-1.5">Lagging Sectors</p>
                <div className="flex flex-wrap gap-1.5">
                  {laggards.map((sym) => {
                    const s = sectors.find((x) => x.symbol === sym);
                    return (
                      <span key={sym} className="inline-flex items-center gap-1 text-xs text-red-400 bg-red-400/5 px-2 py-0.5 rounded-full">
                        <TrendingDown className="h-3 w-3" />
                        {s?.name || sym} {s?.change_1d != null ? `${s.change_1d > 0 ? '+' : ''}${s.change_1d.toFixed(1)}%` : ''}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ── Step 2: Watchlist ── */}
        <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <Search className="h-4 w-4 text-accent" />
              Ticker Watchlist
            </h2>
            <span className="text-xs text-text-muted">{watchlist.length}/10</span>
          </div>

          <div className="flex items-center gap-2 mb-3">
            <input
              value={watchlistInput}
              onChange={(e) => setWatchlistInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Add ticker symbol (e.g. AMZN)"
              className="flex-1 bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50"
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
                  className="inline-flex items-center gap-1.5 bg-accent/10 border border-accent/20 rounded-full px-3 py-1 text-sm font-medium text-accent"
                >
                  {sym}
                  <button onClick={() => removeFromWatchlist(sym)} className="hover:text-loss transition-colors">
                    <X className="h-3.5 w-3.5" />
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-text-muted">Add 2–10 tickers to analyze as a portfolio</p>
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
                {portfolioQuery.isFetching ? 'Analyzing...' : `Analyze Portfolio (${watchlist.length})`}
              </button>
              {portfolioQuery.isError && (
                <span className="text-xs text-red-400 flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  Analysis failed — check symbols are valid
                </span>
              )}
            </div>
          )}
        </section>

        {/* ── Step 3: Results ── */}
        {portfolioResult && portfolioResult.analyses.length > 0 && (
          <>
            {/* Ticker Cards */}
            <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
              <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2 mb-3">
                <Brain className="h-4 w-4 text-accent" />
                Analysis Results
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
                {portfolioResult.analyses.map((a) => (
                  <TickerCard key={a.symbol} analysis={a} />
                ))}
              </div>
            </section>

            {/* Portfolio Summary */}
            <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
              <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2 mb-3">
                <PieChart className="h-4 w-4 text-accent" />
                Portfolio Summary
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Combined Beta */}
                {portfolioResult.combined_beta != null && (
                  <div className="bg-surface/30 border border-border/30 rounded-lg p-3">
                    <div className="text-[10px] font-semibold uppercase text-text-muted tracking-wider mb-1">Combined Beta</div>
                    <div className={cn(
                      'text-lg font-bold',
                      portfolioResult.combined_beta > 1 ? 'text-orange-400' : portfolioResult.combined_beta > 0.8 ? 'text-green-500' : 'text-text-muted'
                    )}>
                      {portfolioResult.combined_beta.toFixed(2)}
                    </div>
                    <div className="text-[10px] text-text-muted mt-0.5">
                      {portfolioResult.combined_beta > 1 ? 'Above market risk' : portfolioResult.combined_beta > 0.8 ? 'Near market' : 'Below market risk'}
                    </div>
                  </div>
                )}

                {/* Portfolio Volatility */}
                {portfolioResult.portfolio_volatility != null && (
                  <div className="bg-surface/30 border border-border/30 rounded-lg p-3">
                    <div className="text-[10px] font-semibold uppercase text-text-muted tracking-wider mb-1">Portfolio Volatility</div>
                    <div className="text-lg font-bold text-text-primary">{portfolioResult.portfolio_volatility.toFixed(1)}%</div>
                    <div className="text-[10px] text-text-muted mt-0.5">Annualized (equal weight)</div>
                  </div>
                )}

                {/* Position Size */}
                {portfolioResult.equal_risk_pct != null && (
                  <div className="bg-surface/30 border border-border/30 rounded-lg p-3">
                    <div className="text-[10px] font-semibold uppercase text-text-muted tracking-wider mb-1">Per-Position Size</div>
                    <div className="text-lg font-bold text-text-primary">{portfolioResult.equal_risk_pct}%</div>
                    <div className="text-[10px] text-text-muted mt-0.5">Equal risk allocation</div>
                  </div>
                )}

                {/* Sector Allocation */}
                {Object.keys(portfolioResult.sector_allocation).length > 0 && (
                  <div className="bg-surface/30 border border-border/30 rounded-lg p-3">
                    <div className="text-[10px] font-semibold uppercase text-text-muted tracking-wider mb-1">Sector Allocation</div>
                    <div className="space-y-1">
                      {Object.entries(portfolioResult.sector_allocation).map(([sector, pct]) => (
                        <div key={sector} className="flex items-center justify-between text-xs">
                          <span className="text-text-primary">{sector}</span>
                          <span className="font-mono text-text-muted">{pct.toFixed(0)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* High Correlation Warnings */}
              {portfolioResult.high_correlation_pairs.length > 0 && (
                <div className="mt-4 bg-red-400/5 border border-red-400/20 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-red-400 mb-1.5">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    High Correlation Warning
                  </div>
                  <p className="text-xs text-text-muted">
                    These pairs have correlation {'>'} 0.7 — they may move together, reducing diversification:
                  </p>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {portfolioResult.high_correlation_pairs.map((pair) => (
                      <span key={`${pair.a}-${pair.b}`} className="text-xs text-red-400 bg-red-400/5 px-2 py-0.5 rounded-full">
                        {pair.a} × {pair.b} (r={pair.r.toFixed(2)})
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Correlation Matrix */}
              {portfolioResult.correlation_matrix.length > 0 && (
                <div className="mt-4">
                  <p className="text-[10px] font-semibold uppercase text-text-muted tracking-wider mb-2">Correlation Matrix</p>
                  <div className="overflow-x-auto">
                    <table className="text-xs">
                      <thead>
                        <tr className="text-text-muted">
                          <th className="pr-3 pb-1 text-left">Pair</th>
                          <th className="pb-1 text-right">r</th>
                        </tr>
                      </thead>
                      <tbody>
                        {portfolioResult.correlation_matrix.map((pair) => {
                          const absR = Math.abs(pair.r);
                          const corrColor = absR > 0.7 ? 'text-red-400' : absR > 0.4 ? 'text-yellow-400' : 'text-green-500';
                          return (
                            <tr key={`${pair.a}-${pair.b}`} className="border-b border-border/20">
                              <td className="py-1 pr-3 text-text-primary">{pair.a} × {pair.b}</td>
                              <td className={cn('py-1 text-right font-mono', corrColor)}>{pair.r.toFixed(3)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </section>

            {/* Action: Go to ticker analysis */}
            <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
              <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2 mb-3">
                <ChevronRight className="h-4 w-4 text-accent" />
                Next Steps
              </h2>
              <div className="flex flex-wrap gap-2">
                {portfolioResult.analyses.map((a) => (
                  <button
                    key={a.symbol}
                    onClick={() => navigate(`/ticker/${a.symbol}`)}
                    className="flex items-center gap-1.5 text-xs bg-accent/5 border border-accent/20 hover:bg-accent/10 rounded-lg px-3 py-2 text-accent transition-colors"
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
            <Loader2 className="h-8 w-8 text-accent animate-spin" />
            <span className="ml-3 text-sm text-text-muted">Analyzing portfolio...</span>
          </div>
        )}

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
