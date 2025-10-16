import os
from PIL import Image

def main():
    print("Image Shrinker - Reduce image dimensions and file size!")
    img_path = input("Enter the path to the image file: ").strip()
    if not os.path.isfile(img_path):
        print(f"File not found: {img_path}")
        return
    try:
        shrink_factor = float(input("Enter shrink factor (e.g., 0.5 for half size): "))
        if not (0 < shrink_factor < 1):
            print("Shrink factor must be between 0 and 1.")
            return
    except ValueError:
        print("Invalid shrink factor.")
        return
    try:
        with Image.open(img_path) as img:
            new_size = (int(img.width * shrink_factor), int(img.height * shrink_factor))
            img_resized = img.resize(new_size, Image.LANCZOS)
            base, ext = os.path.splitext(img_path)
            out_path = f"{base}_shrunken{ext}"
            img_resized.save(out_path, optimize=True, quality=85)
            print(f"Shrunken image saved as: {out_path}")
    except Exception as e:
        print(f"Error processing image: {e}")

if __name__ == "__main__":
    main() 