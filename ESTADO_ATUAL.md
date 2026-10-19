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
