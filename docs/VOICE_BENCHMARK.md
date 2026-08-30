# Benchmark do Voice Engine

Data: 30/08/2026

## Hardware observado

| Recurso | Valor |
|---|---|
| CPU | Intel Core i5-9400F, 6 cores / 6 threads |
| RAM | 31,9 GB |
| GPU | NVIDIA GeForce RTX 5050, 8.151 MiB |
| VRAM ocupada no baseline | 718 MiB |
| Driver | 610.88 |

## Referências reais

| Medida | Resultado |
|---|---:|
| Arquivos autorizados | 28 MP3 mono |
| Duração total medida | 104,38 s |
| Sample rate | 44.100 Hz |
| Tamanho total | 1.670.126 bytes |
| Análise/fingerprint warm | 0,708 s |

Consulte `VOICE_REFERENCE_REPORT.md` para o resultado por arquivo. Como FFmpeg/PyAV ainda não está instalado no ambiente principal, silêncio, pico e clipping de MP3 permanecem como `n/d`; o Voice Worker completa a decodificação sem alterar os originais.

## Escolha inicial

`faster-whisper small` multilíngue em CPU int8 é o padrão inicial: prioriza português e evita concorrer pelos 8 GB de VRAM usados pelo Qwen e pelo XTTS. O modelo medium fica disponível para comparação posterior, mas não é escolhido sem medir latência e memória.

O XTTS deve usar GPU de forma sequencial. AUTO/LOW_VRAM descarregam TTS após inatividade; Qwen não é descarregado a cada turno.

## Estado do benchmark ponta a ponta

Os providers fake validaram, de modo determinístico, fluxo, cache, chunking, confirmação, interrupção e estados. Não são apresentados como números de desempenho real.

O benchmark real de STT/TTS está pendente porque os modelos ainda não foram instalados e a licença CPML não foi aceita pelo usuário. Portanto não há números inventados para:

- fim da fala -> transcript;
- transcript -> primeiro token Qwen;
- primeiro token -> primeiro áudio;
- pico de RAM/VRAM com Whisper + Qwen + XTTS;
- cold versus warm;
- dez frases com o mesmo `conditioning.pt`.

Depois da ativação explícita, executar as frases curta, média, com tool e com interrupção descritas no prompt, com o Cognitive Core aberto e fechado, e registrar os resultados nesta página.
