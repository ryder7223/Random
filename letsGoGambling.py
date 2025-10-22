# 2.5

import subprocess
import importlib
import sys

requiredModules = ['requests']

def installMissingModules(modules):
    try:
        pip = 'pip'
        importlib.import_module(pip)
    except ImportError:
        print(f"{pip} is not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"{module} is not installed. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])

installMissingModules(requiredModules)

import os
import random
import time
import math
import sqlite3
import re
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

global RED
global GREY
global YELLOW
global GREEN
global RESET
RED = '\033[91m'
GREY = '\033[90m'
YELLOW = "\033[93m"
GREEN = "\033[92m"
RESET = '\033[0m'

global databaseFile
databaseFile = 'progress.db'

def initDatabase():
    conn = sqlite3.connect(databaseFile)
    cursor = conn.cursor()    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            username TEXT PRIMARY KEY,
            money REAL,
            bets INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def getOrCreateUser(username: str) -> tuple[float, int]:
    conn = sqlite3.connect(databaseFile)
    cursor = conn.cursor()

    cursor.execute("SELECT money, bets FROM Users WHERE username = ?", (username,))
    row = cursor.fetchone()

    if row:  # Existing user
        balance = row[0]
        totalBets = row[1]
    else:  # New user
        balance = 100.00
        totalBets = 0
        cursor.execute("INSERT INTO Users (username, money, bets) VALUES (?, ?, ?)", (username, balance, totalBets))
        conn.commit()

    conn.close()
    return balance, totalBets

def pause():
    input("\nPress Enter to continue...")

def listUsers():
    conn = sqlite3.connect(databaseFile)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM Users")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print("No users found.")
    else:
        print("=== Registered Users ===")
        for (username,) in rows:
            print(username)
        print("=" * 24)
    pause()

def resetUser():
    conn = sqlite3.connect(databaseFile)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM Users")
    users = [u[0] for u in cursor.fetchall()]

    if not users:
        print("No users found.")
        conn.close()
        input("Press Enter to continue...")
        return

    print("=== RESET USER ===")
    for i, user in enumerate(users, 1):
        print(f"{i}) {user}")

    choice = input("\nEnter the number of the user to reset (or leave blank to cancel): ").strip()
    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(users):
        print("Cancelled.")
        time.sleep(1)
        return
    else:
        username = users[int(choice) - 1]
        confirm = input(f"Are you sure you want to reset '{username}'? (y/n): ").strip().lower()
        if confirm == "y":
            cursor.execute("UPDATE Users SET money = ?, bets = ? WHERE username = ?", (100.00, 0, username))
            conn.commit()
            print(f"User '{username}' has been reset to default values (money=100.00, bets=0).")
        else:
            print("Cancelled.")
            time.sleep(1)
            return

    conn.close()
    input("Press Enter to continue...")

def setUserMoney():
    conn = sqlite3.connect(databaseFile)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM Users")
    users = [u[0] for u in cursor.fetchall()]

    if not users:
        print("No users found.")
        conn.close()
        input("Press Enter to continue...")
        return

    print("=== SET USER MONEY ===")
    for i, user in enumerate(users, 1):
        print(f"{i}) {user}")

    choice = input("\nEnter the number of the user to edit (or leave blank to cancel): ").strip()
    
    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(users):
        print("Cancelled.")
        time.sleep(1)
        return
    moneySet = float(input("Enter the ammount of money to set: "))
    if not moneySet:
        print("Cancelled.")
        time.sleep(1)
        return
    else:
        username = users[int(choice) - 1]
        confirm = input(f"Are you sure you want to cheat for '{username}'? (y/n): ").strip().lower()
        if confirm == "y":
            cursor.execute("UPDATE Users SET money = ? WHERE username = ?", (moneySet, username))
            conn.commit()
            print(f"User '{username}' now has ${moneySet:,.2f}.")
        else:
            print("Cancelled.")
            time.sleep(1)
            return

    conn.close()
    input("Press Enter to continue...")

def deleteUser():
    conn = sqlite3.connect(databaseFile)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM Users")
    users = [u[0] for u in cursor.fetchall()]

    if not users:
        print("No users found.")
        conn.close()
        input("Press Enter to continue...")
        return

    print("=== DELETE USER ===")
    for i, user in enumerate(users, 1):
        print(f"{i}) {user}")

    choice = input("\nEnter the number of the user to delete (or leave blank to cancel): ").strip()
    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(users):
        print("Cancelled.")
        time.sleep(1)
        return
    else:
        username = users[int(choice) - 1]
        confirm = input(f"Are you sure you want to permanently delete '{username}'? (y/n): ").strip().lower()
        if confirm == "y":
            cursor.execute("DELETE FROM Users WHERE username = ?", (username,))
            conn.commit()
            print(f"User '{username}' has been deleted.")
        else:
            print("Cancelled.")
            time.sleep(1)
            return

    conn.close()
    pause()

def changelog():
    changelogStr = '''
2.5:
    Added the ability to type `all` to go all in on a bet.
    Modified Lucky 7s to make it not profitable for the player on average.
    Modified `You made: $x.xx` to make it always take 1 second to type.

2.4:
    Modified scratchie odds to make it not guarantee profit for users with enough money.
    Added a temporary disclaimer to poker.
    Fixed an error that made it impossible to use Force Update.

2.3:
    Added an option to force update the program regardless of version mismatch.

2.2:
    Fixed an erorr with Blackjack that prevented the dealer's hand from being shown.
    Modified Blackjack to be more consistent with variable usage.

2.1:
    Fixed an error in the Higher or Lower game where the next card was able to be the same as the current card, making it impossible sometimes.

2.0:
    Changed database save timing to save progress immediately after every bet.
    Modified `You made: $x.xx` to be calculated using the current session starting balance, instead of the base starting balance.
    Added an option to easily restart the script to make updating easier.

1.9:
    Disabled the requirement for the auto updater to need ssl verification.
    Changed some snake_case naming to cammelCase

1.8:
    Modified Blackjack to make it show yours and the dealer's hand when you lose.

1.7:
    Added a quick game replay feature.
    Fixed incorrect input on main menu resetting on a timer instead of pausing.
    Removed excess pauses that can be replaced by the replay dialogue.

1.6:
    Added a confirmation message for resetting users and setting money.

1.5:
    Fixed issue where invalid input on main menu closed the program.
    Fixed Blackjack so when the player and the dealer tie, it counts as a loss.

1.4:
    Fixed incorrect character in main menu.
    Added auto package installer.

1.3:
    Added changelog viewer.
    Added ability to directly set money.
    Updated money formatting to universally use `,.2f`.

1.2:
    Added delays to make update logs more readable.

1.1:
    Fixed issue with updater where too many new lines were generated.

1.0:
    Added auto updater.
    '''
    print(changelogStr)
    input("\n\nPress enter to exit...")

