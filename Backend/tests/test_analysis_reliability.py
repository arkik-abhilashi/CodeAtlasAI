from datetime import datetime, timedelta, timezone

from app.jobs.recovery import should_recover
from app.jobs.queue import heartbeat_is_live
from app.services.architecture_analysis import architecture_report
from app.services.dependency_analysis import analyze_dependencies
from app.services.language_parsers import parse_source


def test_python_javascript_and_typescript_symbols_and_imports():
    python = parse_source("pkg/api.py", "from .models import User\nclass API:\n    def get_user(self):\n        return User()\n")
    assert python["classes"][0]["name"] == "API"
    assert python["methods"][0]["name"] == "get_user"
    assert python["imports"][0]["level"] == 1

    javascript = parse_source("src/main.mjs", "const load = async () => require('./worker.cjs');\nexport { load };")
    assert javascript["functions"][0]["name"] == "load"
    assert any(item["name"] == "./worker.cjs" for item in javascript["imports"])

    typescript = parse_source("src/types.cts", "export interface Account { id: string }\nexport type AccountId = string;")
    assert {item["name"] for item in typescript["types"]} == {"Account", "AccountId"}


def test_malformed_unicode_and_empty_sources_do_not_abort_analysis():
    malformed = parse_source("bad.py", "def unfinished(:\n    return '\udcff'")
    assert malformed.get("error")
    recovered = parse_source("bad.js", "export const value = ;\n")
    assert recovered.get("parse_warning") or recovered.get("error")
    empty = analyze_dependencies({})
    report = architecture_report(empty)
    assert report["metrics"]["source_files"] == 0
    assert report["metrics"]["verified_dependencies"] == 0
    assert report["metrics"]["module_relationships"] == []


def test_progress_callbacks_cover_parse_and_dependency_resolution_for_large_inputs():
    files = {f"src/module_{index}.js": "export const value = 1;" for index in range(120)}
    files["src/main.js"] = "import { value } from './module_0.js'; export { value };"
    progress = []
    result = analyze_dependencies(files, on_progress=lambda phase, current, total: progress.append((phase, current, total)))
    assert result["graph"].has_edge("src/main.js", "src/module_0.js")
    parse_updates = [entry for entry in progress if entry[0] == "parse"]
    resolve_updates = [entry for entry in progress if entry[0] == "resolve"]
    assert parse_updates[-1] == ("parse", len(files), len(files))
    assert resolve_updates[-1] == ("resolve", len(resolve_updates), len(resolve_updates))


def test_change_impact_ranking_uses_verified_direct_and_transitive_dependents():
    analysis = analyze_dependencies({
        "app.js": "import { service } from './service.js'; service();",
        "service.js": "import { store } from './store.js'; export const service = () => store();",
        "store.js": "export const store = () => 1;",
    })
    ranking = {item["path"]: item for item in architecture_report(analysis)["metrics"]["impact_ranking"]}
    assert ranking["store.js"]["direct_dependents"] == 1
    assert ranking["store.js"]["transitive_dependents"] == 2
    assert ranking["store.js"]["impact_score"] > ranking["service.js"]["impact_score"]


def test_recovery_only_requeues_old_jobs_without_a_live_worker():
    now = datetime.now(timezone.utc)
    old = now - timedelta(minutes=20)
    assert should_recover("job-1", "running", old, set(), now, 300)
    assert not should_recover("job-1", "running", old, {"job-1"}, now, 300)
    assert not should_recover("job-1", "running", now, set(), now, 300)
    assert not should_recover("job-1", "completed", old, set(), now, 300)


def test_worker_liveness_uses_recent_heartbeat_not_a_stale_redis_record():
    now = datetime.now(timezone.utc)
    assert heartbeat_is_live(now - timedelta(seconds=30), 420, now)
    assert not heartbeat_is_live(now - timedelta(hours=1), 420, now)
    assert not heartbeat_is_live(None, 420, now)
