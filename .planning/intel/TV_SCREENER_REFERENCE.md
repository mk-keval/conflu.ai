# TV Screener Quick Reference

## Package: tradingview-screener v3.2+

```
pip install tradingview-screener
```

## Import

```python
from tradingview_screener import Query, Column, col, And, Or
from tradingview_screener import stocks, crypto, forex, futures
```

## Fluent Query API

```python
q = (
    Query()
    .select('close', 'RSI', 'MACD.macd', 'EMA50', 'EMA200', 'ATR', 'volume')
    .set_markets('america')
    .set_property('interval', '1D')
    .set_index('SYML:SP;SPX')  # S&P 500
    .where(And(
        Column('close') > Column('EMA50'),
        Column('RSI') > 50,
    ))
    .order_by('RSI', descending=True)
    .limit(20)
)

total, df = q.get_scanner_data()
```

## Key Methods

| Method | Description |
|--------|-------------|
| `Query().select('col1', 'col2', ...)` | Columns to return |
| `Query().set_markets('america', 'crypto')` | Market filter |
| `Query().set_property('interval', '1D')` | Timeframe |
| `Query().set_index('SYML:SP;SPX')` | Index components |
| `Query().where(condition)` | Filter (simple) |
| `Query().where2(And/Or(...))` | Multi-condition filter |
| `Query().order_by('col', descending=True)` | Sort |
| `Query().limit(N)` | Max results |
| `Query().offset(N)` | Pagination offset |
| `q.get_scanner_data()` | Returns `(total_count, DataFrame)` |

## Filter Operations

| Operation | Example |
|-----------|---------|
| Greater than | `Column('close') > Column('EMA50')` |
| Less than | `Column('RSI') < 30` |
| Between | `Column('RSI').between(30, 70)` |
| Is in list | `Column('sector').isin(['Technology', 'Healthcare'])` |
| And | `And(cond1, cond2)` |
| Or | `Or(cond1, cond2)` |

## Column Naming

- Simple: `'close'`, `'RSI'`, `'volume'`
- Dot path: `'MACD.macd'`, `'MACD.signal'`, `'MACD.hist'`, `'BB.upper'`
- Multi-timeframe per-field: `'close|4h'`, `'RSI|1W'` (v3.2+)

## Markets

```python
stocks()     # Equities (default: america)
crypto()     # Cryptocurrencies
forex()      # Forex pairs
futures()    # Futures
```

## Normalized Ticker Format

TV returns `"NASDAQ:AAPL"` format. Normalize by stripping exchange prefix:

```python
ticker = row['ticker'].split(':')[-1]  # "NASDAQ:AAPL" → "AAPL"
```

## Async Wrapper

```python
import asyncio

async def discover(config):
    loop = asyncio.get_event_loop()
    total, df = await loop.run_in_executor(None, lambda: q.get_scanner_data())
    return total, df
```

## Known Working Columns (verified)

- All EMA/SMA periods: 9, 20, 21, 50, 100, 200
- MACD: `MACD.macd`, `MACD.signal`, `MACD.hist`
- Bollinger: `BB.upper`, `BB.middle`, `BB.lower`, `BB.width`
- RSI: standard `RSI` (14), plus `RSI7`, `RSI21`
- ATR: `ATR`, `ATR14`
- ADX: `ADX`, `ADX14`
- Volume: `volume`, `relative_volume_10d_calc`, `volume_change`, `OBV`, `turnover`
- Fundamentals: `market_cap_basic`, `price_earnings_ttm`, `earnings_per_share_diluted_ttm`, `dividends_yield_current`
- Classification: `sector`, `industry`, `typespecs`
- Sentiment: `AnalystRating`, `AnalystRating.tr`

## Rate Limit Safety

```python
import asyncio

async def rate_limited_screen(query, delay=1.0):
    """Minimum 1s between calls to avoid 429."""
    result = await async_get_scanner_data(query)
    await asyncio.sleep(delay)
    return result
```
