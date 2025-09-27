import pythoncom, win32com.client, sys
from win32com.client import gencache

def list_typelibs():
    # enumerate registered type libs
    tlbs = pythoncom.GetTypeLibCollection()
    for i in range(tlbs.GetCount()):
        tl = tlbs.GetTypeLib(i)
        try:
            name = tl.GetDocumentation(-1)[0]
        except Exception:
            name = "<unknown>"
        print(f"TypeLib index={i} name={name}")
        # try to show attributes
        try:
            attr = tl.GetTypeInfoCount()
            print("  typeinfo count:", attr)
        except Exception:
            pass

def load_and_list(tlb_path):
    tl = pythoncom.LoadTypeLib(tlb_path)
    for i in range(tl.GetTypeInfoCount()):
        ti = tl.GetTypeInfo(i)
        doc = ti.GetDocumentation(-1)
        print(f"TypeInfo[{i}] name={doc[0]}")
        # if this is a coclass, show GUID
        try:
            attr = ti.GetTypeAttr()
            print("  GUID:", attr[0])
        except Exception:
            pass

if __name__ == "__main__":
    print("Registered type libraries (short):")
    list_typelibs()
    print("\nTry auto makepy for likely Interop types (this may create files in gencache):")
    try:
        # if you know the assembly name put it here - gencache will search by progid/class when used later
        pass
    except Exception as e:
        print("makepy error", e)
