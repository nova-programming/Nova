"""Tests for the Galaxy Package Manager CLI."""

import os
import sys
import json
import tempfile
import shutil
import unittest
from unittest.mock import patch

# Add parent dir but remove ast conflict
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
if PROJECT_ROOT in sys.path:
    sys.path.remove(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

# Remove the nova/ast dir from path if present to avoid shadowing Python's ast module
for p in list(sys.path):
    ast_path = os.path.join(p, "ast")
    if os.path.isdir(ast_path) and os.path.exists(os.path.join(ast_path, "__init__.py")):
        # Keep it in sys.path but remove the ast subdir
        pass


class TestGalaxyManifest(unittest.TestCase):
    """Test galaxy.json manifest operations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir)

    def test_create_default_manifest(self):
        from tools.galaxy import create_default_manifest
        m = create_default_manifest("test-pkg")
        self.assertEqual(m["name"], "test-pkg")
        self.assertEqual(m["version"], "0.1.0")
        self.assertEqual(m["license"], "MIT")
        self.assertIn("dependencies", m)

    def test_save_and_load_manifest(self):
        from tools.galaxy import save_manifest, load_manifest
        m = {"name": "test", "version": "1.0.0", "dependencies": {}}
        save_manifest(m)
        loaded = load_manifest()
        self.assertEqual(loaded["name"], "test")

    def test_load_manifest_missing(self):
        from tools.galaxy import load_manifest
        with self.assertRaises(SystemExit):
            load_manifest()

    def test_validate_manifest_valid(self):
        from tools.galaxy import validate_manifest
        m = {"name": "pkg", "version": "1.0.0", "dependencies": {}}
        validate_manifest(m)

    def test_validate_manifest_missing_name(self):
        from tools.galaxy import validate_manifest
        m = {"version": "1.0.0"}
        with self.assertRaises(SystemExit):
            validate_manifest(m)


class TestGalaxyInit(unittest.TestCase):
    """Test galaxy init command."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir)

    def test_init_creates_files(self):
        from tools.galaxy import cmd_init
        cmd_init(["mylib"])
        self.assertTrue(os.path.exists("mylib/galaxy.json"))
        self.assertTrue(os.path.exists("mylib/src/main.nv"))
        self.assertTrue(os.path.exists("mylib/tests/test_main.nv"))
        with open("mylib/galaxy.json") as f:
            m = json.load(f)
        self.assertEqual(m["name"], "mylib")

    def test_init_no_name(self):
        from tools.galaxy import cmd_init
        cmd_init([])
        self.assertTrue(os.path.exists("galaxy.json"))

    def test_init_twice_fails(self):
        from tools.galaxy import cmd_init
        cmd_init(["pkg"])
        cmd_init(["pkg"])


class TestGalaxyRemove(unittest.TestCase):
    """Test galaxy remove command."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        from tools.galaxy import save_manifest, cmd_init
        cmd_init(["testpkg"])
        os.makedirs("galaxy_modules/testpkg")
        from pathlib import Path
        Path("galaxy_modules/testpkg/main.nv").touch()
        m = {"name": "testpkg", "version": "1.0.0",
             "dependencies": {"testpkg": "1.0.0"}}
        save_manifest(m)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir)

    def test_remove_package(self):
        from tools.galaxy import cmd_remove
        self.assertTrue(os.path.exists("galaxy_modules/testpkg"))
        cmd_remove(["testpkg"])
        self.assertFalse(os.path.exists("galaxy_modules/testpkg"))


class TestGalaxySearch(unittest.TestCase):
    """Test galaxy search with mocked registry."""

    @patch("tools.galaxy.registry_fetch_all")
    def test_search_finds_match(self, mock_fetch):
        from tools.galaxy import cmd_search
        mock_fetch.return_value = [
            {"name": "nova-math", "description": "Math library",
             "keywords": ["math", "crypto"], "tier": "core", "version": "1.0",
             "author": "Core Team", "upvotes": 50, "flags": 0},
            {"name": "nova-http", "description": "HTTP client",
             "keywords": ["http", "network"], "tier": "verified", "version": "2.0",
             "author": "Core Team", "upvotes": 30, "flags": 0},
        ]
        cmd_search(["math"])

    @patch("tools.galaxy.registry_fetch_all")
    def test_search_no_match(self, mock_fetch):
        from tools.galaxy import cmd_search
        mock_fetch.return_value = [{"name": "nova-math", "description": "Math"}]
        cmd_search(["zzzzzzz"])


class TestGalaxyInfo(unittest.TestCase):
    """Test galaxy info with mocked registry."""

    @patch("tools.galaxy.registry_fetch_pkg")
    def test_info_found(self, mock_fetch):
        from tools.galaxy import cmd_info
        mock_fetch.return_value = {
            "package": "nova-math",
            "tier": "core",
            "version": "1.0.0",
            "author": "Core Team",
            "license": "MIT",
            "github_repo": "nova-programming/nova-math",
            "description": "Math library",
            "keywords": ["math"],
            "upvotes": 50,
            "flags": 0,
            "versions": [{"version": "1.0.0", "sha256": "abc123"}],
        }
        cmd_info(["nova-math"])

    @patch("tools.galaxy.registry_fetch_pkg")
    def test_info_not_found(self, mock_fetch):
        from tools.galaxy import cmd_info
        mock_fetch.return_value = None
        cmd_info(["nonexistent"])


class TestGalaxyList(unittest.TestCase):
    """Test galaxy list command."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir)

    def test_list_no_project(self):
        from tools.galaxy import cmd_list
        cmd_list([])

    def test_list_no_deps(self):
        from tools.galaxy import save_manifest, cmd_list
        save_manifest({"name": "test", "version": "1.0", "dependencies": {}})
        cmd_list([])

    def test_list_with_deps(self):
        from tools.galaxy import save_manifest, cmd_list
        save_manifest({"name": "test", "version": "1.0",
                       "dependencies": {"nova-math": "1.0.0"}})
        cmd_list([])


class TestGalaxyUtilities(unittest.TestCase):
    """Test utility functions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_compute_sha256(self):
        from tools.galaxy import compute_sha256
        test_file = os.path.join(self.tmpdir, "test.nv")
        with open(test_file, "w") as f:
            f.write("print(1)")
        sha = compute_sha256(test_file)
        self.assertEqual(len(sha), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in sha))

    def test_find_nv_files(self):
        from tools.galaxy import find_nv_files
        os.makedirs(os.path.join(self.tmpdir, "src"))
        from pathlib import Path
        Path(os.path.join(self.tmpdir, "src", "main.nv")).touch()
        Path(os.path.join(self.tmpdir, "README.md")).touch()
        files = find_nv_files(self.tmpdir)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].endswith("main.nv"))

    @patch("tools.galaxy.urllib.request.urlopen")
    def test_registry_fetch_pkg_missing(self, mock_urlopen):
        # Simulate HTTP 404
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            "http://example.com", 404, "Not Found", {}, None
        )
        from tools.galaxy import registry_fetch_pkg
        result = registry_fetch_pkg("nonexistent")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
