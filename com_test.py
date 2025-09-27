import pythoncom, win32com.client, traceback

pythoncom.CoInitialize()
candidates = [
    "Sterling.STIAccountControl",
    "Sterling.STIOrder",
    "SterlingLib.STIOrder",
    "SterlingLib.STIAccountControl",
    "StiGuiDll.StiGui",   # guesses; vendor names vary
]

for p in candidates:
    try:
        obj = win32com.client.Dispatch(p)
        print("DISPATCH OK:", p, "->", obj)
    except Exception as e:
        print("DISPATCH FAIL:", p, ":", e)
        traceback.print_exc()

pythoncom.CoUninitialize()
