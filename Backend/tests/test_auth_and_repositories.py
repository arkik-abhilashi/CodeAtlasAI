from tests.conftest import make_zip
from app.db.models import AnalysisJob
import app.jobs.worker as worker
import app.services.repository_service as repository_service
import app.api.routes.workers as workers_route
from app.services.architecture_analysis import architecture_report
from app.services.dependency_analysis import analyze_dependencies
from app.services.language_parsers import parse_source


def test_typescript_aliases_cycles_and_unresolved_imports():
    files = {
        "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}',
        "src/main.ts": "import { run } from './worker';\nexport const start = () => run();",
        "src/worker.ts": "import { start } from '@/main';\nexport function run() { return start(); }",
        "src/view.tsx": "interface Props { title: string }\nexport const View = () => <main/>;",
        "src/unused.js": "export const unused = 1;",
    }
    parsed = parse_source("src/view.tsx", files["src/view.tsx"])
    assert parsed["types"][0]["name"] == "Props"
    assert parsed["functions"][0]["name"] == "View"
    analysis = analyze_dependencies(files)
    assert analysis["graph"].number_of_edges() == 2
    report = architecture_report(analysis)
    assert report["metrics"]["circular_dependencies"] == 1
    assert any(finding["type"] == "potentially_unused_file" and finding["path"] == "src/unused.js" for finding in report["findings"])
    unused = next(finding for finding in report["findings"] if finding["type"] == "potentially_unused_file")
    assert unused["confidence"] == "low"
    assert "dynamic imports" in unused["reason"]


def test_unused_heuristic_excludes_tests_and_build_configuration():
    result = analyze_dependencies({
        "src/orphan.js": "export const orphan = 1;",
        "src/thing.test.js": "export const testOnly = 1;",
        "vite.config.js": "export default {};",
    })
    findings = architecture_report(result)["findings"]
    unused_paths = {finding["path"] for finding in findings if finding["type"] == "potentially_unused_file"}
    assert unused_paths == {"src/orphan.js"}


def test_python_exports_and_relative_import_resolution():
    files = {"pkg/__init__.py": "from .api import start\n__all__ = ['start']", "pkg/api.py": "def start(): return 1"}
    result = analyze_dependencies(files)
    assert result["graph"].has_edge("pkg/__init__.py", "pkg/api.py")
    assert result["parsed"]["pkg/__init__.py"]["exports"][0]["name"] == "start"


def test_reports_classify_node_builtins_declared_packages_and_local_imports(client, register_user):
    token = register_user()
    response = client.post("/api/repositories/upload", headers={"Authorization": f"Bearer {token}"}, files={"file": ("sample.zip", make_zip({
        "package.json": '{"dependencies":{"lodash":"^4.0.0"}}',
        "src/index.js": "import fs from 'node:fs';\nimport _ from 'lodash';\nimport './missing.js';\nimport('runtime-plugin');",
    }), "application/zip")})
    assert response.status_code == 202, response.text
    report = client.get(f"/api/repositories/{response.json()['repository_id']}/reports", headers={"Authorization": f"Bearer {token}"})
    assert report.status_code == 200, report.text
    classifications = {item["import_name"]: item["classification"] for item in report.json()["unresolved_imports"]}
    assert classifications["node:fs"] == "built_in"
    assert classifications["lodash"] == "declared_external"
    assert classifications["./missing.js"] == "unresolved_local"
    assert classifications["runtime-plugin"] == "dynamic"
    payload = report.json()
    assert not any(item["type"] == "unresolved_import" for item in payload["findings"])
    assert payload["import_resolution"]["counts"]["built_in"] == 1
    assert "overview" in payload["explanation"]


def test_upload_persists_analysis_and_only_verified_edges(client, register_user):
    token = register_user()
    response = client.post("/api/repositories/upload", headers={"Authorization": f"Bearer {token}"}, files={"file": ("sample.zip", make_zip({"app.py": "from .utils import value\nclass App: pass\ndef run(): return value()\n", "utils.py": "def value(): return 1\n", "unrelated.ts": "export const spare = 1"}), "application/zip")})
    assert response.status_code == 202, response.text
    accepted = response.json()
    detail = client.get(f"/api/repositories/{accepted['repository_id']}", headers={"Authorization": f"Bearer {token}"})
    assert detail.status_code == 200
    repository = detail.json()
    assert repository["status"] == "completed"
    assert repository["stats"]["classes"] == 1
    assert repository["stats"]["functions"] == 2
    assert repository["graph"]["nodes"] == [
        {"id": "app.py", "label": "app.py", "directory": ".", "language": "Python", "in_degree": 0, "out_degree": 1},
        {"id": "utils.py", "label": "utils.py", "directory": ".", "language": "Python", "in_degree": 1, "out_degree": 0},
    ]
    assert len(repository["graph"]["edges"]) == 1
    assert repository["graph"]["edges"][0]["verified"] is True
    assert any(file["path"] == "unrelated.ts" for file in repository["files"])
    assert client.get(f"/api/jobs/{accepted['job_id']}", headers={"Authorization": f"Bearer {token}"}).json()["status"] == "completed"
    impact = client.get(f"/api/repositories/{accepted['repository_id']}/impact", params={"path": "utils.py"}, headers={"Authorization": f"Bearer {token}"})
    assert impact.json()["transitive_dependents"] == ["app.py"]
    saved = client.post(f"/api/repositories/{accepted['repository_id']}/graphs", headers={"Authorization": f"Bearer {token}"}, json={"name": "Review view", "graph_data": repository["graph"]})
    assert saved.status_code == 201
    assert client.get(f"/api/repositories/{accepted['repository_id']}/graphs", headers={"Authorization": f"Bearer {token}"}).json()[0]["name"] == "Review view"


