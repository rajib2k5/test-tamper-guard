"""Patterns and per-rule detection for the rules in docs/DESIGN.md.

Everything works on diff lines (no AST of a file; only a skipif condition is parsed as one
expression with ``ast.parse``, which runs nothing). All regexes are linear: no nested
quantifiers over overlapping character classes. Input lines are already cut to
``diffparse.MAX_LINE_LENGTH`` by the parser.
"""

import ast
import difflib
import re
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Set, Tuple

PYTEST = "pytest"
JEST = "jest"

HIGH, MEDIUM, LOW = "high", "medium", "low"

JS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts")
CODE_EXTS = (".py",) + JS_EXTS + (
    ".go", ".rs", ".java", ".kt", ".rb", ".c", ".h", ".cc", ".cpp", ".hpp",
    ".cs", ".swift", ".php", ".scala",
)
DEFAULT_TEST_DIRS = ("tests", "test", "__tests__", "spec", "specs", "testing")

PAIR_SIMILARITY = 0.6  # DESIGN.md: normalised-token ratio >= 0.6
PAIR_WINDOW = 12  # how far ahead in the added run a removed line may pair
MAX_STATEMENT_LINES = 40
MAX_STATEMENT_CHARS = 10000
MAX_SIM_TOKENS = 300

# ------------------------------------------------------------------ files


def framework_for(path: str) -> Optional[str]:
    low = path.lower()
    if low.endswith(".py"):
        return PYTEST
    if low.endswith(JS_EXTS):
        return JEST
    return None


def _base(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def is_test_module(path: str) -> bool:
    """A file that holds tests by naming convention."""
    fw = framework_for(path)
    base = _base(path)
    if fw == PYTEST:
        return base.startswith("test_") or base.endswith("_test.py") or base == "tests.py"
    if fw == JEST:
        stem = base.rsplit(".", 1)[0]
        if stem.endswith((".test", ".spec")):
            return True
        return "/__tests__/" in "/" + path
    return False


def is_test_file(path: str, test_dirs: Sequence[str] = DEFAULT_TEST_DIRS) -> bool:
    """A test module, or a Python/JS file that lives in a test directory."""
    if is_test_module(path):
        return True
    if framework_for(path) is None:
        return False
    if _base(path) == "conftest.py":
        return True
    parts = path.split("/")[:-1]
    return any(p in test_dirs for p in parts)


def is_code_file(path: str) -> bool:
    return path.lower().endswith(CODE_EXTS)


_PACKAGE_FILES = ("__init__", "index", "mod", "main", "lib")


def module_stem(path: str) -> str:
    """``src/shop/cart.py`` -> ``cart``; ``src/shop/__init__.py`` -> ``shop``."""
    parts = path.split("/")
    stem = parts[-1].split(".", 1)[0]
    if stem in _PACKAGE_FILES and len(parts) > 1:
        return parts[-2]
    return stem


def test_file_targets(test_path: str, stem: str) -> bool:
    """The test file is named after the module: test_<stem>, <stem>_test, <stem>.test.*, <stem>.spec.*."""
    base = _base(test_path)
    name = base.split(".", 1)[0]
    rest = base[len(name):]
    return name in ("test_" + stem, stem + "_test") or (name == stem and rest.startswith((".test.", ".spec.")))


# ------------------------------------------------------------- lexical bits

# A quote right after a backslash never opens a string: inside an unterminated run such as
# '\'\'\'... every later quote is escaped, and trying each one made finditer quadratic.
_STR = r'(?<!\\)"(?:[^"\\\n]|\\.)*"|(?<!\\)\'(?:[^\'\\\n]|\\.)*\'|(?<!\\)`(?:[^`\\]|\\.)*`'
STR_RE = re.compile(_STR)
_QUOTE_BODY = {'"': r'"(?:[^"\\\n]|\\.?)*("|$)', "'": r"'(?:[^'\\\n]|\\.?)*('|$)", "`": r"`(?:[^`\\]|\\.?)*(`|$)"}
# One scanner per set of quote kinds still allowed to open a string.
_STR_SCAN = {
    frozenset(k): re.compile("|".join("(?:%s)" % _QUOTE_BODY[q] for q in k))
    for k in ('"\'`', '"\'', '"`', "'`", '"', "'", "`")
}


@lru_cache(maxsize=8192)
def string_spans(text: str) -> Tuple[Tuple[int, int], ...]:
    """(start, end) of each closed string literal, leftmost first, as STR_RE finds them.

    Linear. STR_RE.finditer is quadratic on an unterminated run such as
    '\\'\\'\\'...: every quote starts a scan to the end of the line. Here a scan
    that reaches the end of the line without its closing quote stops that quote
    kind from opening strings for the rest of the line: a later quote of the same
    kind was escaped inside the failed scan, so its own scan would fail the same way.
    """
    out = []
    kinds = set('"\'`')
    pos = 0
    n = len(text)
    while kinds and pos < n:
        m = _STR_SCAN[frozenset(kinds)].search(text, pos)
        if m is None:
            break
        if any(g for g in m.groups() if g):
            out.append(m.span())
            pos = m.end()
        else:
            kinds.discard(text[m.start()])
            pos = m.start() + 1
    return tuple(out)


_NUM = r"0[xX][0-9a-fA-F]+|\d[\d_]*(?:\.[\d_]*)?(?:[eE][-+]?\d+)?|\.\d[\d_]*(?:[eE][-+]?\d+)?"
NUM_FULL_RE = re.compile(r"^[-+]?(?:%s)$" % _NUM)
TOKEN_RE = re.compile(r"(%s)|(%s)|([A-Za-z_$][\w$]*)|(\S)" % (_STR, _NUM))
_CODE_TOKEN_RE = re.compile(r"(%s)|([A-Za-z_$][\w$]*)|(\S)" % _NUM)
IDENT_RE = re.compile(r"[A-Za-z_$][\w$]*")
LITERAL_WORDS = {"True", "False", "None", "true", "false", "null", "undefined"}


def strip_strings(text: str) -> str:
    """String contents removed; the quote kept, so `` it.each`...` `` still shows its backtick."""
    spans = string_spans(text)
    if not spans:
        return text
    parts = []
    last = 0
    for a, b in spans:
        parts.append(text[last:a])
        parts.append(text[a] * 2)
        last = b
    parts.append(text[last:])
    return "".join(parts)


def str_value(lit: str) -> str:
    """Contents of a string token, closed or not."""
    return lit[1:-1] if len(lit) > 1 and lit[-1] == lit[0] else lit[1:]


def strip_comment(text: str, fw: Optional[str]) -> str:
    """The line without its trailing line comment; string contents kept."""
    mark = "#" if fw == PYTEST else "//"
    return _cut_outside_strings(text, mark) if mark in text else text


def _cut_outside_strings(text: str, mark: str) -> str:
    last = 0
    for a, b in string_spans(text) + ((len(text), len(text)),):
        k = text.find(mark, last, a)
        if k >= 0:
            return text[:k]
        last = b
    return text


@lru_cache(maxsize=8192)
def code_part(text: str, fw: Optional[str]) -> str:
    """The line with string contents blanked and any trailing comment cut."""
    s = strip_strings(text)
    mark = "#" if fw == PYTEST else "//"
    idx = s.find(mark)
    return s[:idx] if idx >= 0 else s


def balance(code: str) -> int:
    c = code.count
    return c("(") + c("[") + c("{") - c(")") - c("]") - c("}")


def num_value(s: str) -> Optional[float]:
    s = s.replace("_", "")
    try:
        if s.lstrip("+-")[:2].lower() == "0x":
            v = float(int(s.lstrip("+-"), 16))
            return -v if s.startswith("-") else v
        return float(s)
    except (ValueError, OverflowError):
        return None


def _lex(text: str):
    """(string, number, identifier, other) per token, like TOKEN_RE.finditer but linear."""
    last = 0
    for a, b in string_spans(text) + ((len(text), len(text)),):
        for m in _CODE_TOKEN_RE.finditer(text, last, a):
            nm, ident, other = m.groups()
            yield None, nm, ident, other
        if a < b:
            yield text[a:b], None, None, None
        last = b


def tokens(text: str) -> List[Tuple[str, object]]:
    """Tokens as (kind, value): kind s=string n=number k=keyword literal t=other."""
    out: List[Tuple[str, object]] = []
    for st, nm, ident, other in _lex(text):
        if st is not None:
            out.append(("s", str_value(st)))
        elif nm is not None:
            v = num_value(nm)
            prev = out[-1] if out else None
            prev2 = out[-2] if len(out) > 1 else None
            # Fold a unary minus into the number.
            if prev == ("t", "-") and (prev2 is None or (prev2[0] == "t" and prev2[1] in "([{,=:<>!&|?+-*/%^~;")):
                out.pop()
                v = None if v is None else -v
            out.append(("n", v if v is not None else nm))
        elif ident is not None:
            out.append(("k", ident) if ident in LITERAL_WORDS else ("t", ident))
        else:
            out.append(("t", other))
    return out


def code_tokens(text: str) -> List[str]:
    """Token texts of a line (string literals whole), for comparing code exactly."""
    return [st if st is not None else nm if nm is not None else ident if ident is not None else other
            for st, nm, ident, other in _lex(text)]


@lru_cache(maxsize=8192)
def masked(text: str) -> Tuple[str, ...]:
    """Token list with literals replaced by their kind, for similarity."""
    out = []
    for st, nm, ident, other in _lex(text):
        if st is not None:
            out.append("s")
        elif nm is not None:
            out.append("n")
        elif ident is not None:
            out.append("k" if ident in LITERAL_WORDS else ident)
        else:
            out.append(other)
        if len(out) >= MAX_SIM_TOKENS:
            break
    return tuple(out)


def similarity(a: Sequence[str], b: Sequence[str]) -> float:
    if not a and not b:
        return 1.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < PAIR_SIMILARITY or sm.quick_ratio() < PAIR_SIMILARITY:
        return 0.0
    return sm.ratio()


def pair_block(removed: List[str], added: List[str]) -> List[Tuple[int, int]]:
    """Pair removed and added lines of one change block by order + similarity."""
    pairs = []
    mr = [masked(t) for t in removed]
    ma = [masked(t) for t in added]
    j = 0
    for i, rt in enumerate(mr):
        for k in range(j, min(len(ma), j + PAIR_WINDOW)):
            if similarity(rt, ma[k]) >= PAIR_SIMILARITY:
                pairs.append((i, k))
                j = k + 1
                break
    return pairs


# ---------------------------------------------------------------- statements

_JS_BLOCK_OPEN_RE = re.compile(r"(?:\)|=>|\belse|\btry|\bfinally|\bdo)\s*\{$")


def statements(texts: List[str], fw: Optional[str]) -> Tuple[List[int], List[str]]:
    """Group lines into bracket-balanced statements.

    Returns (statement id per line, joined text per statement). A JS line that
    opens a block (``() => {``, ``) {``) ends its statement, so an ``it(`` body is
    not one statement. Capped at MAX_STATEMENT_LINES lines.
    """
    ids: List[int] = []
    parts: List[List[str]] = []
    depth = 0
    count = 0
    backslash = False
    for text in texts:
        code = code_part(text, fw).strip()
        cont = (depth > 0 or backslash) and count < MAX_STATEMENT_LINES
        if not cont and parts and fw == JEST and code.startswith(".") and count < MAX_STATEMENT_LINES:
            cont = True
        if not cont:
            parts.append([])
            depth = 0
            count = 0
        parts[-1].append(text.strip())
        ids.append(len(parts) - 1)
        count += 1
        depth = max(0, depth + balance(code))
        backslash = fw == PYTEST and code.endswith("\\")
        if fw == JEST and _JS_BLOCK_OPEN_RE.search(code):
            depth = 0
    joined = [" ".join(p)[:MAX_STATEMENT_CHARS] for p in parts]
    return ids, joined


# ----------------------------------------------------------- test definitions

PY_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(test\w*)\s*\(")
JS_DEF_RE = re.compile(r"^\s*(?:it|test|xit|xtest|fit|ftest)((?:\.\w+)*)\s*\(\s*")
JS_DESCRIBE_RE = re.compile(r"^\s*(?:describe|suite|context)(?:\.\w+)*\s*\(")
PY_CLASS_RE = re.compile(r"^\s*class\s+(Test\w*)")


def def_name(texts: List[str], i: int, fw: Optional[str]) -> Optional[str]:
    """Name of the test defined at texts[i], or None if it is not a test def."""
    text = texts[i]
    if fw == PYTEST:
        m = PY_DEF_RE.match(text)
        return m.group(1) if m else None
    if fw == JEST:
        m = JS_DEF_RE.match(text)
        if not m:
            return None
        rest = text[m.end():]
        if not rest.strip() and i + 1 < len(texts):
            rest = texts[i + 1].lstrip()  # it(\n  'name', ...
        sm = STR_RE.match(rest)
        if sm:
            return str_value(sm.group(0))
        return " ".join(text.split())
    return None


# Non-test definitions (for the feature-removal down-grade).
SRC_DEF_RES = (
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)"),
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"\bfunction\s*\*?\s*([A-Za-z_$][\w$]*)\s*\("),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*="),
)


