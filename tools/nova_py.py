import sys
import os
import ctypes
import subprocess

# Add nova root to path
nova_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bootstrap_dir = os.path.join(nova_root, "bootstrap")
if bootstrap_dir not in sys.path:
    sys.path.insert(0, bootstrap_dir)

print("SYS PATH:", sys.path)
print("BOOTSTRAP DIR:", os.listdir(bootstrap_dir))

from main import _find_gcc, _host_os
from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeInferer
from compiler.backend.x86_64.codegen import X86_64Codegen
from main import expand_imports
from compiler.types import IntType, FloatType, StringType, ListType

class NovaListStruct(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_int32),
        ("capacity", ctypes.c_int32),
        ("data", ctypes.c_void_p)
    ]

class NovaModuleWrapper:
    def __init__(self, dll, target_os, functions_metadata):
        self.dll = dll
        self.target_os = target_os
        self.functions_metadata = functions_metadata
        if hasattr(self.dll, '_nova_arc_alloc'):
            self.dll._nova_arc_alloc.argtypes = [ctypes.c_uint, ctypes.c_uint]
            self.dll._nova_arc_alloc.restype = ctypes.c_void_p
        if hasattr(self.dll, '_sys_alloc_c'):
            self.dll._sys_alloc_c.argtypes = [ctypes.c_int]
            self.dll._sys_alloc_c.restype = ctypes.c_void_p

    def _to_nova_type(self, val, expected_type):
        if expected_type == IntType:
            return ctypes.c_int64(int(val)).value
        elif expected_type == FloatType:
            return float(val)
        elif expected_type == StringType:
            if val is None: return 0
            encoded = str(val).encode('utf-8')
            sz = len(encoded) + 1
            ptr = self.dll._nova_arc_alloc(sz, 0)
            ctypes.memmove(ptr, encoded, sz)
            return ptr
        elif isinstance(expected_type, ListType):
            if val is None: return 0
            n = len(val)
            req_cap = max(16, n * 8)
            ptr = self.dll._nova_arc_alloc(16, 1)
            if ptr:
                struct_ptr = ctypes.cast(ptr, ctypes.POINTER(NovaListStruct))
                struct_ptr.contents.count = n
                struct_ptr.contents.capacity = req_cap
                data_ptr = self.dll._sys_alloc_c(req_cap)
                struct_ptr.contents.data = data_ptr
                for i, item in enumerate(val):
                    nv_item = self._to_nova_type(item, expected_type.inner)
                    ctypes.c_int64.from_address(data_ptr + i * 8).value = nv_item
            return ptr
        return val

    def _from_nova_type(self, val, expected_type):
        if expected_type == IntType:
            return val
        elif expected_type == FloatType:
            return val
        elif expected_type == StringType:
            if not val: return None
            return ctypes.cast(val, ctypes.c_char_p).value.decode('utf-8')
        elif isinstance(expected_type, ListType):
            if not val: return None
            struct_ptr = ctypes.cast(val, ctypes.POINTER(NovaListStruct))
            count = struct_ptr.contents.count
            data_ptr = struct_ptr.contents.data
            res = []
            for i in range(count):
                item_val = ctypes.c_int64.from_address(data_ptr + i * 8).value
                res.append(self._from_nova_type(item_val, expected_type.inner))
            return res
        return val

    def __getattr__(self, name):
        if name not in self.functions_metadata:
            raise AttributeError(f"Nova function '{name}' not found or not exported")
            
        metadata = self.functions_metadata[name]
        try:
            func_name = f"{name}_wrapper"
            func = getattr(self.dll, func_name)
        except AttributeError:
            try:
                func = getattr(self.dll, name)
            except AttributeError:
                raise AttributeError(f"Could not find exported symbol for '{name}'")
            
        def call_wrapper(*args):
            converted_args = []
            argtypes = []
            for arg, expected_type in zip(args, metadata.params):
                converted_args.append(self._to_nova_type(arg, expected_type))
                if expected_type == FloatType:
                    argtypes.append(ctypes.c_double)
                else:
                    argtypes.append(ctypes.c_int64)
                    
            func.argtypes = argtypes
            
            if metadata.ret == FloatType:
                func.restype = ctypes.c_double
            else:
                func.restype = ctypes.c_int64
                
            res = func(*converted_args)
            return self._from_nova_type(res, metadata.ret)
            
        return call_wrapper


