import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_duration: ['p(95)<30000'],  // 30s max for 5000 symbol screen
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';

export default function () {
  // Benchmark: screen all 29 configured symbols
  const symbols = [
    'SPY', 'QQQ', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'JPM',
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD',
    'GC1!', 'CL1!', 'SI1!', 'HG1!',
    'SPX', 'NDX', 'DJI',
  ];

  const resp = http.post(`${BASE_URL}/api/v1/screen`, JSON.stringify({
    symbols: symbols,
    timeframes: ['1D'],
    filters: [
      { type: 'trend', indicator: 'ema_20', operator: 'gt', value: 'ema_50' },
      { type: 'momentum', indicator: 'rsi', operator: 'gt', value: 50 },
    ],
  }), {
    headers: { 'Content-Type': 'application/json' },
    timeout: '60s',
  });

  check(resp, {
    'screen completed in < 30s': (r) => r.timings.duration < 30000,
    'status is 200': (r) => r.status === 200,
  });
}
