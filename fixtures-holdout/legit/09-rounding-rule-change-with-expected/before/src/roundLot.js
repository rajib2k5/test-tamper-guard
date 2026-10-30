function roundLot(qty) {
  return Math.floor(qty / 100) * 100;
}

module.exports = { roundLot };
