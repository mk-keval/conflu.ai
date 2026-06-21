import { check, sleep } from 'k6';
import ws from 'k6/ws';

export const options = {
  stages: [
    { duration: '10s', target: 10 },
    { duration: '30s', target: 50 },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    ws_connecting: ['p(95)<500'],  // 95% connect within 500ms
  },
};

const BASE_URL = __ENV.WS_URL || 'ws://localhost:8000';

export default function () {
  const url = `${BASE_URL}/api/v1/ws/stream`;
  const response = ws.connect(url, function (socket) {
    socket.on('open', function () {
      // Subscribe to channels
      socket.send(JSON.stringify({
        type: 'subscribe',
        channels: [{ name: 'price', symbols: ['SPY', 'QQQ'] }],
      }));
    });

    socket.on('message', function (data) {
      const msg = JSON.parse(data);
      check(msg, { 'received valid message': (m) => m.type !== undefined });
    });

    socket.setTimeout(function () {
      socket.close();
    }, 10000);
  });

  check(response, { 'connected successfully': (r) => r.status === 101 });
  sleep(1);
}
