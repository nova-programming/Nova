#!/usr/bin/env python3
"""
Galaxy Package Manager — Professional Installer
Installs the 'galaxy' command globally on your system.

Usage:
  python install.py            Install galaxy
  python install.py --uninstall   Remove galaxy

The installer:
  1. Copies the _galaxy.py CLI to a permanent directory
  2. Creates a launcher script (galaxy.bat on Windows, galaxy on Unix)
  3. Adds the install directory to your PATH (user-level)
"""

import sys
import os
import shutil
import stat
import subprocess
import platform


APP_NAME = "galaxy"
SOURCE_FILE = "_galaxy.py"

# Platform-specific install paths
if platform.system() == "Windows":
    INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "galaxy", "bin")
    LAUNCHER_NAME = "galaxy.bat"
    LAUNCHER_TEMPLATE = '''@echo off
REM Galaxy Package Manager for Nova
REM Installed by install.py
python "%~dp0_galaxy.py" %*
'''
else:
    INSTALL_DIR = os.path.join(os.path.expanduser("~"), ".galaxy", "bin")
    LAUNCHER_NAME = "galaxy"
    LAUNCHER_TEMPLATE = '''#!/usr/bin/env python3
"""Galaxy Package Manager — wrapper for the installed _galaxy.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _galaxy import main
main()
'''


def get_install_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return script_dir


def warn(msg):
    print(f"  [WARN] {msg}")


def success(msg):
    print(f"  [OK]   {msg}")


def info(msg):
    print(f"  [..]  {msg}")


def error(msg):
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def find_python():
    """Find the Python executable to embed in the launcher."""
    return sys.executable or "python"


