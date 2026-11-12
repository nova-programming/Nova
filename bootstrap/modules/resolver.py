"""
Module resolver for Nova .nv file imports.

Handles locating, reading, tokenizing, and parsing imported .nv files.
Maintains an import cache to prevent circular and duplicate imports.
"""

import os
from lexer.tokenizer import tokenize
from parser.parser import Parser


class ModuleResolver:
    def __init__(self, base_dir=None, target_arch="x86_64", target_os=None):
        import sys as _sys
        if target_os is None:
            if _sys.platform == "win32":
                target_os = "windows"
            elif _sys.platform == "darwin":
                target_os = "macos"
            else:
                target_os = "linux"
        self.base_dir = base_dir or os.getcwd()
        self.target_arch = target_arch
        self.target_os = target_os
        self.imported = {}  # canonical resolved path -> parsed AST (cache)

    def resolve(self, module_name, importer_dir=None):
        """
        Resolve and parse a .nv module by name.

        Args:
            module_name: The module name (e.g., "math" resolves to "math.nv")
            importer_dir: Directory of the file doing the import (for relative resolution)

        Returns:
            List of AST nodes from the imported module.

        Raises:
            FileNotFoundError: If the module .nv file cannot be found.
        """
        # Resolve the file path
        file_path = self._find_module(module_name, importer_dir)
        if file_path is None:
            raise FileNotFoundError(
                f"[Nova Import Error] Module '{module_name}' not found. "
                f"Searched for '{module_name}.nv' in: "
                f"{importer_dir or self.base_dir}"
            )
        file_path = os.path.realpath(file_path)
        if file_path in self.imported:
            return self.imported[file_path]

        # Read, tokenize, and parse the module
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        print(f"[Resolver] Parsing {file_path}")
        tokens = tokenize(source)
        ast = Parser(tokens).parse()
        if "stdlib" in file_path and module_name in ("fs", "path", "buffer", "net", "time", "env", "process", "audio", "text", "json"):
            self._namespace_ast(module_name, ast)

        # Cache the result
        self.imported[file_path] = ast
        return ast

    def _namespace_ast(self, module_name, ast):
        if not module_name or module_name == "system":
            return
        prefix = f"{module_name}_"
        renames = {}
        from nova_ast.nodes import Function, Call
        for node in ast:
            if isinstance(node, Function) and not getattr(node, "is_extern", False):
                if not node.name.startswith(prefix):
                    new_name = f"{prefix}{node.name}"
                    renames[node.name] = new_name
                    node.name = new_name
        if not renames:
            return

        def _rewrite_expr(expr):
            if expr is None:
                return
            if isinstance(expr, Call):
                if expr.name in renames:
                    expr.name = renames[expr.name]
                for arg in getattr(expr, "args", []) or []:
                    _rewrite_expr(arg)
            elif hasattr(expr, "args") and isinstance(expr.args, list):
                for arg in expr.args:
                    _rewrite_expr(arg)
            for attr in ("left", "right", "cond", "condition", "value", "instance"):
                if hasattr(expr, attr):
                    _rewrite_expr(getattr(expr, attr))

        def _rewrite_stmt(stmt):
            if stmt is None:
                return
            for attr in ("body", "if_body", "else_body"):
                if hasattr(stmt, attr):
                    body = getattr(stmt, attr)
                    if isinstance(body, list):
                        for s in body:
                            _rewrite_stmt(s)
            for attr in ("left", "right", "cond", "condition", "value", "expr"):
                if hasattr(stmt, attr):
                    _rewrite_expr(getattr(stmt, attr))
            if isinstance(stmt, Call):
                _rewrite_expr(stmt)

        for node in ast:
            if isinstance(node, Function):
                for s in (node.body or []):
                    _rewrite_stmt(s)

        from nova_ast.nodes import Variable, Return, ListLiteral
        if module_name == "path":
            ast.append(Function("path_basename", [("targetPath", None)], [Return(Call("path_base", [Variable("targetPath")]))]))
            ast.append(Function("path_dirname", [("targetPath", None)], [Return(Call("path_dir", [Variable("targetPath")]))]))
            ast.append(Function("path_extension", [("targetPath", None)], [Return(Call("path_ext", [Variable("targetPath")]))]))
            ast.append(Function("path_join2", [("a", None), ("b", None)], [Return(Call("path_join", [ListLiteral([Variable("a"), Variable("b")])]))]))
        elif module_name == "fs":
            ast.append(Function("fs_mkdir", [("p", None)], [Return(Call("fs_makeDir", [Variable("p")]))]))
            ast.append(Function("fs_read_text", [("p", None)], [Return(Call("fs_read", [Variable("p")]))]))
            ast.append(Function("fs_write_text", [("p", None), ("c", None)], [Return(Call("fs_write", [Variable("p"), Variable("c")]))]))
        elif module_name == "text":
            ast.append(Function("text_to_int", [("s", None)], [Return(Call("text_toInt", [Variable("s")]))]))
            ast.append(Function("text_starts_with", [("s", None), ("p", None)], [Return(Call("text_startsWith", [Variable("s"), Variable("p")]))]))
            ast.append(Function("text_ends_with", [("s", None), ("p", None)], [Return(Call("text_endsWith", [Variable("s"), Variable("p")]))]))
            ast.append(Function("text_index_of", [("s", None), ("sub", None)], [Return(Call("text_indexOf", [Variable("s"), Variable("sub")]))]))
            ast.append(Function("text_pad_left", [("s", None), ("w", None), ("ch", None)], [Return(Call("text_padLeft", [Variable("s"), Variable("w"), Variable("ch")]))]))
            ast.append(Function("text_pad_right", [("s", None), ("w", None), ("ch", None)], [Return(Call("text_padRight", [Variable("s"), Variable("w"), Variable("ch")]))]))
        elif module_name == "audio":
            ast.append(Function("audio_play_note", [("n", None), ("d", None)], [Return(Call("audio_playNote", [Variable("n"), Variable("d")]))]))
            ast.append(Function("audio_sample_sine", [("p", None)], [Return(Call("audio_sampleSine", [Variable("p")]))]))
            ast.append(Function("audio_sample_square", [("p", None)], [Return(Call("audio_sampleSquare", [Variable("p")]))]))
            ast.append(Function("audio_sample_triangle", [("p", None)], [Return(Call("audio_sampleTriangle", [Variable("p")]))]))
            ast.append(Function("audio_sample_noise", [("p", None)], [Return(Call("audio_sampleNoise", [Variable("p")]))]))
        elif module_name == "process":
            ast.append(Function("process_capture_output", [("r", None)], [Return(Call("process_captureOutput", [Variable("r")]))]))
            ast.append(Function("process_capture_code", [("r", None)], [Return(Call("process_captureCode", [Variable("r")]))]))
        elif module_name == "json":
            ast.append(Function("json_as_int", [("j", None)], [Return(Call("json_asInt", [Variable("j")]))]))
            ast.append(Function("json_as_string", [("j", None)], [Return(Call("json_asString", [Variable("j")]))]))
            ast.append(Function("json_as_bool", [("j", None)], [Return(Call("json_asBool", [Variable("j")]))]))
            ast.append(Function("json_key_at", [("j", None), ("i", None)], [Return(Call("json_keyAt", [Variable("j"), Variable("i")]))]))
        elif module_name == "buffer":
            ast.append(Function("new_buffer", [("s", None)], [Return(Call("buffer_alloc", [Variable("s")]))]))
        elif module_name == "net":
            ast.append(Function("tcp_listen", [("p", None), ("b", None)], [Return(Call("net_listen", [Variable("p"), Variable("b")]))]))
            ast.append(Function("tcp_connect", [("ip", None), ("p", None)], [Return(Call("net_connect", [Variable("ip"), Variable("p")]))]))
            ast.append(Function("socket_set_timeout", [("s", None), ("t", None)], [Return(Call("net_setTimeout", [Variable("s"), Variable("t")]))]))
        elif module_name == "time":
            ast.append(Function("time_ticks_ms", [], [Return(Call("time_ticks", []))]))

        # Old snake_case spellings of camelCase members stay valid (fs_write_atomic -> fs_writeAtomic, ...):
        # every camelCase module function also gets a snake_case alias unless one was defined above.
        import copy
        import re
        existing = {n.name for n in ast if isinstance(n, Function)}
        for node in list(ast):
            if isinstance(node, Function) and not getattr(node, "is_extern", False) and node.name.startswith(prefix):
                tail = node.name[len(prefix):]
                snake = prefix + re.sub(r"(?<=[a-z0-9])([A-Z])", lambda m: "_" + m.group(1).lower(), tail)
                if snake != node.name and snake not in existing:
                    alias = copy.copy(node)
                    alias.name = snake
                    ast.append(alias)
                    existing.add(snake)

    def _find_module(self, module_name, importer_dir=None):
        """
        Search for a .nv file matching the module name.

        Search order:
            1. Relative to the importing file's directory
            2. Relative to the project base directory
            3. In the stdlib/ directory relative to the Nova installation
        """
        if module_name == "os_impl":
            if self.target_os in ("linux", "macos"):
                module_name = "os_unix"
            else:
                module_name = f"os_{self.target_os}"

        filename = f"{module_name}.nv"

        search_dirs = []

        # 1. Relative to the importing file
        if importer_dir:
            search_dirs.append(importer_dir)

        # 2. Relative to the project base
        search_dirs.append(self.base_dir)

        # 3. stdlib/ directory (relative to Nova's own installation)
        nova_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        stdlib_dir = os.path.join(nova_root, "stdlib")
        search_dirs.append(stdlib_dir)
        
        # 4. Target Architecture specific backend directory
        backend_dir = os.path.join(stdlib_dir, "backend", self.target_arch)
        search_dirs.append(backend_dir)

        for search_dir in search_dirs:
            candidate = os.path.join(search_dir, filename)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

        return None

    def get_module_dir(self, module_name, importer_dir=None):
        """Get the directory containing a module (for chained imports)."""
        file_path = self._find_module(module_name, importer_dir)
        if file_path:
            return os.path.dirname(file_path)
        return None
