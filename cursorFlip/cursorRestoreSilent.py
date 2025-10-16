import os
import shutil
import winreg
import ctypes

def refresh_cursors():
    """Force Windows to reload the cursor scheme without restarting."""
    SPI_SETCURSORS = 0x0057
    ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)

# Define the registry keys and their default values.
registry_defaults = {
    "Arrow": r"C:\Windows\Cursors\aero_arrow.cur",
    "Hand": r"C:\Windows\Cursors\aero_link.cur",
    "AppStarting": r"C:\Windows\Cursors\aero_working.ani"
}

# List of our custom cursor file names.
cursor_files = {"aero_arrow.cur", "aero_link.cur", "aero_working.ani"}

def update_registry(key_name, new_path):
    """
    Update the registry under HKEY_CURRENT_USER\Control Panel\Cursors
    for the given key_name to the new_path.
    """
    try:
        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Control Panel\\Cursors",  # double backslash to avoid escape warnings
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(reg_key, key_name, 0, winreg.REG_SZ, new_path)
        winreg.CloseKey(reg_key)
        return True, ""
    except Exception as e:
        return False, f"Error updating registry for key '{key_name}': {e}"

def delete_cursor_files(cursors_dir):
    """
    Checks the contents of the cursors_dir. If it only contains the three
    custom cursor files, delete the entire directory; otherwise, only delete
    those files.
    """
    try:
        if not os.path.isdir(cursors_dir):
            return True, ""
        
        entries = os.listdir(cursors_dir)
        files_in_dir = {entry for entry in entries if os.path.isfile(os.path.join(cursors_dir, entry))}
        
        if files_in_dir == cursor_files:
            shutil.rmtree(cursors_dir)
        else:
            for file in cursor_files:
                file_path = os.path.join(cursors_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        return True, ""
    except Exception as e:
        return False, f"Error deleting cursor files: {e}"

def main():
    errors = []
    
    user_profile = os.environ.get("USERPROFILE")
    if not user_profile:
        return

    documents_path = os.path.join(user_profile, "Documents")
    cursors_dir = os.path.join(documents_path, "Cursors")
    
    try:
        os.makedirs(cursors_dir, exist_ok=True)
    except Exception as e:
        return

    success, msg = delete_cursor_files(cursors_dir)
    if not success:
        errors.append(msg)
    
    for key, default_path in registry_defaults.items():
        success, msg = update_registry(key, default_path)
        if not success:
            errors.append(msg)
    
    if not errors:
        refresh_cursors()

if __name__ == "__main__":
    main()