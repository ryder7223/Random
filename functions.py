from typing import Generator, Any, Callable, Iterable, Sequence, TypeVar, cast
import time
import ast
import math
import uuid
import sys
from datetime import datetime, timezone
import random
import re

ResultT = TypeVar("ResultT")

def printGenerator(gen: Generator[Any, Any, Any], limit: int | None = None, dot: str = ".", sep: str = "", splitFirst: bool = True) -> None:
	"""
	Prints the values of generators up to any point.
	"""
	if splitFirst:
		firstDigit = next(gen)
		print(firstDigit, end=dot, flush=True)
	count = 0
	for digit in gen:
		print(digit, end=sep, flush=True)
		count += 1
		if limit is not None and count >= limit:
			return

def functionTime(
	func: Callable[..., ResultT],
	runs: int = 10,
	iterableArgs: Iterable[tuple[Any, ...]] | None = None,
) -> tuple[list[float], list[ResultT | Exception]]:

	"""
	Measures execution time over multiple runs.
	Supports iterating func params.\n
	Timing a function with no param iteration:
	```py
	times, result = functionTime(lambda: printGenerator(piSpigot(), limit=200), runs=10)
	```
	Iterating through a list for func:
	```py
	data = [1778637131, 1778637132, 1778637133, 1778637134]
	
	times, results = functionTime(
	    lambda x: unixToRelativeTime(x),
	    iterableArgs=[(x,) for x in data]
	)
	```
	Iterating through a list of tuples for func:
	```py
	data = [(1778637131,), (1778637132,), (1778637133,), (1778637134,)]

	times, results = functionTime(unixToRelativeTime, iterableArgs=data)
	```
	Iterating through a list of tuples for func with multiple params:
	```py
	def add(x, y):
	    return x + y
	
	data = [(2, 3), (4, 5)]
	
	times, results = functionTime(lambda x, y: add(x, y), iterableArgs=data)
	```
	"""

	times: list[float] = []
	results: list[ResultT | Exception] = []

	if iterableArgs is not None:
		iterableArgs = list(iterableArgs)
		runs = len(iterableArgs)
		actualRuns: list[tuple[Any, ...]] = iterableArgs
	else:
		if runs <= 0:
			raise ValueError("runs must be greater than 0")
		actualRuns: list[tuple[Any, ...]] = [()] * runs

	for i in range(runs):
		start = time.perf_counter()

		try:
			if iterableArgs is not None:
				result = func(*actualRuns[i])
			else:
				result = func()
			end = time.perf_counter()

		except Exception as exception:
			end = time.perf_counter()
			result = exception

		times.append(end - start)
		results.append(result)

	return times, results

def printFunctionTime(func: Callable[..., ResultT], runs: int = 10, iterableArgs: Iterable[tuple[Any, ...]] | None = None) -> tuple[list[float], list[ResultT | Exception]]:
	"""
	Calls functionTime() and prints the shortest, longest, and average runtimes.
	Functions exactly the same as functionTime() so returns the same data.
	"""
	times, result = functionTime(func, runs=runs, iterableArgs=iterableArgs)

	print(f"\nShortest runtime: {min(times):.8f} seconds")
	print(f"Longest runtime: {max(times):.8f} seconds")
	print(f"\nAverage runtime: {sum(times) / len(times):.8f} seconds")

	return times, result

def printTree(node: object, indent: int = 4) -> None:
	"""
	Visualises lists through indented printing.
	"""
	prefix = "  " * indent

	if not isinstance(node, (tuple, list)):
		print(prefix + repr(node))
		return

	print(prefix + "[")

	for item in cast(Sequence[Any], node):
		printTree(item, indent + 1)

	print(prefix + "]")

def polygonalNumber(order: int, sides: int) -> int:
	"""
	Generates polygonal numbers of any side conut.
	"""
	return ((sides - 2) * order * order - (sides - 4) * order) // 2

def calcPerc(*values: int | str, decimals: int = 2) -> None:
	"""
	Prints the relative percentages of any amount of integers out of their added total.
	"""
	numericValues: list[float] = []
	try:
		for v in values:
			if isinstance(v, str) and v.isdigit():
				decimals = int(v)
			elif isinstance(v, (int, float)):
				numericValues.append(float(v))
			else:
				raise ValueError("Invalid input type")
		
		total = sum(numericValues)
		for value in numericValues:
			percentage = round(100 * (value / total), decimals)
			print(f"{value}: {percentage}%")
	except Exception:
		print("Invalid input")

