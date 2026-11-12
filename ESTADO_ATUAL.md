# ESTADO_ATUAL — 2026-11-12

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- staging = `d7aa4beb` (10/11), SEM nenhuma mudança de 11/11 nem de 12/11. `main` = `origin/main` (push em 12/11; ver `git log -1`).
- **Onda 12/11, workspace, todas `done`** (detalhe no `CHANGELOG.md`): **414** (`full.sh`, hook nega `Agent` sem tipo), **415** (`land_check` no `wt.sh land`, `red_green.sh`, template novo), **416** (pgTAP no CI, catraca de relógio, `DECISOES_FIXAS.md`), **417** (`weak-tests`, Hypothesis), **418** (gate de tipos).
- Onda 11/11: `done` 405–408 e 412; código na `main` com fechamento pendente: **409** (falta renovar rate cards), **410**, **411** (falta R5 de eval), **413**.
- **SQL da 413 e da 410 já rodou em Postgres real no CI** (`audit-local`: migrações do zero + pgTAP `Files=5, Tests=63, PASS`). No staging segue não aplicado (ver Bloqueios).
- CI de `46fed109`: `eval-gates` verde; `validate` com job `types` verde; `audit-local` vermelho só por 3 testes `image_pricing_unavailable`.
- **Rate cards vencidos:** imagem e STT (12/10) desde 11/11, LLM (08/10) desde 07/11; embedding vence 16/11. Cotação de imagem e STT recusam (falha fechada) até a renovação (409).
- Suíte: última completa verde em 12/11, 11631 passed (`FULL_N=2 bash scripts/dev/full.sh`). Flakes: `test_spec361_gate::test_prazo_real_por_thread` (tempo); `test_spec382_node_golden[campaign_secret_rusher_off]` (ordem entre testes, 1 em 6 suítes); e2e "F17 workspace_modes" (tempo, 1 run no CI).
- **Bug de produto aberto:** `economy.execute_trade` muta o `state` de entrada (`services/economy.py:812`); teste em `xfail(strict=True)`.
- Gate de tipos é estreito: 4 dos ~19 arquivos com `with_structured_output`, nenhum de `agents/`.
- Cartas, bestiário e balanço: sem mudança desde 10/11.

## Próximos 3 passos

1. **Staging (depende do dono, ver Bloqueios):** `migrations push --apply` aplica 413 e 410 em ordem → pgTAP + advisor + smoke → deploy com `RPG_RLS_STRICT_PRINCIPAL=shadow` → janela sem `pool.checkout_without_principal` → `on`. Runbooks: `docs/spec413/README.md`, `docs/spec410/README.md`.
2. **409, resto:** ler preços reais (URL + data), renovar 4 cards, `pricing_versions` e `image_price_profiles.expires_at` no staging, deploy, smoke. Risco `alto` só tem handoff `terra`: o `land_check` exige revisão Opus (`sol`) com `## Evidência verificada` antes do pouso. Fecha o vermelho do `audit-local`.
3. **Follow-ups da onda 12/11:** spec do bug de `execute_trade`; degrau 2 do gate de tipos (tipar `llm`, `agents/` e resto de `services/`); achar o teste que polui o golden da 382; tirar `continue-on-error` do job `types` após 3 runs verdes; campo `Risco` nas specs abertas antigas (197, 198, 222, 297, 359, 379, 380, 384). Antigos: 411 R5, middlewares `async` de `api.py`, `public` fora da Data API, SPEC-404, 383/384/392.

## Bloqueios no dono

Só ação externa do dono; "quando ele disser" = o que o coordenador executa na hora.

| Item | Ação do dono | Quando ele disser… |
|---|---|---|
| **Staging 11/11 (413, 410, 409)** | rodar `bash scripts/dev/py.sh -m scripts.staging.migrations push --apply --confirm-staging uzeagzcyvxzrpjgrhaql --out docs/spec413/evidence/migrations_push.json`, ou liberar a permissão (o classificador nega escrita no staging) | "rodei"/"liberei" → verificação, deploy `shadow`, fechar 413/410 |
| Push de branch `spec-NNN` (CI pré-pouso, 415) | autorizar push de branch de spec | "pode" → `RPG_WT_PUSH=1` no pouso de risco alto |
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
- 2026-11-12 · SPEC-418 `done` — workspace-gate-de-tipos
- 2026-11-12 · SPEC-417 `done` — workspace-oraculos-de-teste
- 2026-11-12 · SPEC-416 `done` — workspace-gates-que-cobram
- 2026-11-12 · SPEC-415 `done` — workspace-pouso-sem-surpresa
- 2026-11-12 · SPEC-414 `done` — workspace-pytest-confiavel
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

- Notas até 11/11 → `CHANGELOG.md`.
- 12/11: 414 → 418 em série, cada uma com revisor Sonnet e suíte completa. A revisão pegou 1 P1 (415: veredito lido por palavra solta liberava pouso reprovado). Pouso passa por `land_check` (RAM < 3 GB reprova; `RPG_LAND_SKIP=ram` só com a suíte já rodada). `ESTADO_ATUAL.md` saiu do import do `CLAUDE.md`. Dono autorizou push da `main` nesta onda.

## Como rodar

- Python 3.13 via `uv` (global é 3.14). Git Bash: `export PATH="$APPDATA/Python/Python314/Scripts:$PATH"`; sempre `PYTHONUTF8=1` (ou `bash scripts/dev/py.sh …`).
- `uv sync --all-extras` · `bash scripts/dev/full.sh` (suíte completa) · `uv run uvicorn api:app --port 8000` · `cd web && npm run build`. Camadas: `docs/guias/TESTES.md`.

## Limitações conhecidas

- `legacy` sem login, serializa por processo (por design).
- Cloud de produção não certificada (SPEC-104 on hold); só staging.
- Arquivista `inline` no Vercel (`post_response` não compensa, 213).
- No hosted, a faixa do bestiário só aparece da rodada 2 no reencontro (overlay SPEC-272 só `legacy`).
- FAISS via `langchain-community` descontinuado (migração exige spec).
- Flake conhecido: `WinError 5` no `os.replace` sob OneDrive (há retry).
