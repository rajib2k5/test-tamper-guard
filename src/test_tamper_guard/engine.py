"""Run the rules over a parsed diff. Pure: no I/O, no code execution."""

import keyword
import re
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from typing import Dict, List, Optional, Set, Tuple

from . import rules as R
from .diffparse import FileDiff, Hunk, Line, parse_diff

SEVERITY_RANK = {R.LOW: 1, R.MEDIUM: 2, R.HIGH: 3}
EVIDENCE_CHARS = 200


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str  # "high" | "medium" | "low"
    path: str
    line: int  # new-side line, or old-side line for deletions
    message: str
    evidence: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Config:
    # Directory names whose Python/JS files count as test code.
    test_dirs: Tuple[str, ...] = R.DEFAULT_TEST_DIRS


@dataclass
class _RemovedDef:
    name: str
    old_no: int
    evidence: str
    body: str
    replaced_by: Optional[str] = None  # a new test added in the same place (rename / rewrite)


@dataclass
class _DiffFacts:
    """Diff-wide facts the per-file rules need."""
    non_test_changed: bool = False
    # (path, module stem, names of the definitions the change touches) of non-test code files
    # with a change beyond comments/whitespace.
    src_changes: List[Tuple[str, str, Set[str]]] = field(default_factory=list)
    added_def_names: Set[str] = field(default_factory=set)
    removed_src_defs: Set[str] = field(default_factory=set)
    added_src_defs: Set[str] = field(default_factory=set)
    # (path, marker kind) removed, so an edited skip line is not "added"; counted per file.
    removed_markers: Counter = field(default_factory=Counter)
    # (test name, marker kind) removed with its test: a skipped test moved to another file.
    moved_markers: Counter = field(default_factory=Counter)


def _evidence(text: str) -> str:
    s = text.strip()
    return s if len(s) <= EVIDENCE_CHARS else s[:EVIDENCE_CHARS] + "..."


def _sides(h: Hunk) -> Tuple[List[int], List[int], Dict[int, int], Dict[int, int]]:
    """Hunk line indices on the old and new side, and index -> side position."""
    old_idx = [i for i, ln in enumerate(h.lines) if ln.kind != "+"]
    new_idx = [i for i, ln in enumerate(h.lines) if ln.kind != "-"]
    return old_idx, new_idx, {h_i: p for p, h_i in enumerate(old_idx)}, {h_i: p for p, h_i in enumerate(new_idx)}


def _pairs(h: Hunk) -> Dict[int, int]:
    """Removed hunk index -> paired added hunk index, per change block."""
    out: Dict[int, int] = {}
    lines = h.lines
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].kind != "-":
            i += 1
            continue
        r_start = i
        while i < n and lines[i].kind == "-":
            i += 1
        a_start = i
        while i < n and lines[i].kind == "+":
            i += 1
        rem = list(range(r_start, a_start))
        add = list(range(a_start, i))
        if add:
            for ri, ai in R.pair_block([lines[k].text for k in rem], [lines[k].text for k in add]):
                out[rem[ri]] = add[ai]
    return out


_Sides = List[Tuple[List[str], List[str], List[str], List[str]]]


def _code_view(f: FileDiff, fw: Optional[str]) -> Tuple[FileDiff, _Sides]:
    """A copy of f with multi-line string and comment parts blanked, and per hunk the
    blanked (old side, new side) texts, then the same two with JS template literals kept
    (for comparing expected values). Each side is scanned on its own, in file order; a
    context line takes its new-side form in the copy."""
    hunks: List[Hunk] = []
    sides: _Sides = []
    for h in f.hunks:
        old_idx, new_idx, _, _ = _sides(h)
        old_b = R.blank_multiline([h.lines[i].text for i in old_idx], fw)
        new_b = R.blank_multiline([h.lines[i].text for i in new_idx], fw)
        texts = [ln.text for ln in h.lines]
        for p, i in enumerate(old_idx):
            texts[i] = old_b[p]
        for p, i in enumerate(new_idx):
            texts[i] = new_b[p]
        lines = [ln if t is ln.text else Line(ln.kind, t, ln.old_no, ln.new_no) for ln, t in zip(h.lines, texts)]
        hunks.append(replace(h, lines=lines))
        if fw == R.JEST:
            old_v = R.blank_multiline([h.lines[i].text for i in old_idx], fw, templates=False)
            new_v = R.blank_multiline([h.lines[i].text for i in new_idx], fw, templates=False)
        else:
            old_v, new_v = old_b, new_b
        sides.append((old_b, new_b, old_v, new_v))
    return replace(f, hunks=hunks), sides


