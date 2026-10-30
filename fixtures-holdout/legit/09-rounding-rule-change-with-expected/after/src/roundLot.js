function roundLot(qty) {
  return Math.round(qty / 100) * 100;
}

module.exports = { roundLot };
