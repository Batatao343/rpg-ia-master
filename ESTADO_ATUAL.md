# ESTADO_ATUAL — 2026-10-19

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- `main` = `4c4167b` (19/10). Única branch não mergeada: `spec-214` (NO_GO, fica fora).
- Suíte offline: **4.023 passed, 229 skipped** (19/10, branch `workspace-improve`; ~4 min serial, ~1m45 com `-n auto`). Atualize
  **substituindo** este número.
- Specs (gerado por `spec_index.py summary`): 258 `done` · 12 `draft` · 5 `in-progress`
  (197 gate de release, 198 Google Play, 222 LGPD, 225 supply chain, 236 FinOps).
- Staging: https://rpg-ia-master-staging.vercel.app (Vercel `gru1` + Supabase
  `uzeagzcyvxzrpjgrhaql`), `hardened=true`, DeepSeek real, Jev `primary` ativo no router.
- LLM: DeepSeek primário em todos os tiers (Groq/OpenAI/Anthropic/Gemini de fallback);
  embeddings Jina. Sem chave → MockLLM.
- Logging P0+P1 na `main` (JSON em stdout, `request_id` ponta a ponta, código de suporte).
- Frontend: `web/` React+Vite (shell chat + painel; mobile single-pane < 900px).

## Próximos 3 passos

1. Fechar as 5 specs `in-progress` (bloqueios abaixo).
2. Aprovar/ordenar os 12 drafts: logging P2 (244, 246, 251–253, 256, 258–261), 104
   (cloud portátil, on hold) e 273 (não recomendada pelo dono).
3. Rebalancear letalidade (SPEC-049): subiu com SPEC-232 e SPEC-275.

## Bloqueios no dono

| Item | O que o dono faz |
|---|---|
| SPEC-197 R-12 | criar cron de produção (staging já tem `pg_cron`) |
| SPEC-197 `ci_green` | push da `main` local e aguardar CI |
| SPEC-198 | Play Console + licença real |
| SPEC-222 | texto legal (`handoffs/SPEC-222-legal-text.md`) + aplicar migration de retenção |
| SPEC-225 | criar environments `eval-provider`/`eval-holdout`/`post-deploy-smoke` |
| SPEC-236 §6.2 | autorizar o teste do teto cross-day |
| Evals autorados (203–216) | aprovar o environment `eval-governance` — use `/eval-publish` |
| Retenção de logs | decidir além do default Vercel Hobby (1 h) |
| Jev `primary` em produção | decisão separada (staging já ativo) |

## Decisões recentes (≤ 7 dias)

Gerado por `uv run python scripts/spec_index.py recent --days 7 --write ESTADO_ATUAL.md`
(roda dentro de `/spec-land` e `/estado`). Não edite à mão entre os marcadores.

<!-- recent:start -->
<!-- recent:end -->

## Notas da onda em curso (coordenador)

O **coordenador** insere aqui, logo abaixo do marcador, no máximo um parágrafo de
≤ 6 linhas por frente/spec da onda atual. Subagentes **não** editam este arquivo:
devolvem o parágrafo no hand-back. Ao abrir a próxima onda, mova estas notas para
`CHANGELOG.md` (seção `## AAAA-MM-DD`) e esvazie a seção.

<!-- onda:inserir-aqui -->

- **19/10 — SPEC-279 e SPEC-280 `done` (aplicadas no staging, 31/31):** apagar campanha não apaga mais o gasto (`usage_events.game_id` → NULL, `operation_id` opaco, `operation_kind` por trigger, reuso de id de operação apagada recusado). Apagar usuário no Auth apaga os jogos dele por trigger (sem FK: perfis OIDC e donos sintéticos), pulando exclusão de conta registrada (SPEC-190). `scripts/admin_orphan_games.py` (dry-run → `--apply --expect N`) limpou os 13 órfãos do staging com gasto e 9 tabelas financeiras idênticos. Revisões Opus com P1 corrigidos → APPROVED ([279](handoffs/SPEC-279-review.md), [280](handoffs/SPEC-280-review.md)).

- **19/10 — SPEC-278 `done`:** React/react-dom 19.3.1 (+ tipos); bundle +12,7 % bruto / +12,5 % gzip, aceito pelo dono (teto de 5 % da 276 não vale para o React). Nenhuma API removida em uso; build, typecheck, 147 Node, audit 0, Playwright Chromium verdes; flake de timing de `account-lifecycle` corrigido (baseline do poll após a tela de conta sair). Revisão Opus APPROVED ([parecer](handoffs/SPEC-278-review.md)). Dependabot #40/#41 obsoletos.

