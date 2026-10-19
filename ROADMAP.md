# ROADMAP — RPG IA (plano vivo, revisado 2026-10-19)

> **Este arquivo é o plano, não o diário.** Atualize só quando o plano muda
> (fase nova, ordem nova, item promovido/cancelado). Entrega de spec vai para o
> cabeçalho da spec → `specs/index.yaml` (gerado) e `CHANGELOG.md`.
> Todo o histórico de entregas até 19/10 está em
> [docs/historico/ROADMAP-ate-2026-10-19.md](docs/historico/ROADMAP-ate-2026-10-19.md).
> Detalhe técnico mora só na spec (`specs/SPEC-NNN-<slug>.md`).

## Fases

| Fase | Status | Spec-âncora / evidência | Próximo marco |
|---|---|---|---|
| 0–1 MVP + frontend React | ✅ | `web/` | — |
| 2.5–2.8 Mundo vivo v1 (codex, eventos, rules engine, context builder) | ✅ | SPEC-001…005 | — |
| 3 Clareza de campanha | ✅ | crônica/codex/quest log | — |
| 4 Gameplay core | ✅ | progressão, inventário, economia, party | — |
| 5 Playtest agêntico + telemetria | ✅ | `playtest/` | — |
| 6 Conteúdo sistêmico | ✅ | economia viva, únicos, encontros, clima | — |
| 7 Autoria + validação | ✅ | `scripts/validate_content.py` | — |
| Conflitos v2 (Cartas, Vitalidade, Reações) | ✅ | `conflito-01..17` | rebalancear letalidade (SPEC-049) |
| Classes (5 Posturas × 3 subclasses, níveis 1–20) | ✅ | SPEC-048/047/127 | tuning de Entropia/Carga |
| 8A/8B Arte contextual | ✅ | SPEC-094/125 | — |
| 9 Sprites e som | backlog | — | spec ainda não escrita |
| 10 local + 10b local-first | ✅ | SPEC-025, SPEC-108 | — |
| 10b.8 Cloud portátil | on hold | SPEC-104 (`draft`) | autorização + orçamento |
| 11 Contratos LLM reais | ✅ | `-m llm_contract` | — |
| Evals v4 (governança, harness, suites) | ✅ | SPEC-163…176 | autoria em lote por onda |
| Jev no router | ✅ staging `primary` | SPEC-177…180, 217 | decisão de produção (dono) |
| Monetização (metering, wallet, Estilhas, Stripe, Play) | ✅ backend · 🔶 Play | SPEC-182…196 | SPEC-198 Play Console |
| Beta desktop (UX, combate por gesto, dossiês, mapa) | ✅ | SPEC-199…216 | gate SPEC-212 ✅ |
| Segurança / bugs funcionais | ✅ quase tudo | SPEC-218…237 | fechar 222, 225, 236 |
| Release gate do beta pago | 🔶 | SPEC-197 | R-12 cron de produção + `ci_green` |
| Logging P0/P1 | ✅ | SPEC-239…262 | P2 (drafts abaixo) |
| Podas (ponytail) | ✅ | SPEC-263…274 | 273 não recomendada |

## Próximas specs (ordem)

1. **Fechar `in-progress`:** 197 (gate de release), 236 §6.2 (teto cross-day),
   222 (texto legal + migration), 225 (CI + environments), 198 (Play Console).
2. **Logging P2 (`draft`, aguardam aprovação):** 244 (erros do cliente), 246
   (rate limit/cotas), 251 (trace mecânico do conflito), 252 (rejeições do mundo),
   253 (persistência), 256 (crons), 258 (providers STT/imagem/embeddings), 259
   (Android), 260 (tooling), 261 (build id ponta a ponta).
3. **SPEC-049** rebalanceamento de letalidade com dados novos (pós 232/275).
4. **SPEC-104** cloud portátil — só com autorização/orçamento.

## Backlog por tema

- **Gameplay:** tuning dos 8 knobs `[BALANCEAR]` de Entropia/Carga (rodada real dedicada);
  tiers além do nível 20 não planejados.
- **Audiovisual (Fase 9):** sprites por bioma/local, música por região e período,
  efeitos de combate, packs CC0.
- **Crônica:** melhorias pendentes listadas no histórico.
- **Infra:** migrar o adapter FAISS do `langchain-community` (spec própria);
  decidir se `project_index/repo_graph.json` deixa de ser commitado.
- **Workspace:** medir de novo após uma onda com as melhorias de
  `docs/melhorias_workspace/` ligadas (metas em `01-tokens-e-contexto.md` §5).

## Princípios de desenvolvimento

- **Estado antes de features.** Mundo vivo e auditável > mais features.
- **Lore base ≠ estado vivo.** Codex é canônico; campanha muda via events + rules.
- **LLM propõe, motor aplica.** Nunca confiar em sinal/valor do LLM sem validar.
- **Mecânica é Python.** IA narra; números resolvem determinístico.
- **Regras genéricas, não hardcode.** Tags + componentes = zero ifs por NPC.
- **MockLLM esconde bugs.** Validar structured output novo com chave real.
- **Fatiar fino.** Cada fatia testável, jogável, com invariantes claros.
