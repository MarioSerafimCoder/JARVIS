param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$pythonExe = Join-Path $backendRoot '.venv\Scripts\python.exe'
$ollamaExe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'

if (-not (Test-Path -LiteralPath $pythonExe)) {
  throw 'Ambiente Python não encontrado. Execute a instalação descrita no README.'
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules'))) {
  throw 'Dependências do frontend não encontradas. Execute npm install na pasta frontend.'
}
if (-not (Get-Process -Name ollama -ErrorAction SilentlyContinue)) {
  $ollamaProcess = Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden -PassThru
  Set-Content -LiteralPath (Join-Path $projectRoot '.ollama.pid') -Value $ollamaProcess.Id
}
$backendProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru
$frontendProcess = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev' -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru
Set-Content -LiteralPath (Join-Path $projectRoot '.backend.pid') -Value $backendProcess.Id
Set-Content -LiteralPath (Join-Path $projectRoot '.frontend.pid') -Value $frontendProcess.Id
Start-Sleep -Seconds 3
if (-not $NoBrowser) {
  Start-Process 'http://127.0.0.1:5173'
}
Write-Host 'Jarvis iniciado em http://127.0.0.1:5173'
