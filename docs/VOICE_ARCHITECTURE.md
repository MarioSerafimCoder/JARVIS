# Voice Engine local

## Resultado arquitetural

```text
getUserMedia -> VAD do navegador + EnergyVAD PCM16 -> WebSocket localhost
  -> VoiceSessionManager -> VoiceTurnManager -> faster-whisper small pt-BR
  -> AgentController -> Qwen / memória / knowledge / tasks / tools
  -> SpeechChunker -> SpeechTextNormalizer -> cache LRU
  -> XTTS-v2 + conditioning.pt do perfil Jarvis -> áudio WAV -> navegador
  -> LISTENING
```

O chat textual e o `AgentController` não dependem de Whisper, Silero, XTTS ou PyTorch. Modelos de voz rodam no `Voice Worker`, processo Python isolado em `127.0.0.1:8766`. O backend principal conversa com ele pelo contrato `SpeechToTextProvider`/`TextToSpeechProvider`. Se o worker estiver ausente, texto, memória e tools continuam funcionando.

## Contratos e componentes

- `SpeechToTextProvider`: initialize, transcribe, health, model info e unload;
- `VoiceActivityDetector`: detecção local com parâmetros conservadores;
- `TextToSpeechProvider`: build persistente, síntese, health e voice info;
- `VoiceProfileManager`: referências autorizadas, fingerprint, relatório e estado `OUTDATED`;
- `VoiceSessionManager`: turnos, estados, confirmação, interrupção e privacidade;
- `SpeechTextNormalizer`: transforma somente o texto falado, preservando a mensagem salva;
- `SpeechChunker`: libera sentenças estáveis sem cortar palavras;
- `TTSCache`: chave por profile/texto/style/config e limpeza LRU;
- `VoiceResourceManager`: AUTO, LOW_LATENCY, BALANCED e LOW_VRAM.

## Identidade vocal

As 28 referências autorizadas em `Jarvis-Voice/` são copiadas, sem alteração, para `data/voices/jarvis/references/`. Perfil, cache e áudio transitório ficam nos demais subdiretórios ignorados pelo Git. O fingerprint usa nome, tamanho e data de modificação. Mudanças produzem `OUTDATED`; a reconstrução nunca ocorre silenciosamente.

O XTTS calcula uma vez `gpt_cond_latent` e `speaker_embedding`, persiste ambos em `profile/conditioning.pt` e os reutiliza em toda síntese. Não há seleção aleatória de WAV e não existe fallback secreto para voz genérica.

XTTS-v2 usa a Coqui Public Model License, limitada a usos não comerciais. O worker só carrega/baixa o modelo depois da aceitação explícita por `JARVIS_XTTS_LICENSE_ACCEPTED=1`.

## Sessão e protocolo

`WS /api/voice/session` aceita `session_start`, áudio binário/`audio_chunk`, mute, unmute, interrupt, confirmation e session_stop. Emite session_ready, listening, transcript, thinking, assistant_text, tts_chunk, speaking, confirmation_required, tool_result e error.

O frontend mantém o microfone com echo cancellation, noise suppression e auto gain control configuráveis. Durante playback, o VAD continua observando a entrada; fala acima do limiar interrompe o áudio e cancela a fila (barge-in). Push-to-talk permanece como fallback.

Estados do turno: waiting, listening, speech_detected, transcribing, processing, speaking, interrupted e waiting_confirmation. Metadados da sessão e texto ficam persistidos; áudio bruto do microfone não.

## Segurança e privacidade

- WebSocket, worker e APIs restritos a localhost;
- nenhum provider de voz cloud, telemetria ou analytics;
- caminhos enviados ao worker precisam estar dentro de `data/voices/jarvis`;
- referências, profile e cache estão no `.gitignore`;
- ações CONFIRM continuam usando o mesmo `AgentController`; frases ambíguas não executam;
- DANGEROUS continua bloqueado pelo Tool Registry;
- backup inclui profile, manifest e settings; referências brutas somente com opção explícita.

## Ativação do provider real

Consulte `backend/voice_worker/README.md`. A recomendação inicial para este hardware é `faster-whisper small` em CPU int8 e XTTS na GPU sequencialmente, deixando Qwen como prioridade. Medium deve ser comparado somente após o benchmark de small.
