function backoffMs(attempt) {
  return Math.min(30000, 250 * 2 ** attempt);
}

module.exports = { backoffMs };