def _collect_facts(files) -> _DiffFacts:
    facts = _DiffFacts()
    for f, fw, is_test, view in files:
        changed = f.is_new or f.is_deleted or any(ln.kind != " " for h in f.hunks for ln in h.lines)
        if not is_test and R.is_code_file(f.path) and changed:
            facts.non_test_changed = True
            if _substantive(f):
                facts.src_changes.append((f.path, R.module_stem(f.path), _touched_defs(f)))
        if view is not None:
            f = view[0]
        for hi, h in enumerate(f.hunks):
            if is_test:
                old_texts, new_texts = view[1][hi][:2] if view is not None else (
                    [ln.text for ln in h.lines if ln.kind != "+"], [ln.text for ln in h.lines if ln.kind != "-"])
                pos = old = 0
                for ln in h.lines:
                    if ln.kind == "-":
                        name = _marked_def(old_texts, old, fw)
                        for k in R.skip_markers(ln.text, fw):
                            facts.removed_markers[(f.path, k)] += 1
                            if name:
                                facts.moved_markers[(name, k)] += 1
                        old += 1
                        continue
                    if ln.kind == "+":
                        name = R.def_name(new_texts, pos, fw)
                        if name:
                            facts.added_def_names.add(name)
                    pos += 1
                    old += ln.kind == " "
            elif R.is_code_file(f.path):
                for ln in h.lines:
                    if ln.kind == "-":
                        facts.removed_src_defs.update(R.src_def_names(ln.text))
                    elif ln.kind == "+":
                        facts.added_src_defs.update(R.src_def_names(ln.text))
    return facts


def _code_key(text: str, fw: Optional[str]) -> str:
    """A source line with its comment and all whitespace removed ('' for comment lines)."""
    s = text.strip()
    if fw != R.PYTEST and s.startswith(("/*", "*", "*/")):
        return ""
    return "".join(R.strip_comment(text, fw).split())


def _substantive(f: FileDiff) -> bool:
    """The file's change is more than comments, blank lines and re-spacing."""
    fw = R.PYTEST if f.path.lower().endswith(".py") else None
    rem: Counter = Counter()
    add: Counter = Counter()
    for h in f.hunks:
        for ln in h.lines:
            if ln.kind == " ":
                continue
            k = _code_key(ln.text, fw)
            if k:
                (rem if ln.kind == "-" else add)[k] += 1
    return rem != add


_KEYWORDS = set(keyword.kwlist) | {
    "function", "const", "let", "var", "new", "this", "typeof", "instanceof", "export", "default", "extends",
    "switch", "case", "do", "throw", "catch", "finally", "void", "delete", "of", "static", "get", "set",
}
_LOCAL_TARGET_RE = re.compile(r"(?:^|[;,(]|\b(?:for|as|let|const|var))\s*([A-Za-z_$][\w$]*)\s*(?:=(?!=)|\bin\b|\bof\b|[,)])")


def _owners(texts: List[str], section: str) -> List[Optional[str]]:
    """Per line, the name of the innermost definition (def, class, function, const) it belongs to.

    By indentation: a definition owns the more-indented lines below it. A line above every
    definition in the hunk belongs to the hunk's section (git's funcname header) when indented.
    """
    sect = R.src_def_names(section)
    stack: List[Tuple[int, str]] = []
    out: List[Optional[str]] = []
    for t in texts:
        if not t.strip():
            out.append(stack[-1][1] if stack else None)
            continue
        ind = _indent(t)
        while stack and stack[-1][0] >= ind:
            stack.pop()
        names = R.src_def_names(t)
        if names:
            stack.append((ind, names[0]))
            out.append(names[0])
        elif stack:
            out.append(stack[-1][1])
        else:
            out.append(sect[0] if sect and ind > 0 else None)
    return out


def _canonical(lines: List[str], fw: Optional[str]) -> Tuple[str, ...]:
    """Tokens of a definition's lines with local names (parameters, assignment and loop
    targets) numbered by first use, so renaming a local gives the same tuple."""
    code = [R.strip_comment(t, fw) for t in lines]
    local: Set[str] = set()
    for c in code:
        if R.src_def_names(c):
            paren = c.find("(")
            if paren >= 0:
                local |= R.identifiers(R.strip_strings(c[paren:])) - _KEYWORDS
        for m in _LOCAL_TARGET_RE.finditer(R.strip_strings(c)):
            local.add(m.group(1))
    names: Dict[str, str] = {}
    out: List[str] = []
    for c in code:
        for tok in R.code_tokens(c):
            if tok in local:
                tok = names.setdefault(tok, "$%d" % len(names))
            out.append(tok)
    return tuple(out)


def _bare_string(text: str, fw: Optional[str]) -> bool:
    """A Python line that is only a string literal (a one-line docstring)."""
    return fw == R.PYTEST and set(R.strip_strings(R.strip_comment(text, fw)).strip()) <= set("\"'rRbBuUfF")


