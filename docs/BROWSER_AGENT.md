# Browser Agent

## Arquitetura

O Browser Agent é separado de Web Intelligence e do processo principal:

`Qwen -> AgentController -> ferramenta semântica -> BrowserPolicy -> SiteAdapter -> Browser Worker (localhost:8767) -> Playwright/Edge -> verificação`.

Componentes: `BrowserAgent`, `BrowserSessionManager`, `BrowserProfileManager`, `BrowserPolicy`, `SiteAdapterRegistry`, `AmazonSiteAdapter` e o Browser Worker isolado.

## Conexão

Em **Conexões -> Amazon -> Conectar**, o worker abre uma janela visível usando apenas o perfil `data/browser/profiles/jarvis`. O usuário faz login, senha, 2FA e CAPTCHA diretamente nessa janela e depois escolhe **Verificar conexão**. O backend armazena apenas site, estado, capacidades e datas; cookies/localStorage permanecem no perfil e nunca entram no Qwen.

O Browser Access nasce `OFF`. Depois de conectar, o usuário pode ativá-lo em Configurações. Pesquisa/leitura são SAFE; mudanças de carrinho continuam CONFIRM.

## Estado real

O worker e o adaptador Amazon estão implementados e executáveis. A saúde do worker foi validada localmente com Playwright 1.55 e Edge existente. O smoke test autenticado na Amazon não foi executado porque exige login manual do usuário. Seletores podem exigir manutenção quando a Amazon alterar a interface; nenhuma capacidade é declarada conectada antes dessa validação.

