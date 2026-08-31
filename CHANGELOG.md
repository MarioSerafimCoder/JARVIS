# Changelog

## 2026-08-30 — Fase 3.1 Hardening

- Proteção do Browser Worker com bearer interno efêmero de 256 bits, localhost, perfil fixo, fila serial e estados explícitos.
- Candidatos de produto com TTL de 15 minutos, ASIN/canonical URL e dinheiro decimal estruturado; checkout continua inexistente.
- Fila FIFO real de áudio no navegador, acknowledgements de playback e barge-in que cancela geração/fila/reprodução.
- Streaming do agente sem exposição de texto intermediário de tool turns e cancelamento parcial persistido corretamente.
- Proveniência web encadeada, recência aplicada e correção de `completed_at` ao reabrir tarefas.
- Context Builder com orçamento integral e prioridades P0–P3; Conversation State estruturado e Memory Engine 2.1 híbrido.
- Ferramentas executadas de modo assíncrono com timeout, cancelamento e auditoria.
- SQLite em WAL/NORMAL, `busy_timeout=5000`, migrações explícitas 001–007 e testes concorrentes.
- Providers globais para Cognitive SSE e Voice Session, Markdown GFM seguro e Action Cards com metadados de domínio.
- Persona padrão v2 com preservação, comparação e atualização explícita de personalizações.
- CI para Windows/Linux, Ruff, cobertura mínima de 65%, testes frontend e build de produção.