def _touched_defs(f: FileDiff) -> Set[str]:
    """Names of the definitions whose code (not comments, docstrings or whitespace) the change
    alters beyond renaming locals."""
    fw = R.PYTEST if f.path.lower().endswith(".py") else R.JEST if f.path.lower().endswith(R.JS_EXTS) else None
    touched: Set[str] = set()
    for h in f.hunks:
        old_idx, new_idx, _, _ = _sides(h)
        per_side = []
        for idx in (old_idx, new_idx):
            texts = R.blank_multiline([h.lines[i].text for i in idx], fw)
            owners = _owners(texts, h.section)
            groups: Dict[Optional[str], List[str]] = {}
            changed: Set[Optional[str]] = set()
            for i, t, o in zip(idx, texts, owners):
                if not _code_key(t, fw) or _bare_string(t, fw):
                    continue
                groups.setdefault(o, []).append(t)
                if h.lines[i].kind != " ":
                    changed.add(o)
            per_side.append((groups, changed))
        (og, oc), (ng, nc) = per_side
        for name in (oc | nc) - {None}:
            if _canonical(og.get(name, []), fw) != _canonical(ng.get(name, []), fw):
                touched.add(name)
    return touched


def _under_test(f: FileDiff, facts: _DiffFacts) -> List[str]:
    """Changed source files that this test file plausibly exercises."""
    text = "\n".join([h.section for h in f.hunks] + [ln.text for h in f.hunks for ln in h.lines])
    words = R.identifiers(text)
    return [p for p, stem, touched in facts.src_changes
            if (stem in words or R.test_file_targets(f.path, stem)) and touched & words]


def _replacement(h: Hunk, old_texts, new_texts, old_pos, new_pos, fw) -> Optional[Tuple[int, str]]:
    """(removed header index, new name) when the hunk removes exactly one test
    definition and adds exactly one, inside the same change block."""
    lines = h.lines
    removed = [i for i, ln in enumerate(lines) if ln.kind == "-" and R.def_name(old_texts, old_pos[i], fw)]
    added = [i for i, ln in enumerate(lines) if ln.kind == "+" and R.def_name(new_texts, new_pos[i], fw)]
    if len(removed) != 1 or len(added) != 1:
        return None
    lo, hi = sorted((removed[0], added[0]))
    if any(lines[k].kind == " " for k in range(lo, hi)):
        return None  # a context line between them: not the same place
    return removed[0], R.def_name(new_texts, new_pos[added[0]], fw) or ""


def _marked_def(texts: List[str], p: int, fw: Optional[str]) -> Optional[str]:
    """Name of the test a marker on texts[p] belongs to: the line itself (``it.skip('x'``),
    or the def under a decorator stack."""
    name = R.def_name(texts, p, fw)
    if name or fw != R.PYTEST or not texts[p].strip().startswith("@"):
        return name
    for q in range(p + 1, min(len(texts), p + 8)):
        name = R.def_name(texts, q, fw)
        if name:
            return name
        if not texts[q].strip().startswith(("@", ")")) and R.balance(R.code_part(texts[q - 1], fw)) <= 0:
            return None
    return None


def _indent(text: str) -> int:
    return len(text) - len(text.lstrip())


def _def_span(h: Hunk, i: int, fw: Optional[str]) -> List[int]:
    """Hunk indices of a removed test definition starting at removed line i."""
    lines = h.lines
    span = [i]
    j = i - 1
    while j >= 0 and lines[j].kind == "-" and lines[j].text.strip().startswith("@"):
        span.insert(0, j)
        j -= 1
    if fw == R.PYTEST:
        ind = _indent(lines[i].text)
        j = i + 1
        while j < len(lines):
            ln = lines[j]
            s = ln.text.strip()
            if ln.kind == " " and not s:
                j += 1
                continue
            if ln.kind != "-":
                break
            if s and _indent(ln.text) <= ind and not s.startswith(")"):
                break
            span.append(j)
            j += 1
    else:
        depth = R.balance(R.code_part(lines[i].text, fw))
        j = i + 1
        while depth > 0 and j < len(lines):
            ln = lines[j]
            if ln.kind == " " and not ln.text.strip():
                j += 1
                continue
            if ln.kind != "-":
                break
            span.append(j)
            depth += R.balance(R.code_part(ln.text, fw))
            j += 1
    return span


