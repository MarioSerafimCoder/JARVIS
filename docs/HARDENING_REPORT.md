# Relatório final — Fase 3.1 Hardening

## Status geral

Concluído para o escopo implementável e automatizável localmente. O sistema inicia, responde com o modelo real e preserva o modo offline. Nenhum push remoto, integração nova, shell para o modelo ou checkout foi adicionado.

## Implementado e corrigido

- Browser Worker autenticado por segredo efêmero, restrito a localhost, perfil dedicado fixo e operações serializadas.
- Pré-flight de sessão, domínio, autenticação e CAPTCHA; estados `AUTH_REQUIRED`, `CAPTCHA_REQUIRED`, `PRICE_CHANGED`, `VARIANT_UNAVAILABLE`, `STALE_CANDIDATE`, `UNKNOWN`, `UNAVAILABLE` e `FAILED`.
- Identidade Amazon por ASIN, fallback de título marcado como baixa confiança, TTL de candidato e dinheiro com `Decimal`.
- Fila de áudio FIFO no browser e protocolo `playback_started`, `playback_finished` e `playback_interrupted`; o estado cognitivo acompanha o playback confirmado.
- Voice Session global, sem wake word, com cancelamento de reprodução, fila e geração no barge-in.
- Agent loop mostra somente o último turno sem tool call; turnos intermediários ficam internos. Cancelamento parcial persiste `generation_status=cancelled` e run cancelado.
- Proveniência `source_id`/`page_fetch_id` vinculada, `published_at` separado de `retrieved_at` e filtro real de recência.
- Contexto contabilizado antes da seleção, itens inteiros, prioridades P0–P3 e estado estruturado de conversa com fallback.
- Memory Engine 2.1 com regras conservadoras, extração JSON pelo modelo local quando há sinal durável, dedupe semântico local e fallback lexical; nada é salvo sem confirmação.
- Tools assíncronas com timeout, propagação de cancelamento, erro estruturado e auditoria.
- Migrações ordenadas 001–007, WAL, synchronous NORMAL, busy timeout e preservação de dados.
- CognitiveProvider global com uma SSE, backoff e cleanup; Markdown `react-markdown` + GFM com HTML bruto ignorado; Action Cards recebem metadados do domínio.
- Persona v2 e fluxo comparar/atualizar/manter, com política de segurança fora do texto editável.
- CI, lint, baseline de cobertura e documentação atualizada.

## Validação

- 71 testes backend aprovados; cobertura 67,25% com baseline CI de 65%; Ruff aprovado.
- 19 testes frontend aprovados; TypeScript/Vite aprovado com 1.940 módulos.
- Smoke real: health HTTP 200, Ollama e `qwen3.5:4b` disponíveis, chat aquecido HTTP 200 em 0,620 s.
- Concorrência SQLite, migrações idempotentes, autenticação do worker e sequência de áudio possuem testes dedicados.

## Limitações verificadas

- Browser Worker e Voice Worker estavam desligados no smoke final. Seus testes determinísticos passaram, mas login Amazon, 2FA, CAPTCHA, microfone físico e audição subjetiva continuam validações manuais.
- O refactor dos arquivos grandes foi gradual: providers e serviços críticos foram extraídos, porém `DomainPages.tsx` e `styles.css` ainda podem ser subdivididos sem urgência funcional.
- Binário WebSocket para TTS permanece opcional; o transporte base64 existente foi mantido para compatibilidade.
- Embeddings dependem do modelo local já presente no cache; na ausência dele, o fallback lexical/FTS5 é explícito.
