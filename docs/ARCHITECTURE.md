# Arquitetura

```text
USUÁRIO
  ↓
REACT / VITE ───────────── CONTEXT INSPECTOR 2.0
  ↓ HTTP + SSE localhost           ↑ evidências + orçamento
FASTAPI / API MODULAR         AGENT CONTROLLER
  ↓                                ↓
SQLITE ← REPOSITÓRIOS ← CONTEXT BUILDER ← RETRIEVERS
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
```

O frontend nunca acessa o SQLite diretamente. `AgentController` orquestra persona, contexto, modelo e ferramentas. `ContextBuilder` seleciona apenas mensagens recentes, memórias relevantes, trechos FTS5 e tarefas relacionadas; o banco inteiro não é enviado ao modelo.

`LLMProvider` impede que detalhes do Ollama se espalhem pelo domínio. `LLMRegistry` permite providers futuros sem mudar o controlador. Atualmente só existe `OllamaProvider`, sem fallback externo. O chat usa SSE e o cancelamento fecha a geração, preservando o texto parcial com estado explícito.

Cada ferramenta declara nome, descrição, JSON Schema, nível de risco e execução. SAFE pode rodar automaticamente; CONFIRM cria uma ação pendente; DANGEROUS é bloqueada. O executor registra sucessos, falhas, bloqueios e cancelamentos. O LLM nunca recebe shell.

O estado de uma ação de escrita percorre `pending_confirmation → executing → success/failed`, ou termina em `cancelled`. Só após o resultado real ser persistido o modelo recebe o resultado verificado e redige a resposta final.

Conversa, memória e biblioteca são domínios separados. Conversa é cronologia, memória é informação estruturada e biblioteca contém documentos externos com trechos pesquisáveis via SQLite FTS5.

Voz, integrações, calendários, automações, mobile e ESP32 usam contratos ou páginas estruturais, mas não são declarados funcionais nesta versão.

O Cognitive Core é um consumidor adicional e não substitui os domínios existentes. O grafo usa layout determinístico, relações computáveis e limite de grau. O `CognitiveStateService` é agnóstico à UI e transmite somente estado operacional e ids de entidades, nunca chain-of-thought.
