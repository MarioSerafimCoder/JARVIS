# Segurança do Browser Agent

- Perfil persistente exclusivo; o navegador pessoal não é reutilizado.
- Worker acessível apenas em `127.0.0.1:8767`.
- Navegação principal limitada a `https://amazon.com.br` e `https://amazon.com`.
- Sem `execute_js`, `eval`, clique genérico, upload, download, clipboard ou acesso a arquivos.
- Sem checkout, finalizar pedido, pagamento ou salvar credenciais.
- Login, 2FA e CAPTCHA são sempre manuais; não há bypass.
- Cookies, localStorage, senha e tokens nunca saem do worker.
- Títulos e descrições de site são dados não confiáveis, não instruções.
- Mudança de preço retorna `PRICE_CHANGED`; a ação para sem adicionar.
- Adição só retorna sucesso depois de verificar produto, quantidade e variante no carrinho. Se a verificação falhar, retorna `UNKNOWN`.
- Atividade registra `BROWSER ACTION` sem credenciais.

Testes usam comércio falso para login, busca, produto, carrinho, preço, variante, quantidade, cancelamento, prompt injection e redirecionamento. CI nunca acessa Amazon real e nunca finaliza compra.

