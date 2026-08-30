$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Ambiente Python do backend não encontrado.' }
& $pythonExe -m pip install 'playwright==1.55.0'
Write-Host 'Browser Worker instalado. Ele usa o Microsoft Edge existente e um perfil exclusivo do Jarvis.'

