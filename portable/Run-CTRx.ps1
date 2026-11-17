param([ValidateSet('Start', 'Stop')][string]$Action = 'Start')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install Docker Desktop, open it, then try again.' }
    $os = & docker info --format '{{.OSType}}' 2>$null
    if ($LASTEXITCODE -ne 0 -or $os -ne 'linux') { throw 'Open Docker Desktop and select Linux containers before continuing.' }
    if (-not (Test-Path .env.docker)) { throw 'Missing .env.docker. Copy your populated settings file into this folder.' }
    $dc = @('compose', '-p', 'ctrx-portable', '--env-file', '.env.docker', '-f', 'compose.yml')
    if ($Action -eq 'Stop') {
        & docker @dc down
        if ($LASTEXITCODE -ne 0) { throw 'Could not stop CTRx.' }
        Write-Host 'CTRx stopped. Uploaded files are retained.'
        exit 0
    }
    & docker @dc config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Invalid configuration.' }
    foreach ($image in @('ctrx-backend:local', 'ctrx-frontend:local')) {
        & docker image inspect $image *> $null
        if ($LASTEXITCODE -ne 0) {
            if (-not (Test-Path ctrx-images.tar)) { throw 'Missing ctrx-images.tar. Export the images on the original PC first.' }
            & docker load --input ctrx-images.tar
            if ($LASTEXITCODE -ne 0) { throw 'Image import failed.' }
            break
        }
    }
    & docker @dc run --rm --no-deps --pull never migrate python -m app.scripts.container_db check
    if ($LASTEXITCODE -ne 0) { throw 'Database check failed. No migration or bootstrap was run.' }
    & docker @dc up -d --no-build --pull never --wait --wait-timeout 180 backend frontend
    if ($LASTEXITCODE -ne 0) {
        & docker @dc logs --tail=60 backend frontend
        throw 'Startup failed. See the logs above.'
    }
    $port = '8080'
    foreach ($line in Get-Content .env.docker) {
        if ($line -match '^\s*CTRX_HTTP_PORT\s*=\s*["'']?(\d+)') { $port = $Matches[1] }
    }
    Start-Process "http://localhost:$port"
    Write-Host "CTRx is running at http://localhost:$port"
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