def letterType(string: str, duration: float):
    for char in string:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(duration)

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def printHeader(balance: float):
    clear()
    print(f"Current Balance: ${balance:,.2f}")
    print("=" * 36)
    print()

def roundMoney(value: float) -> float:
    return round(value + 1e-8, 2)

def validateBet(balance: float) -> float:
    betInput = input("Enter your bet amount: ").strip()
    if betInput.lower() == "all":
        return roundMoney(balance)
    if not betInput.replace('.', '', 1).isdigit():
        print("Invalid bet format.")
        return None
    if '.' in betInput and len(betInput.split('.')[1]) > 2:
        print("No more than two decimal places allowed.")
        return None
    bet = float(betInput)
    if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
        print("Invalid bet amount.")
        return None
    return roundMoney(bet)

# ---------------------- Games ----------------------

def coinFlip(balance: float, totalBets: int) -> tuple[float, int]:
    print("Coin Flip — Double your bet")

    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    choice = input("Heads or Tails (h/t): ").strip().lower()
    if choice not in ["h", "t"]:
        print("Invalid choice.")
        return balance, totalBets

    print("Flipping coin...")
    time.sleep(1.2)
    if random.random() < 0.45:
        outcome = choice
    else:
        outcome = "t" if choice == "h" else "h"

    print(f"Coin lands on {outcome}")
    if choice == outcome:
        balance += bet
        print(f"It's a win! You now have ${balance:,.2f}")
    else:
        balance -= bet
        print(f"It's a loss. You now have ${balance:,.2f}")

    totalBets += 1
    return balance, totalBets

def diceDuel(balance: float, totalBets: int) -> tuple[float, int]:
    print("Dice Duel — Roll against the dealer (tie = loss).")
    print("Player and dealer roll a 6-sided die each.")

    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    print("Rolling dice...")
    time.sleep(1.2)
    playerRoll = random.randint(1, 6)
    dealerRoll = random.randint(1, 6)

    print(f"You rolled: {playerRoll}")
    print(f"Dealer rolled: {dealerRoll}")

    if playerRoll > dealerRoll:
        balance += bet
        print(f"You win! You now have ${balance:,.2f}")
    else:
        balance -= bet
        print(f"You lost. You now have ${balance:,.2f}")

    totalBets += 1
    return balance, totalBets

def highLow(balance: float, totalBets: int) -> tuple[float, int]:
    print("High-Low — Guess if the next card is higher or lower (1–13).")

    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    currentCard = random.randint(2, 12)
    print(f"\nCurrent card: {currentCard}")
    choice = input("Will the next card be (h)igher or (l)ower? ").strip().lower()
    if choice not in ["h", "l"]:
        print("Invalid choice.")
        return balance, totalBets

    nextCard = random.randint(1, 13)
    while nextCard == currentCard:
        nextCard = random.randint(1, 13)
    print(f"Next card: {nextCard}")

    higherCount = 13 - currentCard   # numbers strictly greater than currentCard
    lowerCount  = currentCard - 1    # numbers strictly lower than currentCard
    denom = 13.0                       # total possible next-card outcomes (1..13)

    higherProb = higherCount / denom
    lowerProb  = lowerCount  / denom

    houseEdge = 0.05  # 5% house edge

    if choice == "h":
        winProb = higherProb
        winCondition = nextCard > currentCard
    else:
        winProb = lowerProb
        winCondition = nextCard < currentCard

    # If winProb is zero (impossible guess), it's automatically a loss
    if winProb == 0:
        print("That guess is impossible given the current card — automatic loss.")
        balance -= bet
        print(f"You lost ${bet:,.2f}. New balance: ${balance:,.2f}")
        totalBets += 1
        return balance, totalBets

    # Payout multiplier inverse to chance, reduced by house edge
    payout = (1.0 / winProb) * (1.0 - houseEdge)

    # Ensure payout is positive; (it will be > 1 for reasonable house edges except pathological cases)
    if payout <= 0:
        payout = 1.0

    if winCondition:
        winnings = bet * payout - bet
        balance += winnings   # net: +bet*(payout-1)
        print(f"You win! Payout multiplier: {payout:,.2f}x (${winnings:,.2f})")
    else:
        balance -= bet
        print(f"You lost ${bet:,.2f}.")

    print(f"New balance: ${balance:,.2f}")
    totalBets += 1
    return balance, totalBets

def slotMachine(balance, totalBets) -> tuple[float, int]:
    print("Slot Machine — Match symbols to win!")
    print("Possible symbols: [7, $, *, @, #]")
    
    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    symbols = ["7", "$", "*", "@", "#"]
    print("\nSpinning reels...")
    time.sleep(1.5)
    result = [random.choice(symbols) for _ in range(3)]
    print(" | ".join(result))

    if result.count(result[0]) == 3:
        # Jackpot
        balance += bet * 10
        print(f"Jackpot! You won ${bet * 10:,.2f}")
    elif len(set(result)) == 2:
        balance += bet * 1.5
        print(f"Two matched! You won ${bet * 1.5:,.2f}")
    else:
        balance -= bet
        print(f"No match. You lost ${bet:,.2f}")

    totalBets += 1
    return balance, totalBets