def copy_source():
    """Copy _galaxy.py to the install directory."""
    src = os.path.join(get_install_root(), SOURCE_FILE)
    if not os.path.exists(src):
        error(f"{SOURCE_FILE} not found. Run this script from the Nova project root.")

    os.makedirs(INSTALL_DIR, exist_ok=True)
    dst = os.path.join(INSTALL_DIR, SOURCE_FILE)

    try:
        shutil.copy2(src, dst)
        success(f"Copied {SOURCE_FILE} to {dst}")
    except Exception as e:
        error(f"Failed to copy {SOURCE_FILE}: {e}")

    # Make executable on Unix
    if platform.system() != "Windows":
        st = os.stat(dst)
        os.chmod(dst, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return dst


def create_launcher():
    """Create the galaxy launcher script."""
    launcher_path = os.path.join(INSTALL_DIR, LAUNCHER_NAME)

    if platform.system() == "Windows":
        content = LAUNCHER_TEMPLATE
    else:
        content = LAUNCHER_TEMPLATE

    try:
        with open(launcher_path, "w", newline="\n") as f:
            f.write(content)
        if platform.system() != "Windows":
            st = os.stat(launcher_path)
            os.chmod(launcher_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        success(f"Created launcher: {launcher_path}")
    except Exception as e:
        error(f"Failed to create launcher: {e}")

    return launcher_path


def add_to_path_windows():
    """Add INSTALL_DIR to the user PATH on Windows."""
    try:
        import winreg
    except ImportError:
        warn("Could not import winreg. Add to PATH manually:")
        info(f"  {INSTALL_DIR}")
        return False

    key_path = r"Environment"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current_path, reg_type = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                current_path = ""
                reg_type = winreg.REG_EXPAND_SZ

            # Check if already in PATH
            parts = [p.strip() for p in current_path.split(";") if p.strip()]
            normalized = os.path.normcase(os.path.normpath(INSTALL_DIR))

            if any(os.path.normcase(os.path.normpath(p)) == normalized for p in parts):
                info("Install directory already in PATH")
                return True

            # Append to PATH
            new_path = current_path.rstrip(";") + ";" + INSTALL_DIR
            winreg.SetValueEx(key, "PATH", 0, reg_type, new_path)

        # Notify Windows of environment change
        try:
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            import ctypes
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment")
        except Exception:
            pass

        success(f"Added to PATH: {INSTALL_DIR}")
        info("You may need to restart your terminal for the change to take effect.")
        return True
    except Exception as e:
        warn(f"Could not update PATH automatically: {e}")
        info(f"Add this to your PATH manually: {INSTALL_DIR}")
        return False


def add_to_path_unix():
    """Add INSTALL_DIR to PATH on Unix via shell config."""
    shell_config = None
    shell = os.environ.get("SHELL", "")

    if "zsh" in shell:
        shell_config = os.path.expanduser("~/.zshrc")
    elif "bash" in shell:
        shell_config = os.path.expanduser("~/.bashrc")
    else:
        # Try common configs
        for cfg in ["~/.profile", "~/.bashrc", "~/.zshrc", "~/.config/fish/config.fish"]:
            cfg_path = os.path.expanduser(cfg)
            if os.path.exists(cfg_path):
                shell_config = cfg_path
                break

    path_line = f'\nexport PATH="$PATH:{INSTALL_DIR}"\n'

    if shell_config and os.path.exists(os.path.dirname(shell_config)):
        try:
            with open(shell_config, "r") as f:
                content = f.read()
            if INSTALL_DIR in content:
                info(f"Install directory already in {shell_config}")
                return True

            with open(shell_config, "a") as f:
                f.write(f"\n# Added by galaxy installer\n{path_line}")
            success(f"Added PATH to {shell_config}")
            info("Run 'source {0}' or restart your terminal.".format(shell_config))
            return True
        except Exception as e:
            warn(f"Could not update {shell_config}: {e}")
    else:
        warn("Could not detect shell config file.")

    info(f"Add this to your shell config: export PATH=\"$PATH:{INSTALL_DIR}\"")
    return False


def add_to_path():
    if platform.system() == "Windows":
        return add_to_path_windows()
    else:
        return add_to_path_unix()


def remove_from_path_windows():
    """Remove INSTALL_DIR from user PATH on Windows."""
    try:
        import winreg
    except ImportError:
        return False

    key_path = r"Environment"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current_path, reg_type = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                return True

            parts = [p.strip() for p in current_path.split(";") if p.strip()]
            normalized = os.path.normcase(os.path.normpath(INSTALL_DIR))
            filtered = [p for p in parts if os.path.normcase(os.path.normpath(p)) != normalized]

            if len(filtered) == len(parts):
                return True

            new_path = ";".join(filtered)
            winreg.SetValueEx(key, "PATH", 0, reg_type, new_path)
            return True
    except Exception:
        return False


def remove_from_path_unix():
    for cfg in ["~/.zshrc", "~/.bashrc", "~/.profile"]:
        cfg_path = os.path.expanduser(cfg)
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r") as f:
                    lines = f.readlines()
                filtered = [l for l in lines if INSTALL_DIR not in l]
                if len(filtered) != len(lines):
                    with open(cfg_path, "w") as f:
                        f.writelines(filtered)
                    success(f"Removed from {cfg_path}")
            except Exception:
                pass


def do_uninstall():
    print()
    print(f"  Uninstalling {APP_NAME}...")
    print()

    # Remove launcher
    launcher = os.path.join(INSTALL_DIR, LAUNCHER_NAME)
    if os.path.exists(launcher):
        os.remove(launcher)
        success(f"Removed launcher: {launcher}")

    # Remove _galaxy.py
    galaxy_py = os.path.join(INSTALL_DIR, SOURCE_FILE)
    if os.path.exists(galaxy_py):
        os.remove(galaxy_py)
        success(f"Removed: {galaxy_py}")

    # Remove install directory if empty
    if os.path.exists(INSTALL_DIR):
        try:
            os.rmdir(INSTALL_DIR)
            success(f"Removed directory: {INSTALL_DIR}")
        except OSError:
            info(f"Directory not empty, keeping: {INSTALL_DIR}")

    # Remove from PATH
    if platform.system() == "Windows":
        remove_from_path_windows()
    else:
        remove_from_path_unix()

    print()
    success(f"{APP_NAME} has been uninstalled.")
    print()


def do_install():
    print()
    print(f"  +========================================+")
    print(f"  |  Galaxy Package Manager Installer      |")
    print(f"  +========================================+")
    print()
    info(f"Install directory: {INSTALL_DIR}")

    copy_source()
    launcher = create_launcher()
    add_to_path()

    print()
    success(f"{APP_NAME} installed successfully!")
    print()
    info(f"Install location: {INSTALL_DIR}")
    info(f"Launcher: {launcher}")

    if platform.system() == "Windows":
        info("Open a NEW terminal window and type: galaxy")
    else:
        info("Run 'source ~/.zshrc' (or your shell config), then: galaxy")

    print()
    info("Usage examples:")
    info("  galaxy init my-lib        Create a library")
    info("  galaxy search math        Search registry")
    info("  galaxy install nova-math  Install a package")
    print()


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--uninstall", "uninstall", "remove"):
        do_uninstall()
    else:
        do_install()


if __name__ == "__main__":
    main()