def generateIp(public: bool = True) -> str:
	"""
	Generates ip addresses with the option to include ips that aren't public.
	"""
	while True:
		firstOctet = random.randint(1, 222)

		if firstOctet >= 127:
			firstOctet += 1

		secondOctet = random.randint(0, 255)

		if public:
			if (lambda x, y: True if x == 10 or
				x == 172 and 16 <= y <= 31 or
				x == 192 and y == 168 else False)(firstOctet, secondOctet):
				continue

		return f"{firstOctet}.{secondOctet}.{random.randint(0,255)}.{random.randint(0,255)}"

def mcStacks(amountInput: str | int | float, stackSizeInput: int | str | float) -> list[int]:
	"""
	Calculates stacks of items, supporting arithmatic in the input. e.g.
	`mcStacks(\"8*8*5 + 45\", 64)`
	"""

	def _add(a: float, b: float) -> float:
		return a + b

	def _sub(a: float, b: float) -> float:
		return a - b

	def _mul(a: float, b: float) -> float:
		return a * b

	def _div(a: float, b: float) -> float:
		return a / b

	def _floordiv(a: float, b: float) -> float:
		return a // b

	def _mod(a: float, b: float) -> float:
		return a % b

	def _pow(a: float, b: float) -> float:
		return a ** b

	def _neg(a: float) -> float:
		return -a

	allowedOps: dict[type[ast.AST], Callable[..., float]] = {
		ast.Add: _add,
		ast.Sub: _sub,
		ast.Mult: _mul,
		ast.Div: _div,
		ast.FloorDiv: _floordiv,
		ast.Mod: _mod,
		ast.Pow: _pow,
		ast.USub: _neg,
	}

	def evalArithmetic(expr: str) -> float:
		tree = ast.parse(expr, mode="eval")

		def evalNode(node: ast.AST) -> float:
			if isinstance(node, ast.Expression):
				return evalNode(node.body)

			if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
				return node.value

			if isinstance(node, ast.BinOp) and type(node.op) in allowedOps:
				return allowedOps[type(node.op)](
					evalNode(node.left),
					evalNode(node.right),
				)

			if isinstance(node, ast.UnaryOp) and type(node.op) in allowedOps:
				return allowedOps[type(node.op)](evalNode(node.operand))

			raise ValueError("Unsafe or invalid expression")

		return evalNode(tree.body)

	def fixValue(value: int | float | None) -> int:
		if value is None:
			return 0
		return math.floor(float(value))

	def findStacks(amount: int, stackSize: int) -> tuple[int, int]:
		return amount // stackSize, amount % stackSize


	# --- parse inputs ---
	def resolve(value: int | float | str) -> float:
		if isinstance(value, (int, float)):
			return float(value)
		else:
			try:
				return float(int(value))
			except ValueError:
				return evalArithmetic(value)
		raise TypeError("Input must be int, float, or str expression")

	amount = fixValue(resolve(amountInput))
	stackSize = fixValue(resolve(stackSizeInput))

	if stackSize == 0:
		raise ValueError("Stack size cannot be zero")

	stacks, remainder = findStacks(int(amount), int(stackSize))

	return [stacks, remainder]

def systemID():
	"""
	Wraps uuid.getnode()
	"""
	return uuid.getnode()

def odd(n: int) -> bool:
	return bool(n & 1)

def even(n: int) -> bool:
	return not bool(n & 1)

def version():
	"""
	Prints the current python version.
	"""
	print(f"Python version: {sys.version}")

def dec2bin(x: int | str) -> str:
	"""
	Converts a decimal integer to a binary string without the '0b' prefix.
	"""
	return format(int(x), "b")

def bin2dec(x: str | int) -> int:
	"""
	Converts a binary value to a decimal integer.
	"""
	if isinstance(x, int):
		x = str(x)
	elif x[:2] == "0b":
		x = x[2:]
	return int(x, 2)

def unixToRelativeTime(unixTime: int) -> str:
	"""
	Converts unix time to it's word representation, e.g.
	`in 3 years 8 weeks 6 days 9 hours and 46 minutes` or
	`16 weeks 3 days 17 hours 47 minutes and 55 seconds ago`.
	"""
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

	values: list[tuple[str, int]] = []
	remaining = deltaSeconds

	for name, secondsPerUnit in units:
		count = remaining // secondsPerUnit
		if count > 0:
			values.append((name, count))
			remaining %= secondsPerUnit

	if not values:
		return "now"

	parts: list[str] = []
	for name, count in values:
		parts.append(f"{count} {name}" if count == 1 else f"{count} {name}s")

	if len(parts) == 1:
		result = parts[0]
	else:
		result = " ".join(parts[:-1]) + " and " + parts[-1]

	return f"in {result}" if isFuture else f"{result} ago"

def intToHexRev(n: int) -> str:
	"""
	Converts integers to hex and reverses the hex in pairs of two,
	only accepts integers that convert to an even length hex. e.g.
	`482024245324` becomes `4c 48 e2 3a 70`.
	"""
	reversedHex = bytes.fromhex(str(hex(n))[2:])[::-1].hex()
	return " ".join([reversedHex[i:i+2] for i in range(0, len(reversedHex), 2)])

