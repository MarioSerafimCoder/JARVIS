# Jarvis Local

## Fase 3.1 — Hardening

O Browser Worker agora usa autenticação interna efêmera, candidatos Amazon expiram e usam ASIN/dinheiro estruturado, a voz possui fila FIFO com acknowledgements reais de playback, e o Agent loop não expõe texto intermediário. Contexto, memória, SQLite, persona versionada, providers globais, CI e cobertura também foram endurecidos. Consulte [o relatório da Fase 3.1](docs/HARDENING_REPORT.md) e [os benchmarks](docs/benchmarks/FASE_3_1.md).

## Web Intelligence e Browser Agent

O Jarvis pode pesquisar e ler a web pública com fontes, além de controlar um perfil dedicado do Microsoft Edge por ações semânticas. O modo offline continua funcionando; Web Access começa em **ASK** e Browser Access em **OFF**.

- Configure os modos em **Configurações**.
- Conecte a Amazon em **Conexões**; login, 2FA e CAPTCHA são manuais.
- Busca/leitura web mostram fontes no chat e no Inspetor de contexto.
- Carrinho exige confirmação e verificação. Checkout/finalizar pedido não é implementado.

Na instalação normal, `pip install -r backend/requirements.txt` inclui Playwright. Para uma instalação existente, execute `./setup-browser.ps1`. `./start.ps1` inicia o Browser Worker automaticamente quando disponível. Consulte [Web Architecture](docs/WEB_ARCHITECTURE.md), [Web Security](docs/WEB_SECURITY.md), [Browser Agent](docs/BROWSER_AGENT.md) e [Browser Security](docs/BROWSER_SECURITY.md).

Jarvis Local é a fundação de um sistema operacional pessoal de IA: conversa em português, persiste histórico, separa memória e documentos, gerencia tarefas e só executa ações registradas depois da política de segurança adequada. O núcleo usa Qwen 3.5 4B pelo Ollama e não chama APIs pagas.

## O que já funciona

- Qwen 3.5 4B local, com Ollama e aceleração NVIDIA;
- API FastAPI com SQLite, histórico de conversas, memória, tarefas, notas, biblioteca e auditoria;
- busca de documentos PDF, DOCX, TXT e MD usando FTS5, sem cloud;
- ferramentas SAFE e CONFIRM; ferramentas arbitrárias/perigosas não são expostas ao modelo;
- streaming de respostas por SSE, com interrupção pelo usuário e persistência marcada como cancelada;
- recuperação modular de histórico, memórias, tarefas e documentos com orçamento de contexto e localização da fonte;
- interface React responsiva com Agora, Jarvis, Memória, Biblioteca, Tarefas, Personalidade, Atividade, Uso, Configurações e páginas estruturais;
- CRUD visual de conversas, memória e tarefas, Context Inspector 2.0 e command palette com `Ctrl+K`;
- Cognitive Core 3D baseado em dados reais, com estados do agente, relações justificadas, modo expandido e fallback 2D;
- Intelligence Engine com agent loop de até cinco ciclos, pausa/retomada após confirmação e auditoria por `agent_run_id`;
- Memory Engine 2.0 com sugestões confirmáveis, deduplicação, supersessão, resumo incremental e busca híbrida local com fallback FTS5;
- feedback por resposta, rotas reais, command palette navegável, briefing Agora e onboarding local;
- backup consistente do banco e dos arquivos em ZIP;
- exportação local em JSON pelo endpoint `/api/export`.
- Voice Engine local com WebSocket bidirecional, estados LISTENING/TRANSCRIBING/SPEAKING, barge-in, confirmação segura e fallback textual;
- Voice Lab em **Personalidade → Voz**, análise das 28 referências autorizadas, fingerprint persistente, cache LRU e worker isolado para faster-whisper/XTTS-v2.

Consulte [VOICE_ARCHITECTURE.md](docs/VOICE_ARCHITECTURE.md) para a camada vocal, [VOICE_REFERENCE_REPORT.md](docs/VOICE_REFERENCE_REPORT.md) para os áudios, [INTELLIGENCE_ENGINE.md](docs/INTELLIGENCE_ENGINE.md) para a Fase 2 e [ROADMAP.md](docs/ROADMAP.md) para a separação entre implementado e planejado.

## Iniciar

### Executável para Windows

Baixe ou extraia `release/JarvisLocal-Windows.zip` e abra `app/JarvisLocal/JarvisLocal.exe`. A interface abre em [http://127.0.0.1:8765](http://127.0.0.1:8765). O Ollama e o modelo `qwen3.5:4b` precisam estar instalados; o arquivo `LEIA-ME.txt` acompanha o pacote.

Para gerar novamente o pacote:

```powershell
.\build_executable.ps1
```

### Ambiente de desenvolvimento

Abra o PowerShell nesta pasta e execute:

```powershell
.\start.ps1
```

Depois abra [http://127.0.0.1:5173](http://127.0.0.1:5173). A documentação técnica da API fica em [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

O chat textual inicia mesmo sem as dependências de voz. Para ativar o Voice Worker, leia e aceite conscientemente a licença não comercial do XTTS-v2 e siga [backend/voice_worker/README.md](backend/voice_worker/README.md). Em seguida, `start.ps1` detectará o ambiente isolado automaticamente.

Para parar os processos iniciados pelo script:

```powershell
.\stop.ps1
```

### Início manual

Ollama normalmente inicia com o Windows. Se necessário:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve
```

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend, em outro PowerShell:

```powershell
cd frontend
npm run dev
```

## Dados e privacidade

Os dados ficam em `data/`: banco em `data/database/jarvis.db`, documentos em `data/library/`, notas em `data/notes/` e identidade vocal em `data/voices/jarvis/`. Essa pasta, `Jarvis-Voice/`, `.env` e logs privados estão ignorados pelo Git. Não há telemetria, analytics ou upload automático. Gravações do microfone são descartadas após transcrição por padrão.

Use **Configurações → Criar backup local** para gerar um ZIP consistente em `backups/`. Para restaurar manualmente, pare o Jarvis e recoloque os arquivos da cópia nos mesmos caminhos. O endpoint `GET /api/export` fornece uma exportação JSON lógica.

Para apagar todos os dados, pare o Jarvis e remova manualmente a pasta `data/`. Essa operação é irreversível; o projeto não a automatiza.

## Personalidade e modelo

A personalidade pode ser editada na tela **Personalidade** e está em `backend/app/prompts/persona.md`. O modelo e os caminhos são configurados por `.env`; copie `.env.example` para `.env` quando quiser alterar valores. Para trocar de modelo, baixe-o no Ollama e altere `MODEL_NAME`.

Verifique a GPU com:

```powershell
nvidia-smi
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" ps
```

Quando houver uma inferência ativa, `ollama ps` deve mostrar `100% GPU` na coluna `PROCESSOR`.

## Desenvolvimento e testes

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest

cd ..\frontend
npm test
npm run build
```

## Desinstalação

Pare o Jarvis, desinstale Ollama nas Configurações do Windows se não quiser mais usá-lo e então remova esta pasta. Os modelos locais do Ollama são gerenciados pelo próprio Ollama.