def blackjack(balance: float, totalBets: int) -> tuple[float, int]:
    print("Blackjack — Try to beat the dealer without going over 21.")

    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    suits = ['♠', '♥', '♦', '♣']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

    def drawCard():
        rank = random.choice(ranks)
        suit = random.choice(suits)
        # Return tuple: (symbol, value)
        value = min(ranks.index(rank) + 1, 10)  # Face cards count as 10, Ace as 1
        return (f"{rank}{suit}", value)

    def handValue(cards):
        total = sum(v for _, v in cards)
        aces = sum(1 for r, _ in cards if r.startswith('A'))
        while aces > 0 and total + 10 <= 21:
            total += 10
            aces -= 1
        return total

    player = [drawCard(), drawCard()]
    dealer = [drawCard(), drawCard()]

    def showHand(cards, revealAll=True):
        if revealAll:
            return " ".join(c for c, _ in cards)
        else:
            return f"{cards[0][0]} ??"

    # Player turn
    while handValue(player) < 21:
        printHeader(balance)
        print(f"Your cards: {showHand(player)} (Total: {handValue(player)})")
        print(f"Dealer shows: {showHand(dealer, revealAll=False)}")
        move = input("\nHit or Stand (h/s): ").strip().lower()
        clear()
        if move == "h":
            player.append(drawCard())
        elif move == "s":
            break
        else:
            print("Invalid choice.")

    if handValue(player) > 21:
        printHeader(balance)
        print(f"Your cards: {showHand(player)} (Total: {handValue(player)})")
        print(f"Dealer's cards: {showHand(dealer)} (Total: {handValue(dealer)})")
        print(f"You bust! Dealer wins.")
        balance -= bet
        totalBets += 1
        return balance, totalBets

    # Dealer turn
    while handValue(dealer) < 17:
        dealer.append(drawCard())
    printHeader(balance)
    print(f"Your cards: {showHand(player)} (Total: {handValue(player)})")
    print(f"Dealer's cards: {showHand(dealer)} (Total: {handValue(dealer)})")

    if handValue(dealer) > 21 or handValue(player) > handValue(dealer):
        winnings = bet * 2
        balance += bet
        print(f"You win! Payout: ${winnings:,.2f}")
    else:
        print("Dealer wins.")
        balance -= bet

    print(f"New balance: ${balance:,.2f}")
    totalBets += 1
    return balance, totalBets

def roulette(balance: float, totalBets: int) -> tuple[float, int]:
    print("Roulette — Bet on a color or a number (0–36).")
    print("1) Red/Black/Green (pays 1.9x for red/black, 30x for green)")
    print("2) Single Number (pays 30x)")

    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    choice = input("Choose bet type (1/2): ").strip()
    if choice not in ["1", "2"]:
        print("Invalid choice.")
        return balance, totalBets

    redNumbers = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

    # --- Collect guess BEFORE spinning ---
    if choice == "1":
        guess = input("Bet on red, black, or green: ").strip().lower()
        if guess not in ["red", "black", "green"]:
            print("Invalid color.")
            return balance, totalBets
    else:
        guessInput = input("Enter your number (0–36): ").strip()
        if not guessInput.isdigit():
            print("Invalid number.")
            return balance, totalBets
        guess = int(guessInput)
        if not (0 <= guess <= 36):
            print("Number must be between 0–36.")
            return balance, totalBets

    # --- Animation setup ---
    spinLength = 15
    windowSize = 9
    pointerIndex = 4  # middle of window
    numbers = list(range(37))
    wheel = random.choices(numbers, k=spinLength + windowSize + 10)

    print("Spinning the wheel...")
    time.sleep(1)

    delay = 0.05
    for i in range(spinLength):
        clear()
        window = wheel[i:i + windowSize]
        display = []
        for n in window:
            colorCode = RED if n in redNumbers else GREY if n != 0 else GREEN
            display.append(f"{colorCode}{n:02d}{RESET}")
        print(" ".join(display))
        print(" " * (sum(3 for _ in window[:pointerIndex])) + "^")
        time.sleep(delay)
        delay *= 1.3  # slow down gradually

    finalIndex = spinLength - 1 + pointerIndex
    resultNumber = wheel[finalIndex]
    resultColor = "red" if resultNumber in redNumbers else "black" if resultNumber != 0 else "green"

    clear()
    colorCode = RED if resultColor == "red" else GREY if resultColor == "black" else GREEN
    print(f"            {colorCode}{resultNumber:02d}{RESET}")
    print("            ^")

    # --- Outcome handling ---
    if choice == "1":
        if guess == resultColor:
            if resultColor == "green":
                winnings = bet * 30
                balance += winnings
                print(f"Jackpot! You won ${winnings:,.2f}")
            else:
                winnings = bet * 1.9
                balance += winnings
                print(f"You win! Payout: ${winnings:,.2f}")
        else:
            balance -= bet
            print(f"You lost ${bet:,.2f}.")
    else:
        if guess == resultNumber:
            winnings = bet * 30
            balance += winnings
            print(f"Jackpot! You won ${winnings:,.2f}")
        else:
            balance -= bet
            print(f"You lost ${bet:,.2f}.")

    print(f"New balance: ${balance:,.2f}")
    totalBets += 1
    return balance, totalBets

