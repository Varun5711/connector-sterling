import clr
from pathlib import Path
from System.Reflection import Assembly

DLL_PATH = Path(__file__).resolve().parent / "SterlingWrapper" / "SterlingWrapper.dll"
print(f"Loading {DLL_PATH}")
asm = Assembly.LoadFile(str(DLL_PATH))

for t in asm.GetTypes():
    print(t.FullName)
