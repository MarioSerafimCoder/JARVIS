# Fase 2 - Intelligence Engine

O Intelligence Engine transforma o Jarvis em um agente local iterativo. A inteligência desta fase vem de mecanismos persistidos e verificáveis: agent runs, memórias candidatas, deduplicação, supersessão, resumo de conversa, feedback e recuperação híbrida. Nenhuma API paga ou integração cloud foi adicionada.

## Agent loop controlado

Cada solicitação cria um `agent_run_id`. O ciclo executa no máximo cinco iterações:

```text
LLM -> tool call -> política -> execução -> resultado verificado -> LLM -> ... -> resposta
```

`agent_runs` persiste estado, mensagens operacionais, contexto e contador. `agent_run_steps` registra apenas ações, resultados, evidências e estados observáveis; chain-of-thought não é coletado. Os estados são `running`, `waiting_confirmation`, `completed`, `failed` e `cancelled`.

Ao encontrar uma ferramenta `CONFIRM`, o run é pausado. A ação pendente guarda o mesmo `agent_run_id`; depois da confirmação o resultado verificado é anexado ao histórico operacional e o mesmo run continua, inclusive podendo escolher outra ferramenta. `DANGEROUS` continua bloqueado.

## Serviços de domínio

API e Tool Registry compartilham `MemoryService`, `TaskService`, `KnowledgeService` e `ConversationService`. Os modelos Pydantic em `services/schemas.py` validam categorias, tipos, prioridades, estados, importância, confiança e datas antes de qualquer escrita.

## Memory Engine 2.0

As categorias antigas foram preservadas e migradas para tipos adicionais: `semantic`, `preference`, `episodic`, `procedural`, `person`, `project` e `decision`. Uma memória pode estar `candidate`, `active`, `superseded` ou `archived`.

O `MemoryConsolidator` usa regras locais conservadoras para propor informações úteis. Ele cria candidatos e nunca salva automaticamente. A interface oferece Ignorar, Editar e Salvar. Antes da persistência, o serviço classifica a informação como nova, duplicada, semelhante ou conflitante. Uma atualização cria `supersedes_id` e mantém a memória anterior como histórico.

Editar, arquivar, substituir ou excluir uma memória invalida suas relações persistidas. O Context Builder e o Cognitive Core usam apenas memórias ativas por padrão.

## Embeddings locais e fallback

O provider abstrato é `EmbeddingProvider`. O provider opcional escolhido é `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`: multilíngue, 118 milhões de parâmetros, adequado a português, aproximadamente 470 MB em FP32 e cerca de 0,7-1,2 GB de RAM em execução CPU. VRAM não é obrigatória. Ele só carrega arquivos já presentes no cache local e nunca baixa um modelo durante uma conversa.

Instalação opcional:

```powershell
cd backend
.\.venv\Scripts\pip.exe install -r requirements-embeddings.txt
```

Sem o pacote ou sem o modelo em cache, o status é `fallback_fts5` e o Jarvis continua funcional. Os testes usam um provider local controlado para validar a camada semântica sem rede.

O ranking híbrido usa:

| Sinal | Peso |
| --- | ---: |
| FTS5 / correspondência lexical | 0,50 |
| similaridade de embedding | 0,30 |
| importância | 0,12 |
| recência | 0,08 |

FTS5 nunca é substituído.

## Conversa e aprendizado

A cada seis mensagens elegíveis, `ConversationService` atualiza um resumo incremental local. O Context Builder 3.0 seleciona itens inteiros pelo orçamento, priorizando persona, mensagem atual, resumo, conversa recente, memórias ativas, documentos habilitados e tarefas.

Cada resposta aceita avaliação positiva ou negativa e uma correção opcional. A seção Aprendizado lê `message_feedback`. Esses dados não disparam fine-tuning ou LoRA nesta fase.

## Cognitive Core

As estatísticas separam `memory_relationships`, `structural_connections` e `tool_connections`. Ferramentas ficam em órbita periférica; suas conexões são discretas e ocultas no mapa compacto. O `Cognitive Substrate` é uma camada procedural puramente visual e nunca entra nas contagens.

O renderer mantém a cena Three.js entre mudanças de estado, seleção e destaque. Materiais, cores, matrizes de instâncias e alvo da câmera são atualizados incrementalmente.

## Interface e dados

- rotas reais com back/forward: `/now`, `/chat/:id`, `/cognitive`, `/memory/:id`, `/library/:id`, `/tasks/:id`, `/personality` e `/settings`;
- command palette abre a entidade selecionada;
- Agora é um briefing baseado em tarefas, confirmações, candidatos e atividade reais;
- Markdown seguro é renderizado sem `dangerouslySetInnerHTML`;
- confirmações usam Action Cards humanizados, com JSON apenas em Ver detalhes;
- Configurações usa componentes por seção, sem editor de JSON;
- o onboarding verifica app, Ollama, Qwen e GPU, registra o nome local, configura memória e permite importar documentos;
- parsing de documentos roda como `BackgroundTasks`, sem Redis ou Celery;
- instalações antigas são apenas detectadas e oferecidas para revisão; nada é copiado sem autorização.

## Fora do escopo

Voz, STT, TTS, wake word, Google, Gmail, calendário externo, Home Assistant, mobile, ESP32, APIs pagas, OCR e LoRA continuam não implementados.
