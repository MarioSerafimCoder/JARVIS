# Benchmark — Fase 3.1 Hardening

Medição local em 30/08/2026 no hardware descrito em `SYSTEM_REPORT.md`. Não são números estimados.

| Verificação | Resultado |
|---|---:|
| Backend pytest | 71 aprovados |
| Cobertura backend | 67,25% (baseline CI: 65%) |
| Frontend Vitest | 19 aprovados |
| Build Vite/TypeScript | 1.940 módulos; aprovado |
| Ruff | aprovado |
| Health completo do backend | HTTP 200; 2,508 s |
| Ollama `/api/tags` | 27 ms; `qwen3.5:4b` disponível |
| Chat real aquecido, resposta “OK” | HTTP 200; 0,620 s |
| Asset HTML de produção pelo backend | HTTP 200; 0,114 s |

O Voice Worker e o Browser Worker não estavam ativos durante o smoke final. O health os reportou honestamente como `unavailable/offline`; o chat textual, Ollama e a interface permaneceram operacionais. O smoke autenticado da Amazon continua manual e não foi marcado como concluído.
