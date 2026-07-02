"""Custom Virtual Machine to execute Nova bytecode"""

import struct
import ctypes
import os
from .opcodes import OpCode

class Instance:
    def __init__(self, class_name):
        self.class_name = class_name
        self.fields = {}
        self.ref_count = 0

class Frame:
    def __init__(self, return_address, local_env, self_context=None, is_init=False, pending_action=None, handler_depth=0):
        self.return_address = return_address
        self.locals = local_env.copy() if local_env else {}
        self.self_context = self_context
        self.is_init = is_init
        self.pending_action = pending_action  # Action to perform on return value (e.g. 'print')
        self.handler_depth = handler_depth  # Saved handler stack depth for function scope

class VirtualMachine:
    def __init__(self, program):
        self.code = program["code"]
        self.constants = program["constants"]
        self.strings = program["strings"]
        self.functions = program["functions"]
        self.classes = program["classes"]

        self.stack = []
        self.frames = []
        self.env = {}
        self.ip = 0 # Instruction Pointer

        # Simple simulated heap (1MB memory)
        self.heap = bytearray(1024 * 1024)
        self.heap_ptr = 1 # 0 is null
        self.allocations = {} # ptr -> size

        self.libraries = {} # loaded C libraries (FFI)

        self.open_files = {} # fd -> file object
        self.next_fd = 1

        self.handler_stack = []  # (catch_ip, stack_depth)

    def retain(self, obj):
        if isinstance(obj, Instance):
            obj.ref_count += 1

    def release(self, obj):
        if isinstance(obj, Instance):
            obj.ref_count -= 1
            if obj.ref_count <= 0:
                # Trigger cascading release for properties if they are Instances
                for val in obj.fields.values():
                    self.release(val)
                # In a real environment, memory would be pooled/freed here.
                # Since Python GC actually handles Instance backing, we simulate the logic.
                # If we mapped instances entirely to self.heap bytearray, we'd add to a free list here.

    def _to_str(self, val):
        if isinstance(val, bytearray):
            return val.decode('utf-8')
        return str(val)

    def _to_bytes(self, val):
        return bytearray(self._to_str(val).encode('utf-8'))

    def _call_builtin(self, func_name, args):
        handler = _STRING_HANDLERS.get(func_name)
        if handler:
            handler(self, args)
            return True
        handler = _BUILTIN_HANDLERS.get(func_name)
        if handler:
            handler(self, args)
            return True
        return False

    def run(self):
        while self.ip < len(self.code):
            opcode, arg = self.code[self.ip]
            self.ip += 1

            if opcode == OpCode.LOAD_CONST:
                self.stack.append(self.constants[arg])
            elif opcode == OpCode.LOAD_STR:
                self.stack.append(bytearray(self.strings[arg].encode('utf-8')))
            elif opcode == OpCode.LOAD_BOOL:
                self.stack.append(arg)
            elif opcode == OpCode.LOAD_NAME:
                name = arg
                if self.frames and name in self.frames[-1].locals:
                    self.stack.append(self.frames[-1].locals[name])
                elif name in self.env:
                    self.stack.append(self.env[name])
                else:
                    self.stack.append(0)
            elif opcode == OpCode.STORE_NAME:
                val = self.stack.pop()
                if self.frames:
                    old_val = self.frames[-1].locals.get(arg)
                    self.release(old_val)
                    self.retain(val)
                    self.frames[-1].locals[arg] = val
                else:
                    old_val = self.env.get(arg)
                    self.release(old_val)
                    self.retain(val)
                    self.env[arg] = val
            elif opcode == OpCode.ADD:
                b = self.stack.pop()
                a = self.stack.pop()
                if isinstance(a, Instance):
                    method_name = f"{a.class_name}.__add__"
                    if method_name in self.functions:
                        func_meta = self.functions[method_name]
                        local_env = {}
                        params = func_meta["params"]
                        if len(params) > 0:
                            p = params[0][0] if isinstance(params[0], (list, tuple)) else params[0]
                            local_env[p] = b
                        self.frames.append(Frame(self.ip, local_env, self_context=a, handler_depth=len(self.handler_stack)))
                        self.ip = func_meta["ip"]
                        continue
                if isinstance(a, bytearray) and not isinstance(b, bytearray):
                    b = bytearray(str(b).encode('utf-8'))
                elif isinstance(b, bytearray) and not isinstance(a, bytearray):
                    a = bytearray(str(a).encode('utf-8'))
                self.stack.append(a + b)
            elif opcode == OpCode.SUB:
                b = self.stack.pop()
                a = self.stack.pop()
                if isinstance(a, Instance):
                    method_name = f"{a.class_name}.__sub__"
                    if method_name in self.functions:
                        func_meta = self.functions[method_name]
                        local_env = {}
                        params = func_meta["params"]
                        if len(params) > 0:
                            p = params[0][0] if isinstance(params[0], (list, tuple)) else params[0]
                            local_env[p] = b
                        self.frames.append(Frame(self.ip, local_env, self_context=a, handler_depth=len(self.handler_stack)))
                        self.ip = func_meta["ip"]
                        continue
                self.stack.append(a - b)
            elif opcode == OpCode.MUL:
                b = self.stack.pop()
                a = self.stack.pop()
                if isinstance(a, Instance):
                    method_name = f"{a.class_name}.__mul__"
                    if method_name in self.functions:
                        func_meta = self.functions[method_name]
                        local_env = {}
                        params = func_meta["params"]
                        if len(params) > 0:
                            p = params[0][0] if isinstance(params[0], (list, tuple)) else params[0]
                            local_env[p] = b
                        self.frames.append(Frame(self.ip, local_env, self_context=a, handler_depth=len(self.handler_stack)))
                        self.ip = func_meta["ip"]
                        continue
                self.stack.append(a * b)
            elif opcode == OpCode.DIV:
                b = self.stack.pop()
                a = self.stack.pop()
                if isinstance(a, int) and isinstance(b, int):
                    self.stack.append(a // b)
                else:
                    self.stack.append(a / b)
            elif opcode == OpCode.MOD:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a % b)
            elif opcode == OpCode.CMP_EQ:
                b = self.stack.pop()
                a = self.stack.pop()
                if isinstance(a, Instance):
                    method_name = f"{a.class_name}.__eq__"
                    if method_name in self.functions:
                        func_meta = self.functions[method_name]
                        local_env = {}
                        params = func_meta["params"]
                        if len(params) > 0:
                            p = params[0][0] if isinstance(params[0], (list, tuple)) else params[0]
                            local_env[p] = b
                        self.frames.append(Frame(self.ip, local_env, self_context=a, handler_depth=len(self.handler_stack)))
                        self.ip = func_meta["ip"]
                        continue
                self.stack.append(a == b)
            elif opcode == OpCode.CMP_LT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a < b)
            elif opcode == OpCode.CMP_LE:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a <= b)
            elif opcode == OpCode.CMP_GT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a > b)
            elif opcode == OpCode.CMP_GE:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a >= b)
            elif opcode == OpCode.CMP_NEQ:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a != b)
            elif opcode == OpCode.AND:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a and b)
            elif opcode == OpCode.OR:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a or b)
            elif opcode == OpCode.BIT_AND:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a & b)
            elif opcode == OpCode.BIT_OR:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a | b)
            elif opcode == OpCode.BIT_XOR:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a ^ b)
            elif opcode == OpCode.BIT_NOT:
                a = self.stack.pop()
                self.stack.append(~a)
            elif opcode == OpCode.SHL:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a << b)
            elif opcode == OpCode.SAR:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a >> b)
            elif opcode == OpCode.HAS:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(b in a)
            elif opcode == OpCode.NOT:
                a = self.stack.pop()
                self.stack.append(not a)
            elif opcode == OpCode.PUSH_HANDLER:
                self.handler_stack.append((arg, len(self.stack)))
            elif opcode == OpCode.POP_HANDLER:
                if self.handler_stack:
                    self.handler_stack.pop()
            elif opcode == OpCode.THROW:
                exc_val = self.stack.pop()
                if not self.handler_stack:
                    print(f"Unhandled exception: {exc_val}")
                    break
                catch_ip, saved_sp = self.handler_stack.pop()
                # Restore stack to pre-try depth
                del self.stack[saved_sp:]
                self.stack.append(exc_val)
                self.ip = catch_ip
            elif opcode == OpCode.JUMP:
                self.ip = arg
            elif opcode == OpCode.JUMP_IF_FALSE:
                cond = self.stack.pop()
                if not cond:
                    self.ip = arg
            elif opcode == OpCode.PRINT:
                val = self.stack.pop()
                if isinstance(val, Instance):
                    method_name = f"{val.class_name}.__str__"
                    if method_name in self.functions:
                        func_meta = self.functions[method_name]
                        self.frames.append(Frame(self.ip, {}, self_context=val, pending_action='print', handler_depth=len(self.handler_stack)))
                        self.ip = func_meta["ip"]
                        continue
                    else:
                        print(f"<{val.class_name} instance>")
                elif isinstance(val, bytearray):
                    print(val.decode('utf-8'))
                else:
                    print(val)
            elif opcode == OpCode.ALLOC:
                size = self.stack.pop()
                ptr = self.heap_ptr
                self.heap_ptr += size
                self.allocations[ptr] = size
                self.stack.append(ptr)
            elif opcode == OpCode.FREE:
                ptr = self.stack.pop()
                if ptr in self.allocations:
                    del self.allocations[ptr]
            elif opcode == OpCode.STORE_PTR:
                ptr = self.stack.pop()
                val = self.stack.pop()
                # Store integer as 4 bytes
                struct.pack_into("<i", self.heap, ptr, val)
            elif opcode == OpCode.LOAD_PTR:
                ptr = self.stack.pop()
                val = struct.unpack_from("<i", self.heap, ptr)[0]
                self.stack.append(val)
            elif opcode == OpCode.LOAD_INDEX:
                index = self.stack.pop()
                base = self.stack.pop()
                if isinstance(base, bytearray):
                    self.stack.append(bytearray([base[index]]))
                elif isinstance(base, dict):
                    if isinstance(index, bytearray):
                        index = index.decode('utf-8')
                    if index not in base:
                        raise Exception(f"KeyError: {index} not found in dictionary")
                    self.stack.append(base[index])
                else:
                    self.stack.append(base[index])
            elif opcode == OpCode.STORE_INDEX:
                index = self.stack.pop()
                base = self.stack.pop()
                val = self.stack.pop()
                if isinstance(base, bytearray):
                    if isinstance(val, str):
                        if len(val) != 1:
                            raise Exception("ValueError: can only assign single character string to bytearray index")
                        base[index] = ord(val)
                    elif isinstance(val, bytearray):
                        if len(val) != 1:
                            raise Exception("ValueError: can only assign single character string to bytearray index")
                        base[index] = val[0]
                    else:
                        base[index] = val
                elif isinstance(base, dict):
                    if isinstance(index, bytearray):
                        index = index.decode('utf-8')
                    base[index] = val
                else:
                    base[index] = val
            elif opcode == OpCode.NEW_LIST:
                elements = []
                for _ in range(arg):
                    elements.append(self.stack.pop())
                elements.reverse()
                self.stack.append(elements)
            elif opcode == OpCode.BUILD_DICT:
                d = {}
                for _ in range(arg):
                    k = self.stack.pop()
                    v = self.stack.pop()
                    if isinstance(k, bytearray):
                        k = k.decode('utf-8')
                    d[k] = v
                self.stack.append(d)
            elif opcode == OpCode.SIZEOF:
                val = self.stack.pop()
                if isinstance(val, int) and val in self.allocations: # It's a pointer
                    self.stack.append(self.allocations[val])
                elif isinstance(val, int):
                    self.stack.append(4) # Int size
                elif isinstance(val, str):
                    self.stack.append(len(val))
                elif isinstance(val, Instance):
                    # Sum sizes of fields, approximation for now
                    self.stack.append(len(val.fields) * 4)
                else:
                    self.stack.append(4) # default
            elif opcode == OpCode.LEN:
                val = self.stack.pop()
                if isinstance(val, Instance):
                    method_name = f"{val.class_name}.__len__"
                    if method_name in self.functions:
                        func_meta = self.functions[method_name]
                        self.frames.append(Frame(self.ip, {}, self_context=val, handler_depth=len(self.handler_stack)))
                        self.ip = func_meta["ip"]
                        continue
                    else:
                        raise Exception(f"len() not defined for {val.class_name}")
                elif isinstance(val, (str, bytearray, list, dict)):
                    self.stack.append(len(val))
                else:
                    raise Exception("len() applied to invalid type")
            elif opcode == OpCode.OPEN_FILE:
                mode_val = self.stack.pop()
                path_val = self.stack.pop()
                mode = mode_val.decode('utf-8') if isinstance(mode_val, bytearray) else mode_val
                path = path_val.decode('utf-8') if isinstance(path_val, bytearray) else path_val
                try:
                    f = open(path, mode)
                    fd = self.next_fd
                    self.open_files[fd] = f
                    self.next_fd += 1
                    self.stack.append(fd)
                except Exception as e:
                    print(f"Error opening file: {e}")
                    self.stack.append(0) # 0 for failure
            elif opcode == OpCode.READ_FILE:
                fd = self.stack.pop()
                if fd in self.open_files:
                    content = self.open_files[fd].read()
                    self.stack.append(bytearray(content.encode('utf-8')))
                else:
                    self.stack.append(bytearray(b""))
            elif opcode == OpCode.WRITE_FILE:
                content_val = self.stack.pop()
                fd = self.stack.pop()
                content = content_val.decode('utf-8') if isinstance(content_val, bytearray) else content_val
                if fd in self.open_files:
                    self.open_files[fd].write(str(content))
            elif opcode == OpCode.CLOSE_FILE:
                fd = self.stack.pop()
                if fd in self.open_files:
                    self.open_files[fd].close()
                    del self.open_files[fd]
            elif opcode == OpCode.NEW:
                class_name, num_args = arg
                args = [self.stack.pop() for _ in range(num_args)]
                args.reverse()
                instance = Instance(class_name)
                # Initialization (__init__) logic could go here
                self.stack.append(instance)
            elif opcode == OpCode.LOAD_ATTR:
                prop = arg
                instance = self.stack.pop()
                if not isinstance(instance, Instance):
                    raise Exception("Property access on non-object")
                self.stack.append(instance.fields.get(prop, 0)) # Default 0 if missing
            elif opcode == OpCode.STORE_ATTR:
                prop = arg
                instance = self.stack.pop()
                val = self.stack.pop()
                if not isinstance(instance, Instance):
                    raise Exception("Property assign on non-object")

                old_val = instance.fields.get(prop)
                self.release(old_val)
                self.retain(val)
                instance.fields[prop] = val
            elif opcode == OpCode.LOAD_SELF:
                if self.frames and self.frames[-1].self_context:
                    self.stack.append(self.frames[-1].self_context)
                else:
                    raise Exception("Used 'self' outside of an instance method")
            elif opcode == OpCode.CALL_METHOD:
                method_name, num_args = arg
                instance = self.stack.pop()
                args = [self.stack.pop() for _ in range(num_args)]
                args.reverse()

                # Check if it's actually an FFI call disguised as a method call
                # (e.g. variable `libc` from `load` instead of a real object instance)
                if isinstance(instance, int) and instance == 0:
                    # In our VM, uninitialized variables return 0. If `libc` wasn't assigned an Instance,
                    # we need to check if it matches a loaded library.
                    # To do this cleanly, LOAD_LIB should store the library alias in the environment.
                    raise Exception("Attempted method call on null/uninitialized variable")

                if isinstance(instance, str) and instance in self.libraries:
                    lib = self.libraries[instance]
                    try:
                        func = getattr(lib, method_name)
                    except AttributeError:
                        raise Exception(f"Function {method_name} not found in library {instance}")

                    ctypes_args = []
                    for a in args:
                        if isinstance(a, str):
                            ctypes_args.append(a.encode('utf-8'))
                        elif isinstance(a, bytearray):
                            ctypes_args.append(bytes(a))
                        elif isinstance(a, int):
                            ctypes_args.append(ctypes.c_int(a))
                        elif isinstance(a, float):
                            ctypes_args.append(ctypes.c_double(a))
                        else:
                            ctypes_args.append(a)
                    result = func(*ctypes_args)
                    self.stack.append(result)
                    continue

                if isinstance(instance, list):
                    if method_name == "append":
                        instance.append(args[0])
                        self.stack.append(0)
                    elif method_name == "pop":
                        self.stack.append(instance.pop() if len(instance) > 0 else 0)
                    elif method_name == "insert":
                        instance.insert(args[0], args[1])
                        self.stack.append(0)
                    elif method_name == "clear":
                        instance.clear()
                        self.stack.append(0)
                    else:
                        raise Exception(f"List method {method_name} not supported")
                    continue

                if isinstance(instance, dict):
                    if method_name == "has":
                        k = args[0]
                        if isinstance(k, bytearray):
                            k = k.decode('utf-8')
                        self.stack.append(k in instance)
                    elif method_name == "get":
                        k = args[0]
                        if isinstance(k, bytearray):
                            k = k.decode('utf-8')
                        self.stack.append(instance.get(k, 0))
                    elif method_name == "set":
                        k = args[0]
                        if isinstance(k, bytearray):
                            k = k.decode('utf-8')
                        instance[k] = args[1]
                        self.stack.append(0)
                    elif method_name == "remove":
                        k = args[0]
                        if isinstance(k, bytearray):
                            k = k.decode('utf-8')
                        if k in instance:
                            del instance[k]
                        self.stack.append(0)
                    elif method_name == "keys":
                        keys = [bytearray(k.encode('utf-8')) if isinstance(k, str) else k for k in instance.keys()]
                        self.stack.append(keys)
                    elif method_name == "values":
                        self.stack.append(list(instance.values()))
                    elif method_name == "items":
                        items = []
                        for k, v in instance.items():
                            items.append(bytearray(k.encode('utf-8')) if isinstance(k, str) else k)
                            items.append(v)
                        self.stack.append(items)
                    else:
                        raise Exception(f"Dict method {method_name} not supported")
                    continue

                full_name = f"{instance.class_name}.{method_name}"
                if full_name not in self.functions:
                    raise Exception(f"Method {full_name} not found")

                # Setup local frame for method execution
                func_meta = self.functions[full_name]

                local_env = {}
                for i, param in enumerate(func_meta["params"]):
                    param_name = param[0] if isinstance(param, (list, tuple)) else param
                    local_env[param_name] = args[i] if i < len(args) else 0

                self.frames.append(Frame(self.ip, local_env, self_context=instance, handler_depth=len(self.handler_stack)))
                self.ip = func_meta["ip"]
            elif opcode == OpCode.LOAD_LIB:
                lib_path = self.stack.pop()
                if isinstance(lib_path, bytearray):
                    lib_path = lib_path.decode('utf-8')
                alias = arg

                # Use ctypes to load the shared library
                try:
                    lib = ctypes.CDLL(lib_path)
                    self.libraries[alias] = lib
                except Exception as e:
                    # Fallback for standard libc if just named 'c' or 'm'
                    if os.name != 'nt':
                        try:
                            lib = ctypes.CDLL(f"lib{lib_path}.so.6")
                            self.libraries[alias] = lib
                        except:
                            raise Exception(f"Failed to load FFI library {lib_path}: {str(e)}")
                    else:
                        raise Exception(f"Failed to load FFI library {lib_path}: {str(e)}")

                # Store the alias as a string variable in the global environment
                # so when `libc.puts` is called, `libc` resolves to the string "libc",
                # which our CALL_METHOD trap catches.
                self.env[alias] = alias

            elif opcode == OpCode.CALL_LIB:
                lib_name, func_name, num_args = arg
                args = [self.stack.pop() for _ in range(num_args)]
                args.reverse()

                if lib_name not in self.libraries:
                    raise Exception(f"FFI Library not loaded: {lib_name}")

                lib = self.libraries[lib_name]
                try:
                    func = getattr(lib, func_name)
                except AttributeError:
                    raise Exception(f"Function {func_name} not found in library {lib_name}")

                # Convert args for ctypes (simplified auto-translation)
                ctypes_args = []
                for a in args:
                    if isinstance(a, str):
                        ctypes_args.append(a.encode('utf-8'))
                    elif isinstance(a, bytearray):
                        ctypes_args.append(bytes(a))
                    elif isinstance(a, int):
                        ctypes_args.append(ctypes.c_int(a))
                    elif isinstance(a, float):
                        ctypes_args.append(ctypes.c_double(a))
                    else:
                        ctypes_args.append(a)

                # Call C function
                result = func(*ctypes_args)
                self.stack.append(result)

            elif opcode == OpCode.SLICE:
                end = self.stack.pop()
                start = self.stack.pop()
                base = self.stack.pop()
                if end == -1:
                    end = len(base)
                if isinstance(base, bytearray):
                    self.stack.append(bytearray(base[start:end]))
                elif isinstance(base, list):
                    self.stack.append(base[start:end])
                else:
                    raise Exception(f"Slice not supported for type {type(base)}")
            elif opcode == OpCode.STR_CONVERT:
                val = self.stack.pop()
                if isinstance(val, Instance):
                    method_name = f"{val.class_name}.__str__"
                    if method_name in self.functions:
                        func_meta = self.functions[method_name]
                        self.frames.append(Frame(self.ip, {}, self_context=val, handler_depth=len(self.handler_stack)))
                        self.ip = func_meta["ip"]
                        continue
                    else:
                        self.stack.append(bytearray(f"<{val.class_name} instance>".encode('utf-8')))
                elif isinstance(val, bytearray):
                    self.stack.append(val)  # Already a string
                elif isinstance(val, bool):
                    self.stack.append(bytearray(str(val).lower().encode('utf-8')))
                else:
                    self.stack.append(bytearray(str(val).encode('utf-8')))
            elif opcode == OpCode.CALL:
                func_name, num_args = arg
                args = [self.stack.pop() for _ in range(num_args)]
                args.reverse()

                # Check if it's actually a class or struct instantiation
                if func_name in self.classes:
                    instance = Instance(func_name)
                    # Auto-call __init__ if it exists and args were provided
                    init_name = f"{func_name}.__init__"
                    if init_name in self.functions:
                        func_meta = self.functions[init_name]
                        local_env = {}
                        for i, param in enumerate(func_meta["params"]):
                            param_name = param[0] if isinstance(param, (list, tuple)) else param
                            local_env[param_name] = args[i] if i < len(args) else 0
                        # Push instance first (it will be the return value after __init__)
                        self.stack.append(instance)
                        self.frames.append(Frame(self.ip, local_env, self_context=instance, is_init=True, handler_depth=len(self.handler_stack)))
                        self.ip = func_meta["ip"]
                    else:
                        self.stack.append(instance)
                    continue

                if func_name not in self.functions:
                    if self._call_builtin(func_name, args):
                        continue
                    raise Exception(f"Function {func_name} not found")

                # Setup local frame
                func_meta = self.functions[func_name]
                local_env = {}
                for i, param in enumerate(func_meta["params"]):
                    param_name = param[0] if isinstance(param, (list, tuple)) else param
                    local_env[param_name] = args[i] if i < len(args) else 0

                self.frames.append(Frame(self.ip, local_env, handler_depth=len(self.handler_stack)))
                self.ip = func_meta["ip"]
            elif opcode == OpCode.RETURN:
                if self.frames:
                    frame = self.frames.pop()

                    # Restore handler stack to function entry depth
                    del self.handler_stack[frame.handler_depth:]

                    # ARC: when a frame pops, release all locals
                    for val in frame.locals.values():
                        self.release(val)

                    # If returning from __init__, discard the return value
                    # (the instance is already on the stack below it)
                    if frame.is_init:
                        self.stack.pop()  # Discard __init__'s return value (usually 0)

                    # Execute pending action on the return value
                    if frame.pending_action == 'print':
                        ret_val = self.stack.pop()
                        if isinstance(ret_val, bytearray):
                            print(ret_val.decode('utf-8'))
                        else:
                            print(ret_val)

                    self.ip = frame.return_address
                else:
                    break # Exit VM
            else:
                raise Exception(f"Unknown opcode: {opcode}")

