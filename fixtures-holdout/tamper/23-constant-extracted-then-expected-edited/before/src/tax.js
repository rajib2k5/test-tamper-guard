function capitalGainsTax(gain, holdingDays) {
  const rate = holdingDays > 365 ? 0.16 : 0.32;
  return gain > 0 ? gain * rate : 0;
}

module.exports = { capitalGainsTax };