def craps(balance: float, totalBets: int) -> tuple[float, int]:
    print("Craps — Roll 2 dice. 7 or 11 to win, 2/3/12 to lose.")
    print("Roll any other starting number twice to win.")
    
    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    die1 = random.randint(1, 6)
    die2 = random.randint(1, 6)
    roll = die1 + die2
    print(f"You rolled: {die1} + {die2} = {roll}")

    if roll in [7, 11]:
        winnings = bet * 2
        balance += bet
        print(f"You win! Payout: ${winnings:,.2f}")
    elif roll in [2, 3, 12]:
        print("Craps! You lose.")
        balance -= bet
    else:
        print(f"Point is {roll}. Roll again until you hit {roll} to win or 7 to lose.")
        while True:
            time.sleep(1)
            die1 = random.randint(1, 6)
            die2 = random.randint(1, 6)
            total = die1 + die2
            print(f"Rolled {die1} + {die2} = {total}")
            if total == roll:
                winnings = bet * 2
                balance += bet
                print(f"You hit your point! You win ${winnings:,.2f}")
                break
            elif total == 7:
                print("Seven out! You lose.")
                balance -= bet
                break

    print(f"New balance: ${balance:,.2f}")
    totalBets += 1
    return balance, totalBets

def wheelOfFortune(balance: float, totalBets: int) -> tuple[float, int]:
    print("Wheel of Fortune — Spin for random prizes!")
    print("Possible outcomes: Lose, 1.5x, 2x, 5x, 10x, 20x")

    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    outcomes = ["Lose", "Lose", "Lose", "1.5x", " 2x ", " 5x ", "10x ", "20x "]
    weights  = [0.35, 0.25, 0.15, 0.15, 0.06, 0.03, 0.009, 0.001]

    spinLength = 30
    windowSize = 5
    pointerIndex = 2  # middle of window

    # Generate a long wheel strip with enough random outcomes
    wheel = random.choices(outcomes, weights, k=spinLength + windowSize + 10)

    print("Spinning the wheel...")
    time.sleep(1)

    delay = 0.05
    for i in range(spinLength):
        clear()
        window = wheel[i:i + windowSize]
        print(" ".join(str(x) for x in window))
        print(" " * (sum(len(str(x)) + 1 for x in window[:pointerIndex])) + " ^")
        time.sleep(delay)
        delay *= 1.08

    # Use the middle item of the last window as the final result
    finalIndex = spinLength - 1 + pointerIndex
    result = wheel[finalIndex]

    clear()
    print(f"          {result}     ")
    print("           ^      ")

    if result == "Lose":
        balance -= bet
        print(f"You lost ${bet:,.2f}.")
    else:
        multiplier = float(result.replace("x", ""))
        winnings = bet * multiplier
        balance += winnings
        print(f"You won! Payout multiplier: {multiplier:,.2f}x  (${winnings:,.2f})")

    print(f"New balance: ${balance:,.2f}")
    totalBets += 1
    return balance, totalBets

def baccarat(balance: float, totalBets: int) -> tuple[float, int]:
    print("Baccarat — Bet on Player, Banker, or Tie.")
    print("Player and Banker both choose a number from 0-9.")
    
    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    print("Bet options: (p) Player, (b) Banker, (t) Tie")
    choice = input("Place your bet: ").strip().lower()
    if choice not in ["p", "b", "t"]:
        print("Invalid choice.")
        return balance, totalBets

    def drawHand():
        return random.randint(0, 9)

    playerScore = drawHand()
    bankerScore = drawHand()
    print(f"Player: {playerScore}, Banker: {bankerScore}")

    if choice == "p" and playerScore > bankerScore:
        payout = 1.95
    elif choice == "b" and bankerScore > playerScore:
        payout = 1.95 * 0.95  # 5% commission on banker win
    elif choice == "t" and playerScore == bankerScore:
        payout = 8.0
    else:
        payout = 0

    if payout > 0:
        winnings = bet * payout - bet
        balance += winnings
        print(f"You won! Payout: ${winnings:,.2f}")
    else:
        balance -= bet
        print(f"You lost ${bet:,.2f}.")

    print(f"New balance: ${balance:,.2f}")
    totalBets += 1
    return balance, totalBets

def doubleOrNothing(balance: float, totalBets: int) -> tuple[float, int]:
    print("Double or Nothing — Keep flipping to double your bet each time!")
    
    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    currentBet = bet
    while True:
        print(f"\nCurrent bet: ${currentBet:,.2f}, Balance: ${balance:,.2f}")
        choice = input("Flip coin? (y/n to stop and cash out): ").strip().lower()
        if choice != "y":
            balance += currentBet - bet  # Add winnings so far
            print(f"You cash out with ${currentBet:,.2f}")
            break

        if random.random() < 0.45:
            currentBet *= 2
            print("You won this flip! Bet doubled.")
        else:
            balance -= currentBet
            print(f"You lost! Lost ${currentBet:,.2f}")
            currentBet = 0
            break

    print(f"New balance: ${balance:,.2f}")
    totalBets += 1
    return balance, totalBets

def lottery(balance: float, totalBets: int) -> tuple[float, int]:
    print("Lottery — Pick 3 numbers (0–9). Match any of them to win!")
    
    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    picks = []
    for i in range(3):
        pickInput = input(f"Pick number {i+1} (0–9): ").strip()
        if not pickInput.isdigit() or not (0 <= int(pickInput) <= 9):
            print("Invalid choice.")
            return balance, totalBets
        picks.append(int(pickInput))

    drawn = [random.randint(0, 9) for _ in range(3)]
    print(f"Drawn numbers: {drawn}")

    matches = sum(1 for a, b in zip(picks, drawn) if a == b)
    if matches == 3:
        payout = 50
    elif matches == 2:
        payout = 5
    elif matches == 1:
        payout = 1.5
    else:
        payout = 0

    if payout > 0:
        winnings = bet * payout - bet
        balance += winnings
        print(f"You matched {matches} numbers! Payout: ${winnings:,.2f}")
    else:
        balance -= bet
        print(f"No matches. You lost ${bet:,.2f}.")

    print(f"New balance: ${balance:,.2f}")
    totalBets += 1
    return balance, totalBets

