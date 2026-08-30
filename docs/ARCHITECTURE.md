# Arquitetura

```text
USUÁRIO
  ↓
REACT / VITE ───────────── CONTEXT INSPECTOR 2.0
  ↓ HTTP + SSE localhost           ↑ evidências + orçamento
FASTAPI / API MODULAR         AGENT LOOP (máx. 5 ciclos)
  ↓                                ↓
SQLITE ← DOMAIN SERVICES ← CONTEXT BUILDER 3.0 ← HYBRID RETRIEVERS
  ↑                                ↓
MEMÓRIA · TAREFAS · DOCUMENTOS   LLMProvider
                                   ↓
                             OllamaProvider
                                   ↓
                            Qwen 3.5 4B local
                                   ↓ tool request
                             TOOL REGISTRY
                                   ↓
                      POLICY / CONFIRMATION / EXECUTOR
                                   ↓
                       RESULTADO REAL + ACTIVITY LOG

COGNITIVE GRAPH SERVICE ← SQLITE + TOOL REGISTRY
          ↓                         ↑ eventos reais
THREE.JS / FALLBACK 2D ← SSE ← COGNITIVE STATE SERVICE

MICROFONE → VAD → WEBSOCKET LOCAL → VOICE SESSION MANAGER
                                      ↓
                         VOICE WORKER ISOLADO (8766)
                         faster-whisper / XTTS-v2
                                      ↓
                  PERFIL JARVIS PERSISTENTE → ALTO-FALANTE
```

O frontend nunca acessa o SQLite diretamente. `AgentController` persiste `agent_runs`, itera entre modelo e ferramentas e pausa exatamente o mesmo run em ações `CONFIRM`. `ContextBuilder` seleciona itens inteiros: persona, resumo incremental, mensagens recentes, memórias ativas, trechos habilitados e tarefas relacionadas; o banco inteiro não é enviado ao modelo.

`MemoryService`, `TaskService`, `KnowledgeService` e `ConversationService` concentram validação e regras usadas tanto pela API quanto pelas tools. A busca de memória combina FTS5, embedding local opcional, importância e recência, preservando FTS5 como fallback.

`LLMProvider` impede que detalhes do Ollama se espalhem pelo domínio. `LLMRegistry` permite providers futuros sem mudar o controlador. Atualmente só existe `OllamaProvider`, sem fallback externo. O chat usa SSE e o cancelamento fecha a geração, preservando o texto parcial com estado explícito.

Cada ferramenta declara nome, descrição, JSON Schema, nível de risco e execução. SAFE pode rodar automaticamente; CONFIRM cria uma ação pendente; DANGEROUS é bloqueada. O executor registra sucessos, falhas, bloqueios e cancelamentos. O LLM nunca recebe shell.

O estado de uma ação de escrita percorre `pending_confirmation → executing → success/failed`, ou termina em `cancelled`. Só após o resultado real ser persistido o modelo recebe o resultado verificado e redige a resposta final.

Conversa, memória e biblioteca são domínios separados. Conversa é cronologia, memória é informação estruturada e biblioteca contém documentos externos com trechos pesquisáveis via SQLite FTS5.

Voz usa contratos independentes e um worker Python isolado para não contaminar o backend. O VoiceSessionManager encaminha transcripts ao mesmo AgentController, respeita CONFIRM/DANGEROUS, fragmenta sentenças estáveis e retorna áudio pelo WebSocket. Integrações, calendários, automações, mobile e ESP32 continuam fora desta versão.

O Cognitive Core é um consumidor adicional e não substitui os domínios existentes. O grafo usa layout determinístico, relações computáveis e limite de grau. O `CognitiveStateService` é agnóstico à UI e transmite somente estado operacional e ids de entidades, nunca chain-of-thought.
