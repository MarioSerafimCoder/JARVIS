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
if (-not (Test-Path -LiteralPath $pythonExe)) {
  py -3.12 -m venv (Join-Path $workerRoot '.venv')
}
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $workerRoot 'requirements.txt')
if ($DownloadModels) {
  $env:JARVIS_VOICE_ROOT = $voiceRoot
  $env:JARVIS_XTTS_LICENSE_ACCEPTED = '1'
  $modelRoot = Join-Path $voiceRoot 'models\faster-whisper-small'
  & $pythonExe -c "from faster_whisper.utils import download_model; download_model('small', output_dir=r'$modelRoot')"
  & $pythonExe -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
}
Write-Host 'Voice Worker instalado em ambiente isolado.'
Write-Host 'Para iniciar XTTS nesta sessão, defina JARVIS_XTTS_LICENSE_ACCEPTED=1 e execute .\start-voice.ps1 -NoWait.'
