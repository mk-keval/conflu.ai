/**
 * Educational content for the Ticker Analysis page.
 * Each entry explains a metric or concept in plain English for users
 * with no trading or financial market background.
 */

// ── Metric Explanations (plain English) ──

/**
 * Alias map: several metric keys are THE SAME measurement under different
 * names (verified against backend `technical.py` — `volume_ratio` is assigned
 * directly from `relative_volume_10d_calc`). Each alias resolves to a single
 * canonical lesson below, so we never maintain duplicate copy that drifts.
 */
export const METRIC_LESSON_ALIASES: Record<string, string> = {
  relative_volume: 'volume_ratio',
  days_to_cover: 'short_ratio',
};

export interface MetricLesson {
  label: string;
  /** What this metric measures — simple, no jargon */
  what: string;
  /** How to read the current value */
  readValue: (value: string) => string;
  /** Why traders care about this */
  whyMatters: string;
  /** How it affects the overall score */
  scoringImpact: string;
}

export const TECHNICAL_LESSONS: Record<string, MetricLesson> = {
  ma_alignment: {
    label: 'MA Alignment',
    what: "Moving Averages smooth out price data to show the general direction of a stock. We look at three time windows: 20 days (short-term), 50 days (medium-term), and 200 days (long-term). 'Alignment' means checking if they're stacked in order.",
    readValue: (v) =>
      v === 'bullish'
        ? 'Bullish means the shorter-term average is above the longer-term average (SMA20 > SMA50 > SMA200). This is the ideal pattern — the stock is trending UP across all time frames.'
        : v === 'bearish'
          ? 'Bearish means the shorter-term average is below the longer-term average. This suggests the stock is in a DOWNWARD trend.'
          : "Mixed means there's no clear order. Some averages are above, some below — the stock doesn't have a clear direction right now.",
    whyMatters:
      'Think of it like checking the wind direction. Aligned averages = strong breeze pushing the stock one way. Mixed averages = calm, changing winds. Most traders prefer stocks with clear direction.',
    scoringImpact:
      'This is one of the heaviest-weighted factors. Bullish alignment contributes a large positive boost. Bearish alignment pushes the score negative. Mixed adds nothing.',
  },
  rsi: {
    label: 'RSI (Relative Strength Index)',
    what: 'RSI measures how strongly the stock has been moving recently, on a scale of 0 to 100. It tells us if a stock is being bought too aggressively (overbought) or sold too aggressively (oversold).',
    readValue: (v) => {
      if (v.includes('overbought'))
        return 'Above 70 means the stock has risen very quickly. This can be a warning sign — what goes up fast can come down fast. But in strong trends, stocks can stay overbought for a while.';
      if (v.includes('oversold'))
        return 'Below 30 means the stock has dropped sharply. This might be a bargain opportunity, but it could also mean something is fundamentally wrong.';
      if (v.includes('neutral_bullish'))
        return `RSI ${v.split(' ')[0]} is in the 50-70 range. This is the 'sweet spot' — the stock has upward momentum but isn't at risk of a pullback.`;
      if (v.includes('neutral_bearish'))
        return `RSI ${v.split(' ')[0]} is in the 30-50 range. The stock has downward pressure but isn't at extreme levels.`;
      return `RSI ${v} — neutral territory. The stock isn't being heavily bought or sold.`;
    },
    whyMatters:
      "RSI is like a speedometer for price movement. It helps answer: 'Is this move sustainable, or is it running out of steam?'",
    scoringImpact:
      "RSI in the 'neutral bullish' zone (50-70) adds positive points. Overbought (>85) without fundamental support triggers a dealbreaker. Oversold can go either way depending on other factors.",
  },
  adx: {
    label: 'ADX (Average Directional Index)',
    what: 'ADX measures how STRONG a trend is, not which direction. Think of it as a volume knob — higher numbers mean the trend has more power behind it.',
    readValue: (v) => {
      if (v.includes('strong') || v.includes('extreme'))
        return `ADX ${v.split(' ')[0]} — the trend is strong and has conviction behind it. Big moves are happening.`;
      if (v.includes('moderate'))
        return `ADX ${v.split(' ')[0]} — there's a developing trend with moderate strength. Enough to trade but keep position sizes reasonable.`;
      if (v.includes('weak'))
        return `ADX ${v.split(' ')[0]} — the market is range-bound or directionless. Random back-and-forth movement with no clear trend.`;
      return v;
    },
    whyMatters:
      'A stock can be going up, but if the ADX is low, the move might be weak and easily reversed. Strong trends (high ADX) give you confidence the move will continue.',
    scoringImpact:
      "Strong trends boost the score. Weak trends are neutral. Extreme ADX with poor positioning can signal a trend that's exhausted.",
  },
  atr_pct: {
    label: 'ATR (Average True Range)',
    what: 'ATR measures how much a stock typically moves each day (its volatility). We express it as a percentage of price so you can compare across stocks.',
    readValue: (v) => {
      const pct = v.split('%')[0];
      const numPct = parseFloat(pct);
      if (numPct > 5)
        return `ATR ${v} — HIGH volatility. This stock moves a LOT each day. Bigger potential gains, but also bigger potential losses.`;
      if (numPct > 2)
        return `ATR ${v} — moderate volatility. Normal stock movement with occasional bigger days.`;
      return `ATR ${v} — low volatility. This stock is steady and predictable. Smaller day-to-day moves.`;
    },
    whyMatters:
      'Volatility tells you how bumpy the ride will be. High volatility stocks need wider stop losses and smaller position sizes. Low volatility stocks are calmer but may have less profit potential.',
    scoringImpact:
      'Used to calculate suggested stop loss and position size. Extreme volatility is flagged as a dealbreaker. Normal volatility is ideal.',
  },
  volume_ratio: {
    label: 'Volume Ratio / Relative Volume',
    what: "Compares today's trading volume to the average volume over the last 10 days. It tells us if there's unusual interest in this stock right now. You may see this called 'Relative Volume' (rvol) elsewhere — it is the same number.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 3)
        return `${v} — unusually HIGH volume. Something is happening! Big money is moving in or out of this stock.`;
      if (num > 1.5)
        return `${v} — above-average volume. More interest than usual, but not extreme.`;
      if (num >= 1)
        return `${v} — normal volume. Typical trading activity for this stock.`;
      return `${v} — below-average volume. Less interest than usual. Moves on low volume can be unreliable.`;
    },
    whyMatters:
      'High volume confirms that a price move is real. A stock going up on high volume = genuine buying pressure. A stock going up on low volume = might be a false move.',
    scoringImpact:
      "High volume adds positive points when direction aligns with the trend. Low volume doesn't hurt but doesn't help either. The screener's '×2.3' volume badge uses this same value.",
  },
  bb_position: {
    label: 'Bollinger Band Position',
    what: "Bollinger Bands create a 'price channel' around a stock's moving average. The bands widen during volatility and narrow during calm periods. This tells us where the price sits within that channel.",
    readValue: (v) =>
      v === 'above_upper'
        ? "Price is ABOVE the upper band — an unusually strong move. Could be a breakout or could be 'over-extended' and due for a pullback."
        : v === 'below_lower'
          ? 'Price is BELOW the lower band — an unusually sharp decline. Could be a buying opportunity if the stock is oversold, or a sign of trouble.'
          : 'Price is INSIDE the bands — normal trading within the expected range. No extreme pressure in either direction.',
    whyMatters:
      'When price touches or breaks through the bands, it signals something unusual is happening. Combined with other indicators, this can indicate breakout opportunities or warning signs.',
    scoringImpact:
      'Inside the bands = neutral. Above upper during a strong trend = positive. Below lower = typically negative unless other factors suggest a bounce.',
  },
  macd_status: {
    label: 'MACD (Moving Average Convergence Divergence)',
    what: 'MACD compares two moving averages to spot changes in momentum. It shows whether buying or selling pressure is getting stronger or weaker.',
    readValue: (v) =>
      v === 'bullish'
        ? "Bullish — the shorter-term average crossed above the longer-term one. This is a classic 'buy signal' that momentum is shifting upward."
        : v === 'bearish'
          ? 'Bearish — the shorter-term average crossed below the longer-term one. A warning sign that downward momentum is building.'
          : "Neutral — the two averages are close together. No clear momentum signal right now. The stock is 'coasting'.",
    whyMatters:
      "MACD helps you catch trend changes EARLY. It's like feeling the wind shift before the weather changes. Traders use it to time entries and exits.",
    scoringImpact:
      'Bullish MACD adds to the technical score. Bearish MACD subtracts. Neutral has no impact.',
  },
  avg_volume_20d: {
    label: 'Avg Volume (20d)',
    what: 'The average number of shares traded each day over the last 20 trading days (about 1 calendar month). Higher volume means more liquidity (easier to buy/sell).',
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 10_000_000)
        return `${(num / 1_000_000).toFixed(1)}M shares/day — very liquid. Huge volume means you can trade large positions without affecting the price.`;
      if (num > 1_000_000)
        return `${(num / 1_000_000).toFixed(1)}M shares/day — decent liquidity. Normal for mid-to-large cap stocks.`;
      if (num > 100_000)
        return `${(num / 1_000).toFixed(0)}K shares/day — moderate. Tradeable but larger orders may affect the price.`;
      return `${(num / 1_000).toFixed(0)}K shares/day — low volume. Be careful with position size as the spread may be wide.`;
    },
    whyMatters:
      "Volume is like the 'width' of the market. High volume = easy to get in and out. Low volume = price can move against you when you try to trade. Always check volume before buying an unfamiliar stock.",
    scoringImpact:
      "Low volume (<50K shares/day) can be a dealbreaker for swing trading. High volume is positive but doesn't directly affect the signal score.",
  },
  sma_50_200: {
    label: 'SMA 50/200 (Golden Cross / Death Cross)',
    what: "Compares the 50-day moving average to the 200-day moving average. When the 50-day crosses ABOVE the 200-day, it's called a 'Golden Cross' — very bullish. When it crosses BELOW, it's a 'Death Cross' — very bearish.",
    readValue: (v) =>
      v === 'golden_cross'
        ? 'GOLDEN CROSS — the 50-day average crossed above the 200-day! This is one of the most reliable bullish signals. It means the short-term trend is now stronger than the long-term trend.'
        : v === 'death_cross'
          ? 'DEATH CROSS — the 50-day average crossed below the 200-day. A serious bearish signal. It suggests the short-term trend has broken down and the stock may be entering a downtrend.'
          : 'No cross. The 50 and 200-day averages are maintaining their current order. No extreme trend change signal right now.',
    whyMatters:
      "Golden Crosses historically precede major bull runs. Death Crosses often (but not always) precede bear markets. They don't happen often, so when they do, pay attention.",
    scoringImpact:
      'Golden Cross = strong positive score boost. Death Cross = strong negative. No cross = neutral. This is a high-impact signal that can override other factors.',
  },
  consecutive_gains: {
    label: 'Consecutive Gains',
    what: 'The number of days in a row the stock has closed higher than the previous day. A streak of up days shows strong buying pressure.',
    readValue: (v) => {
      const num = parseFloat(v);
      if (num >= 7)
        return `${num} days — exceptional streak! The stock has been rising for over a week straight. Shows intense buying pressure, but may be due for a breather.`;
      if (num >= 5)
        return `${num} days — strong streak. Consistent buying for a full trading week. Bullish momentum.`;
      if (num >= 3)
        return `${num} days — moderate streak. Three up days in a row is a positive sign of short-term momentum.`;
      if (num === 1)
        return `${num} day — just started. One up day doesn't make a trend, but it's a start.`;
      return `${num} days — declining. The stock has been going down recently. Check other indicators for context.`;
    },
    whyMatters:
      'Streaks show momentum. A stock that keeps going up day after day has strong buying pressure. But beware: long streaks often end with a pullback. The longer the streak, the closer the potential reversal.',
    scoringImpact:
      'Moderate streaks (3-5 days) add to the momentum score. Very long streaks (7+) can be a double-edged sword — strong momentum but higher pullback risk.',
  },
};

