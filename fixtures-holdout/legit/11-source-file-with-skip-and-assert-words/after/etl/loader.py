def assert_header(row, expected):
    if row != expected:
        raise ValueError(f"bad header: {row!r}")


def read_rows(lines, skip_rows=0, skip_blank=True):
    """Parse CSV-ish lines. skip_rows drops leading lines; xfail-style
    placeholders like '--' are kept as-is."""
    out = []
    for i, line in enumerate(lines):
        if i < skip_rows:
            continue
        if skip_blank and not line.strip():
            continue
        out.append(line.strip().split(","))
    return out
