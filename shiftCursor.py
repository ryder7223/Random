from pynput import keyboard
from pynput.mouse import Controller

# Set up mouse controller
mouse = Controller()

# Step size in pixels
STEP = 16

# Movement logic
def on_press(key):
    try:
        if key.char == 'w':
            x, y = mouse.position
            mouse.position = (x, y - STEP)
        elif key.char == 's':
            x, y = mouse.position
            mouse.position = (x, y + STEP)
        elif key.char == 'a':
            x, y = mouse.position
            mouse.position = (x - STEP, y)
        elif key.char == 'd':
            x, y = mouse.position
            mouse.position = (x + STEP, y)
    except AttributeError:
        # Ignore special keys like shift, ctrl, etc.
        pass

# Start listening
with keyboard.Listener(on_press=on_press) as listener:
    listener.join()