def pickARange(balance: float, totalBets: int) -> tuple[float, int]:
    print("Pick-A-Range — Pick a range of 1–50.")
    print("A random number will be generated from 1-50")
    print("Choose a smaller range for a bigger prize with lower odds.")
    
    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    rangeInput = input("Pick a range in the form low-high (e.g., 5-15): ").strip()
    try:
        low, high = map(int, rangeInput.split("-"))
        if not (1 <= low < high <= 50):
            raise ValueError
    except ValueError:
        print("Invalid range.")
        return balance, totalBets

    drawn = random.randint(1, 50)
    print(f"Drawn number: {drawn}")

    if low <= drawn <= high:
        # Payout inversely proportional to range size
        payout = (50 / (high - low + 1)) * 0.99
        if payout < 1.0:
            payout = 1.0
        winnings = bet * payout - bet
        balance += winnings
        print(f"You won! Payout multiplier: {payout:,.2f} (${winnings:,.2f})")
    else:
        balance -= bet
        print(f"You lost ${bet:,.2f}.")

    print(f"New balance: ${balance:,.2f}")
    totalBets += 1
    return balance, totalBets

def scratchie(balance: float, totalBets: int) -> tuple[float, int]:
    print("Lottery Scratchie — Each ticket costs $2.00.")
    ticketPrice = 2.00
    if balance < ticketPrice:
        print("Not enough money.")
        return balance, totalBets
    balance -= ticketPrice
    print("Scratching ticket...")
    time.sleep(1.5)

    # Weighted outcomes
    outcomes = [0, 1, 2, 5, 10, 20, 50, 500, 5000, 100000]
    weights  = [0.65, 0.20, 0.08, 0.04, 0.02, 0.007, 0.002, 0.0003, 0.00005, 0.000001]

    prize = random.choices(outcomes, weights)[0]

    if prize > 0:
        print(f"You won ${prize:,.2f}!")
        balance += prize
    else:
        print("No win this time.")
    balance = roundMoney(balance)
    totalBets += 1
    return balance, totalBets

def multilineSlots(balance: float, totalBets: int) -> tuple[float, int]:
    print("Multiline Slots — Match lines for combos!")

    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    symbols = ["7", "$", "*", "@", "#", "&", "%"]
    grid = [[random.choice(symbols) for _ in range(5)] for _ in range(3)]

    print("\nSpinning reels...")
    time.sleep(1.5)

    # Build all possible lines with their grid positions
    lines = [
        ([(0, i) for i in range(5)], grid[0]),  # top
        ([(1, i) for i in range(5)], grid[1]),  # middle
        ([(2, i) for i in range(5)], grid[2]),  # bottom
        ([(0, 0), (1, 1), (2, 2), (1, 3), (0, 4)],
         [grid[0][0], grid[1][1], grid[2][2], grid[1][3], grid[0][4]]),  # down-diagonal
        ([(2, 0), (1, 1), (0, 2), (1, 3), (2, 4)],
         [grid[2][0], grid[1][1], grid[0][2], grid[1][3], grid[2][4]])   # up-diagonal
    ]

    winnings = 0
    winningPositions = set()

    for positions, line in lines:
        unique = set(line)
        winHere = False
        if len(unique) == 1:
            winnings += bet * 5
            winHere = True
        elif len(unique) == 2:
            winnings += bet * 1.5
            winHere = True
        elif "7" in line and line.count("7") >= 3:
            winnings += bet * 3
            winHere = True

        if winHere:
            winningPositions.update(positions)

    # Print grid with yellow-highlighted winning symbols
    for r in range(3):
        rowDisplay = []
        for c in range(5):
            symbol = grid[r][c]
            if (r, c) in winningPositions:
                rowDisplay.append(f"{YELLOW}{symbol}{RESET}")
            else:
                rowDisplay.append(symbol)
        print(" | ".join(rowDisplay))
    print("")

    if winnings > 0:
        print(f"You won ${winnings:,.2f} across lines!")
        balance += winnings
    else:
        print(f"No winning lines. You lost ${bet:,.2f}.")
        balance -= bet

    balance = roundMoney(balance)
    totalBets += 1
    return balance, totalBets

def lucky7s(balance: float, totalBets: int) -> tuple[float, int]:
    print("Lucky 7s — Roll 7s to win!")

    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    reels = [random.randint(1, 7) for _ in range(3)]
    print(f"Rolled: {reels[0]} | {reels[1]} | {reels[2]}")

    if all(r == 7 for r in reels):
        winnings = bet * 30
    elif len(set(reels)) == 1:
        winnings = bet * 5
    elif 7 in reels:
        winnings = bet * 1.3
    else:
        winnings = 0

    if winnings > 0:
        print(f"You won ${winnings:,.2f}!")
        balance += winnings
    else:
        print(f"You lost ${bet:,.2f}.")
        balance -= bet

    balance = roundMoney(balance)
    totalBets += 1
    return balance, totalBets

