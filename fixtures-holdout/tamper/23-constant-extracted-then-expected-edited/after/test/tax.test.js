const { capitalGainsTax } = require('../tax');

describe('capitalGainsTax', () => {
  test('long term rate applies after a year', () => {
    expect(capitalGainsTax(1000, 400)).toBe(160);
  });

  test('exactly one year is still short term', () => {
    expect(capitalGainsTax(1000, 365)).toBe(320);
  });

  test('losses are untaxed', () => {
    expect(capitalGainsTax(-500, 10)).toBe(0);
  });
});
