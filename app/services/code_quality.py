"""
Code quality scoring (Part 14): rule-based style checks on a learner's
passing solution, shown after solving and shared with the Coach's review.

The code is read with Python's ast module, which parses code into its
structure without running it, so the server still never executes learner
code (decision DR-03). Style never affects XP: correctness is decided by
the tests alone (decision DR-09).
"""

import ast

MAX_LINE_LENGTH = 79  # PEP 8
MAX_NESTING = 3

# Single letters that are conventional and clear in beginner code: loop
# counters, and common maths names.
ALLOWED_SHORT_NAMES = {"i", "j", "k", "n", "x", "y", "z", "_"}

# Python's own names that beginners most often overwrite by accident.
BUILTIN_NAMES = {
    "all", "any", "bool", "dict", "filter", "float", "id", "input", "int",
    "iter", "len", "list", "map", "max", "min", "next", "open", "print",
    "range", "set", "sorted", "str", "sum", "tuple", "type", "zip",
}

# Statements that start a nested block.
_BLOCKS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Match)


def _names_in(code_tree):
    """Collect assigned names, used names, loop names, and argument names."""
    assigned = {}
    used = set()
    loop_names = set()
    arguments = set()

    for node in ast.walk(code_tree):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                assigned.setdefault(node.id, node.lineno)
            else:
                used.add(node.id)
        elif isinstance(node, ast.arg):
            arguments.add(node.arg)
        if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            loop_names.update(n.id for n in ast.walk(node.target) if isinstance(n, ast.Name))

    return assigned, used, loop_names, arguments


def _function_names(code_tree):
    return {
        node.name
        for node in ast.walk(code_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _inner_blocks(node):
    """The nested bodies of a block statement (an if's else is handled separately)."""
    if isinstance(node, ast.If):
        return [node.body]
    if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        return [node.body, node.orelse]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [node.body]
    if isinstance(node, ast.Try):
        return [node.body, *(handler.body for handler in node.handlers), node.orelse, node.finalbody]
    if isinstance(node, ast.Match):
        return [case.body for case in node.cases]
    return []


def _deepest(statements, depth=0):
    """The deepest block nesting among these statements.

    An elif is written as an if inside the previous if's else, but it reads
    as the same level, so an if/elif/elif chain counts as one level.
    """
    deepest = depth
    for node in statements:
        if isinstance(node, _BLOCKS):
            for body in _inner_blocks(node):
                deepest = max(deepest, _deepest(body, depth + 1))
            if isinstance(node, ast.If) and node.orelse:
                is_elif = len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)
                deepest = max(deepest, _deepest(node.orelse, depth if is_elif else depth + 1))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            deepest = max(deepest, _deepest(node.body, depth))
    return deepest


def _is_true_false_or_none(node):
    """True for the literal values True, False, or None in code."""
    return isinstance(node, ast.Constant) and (node.value is None or isinstance(node.value, bool))


def _unclear_comparison_lines(code_tree):
    """Lines that compare with == or != to True, False, or None."""
    lines = set()
    for node in ast.walk(code_tree):
        if not isinstance(node, ast.Compare):
            continue
        uses_equality = any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)
        sides = [node.left, *node.comparators]
        if uses_equality and any(_is_true_false_or_none(side) for side in sides):
            lines.add(node.lineno)
    return sorted(lines)


def _listed(names):
    return ", ".join(sorted(names))


def _check(title, passed, detail):
    return {"title": title, "passed": passed, "detail": "" if passed else detail}


def analyze(code):
    """Score a solution's style.

    Returns:
        {"score": 0 to 100, "rating": "Excellent", "Good", or "Needs work",
         "checks": [{"title", "passed", "detail"}, ...]}, or None if the
        code cannot be parsed (a passing solution always can).
    """
    try:
        code_tree = ast.parse(code)
    except SyntaxError:
        return None

    assigned, used, loop_names, arguments = _names_in(code_tree)
    functions = _function_names(code_tree)
    all_names = set(assigned) | arguments | functions

    short = {n for n in assigned if len(n) == 1 and n not in ALLOWED_SHORT_NAMES and n not in loop_names}
    not_snake = {n for n in all_names if not n.isupper() and n != n.lower()}
    shadowed = {n for n in assigned if n in BUILTIN_NAMES}
    unused = {n for n in assigned if n not in used and n not in loop_names and n != "_"}
    depth = _deepest(code_tree.body)
    long_lines = [
        number for number, line in enumerate(code.splitlines(), start=1)
        if len(line) > MAX_LINE_LENGTH
    ]
    unclear = _unclear_comparison_lines(code_tree)
    bare_excepts = sorted(
        node.lineno for node in ast.walk(code_tree)
        if isinstance(node, ast.ExceptHandler) and node.type is None
    )

    checks = [
        _check(
            "Descriptive names", not short,
            f"Short names such as {_listed(short)} don't say what they hold. "
            "Try names like total, word, or score.",
        ),
        _check(
            "snake_case names", not not_snake,
            f"Python names use lower case with underscores, so {_listed(not_snake)} "
            "would be written like word_count.",
        ),
        _check(
            "No built-in names reused", not shadowed,
            f"{_listed(shadowed)} is already a built-in Python name. Reusing it hides "
            "the original, so use a different name such as items or text.",
        ),
        _check(
            "No unused variables", not unused,
            f"{_listed(unused)} is given a value but never used. Remove it, or use it.",
        ),
        _check(
            "Shallow nesting", depth <= MAX_NESTING,
            f"Your code nests {depth} levels deep. More than {MAX_NESTING} is hard to "
            "follow: try combining conditions with and, or returning early.",
        ),
        _check(
            "Short lines", not long_lines,
            f"Line {', '.join(map(str, long_lines))} is longer than {MAX_LINE_LENGTH} "
            "characters. Split long lines to keep them readable.",
        ),
        _check(
            "Clear comparisons", not unclear,
            f"Line {', '.join(map(str, unclear))} compares with == to True, False, or "
            "None. Write if done: or if value is None: instead.",
        ),
        _check(
            "Specific exceptions", not bare_excepts,
            f"Line {', '.join(map(str, bare_excepts))} uses a bare except:, which hides "
            "every error. Name the error you expect, such as except ValueError:.",
        ),
    ]

    passed = sum(check["passed"] for check in checks)
    score = round(100 * passed / len(checks))
    rating = "Excellent" if score >= 90 else "Good" if score >= 70 else "Needs work"
    return {"score": score, "rating": rating, "checks": checks}