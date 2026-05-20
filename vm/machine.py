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
    def __init__(self, return_address, local_env, self_context=None):
        self.return_address = return_address
        self.locals = local_env.copy() if local_env else {}
        self.self_context = self_context
        self.is_init = False # Tracks if this frame is a constructor

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
        self.free_list = [] # List of tuples: (ptr, size)
        self.method_cache = {} # Cache for inline method resolution

        self.libraries = {} # loaded C libraries (FFI)

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

    def run(self):
        while self.ip < len(self.code):
            opcode, arg = self.code[self.ip]
            self.ip += 1

            if opcode == OpCode.POP:
                if self.stack:
                    self.stack.pop()
            elif opcode == OpCode.LOAD_CONST:
                self.stack.append(self.constants[arg])
            elif opcode == OpCode.LOAD_STR:
                self.stack.append(self.strings[arg])
            elif opcode == OpCode.LOAD_BOOL:
                self.stack.append(arg)
            elif opcode == OpCode.LOAD_NAME:
                name = arg
                # Look in local frame first, then global
                if self.frames and name in self.frames[-1].locals:
                    self.stack.append(self.frames[-1].locals[name])
                elif name in self.env:
                    self.stack.append(self.env[name])
                else:
                    # Let's see if it's an uninitialized variable and just return 0 to support flexible scripting
                    # In a strongly typed later version this will be an error
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
                self.stack.append(a + b)
            elif opcode == OpCode.SUB:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a - b)
            elif opcode == OpCode.MUL:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)
            elif opcode == OpCode.DIV:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a / b)
            elif opcode == OpCode.MOD:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a % b)
            elif opcode == OpCode.CMP_EQ:
                b = self.stack.pop()
                a = self.stack.pop()
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
            elif opcode == OpCode.JUMP:
                self.ip = arg
            elif opcode == OpCode.JUMP_IF_FALSE:
                cond = self.stack.pop()
                if not cond:
                    self.ip = arg
            elif opcode == OpCode.PRINT:
                val = self.stack.pop()
                print(val)
            elif opcode == OpCode.ALLOC:
                size = self.stack.pop()

                # Best-fit search
                best_idx = -1
                best_size = float('inf')
                for i, (f_ptr, f_size) in enumerate(self.free_list):
                    if f_size >= size and f_size < best_size:
                        best_size = f_size
                        best_idx = i

                if best_idx != -1:
                    ptr, f_size = self.free_list.pop(best_idx)
                    self.allocations[ptr] = f_size # We allocate the whole block to avoid fragmentation logic for now
                else:
                    ptr = self.heap_ptr
                    self.heap_ptr += size
                    self.allocations[ptr] = size
                self.stack.append(ptr)
            elif opcode == OpCode.FREE:
                ptr = self.stack.pop()
                if ptr in self.allocations:
                    self.free_list.append((ptr, self.allocations[ptr]))
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
                if isinstance(val, str):
                    self.stack.append(len(val))
                elif isinstance(val, list):
                    self.stack.append(len(val))
                else:
                    raise Exception("len() applied to invalid type")
            elif opcode == OpCode.NEW:
                class_name, num_args = arg
                args = [self.stack.pop() for _ in range(num_args)]
                args.reverse()
                instance = Instance(class_name)
                self.retain(instance) # Hold a reference initially

                # Check for __init__ method
                init_name = f"{class_name}.__init__"
                if init_name in self.functions:
                    func_meta = self.functions[init_name]
                    local_env = {}
                    for i, param in enumerate(func_meta["params"]):
                        local_env[param] = args[i] if i < len(args) else 0

                    frame = Frame(self.ip, local_env, self_context=instance)
                    frame.is_init = True
                    self.frames.append(frame)
                    self.ip = func_meta["ip"]
                else:
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
                        elif isinstance(a, int):
                            ctypes_args.append(ctypes.c_int(a))
                        elif isinstance(a, float):
                            ctypes_args.append(ctypes.c_double(a))
                        else:
                            ctypes_args.append(a)
                    result = func(*ctypes_args)
                    self.stack.append(result)
                    continue

                # Safe Polymorphic Caching: O(1) method resolution
                cache_key = (instance.class_name, method_name)
                if cache_key in self.method_cache:
                    func_meta = self.method_cache[cache_key]
                else:
                    full_name = f"{instance.class_name}.{method_name}"
                    if full_name not in self.functions:
                        raise Exception(f"Method {full_name} not found")
                    func_meta = self.functions[full_name]
                    self.method_cache[cache_key] = func_meta

                # Setup local frame for method execution
                local_env = {}
                for i, param in enumerate(func_meta["params"]):
                    local_env[param] = args[i] if i < len(args) else 0

                self.frames.append(Frame(self.ip, local_env, self_context=instance))
                self.ip = func_meta["ip"]
            elif opcode == OpCode.LOAD_LIB:
                lib_path = self.stack.pop()
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
                    elif isinstance(a, int):
                        ctypes_args.append(ctypes.c_int(a))
                    elif isinstance(a, float):
                        ctypes_args.append(ctypes.c_double(a))
                    else:
                        ctypes_args.append(a)

                # Call C function
                result = func(*ctypes_args)
                self.stack.append(result)

            elif opcode == OpCode.CALL:
                func_name, num_args = arg
                args = [self.stack.pop() for _ in range(num_args)]
                args.reverse()

                if func_name not in self.functions:
                    raise Exception(f"Function {func_name} not found")

                # Setup local frame
                func_meta = self.functions[func_name]
                local_env = {}
                for i, param in enumerate(func_meta["params"]):
                    local_env[param] = args[i] if i < len(args) else 0

                self.frames.append(Frame(self.ip, local_env))
                self.ip = func_meta["ip"]
            elif opcode == OpCode.RETURN:
                if self.frames:
                    frame = self.frames.pop()

                    # ARC: when a frame pops, release all locals
                    for val in frame.locals.values():
                        self.release(val)

                    self.ip = frame.return_address

                    # If returning from __init__, we want to return the instance itself
                    # (and override whatever dummy 0 return was compiled at the end)
                    if frame.is_init:
                        # Pop the dummy return value
                        self.stack.pop()
                        self.stack.append(frame.self_context)
                else:
                    break # Exit VM
            else:
                raise Exception(f"Unknown opcode: {opcode}")