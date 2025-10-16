import os
import random
import sys
import time
import math

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

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def pause():
    input("\nPress Enter to continue...")

def print_header(balance):
    clear()
    print(f"Current Balance: ${balance:,.2f}")
    print("=" * 36)
    print()

def round_money(value):
    return round(value + 1e-8, 2)

def validate_bet(balance):
    bet_input = input("Enter your bet amount: ").strip()
    if not bet_input.replace('.', '', 1).isdigit():
        print("Invalid bet format.")
        pause()
        return None
    if '.' in bet_input and len(bet_input.split('.')[1]) > 2:
        print("No more than two decimal places allowed.")
        pause()
        return None
    bet = float(bet_input)
    if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
        print("Invalid bet amount.")
        pause()
        return None
    return round_money(bet)

# ---------------------- Games ----------------------
def coin_flip(balance):
    print("Coin Flip — Double your bet")
    bet = validate_bet(balance)
    if bet is None:
        return balance

    choice = input("Heads or Tails (h/t): ").strip().lower()
    if choice not in ["h", "t"]:
        print("Invalid choice.")
        pause()
        return balance

    print("Flipping coin...")
    time.sleep(1.2)
    if random.random() < 0.45:
        outcome = choice
    else:
        outcome = "t" if choice == "h" else "h"

    print(f"Coin lands on {outcome}")
    if choice == outcome:
        balance += bet
        print(f"It's a win! You now have ${balance:.2f}")
    else:
        balance -= bet
        print(f"It's a loss. You now have ${balance:.2f}")

    pause()
    return balance

def dice_duel(balance):
    print("Dice Duel — Roll against the dealer (tie = loss).")
    print("Player and dealer roll a 6-sided die each.")

    bet_input = input("Enter your bet amount: ").strip()
    try:
        bet = float(bet_input)
        if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
            print("Invalid bet amount.")
            pause()
            return balance
    except ValueError:
        print("Invalid bet.")
        pause()
        return balance

    print("Rolling dice...")
    time.sleep(1.2)
    player_roll = random.randint(1, 6)
    dealer_roll = random.randint(1, 6)

    print(f"You rolled: {player_roll}")
    print(f"Dealer rolled: {dealer_roll}")

    if player_roll > dealer_roll:
        balance += bet
        print(f"You win! You now have ${balance:.2f}")
    else:
        balance -= bet
        print(f"You lost. You now have ${balance:.2f}")

    pause()
    return balance

def high_low(balance):
    print("High-Low — Guess if the next card is higher or lower (1–13).")

    bet_input = input("Enter your bet amount: ").strip()
    try:
        bet = float(bet_input)
        if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
            print("Invalid bet amount.")
            pause()
            return balance
    except ValueError:
        print("Invalid bet.")
        pause()
        return balance

    current_card = random.randint(1, 13)
    print(f"\nCurrent card: {current_card}")
    choice = input("Will the next card be (h)igher or (l)ower? ").strip().lower()
    if choice not in ["h", "l"]:
        print("Invalid choice.")
        pause()
        return balance

    next_card = random.randint(1, 13)
    print(f"Next card: {next_card}")

    higher_count = 13 - current_card   # numbers strictly greater than current_card
    lower_count  = current_card - 1    # numbers strictly lower than current_card
    denom = 13.0                       # total possible next-card outcomes (1..13)

    higher_prob = higher_count / denom
    lower_prob  = lower_count  / denom

    house_edge = 0.05  # 5% house edge

    if choice == "h":
        win_prob = higher_prob
        win_condition = next_card > current_card
    else:
        win_prob = lower_prob
        win_condition = next_card < current_card

    # If win_prob is zero (impossible guess), it's automatically a loss
    if win_prob == 0:
        print("That guess is impossible given the current card — automatic loss.")
        balance -= bet
        print(f"You lost ${bet:.2f}. New balance: ${balance:.2f}")
        pause()
        return balance

    # Payout multiplier inverse to chance, reduced by house edge
    payout = (1.0 / win_prob) * (1.0 - house_edge)

    # Ensure payout is positive; (it will be > 1 for reasonable house edges except pathological cases)
    if payout <= 0:
        payout = 1.0

    if win_condition:
        winnings = bet * payout
        balance += winnings   # net: +bet*(payout-1)
        print(f"You win! Payout multiplier: {payout:.2f}x (${winnings:.2f})")
    else:
        balance -= bet
        print(f"You lost ${bet:.2f}.")

    print(f"New balance: ${balance:.2f}")
    pause()
    return balance

