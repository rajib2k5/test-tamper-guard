"""Build unified diffs for tests from before/after text (input construction only)."""

import difflib
import textwrap


def _lines(text):
    return textwrap.dedent(text).lstrip("\n").splitlines(keepends=True)


def modify(path, before, after, n=3):
    body = "".join(difflib.unified_diff(_lines(before), _lines(after), "a/" + path, "b/" + path, n=n))
    return "diff --git a/%s b/%s\n%s" % (path, path, body)


def add_file(path, content):
    lines = _lines(content)
    out = ["diff --git a/%s b/%s\n" % (path, path), "new file mode 100644\n",
           "--- /dev/null\n", "+++ b/%s\n" % path, "@@ -0,0 +1,%d @@\n" % len(lines)]
    out += ["+" + ln for ln in lines]
    return "".join(out)


def delete_file(path, content):
    lines = _lines(content)
    out = ["diff --git a/%s b/%s\n" % (path, path), "deleted file mode 100644\n",
           "--- a/%s\n" % path, "+++ /dev/null\n", "@@ -1,%d +0,0 @@\n" % len(lines)]
    out += ["-" + ln for ln in lines]
    return "".join(out)
