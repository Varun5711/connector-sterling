import clr
from pathlib import Path

DLL_PATH = Path(__file__).resolve() / "SterlingWrapper" / "SterlingWrapper.dll"
clr.AddReference(str(DLL_PATH))

import SterlingWrapper
print("dir(SterlingWrapper):", dir(SterlingWrapper))

from SterlingWrapper import Connector
c = Connector()
print("Instance created:", c)
