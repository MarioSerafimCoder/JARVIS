# Voice Worker local

Processo isolado para `faster-whisper` e `XTTS-v2`. Ele escuta apenas em `127.0.0.1:8766`; o backend principal não importa PyTorch, Coqui ou CTranslate2.

O modelo XTTS-v2 usa a Coqui Public Model License e é permitido apenas para uso não comercial. Antes do primeiro download/build, leia a licença e use o parâmetro de aceite somente se concordar. O aceite fica registrado nos dados privados do perfil; nenhum áudio é enviado para fora da máquina.

```powershell
cd ..\..
.\setup-voice.ps1 -AcceptXttsNonCommercialLicense -DownloadModels
.\start-voice.ps1 -NoWait
```

O instalador usa PyTorch 2.8 com CUDA 12.8, fixa Transformers 4.57.3 por compatibilidade com XTTS e coloca os modelos em `data/voices/jarvis/models/`. O worker usa `local_files_only=True` para o Whisper e não baixa o STT durante uma conversa.
