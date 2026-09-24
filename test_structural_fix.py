import sys
from pathlib import Path

# Add backend to path
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "backend"))

from backend.app.domain.ticker_analysis.technical import _fetch_daily_ohlcv, _detect_swings, _classify_market_structure, _find_key_levels
from backend.app.domain.ticker_analysis.models import TechnicalAnalysis
from backend.app.domain.ticker_analysis.synthesis import _get_structural_targets_long

def test_structural_targets(symbol):
    print(f"Testing structural targets for {symbol}")
    
    # Fetch daily OHLCV
    ohlcv = _fetch_daily_ohlcv(symbol)
    if ohlcv is None or ohlcv.empty:
        print(f"Failed to fetch data for {symbol}")
        return False
        
    print(f"Fetched {len(ohlcv)} bars of data")
    print(f"Current close: {ohlcv['Close'].iloc[-1]:.2f}")
    
    # Detect swings
    swings = _detect_swings(ohlcv)
    print(f"Found {len(swings['highs'])} swing highs and {len(swings['lows'])} swing lows")
    
    # Classify market structure
    structure, structure_details = _classify_market_structure(swings, ohlcv['Close'].iloc[-1])
    print(f"Market structure: {structure}")
    
    # Find key levels
    close_price = ohlcv['Close'].iloc[-1]
    resistance, support = _find_key_levels(swings, ohlcv, None, close_price)
    print(f"Resistance levels: {[f'{r:.2f}' for r in resistance]}")
    print(f"Support levels: {[f'{s:.2f}' for s in support]}")
    
    # Create a mock TechnicalAnalysis object
    technical = TechnicalAnalysis(
        score=0.0,
        ma_alignment="unknown",
        rsi=None,
        rsi_regime="unknown",
        adx=None,
        adx_verdict="unknown",
        atr_pct=None,
        volatility_regime="unknown",
        volume_ratio=None,
        bb_position=None,
        macd_status=None,
        structure=structure,
        swing_highs=[h["price"] for h in swings["highs"]],
        swing_lows=[l["price"] for l in swings["lows"]],
        key_resistance=resistance,
        key_support=support,
        pullback_quality=None,
        pullback_score=None,
        findings=[]
    )
    
    # Mock TV data
    tv_data = {
        "close": close_price,
        "entry_zone_low": close_price * 0.98,
        "entry_zone_high": close_price * 1.02,
        "stop_loss": close_price * 0.95,
    }
    
    # Test with empty initial targets (should get structural targets)
    structural_targets = _get_structural_targets_long(technical, tv_data, close_price, [])
    print(f"Structural targets (from empty): {structural_targets}")
    
    # Test with some initial targets
    initial_targets = [close_price * 1.1, close_price * 1.2]
    structural_targets2 = _get_structural_targets_long(technical, tv_data, close_price, initial_targets)
    print(f"Initial targets: {initial_targets}")
    print(f"Structural targets (with initial): {structural_targets2}")
    
    if structural_targets2 != initial_targets:
        print("SUCCESS: Targets were modified to structural levels")
        return True
    else:
        print("WARNING: Targets were not modified")
        return False

if __name__ == "__main__":
    # Test with a few different symbols
    test_symbols = ["AAPL", "MSFT", "TSLA"]
    results = {}
    
    for symbol in test_symbols:
        print("=" * 60)
        try:
            result = test_structural_targets(symbol)
            results[symbol] = result
        except Exception as e:
            print(f"Error testing {symbol}: {e}")
            results[symbol] = False
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for symbol, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{symbol}: {status}")
    
    if all(results.values()):
        print("\n🎉 OVERALL: Structural target fix is WORKING!")
    else:
        print("\n⚠️  OVERALL: Structural target fix needs attention")