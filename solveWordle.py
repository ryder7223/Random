import os
import requests
from typing import List

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
GRAY = '\033[90m'
RESET = '\033[0m'

def load_words() -> List[str]:
    filename = "possible_words6LAWu.txt"
    url = "https://gist.githubusercontent.com/scholtes/94f3c0303ba6a7768b47583aff36654d/raw/73f890e1680f3fa21577fef3d1f06b8d6c6ae318/wordle-La.txt"

    if os.path.exists(filename):
        try:
            with open(filename, "r") as file:
                return [line.strip().upper() for line in file if len(line.strip()) == 5 and line.strip().isalpha()]
        except Exception:
            print("Failed to load word list from local file.")
            return []

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        words = [line.strip().upper() for line in response.text.splitlines() if len(line.strip()) == 5 and line.isalpha()]
        try:
            with open(filename, "w") as file:
                file.write("\n".join(words))
        except Exception:
            print("Could not save the downloaded word list to a local file.")
        return words
    except requests.RequestException:
        print("Could not download the word list.")
        return []

def filter_words(possible_words: List[str], guess: str, pattern: str) -> List[str]:
    guess = guess.upper()
    new_list = []

    for word in possible_words:
        valid = True
        used_letters = list(word)

        # First pass: greens
        for i in range(5):
            if pattern[i] == 'g':
                if word[i] != guess[i]:
                    valid = False
                    break
                used_letters[i] = None

        if not valid:
            continue

        # Second pass: yellows and grays
        for i in range(5):
            if pattern[i] == 'y':
                if guess[i] == word[i] or guess[i] not in used_letters:
                    valid = False
                    break
                used_letters[used_letters.index(guess[i])] = None
            elif pattern[i] == 'x':
                if guess[i] in used_letters:
                    valid = False
                    break

        if valid:
            new_list.append(word)

    return new_list

def main():
    full_word_list = load_words()
    if not full_word_list:
        print("No words loaded. Exiting.")
        return

    while True:
        possible_words = full_word_list.copy()
        history = []

        while True:
            print("\nEnter your guess and pattern (e.g., 'crate gxxyx')")
            print("Type 'restart' to reset the session.")
            print("Type 'exit' to quit.")
            user_input = input(">>> ").strip()

            if user_input.lower() == "exit":
                return
            if user_input.lower() == "restart":
                print("\nRestarting...\n")
                break

            try:
                guess, pattern = user_input.split()
                guess = guess.upper()
                pattern = pattern.lower()
                if len(guess) != 5 or len(pattern) != 5 or not all(c in 'gyx' for c in pattern):
                    raise ValueError
            except ValueError:
                print("Invalid input format. Use: 'guess gxyxx'")
                continue

            possible_words = filter_words(possible_words, guess, pattern)
            history.append((guess, pattern))

            print("\nCurrent filters:")
            for g, p in history:
                colored = ''
                for i in range(5):
                    color = GREEN if p[i] == 'g' else YELLOW if p[i] == 'y' else GRAY
                    colored += f"{color}{g[i]}{RESET}"
                print(f"  {colored}")

            print(f"\nPossible words remaining: {len(possible_words)}")
            #print(", ".join(possible_words[:20]) + ("..." if len(possible_words) > 20 else ""))
            print(", ".join(possible_words))

if __name__ == "__main__":
    main()