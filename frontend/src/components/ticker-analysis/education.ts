/**
 * Educational content for the Ticker Analysis page.
 * Each entry explains a metric or concept in plain English for users
 * with no trading or financial market background.
 */

// ── Metric Explanations (plain English) ──

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
    label: "MA Alignment",
    what: "Moving Averages smooth out price data to show the general direction of a stock. We look at three time windows: 20 days (short-term), 50 days (medium-term), and 200 days (long-term). 'Alignment' means checking if they're stacked in order.",
    readValue: (v) =>
      v === "bullish"
        ? "Bullish means the shorter-term average is above the longer-term average (SMA20 > SMA50 > SMA200). This is the ideal pattern — the stock is trending UP across all time frames."
        : v === "bearish"
          ? "Bearish means the shorter-term average is below the longer-term average. This suggests the stock is in a DOWNWARD trend."
          : "Mixed means there's no clear order. Some averages are above, some below — the stock doesn't have a clear direction right now.",
    whyMatters: "Think of it like checking the wind direction. Aligned averages = strong breeze pushing the stock one way. Mixed averages = calm, changing winds. Most traders prefer stocks with clear direction.",
    scoringImpact: "This is one of the heaviest-weighted factors. Bullish alignment contributes a large positive boost. Bearish alignment pushes the score negative. Mixed adds nothing.",
  },
  rsi: {
    label: "RSI (Relative Strength Index)",
    what: "RSI measures how strongly the stock has been moving recently, on a scale of 0 to 100. It tells us if a stock is being bought too aggressively (overbought) or sold too aggressively (oversold).",
    readValue: (v) => {
      if (v.includes("overbought")) return "Above 70 means the stock has risen very quickly. This can be a warning sign — what goes up fast can come down fast. But in strong trends, stocks can stay overbought for a while.";
      if (v.includes("oversold")) return "Below 30 means the stock has dropped sharply. This might be a bargain opportunity, but it could also mean something is fundamentally wrong.";
      if (v.includes("neutral_bullish")) return `RSI ${v.split(" ")[0]} is in the 50-70 range. This is the 'sweet spot' — the stock has upward momentum but isn't at risk of a pullback.`;
      if (v.includes("neutral_bearish")) return `RSI ${v.split(" ")[0]} is in the 30-50 range. The stock has downward pressure but isn't at extreme levels.`;
      return `RSI ${v} — neutral territory. The stock isn't being heavily bought or sold.`;
    },
    whyMatters: "RSI is like a speedometer for price movement. It helps answer: 'Is this move sustainable, or is it running out of steam?'",
    scoringImpact: "RSI in the 'neutral bullish' zone (50-70) adds positive points. Overbought (>85) without fundamental support triggers a dealbreaker. Oversold can go either way depending on other factors.",
  },
  adx: {
    label: "ADX (Average Directional Index)",
    what: "ADX measures how STRONG a trend is, not which direction. Think of it as a volume knob — higher numbers mean the trend has more power behind it.",
    readValue: (v) => {
      if (v.includes("strong") || v.includes("extreme")) return `ADX ${v.split(" ")[0]} — the trend is strong and has conviction behind it. Big moves are happening.`;
      if (v.includes("moderate")) return `ADX ${v.split(" ")[0]} — there's a developing trend with moderate strength. Enough to trade but keep position sizes reasonable.`;
      if (v.includes("weak")) return `ADX ${v.split(" ")[0]} — the market is range-bound or directionless. Random back-and-forth movement with no clear trend.`;
      return v;
    },
    whyMatters: "A stock can be going up, but if the ADX is low, the move might be weak and easily reversed. Strong trends (high ADX) give you confidence the move will continue.",
    scoringImpact: "Strong trends boost the score. Weak trends are neutral. Extreme ADX with poor positioning can signal a trend that's exhausted.",
  },
  atr_pct: {
    label: "ATR (Average True Range)",
    what: "ATR measures how much a stock typically moves each day (its volatility). We express it as a percentage of price so you can compare across stocks.",
    readValue: (v) => {
      const pct = v.split("%")[0];
      const numPct = parseFloat(pct);
      if (numPct > 5) return `ATR ${v} — HIGH volatility. This stock moves a LOT each day. Bigger potential gains, but also bigger potential losses.`;
      if (numPct > 2) return `ATR ${v} — moderate volatility. Normal stock movement with occasional bigger days.`;
      return `ATR ${v} — low volatility. This stock is steady and predictable. Smaller day-to-day moves.`;
    },
    whyMatters: "Volatility tells you how bumpy the ride will be. High volatility stocks need wider stop losses and smaller position sizes. Low volatility stocks are calmer but may have less profit potential.",
    scoringImpact: "Used to calculate suggested stop loss and position size. Extreme volatility is flagged as a dealbreaker. Normal volatility is ideal.",
  },
  volume_ratio: {
    label: "Volume Ratio",
    what: "Compares today's trading volume to the average volume over the last 10 days. It tells us if there's unusual interest in this stock right now.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 3) return `${v} — unusually HIGH volume. Something is happening! Big money is moving in or out of this stock.`;
      if (num > 1.5) return `${v} — above-average volume. More interest than usual, but not extreme.`;
      if (num >= 1) return `${v} — normal volume. Typical trading activity for this stock.`;
      return `${v} — below-average volume. Less interest than usual. Moves on low volume can be unreliable.`;
    },
    whyMatters: "High volume confirms that a price move is real. A stock going up on high volume = genuine buying pressure. A stock going up on low volume = might be a false move.",
    scoringImpact: "High volume adds positive points when direction aligns with the trend. Low volume doesn't hurt but doesn't help either.",
  },
  bb_position: {
    label: "Bollinger Band Position",
    what: "Bollinger Bands create a 'price channel' around a stock's moving average. The bands widen during volatility and narrow during calm periods. This tells us where the price sits within that channel.",
    readValue: (v) =>
      v === "above_upper"
        ? "Price is ABOVE the upper band — an unusually strong move. Could be a breakout or could be 'over-extended' and due for a pullback."
        : v === "below_lower"
          ? "Price is BELOW the lower band — an unusually sharp decline. Could be a buying opportunity if the stock is oversold, or a sign of trouble."
          : "Price is INSIDE the bands — normal trading within the expected range. No extreme pressure in either direction.",
    whyMatters: "When price touches or breaks through the bands, it signals something unusual is happening. Combined with other indicators, this can indicate breakout opportunities or warning signs.",
    scoringImpact: "Inside the bands = neutral. Above upper during a strong trend = positive. Below lower = typically negative unless other factors suggest a bounce.",
  },
  macd_status: {
    label: "MACD (Moving Average Convergence Divergence)",
    what: "MACD compares two moving averages to spot changes in momentum. It shows whether buying or selling pressure is getting stronger or weaker.",
    readValue: (v) =>
      v === "bullish"
        ? "Bullish — the shorter-term average crossed above the longer-term one. This is a classic 'buy signal' that momentum is shifting upward."
        : v === "bearish"
          ? "Bearish — the shorter-term average crossed below the longer-term one. A warning sign that downward momentum is building."
          : "Neutral — the two averages are close together. No clear momentum signal right now. The stock is 'coasting'.",
    whyMatters: "MACD helps you catch trend changes EARLY. It's like feeling the wind shift before the weather changes. Traders use it to time entries and exits.",
    scoringImpact: "Bullish MACD adds to the technical score. Bearish MACD subtracts. Neutral has no impact.",
  },
};

