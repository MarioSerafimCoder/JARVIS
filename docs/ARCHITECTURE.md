# Arquitetura

```text
USUÁRIO
  ↓
REACT / VITE ─────────────── CONTEXT INSPECTOR
  ↓ HTTP localhost                 ↑ evidências
FASTAPI / API                 AGENT CONTROLLER
  ↓                                ↓
SQLITE ← REPOSITÓRIOS ← CONTEXT BUILDER
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
```

O frontend nunca acessa o SQLite diretamente. `AgentController` orquestra persona, contexto, modelo e ferramentas. `ContextBuilder` seleciona apenas mensagens recentes, memórias relevantes, trechos FTS5 e tarefas relacionadas; o banco inteiro não é enviado ao modelo.

`LLMProvider` impede que detalhes do Ollama se espalhem pelo domínio. `LLMRegistry` permite providers futuros sem mudar o controlador. Atualmente só existe `OllamaProvider`, sem fallback externo.

Cada ferramenta declara nome, descrição, JSON Schema, nível de risco e execução. SAFE pode rodar automaticamente; CONFIRM cria uma ação pendente; DANGEROUS é bloqueada. O executor registra sucessos, falhas, bloqueios e cancelamentos. O LLM nunca recebe shell.

Conversa, memória e biblioteca são domínios separados. Conversa é cronologia, memória é informação estruturada e biblioteca contém documentos externos com trechos pesquisáveis via SQLite FTS5.

Voz, integrações, calendários, automações, mobile e ESP32 usam contratos ou páginas estruturais, mas não são declarados funcionais nesta versão.

