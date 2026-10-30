"""Parse unified / git diffs into files -> hunks -> lines.

The input is untrusted. The parser never raises on malformed input: a line it
cannot place is ignored, and a hunk header it cannot read is skipped.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Lines longer than this are cut before any rule sees them.
MAX_LINE_LENGTH = 10000

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}


@dataclass
class Line:
    kind: str  # " " context, "-" removed, "+" added
    text: str
    old_no: Optional[int]
    new_no: Optional[int]


@dataclass
class Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    section: str = ""
    lines: List[Line] = field(default_factory=list)


@dataclass
class FileDiff:
    old_path: Optional[str] = None
    new_path: Optional[str] = None
    is_new: bool = False
    is_deleted: bool = False
    is_rename: bool = False
    is_binary: bool = False
    hunks: List[Hunk] = field(default_factory=list)
    # Set once a "---" line was read for this file (plain-diff file boundary).
    _seen_minus: bool = field(default=False, repr=False, compare=False)

    @property
    def path(self) -> str:
        return self.new_path or self.old_path or ""


def _unquote(s: str) -> Tuple[str, str]:
    """Read a C-style quoted string at the start of ``s``; return (value, rest)."""
    out = bytearray()
    i = 1
    n = len(s)
    while i < n:
        c = s[i]
        if c == '"':
            return out.decode("utf-8", "replace"), s[i + 1:]
        if c == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt in "01234567":
                j = i + 1
                while j < n and j < i + 4 and s[j] in "01234567":
                    j += 1
                out.append(int(s[i + 1:j], 8) & 0xFF)
                i = j
                continue
            out.append(_ESCAPES.get(nxt, ord(nxt) if ord(nxt) < 128 else 63))
            i += 2
            continue
        out.extend(c.encode("utf-8"))
        i += 1
    return out.decode("utf-8", "replace"), ""


def _strip_prefix(path: str, prefix: str) -> str:
    return path[len(prefix):] if path.startswith(prefix) else path


def _marker_path(raw: str, prefix: str) -> Optional[str]:
    """Path from a ``---`` / ``+++`` line body. None for /dev/null."""
    if raw.startswith('"'):
        path = _unquote(raw)[0]
    else:
        path = raw.split("\t", 1)[0].rstrip(" ")
    if path == "/dev/null":
        return None
    return _strip_prefix(path, prefix)


def _git_header_paths(rest: str) -> Tuple[Optional[str], Optional[str]]:
    """Paths from ``diff --git <a> <b>``; (None, None) if unreadable."""
    if rest.startswith('"'):
        a, tail = _unquote(rest)
        tail = tail.lstrip(" ")
        b = _unquote(tail)[0] if tail.startswith('"') else tail
    elif rest.endswith('"') and ' "' in rest:
        idx = rest.rfind(' "')
        a, b = rest[:idx], _unquote(rest[idx + 1:])[0]
    else:
        # Unquoted: ambiguous when the path holds " b/". Prefer the split
        # that gives the same path on both sides (no rename).
        cands = [m.start() for m in re.finditer(r" b/", rest)]
        if not cands:
            parts = rest.split(" ", 1)
            if len(parts) != 2:
                return None, None
            return parts[0], parts[1]
        pick = cands[0]
        for c in cands:
            if _strip_prefix(rest[:c], "a/") == rest[c + 3:]:
                pick = c
                break
        a, b = rest[:pick], rest[pick + 1:]
    return _strip_prefix(a, "a/"), _strip_prefix(b, "b/")


def parse_diff(text: str) -> List[FileDiff]:
    files: List[FileDiff] = []
    cur: Optional[FileDiff] = None
    hunk: Optional[Hunk] = None
    rem_old = rem_new = 0
    old_no = new_no = 0
    lines = text.split("\n")
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        i += 1
        if line.endswith("\r"):
            line = line[:-1]

        if hunk is not None and (rem_old > 0 or rem_new > 0):
            tag = line[:1]
            body = line[1:]
            if len(body) > MAX_LINE_LENGTH:
                body = body[:MAX_LINE_LENGTH]
            if tag == " " or line == "":
                hunk.lines.append(Line(" ", body, old_no, new_no))
                old_no += 1
                new_no += 1
                rem_old -= 1
                rem_new -= 1
                continue
            if tag == "-" and rem_old > 0:
                hunk.lines.append(Line("-", body, old_no, None))
                old_no += 1
                rem_old -= 1
                continue
            if tag == "+" and rem_new > 0:
                hunk.lines.append(Line("+", body, None, new_no))
                new_no += 1
                rem_new -= 1
                continue
            if tag == "\\":
                continue
            # Counts did not add up: leave the hunk, treat as a header line.
            hunk = None
            rem_old = rem_new = 0

        if line.startswith("\\"):
            continue

        if line.startswith("diff --git "):
            cur = FileDiff()
            files.append(cur)
            hunk = None
            a, b = _git_header_paths(line[len("diff --git "):])
            cur.old_path, cur.new_path = a, b
            continue

        if line.startswith("--- ") and i < n and lines[i].startswith("+++ "):
            if cur is None or cur.hunks or cur._seen_minus:
                cur = FileDiff()
                files.append(cur)
            hunk = None
            cur._seen_minus = True
            cur.old_path = _marker_path(line[4:].rstrip("\r"), "a/")
            plus = lines[i].rstrip("\r")
            i += 1
            cur.new_path = _marker_path(plus[4:], "b/")
            if cur.old_path is None:
                cur.is_new = True
            if cur.new_path is None:
                cur.is_deleted = True
            continue

        if cur is None:
            continue

        if line.startswith("@@"):
            m = _HUNK_RE.match(line)
            if not m:
                hunk = None
                continue
            os_, ol, ns, nl, section = m.groups()
            hunk = Hunk(
                int(os_), 1 if ol is None else int(ol),
                int(ns), 1 if nl is None else int(nl),
                section.strip(),
            )
            cur.hunks.append(hunk)
            rem_old, rem_new = hunk.old_len, hunk.new_len
            old_no, new_no = hunk.old_start, hunk.new_start
            continue

        if line.startswith("new file mode"):
            cur.is_new = True
            cur.old_path = None
        elif line.startswith("deleted file mode"):
            cur.is_deleted = True
            cur.new_path = None
        elif line.startswith("rename from "):
            cur.is_rename = True
            cur.old_path = _marker_path(line[len("rename from "):], "")
        elif line.startswith("rename to "):
            cur.is_rename = True
            cur.new_path = _marker_path(line[len("rename to "):], "")
        elif line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            cur.is_binary = True
    return files
