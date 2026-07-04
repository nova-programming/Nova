"""Runs type_checker_tests.nv through the Nova pipeline and verifies output.

Test data lives in the .nv file — this runner executes it via the
bootstrap Python compiler and checks results section by section."""
import sys, os, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bootstrap'))

from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeInferer
from vm.compiler import Compiler
from vm.machine import VirtualMachine


NV_FILE = os.path.join(os.path.dirname(__file__), "type_checker_tests.nv")


def run_nova(source):
    tokens = tokenize(source)
    ast = Parser(tokens).parse()
    TypeInferer().infer(ast)
    compiler = Compiler()
    program = compiler.compile(ast)
    vm = VirtualMachine(program)
    vm.run()
    return vm


def _capture_print(source):
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        run_nova(source)
    finally:
        sys.stdout = old
    return buf.getvalue().strip()


def read_sections():
    """Read the .nv file and split it into sections."""
    with open(NV_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    sections = {}
    current_name = None
    current_lines = []
    for line in content.split("\n"):
        if line.startswith("# --- ") and line.endswith(" ---"):
            if current_name:
                sections[current_name] = "\n".join(current_lines)
            current_name = line.replace("# --- ", "").replace(" ---", "").strip()
            current_lines = []
        elif current_name:
            # Skip print("===...===") header lines in each section
            if line.startswith('print("==='):
                continue
            current_lines.append(line)
    if current_name:
        sections[current_name] = "\n".join(current_lines)
    return sections


# --- Test each section ---

def test_number_literal_section():
    sections = read_sections()
    out = _capture_print(sections["NumberLiteral"])
    lines = out.split("\n")
    assert lines[0] == "42", f"got {lines[0]}"
    assert "3.14" in lines[1], f"got {lines[1]}"


def test_string_literal_section():
    sections = read_sections()
    out = _capture_print(sections["StringLiteral"])
    assert out == "hello"


def test_boolean_literal_section():
    sections = read_sections()
    out = _capture_print(sections["BooleanLiteral"])
    lines = out.split("\n")
    assert lines[0] == "True"
    assert lines[1] == "False"


def test_variable_section():
    sections = read_sections()
    out = _capture_print(sections["Variable"])
    assert out == "10"


def test_binop_section():
    sections = read_sections()
    out = _capture_print(sections["BinOp"])
    lines = out.split("\n")
    assert lines[0] == "3"
    assert lines[1] == "7"
    assert lines[2] == "20"


def test_compare_section():
    sections = read_sections()
    out = _capture_print(sections["Compare"])
    lines = out.split("\n")
    assert all(l == "True" for l in lines)


def test_assignment_section():
    sections = read_sections()
    out = _capture_print(sections["Assignment"])
    lines = out.split("\n")
    assert lines[0] == "15"
    assert lines[1] == "3"


def test_function_section():
    sections = read_sections()
    out = _capture_print(sections["Function + Return"])
    assert out == "42"


def test_call_section():
    sections = read_sections()
    out = _capture_print(sections["Call"])
    lines = out.split("\n")
    assert lines[0] == "5"
    assert lines[1] == "42"


def test_ifelse_section():
    sections = read_sections()
    out = _capture_print(sections["IfElse"])
    lines = out.split("\n")
    assert lines[0] == "yes"
    assert lines[1] == "no"


def test_while_section():
    sections = read_sections()
    out = _capture_print(sections["While"])
    lines = out.split("\n")
    assert lines == ["0", "1", "2"]


def test_methodcall_section():
    sections = read_sections()
    out = _capture_print(sections["MethodCall (dict)"])
    lines = out.split("\n")
    assert lines[0] == "1"
    assert lines[1] == "True"
    assert lines[2] == "42"


def test_arrayindex_section():
    sections = read_sections()
    out = _capture_print(sections["ArrayIndex"])
    lines = out.split("\n")
    assert lines == ["10", "20", "30"]


def test_arrayindexassign_section():
    sections = read_sections()
    out = _capture_print(sections["ArrayIndexAssign"])
    lines = out.split("\n")
    assert lines == ["1", "99", "3"]


def test_dict_section():
    sections = read_sections()
    out = _capture_print(sections["DictLiteral"])
    lines = out.split("\n")
    assert lines[0] == "5"
    assert lines[1] == "10"


def test_list_section():
    sections = read_sections()
    out = _capture_print(sections["ListLiteral"])
    assert out == "3"


def test_forloop_section():
    sections = read_sections()
    out = _capture_print(sections["ForLoop"])
    lines = out.split("\n")
    assert lines == ["0", "1", "2", "3", "4"]


def test_len_section():
    sections = read_sections()
    out = _capture_print(sections["Len"])
    lines = out.split("\n")
    assert lines[0] == "5"
    assert lines[1] == "3"


def test_try_section():
    sections = read_sections()
    out = _capture_print(sections["TRY + THROW"])
    lines = out.split("\n")
    assert lines[0] == "1"
    assert lines[1] == "99"


def test_full_file():
    """Run entire .nv file and verify all section headers appear."""
    with open(NV_FILE, "r", encoding="utf-8") as f:
        source = f.read()
    out = _capture_print(source)
    lines = out.split("\n")
    assert "=== NUMBER ===" in out
    assert "=== STRING ===" in out
    assert "=== BOOLEAN ===" in out
    assert "=== VARIABLE ===" in out
    assert "=== BINOP ===" in out
    assert "=== COMPARE ===" in out
    assert "=== ASSIGNMENT ===" in out
    assert "=== FUNCTION ===" in out
    assert "=== CALL ===" in out
    assert "=== IFELSE ===" in out
    assert "=== WHILE ===" in out
    assert "=== METHODCALL ===" in out
    assert "=== ARRAYINDEX ===" in out
    assert "=== ARRAYINDEXASSIGN ===" in out
    assert "=== DICT ===" in out
    assert "=== LIST ===" in out
    assert "=== FORLOOP ===" in out
    assert "=== LEN ===" in out
    assert "=== TRY ===" in out
