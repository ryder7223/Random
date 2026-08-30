"""
Use only for sublime text. This will handle setting up and removing SQL Relational Notation syntax highlighting. Running it with no arguments will default it to the install option.
"""

from pathlib import Path
import os
import re
import shutil
import sys


sqlrel_syntax = r"""%YAML 1.2
---
name: SQL Relational Notation
file_extensions:
  - sqlrel
scope: source.relational

contexts:
  main:
    # Table name
    - match: '^\s*([A-Z][A-Z0-9_]*)\s*(\()'
      captures:
        1: support.function.relational
        2: punctuation.section.parens.begin.relational
      push: table

  table:
    # First column
    - match: '^\s*([a-zA-Z_][a-zA-Z0-9_]*)'
      scope: variable.other.member.declaration.relational

    # PK / FK
    - match: '\s(PK|FK)\b'
      scope: storage.modifier.relational

    # Commas
    - match: ','
      scope: punctuation.separator.sequence.relational

    # End of table
    - match: '\)'
      scope: punctuation.section.parens.end.relational
      pop: true
"""


sqlrel_fenced_syntax = """  fenced-sqlrel:
    - match: |-
         (?x)
          {{fenced_code_block_start}}
          (?i:\\s*(sqlrel))
          {{fenced_code_block_trailing_infostring_characters}}
      captures:
        0: meta.code-fence.definition.begin.markdown-gfm
        2: punctuation.definition.raw.code-fence.begin.markdown
        5: constant.other.language-name.markdown
        6: comment.line.infostring.markdown
        7: meta.fold.code-fence.begin.markdown
      embed: scope:source.relational
      embed_scope:
        meta.code-fence.body.markdown-gfm
        markup.raw.code-fence.relational.markdown-gfm
        source.relational
      escape: '{{fenced_code_block_escape}}'
      escape_captures:
        0: meta.code-fence.definition.end.markdown-gfm
        1: punctuation.definition.raw.code-fence.end.markdown
        2: meta.fold.code-fence.end.markdown
"""


fenced_sqlrel_include = "    - include: fenced-sqlrel"


def get_sublime_paths():
	app_data = os.environ.get("APPDATA")

	if not app_data:
		raise RuntimeError(
		 "Could not determine the Windows APPDATA directory."
		)

	sublime_directory = Path(app_data) / "Sublime Text"
	packages_directory = sublime_directory / "Packages"

	markdown_file = (
	 packages_directory
	 / "Markdown"
	 / "Markdown.sublime-syntax"
	)

	user_directory = packages_directory / "User"
	sqlrel_file = user_directory / "sqlrel.sublime-syntax"

	return markdown_file, user_directory, sqlrel_file


def read_text_file(file_path):
	try:
		return file_path.read_text(encoding="utf-8")
	except UnicodeDecodeError:
		return file_path.read_text(encoding="utf-8-sig")


def create_backup(file_path):
	backup_path = file_path.with_suffix(
	 file_path.suffix + ".backup"
	)

	if backup_path.exists():
		counter = 1

		while True:
			backup_path = file_path.with_suffix(
			 file_path.suffix + f".backup{counter}"
			)

			if not backup_path.exists():
				break

			counter += 1

	shutil.copy2(file_path, backup_path)

	return backup_path


# =========================================================
# INSTALLATION
# =========================================================

def install_sqlrel_syntax(sqlrel_file):
	sqlrel_file.parent.mkdir(
	 parents=True,
	 exist_ok=True
	)

	# Do not silently overwrite a different syntax file.
	if sqlrel_file.exists():
		existing_data = read_text_file(sqlrel_file)

		if existing_data != sqlrel_syntax:
			raise RuntimeError(
			 f"{sqlrel_file} already exists and does not match "
			 "the SQL Relational Notation syntax installed by "
			 "this script.\n"
			 "Refusing to overwrite it."
			)

		print(f"Already installed: {sqlrel_file}")
		return False

	sqlrel_file.write_text(
	 sqlrel_syntax,
	 encoding="utf-8",
	 newline="\n"
	)

	print(f"Installed: {sqlrel_file}")

	return True


