
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$Backend = Join-Path $Root "Backend"
$Frontend = Join-Path $Root "Frontend"

$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$RQ = Join-Path $Backend ".venv\Scripts\rq.exe"

Write-Host "`n=== Starting CodeAtlas AI ===" -ForegroundColor Cyan

# Check required files
if (!(Test-Path $Python)) {
    throw "Backend virtual environment not found. Check Backend\.venv"
}
if (!(Test-Path $RQ)) {
    throw "RQ executable not found in Backend\.venv"
}
if (!(Test-Path (Join-Path $Frontend "package.json"))) {
    throw "Frontend package.json not found"
}

# Start Docker services
Write-Host "`nStarting PostgreSQL and Redis..." -ForegroundColor Yellow
docker compose -f (Join-Path $Root "docker-compose.yml") up -d

if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed. Open Docker Desktop and retry."
}

# Wait for PostgreSQL
Write-Host "Waiting for PostgreSQL..." -ForegroundColor Yellow
$Ready = $false

for ($i = 0; $i -lt 30; $i++) {
    docker compose exec -T postgres pg_isready 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $Ready = $true
        break
    }
    Start-Sleep -Seconds 2
}

if (!$Ready) {
    throw "PostgreSQL did not become ready."
}

# Wait for Redis
Write-Host "Waiting for Redis..." -ForegroundColor Yellow
$Ready = $false

for ($i = 0; $i -lt 30; $i++) {
    $RedisStatus = docker compose exec -T redis redis-cli ping 2>$null
    if ($LASTEXITCODE -eq 0 -and "$RedisStatus".Trim() -eq "PONG") {
        $Ready = $true
        break
    }
    Start-Sleep -Seconds 2
}

if (!$Ready) {
    throw "Redis did not become ready."
}

# Apply database migrations
Write-Host "`nApplying database migrations..." -ForegroundColor Yellow
Push-Location $Backend
try {
    & $Python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Database migration failed."
    }
}
finally {
    Pop-Location
}

# Start backend
Write-Host "`nStarting FastAPI..." -ForegroundColor Green
Start-Process powershell.exe -WorkingDirectory $Backend -ArgumentList @(
    "-NoExit",
    "-Command",
    "& '$Python' -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"
)

# Start analysis worker
Write-Host "Starting RQ worker..." -ForegroundColor Green
Start-Process powershell.exe -WorkingDirectory $Backend -ArgumentList @(
    "-NoExit",
    "-Command",
    "& '$RQ' worker -w rq.worker.SimpleWorker codeatlas-analysis"
)

# Start frontend
Write-Host "Starting React frontend..." -ForegroundColor Green
Start-Process powershell.exe -WorkingDirectory $Frontend -ArgumentList @(
    "-NoExit",
    "-Command",
    "npm.cmd run dev"
)

Write-Host "`nCodeAtlas startup completed!" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173"
Write-Host "Backend:  http://localhost:8000/docs"
