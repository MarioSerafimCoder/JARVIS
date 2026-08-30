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

Consulte `VOICE_REFERENCE_REPORT.md` para o resultado por arquivo. O ambiente isolado decodificou os 28 MP3, mediu silêncio, pico e clipping sem alterar os originais: todos ficaram em `GOOD`, sem clipping aparente.

## Escolha inicial

`faster-whisper small` multilíngue em CPU int8 é o padrão inicial: prioriza português e evita concorrer pelos 8 GB de VRAM usados pelo Qwen e pelo XTTS. O modelo medium fica disponível para comparação posterior, mas não é escolhido sem medir latência e memória.

O XTTS deve usar GPU de forma sequencial. AUTO/LOW_VRAM descarregam TTS após inatividade; Qwen não é descarregado a cada turno.

## Ativação real

- PyTorch 2.8.0 + CUDA 12.8 reconheceu a NVIDIA GeForce RTX 5050;
- faster-whisper 1.2.1 e XTTS-v2 foram baixados para dados locais;
- Transformers foi fixado em 4.57.3 por compatibilidade com XTTS;
- perfil `Jarvis` construído com 28 referências, 104,384 s e fingerprint `963aee7bfdf8ee240ec6456568ad827111bbac8cdcf3a3867a777521dd625703`;
- artefato persistente: `conditioning.pt`;
- modelos locais: aproximadamente 2,20 GB, sem contar o ambiente PyTorch isolado.

## Síntese XTTS-v2 real

Medições em localhost, após descarregar os modelos. `RTF` menor que 1 significa geração mais rápida que a duração do áudio.

| Caso | Estado | Tempo total | Geração | Áudio | RTF | VRAM observada |
|---|---|---:|---:|---:|---:|---:|
| Frase curta | cold | 15,416 s | 1,026 s | 1,291 s | 0,795 | 2.576 MiB |
| Frase média | warm | 5,080 s | 5,044 s | 7,051 s | 0,715 | 2.834 MiB |
| Confirmação | warm | 3,363 s | 3,352 s | 4,640 s | 0,722 | 2.832 MiB |
| Aviso | warm | 3,091 s | 3,081 s | 4,267 s | 0,722 | 2.834 MiB |

VRAM antes do carregamento cold: 745 MiB. O cold total inclui aproximadamente 14 s de carregamento do XTTS; a geração warm ficou abaixo do tempo de reprodução nos quatro casos.

## STT real e round-trip

A frase sintetizada “Olá, senhor. O sistema de voz local do Jarvis está funcionando corretamente.” gerou 6,219 s de áudio. O faster-whisper retornou “Olá senhor, o sistema de voz local do Jarvis está funcionando corretamente.”

| Estado | Tempo total | Processamento reportado |
|---|---:|---:|
| cold | 3,429 s | 3,418 s |
| warm | 2,254 s | 2,250 s |

## O que permanece interativo

Os providers fake continuam cobrindo deterministicamente cache, chunking, confirmação, interrupção e estados. A permissão física do microfone, a audição subjetiva e o gesto de barge-in durante playback precisam ser confirmados pelo usuário no navegador. A medição conjunta de Qwen + Whisper + XTTS e dez frases consecutivas fica reservada ao benchmark de uso prolongado, pois depende do modelo Ollama estar carregado simultaneamente.
