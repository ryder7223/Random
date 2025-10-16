import os
import sys

def get_dir_size(path: str) -> int:
    """Return total size of all files under the given directory."""
    total = 0
    for root, _, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                fp = os.path.join(root, f)
                if not os.path.islink(fp):  # avoid symlinks
                    total += os.path.getsize(fp)
            except (OSError, FileNotFoundError):
                pass
    return total

def scan_directories(base_dir: str):
    """Scan all subdirectories and return their sizes and depths."""
    folder_stats = []
    count = 0
    for root, dirs, _ in os.walk(base_dir):
        depth = root.count(os.sep) - base_dir.count(os.sep)
        size = get_dir_size(root)
        folder_stats.append((root, size, depth))
        count += 1
        if count % 10 == 0:  # print progress every 10 folders
            print(f"Scanned {count} folders...", end="\r", file=sys.stderr)
    print(f"Scanning complete. {count} folders processed.", file=sys.stderr)
    return folder_stats

def rank_folders(folder_stats, depth_weight: float = 1.5):
    """
    Rank folders by a weighted score = size * (1 + depth * depth_weight).
    Deeper folders are ranked higher for the same size.
    """
    ranked = []
    for path, size, depth in folder_stats:
        score = size * (1 + depth * depth_weight)
        ranked.append((path, size, depth, score))
    return sorted(ranked, key=lambda x: x[3], reverse=True)

def format_size(num_bytes: int) -> str:
    """Convert bytes into human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} PB"

if __name__ == "__main__":
    base = os.getcwd()  # run in current directory
    print(f"Scanning directory: {base}\n", file=sys.stderr)
    stats = scan_directories(base)
    ranked = rank_folders(stats)

    # Determine max path length for clean alignment
    max_path_len = max(len(path) for path, _, _, _ in ranked[:20])

    # Print header
    print(f"{'Folder':<{max_path_len}}  {'Size':>12} {'Depth':>5}")
    print("=" * (max_path_len + 22))

    # Print top results
    for path, size, depth, score in ranked[:20]:  # top 20 results
        print(f"{path:<{max_path_len}}  {format_size(size):>12} {depth:>5}")