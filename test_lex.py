import sys
sys.path.insert(0, 'bootstrap')
from lexer.tokenizer import tokenize
tokens = tokenize('s = """hello"""')
for t in tokens:
    print(t)