def add_fenced_syntax_include(markdown_data):
	if fenced_sqlrel_include in markdown_data:
		return markdown_data, False

	sql_include = "    - include: fenced-sql"

	position = markdown_data.find(sql_include)

	if position == -1:
		raise RuntimeError(
		 "Could not find 'fenced-sql' in the Markdown syntax."
		)

	line_end = markdown_data.find("\n", position)

	if line_end == -1:
		raise RuntimeError(
		 "Could not determine where to insert fenced-sqlrel."
		)

	insert_position = line_end + 1

	markdown_data = (
	 markdown_data[:insert_position]
	 + fenced_sqlrel_include
	 + "\n"
	 + markdown_data[insert_position:]
	)

	return markdown_data, True


def get_fenced_sqlrel_context_pattern():
	return re.compile(
	 r"(?ms)"
	 r"^  fenced-sqlrel:\s*\n"
	 r".*?"
	 r"(?=^  fenced-[A-Za-z0-9_-]+:\s*$|\Z)"
	)


def is_our_fenced_sqlrel_context(context_data):
	required_parts = (
	 "(?i:\\s*(sqlrel))",
	 "embed: scope:source.relational",
	 "markup.raw.code-fence.relational.markdown-gfm",
	 "source.relational",
	 "{{fenced_code_block_escape}}",
	)

	return all(
	 required_part in context_data
	 for required_part in required_parts
	)


def normalise_fenced_sqlrel_spacing(markdown_data):
	"""
	Normalise only the whitespace immediately surrounding the
	installer's fenced-sqlrel context.

	This prevents repeated installations from accumulating
	empty lines.
	"""

	pattern = get_fenced_sqlrel_context_pattern()
	match = pattern.search(markdown_data)

	if not match:
		return markdown_data, False

	context_data = match.group(0)

	if not is_our_fenced_sqlrel_context(context_data):
		raise RuntimeError(
		 "Found a fenced-sqlrel context, but it does not "
		 "match the context installed by this script.\n"
		 "Refusing to modify it automatically."
		)

 # Remove all trailing newlines from the captured context.
	context_data = context_data.rstrip("\r\n")

	# Determine the whitespace immediately before the context.
	before = markdown_data[:match.start()]
	after = markdown_data[match.end():]

	# Keep exactly one blank line before the context.
	before = re.sub(
	 r"\n[ \t]*(?:\n[ \t]*)*$",
	 "\n\n",
	 before
	)

	# Keep exactly one blank line after the context, provided
	# another top-level context follows.
	if re.match(
	 r"^[ \t]*\n?[ \t]*  fenced-[A-Za-z0-9_-]+:",
	 after
	):
		after = re.sub(
		 r"^(?:\r?\n[ \t]*)*",
		 "\n\n",
		 after
		)

	new_data = before + context_data + after

	return new_data, new_data != markdown_data


def add_fenced_sqlrel_context(markdown_data):
 # If the context already exists, do not insert another one.
 # Instead, normalise its surrounding whitespace.
	if re.search(
	 r"(?m)^  fenced-sqlrel:\s*$",
	 markdown_data
	):
		return normalise_fenced_sqlrel_spacing(markdown_data)

	sql_match = re.search(
	 r"(?m)^  fenced-sql:\s*$",
	 markdown_data
	)

	if not sql_match:
		raise RuntimeError(
		 "Could not find the 'fenced-sql' context "
		 "in the Markdown syntax."
		)

 # Find the next top-level fenced context.
	next_context_match = re.search(
	 r"(?m)^  fenced-[A-Za-z0-9_-]+:\s*$",
	 markdown_data[sql_match.end():]
	)

	if next_context_match:
		insert_position = (
		 sql_match.end()
		 + next_context_match.start()
		)

		# The next context already begins at a line boundary.
		# Strip surrounding whitespace from the insertion so
		# we control exactly how many blank lines are created.
		insertion = (
		 "\n\n"
		 + sqlrel_fenced_syntax.rstrip("\r\n")
		 + "\n\n"
		)

		markdown_data = (
		 markdown_data[:insert_position]
		 + insertion
		 + markdown_data[insert_position:]
		)

	else:
	 # fenced-sql is the final context.
		insertion = (
		 "\n\n"
		 + sqlrel_fenced_syntax.rstrip("\r\n")
		 + "\n"
		)

		markdown_data = (
		 markdown_data.rstrip("\r\n")
		 + insertion
		)

 # Ensure the newly inserted context has canonical spacing.
	markdown_data, _ = normalise_fenced_sqlrel_spacing(
	 markdown_data
	)

	return markdown_data, True