def test_repository_ownership_and_auth_logout(client, register_user):
    owner = register_user("owner@example.com")
    other = register_user("other@example.com")
    created = client.post("/api/repositories/upload", headers={"Authorization": f"Bearer {owner}"}, files={"file": ("repo.zip", make_zip({"main.js": "import { util } from './util.js';\n", "util.js": "export const util = 1;"}), "application/zip")}).json()
    repository_id = created["repository_id"]
    assert client.get(f"/api/repositories/{repository_id}", headers={"Authorization": f"Bearer {other}"}).status_code == 404
    assert client.post("/api/auth/logout", headers={"Authorization": f"Bearer {owner}"}).status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {owner}"}).status_code == 401


def test_auth_is_required(client):
    assert client.get("/api/repositories").status_code == 401
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/workers/status").status_code == 401


def test_authenticated_worker_status_endpoint_reports_idle_workers(client, register_user, monkeypatch):
    token = register_user("worker-status@example.com")
    monkeypatch.setattr(workers_route, "worker_status", lambda: {
        "queue": "codeatlas-analysis", "available": True, "worker_count": 1,
        "workers": [{"name": "worker-1", "hostname": "test-host", "pid": 1234,
                     "state": "idle", "queues": ["codeatlas-analysis"], "version": "2.12.0",
                     "last_heartbeat": "2026-11-04T10:00:00+00:00", "registration_ttl_seconds": 300}],
        "reason": None,
    })
    response = client.get("/api/workers/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    assert response.json()["available"] is True
    assert response.json()["workers"][0]["state"] == "idle"


def test_cancel_queued_job_and_duplicate_completed_execution_is_ignored(client, register_user, monkeypatch):
    token = register_user()
    monkeypatch.setattr(repository_service, "enqueue_import", lambda _job_id: None)
    accepted = client.post("/api/repositories/upload", headers={"Authorization": f"Bearer {token}"}, files={"file": ("sample.zip", make_zip({"main.py": "print('ready')"}), "application/zip")}).json()
    cancelled = client.post(f"/api/jobs/{accepted['job_id']}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    repository = client.get(f"/api/repositories/{accepted['repository_id']}", headers={"Authorization": f"Bearer {token}"}).json()
    assert repository["status"] == "cancelled"
    worker.process_analysis(accepted["job_id"])
    assert client.get(f"/api/jobs/{accepted['job_id']}", headers={"Authorization": f"Bearer {token}"}).json()["status"] == "cancelled"


def test_worker_exception_persists_failure_state(client, register_user, monkeypatch):
    token = register_user()
    def fail_analysis(*_args, **_kwargs):
        raise RuntimeError("simulated parser worker failure")
    monkeypatch.setattr(worker, "analyze_dependencies", fail_analysis)
    response = client.post("/api/repositories/upload", headers={"Authorization": f"Bearer {token}"}, files={"file": ("sample.zip", make_zip({"main.py": "print('ready')"}), "application/zip")})
    assert response.status_code == 202
    assert response.json()["status"] == "failed"
    repositories = client.get("/api/repositories", headers={"Authorization": f"Bearer {token}"}).json()
    assert repositories[0]["status"] == "failed"


def test_owner_can_read_source_but_other_users_cannot(client, register_user):
    owner = register_user("source-owner@example.com")
    other = register_user("source-other@example.com")
    accepted = client.post("/api/repositories/upload", headers={"Authorization": f"Bearer {owner}"}, files={"file": ("sample.zip", make_zip({"src/main.py": "def run(): return 1"}), "application/zip")}).json()
    response = client.get(f"/api/repositories/{accepted['repository_id']}/files/content", params={"path": "src/main.py"}, headers={"Authorization": f"Bearer {owner}"})
    assert response.status_code == 200
    assert response.json()["content"] == "def run(): return 1"
    forbidden = client.get(f"/api/repositories/{accepted['repository_id']}/files/content", params={"path": "src/main.py"}, headers={"Authorization": f"Bearer {other}"})
    assert forbidden.status_code == 404


def test_import_persists_job_and_processes_more_than_one_hundred_files(client, register_user):
    token = register_user("many-files@example.com")
    files = {f"src/module_{index}.js": f"export const value{index} = {index};" for index in range(150)}
    response = client.post("/api/repositories/upload", headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "large-archive-1"}, files={"file": ("many-files.zip", make_zip(files), "application/zip")})
    assert response.status_code == 202, response.text
    accepted = response.json()
    jobs = client.get("/api/jobs", headers={"Authorization": f"Bearer {token}"})
    job = next(item for item in jobs.json() if item["id"] == accepted["job_id"])
    assert job["status"] == "completed"
    assert job["files_discovered"] == 150
    assert job["files_processed"] == 150
    assert job["files_skipped"] == 0
    detail = client.get(f"/api/repositories/{accepted['repository_id']}", headers={"Authorization": f"Bearer {token}"}).json()
    assert len(detail["files"]) == 150
    assert detail["progress"] == 100

    duplicate = client.post("/api/repositories/upload", headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "large-archive-1"}, files={"file": ("retry.zip", make_zip({"other.js": "export const other = true;"}), "application/zip")})
    assert duplicate.status_code == 202
    assert duplicate.json()["repository_id"] == accepted["repository_id"]
    assert duplicate.json()["job_id"] == accepted["job_id"]
    assert len(client.get("/api/repositories", headers={"Authorization": f"Bearer {token}"}).json()) == 1
