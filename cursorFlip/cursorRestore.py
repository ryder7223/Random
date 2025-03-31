import os
import shutil
import winreg
import ctypes

def refresh_cursors():
    """Force Windows to reload the cursor scheme without restarting."""
    SPI_SETCURSORS = 0x0057
    ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)
    print("Cursor refreshed.")

if __name__ == "__main__":
    refresh_cursors()

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
            r"Control Panel\Cursors",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(reg_key, key_name, 0, winreg.REG_SZ, new_path)
        winreg.CloseKey(reg_key)
        print(f"Registry key '{key_name}' reset to: {new_path}")
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
            print("Cursors folder does not exist; nothing to delete.")
            return True, ""
        
        # List the contents of the directory (files and subdirectories).
        entries = os.listdir(cursors_dir)
        # Filter only files
        files_in_dir = {entry for entry in entries if os.path.isfile(os.path.join(cursors_dir, entry))}
        
        if files_in_dir == cursor_files:
            # Only our files are present; delete the entire folder.
            shutil.rmtree(cursors_dir)
            print(f"Deleted the entire folder: {cursors_dir}")
        else:
            # Delete only the custom cursor files if they exist.
            for file in cursor_files:
                file_path = os.path.join(cursors_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"Deleted file: {file_path}")
        return True, ""
    except Exception as e:
        return False, f"Error deleting cursor files: {e}"

def main():
    errors = []
    
    # Determine the current user's Documents\Cursors folder.
    user_profile = os.environ.get("USERPROFILE")
    if not user_profile:
        print("Cannot determine user profile directory.")
        input("Enter to exit...")
        return

    documents_path = os.path.join(user_profile, "Documents")
    cursors_dir = os.path.join(documents_path, "Cursors")
    
    # Delete custom cursor files (or the folder if appropriate)
    success, msg = delete_cursor_files(cursors_dir)
    if not success:
        errors.append(msg)
    
    # Reset registry keys to default paths.
    for key, default_path in registry_defaults.items():
        success, msg = update_registry(key, default_path)
        if not success:
            errors.append(msg)
    
    # Final output.
    if errors:
        print("The following error(s) occurred:")
        for error in errors:
            print(" -", error)
    else:
        print("successful")
        refresh_cursors()
    
    input("Enter to exit...")

if __name__ == "__main__":
    main()