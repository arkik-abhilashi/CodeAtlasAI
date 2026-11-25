import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import Any

import networkx as nx

from app.services.language_parsers import language_for_path


def architecture_report(analysis: dict[str, Any]) -> dict[str, Any]:
    graph: nx.DiGraph = analysis["graph"]
    parsed = analysis["parsed"]
    files = analysis["files"]
    entry_points = analysis["entry_points"]
    language_counts: dict[str, int] = defaultdict(int)
    module_counts: dict[str, int] = defaultdict(int)
    for path in files:
        language_counts[language_for_path(path) or "Other"] += 1
        module_counts[str(PurePosixPath(path).parent)] += 1
    complexity: list[dict[str, Any]] = []
    for path, source in files.items():
        branches = len(re.findall(r"\b(if|elif|for|while|except|case|catch)\b|&&|\|\|", source))
        complexity.append({"path": path, "score": branches + 1, "basis": "Estimated from branch-like syntax tokens; heuristic, not a compiler metric."})
    # A strongly connected component proves at least one cycle; one witness
    # per component avoids enumerating exponentially many simple cycles.
    cycles = []
    for component in nx.strongly_connected_components(graph):
        if len(component) == 1:
            node = next(iter(component))
            if not graph.has_edge(node, node):
                continue
        try:
            cycles.append(nx.find_cycle(graph.subgraph(component)))
        except nx.NetworkXNoCycle:
            continue
    conventional_runtime_files = {"index.js", "index.jsx", "index.ts", "index.tsx", "main.js", "main.ts", "main.py", "app.py", "server.js", "server.ts", "__main__.py"}
    tooling_markers = ("test", "tests", "__tests__", "fixtures", "mocks", "scripts", "config", "configs", "build", "dist", "public", ".github")
    tooling_names = ("vite.config.", "webpack.config.", "jest.config.", "vitest.config.", "babel.config.", "eslint.config.", "rollup.config.", "postcss.config.", "tailwind.config.")
    unused = []
    for path in files:
        parts = PurePosixPath(path).parts
        name = PurePosixPath(path).name.lower()
        excluded_as_runtime = (
            path in entry_points
            or name in conventional_runtime_files
            or any(part.lower() in tooling_markers for part in parts[:-1])
            or name.startswith(("test_", "test.", "spec_", "spec."))
            or name.endswith((".test.js", ".test.jsx", ".test.ts", ".test.tsx", ".spec.js", ".spec.ts", ".d.ts"))
            or name.startswith(tooling_names)
        )
        if graph.in_degree(path) == 0 and not excluded_as_runtime:
            unused.append({"path": path, "verified": False, "confidence": "low", "reason": "No incoming static local imports were found. This file may still be used by dynamic imports, external scripts, test runners, or runtime conventions."})
    fan = [{"path": path, "in_degree": graph.in_degree(path), "out_degree": graph.out_degree(path), "coupling": graph.in_degree(path) + graph.out_degree(path)} for path in graph.nodes]
    highly_connected = sorted(fan, key=lambda item: item["coupling"], reverse=True)[:10]
    # Edges run from an importing file to the file it imports. Therefore, a
    # node's ancestors are the verified files that can be affected by changing it.
    impact_ranking = sorted(
        (
            {
                "path": path,
                "direct_dependents": graph.in_degree(path),
                "transitive_dependents": len(nx.ancestors(graph, path)),
                "impact_score": graph.in_degree(path) + (len(nx.ancestors(graph, path)) * 2),
            }
            for path in graph.nodes
        ),
        key=lambda item: (item["impact_score"], item["direct_dependents"]),
        reverse=True,
    )[:10]
    module_graph = nx.DiGraph()
    module_relationship_counts: Counter[tuple[str, str]] = Counter()
    for source, target in graph.edges:
        source_module = str(PurePosixPath(source).parent)
        target_module = str(PurePosixPath(target).parent)
        if source_module != target_module:
            module_graph.add_edge(source_module, target_module)
            module_relationship_counts[(source_module, target_module)] += 1
    module_coupling = sorted(({"module": module, "in_degree": module_graph.in_degree(module), "out_degree": module_graph.out_degree(module), "coupling": module_graph.in_degree(module) + module_graph.out_degree(module)} for module in module_graph.nodes), key=lambda item: item["coupling"], reverse=True)
    module_relationships = [{"source": source, "target": target, "imports": count} for (source, target), count in module_relationship_counts.most_common(12)]
    function_count = sum(len(result.get("functions", [])) + len(result.get("methods", [])) for result in parsed.values())
    class_count = sum(len(result.get("classes", [])) for result in parsed.values())
    dominant = sorted(language_counts.items(), key=lambda item: item[1], reverse=True)
    summary = f"{len(files)} source files form {len(module_counts)} directory modules with {graph.number_of_edges()} verified local dependencies. "
    summary += f"The most common language is {dominant[0][0]} ({dominant[0][1]} files). " if dominant else "No supported languages were detected. "
    summary += f"Found {len(entry_points)} likely entry points and {len(cycles)} circular dependency paths."
    return {
        "summary": summary,
        "metrics": {"source_files": len(files), "directories": len(module_counts), "languages": dict(language_counts), "classes": class_count, "functions_and_methods": function_count, "verified_dependencies": graph.number_of_edges(), "modules": len(module_counts), "entry_points": sorted(entry_points), "circular_dependencies": len(cycles), "complexity_estimates": sorted(complexity, key=lambda item: item["score"], reverse=True)[:20], "highly_connected_files": highly_connected, "impact_ranking": impact_ranking, "module_coupling": module_coupling, "module_relationships": module_relationships},
        "findings": [{"type": "circular_dependency", "confidence": "verified", "files": [edge[0] for edge in cycle] + ([cycle[0][0]] if cycle else [])} for cycle in cycles] + [{"type": "potentially_unused_file", "confidence": "heuristic", **item} for item in unused],
        "unresolved_imports": [item for item in analysis["imports"] if not item["resolved"]],
    }
