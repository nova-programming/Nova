r"""text.words / lines / padLeft / padRight / count / capitalize in every pipeline.

The Nova program is a raw string so backslash escapes reach the Nova lexer unchanged.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_names import _vm_output, _native_output  # noqa: E402

PROGRAM = r'''import text
w = text.words("  alpha   beta\tgamma \n")
print(len(w))
print(w[0] + "|" + w[1] + "|" + w[2])
l = text.lines("one\r\ntwo\n\nfour")
print(len(l))
print(l[0] + "," + l[1] + "," + l[3])
print(len(text.lines("tail\n")))
print("[" + text.padLeft("7", 3, "0") + "]")
print("[" + text.padRight("ab", 5, "*") + "]")
print("[" + text.padLeft("toolong", 3, " ") + "]")
print(text.count("banana", "an"))
print(text.count("aaaa", "aa"))
print(text.count("abc", ""))
print(text.capitalize("hELLO wORLD"))
'''
EXPECTED = ["3", "alpha|beta|gamma", "4", "one,two,four", "1", "[007]", "[ab***]", "[toolong]",
            "2", "2", "0", "Hello", "world"]


def test_text_helpers_all_pipelines(tmp_path, selfhost_run):
    assert _vm_output(PROGRAM).split() == EXPECTED
    assert _native_output(PROGRAM, tmp_path).split() == EXPECTED
    r, _ = selfhost_run(PROGRAM, "text_more")
    assert r.returncode == 0 and r.stdout.split() == EXPECTED
