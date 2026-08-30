# Voice Worker local

Processo isolado para `faster-whisper` e `XTTS-v2`. Ele escuta apenas em `127.0.0.1:8766`; o backend principal não importa PyTorch, Coqui ou CTranslate2.

O modelo XTTS-v2 usa a Coqui Public Model License e é permitido apenas para uso não comercial. Antes do primeiro download/build, leia a licença e defina `JARVIS_XTTS_LICENSE_ACCEPTED=1` somente se concordar. Nenhum áudio é enviado para fora da máquina.

```powershell
cd ..\..
.\setup-voice.ps1 -AcceptXttsNonCommercialLicense -DownloadModels
$env:JARVIS_XTTS_LICENSE_ACCEPTED='1'
.\start-voice.ps1 -NoWait
```

Baixe/converta o modelo `faster-whisper-small` previamente para `data/voices/jarvis/models/faster-whisper-small`. O worker usa `local_files_only=True` e não baixa o STT durante uma conversa.
