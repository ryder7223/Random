import random
import requests
import os
import platform
import ctypes
from typing import List, Tuple, Dict

# ANSI color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
GRAY = '\033[90m'
RESET = '\033[0m'
NO_COLOR = ''

# QWERTY keyboard layout
KEYBOARD_ROWS = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]

def set_hidden_file(filepath: str):
    system = platform.system()

    if system == "Windows":
        try:
            FILE_ATTRIBUTE_HIDDEN = 0x02
            ctypes.windll.kernel32.SetFileAttributesW(str(filepath), FILE_ATTRIBUTE_HIDDEN)
        except Exception as e:
            print(f"Failed to hide file on Windows: {e}")
    elif system in ("Linux", "Darwin"):  # Darwin is macOS
        dirname, basename = os.path.split(filepath)
        if not basename.startswith("."):
            hidden_path = os.path.join(dirname, "." + basename)
            try:
                os.rename(filepath, hidden_path)
                return hidden_path
            except Exception as e:
                print(f"Failed to hide file on Unix-like system: {e}")
    return filepath

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

            hidden_filepath = set_hidden_file(filename)
            return words
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

def play_wordle(show_intro: bool) -> None:
    target_word = random.choice(POSSIBLE_WORDS)
    guesses = []
    key_colors = {char: NO_COLOR for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}

    if show_intro:
        clear_screen()
        print("Welcome to Wordle!")
        print("Try to guess the 5-letter word in 6 attempts.")
        print(f"{GREEN}Green{RESET}: correct letter in correct position")
        print(f"{YELLOW}Yellow{RESET}: correct letter in wrong position")
        print(f"{GRAY}Gray{RESET}: letter not in the word")
        print("\nPress Enter to start...")
        input()

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
            return

    display_board(guesses, target_word, key_colors)
    print(f"\nGame Over! The word was {target_word}")

if __name__ == "__main__":
    first_time = True
    while True:
        play_wordle(show_intro=first_time)
        first_time = False
        choice = input("\nType 'restart' to play again or 'exit' to quit: ").strip().lower()
        if choice == 'exit':
            print("Goodbye!")
            break
        elif choice != 'restart':
            print("Unrecognized input. Exiting by default.")
            break