def slot_machine(balance):
    print("Slot Machine — Match symbols to win!")
    print("Possible symbols: [7, $, *, @, #]")
    bet_input = input("Enter your bet amount: ").strip()
    try:
        bet = float(bet_input)
        if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
            print("Invalid bet amount.")
            pause()
            return balance
    except ValueError:
        print("Invalid bet.")
        pause()
        return balance

    symbols = ["7", "$", "*", "@", "#"]
    print("\nSpinning reels...")
    time.sleep(1.5)
    result = [random.choice(symbols) for _ in range(3)]
    print(" | ".join(result))

    if result.count(result[0]) == 3:
        # Jackpot
        balance += bet * 10
        print(f"Jackpot! You won ${bet * 10:.2f}")
    elif len(set(result)) == 2:
        balance += bet * 1.5
        print(f"Two matched! You won ${bet * 1.5:.2f}")
    else:
        balance -= bet
        print(f"No match. You lost ${bet:.2f}")

    pause()
    return balance

def blackjack(balance):
    print("Blackjack — Try to beat the dealer without going over 21.")
    bet_input = input("Enter your bet amount: ").strip()
    try:
        bet = float(bet_input)
        if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
            print("Invalid bet amount.")
            pause()
            return balance
    except ValueError:
        print("Invalid bet.")
        pause()
        return balance

    suits = ['♠', '♥', '♦', '♣']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

    def draw_card():
        rank = random.choice(ranks)
        suit = random.choice(suits)
        # Return tuple: (symbol, value)
        value = min(ranks.index(rank) + 1, 10)  # Face cards count as 10, Ace as 1
        return (f"{rank}{suit}", value)

    def hand_value(cards):
        total = sum(v for _, v in cards)
        aces = sum(1 for r, _ in cards if r.startswith('A'))
        while aces > 0 and total + 10 <= 21:
            total += 10
            aces -= 1
        return total

    player = [draw_card(), draw_card()]
    dealer = [draw_card(), draw_card()]

    def show_hand(cards, reveal_all=True):
        if reveal_all:
            return " ".join(c for c, _ in cards)
        else:
            return f"{cards[0][0]} ??"

    # Player turn
    while hand_value(player) < 21:
        print_header(balance)
        print(f"Your cards: {show_hand(player)} (Total: {hand_value(player)})")
        print(f"Dealer shows: {show_hand(dealer, reveal_all=False)}")
        move = input("\nHit or Stand (h/s): ").strip().lower()
        clear()
        if move == "h":
            player.append(draw_card())
        elif move == "s":
            break
        else:
            print("Invalid choice.")

    player_total = hand_value(player)
    if player_total > 21:
        print_header(balance)
        print(f"You bust! Your total was {player_total}. Dealer wins.")
        balance -= bet
        pause()
        return balance

    # Dealer turn
    while hand_value(dealer) < 17:
        dealer.append(draw_card())
    dealer_total = hand_value(dealer)
    print_header(balance)
    print(f"Your cards: {show_hand(player)} (Total: {hand_value(player)})")
    print(f"Dealer's cards: {show_hand(dealer)} (Total: {dealer_total})")

    if dealer_total > 21 or player_total > dealer_total:
        winnings = bet * 2
        balance += bet
        print(f"You win! Payout: ${winnings:.2f}")
    elif dealer_total == player_total:
        print("Push — It's a tie.")
    else:
        print("Dealer wins.")
        balance -= bet

    print(f"New balance: ${balance:.2f}")
    pause()
    return balance