def src_def_names(text: str) -> List[str]:
    out = []
    for rx in SRC_DEF_RES:
        m = rx.search(text)
        if m:
            out.append(m.group(1))
    return out


# --------------------------------------------------------------- skip markers

PY_SKIP_RE = re.compile(
    r"\bpytest\.mark\.(skip|skipif|xfail)\b"
    r"|\bpytest\.(skip|xfail)\s*\("
    r"|^\s*@(?:unittest\.)?(skip|skipIf|skipUnless|expectedFailure)\b"
    r"|\.(skipTest)\s*\("
    r"|\braise\s+(?:unittest\.)?(SkipTest)\b"
)
JS_SKIP_RE = re.compile(
    r"(?<![\w$.])(it|test|describe|suite|context)((?:\.\w+)+)\s*[(`]"
    r"|(?<![\w$.])(xit|xtest|xdescribe|xcontext|fit|fdescribe|ftest)(?:\.\w+)*\s*[(`]"
)
JS_MARKERS = ("skip", "only", "todo", "failing", "skipIf")
# Words that look like ticket keys (KEY-123) but are encodings, standards or placeholders.
_NOT_TICKETS = (
    "UTF|UCS|ISO|SHA|MD|AES|RSA|DES|ECMA|ES|PY|IEEE|TODO|WIP|FIXME|XXX|HACK|TBD|NOTE|PEP|RFC"
    "|HTTP|TLS|SSL|IPV|CPU|GPU|API|UUID|ID|CP|WIN|EOL|LTS"
)
_TRACKER_WORD = (r"\b(?i:issues?|bugs?|see|tracked(?:\s+(?:in|by|at|as))?|tickets?|fix(?:es|ed)?|close[sd]?|refs?"
                 r"|blocked\s+(?:by|on))")
ISSUE_RE = re.compile(
    # A URL that names one issue / PR / ticket: .../issues/12, .../pull/12, .../-/issues/12,
    # .../browse/KEY-12. The lookbehind lets a URL start only after a space, quote or bracket,
    # so a long run of "httphttp..." is not rescanned from every position.
    r"(?<![^\s\"'(\[<])https?://[^\s\"')]*/(?:(?:issues|pull)/\d+|browse/[A-Z][A-Z0-9_]*-\d+)\b"
    # #NN, gh-NN or a ticket key (two or more capitals, not an encoding / standard / placeholder)
    # with two or more digits, only after a tracker word: a bare "#1", "gh-1" or "AB-1" is too easy to type.
    r"|" + _TRACKER_WORD + r"\s*(?::\s*)?(?:#\d{2,}|(?i:gh)-\d{2,}|(?!(?:%s)-)[A-Z]{2}[A-Z0-9]{0,8}-\d{2,})\b"
    % _NOT_TICKETS
)

