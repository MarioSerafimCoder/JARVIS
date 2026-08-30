param([switch]$NoWait)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workerRoot = Join-Path $projectRoot 'backend\voice_worker'
$pythonExe = Join-Path $workerRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
  throw 'Voice Worker não instalado. Siga backend\voice_worker\README.md. O chat textual continua funcionando.'
}
$process = Start-Process -FilePath $pythonExe -ArgumentList '-m','uvicorn','app:app','--host','127.0.0.1','--port','8766' -WorkingDirectory $workerRoot -WindowStyle Hidden -PassThru
Set-Content -LiteralPath (Join-Path $projectRoot '.voice.pid') -Value $process.Id
Write-Host 'Voice Worker local iniciado em 127.0.0.1:8766.'
if (-not $NoWait) { Wait-Process -Id $process.Id }
