import time
from datetime import datetime, timezone

def formatRelativeTime(unixTime: int) -> str:
    now = datetime.now().astimezone()
    target = datetime.fromtimestamp(unixTime, tz=timezone.utc).astimezone()

    deltaSeconds = int((target - now).total_seconds())
    isFuture = deltaSeconds > 0
    deltaSeconds = abs(deltaSeconds)

    units = [
        ("year", 60 * 60 * 24 * 365),
        ("week", 60 * 60 * 24 * 7),
        ("day", 60 * 60 * 24),
        ("hour", 60 * 60),
        ("minute", 60),
        ("second", 1),
    ]

    values = []
    remaining = deltaSeconds

    for name, secondsPerUnit in units:
        count = remaining // secondsPerUnit
        if count > 0:
            values.append((name, count))
            remaining %= secondsPerUnit

    if not values:
        return "now"

    parts = []
    for name, count in values:
        parts.append(f"{count} {name}" if count == 1 else f"{count} {name}s")

    if len(parts) == 1:
        result = parts[0]
    else:
        result = " ".join(parts[:-1]) + " and " + parts[-1]

    return f"in {result}" if isFuture else f"{result} ago"


if __name__ == "__main__":
    unixInput = int(input("Enter unix time: "))
    print(formatRelativeTime(unixInput))