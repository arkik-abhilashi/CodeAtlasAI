from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any, Iterable


def _role_for_path(path: str) -> str:
    parts = {part.lower() for part in PurePosixPath(path).parts[:-1]}
    if parts & {"test", "tests", "__tests__", "spec", "specs", "fixtures", "mocks"}:
        return "Test and verification"
    if parts & {"examples", "example", "demo", "demos"}:
        return "Examples and demonstrations"
    if parts & {"config", "configs", ".github", "scripts", "build"}:
        return "Configuration and tooling"
    if parts & {"routes", "route", "controllers", "controller", "api"}:
        return "Interface and request handling"
    if parts & {"services", "service", "middleware", "middlewares"}:
        return "Application services"
    if parts & {"models", "model", "db", "database", "data"}:
        return "Data and domain logic"
    if parts & {"utils", "util", "helpers", "helper", "lib"}:
        return "Shared utilities"
    return "Application code"


def build_repository_explanation(files: Iterable[Any], metrics: dict[str, Any], import_counts: dict[str, int]) -> dict[str, Any]:
    file_list = list(files)
    top_level: dict[str, list[Any]] = defaultdict(list)
    for file in file_list:
        parts = PurePosixPath(file.path).parts
        top_level[parts[0] if len(parts) > 1 else "(root)"].append(file)

    components = []
    for path, members in sorted(top_level.items(), key=lambda item: (-len(item[1]), item[0]))[:6]:
        representative = next((member.path for member in members if member.path != path), members[0].path)
        components.append({"path": path, "role": _role_for_path(representative), "file_count": len(members)})

    cycles = metrics.get("circular_dependencies", 0)
    unresolved_local = import_counts.get("unresolved_local", 0)
    health_notes = [
        "No circular dependencies were detected in the verified local dependency graph." if not cycles else f"{cycles} circular dependency path{'s' if cycles != 1 else ''} need review.",
        "All local imports resolved to indexed repository files." if not unresolved_local else f"{unresolved_local} local import{'s' if unresolved_local != 1 else ''} could not be resolved.",
    ]
    dependency_total = metrics.get("verified_dependencies", 0)
    modules = metrics.get("modules", 0)
    source_files = metrics.get("source_files", 0)
    languages = metrics.get("languages", {})
    dominant_language = max(languages.items(), key=lambda item: item[1])[0] if languages else "supported source"
    overview = f"This repository contains {source_files} analyzed {dominant_language} files organized into {modules} directory modules. CodeAtlas verified {dependency_total} local import relationships to build the architecture map."
    largest_component = components[0] if components else None
    architecture_notes = [
        f"The repository is divided into {len(top_level)} top-level areas, which CodeAtlas groups using the real directory structure.",
        f"The largest visible area is {largest_component['path']} with {largest_component['file_count']} indexed files; its path suggests a {largest_component['role'].lower()} responsibility." if largest_component else "No top-level directory areas were detected.",
        "Only static local imports are used to draw dependency flow. External packages and runtime-resolved imports stay outside the verified architecture graph.",
    ]

    return {
        "overview": overview,
        "components": components,
        "entry_points": metrics.get("entry_points", [])[:8],
        "hotspots": metrics.get("highly_connected_files", [])[:5],
        "impact_ranking": metrics.get("impact_ranking", [])[:8],
        "complexity_hotspots": [item for item in metrics.get("complexity_estimates", []) if item.get("score", 0) > 1][:5],
        "module_flows": metrics.get("module_relationships", [])[:6],
        "architecture_notes": architecture_notes,
        "health_notes": health_notes,
    }
