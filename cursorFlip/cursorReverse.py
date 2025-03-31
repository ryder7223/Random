import os
import requests
import winreg
import urllib3
import ctypes

def refresh_cursors():
    """Force Windows to reload the cursor scheme without restarting."""
    SPI_SETCURSORS = 0x0057
    ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)
    print("Cursor refreshed.")

if __name__ == "__main__":
    refresh_cursors()

# Disable insecure request warnings when SSL verification is disabled.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Define the URLs and corresponding registry keys.
files_to_download = {
    "Arrow": {
        "url": "https://github.com/ryder7223/Random/raw/refs/heads/main/Cursors/aero_arrow.cur",
        "filename": "aero_arrow.cur"
    },
    "Hand": {
        "url": "https://github.com/ryder7223/Random/raw/refs/heads/main/Cursors/aero_link.cur",
        "filename": "aero_link.cur"
    },
    "AppStarting": {
        "url": "https://github.com/ryder7223/Random/raw/refs/heads/main/Cursors/aero_working.ani",
        "filename": "aero_working.ani"
    }
}

def download_file(url, save_path):
    """Download a file from a URL and save it to the provided path with SSL verification disabled."""
    try:
        response = requests.get(url, stream=True, verify=False)
        response.raise_for_status()  # Raise an exception for HTTP errors.
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded: {save_path}")
        return True, ""
    except Exception as e:
        return False, f"Error downloading {url}: {e}"

def update_registry(key_name, file_path):
    """
    Update the registry under:
      HKEY_CURRENT_USER\Control Panel\Cursors
    for the given key_name to point to file_path.
    """
    try:
        registry_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Cursors",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(registry_key, key_name, 0, winreg.REG_SZ, file_path)
        winreg.CloseKey(registry_key)
        print(f"Registry key '{key_name}' updated to: {file_path}")
        return True, ""
    except Exception as e:
        return False, f"Error updating registry for key '{key_name}': {e}"

def main():
    errors = []

    # Determine the current user's Documents folder.
    user_profile = os.environ.get("USERPROFILE")
    if not user_profile:
        print("Cannot determine user profile directory.")
        input("Enter to exit...")
        return

    documents_path = os.path.join(user_profile, "Documents")
    cursors_dir = os.path.join(documents_path, "Cursors")
    
    # Create the Cursors directory if it doesn't exist.
    try:
        os.makedirs(cursors_dir, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {cursors_dir}: {e}")
        input("Enter to exit...")
        return

    downloaded_files = {}

    # Check each file if it exists; download missing files.
    for reg_key, info in files_to_download.items():
        file_path = os.path.join(cursors_dir, info["filename"])
        if os.path.isfile(file_path):
            print(f"File already exists: {file_path}")
        else:
            success, msg = download_file(info["url"], file_path)
            if not success:
                errors.append(msg)
        downloaded_files[reg_key] = file_path

    # Update the registry for each file.
    for reg_key, file_path in downloaded_files.items():
        success, msg = update_registry(reg_key, file_path)
        if not success:
            errors.append(msg)

    # Final output based on errors collected.
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