export const FUNDAMENTAL_LESSONS: Record<string, MetricLesson> = {
  market_cap: {
    label: 'Market Cap',
    what: 'The total value of the company. Calculated by multiplying the stock price by the number of shares. It tells you how big the company is.',
    readValue: (v) =>
      `$${v} — this tells you the company's size. Large-cap (${v}B+) companies are established and stable. Small-cap (under $2B) are younger, riskier, but can grow faster.`,
    whyMatters:
      'Company size affects risk. Big companies (Apple, Microsoft) are less likely to crash but grow slower. Small companies can 10x but can also go to zero. Your strategy should match the size.',
    scoringImpact:
      "Market cap doesn't directly add or subtract from the score, but very small caps (< $50M) with poor profitability are flagged as a dealbreaker — too risky.",
  },
  pe_ratio: {
    label: 'P/E Ratio (Price to Earnings)',
    what: "How much investors are paying for each dollar of the company's profit. If P/E is 20, you're paying $20 for every $1 of annual profit.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 50)
        return `P/E ${v} — HIGH. Investors expect big future growth. Common for exciting companies (tech, biotech). Risk: if growth doesn't happen, the stock can fall hard.`;
      if (num > 20)
        return `P/E ${v} — above average. Investors are optimistic about growth. Reasonable for most growing companies.`;
      if (num > 0)
        return `P/E ${v} — moderate to low. The stock is reasonably priced relative to earnings. Could be a value opportunity, or the market sees problems ahead.`;
      return `P/E ${v} — negative. The company is LOSING money. Not necessarily bad (many young companies are profitable on purpose), but riskier.`;
    },
    whyMatters:
      "P/E is like a price tag on a company's earnings. A high P/E means you're paying a premium — you need strong growth to justify it. A low P/E can mean a bargain or a trap.",
    scoringImpact:
      'Very high P/E (>50) without strong growth = negative. Reasonable P/E (10-25) = positive. Negative P/E = neutral (common for growth companies).',
  },
  eps: {
    label: 'EPS (Earnings Per Share)',
    what: "The company's profit divided by its number of shares. It tells you how much profit each share of stock 'owns'.",
    readValue: (v) =>
      `$${v} per share. This is the company's per-share profit. Higher EPS means the company is more profitable. Consistent growth in EPS over years is a hallmark of a quality company.`,
    whyMatters:
      'EPS is the foundation of stock value. Over the long run, stock prices follow earnings. If EPS keeps growing, the stock price usually follows.',
    scoringImpact:
      'Positive and growing EPS = positive score contribution. Negative EPS = neutral (common in early-stage companies).',
  },
  profit_margin: {
    label: 'Profit Margin',
    what: 'The percentage of revenue that the company keeps as profit. If a company makes $100 in sales and has a 20% margin, it keeps $20 as profit.',
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 20)
        return `${v}% — excellent! The company is very efficient at turning revenue into profit.`;
      if (num > 10)
        return `${v}% — good. Healthy profitability with room to grow.`;
      if (num > 0)
        return `${v}% — positive but thin. The company is profitable but doesn't keep much from each sale.`;
      return `${v}% — negative. The company spends more than it earns. Common for young/high-growth companies.`;
    },
    whyMatters:
      'Profit margin shows how much pricing power and efficiency a company has. High margins = strong competitive advantage (like software companies). Low margins = tough business (like grocery stores).',
    scoringImpact:
      'Positive margins contribute to the score. Negative margins with small market cap triggers a dealbreaker. High margins = strong positive.',
  },
  debt_to_equity: {
    label: 'D/E Ratio (Debt to Equity)',
    what: 'How much debt the company has compared to its own money (equity). A D/E of 1 means the company has equal amounts of debt and equity.',
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 2)
        return `${v} — HIGH debt. The company owes a lot relative to its own money. Riskier because debt payments eat into profits.`;
      if (num > 0.5)
        return `${v} — moderate debt. Normal for most companies. Some debt is healthy — it funds growth.`;
      if (num >= 0)
        return `${v} — low debt. Conservative financial management. Less risk, but might be growing slower.`;
      return 'Negative — the company has more cash than debt. Very safe financially, but unusual for growing companies.';
    },
    whyMatters:
      "Too much debt can sink a company if business slows down (like high mortgage payments if you lose your job). Too little debt might mean the company isn't investing in growth.",
    scoringImpact:
      'High debt (>2) is negative. Moderate debt (0.5-1.5) is neutral. Very low or negative debt = slightly positive (financially conservative).',
  },
  revenue_growth_yoy: {
    label: 'Revenue Growth',
    what: "How much the company's sales have grown compared to the same period last year. Shows if the business is expanding.",
    readValue: (v) => {
      const num = parseFloat(v) * 100;
      if (num > 30)
        return `${v}% — RAPID growth. The company is expanding quickly. This is exciting but can be risky if growth isn't profitable.`;
      if (num > 10)
        return `${v}% — solid growth. Healthy expansion without being reckless. Ideal for most investors.`;
      if (num > 0)
        return `${v}% — modest growth. The company is growing, but slowly. Could be a mature company or facing competition.`;
      return `${v}% — NEGATIVE growth. Sales are shrinking. This is a red flag unless there's a clear one-time reason.`;
    },
    whyMatters:
      "Growing revenue means more customers, more sales, a growing business. Shrinking revenue means the opposite. It's the most basic measure of business health.",
    scoringImpact:
      'Strong growth adds to the score. Negative growth subtracts. This is one of the most important fundamental factors.',
  },
  fcf_yield: {
    label: 'FCF Yield (Free Cash Flow Yield)',
    what: "Free Cash Flow is the cash a company generates after paying for everything it needs to keep running. FCF Yield compares that cash to the stock price — like a 'cash on cash' return.",
    readValue: (v) => {
      const num = parseFloat(v) * 100;
      if (num > 8)
        return `${v}% — HIGH. The company generates lots of cash relative to its price. A sign of a quality business.`;
      if (num > 4) return `${v}% — good. Healthy cash generation.`;
      if (num > 0)
        return `${v}% — positive but low. Generates some cash but not a huge amount.`;
      return `${v}% — negative. The company is burning cash. Very common for high-growth companies. Not a problem if revenue is growing fast.`;
    },
    whyMatters:
      'Cash is king. Companies that generate lots of free cash can invest in growth, pay dividends, buy back stock, or weather hard times. Negative FCF means they need to borrow or raise money.',
    scoringImpact:
      'Positive FCF yield = positive score contribution. Negative = neutral or slightly negative. Strong FCF yield with growth = very positive.',
  },
  dividend_yield: {
    label: 'Dividend Yield',
    what: 'The percentage of the stock price that the company pays back to shareholders each year as cash payments (dividends).',
    readValue: (v) => {
      const num = parseFloat(v) * 100;
      if (num > 4)
        return `${v}% — HIGH yield. The company returns a lot of cash to shareholders. Can be a sign of a mature, stable business.`;
      if (num > 1)
        return `${v}% — moderate yield. A reasonable income stream plus growth potential.`;
      return `${v}% — low or no dividend. The company reinvests profits into growth instead of paying shareholders. Normal for growth companies.`;
    },
    whyMatters:
      'Dividends are like rent on your stock. Some investors want regular income (retirees). Others prefer companies that reinvest for growth. Neither is better — it depends on your goals.',
    scoringImpact:
      'High dividend yield with sustainable earnings = positive. No dividend = neutral (expected for growth stocks). Suspended dividend = negative flag.',
  },
  return_on_equity: {
    label: 'ROE (Return on Equity)',
    what: "ROE measures how efficiently the company uses its shareholders' money to generate profit. If a company has $100 of shareholder equity and earns $15 per year, its ROE is 15%.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 30)
        return `${v}% — exceptional! The company generates outstanding returns from its shareholders' money. Often a hallmark of a competitive advantage.`;
      if (num > 15)
        return `${v}% — strong ROE. The company is effectively deploying capital to generate profits.`;
      if (num > 10)
        return `${v}% — decent. In line with the overall market average.`;
      if (num > 0)
        return `${v}% — positive but below average. The company earns a return, but less than what investors might get elsewhere.`;
      return `${v}% — negative. The company is destroying shareholder value. A serious red flag if persistent.`;
    },
    whyMatters:
      "ROE tells you if the company is a good steward of investor money. High ROE suggests the business has a 'moat' — something that lets it earn above-average profits. It's Warren Buffett's favorite metric.",
    scoringImpact:
      "High ROE (>15%) contributes positively to the fundamental score. Negative ROE is a concern. It's used alongside other metrics to gauge overall financial health.",
  },
  price_to_book: {
    label: 'P/B Ratio (Price to Book)',
    what: "Compares the company's stock price to its 'book value' — what would be left if the company sold everything and paid all debts. It's like comparing a house's market price to its rebuild cost.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 5)
        return `${v} — high premium. Investors are paying far more than the company's assets are worth. Common for tech and service companies where value is in intangibles.`;
      if (num > 2)
        return `${v} — above book value. The market believes the company is worth more than its physical assets. Normal for most profitable companies.`;
      if (num > 1)
        return `${v} — reasonable. Stock price roughly in line with asset value. Could be undervalued or just a capital-intensive business.`;
      if (num > 0)
        return `${v} — below book value. Potentially UNDERVALUED — the market is pricing the company below its asset value. Could be a bargain or a value trap.`;
      return `${v} — negative book value. The company has more liabilities than assets. High risk.`;
    },
    whyMatters:
      'P/B is useful for valuing banks, insurance companies, and asset-heavy businesses. A low P/B can indicate a bargain, but only if the company is still profitable. Very high P/B is normal for tech companies with few physical assets.',
    scoringImpact:
      'Contributes to the overall fundamental picture but weighted less than P/E and profit margin. Very low P/B with good profitability = positive value signal.',
  },
  operating_margin: {
    label: 'Operating Margin',
    what: "The percentage of revenue that remains after paying for production costs and operating expenses (salaries, rent, R&D), but before interest and taxes. It's a narrower measure than profit margin.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 20)
        return `${v}% — excellent. The company's core business is highly efficient at turning revenue into operating profit.`;
      if (num > 10)
        return `${v}% — good. Healthy operating efficiency with room to invest in growth.`;
      if (num > 5)
        return `${v}% — adequate. The core business is profitable but not highly efficient.`;
      if (num > 0)
        return `${v}% — thin. The company makes a small operating profit on each sale. Vulnerable to cost increases.`;
      return `${v}% — negative. The core business operations are losing money. Different from net loss which could include one-time items.`;
    },
    whyMatters:
      "Operating margin focuses on the CORE business, excluding interest and taxes. It tells you if the company's products/services are fundamentally profitable, regardless of how the company is financed or its tax situation.",
    scoringImpact:
      'Strong operating margins (>15%) bolster the fundamental score. Negative operating margins over multiple periods indicate the business model may not be viable.',
  },
};

