from nova.lexer.tokenizer import tokenize
from nova.parser.parser import Parser
from nova.codegen.generator import CodeGen
import os


class ModuleLoader:
    def __init__(self):
        self.cache = {}

    def load(self, name):
        if name in self.cache:
            return self.cache[name]

        path = f"{name}.nv"
        if not os.path.exists(path):
            path = f"{name}.nova"
            if not os.path.exists(path):
                raise FileNotFoundError(f"Module '{name}' not found")

        with open(path, "r", encoding="utf-8") as f:
            source = f.read()

        tokens = tokenize(source)
        ast = Parser(tokens).parse()

        codegen = CodeGen()
        codegen.module_name = name
        codegen.generate(ast, is_module=True)

        exports = codegen.exports.copy()

        self.cache[name] = exports
        return exports