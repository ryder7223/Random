import ast
import io
import keyword
import re
import tokenize
from pathlib import Path


CAMEL_CASE_PATTERN = re.compile(
	r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])"
)

PYTHON_CONSTANTS = {
	"True",
	"False",
	"None",
	"NotImplemented",
	"Ellipsis",
}


PYTHON_KEYWORDS = set(keyword.kwlist)


def toSnakeCase(name):
	"""
	Convert camelCase/PascalCase to snake_case.

	Examples:
		getSublimePaths -> get_sublime_paths
		RuntimeError -> runtime_error
		SQLREL_SYNTAX -> sqlrel_syntax
		HTTPServer -> http_server
	"""
	return CAMEL_CASE_PATTERN.sub("_", name).lower()


def toCamelCase(name):
	"""
	Convert snake_case to camelCase.

	Examples:
		get_sublime_paths -> getSublimePaths
		sqlrel_syntax -> sqlrelSyntax
		hello_world -> helloWorld
	"""
	parts = name.split("_")

	if len(parts) == 1:
		return name

	return parts[0] + "".join(
		part[:1].upper() + part[1:]
		for part in parts[1:]
		if part
	)


def isConstantName(name):
	"""
	Determine whether a name looks like a Python constant.

	This is intentionally only used as a fallback. Constants defined
	inside the file are still converted consistently.
	"""
	return (
		name.isupper()
		and any(character.isalpha() for character in name)
	)


def isValidIdentifier(name):
	return name.isidentifier() and not keyword.iskeyword(name)


def getDefinitionNames(tree):
	"""
	Find identifiers which are actually defined by the source file.

	This includes:

	- functions
	- async functions
	- classes
	- assignments
	- annotated assignments
	- named expressions
	- for-loop variables
	- with/as variables
	- except/as variables
	- import aliases
	- from-import aliases
	- function arguments
	- lambda arguments
	- comprehensions
	"""
	names = set()

	class DefinitionVisitor(ast.NodeVisitor):

		def addTarget(self, target):
			if isinstance(target, ast.Name):
				names.add(target.id)

			elif isinstance(target, (ast.Tuple, ast.List)):
				for element in target.elts:
					self.addTarget(element)

			elif isinstance(target, ast.Starred):
				self.addTarget(target.value)

		def visit_FunctionDef(self, node):
			names.add(node.name)

			for argument in (
				node.args.posonlyargs
				+ node.args.args
				+ node.args.kwonlyargs
			):
				names.add(argument.arg)

			if node.args.vararg:
				names.add(node.args.vararg.arg)

			if node.args.kwarg:
				names.add(node.args.kwarg.arg)

			self.generic_visit(node)

		def visit_AsyncFunctionDef(self, node):
			names.add(node.name)

			for argument in (
				node.args.posonlyargs
				+ node.args.args
				+ node.args.kwonlyargs
			):
				names.add(argument.arg)

			if node.args.vararg:
				names.add(node.args.vararg.arg)

			if node.args.kwarg:
				names.add(node.args.kwarg.arg)

			self.generic_visit(node)

		def visit_ClassDef(self, node):
			names.add(node.name)
			self.generic_visit(node)

		def visit_Assign(self, node):
			for target in node.targets:
				self.addTarget(target)

			self.generic_visit(node)

		def visit_AnnAssign(self, node):
			self.addTarget(node.target)
			self.generic_visit(node)

		def visit_NamedExpr(self, node):
			self.addTarget(node.target)
			self.generic_visit(node)

		def visit_For(self, node):
			self.addTarget(node.target)
			self.generic_visit(node)

		def visit_AsyncFor(self, node):
			self.addTarget(node.target)
			self.generic_visit(node)

		def visit_With(self, node):
			for item in node.items:
				if item.optional_vars:
					self.addTarget(item.optional_vars)

			self.generic_visit(node)

		def visit_AsyncWith(self, node):
			for item in node.items:
				if item.optional_vars:
					self.addTarget(item.optional_vars)

			self.generic_visit(node)

		def visit_ExceptHandler(self, node):
			if node.name:
				if isinstance(node.name, str):
					names.add(node.name)
				else:
					self.addTarget(node.name)

			self.generic_visit(node)

		def visit_Import(self, node):
			for alias in node.names:
				if alias.asname:
					names.add(alias.asname)
				else:
					# For "import pathlib", the local name is
					# pathlib, not Path/etc.
					names.add(alias.name.split(".")[0])

		def visit_ImportFrom(self, node):
			for alias in node.names:
				if alias.name == "*":
					continue

				names.add(
					alias.asname if alias.asname else alias.name
				)

		def visit_Lambda(self, node):
			for argument in (
				node.args.posonlyargs
				+ node.args.args
				+ node.args.kwonlyargs
			):
				names.add(argument.arg)

			if node.args.vararg:
				names.add(node.args.vararg.arg)

			if node.args.kwarg:
				names.add(node.args.kwarg.arg)

			self.generic_visit(node)

		def visit_comprehension(self, node):
			self.addTarget(node.target)
			self.generic_visit(node)

	visitor = DefinitionVisitor()
	visitor.visit(tree)

	return names


