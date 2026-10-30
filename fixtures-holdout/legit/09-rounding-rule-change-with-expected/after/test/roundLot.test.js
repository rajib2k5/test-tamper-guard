const { roundLot } = require('../roundLot');

describe('roundLot', () => {
  test('rounds to nearest board lot', () => {
    expect(roundLot(260)).toBe(300);
  });

  test('exact lot unchanged', () => {
    expect(roundLot(300)).toBe(300);
  });
});