def _py_string_blocks(f: FileDiff) -> Dict[Tuple[int, int], Tuple[bool, Optional[str]]]:
    """(hunk, line) -> (inside an added triple-quoted block, text that block holds on the line).

    Only new-side lines are scanned, in order, so a delimiter opens and the next
    one closes it. The scan restarts at each hunk: the unchanged gap between hunks
    can hold delimiters the diff does not show (a docstring whose first line was
    edited closes in the gap), and carrying state over it would shift every pair. A block counts as "added" (code turned into a string)
    only when its opening and its closing delimiter are both on added lines and
    the opening starts a bare string statement. Any other triple-quoted string
    (a docstring, ``x = \"\"\"...``) maps its lines to (False, None): string
    content, never code. Lines outside every string are left out of the map.
    """
    regions: List[dict] = []
    state: Optional[str] = None
    cur: Optional[dict] = None
    for hi, h in enumerate(f.hunks):
        state, cur = None, None
        for li, ln in enumerate(h.lines):
            if ln.kind == "-":
                continue
            marks, state = R.triple_quotes(ln.text, state)
            start = 0
            for col, what in marks:
                if what == "close":
                    if cur is not None:
                        cur["segs"].append((hi, li, start, col))
                        cur["close_kind"] = ln.kind
                    cur = None
                else:
                    cur = {"open_kind": ln.kind, "bare": R.is_bare_string_start(ln.text, col),
                           "close_kind": None, "segs": []}
                    regions.append(cur)
                    start = col + 3
            if cur is not None:
                cur["segs"].append((hi, li, start, None))
    out: Dict[Tuple[int, int], Tuple[bool, Optional[str]]] = {}
    for r in regions:
        added = r["open_kind"] == "+" and r["close_kind"] == "+" and r["bare"]
        for hi, li, a, b in r["segs"]:
            if out.get((hi, li), (False, None))[0]:
                continue
            out[(hi, li)] = (True, f.hunks[hi].lines[li].text[a:b].strip()) if added else (False, None)
    return out


def _blocks(h: Hunk) -> List[Tuple[List[int], List[int]]]:
    """Change blocks of a hunk: (removed indices, added indices) per run of non-context lines."""
    out: List[Tuple[List[int], List[int]]] = []
    cur: Optional[Tuple[List[int], List[int]]] = None
    for i, ln in enumerate(h.lines):
        if ln.kind == " ":
            cur = None
            continue
        if cur is None:
            cur = ([], [])
            out.append(cur)
        (cur[0] if ln.kind == "-" else cur[1]).append(i)
    return out


def _next_code(texts: List[str], p: int, step: int) -> int:
    """Index of the next non-blank text from p in direction step, or -1."""
    while 0 <= p < len(texts):
        if texts[p].strip():
            return p
        p += step
    return -1


def _weakened(f, h, fw, old_ids, old_stmts, new_ids, new_stmts, new_idx, old_pos, new_pos, removed_norm, out) -> None:
    """assert-weakened: tautologies when added; weaker forms when they replace a stronger one.
    Not for a new file: there nothing was weakened (review 2: vitest fixtures and matcher self-tests)."""
    if f.is_new:
        return
    lines = h.lines
    new_texts = [lines[k].text for k in new_idx]
    hits: List[Tuple[int, str]] = []

    seen: Set[int] = set()
    for i, ln in enumerate(lines):
        if ln.kind != "+":
            continue
        sid = new_ids[new_pos[i]]
        if sid not in seen:
            seen.add(sid)
            why = R.weak_alone(new_stmts[sid], fw)
            if why:
                hits.append((i, why))
        p = new_pos[i]
        if R.is_bare_return(ln.text, fw):
            q = _next_code(new_texts, p - 1, -1)
            if q >= 0 and R.is_def_header(new_texts, q, fw):
                hits.append((i, "early return added as the first statement of a test"))
        elif R.is_if_false(ln.text, fw):
            q = _next_code(new_texts, p + 1, 1)
            if q >= 0 and R.assert_count(new_texts[q], fw):
                hits.append((i, "assertions wrapped in a branch that never runs"))
        elif fw == R.PYTEST:
            rest = R.except_assertion(ln.text)
            if rest is None:
                continue
            if rest:
                swallow = R.is_swallow(rest)
            else:
                q = _next_code(new_texts, p + 1, 1)
                swallow = q >= 0 and R.is_swallow(new_texts[q])
            if swallow and _try_wraps_moved_assert(lines, new_idx, new_texts, p, fw, removed_norm):
                hits.append((i, "assertion failure caught and ignored (except AssertionError)"))

    for rem, add in _blocks(h):
        if not rem or not add:
            continue
        real_removed = any(R.assert_count(lines[k].text, fw) and not R.is_noop_assert(lines[k].text, fw) for k in rem)
        for k in add:
            if real_removed and R.is_noop_assert(lines[k].text, fw):
                hits.append((k, "a real assertion replaced by an always-true one"))
        first_line: Dict[int, int] = {}
        for k in add:
            first_line.setdefault(new_ids[new_pos[k]], k)
        old_s = _unique([old_ids[old_pos[k]] for k in rem])
        old_sub = {x: R.subject(old_stmts[x], fw) for x in old_s}
        new_sub = {x: R.subject(new_stmts[x], fw) for x in first_line}
        old_a = [x for x in old_s if old_sub[x] or R.assert_count(old_stmts[x], fw)]
        new_a = [x for x in first_line if new_sub[x] or R.assert_count(new_stmts[x], fw)]
        by_sub: Dict[str, List[int]] = {}
        for x in reversed(old_a):
            if old_sub[x]:
                by_sub.setdefault(old_sub[x], []).append(x)  # popped from the end: first one first
        for ns in new_a:
            cands = by_sub.get(new_sub[ns] or "")
            match = cands.pop() if cands else None
            if match is None and len(old_a) == 1 and len(new_a) == 1:
                match = old_a[0]
            if match is None:
                continue
            why = R.weak_pair(old_stmts[match], new_stmts[ns], fw)
            if why:
                hits.append((first_line[ns], why))

    for i, why in hits:
        out.append(Finding("assert-weakened", R.MEDIUM, f.path, lines[i].new_no or 1, why, _evidence(lines[i].text)))