def getImportNames(tree):
	"""
	Return names introduced by imports.

	Imported names are deliberately excluded from conversion because
	they belong to external APIs.

	For example:

		from pathlib import Path

	Path remains Path.

	Similarly:

		from pathlib import Path as MyPath

	MyPath remains MyPath because it is an imported API name/alias.
	"""
	names = set()

	for node in ast.walk(tree):

		if isinstance(node, ast.Import):
			for alias in node.names:
				names.add(
					alias.asname
					if alias.asname
					else alias.name.split(".")[0]
				)

		elif isinstance(node, ast.ImportFrom):
			for alias in node.names:
				if alias.name != "*":
					names.add(
						alias.asname
						if alias.asname
						else alias.name
					)

	return names


def getAttributeNames(tree):
	"""
	Get attribute names.

	Attribute names are not local Python identifiers.

	For example:

		Path.read_text()

	"read_text" belongs to Path's API and should not automatically
	be renamed.
	"""
	names = set()

	for node in ast.walk(tree):
		if isinstance(node, ast.Attribute):
			names.add(node.attr)

	return names


def buildNameMap(tree, mode):
	"""
	Build a mapping of original local names to converted names.

	Only names actually defined by this source file are converted.
	Imported/external names are protected.
	"""
	definitionNames = getDefinitionNames(tree)
	importNames = getImportNames(tree)
	attributeNames = getAttributeNames(tree)

	nameMap = {}

	for name in definitionNames:

		if name in PYTHON_KEYWORDS:
			continue

		if name in PYTHON_CONSTANTS:
			continue

		if name in importNames:
			continue

		# Attribute names are normally external API names.
		# Do not convert them merely because an identical local
		# identifier happens to exist elsewhere.
		if name in attributeNames:
			continue

		if mode == "snake":
			convertedName = toSnakeCase(name)

		elif mode == "camel":
			convertedName = toCamelCase(name)

		else:
			raise ValueError(
				f"Unknown conversion mode: {mode}"
			)

		if convertedName != name:
			nameMap[name] = convertedName

	return nameMap


def getNameContext(tokens, index):
	"""
	Determine the significant tokens immediately surrounding a NAME.

	This is used for special Python constructs where blindly changing
	a NAME would be incorrect.
	"""
	previousToken = None
	nextToken = None

	for position in range(index - 1, -1, -1):
		token = tokens[position]

		if token.type in {
			tokenize.INDENT,
			tokenize.DEDENT,
			tokenize.NEWLINE,
			tokenize.NL,
			tokenize.COMMENT,
			tokenize.ENCODING,
		}:
			continue

		previousToken = token
		break

	for position in range(index + 1, len(tokens)):
		token = tokens[position]

		if token.type in {
			tokenize.INDENT,
			tokenize.DEDENT,
			tokenize.NEWLINE,
			tokenize.NL,
			tokenize.COMMENT,
			tokenize.ENCODING,
		}:
			continue

		nextToken = token
		break

	return previousToken, nextToken


