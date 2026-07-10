// ── Human-readable filter descriptions for screener templates ──

export interface FilterRuleDisplay {
  category: string;
  indicator: string;
  params: Record<string, number | string>;
  operator: string;
  timeframe: string;
  negate: boolean;
}

const INDICATOR_LABELS: Record<string, (params: Record<string, number | string>) => string> = {
  price_above_ema:     (p) => `Price > ${p.period ?? '?'}-period EMA`,
  price_below_ema:     (p) => `Price < ${p.period ?? '?'}-period EMA`,
  price_above_vwap:    ()  => 'Price > VWAP',
  price_below_vwap:    ()  => 'Price < VWAP',
  adx_trending:        (p) => `ADX > ${p.threshold ?? 25} (trending)`,
  macd_bullish:        ()  => 'MACD bullish crossover',
  macd_bearish:        ()  => 'MACD bearish crossover',
  rsi_oversold:        (p) => `RSI < ${p.threshold ?? 30} (oversold)`,
  rsi_overbought:      (p) => `RSI > ${p.threshold ?? 70} (overbought)`,
  rsi_gt:              (p) => `RSI > ${p.threshold ?? 50}`,
  rsi_lt:              (p) => `RSI < ${p.threshold ?? 50}`,
  rvol_high:           (p) => `Volume > ${p.threshold ?? 1.5}x average`,
  bb_squeeze:          (p) => `BB width ratio < ${p.threshold ?? 1.15} (squeeze)`,
  ema_cross:           (p) => `EMA${p.fast ?? 50} > EMA${p.slow ?? 200}`,
};

const CATEGORY_LABELS: Record<string, string> = {
  trend:     'Trend',
  momentum:  'Momentum',
  volume:    'Volume',
  volatility:'Volatility',
};

/** Format a single filter rule into a short human-readable string. */
export function formatFilter(f: FilterRuleDisplay): string {
  const indicatorLabel = INDICATOR_LABELS[f.indicator]?.(f.params) ?? `${f.indicator}`;
  const neg = f.negate ? '[NOT] ' : '';
  const cat = CATEGORY_LABELS[f.category] ?? f.category;
  return `${neg}${indicatorLabel} (${cat}, ${f.timeframe})`;
}

/** Format all filters for a template as a compact join string. */
export function formatFilterList(filters: FilterRuleDisplay[]): string {
  return filters.map(formatFilter).join(' · ');
}

/** Return detailed description blocks for each filter category. */
export function filtersByCategory(filters: FilterRuleDisplay[]): { category: string; rules: string[] }[] {
  const groups: Record<string, string[]> = {};
  for (const f of filters) {
    const cat = CATEGORY_LABELS[f.category] ?? f.category;
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(formatFilter(f));
  }
  return Object.entries(groups).map(([category, rules]) => ({ category, rules }));
}