def patch_markdown_syntax(markdown_file):
	markdown_data = read_text_file(markdown_file)
	original_data = markdown_data

	markdown_data, include_changed = add_fenced_syntax_include(
	 markdown_data
	)

	markdown_data, context_changed = add_fenced_sqlrel_context(
	 markdown_data
	)

	if markdown_data == original_data:
		print("Markdown syntax already contains sqlrel support.")
		return False

	backup_path = create_backup(markdown_file)

	markdown_file.write_text(
	 markdown_data,
	 encoding="utf-8",
	 newline="\n"
	)

	print(f"Updated:  {markdown_file}")
	print(f"Backup:   {backup_path}")

	if include_changed:
		print("Added:    fenced-sqlrel include")

	if context_changed:
		print("Added:    fenced-sqlrel context/formatting")

	return True


def verify_installation(markdown_file, sqlrel_file):
	if not sqlrel_file.exists():
		raise RuntimeError(
		 "Verification failed: sqlrel.sublime-syntax "
		 "was not installed."
		)

	markdown_data = read_text_file(markdown_file)

	if fenced_sqlrel_include not in markdown_data:
		raise RuntimeError(
		 "Verification failed: fenced-sqlrel include "
		 "is missing."
		)

	if not re.search(
	 r"(?m)^  fenced-sqlrel:\s*$",
	 markdown_data
	):
		raise RuntimeError(
		 "Verification failed: fenced-sqlrel context "
		 "is missing."
		)

	if "embed: scope:source.relational" not in markdown_data:
		raise RuntimeError(
		 "Verification failed: source.relational "
		 "is not embedded."
		)

	print()
	print("Installation verified successfully.")


def install():
	print("SQL Relational Notation - Installer")
	print("=" * 52)
	print()

	markdown_file, user_directory, sqlrel_file = get_sublime_paths()

	print(f"Markdown syntax: {markdown_file}")
	print(f"User package:    {user_directory}")
	print(f"SQLREL syntax:   {sqlrel_file}")
	print()

	if not markdown_file.exists():
		raise FileNotFoundError(
		 "Could not find the Sublime Text Markdown syntax at:\n"
		 f"{markdown_file}\n\n"
		 "Make sure Sublime Text is installed and that "
		 "the Markdown package is available."
		)

	install_sqlrel_syntax(sqlrel_file)
	patch_markdown_syntax(markdown_file)
	verify_installation(markdown_file, sqlrel_file)


# =========================================================
# UNINSTALLATION
# =========================================================

def remove_fenced_syntax_include(markdown_data):
 # Only remove the exact line belonging to this installer.
	pattern = (
	 r"(?m)^"
	 + re.escape(fenced_sqlrel_include)
	 + r"\r?\n?"
	)

	new_data, count = re.subn(
	 pattern,
	 "",
	 markdown_data
	)

	return new_data, count > 0


def remove_fenced_sqlrel_context(markdown_data):
	"""
	Remove exactly the fenced-sqlrel context installed by this
	script.

	The context ends immediately before the next top-level
	fenced-* context.
	"""

	pattern = get_fenced_sqlrel_context_pattern()

	match = pattern.search(markdown_data)

	if not match:
		return markdown_data, False

	context_data = match.group(0)

	# Safety check: only remove a context that contains the
	# exact implementation installed by this script.
	if not is_our_fenced_sqlrel_context(context_data):
		raise RuntimeError(
		 "Found a fenced-sqlrel context, but it does not "
		 "match the context installed by this script.\n"
		 "Refusing to remove it automatically."
		)

	before = markdown_data[:match.start()]
	after = markdown_data[match.end():]

	# Remove whitespace belonging to our context, while keeping
	# the surrounding Markdown syntax clean.
	before = re.sub(
	 r"\n[ \t]*(?:\n[ \t]*)*$",
	 "\n",
	 before
	)

	after = re.sub(
	 r"^(?:\r?\n[ \t]*)*",
	 "\n",
	 after
	)

	new_data = before + after

	return new_data, True


