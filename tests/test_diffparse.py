"""Unit tests for the unified / git diff parser."""

from test_tamper_guard.diffparse import MAX_LINE_LENGTH, parse_diff

MODIFY = """\
diff --git a/tests/test_calc.py b/tests/test_calc.py
index 1111111..2222222 100644
--- a/tests/test_calc.py
+++ b/tests/test_calc.py
@@ -1,4 +1,4 @@ import calc
 def test_add():
-    assert calc.add(1, 2) == 3
+    assert calc.add(1, 2) == 4
     assert calc.add(0, 0) == 0
 
"""


def test_modified_file_paths_have_prefixes_stripped():
    (f,) = parse_diff(MODIFY)
    assert (f.old_path, f.new_path, f.path) == ("tests/test_calc.py", "tests/test_calc.py", "tests/test_calc.py")


def test_hunk_header_numbers_are_parsed():
    (f,) = parse_diff(MODIFY)
    (h,) = f.hunks
    assert (h.old_start, h.old_len, h.new_start, h.new_len) == (1, 4, 1, 4)


def test_removed_line_carries_old_line_number():
    (f,) = parse_diff(MODIFY)
    removed = [ln for ln in f.hunks[0].lines if ln.kind == "-"]
    assert [(ln.old_no, ln.new_no, ln.text) for ln in removed] == [(2, None, "    assert calc.add(1, 2) == 3")]


def test_added_line_carries_new_line_number():
    (f,) = parse_diff(MODIFY)
    added = [ln for ln in f.hunks[0].lines if ln.kind == "+"]
    assert [(ln.old_no, ln.new_no) for ln in added] == [(None, 2)]


def test_context_line_carries_both_line_numbers():
    (f,) = parse_diff(MODIFY)
    ctx = [ln for ln in f.hunks[0].lines if ln.kind == " "]
    assert [(ln.old_no, ln.new_no) for ln in ctx] == [(1, 1), (3, 3), (4, 4)]


def test_added_file_is_marked_new_with_dev_null_old_path():
    diff = (
        "diff --git a/tests/test_new.py b/tests/test_new.py\n"
        "new file mode 100644\n"
        "index 0000000..3333333\n"
        "--- /dev/null\n"
        "+++ b/tests/test_new.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def test_x():\n"
        "+    assert True\n"
    )
    (f,) = parse_diff(diff)
    assert (f.is_new, f.is_deleted, f.old_path, f.path) == (True, False, None, "tests/test_new.py")


def test_deleted_file_is_marked_deleted_and_keeps_old_path():
    diff = (
        "diff --git a/tests/test_old.py b/tests/test_old.py\n"
        "deleted file mode 100644\n"
        "index 3333333..0000000\n"
        "--- a/tests/test_old.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-def test_x():\n"
        "-    assert 1 == 1\n"
    )
    (f,) = parse_diff(diff)
    assert (f.is_deleted, f.new_path, f.path, len(f.hunks[0].lines)) == (True, None, "tests/test_old.py", 2)


def test_rename_without_content_change_records_both_paths():
    diff = (
        "diff --git a/tests/test_a.py b/tests/test_b.py\n"
        "similarity index 100%\n"
        "rename from tests/test_a.py\n"
        "rename to tests/test_b.py\n"
    )
    (f,) = parse_diff(diff)
    assert (f.is_rename, f.old_path, f.new_path, f.hunks) == (True, "tests/test_a.py", "tests/test_b.py", [])


def test_quoted_paths_are_unescaped():
    diff = (
        'diff --git "a/tests/test \\303\\251t\\303\\251.py" "b/tests/test \\303\\251t\\303\\251.py"\n'
        "index 1..2 100644\n"
        '--- "a/tests/test \\303\\251t\\303\\251.py"\n'
        '+++ "b/tests/test \\303\\251t\\303\\251.py"\n'
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
    )
    (f,) = parse_diff(diff)
    assert f.path == "tests/test été.py"


def test_quoted_path_with_tab_escape_is_unescaped():
    diff = (
        'diff --git "a/x\\ty.py" "b/x\\ty.py"\n'
        'deleted file mode 100644\n'
        "Binary files \"a/x\\ty.py\" and /dev/null differ\n"
    )
    (f,) = parse_diff(diff)
    assert f.old_path == "x\ty.py"


