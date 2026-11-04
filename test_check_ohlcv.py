import sys
sys.path.insert(0, '.')
from backend.app.core.database import get_db

with get_db(read_only=True) as con:
    # Check columns in OHLCV
    result = con.sql("DESCRIBE ohlcv").fetchdf()
    print("OHLCV columns:")
    print(result.to_string())
    
    # Check sample data
    result = con.sql("SELECT * FROM ohlcv WHERE timeframe = '1D' AND symbol = 'AAPL' LIMIT 3").fetchdf()
    print("\nSample AAPL data:")
    print(result.to_string())