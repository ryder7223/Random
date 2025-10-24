import sys
import time
import os

def moveCursor(x: int, y: int) -> str:
    return f"\033[{y};{x}H"

def rgbToAnsi(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"

def rainbowColorAtPosition(position: float) -> tuple[int, int, int]:
    k = (position % 1.0) * 6
    i = int(k)
    f = k - i
    if i == 0:
        return (255, int(255 * f), 0)
    elif i == 1:
        return (int(255 * (1 - f)), 255, 0)
    elif i == 2:
        return (0, 255, int(255 * f))
    elif i == 3:
        return (0, int(255 * (1 - f)), 255)
    elif i == 4:
        return (int(255 * f), 0, 255)
    else:
        return (255, 0, int(255 * (1 - f)))

def renderRainbowSection(text: str, phase: float, step: float, offset: float) -> str:
    output = ""
    for i, char in enumerate(text):
        r, g, b = rainbowColorAtPosition((i * step + phase + offset) % 1.0)
        output += f"{rgbToAnsi(r, g, b)}{char}"
    return output + "\033[0m"

def animateMixedText(segments: list[tuple[str, bool, float, int, int]], speed: float = 0.03, step: float = 0.02, relative: bool = True) -> None:
    phase = 0.0
    sys.stdout.write("\033[?25l")
    try:
        baseX, baseY = 0, 0
        absoluteSegments = []
        for i, (text, isRainbow, offset, x, y) in enumerate(segments):
            if i == 0 or not relative:
                absX, absY = x, y
            else:
                absX = baseX + x + len(segments[i - 1][0])
                absY = baseY + y
            absoluteSegments.append((text, isRainbow, offset, absX, absY))
            baseX, baseY = absX, absY

        while True:
            for text, isRainbow, offset, x, y in absoluteSegments:
                sys.stdout.write(moveCursor(x, y))
                if isRainbow:
                    output = renderRainbowSection(text, phase, step, offset)
                else:
                    output = text
                sys.stdout.write(output + "\033[0m")
            sys.stdout.flush()
            time.sleep(0.05)
            phase += speed
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

if __name__ == "__main__":
    os.system("cls" if os.name == "nt" else "clear")
    animateMixedText([
        ("Look I have", False, 0.0, 1, 1),
        ("RAINBOW", True, 0.0, 1, 0),
        ("text! :D", False, 0.0, 1, 0)
    ], speed=0.03, step=0.1, relative=True)