def roulette(balance):
    """European Roulette — Animated spin with red/black/green betting and single number option."""
    print("Roulette — Bet on a color or a number (0–36).")
    print("1) Red/Black/Green (pays 1.9x for red/black, 30x for green)")
    print("2) Single Number (pays 30x)")

    choice = input("Choose bet type (1/2): ").strip()
    if choice not in ["1", "2"]:
        print("Invalid choice.")
        pause()
        return balance

    bet_input = input("Enter your bet amount: ").strip()
    try:
        bet = float(bet_input)
        if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
            print("Invalid bet amount.")
            pause()
            return balance
    except ValueError:
        print("Invalid bet.")
        pause()
        return balance

    red_numbers = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

    # --- Collect guess BEFORE spinning ---
    if choice == "1":
        guess = input("Bet on red, black, or green: ").strip().lower()
        if guess not in ["red", "black", "green"]:
            print("Invalid color.")
            pause()
            return balance
    else:
        guess_input = input("Enter your number (0–36): ").strip()
        if not guess_input.isdigit():
            print("Invalid number.")
            pause()
            return balance
        guess = int(guess_input)
        if not (0 <= guess <= 36):
            print("Number must be between 0–36.")
            pause()
            return balance

    # --- Animation setup ---
    spin_length = 15
    window_size = 9
    pointer_index = 4  # middle of window
    numbers = list(range(37))
    wheel = random.choices(numbers, k=spin_length + window_size + 10)

    print("Spinning the wheel...")
    time.sleep(1)

    delay = 0.05
    for i in range(spin_length):
        clear()
        window = wheel[i:i + window_size]
        display = []
        for n in window:
            color_code = RED if n in red_numbers else GREY if n != 0 else GREEN
            display.append(f"{color_code}{n:02d}{RESET}")
        print(" ".join(display))
        print(" " * (sum(3 for _ in window[:pointer_index])) + "^")
        time.sleep(delay)
        delay *= 1.3  # slow down gradually

    final_index = spin_length - 1 + pointer_index
    result_number = wheel[final_index]
    result_color = "red" if result_number in red_numbers else "black" if result_number != 0 else "green"

    clear()
    color_code = RED if result_color == "red" else GREY if result_color == "black" else GREEN
    print(f"            {color_code}{result_number:02d}{RESET}")
    print("            ^")

    # --- Outcome handling ---
    if choice == "1":
        if guess == result_color:
            if result_color == "green":
                winnings = bet * 30
                balance += winnings
                print(f"Jackpot! You won ${winnings:.2f}")
            else:
                winnings = bet * 1.9
                balance += winnings
                print(f"You win! Payout: ${winnings:.2f}")
        else:
            balance -= bet
            print(f"You lost ${bet:.2f}.")
    else:
        if guess == result_number:
            winnings = bet * 30
            balance += winnings
            print(f"Jackpot! You won ${winnings:.2f}")
        else:
            balance -= bet
            print(f"You lost ${bet:.2f}.")

    print(f"New balance: ${balance:.2f}")
    pause()
    return balance

def craps(balance):
    print("Craps — Roll 2 dice. 7 or 11 to win, 2/3/12 to lose.")
    print("Roll any other starting number twice to win.")
    bet_input = input("Enter your bet amount: ").strip()
    try:
        bet = float(bet_input)
        if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
            print("Invalid bet amount.")
            pause()
            return balance
    except ValueError:
        print("Invalid bet.")
        pause()
        return balance

    die1 = random.randint(1, 6)
    die2 = random.randint(1, 6)
    roll = die1 + die2
    print(f"You rolled: {die1} + {die2} = {roll}")

    if roll in [7, 11]:
        winnings = bet * 2
        balance += bet
        print(f"You win! Payout: ${winnings:.2f}")
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
                print(f"You hit your point! You win ${winnings:.2f}")
                break
            elif total == 7:
                print("Seven out! You lose.")
                balance -= bet
                break

    print(f"New balance: ${balance:.2f}")
    pause()
    return balance

