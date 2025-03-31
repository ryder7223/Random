import ctypes

def refresh_cursors():
    """Force Windows to reload the cursor scheme without restarting."""
    SPI_SETCURSORS = 0x0057
    ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)
    print("Cursor refreshed.")

if __name__ == "__main__":
    refresh_cursors()