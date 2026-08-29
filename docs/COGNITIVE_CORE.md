# Cognitive Core

O Cognitive Core é a representação visual oficial da memória, do conhecimento e do estado operacional do Jarvis. Ele não simula atividade: cada nó, relação, destaque e mudança de estado deriva de dados ou eventos reais do sistema.

## Fluxo de dados

```text
SQLite + ToolRegistry
        ↓
CognitiveGraphService
        ↓
GET /api/cognitive-graph
        ↓
Three.js (InstancedMesh + LineSegments + Points)

AgentController + ToolExecutor + ContextBuilder
        ↓
CognitiveStateService / CognitiveEvent
        ↓ SSE
GET /api/cognitive-events
        ↓
destaques e estados efêmeros na interface
```

## Entidades visuais

- `core:jarvis`: núcleo abstrato central;
- `memory:*`: memórias agrupadas em projects, people, preferences, routine, facts, instructions, decisions e other;
- `document:*`: um nó por documento, nunca um nó permanente por chunk;
- `task:*`: tarefas abertas na órbita operations;
- `tool:*`: ferramentas registradas na periferia tools.

Os identificadores e metadados vêm diretamente do banco e do registro de ferramentas. Quando não há memórias, documentos ou tarefas, o mapa mostra honestamente apenas o núcleo e as ferramentas existentes.

## Relações

`GraphRelationshipProvider` define o contrato. A versão ativa, `DeterministicRelationshipProvider`, usa:

- termos normalizados compartilhados;
- categoria comum como reforço, nunca como justificativa única;
- mesma referência de origem;
- coocorrência apenas quando memórias foram realmente selecionadas juntas pelo ContextBuilder.

Cada relação contém `type`, `weight` e `evidence`. O grau é limitado a quatro relações significativas por memória. `EmbeddingRelationshipProvider` existe somente como contrato futuro e lança `NotImplementedError` nesta fase.

## Layout e performance

As posições usam SHA-256 do identificador e centros fixos de cluster. Assim, o mesmo nó retorna aproximadamente ao mesmo lugar entre sessões sem gravar coordenadas arbitrárias.

O renderer usa uma malha instanciada para nós, `LineSegments` para relações e `Points` derivados das posições reais. Os níveis AUTO/HIGH/MEDIUM/LOW limitam geometria e pixel ratio; AUTO reduz custo quando a taxa de quadros cai. Se WebGL falhar, um SVG 2D acessível preserva o mapa e a seleção.

Benchmark controlado em 29/08/2026:

| Memórias | Relações | Geração do grafo |
|---:|---:|---:|
| 100 | 0 | 0,006 s |
| 1.000 | 920 | 0,057 s |
| 5.000 | 9.240 | 0,856 s |

O caso de 100 itens não formou relações porque o dataset controlado não continha termos específicos repetidos; o sistema não inventou conexões para preencher a tela.

## Estados e eventos

Estados ativos: IDLE, THINKING, SEARCHING_MEMORY, SEARCHING_KNOWLEDGE, USING_TOOL, WAITING_CONFIRMATION e ERROR. LISTENING e SPEAKING estão tipados, porém não são ativados.

Eventos: MEMORY_RETRIEVED, MEMORY_CREATED, DOCUMENT_RETRIEVED, TOOL_REQUESTED, TOOL_EXECUTED, TOOL_FAILED, GENERATION_STARTED, GENERATION_FINISHED, ERROR, GRAPH_CHANGED e CONTEXT_SELECTED.

Esses eventos registram transições e entidades envolvidas; nenhum conteúdo de chain-of-thought é produzido ou transmitido.

## API

- `GET /api/cognitive-graph`: nodes, edges, clusters, state e stats;
- `GET /api/cognitive-state`: estado atual e último id de evento;
- `GET /api/cognitive-events`: stream SSE com retomada por `Last-Event-ID`.

## Limites desta fase

Não inclui embeddings, vector database, LoRA, STT, TTS, wake word, Bluetooth, ESP32 ou integrações cloud. Memória, Biblioteca, Tarefas e Busca continuam sendo formas textuais completas de acesso aos mesmos dados.