def _string_split(m, args):
    s = m._to_str(args[0])
    delim = m._to_str(args[1]) if len(args) > 1 else " "
    m.stack.append([bytearray(p.encode('utf-8')) for p in s.split(delim)])

def _string_join(m, args):
    lst = args[0]
    delim = m._to_str(args[1]) if len(args) > 1 else ""
    m.stack.append(bytearray(delim.join(m._to_str(x) for x in lst).encode('utf-8')))

def _string_trim(m, args):
    m.stack.append(bytearray(m._to_str(args[0]).strip().encode('utf-8')))

def _string_contains(m, args):
    m.stack.append(1 if m._to_str(args[1]) in m._to_str(args[0]) else 0)

def _string_replace(m, args):
    s = m._to_str(args[0])
    old = m._to_str(args[1]) if len(args) > 1 else ""
    new = m._to_str(args[2]) if len(args) > 2 else ""
    m.stack.append(bytearray(s.replace(old, new).encode('utf-8')))

def _string_to_upper(m, args):
    m.stack.append(bytearray(m._to_str(args[0]).upper().encode('utf-8')))

def _string_to_lower(m, args):
    m.stack.append(bytearray(m._to_str(args[0]).lower().encode('utf-8')))

def _string_starts_with(m, args):
    m.stack.append(1 if m._to_str(args[0]).startswith(m._to_str(args[1])) else 0)

