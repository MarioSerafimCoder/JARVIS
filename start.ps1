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
Start-Process -FilePath $pythonExe -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $backendRoot -WindowStyle Hidden | Out-Null
$voicePython = Join-Path $backendRoot 'voice_worker\.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $voicePython) {
  $voiceProcess = Start-Process -FilePath $voicePython -ArgumentList '-m','uvicorn','app:app','--host','127.0.0.1','--port','8766' -WorkingDirectory (Join-Path $backendRoot 'voice_worker') -WindowStyle Hidden -PassThru
  Set-Content -LiteralPath (Join-Path $projectRoot '.voice.pid') -Value $voiceProcess.Id
}
$browserReady = (& $pythonExe -c 'import importlib.util; print(1 if importlib.util.find_spec("playwright") else 0)').Trim() -eq '1'
if ($browserReady) {
  $browserProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m','uvicorn','app:app','--host','127.0.0.1','--port','8767' -WorkingDirectory (Join-Path $backendRoot 'browser_worker') -WindowStyle Hidden -PassThru
  Set-Content -LiteralPath (Join-Path $projectRoot '.browser.pid') -Value $browserProcess.Id
}
Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev' -WorkingDirectory $frontendRoot -WindowStyle Hidden | Out-Null
Start-Sleep -Seconds 3
$backendProcessId = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction Stop | Select-Object -First 1).OwningProcess
$frontendProcessId = (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction Stop | Select-Object -First 1).OwningProcess
Set-Content -LiteralPath (Join-Path $projectRoot '.backend.pid') -Value $backendProcessId
Set-Content -LiteralPath (Join-Path $projectRoot '.frontend.pid') -Value $frontendProcessId
if (-not $NoBrowser) {
  Start-Process 'http://127.0.0.1:5173'
}
Write-Host 'Jarvis iniciado em http://127.0.0.1:5173'
if (-not (Test-Path -LiteralPath $voicePython)) { Write-Host 'Voice Worker opcional não instalado; chat textual disponível.' }
if (-not $browserReady) { Write-Host 'Browser Worker opcional não instalado; execute setup-browser.ps1. Recursos offline e busca web continuam disponíveis.' }
