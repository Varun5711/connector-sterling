# test_sterling_wrapper_reflection.py
import clr, os
from System import Activator
from System import Reflection

dll_path = r"C:\Users\Administrator\Desktop\connector-sterling\SterlingWrapper\SterlingWrapper.dll"
if not os.path.exists(dll_path):
    raise SystemExit("DLL not found at: " + dll_path)

# Load assembly
asm = Reflection.Assembly.LoadFile(dll_path)
print("Loaded assembly:", asm.FullName)

# List types in DLL
types = asm.GetTypes()
print("Types in assembly:")
for t in types:
    print(" -", t.FullName)

# Locate Connector type
type_name = "SterlingWrapper.Connector"
ConnectorType = asm.GetType(type_name)
if ConnectorType is None:
    print("Could not find type:", type_name)
    candidates = [t for t in types if "Connector" in t.FullName]
    print("Connector-like candidates:", [c.FullName for c in candidates])
    raise SystemExit("Connector type not found.")

print("Connector type found:", ConnectorType.FullName)

# Instantiate Connector
instance = Activator.CreateInstance(ConnectorType)
print("Instance created:", instance, "type:", instance.GetType().FullName)

# ---------------------------
# Test method calls (safe ones)
# ---------------------------
try:
    # Test GetOrders (should return an int count of open orders)
    get_orders = getattr(instance, "GetOrders", None)
    if callable(get_orders):
        print("Calling GetOrders() ...")
        print("GetOrders ->", get_orders())
    else:
        print("GetOrders not available")

    # Test Position with demo account
    example_account = "DEMOJKST012"
    example_symbol = "AAPL"

    pos_method = getattr(instance, "Position", None)
    if callable(pos_method):
        print(f"Calling Position({example_account}, {example_symbol}) ...")
        print("Position ->", pos_method(example_account, example_symbol))
    else:
        print("Position method not available")

except Exception as e:
    import traceback
    traceback.print_exc()
    print("Method invocation failed:", e)
