# ESTADO_ATUAL — 2026-11-11

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- staging = `d7aa4beb` (10/11), SEM nenhuma mudança de 11/11. `main` local = ver `git log -1` (≈ 65 commits à frente do `origin`, **sem push**).
- **Onda 11/11, segurança e qualidade** (coordenador, decisões delegadas; relatórios em `docs/auditorias/auditoria-workspace-2026-11-11.md`):
  - `done`: **405** (poda de 19 símbolos, −350 l.), **406** (`api.py` 1069 → 984 l., `F401` fora da baseline), **407** (size budget virou catraca, `--tighten`), **408** (resolvedor único `services/llm_mode.py`), **412** (STT fora do event loop, espera-até-terminar sob cancelamento).
  - código na `main`, fechamento pendente: **409** (testes com relógio fixo; falta renovar rate cards), **410** (flag `RPG_RLS_STRICT_PRINCIPAL` `off` + migração `20261111140000`), **411** (boot/CI; falta R5 de eval), **413** (migração `20261111130000` dropa 3 RPCs).
  - **Nenhum SQL novo (413, 410) rodou em Postgres.** Aplicar no staging está bloqueado por permissão (ver Bloqueios).
- Varredura de segurança 11/11: pip-audit, osv, npm audit, gitleaks (histórico), actionlint = 0; semgrep/zizmor/ruff-S triados = 0 verdadeiros positivos; revisões de authz, RLS e Fable: nenhum achado médio/alto.
- **Rate cards vencidos:** imagem e STT (12/10) desde 11/11, LLM (08/10) desde 07/11; embedding vence 16/11. Cotação de imagem e STT recusam no staging (falha fechada) até a renovação (409).
- Suíte: última completa verde em 11/11 (`-n 4`/`-n 6`). Flake conhecido: `tests/test_spec361_gate.py::test_prazo_real_por_thread` (tempo de parede a frio).
- Épico de cartas, bestiário e balanço: sem mudança desde 10/11 (ver `CHANGELOG.md`).

## Próximos 3 passos

1. **Staging (depende do dono, ver Bloqueios):** `migrations push --apply` aplica 413 e 410 em ordem → pgTAP + advisor + smoke → deploy com `RPG_RLS_STRICT_PRINCIPAL=shadow` → janela sem `pool.checkout_without_principal` → `on`. Runbooks: `docs/spec413/README.md`, `docs/spec410/README.md`. Antes, `git push` para o `audit-local.yml` rodar as migrações num Postgres real.
2. **409, resto:** ler preços reais (URL + data), renovar 4 cards, `pricing_versions` e `image_price_profiles.expires_at` no staging, deploy, smoke; guarda de vencimento no CI (N = 10 dias); cron acusa `stale_rate_card`.
3. **Workspace:** specs W-A (pytest confiável), W-B (pouso sem surpresa), W-C (gates que cobram), da auditoria de 11/11. Follow-ups: 411 R5 (autor de eval), middlewares `async` de `api.py`, tirar `public` da Data API, 2 linhas de guia da 407, SPEC-404, 383/384/392.

## Bloqueios no dono

Só ação externa do dono; "quando ele disser" = o que o coordenador executa na hora.

| Item | Ação do dono | Quando ele disser… |
|---|---|---|
| **Staging 11/11 (413, 410, 409)** | rodar `bash scripts/dev/py.sh -m scripts.staging.migrations push --apply --confirm-staging uzeagzcyvxzrpjgrhaql --out docs/spec413/evidence/migrations_push.json`, ou liberar a permissão (o classificador nega escrita no staging) | "rodei"/"liberei" → verificação, deploy `shadow`, fechar 413/410 |
| `git push` da onda 11/11 | autorizar o push da `main` | "pode" → push, CI, `audit-local` |
| SPEC-411 R5 | aprovar no environment `eval-governance` quando publicado | "aprovei" → fechar 411 |
| Supabase Auth | ligar proteção contra senha vazada no painel | — |
| Conta no staging (R-01) | entrar no staging e confirmar o e-mail | "confirmei" → fechar R-01 |
| SPEC-222 compra de teste | Stripe teste: chave + webhook secret no `.env.staging` | "colei" → compra de teste, fechar 222 |
| SPEC-222/197 domínio de produção | comprar domínio e apontar DNS para a Vercel | "comprei X" → URLs, CORS, checklist |
| SPEC-197 | contas pagas, Stripe live, go/no-go ([lista](docs/spec197/decision-request.md)), incluindo o teto de gasto de produção | "go" → checklist production e release; spec de cold start |
| SPEC-198 | Play Console (taxa), package ID, service account | "criei" → upload interno |
| Logs externos (Axiom) | token Axiom no `.env.staging` | "faz" → envio do app |
| SPEC-104 (cloud Railway) | conta Railway + orçamento | "libera" → certificação |
| Auth staging/prod (343) | confirmar e-mail obrigatório + captcha na Vercel | "confirmei" → fechar enumeração |
| Branch remota `spec-380` | apagar no GitHub (já pousada) | — |
| PR #42 (TypeScript 7) | nada: aguarda typescript-eslint suportar TS 7 | — |

