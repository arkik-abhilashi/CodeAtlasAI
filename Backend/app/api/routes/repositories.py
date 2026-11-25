import logging
from datetime import datetime, timezone
import json
import sys
from collections import Counter
from pathlib import PurePosixPath

import networkx as nx
from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile
from sqlalchemy import delete, select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.db.models import AnalysisJob, AnalysisResult, Dependency, Repository, RepositoryFile, RepositoryImportPayload, SavedGraph
from app.schemas.repositories import GitHubImportRequest, GraphResponse, ImportAccepted, JobResponse, RepositoryDetailResponse, RepositorySummary, SaveGraphRequest
from app.services.dependency_analysis import graph_payload
from app.services.repository_ingestion import github_repository_details
from app.services.repository_explainer import build_repository_explanation
from app.services.repository_service import create_import_job, owned_repository, public_repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["repositories"])


def accepted(repository: Repository, job: AnalysisJob) -> ImportAccepted:
    message = job.error_message or "Repository saved. Import and analysis are running in the background."
    return ImportAccepted(repository_id=repository.id, job_id=job.id, status=job.status, message=message)


@router.post("/repositories/upload", response_model=ImportAccepted, status_code=202)
async def upload_repository(user: CurrentUser, db: DbSession, file: UploadFile = File(...), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Upload a repository as a .zip archive")
    payload = await file.read(settings.max_archive_bytes + 1)
    if len(payload) > settings.max_archive_bytes:
        raise HTTPException(413, f"ZIP files are limited to {settings.max_archive_bytes // (1024 * 1024)} MB")
    name = PurePosixPath(file.filename).stem[:255]
    repository, job = create_import_job(db, user.id, name, "upload", metadata={"archive_name": file.filename}, archive=payload, idempotency_key=idempotency_key)
    logger.info("Accepted ZIP import repository=%s job=%s user=%s archive_bytes=%s", repository.id, job.id, user.id, len(payload))
    return accepted(repository, job)


@router.post("/repositories/github", response_model=ImportAccepted, status_code=202)
def import_github(body: GitHubImportRequest, user: CurrentUser, db: DbSession, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    owner, name, branch, _archive_url = github_repository_details(str(body.url))
    metadata = {"owner": owner, "repository": name, "branch": branch, "full_name": f"{owner}/{name}"}
    repository, job = create_import_job(db, user.id, name, "github", str(body.url), metadata, idempotency_key=idempotency_key)
    logger.info("Accepted GitHub import repository=%s job=%s user=%s full_name=%s", repository.id, job.id, user.id, metadata["full_name"])
    return accepted(repository, job)


@router.get("/repositories", response_model=list[RepositorySummary])
def list_repositories(user: CurrentUser, db: DbSession):
    repositories = db.scalars(select(Repository).where(Repository.owner_id == user.id).order_by(Repository.updated_at.desc())).all()
    return [public_repository(repository) for repository in repositories]


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(user: CurrentUser, db: DbSession, limit: int = Query(default=50, ge=1, le=200)):
    return db.scalars(select(AnalysisJob).join(Repository).where(Repository.owner_id == user.id).order_by(AnalysisJob.created_at.desc()).limit(limit)).all()


@router.get("/repositories/{repository_id}", response_model=RepositoryDetailResponse)
def get_repository(repository_id: str, user: CurrentUser, db: DbSession):
    repository = owned_repository(db, user.id, repository_id)
    files = db.scalars(select(RepositoryFile).where(RepositoryFile.repository_id == repository.id).order_by(RepositoryFile.path)).all()
    parsed = {file.path: file.analysis_data for file in files if file.analysis_data}
    dependencies = db.scalars(select(Dependency).where(Dependency.repository_id == repository.id, Dependency.resolved.is_(True))).all()
    graph = nx.DiGraph()
    id_to_path = {file.id: file.path for file in files}
    for dependency in dependencies:
        source, target = id_to_path.get(dependency.source_file_id), id_to_path.get(dependency.target_file_id)
        if source and target:
            graph.add_edge(source, target, import_name=dependency.import_name, line=dependency.line, verified=True)
    latest = db.scalar(select(AnalysisResult).where(AnalysisResult.repository_id == repository.id).order_by(AnalysisResult.created_at.desc()).limit(1))
    return {
        **public_repository(repository),
        "files": [{"id": file.id, "path": file.path, "size": file.size_bytes, "language": file.language, "analysis": file.analysis_data or None, "is_entry_point": file.is_entry_point} for file in files],
        "analysis": parsed,
        "graph": graph_payload(graph),
        "report": {"summary": latest.summary, "metrics": latest.metrics, "findings": latest.findings} if latest else None,
    }


@router.get("/repositories/{repository_id}/files/content")
def get_file_content(repository_id: str, user: CurrentUser, db: DbSession, path: str = Query(min_length=1, max_length=1024)):
    repository = owned_repository(db, user.id, repository_id)
    file = db.scalar(select(RepositoryFile).where(RepositoryFile.repository_id == repository.id, RepositoryFile.path == path))
    if file is None:
        raise HTTPException(404, "File not found in this repository")
    return {"path": file.path, "language": file.language, "content": file.source_content or ""}


@router.get("/repositories/{repository_id}/graph", response_model=GraphResponse)
def get_graph(repository_id: str, user: CurrentUser, db: DbSession, q: str = Query(default="", max_length=200), directory: str = Query(default="", max_length=512)):
    repository = owned_repository(db, user.id, repository_id)
    files = db.scalars(select(RepositoryFile).where(RepositoryFile.repository_id == repository.id)).all()
    dependencies = db.scalars(select(Dependency).where(Dependency.repository_id == repository.id, Dependency.resolved.is_(True))).all()
    id_to_path = {file.id: file.path for file in files}
    graph = nx.DiGraph()
    for dependency in dependencies:
        source, target = id_to_path.get(dependency.source_file_id), id_to_path.get(dependency.target_file_id)
        if source and target:
            graph.add_edge(source, target, import_name=dependency.import_name, line=dependency.line, verified=True)
    return graph_payload(graph, q, directory)


@router.get("/repositories/{repository_id}/reports")
def get_report(repository_id: str, user: CurrentUser, db: DbSession):
    repository = owned_repository(db, user.id, repository_id)
    report = db.scalar(select(AnalysisResult).where(AnalysisResult.repository_id == repository.id).order_by(AnalysisResult.created_at.desc()).limit(1))
    if report is None:
        if repository.status == "failed":
            raise HTTPException(409, "Analysis failed. Re-import the repository to retry.")
        raise HTTPException(409, "Analysis is not complete yet")
    unresolved = db.execute(select(Dependency, RepositoryFile.path, RepositoryFile.source_content).join(RepositoryFile, Dependency.source_file_id == RepositoryFile.id).where(Dependency.repository_id == repository.id, Dependency.resolved.is_(False))).all()
    package_file = db.scalar(select(RepositoryFile).where(RepositoryFile.repository_id == repository.id, RepositoryFile.path == "package.json"))
    try:
        package = json.loads(package_file.source_content or "{}") if package_file else {}
    except (json.JSONDecodeError, TypeError):
        package = {}
    declared = set().union(*(set(package.get(section, {}) or {}) for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")))
    node_builtins = {"assert", "buffer", "child_process", "cluster", "crypto", "dgram", "diagnostics_channel", "dns", "events", "fs", "http", "https", "module", "net", "os", "path", "process", "querystring", "readline", "stream", "string_decoder", "timers", "tls", "tty", "url", "util", "v8", "vm", "worker_threads", "zlib", "test", "assert/strict", "fs/promises", "path/posix", "path/win32"}
    classified = []
    for row, path, source_content in unresolved:
        name = row.import_name.strip()
        top_level = name.removeprefix("node:").split(".")[0].split("/")[0]
        source_lines = (source_content or "").splitlines()
        source_line = source_lines[row.line - 1] if 0 < row.line <= len(source_lines) else ""
        if "import(" in source_line.replace(" ", "") or "require(" in source_line.replace(" ", ""):
            kind = "dynamic"
        elif name.startswith(("./", "../", ".", "/")):
            kind = "unresolved_local"
        elif name.startswith("node:") or top_level in node_builtins or top_level in sys.stdlib_module_names:
            kind = "built_in"
        else:
            package_name = "/".join(name.split("/")[:2]) if name.startswith("@") else name.split("/")[0]
            kind = "declared_external" if package_name in declared else "unresolved_external"
        classified.append({"path": path, "import_name": row.import_name, "line": row.line, "verified": False, "classification": kind, "confidence": "heuristic" if kind in {"unresolved_external", "dynamic"} else "verified"})
    import_counts = Counter(item["classification"] for item in classified)
    group_details = {
        "built_in": ("Node.js built-ins", "Standard runtime modules used by this repository."),
        "declared_external": ("Declared packages", "Packages listed in package.json and available outside this repository."),
        "dynamic": ("Dynamic imports", "Imports resolved at runtime and not safely traceable as local file links."),
        "unresolved_external": ("External packages to review", "Packages not found in package.json; they may be runtime-provided or need dependency review."),
        "unresolved_local": ("Local paths to review", "Relative imports that could not be matched to an indexed repository file."),
    }
    import_groups = [
        {"classification": key, "label": label, "description": description,
         "items": [item for item in classified if item["classification"] == key]}
        for key, (label, description) in group_details.items() if import_counts.get(key)
    ]
    findings = [finding for finding in report.findings if finding.get("type") != "unresolved_import"]
    files = db.scalars(select(RepositoryFile).where(RepositoryFile.repository_id == repository.id)).all()
    return {
        "summary": report.summary,
        "metrics": report.metrics,
        "findings": findings,
        "unresolved_imports": classified,
        "import_resolution": {"counts": dict(import_counts), "groups": import_groups},
        "explanation": build_repository_explanation(files, report.metrics, dict(import_counts)),
    }


@router.get("/repositories/{repository_id}/impact")
def dependency_impact(repository_id: str, user: CurrentUser, db: DbSession, path: str = Query(min_length=1, max_length=1024)):
    repository = owned_repository(db, user.id, repository_id)
    files = db.scalars(select(RepositoryFile).where(RepositoryFile.repository_id == repository.id)).all()
    file_by_path = {file.path: file for file in files}
    target = file_by_path.get(path)
    if target is None:
        raise HTTPException(404, "File not found in this repository")
    rows = db.scalars(select(Dependency).where(Dependency.repository_id == repository.id, Dependency.resolved.is_(True))).all()
    graph = nx.DiGraph()
    path_by_id = {file.id: file.path for file in files}
    graph.add_nodes_from(path_by_id.values())
    for edge in rows:
        source, destination = path_by_id.get(edge.source_file_id), path_by_id.get(edge.target_file_id)
        if source and destination:
            graph.add_edge(source, destination)
    dependents = sorted(nx.ancestors(graph, path))
    imports = sorted(nx.descendants(graph, path))
    return {"path": path, "verified": True, "direct_dependents": sorted(graph.predecessors(path)), "transitive_dependents": dependents, "direct_imports": sorted(graph.successors(path)), "transitive_imports": imports, "potentially_affected_count": len(dependents)}


@router.get("/repositories/{repository_id}/jobs/latest", response_model=JobResponse)
def latest_job(repository_id: str, user: CurrentUser, db: DbSession):
    owned_repository(db, user.id, repository_id)
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.repository_id == repository_id).order_by(AnalysisJob.created_at.desc()).limit(1))
    if job is None:
        raise HTTPException(404, "Analysis job not found")
    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, user: CurrentUser, db: DbSession):
    job = db.scalar(select(AnalysisJob).join(Repository).where(AnalysisJob.id == job_id, Repository.owner_id == user.id))
    if job is None:
        raise HTTPException(404, "Analysis job not found")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str, user: CurrentUser, db: DbSession):
    job = db.scalar(select(AnalysisJob).join(Repository).where(AnalysisJob.id == job_id, Repository.owner_id == user.id))
    if job is None:
        raise HTTPException(404, "Analysis job not found")
    if job.status in {"queued", "running"}:
        job.status = "cancelled"
        job.stage = "Analysis cancelled by user"
        job.finished_at = datetime.now(timezone.utc)
        repository = db.get(Repository, job.repository_id)
        if repository:
            repository.status = "cancelled"
        db.execute(delete(RepositoryImportPayload).where(RepositoryImportPayload.repository_id == job.repository_id))
        db.commit()
        db.refresh(job)
    return job


