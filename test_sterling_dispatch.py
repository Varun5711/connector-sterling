# test_sterling_dispatch.py
import pythoncom, win32com.client, traceback, sys

pythoncom.CoInitialize()
candidates = [
    "Sterling.STIAccountControl",
    "Sterling.STIOrder",
    "SterlingLib.STIAccountControl",
    "SterlingLib.STIOrder",
    "StiGuiDll.StiGui",
    "StiMsgDll.StiMsg",
    "Interop.SterlingLib.STIOrder",  # try possible .NET interop names
]

for p in candidates:
    try:
        print("Trying:", p)
        obj = win32com.client.Dispatch(p)
        print("DISPATCH OK:", p, "->", obj)
    except Exception as e:
        print("DISPATCH FAIL:", p, ":", repr(e))
        traceback.print_exc()
        print("-" * 60)
sys.stdout.flush()
pythoncom.CoUninitialize()