def randomList(length: int, minimum: int, maximum: int) -> list[int]:
	"""
	Generates a list of random numbers.
	"""
	return [random.randint(minimum, maximum) for _ in range(length)]

def diff(a: int, b: int):
	"""
	Calculates the magnitude of the difference between two values,
	always returns a positive number.
	"""
	result = a - b
	if result < 0:
		return -result
	return result

def subnetCoverage(x: int) -> int:
	"""
	Returns the amount of available IPs for a subnet using CIDR notation.
	"""
	return 2 ** (32 - x)

def fallDistance(totalTime: float, speedOfSound: float = 343.0, gravity: float = 9.81) -> float:
	"""
	Calculate the distance fallen from the elapsed time between release
	and hearing the impact, accounting for the speed of sound.
	"""
	if totalTime < 0:
		raise ValueError("Time must be non-negative")

	root = math.sqrt(1.0 + (2.0 * gravity * totalTime) / speedOfSound) - 1.0
	return (speedOfSound * speedOfSound * root * root) / (2.0 * gravity)

def toBytes(data: bytes) -> str:
	"""
	Returns the \\x representation of bytes.
	"""
	return "".join(f"\\x{b:02x}" for b in data)

def _all(items: Iterable[object]) -> bool:
	for item in items:
		if not item:
			return False
	return True

def timeToSeconds(timeValue: str) -> int:
	timeValue = timeValue.strip().lower()
	validPattern = r"^(\d{1,2}):(\d{2})(?:\s*(am|pm))?$"
	match = re.match(validPattern, timeValue)

	if not match:
		raise ValueError("Invalid Input")

	hours, minutes, period = match.groups()
	hours = int(hours)
	minutes = int(minutes)

	if minutes > 59:
		raise ValueError("Invalid Input")

	if period:
		if hours < 1 or hours > 12:
			raise ValueError("Invalid 12-hour time")

		if period == "am":
			hours = 0 if hours == 12 else hours
		else:
			hours = 12 if hours == 12 else hours + 12
	elif hours > 23:
		raise ValueError("Invalid 24-hour time")

	return hours * 3600 + minutes * 60

def secondsToTime(seconds: int, use12Hour: bool = False) -> str:
	seconds %= 86400

	hours = seconds // 3600
	minutes = (seconds % 3600) // 60

	if use12Hour:
		period = "AM" if hours < 12 else "PM"
		displayHours = hours % 12 or 12
		return f"{displayHours}:{minutes:02d} {period}"

	return f"{hours:02d}:{minutes:02d}"


def calculateTime(time1: str, time2: str, operation: str, use12Hour: bool = False) -> str:
	operation = operation.strip().lower()

	if operation not in ("+", "-", "add", "minus"):
		raise ValueError("Operation must be '+' or '-'")

	seconds1 = timeToSeconds(time1)
	seconds2 = timeToSeconds(time2)

	if operation in ("+", "add"):
		result = seconds1 + seconds2
	else:
		result = seconds1 - seconds2

	return secondsToTime(result, use12Hour)

