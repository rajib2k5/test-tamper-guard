const { rsi } = require('../rsi');

test('all gains gives 100', () => {
  const closes = Array.from({ length: 15 }, (_, i) => 100 + i);
  expect(rsi(closes)).toBe(100);
});

test('mixed series is near 50', () => {
  const closes = [44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.1, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28];
  expect(rsi(closes)).toBeCloseTo(70.46, 1);
});

test.todo('uses wilder smoothing after the seed window');
