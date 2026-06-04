import sys
import os
import json
import urllib.request
import urllib.error
import zipfile
import io
import shutil
import subprocess

from lexer.tokenizer import tokenize
from parser.parser import Parser
from vm.compiler import Compiler
from vm.machine import VirtualMachine
from compiler.type_checker import TypeInferer, StaticTypeError

NOVA_VERSION = "0.6.0"
REGISTRY_URL = "https://galaxy-registry.vercel.app"
NOVA_ZIP_URL = "https://github.com/nova-programming/Nova/archive/refs/heads/develop.zip"
ZIP_PREFIX = "Nova-develop"
NOVA_RELEASE_BASE = "https://github.com/nova-programming/Nova/releases/download"

ALLOWED_UPDATE_FILES = {"main.py", "_galaxy.py", "nova.nv"}
ALLOWED_UPDATE_DIRS = {"compiler", "parser", "lexer", "nova_ast", "vm", "stdlib", "modules", "tools", "galaxy"}

BUNDLED_GCC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gcc")

def _find_gcc():
    """Find GCC: bundled dir first, then system PATH."""
    gcc_name = "gcc.exe" if os.name == "nt" else "gcc"
    bundled = os.path.join(BUNDLED_GCC_DIR, "bin", gcc_name)
    if os.path.exists(bundled):
        return bundled
    system = shutil.which("gcc")
    if system:
        return system
    return None


