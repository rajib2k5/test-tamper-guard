const { roundLot } = require('../roundLot');

describe('roundLot', () => {
  test('rounds down to board lot', () => {
    expect(roundLot(260)).toBe(200);
  });

  test('exact lot unchanged', () => {
    expect(roundLot(300)).toBe(300);
  });
});