def shouldConvertName(
	token,
	previousToken,
	nextToken,
	nameMap
):
	"""
	Determine whether a NAME token should be converted.
	"""
	name = token.string

	if name not in nameMap:
		return False

	if keyword.iskeyword(name):
		return False

	if name in PYTHON_CONSTANTS:
		return False

	# Python's soft keywords.
	if name in {"match", "case", "_"}:
		return False

	# Never convert an identifier used after raise/except.
	#
	# Example:
	#	raise RuntimeError
	#	except RuntimeError
	#
	# RuntimeError is not defined by this file, so normally it
	# would not be in nameMap anyway. This additionally protects
	# against local definitions with these names.
	if previousToken and previousToken.type == tokenize.NAME:
		if previousToken.string in {"raise", "except"}:
			return False

	# Never convert attribute names.
	#
	# Example:
	#	object.getValue()
	#
	# "getValue" is an API/member name, not necessarily one of
	# our local definitions.
	if previousToken and previousToken.string == ".":
		return False

	# Never convert imported names.
	#
	# This mainly protects unusual import constructs.
	if previousToken and previousToken.string in {
		"import",
		"from",
		"as",
	}:
		return False

	# Function/class definitions are deliberately converted because
	# they are local declarations.
	if previousToken and previousToken.string in {
		"def",
		"class",
	}:
		return True

	return True


def convertFile(filePath, mode):
	data = filePath.read_text(encoding="utf-8")

	try:
		tree = ast.parse(data, filename=str(filePath))
	except SyntaxError as error:
		raise RuntimeError(
			f"Could not parse {filePath}:\n{error}"
		) from error

	nameMap = buildNameMap(tree, mode)

	if not nameMap:
		print(f"No local identifiers to convert: {filePath}")
		return False

	tokens = list(
		tokenize.generate_tokens(
			io.StringIO(data).readline
		)
	)

	convertedTokens = []

	for index, token in enumerate(tokens):

		if token.type != tokenize.NAME:
			convertedTokens.append(token)
			continue

		previousToken, nextToken = getNameContext(
			tokens,
			index
		)

		if shouldConvertName(
			token,
			previousToken,
			nextToken,
			nameMap
		):
			token = token._replace(
				string=nameMap[token.string]
			)

		convertedTokens.append(token)

	convertedData = tokenize.untokenize(convertedTokens)

	if convertedData == data:
		print(f"No changes required: {filePath}")
		return False

	filePath.write_text(
		convertedData,
		encoding="utf-8",
		newline=""
	)

	print(f"Converted: {filePath}")

	print()
	print("Changes:")
	for originalName, convertedName in nameMap.items():
		print(
			f"  {originalName} -> {convertedName}"
		)

	return True


def main():
	import argparse

	parser = argparse.ArgumentParser(
		description=(
			"Convert Python identifiers between camelCase "
			"and snake_case."
		)
	)

	parser.add_argument(
		"file",
		nargs="?",
		default="main.py",
		help="Python file to convert."
	)

	parser.add_argument(
		"--to-snake",
		action="store_true",
		help="Convert local identifiers to snake_case."
	)

	parser.add_argument(
		"--to-camel",
		action="store_true",
		help="Convert local identifiers to camelCase."
	)

	arguments = parser.parse_args()

	if arguments.to_snake and arguments.toCamel:
		parser.error(
			"--to-snake and --to-camel cannot be used together."
		)

	if arguments.to_camel:
		mode = "camel"
	else:
		mode = "snake"

	filePath = Path(arguments.file)

	if not filePath.exists():
		raise FileNotFoundError(
			f"Could not find: {filePath.resolve()}"
		)

	convertFile(
		filePath,
		mode
	)


if __name__ == "__main__":
	main()