_DLL_CACHE = {}

def load(filepath):
    filepath = os.path.abspath(filepath)
    if filepath in _DLL_CACHE:
        return _DLL_CACHE[filepath]
        
    base_dir = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    name = os.path.splitext(filename)[0]
    
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    tokens = tokenize(source)
    ast = Parser(tokens).parse()
    
    from nova_ast.nodes import Import
    module_names = set()
    for node in ast:
        if isinstance(node, Import):
            module_names.add(node.module)

    target_os = _host_os()
    ast = expand_imports(ast, base_dir, target_arch="x86_64", target_os=target_os)
    
    inferer = TypeInferer()
    inferer.infer(ast)

    codegen = X86_64Codegen(ast, module_names=module_names, debug_mode=0, target_os=target_os, source_path=filename)
    asm_code = codegen.generate()

    asm_file = os.path.join(base_dir, f"{name}.s")
    with open(asm_file, "w", encoding="utf-8") as f:
        f.write(asm_code)
        
    # Generate C wrapper for ABI translation (SysV to Host ABI)
    wrapper_c_code = ["#include <stdint.h>\n"]
    for fn_name, fn_meta in inferer.functions.items():
        if fn_name == "main": continue
        
        params_c = []
        args_c = []
        for i, pt in enumerate(fn_meta.params):
            arg_name = f"arg{i}"
            if pt == FloatType:
                params_c.append(f"double {arg_name}")
            else:
                params_c.append(f"int64_t {arg_name}")
            args_c.append(arg_name)
            
        ret_c = "double" if fn_meta.ret == FloatType else "int64_t"
        params_str = ", ".join(params_c) if params_c else "void"
        args_str = ", ".join(args_c)
        
        wrapper_c_code.append(f"extern __attribute__((sysv_abi)) {ret_c} _{fn_name}({params_str});")
        dllexport = "__declspec(dllexport)" if target_os == "windows" else "__attribute__((visibility(\"default\")))"
        wrapper_c_code.append(f"{dllexport} {ret_c} {fn_name}_wrapper({params_str}) {{")
        if ret_c == "void" or fn_meta.ret == None: # though nova doesn't have void yet
            wrapper_c_code.append(f"    _{fn_name}({args_str});")
        else:
            wrapper_c_code.append(f"    return _{fn_name}({args_str});")
        wrapper_c_code.append("}\n")
        
    wrapper_file = os.path.join(base_dir, f"{name}_wrapper.c")
    with open(wrapper_file, "w", encoding="utf-8") as fw:
        fw.write("\n".join(wrapper_c_code))
        
    gcc = _find_gcc(target_os=target_os, target_arch="x86_64")
    runtime_c = os.path.join(nova_root, "runtime.c")
    dll_ext = ".dll" if target_os == "windows" else ".dylib" if target_os == "macos" else ".so"
    dll_file = os.path.join(base_dir, f"{name}{dll_ext}")
    
    cmd = [gcc, "-shared", "-O3", asm_file, wrapper_file, runtime_c, "-o", dll_file, "-DNOVA_SHARED_LIB"]
    if target_os != "windows":
        cmd.append("-fPIC")
        
    if target_os == "windows":
        cmd.append("-Wl,--export-all-symbols")
    elif target_os == "linux":
        cmd.append("-DLINUX_WRAP")
    elif target_os == "macos":
        cmd.append("-DMACOS")
        
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"GCC failed to build shared library:\n{res.stderr}")
        
    dll = ctypes.CDLL(dll_file)
    
    # Initialize globals via main block
    entry = "_main" if target_os != "linux" else "main"
    if hasattr(dll, entry):
        getattr(dll, entry)()
    
    wrapper = NovaModuleWrapper(dll, target_os, inferer.functions)
    _DLL_CACHE[filepath] = wrapper
    return wrapper

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/nova_py.py <file.nv>")
        sys.exit(1)
    
    mod = load(sys.argv[1])
    print(f"Loaded {sys.argv[1]} successfully.")
    print("Available functions:")
    for f in mod.functions_metadata:
        print(f" - {f}")
