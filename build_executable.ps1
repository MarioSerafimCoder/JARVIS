$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendRoot = Join-Path $projectRoot 'frontend'
$backendRoot = Join-Path $projectRoot 'backend'
$pythonExe = Join-Path $backendRoot '.venv\Scripts\python.exe'
$staticRoot = Join-Path $backendRoot 'frontend'
$releaseRoot = Join-Path $projectRoot 'release'

Push-Location $frontendRoot
try { npm run build } finally { Pop-Location }
if (Test-Path -LiteralPath $staticRoot) { Remove-Item -LiteralPath $staticRoot -Recurse -Force }
Copy-Item -LiteralPath (Join-Path $frontendRoot 'dist') -Destination $staticRoot -Recurse

Push-Location $backendRoot
try {
  & $pythonExe -m PyInstaller --noconfirm --clean --onedir --name JarvisLocal `
    --distpath (Join-Path $releaseRoot 'app') --workpath (Join-Path $releaseRoot 'build') `
    --specpath (Join-Path $releaseRoot 'spec') `
    --add-data "$staticRoot;frontend" --add-data "$(Join-Path $backendRoot 'app\prompts\persona.md');app/prompts" `
    --collect-all uvicorn --collect-all pydantic_settings --collect-all fitz --collect-all docx `
    launcher.py
  if ($LASTEXITCODE -ne 0) { throw "A geração do executável falhou com código $LASTEXITCODE." }
} finally { Pop-Location }

$guide = Join-Path $releaseRoot 'LEIA-ME.txt'
@'
JARVIS LOCAL — COMO ABRIR

1. Instale o Ollama: https://ollama.com/download/windows
2. No PowerShell, execute: ollama pull qwen3.5:4b
3. Abra app\JarvisLocal\JarvisLocal.exe
4. A interface abrirá no navegador em http://127.0.0.1:8765

Se a janela do Jarvis for fechada, o serviço local será encerrado.
Seus dados ficam na pasta app\JarvisLocal\data, ao lado do executável.
'@ | Set-Content -LiteralPath $guide -Encoding utf8
Compress-Archive -Path (Join-Path $releaseRoot 'app\JarvisLocal'),$guide -DestinationPath (Join-Path $releaseRoot 'JarvisLocal-Windows.zip') -Force
Write-Host "Executável criado em $releaseRoot\app\JarvisLocal\JarvisLocal.exe"
