import requests
from bs4 import BeautifulSoup
import random
import time
import re
import unicodedata

def normalize_text(text):
    # Normalize Unicode characters (e.g., curly quotes to straight ones)
    return unicodedata.normalize('NFKC', text)

# Variable settings:
context_length = 1         # Number of tokens used as context for the n-gram
tokens_per_sequence = 40   # Not used now, since we print continuously

def get_text(url):
    """Download and extract text from all paragraphs on the page."""
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    paragraphs = soup.find_all('p')
    text = " ".join(para.get_text() for para in paragraphs)
    return text

def tokenize(text):
    """
    Tokenize the text preserving words with straight or curly apostrophes,
    numbers, and punctuation tokens.
    """
    tokens = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)*|[0-9]+|[.,!?;:]", text)
    return tokens

def build_markov_chain(tokens, context_length):
    """
    Build an n-gram Markov chain from the list of tokens.
    Each key is a tuple of 'context_length' tokens.
    Values are lists of tokens that follow that sequence.
    """
    chain = {}
    for i in range(len(tokens) - context_length):
        context = tuple(tokens[i:i+context_length])
        next_token = tokens[i+context_length]
        chain.setdefault(context, []).append(next_token)
    return chain

def predict_next_token(current_context, chain):
    """
    Given the current context tuple, predict the next token using the chain.
    If the context is not found, choose a random context from the chain.
    """
    if current_context in chain:
        return random.choice(chain[current_context])
    else:
        random_context = random.choice(list(chain.keys()))
        return random.choice(chain[random_context])

def print_token(token, is_first=False):
    """
    Print a token with proper spacing.
    - If the token is punctuation (",", ".", "!", "?", ";", ":"), print it immediately (without preceding space).
    - For all other tokens, if it's not the first token printed, prepend a space.
    """
    punctuation = {",", ".", "!", "?", ";", ":"}
    if token in punctuation:
        print(token, end='', flush=True)
    else:
        if is_first:
            print(token, end='', flush=True)
        else:
            print(" " + token, end='', flush=True)

def main():
    url = "http://shakespeare.mit.edu/macbeth/full.html"
    text = normalize_text(get_text(url))
    tokens = tokenize(text)
    chain = build_markov_chain(tokens, context_length)
    

    
    # Initialize the output by choosing an initial context randomly.
    generated_tokens = []
    current_context = random.choice(list(chain.keys()))
    generated_tokens.extend(current_context)
    
    # Print the initial context tokens.
    for idx, token in enumerate(current_context):
        print_token(token, is_first=(idx == 0))
        time.sleep(random.uniform(0.1, 0.3))
    
    # Continuously generate and print tokens one at a time.
    while True:
        next_token = predict_next_token(tuple(generated_tokens[-context_length:]), chain)
        print_token(next_token)
        generated_tokens.append(next_token)
        time.sleep(random.uniform(0.1, 0.3))

if __name__ == "__main__":
    main()