export const EARNINGS_LESSONS: Record<string, MetricLesson> = {
  last_surprise_pct: {
    label: 'Earnings Surprise',
    what: "Companies report profits every 3 months. Analysts predict what the number will be. The 'surprise' is how much the actual result beat (or missed) those predictions, shown as a percentage.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 10)
        return `${v}% BEAT — the company crushed expectations! This usually pushes the stock price up.`;
      if (num > 0)
        return `${v}% beat — the company did better than expected. A positive sign.`;
      if (num > -5)
        return `${v}% miss — slightly below expectations. Not a disaster, but not ideal.`;
      return `${v}% miss — significantly below expectations. This can hit the stock price hard.`;
    },
    whyMatters:
      "Earnings surprises show whether the company is performing better or worse than the 'consensus' view. Consistent positive surprises suggest the business is stronger than people think.",
    scoringImpact:
      'Positive surprises = score boost. Large negative surprises = score penalty. Consistent beaters get higher scores.',
  },
  beat_rate: {
    label: 'Beat Rate',
    what: "Out of the last several earnings reports, how many beat expectations? '3/4' means they beat 3 out of the last 4 quarters.",
    readValue: (v) =>
      `${v} quarters beat expectations. A company that consistently beats (like 4/4) is showing strong execution. One that frequently misses is struggling.`,
    whyMatters:
      'A single beat or miss could be luck. A consistent track record tells you the company has real momentum (or real problems).',
    scoringImpact:
      'High beat rate (3+/4) = strong positive. Low beat rate (1/4 or 0/4) = negative. This is a reliable quality indicator.',
  },
  next_earnings_date: {
    label: 'Next Earnings Date',
    what: 'The date when the company will next report its quarterly results. Earnings day is when the biggest stock moves happen.',
    readValue: (v) => {
      if (!v || v === '—') return 'No upcoming earnings date available.';
      const daysUntil = Math.ceil(
        (new Date(v).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
      );
      if (daysUntil <= 7)
        return `${v} — coming up SOON (${daysUntil} days). Expect higher volatility around this date. Consider waiting until after earnings to enter a new position.`;
      if (daysUntil <= 30)
        return `${v} — about ${daysUntil} days away. The stock may start 'pricing in' expectations soon.`;
      return `${v} — ${daysUntil} days away. Plenty of time before the next report.`;
    },
    whyMatters:
      "Earnings reports cause the biggest price swings. A stock can move 10-20% in a single day. If you're risk-averse, wait until after earnings. If you're confident in the result, you can profit from the move.",
    scoringImpact:
      'Does not directly impact the score, but is shown so you can make informed timing decisions.',
  },
};

