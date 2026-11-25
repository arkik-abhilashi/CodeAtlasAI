# CodeAtlas AI — Project Handoff and Run Guide

## Purpose

CodeAtlas AI is a web platform for importing a source repository, extracting a bounded subset of static source facts, resolving local dependencies, persisting the analysis, and exploring it through an interactive graph and repository browser. The product name includes “AI,” but the current implementation does not use a generative or machine-learning model.

This handoff is for a developer or agent continuing work on another computer. It separates implemented behavior and recorded evidence from limitations and future work.

## Shared project archive

Use the full project archive **`CodeAtlas-Share-20261111T102429Z-1-001.zip`** to run the app. It has a top-level `CodeAtlas-Share` directory and includes the frontend, backend, migrations, tests, Compose file, README, and `.env.example`. After extracting, open PowerShell in the extracted `CodeAtlas-Share` directory (the directory containing `docker-compose.yml`).

The smaller `codeatlas_demo.zip` mentioned in the project report was a temporary local archive used to populate the application for the report screenshots; it was not the full project handoff. The recorded GitHub acceptance run against `trekhleb/javascript-algorithms` was a separate test and is not the screenshot fixture.

## What is implemented

- **Frontend:** React 19 and Vite; authenticated API client; repository workspace, source/file browsing, reports, architecture and dependency visualizations; Cytoscape.js graph interactions.
- **Backend:** FastAPI routes and schemas; SQLAlchemy 2 models; Alembic migrations; PostgreSQL persistence; Redis/RQ asynchronous ingestion and analysis; cancellation and stale-job recovery.
- **Authentication and ownership:** registration/login/profile/logout flows, JWT access tokens, revoked-token tracking, and owner-scoped repository access.
- **Ingestion:** ZIP and public GitHub HTTPS imports; archive/path/type/size safeguards; exclusion of generated directories; per-entry skip accounting. Private GitHub imports and token linking are not implemented.
- **Parsing:** Python is parsed with `ast` and a visitor. JavaScript/TypeScript-family files use Tree-sitter grammars with bounded regular-expression extraction of selected declarations/imports; this is not full semantic TypeScript analysis. Parsing is bounded to one million source characters per file.
- **Dependency analysis:** static import candidates are resolved against indexed repository paths. Only resolved local imports become graph edges; unresolved/external imports remain findings. NetworkX supplies graph analysis; Cytoscape.js renders the client graph.
- **Analysis output:** directory/module summaries, dependency/cycle information, branch-token complexity estimate, and heuristic potentially-unused findings. Complexity and unused-file findings are explicitly approximate.

## Data model and migrations

The migration directory is `Backend/alembic/versions/`. The latest report review covered both migrations, including revision `0002`, which adds job idempotency and archive-import accounting (`discovered_count`, `processed_count`, `skipped_count`, `skip_reasons`) and the temporary `repository_import_payloads` table. That table is keyed by `repository_id` as both primary key and foreign key, so its relationship to a repository is one-to-one. The schema also includes user/revoked-token, repository, repository-file, dependency, analysis-job, analysis-result, and saved-graph records. A dependency may have a nullable target file for an unresolved import.

Before making schema claims or changes, inspect the migrations and models in the extracted archive; treat these as the authority for the current checkout.

## Evidence and verification recorded for the report

- Backend tests: **23 passed**.
- Frontend tests: **22 passed in 8 test files**.
- The README records a separate GitHub ingestion acceptance run against `trekhleb/javascript-algorithms`: 679 archive entries discovered, 624 files indexed, 55 skipped, 361 eligible source files parsed, 341 verified dependency edges, and terminal progress of 100%. These are recorded run counts, not performance measurements.
- The report screenshot import describes a local CodeAtlas source snapshot with 63 indexed files, 59 analyzed source files, 24 verified links, and 3 detected languages. Do not conflate these screenshot snapshot counts with the GitHub acceptance run.
- No formal performance benchmark, ground-truth accuracy evaluation, or user study is claimed.

