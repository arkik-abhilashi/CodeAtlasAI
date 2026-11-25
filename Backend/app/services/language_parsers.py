import ast
from functools import lru_cache
import re
from pathlib import PurePosixPath
from typing import Any

LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript JSX", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript JSX", ".mts": "TypeScript", ".cts": "TypeScript",
}
SUPPORTED_SUFFIXES = set(LANGUAGES)


def language_for_path(path: str) -> str | None:
    return LANGUAGES.get(PurePosixPath(path).suffix.lower())


def _parse_python(source: str) -> dict[str, Any]:
    result: dict[str, Any] = {"classes": [], "types": [], "functions": [], "methods": [], "imports": [], "exports": [], "variables": []}
    try:
        root = ast.parse(source)
    except SyntaxError as exc:
        result["error"] = f"Syntax error on line {exc.lineno}: {exc.msg}"
        return result
    class Extractor(ast.NodeVisitor):
        class_depth = 0
        function_depth = 0

        def visit_ClassDef(self, node):
            result["classes"].append({"name": node.name, "line": node.lineno, "end_line": node.end_lineno})
            self.class_depth += 1
            self.generic_visit(node)
            self.class_depth -= 1

        def visit_FunctionDef(self, node):
            self._function(node, False)

        def visit_AsyncFunctionDef(self, node):
            self._function(node, True)

        def _function(self, node, is_async):
            item = {"name": node.name, "line": node.lineno, "end_line": node.end_lineno, "async": is_async}
            category = "methods" if self.class_depth and self.function_depth == 0 else "functions"
            result[category].append(item)
            self.function_depth += 1
            self.generic_visit(node)
            self.function_depth -= 1

        def visit_Import(self, node):
            result["imports"].extend({"name": alias.name, "line": node.lineno, "kind": "import"} for alias in node.names)

        def visit_ImportFrom(self, node):
            module = "." * node.level + (node.module or "")
            result["imports"].append({"name": module, "module": node.module or "", "level": node.level, "members": [alias.name for alias in node.names], "line": node.lineno, "kind": "from"})

        def visit_Assign(self, node):
            self._variables(node, node.targets)
            if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets) and isinstance(node.value, (ast.List, ast.Tuple)):
                result["exports"].extend({"name": item.value, "line": node.lineno} for item in node.value.elts if isinstance(item, ast.Constant) and isinstance(item.value, str))
            self.generic_visit(node)

        def visit_AnnAssign(self, node):
            self._variables(node, [node.target])
            self.generic_visit(node)

        @staticmethod
        def _variables(node, targets):
            if isinstance(getattr(node, "value", None), (ast.Constant, ast.List, ast.Dict, ast.Set, ast.Tuple, ast.Call)):
                for target in targets:
                    if isinstance(target, ast.Name):
                        result["variables"].append({"name": target.id, "line": node.lineno})

    Extractor().visit(root)
    return result


@lru_cache(maxsize=3)
def _tree_sitter_language_for_suffix(suffix: str):
    from tree_sitter import Language
    if suffix in {".ts", ".mts", ".cts"}:
        import tree_sitter_typescript as grammar
        return Language(grammar.language_typescript())
    if suffix == ".tsx":
        import tree_sitter_typescript as grammar
        return Language(grammar.language_tsx())
    import tree_sitter_javascript as grammar
    return Language(grammar.language())


def _tree_sitter_language(path: str):
    return _tree_sitter_language_for_suffix(PurePosixPath(path).suffix.lower())


