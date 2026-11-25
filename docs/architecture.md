# CodeAtlas architecture upgrade

## Phase 1: inspected baseline

The repository is one Vite/React application in `Frontend` and a FastAPI app in `Backend/main.py`. The UI already has the dark grid and orange accents, ZIP/GitHub import forms, a file tree, statistics and a Cytoscape view. The API validates and parses imports, but keeps repository records in a module-level dictionary, performs work during the request, and has no authentication or migrations. The frontend calls the import endpoints directly and has no account flow or job polling.

## Target architecture

`Backend/app` separates configuration, database/session setup, relational models, API schemas/routes, authentication, repository ingestion, language parsing, dependency/architecture analysis and queue workers. PostgreSQL owns user and repository data; Redis/RQ executes analysis jobs; Alembic owns schema changes. React remains the existing Vite application and consumes authenticated API resources, polling durable job status. Cytoscape remains the graph renderer and receives only resolved dependency relationships.

## Runtime lifecycle

1. A signed-in user submits a ZIP or public GitHub URL. The API creates and commits the user's repository and queued job before acknowledging acceptance. An idempotency key makes retrying the same request safe.
2. ZIP uploads are validated and stored with the queued import payload in PostgreSQL. The worker reads that payload, extracts eligible files, and saves repository files and analysis results. GitHub archives are downloaded by the worker before extraction.
3. Redis/RQ carries only the job ID. The worker records each stage and discovered/indexed/skipped counts in PostgreSQL, saves file batches, parses supported sources, resolves only imports supported by source and local paths, and persists report/graph data.
4. The authenticated job and repository endpoints are the source of truth. The frontend fetches current repositories and jobs on app load and again when Repositories is activated, then polls nonterminal jobs.
5. The API recovery loop uses worker heartbeats and job age. It recovers stale jobs when a worker is live and marks jobs failed with a reason when the queue has no live worker, avoiding indefinite waiting states.

## Import limits

The default safety limits are 30 MiB compressed, 100 MiB expanded repository content, 2,500 indexed files and 1 MB per source file. These values are configurable through the `MAX_ARCHIVE_BYTES`, `MAX_REPOSITORY_BYTES`, `MAX_REPOSITORY_FILES` and `MAX_SOURCE_FILE_BYTES` environment variables. Generated and binary files are filtered during ingestion.

## Import acceptance run

The public `trekhleb/javascript-algorithms` repository was imported through FastAPI with the Compose PostgreSQL and Redis services and a real RQ `SimpleWorker` (not the inline test queue). The job completed at 100%: 679 archive entries discovered, 624 filtered/indexed repository files, 55 unsupported entries skipped, 361 supported source files parsed, 341 resolved dependency edges, and an architecture report saved. One formerly crashing JavaScript source was traced to native Tree-sitter node traversal causing a Python access violation. The parser still invokes Tree-sitter for syntax recovery, while symbol/import extraction now avoids retaining/traversing native node wrappers.

## Layout behavior

The app shell uses a fixed desktop sidebar column and `minmax(0, 1fr)` for the content column. At mobile widths the sidebar is a drawer with an outside-click backdrop. A resize listener restores the persistent sidebar when returning to desktop width. The frontend test exercises the desktop/tablet sidebar at 1920, 1600, 1366, 1280, 1024 and 768 pixel widths and the mobile drawer at 390 pixels. These checks validate responsive navigation state; actual browser screenshots and horizontal-overflow measurements at those viewport heights remain unverified.

## Database entities

Users own repositories. Repositories own files, analysis results, dependencies, jobs and saved graphs. Dependencies point to a source file and optionally a resolved target file; unresolved imports retain their source text and are never drawn as verified graph edges. Cascading deletes remove a user's repository data.
