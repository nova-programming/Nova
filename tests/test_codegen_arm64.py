"""Tests for Arm64Codegen — verifies AArch64 assembly output for Apple Silicon."""
import sys, os, unittest

BOOTSTRAP = os.path.join(os.path.dirname(__file__), "..", "bootstrap")
sys.path.insert(0, BOOTSTRAP)
from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeInferer, StaticTypeError
from nova_ast.nodes import *


def compile_to_asm(source):
    """Tokenize, parse, type-check, and generate ARM64 assembly from Nova source."""
    tokens = tokenize(source)
    ast = Parser(tokens).parse()
    try:
        TypeInferer().infer(ast)
    except StaticTypeError:
        pass
    from compiler.backend.arm64.codegen import Arm64Codegen
    module_names = set()
    from nova_ast.nodes import Import
    for node in ast:
        if isinstance(node, Import):
            module_names.add(node.module)
    codegen = Arm64Codegen(ast, module_names=module_names)
    return codegen.generate()


class TestArm64CodegenOutput(unittest.TestCase):
    """Verify structural properties of the generated ARM64 assembly."""

    def test_headers_and_externs(self):
        """Verify headers, .global _main, and extern declarations."""
        asm = compile_to_asm('print("hello")')
        self.assertIn(".text", asm)
        self.assertIn(".align 2", asm)
        self.assertIn(".global _main", asm)
        self.assertIn(".extern _printf", asm)
        self.assertIn(".extern _malloc", asm)
        self.assertIn(".extern _free", asm)
        self.assertIn(".extern _exit", asm)

    def test_main_prologue_arm64(self):
        """_main uses fp-based frame: stp fp/lr then mov fp,sp"""
        asm = compile_to_asm('print("hello")')
        self.assertIn("stp fp, lr, [sp, #-16]!", asm)
        self.assertIn("mov fp, sp", asm)
        self.assertIn("sub sp, sp, #", asm)

    def test_string_literal_pic(self):
        """String literals must use ADRP/ADD @PAGE/@PAGEOFF (PIC)."""
        asm = compile_to_asm('print("hello")')
        adrp_count = asm.count("adrp x0, str_")
        add_count = asm.count("add x0, x0, str_")
        self.assertGreater(adrp_count, 0, "Expected ADRP for string literals")
        self.assertGreater(add_count, 0, "Expected ADD @PAGEOFF for string literals")

    def test_printf_call_arm64(self):
        """printf is called with format in x0; no x0 clobber (x0 aliases x0 on ARM64)."""
        asm = compile_to_asm('print("hello")')
        self.assertIn("adrp x0, fmt_str@PAGE", asm)
        self.assertIn("add x0, x0, fmt_str@PAGEOFF", asm)
        self.assertIn("ldr x1, [sp], #16", asm)
        self.assertIn("bl _printf", asm)
        # Verify x0 is NOT set between loading fmt_str and calling printf
        # (mov x0 clears x0, destroying the format string pointer)
        idx_fmt = asm.index("add x0, x0, fmt_str@PAGEOFF")
        idx_call = asm.index("bl _printf")
        between = asm[idx_fmt:idx_call]
        self.assertNotIn("mov x0, #0", between)

    def test_print_int(self):
        """Print integer uses fmt_int."""
        asm = compile_to_asm("print(42)")
        self.assertIn("adrp x0, fmt_int@PAGE", asm)
        self.assertIn("bl _printf", asm)

    def test_print_float(self):
        """Print float uses fmt_float."""
        asm = compile_to_asm("print(3.14)")
        self.assertIn("adrp x0, fmt_float@PAGE", asm)

    def test_binary_ops(self):
        """Binary ops should use x-registers, str to stack."""
        asm = compile_to_asm("a = 10\nb = 20\nprint(a + b)")
        self.assertIn("add x0, x0, x1", asm)
        self.assertIn("str x0, [sp, #-16]!", asm)

    def test_binary_sub(self):
        asm = compile_to_asm("a = 10\nb = 5\nprint(a - b)")
        self.assertIn("sub x0, x0, x1", asm)

    def test_binary_mul(self):
        asm = compile_to_asm("a = 10\nb = 5\nprint(a * b)")
        self.assertIn("mul x0, x0, x1", asm)

    def test_binary_div_sdiv(self):
        """Division uses sdiv for signed 64-bit."""
        asm = compile_to_asm("a = 100\nb = 3\nprint(a / b)")
        self.assertIn("sdiv x0, x0, x1", asm)

    def test_binary_mod(self):
        """Modulo uses sdiv + msub."""
        asm = compile_to_asm("a = 100\nb = 3\nprint(a % b)")
        self.assertIn("sdiv", asm)
        self.assertIn("msub x0, x2, x1, x0", asm)

    def test_binary_bitwise_and(self):
        asm = compile_to_asm("a = 12\nb = 6\nprint(a & b)")
        self.assertIn("and x0, x0, x1", asm)

    def test_unary_neg(self):
        asm = compile_to_asm("print(-5)")
        self.assertIn("neg x0, x0", asm)

    def test_unary_not(self):
        asm = compile_to_asm("print(not 0)")
        self.assertIn("cset x0, eq", asm)

    def test_if_else(self):
        asm = compile_to_asm("if 1 { print(1) } else { print(0) }")
        # peephole replaces cmp+b.eq with cbz
        self.assertIn("cbz x0, L_else", asm)
        self.assertIn("b L_end", asm)
        self.assertIn("L_else", asm)
        self.assertIn("L_end", asm)

    def test_while_loop(self):
        asm = compile_to_asm("while 0 { print(1) }")
        self.assertIn("L_loop", asm)
        self.assertIn("L_loop_end", asm)
        self.assertIn("b L_loop", asm)

    def test_for_loop(self):
        asm = compile_to_asm("for x = 0 to 10 { print(x) }")
        self.assertIn("L_for", asm)
        self.assertIn("L_for_end", asm)
        self.assertIn("cmp x0, x1", asm)

    def test_forin_loop(self):
        asm = compile_to_asm("for x in [1,2,3] { print(x) }")
        self.assertIn("L_forin", asm)

    def test_variable_assignment_and_load(self):
        asm = compile_to_asm("x = 42\nprint(x)")
        # peephole eliminates dead str/ldr push/pop pair
        self.assertIn("str x0, [sp, #", asm)
        self.assertIn("ldr x0, [sp, #", asm)

    def test_compare_eq(self):
        asm = compile_to_asm("a = 1\nb = 2\nprint(a == b)")
        self.assertIn("cmp x0, x1", asm)
        self.assertIn("cset x0, eq", asm)

    def test_compare_neq(self):
        asm = compile_to_asm("a = 1\nb = 2\nprint(a != b)")
        self.assertIn("cset x0, ne", asm)

    def test_compare_lt(self):
        asm = compile_to_asm("a = 1\nb = 2\nprint(a < b)")
        self.assertIn("cset x0, lt", asm)

    def test_compare_str_eq(self):
        asm = compile_to_asm('print("abc" == "def")')
        self.assertIn("bl _strcmp", asm)
        self.assertRegex(asm, r'cset x\d+, eq')

    def test_compare_float_eq(self):
        asm = compile_to_asm("print(1.5 == 2.5)")
        self.assertIn("fcmp d0, d1", asm)
        self.assertRegex(asm, r'cset x\d+, eq')

    def test_data_fields(self):
        """Struct field access uses 8-byte offsets on ARM64."""
        asm = compile_to_asm("data Point { x: int\ny: int }\np = Point(10, 20)\nprint(p.x)\nprint(p.y)")
        self.assertIn("ldr x0, [x0, #0]", asm)
        self.assertIn("ldr x0, [x0, #8]", asm)

    def test_out_of_bounds_helper(self):
        asm = compile_to_asm("print(1)")
        self.assertNotIn("_out_of_bounds:", asm)
        self.assertIn(".extern _oob_file_ptr", asm)
        self.assertIn(".extern _oob_line", asm)
        self.assertIn("source_path_str:", asm)

    def test_concat_strings_helper(self):
        asm = compile_to_asm('print("a" + "b")')
        self.assertIn("_concat_strings:", asm)
        self.assertIn("bl _strlen", asm)
        self.assertIn("bl _strcat", asm)

    def test_slice_string_helper(self):
        asm = compile_to_asm('print("abc"[1:2])')
        self.assertIn("bl _str_sub", asm)

    def test_return_statement(self):
        asm = compile_to_asm("def add(a, b) { return a + b }\nprint(add(1, 2))")
        # Peephole removes dead str x0/[sp,#-16]! / ldr x0/[sp],#16 pair.
        # Second arg remains: ldr x1, [sp], #16 pops 2 into x1, x0=1 from movz.
        self.assertIn("ldr x1, [sp], #16", asm)
        self.assertNotIn("mov sp, fp", asm)
        self.assertIn("ldp fp, lr, [sp], #16", asm)
        self.assertIn("ret", asm)

    def test_main_receives_argc_argv(self):
        """_main should store x0/x1 (argc/argv) into the local frame."""
        asm = compile_to_asm('print("hello")')
        self.assertIn("str x0, [sp, #", asm)
        self.assertIn("str x1, [sp, #", asm)

    def test_list_literal(self):
        asm = compile_to_asm("print([1, 2, 3])")
        self.assertGreaterEqual(asm.count("bl _malloc"), 2)
        self.assertIn("str w3, [x2]", asm)
        self.assertIn("str w3, [x2, #4]", asm)
        self.assertIn("str x1, [x2, #8]", asm)
        self.assertIn("str x0, [x1, #0]", asm)
        self.assertIn("str x0, [x1, #8]", asm)

    def test_len_string(self):
        asm = compile_to_asm('print(len("abc"))')
        self.assertIn("bl _strlen", asm)

    def test_len_list(self):
        asm = compile_to_asm("print(len([1,2,3]))")
        self.assertIn("ldr w0, [x0]", asm)

    def test_no_x86_64_registers(self):
        """Must not contain x86_64 register names."""
        asm = compile_to_asm("print(1)")
        self.assertNotIn("push rbp", asm)
        self.assertNotIn("pop rbp", asm)
        self.assertNotIn("mov rbp, rsp", asm)
        self.assertNotIn("[rbp -", asm)

    def test_data_section_has_str_0(self):
        asm = compile_to_asm('print("hello")')
        data_section = asm.split(".data")[-1]
        self.assertIn("str_0: .asciz", data_section)

    def test_char_strings_table(self):
        asm = compile_to_asm('print("x")')
        self.assertIn("char_strings:", asm)
        self.assertIn(".byte 0", asm)
        self.assertIn(".byte 255", asm)

    def test_free_call(self):
        asm = compile_to_asm("free(0)")
        self.assertIn("bl _free", asm)

    def test_nova_function_call(self):
        """Nova function calls should use ARM64 calling convention (x0-x7)."""
        asm = compile_to_asm("def foo(x) { print(x) }\nfoo(42)")
        self.assertIn("_foo:", asm)
        self.assertIn("stp fp, lr, [sp, #-16]!", asm)
        self.assertIn("bl _foo", asm)

    def test_float_arithmetic(self):
        asm = compile_to_asm("a = 1.5\nb = 2.5\nprint(a + b)")
        self.assertIn("fadd d0, d0, d1", asm)

    def test_float_sub(self):
        asm = compile_to_asm("a = 5.5\nb = 1.5\nprint(a - b)")
        self.assertIn("fsub d0, d0, d1", asm)

    def test_float_mul(self):
        asm = compile_to_asm("a = 3.0\nb = 4.0\nprint(a * b)")
        self.assertIn("fmul d0, d0, d1", asm)

    def test_float_div(self):
        asm = compile_to_asm("a = 10.0\nb = 2.0\nprint(a / b)")
        self.assertIn("fdiv d0, d0, d1", asm)

    def test_float_compare_gt(self):
        asm = compile_to_asm("if 1.5 > 2.5 { print(1) }")
        self.assertIn("fcmp d0, d1", asm)

    def test_concat_strings_helper_full(self):
        """Concat strings helper is emitted as a named label."""
        asm = compile_to_asm('print("test")')
        self.assertIn("_concat_strings:", asm)

    def test_forloop_downto(self):
        asm = compile_to_asm("for x = 10 downto 0 { print(x) }")
        self.assertIn("b.lt", asm)

    def test_break_continue(self):
        asm = compile_to_asm("while 1 { break }\nwhile 1 { continue }")
        self.assertIn("b L_loop_end", asm)
        self.assertIn("b L_loop", asm)

    def test_str_convert(self):
        asm = compile_to_asm('print(str(42))')
        self.assertIn("bl _sprintf", asm)

    def test_alloc_free(self):
        asm = compile_to_asm("p = alloc(16)\nfree(p)")
        self.assertIn("bl _malloc", asm)
        self.assertIn("bl _free", asm)

    def test_binary_shift_left(self):
        asm = compile_to_asm("a = 1\nb = 3\nprint(a << b)")
        self.assertIn("lsl x0, x0, x1", asm)

    def test_binary_shift_right(self):
        asm = compile_to_asm("a = 8\nb = 2\nprint(a >> b)")
        self.assertIn("asr x0, x0, x1", asm)

    def test_and_short_circuit(self):
        asm = compile_to_asm("print(1 and 0)")
        self.assertIn("and_false", asm)
        self.assertIn("and_end", asm)

    def test_or_short_circuit(self):
        asm = compile_to_asm("print(1 or 0)")
        self.assertIn("or_true", asm)
        self.assertIn("or_end", asm)

    def test_printd_debug(self):
        from compiler.backend.arm64.codegen import Arm64Codegen
        tokens = tokenize("print(1)")
        ast = Parser(tokens).parse()
        codegen = Arm64Codegen(ast, debug_mode=1)
        asm = codegen.generate()
        self.assertIn("debug_prefix", asm)

    def test_ptr_value(self):
        asm = compile_to_asm("x = alloc(4)\np = ptr(x)\nprint(p.value)")
        self.assertIn("ldr x0, [x0]", asm)

    def test_ptr_addr(self):
        asm = compile_to_asm("x = alloc(4)\np = ptr(x)\nq = p.addr")
        self.assertIn("str x0", asm)