export const FUNDAMENTAL_LESSONS: Record<string, MetricLesson> = {
  market_cap: {
    label: "Market Cap",
    what: "The total value of the company. Calculated by multiplying the stock price by the number of shares. It tells you how big the company is.",
    readValue: (v) => `$${v} — this tells you the company's size. Large-cap (${v}B+) companies are established and stable. Small-cap (under $2B) are younger, riskier, but can grow faster.`,
    whyMatters: "Company size affects risk. Big companies (Apple, Microsoft) are less likely to crash but grow slower. Small companies can 10x but can also go to zero. Your strategy should match the size.",
    scoringImpact: "Market cap doesn't directly add or subtract from the score, but very small caps (< $50M) with poor profitability are flagged as a dealbreaker — too risky.",
  },
  pe_ratio: {
    label: "P/E Ratio (Price to Earnings)",
    what: "How much investors are paying for each dollar of the company's profit. If P/E is 20, you're paying $20 for every $1 of annual profit.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 50) return `P/E ${v} — HIGH. Investors expect big future growth. Common for exciting companies (tech, biotech). Risk: if growth doesn't happen, the stock can fall hard.`;
      if (num > 20) return `P/E ${v} — above average. Investors are optimistic about growth. Reasonable for most growing companies.`;
      if (num > 0) return `P/E ${v} — moderate to low. The stock is reasonably priced relative to earnings. Could be a value opportunity, or the market sees problems ahead.`;
      return `P/E ${v} — negative. The company is LOSING money. Not necessarily bad (many young companies are profitable on purpose), but riskier.`;
    },
    whyMatters: "P/E is like a price tag on a company's earnings. A high P/E means you're paying a premium — you need strong growth to justify it. A low P/E can mean a bargain or a trap.",
    scoringImpact: "Very high P/E (>50) without strong growth = negative. Reasonable P/E (10-25) = positive. Negative P/E = neutral (common for growth companies).",
  },
  eps: {
    label: "EPS (Earnings Per Share)",
    what: "The company's profit divided by its number of shares. It tells you how much profit each share of stock 'owns'.",
    readValue: (v) => `$${v} per share. This is the company's per-share profit. Higher EPS means the company is more profitable. Consistent growth in EPS over years is a hallmark of a quality company.`,
    whyMatters: "EPS is the foundation of stock value. Over the long run, stock prices follow earnings. If EPS keeps growing, the stock price usually follows.",
    scoringImpact: "Positive and growing EPS = positive score contribution. Negative EPS = neutral (common in early-stage companies).",
  },
  profit_margin: {
    label: "Profit Margin",
    what: "The percentage of revenue that the company keeps as profit. If a company makes $100 in sales and has a 20% margin, it keeps $20 as profit.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 20) return `${v}% — excellent! The company is very efficient at turning revenue into profit.`;
      if (num > 10) return `${v}% — good. Healthy profitability with room to grow.`;
      if (num > 0) return `${v}% — positive but thin. The company is profitable but doesn't keep much from each sale.`;
      return `${v}% — negative. The company spends more than it earns. Common for young/high-growth companies.`;
    },
    whyMatters: "Profit margin shows how much pricing power and efficiency a company has. High margins = strong competitive advantage (like software companies). Low margins = tough business (like grocery stores).",
    scoringImpact: "Positive margins contribute to the score. Negative margins with small market cap triggers a dealbreaker. High margins = strong positive.",
  },
  debt_to_equity: {
    label: "D/E Ratio (Debt to Equity)",
    what: "How much debt the company has compared to its own money (equity). A D/E of 1 means the company has equal amounts of debt and equity.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 2) return `${v} — HIGH debt. The company owes a lot relative to its own money. Riskier because debt payments eat into profits.`;
      if (num > 0.5) return `${v} — moderate debt. Normal for most companies. Some debt is healthy — it funds growth.`;
      if (num >= 0) return `${v} — low debt. Conservative financial management. Less risk, but might be growing slower.`;
      return "Negative — the company has more cash than debt. Very safe financially, but unusual for growing companies.";
    },
    whyMatters: "Too much debt can sink a company if business slows down (like high mortgage payments if you lose your job). Too little debt might mean the company isn't investing in growth.",
    scoringImpact: "High debt (>2) is negative. Moderate debt (0.5-1.5) is neutral. Very low or negative debt = slightly positive (financially conservative).",
  },
  revenue_growth_yoy: {
    label: "Revenue Growth",
    what: "How much the company's sales have grown compared to the same period last year. Shows if the business is expanding.",
    readValue: (v) => {
      const num = parseFloat(v) * 100;
      if (num > 30) return `${v}% — RAPID growth. The company is expanding quickly. This is exciting but can be risky if growth isn't profitable.`;
      if (num > 10) return `${v}% — solid growth. Healthy expansion without being reckless. Ideal for most investors.`;
      if (num > 0) return `${v}% — modest growth. The company is growing, but slowly. Could be a mature company or facing competition.`;
      return `${v}% — NEGATIVE growth. Sales are shrinking. This is a red flag unless there's a clear one-time reason.`;
    },
    whyMatters: "Growing revenue means more customers, more sales, a growing business. Shrinking revenue means the opposite. It's the most basic measure of business health.",
    scoringImpact: "Strong growth adds to the score. Negative growth subtracts. This is one of the most important fundamental factors.",
  },
  fcf_yield: {
    label: "FCF Yield (Free Cash Flow Yield)",
    what: "Free Cash Flow is the cash a company generates after paying for everything it needs to keep running. FCF Yield compares that cash to the stock price — like a 'cash on cash' return.",
    readValue: (v) => {
      const num = parseFloat(v) * 100;
      if (num > 8) return `${v}% — HIGH. The company generates lots of cash relative to its price. A sign of a quality business.`;
      if (num > 4) return `${v}% — good. Healthy cash generation.`;
      if (num > 0) return `${v}% — positive but low. Generates some cash but not a huge amount.`;
      return `${v}% — negative. The company is burning cash. Very common for high-growth companies. Not a problem if revenue is growing fast.`;
    },
    whyMatters: "Cash is king. Companies that generate lots of free cash can invest in growth, pay dividends, buy back stock, or weather hard times. Negative FCF means they need to borrow or raise money.",
    scoringImpact: "Positive FCF yield = positive score contribution. Negative = neutral or slightly negative. Strong FCF yield with growth = very positive.",
  },
  dividend_yield: {
    label: "Dividend Yield",
    what: "The percentage of the stock price that the company pays back to shareholders each year as cash payments (dividends).",
    readValue: (v) => {
      const num = parseFloat(v) * 100;
      if (num > 4) return `${v}% — HIGH yield. The company returns a lot of cash to shareholders. Can be a sign of a mature, stable business.`;
      if (num > 1) return `${v}% — moderate yield. A reasonable income stream plus growth potential.`;
      return `${v}% — low or no dividend. The company reinvests profits into growth instead of paying shareholders. Normal for growth companies.`;
    },
    whyMatters: "Dividends are like rent on your stock. Some investors want regular income (retirees). Others prefer companies that reinvest for growth. Neither is better — it depends on your goals.",
    scoringImpact: "High dividend yield with sustainable earnings = positive. No dividend = neutral (expected for growth stocks). Suspended dividend = negative flag.",
  },
};