def _unique(xs: List[int]) -> List[int]:
    seen: Set[int] = set()
    return [x for x in xs if not (x in seen or seen.add(x))]


def _try_wraps_moved_assert(lines, new_idx, new_texts, p, fw, removed_norm) -> bool:
    """The ``try:`` block above new-side line p holds an added assert that the diff removed elsewhere."""
    ind = _indent(new_texts[p])
    q = p - 1
    while q >= 0 and p - q <= 40:
        t = new_texts[q]
        if t.strip() and _indent(t) <= ind:
            if R.code_part(t, fw).strip() != "try:" or _indent(t) != ind:
                return False
            break
        q -= 1
    else:
        return False
    for r in range(q + 1, p):
        ln = lines[new_idx[r]]
        if ln.kind == "+" and R.norm(ln.text) in removed_norm and R.assert_count(ln.text, fw):
            return True
    return False


_GATE_KINDS = ("pytest.mark.skipif", "unittest.skipIf", "unittest.skipUnless")


def _line_above(lines, i: int) -> Optional[str]:
    """The new-side line just above hunk line i when the diff adds it, else None. A context
    line was already there, so an issue link on it does not vouch for the new marker."""
    j = i - 1
    while j >= 0 and lines[j].kind == "-":
        j -= 1
    return lines[j].text if j >= 0 and lines[j].kind == "+" else None


