# Site Adapters

`SiteAdapterRegistry` impede que o modelo controle páginas arbitrárias. Cada adaptador publica somente operações de domínio conhecidas.

## Amazon

Domínios: `amazon.com.br`, `www.amazon.com.br`, `amazon.com`, `www.amazon.com`.

Operações: pesquisar produtos, ler produto, ler carrinho, adicionar, remover e alterar quantidade. `ProductCandidate` persiste ID opaco, título, preço observado, vendedor, avaliação, número de reviews, entrega, Prime, disponibilidade, URL, site e variante. A URL é validada novamente antes de toda navegação.

Para adicionar outro site, implemente a interface semântica, defina allowlist de domínios, seletores por ARIA/nome/rótulo, estados de autenticação/CAPTCHA e testes falsos antes do registro. Não exponha locators ou cliques genéricos ao modelo.