def test_path_with_spaces_and_trailing_tab_is_parsed():
    diff = (
        "diff --git a/tests/my test.py b/tests/my test.py\n"
        "--- a/tests/my test.py\t\n"
        "+++ b/tests/my test.py\t\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
    )
    (f,) = parse_diff(diff)
    assert f.path == "tests/my test.py"


def test_binary_file_is_marked_binary_with_no_hunks():
    diff = (
        "diff --git a/img.png b/img.png\n"
        "index 1..2 100644\n"
        "Binary files a/img.png and b/img.png differ\n"
        "diff --git a/tests/test_a.py b/tests/test_a.py\n"
        "--- a/tests/test_a.py\n"
        "+++ b/tests/test_a.py\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
    )
    files = parse_diff(diff)
    assert [(f.path, f.is_binary, len(f.hunks)) for f in files] == [("img.png", True, 0), ("tests/test_a.py", False, 1)]


def test_no_newline_marker_is_not_a_content_line():
    diff = (
        "--- a/t.py\n"
        "+++ b/t.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "\\ No newline at end of file\n"
        "+new\n"
        "\\ No newline at end of file\n"
    )
    (f,) = parse_diff(diff)
    assert [(ln.kind, ln.text) for ln in f.hunks[0].lines] == [("-", "old"), ("+", "new")]


def test_plain_unified_diff_without_git_header_is_parsed():
    diff = (
        "--- tests/test_a.py\t2024-01-01 00:00:00\n"
        "+++ tests/test_a.py\t2024-01-02 00:00:00\n"
        "@@ -1,2 +1,1 @@\n"
        " x\n"
        "-y\n"
    )
    (f,) = parse_diff(diff)
    assert (f.path, [ln.kind for ln in f.hunks[0].lines]) == ("tests/test_a.py", [" ", "-"])


def test_removed_line_starting_with_dashes_stays_inside_the_hunk():
    diff = (
        "--- a/t.py\n"
        "+++ b/t.py\n"
        "@@ -1,2 +1,1 @@\n"
        "--- not a header\n"
        " keep\n"
    )
    (f,) = parse_diff(diff)
    assert [(ln.kind, ln.text) for ln in f.hunks[0].lines] == [("-", "-- not a header"), (" ", "keep")]


def test_multiple_files_and_hunks_are_split():
    diff = MODIFY + (
        "diff --git a/src/calc.py b/src/calc.py\n"
        "--- a/src/calc.py\n"
        "+++ b/src/calc.py\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
        "@@ -10 +10 @@\n"
        "-c\n"
        "+d\n"
    )
    files = parse_diff(diff)
    assert [(f.path, len(f.hunks)) for f in files] == [("tests/test_calc.py", 1), ("src/calc.py", 2)]


def test_hunk_header_without_counts_defaults_to_one():
    diff = "--- a/t.py\n+++ b/t.py\n@@ -5 +5 @@\n-a\n+b\n"
    (f,) = parse_diff(diff)
    h = f.hunks[0]
    assert (h.old_start, h.old_len, h.new_start, h.new_len) == (5, 1, 5, 1)


def test_overlong_line_is_truncated():
    diff = "--- a/t.py\n+++ b/t.py\n@@ -1 +1 @@\n-a\n+" + "x" * 20000 + "\n"
    (f,) = parse_diff(diff)
    assert len(f.hunks[0].lines[1].text) == MAX_LINE_LENGTH


def test_crlf_line_endings_are_accepted():
    diff = MODIFY.replace("\n", "\r\n")
    (f,) = parse_diff(diff)
    assert f.hunks[0].lines[1].text == "    assert calc.add(1, 2) == 3"


def test_malformed_hunk_header_is_skipped_without_crashing():
    diff = "--- a/t.py\n+++ b/t.py\n@@ garbage @@\n-a\n+b\n"
    (f,) = parse_diff(diff)
    assert f.hunks == []


def test_empty_input_gives_no_files():
    assert parse_diff("") == []


def test_rename_lines_resolve_a_header_made_ambiguous_by_spaces():
    diff = (
        "diff --git a/x b/old.py b/new.py\n"
        "similarity index 100%\n"
        "rename from x b/old.py\n"
        "rename to new.py\n"
    )
    (f,) = parse_diff(diff)
    assert (f.old_path, f.new_path) == ("x b/old.py", "new.py")