Decididas em 09/11 pelo coordenador, com delegação ("confio em vc nas decisoes"): D-363-1 (mantém o crítico por dupla), D-363-2 (R$ 5/dia no staging), D-364-2 (teto exato), D-367-2 (8 reescritas), D-391-9/10. Veto do dono continua possível, registrado na spec.

## Decisões recentes (≤ 1 dia)

Gerado por `spec_index.py recent` (`/spec-land`, `/estado`); não edite entre os marcadores.

<!-- recent:start -->
- 2026-11-11 · SPEC-413 `in-progress` — rpcs-security-definer-publicas
- 2026-11-11 · SPEC-412 `done` — stt-fora-do-event-loop
- 2026-11-11 · SPEC-411 `in-progress` — seguranca-higiene-boot-ci
- 2026-11-11 · SPEC-410 `in-progress` — rls-sem-falha-aberta
- 2026-11-11 · SPEC-409 `in-progress` — rate-cards-renovacao-e-alerta
- 2026-11-11 · SPEC-408 `done` — llm-modo-resolvedor-unico
- 2026-11-11 · SPEC-407 `done` — size-budget-catraca
- 2026-11-11 · SPEC-406 `done` — api-imports-mortos
- 2026-11-11 · SPEC-405 `done` — poda-simbolos-sem-chamador
- 2026-11-11 · SPEC-404 `approved` — Rotas de entrega ampliadas
- 2026-11-11 · SPEC-313 `done` — Quests ancoradas em lore (caça, entrega, escolta, rumor, mortos)
- 2026-11-11 · SPEC-312 `done` — Rumores com semente (lore → motor sorteia → LLM costura; boato falso nunca vira fato)
<!-- recent:end -->

## Notas da onda em curso (coordenador)

Só o coordenador escreve aqui (≤ 6 linhas por frente); nova onda → mover para `CHANGELOG.md`.

- Notas até 10/11 → `CHANGELOG.md`.
- 11/11: 405 → 409-A → 406 → 407 → 408 → 411 → 412 → 413 → 410 pousadas em série. Revisão independente pegou todos os bugs graves (412: 3 de cancelamento em 2 rodadas; 411: checklist de produção; 413: smoke frouxo; 410: comentário de role). Outra sessão deixou `AGENTS.md`, `CLAUDE.md`, `docs/guias/*` modificados e não commitados: nenhuma spec pôde tocá-los. Handoff: `.tmp/handoff-semana-seguranca-2026-11-11.md`.

## Como rodar

- Python 3.13 via `uv` (global é 3.14). Git Bash: `export PATH="$APPDATA/Python/Python314/Scripts:$PATH"`; sempre `PYTHONUTF8=1` (ou `bash scripts/dev/py.sh …`).
- `uv sync --all-extras` · `uv run pytest -q` · `uv run uvicorn api:app --port 8000` · `cd web && npm run build`. Camadas: `docs/guias/TESTES.md`.

## Limitações conhecidas

- `legacy` sem login, serializa por processo (por design).
- Cloud de produção não certificada (SPEC-104 on hold); só staging.
- Arquivista `inline` no Vercel (`post_response` não compensa, 213).
- No hosted, a faixa do bestiário só aparece da rodada 2 no reencontro (overlay SPEC-272 só `legacy`).
- FAISS via `langchain-community` descontinuado (migração exige spec).
- Flake conhecido: `WinError 5` no `os.replace` sob OneDrive (há retry).
