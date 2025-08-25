import os
import time

def format_size(bytes_size):
    """Format size in bytes into a human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.2f} PB"

def get_folder_stats(folder):
    """Walk the folder and calculate total size and file count."""
    total_size = 0
    file_count = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        file_count += len(filenames)
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            # Use os.path.getsize() to get file size; ignore if file does not exist anymore.
            try:
                total_size += os.path.getsize(file_path)
            except OSError:
                pass
    return total_size, file_count

def list_folders():
    """Return a list of folders in the current directory."""
    folders = [f for f in os.listdir('.') if os.path.isdir(f)]
    return folders

def main():
    folders = list_folders()
    if not folders:
        print("No subfolders found in the current directory.")
        return

    print("Folders in the current directory:")
    for idx, folder in enumerate(folders, 1):
        print(f"{idx}. {folder}")

    try:
        choice = int(input("\nChoose a folder by number: "))
        if choice < 1 or choice > len(folders):
            print("Invalid selection.")
            return
    except ValueError:
        print("Please enter a valid number.")
        return

    selected_folder = folders[choice - 1]
    print(f"\nMonitoring folder: {selected_folder}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            total_size, file_count = get_folder_stats(selected_folder)
            # Clear terminal screen
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"Monitoring folder: {selected_folder}")
            print("-" * 40)
            print(f"Total files: {file_count}")
            print(f"Total size: {format_size(total_size)}")
            print("-" * 40)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == '__main__':
    main()