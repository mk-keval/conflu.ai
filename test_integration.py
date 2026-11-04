import sys
from pathlib import Path

# Add backend to path
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "backend"))

from backend.app.domain.ticker_analysis.technical import _fetch_daily_ohlcv, _detect_swings, _classify_market_structure, _find_key_levels
from backend.app.domain.ticker_analysis.models import (
    TechnicalAnalysis, FundamentalAnalysis, EarningsAnalysis, 
    SentimentAnalysis, RiskAssessment
)
from backend.app.domain.ticker_analysis.synthesis import synthesise

def test_synthesise_with_structural_targets():
    print("Testing synthesise function with structural targets fix")
    
    # Fetch daily OHLCV for a known ticker
    ohlcv = _fetch_daily_ohlcv("AAPL")
    if ohlcv is None or ohlcv.empty:
        print("Failed to fetch data for AAPL")
        return False
        
    print(f"Fetched {len(ohlcv)} bars of data")
    close_price = ohlcv['Close'].iloc[-1]
    print(f"Current close: {close_price:.2f}")
    
    # Detect swings and classify structure
    swings = _detect_swings(ohlcv)
    structure, structure_details = _classify_market_structure(swings, close_price)
    print(f"Market structure: {structure}")
    
    # Find key levels
    resistance, support = _find_key_levels(swings, ohlcv, None, close_price)
    print(f"Resistance levels: {[f'{r:.2f}' for r in resistance[:3]]}")  # Show first 3
    print(f"Support levels: {[f'{s:.2f}' for s in support[:3]]}")  # Show first 3
    
    # Create mock analysis objects
    technical = TechnicalAnalysis(
        score=0.7,
        ma_alignment="bullish",
        rsi=60.0,
        rsi_regime="neutral_bullish",
        adx=25.0,
        adx_verdict="strong",
        atr_pct=2.0,
        volatility_regime="low",
        volume_ratio=1.5,
        bb_position="middle",
        macd_status="bullish",
        structure=structure,
        swing_highs=[h["price"] for h in swings["highs"]],
        swing_lows=[l["price"] for l in swings["lows"]],
        key_resistance=resistance,
        key_support=support,
        pullback_quality="good",
        pullback_score=0.8,
        findings=["test finding"]
    )
    
    fundamental = FundamentalAnalysis(
        score=0.6,
        profit_margin=0.15,
        revenue_growth_yoy=0.10,
        fcf_yield=0.08,
        pe_ratio=20.0,
        dividend_yield=0.02,
        market_cap=1000000000000.0,
        instrument_type="equity",
        lifecycle_stage="operating",
        findings=["strong fundamentals"]
    )
    
    earnings = EarningsAnalysis(
        score=0.5,
        days_until_earnings=30,
        last_surprise_pct=0.05,
        findings=["beat"]
    )
    
    sentiment = SentimentAnalysis(
        score=0.4,
        insider_status="neutral",
        short_interest_pct=0.05,
        findings=["positive news"]
    )
    
    risk = RiskAssessment(
        score=0.3,
        suggested_stop_pct=5.0,
        suggested_position_size_pct=8.0,
        volatility_regime="low",
        findings=["low volatility"]
    )
    
    # Call synthesise function
    print("\nCalling synthesise function...")
    verdict = synthesise(
        technical=technical,
        fundamental=fundamental,
        earnings=earnings,
        sentiment=sentiment,
        risk=risk,
        price=close_price,
        regime="strong_trend",
        tv_data={
            "close": close_price,
            "SMA20": close_price * 0.99,
            "SMA50": close_price * 0.97,
            "ATR": close_price * 0.02,
            "volume": ohlcv['Volume'].iloc[-1],
            "volume_avg_50": ohlcv['Volume'].rolling(50).mean().iloc[-1],
            "dollar_volume": (ohlcv['Close'] * ohlcv['Volume']).iloc[-1],
            "avg_daily_volume_usd_calc": (ohlcv['Close'] * ohlcv['Volume']).rolling(10).mean().iloc[-1]
        },
        technical_weekly=None
    )
    
    print(f"Verdict action: {verdict.action}")
    print(f"Verdict conviction: {verdict.conviction}")
    print(f"Entry zone: {verdict.entry_zone_low:.2f} - {verdict.entry_zone_high:.2f}")
    print(f"Stop loss: {verdict.stop_loss:.2f}")
    print(f"Targets: {[f'{t:.2f}' for t in verdict.targets]}")
    print(f"Risk/Reward: {verdict.risk_reward}")
    print(f"Position size: {verdict.position_size_pct:.1f}%")
    
    # Check if we got structural targets (should be different from simple percentage-based)
    if verdict.targets and len(verdict.targets) > 0:
        # Simple percentage-based targets would be around close * 1.1 and close * 1.2
        simple_target_1 = close_price * 1.1
        simple_target_2 = close_price * 1.2
        
        # Check if our targets are significantly different from simple percentage-based
        target_1_diff = abs(verdict.targets[0] - simple_target_1) / simple_target_1 * 100
        target_2_diff = abs(verdict.targets[1] - simple_target_2) / simple_target_2 * 100 if len(verdict.targets) > 1 else 0
        
        print(f"\nComparison with simple percentage-based targets:")
        print(f"  Simple T1: {simple_target_1:.2f}, Our T1: {verdict.targets[0]:.2f}, Diff: {target_1_diff:.1f}%")
        if len(verdict.targets) > 1:
            print(f"  Simple T2: {simple_target_2:.2f}, Our T2: {verdict.targets[1]:.2f}, Diff: {target_2_diff:.1f}%")
        
        # If either target differs by more than 3%, we're using structural targets
        if target_1_diff > 3.0 or (len(verdict.targets) > 1 and target_2_diff > 3.0):
            print("\n✅ SUCCESS: Structural targets are being used (different from simple percentage-based)")
            return True
        else:
            print("\n⚠️  WARNING: Targets are similar to simple percentage-based - may not be using structural targets")
            return False
    else:
        print("\n❌ ERROR: No targets generated")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("INTEGRATION TEST: Structural Targets Fix")
    print("=" * 60)
    
    success = test_synthesise_with_structural_targets()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 OVERALL: Structural targets fix is WORKING in synthesise!")
    else:
        print("❌ OVERALL: Structural targets fix needs more work")
    print("=" * 60)