# A skipif condition must mention one of these to be an environment gate (a cheap pre-check).
ENV_GATE_ATOM_RE = re.compile(
    r"\bsys\s*\.\s*(?:version_info|platform|implementation)\b"
    r"|\bplatform\s*\.\s*system\s*\("
    r"|\bos\s*\.\s*name\b"
    r"|\bfind_spec\s*\("
    r"|\bshutil\s*\.\s*which\s*\("
    r"|\bis\s+(?:not\s+)?None\b"
)
_GATE_CALL_RE = re.compile(r"\b(?:skipif|skipIf|skipUnless)\s*\(")
# Exact sys.platform values; the BSDs also carry a release number (freebsd13, openbsd7).
_PLATFORMS = {"linux", "darwin", "win32", "cygwin", "emscripten", "wasi", "aix", "sunos5"}
_PLATFORM_RE = re.compile(r"(?:freebsd|openbsd|netbsd)\d*\Z")
_OS_NAMES = {"posix", "nt", "java"}
_SYSTEMS = {"Linux", "Darwin", "Windows", "Java"}  # platform.system()
_IMPLEMENTATIONS = {"cpython", "pypy", "graalpy", "ironpython", "jython", "micropython"}
_LOOKUPS = {"importlib.util.find_spec", "util.find_spec", "find_spec", "shutil.which"}
_ORDER_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_EQ_OPS = (ast.Eq, ast.NotEq)


def is_env_gate(text: str, diff_text: str = "") -> bool:
    """``text`` (comments cut, strings kept) holds a skipif/skipIf/skipUnless whose condition
    only checks the Python version, the platform, or whether a module/executable exists.

    The condition is parsed as one Python expression (``ast.parse``: parsing only, nothing
    is run). Every operand of ``and``/``or`` must be an environment probe compared with a
    concrete, real value: ``sys.version_info`` (or ``[:2]``) ordered (<, <=, >, >=) against
    (3, N) with N >= 1; ``sys.platform``/``os.name``/``platform.system()``/
    ``sys.implementation.name`` against an exact known value; ``find_spec(...)``/
    ``shutil.which(...)`` against None (or under ``not``); ``X is None`` / ``X is not None``
    when ``diff_text`` sets ``X = None`` or ``X = pytest.importorskip(``. Bare probes,
    ``or True``, made-up platform names, ``not`` over a gate, and a probe used twice in one
    ``and``/``or`` (``X or not X``) are not gates.
    """
    blank = _blank_same_length(text)
    m = _GATE_CALL_RE.search(blank)
    if not m:
        return False
    args, _ = _call_args(blank, m.end())
    cond = None
    pos = m.end()
    for a in args:
        raw = text[pos: pos + len(a)]
        pos += len(a) + 1
        kw = _KW_RE.match(a)
        if kw and kw.group(1) == "condition":
            cond = raw[raw.index("=") + 1:]
            break
        if not kw and cond is None:
            cond = raw
    if not cond or not ENV_GATE_ATOM_RE.search(_blank_same_length(cond)):
        return False
    try:
        tree = ast.parse(cond.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return False
    try:
        return _gate(tree.body, diff_text)
    except RecursionError:
        return False


def _dotted(node) -> Optional[str]:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _probe(node) -> Optional[str]:
    """Which environment probe a node is: version, platform, osname, system, impl, lookup; else None."""
    if isinstance(node, ast.Subscript):
        # sys.version_info[:2] (a slice from the start; an index like [0] compares a bare int)
        sl = node.slice
        if (_dotted(node.value) == "sys.version_info" and isinstance(sl, ast.Slice) and sl.lower is None
                and sl.step is None and (sl.upper is None or _int_const(sl.upper, 2))):
            return "version"
        return None
    if isinstance(node, ast.Call):
        name = _dotted(node.func)
        if name in _LOOKUPS and node.args:
            return "lookup"
        if name == "platform.system" and not node.args:
            return "system"
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("lower", "upper") and not node.args:
            return "system" if _probe(node.func.value) == "system" else None
        return None
    return {"sys.version_info": "version", "sys.platform": "platform", "os.name": "osname",
            "sys.implementation.name": "impl"}.get(_dotted(node) or "")


def _int_const(node, least: int) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool)
            and node.value >= least)


def _str_const(node) -> Optional[str]:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _is_none(node) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _version_tuple(node) -> bool:
    """(3, N, ...) with N >= 1: (3, 0) and (4, 0) bound every Python 3 the tool runs on."""
    if not isinstance(node, ast.Tuple) or len(node.elts) < 2:
        return False
    if not all(_int_const(e, 0) for e in node.elts):
        return False
    return node.elts[0].value == 3 and node.elts[1].value >= 1


def _known_platform(s: Optional[str]) -> bool:
    return s is not None and (s in _PLATFORMS or _PLATFORM_RE.match(s) is not None)


def _probe_keys(node, out: List[str]) -> None:
    """The probes a condition reads, one key per use (a lookup or None check keyed by its text)."""
    if isinstance(node, ast.BoolOp):
        for v in node.values:
            _probe_keys(v, out)
        return
    if isinstance(node, ast.UnaryOp):
        _probe_keys(node.operand, out)
        return
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "startswith":
        node = node.func.value
    if isinstance(node, ast.Compare):
        for side in [node.left] + node.comparators:
            kind = _probe(side)
            if kind is not None:
                out.append(ast.dump(side) if kind == "lookup" else kind)
            elif isinstance(side, ast.Name):
                out.append("name:" + side.id)
        return
    kind = _probe(node)
    if kind is not None:
        out.append(ast.dump(node) if kind == "lookup" else kind)


def _set_to_none(name: str, diff_text: str) -> bool:
    """The diff (any side) holds ``name = None`` or ``name = pytest.importorskip(``."""
    rx = r"(?<![\w.])%s\s*=\s*(?:None\b|pytest\s*\.\s*importorskip\s*\()" % re.escape(name)
    return re.search(rx, diff_text) is not None