def wheel_of_fortune(balance):
    print("Wheel of Fortune — Spin for random prizes!")
    print("Possible outcomes: Lose, 1.5x, 2x, 5x, 10x, 20x")

    bet_input = input("Enter your bet amount: ").strip()
    try:
        bet = float(bet_input)
        if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
            print("Invalid bet amount.")
            pause()
            return balance
    except ValueError:
        print("Invalid bet.")
        pause()
        return balance

    outcomes = ["Lose", "Lose", "Lose", "1.5x", " 2x ", " 5x ", "10x ", "20x "]
    weights  = [0.35, 0.25, 0.15, 0.15, 0.06, 0.03, 0.009, 0.001]

    spin_length = 30
    window_size = 5
    pointer_index = 2  # middle of window

    # Generate a long wheel strip with enough random outcomes
    wheel = random.choices(outcomes, weights, k=spin_length + window_size + 10)

    print("Spinning the wheel...")
    time.sleep(1)

    delay = 0.05
    for i in range(spin_length):
        clear()
        window = wheel[i:i + window_size]
        print(" ".join(str(x) for x in window))
        print(" " * (sum(len(str(x)) + 1 for x in window[:pointer_index])) + " ^")
        time.sleep(delay)
        delay *= 1.08

    # Use the middle item of the last window as the final result
    final_index = spin_length - 1 + pointer_index
    result = wheel[final_index]

    clear()
    print(f"          {result}     ")
    print("           ^      ")

    if result == "Lose":
        balance -= bet
        print(f"You lost ${bet:.2f}.")
    else:
        multiplier = float(result.replace("x", ""))
        winnings = bet * multiplier
        balance += winnings
        print(f"You won! Payout multiplier: {multiplier:.2f}x  (${winnings:.2f})")

    print(f"New balance: ${balance:.2f}")
    pause()
    return balance

def baccarat(balance):
    print("Baccarat — Bet on Player, Banker, or Tie.")
    print("Player and Banker both choose a number from 0-9.")
    bet_input = input("Enter your bet amount: ").strip()
    try:
        bet = float(bet_input)
        if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
            print("Invalid bet amount.")
            pause()
            return balance
    except ValueError:
        print("Invalid bet.")
        pause()
        return balance

    print("Bet options: (p) Player, (b) Banker, (t) Tie")
    choice = input("Place your bet: ").strip().lower()
    if choice not in ["p", "b", "t"]:
        print("Invalid choice.")
        pause()
        return balance

    def draw_hand():
        return random.randint(0, 9)

    player_score = draw_hand()
    banker_score = draw_hand()
    print(f"Player: {player_score}, Banker: {banker_score}")

    if choice == "p" and player_score > banker_score:
        payout = 1.95
    elif choice == "b" and banker_score > player_score:
        payout = 1.95 * 0.95  # 5% commission on banker win
    elif choice == "t" and player_score == banker_score:
        payout = 8.0
    else:
        payout = 0

    if payout > 0:
        winnings = bet * payout
        balance += winnings
        print(f"You won! Payout: ${winnings:.2f}")
    else:
        balance -= bet
        print(f"You lost ${bet:.2f}.")

    print(f"New balance: ${balance:.2f}")
    pause()
    return balance

def double_or_nothing(balance):
    print("Double or Nothing — Keep flipping to double your bet each time!")
    bet_input = input("Enter your starting bet amount: ").strip()
    try:
        bet = float(bet_input)
        if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
            print("Invalid bet amount.")
            pause()
            return balance
    except ValueError:
        print("Invalid bet.")
        pause()
        return balance

    current_bet = bet
    while True:
        print(f"\nCurrent bet: ${current_bet:.2f}, Balance: ${balance:.2f}")
        choice = input("Flip coin? (y/n to stop and cash out): ").strip().lower()
        if choice != "y":
            balance += current_bet - bet  # Add winnings so far
            print(f"You cash out with ${current_bet:.2f}")
            break

        if random.random() < 0.45:
            current_bet *= 2
            print("You won this flip! Bet doubled.")
        else:
            balance -= current_bet
            print(f"You lost! Lost ${current_bet:.2f}")
            current_bet = 0
            break

    print(f"New balance: ${balance:.2f}")
    pause()
    return balance