def _parse_tree_sitter(path: str, source: str) -> dict[str, Any]:
    from tree_sitter import Parser
    parser = Parser(_tree_sitter_language(path))
    tree = parser.parse(source.encode("utf-8"))
    result: dict[str, Any] = {"classes": [], "types": [], "functions": [], "methods": [], "imports": [], "exports": [], "variables": []}
    def line_at(offset: int) -> int:
        return source.count("\n", 0, offset) + 1

    # Tree-sitter is used for full-file parsing and syntax recovery. Symbol
    # extraction below uses bounded token patterns instead of retaining native
    # Node objects, which can access-violate on Windows for some valid JS trees.
    for pattern in (r"\b(?:abstract\s+)?class\s+([\w$]+)",):
        result["classes"].extend({"name": match.group(1), "line": line_at(match.start()), "end_line": line_at(match.end())} for match in re.finditer(pattern, source))
    for match in re.finditer(r"\b(?:interface|type|enum)\s+([\w$]+)", source):
        result["types"].append({"name": match.group(1), "line": line_at(match.start()), "end_line": line_at(match.end())})

    function_pattern = r"\b(?:async\s+)?function\s*\*?\s*([\w$]+)\s*\(|\b(?:const|let|var)\s+([\w$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[\w$]+)\s*=>"
    seen_functions = set()
    for match in re.finditer(function_pattern, source):
        name = match.group(1) or match.group(2)
        line = line_at(match.start())
        if (name, line) not in seen_functions:
            result["functions"].append({"name": name, "line": line, "end_line": line, "async": bool(re.match(r"\s*async\b", source[match.start():match.end()]))})
            seen_functions.add((name, line))
    for match in re.finditer(r"\b(?:const|let|var)\s+([\w$]+)", source):
        result["variables"].append({"name": match.group(1), "line": line_at(match.start())})

    import_patterns = (
        (r"\bimport\s+(?:type\s+)?(?:[^;\n]*?\s+from\s*)?['\"]([^'\"]+)['\"]", "import"),
        (r"\bexport\s+(?:\*|\{[^}]*\})\s+from\s*['\"]([^'\"]+)['\"]", "re-export"),
    )
    for pattern, kind in import_patterns:
        for match in re.finditer(pattern, source):
            result["imports"].append({"name": match.group(1), "line": line_at(match.start()), "kind": kind})
            if kind == "re-export":
                result["exports"].append({"name": "*", "line": line_at(match.start()), "source": match.group(1)})
    for match in re.finditer(r"\bexport\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var|interface|type|enum)\s+([\w$]+)", source):
        result["exports"].append({"name": match.group(1), "line": line_at(match.start()), "source": None})
    for match in re.finditer(r"\bexport\s*\{([^}]+)\}", source):
        result["exports"].extend({"name": item.strip().split(" as ")[-1].strip(), "line": line_at(match.start()), "source": None} for item in match.group(1).split(",") if item.strip())
    if re.search(r"\bexport\s+default\b", source) and not any(item["name"] == "default" for item in result["exports"]):
        result["exports"].append({"name": "default", "line": line_at(re.search(r"\bexport\s+default\b", source).start()), "source": None})

    # Capture CommonJS static requires and literal dynamic imports.
    for match in re.finditer(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)|\bimport\(\s*['\"]([^'\"]+)['\"]\s*\)", source):
        result["imports"].append({"name": match.group(1) or match.group(2), "line": source.count("\n", 0, match.start()) + 1, "kind": "require" if match.group(1) else "dynamic-import"})
    if tree.root_node.has_error:
        result["parse_warning"] = "Tree-sitter recovered from syntax errors; results may be partial."
    return result


def parse_source(path: str, source: str) -> dict[str, Any]:
    source = source[:1_000_000]
    if PurePosixPath(path).suffix.lower() == ".py":
        try:
            return _parse_python(source)
        except (SyntaxError, ValueError, UnicodeError, RecursionError) as exc:
            return {"classes": [], "types": [], "functions": [], "methods": [], "imports": [], "exports": [], "variables": [], "error": f"Python parsing failed safely: {exc}"}
    try:
        return _parse_tree_sitter(path, source)
    except Exception as exc:
        return {"classes": [], "types": [], "functions": [], "methods": [], "imports": [], "exports": [], "variables": [], "error": f"Parser failed safely: {type(exc).__name__}: {exc}"}
