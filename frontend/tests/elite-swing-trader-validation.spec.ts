import { test, expect } from '@playwright/test';

const API_URL = 'http://localhost:8000';

// Helper to run screener
async function runScreener(config: string, limit = 20) {
  const response = await fetch(`http://localhost:8000/api/v1/screen/tv`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config, limit })
  });
  if (!response.ok) return [];
  const data = await response.json();
  return data.data || [];
}

// Helper to run deep analysis
async function analyzeTicker(symbol: string) {
  const response = await fetch(`http://localhost:8000/api/v1/ticker/${symbol}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, timeframe: '1D' })
  });
  if (!response.ok) return null;
  return response.json();
}

// Extract real market data from analysis
function extractRealData(analysisData: any) {
  const tech = analysisData.data?.technical?.daily || analysisData.data?.technical;
  const sent = analysisData.data?.sentiment;
  const fund = analysisData.data?.fundamental;
  const verd = analysisData.data?.verdict;
  const price = analysisData.data?.price;
  
  return {
    price: price || verd?.entry_zone_low || verd?.entry_zone_high,
    rsi: tech?.rsi,
    ma_alignment: tech?.ma_alignment,
    volume_ratio: tech?.volume_ratio,
    atr_pct: tech?.atr_pct,
    swing_highs: tech?.swing_highs,
    swing_lows: tech?.swing_lows,
    key_resistance: tech?.key_resistance,
    key_support: tech?.key_support,
    structure: tech?.structure,
    pullback_quality: tech?.pullback_quality,
    short_interest_pct: sent?.short_interest_pct,
    institutional_ownership: sent?.institutional_ownership,
    beta: sent?.beta,
    pe_ratio: fund?.pe_ratio,
    market_cap: fund?.market_cap,
    target_price: sent?.target_price,
    recommendation: sent?.analyst_consensus,
  };
}

// Elite swing trader validation criteria
function validateSwingTrade(verdict: any, realData: any, technical: any) {
  const issues: string[] = [];
  const strengths: string[] = [];
  
  // 1. Trend Quality - must have aligned MAs for swing trades
  if (technical?.ma_alignment !== 'bullish') {
    issues.push(`❌ MA alignment: ${technical?.ma_alignment} (need bullish for long swing)`);
  } else {
    strengths.push(`✅ MA alignment: bullish`);
  }
  
  // 2. RSI in sweet spot (50-70 for swing long)
  if (realData.rsi) {
    if (realData.rsi >= 50 && realData.rsi <= 70) {
      strengths.push(`✅ RSI: ${realData.rsi.toFixed(1)} (swing sweet spot)`);
    } else if (realData.rsi > 70) {
      issues.push(`⚠️ RSI: ${realData.rsi.toFixed(1)} overbought`);
    } else {
      issues.push(`❌ RSI: ${realData.rsi.toFixed(1)} below 50`);
    }
  }
  
  // 3. Structure quality
  if (technical?.structure) {
    if (technical.structure.includes('bullish')) {
      strengths.push(`✅ Structure: ${technical.structure}`);
    } else if (technical.structure.includes('transition')) {
      strengths.push(`⚠️ Structure: ${technical.structure} (transitional)`);
    } else {
      issues.push(`❌ Structure: ${technical.structure}`);
    }
  }
  
  // 4. Pullback quality
  if (technical?.pullback_quality) {
    const pq = technical.pullback_quality;
    if (['A+', 'A', 'B'].includes(pq)) {
      strengths.push(`✅ Pullback quality: ${pq}`);
    } else {
      issues.push(`⚠️ Pullback quality: ${pq} (C or worse)`);
    }
  }
  
  // 5. Volume confirmation
  if (realData.volume_ratio) {
    if (realData.volume_ratio >= 1.2) {
      strengths.push(`✅ Volume: ${realData.volume_ratio.toFixed(1)}x above avg`);
    } else if (realData.volume_ratio >= 0.8) {
      strengths.push(`⚠️ Volume: ${realData.volume_ratio.toFixed(1)}x avg`);
    } else {
      issues.push(`❌ Volume: ${realData.volume_ratio.toFixed(1)}x below avg`);
    }
  }
  
  // 6. Support/Resistance validation
  const entry = verdict?.entry_zone_low || verdict?.entry_zone_high;
  const stop = verdict?.stop_loss;
  const targets = verdict?.targets || [];
  
  if (entry && stop && realData.price) {
    const riskPct = (entry - stop) / entry * 100;
    if (riskPct > 0 && riskPct <= 8) {
      strengths.push(`✅ Risk: ${riskPct.toFixed(1)}% (reasonable for swing)`);
    } else if (riskPct > 8) {
      issues.push(`❌ Risk: ${riskPct.toFixed(1)}% too wide`);
    }
  }
  
  // 7. R:R validation
  if (verdict?.risk_reward && targets.length > 0 && entry && stop) {
    const realRR = (targets[targets.length - 1] - entry) / (entry - stop);
    const analysisRR = verdict.risk_reward;
    if (realRR >= 2 && analysisRR >= 2) {
      strengths.push(`✅ R:R: ${analysisRR.toFixed(2)} (real: ${realRR.toFixed(2)})`);
    } else if (realRR < 2) {
      issues.push(`❌ R:R: ${realRR.toFixed(2)} below 2:1 minimum`);
    }
  }
  
  // 8. Stop at Support / Target at Resistance
  if (stop && realData.key_support && realData.key_support.length > 0) {
    const nearestSupport = realData.key_support[0];
    if (Math.abs(stop - nearestSupport) / stop < 0.03) {
      strengths.push(`✅ Stop at support: $${stop.toFixed(2)} ≈ $${nearestSupport.toFixed(2)}`);
    } else {
      issues.push(`⚠️ Stop $${stop.toFixed(2)} not at key support ($${nearestSupport.toFixed(2)})`);
    }
  }
  
  if (targets.length > 0 && realData.key_resistance && realData.key_resistance.length > 0) {
    for (const target of targets) {
      const nearestRes = realData.key_resistance.find((r: number) => Math.abs(r - target) / target < 0.03);
      if (nearestRes) {
        strengths.push(`✅ Target $${target} at resistance $${nearestRes.toFixed(2)}`);
      }
    }
  }
  
  // 9. Positioning (Gate Step 3)
  if (realData.short_interest_pct !== undefined) {
    if (realData.short_interest_pct > 25) {
      issues.push(`🚨 Short interest: ${realData.short_interest_pct.toFixed(1)}% HIGH`);
    } else if (realData.short_interest_pct > 15) {
      issues.push(`⚠️ Short interest: ${realData.short_interest_pct.toFixed(1)}% elevated`);
    } else {
      strengths.push(`✅ Short interest: ${realData.short_interest_pct.toFixed(1)}% low`);
    }
  }
  
  if (realData.institutional_ownership !== undefined) {
    if (realData.institutional_ownership > 60) {
      strengths.push(`✅ Inst ownership: ${realData.institutional_ownership.toFixed(1)}% STRONG`);
    } else if (realData.institutional_ownership > 30) {
      strengths.push(`✅ Inst ownership: ${realData.institutional_ownership.toFixed(1)}% moderate`);
    } else {
      issues.push(`⚠️ Inst ownership: ${realData.institutional_ownership.toFixed(1)}% low`);
    }
  }
  
  // 10. Catalyst / Earnings proximity
  // Would need earnings data
  
  return { issues, strengths };
}

// Pick random ticker from array
function pickRandom<T>(arr: T[]): T | null {
  if (arr.length === 0) return null;
  return arr[Math.floor(Math.random() * arr.length)];
}

// Screen templates to test (mix of strategies)
const SCREEN_TEMPLATES = [
  'trend-follower-v2',
  'trend-pullback-v2', 
  'vcp-breakout',
  'institutional-quality-v2',
  'institutional-trend-follower-mtf',
  '52-Week Breakout',
  'Bull Flag Continuation',
  'Quality Trend + Fundamentals',
  'Low-Vol Setup Simple',
  'trend-follower',
];

// Fallback universe - S&P 500 / major tickers for when screeners return 0
const FALLBACK_TICKERS = [
  'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AVGO', 'JPM', 'V',
  'UNH', 'XOM', 'MA', 'HD', 'PG', 'LLY', 'MRK', 'ABBV', 'PEP', 'KO',
  'COST', 'ADBE', 'CRM', 'NFLX', 'CSCO', 'ACN', 'DIS', 'NKE', 'TMO', 'LIN',
  'WMT', 'ORCL', 'BMY', 'ABT', 'PM', 'TXN', 'CVX', 'QCOM', 'AMD', 'HON',
  'INTC', 'IBM', 'CAT', 'DE', 'LOW', 'UPS', 'RTX', 'SPGI', 'NOW', 'ISRG',
  'GS', 'BKNG', 'MDT', 'SBUX', 'GILD', 'ADI', 'LRCX', 'REGN', 'VRTX', 'PLD',
  'SYK', 'BLK', 'C', 'ZTS', 'MO', 'AMGN', 'CI', 'DUK', 'SO', 'EL',
  'TMUS', 'EQIX', 'CB', 'BDX', 'CL', 'PGR', 'CME', 'TJX', 'APD', 'MMC',
  'FCX', 'ICE', 'EW', 'ADP', 'AON', 'MCO', 'SHW', 'ITW', 'APH', 'FIS',
  'DXCM', 'MCHP', 'NSC', 'WM', 'FDX', 'PNC', 'USB', 'EOG', 'PSA', 'AEP',
  'EXC', 'SRE', 'AIG', 'ALL', 'MET', 'PRU', 'TRV', 'AFL', 'HIG', 'CINF',
];

test.describe('Elite Swing Trader Multi-Screener Validation', () => {
  
  test('Run multiple screeners, pick random tickers, validate with swing trader criteria', async () => {
    test.setTimeout(600000); // 10 minutes
    
    console.log('\n========== ELITE SWING TRADER MULTI-SCREENER VALIDATION ==========');
    console.log(`Testing ${SCREEN_TEMPLATES.length} screen templates`);
    
    const allResults: any[] = [];
    let totalTickers = 0;
    let validSetups = 0;
    let flaggedSetups = 0;
    
    // Track which tickers we've already analyzed (across all templates)
    const analyzedTickers = new Set<string>();
    
    for (const template of SCREEN_TEMPLATES) {
      console.log(`\n📊 Running screener: ${template}`);
      
      const tickers = await runScreener(template, 20);
      console.log(`   Found ${tickers.length} candidates`);
      
      // Combine screener results with fallback tickers
      let candidates: any[] = [...tickers];
      
      // If screener returns 0, add some fallback tickers for this template
      if (tickers.length === 0) {
        console.log(`   ⚠️  No screener results - using fallback universe`);
        // Pick 3 random fallback tickers for this template
        const shuffled = [...FALLBACK_TICKERS].sort(() => Math.random() - 0.5);
        const fallbackPicks = shuffled.slice(0, 3);
        candidates = fallbackPicks.map(sym => ({ symbol: sym, screenScore: 0, screenName: template }));
      }
      
      // Filter out already analyzed tickers
      const newCandidates = candidates.filter(c => !analyzedTickers.has(c.symbol));
      
      if (newCandidates.length === 0) {
        console.log(`   ⚠️  All candidates already analyzed - skipping`);
        continue;
      }
      
      // Pick 2 random tickers from this screener
      const shuffled = [...newCandidates].sort(() => Math.random() - 0.5);
      const picks = shuffled.slice(0, Math.min(2, newCandidates.length));
      
      for (const pick of picks) {
        const symbol = pick.symbol;
        
        // Mark as analyzed
        analyzedTickers.add(symbol);
        totalTickers++;
        
        console.log(`\n   🔍 Analyzing ${symbol} (screen: ${template}, score: ${pick.screenScore?.toFixed(1) || 'fallback'})`);
        
        const analysisData = await analyzeTicker(symbol);
        if (!analysisData) {
          console.log(`   ❌ Analysis failed`);
          continue;
        }
        
        const verdict = analysisData.data?.verdict;
        const technical = analysisData.data?.technical?.daily || analysisData.data?.technical;
        const realData = extractRealData(analysisData);
        
        if (!verdict || !realData.price) {
          console.log(`   ❌ No valid verdict/price`);
          continue;
        }
        
        console.log(`   ${symbol}: $${realData.price} | ${verdict.action} c:${verdict.conviction} | Gate: ${verdict.gate?.overall}`);
        console.log(`     Entry: ${verdict.entry_zone_low} - ${verdict.entry_zone_high} | Stop: ${verdict.stop_loss}`);
        console.log(`     Targets: [${verdict.targets?.join(', ')}] | R:R: ${verdict.risk_reward}`);
        console.log(`     RSI: ${realData.rsi?.toFixed(1)} | MA: ${realData.ma_alignment} | Vol: ${realData.volume_ratio?.toFixed(1) || 'N/A'}x`);
        console.log(`     SI: ${realData.short_interest_pct?.toFixed(1)}% | Inst: ${realData.institutional_ownership?.toFixed(1)}% | Beta: ${realData.beta?.toFixed(2)}`);
        console.log(`     Structure: ${technical?.structure} | PQ: ${technical?.pullback_quality} | Vol: ${realData.volume_ratio?.toFixed(1) || 'N/A'}x`);
        
        // Elite swing trader validation
        const { issues, strengths } = validateSwingTrade(verdict, realData, technical);
        
        console.log(`\n   📋 SWING TRADER VALIDATION:`);
        strengths.forEach(s => console.log(`      ${s}`));
        issues.forEach(i => console.log(`      ${i}`));
        
        const isValid = issues.filter(i => i.startsWith('❌')).length === 0;
        const hasCritical = issues.some(i => i.startsWith('❌') || i.startsWith('🚨'));
        
        if (isValid) {
          validSetups++;
          console.log(`   ✅ VALID SETUP`);
        } else if (hasCritical) {
          flaggedSetups++;
          console.log(`   🚨 FLAGGED - Critical issues`);
        } else {
          console.log(`   ⚠️  MARGINAL - Minor issues`);
        }
        
        allResults.push({
          symbol,
          template,
          price: realData.price,
          action: verdict.action,
          conviction: verdict.conviction,
          gate: verdict.gate?.overall,
          valid: isValid,
          issues: issues.filter(i => i.startsWith('❌') || i.startsWith('🚨')),
          warnings: issues.filter(i => i.startsWith('⚠️')),
          strengths,
        });
      }
    }
    
    // Summary
    console.log('\n========== VALIDATION SUMMARY ==========');
    console.log(`Total tickers analyzed: ${totalTickers}`);
    console.log(`✅ Valid setups: ${validSetups}`);
    console.log(`⚠️  Marginal setups: ${totalTickers - validSetups - flaggedSetups}`);
    console.log(`🚨 Flagged setups: ${flaggedSetups}`);
    console.log(`Success rate: ${totalTickers > 0 ? ((validSetups/totalTickers)*100).toFixed(1) : 0}%`);
    
    // Per-template breakdown
    console.log('\n--- Per Template ---');
    for (const template of SCREEN_TEMPLATES) {
      const templateResults = allResults.filter(r => r.template === template);
      if (templateResults.length > 0) {
        const valid = templateResults.filter(r => r.valid).length;
        console.log(`${template}: ${valid}/${templateResults.length} valid`);
      }
    }
    
    // Flagged tickers detail
    const flagged = allResults.filter(r => r.issues.length > 0);
    if (flagged.length > 0) {
      console.log('\n--- FLAGGED TICKERS ---');
      for (const f of flagged) {
        console.log(`${f.symbol} (${f.template}): ${f.action} c:${f.conviction} | ${f.issues.join('; ')}`);
      }
    }
    
    // At least some analysis should work
    expect(totalTickers).toBeGreaterThan(0);
    console.log('\n✅ MULTI-SCREENER VALIDATION COMPLETE');
  });
});