def lottery(balance):
    print("Lottery — Pick 3 numbers (0–9). Match any of them to win!")
    bet_input = input("Enter your bet amount: ").strip()
    try:
        bet = float(bet_input)
        if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
            print("Invalid bet amount.")
            pause()
            return balance
    except ValueError:
        print("Invalid bet.")
        pause()
        return balance

    picks = []
    for i in range(3):
        pick_input = input(f"Pick number {i+1} (0–9): ").strip()
        if not pick_input.isdigit() or not (0 <= int(pick_input) <= 9):
            print("Invalid choice.")
            pause()
            return balance
        picks.append(int(pick_input))

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
        winnings = bet * payout
        balance += winnings
        print(f"You matched {matches} numbers! Payout: ${winnings:.2f}")
    else:
        balance -= bet
        print(f"No matches. You lost ${bet:.2f}.")

    print(f"New balance: ${balance:.2f}")
    pause()
    return balance

def pick_a_range(balance):
    print("Pick-A-Range — Pick a range of 1–50.")
    print("A random number will be generated from 1-50")
    print("Choose a smaller range for a bigger prize with lower odds.")
    bet_input = input("Enter your bet amount: ").strip()
    try:
        bet = float(bet_input)
        if bet <= 0 or (bet > balance and not math.isclose(bet, balance, rel_tol=1e-9, abs_tol=1e-9)):
            print("Invalid bet amount.")
            pause()
            return balance
    except ValueError:
        print("Invalid bet.")
        pause()
        return balance

    range_input = input("Pick a range in the form low-high (e.g., 5-15): ").strip()
    try:
        low, high = map(int, range_input.split("-"))
        if not (1 <= low < high <= 50):
            raise ValueError
    except ValueError:
        print("Invalid range.")
        pause()
        return balance

    drawn = random.randint(1, 50)
    print(f"Drawn number: {drawn}")

    if low <= drawn <= high:
        # Payout inversely proportional to range size
        payout = (50 / (high - low + 1)) * 0.99
        if payout < 1.0:
            payout = 1.0
        winnings = bet * payout
        balance += winnings
        print(f"You won! Payout multiplier: {payout:.2f} (${winnings:.2f})")
    else:
        balance -= bet
        print(f"You lost ${bet:.2f}.")

    print(f"New balance: ${balance:.2f}")
    pause()
    return balance

def scratchie(balance):
    print("Lottery Scratchie — Each ticket costs $2.00.")
    ticket_price = 2.00
    if balance < ticket_price:
        print("Not enough funds.")
        pause()
        return balance
    balance -= ticket_price
    print("Scratching ticket...")
    time.sleep(1.5)

    # Weighted outcomes
    outcomes = [0, 1, 2, 5, 10, 20, 50, 1000, 10000, 100000]
    weights = [0.60, 0.20, 0.10, 0.06, 0.05, 0.02, 0.01, 0.001, 0.0001, 0.00001]
    prize = random.choices(outcomes, weights)[0]

    if prize > 0:
        print(f"You won ${prize:.2f}!")
        balance += prize
    else:
        print("No win this time.")
    balance = round_money(balance)
    pause()
    return balance

def multiline_slots(balance):
    print("Multiline Slots — Match lines for combos!")
    bet = validate_bet(balance)
    if bet is None:
        return balance

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
    winning_positions = set()

    for positions, line in lines:
        unique = set(line)
        win_here = False
        if len(unique) == 1:
            winnings += bet * 5
            win_here = True
        elif len(unique) == 2:
            winnings += bet * 1.5
            win_here = True
        elif "7" in line and line.count("7") >= 3:
            winnings += bet * 3
            win_here = True

        if win_here:
            winning_positions.update(positions)

    # Print grid with yellow-highlighted winning symbols
    for r in range(3):
        row_display = []
        for c in range(5):
            symbol = grid[r][c]
            if (r, c) in winning_positions:
                row_display.append(f"{YELLOW}{symbol}{RESET}")
            else:
                row_display.append(symbol)
        print(" | ".join(row_display))
    print("")

    if winnings > 0:
        print(f"You won ${winnings:.2f} across lines!")
        balance += winnings
    else:
        print(f"No winning lines. You lost ${bet:.2f}.")
        balance -= bet

    balance = round_money(balance)
    pause()
    return balance

