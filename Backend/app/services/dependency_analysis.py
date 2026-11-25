import json
import posixpath
import re
from pathlib import PurePosixPath
from typing import Any, Callable

import networkx as nx

from app.services.language_parsers import parse_source, language_for_path

EXTENSIONS = (".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")
ENTRY_NAMES = {"main.py", "app.py", "__main__.py", "index.js", "index.jsx", "index.ts", "index.tsx", "main.js", "main.ts", "server.js", "server.ts"}


def _alias_targets(files: dict[str, str]) -> list[tuple[str, str]]:
    mappings: list[tuple[str, str]] = []
    try:
        config = json.loads(files.get("tsconfig.json", "{}"))
        options = config.get("compilerOptions", {})
        base = options.get("baseUrl", "")
        for alias, targets in options.get("paths", {}).items():
            for target in targets:
                mappings.append((posixpath.normpath(posixpath.join(base, target)), alias))
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    try:
        package = json.loads(files.get("package.json", "{}"))
        for alias, target in package.get("_moduleAliases", {}).items():
            mappings.append((posixpath.normpath(target), alias))
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    return mappings


def _resolve_import(path: str, item: dict[str, Any], file_paths: set[str], aliases: list[tuple[str, str]]) -> str | None:
    name = item["name"]
    suffix = PurePosixPath(path).suffix.lower()
    relative_base = PurePosixPath(path).parent.as_posix()
    candidates: list[str] = []
    if item.get("level", 0):
        base = relative_base
        for _ in range(max(0, item["level"] - 1)):
            base = posixpath.dirname(base)
        module = item.get("module", "").replace(".", "/")
        root = posixpath.normpath(posixpath.join(base, module))
        candidates.extend([root, *(root + ext for ext in EXTENSIONS), *(root + "/index" + ext for ext in EXTENSIONS), root + "/__init__.py"])
        for member in item.get("members", []):
            member_path = posixpath.join(root, member)
            candidates.extend([member_path, *(member_path + ext for ext in EXTENSIONS), member_path + "/__init__.py"])
    elif name.startswith((".", "/")):
        base = "" if name.startswith("/") else relative_base
        root = posixpath.normpath(posixpath.join(base, name.lstrip("/")))
        candidates.extend([root, *(root + ext for ext in EXTENSIONS), *(root + "/index" + ext for ext in EXTENSIONS), root + "/__init__.py"])
    else:
        alias_resolved = False
        for target, pattern in aliases:
            if "*" in pattern:
                before, after = pattern.split("*", 1)
                if name.startswith(before) and name.endswith(after):
                    capture = name[len(before):len(name) - len(after) if after else None]
                    root = posixpath.normpath(target.replace("*", capture))
                    alias_resolved = True
                    break
            elif name == pattern:
                root = target
                alias_resolved = True
                break
        if not alias_resolved:
            root = name.replace(".", "/") if suffix == ".py" else name
        candidates.extend([root, *(root + ext for ext in EXTENSIONS), *(root + "/index" + ext for ext in EXTENSIONS), root + "/__init__.py"])
        if suffix == ".py":
            for member in item.get("members", []):
                member_path = posixpath.join(root, member)
                candidates.extend([member_path, *(member_path + ext for ext in EXTENSIONS), member_path + "/__init__.py"])
    for candidate in candidates:
        normalized = posixpath.normpath(candidate)
        if normalized == ".." or normalized.startswith("../"):
            continue
        if normalized in file_paths:
            return normalized
    return None


def _entry_points(files: dict[str, str], parsed: dict[str, dict]) -> set[str]:
    entries = {path for path in parsed if PurePosixPath(path).name.lower() in ENTRY_NAMES}
    for path, source in files.items():
        if path.endswith(".py") and re.search(r"if\s+__name__\s*==\s*['\"]__main__['\"]", source):
            entries.add(path)
    try:
        package = json.loads(files.get("package.json", "{}"))
        for script in package.get("scripts", {}).values():
            for candidate in re.findall(r"(?:node|tsx?|vite|webpack)\s+([\w./-]+\.(?:[cm]?[jt]sx?))", script):
                normalized = posixpath.normpath(candidate).lstrip("./")
                if normalized in parsed:
                    entries.add(normalized)
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    return entries


def analyze_dependencies(files: dict[str, str], on_progress: Callable[[str, int, int], None] | None = None) -> dict[str, Any]:
    source_files = {path: content for path, content in files.items() if language_for_path(path)}
    parsed: dict[str, dict] = {}
    for index, (path, content) in enumerate(source_files.items(), 1):
        parsed[path] = parse_source(path, content)
        if on_progress:
            on_progress("parse", index, len(source_files))
    aliases = _alias_targets(files)
    graph = nx.DiGraph()
    graph.add_nodes_from(source_files)
    imports: list[dict[str, Any]] = []
    file_paths = set(source_files)
    work = [(path, item) for path, result in parsed.items() for item in result.get("imports", [])]
    for index, (path, item) in enumerate(work, 1):
        target = _resolve_import(path, item, file_paths, aliases)
        record = {"source": path, "target": target, "import_name": item["name"], "line": item["line"], "resolved": target is not None, "verified": target is not None}
        imports.append(record)
        if target:
            graph.add_edge(path, target, import_name=item["name"], line=item["line"], verified=True)
        if on_progress:
            on_progress("resolve", index, len(work))
    return {"files": source_files, "parsed": parsed, "imports": imports, "graph": graph, "entry_points": _entry_points(files, parsed)}


def graph_payload(graph: nx.DiGraph, query: str = "", directory: str = "") -> dict[str, list[dict[str, Any]]]:
    # Only files participating in a verified edge are dependency graph nodes.
    connected = {node for edge in graph.edges for node in edge}
    if directory:
        connected = {node for node in connected if node.startswith(directory.rstrip("/") + "/") or node == directory.rstrip("/")}
    if query:
        needle = query.lower()
        matched = {node for node in connected if needle in node.lower()}
        neighbors = {neighbor for node in matched for neighbor in graph.predecessors(node)} | {neighbor for node in matched for neighbor in graph.successors(node)}
        connected = matched | neighbors
    subgraph = graph.subgraph(connected)
    return {
        "nodes": [{"id": path, "label": PurePosixPath(path).name, "directory": str(PurePosixPath(path).parent), "language": language_for_path(path), "in_degree": subgraph.in_degree(path), "out_degree": subgraph.out_degree(path)} for path in subgraph.nodes],
        "edges": [{"source": source, "target": target, **data} for source, target, data in subgraph.edges(data=True)],
    }


