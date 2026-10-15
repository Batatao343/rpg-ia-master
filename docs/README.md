# docs/ — índice

Documentação do rpg-ia-master organizada por propósito. O estado vivo do projeto continua na raiz
([ESTADO_ATUAL.md](../ESTADO_ATUAL.md), [ROADMAP.md](../ROADMAP.md), [CLAUDE.md](../CLAUDE.md), [AGENTS.md](../AGENTS.md));
o detalhe técnico de cada mudança mora na spec correspondente em [specs/](../specs/).

| Pasta | O que tem | Comece por |
|---|---|---|
| [descricao_projeto/](descricao_projeto/) | Visão completa do projeto: guia interativo, vídeo explicativo, vídeo promocional, roteiros | [guia_interativo.html](descricao_projeto/guia_interativo.html) · [README](descricao_projeto/README.md) |
| [guias/](guias/) | Como fazer: autoria de conteúdo (lore, NPCs, curadoria) e pipeline de arte | [AUTORIA.md](guias/AUTORIA.md) · [ARTE_VISUAL.md](guias/ARTE_VISUAL.md) · [templates/](guias/templates/) |
| [operacao/](operacao/) | Rodar e manter a stack local-first: Supabase local, observabilidade, backup/restore, prontidão G0–G7 | [OPERACAO_LOCAL.md](operacao/OPERACAO_LOCAL.md) · [readiness/](operacao/readiness/) |
| [design/](design/) | Regras do jogo: Cartas, as 5 Posturas e a migração do sistema de conflitos (Valoria v2) | [CARTAS.md](design/CARTAS.md) · [CLASSES_NARRATIVA.md](design/CLASSES_NARRATIVA.md) |
| [playtests/](playtests/) | Relatórios de playtests longos, matrizes A/B, smokes reais e medições | [playtest-matriz-b-2026-09-28.md](playtests/playtest-matriz-b-2026-09-28.md) |
| [auditorias/](auditorias/) | Auditorias, remediações e fechamentos locais; relatório da migração de IDs de specs | [auditoria-execucao-2026-09-26.md](auditorias/auditoria-execucao-2026-09-26.md) |
| [planos/](planos/) | Planos de fases futuras e o pacote v5 (JEV, monetização, hosted, mobile) | [rpg-next-jev-golive-plan/](planos/rpg-next-jev-golive-plan/) |
| [historico/](historico/) | Handoffs de sessões antigas (contexto histórico; não refletem o estado atual) | — |

## Mantidos no lugar de propósito

Estes caminhos são citados por artefatos selados ou por ferramentas, então **não devem ser movidos**:

| Caminho | Por quê |
|---|---|
| [evals-plan-v4/](evals-plan-v4/) | Citado pelo dataset protegido `evals/datasets/regression/memory_context.jsonl` (régua travada por hash) e excluído por caminho em `scripts/normalize_specs.py` |
| [eval-baselines/](eval-baselines/) | Baseline v1 dos evals com hashes registrados |
| [project-index-benchmark/](project-index-benchmark/) | Benchmark A/B selado; o compromisso criptográfico referencia o próprio caminho e o harness lê daqui |
| `specNNN/` (ex.: [spec176/](spec176/)) | Evidência por spec; o fluxo de trabalho grava uma pasta `docs/specNNN/` por spec |

As revisões independentes por spec ficam em [`handoffs/`](../handoffs/) na raiz, convenção do [AGENTS.md](../AGENTS.md).
