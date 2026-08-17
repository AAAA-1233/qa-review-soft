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
  throw "未找到后端入口：$backend\app\main.py"
}

if (-not (Test-Path (Join-Path $frontend "package.json"))) {
  throw "未找到前端 package.json：$frontend\package.json"
}

if (-not (Test-Path $python)) {
  throw "未找到 Python：$python"
}

if (-not (Test-Path $npm)) {
  $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if (-not $npmCommand) {
    throw "未找到 npm：$npm，也没有在 PATH 里找到 npm.cmd"
  }
  $npm = $npmCommand.Source
}

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
  Write-Host "首次运行：正在安装前端依赖..."
  Push-Location $frontend
  try {
    & $npm install
  } finally {
    Pop-Location
  }
}

if (-not (Test-Path (Join-Path $frontend "dist\index.html"))) {
  Write-Host "首次运行：正在构建前端..."
  Push-Location $frontend
  try {
    & $npm run build
  } finally {
    Pop-Location
  }
}

$backendLog = Join-Path $logDir "backend.log"
$frontendLog = Join-Path $logDir "frontend.log"

$backendCommand = "cd /d `"$backend`" && `"$python`" -m uvicorn app.main:app --host 127.0.0.1 --port 8010 1>> `"$backendLog`" 2>>&1"
$frontendCommand = "cd /d `"$frontend`" && call `"$npm`" run preview -- --host 127.0.0.1 --port 4183 1>> `"$frontendLog`" 2>>&1"

Write-Host "正在启动后端：http://127.0.0.1:8010"
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $backendCommand -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "正在启动前端：$url"
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $frontendCommand -WindowStyle Normal

Start-Sleep -Seconds 4
Start-Process $url

Write-Host ""
Write-Host "已启动。日志位置：$logDir"