def poker(balance: float, totalBets: int) -> tuple[float, int]:
    print("(This game is a work in progress and hard to program\nso it will either be a while before it works well or I'll just remove the game later)")
    print("Welcome to Texas Hold'em Poker!")
    print("Rules:")
    print("- You will play against 3 opponents.")
    print("- Each player gets 2 private cards.")
    print("- Five community cards are revealed over multiple rounds (Flop, Turn, River).")
    print("- Hands are ranked: Royal Flush > Straight Flush > Four of a Kind > Full House > Flush > Straight > Three of a Kind > Two Pair > One Pair > High Card.")
    print("- You can choose to fold, check/call, or raise in each round.\n")

    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♠', '♥', '♦', '♣']
    deck = [f"{r}{s}" for r in ranks for s in suits]
    random.shuffle(deck)

    numOpp = 3
    playerHand = [deck.pop() for _ in range(2)]
    oppHands = [[deck.pop() for _ in range(2)] for _ in range(numOpp)]
    communityCards = []

    rankValues = {r: i for i, r in enumerate(ranks, 2)}

    def showTable(roundName: str):
        clear()
        printHeader(balance)
        print(f"--- {roundName} ---")
        print(f"Your hand: {' '.join(playerHand)}")
        if communityCards:
            print(f"Community Cards: {' '.join(communityCards)}")
        else:
            print("Community Cards: None yet")
        print(f"Current pot: ${pot:,.2f}\n")

    def evaluateHand(hand: list) -> tuple[bool, bool, list[int], int, list[int]]:
        values = sorted([rankValues[c[:-1]] for c in hand])
        suitsInHand = [c[-1] for c in hand]
        counts = {v: values.count(v) for v in values}
        freq = sorted(counts.values(), reverse=True)
        isFlush = len(set(suitsInHand)) == 1
        isStraight = all(values[i] + 1 == values[i + 1] for i in range(len(values) - 1))
        if values == [2, 3, 4, 5, 14]:
            isStraight = True
            values = [1, 2, 3, 4, 5]
        return (isStraight, isFlush, freq, max(values), values)

    def handScore(hand: list) -> tuple[int, list[int], str]:
        isStraight, isFlush, freq, high, values = evaluateHand(hand)
        if isStraight and isFlush and max(values) == 14:
            return (10, values[::-1], "Royal Flush")
        elif isStraight and isFlush:
            return (9, values[::-1], "Straight Flush")
        elif freq == [4, 1]:
            return (8, values[::-1], "Four of a Kind")
        elif freq == [3, 2]:
            return (7, values[::-1], "Full House")
        elif isFlush:
            return (6, values[::-1], "Flush")
        elif isStraight:
            return (5, values[::-1], "Straight")
        elif freq == [3, 1, 1]:
            return (4, values[::-1], "Three of a Kind")
        elif freq == [2, 2, 1]:
            return (3, values[::-1], "Two Pair")
        elif freq == [2, 1, 1, 1]:
            return (2, values[::-1], "One Pair")
        else:
            return (1, values[::-1], "High Card")

    def generateCombinations(cards: list, n=5) -> list:
        combos = []
        def backtrack(start, path):
            if len(path) == n:
                combos.append(path[:])
                return
            for i in range(start, len(cards)):
                backtrack(i + 1, path + [cards[i]])
        backtrack(0, [])
        return combos

    def evaluateBestHand(cards: list) -> tuple:
        best = (-1, [], "", [])
        for combo in generateCombinations(cards, 5):
            cat, tiebreak, label = handScore(combo)
            if (cat, tiebreak) > (best[0], best[1]):
                best = (cat, tiebreak, label, combo)
        return best

    def playerAction(roundName: str):
        nonlocal pot, folded, bet
        while True:
            print(f"Your options: [C]heck/Call, [R]aise, [F]old")
            choice = input("> ").strip().lower()
            if choice == "f":
                folded = True
                print("You folded.")
                return
            elif choice == "r":
                try:
                    raiseAmt = float(input("Enter raise amount: $"))
                    if 0 < raiseAmt <= balance:
                        pot += raiseAmt
                        bet += raiseAmt  # Player's total at risk increases
                        print(f"\nYou raised by ${raiseAmt:,.2f}.")
                        return
                    else:
                        print("Invalid raise amount.")
                except ValueError:
                    print("Invalid number.")
            elif choice == "c" or choice == "":
                print("\nYou checked/called.")
                return
            else:
                print("Invalid input. Choose C, R, or F.")

    def opponentsAction():
        nonlocal pot
        for i, opp in enumerate(oppHands):
            # Evaluate opponent confidence
            best = evaluateBestHand(opp + communityCards)
            confidence = best[0]  # hand rank as confidence
            if random.random() < confidence / 10:
                raiseAmt = round(pot * (0.1 + confidence * 0.05), 2)
                pot += raiseAmt
                print(f"Opponent {i+1} raises by ${raiseAmt:,.2f}.")
            else:
                print(f"Opponent {i+1} checks/calls.")

    pot = bet * (numOpp + 1)
    folded = False

    # --- Pre-Flop ---
    showTable("Pre-Flop")
    playerAction("Pre-Flop")
    opponentsAction()
    if folded:
        balance -= bet
        balance = roundMoney(balance)
        print(f"You folded pre-flop and lost ${bet:,.2f}.")
        return balance, totalBets
    input("\nEnter to continue...")
    # --- Flop ---
    communityCards.extend([deck.pop() for _ in range(3)])
    showTable("Flop")
    playerAction("Flop")
    opponentsAction()
    if folded:
        balance -= bet
        balance = roundMoney(balance)
        print(f"You folded after the flop and lost ${bet:,.2f}.")
        return balance, totalBets
    input("\nEnter to continue...")
    # --- Turn ---
    communityCards.append(deck.pop())
    showTable("Turn")
    playerAction("Turn")
    opponentsAction()
    if folded:
        balance -= bet
        balance = roundMoney(balance)
        print(f"You folded after the turn and lost ${bet:,.2f}.")
        return balance, totalBets
    input("\nEnter to continue...")
    # --- River ---
    communityCards.append(deck.pop())
    showTable("River")
    playerAction("River")
    opponentsAction()
    if folded:
        balance -= bet
        balance = roundMoney(balance)
        print(f"You folded after the river and lost ${bet:,.2f}.")
        return balance, totalBets
    input("\nEnter to continue...")
    # --- Showdown ---
    playerBest = evaluateBestHand(playerHand + communityCards)
    oppBests = [evaluateBestHand(opp + communityCards) for opp in oppHands]

    def getKeyCards(hand: list) -> list:
        values = [c[:-1] for c in hand]
        counts = {v: values.count(v) for v in set(values)}
        freqSorted = sorted(counts.items(), key=lambda x: (-x[1], -rankValues[x[0]]))
        keyCards = []
        if freqSorted[0][1] >= 2:
            maxCount = freqSorted[0][1]
            for val, count in freqSorted:
                if count == maxCount:
                    keyCards.extend([c for c in hand if c[:-1] == val])
                if len(keyCards) >= maxCount * (2 if freqSorted[1][1] == maxCount else 1):
                    break
        elif freqSorted[0][1] == 1 and len(hand) == 5:
            keyCards = hand
        return keyCards

    def highlightHand(allCards: list, bestCombo: list, handRankLabel: str) -> str:
        keyCards = getKeyCards(bestCombo) if handRankLabel not in ["Straight", "Flush", "Straight Flush", "Royal Flush", "High Card"] else bestCombo
        return " ".join(f"{YELLOW}{c}{RESET}" if c in keyCards else c for c in allCards)

    print("\n--- SHOWDOWN ---")
    print(f"Your final hand: {highlightHand(playerHand + communityCards, playerBest[3], playerBest[2])} -> {YELLOW}{playerBest[2]}{RESET}")
    for i, (h, s) in enumerate(zip(oppHands, oppBests), 1):
        fullHand = h + communityCards
        print(f"Opponent {i}: {highlightHand(fullHand, s[3], s[2])} -> {YELLOW}{s[2]}{RESET}")
    print("")

    allScores = [(playerBest, "Player")] + list(zip(oppBests, [f"Opponent {i}" for i in range(1, numOpp + 1)]))
    allScores.sort(key=lambda x: (x[0][0], x[0][1]), reverse=True)
    bestScore = allScores[0][0]
    winners = [name for score, name in allScores if (score[0], score[1]) == (bestScore[0], bestScore[1])]

    if "Player" in winners:
        if len(winners) == 1:
            winnings = pot
            balance += winnings
            print(f"You won the pot of ${winnings:,.2f}!")
        else:
            winnings = pot / len(winners)
            balance += winnings
            print(f"You tied and split the pot! You win ${winnings:,.2f}.")
    else:
        print("You lost the hand.")
        balance -= bet

    balance = roundMoney(balance)
    totalBets += 1
    return balance, totalBets

