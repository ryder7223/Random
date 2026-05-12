from typing import Generator, Any, NoReturn
import time
import ast
import operator
import math
import uuid
import sys
from datetime import datetime, timezone

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

def functionTime(func, runs: int = 10, *args, **kwargs) -> tuple[float, float, float]:
	"""
	Measures the average execution time of func over a given number of runs.
	"""
	times = []

	if runs <= 0:
		return 0.0, 0.0, 0.0

	for _ in range(runs):
		start = time.perf_counter()
		func(*args, **kwargs)
		end = time.perf_counter()
		times.append(end - start)

	# End high-resolution timer
	return sum(times) / runs, min(times), max(times)

def printFunctionTime(func, runs: int = 10, *args, **kwargs):
	avg, minimum, maximum = functionTime(func, runs=runs, *args, **kwargs)

	print(f"\nShortest runtime: {minimum:.8f} seconds")
	print(f"Longest runtime: {maximum:.8f} seconds")
	print(f"\nAverage runtime: {avg:.8f} seconds")

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

def unixToTime(unixTime: int) -> str:
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