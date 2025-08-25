import time
import requests
import win32clipboard
import win32con
import os

API_URL = (
    'https://api.python-minifier.com/shrink/3.12?combine_imports=true&remove_pass=true&remove_literal_statements=true&hoist_literals=true&rename_locals=true&rename_globals=true&convert_posargs_to_args=true&preserve_shebang=true&remove_asserts=true&remove_debug=true&remove_explicit_return_none=true&remove_builtin_exception_brackets=true&constant_folding=true&remove_variable_annotations=true&remove_return_annotations=true&remove_argument_annotations=true&remove_class_attribute_annotations=false&preserve_globals=handler'
)


def get_clipboard_file_path():
    """Return the first file path from clipboard if clipboard contains files, else None."""
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
            data = win32clipboard.GetClipboardData(win32con.CF_HDROP)
            if data and len(data) > 0:
                return data[0]
    except Exception:
        pass
    finally:
        win32clipboard.CloseClipboard()
    return None


def set_clipboard_text(text):
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def minify_python_code(code):
    try:
        resp = requests.post(API_URL, data=code.encode('utf-8'), timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"Error minifying code: {e}")
        return None


def process_clipboard():
    file_path = get_clipboard_file_path()
    if file_path and file_path.lower().endswith('.py') and os.path.isfile(file_path):
        print(f"Detected Python file in clipboard: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as e:
            print(f"Failed to read file: {e}")
            return
        minified = minify_python_code(code)
        if minified:
            set_clipboard_text(minified)
            print("Minified code placed in clipboard!")
        else:
            print("Failed to minify code.")


def main():
    print("Monitoring clipboard for Python files... (copy a .py file in Explorer to minify it)")
    print("Press Ctrl+C to exit.")
    
    last_clipboard_data = None
    
    try:
        while True:
            # Check if clipboard has changed
            try:
                win32clipboard.OpenClipboard()
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                    current_data = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                    if current_data != last_clipboard_data:
                        last_clipboard_data = current_data
                        win32clipboard.CloseClipboard()
                        process_clipboard()
                    else:
                        win32clipboard.CloseClipboard()
                else:
                    win32clipboard.CloseClipboard()
            except Exception as e:
                # If there's an error, try to close clipboard safely
                try:
                    win32clipboard.CloseClipboard()
                except:
                    pass  # Ignore errors when closing clipboard
            
            time.sleep(0.5)  # Check every 500ms
            
    except KeyboardInterrupt:
        print("Exiting.")


if __name__ == "__main__":
    main() 