def lucky_7s(balance):
    print("Lucky 7s — Roll 7s to win!")
    bet = validate_bet(balance)
    if bet is None:
        return balance

    reels = [random.randint(1, 7) for _ in range(3)]
    print(f"Rolled: {reels[0]} | {reels[1]} | {reels[2]}")

    if all(r == 7 for r in reels):
        winnings = bet * 50
    elif len(set(reels)) == 1:
        winnings = bet * 10
    elif 7 in reels:
        winnings = bet * 2
    else:
        winnings = 0

    if winnings > 0:
        print(f"You won ${winnings:.2f}!")
        balance += winnings
    else:
        print(f"You lost ${bet:.2f}.")
        balance -= bet

    balance = round_money(balance)
    pause()
    return balance

def poker(balance):
    print("Welcome to Texas Hold'em Poker!")
    print("Rules:")
    print("- You will play against 3 opponents.")
    print("- Each player gets 2 private cards.")
    print("- Five community cards are revealed over multiple rounds (Flop, Turn, River).")
    print("- Hands are ranked: Royal Flush > Straight Flush > Four of a Kind > Full House > Flush > Straight > Three of a Kind > Two Pair > One Pair > High Card.")
    print("- You can choose to fold, check/call, or raise in each round.\n")

    bet = validate_bet(balance)
    if bet is None:
        return balance

    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♠', '♥', '♦', '♣']
    deck = [f"{r}{s}" for r in ranks for s in suits]
    random.shuffle(deck)

    num_opp = 3
    player_hand = [deck.pop() for _ in range(2)]
    opp_hands = [[deck.pop() for _ in range(2)] for _ in range(num_opp)]
    community_cards = []

    rank_values = {r: i for i, r in enumerate(ranks, 2)}

    def show_table(round_name):
        clear()
        print_header(balance)
        print(f"--- {round_name} ---")
        print(f"Your hand: {' '.join(player_hand)}")
        if community_cards:
            print(f"Community Cards: {' '.join(community_cards)}")
        else:
            print("Community Cards: None yet")
        print(f"Current pot: ${pot:.2f}\n")

    def evaluate_hand(hand):
        values = sorted([rank_values[c[:-1]] for c in hand])
        suits_in_hand = [c[-1] for c in hand]
        counts = {v: values.count(v) for v in values}
        freq = sorted(counts.values(), reverse=True)
        is_flush = len(set(suits_in_hand)) == 1
        is_straight = all(values[i] + 1 == values[i + 1] for i in range(len(values) - 1))
        if values == [2, 3, 4, 5, 14]:
            is_straight = True
            values = [1, 2, 3, 4, 5]
        return (is_straight, is_flush, freq, max(values), values)

    def hand_score(hand):
        is_straight, is_flush, freq, high, values = evaluate_hand(hand)
        if is_straight and is_flush and max(values) == 14:
            return (10, values[::-1], "Royal Flush")
        elif is_straight and is_flush:
            return (9, values[::-1], "Straight Flush")
        elif freq == [4, 1]:
            return (8, values[::-1], "Four of a Kind")
        elif freq == [3, 2]:
            return (7, values[::-1], "Full House")
        elif is_flush:
            return (6, values[::-1], "Flush")
        elif is_straight:
            return (5, values[::-1], "Straight")
        elif freq == [3, 1, 1]:
            return (4, values[::-1], "Three of a Kind")
        elif freq == [2, 2, 1]:
            return (3, values[::-1], "Two Pair")
        elif freq == [2, 1, 1, 1]:
            return (2, values[::-1], "One Pair")
        else:
            return (1, values[::-1], "High Card")

    def generate_combinations(cards, n=5):
        combos = []
        def backtrack(start, path):
            if len(path) == n:
                combos.append(path[:])
                return
            for i in range(start, len(cards)):
                backtrack(i + 1, path + [cards[i]])
        backtrack(0, [])
        return combos

    def evaluate_best_hand(cards):
        best = (-1, [], "", [])
        for combo in generate_combinations(cards, 5):
            cat, tiebreak, label = hand_score(combo)
            if (cat, tiebreak) > (best[0], best[1]):
                best = (cat, tiebreak, label, combo)
        return best

    def player_action(round_name):
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
                    raise_amt = float(input("Enter raise amount: $"))
                    if 0 < raise_amt <= balance:
                        pot += raise_amt
                        bet += raise_amt  # Player's total at risk increases
                        print(f"\nYou raised by ${raise_amt:.2f}.")
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

    def opponents_action():
        nonlocal pot
        for i, opp in enumerate(opp_hands):
            # Evaluate opponent confidence
            best = evaluate_best_hand(opp + community_cards)
            confidence = best[0]  # hand rank as confidence
            if random.random() < confidence / 10:
                raise_amt = round(pot * (0.1 + confidence * 0.05), 2)
                pot += raise_amt
                print(f"Opponent {i+1} raises by ${raise_amt:.2f}.")
            else:
                print(f"Opponent {i+1} checks/calls.")

    pot = bet * (num_opp + 1)
    folded = False

    # --- Pre-Flop ---
    show_table("Pre-Flop")
    player_action("Pre-Flop")
    opponents_action()
    if folded:
        balance -= bet
        balance = round_money(balance)
        print(f"You folded pre-flop and lost ${bet:.2f}.")
        pause()
        return balance
    input("\nEnter to continue...")
    # --- Flop ---
    community_cards.extend([deck.pop() for _ in range(3)])
    show_table("Flop")
    player_action("Flop")
    opponents_action()
    if folded:
        balance -= bet
        balance = round_money(balance)
        print(f"You folded after the flop and lost ${bet:.2f}.")
        pause()
        return balance
    input("\nEnter to continue...")
    # --- Turn ---
    community_cards.append(deck.pop())
    show_table("Turn")
    player_action("Turn")
    opponents_action()
    if folded:
        balance -= bet
        balance = round_money(balance)
        print(f"You folded after the turn and lost ${bet:.2f}.")
        pause()
        return balance
    input("\nEnter to continue...")
    # --- River ---
    community_cards.append(deck.pop())
    show_table("River")
    player_action("River")
    opponents_action()
    if folded:
        balance -= bet
        balance = round_money(balance)
        print(f"You folded after the river and lost ${bet:.2f}.")
        pause()
        return balance
    input("\nEnter to continue...")
    # --- Showdown ---
    player_best = evaluate_best_hand(player_hand + community_cards)
    opp_bests = [evaluate_best_hand(opp + community_cards) for opp in opp_hands]

    def get_key_cards(hand):
        values = [c[:-1] for c in hand]
        counts = {v: values.count(v) for v in set(values)}
        freq_sorted = sorted(counts.items(), key=lambda x: (-x[1], -rank_values[x[0]]))
        key_cards = []
        if freq_sorted[0][1] >= 2:
            max_count = freq_sorted[0][1]
            for val, count in freq_sorted:
                if count == max_count:
                    key_cards.extend([c for c in hand if c[:-1] == val])
                if len(key_cards) >= max_count * (2 if freq_sorted[1][1] == max_count else 1):
                    break
        elif freq_sorted[0][1] == 1 and len(hand) == 5:
            key_cards = hand
        return key_cards

    def highlight_hand(all_cards, best_combo, hand_rank_label):
        key_cards = get_key_cards(best_combo) if hand_rank_label not in ["Straight", "Flush", "Straight Flush", "Royal Flush", "High Card"] else best_combo
        return " ".join(f"{YELLOW}{c}{RESET}" if c in key_cards else c for c in all_cards)

    print("\n--- SHOWDOWN ---")
    print(f"Your final hand: {highlight_hand(player_hand + community_cards, player_best[3], player_best[2])} -> {YELLOW}{player_best[2]}{RESET}")
    for i, (h, s) in enumerate(zip(opp_hands, opp_bests), 1):
        full_hand = h + community_cards
        print(f"Opponent {i}: {highlight_hand(full_hand, s[3], s[2])} -> {YELLOW}{s[2]}{RESET}")
    print("")

    all_scores = [(player_best, "Player")] + list(zip(opp_bests, [f"Opponent {i}" for i in range(1, num_opp + 1)]))
    all_scores.sort(key=lambda x: (x[0][0], x[0][1]), reverse=True)
    best_score = all_scores[0][0]
    winners = [name for score, name in all_scores if (score[0], score[1]) == (best_score[0], best_score[1])]

    if "Player" in winners:
        if len(winners) == 1:
            winnings = pot
            balance += winnings
            print(f"You won the pot of ${winnings:.2f}!")
        else:
            winnings = pot / len(winners)
            balance += winnings
            print(f"You tied and split the pot! You win ${winnings:.2f}.")
    else:
        print("You lost the hand.")
        balance -= bet

    balance = round_money(balance)
    pause()
    return balance

