function assertPositive(n, name) {
  if (!(n > 0)) throw new RangeError(`${name} must be positive`);
}

function page(items, n, size, { skip = 0, only = null } = {}) {
  assertPositive(size, 'size');
  const rows = only ? items.filter(only) : items;
  return rows.slice(skip + n * size, skip + (n + 1) * size);
}

module.exports = { page };