class customStr:
	uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
	lowercase = "abcdefghijklmnopqrstuvwxyz"
	numbers = "0123456789"

	def __init__(self, string: Sequence):
		self.string = string

	def isdigit(self: customStr):
		numbers = self.numbers
		return all(i in numbers for i in self.string)

	def capitalise(self: customStr):
		uppercase = self.uppercase
		lowercase = self.lowercase

		if not self.string:
			return ""

		result = []

		for index, letter in enumerate(self.string):
			if index == 0:
				if letter in lowercase:
					pos = lowercase.index(letter)
					result.append(uppercase[pos])
				else:
					result.append(letter)
			else:
				if letter in uppercase:
					pos = uppercase.index(letter)
					result.append(lowercase[pos])
				else:
					result.append(letter)
		
		return "".join(result)

	def upper(self: customStr):
		uppercase = self.uppercase
		lowercase = self.lowercase

		if not self.string:
			return ""

		result = []

		for letter in self.string:
			if letter in lowercase:
				pos = lowercase.index(letter)
				result.append(uppercase[pos])
			else:
				result.append(letter)

		return "".join(result)

	def lower(self: customStr):
		uppercase = self.uppercase
		lowercase = self.lowercase

		if not self.string:
			return ""

		result = []

		for letter in self.string:
			if letter in uppercase:
				pos = uppercase.index(letter)
				result.append(lowercase[pos])
			else:
				result.append(letter)

		return "".join(result)

	def find(self: customStr, sub: Sequence, start: int | None = None, end: int | None = None) -> int:
		subLength = len(sub)
		storedString = self.string
		
		if start is not None:
			storedString = storedString[start:]

		if end is not None:
			storedString = storedString[:end]

		for index, _ in enumerate(storedString):
			if storedString[index:index+subLength] == sub:
				if start and start <= index or end and end > index:
					return index

		return -1

	def index(self: customStr, sub: Sequence, start: int | None = None, end: int | None = None) -> int | ValueError:
		subLength = len(sub)
		storedString = self.string

		if start is not None:
			storedString = storedString[start:]

		if end is not None:
			storedString = storedString[:end]

		for index, _ in enumerate(storedString):
			if storedString[index:index+subLength] == sub:
				if start and start <= index or end and end > index:
					return index

		return ValueError("substring not found")

	def endswith(self: customStr, suffix: Sequence, start: int | None = None, end: int | None = None) -> bool:
		storedString = self.string
		
		if start is not None:
			storedString = storedString[start:]

		if end is not None:
			if start is not None:
				storedString = storedString[:(end - start)]
			else:
				storedString = storedString[:end]

		strLen, suffLen = len(storedString), len(suffix)

		if suffLen > strLen:
			return False

		endSlice = storedString[(strLen - suffLen):]

		return endSlice == suffix

	def startswith(self: customStr, prefix: Sequence, start: int | None = None, end: int | None = None) -> bool:
		storedString = self.string
		
		if start is not None:
			storedString = storedString[start:]

		if end is not None:
			if start is not None:
				storedString = storedString[:(end - start)]
			else:
				storedString = storedString[:end]

		strLen, prefLen = len(storedString), len(prefix)

		if prefLen > strLen:
			return False

		startSlice = storedString[:prefLen]

		return startSlice == prefix


class Sort:
	"""
	Sorting utilities and visualised sorting algorithms.
	"""

	@staticmethod
	def _lpad(list_: Sequence[int], index: int, step: int | None = None, pad: str | None = None) -> str:
		"""
		Left pads up to a specific index for lists using spaces by default.
		"""
		totalLength = len(repr(list_))
		startToIndex = len(repr(list_[:index+1])) - 1
		indexToEnd = len(repr(list_)[startToIndex:])
		indexLength = len(repr(list_[index]))
		resultLength = totalLength - indexToEnd - indexLength

		valueLength = len(str(list_[index]))
		literalLength = len(repr(list_[index]))

		# assume symmetrical difference
		if valueLength != literalLength:
			resultLength += diff(valueLength, literalLength) // 2

		if step is not None:
			resultLength += len(str(step)) + 2

		padder = " "
		if pad is not None:
			padder = pad

		return resultLength * padder

	@staticmethod
	def _isSorted(list_: list[int]) -> bool:
		return all(list_[i] <= list_[i + 1] for i in range(len(list_) - 1))

	@staticmethod
	def _swap(list_: list[int], index: int) -> None:
		list_[index], list_[index + 1] = list_[index + 1], list_[index]

	@staticmethod
	def _listInfo(values: list[int]) -> None:
		print(f"Length: {len(values)}")
		print(f"Range: {min(values)} to {max(values)} ({max(values) - min(values)})")

	@staticmethod
	def _printStepSwap(values: list[int], index: int, step: int) -> None:
		print(f"{step}. " + str(values))
		print(Sort._lpad(values, index, step) + f"{values[index]}--{values[index + 1]}")

	@staticmethod
	def _printStepSelectionSwap(values: list[int], left: int, right: int, step: int) -> None:
		pad2 = (diff(len(Sort._lpad(values, left, step)), len(Sort._lpad(values, right, step))) - 1) * " "
		print(f"{step}. {values}")
		print(
			Sort._lpad(values, left, step)
			+ f"^{pad2}^"
		)

	@staticmethod
	def bubble(values: list[int]) -> list[int]:
		Sort._listInfo(values)
		print("\nSorting...")
		step = 1
		while True:
			swapped = False
			for index in range(len(values) - 1):
				if values[index] > values[index + 1]:
					Sort._printStepSwap(values, index, step)
					Sort._swap(values, index)
					swapped = True
					step += 1
			
			if not swapped:
				print("Sorted!\n")
				break
		return values

	@staticmethod
	def selection(values: list[int]) -> list[int]:
		Sort._listInfo(values)
		print("\nSorting...")
		step = 1
	
		for start in range(len(values) - 1):
			minIndex = start
	
			for index in range(start + 1, len(values)):
				if values[index] < values[minIndex]:
					minIndex = index
	
			if minIndex != start:
				Sort._printStepSelectionSwap(
					values,
					start,
					minIndex,
					step
				)
	
				values[start], values[minIndex] = (
					values[minIndex],
					values[start]
				)
	
				step += 1
	
		print("Sorted!\n")
		return values
