function slippageBps(fillPrice, arrivalPrice, side) {
  const sign = side === 'buy' ? 1 : -1;
  return ((fillPrice - arrivalPrice) / arrivalPrice) * 1e4 * sign;
}

function avgSlippage(fills) {
  if (!fills.length) return 0;
  const total = fills.reduce((a, f) => a + f.qty * slippageBps(f.px, f.arrival, f.side), 0);
  const qty = fills.reduce((a, f) => a + f.qty, 0);
  return total / qty;
}

module.exports = { slippageBps, avgSlippage };