def _analyze_test_file(raw: FileDiff, fw: Optional[str], facts: _DiffFacts, out: List[Finding],
                       view: Optional[Tuple[FileDiff, _Sides]] = None) -> None:
    """Rules on one test file. They read the code view (multi-line strings and comments
    blanked); test-commented-out reads the raw lines, since it looks for code put in comments."""
    f, sides = view if view is not None else _code_view(raw, fw)
    path = f.path
    removed_defs: List[_RemovedDef] = []
    removed_asserts: List[Tuple[int, str]] = []  # (old_no, text) outside deleted defs
    added_asserts = 0
    noop_lines: List[Tuple[int, str]] = []
    removed_norm = {R.norm(ln.text) for h in raw.hunks for ln in h.lines if ln.kind == "-" and ln.text.strip()}

    py_blocks = _py_string_blocks(raw) if fw == R.PYTEST else {}
    under_test: Optional[List[str]] = None

    for hi, h in enumerate(f.hunks):
        lines = h.lines
        old_idx, new_idx, old_pos, new_pos = _sides(h)
        old_texts, new_texts, old_values, new_values = sides[hi]
        pairs = _pairs(h)
        excluded: Set[int] = set()

        # test-deleted: removed test definitions in this hunk.
        replaced = _replacement(h, old_texts, new_texts, old_pos, new_pos, fw)
        for i, ln in enumerate(lines):
            if ln.kind != "-":
                continue
            name = R.def_name(old_texts, old_pos[i], fw)
            if not name:
                continue
            span = _def_span(h, i, fw)
            partner = pairs.get(i)
            renamed = partner is not None and R.def_name(new_texts, new_pos[partner], fw) is not None and all(
                k in pairs or not lines[k].text.strip() for k in span
            )
            if renamed:
                continue
            if replaced is not None and replaced[0] == i:
                # Renamed and rewritten in place: its asserts stay in the assert-removed count.
                removed_defs.append(_RemovedDef(name, ln.old_no or 1, ln.text, "", replaced[1]))
                continue
            excluded.update(span)
            body = "\n".join(lines[k].text for k in span)
            removed_defs.append(_RemovedDef(name, ln.old_no or 1, ln.text, body))

        # test-deleted (medium): one case of a parametrize / .each table removed, nothing in its place.
        old_removed = [lines[k].kind == "-" for k in old_idx]
        replaced_rows = {k for rem, add in _blocks(h) if any(R.is_table_row(R.code_part(lines[a].text, fw)) for a in add)
                         for k in rem}
        table_ctx: Optional[R.TableContext] = None
        for i, ln in enumerate(lines):
            if ln.kind != "-" or i in excluded or i in pairs or i in replaced_rows:
                continue
            if not R.is_table_row(R.code_part(ln.text, fw)):
                continue
            if table_ctx is None:
                table_ctx = R.TableContext(old_texts, fw, old_removed)
            if table_ctx(old_pos[i]):
                out.append(Finding("test-deleted", R.MEDIUM, path, ln.old_no or 1,
                                   "parametrized case removed: %s" % _evidence(ln.text), _evidence(ln.text)))

        # assert-removed: counts outside deleted test definitions.
        for i, ln in enumerate(lines):
            if ln.kind == "-":
                if i not in excluded:
                    removed_asserts.extend([(ln.old_no or 1, ln.text)] * R.assert_count(ln.text, fw))
            elif ln.kind == "+":
                if R.is_noop_assert(ln.text, fw):
                    noop_lines.append((ln.new_no or 1, ln.text))
                else:
                    added_asserts += R.assert_count(ln.text, fw)

        # skip-added
        diff_text: Optional[str] = None  # every line of this file's diff, for the env-gate check
        for i, ln in enumerate(lines):
            if ln.kind != "+":
                continue
            for kind in R.skip_markers(ln.text, fw):
                if facts.removed_markers[(path, kind)] > 0:
                    facts.removed_markers[(path, kind)] -= 1
                    continue
                name = _marked_def(new_texts, new_pos[i], fw)
                if name and facts.moved_markers[(name, kind)] > 0:
                    facts.moved_markers[(name, kind)] -= 1
                    continue
                ctx = ln.text
                code = R.code_part(ln.text, fw)
                gate_text = R.strip_comment(ln.text, fw)  # strings kept: the env-gate check reads them
                depth = R.balance(code)
                k = i + 1
                while depth > 0 and k < len(lines) and k <= i + 3 and lines[k].kind == "+":
                    ctx += " " + lines[k].text
                    code += " " + R.code_part(lines[k].text, fw)
                    gate_text += " " + R.strip_comment(lines[k].text, fw)
                    depth += R.balance(R.code_part(lines[k].text, fw))
                    k += 1
                above = _line_above(lines, i)
                if above is not None and R.uncomment(above, fw) is not None:
                    ctx = above + " " + ctx  # a comment directly above the marker
                linked = R.ISSUE_RE.search(ctx) is not None
                if diff_text is None:
                    diff_text = "\n".join(x.text for h in raw.hunks for x in h.lines)
                gate = not linked and kind in _GATE_KINDS and R.is_env_gate(gate_text, diff_text)
                what = "focus marker %s (silences every other test)" % kind if R.is_focus(kind) else "skip marker %s" % kind
                if linked:
                    msg = "added %s with a linked issue" % what
                elif gate:
                    msg = "added %s gated on the Python version / platform / an optional dependency" % what
                else:
                    msg = "added %s without a linked issue" % what
                sev = R.LOW if linked or gate else R.HIGH
                out.append(Finding("skip-added", sev, path, ln.new_no or 1, msg, _evidence(ln.text)))
                break

        # tolerance-loosened / expected-changed on paired statements.
        old_ids, old_stmts = R.statements(old_texts, fw)
        new_ids, new_stmts = R.statements(new_texts, fw)
        # Values are compared with template literals kept: an inline snapshot is an expected value.
        if old_values is old_texts and new_values is new_texts:
            old_vids, old_vstmts, new_vids, new_vstmts = old_ids, old_stmts, new_ids, new_stmts
        else:
            old_vids, old_vstmts = R.statements(old_values, fw)
            new_vids, new_vstmts = R.statements(new_values, fw)
        seen: Set[Tuple[int, int]] = set()
        for ri in sorted(pairs):
            ai = pairs[ri]
            key = (old_vids[old_pos[ri]], new_vids[new_pos[ai]])
            if key in seen:
                continue
            seen.add(key)
            old_t, new_t = old_vstmts[key[0]], new_vstmts[key[1]]
            loosened, changed, reason = R.compare_tolerance(old_t, new_t)
            line_no = lines[ai].new_no or 1
            if loosened:
                out.append(Finding("tolerance-loosened", R.HIGH, path, line_no, reason, _evidence(lines[ai].text)))
                continue
            if changed:
                continue
            if not (R.ASSERT_CTX_RE.search(R.strip_strings(old_t)) or R.ASSERT_CTX_RE.search(R.strip_strings(new_t))):
                continue
            lc = R.literal_change(old_t, new_t)
            if lc is None:
                continue
            if under_test is None:
                under_test = _under_test(f, facts)
            sev = R.LOW if under_test else R.MEDIUM
            msg = "expected value changed from %r to %r with the assertion otherwise unchanged" % lc
            if under_test:
                msg += " (the diff also changes %s, which this test uses)" % ", ".join(under_test[:3])
            out.append(Finding("expected-changed", sev, path, line_no, msg, _evidence(lines[ai].text)))

        _weakened(f, h, fw, old_ids, old_stmts, new_ids, new_stmts, new_idx, old_pos, new_pos, removed_norm, out)

        # test-commented-out
        in_block = False
        group_open = False
        for li, ln in enumerate(raw.hunks[hi].lines):
            hit = False
            s = ln.text.strip()
            if fw == R.PYTEST:
                in_block, inner = py_blocks.get((hi, li), (False, None))
                if ln.kind == "+" and inner is None and (hi, li) not in py_blocks:
                    inner = R.uncomment(ln.text, fw)
                if ln.kind == "+":
                    if inner and R.norm(inner) in removed_norm and R.is_test_like(inner, fw):
                        hit = True
                elif ln.kind == " " and in_block and R.is_test_like(s, fw):
                    hit = True  # an existing line wrapped in an added triple-quoted string
            elif ln.kind == "+":
                inner = None
                if in_block:
                    inner = s
                    if "*/" in s:
                        inner = s.split("*/", 1)[0]
                        in_block = False
                elif s.startswith("/*"):
                    rest = s[2:]
                    if "*/" in rest:
                        inner = rest.split("*/", 1)[0]
                    else:
                        inner = rest
                        in_block = True
                else:
                    inner = R.uncomment(ln.text, fw)
                if inner and R.norm(inner) in removed_norm and R.is_test_like(inner, fw):
                    hit = True
            elif fw == R.JEST and ln.kind == " " and in_block and R.is_test_like(s, fw):
                hit = True  # an existing line wrapped in an added block comment
            if hit and not group_open:
                out.append(Finding(
                    "test-commented-out", R.HIGH, path, ln.new_no or 1,
                    "test code commented out instead of fixed", _evidence(ln.text),
                ))
            if ln.kind == "-":
                continue
            group_open = hit or (group_open and ln.kind == "+" and not s)

    # test-deleted findings
    gone = [d for d in removed_defs if d.name not in facts.added_def_names]
    really_removed = facts.removed_src_defs - facts.added_src_defs
    if f.is_deleted:
        if gone or (not removed_defs and R.is_test_module(path)):
            body = "\n".join(ln.text for h in f.hunks for ln in h.lines if ln.kind == "-")
            names = ", ".join(d.name for d in gone[:5]) + (", ..." if len(gone) > 5 else "")
            msg = "test file deleted" + (" (%d test(s) not re-added: %s)" % (len(gone), names) if gone else "")
            first = gone[0] if gone else None
            out.append(_deleted_finding(path, first.old_no if first else 1, msg,
                                        first.evidence if first else path, body, really_removed))
    else:
        for d in gone:
            if d.replaced_by is not None:
                out.append(Finding("test-deleted", R.LOW, path, d.old_no,
                                   "test %r replaced in the same place by %r (renamed or rewritten)" % (d.name, d.replaced_by),
                                   _evidence(d.evidence)))
                continue
            out.append(_deleted_finding(path, d.old_no, "test %r removed and not re-added anywhere in the diff" % d.name,
                                        d.evidence, d.body, really_removed))

    # assert-removed finding (not for deleted files: test-deleted covers them)
    if not f.is_deleted and len(removed_asserts) > added_asserts:
        lost = len(removed_asserts) - added_asserts
        if noop_lines:
            line_no, ev = noop_lines[0]
            msg = "assertion replaced by a no-op (%d removed, %d real added)" % (len(removed_asserts), added_asserts)
        else:
            line_no, ev = removed_asserts[0]
            msg = "%d assertion(s) removed, %d added (net loss %d)" % (len(removed_asserts), added_asserts, lost)
        out.append(Finding("assert-removed", R.MEDIUM, path, line_no, msg, _evidence(ev)))


