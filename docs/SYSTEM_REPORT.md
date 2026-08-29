# Relatório do sistema

Levantamento realizado em 29/08/2026 antes da criação do projeto. Os valores abaixo foram detectados no computador; não são estimativas de catálogo.

## Hardware

| Item | Resultado |
| --- | --- |
| Sistema | Microsoft Windows 11 Pro, versão 10.0.26200, build 26200 |
| CPU | Intel Core i5-9400F @ 2.90 GHz, 6 núcleos / 6 threads |
| RAM | 31,94 GB; 23,56 GB livres antes do benchmark |
| GPU | NVIDIA GeForce RTX 5050 |
| VRAM | 8.151 MiB; 7.221 MiB livres antes do benchmark |
| Disco C: | 464,86 GB totais; 206,84 GB livres antes das instalações |
| Driver NVIDIA | 610.88 |
| CUDA | runtime UMD 13.3 informado por `nvidia-smi`; toolkit `nvcc` não instalado |

## Ambiente

| Ferramenta | Resultado |
| --- | --- |
| Python | 3.12.5 em `C:\Python312\python.exe` |
| Node.js | 24.18.0 |
| npm | 11.16.0 |
| Git | 2.55.0.windows.5 |
| Ollama | 0.33.2, instalado oficialmente pelo winget |

Python 3.12 atende ao requisito 3.11+. O toolkit CUDA completo não é necessário para o Ollama: a aceleração foi validada com o runtime do driver NVIDIA.

## Modelo e benchmark

| Métrica | Resultado |
| --- | --- |
| Modelo | `qwen3.5:4b` |
| Arquitetura / parâmetros | qwen35 / 4,7B |
| Quantização | Q4_K_M |
| Tamanho local | 3,4 GB |
| Contexto nativo informado | 262.144 tokens |
| Contexto adotado pelo Jarvis | 8.192 tokens |
| Tempo total da primeira inferência | 154,45 s |
| Carga inicial do modelo | 51,05 s |
| Prompt | 40 tokens, 1,05 token/s na primeira carga |
| Geração total | 4.603 tokens internos/saída, 70,41 tokens/s |
| VRAM observada | aproximadamente 3,8 GB durante inferência |
| GPU | `ollama ps` confirmou `100% GPU`; pico amostrado de utilização de 57% |
| CPU | processo Ollama acumulou cerca de 0,18 s de CPU durante a janela amostrada após a carga; inferência predominantemente na GPU |

O primeiro teste usou o modo de raciocínio padrão do modelo e gerou 4.603 tokens para uma resposta curta, causando latência de 154 s. O `OllamaProvider` do projeto envia `think: false` e limita a saída a 768 tokens para conversas normais. Um benchmark de aplicação aquecida é executado no smoke test.

## Adequação

O hardware é adequado para Qwen 3.5 4B Q4_K_M. O modelo ocupou menos da metade da VRAM disponível e a geração efetiva atingiu 70,41 tokens/s. Modelos substancialmente maiores podem exigir offload parcial para RAM e devem ser avaliados separadamente.

