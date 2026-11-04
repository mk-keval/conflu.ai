// ── Human-readable filter descriptions for screener templates ──

export interface FilterRuleDisplay {
  category: string;
  indicator: string;
  params: Record<string, number | string>;
  operator: string;
  timeframe: string;
  negate: boolean;
}

/** Humanize large numbers: 2000000000 → "$2B", 500000 → "500K". */
function humanizeCount(n: number | string): string {
  const v = typeof n === 'string' ? parseFloat(n) : n;
  if (!isFinite(v)) return String(n);
  if (v >= 1e9) return `${trimZero(v / 1e9)}B`;
  if (v >= 1e6) return `${trimZero(v / 1e6)}M`;
  if (v >= 1e3) return `${trimZero(v / 1e3)}K`;
  return trimZero(v);
}

function trimZero(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

const INDICATOR_LABELS: Record<
  string,
  (params: Record<string, number | string>) => string
> = {
  price_above_ema: (p) => `Price > ${p.period ?? '?'}-period EMA`,
  price_below_ema: (p) => `Price < ${p.period ?? '?'}-period EMA`,
  price_above_vwap: () => 'Price > VWAP',
  price_below_vwap: () => 'Price < VWAP',
  adx_trending: (p) => `ADX > ${p.threshold ?? 25} (trending)`,
  macd_bullish: () => 'MACD bullish crossover',
  macd_bearish: () => 'MACD bearish crossover',
  rsi_oversold: (p) => `RSI < ${p.threshold ?? 30} (oversold)`,
  rsi_overbought: (p) => `RSI > ${p.threshold ?? 70} (overbought)`,
  rsi_gt: (p) => `RSI > ${p.threshold ?? 50}`,
  rsi_lt: (p) => `RSI < ${p.threshold ?? 50}`,
  rvol_high: (p) => `Relative volume > ${p.threshold ?? 1.5}x average`,
  bb_squeeze: (p) => `BB width ratio < ${p.threshold ?? 1.15} (squeeze)`,
  bb_squeeze_tight: (p) =>
    `BB width ratio < ${p.threshold ?? 1.05} (tight squeeze)`,
  ema_cross: (p) => `EMA${p.fast ?? 50} > EMA${p.slow ?? 200}`,
  // ── Institutional quality gates (used by most screen templates) ──
  market_cap_gt: (p) =>
    `Market cap > $${humanizeCount(p.value ?? p.threshold ?? 0)}`,
  exchange_in: (p) => {
    const ex = Array.isArray(p.exchanges) ? (p.exchanges as string[]) : [];
    return ex.length
      ? `Listed on ${ex.join(' or ')}`
      : 'Major exchange listing';
  },
  country_in: (p) => {
    const c = Array.isArray(p.countries) ? (p.countries as string[]) : [];
    return c.length === 1 && c[0] === 'United States'
      ? 'US-based company'
      : c.length
        ? `Based in ${c.join('/')}`
        : 'Domestic listing';
  },
  close_above: (p) => `Price > $${p.threshold ?? '?'}`,
  avg_volume_gt: (p) =>
    `Avg daily volume > ${humanizeCount(p.threshold ?? 0)} shares`,
  volume_gt: (p) => `Volume > ${humanizeCount(p.threshold ?? 0)} shares`,
  ema_stack_bullish: () => 'Bullish EMA stack (short EMAs above long)',
  ema_stack_bearish: () => 'Bearish EMA stack (short EMAs below long)',
  eps_positive: () => 'Positive EPS (profitable)',
  pe_max: (p) => `P/E ≤ ${p.threshold ?? '?'}`,
  rsi_macd_bullish: () => 'RSI and MACD both confirm bullish momentum',
};

const CATEGORY_LABELS: Record<string, string> = {
  trend: 'Trend',
  momentum: 'Momentum',
  volume: 'Volume',
  volatility: 'Volatility',
  fundamental: 'Quality Gates',
};

export const CATEGORY_HINTS: Record<string, string> = {
  trend:
    'Confirms the stock is in an uptrend (or downtrend for short screens).',
  momentum: 'Times the entry — confirms buying pressure is building.',
  volume:
    'Confirms institutional participation; low-volume moves are unreliable.',
  volatility:
    'Identifies compression setups that tend to precede explosive moves.',
  fundamental:
    'Liquidity & quality gates — keeps tiny, illiquid, or un-listed names out of results.',
};

/** Format a single filter rule into a short human-readable string. */
export function formatFilter(f: FilterRuleDisplay): string {
  const indicatorLabel =
    INDICATOR_LABELS[f.indicator]?.(f.params) ?? `${f.indicator}`;
  const neg = f.negate ? '[NOT] ' : '';
  const cat = CATEGORY_LABELS[f.category] ?? f.category;
  return `${neg}${indicatorLabel} (${cat}, ${f.timeframe})`;
}

/** Format all filters for a template as a compact join string. */
export function formatFilterList(filters: FilterRuleDisplay[]): string {
  return filters.map(formatFilter).join(' · ');
}

/** Return detailed description blocks for each filter category. */
export function filtersByCategory(
  filters: FilterRuleDisplay[]
): { category: string; rules: string[] }[] {
  const groups: Record<string, string[]> = {};
  for (const f of filters) {
    const cat = CATEGORY_LABELS[f.category] ?? f.category;
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(formatFilter(f));
  }
  return Object.entries(groups).map(([category, rules]) => ({
    category,
    rules,
  }));
}
