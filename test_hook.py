import sys
import os
sys.path.insert(0, os.path.abspath("tools"))
import nova_py

# Now we can just import .nv files directly!
import test_bridge

print("Custom Import Hook Success!")
print("add(10, 20) =", test_bridge.add(10, 20))
print("greet('Universe') =", test_bridge.greet("Universe"))