- **19/10 — Logs P2/P3 no staging:** migration `cron_run_state` aplicada (29/29, upsert do cron via `rpg_admin` ok); deploy `da6186b` com Jev `primary`, teto R$ 5; post_deploy/vercel_smoke/e2e verdes; eventos confirmados: `cron.*` com `run_id`, `client_build`/`build_skew`, `client.error` (Origin cruzada 403), `http.body_too_large`, `abuse.blocked`, `combat.summary`, `economy.trade`. Deploy pela CLI exige `-b GIT_SHA` (skill corrigida).
- **19/10 — SPEC-276 `done` parcial:** Playwright 1.64 + Vite 8 (bundle +2,5 % bruto / −0,5 % gzip), `npm audit` 0 e `npm-audit-full` bloqueante; fixture e2e aceita o beacon `client-error` (3 jornadas voltaram). TypeScript 7 bloqueado (typescript-eslint exige TS < 6.1) e React 19 bloqueado pelo teto de bundle (+15,7 %) — decisão do dono. Revisão Opus APPROVED_WITH_FOLLOWUPS ([parecer](handoffs/SPEC-276-review.md)). Dependabot #35/#37 obsoletos.

- **19/10 — Logging P2/P3 `done`** (SPEC-244/246/251/252/253/256/258/259/260/261): beacon de erro do cliente (`client.error`, endpoint público fechado, 4 KiB, rate limit `telemetry`, ids normalizados, amostrado) + ErrorBoundary; build id ponta a ponta (`X-RPG-Build`, `build_skew`); 429/413 com rótulo fechado; trace mecânico do combate (`combat.summary`, `audit_trace.mechanics`); `reason_code` fechado em rejeições; cron com `run_id` + `app.cron_run_state`; `provider.attempt` STT/imagem/Jina; billing Android com códigos. Revisão Opus CHANGES_REQUIRED → 10+1 correções → APPROVED ([parecer](handoffs/LOGS-P2P3-review.md)). Pendente: migration `20261019100000_cron_run_state.sql` + deploy + smoke no staging; AVD da 259; SPEC-277 (R2 da 260, relock de evals) `draft`.

- **19/10 — Workspace `done`:** melhorias de `docs/melhorias_workspace/` (10 recs + bônus): ESTADO ≤ 8 KB e ROADMAP só plano (histórico em `docs/historico/`), cabeçalho da spec como fonte única (`scripts/spec_index.py`), Project Index só de arquivos rastreados, skills/agents versionados, LF/UTF-8, pytest-xdist + timeout, Ruff incremental com baseline, `AGENTS.md` fonte única. Pendente do dono: variável `EVALUATOR_CHANGE_APPROVED` no environment `eval-governance`.
- **19/10 — Staging:** SPEC-222 R6 verde (retrato real OpenAI US$ 0,011; `DELETE /game/save` apagou os 2 objetos do bucket no cron seguinte). 222 pendente só de compra fake (sem chave Stripe test) e domínio de produção. SPEC-236 §6.2 dia 1: trip real do teto diário em `2026-10-19T12:12:37Z`; staging restaurado (teto R$ 5, Jev `primary`, `e2e_session` verde). Dia 2 a partir de 20/10 00:00 BRT pelo [roteiro](docs/staging-wave-2026-10-17/spec236-s62-plano.md). Achados: `usage_events` cai em cascata ao apagar a campanha (some do teto/FinOps, contra a retenção da 222); `app.games` sem FK para `auth.users` (13 órfãos no staging).

## Como rodar

- Python 3.13 via `uv` (o `python` global do Windows é 3.14 — errado). `uv` fica em
  `%APPDATA%\Python\Python314\Scripts`; no Git Bash: `export PATH="$APPDATA/Python/Python314/Scripts:$PATH"`.
- Sempre `PYTHONUTF8=1` (evita `UnicodeEncodeError: 'charmap'`); rode Python a partir
  da raiz do repo (ou `bash scripts/dev/py.sh …`, que faz as duas coisas).
- `uv sync --all-extras` · `uv run pytest -q` (offline, MockLLM) ·
  `uv run uvicorn api:app --port 8000` · `cd web && npm run build`.
- Suíte em camadas e paralelismo: `docs/guias/TESTES.md`.
- Worktree por spec: `/spec-new` (ver `CLAUDE.md` § Fluxo de spec).
- `.env` é carregado com `override=True`; o Git Bash não enxerga variáveis de ambiente
  do Windows definidas depois que ele abriu.
- Ambiente/quotas/providers em detalhe: `docs/historico/ESTADO_ATUAL-ate-2026-10-19.md`
  § "Como rodar" e `.env.example`.

## Limitações conhecidas

- Perfil `legacy` serializa por processo e não tem login (por design; hosted é fail-closed).
- Cloud de produção não certificada (SPEC-104 on hold); só staging.
- `saves/` local mistura fixtures históricas e campanhas reais — limpeza só com seleção humana.
- Free tiers (Groq/Gemini) não sustentam playtest real longo; long-runs são opt-in.
- `post_response` do arquivista não compensa no Vercel (SPEC-213): staging fica `inline`.
- Aviso de descontinuação do FAISS via `langchain-community` (migração exige spec).
- Flake conhecido: `WinError 5` no `os.replace` sob OneDrive (há retry).
