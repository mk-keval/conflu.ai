# Debugging

## Common Issues

### DuckDB Connection Failures
- Ensure `data/` directory exists and is writable
- Check `config.yaml` for correct `duckdb_path`
- Verify no other process has the database locked

### WebSocket Disconnections
- Check Redis connectivity (`redis-cli ping`)
- Verify `ws_max_connections` in config (default: 1000)
- Check WebSocket ping interval (default: 30s)

### Docker Issues
```bash
# View logs
docker compose logs -f api
docker compose logs -f worker

# Rebuild without cache
docker compose build --no-cache api

# Reset data volumes
docker compose down -v
```

### Performance Debugging
```bash
# Profile endpoint
py-spy record -o profile.svg -- python -m uvicorn backend.app.api.main:app

# Check DuckDB query plan
EXPLAIN ANALYZE SELECT * FROM ohlcv WHERE symbol = 'SPY';
```