def run_source(file_path):
    """Run a Nova program in the VM (development mode — fast execution)."""
    file_path = os.path.abspath(file_path)
    base_dir = os.path.dirname(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    tokens = tokenize(source)
    ast = Parser(tokens).parse()

    try:
        TypeInferer().infer(ast)
    except StaticTypeError as e:
        print(f"TypeError: {e}")
        sys.exit(1)

    compiler = Compiler(base_dir=base_dir)
    program = compiler.compile(ast)

    vm = VirtualMachine(program)
    vm.run()


def expand_imports(ast, base_dir, resolver=None, visited=None):
    from modules.resolver import ModuleResolver
    from nova_ast.nodes import Import
    import sys
    if resolver is None:
        resolver = ModuleResolver(base_dir=base_dir)
    if visited is None:
        visited = set()

    expanded_ast = []
    for node in ast:
        if isinstance(node, Import):
            if node.module not in visited:
                visited.add(node.module)
                try:
                    imported_ast = resolver.resolve(node.module, base_dir)
                    # Recursively expand imports inside the imported file
                    expanded_ast.extend(expand_imports(imported_ast, base_dir, resolver, visited))
                except FileNotFoundError as e:
                    print(e)
                    sys.exit(1)
        else:
            expanded_ast.append(node)
    return expanded_ast


def compile_native(file_path, debug_mode=0):
    """Compile a Nova program to a native executable (build mode)."""
    file_path = os.path.abspath(file_path)
    base_dir = os.path.dirname(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    tokens = tokenize(source)
    ast = Parser(tokens).parse()
    
    # Collect module names before expansion
    from nova_ast.nodes import Import
    module_names = set()
    for node in ast:
        if isinstance(node, Import):
            module_names.add(node.module)

    ast = expand_imports(ast, base_dir)

    try:
        TypeInferer().infer(ast)
    except StaticTypeError as e:
        print(f"TypeWarning: {e} (continuing build)")

    from compiler.codegen_x86 import X86Codegen
    codegen = X86Codegen(ast, module_names=module_names, debug_mode=debug_mode)
    asm_code = codegen.generate()

    asm_file = file_path.rsplit(".", 1)[0] + ".s"
    exe_file = file_path.rsplit(".", 1)[0] + ".exe"

    with open(asm_file, "w", encoding="utf-8") as f:
        f.write(asm_code)

    print(f"Generated assembly: {asm_file}")
    
    nova_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova.exe")
    nova_self = os.path.basename(exe_file) == "nova.exe"
    
    if os.path.exists(nova_exe) and not nova_self:
        try:
            asm_rel = os.path.relpath(asm_file)
            exe_rel = os.path.relpath(exe_file)
        except ValueError:
            asm_rel = asm_file
            exe_rel = exe_file
        cmd = [nova_exe, "assemble-link", asm_rel, exe_rel]
        print(f"Running: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            if os.path.exists(exe_file):
                if res.stdout:
                    print(res.stdout)
                print(f"Successfully compiled native executable: {exe_file}")
                return
            print(f"Weird: nova.exe said OK but {exe_file} not found. Falling back to GCC.")
            if res.stdout:
                print(res.stdout)
        print(f"Nova assembler failed (code {res.returncode}), falling back to GCC")
        if res.stderr:
            print(res.stderr)
    
    gcc_path = _find_gcc()
    if not gcc_path:
        print()
        print("  [FAIL] GCC not found.")
        print("  Nova build requires GCC/MinGW to link native executables.")
        print()
        print("  To install GCC:")
        if os.name == "nt":
            print("    Option 1: Download w64devkit from https://github.com/skeeto/w64devkit")
            print("    Option 2: Install MinGW-w64 from https://winlibs.com")
            print("    Option 3: Use 'nova dev <file.nv>' (runs via Python VM, no GCC needed)")
        else:
            print("    Ubuntu/Debian: sudo apt install build-essential")
            print("    Fedora:        sudo dnf install gcc")
            print("    macOS:         xcode-select --install")
        print()
        print("  Or run in development mode (no compilation needed):")
        print("    nova dev <file.nv>")
        print()
        sys.exit(1)
    
    cmd = [gcc_path, asm_file, "-o", exe_file, "-mconsole", "-lkernel32", "-Wl,--heap=67108864"]
    print(f"Running command: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("GCC Compilation Failed:")
        print(res.stderr)
        sys.exit(1)
    print(f"Successfully compiled native executable: {exe_file}")


def cmd_uninstall():
    """Remove Nova installation and all files it downloaded (GCC, launchers, galaxy_modules, etc)."""
    print(f"Nova v{NOVA_VERSION}")
    print()

    # Collect all directories to remove
    install_dirs = set()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Detect install locations
    if os.name == "nt":
        candidates = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "galaxy"),
            script_dir if "nova" in script_dir.lower() else None,
        ]
    else:
        candidates = [
            os.path.join(os.path.expanduser("~"), ".nova"),
            os.path.join(os.path.expanduser("~"), ".galaxy"),
        ]
    for d in candidates:
        if d and os.path.exists(d):
            install_dirs.add(d)

    # Also check for galaxy_modules directories that may have been installed
    for search_root in [os.path.expanduser("~"), os.environ.get("LOCALAPPDATA", ""), script_dir]:
        if search_root and os.path.exists(search_root):
            for root, dirs, files in os.walk(search_root):
                if "galaxy_modules" in dirs:
                    install_dirs.add(os.path.join(root, "galaxy_modules"))
                dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules") and not d.startswith(".")]

    # Also check for galaxy_modules in typical project locations
    for loc in [script_dir, os.path.join(os.path.expanduser("~"), "projects")]:
        gm = os.path.join(loc, "galaxy_modules") if loc else None
        if gm and os.path.exists(gm):
            install_dirs.add(gm)

    if not install_dirs:
        print("  No Nova installation found. Nothing to uninstall.")
        return

    print("  This will remove the following:")
    for d in sorted(install_dirs):
        print(f"    {d}")
    print()
    answer = input("  Uninstall Nova? (y/N): ").strip().lower()
    if answer not in ("y", "yes"):
        print("  Uninstall cancelled.")
        return

    # Remove directories
    for d in sorted(install_dirs):
        try:
            shutil.rmtree(d)
            print(f"  Removed {d}")
        except Exception as e:
            print(f"  [WARN] Could not remove {d}: {e}")

    # Remove generated files in the script directory (compiler intermediates)
    for f in ["nova.s", "nova_main.s"]:
        gen = os.path.join(script_dir, f)
        if os.path.exists(gen):
            try:
                os.remove(gen)
                print(f"  Removed {gen}")
            except Exception:
                pass

    # Remove User PATH entries
    if os.name == "nt":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
            try:
                current, _ = winreg.QueryValueEx(key, "PATH")
                entries = current.split(";")
                filtered = [e for e in entries if "nova" not in e.lower() and "galaxy" not in e.lower()]
                new_path = ";".join(filtered)
                winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
                print("  Removed Nova/Galaxy from User PATH")
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
        except Exception:
            print("  [WARN] Could not update PATH automatically. Remove manually if needed.")
    else:
        for rc in [".bashrc", ".zshrc", ".profile", ".bash_profile"]:
            rc_path = os.path.join(os.path.expanduser("~"), rc)
            if os.path.exists(rc_path):
                with open(rc_path, "r") as f:
                    content = f.read()
                if "nova" in content.lower():
                    new_content = "\n".join(
                        line for line in content.split("\n")
                        if "nova" not in line.lower()
                    )
                    with open(rc_path, "w") as f:
                        f.write(new_content)
                    print(f"  Cleaned Nova references from ~/{rc}")

    print()
    print("  Nova has been uninstalled.")
    print("  Close and reopen your terminal for PATH changes to take effect.")


def print_usage():
    print("Nova Programming Language")
    print(f"Version: {NOVA_VERSION}")
    print("")
    print("Usage:")
    print("  nova --version            Show version")
    print("  nova dev <file.nv>       Run in VM (fast, for development)")
    print("  nova build <file.nv>     Compile to native executable")
    print("  nova run <file.nv>       Alias for 'dev' (backward compatible)")
    print("  nova update              Update Nova compiler")
    print("  nova --uninstall         Remove Nova from your system")
    print("  nova galaxy <cmd>        Run Galaxy Package Manager")
    print("  galaxy <cmd>             Or use the standalone 'galaxy' command")
    print("")
    print("Examples:")
    print("  nova build hello.nv")
    print("  nova --uninstall")
    print("")
    print("Fallback (python):")
    print("  python main.py dev program.nv")
    print("  python main.py build program.nv")
    print("  python main.py --uninstall")


def _detect_install_dir():
    """Detect the Nova installation directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_dir, "main.py")):
        return script_dir
    known = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova"),
        os.path.join(os.path.expanduser("~"), ".nova"),
    ]
    for p in known:
        if p and os.path.exists(os.path.join(p, "main.py")):
            return p
    return script_dir


def cmd_update():
    """Update the Nova compiler itself."""
    print(f"Nova v{NOVA_VERSION}")
    print()

    try:
        req = urllib.request.Request(
            f"{REGISTRY_URL}/versions/nova.json",
            headers={"User-Agent": "Nova/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        latest = data.get("version", "")
    except Exception as e:
        print(f"Could not check for updates ({e})")
        return

    if latest == NOVA_VERSION:
        print(f"Already up to date (v{NOVA_VERSION}).")
        return

    print(f"Latest version: v{latest}  (current: v{NOVA_VERSION})")
    answer = input(f"Update to v{latest}? (Y/n): ").strip().lower()
    if answer not in ("", "y", "yes"):
        print("Update cancelled.")
        return

    install_dir = _detect_install_dir()
    print(f"Install directory: {install_dir}")
    print("Downloading...")

    url = f"{NOVA_RELEASE_BASE}/nova-v{latest}/nova-v{latest}.zip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nova/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            zip_data = r.read()
    except Exception as e:
        print(f"Download failed ({e}). Falling back to full repo zip...")
        try:
            req = urllib.request.Request(NOVA_ZIP_URL, headers={"User-Agent": "Nova/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                zip_data = r.read()
        except Exception as e2:
            print(f"Download failed: {e2}")
            return

    print("Extracting...")
    count = 0
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        bad = zf.testzip()
        if bad is not None:
            print(f"Corrupted archive: {bad}")
            return
        for name in zf.namelist():
            parts = name.split("/")
            top = parts[0]
            if top in ALLOWED_UPDATE_FILES or top in ALLOWED_UPDATE_DIRS:
                dst = os.path.join(install_dir, name)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with zf.open(name) as src, open(dst, "wb") as df:
                    shutil.copyfileobj(src, df)
                count += 1

    print(f"Updated {count} files.")
    print(f"Nova has been updated to v{latest}.")
    print("Restart your terminal or run 'nova --version' to confirm.")


def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1]

    if command in ("-v", "--version", "version"):
        print(f"Nova v{NOVA_VERSION}")
        return

    if command in ("--uninstall", "uninstall", "remove"):
        cmd_uninstall()
        return

    if command == "update":
        cmd_update()
        return

    if command == "galaxy":
        from tools.galaxy import main as galaxy_main
        old_argv = sys.argv
        sys.argv = ["galaxy"] + sys.argv[2:]
        galaxy_main()
        sys.argv = old_argv
        return

    if len(sys.argv) < 3:
        print_usage()
        return

    debug_mode = 0
    bench_mode = 0
    file_path = None
    for arg in sys.argv[2:]:
        if arg in ("-d", "--debug"):
            debug_mode = 1
        elif arg in ("-b", "--bench"):
            bench_mode = 1
        else:
            file_path = arg
    if file_path is None:
        print_usage()
        return

    import time
    start_time = time.time()

    if command in ("dev", "run"):
        run_source(file_path)
    elif command == "build":
        compile_native(file_path, debug_mode)
    else:
        print(f"Unknown command: {command}")
        print_usage()
        
    if bench_mode:
        print(f"[Benchmark] Build completed in {int((time.time() - start_time) * 1000)} ms")


if __name__ == "__main__":
    main()