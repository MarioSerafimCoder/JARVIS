# Relatório de consolidação do cérebro local

Data: 29/08/2026

## Resultado

A Fase 1.5 consolida o Jarvis como aplicativo local utilizável, testado e empacotado para Windows. A IA permanece no computador, usa `qwen3.5:4b` pelo Ollama e não depende de API paga.

## Entregas principais

- streaming de chat via SSE, atualização incremental, botão de parar, nova tentativa, cópia e timestamps;
- persistência de resposta parcial como `cancelled` quando a geração é interrompida;
- confirmação de ferramentas com estados explícitos e resposta final do modelo baseada no resultado executado;
- `ConversationContextRetriever`, `MemoryRetriever`, `KnowledgeRetriever` e `TaskContextRetriever` coordenados pelo `ContextBuilder`;
- ranking FTS5 leve, orçamento configurável de contexto e atualização seletiva de `last_used_at`;
- aviso de conteúdo não confiável para impedir que instruções encontradas em documentos sejam tratadas como comandos;
- localização de evidências por página de PDF, parágrafo de DOCX e linhas de TXT/Markdown;
- APIs separadas de chat, conversas, ferramentas, backup e domínios;
- migrações aditivas simples e versão de esquema no SQLite;
- CRUD visual de conversas, memórias e tarefas, exclusão de documentos, filtros, auditoria detalhada e backup;
- frontend modular e tipado, sem `Record<string, any>`;
- executável Windows onedir, com interface e servidor local no mesmo pacote.
- Cognitive Core 3D com grafo real, eventos cognitivos, layout estável, relações justificadas e fallback acessível.

## Segurança e privacidade

- binding exclusivo em localhost;
- nenhuma telemetria ou integração externa ativada;
- o modelo não recebe shell nem caminho arbitrário;
- uploads limitados e armazenados com nome interno seguro;
- ferramentas desconhecidas ou perigosas permanecem bloqueadas;
- dados, persona, biblioteca e backups persistem ao lado do executável.

## Validação

- backend: 27 testes aprovados;
- frontend: 10 testes de componentes/cliente aprovados;
- TypeScript e build Vite aprovados, com 1.674 módulos transformados;
- executável validado em execução real: interface HTTP 200, `/api/health` saudável e modelo disponível;
- streaming real validado no navegador com resposta do `qwen3.5:4b`;
- pacote final: `release/JarvisLocal-Windows.zip`, aproximadamente 41,11 MB.

## Funcionalidades deliberadamente fora do escopo

Voz, wake word, calendários reais, automações, OAuth, Google/Microsoft/GitHub/Home Assistant, mobile, ESP32-S3, OCR, embeddings, banco vetorial e providers pagos continuam reservados para fases futuras.

## Limitações conhecidas

- o Ollama e o modelo `qwen3.5:4b` precisam estar instalados na máquina;
- a indexação de documentos ainda ocorre no processo da API, sem fila de jobs;
- o SQLite não é criptografado; a aplicação deve permanecer restrita ao computador local;
- a versão atual usa FTS5, sem embeddings ou OCR.
