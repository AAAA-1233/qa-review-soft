$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = "C:\Users\28595\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$npm = "D:\Program Files\nodejs\npm.cmd"
$url = "http://127.0.0.1:4183/"
$logDir = Join-Path $root "logs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path (Join-Path $backend "app\main.py"))) {
  throw "Backend entry not found: $backend\app\main.py"
}

if (-not (Test-Path (Join-Path $frontend "package.json"))) {
  throw "Frontend package.json not found: $frontend\package.json"
}

if (-not (Test-Path $python)) {
  throw "Python not found: $python"
}

if (-not (Test-Path $npm)) {
  $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if (-not $npmCommand) {
    throw "npm not found: $npm"
  }
  $npm = $npmCommand.Source
}

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
  Write-Host "Installing frontend dependencies..."
  Push-Location $frontend
  try {
    & $npm install
  } finally {
    Pop-Location
  }
}

Write-Host "Building frontend..."
Push-Location $frontend
try {
  & $npm run build
} finally {
  Pop-Location
}

$backendLog = Join-Path $logDir "backend.log"
$frontendLog = Join-Path $logDir "frontend.log"
$backendExit = Join-Path $logDir "backend-exit.txt"
$frontendExit = Join-Path $logDir "frontend-exit.txt"
$backendRunner = Join-Path $logDir "run-backend.ps1"
$frontendRunner = Join-Path $logDir "run-frontend.ps1"

Remove-Item -ErrorAction SilentlyContinue $backendExit, $frontendExit

$backendScript = @"
`$ErrorActionPreference = "Continue"
Set-Location -LiteralPath '$backend'
"Backend starting at $(Get-Date -Format s)" | Tee-Object -FilePath '$backendLog' -Append
& '$python' -m uvicorn app.main:app --host 127.0.0.1 --port 8010 *>> '$backendLog'
`$code = if (`$LASTEXITCODE -ne `$null) { `$LASTEXITCODE } else { 0 }
"Backend stopped. Exit code: `$code" | Tee-Object -FilePath '$backendExit'
"Backend stopped. Check log: $backendLog"
Read-Host "Press Enter to close"
"@

$frontendScript = @"
`$ErrorActionPreference = "Continue"
Set-Location -LiteralPath '$frontend'
"Frontend starting at $(Get-Date -Format s)" | Tee-Object -FilePath '$frontendLog' -Append
& '$npm' run preview -- --host 127.0.0.1 --port 4183 *>> '$frontendLog'
`$code = if (`$LASTEXITCODE -ne `$null) { `$LASTEXITCODE } else { 0 }
"Frontend stopped. Exit code: `$code" | Tee-Object -FilePath '$frontendExit'
"Frontend stopped. Check log: $frontendLog"
Read-Host "Press Enter to close"
"@

Set-Content -Encoding UTF8 -Path $backendRunner -Value $backendScript
Set-Content -Encoding UTF8 -Path $frontendRunner -Value $frontendScript

Write-Host "Starting backend: http://127.0.0.1:8010"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $backendRunner -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "Starting frontend: $url"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $frontendRunner -WindowStyle Normal

Start-Sleep -Seconds 5
try {
  Start-Process $url
} catch {
  Write-Host "Could not open browser automatically. Open this URL manually:"
  Write-Host $url
}

Write-Host ""
Write-Host "Started. Logs:"
Write-Host $backendLog
Write-Host $frontendLog