Re-run tests on the target machine before changing or relying on the counts:

```powershell
# In Backend
pytest -q

# In Frontend
npm test -- --run
npm run lint
npm run build
```

## Windows setup from the shared ZIP

Requirements: Windows 10/11, Docker Desktop with Compose, Python 3.11 or newer, and Node.js 20 or newer. Internet access is needed for first-time dependency installation and Docker image pulls.

1. Extract `CodeAtlas-Share-20261111T102429Z-1-001.zip`. In PowerShell, change directory to the extracted `CodeAtlas-Share` root.
2. Create the local environment file and replace the development JWT secret with a long random value:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

3. Start PostgreSQL and Redis:

   ```powershell
   docker compose up -d postgres redis
   docker compose ps
   ```

4. In PowerShell terminal 1, install backend dependencies, migrate the database, and start the API:

   ```powershell
   cd Backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   alembic upgrade head
   python -m uvicorn main:app --reload
   ```

   If script activation is blocked by local PowerShell policy, run the environment's executables directly, for example `Backend\.venv\Scripts\python.exe -m uvicorn main:app --reload`, or use Command Prompt activation instead.

5. In PowerShell terminal 2, from the project root, start the Windows-compatible RQ worker:

   ```powershell
   cd Backend
   .\.venv\Scripts\Activate.ps1
   rq worker -w rq.worker.SimpleWorker codeatlas-analysis
   ```

6. In PowerShell terminal 3, install frontend packages and start Vite:

   ```powershell
   cd Frontend
   npm ci
   npm run dev
   ```

7. Open the Vite URL (normally `http://localhost:5173`), register an account, then upload a repository ZIP or submit a public GitHub HTTPS URL. API documentation is at `http://localhost:8000/docs`; health endpoint is `http://localhost:8000/api/health`.

Keep the API and worker terminals running while importing/analyzing repositories. If the API URL is different, copy `Frontend/.env.example` to `Frontend/.env`, set `VITE_API_URL`, and restart Vite.

## Stopping and resetting local services

Stop the API, worker, and Vite with Ctrl+C in their terminals. Stop database services from the project root:

```powershell
docker compose down
```

The default Compose setup uses persistent named volumes. To permanently delete local database and Redis contents as well, use `docker compose down -v`; this deletes local data.

## Importing a ZIP into CodeAtlas

The ZIP upload is a repository to analyze, not an installer. After the platform is running, choose the ZIP import in the UI. The archive should contain the project directory and relative source paths. Generated folders such as `.git`, `node_modules`, `dist`, and virtual environments are filtered. Current default limits from `.env.example` are 30 MiB compressed, 100 MiB expanded, 2,500 indexed files, and 1 MB per source file. Unsupported/binary files and unsafe paths are skipped and counted. No uploaded code is executed.

## Known boundaries for future work

- Static analysis cannot reliably model runtime imports, reflection, plugins, computed module names, or every bundler configuration.
- There is no private GitHub integration, team sharing, password reset/email verification, refresh-token flow, or production rate limiting.
- Repository source text is stored in PostgreSQL; retention and automatic expiry are not implemented.
- The graph is based on verified static import resolution, not all runtime interactions.
- UI/e2e browser verification and formal user/performance/accuracy evaluation remain future work.

## Continuation guidance for another agent

1. Read `README.md`, `.env.example`, `docker-compose.yml`, both Alembic revisions, and the relevant service/router/test files before changing behavior.
2. Treat source code and tests in the extracted ZIP as the authority; do not assume report prose or historical acceptance counts prove a feature still works in a changed checkout.
3. Preserve the distinction between parsed files, indexed files, skipped archive entries, and verified graph edges.
4. Do not describe regex-assisted Tree-sitter extraction as complete semantic AST analysis for JavaScript/TypeScript.
5. Do not claim the project implements LLM/generative AI.
6. Keep evaluation results traceable to commands, fixtures, and run logs; do not invent performance or accuracy claims.
