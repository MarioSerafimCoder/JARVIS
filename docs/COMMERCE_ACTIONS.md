# Ações de Comércio

| Ação | Risco | Comportamento |
|---|---|---|
| Pesquisar produtos | SAFE | Retorna candidatos persistidos |
| Ler produto | SAFE | Atualiza dados atuais |
| Ler carrinho | SAFE | Retorna snapshot verificado |
| Adicionar ao carrinho | CONFIRM | Revalida preço/variante e verifica carrinho |
| Remover do carrinho | CONFIRM | Verifica ausência após remoção |
| Alterar quantidade | CONFIRM | Verifica quantidade selecionada |
| Checkout/finalizar pedido | INDISPONÍVEL | Não existe ferramenta ou endpoint |

O card de confirmação mostra a ação, candidato e preço esperado. A confirmação retoma o mesmo fluxo persistido. Respostas especiais: `PRICE_CHANGED`, `VARIANT_UNAVAILABLE`, `AUTH_REQUIRED`, `CAPTCHA_REQUIRED`, `UNAVAILABLE` e `UNKNOWN`. Nenhuma delas é apresentada como sucesso verificado.

Confirmação por voz usa o mesmo `pending_action` do chat; não existe caminho privilegiado para voz.

