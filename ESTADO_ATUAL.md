# ESTADO_ATUAL — 2026-11-22

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- staging = `d7aa4beb` (10/11), sem nada de 11/11 em diante: migrações 413/410 não aplicadas e `pricing_versions` só com o card de 08/10. `main` = `origin/main` (push em 22/11).
- **409, pouso B na `main` (22/11):** 4 rate cards renovados com leitura de 13/11, nenhum preço mudou; guarda de CI a T-10 d; cron `finops` devolve 500 com card vencido; `scripts/staging/publish_rate_card.py`. Revisão Sol APPROVED_WITH_FOLLOWUPS. Falta só o staging (Bloqueios).
- **Os cards novos vencem em 13/12; a `main` fica vermelha de propósito a partir de 03/12** (`test_rate_card_freshness`) até renovar: `docs/spec197/runbooks/budget.md` § Renovação.
- **Ordem obrigatória no staging:** `publish_rate_card` → `vercel_env.py` → deploy. `vercel_env.py` e os smokes já apontam para os ids `spec409-staging-2026-11-13*`, que ainda não existem no banco. Deploy antes disso falha fechada (imagem, STT e compra em 503, como hoje); turno de texto não é afetado.
- **`gpt-image-2-2026-04-21` foi descontinuado** (aviso 10/11, desliga 10/02/2027). Trocar para `gpt-image-2.6-*` pede spec própria antes dessa data.
- Onda 12/11 (414–418) `done`. Onda 11/11: `done` 405–408 e 412; fechamento pendente 409, 410, 413 (staging) e 411 (R5 de eval).
- **Latência (419–423, sessão `fb`):** 419–422 na `main`, `in-progress` até o staging; 421 e 422 pousaram com a flag `off`. 423 (abertura, 3 pousos): Etapa 0 + Fase A na branch, em revisão Sol. Detalhe: `CHANGELOG.md` 22/11. **424** reservada: `economy.execute_trade` muta o `state` de entrada (`services/economy.py:812`), teste em `xfail(strict=True)`.
- Suíte: última completa verde em 22/11, 11858 passed (`FULL_N=2 bash scripts/dev/full.sh`). Flakes: `test_spec361_gate::test_prazo_real_por_thread` (tempo); `test_spec382_node_golden[campaign_secret_rusher_off]` (ordem, 1 em 8 suítes); e2e "F17 workspace_modes".
- Gate de tipos é estreito: 4 dos ~19 arquivos com `with_structured_output`, nenhum de `agents/`. `.venv` velho dentro de worktree engana o basedpyright (acusa import faltando): apagar.
- Cartas, bestiário e balanço: sem mudança desde 10/11.

## Próximos 3 passos

1. **Staging (o dono roda 2 comandos, ver Bloqueios):** migrações 413 e 410 → conferência (`docs/spec413/README.md` PC-4, `docs/spec410/README.md` etapa 2) → `publish_rate_card` → `vercel_env.py` → deploy com `RPG_RLS_STRICT_PRINCIPAL=shadow` → smokes (409 §6, 419 §6) → janela sem `pool.checkout_without_principal` → `on`. Fecha 409, 410 e 413. O "antes" está em `docs/spec410/staging-antes.txt`.
2. **Até 03/12:** renovar os 4 rate cards (ler as páginas de novo, runbook `budget.md`) e escrever a spec da troca do modelo de imagem.
3. **Follow-ups:** 424 (`execute_trade`); 411 R5 (autoria de eval + clique do dono); degrau 2 do gate de tipos (tipar `llm`, `agents/`); `type_gate.py` fixar o interpretador; achar o teste que polui o golden da 382; tirar `continue-on-error` do job `types` (falta 1 run verde); guarda de relógio do R3 mais forte (409 P2-2). Antigos: middlewares `async` de `api.py`, `public` fora da Data API, SPEC-404, 383/384/392.

## Bloqueios no dono

Só ação externa do dono; "quando ele disser" = o que o coordenador executa na hora.

| Item | Ação do dono | Quando ele disser… |
|---|---|---|
| **Staging (413, 410, 409)** | rodar, nesta ordem: (1) `bash scripts/dev/py.sh -m scripts.staging.migrations push --apply --confirm-staging uzeagzcyvxzrpjgrhaql --out docs/spec413/evidence/migrations_push.json`; (2) `bash scripts/dev/py.sh -m scripts.staging.publish_rate_card --confirm-staging uzeagzcyvxzrpjgrhaql`. Ou criar regra de permissão para o Bash (o classificador nega escrita no staging) | "rodei" → conferência, `vercel_env.py`, deploy `shadow`, smokes, fechar 409/410/413 |
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
- 2026-11-22 · SPEC-426 `approved` — workspace-gate-de-tipos-degrau-2
- 2026-11-22 · SPEC-425 `approved` — arte-troca-modelo-imagem-gpt-image-2-6
- 2026-11-22 · SPEC-424 `approved` — economia-execute-trade-sem-mutar-entrada
- 2026-11-22 · SPEC-422 `in-progress` — latencia-arquivista-sem-llm-fatos-canonicos
- 2026-11-22 · SPEC-421 `in-progress` — latencia-fala-mediada-texto-ao-vivo
- 2026-11-22 · SPEC-420 `in-progress` — latencia-cliente-sem-getoperation
- 2026-11-22 · SPEC-419 `in-progress` — latencia-embedding-timeout-curto
- 2026-11-22 · SPEC-418 `done` — workspace-gate-de-tipos
- 2026-11-22 · SPEC-409 `in-progress` — rate-cards-renovacao-e-alerta
<!-- recent:end -->

## Notas da onda em curso (coordenador)

Só o coordenador escreve aqui (≤ 6 linhas por frente); nova onda → mover para `CHANGELOG.md`.

- Notas até 12/11 → `CHANGELOG.md`.
- 13–22/11: dono disse "autorizo tudo" (13/11) para os bloqueios que não pedem ação externa dele. Mesmo assim o classificador de permissão negou `migrations push --apply`: escrita no staging só anda com o dono rodando o comando ou criando regra de permissão. Push de branch `spec-NNN` ficou autorizado (`RPG_WT_PUSH=1` em pouso de risco alto). 409 pousou depois de 2 suítes completas (a 1ª pegou 2 testes presos ao card antigo). Campo `Risco` preenchido nas 8 specs abertas antigas.

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
