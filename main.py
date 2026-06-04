import sys
import os
import json
import urllib.request
import urllib.error
import zipfile
import io
import shutil

from lexer.tokenizer import tokenize
from parser.parser import Parser
from vm.compiler import Compiler
from vm.machine import VirtualMachine
from compiler.type_checker import TypeInferer, StaticTypeError

NOVA_VERSION = "0.5.0"
REGISTRY_URL = "https://galaxy-registry.vercel.app"
NOVA_ZIP_URL = "https://github.com/nova-programming/Nova/archive/refs/heads/develop.zip"
ZIP_PREFIX = "Nova-develop"
NOVA_RELEASE_BASE = "https://github.com/nova-programming/Nova/releases/download"

ALLOWED_UPDATE_FILES = {"main.py", "_galaxy.py", "nova_main.nv"}
ALLOWED_UPDATE_DIRS = {"compiler", "parser", "lexer", "nova_ast", "vm", "stdlib", "modules", "tools", "galaxy"}


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
    
    import subprocess
    nova_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_main.exe")
    nova_self = os.path.basename(exe_file) == "nova_main.exe"
    
    if os.path.exists(nova_exe) and not nova_self:
        asm_rel = os.path.relpath(asm_file)
        exe_rel = os.path.relpath(exe_file)
        cmd = [nova_exe, "assemble-link", asm_rel, exe_rel]
        print(f"Running: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            if res.stdout:
                print(res.stdout)
            print(f"Successfully compiled native executable: {exe_file}")
            return
        print(f"Nova assembler failed (code {res.returncode}), falling back to GCC")
        if res.stderr:
            print(res.stderr)
    
    cmd = ["gcc", asm_file, "-o", exe_file, "-lkernel32", "-Wl,--heap=67108864"]
    print(f"Running command: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("GCC Compilation Failed:")
        print(res.stderr)
        sys.exit(1)
    print(f"Successfully compiled native executable: {exe_file}")


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
    print("  nova galaxy <cmd>        Run Galaxy Package Manager")
    print("  galaxy <cmd>             Or use the standalone 'galaxy' command")
    print("")
    print("Examples:")
    print("  python main.py dev program.nv")
    print("  python main.py galaxy init")
    print("  python main.py update")


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