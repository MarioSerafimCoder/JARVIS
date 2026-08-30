# Jarvis Local

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

Consulte [INTELLIGENCE_ENGINE.md](docs/INTELLIGENCE_ENGINE.md) para a Fase 2, [COGNITIVE_CORE.md](docs/COGNITIVE_CORE.md) para o modelo visual e [ROADMAP.md](docs/ROADMAP.md) para a separação entre implementado e planejado.

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

Os dados ficam em `data/`: banco em `data/database/jarvis.db`, documentos em `data/library/` e notas em `data/notes/`. Essa pasta, `.env` e logs privados estão ignorados pelo Git. Não há telemetria, analytics ou upload automático.

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
