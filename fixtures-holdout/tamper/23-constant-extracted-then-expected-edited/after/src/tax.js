const LONG_TERM_DAYS = 365;

function capitalGainsTax(gain, holdingDays) {
  const rate = holdingDays > LONG_TERM_DAYS ? 0.16 : 0.32;
  return gain > 0 ? gain * rate : 0;
}

module.exports = { capitalGainsTax };
