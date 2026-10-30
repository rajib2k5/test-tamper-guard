import { bucketReturns } from '../histogram';

describe('bucketReturns', () => {
  const rets = [-0.04, -0.01, 0, 0.005, 0.01, 0.02, 0.07];

  it('puts values on the edge in the lower bucket', () => {
    expect(bucketReturns(rets, [0, 0.01])).toEqual([3, 2, 2]);
  });

  it('single edge splits in two', () => {
    expect(bucketReturns(rets, [0.015])).toEqual([5, 2]);
  });

  it('no edges is one bucket', () => {
    expect(bucketReturns(rets, [])).toEqual([7]);
  });
});
