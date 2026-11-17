# Run from PowerShell on the PC where the CTRx Docker images were built.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker is not on PATH. Open a fresh PowerShell after installing Docker Desktop.' }
foreach ($image in @('ctrx-backend:local', 'ctrx-frontend:local')) {
    & docker image inspect $image *> $null
    if ($LASTEXITCODE -ne 0) { throw "Missing $image. Build CTRx first." }
}
if (-not (Test-Path .env.docker)) { throw 'Missing populated .env.docker.' }
$destination = Join-Path $root 'CTRx-Portable'
New-Item -ItemType Directory -Force $destination | Out-Null
Copy-Item "$root/portable/*" $destination -Force
Copy-Item "$root/portable/.env.docker.example" $destination -Force
Copy-Item "$root/.env.docker" "$destination/.env.docker" -Force
& docker save --output "$destination/ctrx-images.tar" ctrx-backend:local ctrx-frontend:local
if ($LASTEXITCODE -ne 0) { throw 'Image export failed. Do not use the incomplete package.' }
Write-Host "Ready: $destination"
Write-Host 'Carry the entire folder. It contains private credentials; share only with trusted operators.'
