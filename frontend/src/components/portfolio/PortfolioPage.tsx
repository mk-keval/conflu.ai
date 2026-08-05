import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { analyzePortfolio } from '@/api/workflow';
import { usePortfolioStore } from '@/store/portfolio';
import {
  PieChart, BarChart3, X, Loader2, AlertTriangle, ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatPrice } from '@/lib/format';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';

function PortfolioContent() {
  const navigate = useNavigate();
  const { items, removeSymbol, clearAll } = usePortfolioStore();
  const symbols = useMemo(() => items.map((i) => i.symbol), [items]);

  const { data, isFetching, isError, refetch } = useQuery({
    queryKey: ['portfolio-analysis', symbols],
    queryFn: () => analyzePortfolio(symbols),
    enabled: symbols.length >= 2,
    staleTime: 30_000,
    retry: 1,
  });

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="border-b border-border bg-surface/50 px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-text-primary flex items-center gap-2">
            <PieChart className="h-5 w-5 text-accent" />
            Portfolio
          </h1>
          <p className="text-sm text-text-muted">{items.length} ticker{items.length !== 1 ? 's' : ''} tracked</p>
        </div>
        <div className="flex items-center gap-2">
          {items.length > 0 && (
            <button onClick={clearAll} className="btn-ghost text-xs text-red-400 hover:text-red-300 px-2 py-1">
              Clear all
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 space-y-4 p-4 max-w-5xl mx-auto w-full">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[40vh] text-center">
            <PieChart className="w-16 h-16 text-text-muted/30 mb-4" />
            <h2 className="text-lg font-semibold text-text-primary mb-2">No tickers yet</h2>
            <p className="text-sm text-text-muted mb-6 max-w-md">
              Add tickers from the Ticker Analysis page using the "Add to Portfolio" button.
            </p>
            <div className="flex gap-3">
              <button onClick={() => navigate('/dashboard')} className="btn-primary">
                Dashboard
              </button>
              <button onClick={() => navigate('/screener')} className="btn-ghost">
                Run Screener
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Ticker cards */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {items.map((item) => {
                const analysis = data?.analyses.find((a) => a.symbol === item.symbol);
                return (
                  <div key={item.symbol} className="rounded-xl border border-border/50 bg-surface/20 p-4 hover:border-accent/30 transition-colors">
                    <div className="flex items-center justify-between mb-2">
                      <button
                        onClick={() => navigate(`/ticker/${item.symbol}`)}
                        className="text-lg font-bold text-text-primary hover:text-accent transition-colors"
                      >
                        {item.symbol}
                      </button>
                      <button
                        onClick={() => removeSymbol(item.symbol)}
                        className="text-text-muted hover:text-red-400 transition-colors"
                        title="Remove"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    {analysis && (
                      <div className="space-y-1 text-xs">
                        {analysis.sector && (
                          <div className="text-text-muted">{analysis.sector}</div>
                        )}
                        {analysis.price != null && (
                          <div className="text-text-primary font-mono">{formatPrice(analysis.price)}</div>
                        )}
                        {analysis.beta != null && (
                          <div className="text-text-muted">β {analysis.beta.toFixed(2)}</div>
                        )}
                      </div>
                    )}
                    <div className="text-[10px] text-text-muted mt-2">
                      Added {new Date(item.addedAt).toLocaleDateString()}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Analyze button */}
            {symbols.length >= 2 && (
              <div className="flex items-center gap-3">
                <button
                  onClick={() => refetch()}
                  disabled={isFetching}
                  className="btn-primary gap-2"
                >
                  {isFetching ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <BarChart3 className="h-4 w-4" />
                  )}
                  {isFetching ? 'Analyzing...' : `Analyze Portfolio (${symbols.length})`}
                </button>
                {isError && (
                  <span className="text-xs text-red-400 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    Analysis failed
                  </span>
                )}
              </div>
            )}

            {/* Portfolio results */}
            {data && (
              <>
                {/* Summary metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {data.combined_beta != null && (
                    <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
                      <div className="text-[10px] font-semibold uppercase text-text-muted tracking-wider">Combined Beta</div>
                      <div className={cn('text-lg font-bold mt-1', data.combined_beta > 1 ? 'text-orange-400' : 'text-green-500')}>
                        {data.combined_beta.toFixed(2)}
                      </div>
                    </div>
                  )}
                  {data.portfolio_volatility != null && (
                    <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
                      <div className="text-[10px] font-semibold uppercase text-text-muted tracking-wider">Portfolio Vol</div>
                      <div className="text-lg font-bold mt-1 text-text-primary">{data.portfolio_volatility.toFixed(1)}%</div>
                    </div>
                  )}
                  {data.equal_risk_pct != null && (
                    <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
                      <div className="text-[10px] font-semibold uppercase text-text-muted tracking-wider">Per-Position Size</div>
                      <div className="text-lg font-bold mt-1 text-text-primary">{data.equal_risk_pct}%</div>
                    </div>
                  )}
                  {Object.keys(data.sector_allocation).length > 0 && (
                    <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
                      <div className="text-[10px] font-semibold uppercase text-text-muted tracking-wider">Top Sector</div>
                      <div className="text-lg font-bold mt-1 text-text-primary">
                        {Object.entries(data.sector_allocation).sort((a, b) => b[1] - a[1])[0]?.[0]}
                      </div>
                    </div>
                  )}
                </div>

                {/* Correlation warnings */}
                {data.high_correlation_pairs.length > 0 && (
                  <div className="bg-red-400/5 border border-red-400/20 rounded-xl p-4">
                    <div className="flex items-center gap-1.5 text-xs font-medium text-red-400 mb-2">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      High Correlation Warning
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {data.high_correlation_pairs.map((pair) => (
                        <span key={`${pair.a}-${pair.b}`} className="text-xs text-red-400 bg-red-400/5 px-2 py-0.5 rounded-full">
                          {pair.a} × {pair.b} (r={pair.r.toFixed(2)})
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Correlation matrix */}
                {data.correlation_matrix.length > 0 && (
                  <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
                    <h3 className="text-sm font-semibold text-text-primary mb-3">Correlation Matrix</h3>
                    <div className="overflow-x-auto">
                      <table className="text-xs w-full">
                        <thead>
                          <tr className="text-text-muted border-b border-border/30">
                            <th className="text-left pb-2 pr-4">Pair</th>
                            <th className="text-right pb-2">r</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.correlation_matrix.map((pair) => {
                            const absR = Math.abs(pair.r);
                            const color = absR > 0.7 ? 'text-red-400' : absR > 0.4 ? 'text-yellow-400' : 'text-green-500';
                            return (
                              <tr key={`${pair.a}-${pair.b}`} className="border-b border-border/20">
                                <td className="py-1.5 pr-4 text-text-primary">{pair.a} × {pair.b}</td>
                                <td className={cn('py-1.5 text-right font-mono', color)}>{pair.r.toFixed(3)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Quick links */}
                <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
                  <h3 className="text-sm font-semibold text-text-primary mb-3">Full Analysis</h3>
                  <div className="flex flex-wrap gap-2">
                    {symbols.map((sym) => (
                      <button
                        key={sym}
                        onClick={() => navigate(`/ticker/${sym}`)}
                        className="flex items-center gap-1 text-xs bg-accent/5 border border-accent/20 rounded-lg px-3 py-2 text-accent hover:bg-accent/10 transition-colors"
                      >
                        {sym} <ChevronRight className="h-3 w-3" />
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* Loading */}
            {isFetching && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 text-accent animate-spin" />
                <span className="ml-2 text-sm text-text-muted">Analyzing...</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function PortfolioPage() {
  return (
    <ErrorBoundary>
      <PortfolioContent />
    </ErrorBoundary>
  );
}
