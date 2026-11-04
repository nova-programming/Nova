"""Tests for the zero-dependency Nova VS Code extension (`editors/vscode`)."""

import json
import os
import subprocess
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(ROOT, "editors", "vscode")


def test_extension_manifest():
    pkg_path = os.path.join(EXT_DIR, "package.json")
    assert os.path.isfile(pkg_path), "package.json missing"
    with open(pkg_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)

    assert pkg["name"] == "nova-lang"
    assert "main" in pkg and os.path.isfile(os.path.join(EXT_DIR, pkg["main"]))
    assert "contributes" in pkg
    languages = pkg["contributes"].get("languages", [])
    assert any(lang.get("id") == "nova" and ".nv" in lang.get("extensions", []) for lang in languages)

    grammars = pkg["contributes"].get("grammars", [])
    assert any(g.get("language") == "nova" for g in grammars)
    grammar_file = os.path.join(EXT_DIR, grammars[0]["path"])
    assert os.path.isfile(grammar_file), f"Grammar file missing: {grammar_file}"


def test_language_configuration():
    config_path = os.path.join(EXT_DIR, "language-configuration.json")
    assert os.path.isfile(config_path), "language-configuration.json missing"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    assert config.get("comments", {}).get("lineComment") == "#"
    assert "brackets" in config


def test_tm_grammar_validity():
    grammar_path = os.path.join(EXT_DIR, "syntaxes", "nova.tmLanguage.json")
    with open(grammar_path, "r", encoding="utf-8") as f:
        grammar = json.load(f)
    assert grammar.get("scopeName") == "source.nova"
    assert "repository" in grammar
    repo = grammar["repository"]
    for required_key in ["comments", "keywords", "strings", "builtins", "types"]:
        assert required_key in repo, f"Missing key in grammar repository: {required_key}"


def test_extension_syntax_via_node():
    node = shutil.which("node")
    if not node:
        return
    ext_js = os.path.join(EXT_DIR, "extension.js")
    r = subprocess.run([node, "-c", ext_js], capture_output=True, text=True)
    assert r.returncode == 0, f"extension.js syntax error: {r.stderr}"

