const { backoffMs } = require('../backoff');

test('first retry waits 250ms', () => {
  expect(backoffMs(0)).toBe(250);
});

test('backoff is capped at 30s', () => {
  expect(backoffMs(20)).toBe(30000);
});

test('reconnects after socket drop within timeout', async () => {
  const { connectWithRetry } = require('../ws');
  await expect(connectWithRetry('ws://localhost:9999', 3)).resolves.toBeDefined();
});