def remove_sqlrel_syntax(sqlrel_file):
	if not sqlrel_file.exists():
		print(f"Already removed: {sqlrel_file}")
		return False

	existing_data = read_text_file(sqlrel_file)

	# Never delete a file that happens to have the same filename
	# but was created by something else.
	if existing_data != sqlrel_syntax:
		raise RuntimeError(
		 f"Refusing to delete {sqlrel_file}.\n"
		 "The file exists, but its contents do not exactly "
		 "match the SQL Relational Notation syntax installed "
		 "by this script."
		)

	sqlrel_file.unlink()

	print(f"Removed: {sqlrel_file}")

	return True


def uninstall_markdown_changes(markdown_file):
	markdown_data = read_text_file(markdown_file)
	original_data = markdown_data

	markdown_data, include_changed = remove_fenced_syntax_include(
	 markdown_data
	)

	markdown_data, context_changed = remove_fenced_sqlrel_context(
	 markdown_data
	)

	if markdown_data == original_data:
		print("Markdown syntax does not contain installed sqlrel support.")
		return False

	backup_path = create_backup(markdown_file)

	markdown_file.write_text(
	 markdown_data,
	 encoding="utf-8",
	 newline="\n"
	)

	print(f"Updated:  {markdown_file}")
	print(f"Backup:   {backup_path}")

	if include_changed:
		print("Removed:  fenced-sqlrel include")

	if context_changed:
		print("Removed:  fenced-sqlrel context")

	return True


def verify_uninstallation(markdown_file, sqlrel_file):
	if sqlrel_file.exists():
		raise RuntimeError(
		 "Uninstallation verification failed: "
		 "sqlrel.sublime-syntax still exists."
		)

	markdown_data = read_text_file(markdown_file)

	if fenced_sqlrel_include in markdown_data:
		raise RuntimeError(
		 "Uninstallation verification failed: "
		 "fenced-sqlrel include still exists."
		)

	if re.search(
	 r"(?m)^  fenced-sqlrel:\s*$",
	 markdown_data
	):
		raise RuntimeError(
		 "Uninstallation verification failed: "
		 "fenced-sqlrel context still exists."
		)

	print()
	print("Uninstallation verified successfully.")


def uninstall():
	print("SQL Relational Notation - Uninstaller")
	print("=" * 52)
	print()

	markdown_file, user_directory, sqlrel_file = get_sublime_paths()

	print(f"Markdown syntax: {markdown_file}")
	print(f"SQLREL syntax:   {sqlrel_file}")
	print()

	if not markdown_file.exists():
		raise FileNotFoundError(
		 "Could not find the Sublime Text Markdown syntax at:\n"
		 f"{markdown_file}"
		)

 # Modify Markdown first. If the syntax file is somehow not
 # ours, the safety checks prevent deleting it.
	uninstall_markdown_changes(markdown_file)
	remove_sqlrel_syntax(sqlrel_file)

	verify_uninstallation(
	 markdown_file,
	 sqlrel_file
	)


# =========================================================
# ENTRY POINT
# =========================================================

def main():
	arguments = [
	 argument.lower()
	 for argument in sys.argv[1:]
	]

	if len(arguments) > 1:
		print(
		 "Usage:\n"
		 "  python installSQLRelSyntax.py install\n"
		 "  python installSQLRelSyntax.py uninstall"
		)
		sys.exit(1)

	mode = arguments[0] if arguments else "install"

	try:
		if mode == "install":
			install()

		elif mode == "uninstall":
			uninstall()

		else:
			print(
			 f"Unknown command: {mode}\n\n"
			 "Usage:\n"
			 "  python installSQLRelSyntax.py install\n"
			 "  python installSQLRelSyntax.py uninstall"
			)
			sys.exit(1)

	except Exception as error:
		print()
		print(f"Operation failed: {error}")
		sys.exit(1)


if __name__ == "__main__":
	main()