export const GROWTH_LESSONS: Record<string, MetricLesson> = {
  earnings_growth_yoy: {
    label: 'Earnings Growth (YoY)',
    what: "How much the company's earnings (profit) have grown compared to the same period last year. Shows if profitability is improving.",
    readValue: (v) => {
      const num = parseFloat(v) * 100;
      if (num > 50)
        return `${num.toFixed(0)}% — EXPLOSIVE growth. Earnings are growing much faster than revenue, which means the company is becoming more efficient.`;
      if (num > 20)
        return `${num.toFixed(0)}% — strong growth. The company is getting more profitable rapidly. A sign of a quality business.`;
      if (num > 0)
        return `${num.toFixed(0)}% — positive growth. Earnings are heading in the right direction.`;
      if (num > -20)
        return `${num.toFixed(0)}% — slight decline. Earnings are down a bit. Not a crisis, but worth monitoring.`;
      return `${num.toFixed(0)}% — significant decline. Profits are shrinking. A red flag unless there's a clear one-time reason.`;
    },
    whyMatters:
      "Revenue growth shows the company is getting bigger. Earnings growth shows it's getting MORE profitable. Both together = the ideal combination.",
    scoringImpact:
      'Strong earnings growth adds to the fundamental score. Negative earnings growth is a concern, especially if revenue is still growing (shrinking margins).',
  },
  peg_ratio: {
    label: 'PEG Ratio',
    what: "The P/E ratio divided by the earnings growth rate. It answers: 'Is the stock's price reasonable given how fast it's growing?' A PEG of 1 is considered fair value.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num < 0)
        return `${v} — negative earnings growth. The company's profits are shrinking. The low PEG is NOT a bargain — it's a warning.`;
      if (num < 1)
        return `${v} — UNDERVALUED relative to growth. The stock's price is low compared to how fast earnings are growing. This is often a good sign.`;
      if (num < 2)
        return `${v} — fairly valued. The price is reasonable for the growth rate. No obvious bargain or overvaluation.`;
      return `${v} — OVERVALUED relative to growth. The stock's price is high compared to its growth rate. Either the growth is expected to accelerate, or the stock is too expensive.`;
    },
    whyMatters:
      "PEG is P/E with context. A high P/E looks scary, but if the company is growing at 50% per year, a PEG of 1 means it's actually fairly priced. It's the 'growth-adjusted value' measure.",
    scoringImpact:
      'PEG < 1 with positive earnings growth = strong value signal. PEG > 2 = potential overvaluation. Negative PEG = caution flag.',
  },
  price_to_sales: {
    label: 'P/S Ratio (Price to Sales)',
    what: "The stock price divided by the company's revenue per share. It values the company based on sales rather than profits. Useful when the company isn't yet profitable.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 20)
        return `${v} — very high. Common for high-growth tech companies. Investors are paying a huge premium for future revenue. High risk if growth slows.`;
      if (num > 5)
        return `${v} — above average. The market is optimistic about future growth. Reasonable for growth companies.`;
      if (num > 1)
        return `${v} — typical range. Normal valuation for most businesses.`;
      if (num > 0)
        return `${v} — low. The company's sales are valued conservatively. Could be a bargain or a value trap.`;
      return `${v} — negative (unusual). The company has negative revenue? This is very rare — likely a data issue.`;
    },
    whyMatters:
      "P/S is useful for young companies that aren't profitable yet (they have P/E but it's often negative/meaningless). It tells you how much you're paying for each dollar of sales, regardless of profitability.",
    scoringImpact:
      'Very high P/S (>20) with slow revenue growth = overvalued. Low P/S with high revenue growth = potential bargain. No direct score impact for unprofitable companies — assessed alongside growth rate.',
  },
  current_ratio: {
    label: 'Current Ratio',
    what: 'Short-term assets divided by short-term liabilities. It measures whether the company has enough cash and near-cash items to pay its bills over the next 12 months.',
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 3)
        return `${v} — VERY healthy. The company has far more short-term assets than liabilities. A strong safety cushion.`;
      if (num > 1.5)
        return `${v} — healthy. The company can comfortably cover its short-term obligations. Standard for most businesses.`;
      if (num > 1)
        return `${v} — adequate. The company can just barely cover its short-term debts. Watch for any deterioration.`;
      return `${v} — concerning. The company's short-term liabilities exceed its liquid assets. Could face cash flow problems if business slows.`;
    },
    whyMatters:
      "Current ratio is a 'can they pay the rent?' check. A company that can't cover its short-term bills may need to borrow or sell assets, which hurts shareholders. Below 1.0 is a warning sign for traditional businesses.",
    scoringImpact:
      'Current ratio < 1.0 with small market cap = dealbreaker flag. Healthy ratio (1.5-3) = positive. Very high (>5) can mean inefficient use of cash.',
  },
  institutional_flow: {
    label: 'Institutional Flow',
    what: "Net buying or selling by large institutions (mutual funds, pension funds, hedge funds) over the last month. Positive means more buying than selling by the 'smart money'.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 5)
        return `${v} — STRONG institutional buying. Major investors are accumulating shares. One of the most bullish signals available.`;
      if (num > 1)
        return `${num.toFixed(1)} — moderate buying. Institutions are adding to positions. Mildly bullish.`;
      if (num > -1)
        return `${num.toFixed(1)} — neutral. No significant institutional activity this month.`;
      if (num > -5)
        return `${num.toFixed(1)} — moderate selling. Institutions are reducing positions. Mildly bearish.`;
      return `${num.toFixed(1)} — STRONG institutional selling. Smart money is getting out. A significant warning sign.`;
    },
    whyMatters:
      "Institutions do extensive research before making moves. When they're consistently buying a stock, it's because their analysts found something compelling. When they're all selling, pay attention.",
    scoringImpact:
      'Strong buying = significant positive boost. Strong selling = significant negative. This is weighted heavily in sentiment because it represents real money in action.',
  },
};

