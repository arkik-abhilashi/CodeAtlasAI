# CodeAtlas

CodeAtlas imports ZIP archives and public GitHub repositories, stores them under a signed-in user's account, and analyzes Python, JavaScript, JSX, TypeScript, and TSX source. The existing React/Vite interface keeps the dark grid and orange accent design.

## Architecture

- `Frontend`: React 19, Vite, Cytoscape.js and authenticated API client.
- `Backend/app/api`: FastAPI routes and request/response schemas.
- `Backend/app/db/models`: SQLAlchemy 2.0 relational models.
- `Backend/app/services`: authentication, safe ingestion, language parsing, dependency resolution, and architecture metrics.
- `Backend/app/jobs`: Redis/RQ queue and analysis worker.
- `Backend/alembic`: versioned PostgreSQL migrations.
- `docs/architecture.md`: baseline inspection and data lifecycle.

## Run on Windows

Requirements: Python 3.11+, Node.js 20+, and Docker Desktop. Docker Compose supplies PostgreSQL and Redis.

1. From the repository root, create your local environment file and change the JWT secret:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Start PostgreSQL and Redis:

   ```powershell
   docker compose up -d postgres redis
   ```

3. In a terminal, install the backend and apply the schema migration:

   ```powershell
   cd Backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   alembic upgrade head
   python -m uvicorn main:app --reload
   ```

4. Open a second terminal for the queue worker. `SimpleWorker` works on Windows where RQ's fork-based worker does not:

   ```powershell
   cd Backend
   .\.venv\Scripts\Activate.ps1
   rq worker -w rq.worker.SimpleWorker codeatlas-analysis
   ```

5. In a third terminal, start the frontend:

   ```powershell
   cd Frontend
   npm ci
   npm run dev
   ```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`), create an account, then import a ZIP archive or public GitHub repository. The backend docs are at `http://localhost:8000/docs`; the health check is `http://localhost:8000/api/health`.

If you need a different API address, copy `Frontend/.env.example` to `Frontend/.env` and set `VITE_API_URL`.

## Upload format

Uploads must be a `.zip` containing the project folder. CodeAtlas keeps the folder paths as the file explorer structure. The service filters generated folders such as `node_modules`, `.git`, `dist`, and virtual environments; skips binary files; and enforces compressed archive, expanded content, file count, and per-file size limits. GitHub import supports public repositories and selected branch URLs.

## Analysis behavior

- Python's AST and Tree-sitter grammars parse supported source. Tree-sitter JavaScript and TypeScript grammars handle `.js`, `.jsx`, `.ts`, and `.tsx` files.
- Import relationships become graph edges only when a static import resolves to an included file. External packages and unresolved local imports are reported separately.
- TypeScript `compilerOptions.paths`, `baseUrl`, and package `_moduleAliases` are used for aliases when present.
- The dependency graph contains only files participating in verified edges. Cytoscape provides force-directed placement, directory grouping, search, directory filters, zoom and pan, and selected-file details.
- Circular dependency paths are based on verified edges. Complexity scores and potential-unused-file findings are heuristics and are labeled as such.
- Analysis runs in an RQ worker. Job stage/progress and repository results are stored in PostgreSQL; Redis queues work between the API and worker.
- The API exposes `POST /api/jobs/{job_id}/cancel` for queued or running analyses. Running workers check for cancellation at progress checkpoints and persist the terminal state.
- Worker progress advances through ingestion, parsing, import resolution, architecture analysis and persistence. It reports batched progress during parsing and dependency resolution instead of remaining at 10% for the full analysis.
- The API runs periodic recovery checks. It uses RQ worker registration expiry, queue assignment, status, and heartbeat age to detect dead workers, requeues recoverable imports/analysis, and persists a useful failure if no worker can process the job. `python -m app.jobs.recovery` can also run a one-time check. Stale job age is configured by `ANALYSIS_STALE_JOB_SECONDS`.
- `GET /api/workers/status` reports authenticated queue availability and the ready workers' state, identity, RQ version, heartbeat and registration TTL. Idle workers count as available; busy workers count as connected and ready to pick up subsequent work.
- Analysis worker timeout is configured by `ANALYSIS_JOB_TIMEOUT_SECONDS` (default 3600 seconds).
- Import jobs report archive entries discovered, indexed files, eligible source files parsed, skipped counts and skip reasons separately. The default limits are 30 MiB compressed, 100 MiB expanded content, 2,500 indexed files and 1 MB per file. Generated folders, unsupported/binary files and unsafe paths are filtered.

## Tests

From `Backend`:

```powershell
pytest -q
```

From `Frontend`:

```powershell
npm test
npm run lint
npm run build
```

Backend endpoint tests use SQLite and an inline test queue so they do not require Docker. Production configuration targets PostgreSQL and Redis. Migrations are checked against generated PostgreSQL SQL and SQLite locally; run `alembic upgrade head` with the Compose PostgreSQL service for a live PostgreSQL migration.

The GitHub ingestion acceptance run was also performed against the Compose PostgreSQL and Redis services with a real FastAPI process and Windows-compatible RQ `SimpleWorker`: `trekhleb/javascript-algorithms` completed at 100%, with 679 archive entries discovered, 624 repository files indexed, 55 unsupported files skipped, 361 eligible source files parsed, 341 verified dependency edges, and a persisted architecture report.

## Current boundaries

- GitHub private repositories and GitHub token linking are not supported.
- Repository source text is retained in PostgreSQL to support persisted analysis and re-analysis. No code is executed.
- Complexity is a branch-token estimate; unused-file detection is heuristic. Static parsing cannot resolve runtime imports, dynamic module names, plugin loading, or every custom bundler configuration.
- Job progress is batched and stage-aware; it does not represent an exact per-file completion estimate.
- There is no team sharing, password reset/email verification, refresh-token flow, or production rate limiting yet.
