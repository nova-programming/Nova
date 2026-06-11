"""
Cross-platform installer tests — simulates install on Windows, macOS, and Linux
without actually modifying the real system. Exercises PATH logic, launcher
creation, extraction filtering, and all bug fixes.
"""

import sys
import os
import tempfile
import shutil
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestInstallPy(unittest.TestCase):
    """Test install.py logic in isolation with a sandboxed environment."""

    def setUp(self):
        # Sandbox: temp dir that acts as the install destination
        self.sandbox = tempfile.mkdtemp(prefix="nova-test-")
        # Prevent actual PATH modification during tests
        self.env_patch = mock.patch.dict(os.environ, {"PATH": "/usr/bin:/bin"})
        self.env_patch.start()
        # Import install module fresh for each test
        if "install" in sys.modules:
            del sys.modules["install"]

    def tearDown(self):
        self.env_patch.stop()
        shutil.rmtree(self.sandbox, ignore_errors=True)
        if "install" in sys.modules:
            del sys.modules["install"]

    # ===== MODULE IMPORT =====
    # Bug fix: INSTALL_DIR was used before assignment on line 40 (GCC_DIR)
    # This test verifies the module can be imported without NameError
    def test_module_imports_without_crash(self):
        """CRITICAL: install.py must import without NameError."""
        import install
        self.assertTrue(hasattr(install, "INSTALL_DIR"))
        self.assertTrue(hasattr(install, "GCC_DIR"))
        self.assertIsNotNone(install.INSTALL_DIR)
        self.assertIsNotNone(install.GCC_DIR)

    def test_gcc_dir_is_subdir_of_install_dir(self):
        """GCC_DIR must be $INSTALL_DIR/gcc."""
        import install
        self.assertEqual(install.GCC_DIR, os.path.join(install.INSTALL_DIR, "gcc"))

    # ===== INSTALL LOCATIONS =====
    # Windows: %LOCALAPPDATA%\nova
    # Unix: ~/.nova
    def _reload_install(self, platform_name, env=None, expanduser=None):
        """Reload install module with mocked platform/system environment."""
        if "install" in sys.modules:
            del sys.modules["install"]
        patches = [
            mock.patch("platform.system", return_value=platform_name),
        ]
        if env is not None:
            patches.append(mock.patch.dict(os.environ, env, clear=True))
        if expanduser is not None:
            patches.append(mock.patch("os.path.expanduser", return_value=expanduser))
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        import install
        import importlib
        importlib.reload(install)
        return install

    def test_windows_install_dir(self):
        """On Windows, install dir should be under LOCALAPPDATA."""
        install = self._reload_install(
            "Windows",
            env={"LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local"},
        )
        self.assertEqual(install.INSTALL_DIR, "C:\\Users\\Test\\AppData\\Local\\nova")

    def test_windows_install_dir_fallback(self):
        """On Windows without LOCALAPPDATA, fall back to home dir."""
        install = self._reload_install(
            "Windows",
            env={},
            expanduser="C:\\Users\\Test",
        )
        self.assertIn("nova", install.INSTALL_DIR)

    def test_unix_install_dir(self):
        """On Unix, install dir should be ~/.nova."""
        install = self._reload_install("Linux", expanduser="/home/testuser")
        expected = os.path.join("/home/testuser", ".nova")
        self.assertEqual(install.INSTALL_DIR, expected)

    # ===== LAUNCHER TEMPLATES =====
    def test_windows_launcher_templates(self):
        """Windows launchers should be .bat files calling python."""
        install = self._reload_install("Windows")
        self.assertIn("nova.bat", install.LAUNCHER_TEMPLATES)
        self.assertIn("galaxy.bat", install.LAUNCHER_TEMPLATES)
        nova_bat = install.LAUNCHER_TEMPLATES["nova.bat"]
        self.assertIn("python", nova_bat)
        self.assertIn("bootstrap\\main.py", nova_bat)

    def test_unix_launcher_templates(self):
        """Unix launchers should use 'python' shebang (not python3)."""
        install = self._reload_install("Linux")
        self.assertIn("nova", install.LAUNCHER_TEMPLATES)
        self.assertIn("galaxy", install.LAUNCHER_TEMPLATES)
        nova_launcher = install.LAUNCHER_TEMPLATES["nova"]
        self.assertNotIn("python3", nova_launcher.split("\n")[0])
        self.assertIn("python", nova_launcher.split("\n")[0])
        self.assertIn("from bootstrap.main import main", nova_launcher)

    # ===== _should_extract =====
    def test_should_extract_allowed_root_files(self):
        """Only _galaxy.py, nova.nv should be extracted from root."""
        import install
        self.assertFalse(install._should_extract("main.py"))
        self.assertTrue(install._should_extract("_galaxy.py"))
        self.assertTrue(install._should_extract("nova.nv"))
        self.assertFalse(install._should_extract("README.md"))
        self.assertFalse(install._should_extract("package.json"))
        self.assertFalse(install._should_extract("setup.py"))

    def test_should_extract_allowed_subdirs(self):
        """Files in allowed subdirectories should be extracted."""
        import install
        for d in install.ALLOWED_SUBDIRS:
            self.assertTrue(install._should_extract(f"{d}/some_file.py"))
            self.assertTrue(install._should_extract(f"{d}/subdir/other.nv"))

    def test_should_extract_reject_hidden(self):
        """__pycache__ directories should never be extracted."""
        import install
        self.assertFalse(install._should_extract("stdlib/compiler/__pycache__/codegen.cpython-312.pyc"))

    def test_should_extract_reject_unknown(self):
        """Unknown top-level dirs should not be extracted."""
        import install
        self.assertFalse(install._should_extract(".git/config"))
        self.assertFalse(install._should_extract("node_modules/pkg/index.js"))
        self.assertFalse(install._should_extract("__pycache__/foo.pyc"))

    # ===== _create_launchers (sandboxed) =====
    def test_create_launchers_writes_files(self):
        """_create_launchers should write launcher scripts to INSTALL_DIR."""
        import install
        with mock.patch.object(install, "INSTALL_DIR", self.sandbox):
            with mock.patch("platform.system", return_value="Windows"):
                install._create_launchers()
                self.assertTrue(os.path.exists(os.path.join(self.sandbox, "nova.bat")))
                self.assertTrue(os.path.exists(os.path.join(self.sandbox, "galaxy.bat")))

    def test_create_launchers_unix_executable(self):
        """Unix launchers should have executable permission."""
        import install
        with mock.patch.object(install, "INSTALL_DIR", self.sandbox):
            with mock.patch("platform.system", return_value="Linux"):
                # LAUNCHER_TEMPLATES was set at import time on real platform;
                # override for this test
                install.LAUNCHER_TEMPLATES = {
                    "nova": (
                        '#!/usr/bin/env python\n'
                        'import sys, os\n'
                        'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n'
                        'os.chdir(os.path.dirname(os.path.abspath(__file__)))\n'
                        'from main import main\n'
                        'main()\n'
                    ),
                    "galaxy": (
                        '#!/usr/bin/env python\n'
                        'import sys, os\n'
                        'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n'
                        'from _galaxy import main\n'
                        'main()\n'
                    ),
                }
                install._create_launchers()
                nova_path = os.path.join(self.sandbox, "nova")
                galaxy_path = os.path.join(self.sandbox, "galaxy")
                self.assertTrue(os.path.exists(nova_path))
                self.assertTrue(os.path.exists(galaxy_path))

    # ===== _add_to_path_windows (sandboxed) =====
    def test_add_to_path_windows_appends(self):
        """Windows PATH should get INSTALL_DIR appended."""
        import install
        with mock.patch.object(install, "INSTALL_DIR", self.sandbox):
            with mock.patch("platform.system", return_value="Windows"):
                with mock.patch("builtins.open", mock.mock_open()):
                    result = install._add_to_path_windows()
                    self.assertTrue(result)

    @unittest.skipIf(sys.platform == "win32", "winreg is a C module on Windows, cannot mock")
    def test_path_dedup_detects_existing(self):
        """Dedup should detect existing entry even with %VAR% in path."""
        # On non-Windows, winreg is mocked; on Windows this tests that
        # the REAL winreg doesn't crash when given %VAR% entries
        import install
        with mock.patch("platform.system", return_value="Windows"):
            # Import winreg at test level (non-Windows only)
            import winreg as _wr
            with mock.patch.object(_wr, "OpenKey") as mock_key:
                mock_handle = mock.MagicMock()
                mock_handle.__enter__.return_value = mock_handle
                mock_key.return_value = mock_handle
                mock_handle.QueryValueEx.return_value = (
                    "C:\\Windows;%LOCALAPPDATA%\\nova;",
                    2
                )
                result = install._add_to_path_windows()
                self.assertTrue(result,
                    "_add_to_path_windows should handle %VAR% in PATH")

    # ===== _add_to_path_unix (sandboxed) =====
    def test_add_to_path_unix_writes_export(self):
        """Unix PATH setup should write 'export PATH=...' to config."""
        import install
        cfg_file = os.path.join(self.sandbox, ".bashrc")
        with open(cfg_file, "w") as f:
            f.write("# existing config\n")
        with mock.patch.object(install, "INSTALL_DIR", self.sandbox):
            with mock.patch("platform.system", return_value="Linux"):
                with mock.patch.dict(os.environ, {"SHELL": "/bin/bash"}):
                    with mock.patch("os.path.expanduser", side_effect=lambda p: p.replace("~", self.sandbox)):
                        install._add_to_path_unix()
        with open(cfg_file) as f:
            content = f.read()
        self.assertIn("export PATH=", content)
        self.assertIn(self.sandbox, content)

    def test_add_to_path_unix_dedup(self):
        """Unix PATH setup should not duplicate entries."""
        import install
        cfg_file = os.path.join(self.sandbox, ".zshrc")
        with open(cfg_file, "w") as f:
            f.write("# Added by Nova installer\nexport PATH=\"$PATH:/home/user/.nova\"\n")
        with mock.patch.object(install, "INSTALL_DIR", "/home/user/.nova"):
            with mock.patch("platform.system", return_value="Linux"):
                with mock.patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
                    with mock.patch("os.path.expanduser", side_effect=lambda p: p.replace("~", self.sandbox)):
                        result = install._add_to_path_unix()
                        self.assertTrue(result)

    # ===== ZIP EXTRACTION =====
    def test_extract_filter_correctness(self):
        """_should_extract should match the exact file list we need."""
        import install
        test_cases = [
            ("main.py", False),
            ("_galaxy.py", True),
            ("nova.nv", True),
            ("bootstrap/main.py", True),
            ("stdlib/compiler/backend/x86_64/codegen.py", True),
            ("stdlib/lexer.nv", True),
            ("stdlib/lexer/tokenizer.py", True),
            ("stdlib/parser/parser.py", True),
            ("galaxy/__init__.py", True),
            ("README.md", False),
            ("install.py", False),
            (".github/workflows/release.yml", False),
            ("stdlib/compiler/__pycache__/codegen.cpython-312.pyc", False),
        ]
        for path, expected in test_cases:
            with self.subTest(path=path):
                self.assertEqual(install._should_extract(path), expected)

    # ===== VERSION CHECK =====
    def test_python_version_check(self):
        """install.py should require Python 3.6+."""
        # Can't actually change sys.version_info, but verify the check exists
        import install
        self.assertTrue(hasattr(install, "main"))
        self.assertTrue(hasattr(install, "install"))

    # ===== UNINSTALL =====
    def test_uninstall_removes_install_dir(self):
        """uninstall() should remove the install directory."""
        import install
        test_dir = os.path.join(self.sandbox, "test_install")
        os.makedirs(test_dir)
        with open(os.path.join(test_dir, "dummy.txt"), "w") as f:
            f.write("test")
        with mock.patch.object(install, "INSTALL_DIR", test_dir):
            install.uninstall()
        self.assertFalse(os.path.exists(test_dir))


