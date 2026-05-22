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

def printFunctionTime(func: Callable[..., Any], runs: int = 10, *args, **kwargs) -> tuple[list[float], list[Any | Exception]]:
	times, result = functionTime(func, runs=runs, *args, **kwargs)

	print(f"\nShortest runtime: {min(times):.8f} seconds")
	print(f"Longest runtime: {max(times):.8f} seconds")
	print(f"\nAverage runtime: {sum(times) / len(times):.8f} seconds")

	return times, result

def printTree(node, indent=0):
	prefix = "  " * indent

	if not isinstance(node, (tuple, list)):
		print(prefix + repr(node))
		return

	print(prefix + "[")

	for item in node:
		printTree(item, indent + 1)

	print(prefix + "]")

def calcPerc(*values, decimals: int = 2) -> None:
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

def mcStacks(amountInput: str, stackSizeInput: int):
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
	return uuid.getnode()

def odd(n: int) -> bool:
	return True if n & 1 else False

def even(n: int) -> bool:
	return False if n & 1 else True

def version():
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
	reversedHex = bytes.fromhex(str(hex(n))[2:])[::-1].hex()
	return " ".join([reversedHex[i:i+2] for i in range(0, len(reversedHex), 2)])

def randomList(length: int, minimum: int, maximum: int) -> list:
	return [random.randint(minimum, maximum) for _ in range(length)]

class Sort:

	@staticmethod
	def isSorted(list_: list) -> bool:
		return all(list_[i] <= list_[i + 1] for i in range(len(list_) - 1))

	@staticmethod
	def swap(list_, index):
		list_[index], list_[index + 1] = list_[index + 1], list_[index]
		

	@staticmethod
	def bubble(values: list):
		print(f"Length: {len(values)}")
		print(f"Range: {min(values)} to {max(values)} ({max(values) - min(values)})")
		print("\nSorting...")
		step = 1
		while True:
			swapped = False

			for index in range(len(values) - 1):
				if values[index] > values[index + 1]:
					print(f"{step}. " + str(values))
					print(len(str(step)) * " " + "   " + " " * index * 3 + f"{values[index]}--{values[index + 1]}")
					Sort.swap(values, index)
					swapped = True
					step += 1
			
			if not swapped:
				print("Sorted!\n")
				break
		return values

print(Sort.bubble(randomList(5, 0, 10)))