def horseRacing(balance: float, totalBets: int) -> tuple[float, int]:
    print("Horse Racing — Bet on a horse (A–E)!")

    bet = validateBet(balance)
    if bet is None:
        return balance, totalBets

    horses = ['A', 'B', 'C', 'D', 'E']
    choice = input("Choose your horse (A–E): ").strip().upper()
    if choice not in horses:
        print("Invalid choice.")
        return balance, totalBets

    positions = {h: 0 for h in horses}
    trackLength = 20
    winner = None

    while not winner:
        clear()
        print("Horse Racing!\n")

        # Determine which horses are 1 space away from finishing
        oneSpaceAway = [h for h, pos in positions.items() if pos == trackLength - 1]

        for h in horses:
            if positions[h] < trackLength:
                if h in oneSpaceAway:
                    # Only one randomly chosen horse moves if multiple are 1 space away
                    if len(oneSpaceAway) > 1:
                        chosen = random.choice(oneSpaceAway)
                        if h == chosen:
                            positions[h] += 1
                    else:
                        positions[h] += 1
                else:
                    # Normal random movement for horses not 1 space away
                    positions[h] += random.choice([0, 1])

                if positions[h] >= trackLength:
                    positions[h] = trackLength
                    if not winner:
                        winner = h

            # Draw horse on track
            preSpaces = " " * positions[h]
            postSpaces = " " * (trackLength - positions[h])
            print(f"{preSpaces}{h}{postSpaces}|")

        time.sleep(0.1)

    print(f"\nHorse {winner} wins!")
    if winner == choice:
        winnings = bet * 4
        balance += winnings
        print(f"You won ${winnings:,.2f}!")
    else:
        balance -= bet
        print(f"You lost ${bet:,.2f}.")

    balance = roundMoney(balance)
    totalBets += 1
    return balance, totalBets

# ---------------------- Stats ----------------------

def stats(balance: float, startingBalanc: float, totalBets: int):
    clear()
    profit = balance - startingBalance
    print("=== GAME STATS ===")
    print(f"Starting Balance: ${startingBalance:,.2f}")
    print(f"Current Balance:  ${balance:,.2f}")
    print(f"Profit/Loss:      ${profit:,.2f}")
    print(f"Total Bets Made:  {totalBets}")
    print("=" * 24)
    pause()

# ---------------------- Updater ----------------------

def checkForUpdate(force: int):
    localFile = os.path.abspath(__file__)
    repoUrl = "https://raw.githubusercontent.com/ryder7223/Random/refs/heads/main/letsGoGambling.py"
    print("Checking for updates...")
    time.sleep(1)

    # Read local version
    try:
        with open(localFile, "r", encoding="utf-8") as f:
            firstLine = f.readline().strip()
            localVersionMatch = re.match(r"#\s*([\d.]+)", firstLine)
            if not localVersionMatch:
                print("Unable to read local version number.")
                time.sleep(1)
                return
            localVersion = localVersionMatch.group(1)
    except Exception as e:
        print(f"Error reading local version: {e}")
        time.sleep(1)
        return

    # Get version from GitHub
    try:
        response = requests.get(repoUrl, timeout=10, verify=False)
        if response.status_code != 200:
            print(f"Failed to fetch version (HTTP {response.status_code}).")
            time.sleep(1)
            return
        remoteText = response.text
        remoteFirstLine = remoteText.splitlines()[0].strip()
        remoteVersionMatch = re.match(r"#\s*([\d.]+)", remoteFirstLine)
        if not remoteVersionMatch:
            print("Unable to read version number.")
            time.sleep(1)
            return
        remoteVersion = remoteVersionMatch.group(1)
    except Exception:
        print(f"Unable to fetch newest version, proceeding offline.")
        time.sleep(1)
        return

    # Compare versions
    def versionTuple(v: str): 
        return tuple(map(int, v.split('.')))

    updateNeeded = False
    if force == 1:
        print("Updating...")
        updateNeeded = True
    elif versionTuple(remoteVersion) > versionTuple(localVersion):
        print(f"New version available ({localVersion} → {remoteVersion}). Updating...")
        updateNeeded = True
    else:
        print(f"Version {localVersion} is up to date.")
        time.sleep(1)

    if updateNeeded:
        time.sleep(1)
        try:
            normalizedText = re.sub(r'\n{3,}', '\n\n', remoteText.replace('\r\n', '\n'))
            with open(localFile, "w", encoding="utf-8") as f:
                f.write(normalizedText)
            print("Update complete. Restarting...")
            time.sleep(1)
        except Exception as e:
            print(f"Failed to write updated file: {e}")
            time.sleep(1)
            return

        # Restart script
        os.execv(sys.executable, [sys.executable] + sys.argv)

