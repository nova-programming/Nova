import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "tools")))
import nova_py

mod = nova_py.load("test_bridge.nv")

print("add(5, 7) =", mod.add(5, 7))
print("greet('World') =", mod.greet("World"))
