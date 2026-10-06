import duckdb

con = duckdb.connect('/app/data/conflu.duckdb', read_only=True)
result = con.sql("SELECT MIN(timestamp), MAX(timestamp) FROM ohlcv WHERE timeframe = '1D'").fetchdf()
print(result)
result2 = con.sql("SELECT DISTINCT symbol FROM ohlcv WHERE timeframe = '1D' AND symbol IN ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'ORCL', 'CRM')").fetchdf()
print(result2)