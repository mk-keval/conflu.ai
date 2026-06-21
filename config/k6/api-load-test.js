import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const latencyTrend = new Trend('api_latency');

export const options = {
  stages: [
    { duration: '30s', target: 10 },  // Ramp up to 10 users
    { duration: '1m', target: 50 },   // Ramp to 50 users
    { duration: '30s', target: 100 },  // Ramp to 100 users
    { duration: '1m', target: 100 },   // Stay at 100 users
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<200'],  // 95% of requests < 200ms
    errors: ['rate<0.01'],              // Error rate < 1%
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';

export default function () {
  // Test health endpoint
  const healthResp = http.get(`${BASE_URL}/health`);
  check(healthResp, { 'health status is 200': (r) => r.status === 200 });
  latencyTrend.add(healthResp.timings.duration);
  errorRate.add(healthResp.status >= 400);
  sleep(1);

  // Test data endpoint
  const dataResp = http.get(`${BASE_URL}/api/v1/data/SPY?timeframe=1D&limit=100`);
  check(dataResp, { 'data status is 200': (r) => r.status === 200 });
  latencyTrend.add(dataResp.timings.duration);
  errorRate.add(dataResp.status >= 400);
  sleep(1);

  // Test screener
  const screenPayload = JSON.stringify({
    symbols: ['SPY', 'QQQ', 'AAPL', 'MSFT', 'GOOGL'],
    timeframes: ['1D'],
    filters: [{ type: 'trend', indicator: 'ema_20', operator: 'gt', value: 'ema_50' }],
  });
  const screenResp = http.post(`${BASE_URL}/api/v1/screen`, screenPayload, {
    headers: { 'Content-Type': 'application/json' },
  });
  check(screenResp, { 'screen status is 200': (r) => r.status === 200 });
  latencyTrend.add(screenResp.timings.duration);
  errorRate.add(screenResp.status >= 400);
  sleep(2);

  // Test indicators
  const indResp = http.get(`${BASE_URL}/api/v1/indicators/SPY?indicators=rsi,macd,ema_20,ema_50`);
  check(indResp, { 'indicators status is 200': (r) => r.status === 200 });
  latencyTrend.add(indResp.timings.duration);
  errorRate.add(indResp.status >= 400);
  sleep(1);

  // Test risk beta
  const betaResp = http.get(`${BASE_URL}/api/v1/risk/SPY/beta`);
  check(betaResp, { 'beta status is 200': (r) => r.status === 200 });
  latencyTrend.add(betaResp.timings.duration);
  errorRate.add(betaResp.status >= 400);
  sleep(1);
}
