# ESTADO_ATUAL — 2026-11-03

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- staging = `9e5f43d9` (cartas `on`, preset `staging_flags.json`; 3 smokes pós-deploy verdes 03/11). 296–326 `done`.
- Épico cartas: 334/342/353/354/362/363/364 `done`; 367 (acabamento smoke 5) e 368 (fechamento: rollback, 24 baralhos de facção, Dor Surda, métricas, `seed_save`) na `main`, revisão Sol aprovada, `in-progress` até a 387.
- Smoke 6 (03/11, LLM real; `docs/spec367/smoke-staging.md`, `docs/spec36{7,8}/smoke-local.md`): 0 LLM por rodada; débito 8 ≤ 15 milli; concorrência ok. Achados → **SPEC-387** (`draft`): Carta de Cena só no cache do processo (P1 serverless), oferta de retrato intermitente, chip "Gerando…" tardio, fallback Groq quebrado (2 de 3 tiers), seeds e 10 P3.
- Métricas do épico não atingidas registradas (368 R9/R10) → SPEC-369 (balanço) a escrever.
- Balanço: Arcanista 49,7 %; Sangromante acima do teto (aceito).
- Latência: 1ª narração p50 2,6 s; abertura de combate ~13 s (staging). Flags: `config/flags.yaml`, preset `staging_flags.json`.
- 02/11: 349/350/351/360/361/366 `done`; flags novas off/legacy (`RPG_PLOT_THREADS`, `RPG_FAUNA`, `RPG_CREATURE_GEN`).
- Retrato `tipo:gen:criatura-hostil` retirado do staging (03/11).

## Próximos 3 passos

1. SPEC-387: aprovar → executar → Sol → pouso → deploy → smoke curto; depois fechar 367/368 e 327–333, 335, 336, 345–347, 352, 355, 357.
2. SPEC-369 (balanço: Médico p95 19, bot que lê o Presságio, cartas/rodada ≥ 2, 14 Cartas > 60 %).
3. Follow-ups: `bomba_estopim`; Corruptor anti-emboscada; turno ~10 s; artes do staging (326 D2); smoke §6 de 349/359/360/361; refatoração 375–385 (outra sessão).

## Bloqueios no dono

Só ação externa do dono; "quando ele disser" = o que o coordenador executa na hora.

| Item | Ação do dono | Quando ele disser… |
|---|---|---|
| Conta no staging (R-01) | entrar no staging e confirmar o e-mail | "confirmei" → fechar R-01 |
| SPEC-222 compra de teste | Stripe teste: chave + webhook secret no `.env.staging` | "colei" → compra de teste, fechar 222 |
| SPEC-222/197 domínio de produção | comprar domínio e apontar DNS para a Vercel | "comprei X" → URLs, CORS, checklist |
| SPEC-197 | contas pagas, Stripe live, go/no-go ([lista](docs/spec197/decision-request.md)) | "go" → checklist production e release; spec de cold start |
| SPEC-198 | Play Console (taxa), package ID, service account | "criei" → upload interno |
| Logs externos (Axiom) | token Axiom no `.env.staging` | "faz" → envio do app |
| SPEC-104 (cloud Railway) | conta Railway + orçamento | "libera" → certificação |
| Auth staging/prod (343) | confirmar e-mail obrigatório + captcha na Vercel | "confirmei" → fechar enumeração |
| Plugins não usados | desligar em claude.ai → Settings → Plugins | — |
| Decisões abertas | D-363-1 (crítico em dupla abaixo da defesa), D-363-2 (teto diário R$ 5), D-364-2 ("até 0,015 Estilhas"), D-367-2 (8 frases do Presságio em "você") | dono responde → registrar na spec |
| Flags novas (350/360/361) | decidir quando ligar `RPG_PLOT_THREADS` / `RPG_FAUNA` / `RPG_CREATURE_GEN` | "liga X" → staging_flags + smoke real |
| PR #42 (TypeScript 7) | nada: aguarda typescript-eslint suportar TS 7 | — |
| Lore 312 D1 / 313 D8 | ler `data/world/rumor_seed_overrides.json`, `lore_quests.json` | ajustes → reindexar |

## Decisões recentes (≤ 1 dia)

Gerado por `spec_index.py recent` (`/spec-land`, `/estado`); não edite entre os marcadores.