class TestArm64DictCodegen(unittest.TestCase):
    """Verify dict literal and method call codegen on ARM64."""

    def test_dict_literal_empty(self):
        asm = compile_to_asm("d = {}\n")
        self.assertIn("bl _dict_new", asm)

    def test_dict_literal_one_pair(self):
        asm = compile_to_asm('d = {"a": 1}\n')
        self.assertIn("bl _dict_new", asm)
        self.assertIn("bl _dict_set", asm)

    def test_dict_literal_two_pairs(self):
        asm = compile_to_asm('d = {"a": 1, "b": 2}\n')
        self.assertIn("bl _dict_new", asm)
        self.assertEqual(asm.count("bl _dict_set"), 2)

    def test_dict_method_get(self):
        asm = compile_to_asm('d = {"a": 1}\nx = d.get("a")\n')
        self.assertIn("bl _dict_get", asm)

    def test_dict_method_set(self):
        asm = compile_to_asm('d = {}\nd.set("k", 42)\n')
        self.assertIn("bl _dict_set", asm)

    def test_dict_method_has(self):
        asm = compile_to_asm('d = {"a": 1}\nd.has("a")\n')
        self.assertIn("bl _dict_has", asm)

    def test_dict_method_keys(self):
        asm = compile_to_asm('d = {"a": 1}\nd.keys()\n')
        self.assertIn("bl _dict_keys", asm)

    def test_dict_method_values(self):
        asm = compile_to_asm('d = {"a": 1}\nd.values()\n')
        self.assertIn("bl _dict_values", asm)

    def test_dict_method_items(self):
        asm = compile_to_asm('d = {"a": 1}\nd.items()\n')
        self.assertIn("bl _dict_items", asm)

    def test_dict_method_remove(self):
        asm = compile_to_asm('d = {"a": 1}\nd.remove("a")\n')
        self.assertIn("bl _dict_remove", asm)

    def test_dict_len(self):
        asm = compile_to_asm('d = {"a": 1}\nx = len(d)\n')
        self.assertIn("ldr w0, [x0]", asm)

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
        self.assertIn(".extern _dict_free", asm)


if __name__ == "__main__":
    unittest.main()