def horse_racing(balance):
    print("Horse Racing — Bet on a horse (A–E)!")
    bet = validate_bet(balance)
    if bet is None:
        return balance

    horses = ['A', 'B', 'C', 'D', 'E']
    choice = input("Choose your horse (A–E): ").strip().upper()
    if choice not in horses:
        print("Invalid choice.")
        pause()
        return balance

    positions = {h: 0 for h in horses}
    track_length = 20
    winner = None

    while not winner:
        clear()
        print("Horse Racing!\n")

        # Determine which horses are 1 space away from finishing
        one_space_away = [h for h, pos in positions.items() if pos == track_length - 1]

        for h in horses:
            if positions[h] < track_length:
                if h in one_space_away:
                    # Only one randomly chosen horse moves if multiple are 1 space away
                    if len(one_space_away) > 1:
                        chosen = random.choice(one_space_away)
                        if h == chosen:
                            positions[h] += 1
                    else:
                        positions[h] += 1
                else:
                    # Normal random movement for horses not 1 space away
                    positions[h] += random.choice([0, 1])

                if positions[h] >= track_length:
                    positions[h] = track_length
                    if not winner:
                        winner = h

            # Draw horse on track
            pre_spaces = " " * positions[h]
            post_spaces = " " * (track_length - positions[h])
            print(f"{pre_spaces}{h}{post_spaces}|")

        time.sleep(0.1)

    print(f"\nHorse {winner} wins!")
    if winner == choice:
        winnings = bet * 4
        balance += winnings
        print(f"You won ${winnings:.2f}!")
    else:
        balance -= bet
        print(f"You lost ${bet:.2f}.")

    balance = round_money(balance)
    pause()
    return balance