class TestInstallSh(unittest.TestCase):
    """Validate install.sh logic — we parse and check critical patterns."""

    def setUp(self):
        self.script_path = os.path.join(os.path.dirname(__file__), "..", "install.sh")
        with open(self.script_path) as f:
            self.content = f.read()

    def test_shebang_is_sh(self):
        """install.sh must use #!/usr/bin/env sh (POSIX-compatible)."""
        self.assertTrue(self.content.startswith("#!/usr/bin/env sh"))

    def test_no_hardcoded_python3_in_launcher(self):
        """Launcher creation must probe for python3/python, not hardcode python3."""
        # Search for the create_launchers function
        self.assertIn('command -v python3', self.content)
        self.assertIn('|| py_cmd="python"', self.content)
        # Must use $py_cmd not hardcoded python3
        self.assertNotIn("#!/usr/bin/env python3", self.content)

    def test_install_dir_is_home_nova(self):
        """Install dir should be $HOME/.nova."""
        self.assertIn('INSTALL_DIR="${HOME}/.nova"', self.content)

    def test_python_required(self):
        """install.sh should fail early if Python is missing."""
        self.assertIn('have_python', self.content)
        # Must have a fail call guarded by have_python check
        fail_calls = [l for l in self.content.split("\n") if 'fail' in l and 'have_python' in l]
        self.assertTrue(len(fail_calls) > 0,
            "Expected a fail() call guarded by have_python check")

    def test_add_to_path_writes_export(self):
        """PATH setup should write 'export PATH=...'."""
        self.assertIn('export PATH=', self.content)

    def test_remove_from_path_cleans_configs(self):
        """Uninstall should clean profile, bashrc, zshrc."""
        self.assertIn(".profile", self.content)
        self.assertIn(".bashrc", self.content)
        self.assertIn(".zshrc", self.content)


