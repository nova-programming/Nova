import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bootstrap'))
from lexer.tokenizer import tokenize
# Nova has no triple-quote strings; use a normal string literal
tokens = tokenize('s = "hello"')
for t in tokens:
    print(t)