def _string_ends_with(m, args):
    m.stack.append(1 if m._to_str(args[0]).endswith(m._to_str(args[1])) else 0)

_STRING_HANDLERS = {
    "split": _string_split,
    "join": _string_join,
    "trim": _string_trim,
    "contains": _string_contains,
    "replace": _string_replace,
    "to_upper": _string_to_upper,
    "to_lower": _string_to_lower,
    "starts_with": _string_starts_with,
    "ends_with": _string_ends_with,
}

# === Built-in function handlers (for the VM interpreter) ===

def _builtin_abs(m, args):
    m.stack.append(abs(args[0]))

def _builtin_min(m, args):
    m.stack.append(min(args[0], args[1]))

def _builtin_max(m, args):
    m.stack.append(max(args[0], args[1]))

def _builtin_now(m, args):
    import datetime
    m.stack.append(bytearray(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S").encode('utf-8')))

def _builtin_call(m, args):
    """call(name: string, args_list: list) -> any
    Dynamically look up a Nova function by name and call it with the given args.
    The return value is left on the VM stack."""
    func_name = m._to_str(args[0])
    call_args = args[1] if len(args) > 1 else []

    if func_name not in m.functions:
        if not m._call_builtin(func_name, call_args):
            raise Exception(f"call(): function '{func_name}' not found")
        return

    func_meta = m.functions[func_name]
    local_env = {}
    for i, param in enumerate(func_meta["params"]):
        param_name = param[0] if isinstance(param, (list, tuple)) else param
        local_env[param_name] = call_args[i] if i < len(call_args) else 0

    m.frames.append(Frame(m.ip, local_env, handler_depth=len(m.handler_stack)))
    m.ip = func_meta["ip"]

def _builtin_type(m, args):
    val = args[0]
    if isinstance(val, Instance):
        m.stack.append(bytearray(b"data:" + val.class_name.encode('utf-8')))
    elif isinstance(val, bytearray):
        m.stack.append(bytearray(b"string"))
    elif isinstance(val, bool):
        m.stack.append(bytearray(b"bool"))
    elif isinstance(val, int):
        m.stack.append(bytearray(b"int"))
    elif isinstance(val, float):
        m.stack.append(bytearray(b"float"))
    elif isinstance(val, list):
        m.stack.append(bytearray(b"list"))
    elif isinstance(val, dict):
        m.stack.append(bytearray(b"dict"))
    else:
        m.stack.append(bytearray(b"unknown"))

def _builtin_file_exists(m, args):
    import os
    m.stack.append(1 if os.path.exists(m._to_str(args[0])) else 0)

def _builtin_file_size(m, args):
    import os
    path = m._to_str(args[0])
    try:
        m.stack.append(os.path.getsize(path))
    except:
        m.stack.append(0)

def _builtin_file_type(m, args):
    import os
    path = m._to_str(args[0])
    if os.path.isdir(path):
        m.stack.append(bytearray(b"dir"))
    elif os.path.isfile(path):
        m.stack.append(bytearray(b"file"))
    else:
        m.stack.append(bytearray(b""))

_BUILTIN_HANDLERS = {
    "type": _builtin_type,
    "call": _builtin_call,
    "abs": _builtin_abs,
    "min": _builtin_min,
    "max": _builtin_max,
    "now": _builtin_now,
    "file_exists": _builtin_file_exists,
    "file_size": _builtin_file_size,
    "file_type": _builtin_file_type,
}