# ---------------------- Main Loop ----------------------

def main(startingBalance: float, totalBets: int, name: str) -> tuple[float, float, int]:
    balance = startingBalance
    sessionStart = startingBalance
    startingBalance = 100.00

    games = {
        "1": coinFlip,
        "2": diceDuel,
        "3": highLow,
        "4": slotMachine,
        "5": blackjack,
        "6": roulette,
        "7": craps,
        "8": wheelOfFortune,
        "9": baccarat,
        "10": doubleOrNothing,
        "11": lottery,
        "12": pickARange,
        "13": scratchie,
        "14": multilineSlots,
        "15": lucky7s,
        "16": poker,
        "17": horseRacing,
    }

    try:
        while True:

            balance = roundMoney(balance)
            printHeader(balance)
            print("1) Coin Flip")
            print("2) Dice Duel")
            print("3) High-Low Card Game")
            print("4) Slot Machine")
            print("5) Blackjack")
            print("6) Roulette")
            print("7) Craps")
            print("8) Wheel of Fortune")
            print("9) Baccarat")
            print("10) Double or Nothing")
            print("11) Lottery")
            print("12) Pick-A-Range")
            print("13) Scratchie Ticket")
            print("14) Multiline Slots")
            print("15) Lucky 7s")
            print("16) Poker")
            print("17) Horse Racing")
            print("18) View Stats")
            print("19) Quit")
    
            choice = input("\nSelect an option: ").strip()
    
            # Handle game selections 1–17
            if choice in games:
                while True:
                    clear()
                    printHeader(balance)
                    balance, totalBets = games[choice](balance, totalBets)

                    conn = sqlite3.connect(databaseFile)
                    cursor = conn.cursor()
                    cursor.execute(
                    "INSERT OR REPLACE INTO Users (username, money, bets) VALUES (?, ?, ?)",
                    (name, balance, totalBets)
                    )
                    conn.commit()
                    conn.close()

                    replay = input("\nPlay again? (y)es/(n)o: ")
                    if replay == "y":
                        pass
                    else:
                        break
    
            elif choice == "18":
                profit = roundMoney(balance - startingBalance)
                clear()
                print("=== GAME STATS ===")
                print(f"Starting Balance: ${startingBalance:,.2f}")
                print(f"Current Balance:  ${balance:,.2f}")
                print(f"Profit/Loss:      ${profit:,.2f}")
                print(f"Total Bets Made:  {totalBets}")
                print("=" * 24)
                pause()
    
            elif choice == "19":
                print(f"\nYou left with ${balance:,.2f}. Thanks for playing.")
                break
    
            else:
                print("Invalid choice. Please enter a number between 1 and 20.")
                pause()
    
            if balance <= 0:
                print("You’ve lost all your money. Game over.")
                break
    
            clear()
        return balance, startingBalance, totalBets, sessionStart
    except KeyboardInterrupt:
        return balance, startingBalance, totalBets, sessionStart
    except Exception as e:
        print(e)
        input("Please copy and save this error somewhere so the developer can fix it.\n\nAwaiting input...")

if __name__ == "__main__":
    try:
        clear()
        checkForUpdate(force=0)
        clear()
        initDatabase()

        while True:
            clear()
            print("==== MENU ====")
            print("1) List Users")
            print("2) Begin Game")
            print("3) Reset User")
            print("4) Set User Money")
            print("5) Delete User")
            print("6) Changelog")
            print("7) Restart Program")
            print("8) Force Update")
            print("9) Exit")

            choice = input("\nSelect an option: ").strip()

            if choice == "1":
                clear()
                listUsers()
                continue

            elif choice == "2":
                clear()
                name = input("Enter your name: ").strip()
                startingBalance, totalBets = getOrCreateUser(name)
                balance, startingBalance, totalBets, sessionStart = main(startingBalance, totalBets, name)

                clear()
                profit = roundMoney(balance - sessionStart)
                print("You made: ", end="")
                sys.stdout.flush()
                time.sleep(1)
                text = f"${profit:,.2f}"
                typeDelay = 1.0 / len(text)
                letterType(f"${profit:,.2f}", typeDelay)
                time.sleep(0.5)
                input("\nPress Enter to exit...")

            elif choice == "3":
                clear()
                resetUser()

            elif choice == "4":
                clear()
                setUserMoney()

            elif choice == "5":
                clear()
                deleteUser()

            elif choice == "6":
                clear()
                changelog()

            elif choice == "7":
                clear()
                print("Restarting program...")
                time.sleep(0.5)
                os.execl(sys.executable, sys.executable, *sys.argv)

            elif choice == "8":
                clear()
                checkForUpdate(force=1)

            elif choice == "9":
                print("Exiting...")
                time.sleep(0.5)
                sys.exit(0)

            else:
                print("Invalid choice. Please select 1–5.")
                pause()
    except KeyboardInterrupt:
        print("\nForce Exiting, your progress will be saved.")
        time.sleep(0.5)
        sys.exit(0)
    except Exception as e:
        print(f"An error has occurred: {e}")
        input("Awaiting...")
        sys.exit(0)
