from typing import Generator, Any, Callable, Iterable
import time
import ast
import operator
import math
import uuid
import sys
from datetime import datetime, timezone
import random

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
	func: Callable[..., Any],
	runs: int = 10,
	iterableArgs: Iterable[tuple[Any, ...]] | None = None
) -> tuple[list[float], list[Any | Exception]]:

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

	times = []
	results = []

	if iterableArgs is not None:
		iterableArgs = list(iterableArgs)
		runs = len(iterableArgs)
		actualRuns = iterableArgs
	else:
		if runs <= 0:
			raise ValueError("runs must be greater than 0")
		actualRuns = [()] * runs

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

def printFunctionTime(func: Callable[..., Any], runs: int = 10, iterableArgs: Iterable[tuple[Any, ...]] | None = None) -> tuple[list[float], list[Any | Exception]]:
	"""
	Calls functionTime() and prints the shortest, longest, and average runtimes.
	Functions exactly the same as functionTime() so returns the same data.
	"""
	times, result = functionTime(func, runs=runs, iterableArgs=iterableArgs)

	print(f"\nShortest runtime: {min(times):.8f} seconds")
	print(f"Longest runtime: {max(times):.8f} seconds")
	print(f"\nAverage runtime: {sum(times) / len(times):.8f} seconds")

	return times, result

def printTree(node, indent=0):
	"""
	Visualises lists through indented printing.
	"""
	prefix = "  " * indent

	if not isinstance(node, (tuple, list)):
		print(prefix + repr(node))
		return

	print(prefix + "[")

	for item in node:
		printTree(item, indent + 1)

	print(prefix + "]")

def polygonalNumber(order: int, sides: int) -> int:
	"""
	Generates polygonal numbers of any side conut.
	"""
	return ((sides - 2) * order * order - (sides - 4) * order) // 2

def calcPerc(*values: tuple[int], decimals: int = 2) -> None:
	"""
	Prints the relative percentages of any amount of integers out of their added total.
	"""
	numericValues = []
	try:
		for v in values:
			if isinstance(v, str) and v.isdigit():
				decimals = int(v)
			else:
				numericValues.append(v)
		
		total = sum(numericValues)
		for value in numericValues:
			percentage = round(100 * (value / total), decimals)
			print(f"{value}: {percentage}%")
	except:
		print("Invalid input")

def generateIp(public: bool = True):
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

def mcStacks(amountInput: str, stackSizeInput: int):
	"""
	Calculates stacks of items, supporting arithmatic in the input. e.g.
	`mcStacks(\"8*8*5 + 45\", 64)`
	"""
	allowedOps = {
		ast.Add: operator.add,
		ast.Sub: operator.sub,
		ast.Mult: operator.mul,
		ast.Div: operator.truediv,
		ast.FloorDiv: operator.floordiv,
		ast.Mod: operator.mod,
		ast.Pow: operator.pow,
		ast.USub: operator.neg,
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

	def fixValue(value):
		if value is None:
			return 0.0
		return math.floor(value)

	def findStacks(amount, stackSize):
		return [amount // stackSize, amount % stackSize]


	# --- parse inputs ---
	def resolve(value):
		if isinstance(value, (int, float)):
			return value
		if isinstance(value, str):
			try:
				return int(value)
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
	return True if n & 1 else False

def even(n: int) -> bool:
	return False if n & 1 else True

def version():
	"""
	Prints the current python version.
	"""
	print(f"Python version: {sys.version}")

def dec2bin(x: int | str) -> str:
	"""
	Converts a decimal integer to a binary string without the '0b' prefix.
	"""
	return bin(x)[2:] if isinstance(x, int) else bin(int(x))[2:]

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

def intToHexRev(n):
	"""
	Converts integers to hex and reverses the hex in pairs of two,
	only accepts integers that convert to an even length hex. e.g.
	`482024245324` becomes `4c 48 e2 3a 70`.
	"""
	reversedHex = bytes.fromhex(str(hex(n))[2:])[::-1].hex()
	return " ".join([reversedHex[i:i+2] for i in range(0, len(reversedHex), 2)])

def randomList(length: int, minimum: int, maximum: int) -> list:
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
		result *= -1
	return result

class Sort:
	"""
	Sorting utilities and visualised sorting algorithms.
	"""

	@staticmethod
	def lpad(list_, index, step: int | None = None, pad: str | None = None):
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
	def _isSorted(list_: list) -> bool:
		return all(list_[i] <= list_[i + 1] for i in range(len(list_) - 1))

	@staticmethod
	def _swap(list_, index):
		list_[index], list_[index + 1] = list_[index + 1], list_[index]

	@staticmethod
	def _listInfo(values: list):
		print(f"Length: {len(values)}")
		print(f"Range: {min(values)} to {max(values)} ({max(values) - min(values)})")

	@staticmethod
	def _printStepSwap(values: list, index: int, step: int):
		print(f"{step}. " + str(values))
		print(Sort.lpad(values, index, step) + f"{values[index]}--{values[index + 1]}")

	@staticmethod
	def _printStepSelectionSwap(values: list, left: int, right: int, step: int):
		pad2 = (diff(len(Sort.lpad(values, left, step)), len(Sort.lpad(values, right, step))) - 1) * " "
		print(f"{step}. {values}")
		print(
			Sort.lpad(values, left, step)
			+ f"^{pad2}^"
		)

	@staticmethod
	def bubble(values: list):
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
	def selection(values: list):
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
