import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import {
  Search, Plus, Trash2, BarChart3, ExternalLink,
  Loader2, CheckCircle2,
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
  const quickAddTickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'JPM'];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-text-primary">Watchlist Builder</h1>
          <p className="text-xs text-text-muted">
            Build and analyze your watchlist in minutes
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left panel: Add tickers */}
        <div className="lg:col-span-1 space-y-4">
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
              className="w-full pl-10 pr-4 rounded-lg border border-border/60 bg-background px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all"
            />
          </div>

          {/* Quick add from popular tickers */}
          <div>
            <span className="text-xs text-text-muted block mb-2">Quick add</span>
            <div className="flex flex-wrap gap-1.5">
              {quickAddTickers.map((ticker) => (
                <button
                  key={ticker}
                  onClick={() => handleAddSymbol(ticker)}
                  disabled={hasSymbol(ticker)}
                  className={cn(
                    'px-2.5 py-1 rounded-md text-xs font-medium border transition-colors',
                    hasSymbol(ticker)
                      ? 'bg-green-500/10 border-green-500/20 text-green-400 cursor-default'
                      : 'bg-surface-secondary border-border/60 text-text-muted hover:text-accent hover:border-accent/30'
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
              <span className="text-xs text-text-muted block mb-2">Search results</span>
              <div className="space-y-1">
                {searchResults.map((symbol) => (
                  <div
                    key={symbol}
                    className="flex items-center justify-between px-3 py-2 rounded-md bg-surface-secondary/50 border border-border/50"
                  >
                    <span className="text-sm font-medium text-text-primary">{symbol}</span>
                    <button
                      onClick={() => handleAddSymbol(symbol)}
                      disabled={hasSymbol(symbol)}
                      className={cn(
                        'px-2 py-1 text-xs rounded transition-colors',
                        hasSymbol(symbol)
                          ? 'text-green-400 cursor-default'
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
          <div className="rounded-lg border border-border overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-surface-secondary/50 border-b border-border">
              <span className="text-sm font-semibold text-text-primary">
                Watchlist ({portfolioItems.length})
              </span>
              <button
                onClick={() => analyzeMutation.mutate()}
                disabled={portfolioItems.length === 0 || analyzeMutation.isPending}
                className={cn(
                  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                  'bg-accent/10 text-accent hover:bg-accent/20',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
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
                <BarChart3 className="h-10 w-10 text-text-muted mx-auto mb-3 opacity-50" />
                <p className="text-sm text-text-muted">
                  Your watchlist is empty. Start by adding tickers from the Morning Brief or search above.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border/50">
                {/* Column headers */}
                <div className="grid grid-cols-5 gap-2 px-4 py-2 text-2xs text-text-muted font-medium uppercase tracking-wider bg-surface-tertiary/30">
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
                    className="grid grid-cols-5 gap-2 px-4 py-3 items-center hover:bg-surface-tertiary/30 transition-colors"
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
                    <span className="text-xs font-mono text-text-muted">
                      {accountSize
                        ? `~$${Math.floor(accountSize * 0.05).toLocaleString()}`
                        : 'Set in Settings'}
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => navigate(`/pro/ticker/${item.symbol}`)}
                        className="p-1 rounded text-text-muted hover:text-accent hover:bg-accent/10 transition-colors"
                        title="Analyze"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => handlePaperTrade()}
                        className="p-1 rounded text-text-muted hover:text-green-400 hover:bg-green-500/10 transition-colors"
                        title="Paper Trade"
                      >
                        <BarChart3 className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => handleRemoveSymbol(item.symbol)}
                        className="p-1 rounded text-text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
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
              <p className="text-xs text-green-400 font-medium">
                Analysis complete — {analyzeMutation.data.items.length} symbols analyzed
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
