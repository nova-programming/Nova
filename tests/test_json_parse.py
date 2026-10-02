"""json.parse: a typed tree written in plain Nova, identical in the VM, Python-native and self-hosted builds."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_names import _vm_output, _native_output  # noqa: E402

# JSON text is assembled from pieces because a string literal containing {...} is interpolated.
PRELUDE = 'import json\nlb = "{"\nrb = "}"\nq = "\\""\n'

PROGRAM = PRELUDE + (
    'doc = json.parse(lb + q + "name" + q + ": " + q + "Ada" + q + ", " + q + "age" + q + ": 36, "'
    ' + q + "tags" + q + ": [" + q + "a" + q + ", " + q + "b" + q + ", true, null], "'
    ' + q + "nested" + q + ": " + lb + q + "x" + q + ": -5" + rb + rb)\n'
    "print(json.kind(doc))\n"
    'print(json.asString(json.get(doc, "name")))\n'
    'print(json.asInt(json.get(doc, "age")))\n'
    'tags = json.get(doc, "tags")\n'
    "print(json.size(tags))\n"
    "print(json.asString(json.at(tags, 1)))\n"
    "print(json.asBool(json.at(tags, 2)))\n"
    "print(json.kind(json.at(tags, 3)))\n"
    'print(json.asInt(json.get(json.get(doc, "nested"), "x")))\n'
    'print(json.has(doc, "age"))\n'
    'print(json.has(doc, "zzz"))\n'
    "print(json.keyAt(doc, 3))\n"
    'bad = json.parse(lb + q + "a" + q + ": [1, 2," + rb)\n'
    "print(json.kind(bad))\n"
    'print(json.kind(json.parse("  [ ]  ")))\n'
    'print(json.asInt(json.parse("12.9")))\n'
    'print(json.kind(json.parse("1 2")))\n'
    'print(json.asString(json.parse(q + "line" + "\\\\" + "n" + "end " + "\\\\" + "u0041" + q)))\n'
)
EXPECTED = ["5", "Ada", "36", "4", "b", "1", "0", "-5", "1", "0", "nested", "-1", "4", "12", "-1",
            "line", "end", "A"]


def test_json_parse_all_pipelines(tmp_path, selfhost_run):
    vm = _vm_output(PROGRAM).split()
    assert vm == EXPECTED
    assert _native_output(PROGRAM, tmp_path).split() == EXPECTED
    r, _ = selfhost_run(PROGRAM, "json_parse")
    assert r.returncode == 0 and r.stdout.split() == EXPECTED


def test_json_parse_in_stage2_compiler(stage2):
    from test_stage2 import _run
    assert _run(stage2, "st2_json", PROGRAM) == EXPECTED


def test_json_table_entries_registered():
    import names
    assert names.module_function("json", "parse") == "json_parse"
    assert names.module_function("json", "keyAt") == "json_key_at"