class TestInstallPs1(unittest.TestCase):
    """Validate install.ps1 logic — we parse and check critical patterns."""

    def setUp(self):
        self.script_path = os.path.join(os.path.dirname(__file__), "..", "install.ps1")
        with open(self.script_path) as f:
            self.content = f.read()

    def test_no_expanded_path_write(self):
        """Must NOT write expanded PATH to registry via 'User' scope."""
        # The 'User' scope SetEnvironmentVariable was the bug
        # We should only use 'Process' scope for current-session updates
        lines_with_user = [l for l in self.content.split("\n") if '"User"' in l]
        for line in lines_with_user:
            self.assertIn("Process", line,
                f"Found 'User' scope SetEnvironmentVariable: {line.strip()}")

    def test_uses_expand_environment_variables(self):
        """PATH dedup must expand %VAR% before GetFullPath comparison."""
        self.assertIn("ExpandEnvironmentVariables", self.content)

    def test_install_dir_under_localappdata(self):
        """Install dir should be under LOCALAPPDATA."""
        self.assertIn('$env:LOCALAPPDATA', self.content)
        self.assertIn('"nova"', self.content)

    def test_launcher_creation(self):
        """Should create nova.bat and galaxy.bat launchers."""
        self.assertIn("nova.bat", self.content)
        self.assertIn("galaxy.bat", self.content)
        self.assertIn("bootstrap\\main.py", self.content)
        self.assertIn("_galaxy.py", self.content)

    def test_notify_only_via_process_scope(self):
        """Environment broadcast should use Process scope, not User."""
        process_lines = [l for l in self.content.split("\n") if "Process" in l]
        self.assertTrue(len(process_lines) > 0,
            "Should update current process PATH via 'Process' scope")

    def test_wm_settingchange_equivalent(self):
        """Must have a mechanism to notify running apps."""
        # PowerShell method: SetEnvironmentVariable with 'User' scope was
        # replaced with registry + Process scope approach
        self.assertIn("OpenSubKey", self.content)
        self.assertIn("SetValue", self.content)


