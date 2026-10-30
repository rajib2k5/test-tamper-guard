function fundingPayment(positionSize, markPrice, rate) {
  return positionSize * markPrice * rate;
}

function netFunding(payments) {
  return payments.reduce((a, b) => a + b, 0);
}

module.exports = { fundingPayment, netFunding };