export const SENTIMENT_LESSONS: Record<string, MetricLesson> = {
  analyst_consensus: {
    label: 'Analyst Consensus',
    what: 'Professional stock analysts study the company and give their opinion: Buy, Hold, or Sell. This is the average of all analysts covering the stock.',
    readValue: (v) => {
      if (v.includes('Buy') || v === 'Strong Buy')
        return `${v} — analysts are BULLISH. Most experts think this stock will go up.`;
      if (v === 'Hold' || v === 'Neutral')
        return `${v} — analysts are neutral. They don't see strong reasons to buy or sell at current prices.`;
      if (v.includes('Sell'))
        return `${v} — analysts are BEARISH. Many experts recommend selling. This is a warning sign.`;
      return `${v} — analyst consensus.`;
    },
    whyMatters:
      "Analyst ratings give you a 'second opinion' on the stock. But remember: analysts are often too optimistic (they don't like to say Sell). Take Strong Buy ratings seriously, but do your own research too.",
    scoringImpact:
      'Strong Buy consensus = positive score contribution. Hold/Neutral = neutral. Sell = negative. Heavy weight on this factor.',
  },
  insider_status: {
    label: 'Insider Activity',
    what: "Company insiders (executives, directors) are required to report when they buy or sell their own stock. Their actions reveal what they really think about the company's prospects.",
    readValue: (v) =>
      v === 'buying'
        ? "Insiders are BUYING — they're putting their own money into the stock. This is one of the most BULLISH signals. They know the business better than anyone."
        : v === 'selling'
          ? 'Insiders are SELLING — but context matters. Executives often sell for personal reasons (diversification, taxes, buying a house). Heavy selling by multiple insiders is a warning sign.'
          : 'No significant insider activity detected recently. Neither strongly bullish or bearish from an insider perspective.',
    whyMatters:
      "Insiders have the most accurate information about their company. When they buy, it's because they genuinely believe the stock will go up. When multiple insiders sell heavily, they might see trouble ahead.",
    scoringImpact:
      'Insider buying = positive boost. Heavy insider selling = negative. This factor can override other signals when extreme.',
  },
  short_interest_pct: {
    label: 'Short Interest',
    what: "The percentage of shares that investors have 'borrowed and sold' hoping to buy them back cheaper later. It measures how many people are betting the stock will go DOWN.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 20)
        return `${v}% — VERY HIGH short interest. A huge number of people are betting against this stock. If they're wrong, a 'short squeeze' could rocket the price up.`;
      if (num > 10)
        return `${v}% — high short interest. Significant bearish sentiment. Could mean trouble, or could be a squeeze opportunity.`;
      if (num > 3)
        return `${v}% — moderate. Some bearish bets but nothing unusual.`;
      return `${v}% — low. Very few people are betting against this stock. Generally a positive sign.`;
    },
    whyMatters:
      "High short interest is controversial — it means many smart investors think the stock will fall. But if they're wrong, they're forced to buy back shares, creating a 'squeeze' that pushes prices even higher. It's a double-edged sword.",
    scoringImpact:
      "Very high short interest (>30%) is flagged as a dealbreaker — it signals serious doubt about the company. Moderate levels add interest but don't change the score much.",
  },
  short_ratio: {
    label: 'Short Ratio (Days to Cover)',
    what: "How many trading days it would take for ALL short sellers to buy back their borrowed shares, based on average daily volume. You may see this called 'Days to Cover' elsewhere — it is the same number. Higher = more squeeze potential.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 10)
        return `${num.toFixed(1)} days — extremely high squeeze potential. Would take over 10 days of normal trading to cover all shorts. If a squeeze starts, it'll be VIOLENT.`;
      if (num > 5)
        return `${num.toFixed(1)} days — high squeeze risk. Short sellers are crowded and vulnerable to positive catalysts.`;
      if (num > 2)
        return `${num.toFixed(1)} days — moderate. Short sellers could cover in a few days if needed. Some squeeze potential.`;
      return `${num.toFixed(1)} days — low. Short positions can be closed quickly. Less squeeze risk.`;
    },
    whyMatters:
      "Together with short interest percentage, this tells you how 'trapped' short sellers are. High short interest + high days to cover = squeeze setup. When a heavily-shorted stock gets positive news, the forced buying can push the price up 50-100%+. But a high ratio alone isn't a buy signal — the shorts might be right.",
    scoringImpact:
      'Does not directly change the score but is cross-referenced with short interest to flag squeeze potential. High values combined with positive momentum = boost.',
  },
  institutional_ownership: {
    label: 'Institutional Ownership',
    what: "The percentage of shares owned by large institutions like mutual funds, pension funds, and hedge funds. These are the 'smart money' professional investors.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 60)
        return `${v}% — strong institutional confidence. The big money players are heavily invested. This usually means they've done deep research and like what they see.`;
      if (num > 30)
        return `${v}% — moderate. Respectable institutional interest but not overwhelming.`;
      if (num > 10)
        return `${v}% — light. Few institutions have taken a position. Could be because the company is too small for them, or they're not convinced.`;
      return `${v}% — minimal. Very little institutional interest. This can be a red flag — professionals tend to avoid stocks with serious problems.`;
    },
    whyMatters:
      'Institutions do extensive research before buying. High institutional ownership means the stock has passed rigorous scrutiny. But be careful: if institutions all decide to sell at once, the stock can drop fast (no one to catch the falling knife).',
    scoringImpact:
      'High institutional ownership adds to the sentiment score. Very low institutional ownership is a concern. This is a moderate-weight factor.',
  },
  beta: {
    label: 'Beta (Market Correlation)',
    what: 'Beta measures how much the stock moves compared to the overall market. A beta of 1 means the stock moves in line with the market. A beta of 1.5 means it moves 50% more than the market.',
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 1.5)
        return `${v} — high beta. The stock amplifies market moves. If the market goes up 1%, this stock often goes up 1.5%+. But it also falls harder.`;
      if (num > 0.8)
        return `${v} — market-like. The stock moves roughly in line with the overall market. Typical for most stocks.`;
      if (num > 0.3)
        return `${v} — low beta. The stock is more stable than the market. Good for defensive/conservative positioning.`;
      return `${v} — very low or negative. The stock barely reacts to the market or moves opposite to it. Rare — found in gold stocks, deep-value, or heavily distressed companies.`;
    },
    whyMatters:
      "Beta helps you understand a stock's risk profile. High beta = high risk, high reward. Low beta = stable but less upside. If you're building a portfolio, mixing high and low beta stocks balances risk.",
    scoringImpact:
      'High beta (>1.5) is a slight negative (more risk). Low beta (<0.8) is a slight positive (more stable). Market-line beta (0.8-1.3) is neutral. Combined with other risk metrics.',
  },
  target_upside_pct: {
    label: 'Price Target Upside',
    what: 'The difference between the current stock price and the average price target set by professional analysts. A positive number means analysts expect the stock to go UP from here.',
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 30)
        return `${v}% — huge upside. Analysts see massive potential. But very high targets can also mean high uncertainty — be skeptical.`;
      if (num > 10)
        return `${v}% — meaningful upside. Analysts believe there's room to run. A solid positive signal.`;
      if (num > 0)
        return `${v}% — slight upside. The stock is considered fairly valued or slightly cheap.`;
      if (num > -10)
        return `${v}% — slight downside. The stock may be slightly overvalued. Analysts expect a modest pullback.`;
      return `${v}% — significant downside. Analysts think the stock is overvalued and expect it to fall. A bearish signal.`;
    },
    whyMatters:
      "Price targets give you a sense of the 'consensus destination' for the stock. But remember: analysts are often too optimistic. Use targets as one input, not the deciding factor. A stock hitting its target isn't guaranteed.",
    scoringImpact:
      'Strong upside (>15%) contributes positively. Downside is negative. The conviction is tempered by how many analysts cover the stock (more analysts = more reliable).',
  },
};

