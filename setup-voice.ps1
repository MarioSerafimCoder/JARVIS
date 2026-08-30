param(
  [switch]$AcceptXttsNonCommercialLicense,
  [switch]$DownloadModels
)

$ErrorActionPreference = 'Stop'
if (-not $AcceptXttsNonCommercialLicense) {
  throw 'Leia a Coqui Public Model License. Execute novamente com -AcceptXttsNonCommercialLicense somente para uso não comercial e se concordar.'
}
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workerRoot = Join-Path $projectRoot 'backend\voice_worker'
$voiceRoot = Join-Path $projectRoot 'data\voices\jarvis'
$pythonExe = Join-Path $workerRoot '.venv\Scripts\python.exe'
$licenseMarker = Join-Path $voiceRoot 'profile\xtts-license-accepted.json'
if (-not (Test-Path -LiteralPath $pythonExe)) {
  py -3.12 -m venv (Join-Path $workerRoot '.venv')
  if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o ambiente isolado do Voice Worker.' }
}
& $pythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Falha ao atualizar o instalador Python do Voice Worker.' }
& $pythonExe -m pip install -r (Join-Path $workerRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar as dependências do Voice Worker.' }
& $pythonExe -c "import torch, torchaudio"
if ($LASTEXITCODE -ne 0) {
  & $pythonExe -m pip install 'torch==2.8.0' 'torchaudio==2.8.0' --index-url 'https://download.pytorch.org/whl/cu128'
  if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar PyTorch/Torchaudio com suporte CUDA 12.8.' }
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $licenseMarker) | Out-Null
@{
  license = 'Coqui Public Model License 1.0.0'
  scope = 'non-commercial'
  accepted_at = (Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json | Set-Content -LiteralPath $licenseMarker -Encoding UTF8
if ($DownloadModels) {
  $env:JARVIS_VOICE_ROOT = $voiceRoot
  $env:JARVIS_XTTS_LICENSE_ACCEPTED = '1'
  $env:COQUI_TOS_AGREED = '1'
  $env:TTS_HOME = Join-Path $voiceRoot 'models\coqui'
  $modelRoot = Join-Path $voiceRoot 'models\faster-whisper-small'
  & $pythonExe -c "from faster_whisper.utils import download_model; download_model('small', output_dir=r'$modelRoot')"
  if ($LASTEXITCODE -ne 0) { throw 'Falha ao baixar o modelo faster-whisper small.' }
  & $pythonExe -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
  if ($LASTEXITCODE -ne 0) { throw 'Falha ao baixar ou carregar o modelo XTTS-v2.' }
}
Write-Host 'Voice Worker instalado em ambiente isolado.'
Write-Host 'Aceite não comercial registrado localmente. Execute .\start-voice.ps1 -NoWait.'
