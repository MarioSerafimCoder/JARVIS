# Web Intelligence

## Escopo

Web Intelligence é uma capacidade de pesquisa e leitura pública separada do Browser Agent. O Qwen não abre sockets, não recebe um cliente HTTP e não escolhe redirecionamentos: ele só pode solicitar `web_search` e `web_read` pelo Tool Registry.

Fluxo: `Qwen -> AgentController -> ToolRegistry -> política OFF/ASK/ON -> WebIntelligenceService -> resultado verificado -> AgentController -> resposta + fontes`.

`DefaultWebSearchProvider` usa o feed RSS público do Bing sem chave ou serviço pago. A interface `WebSearchProvider` permite substituir por SearXNG ou Brave sem alterar o agente. `WebSearchService` sanitiza a consulta, limita resultados/domínios, remove duplicatas e adiciona proveniência. `WebPageFetcher` lê apenas HTML/texto público, extrai conteúdo principal e limita tamanho.

Cada fonte possui `source_id`, título, URL, domínio, data de publicação quando disponível, data de recuperação e excerto. A evidência fica em `messages.context_json` e `web_sources`; ela aparece nos cards da resposta e no Inspetor de contexto.

Conteúdo web nunca é salvo automaticamente como memória. O aviso `UNTRUSTED WEB CONTENT` faz parte do contexto do agente e do resultado de leitura.

## Modos

- `OFF`: as ferramentas são bloqueadas.
- `ASK` (padrão): cada acesso gera confirmação humana e retoma o mesmo `agent_run_id`.
- `ON`: busca e leitura públicas podem executar como ações SAFE.

Estados cognitivos: `SEARCHING_WEB` durante pesquisa e `BROWSING` durante leitura.

## Medições locais

Em 30/08/2026, a busca real de três resultados no domínio `openai.com` levou aproximadamente 1,05 s; a leitura de `example.com` levou aproximadamente 0,58 s. São medições de uma única execução e variam com a rede.