# ---------------------- Stats ----------------------

def stats(balance, starting_balance, total_bets):
    clear()
    profit = balance - starting_balance
    print("=== GAME STATS ===")
    print(f"Starting Balance: ${starting_balance:.2f}")
    print(f"Current Balance:  ${balance:.2f}")
    print(f"Profit/Loss:      ${profit:.2f}")
    print(f"Total Bets Made:  {total_bets}")
    print("=" * 24)
    pause()

# ---------------------- Main Loop ----------------------

def main():
    balance = 100.00
    starting_balance = balance
    total_bets = 0

    games = {
        "1": coin_flip,
        "2": dice_duel,
        "3": high_low,
        "4": slot_machine,
        "5": blackjack,
        "6": roulette,
        "7": craps,
        "8": wheel_of_fortune,
        "9": baccarat,
        "10": double_or_nothing,
        "11": lottery,
        "12": pick_a_range,
        "13": scratchie,
        "14": multiline_slots,
        "15": lucky_7s,
        "16": poker,
        "17": horse_racing,
    }

    while True:
        balance = round_money(balance)
        print_header(balance)
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
        total_bets += 1

        # Handle game selections 1–17
        if choice in games:
            clear()
            print_header(balance)
            balance = games[choice](balance)

        elif choice == "18":
            profit = round_money(balance - starting_balance)
            clear()
            print("=== GAME STATS ===")
            print(f"Starting Balance: ${starting_balance:.2f}")
            print(f"Current Balance:  ${balance:.2f}")
            print(f"Profit/Loss:      ${profit:.2f}")
            print(f"Total Bets Made:  {total_bets}")
            print("=" * 24)
            pause()

        elif choice == "19":
            print(f"\nYou left with ${balance:.2f}. Thanks for playing.")
            break

        else:
            print("Invalid choice. Please enter a number between 1 and 20.")
            pause()

        if balance <= 0:
            print("You’ve lost all your money. Game over.")
            break

        clear()

if __name__ == "__main__":
    main()
    input()