def _side(h: Hunk, keep: str) -> Tuple[List[int], List[str]]:
    """Hunk indices and texts of one side: keep '-' for old, '+' for new."""
    idx = [i for i, ln in enumerate(h.lines) if ln.kind in (" ", keep)]
    return idx, [h.lines[i].text for i in idx]


def _analyze_config_file(f: FileDiff, kind: str, out: List[Finding]) -> None:
    """test-config-weakened: runner config that stops tests from being collected or failing."""
    hits: List[Tuple[int, str, str]] = []  # (new line, message, evidence)
    removed_opts: Counter = Counter()
    added_opts: List[Tuple[int, str, str]] = []
    removed_entries: Set[str] = set()
    removed_script_weak = False
    for h in f.hunks:
        if kind == "pytest-cfg":
            for keep in "-+":
                idx, texts = _side(h, keep)
                for i, inside in zip(idx, R.addopts_lines(texts)):
                    ln = h.lines[i]
                    if not inside or ln.kind != keep:
                        continue
                    for opt in R.drop_opts(ln.text):
                        if keep == "-":
                            removed_opts[opt] += 1
                        else:
                            added_opts.append((ln.new_no or 1, opt, ln.text))
        elif kind == "conftest":
            idx, texts = _side(h, "+")
            for p, i in enumerate(idx):
                ln = h.lines[i]
                if ln.kind != "+":
                    continue
                if R.COLLECT_IGNORE_RE.match(R.code_part(ln.text, R.PYTEST)):
                    hits.append((ln.new_no or 1, "collect_ignore added: test files are no longer collected", ln.text))
                elif R.DESELECT_RE.search(R.code_part(ln.text, R.PYTEST)) and _in_func(texts, p, "pytest_collection_modifyitems"):
                    hits.append((ln.new_no or 1, "pytest_collection_modifyitems now drops collected tests", ln.text))
        else:
            for keep in "-+":
                idx, texts = _side(h, keep)
                for i, entries in zip(idx, R.jest_ignore_entries(texts)):
                    ln = h.lines[i]
                    if ln.kind != keep:
                        continue
                    if keep == "-":
                        removed_entries.update(entries)
                    else:
                        added_opts.extend((ln.new_no or 1, e, ln.text) for e in entries)
                    m = R.TEST_SCRIPT_RE.match(ln.text) if kind == "package" else None
                    if m and R.SCRIPT_WEAK_RE.search(m.group(1)):
                        if keep == "-":
                            removed_script_weak = True
                        else:
                            hits.append((ln.new_no or 1, "the test script can no longer fail (|| true / --passWithNoTests)",
                                         ln.text))
    if kind == "pytest-cfg":
        for line, opt, text in added_opts:
            if removed_opts[opt] > 0:
                removed_opts[opt] -= 1
                continue
            hits.append((line, "pytest addopts now passes %s, which drops tests from the run" % opt, text))
    elif kind in ("jest", "package"):
        for line, entry, text in added_opts:
            if entry not in removed_entries:
                hits.append((line, "jest now ignores %r: matching tests are no longer run" % entry, text))
        if removed_script_weak:
            hits = [x for x in hits if "test script" not in x[1]]
    for line, msg, text in hits:
        out.append(Finding("test-config-weakened", R.HIGH, f.path, line, msg, _evidence(text)))


