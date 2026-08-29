# Segurança

## Fronteiras

- O servidor escuta apenas em `127.0.0.1` nos scripts fornecidos.
- O modelo só pode solicitar ferramentas registradas; não existe ferramenta de PowerShell, CMD, bash ou execução arbitrária.
- Ferramentas DANGEROUS são bloqueadas. Escritas feitas pelo modelo usam CONFIRM e só rodam após aprovação explícita.
- Cada execução gera resultado verificável e registro em `activity_log`. Proposta, execução e fala são estados distintos.
- Uploads aceitam somente PDF, DOCX, TXT e MD, até 20 MB. O nome é validado e o arquivo recebe nome interno aleatório.
- Caminhos são resolvidos e precisam permanecer dentro de `data/library/`, protegendo contra directory traversal.
- O banco, documentos, `.env`, credenciais e logs privados estão no `.gitignore`.
- Não há telemetria, analytics, crash reporting cloud ou API paga.

## Limitações conhecidas

Esta fase é para uso local de um único usuário. Ainda não há autenticação, criptografia do banco em repouso, sandbox de parsers, antivírus de uploads ou autenticação de dispositivos. Não exponha a porta 8000 na rede ou internet. Integrações futuras deverão armazenar segredos no cofre do sistema operacional, nunca no repositório.