@router.delete("/repositories/{repository_id}", status_code=204)
def delete_repository(repository_id: str, user: CurrentUser, db: DbSession):
    repository = owned_repository(db, user.id, repository_id)
    db.delete(repository)
    db.commit()


@router.get("/repositories/{repository_id}/graphs")
def list_saved_graphs(repository_id: str, user: CurrentUser, db: DbSession):
    owned_repository(db, user.id, repository_id)
    graphs = db.scalars(select(SavedGraph).where(SavedGraph.repository_id == repository_id).order_by(SavedGraph.created_at.desc())).all()
    return [{"id": graph.id, "name": graph.name, "graph_data": graph.graph_data, "created_at": graph.created_at.isoformat()} for graph in graphs]


@router.post("/repositories/{repository_id}/graphs", status_code=201)
def save_graph(repository_id: str, body: SaveGraphRequest, user: CurrentUser, db: DbSession):
    owned_repository(db, user.id, repository_id)
    graph = SavedGraph(repository_id=repository_id, name=body.name.strip(), graph_data=body.graph_data)
    db.add(graph)
    db.commit()
    db.refresh(graph)
    return {"id": graph.id, "name": graph.name, "graph_data": graph.graph_data, "created_at": graph.created_at.isoformat()}


@router.delete("/repositories/{repository_id}/graphs/{graph_id}", status_code=204)
def delete_saved_graph(repository_id: str, graph_id: str, user: CurrentUser, db: DbSession):
    owned_repository(db, user.id, repository_id)
    graph = db.scalar(select(SavedGraph).where(SavedGraph.id == graph_id, SavedGraph.repository_id == repository_id))
    if graph is None:
        raise HTTPException(404, "Saved graph not found")
    db.delete(graph)
    db.commit()