def _in_func(texts: List[str], p: int, name: str) -> bool:
    """texts[p] sits inside ``def name(...)`` (the nearest less-indented def above it)."""
    ind = _indent(texts[p])
    for q in range(p - 1, -1, -1):
        m = R.PY_FUNC_RE.match(texts[q])
        if m and len(m.group(1)) < ind:
            return m.group(2) == name
    return False


def _deleted_finding(path, line, msg, evidence, body, really_removed) -> Finding:
    hit = sorted(R.identifiers(body) & really_removed)
    if hit:
        return Finding("test-deleted", R.LOW, path, line,
                       msg + "; the diff also removes %s from non-test code (feature removal?)" % ", ".join(hit[:3]),
                       _evidence(evidence))
    return Finding("test-deleted", R.HIGH, path, line, msg, _evidence(evidence))


def analyze_diff(diff_text: str, config: Optional[Config] = None) -> List[Finding]:
    """Return the findings for a unified diff. Pure function, no I/O."""
    cfg = config or Config()
    files = []
    for f in parse_diff(diff_text):
        if f.is_binary or not f.path:
            continue
        fw, is_test = R.framework_for(f.path), R.is_test_file(f.path, cfg.test_dirs)
        files.append((f, fw, is_test, _code_view(f, fw) if is_test and fw is not None else None))
    facts = _collect_facts(files)
    out: List[Finding] = []
    for f, fw, is_test, view in files:
        if is_test and fw is not None:
            _analyze_test_file(f, fw, facts, out, view)
        kind = R.config_kind(f.path)
        if kind is not None:
            _analyze_config_file(f, kind, out)
    uniq = {(x.rule, x.path, x.line): x for x in out}
    return sorted(uniq.values(), key=lambda x: (x.path, x.line, -SEVERITY_RANK[x.severity], x.rule))
