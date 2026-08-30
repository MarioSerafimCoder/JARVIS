# Segurança da Web

## SSRF e rede

`WebURLPolicy` aceita somente HTTP/HTTPS, resolve o host antes da requisição e bloqueia loopback, redes privadas, link-local, multicast, endereços reservados, hosts `.local`/`.internal`/`.lan` e endpoints de metadados. Redirecionamentos são manuais e cada salto passa pela mesma validação. `file:`, FTP, credenciais embutidas e caminhos locais não são aceitos.

O cliente HTTP não herda proxies do ambiente, limita tempo, redirecionamentos, bytes e tipos de conteúdo. A resposta entregue ao modelo contém texto extraído, não HTML bruto ilimitado.

## Privacidade e prompt injection

`WebQuerySanitizer` remove e registra e-mail, telefone, CPF, segredos aparentes e caminhos locais. A instrução de sistema proíbe enviar memórias, conversas e documentos. O log guarda a consulta sanitizada e metadados da fonte, nunca cookies, tokens ou credenciais.

Texto de páginas é marcado como não confiável e só pode ser evidência. Instruções presentes em página, título, anúncio ou descrição não alteram políticas, ferramentas ou memória. O modelo nunca recebe uma primitiva de shell, JavaScript livre ou rede direta.

Os testes cobrem URLs locais, esquemas proibidos, redirecionamento malicioso, sanitização, deduplicação, proveniência e modos OFF/ASK/ON com provider/fetcher falsos.

