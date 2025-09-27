# inspect_dotnet_types.py
import clr, sys, os
import System
from System import Reflection

paths = [
    r"C:\Program Files\Sti\Excel RTD Add-in\Interop.SterlingLib.dll",
    r"C:\Program Files\Sti\SterlingTraderPro\SterlingWrapper.dll",  # if present
    r"C:\Users\Administrator\Desktop\connector-sterling\SterlingWrapper\SterlingWrapper.dll"  # your local copy
]

found = []
for p in paths:
    if os.path.exists(p):
        try:
            asm = Reflection.Assembly.LoadFile(p)
            print(f"\nLoaded assembly: {p}")
            types = asm.GetTypes()
            for t in types:
                print(f"TYPE: {t.FullName}")
                # list public methods (non-special)
                methods = [m for m in t.GetMethods() if not m.IsSpecialName and m.IsPublic]
                if methods:
                    for m in methods:
                        sig = f"{m.ReturnType.Name} {m.Name}({', '.join([param.ParameterType.Name + ' ' + param.Name for param in m.GetParameters()])})"
                        print(f"  - {sig}")
            found.append(p)
        except Exception as e:
            print(f"Failed to load {p}: {e}")
    else:
        print(f"Not found: {p}")

if not found:
    print("\nNo assemblies found at those paths — update paths variable to point to your DLLs.")
