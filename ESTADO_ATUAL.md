# ESTADO_ATUAL — 2026-11-23

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- **staging = `6f10f34e` (23/11)**: migrações 413 e 410 aplicadas, rate card `2026-11-13-v1` publicado, `RPG_RLS_STRICT_PRINCIPAL=on`, `RPG_ARCHIVE_RECORD=shadow`. `post_deploy` e `vercel_smoke` verdes. **Turnos e novo jogo falham desde 23/11 13:11 UTC:** DeepSeek responde 402 e um `stream_interrupted` do fallback virou US$ 1 de gasto estimado (503 `daily_spend_cap` até 03:00 UTC; spec com a `fb`). Kill switch `image_generation` fica desligado lá.
- **`VERCEL_TOKEN` do `.env.staging` perdeu o escopo do time em 14/11:** `vercel_env.py` dá 403. Variáveis não secretas vão pela CLI logada (`npx vercel@64.2.0 env add NOME production --force`); segredos intocados desde 10/11.
- **Fechadas em 22/11:** 409, 411 (R5 aprovado no `eval-governance`), 424. **413** `in-progress` só por 2 critérios que não rodam nesta máquina (RPCs com JWT de usuário; `rollback.sql` num Postgres local). **410** `in-progress`: `on` ligado; faltam `e2e_session`, `job_survival` e `account_deletion_recovery` no `on` (`docs/spec410/README.md`).
- **Os rate cards vencem em 13/12; a `main` fica vermelha de propósito a partir de 03/12** (`test_rate_card_freshness`) até renovar: `docs/spec197/runbooks/budget.md` § Renovação. O card de imagem renovado ganha `extra_models` (425 R1/R3).
- **425 (troca do modelo de imagem; `gpt-image-2` desliga em 10/02/2027):** Etapa 0 (suporte inerte ao 2.6 + script de medição com teto de US$ 2) na `main`. Etapas 1–3 esperam o dono (Bloqueios).
- **426 `done` (23/11):** gate de tipos cobre `character_creator.py`, os 10 `agents/` com LLM estruturado e os `services/` que chamam LLM (baseline 247 entradas; job `types` bloqueante, 38 s). Parâmetro `llm` novo usa `LLMClient`. Ainda cego: `agents/storyteller.py`.
- **Latência (419–423, 427–429, sessão `fb`):** 419–422, 427 e 428 na `main` com flags `off`, `in-progress` até o staging; 423 parte 1 revisada na branch; 429 `draft` espera o dono. Detalhe: `CHANGELOG.md` 22–23/11.
- Suíte: última completa verde em 22/11, 11892 passed (`FULL_N=3 bash scripts/dev/full.sh`). Flakes: `test_spec361_gate::test_prazo_real_por_thread` (tempo); `test_spec382_node_golden[campaign_secret_rusher_off]`; e2e "F17 workspace_modes".

## Próximos 3 passos

1. **Staging, quando o DeepSeek tiver saldo e o teto diário zerar:** rodar `e2e_session`, `job_survival --skip-redeploy` e `account_deletion_recovery` no `on` e fechar a 410. Rollback: `shadow` + redeploy. A sessão `fb` usa o staging para 419 §6 itens 2–3 e 423.
2. **Até 03/12:** renovar os 4 rate cards, com `extra_models` no de imagem.
3. **Follow-ups:** flake da 382: na suíte que falhou cada log chegou 2× ao root (só a parte `events` diverge); falta achar o teste que deixa o handler duplicado. Suíte no checkout principal chama o Jina de verdade (`.env` com `JINA_API_KEY` + `load_dotenv(override=True)` em `rag.py`). `smoke_ab.py` não loga com Turnstile real (usar o caminho de `s192.app_login`).

## Bloqueios no dono

Só ação externa do dono; "quando ele disser" = o que o coordenador executa na hora.

| Item | Ação do dono | Quando ele disser… |
|---|---|---|
| **DeepSeek** | recarregar o saldo da conta (402 desde 23/11) | "recarreguei" → smokes de turno, fechar 410 e 419–422 |
| **`VERCEL_TOKEN`** | criar token novo na Vercel com acesso ao time e colar no `.env.staging` | "troquei" → `vercel_env.py` volta a valer (hoje só CLI logada) |
| **SPEC-425 Etapas 1–3** | D8: liberar até US$ 2,00 com a `OPENAI_API_KEY` (e a Organization Verification, se a OpenAI pedir); depois D1: escolher Sunburst ou Flare pela ficha de contato; D3 só se o teto passar de US$ 0,12 | "pode medir" → `scripts/art/measure_image_model.py --confirm-spend`, `escolha.md`, Etapa 2 |
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

Decididas por delegação em 09/11 (D-363-1, D-363-2, D-364-2, D-367-2, D-391-9/10) e 22/11 (425: D2, D4–D7, D9; 426: D-426-1 a 5). Veto do dono continua possível, registrado na spec.

## Decisões recentes (≤ 1 dia)

Gerado por `spec_index.py recent` (`/spec-land`, `/estado`); não edite entre os marcadores.

<!-- recent:start -->
- 2026-11-23 · SPEC-429 `draft` — finops-stream-interrompido-estimativa-por-tokens
- 2026-11-23 · SPEC-426 `done` — workspace-gate-de-tipos-degrau-2
- 2026-11-22 · SPEC-428 `draft` — latencia-narracao-tamanho-alvo
- 2026-11-22 · SPEC-427 `draft` — latencia-fila-de-uma-acao
- 2026-11-22 · SPEC-425 `in-progress` — arte-troca-modelo-imagem-gpt-image-2-6
- 2026-11-22 · SPEC-424 `done` — economia-execute-trade-sem-mutar-entrada
- 2026-11-22 · SPEC-422 `in-progress` — latencia-arquivista-sem-llm-fatos-canonicos
- 2026-11-22 · SPEC-421 `in-progress` — latencia-fala-mediada-texto-ao-vivo
- 2026-11-22 · SPEC-420 `in-progress` — latencia-cliente-sem-getoperation
- 2026-11-22 · SPEC-419 `in-progress` — latencia-embedding-timeout-curto
- 2026-11-22 · SPEC-418 `done` — workspace-gate-de-tipos
- 2026-11-22 · SPEC-413 `in-progress` — rpcs-security-definer-publicas
- 2026-11-22 · SPEC-411 `done` — seguranca-higiene-boot-ci
- 2026-11-22 · SPEC-409 `done` — rate-cards-renovacao-e-alerta
<!-- recent:end -->

## Notas da onda em curso (coordenador)

Só o coordenador escreve aqui (≤ 6 linhas por frente); nova onda → mover para `CHANGELOG.md`.

- Notas até 12/11 → `CHANGELOG.md`.
- 22/11: dono liberou tudo que não exige ação externa dele ("autorizo a fazer tudo que vc pode fazer") e o piso de RAM só nesta sessão. Escrita no staging anda pelo coordenador. Duas sessões no mesmo checkout (esta e a `fb`, latência); deploy do staging só com aviso entre as duas. Push de branch `spec-NNN` autorizado (`RPG_WT_PUSH=1` em pouso de risco alto).

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