export const EARNINGS_LESSONS: Record<string, MetricLesson> = {
  last_surprise_pct: {
    label: "Earnings Surprise",
    what: "Companies report profits every 3 months. Analysts predict what the number will be. The 'surprise' is how much the actual result beat (or missed) those predictions, shown as a percentage.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 10) return `${v}% BEAT — the company crushed expectations! This usually pushes the stock price up.`;
      if (num > 0) return `${v}% beat — the company did better than expected. A positive sign.`;
      if (num > -5) return `${v}% miss — slightly below expectations. Not a disaster, but not ideal.`;
      return `${v}% miss — significantly below expectations. This can hit the stock price hard.`;
    },
    whyMatters: "Earnings surprises show whether the company is performing better or worse than the 'consensus' view. Consistent positive surprises suggest the business is stronger than people think.",
    scoringImpact: "Positive surprises = score boost. Large negative surprises = score penalty. Consistent beaters get higher scores.",
  },
  beat_rate: {
    label: "Beat Rate",
    what: "Out of the last several earnings reports, how many beat expectations? '3/4' means they beat 3 out of the last 4 quarters.",
    readValue: (v) => `${v} quarters beat expectations. A company that consistently beats (like 4/4) is showing strong execution. One that frequently misses is struggling.`,
    whyMatters: "A single beat or miss could be luck. A consistent track record tells you the company has real momentum (or real problems).",
    scoringImpact: "High beat rate (3+/4) = strong positive. Low beat rate (1/4 or 0/4) = negative. This is a reliable quality indicator.",
  },
  next_earnings_date: {
    label: "Next Earnings Date",
    what: "The date when the company will next report its quarterly results. Earnings day is when the biggest stock moves happen.",
    readValue: (v) => {
      if (!v || v === "—") return "No upcoming earnings date available.";
      const daysUntil = Math.ceil((new Date(v).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
      if (daysUntil <= 7) return `${v} — coming up SOON (${daysUntil} days). Expect higher volatility around this date. Consider waiting until after earnings to enter a new position.`;
      if (daysUntil <= 30) return `${v} — about ${daysUntil} days away. The stock may start 'pricing in' expectations soon.`;
      return `${v} — ${daysUntil} days away. Plenty of time before the next report.`;
    },
    whyMatters: "Earnings reports cause the biggest price swings. A stock can move 10-20% in a single day. If you're risk-averse, wait until after earnings. If you're confident in the result, you can profit from the move.",
    scoringImpact: "Does not directly impact the score, but is shown so you can make informed timing decisions.",
  },
};

export const SENTIMENT_LESSONS: Record<string, MetricLesson> = {
  analyst_consensus: {
    label: "Analyst Consensus",
    what: "Professional stock analysts study the company and give their opinion: Buy, Hold, or Sell. This is the average of all analysts covering the stock.",
    readValue: (v) => {
      if (v.includes("Buy") || v === "Strong Buy") return `${v} — analysts are BULLISH. Most experts think this stock will go up.`;
      if (v === "Hold" || v === "Neutral") return `${v} — analysts are neutral. They don't see strong reasons to buy or sell at current prices.`;
      if (v.includes("Sell")) return `${v} — analysts are BEARISH. Many experts recommend selling. This is a warning sign.`;
      return `${v} — analyst consensus.`;
    },
    whyMatters: "Analyst ratings give you a 'second opinion' on the stock. But remember: analysts are often too optimistic (they don't like to say Sell). Take Strong Buy ratings seriously, but do your own research too.",
    scoringImpact: "Strong Buy consensus = positive score contribution. Hold/Neutral = neutral. Sell = negative. Heavy weight on this factor.",
  },
  insider_status: {
    label: "Insider Activity",
    what: "Company insiders (executives, directors) are required to report when they buy or sell their own stock. Their actions reveal what they really think about the company's prospects.",
    readValue: (v) =>
      v === "buying"
        ? "Insiders are BUYING — they're putting their own money into the stock. This is one of the most BULLISH signals. They know the business better than anyone."
        : v === "selling"
          ? "Insiders are SELLING — but context matters. Executives often sell for personal reasons (diversification, taxes, buying a house). Heavy selling by multiple insiders is a warning sign."
          : "No significant insider activity detected recently. Neither strongly bullish or bearish from an insider perspective.",
    whyMatters: "Insiders have the most accurate information about their company. When they buy, it's because they genuinely believe the stock will go up. When multiple insiders sell heavily, they might see trouble ahead.",
    scoringImpact: "Insider buying = positive boost. Heavy insider selling = negative. This factor can override other signals when extreme.",
  },
  short_interest_pct: {
    label: "Short Interest",
    what: "The percentage of shares that investors have 'borrowed and sold' hoping to buy them back cheaper later. It measures how many people are betting the stock will go DOWN.",
    readValue: (v) => {
      const num = parseFloat(v);
      if (num > 20) return `${v}% — VERY HIGH short interest. A huge number of people are betting against this stock. If they're wrong, a 'short squeeze' could rocket the price up.`;
      if (num > 10) return `${v}% — high short interest. Significant bearish sentiment. Could mean trouble, or could be a squeeze opportunity.`;
      if (num > 3) return `${v}% — moderate. Some bearish bets but nothing unusual.`;
      return `${v}% — low. Very few people are betting against this stock. Generally a positive sign.`;
    },
    whyMatters: "High short interest is controversial — it means many smart investors think the stock will fall. But if they're wrong, they're forced to buy back shares, creating a 'squeeze' that pushes prices even higher. It's a double-edged sword.",
    scoringImpact: "Very high short interest (>30%) is flagged as a dealbreaker — it signals serious doubt about the company. Moderate levels add interest but don't change the score much.",
  },
};

export const RISK_LESSONS: Record<string, MetricLesson> = {
  volatility_regime: {
    label: "Volatility Regime",
    what: "A category for how much this stock moves day-to-day. Based on its ATR percentage compared to other stocks.",
    readValue: (v) =>
      v === "low"
        ? "LOW volatility — this stock is very steady. Calm, predictable moves. Good for conservative traders."
        : v === "normal"
          ? "NORMAL volatility — typical day-to-day movement. Most stocks fall in this range."
          : v === "high"
            ? "HIGH volatility — this stock moves a lot. Expect bigger swings. Higher potential reward, higher risk."
            : "EXTREME volatility — very unusual moves. Either a huge opportunity or a dangerous situation. Requires wider stops and smaller positions.",
    whyMatters: "Your strategy should match the stock's volatility. A calm stock needs tight stops. A volatile stock needs room to breathe. Don't trade a high-volatility stock with a low-volatility mindset.",
    scoringImpact: "Normal volatility = ideal. Low = slightly positive (stable). High = negative (riskier). Extreme = dealbreaker.",
  },
  suggested_stop_pct: {
    label: "Suggested Stop Loss",
    what: "The recommended 'emergency exit' price. If the stock falls below this level, it means the trade idea is likely wrong and you should sell to limit your losses.",
    readValue: (v) => `${v}% below entry. Based on the stock's volatility (ATR). Think of it like a 'circuit breaker' — if the stock drops this much, something unexpected is happening, and it's safer to exit.`,
    whyMatters: "Stop losses are the single most important risk management tool. They prevent a small loss from becoming a disaster. Without stops, a -10% loss can turn into -50%.",
    scoringImpact: "Not a scoring factor — it's a risk management recommendation calculated from the stock's volatility.",
  },
  suggested_position_size_pct: {
    label: "Suggested Position Size",
    what: "What percentage of your total trading money should go into this stock. Based on risk: higher volatility = smaller position.",
    readValue: (v) => `${v}% of your portfolio. This is calculated conservatively to protect your capital. High volatility stocks get smaller sizes. Low volatility stocks can have larger sizes.`,
    whyMatters: "Position sizing is how professionals avoid blowing up. Even the best traders are wrong 40% of the time. By keeping position sizes reasonable, no single loss can wipe you out.",
    scoringImpact: "Not a scoring factor — it's a risk management recommendation.",
  },
  max_risk_per_trade_pct: {
    label: "Max Risk Per Trade",
    what: "The maximum percentage of your portfolio you should risk on this single trade. The default is 1%, a common rule used by professional traders.",
    readValue: (v) => `${v}% max risk. Professional risk management rule: never risk more than this on any single trade. This ensures you can survive a string of losses.`,
    whyMatters: "If you risk 1% per trade, you'd need 100 consecutive losses to go to zero. If you risk 10% per trade, just 10 losses wipes you out. This rule is what keeps traders IN the game long-term.",
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
    title: "Technical Analysis",
    whatItIs: "Technical analysis studies the stock's PRICE and VOLUME data to gauge direction and momentum. It doesn't care about the company's products or profits — it only looks at what the market is DOING.",
    whyItMatters: "In the short to medium term, price patterns and momentum matter more than company fundamentals. A stock can have great products but a terrible chart. Technical analysis helps you buy at the right time.",
    howScoreWorks: "We look at 7 factors: MA alignment (trend direction), RSI (momentum), ADX (trend strength), ATR (volatility), Volume Ratio (interest), Bollinger Band position, and MACD (momentum signal). Each factor is scored, then combined into a -1.0 to +1.0 score. The trend alignment and RSI get the most weight.",
  },
  fundamental: {
    title: "Fundamental Analysis",
    whatItIs: "Fundamental analysis looks at the COMPANY's financial health: how much money it makes, how fast it's growing, how much debt it has. It answers: 'Is this a good business?'",
    whyItMatters: "A stock's price eventually follows its earnings. Good fundamentals don't guarantee the stock will go up tomorrow, but they strongly predict where it'll be in 1-3 years. Technical + fundamental together give you the complete picture.",
    howScoreWorks: "We score 8 factors: market cap (size), P/E (valuation), EPS (profitability), profit margin (efficiency), debt/equity (financial risk), revenue growth (expansion), free cash flow yield (cash generation), and dividend yield (shareholder returns). Positive values = good. Negative values = concerning. The final score combines these into -1.0 to +1.0.",
  },
  earnings: {
    title: "Earnings Analysis",
    whatItIs: "Companies report their financial results every 3 months (quarterly earnings). This analysis looks at their track record of beating or missing expectations, and when the next report is due.",
    whyItMatters: "Earnings reports cause the biggest single-day moves in stock prices (5-20% is common). Knowing the earnings track record helps you assess whether the company consistently delivers or frequently disappoints.",
    howScoreWorks: "We look at the latest surprise percentage, the beat rate (how many of the last 4 reports beat expectations), and the average stock reaction to earnings. Consistent beaters get positive scores. Consistent missers get negative scores.",
  },
  sentiment: {
    title: "Market Sentiment",
    whatItIs: "Sentiment measures what OTHER market participants think about the stock: professional analysts, company insiders, and short sellers. It's like getting a 'consensus opinion' from everyone watching the stock.",
    whyItMatters: "When everyone is bullish, the stock usually goes up — until it doesn't. When insiders are buying heavily, it's one of the most reliable signals. When short interest is extreme, be careful.",
    howScoreWorks: "We combine: analyst consensus (weighted heavily), insider buying/selling activity, institutional ownership, short interest percentage, days to cover, and beta (how much the stock moves relative to the market). The overall range is -1.0 to +1.0.",
  },
  risk: {
    title: "Risk Assessment",
    whatItIs: "Risk analysis tells you how DANGEROUS this trade is and how to manage that danger. It's not about predicting direction — it's about protecting your money.",
    whyItMatters: "Even the best analysis can be wrong. Risk management is what separates professionals from amateurs. Professionals focus on how MUCH they can lose. Amateurs only think about how MUCH they can make.",
    howScoreWorks: "We assess volatility (ATR percentage), calculate an appropriate stop loss level, determine the right position size based on volatility, and suggest how much of your portfolio to risk. The score ranges from -1.0 (extreme risk) to +1.0 (very safe).",
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
  dealbreakers: string[],
): WalkthroughStep[] {
  const weighted = moduleScores.reduce((s, m) => s + m.score, 0) / Math.max(moduleScores.length, 1);
  const steps: WalkthroughStep[] = [];

  steps.push({
    module: "Module Scores",
    score: `avg ${(weighted >= 0 ? '+' : '')}${weighted.toFixed(2)}`,
    explanation: `Calculated individual scores for each analysis module:\n${
      moduleScores.map(m => {
        const emoji = m.score >= 0.3 ? '✅' : m.score >= -0.1 ? '➖' : '⚠️';
        return `${emoji} ${m.label}: ${(m.score >= 0 ? '+' : '')}${m.score.toFixed(2)}`;
      }).join('\n')
    }\n\nThese scores are averaged to determine the overall signal. Positive scores = bullish, negative = bearish.`,
  });

  steps.push({
    module: "Weighted Average",
    score: (weighted >= 0 ? '+' : '') + weighted.toFixed(2),
    explanation: `The average of all module scores is ${(weighted >= 0 ? '+' : '')}${weighted.toFixed(2)}. This represents the overall balance of bullish vs bearish signals across technical, fundamental, earnings, sentiment, and risk analysis.`,
  });

  if (dealbreakers.length > 0) {
    steps.push({
      module: "Dealbreakers",
      score: `${dealbreakers.length} issue(s)`,
      explanation: `Found ${dealbreakers.length} critical issue(s) that override the score:\n${dealbreakers.map(d => `• ${d}`).join('\n')}\n\nThese issues signal significant risk regardless of otherwise positive indicators.`,
    });
  } else {
    steps.push({
      module: "Dealbreaker Check",
      score: "PASSED",
      explanation: "No critical issues found that would override the score. All modules passed the minimum thresholds for consideration.",
    });
  }

  const actionExplanations: Record<string, string> = {
    BUY: "Strong positive signal. All indicators align favorably. Consider entering a position within the suggested entry zone.",
    WATCH: "Mixed or mildly positive signals. The setup has potential but needs more confirmation. Wait for better entry or more data.",
    HOLD: "Neutral signals. No strong reason to buy or sell. If you own it, keep it. If not, wait for a clearer signal.",
    AVOID: "Negative signals dominate. Significant issues identified. Stay away until conditions improve.",
    SELL: "Clear negative signals. If you own this stock, consider selling. If not, do not buy.",
  };
  const baseAction = action.split("—")[0].trim();
  const actionExplanation = actionExplanations[baseAction] ?? `${baseAction} — proceed with caution according to the analysis.`;

  steps.push({
    module: "Action",
    score: `${action} (${conviction}/10)`,
    explanation: `Score ${(weighted >= 0 ? '+' : '')}${weighted.toFixed(2)} mapped to action: ${action} with conviction ${conviction}/10.\n\n${actionExplanation}`,
  });

  return steps;
}

// ── Glossary of Common Terms ──

export interface GlossaryEntry {
  term: string;
  definition: string;
}

export const GLOSSARY: GlossaryEntry[] = [
  { term: "Bullish", definition: "Expecting the price to go UP. Named after a bull attacking by lifting upward with its horns." },
  { term: "Bearish", definition: "Expecting the price to go DOWN. Named after a bear swiping downward with its paws." },
  { term: "Volatility", definition: "How much and how quickly a stock's price moves up and down. High volatility = big swings. Low volatility = steady prices." },
  { term: "Momentum", definition: "The speed and strength of a price move. A stock with strong momentum keeps moving in the same direction." },
  { term: "Trend", definition: "The general direction a stock is moving over time. Up trend = making higher highs. Down trend = making lower lows. Sideways = no clear direction." },
  { term: "Breakout", definition: "When a stock's price moves above a resistance level or below a support level. Often signals the start of a new trend." },
  { term: "Pullback", definition: "A temporary dip in an uptrend. Price goes down a bit but the overall upward direction remains. Often a good buying opportunity." },
  { term: "Short Selling", definition: "Betting that a stock will go DOWN. You borrow shares, sell them, and hope to buy them back cheaper later." },
  { term: "Short Squeeze", definition: "When a heavily shorted stock goes UP instead of down, forcing short sellers to buy back shares quickly, which pushes the price even higher." },
  { term: "Moving Average", definition: "The average price over a set number of days. Smooths out daily noise to show the underlying trend direction." },
  { term: "Liquidity", definition: "How easy it is to buy or sell a stock without moving the price. High liquidity = many buyers and sellers. Low liquidity = harder to trade." },
  { term: "Drawdown", definition: "How much your investment falls from its peak. A 20% drawdown means you're down 20% from your highest value." },
  { term: "Risk/Reward Ratio", definition: "How much you could gain compared to how much you could lose. A 3:1 ratio means you could make $3 for every $1 you risk." },
  { term: "Position Sizing", definition: "Deciding how much money to put into a single trade. The goal is to limit any single loss to a small % of your total portfolio." },
  { term: "Diversification", definition: "Spreading your money across different stocks to reduce risk. If one stock crashes, others may be fine." },
];
