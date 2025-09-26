def is_com_ready():
    try:
        import win32com.client
        return True
    except Exception:
        return False