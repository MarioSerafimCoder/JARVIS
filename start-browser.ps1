param([switch]$NoWait)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workerRoot = Join-Path $projectRoot 'backend\browser_worker'
$pythonExe = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Ambiente Python do backend não encontrado.' }
& $pythonExe -c 'import playwright' 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Playwright não instalado. Execute setup-browser.ps1.' }
$process = Start-Process -FilePath $pythonExe -ArgumentList '-m','uvicorn','app:app','--host','127.0.0.1','--port','8767' -WorkingDirectory $workerRoot -WindowStyle Hidden -PassThru
Set-Content -LiteralPath (Join-Path $projectRoot '.browser.pid') -Value $process.Id
Write-Host 'Browser Worker local iniciado em 127.0.0.1:8767.'
if (-not $NoWait) { Wait-Process -Id $process.Id }

