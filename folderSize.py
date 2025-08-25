import os
from pathlib import Path

def get_folder_size(folder: Path) -> int:
    """Recursively calculate the total size of all files in a folder."""
    total_size = 0
    for path in folder.rglob('*'):
        if path.is_file():
            try:
                total_size += path.stat().st_size
            except OSError:
                continue  # Skip files that can't be accessed
    return total_size

def truncate_name(name: str, max_length: int = 40) -> str:
    """Truncate folder name if it exceeds max_length, appending '...'."""
    if len(name) > max_length:
        return name[:max_length - 3] + "..."
    return name

def list_folders_sorted_by_size(base_path: Path):
    folders = [item for item in base_path.iterdir() if item.is_dir()]
    folder_sizes = [(folder, get_folder_size(folder)) for folder in folders]
    folder_sizes.sort(key=lambda x: x[1], reverse=True)

    total_size = sum(size for _, size in folder_sizes)

    print(f"{'Folder':<40} {'Size (MB)':>12}")
    print("-" * 55)
    for folder, size in folder_sizes:
        name_display = truncate_name(folder.name)
        print(f"{name_display:<40} {size / (1024 * 1024):>12.2f}")
    
    print("-" * 55)
    print(f"{'Total':<40} {total_size / (1024 * 1024):>12.2f}")

if __name__ == "__main__":
    current_directory = Path.cwd()
    list_folders_sorted_by_size(current_directory)
    input()