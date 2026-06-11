"""Tests for X86_64Codegen — verifies x86_64 System V AMD64 assembly output."""
import sys, os, unittest, tempfile

BOOTSTRAP = os.path.join(os.path.dirname(__file__), "..", "bootstrap")
sys.path.insert(0, BOOTSTRAP)
from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeInferer, StaticTypeError
from nova_ast.nodes import *


def compile_to_asm(source):
    """Tokenize, parse, type-check, and generate x86_64 assembly from Nova source."""
    tokens = tokenize(source)
    ast = Parser(tokens).parse()
    try:
        TypeInferer().infer(ast)
    except StaticTypeError:
        pass
    from compiler.backend.x86_64.codegen import X86_64Codegen
    module_names = set()
    from nova_ast.nodes import Import
    for node in ast:
        if isinstance(node, Import):
            module_names.add(node.module)
    codegen = X86_64Codegen(ast, module_names=module_names)
    return codegen.generate()


class TestX86_64CodegenOutput(unittest.TestCase):
    """Verify structural properties of the generated x86_64 assembly."""

    def test_headers_and_externs(self):
        """Verify headers, .global _main, and extern declarations."""
        asm = compile_to_asm('print("hello")')
        self.assertIn(".intel_syntax noprefix", asm)
        self.assertIn(".global _main", asm)
        self.assertIn(".extern _printf", asm)
        self.assertIn(".extern _malloc", asm)
        self.assertIn(".extern _free", asm)
        self.assertIn(".extern _exit", asm)
        self.assertIn(".text", asm)
        self.assertIn(".data", asm)

    def test_main_prologue_64bit(self):
        """_main must use 64-bit registers and stack alignment."""
        asm = compile_to_asm('print("hello")')
        self.assertIn("push rbp", asm)
        self.assertIn("mov rbp, rsp", asm)
        self.assertIn("and rsp, -16", asm)
        self.assertIn("sub rsp,", asm)

    def test_string_literal_rip_relative(self):
        """String literals must use RIP-relative LEA (not 'push offset')."""
        asm = compile_to_asm('print("hello")')
        lea_count = asm.count("lea rax, [rip + str_")
        push_offset_count = asm.count("push offset")
        self.assertGreater(lea_count, 0, "Expected RIP-relative LEA for string literals")
        self.assertEqual(push_offset_count, 0, "Expected NO 'push offset' in x86_64 codegen")

    def test_printf_call_systemv(self):
        """printf must be called via System V ABI (args in rdi, rsi, xor eax)."""
        asm = compile_to_asm('print("hello")')
        self.assertIn("lea rdi, [rip + fmt_str]", asm)
        self.assertIn("pop rsi", asm)
        self.assertIn("mov eax, 0", asm)
        self.assertIn("call _printf", asm)

    def test_print_int(self):
        """Print integer uses fmt_int and pop rsi."""
        asm = compile_to_asm("print(42)")
        self.assertIn("lea rdi, [rip + fmt_int]", asm)
        self.assertIn("pop rsi", asm)
        self.assertIn("call _printf", asm)

    def test_print_float(self):
        """Print float uses fmt_float."""
        asm = compile_to_asm("print(3.14)")
        self.assertIn("lea rdi, [rip + fmt_float]", asm)

    def test_printf_zero_vector_regs(self):
        """printf requires RAX=0 to specify 0 vector registers used."""
        asm = compile_to_asm("print(42)")
        # Peephole replaces xor eax, eax with mov eax, 0
        self.assertIn("mov eax, 0", asm)
        self.assertIn("call _printf", asm)

    def test_binary_ops(self):
        """Binary ops fold memory operands for leaf variables."""
        asm = compile_to_asm("a = 10\nb = 20\nprint(a + b)")
        self.assertRegex(asm, r"add e\w\w, e\w\w")
        self.assertIn("push rax", asm)

    def test_binary_sub(self):
        asm = compile_to_asm("a = 10\nb = 5\nprint(a - b)")
        self.assertRegex(asm, r"sub e\w\w, e\w\w")

    def test_binary_mul(self):
        asm = compile_to_asm("a = 10\nb = 5\nprint(a * b)")
        self.assertRegex(asm, r"imul e\w\w, e\w\w")

    def test_binary_div_idiv(self):
        """Division uses cdq/idiv for signed 32-bit."""
        asm = compile_to_asm("a = 100\nb = 3\nprint(a / b)")
        self.assertIn("cdq", asm)
        self.assertRegex(asm, r"idiv e\w\w")

    def test_unary_neg(self):
        asm = compile_to_asm("print(-5)")
        self.assertIn("neg eax", asm)

    def test_unary_not(self):
        asm = compile_to_asm("print(not 0)")
        self.assertIn("sete al", asm)
        self.assertIn("movzx eax, al", asm)

    def test_if_else(self):
        asm = compile_to_asm("if 1 { print(1) } else { print(0) }")
        self.assertIn("cmp eax, 0", asm)
        self.assertIn("je L_else", asm)
        self.assertIn("jmp L_end", asm)

    def test_while_loop(self):
        asm = compile_to_asm("while 0 { print(1) }")
        self.assertIn("L_loop", asm)
        self.assertIn("L_loop_end", asm)
        self.assertIn("jmp L_loop", asm)

    def test_for_loop(self):
        asm = compile_to_asm("for x = 0 to 10 { print(x) }")
        self.assertIn("L_for", asm)
        self.assertIn("L_for_end", asm)
        self.assertIn("cmp rax, rbx", asm)

    def test_variable_assignment_and_load(self):
        asm = compile_to_asm("x = 42\nprint(x)")
        self.assertIn("pop rax", asm)
        self.assertIn("mov [rbp -", asm)
        # Variable load: mov rax, [rbp - N]
        self.assertIn("mov rax, [rbp -", asm)

    def test_compare_eq(self):
        asm = compile_to_asm("a = 1\nb = 2\nprint(a == b)")
        self.assertRegex(asm, r"cmp e\w\w, e\w\w")
        self.assertIn("sete al", asm)

    def test_compare_neq(self):
        asm = compile_to_asm("a = 1\nb = 2\nprint(a != b)")
        self.assertIn("setne al", asm)

    def test_compare_lt(self):
        asm = compile_to_asm("a = 1\nb = 2\nprint(a < b)")
        self.assertIn("setl al", asm)

    def test_compare_str_eq(self):
        asm = compile_to_asm('print("abc" == "def")')
        self.assertIn("call _strcmp", asm)
        self.assertIn("sete al", asm)

    def test_data_fields(self):
        """Struct field access uses 8-byte offsets."""
        asm = compile_to_asm("data Point { x: int\ny: int }\np = Point(10, 20)\nprint(p.x)")
        self.assertIn("mov rax, [rax + 0]", asm)
        # 8-byte property offsets (0, 8, 16, ...)
        self.assertIn("mov rax, [rax + 0]", asm)  # first field at offset 0

    def test_out_of_bounds_helper(self):
        asm = compile_to_asm("print(1)")
        self.assertIn("_out_of_bounds:", asm)
        self.assertIn('lea rdi, [rip + oob_msg]', asm)
        self.assertIn("call _printf", asm)
        self.assertIn("call _exit", asm)

    def test_concat_strings_helper(self):
        asm = compile_to_asm('print("a" + "b")')
        self.assertIn("_concat_strings:", asm)
        self.assertIn("call _strlen", asm)
        self.assertIn("call _strcat", asm)

    def test_slice_string_helper(self):
        """_slice_string should be emitted with x86_64 prologue and rip-relative refs."""
        asm = compile_to_asm('print("abc"[1:2])')
        self.assertIn("_slice_string:", asm)

    def test_peephole_push_pop_rax(self):
        """push rax / pop rax should be removed by peephole."""
        asm = compile_to_asm("print(99)")
        # Check that no redundant push/pop pair survives
        lines = asm.splitlines()
        for i in range(len(lines) - 1):
            pair = lines[i].strip() + " / " + lines[i+1].strip()
            if pair == "push rax / pop rax":
                self.fail(f"Peephole failed: redundant push/pop found:\n  {lines[i]}\n  {lines[i+1]}")

    def test_return_statement(self):
        asm = compile_to_asm("def add(a, b) { return a + b }\nprint(add(1, 2))")
        self.assertIn("mov rsp, rbp", asm)
        self.assertIn("pop rbp", asm)
        self.assertIn("ret", asm)

    def test_main_receives_argc_argv(self):
        """_main should store rdi/rsi (argc/argv) into the local frame."""
        asm = compile_to_asm('print("hello")')
        self.assertIn("mov [rbp - 8], rdi", asm)
        self.assertIn("mov [rbp - 16], rsi", asm)

    def test_list_literal(self):
        asm = compile_to_asm("print([1, 2, 3])")
        self.assertIn("call _malloc", asm)  # allocate list struct
        self.assertIn("dword ptr [rbx]", asm)   # store length
        self.assertIn("[rbx + 8]", asm)  # data pointer

    def test_dict_literal(self):
        asm = compile_to_asm('d = {"a": 1}\nprint(d.get("a"))')
        self.assertIn("call _dict_new", asm)
        self.assertIn("call _dict_set", asm)
        self.assertIn("call _dict_get", asm)

    def test_len(self):
        asm = compile_to_asm('print(len("abc"))')
        self.assertIn("call _strlen", asm)

    def test_no_32bit_registers_for_pointers(self):
        """64-bit pointers must use 64-bit register loads."""
        asm = compile_to_asm('print("hello")')
        # String access via rax (64-bit pointer), never eax
        self.assertIn("lea rax, [rip + str_", asm)

    def test_no_ebp_esp_in_32bit_mode(self):
        """Must use rbp/rsp not ebp/esp in memory operands."""
        asm = compile_to_asm("x = 1\nprint(x)")
        self.assertNotIn("[ebp +", asm)
        self.assertNotIn("[ebp -", asm)
        self.assertIn("[rbp -", asm)

    def test_data_section_has_str_0(self):
        asm = compile_to_asm('print("hello")')
        data_section = asm.split(".data")[-1]
        self.assertIn("str_0: .asciz", data_section)

    def test_char_strings_table(self):
        asm = compile_to_asm('print("x")')
        self.assertIn("char_strings:", asm)
        self.assertIn(".byte 0", asm)
        self.assertIn(".byte 255", asm)

    def test_forin_loop(self):
        asm = compile_to_asm("for x in [1,2,3] { print(x) }")
        self.assertIn("L_forin", asm)

    def test_free_call(self):
        asm = compile_to_asm("free(0)")
        self.assertIn("call _free", asm)

    def test_nova_function_call(self):
        """Nova function calls should preserve the stack-based convention."""
        asm = compile_to_asm("def foo(x) { print(x) }\nfoo(42)")
        # Function definition
        self.assertIn("_foo:", asm)
        self.assertIn("push rbp", asm)
        self.assertIn("and rsp, -16", asm)
        # Call site: pushes args, calls
        self.assertIn("call _foo", asm)

    def test_ptr_value(self):
        asm = compile_to_asm("x = alloc(4)\np = ptr(x)\nprint(p.value)")
        self.assertIn("mov eax, [rdx]", asm)
        self.assertIn("push rax", asm)

    def test_ptr_addr(self):
        asm = compile_to_asm("x = alloc(4)\np = ptr(x)\nq = p.addr")
        self.assertIn("push rax", asm)

    def test_float_compare(self):
        asm = compile_to_asm("if 1.5 > 2.5 { print(1) }")
        self.assertIn("comisd xmm0, xmm1", asm)
        self.assertIn("seta al", asm)

    def test_printd_debug(self):
        from compiler.backend.x86_64.codegen import X86_64Codegen
        tokens = tokenize("print(1)")
        ast = Parser(tokens).parse()
        codegen = X86_64Codegen(ast, debug_mode=1)
        asm = codegen.generate()
        self.assertIn("debug_prefix", asm)


