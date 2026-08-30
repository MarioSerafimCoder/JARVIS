# Relatório de consolidação do cérebro local

Data: 29/08/2026

## Resultado

A Fase 1.5 consolida o Jarvis como aplicativo local utilizável, testado e empacotado para Windows. A IA permanece no computador, usa `qwen3.5:4b` pelo Ollama e não depende de API paga.

## Atualização - Fase 2 Intelligence Engine (30/08/2026)

- agent loop persistido com até cinco ciclos, pausa e retomada do mesmo `agent_run_id` após confirmação;
- serviços centrais compartilhados entre API e tools, com validação Pydantic;
- Memory Engine 2.0 com tipos, estados, candidatos, deduplicação, conflitos, supersessão e invalidação de relações;
- embeddings multilíngues locais opcionais e ranking híbrido FTS5 + similaridade + importância + recência;
- resumo incremental de conversa, feedback por mensagem e seção Aprendizado;
- Context Builder 3.0 sem corte arbitrário de itens;
- Cognitive Core com estatísticas separadas, substrato visual não contabilizado, ferramentas periféricas e cena persistente;
- rotas reais, command palette navegável, briefing Agora, Action Cards, Markdown seguro, Configurações estruturadas e onboarding local;
- biblioteca com tags, descrição, coleção, controle de RAG e processamento em segundo plano;
- health status separado para app, Ollama, modelo e eventos cognitivos.

## Atualização - Fase 3 Voice Engine (30/08/2026)

- 28 referências autorizadas detectadas, copiadas para dados privados, analisadas e fingerprintadas;
- contratos STT/VAD/TTS/profile/session desacoplados do AgentController;
- worker localhost isolado para faster-whisper small e XTTS-v2, sem dependências pesadas no backend principal;
- perfil persistente por conditioning latents/embedding, estado OUTDATED e proibição de voz genérica silenciosa;
- normalização de texto falado, sentence chunking, cache determinístico LRU e estilos de entrega com um único speaker;
- WebSocket bidirecional, turn manager, barge-in, descarte de áudio bruto e confirmação inequívoca por voz/visual;
- Chat com Conversar, transcript, fallback push-to-talk e controles essenciais;
- Voice Lab em Personalidade com perfil, dispositivos, testes e configurações locais;
- migrations, backup vocal opcional, relatório de referências, arquitetura e benchmark honesto;
- 50 testes backend e 16 frontend aprovados; build Vite com 1.685 módulos.

O provider real não foi marcado como pronto: XTTS-v2 exige aceitação explícita da licença CPML não comercial e os modelos ainda não estão instalados. Até essa decisão, a interface informa indisponibilidade e mantém o chat textual.

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

- backend: 34 testes aprovados, incluindo multi-tool, limite do loop, pausa/retomada, candidatos, deduplicação, supersessão, busca híbrida, fallback, resumo, feedback, invalidação e estatísticas;
- frontend: 15 testes de componentes/cliente aprovados, incluindo navegação da command palette e rotas;
- TypeScript e build Vite aprovados, com 1.683 módulos transformados;
- executável validado em execução real: interface HTTP 200, `/api/health` saudável e modelo disponível;
- streaming real validado no navegador com resposta do `qwen3.5:4b`;
- pacote final: `release/JarvisLocal-Windows.zip`, aproximadamente 41,11 MB.

## Funcionalidades deliberadamente fora do escopo

Wake word, calendários reais, automações, OAuth, Google/Microsoft/GitHub/Home Assistant, mobile, ESP32-S3, OCR, banco vetorial externo, LoRA e providers pagos continuam reservados para fases futuras.

## Limitações conhecidas

- o Ollama e o modelo `qwen3.5:4b` precisam estar instalados na máquina;
- a indexação usa job local em segundo plano, sem Redis/Celery; fechar o processo interrompe jobs ativos;
- o SQLite não é criptografado; a aplicação deve permanecer restrita ao computador local;
- embeddings são opcionais; sem o modelo local em cache o sistema usa FTS5. OCR continua indisponível.
