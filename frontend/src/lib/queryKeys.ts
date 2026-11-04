/**
 * Centralized react-query key factory (FIX D).
 * Single source of truth for query keys — prevents key drift/collisions
 * (e.g. the old `['education']` vs `['professional','education']` mismatch).
 */
export const queryKeys = {
  marketRegime: () => ['market-regime'] as const,
  sectorRotation: () => ['sector-rotation'] as const,
  sectorFocus: () => ['sectors', 'focus'] as const,
  sectorDetail: (symbol: string) => ['sector-rotation', symbol] as const,
  rotationHistory: () => ['sector-rotation', 'history'] as const,
  marketEvents: () => ['market-events'] as const,
  tickerAnalysis: (symbol: string, timeframe: string) =>
    ['ticker', symbol, timeframe] as const,
  tickerOptions: (symbol: string) => ['ticker', symbol, 'options'] as const,
  tickerNews: (symbol: string) => ['ticker', symbol, 'news'] as const,
  chartOHLCV: (symbol: string, timeframe: string) =>
    ['chart', symbol, timeframe] as const,
  backtest: (runId?: string) =>
    runId ? (['backtest', runId] as const) : (['backtest'] as const),
  risk: (symbol: string) => ['risk', symbol] as const,
  education: (metric: string) => ['professional', 'education', metric] as const,
  portfolioAnalysis: (symbols: string[]) =>
    ['portfolio-analysis', symbols] as const,
} as const;