<!-- recent:start -->
- 2026-11-03 · SPEC-387 `draft` — cartas-smoke6-serverless
- 2026-11-03 · SPEC-386 `approved` — Workspace: guardrails de qualidade e de tokens para os agentes
- 2026-11-03 · SPEC-385 `draft` — Contrato front↔back: forma real das respostas × backend falso do e2e
- 2026-11-03 · SPEC-384 `draft` — Poda que depende do dono: flags aposentáveis, reforços, combate sem tabuleiro, perfis portable/hosted, CLI, `set_deck`, aliases e métrica antiga
- 2026-11-03 · SPEC-383 `draft` — Front: hooks do `App.tsx`, `GameActionsContext`, `Hud.tsx` por aba e poda de e2e de prints
- 2026-11-03 · SPEC-382 `draft` — Refatoração pura dos nós grandes: `storyteller_node`, `_combat_node` e `_run_round` em fases nomeadas no mesmo módulo
- 2026-11-03 · SPEC-381 `draft` — Fatiar `api.py` em routers por domínio, DTOs e montagem de resposta (refatoração pura)
- 2026-11-03 · SPEC-380 `draft` — Evals vivos: baseline no CI, suíte `cards_combat` e playtest real semanal
- 2026-11-03 · SPEC-379 `draft` — Testes: fábricas de estado, fake único de LLM, cobertura real e testes que leem código-fonte
- 2026-11-03 · SPEC-378 `draft` — Refatoração: helpers comuns (fold, leitor de flag, structured output, telemetria do LLM, memória do RAG, perfil runtime)
- 2026-11-03 · SPEC-377 `draft` — Divergências de regra: poda da lei, custo de Fôlego, "vivo" no combate e esconder facção
- 2026-11-03 · SPEC-376 `draft` — Refatoração: fonte única de Cartas/classes (geradores-armadilha) e poda de scripts e código sem chamador
- 2026-11-03 · SPEC-375 `draft` — Higiene do repositório: Project Index fora do git, CI sem passos repetidos, lixo local
- 2026-11-03 · SPEC-374 `draft` — creature-gen-d11
- 2026-11-03 · SPEC-373 `draft` — bestiario-chefes-familia
- 2026-11-03 · SPEC-372 `draft` — fauna-tramas
- 2026-11-03 · SPEC-371 `draft` — fauna-saber-telegrafo
- 2026-11-03 · SPEC-370 `draft` — fauna-backfill-regioes
- 2026-11-03 · SPEC-369 `draft` — cartas-balanco-metas-epico
- 2026-11-03 · SPEC-368 `in-progress` — Cartas: fechamento do épico (bug do rollback, conteúdo faltante, métricas nunca medidas e smoke dos §6 não verificados)
- 2026-11-03 · SPEC-367 `approved` — Cartas: acabamento do 5º smoke real (cotação por nome parcial, chip do retrato depois de confirmar, presságio na voz do jogador, retrato de inimigo de fallback, condição de inimigo que termina, ouro na narração da compra, timeout do pool dos scripts de operação)
- 2026-11-03 · SPEC-355 `in-progress` — Cartas: pendências abertas do épico (regras do motor, conteúdo e balanço final)
- 2026-11-03 · SPEC-331 `in-progress` — Cartas #04: A LLM monta a cena, a cena vira tabuleiro (Cartas de Cena, Objetivo e Relógio)
- 2026-11-03 · SPEC-330 `in-progress` — Cartas #03: Gramática de efeitos e palavras-chave de Valoria
- 2026-11-03 · SPEC-329 `in-progress` — Cartas #02: Presságio (intenção do inimigo visível antes da jogada)
- 2026-11-03 · SPEC-327 `approved` — Cartas #00: Visão — o conflito de Valoria como jogo de cartas estratégico
<!-- recent:end -->

## Notas da onda em curso (coordenador)

Só o coordenador escreve aqui (≤ 6 linhas por frente); nova onda → mover para `CHANGELOG.md`.

<!-- onda:inserir-aqui -->
- Notas 27/10–02/11 → `CHANGELOG.md`.
- 03/11: SPEC-375–385 `draft` (refatoração; plano e regra W1 anti-conflito em `docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md` §6).


## Como rodar

- Python 3.13 via `uv` (global é 3.14). Git Bash: `export PATH="$APPDATA/Python/Python314/Scripts:$PATH"`; sempre `PYTHONUTF8=1` (ou `bash scripts/dev/py.sh …`).
- `uv sync --all-extras` · `uv run pytest -q` · `uv run uvicorn api:app --port 8000` · `cd web && npm run build`. Camadas: `docs/guias/TESTES.md`.

## Limitações conhecidas

- `legacy` sem login, serializa por processo (por design).
- Cloud de produção não certificada (SPEC-104 on hold); só staging.
- Arquivista `inline` no Vercel (`post_response` não compensa, 213).
- FAISS via `langchain-community` descontinuado (migração exige spec).
- Flake conhecido: `WinError 5` no `os.replace` sob OneDrive (há retry).