export const RISK_LESSONS: Record<string, MetricLesson> = {
  volatility_regime: {
    label: 'Volatility Regime',
    what: 'A category for how much this stock moves day-to-day. Based on its ATR percentage compared to other stocks.',
    readValue: (v) =>
      v === 'low'
        ? 'LOW volatility — this stock is very steady. Calm, predictable moves. Good for conservative traders.'
        : v === 'normal'
          ? 'NORMAL volatility — typical day-to-day movement. Most stocks fall in this range.'
          : v === 'high'
            ? 'HIGH volatility — this stock moves a lot. Expect bigger swings. Higher potential reward, higher risk.'
            : 'EXTREME volatility — very unusual moves. Either a huge opportunity or a dangerous situation. Requires wider stops and smaller positions.',
    whyMatters:
      "Your strategy should match the stock's volatility. A calm stock needs tight stops. A volatile stock needs room to breathe. Don't trade a high-volatility stock with a low-volatility mindset.",
    scoringImpact:
      'Normal volatility = ideal. Low = slightly positive (stable). High = negative (riskier). Extreme = dealbreaker.',
  },
  suggested_stop_pct: {
    label: 'Suggested Stop Loss',
    what: "The recommended 'emergency exit' price. If the stock falls below this level, it means the trade idea is likely wrong and you should sell to limit your losses.",
    readValue: (v) =>
      `${v}% below entry. Based on the stock's volatility (ATR). Think of it like a 'circuit breaker' — if the stock drops this much, something unexpected is happening, and it's safer to exit.`,
    whyMatters:
      'Stop losses are the single most important risk management tool. They prevent a small loss from becoming a disaster. Without stops, a -10% loss can turn into -50%.',
    scoringImpact:
      "Not a scoring factor — it's a risk management recommendation calculated from the stock's volatility.",
  },
  suggested_position_size_pct: {
    label: 'Suggested Position Size',
    what: 'What percentage of your total trading money should go into this stock. Based on risk: higher volatility = smaller position.',
    readValue: (v) =>
      `${v}% of your portfolio. This is calculated conservatively to protect your capital. High volatility stocks get smaller sizes. Low volatility stocks can have larger sizes.`,
    whyMatters:
      'Position sizing is how professionals avoid blowing up. Even the best traders are wrong 40% of the time. By keeping position sizes reasonable, no single loss can wipe you out.',
    scoringImpact:
      "Not a scoring factor — it's a risk management recommendation.",
  },
  max_risk_per_trade_pct: {
    label: 'Max Risk Per Trade',
    what: 'The maximum percentage of your portfolio you should risk on this single trade. The default is 1%, a common rule used by professional traders.',
    readValue: (v) =>
      `${v}% max risk. Professional risk management rule: never risk more than this on any single trade. This ensures you can survive a string of losses.`,
    whyMatters:
      "If you risk 1% per trade, you'd need 100 consecutive losses to go to zero. If you risk 10% per trade, just 10 losses wipes you out. This rule is what keeps traders IN the game long-term.",
    scoringImpact: "Not a scoring factor — it's a configurable risk parameter.",
  },
};

