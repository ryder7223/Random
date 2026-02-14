import os
import shutil
import zipfile

def compress_file(file_path, output_zip):
    """Compresses the input file into a zip file."""
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file_path, os.path.basename(file_path))

def main(file_path, iterations):
    """Main function to create folders, compress files, move compressed files, and delete extra folders."""
    if not os.path.exists(file_path):
        print(f"File '{file_path}' not found.")
        return

    parent_folder = os.getcwd()
    file_name = os.path.basename(file_path)
    file_base_name, file_ext = os.path.splitext(file_name)
    folders_to_delete = []

    for i in range(1, iterations + 1):
        # Compress file
        zip_name = f"{parent_folder}/{file_base_name}.zip"
        compress_file(file_path, zip_name)

        # Create folder for compressed file
        folder_path = f"{parent_folder}/{i}"
        os.makedirs(folder_path, exist_ok=True)

        # Move compressed file to folder
        shutil.move(zip_name, folder_path)

        # Update file path for next iteration
        file_path = f"{folder_path}/{os.path.basename(zip_name)}"

        # Track folders to delete
        if i > 1:
            folders_to_delete.append(f"{parent_folder}/{i-1}")

    # Delete extra folders
    for folder in folders_to_delete:
        shutil.rmtree(folder)

if __name__ == "__main__":
    file_path = input("Enter the file path: ")
    iterations = int(input("Enter the number of iterations: "))
    main(file_path, iterations)
    print(f"Process completed for {iterations} iterations.")