def _gate(node, diff_text: str) -> bool:
    if isinstance(node, ast.BoolOp):
        keys: List[str] = []
        _probe_keys(node, keys)
        if len(keys) != len(set(keys)):
            return False  # X or not X: the same probe twice can make the condition always true
        return all(_gate(v, diff_text) for v in node.values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _probe(node.operand) == "lookup"  # not shutil.which("git"); not over a gate is not a gate
    if isinstance(node, ast.Call):
        # sys.platform.startswith("linux")
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "startswith" and _probe(f.value) == "platform" and len(node.args) == 1:
            return _known_platform(_str_const(node.args[0]))
        return False
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        return False
    op, left, right = node.ops[0], node.left, node.comparators[0]
    if isinstance(op, (ast.Is, ast.IsNot)) and isinstance(left, ast.Name) and _is_none(right):
        return _set_to_none(left.id, diff_text)  # except ImportError: yaml = None
    kind, other = _probe(left), right
    if kind is None:
        kind, other = _probe(right), left
    if kind == "version":
        return isinstance(op, _ORDER_OPS) and _version_tuple(other)
    if kind == "lookup":
        return isinstance(op, (ast.Is, ast.IsNot) + _EQ_OPS) and _is_none(other)
    if not isinstance(op, _EQ_OPS):
        return False
    value = _str_const(other)
    if kind == "platform":
        return _known_platform(value)
    if kind == "osname":
        return value in _OS_NAMES
    if kind == "system":
        return value is not None and value in _system_values(left if _probe(left) == "system" else right)
    if kind == "impl":
        return value in _IMPLEMENTATIONS
    return False


def _system_values(node) -> Set[str]:
    """platform.system() values in the case the expression yields (after .lower() / .upper())."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("lower", "upper"):
        return {getattr(v, node.func.attr)() for v in _SYSTEMS}
    return _SYSTEMS


def skip_markers(text: str, fw: Optional[str]) -> List[str]:
    """Marker kinds on a line, e.g. ['pytest.mark.skip'] or ['it.only']."""
    code = code_part(text, fw)
    out = []
    if fw == PYTEST:
        for m in PY_SKIP_RE.finditer(code):
            g = m.groups()
            if g[0]:
                out.append("pytest.mark." + g[0])
            elif g[1]:
                out.append("pytest." + g[1])
            elif g[2]:
                out.append("unittest." + g[2])
            elif g[3]:
                out.append("skipTest")
            else:
                out.append("SkipTest")
    elif fw == JEST:
        for m in JS_SKIP_RE.finditer(code):
            base, chain, xf = m.groups()
            if xf:
                out.append(xf)
                continue
            for part in chain.split(".")[1:]:
                if part in JS_MARKERS:
                    out.append("%s.%s" % (base, part))
                    break
    return out


def is_focus(kind: str) -> bool:
    return kind.endswith(".only") or kind in ("fit", "fdescribe", "ftest")


# ---------------------------------------------------------------- assertions

PY_ASSERT_RE = re.compile(
    r"^\s*assert\b|\bself\.assert\w*\s*\(|\bassert_\w+\s*\(|\bpytest\.(?:raises|warns)\s*\(|\bself\.fail\s*\("
)
JS_ASSERT_RE = re.compile(r"(?<![\w$.])expect\s*\(|(?<![\w$.])assert(?:\.\w+)?\s*\(")
PY_NOOP_RE = re.compile(
    r"^\s*assert\s+(?:True|1|not\s+False|not\s+None)\s*(?:,.*)?$"
    r"|\bself\.assertTrue\(\s*(?:True|1)\s*\)"
    r"|\bself\.assert(?:Equal|Is)\(\s*([\w.]+)\s*,\s*\1\s*\)"
)
JS_NOOP_RE = re.compile(
    r"\bexpect\(\s*(?:true|1|!0)\s*\)\s*\.\s*(?:toBe\(\s*(?:true|1)\s*\)|toBeTruthy\(\s*\)|toEqual\(\s*(?:true|1)\s*\))"
    r"|\bexpect\(\s*([\w$.]+)\s*\)\s*\.\s*(?:toBe|toEqual|toStrictEqual)\(\s*\1\s*\)"
)


def assert_count(text: str, fw: Optional[str]) -> int:
    code = code_part(text, fw)
    if fw == PYTEST:
        return len(PY_ASSERT_RE.findall(code))
    if fw == JEST:
        return len(JS_ASSERT_RE.findall(code))
    return 0


def is_noop_assert(text: str, fw: Optional[str]) -> bool:
    code = code_part(text, fw)
    rx = PY_NOOP_RE if fw == PYTEST else JS_NOOP_RE
    return bool(rx.search(code))


# Statement-level "this is an assertion or an expected value" context.
ASSERT_CTX_RE = re.compile(
    r"(?<![\w$.])assert\b|\.assert\w*\s*\(|\bassert_\w+\s*\(|(?<![\w$.])expect\s*\("
    r"|\bparametrize\s*\(|\.each\s*[(`]"
    r"|^\s*(?:(?:const|let|var)\s+)?(?:self\.)?(?:expected|want|EXPECTED)\w*\s*(?::[^=]*)?=(?!=)"
)


def is_test_like(text: str, fw: Optional[str]) -> bool:
    """A def, decorator, describe/it/test header or assertion (for commented-out)."""
    s = text.strip()
    if not s:
        return False
    if fw == PYTEST:
        return bool(PY_DEF_RE.match(s) or PY_CLASS_RE.match(s) or s.startswith("@") or PY_ASSERT_RE.search(code_part(s, fw)))
    if fw == JEST:
        return bool(JS_DEF_RE.match(s) or JS_DESCRIBE_RE.match(s) or JS_ASSERT_RE.search(code_part(s, fw)))
    return False


# ---------------------------------------------------------------- tolerances

TOL_CALL_RE = re.compile(
    r"\b(approx|isclose|allclose|assert_allclose|assertAlmostEqual|assertNotAlmostEqual"
    r"|assert_almost_equal|assert_array_almost_equal|toBeCloseTo|abs)\s*\("
)
APPROX_FUNCS = {
    "approx", "isclose", "allclose", "assert_allclose", "assertAlmostEqual",
    "assert_almost_equal", "assert_array_almost_equal", "toBeCloseTo",
}
EXACT_RE = re.compile(
    r"==|\bassertEqual\s*\(|\bassert_equal\s*\(|\bassert_array_equal\s*\(|\.toBe\s*\("
    r"|\.toEqual\s*\(|\.toStrictEqual\s*\(|\bassert\.(?:strict)?[eE]qual\s*\("
)
POSITIONAL = {
    "approx": {1: "rel", 2: "abs"},
    "assert_allclose": {2: "rtol", 3: "atol"},
    "allclose": {2: "rtol", 3: "atol"},
    "isclose": {2: "rtol", 3: "atol"},
    "assertAlmostEqual": {2: "places"},
    "assertNotAlmostEqual": {2: "places"},
    "assert_almost_equal": {2: "decimal"},
    "assert_array_almost_equal": {2: "decimal"},
    "toBeCloseTo": {1: "digits"},
}
DEFAULTS = {
    "approx": {"rel": 1e-6, "abs": 1e-12},
    "assert_allclose": {"rtol": 1e-7, "atol": 0.0},
    "allclose": {"rtol": 1e-5, "atol": 1e-8},
    "isclose": {"rtol": 1e-5, "atol": 1e-8, "rel_tol": 1e-9, "abs_tol": 0.0},
    "assertAlmostEqual": {"places": 7.0},
    "assertNotAlmostEqual": {"places": 7.0},
    "assert_almost_equal": {"decimal": 7.0},
    "assert_array_almost_equal": {"decimal": 6.0},
    "toBeCloseTo": {"digits": 2.0},
}
# For these a smaller number is looser.
DIGIT_PARAMS = {"places", "decimal", "digits"}
TOL_PARAMS = {"rel", "abs", "rtol", "atol", "rel_tol", "abs_tol", "delta", "places", "decimal", "digits"}
# Linear: the value is cut with str.strip(), not with \s*(.*?)\s*$ (quadratic on
# a long whitespace run).
_KW_RE = re.compile(r"^\s*(\w+)\s*=(?!=)(.*)")
# Used with .match() right after a closing paren; the lookbehind stops finditer from
# retrying the leading \s* at every position of a long whitespace run.
_BOUND_RE = re.compile(r"(?<!\s)\s*<=?\s*([-+]?(?:%s))" % _NUM)


def _call_args(code: str, start: int) -> Tuple[List[str], int]:
    """Top-level comma-split args of the call whose '(' is at code[start-1]."""
    args = []
    depth = 0
    cur_start = start
    i = start
    n = len(code)
    while i < n:
        c = code[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                args.append(code[cur_start:i])
                return args, i + 1
            depth -= 1
        elif c == "," and depth == 0:
            args.append(code[cur_start:i])
            cur_start = i + 1
        i += 1
    args.append(code[cur_start:])
    return args, n


def tolerances(text: str) -> Dict[str, Dict[str, float]]:
    """First call of each tolerance function in a statement -> {param: value}."""
    code = strip_strings(text)
    found: Dict[str, Dict[str, float]] = {}
    for m in TOL_CALL_RE.finditer(code):
        func = m.group(1)
        if func in found:
            continue
        args, end = _call_args(code, m.end())
        if func == "abs":
            b = _BOUND_RE.match(code, end)
            if b:
                v = num_value(b.group(1))
                if v is not None:
                    found["abs<"] = {"bound": v}
            continue
        params: Dict[str, float] = {}
        pos = POSITIONAL.get(func, {})
        p_index = 0
        for a in args:
            kw = _KW_RE.match(a)
            if kw:
                name, val = kw.group(1), kw.group(2).strip()
                if name in TOL_PARAMS and NUM_FULL_RE.match(val):
                    v = num_value(val)
                    if v is not None:
                        params[name] = v
                continue
            if p_index in pos and NUM_FULL_RE.match(a.strip()):
                v = num_value(a.strip())
                if v is not None:
                    params[pos[p_index]] = v
            p_index += 1
        found[func] = params
    return found


def _effective(func: str, params: Dict[str, float]) -> Dict[str, float]:
    """Param -> tolerance where bigger always means looser; defaults filled in."""
    merged = dict(DEFAULTS.get(func, {}))
    merged.update(params)
    if func in ("assertAlmostEqual", "assertNotAlmostEqual"):
        if "delta" in params:
            return {"tol": params["delta"]}
        return {"tol": 0.5 * 10 ** -min(merged.get("places", 7.0), 300)}
    out = {}
    for k, v in merged.items():
        out[k] = 10 ** -min(v, 300) if k in DIGIT_PARAMS else v
    return out


def compare_tolerance(old_text: str, new_text: str) -> Tuple[bool, bool, str]:
    """(loosened, changed_at_all, reason) between two statements."""
    old = tolerances(old_text)
    new = tolerances(new_text)
    changed = False
    for func, nparams in new.items():
        if func not in old:
            if func in APPROX_FUNCS and EXACT_RE.search(strip_strings(old_text)) and not (set(old) & APPROX_FUNCS):
                return True, True, "exact comparison replaced by approximate %s()" % func
            continue
        eo, en = _effective(func, old[func]), _effective(func, nparams)
        for k in set(eo) | set(en):
            if k not in eo or k not in en:
                continue
            if en[k] != eo[k]:
                changed = True
            if en[k] > eo[k] * (1 + 1e-9) + 1e-300:
                label = func if func != "abs<" else "abs() bound"
                return True, True, "%s tolerance loosened (%s)" % (label, _describe(func, old[func], nparams, k))
    if set(old) != set(new):
        changed = True
    return False, changed, ""


def _describe(func: str, old: Dict[str, float], new: Dict[str, float], key: str) -> str:
    keys = [k for k in set(old) | set(new) if old.get(k) != new.get(k)] or [key]
    bits = []
    for k in sorted(keys):
        o = old.get(k, "default")
        nv = new.get(k, "default")
        bits.append("%s: %s -> %s" % (k, _fmt(o), _fmt(nv)))
    return ", ".join(bits)


def _fmt(v) -> str:
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e6:
        return str(int(v))
    return str(v)


def literal_change(old_text: str, new_text: str) -> Optional[Tuple[object, object]]:
    """If the statements have the same shape and only literals differ, return
    the first (old, new) differing literal values; else None."""
    a, b = tokens(old_text), tokens(new_text)
    if len(a) != len(b):
        return None
    first = None
    for (ka, va), (kb, vb) in zip(a, b):
        if ka == "t" or kb == "t":
            if (ka, va) != (kb, vb):
                return None
            continue
        if (ka, va) != (kb, vb) and first is None:
            first = (va, vb)
    return first


# ------------------------------------------------------------- comment lines


def uncomment(text: str, fw: Optional[str]) -> Optional[str]:
    """The text of a line-comment with its marker removed, or None."""
    s = text.strip()
    mark = "#" if fw == PYTEST else "//"
    if s.startswith(mark):
        return s.lstrip(mark[0]).strip()
    return None


_STR_PREFIX = set("rRbBuUfF")


def _escaped(text: str, j: int, lo: int) -> bool:
    """An odd run of backslashes ends just before text[j] (not looking before lo)."""
    k = j - 1
    while k >= lo and text[k] == "\\":
        k -= 1
    return (j - 1 - k) % 2 == 1


def triple_quotes(text: str, state: Optional[str]) -> Tuple[List[Tuple[int, str]], Optional[str]]:
    """Python triple-quote delimiters on a line, given the open delimiter (or None).

    Returns ([(column, "open"|"close")], state after the line). Single-quoted
    strings and ``#`` comments outside a triple-quoted string are skipped. Linear.
    """
    out: List[Tuple[int, str]] = []
    i = 0
    n = len(text)
    while i < n:
        if state is not None:
            j = text.find(state, i)
            while j > 0 and _escaped(text, j, i):
                j = text.find(state, j + 1)
            if j < 0:
                return out, state
            out.append((j, "close"))
            state = None
            i = j + 3
            continue
        c = text[i]
        if c == "#":
            break
        if c in "\"'":
            if text.startswith(c * 3, i):
                state = c * 3
                out.append((i, "open"))
                i += 3
                continue
            k = i + 1
            while k < n and text[k] != c:
                k += 2 if text[k] == "\\" else 1
            i = k + 1
            continue
        i += 1
    return out, state


def is_bare_string_start(text: str, col: int) -> bool:
    """The triple quote at ``col`` starts the line's statement (``\"\"\"`` or ``r\"\"\"``)."""
    head = text[:col].strip()
    return not head or (len(head) <= 2 and set(head) <= _STR_PREFIX)


# ------------------------------------------- multi-line strings and comments
#
# The rules read one line at a time, so a line inside a docstring, a block comment or a
# multi-line template literal looks like code. ``blank_multiline`` blanks those parts of
# one side of a hunk (old: context + removed lines; new: context + added lines), in order.
# Strings and comments that open and close on the same line are left to string_spans().
# When a hunk starts inside such a string, its opener is not in the diff; then a closing
# delimiter with no opener before it marks the lines above it as string content.

_EXPR_END = tuple("=([{,:+-*/%<>!&|^~?;")
_CLOSE_ONLY = set(")]},; \t")


def blank_multiline(texts: List[str], fw: Optional[str], templates: bool = True) -> List[str]:
    """``templates=False`` keeps the content of JS template literals (an inline snapshot is an
    expected value) while still blanking block comments."""
    if fw == PYTEST:
        return _py_blank(texts)
    if fw == JEST:
        return _js_blank(texts, templates)
    return list(texts)


def _py_blank(texts: List[str]) -> List[str]:
    marks: List[Tuple[int, int, str]] = []  # (line, column, "open"|"close") with no initial state
    state: Optional[str] = None
    for li, t in enumerate(texts):
        if '"""' in t or "'''" in t or state is not None:
            ms, state = triple_quotes(t, state)
            marks.extend((li, c, w) for c, w in ms)
    if not marks:
        return list(texts)
    start = _py_start_state(texts, marks)
    out: List[str] = []
    state = start
    for t in texts:
        if state is None and '"""' not in t and "'''" not in t:
            out.append(t)
            continue
        ms, after = triple_quotes(t, state)
        chars = list(t)
        carried = 0 if state is not None else None  # a string from an earlier line, open at column 0
        opened = None
        for col, what in ms:
            if what == "open":
                opened = col
            elif carried is not None:
                chars[carried:col + 3] = " " * (col + 3 - carried)
                carried = None
            else:
                opened = None  # opened and closed on this line: string_spans() handles it
        if carried is not None:
            chars = [" "] * len(t)
        elif opened is not None:
            chars[opened:] = " " * (len(t) - opened)
        out.append("".join(chars))
        state = after
    return out


def _py_start_state(texts: List[str], marks: List[Tuple[int, int, str]]) -> Optional[str]:
    """The triple quote the hunk side starts inside, or None.

    The first delimiter is read as a closer when nothing but closing brackets follows
    it on its line and the text before it is prose (``more text.\"\"\"``), not the start
    of an expression (``x = \"\"\"``). A delimiter alone on its line is a closer only
    when the side has an odd number of delimiters and the line above does not open a
    block (``def f():`` before a docstring).
    """
    li, col, _ = marks[0]
    t = texts[li]
    after = t[col + 3:].strip()
    if after and not (set(after) <= _CLOSE_ONLY or after.startswith("#")):
        return None
    before = t[:col].strip()
    if before:
        if before.endswith(_EXPR_END) or (len(before) <= 2 and set(before) <= _STR_PREFIX):
            return None
        if before.split()[-1] in ("return", "yield", "in", "else", "lambda", "not", "and", "or", "assert"):
            return None
        return t[col:col + 3]
    if len(marks) % 2 == 0:
        return None
    for q in range(li - 1, -1, -1):
        prev = code_part(texts[q], PYTEST).rstrip()
        if prev:
            if prev.endswith(_EXPR_END + ("\\",)):
                return None
            break
    return t[col:col + 3]


def _js_blank(texts: List[str], templates: bool = True) -> List[str]:
    out, _state, start = _js_scan(texts, None, templates)
    if start is not None:
        out, _state, _ = _js_scan(texts, start, templates)
    return out


_REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_AFTER_WORDS = ("return", "typeof", "case", "in", "of", "void", "delete", "throw", "yield", "await")


def _regex_can_start(t: str, i: int) -> bool:
    """A ``/`` at t[i] starts a regex literal (not a division): judged from the code before it."""
    j = i - 1
    while j >= 0 and t[j] in " \t":
        j -= 1
    if j < 0:
        return True
    if t[j] in _REGEX_AFTER:
        return True
    k = j
    while k >= 0 and (t[k].isalnum() or t[k] in "_$"):
        k -= 1
    return t[k + 1:j + 1] in _REGEX_AFTER_WORDS


def _js_scan(texts: List[str], state: Optional[str], templates: bool = True
             ) -> Tuple[List[str], Optional[str], Optional[str]]:
    """Blank block comments (also one-line ones) and the lines of multi-line template literals.

    Returns (lines, state at the end, the state the side probably started in). The last is
    "block" when a ``*/`` appears outside any comment before the first ``/*``, and "tmpl"
    when, before any multi-line literal or comment opened, a backtick that does not close on
    its line stands alone with only closing brackets after it (`` `, ``, `` `) ``): the closer
    of a template literal opened above the hunk. Linear: every character is looked at a
    bounded number of times.
    """
    out: List[str] = []
    stray: Optional[str] = None
    seen_open = False
    for t in texts:
        chars = list(t)
        n = len(t)
        i = 0
        tmpl_from = 0 if state == "tmpl" else None
        while i < n:
            if state == "block":
                j = t.find("*/", i)
                end = n if j < 0 else j + 2
                chars[i:end] = " " * (end - i)
                i = end
                if j >= 0:
                    state = None
                continue
            if state == "tmpl":
                j = i
                while j < n and t[j] != "`":
                    j += 2 if t[j] == "\\" else 1
                if j >= n:
                    if tmpl_from is not None and templates:
                        chars[tmpl_from:] = " " * (n - tmpl_from)
                    i = n
                    break
                if tmpl_from is not None and templates:  # opened on an earlier line: blank up to the closing backtick
                    chars[tmpl_from:j] = " " * (j - tmpl_from)
                tmpl_from = None
                state = None
                i = j + 1
                continue
            c = t[i]
            if c in "'\"":
                j = i + 1
                while j < n and t[j] != c:
                    j += 2 if t[j] == "\\" else 1
                i = j + 1
                continue
            if c == "`":
                state = "tmpl"
                # Blank the content only if the literal does not close on this line.
                j = i + 1
                while j < n and t[j] != "`":
                    j += 2 if t[j] == "\\" else 1
                if j < n:
                    state = None
                    i = j + 1
                    continue
                if not seen_open and stray is None and not t[:i].strip() and set(t[i + 1:]) <= _CLOSE_ONLY:
                    stray = "tmpl"
                seen_open = True
                tmpl_from = i + 1
                i = i + 1
                continue
            if c == "/" and i + 1 < n:
                nxt = t[i + 1]
                if nxt == "/":
                    break
                if nxt == "*":
                    seen_open = True
                    state = "block"
                    chars[i:i + 2] = "  "
                    i += 2  # "/*/" does not close itself
                    continue
                if _regex_can_start(t, i):
                    j = i + 1
                    cls = False
                    while j < n and (t[j] != "/" or cls):
                        if t[j] == "\\":
                            j += 1
                        elif t[j] == "[":
                            cls = True
                        elif t[j] == "]":
                            cls = False
                        j += 1
                    i = j + 1
                    continue
            if c == "*" and i + 1 < n and t[i + 1] == "/" and not seen_open and stray is None:
                stray = "block"
            i += 1
        out.append("".join(chars))
    return out, state, stray


def norm(text: str) -> str:
    return " ".join(text.split())


def identifiers(text: str) -> Set[str]:
    return set(IDENT_RE.findall(text))



# ------------------------------------------------------------ assert-weakened


def top_level(text: str, start: int = 0, end: Optional[int] = None) -> List[Tuple[int, str]]:
    """Positions of top-level ``,`` and ``==`` in text[start:end], outside strings and brackets."""
    end = len(text) if end is None else end
    out: List[Tuple[int, str]] = []
    spans = [s for s in string_spans(text) if s[1] > start and s[0] < end]
    depth = 0
    i = start
    k = 0
    while i < end:
        if k < len(spans) and i >= spans[k][0]:
            i = max(i, spans[k][1])
            k += 1
            continue
        c = text[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0:
            if c == "," :
                out.append((i, ","))
            elif c == "=" and text.startswith("==", i) and not text.startswith("===", i) and (i == 0 or text[i - 1] not in "=!<>"):
                out.append((i, "=="))
                i += 2
                continue
        i += 1
    return out


_PY_ASSERT_STMT_RE = re.compile(r"^\s*assert\b")
_OR_TRUE_RE = re.compile(r"(?:^|[\s)])or\s+True\s*$")


def py_assert_expr(stmt: str) -> Optional[str]:
    """The tested expression of a Python ``assert`` statement (message cut), else None."""
    m = _PY_ASSERT_STMT_RE.match(stmt)
    if not m:
        return None
    text = strip_comment(stmt, PYTEST)
    commas = [p for p, w in top_level(text, m.end()) if w == ","] if "," in text else []
    return text[m.end(): commas[0] if commas else len(text)].strip()


def _same_sides(expr: str) -> bool:
    if "==" not in expr:
        return False
    eqs = [p for p, w in top_level(expr) if w == "=="]
    if len(eqs) != 1:
        return False
    left, right = norm(expr[:eqs[0]]), norm(expr[eqs[0] + 2:])
    return bool(left) and "".join(left.split()) == "".join(right.split()) and plain_operand(left, PYTEST)


_SCALAR_RE = re.compile(r"[-+]?(?:%s)\Z|(?:True|False|None)\Z" % _NUM)


def plain_operand(expr: str, fw: Optional[str]) -> bool:
    """A name, attribute chain or call (``v``, ``res.body.id``, ``g(2)``) that builds no value
    of its own: no list/dict/object literal, no ``new``, no ``X.from([...])``. Comparing such a
    value with itself is a matcher self-test (vitest checks ``toEqual`` on typed arrays this
    way), not a weakened test. In Python a bare scalar literal (``4 == 4``) also counts.
    """
    e = expr.strip()
    code = strip_strings(e)
    if fw == PYTEST and (_SCALAR_RE.match(e) or (len(code) == 2 and code[0] in "\"'" and code[1] == code[0])):
        return True
    if not e or not (e[0].isalpha() or e[0] in "_$"):
        return False
    if re.search(r"\bnew\b", code):
        return False
    for i, c in enumerate(code):
        if c == "{":
            return False
        if c == "[":
            j = i - 1
            while j >= 0 and code[j] == " ":
                j -= 1
            if j < 0 or not (code[j].isalnum() or code[j] in "_$)]"):
                return False  # an array literal, not an index
    return True


_EXPECT_RE = re.compile(r"(?<![\w$.])expect\s*\(")
# Starts only where a chain can start (after a bracket or quote), so a long .a.a.a run is
# scanned once, not once per dot.
_CHAIN_RE = re.compile(r"(?<![\w$.\s])((?:\s*\.\s*[A-Za-z_$][\w$]*)+)\s*\(")


def js_expect(stmt: str) -> Optional[Tuple[str, List[str], str, List[str]]]:
    """(subject, chain parts, matcher, matcher args) of the first ``expect(...)...matcher(...)``."""
    code = strip_comment(stmt, JEST)
    blank = _blank_same_length(code)  # same offsets as code, brackets in strings hidden
    m = _EXPECT_RE.search(blank)  # not an "expect(" inside a string (a fixture file's source)
    if not m:
        return None
    _args, end = _call_args(blank, m.end())
    subject = norm(code[m.end(): end - 1])
    c = _CHAIN_RE.match(blank, end)
    if not c:
        return subject, [], "", []
    parts = [p.strip() for p in c.group(1).split(".") if p.strip()]
    margs, _end = _call_args(blank, c.end())
    raw = []
    pos = c.end()
    for a in margs:
        raw.append(code[pos: pos + len(a)].strip())
        pos += len(a) + 1
    return subject, parts, parts[-1], [a for a in raw if a]


def _blank_same_length(text: str) -> str:
    """String contents replaced by spaces, keeping every offset."""
    spans = string_spans(text)
    if not spans:
        return text
    parts = []
    last = 0
    for a, b in spans:
        parts.append(text[last:a + 1])
        parts.append(" " * max(0, b - a - 2))
        last = b - 1
    parts.append(text[last:])
    return "".join(parts)


_RAISES_RE = re.compile(r"\b(?:pytest\s*\.\s*raises|raises|assertRaises)\s*\(")
_BROAD_EXC = {"Exception", "BaseException"}
_UNITTEST_CALL_RE = re.compile(r"\bself\s*\.\s*(assert\w+)\s*\(")
_EXACT_UNITTEST = {"assertEqual", "assertEquals", "assertIs", "assertIn", "assertListEqual", "assertDictEqual",
                   "assertCountEqual", "assertSequenceEqual", "assertTupleEqual", "assertSetEqual",
                   "assertMultiLineEqual", "assertAlmostEqual"}
_WEAK_UNITTEST = {"assertTrue", "assertIsNotNone"}
_EXACT_MATCHERS = {"toEqual", "toStrictEqual", "toBe"}
_WEAK_MATCHERS = {"toMatchObject", "toBeDefined", "toBeTruthy"}
_THROW_MATCHERS = {"toThrow", "toThrowError"}


def _first_arg(stmt: str, rx) -> Optional[Tuple[str, str]]:
    """(callee group or '', first argument) of the first call matching rx."""
    blank = _blank_same_length(stmt)
    m = rx.search(blank)
    if not m:
        return None
    args, _ = _call_args(blank, m.end())
    first = stmt[m.end(): m.end() + len(args[0])].strip() if args else ""
    return (m.group(1) if m.groups() else ""), first


def weak_alone(stmt: str, fw: Optional[str]) -> Optional[str]:
    """Reason when a statement is a tautology on its own (``x == x``, ``... or True``)."""
    if fw == PYTEST:
        m = _PY_ASSERT_STMT_RE.match(stmt)
        if m is None:
            return None
        if "True" not in stmt:
            # Cheap reject before the exact check: x == x needs the right side to start like the left.
            i = stmt.find("==", m.end())
            left = "".join(stmt[m.end():i].split()) if i >= 0 else ""
            if not left or not "".join(stmt[i + 2:].split()).startswith(left):
                return None
        expr = py_assert_expr(stmt)
        if expr is None:
            return None
        if _OR_TRUE_RE.search(strip_strings(expr)):
            return "assert made always-true with 'or True'"
        if _same_sides(expr):
            return "assert compares an expression with itself"
        return None
    if fw == JEST and "expect" in stmt:
        e = js_expect(stmt)
        if (e and e[2] in _EXACT_MATCHERS and len(e[3]) == 1 and e[0] and "".join(e[0].split()) == "".join(e[3][0].split())
                and plain_operand(e[0], JEST)):
            return "expect compares an expression with itself"
    return None


def subject(stmt: str, fw: Optional[str]) -> Optional[str]:
    """What an assertion statement is about, to match an old one with its new form."""
    if fw == JEST:
        e = js_expect(stmt) if "expect" in stmt else None
        return None if e is None else "expect:" + "".join(e[0].split())
    if "aises" not in stmt and "self" not in stmt:
        return None
    if _RAISES_RE.search(_blank_same_length(stmt)):
        return "raises"
    u = _first_arg(stmt, _UNITTEST_CALL_RE)
    if u:
        return "unittest:" + "".join(u[1].split())
    return None


def weak_pair(old: str, new: str, fw: Optional[str]) -> Optional[str]:
    """Reason when ``new`` is a weaker form of the assertion ``old``."""
    if fw == JEST:
        a, b = js_expect(old), js_expect(new)
        if not a or not b or not a[2] or not b[2]:
            return None
        if a[2] in _EXACT_MATCHERS and b[2] in _WEAK_MATCHERS:
            return "%s() weakened to %s()" % (a[2], b[2])
        if "not" in b[1] and "not" not in a[1] and "".join(a[0].split()) == "".join(b[0].split()) and a[2] == b[2]:
            return ".not added to an existing expect"
        if a[2] in _THROW_MATCHERS and b[2] in _THROW_MATCHERS and a[3] and not b[3]:
            return "%s(%s) weakened to %s()" % (a[2], a[3][0], b[2])
        return None
    if fw == PYTEST:
        ra, rb = _first_arg(old, _RAISES_RE), _first_arg(new, _RAISES_RE)
        if ra and rb and ra[1] and ra[1] not in _BROAD_EXC and rb[1] in _BROAD_EXC:
            return "raises(%s) broadened to raises(%s)" % (ra[1], rb[1])
        ua, ub = _first_arg(old, _UNITTEST_CALL_RE), _first_arg(new, _UNITTEST_CALL_RE)
        if ua and ub and ua[0] in _EXACT_UNITTEST and ub[0] in _WEAK_UNITTEST:
            return "%s() weakened to %s()" % (ua[0], ub[0])
    return None


_PY_IF_FALSE_RE = re.compile(r"^\s*if\s+(?:False|0)\s*:\s*$")
_JS_IF_FALSE_RE = re.compile(r"^\s*if\s*\(\s*(?:false|0)\s*\)\s*\{?\s*$")
_BARE_RETURN_RE = re.compile(r"^\s*return\s*;?\s*$")
_EXCEPT_ASSERTION_RE = re.compile(r"^\s*except\s*\(?[\w.,\s]*\bAssertionError\b[^:]*:\s*(.*)$")
# One \s* run before the keyword and one after it, never two adjacent (quadratic on tabs).
_SWALLOW_RE = re.compile(r"^\s*(?:(?:pass|\.\.\.|continue)\s*)?$")


def is_if_false(text: str, fw: Optional[str]) -> bool:
    code = code_part(text, fw)
    return bool((_PY_IF_FALSE_RE if fw == PYTEST else _JS_IF_FALSE_RE).match(code))


def is_bare_return(text: str, fw: Optional[str]) -> bool:
    return bool(_BARE_RETURN_RE.match(code_part(text, fw)))


def except_assertion(text: str) -> Optional[str]:
    """For ``except AssertionError: <rest>`` return <rest> (may be ''), else None."""
    m = _EXCEPT_ASSERTION_RE.match(code_part(text, PYTEST))
    return None if m is None else m.group(1).strip()


def is_swallow(text: str) -> bool:
    return bool(_SWALLOW_RE.match(code_part(text, PYTEST))) and bool(text.strip())


def is_def_header(texts: List[str], i: int, fw: Optional[str]) -> bool:
    """texts[i] ends the header of a test definition (``def test_x():`` / ``it('x', () => {``)."""
    code = code_part(texts[i], fw).rstrip()
    if fw == PYTEST:
        if not code.endswith(":"):
            return False
        if def_name(texts, i, fw):
            return True
        j = i - 1
        while j >= 0 and i - j <= 6:
            if def_name(texts, j, fw):
                return True
            if code_part(texts[j], fw).rstrip().endswith(":"):
                return False
            j -= 1
        return False
    if fw == JEST:
        if not code.endswith("{"):
            return False
        return bool(def_name(texts, i, fw) or (i > 0 and JS_DEF_RE.match(texts[i - 1]) and def_name(texts, i - 1, fw)))
    return False


# ------------------------------------------------------- test-config-weakened

PYTEST_CFG_FILES = ("pytest.ini", "setup.cfg", "tox.ini", "pyproject.toml")


def config_kind(path: str) -> Optional[str]:
    """Which test-runner config a file is: pytest-cfg, conftest, jest, package; else None."""
    base = _base(path)
    if base in PYTEST_CFG_FILES:
        return "pytest-cfg"
    if base == "conftest.py":
        return "conftest"
    if base.startswith("jest.config."):
        return "jest"
    if base == "package.json":
        return "package"
    return None


ADDOPTS_RE = re.compile(r"^\s*addopts\s*=")
CFG_KEY_RE = re.compile(r"^\s*[\w.-]+\s*=")
DROP_OPT_RE = re.compile(r"(?<![\w-])(--deselect|--ignore-glob|--ignore|-k)(?=[\s=\"',\]]|$)")
COLLECT_IGNORE_RE = re.compile(r"^\s*collect_ignore(?:_glob)?\s*(?:\+?=|\.\s*(?:append|extend|insert)\s*\()")
PY_FUNC_RE = re.compile(r"^(\s*)(?:async\s+)?def\s+(\w+)")
DESELECT_RE = re.compile(
    r"\bitems\s*\[\s*:\s*\]\s*=|\bitems\s*\.\s*(?:remove|pop|clear)\s*\(|\bdel\s+items\b|\bpytest_deselected\s*\("
)
JEST_IGNORE_KEY_RE = re.compile(r"[\"']?(testPathIgnorePatterns|modulePathIgnorePatterns)[\"']?\s*:")
TEST_SCRIPT_RE = re.compile(r"^\s*\"test\"\s*:\s*\"(.*)\"\s*,?\s*$")
SCRIPT_WEAK_RE = re.compile(r"\|\|\s*true\b|\|\|\s*exit\s+0\b|--passWithNoTests\b")


def addopts_lines(texts: List[str]) -> List[bool]:
    """Per line: is it (part of) a pytest ``addopts`` value?

    ini files continue a value on indented lines; pyproject.toml uses a string
    (one line) or an array (until the closing ``]``).
    """
    out = []
    mode = None  # None | "ini" | "array"
    for t in texts:
        s = t.strip()
        if ADDOPTS_RE.match(t):
            val = t.split("=", 1)[1].strip()
            if val.startswith("["):
                mode = None if "]" in strip_strings(val) else "array"
            elif val.startswith(("'", '"')):
                mode = None
            else:
                mode = "ini"
            out.append(True)
            continue
        if mode == "array":
            out.append(True)
            if "]" in strip_strings(t):
                mode = None
            continue
        if mode == "ini" and s and t[:1].isspace():
            out.append(True)
            continue
        mode = None
        out.append(False)
    return out


def drop_opts(text: str) -> List[str]:
    return DROP_OPT_RE.findall(text)


def jest_ignore_entries(texts: List[str]) -> List[List[str]]:
    """Per line: the ignore-pattern strings it adds to testPathIgnorePatterns / modulePathIgnorePatterns."""
    out: List[List[str]] = []
    inside = False
    for t in texts:
        m = JEST_IGNORE_KEY_RE.search(t)
        rest = t[m.end():] if m else (t if inside else "")
        if m:
            inside = "[" in rest and "]" not in rest
        elif inside and "]" in t:
            rest = t.split("]", 1)[0]
            inside = False
        vals = [str_value(rest[a:b]) for a, b in string_spans(rest)]
        out.append([v for v in vals if v.strip("/").replace("<rootDir>", "").strip("/") != "node_modules"])
    return out


# ------------------------------------------------- parametrized cases (test-deleted)

# (?<![\w$.]): an `it` inside an it.it.it... chain does not start a new (linear) scan.
TABLE_OPENER_RE = re.compile(r"\bparametrize\s*\(|(?<![\w$.])(?:it|test|describe|xit|xtest|fit)(?:\.\w+)*\.each\s*\(")
_CLOSER_RE = re.compile(r"^[\])}]+\s*[,)]*\s*,?$")
_JS_EACH_CLOSE_RE = re.compile(r"^\]\s*\)\s*\(")
_ROW_START_RE = re.compile(r"^(?:[(\[{]|pytest\s*\.\s*param\s*\(|[-+]?\.?\d|\"\"|''|``|None\b|True\b|False\b|null\b)")


def is_table_row(code: str) -> bool:
    """A self-contained element line of a case table: ``(1, 2),`` / ``[0, 10],`` / ``pytest.param(...)``."""
    c = code.strip()
    return bool(c) and balance(c) == 0 and bool(_ROW_START_RE.match(c)) and c.endswith((",", ")", "]", "}"))


TABLE_LOOKBACK = 400


class TableContext:
    """``table_row_context`` for every line of one hunk side, with the per-hunk work done once.

    A forward pass with a stack finds, for each line, the nearest line above it whose
    brackets are still open (what scanning back with a running balance finds); the
    opener test and the forward scan to the closing brackets are cached per line.
    """

    def __init__(self, texts: List[str], fw: Optional[str], removed: Sequence[bool]) -> None:
        self.texts, self.fw, self.removed = texts, fw, removed
        n = len(texts)
        self.open_above: List[int] = [-1] * n
        stack: List[List[int]] = []  # [line, brackets still open]
        for q in range(n):
            self.open_above[q] = stack[-1][0] if stack else -1
            b = balance(code_part(texts[q], fw))
            while b < 0 and stack:
                take = min(-b, stack[-1][1])
                stack[-1][1] -= take
                b += take
                if stack[-1][1] == 0:
                    stack.pop()
            if b > 0:
                stack.append([q, b])
        # Next line after q that is neither a table row nor blank.
        self.after_rows: List[int] = [n] * (n + 1)
        for q in range(n - 1, -1, -1):
            row = is_table_row(code_part(texts[q], fw)) or not texts[q].strip()
            self.after_rows[q] = self.after_rows[q + 1] if row else q
        self._opener: Dict[int, bool] = {}
        self._closing: Dict[int, bool] = {}

    def __call__(self, p: int) -> bool:
        q = self.open_above[p]
        if q >= 0 and p - q < TABLE_LOOKBACK:
            if q not in self._opener:
                self._opener[q] = bool(TABLE_OPENER_RE.search(strip_strings(self.texts[q]))) and not self.removed[q]
            return self._opener[q]
        start = self.after_rows[p + 1]
        if start not in self._closing:
            self._closing[start] = _table_closes(self.texts, start, self.fw, self.removed)
        return self._closing[start]


def table_row_context(texts: List[str], p: int, fw: Optional[str], removed: Sequence[bool]) -> bool:
    """texts[p] (a row) sits in a parametrize / .each table whose header is not itself removed.

    Looks back for the unclosed opener; if the hunk starts before one is found,
    looks forward over rows and closing brackets to the test that uses the table.
    For many rows of one hunk use ``TableContext``, which does this once per hunk.
    """
    return TableContext(texts, fw, removed)(p)


def _table_closes(texts: List[str], q: int, fw: Optional[str], removed: Sequence[bool]) -> bool:
    """From texts[q] (the first line after the rows): closing brackets, then the test using the table."""
    n = len(texts)
    closers = 0
    while q < n:
        c = code_part(texts[q], fw).strip()
        if fw == JEST and _JS_EACH_CLOSE_RE.match(c):
            return not removed[q]
        if not _CLOSER_RE.match(c):
            break
        closers += 1
        q += 1
    if fw == PYTEST and closers and q < n:
        s = texts[q].strip()
        return (bool(PY_DEF_RE.match(texts[q])) or s.startswith("@")) and not removed[q]
    return False
