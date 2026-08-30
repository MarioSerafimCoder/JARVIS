$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFiles = @('.backend.pid', '.frontend.pid', '.voice.pid', '.browser.pid', '.ollama.pid')
foreach ($pidFile in $pidFiles) {
  $path = Join-Path $projectRoot $pidFile
  if (Test-Path -LiteralPath $path) {
    $processId = [int](Get-Content -LiteralPath $path)
    Stop-Process -Id $processId -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $path -Force
  }
}
Write-Host 'Processos do Jarvis encerrados.'
