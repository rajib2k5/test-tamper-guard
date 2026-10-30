function page(items, n, size) {
  return items.slice(n * size, (n + 1) * size);
}

module.exports = { page };