// ── Module Explanations ──

export interface ModuleLesson {
  title: string;
  whatItIs: string;
  whyItMatters: string;
  howScoreWorks: string;
}

export const MODULE_LESSONS: Record<string, ModuleLesson> = {
  technical: {
    title: 'Technical Analysis',
    whatItIs:
      "Technical analysis studies the stock's PRICE and VOLUME data to gauge direction and momentum. It doesn't care about the company's products or profits — it only looks at what the market is DOING.",
    whyItMatters:
      'In the short to medium term, price patterns and momentum matter more than company fundamentals. A stock can have great products but a terrible chart. Technical analysis helps you buy at the right time.',
    howScoreWorks:
      'We look at 7 factors: MA alignment (trend direction), RSI (momentum), ADX (trend strength), ATR (volatility), Volume Ratio (interest), Bollinger Band position, and MACD (momentum signal). Each factor is scored, then combined into a -1.0 to +1.0 score. The trend alignment and RSI get the most weight.',
  },
  fundamental: {
    title: 'Fundamental Analysis',
    whatItIs:
      "Fundamental analysis looks at the COMPANY's financial health: how much money it makes, how fast it's growing, how much debt it has. It answers: 'Is this a good business?'",
    whyItMatters:
      "A stock's price eventually follows its earnings. Good fundamentals don't guarantee the stock will go up tomorrow, but they strongly predict where it'll be in 1-3 years. Technical + fundamental together give you the complete picture.",
    howScoreWorks:
      'We score 11 factors: market cap (size), P/E (valuation), EPS (profitability), profit margin (efficiency), debt/equity (financial risk), revenue growth (expansion), free cash flow yield (cash generation), dividend yield (shareholder returns), return on equity (capital efficiency), price-to-book (asset valuation), and operating margin (core business efficiency). Positive values = good. Negative values = concerning. The final score combines these into -1.0 to +1.0.',
  },
  earnings: {
    title: 'Earnings Analysis',
    whatItIs:
      'Companies report their financial results every 3 months (quarterly earnings). This analysis looks at their track record of beating or missing expectations, and when the next report is due.',
    whyItMatters:
      'Earnings reports cause the biggest single-day moves in stock prices (5-20% is common). Knowing the earnings track record helps you assess whether the company consistently delivers or frequently disappoints.',
    howScoreWorks:
      'We look at the latest surprise percentage, the beat rate (how many of the last 4 reports beat expectations), and the average stock reaction to earnings. Consistent beaters get positive scores. Consistent missers get negative scores.',
  },
  sentiment: {
    title: 'Market Sentiment',
    whatItIs:
      "Sentiment measures what OTHER market participants think about the stock: professional analysts, company insiders, and short sellers. It's like getting a 'consensus opinion' from everyone watching the stock.",
    whyItMatters:
      "When everyone is bullish, the stock usually goes up — until it doesn't. When insiders are buying heavily, it's one of the most reliable signals. When short interest is extreme, be careful.",
    howScoreWorks:
      'We combine: analyst consensus (weighted heavily), insider buying/selling activity, institutional ownership percentage, short interest and days to cover, price target upside potential, and beta (how much the stock moves relative to the market). The overall range is -1.0 to +1.0.',
  },
  risk: {
    title: 'Risk Assessment',
    whatItIs:
      "Risk analysis tells you how DANGEROUS this trade is and how to manage that danger. It's not about predicting direction — it's about protecting your money.",
    whyItMatters:
      'Even the best analysis can be wrong. Risk management is what separates professionals from amateurs. Professionals focus on how MUCH they can lose. Amateurs only think about how MUCH they can make.',
    howScoreWorks:
      'We assess volatility (ATR percentage), calculate an appropriate stop loss level, determine the right position size based on volatility, and suggest how much of your portfolio to risk. The score ranges from -1.0 (extreme risk) to +1.0 (very safe).',
  },
};

