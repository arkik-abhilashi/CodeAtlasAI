import io
import json
import re
import stat
import tomllib
import zipfile
from pathlib import PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app.core.config import settings

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".venv", "venv", "__pycache__", ".next", "coverage"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
ALWAYS_TEXT = {".json", ".md", ".yml", ".yaml", ".toml", ".txt", ".css", ".html", ".env.example", ".gitignore"}


def normalize_archive_path(raw_path: str) -> str | None:
    name = raw_path.replace("\\", "/")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    if any(part.lower() in SKIP_DIRS for part in path.parts):
        return None
    if path.name in {".DS_Store", "Thumbs.db"}:
        return None
    return str(path)


def is_text_candidate(path: str) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    return suffix in SOURCE_SUFFIXES | ALWAYS_TEXT or PurePosixPath(path).name in {"Dockerfile", "Makefile", ".gitignore"}


def extract_repository_metadata(files: dict[str, str]) -> dict:
    metadata: dict = {"text_file_count": len(files), "languages": sorted({PurePosixPath(path).suffix.lower().lstrip(".") for path in files if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES})}
    package_json = files.get("package.json")
    if package_json:
        try:
            package = json.loads(package_json)
            metadata["package"] = {key: package[key] for key in ("name", "version", "description", "license", "scripts") if key in package}
            metadata["package"]["dependency_count"] = len(package.get("dependencies", {})) + len(package.get("devDependencies", {}))
        except (json.JSONDecodeError, TypeError):
            metadata["package"] = {"parse_warning": "Invalid package.json"}
    pyproject = files.get("pyproject.toml")
    if pyproject:
        try:
            project = tomllib.loads(pyproject).get("project", {})
            metadata["python_project"] = {key: project[key] for key in ("name", "version", "description", "requires-python") if key in project}
            metadata["python_project"]["dependency_count"] = len(project.get("dependencies", []))
        except (tomllib.TOMLDecodeError, TypeError):
            metadata["python_project"] = {"parse_warning": "Invalid pyproject.toml"}
    readme = next((content for path, content in files.items() if PurePosixPath(path).name.lower().startswith("readme")), None)
    if readme:
        metadata["readme_excerpt"] = readme[:500]
    return metadata


def extract_zip_report(payload: bytes) -> tuple[dict[str, str], dict]:
    if len(payload) > settings.max_archive_bytes:
        raise HTTPException(413, f"ZIP files are limited to {settings.max_archive_bytes // (1024 * 1024)} MB")
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except (zipfile.BadZipFile, OSError):
        raise HTTPException(400, "Please upload a valid ZIP archive")
    result: dict[str, str] = {}
    count = 0
    expanded_bytes = 0
    discovered = 0
    skipped: dict[str, int] = {}

    def skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    for entry in archive.infolist():
        if entry.is_dir():
            continue
        discovered += 1
        path = normalize_archive_path(entry.filename)
        if path is None:
            skip("excluded or unsafe path")
            continue
        if stat.S_ISLNK(entry.external_attr >> 16):
            skip("symbolic link")
            continue
        if not is_text_candidate(path):
            skip("unsupported file type")
            continue
        count += 1
        if count > settings.max_repository_files:
            raise HTTPException(413, f"Found more than the configured limit of {settings.max_repository_files} supported text files")
        if entry.file_size > settings.max_source_file_bytes:
            skip("file exceeds per-file size limit")
            continue
        expanded_bytes += entry.file_size
        if expanded_bytes > settings.max_repository_bytes:
            raise HTTPException(413, f"Expanded repository text is limited to {settings.max_repository_bytes // (1024 * 1024)} MB")
        if entry.file_size and not entry.compress_size or entry.compress_size and entry.file_size / entry.compress_size > 250:
            skip("suspicious compression ratio")
            continue
        try:
            result[path] = archive.read(entry).decode("utf-8-sig")
        except (UnicodeDecodeError, RuntimeError, OSError):
            skip("binary or unreadable text")
            continue
    if not result:
        raise HTTPException(400, "No supported text files were found in this archive. Skipped files: " + ", ".join(f"{reason}: {total}" for reason, total in sorted(skipped.items())))
    # Strip only one shared top-level directory, as produced by GitHub ZIPs.
    roots = {PurePosixPath(name).parts[0] for name in result}
    if len(roots) == 1 and all(len(PurePosixPath(name).parts) > 1 for name in result):
        prefix = next(iter(roots)) + "/"
        result = {name[len(prefix):]: content for name, content in result.items()}
    return result, {"files_discovered": discovered, "files_processed": len(result), "files_skipped": sum(skipped.values()), "skip_reasons": skipped}


def extract_zip(payload: bytes) -> dict[str, str]:
    return extract_zip_report(payload)[0]


def github_repository_details(url: str) -> tuple[str, str, str, str]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        raise HTTPException(400, "Enter a public https://github.com/owner/repository URL")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2 or parts[0] in {"archive", "login", "features", "settings"}:
        raise HTTPException(400, "Use a URL like https://github.com/owner/repository")
    owner, repository = parts[:2]
    if repository.endswith(".git"):
        repository = repository[:-4]
    branch = parts[3] if len(parts) > 3 and parts[2] == "tree" else "HEAD"
    return owner, repository, branch, f"https://codeload.github.com/{quote(owner)}/{quote(repository)}/zip/{quote(branch, safe='')}"


def fetch_github_repository(url: str, on_download_progress=None) -> tuple[dict[str, str], str, dict, dict]:
    owner, repository, branch, archive_url = github_repository_details(url)
    try:
        request = Request(archive_url, headers={"User-Agent": "CodeAtlas/2.0", "Accept": "application/vnd.github+json"})
        with urlopen(request, timeout=60) as response:
            payload_parts = []
            received = 0
            content_length = int(response.headers.get("Content-Length", "0") or 0)
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                payload_parts.append(block)
                received += len(block)
                if received > settings.max_archive_bytes:
                    raise HTTPException(413, f"GitHub repository ZIP exceeds the {settings.max_archive_bytes // (1024 * 1024)} MB limit")
                if on_download_progress:
                    on_download_progress(received, content_length)
            payload = b"".join(payload_parts)
    except HTTPError as exc:
        raise HTTPException(404 if exc.code == 404 else 502, "Could not fetch that public repository. Check its URL and branch.") from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(502, "GitHub could not be reached. Try again shortly.") from exc
    files, ingestion = extract_zip_report(payload)
    metadata = {"owner": owner, "repository": repository, "branch": branch, "full_name": f"{owner}/{repository}", **extract_repository_metadata(files)}
    return files, repository, metadata, ingestion
