import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import {
  Search,
  Plus,
  Trash2,
  BarChart3,
  ExternalLink,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { analyzeWatchlist } from '@/api/professional';
import { useProModeStore } from '@/store/professional';
import { usePortfolioStore } from '@/store/portfolio';
import type { WatchlistAnalyzeItem } from '@/types/professional';

export function WatchlistBuilderPage() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<string[]>([]);
  const accountSize = useProModeStore((s) => s.accountSize);
  const addNotification = useProModeStore((s) => s.addNotification);
  const portfolioItems = usePortfolioStore((s) => s.items);
  const addToPortfolio = usePortfolioStore((s) => s.addSymbol);
  const removeFromPortfolio = usePortfolioStore((s) => s.removeSymbol);
  const hasSymbol = usePortfolioStore((s) => s.hasSymbol);

  // Analyze watchlist mutation
  const analyzeMutation = useMutation({
    mutationFn: () => analyzeWatchlist(portfolioItems.map((i) => i.symbol)),
    onSuccess: (data) => {
      addNotification({
        type: 'target_hit',
        symbol: null,
        title: 'Watchlist Analysis Complete',
        message: `Analyzed ${data.items.length} symbols`,
        read: false,
      });
    },
  });

  const handleSearch = () => {
    if (!searchQuery.trim()) return;
    // Simple search: just add the typed symbol to results
    const sym = searchQuery.trim().toUpperCase();
    if (sym && !searchResults.includes(sym)) {
      setSearchResults([sym, ...searchResults]);
    }
    setSearchQuery('');
  };

  const handleAddSymbol = (symbol: string) => {
    addToPortfolio(symbol);
    setSearchResults((prev) => prev.filter((s) => s !== symbol));
    addNotification({
      type: 'morning_brief',
      symbol,
      title: 'Added to Watchlist',
      message: `${symbol} added to your watchlist`,
      read: false,
    });
  };

  const handleRemoveSymbol = (symbol: string) => {
    removeFromPortfolio(symbol);
  };

  const handlePaperTrade = () => {
    navigate('/portfolio');
  };

  // Quick-add suggestions from popular tickers
  const quickAddTickers = [
    'AAPL',
    'MSFT',
    'NVDA',
    'GOOGL',
    'AMZN',
    'META',
    'TSLA',
    'JPM',
  ];

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-text-primary">
            Watchlist Builder
          </h1>
          <p className="text-xs text-text-muted">
            Build and analyze your watchlist in minutes
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left panel: Add tickers */}
        <div className="space-y-4 lg:col-span-1">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
            <input
              data-testid="watchlist-search"
              type="text"
              placeholder="Search symbols..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full rounded-lg border border-border/60 bg-background px-3 py-2 pl-10 pr-4 text-sm text-text-primary placeholder-text-muted outline-none transition-all focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
          </div>

          {/* Quick add from popular tickers */}
          <div>
            <span className="mb-2 block text-xs text-text-muted">
              Quick add
            </span>
            <div className="flex flex-wrap gap-1.5">
              {quickAddTickers.map((ticker) => (
                <button
                  key={ticker}
                  onClick={() => handleAddSymbol(ticker)}
                  disabled={hasSymbol(ticker)}
                  className={cn(
                    'rounded-md border px-2.5 py-1 text-xs font-medium transition-colors',
                    hasSymbol(ticker)
                      ? 'cursor-default border-green-500/20 bg-green-500/10 text-green-400'
                      : 'bg-surface-secondary border-border/60 text-text-muted hover:border-accent/30 hover:text-accent'
                  )}
                >
                  {hasSymbol(ticker) ? (
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3" />
                      {ticker}
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <Plus className="h-3 w-3" />
                      {ticker}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Search results */}
          {searchResults.length > 0 && (
            <div>
              <span className="mb-2 block text-xs text-text-muted">
                Search results
              </span>
              <div className="space-y-1">
                {searchResults.map((symbol) => (
                  <div
                    key={symbol}
                    className="bg-surface-secondary/50 flex items-center justify-between rounded-md border border-border/50 px-3 py-2"
                  >
                    <span className="text-sm font-medium text-text-primary">
                      {symbol}
                    </span>
                    <button
                      onClick={() => handleAddSymbol(symbol)}
                      disabled={hasSymbol(symbol)}
                      className={cn(
                        'rounded px-2 py-1 text-xs transition-colors',
                        hasSymbol(symbol)
                          ? 'cursor-default text-green-400'
                          : 'text-accent hover:bg-accent/10'
                      )}
                    >
                      {hasSymbol(symbol) ? 'Added' : 'Add'}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right panel: Watchlist */}
        <div className="lg:col-span-2">
          <div className="overflow-hidden rounded-lg border border-border">
            {/* Header */}
            <div className="bg-surface-secondary/50 flex items-center justify-between border-b border-border px-4 py-3">
              <span className="text-sm font-semibold text-text-primary">
                Watchlist ({portfolioItems.length})
              </span>
              <button
                onClick={() => analyzeMutation.mutate()}
                disabled={
                  portfolioItems.length === 0 || analyzeMutation.isPending
                }
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                  'bg-accent/10 text-accent hover:bg-accent/20',
                  'disabled:cursor-not-allowed disabled:opacity-50'
                )}
              >
                {analyzeMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <BarChart3 className="h-3.5 w-3.5" />
                )}
                Analyze All
              </button>
            </div>

            {/* Body */}
            {portfolioItems.length === 0 ? (
              <div className="p-8 text-center">
                <BarChart3 className="mx-auto mb-3 h-10 w-10 text-text-muted opacity-50" />
                <p className="text-sm text-text-muted">
                  Your watchlist is empty. Start by adding tickers from the
                  Morning Brief or search above.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border/50">
                {/* Column headers */}
                <div className="text-2xs grid grid-cols-5 gap-2 bg-surface-tertiary/30 px-4 py-2 font-medium uppercase tracking-wider text-text-muted">
                  <span>Symbol</span>
                  <span>Verdict</span>
                  <span>Conviction</span>
                  <span>Position Preview</span>
                  <span>Actions</span>
                </div>

                {/* Rows */}
                {portfolioItems.map((item) => (
                  <div
                    key={item.symbol}
                    data-testid="watchlist-row"
                    className="grid grid-cols-5 items-center gap-2 px-4 py-3 transition-colors hover:bg-surface-tertiary/30"
                  >
                    <span className="text-sm font-semibold text-text-primary">
                      {item.symbol}
                    </span>
                    <span className="text-xs text-text-muted">
                      {analyzeMutation.data?.items.find(
                        (i: WatchlistAnalyzeItem) => i.symbol === item.symbol
                      )?.verdict || 'Pending'}
                    </span>
                    <span className="text-xs text-text-muted">
                      {analyzeMutation.data?.items.find(
                        (i: WatchlistAnalyzeItem) => i.symbol === item.symbol
                      )?.conviction || '--'}
                      /10
                    </span>
                    <span className="font-mono text-xs text-text-muted">
                      {accountSize
                        ? `~$${Math.floor(accountSize * 0.05).toLocaleString()}`
                        : 'Set in Settings'}
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => navigate(`/pro/ticker/${item.symbol}`)}
                        className="rounded p-1 text-text-muted transition-colors hover:bg-accent/10 hover:text-accent"
                        title="Analyze"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => handlePaperTrade()}
                        className="rounded p-1 text-text-muted transition-colors hover:bg-green-500/10 hover:text-green-400"
                        title="Paper Trade"
                      >
                        <BarChart3 className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => handleRemoveSymbol(item.symbol)}
                        className="rounded p-1 text-text-muted transition-colors hover:bg-red-500/10 hover:text-red-400"
                        title="Remove"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Analyze results */}
          {analyzeMutation.data && (
            <div className="mt-4 rounded-lg border border-green-500/20 bg-green-500/5 p-3">
              <p className="text-xs font-medium text-green-400">
                Analysis complete — {analyzeMutation.data.items.length} symbols
                analyzed
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