class TestX86_64DictCodegen(unittest.TestCase):
    """Verify dict literal and method call codegen."""

    def test_dict_literal_empty(self):
        asm = compile_to_asm("d = {}\n")
        self.assertIn("call _dict_new", asm)

    def test_dict_literal_one_pair(self):
        asm = compile_to_asm('d = {"a": 1}\n')
        self.assertIn("call _dict_new", asm)
        self.assertIn("call _dict_set", asm)

    def test_dict_literal_two_pairs(self):
        asm = compile_to_asm('d = {"a": 1, "b": 2}\n')
        self.assertIn("call _dict_new", asm)
        self.assertEqual(asm.count("call _dict_set"), 2)

    def test_dict_method_get(self):
        asm = compile_to_asm('d = {"a": 1}\nx = d.get("a")\n')
        self.assertIn("call _dict_get", asm)

    def test_dict_method_set(self):
        asm = compile_to_asm('d = {}\nd.set("k", 42)\n')
        self.assertIn("call _dict_set", asm)

    def test_dict_method_has(self):
        asm = compile_to_asm('d = {"a": 1}\nd.has("a")\n')
        self.assertIn("call _dict_has", asm)

    def test_dict_method_keys(self):
        asm = compile_to_asm('d = {"a": 1}\nd.keys()\n')
        self.assertIn("call _dict_keys", asm)

    def test_dict_method_values(self):
        asm = compile_to_asm('d = {"a": 1}\nd.values()\n')
        self.assertIn("call _dict_values", asm)

    def test_dict_method_items(self):
        asm = compile_to_asm('d = {"a": 1}\nd.items()\n')
        self.assertIn("call _dict_items", asm)

    def test_dict_method_remove(self):
        asm = compile_to_asm('d = {"a": 1}\nd.remove("a")\n')
        self.assertIn("call _dict_remove", asm)

    def test_dict_len(self):
        asm = compile_to_asm('d = {"a": 1}\nx = len(d)\n')
        self.assertIn("mov eax, [rax]", asm)

    def test_dict_externs(self):
        """All dict runtime functions should be declared as extern."""
        asm = compile_to_asm('d = {"a": 1}\n')
        self.assertIn(".extern _dict_new", asm)
        self.assertIn(".extern _dict_get", asm)
        self.assertIn(".extern _dict_set", asm)
        self.assertIn(".extern _dict_has", asm)
        self.assertIn(".extern _dict_remove", asm)
        self.assertIn(".extern _dict_keys", asm)
        self.assertIn(".extern _dict_values", asm)
        self.assertIn(".extern _dict_items", asm)


if __name__ == "__main__":
    unittest.main()