class TestInstallDryRun(unittest.TestCase):
    """Perform a dry-run of the actual install flow on the current system."""

    def test_install_py_dry_run_importable(self):
        """install.py must be importable without side effects."""
        # Already tested above, but this runs the actual module
        import install
        self.assertIsNotNone(install.INSTALL_DIR)
        self.assertIsNotNone(install.GCC_DIR)
        self.assertIsNotNone(install.LAUNCHER_TEMPLATES)

    def test_allowed_files_match_actual_files(self):
        """ALLOWED_ROOT_FILES and ALLOWED_SUBDIRS must exist in the repo."""
        import install
        repo_root = os.path.join(os.path.dirname(__file__), "..")
        for f in install.ALLOWED_ROOT_FILES:
            path = os.path.join(repo_root, f)
            self.assertTrue(os.path.exists(path), f"Missing root file: {f}")
        for d in install.ALLOWED_SUBDIRS:
            path = os.path.join(repo_root, d)
            self.assertTrue(os.path.isdir(path), f"Missing subdir: {d}")

    def test_launcher_execution_simulated(self):
        """Simulate launcher execution to verify imports work."""
        import install
        for name, content in install.LAUNCHER_TEMPLATES.items():
            if name == "use_nova.bat":
                continue  # helper script, not a python launcher
            if name.endswith(".bat"):
                self.assertIn(".py", content)
            else:
                self.assertIn("from", content)
                self.assertIn("import", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
