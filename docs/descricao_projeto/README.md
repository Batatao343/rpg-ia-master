# Descrição do projeto — vídeo e guia interativo

Dois materiais que explicam o rpg-ia-master inteiro, gerados a partir da mesma exploração do código (12/10/2026).

| Arquivo | O que é |
|---|---|
| `brag-output/brag.mp4` | **Vídeo promocional de 45 s** (ritmo de leitura; versão rápida de 25 s em `brag-25s.mp4`) (feito com a skill /brag): app real em uso, trilha e efeitos, sem narração. Thumbnail em `brag.jpg`, texto do post em `share-copy.txt`, roteiro em `brag-plan.md`. Fonte: `video/src/brag/Brag.tsx` (composição `Brag`). |
| `rpg-ia-master-linkedin-3min-narrado.mp4` | Corte de 3 minutos para redes sociais (12 cenas, legendas embutidas para autoplay sem som). Roteiro em `roteiro_linkedin.json`. |
| `rpg-ia-explicado-completo.mp4` | Vídeo explicativo completo (~132 min, 1080p, 19 capítulos, 239 cenas) com narração pt-BR e legendas. |
| `guia_interativo.html` | Guia pedagógico em um único HTML: 23 capítulos, diagramas clicáveis, passo a passo animado, calculadoras com as fórmulas reais (ataque, preço, orçamento de encontro, pontuação de contexto), simulador do roteamento de LLM e quizzes. Abra direto no navegador. |
| `roteiro.md` / `roteiro.json` | Roteiro do vídeo (versão legível e versão que alimenta o Remotion). |
| `revisao_roteiro.md` | Checklist de cobertura, correções e cenas adicionadas na revisão. |
| `video/` | Projeto Remotion que gera o vídeo. |
| `fontes/` | Relatórios da exploração (`exploracao/`), fontes do roteiro (`roteiro/`) e do guia (`guia/`). |

## Como foi feito

1. Seis subagentes Sonnet exploraram o código por fatias (núcleo/agentes/LLM, mecânica, mundo/memória, API/frontend, infraestrutura, qualidade/processo) → `fontes/exploracao/`.
2. Um subagente Opus escreveu o roteiro a partir desses relatórios.
3. Outro subagente Opus revisou contra os relatórios e o código: 31 correções e 46 cenas novas.
4. O vídeo é renderizado a partir do `roteiro.json`; o guia usa a mesma exploração.

## Regenerar

Vídeo (Node ≥ 20, Windows com a voz "Microsoft Maria" para a narração):

```bash
cd docs/descricao_projeto/video
npm install
python scripts/build_timeline.py      # narração TTS (só cenas novas/alteradas) + timeline
npm run studio                         # pré-visualizar
npm run render                         # gera out/rpg-ia-explicado.mp4
npm run timeline:linkedin && npm run render:linkedin   # corte de 3 min
```

Roteiro (depois de editar `fontes/roteiro/p1.py`…`p5.py`):

```bash
cd docs/descricao_projeto/fontes/roteiro
python build.py ../..                  # regera roteiro.md e roteiro.json
python validate_roteiro.py ../../roteiro.json
```

Guia: `bash docs/descricao_projeto/fontes/guia/build.sh`.

`video/node_modules`, `video/out` e `video/public/audio` (≈350 MB de WAV) são regeneráveis e ficam fora do Git.
