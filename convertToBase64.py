#!/usr/bin/env python3
import sys
import base64
import os

def save_base64_to_file(b64_data, output_path):
    """Save Base64 data to a text file."""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(b64_data)
        print(f"Base64 written to: {output_path}")
        return True
    except Exception as e:
        print(f"Error writing file {output_path}: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: Drag a file onto this script.")
        input("Press Enter to exit...")
        return

    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        print(f"File not found: {filepath}")
        input("Press Enter to exit...")
        return

    try:
        with open(filepath, "rb") as f:
            data = f.read()
        # Encode file data to Base64
        b64_data = base64.b64encode(data).decode("utf-8")
        # Create output path with .txt extension
        base_name = os.path.basename(filepath)
        output_name = os.path.splitext(base_name)[0] + ".txt"
        output_path = os.path.join(os.path.dirname(filepath), output_name)
        # Save to text file
        save_base64_to_file(b64_data, output_path)
    except Exception as e:
        print(f"Error reading file: {e}")

    input("Press Enter to exit...")

if __name__ == "__main__":
    main()