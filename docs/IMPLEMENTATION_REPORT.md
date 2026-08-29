# Relatório da implementação inicial

Data: 29/08/2026

## Hardware e ambiente

- CPU: Intel Core i5-9400F, 6 núcleos / 6 threads.
- RAM: 31,94 GB.
- GPU: NVIDIA GeForce RTX 5050, 8.151 MiB de VRAM.
- Windows 11 Pro build 26200; driver NVIDIA 610.88; CUDA UMD 13.3.
- Python 3.12.5, Node 24.18.0, npm 11.16.0, Git 2.55.0 e Ollama 0.33.2.

## Modelo e performance

- `qwen3.5:4b`, 4,7B parâmetros, Q4_K_M, 3,4 GB.
- Execução confirmada como 100% GPU pelo Ollama.
- Aproximadamente 3,8 GB de VRAM durante inferência.
- Primeira carga: 51,05 s; geração medida: 70,41 tokens/s.
- Resposta aquecida pelo endpoint real do Jarvis: 5,73 s.
- O provider desliga `thinking` em conversas normais e limita a saída, evitando os 4.603 tokens gerados pelo primeiro benchmark bruto.

## Backend implementado

- FastAPI, configuração central, CORS restrito ao frontend local e SQLite em WAL.
- `LLMProvider`, `OllamaProvider`, `LLMRegistry`, `AgentController` e `ContextBuilder`.
- Conversas e mensagens persistentes.
- Memória estruturada e separada do histórico.
- Notas, tarefas, biblioteca de documentos, FTS5, auditoria e uso.
- Endpoints organizados para chat, conversas, memória, biblioteca, tarefas, tools, atividade, persona, sistema, uso, integrações, dispositivos, busca e exportação.

## Frontend implementado

- React, TypeScript, Vite, Tailwind CSS e Lucide.
- Telas funcionais: Agora, Jarvis, Memória, Biblioteca, Tarefas, Personalidade, Atividade, Uso, Dispositivos e Configurações.
- Telas estruturais com estados honestos: Agenda, Automações e Conexões.
- Context Inspector, confirmação visual, busca global e command palette `Ctrl+K`.
- Responsividade validada em desktop e viewport 390×844.

## Banco

Tabelas: `conversations`, `messages`, `memories`, `memories_fts`, `notes`, `tasks`, `documents`, `document_chunks`, `document_chunks_fts`, `pending_actions`, `activity_log`, `usage_events` e `devices`.

## Ferramentas reais

- SAFE: `get_current_datetime`, `get_system_info`, `read_note`, `list_notes`, `search_memory`, `list_memories`, `list_tasks`, `search_documents`.
- CONFIRM: `create_note`, `save_memory`, `delete_memory`, `create_task`, `update_task`, `complete_task`.
- Ferramentas desconhecidas e DANGEROUS são bloqueadas e auditadas.

## Segurança

- O LLM não recebe shell nem caminhos arbitrários.
- Escritas solicitadas pelo modelo só executam após confirmação explícita.
- Uploads limitados por extensão e tamanho, nomes internos aleatórios e proteção contra directory traversal.
- Sem telemetria, analytics, cloud database, API paga ou push remoto.

## Testes executados

- Backend: 16 testes aprovados; zero falhas. Cobrem banco, persistência, documentos, FTS5, políticas SAFE/CONFIRM/DANGEROUS, executor, auditoria e caminhos.
- Frontend: TypeScript e build de produção aprovados; 1.670 módulos transformados.
- Smoke test real aprovado: health, memória, tarefa, upload MD, busca FTS5, chat Qwen, proposta de ferramenta, confirmação, persistência e auditoria.
- Dados artificiais do smoke test não estão no banco ativo.

## Funcionalidades preparadas, não funcionais

Voz, wake word, calendários, lembretes, automações, OAuth, Google/Microsoft/GitHub/Home Assistant, mobile, ESP32-S3, OCR, embeddings, banco vetorial e providers externos.

## Limitações

- Sem streaming visual de tokens e sem botão funcional de parar geração.
- Editor de persona usa Markdown; o formulário estruturado completo ainda será refinado.
- Sem autenticação ou criptografia do SQLite; a API deve permanecer em localhost.
- Parser de documentos roda no processo da API e ainda não tem fila de jobs.
- Cobertura frontend automatizada e CRUD visual de edição precisam ser ampliados.

## Próximas cinco prioridades

1. Streaming de chat e cancelamento de geração.
2. Testes de integração do AgentController com respostas simuladas do Ollama e testes de componentes React.
3. CRUD visual completo de memória, tarefas e conversas.
4. Processamento assíncrono de biblioteca, citações por página/localização e melhor ranking FTS5.
5. Editor de personalidade estruturado com campos, presets e prévia lado a lado.

## Comandos

```powershell
# iniciar tudo
.\start.ps1

# parar os processos iniciados pelo script
.\stop.ps1

# checar Ollama e GPU durante inferência
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" ps
nvidia-smi
```

Aplicação: `http://127.0.0.1:5173`  
API: `http://127.0.0.1:8000/docs`