// ── Verdict Walkthrough ──

export interface WalkthroughStep {
  module: string;
  score: string;
  explanation: string;
}

export function verdictWalkthrough(
  action: string,
  conviction: number,
  moduleScores: { label: string; score: number }[],
  dealbreakers: string[]
): WalkthroughStep[] {
  const weighted =
    moduleScores.reduce((s, m) => s + m.score, 0) /
    Math.max(moduleScores.length, 1);
  const steps: WalkthroughStep[] = [];

  steps.push({
    module: 'Module Scores',
    score: `avg ${weighted >= 0 ? '+' : ''}${weighted.toFixed(2)}`,
    explanation: `Calculated individual scores for each analysis module:\n${moduleScores
      .map((m) => {
        const emoji = m.score >= 0.3 ? '✅' : m.score >= -0.1 ? '➖' : '⚠️';
        return `${emoji} ${m.label}: ${m.score >= 0 ? '+' : ''}${m.score.toFixed(2)}`;
      })
      .join(
        '\n'
      )}\n\nThese scores are averaged to determine the overall signal. Positive scores = bullish, negative = bearish.`,
  });

  steps.push({
    module: 'Weighted Average',
    score: (weighted >= 0 ? '+' : '') + weighted.toFixed(2),
    explanation: `The average of all module scores is ${weighted >= 0 ? '+' : ''}${weighted.toFixed(2)}. This represents the overall balance of bullish vs bearish signals across technical, fundamental, earnings, sentiment, and risk analysis.`,
  });

  if (dealbreakers.length > 0) {
    steps.push({
      module: 'Dealbreakers',
      score: `${dealbreakers.length} issue(s)`,
      explanation: `Found ${dealbreakers.length} critical issue(s) that override the score:\n${dealbreakers.map((d) => `• ${d}`).join('\n')}\n\nThese issues signal significant risk regardless of otherwise positive indicators.`,
    });
  } else {
    steps.push({
      module: 'Dealbreaker Check',
      score: 'PASSED',
      explanation:
        'No critical issues found that would override the score. All modules passed the minimum thresholds for consideration.',
    });
  }

  const actionExplanations: Record<string, string> = {
    STRONG_BUY:
      'Exceptional setup with high conviction. All modules strongly aligned with no major dealbreakers. High-confidence entry with wider targets justified.',
    BUY: 'Strong positive signal. All indicators align favorably. Consider entering a position within the suggested entry zone.',
    WATCH:
      'Mixed or mildly positive signals. The setup has potential but needs more confirmation. Wait for better entry or more data.',
    HOLD: 'Neutral signals. No strong reason to buy or sell. If you own it, keep it. If not, wait for a clearer signal.',
    AVOID:
      'Negative signals dominate. Significant issues identified. Stay away until conditions improve.',
    SELL: 'Clear negative signals. If you own this stock, consider selling. If not, do not buy.',
  };
  const baseAction = action.split('—')[0].trim();
  const actionExplanation =
    actionExplanations[baseAction] ??
    `${baseAction} — proceed with caution according to the analysis.`;

  steps.push({
    module: 'Action',
    score: `${action} (${conviction}/10)`,
    explanation: `Score ${weighted >= 0 ? '+' : ''}${weighted.toFixed(2)} mapped to action: ${action} with conviction ${conviction}/10.\n\n${actionExplanation}`,
  });

  return steps;
}

// ── Glossary of Common Terms ──

export interface GlossaryEntry {
  term: string;
  definition: string;
}

export const GLOSSARY: GlossaryEntry[] = [
  {
    term: 'Bullish',
    definition:
      'Expecting the price to go UP. Named after a bull attacking by lifting upward with its horns.',
  },
  {
    term: 'Bearish',
    definition:
      'Expecting the price to go DOWN. Named after a bear swiping downward with its paws.',
  },
  {
    term: 'Volatility',
    definition:
      "How much and how quickly a stock's price moves up and down. High volatility = big swings. Low volatility = steady prices.",
  },
  {
    term: 'Momentum',
    definition:
      'The speed and strength of a price move. A stock with strong momentum keeps moving in the same direction.',
  },
  {
    term: 'Trend',
    definition:
      'The general direction a stock is moving over time. Up trend = making higher highs. Down trend = making lower lows. Sideways = no clear direction.',
  },
  {
    term: 'Breakout',
    definition:
      "When a stock's price moves above a resistance level or below a support level. Often signals the start of a new trend.",
  },
  {
    term: 'Pullback',
    definition:
      'A temporary dip in an uptrend. Price goes down a bit but the overall upward direction remains. Often a good buying opportunity.',
  },
  {
    term: 'Short Selling',
    definition:
      'Betting that a stock will go DOWN. You borrow shares, sell them, and hope to buy them back cheaper later.',
  },
  {
    term: 'Short Squeeze',
    definition:
      'When a heavily shorted stock goes UP instead of down, forcing short sellers to buy back shares quickly, which pushes the price even higher.',
  },
  {
    term: 'Moving Average',
    definition:
      'The average price over a set number of days. Smooths out daily noise to show the underlying trend direction.',
  },
  {
    term: 'Liquidity',
    definition:
      'How easy it is to buy or sell a stock without moving the price. High liquidity = many buyers and sellers. Low liquidity = harder to trade.',
  },
  {
    term: 'Drawdown',
    definition:
      "How much your investment falls from its peak. A 20% drawdown means you're down 20% from your highest value.",
  },
  {
    term: 'Risk/Reward Ratio',
    definition:
      'How much you could gain compared to how much you could lose. A 3:1 ratio means you could make $3 for every $1 you risk.',
  },
  {
    term: 'Position Sizing',
    definition:
      'Deciding how much money to put into a single trade. The goal is to limit any single loss to a small % of your total portfolio.',
  },
  {
    term: 'Diversification',
    definition:
      'Spreading your money across different stocks to reduce risk. If one stock crashes, others may be fine.',
  },
];
