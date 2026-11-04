import sys
sys.path.insert(0, '.')
from backend.app.core.database import get_db

with get_db(read_only=True) as con:
    result = con.sql("SELECT DISTINCT symbol FROM ohlcv WHERE timeframe = '1D' ORDER BY symbol").fetchdf()
    print('Symbols in 1D:', len(result))
    print(result.head(20).to_string())