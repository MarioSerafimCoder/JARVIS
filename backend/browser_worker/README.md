# Jarvis Browser Worker

Processo local isolado que controla somente um perfil persistente dedicado do Microsoft Edge via Playwright. O modelo local nunca recebe cookies, localStorage ou credenciais. Login, 2FA e CAPTCHA são concluídos pelo usuário na janela visível.

Execute `setup-browser.ps1` uma vez e `start-browser.ps1` quando quiser habilitar o Browser Agent.

O worker não expõe JavaScript livre, upload, download, clipboard, checkout ou finalização de compra.

