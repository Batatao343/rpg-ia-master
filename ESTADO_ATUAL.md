# ESTADO_ATUAL — 2026-11-10

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- staging = `d7aa4beb` (10/11; cartas `on`, `RPG_PLOT_THREADS`/`RPG_FAUNA`/`RPG_CREATURE_GEN`/`RPG_COMBAT_REINFORCEMENTS` `on` pelo `staging_flags.json`; post_deploy, vercel_smoke e e2e_session verdes). `image_generation` off.
- **Onda 09–10/11** (coordenador, com delegação do dono), toda na `main`:
  - **398** `done`: contrato da mão, `outcome_reason=objective_failed` (D-398-1), chip "de pé, sem Vitalidade", Procurar mira escondidos. Smoke R6 no staging (`docs/spec398/smoke.md`): o item 4 da 369 passa e a purga do `unico` ao apagar o jogo também (352 R14).
  - **399** `done`: Dependabot majors (multidict 7.2.1, websockets 17.4, setup-node v7.1.0, motion 14.10.1); PRs do `uv` exigem reexport do `requirements.txt` (D-399-4).
  - **401** `done`: o odre fecha. Armador e escuta mantêm o dial novo, mais perto da faixa, e seguem como exceção nominal (caem na janela 120–199). Registro protegido `206306eb` publicado (eval-gates `42864248456` aprovado pelo dono), com guarda nova da `absoluta` nas recalibradas.
  - **402** `done`: a guarda R3 normaliza o gatilho igual ao produto.
- Épico de cartas fechado (04/11). 369 (balanço), 393 e 397 `done`. Bestiário 370–374, 394, 395 e 400 `done`.
- Balanço: Arcanista 49,7 %; Sangromante acima do teto (exceção do dono, 335). Exceções nominais do bestiário: armador, escuta, chefes hospede/escavador (D-373).
- Latência: 1ª narração p50 2,6 s; abertura de combate ~13 s (staging).
- Project Index não versionado: `python -m project_index build` sob demanda.

## Próximos 3 passos

1. **SPEC-403** `done` (10/11, `18a05688`): Dependabot #71/#72 incorporados (14 pip + 5 npm minor/patch, 3 SIM102); PRs fechados. Adiados, e cada um vira spec própria: Playwright 1.65 (pin de eval), #65 (langchain-google-genai 4.x, exige smoke real) e #67 (uuid-utils 1.x). Nenhum PR aberto.
2. Follow-ups para virar spec:
   - 398: overlay do bestiário entre encontros no hosted ou `RPG_FAUNA_SABER` no staging.
   - 391 (`done` 10/11, `1db1c11f`): o `_r1` sem oferta de retrato pago no meio do combate (D-391-10), o payload encerrado com `stage=called`, P3-9 (`lider_caido`), P3-10 (comentário do R20) e P3-11 (save `telegraphed` com flag off).
   - 401 P2-4: amarrar os artefatos de arena ao hash dos dials.
   - 382: helpers em módulo próprio; golden sem rede.
   - 396: VoiceOver real; sufixo do `PlayQueue`.
3. Refatoração 375–385 restante (383/384 parciais, 392 `draft`); artes do staging (326 D2); smoke §6 de 349/359/360/361.

## Bloqueios no dono

Só ação externa do dono; "quando ele disser" = o que o coordenador executa na hora.

| Item | Ação do dono | Quando ele disser… |
|---|---|---|
| Conta no staging (R-01) | entrar no staging e confirmar o e-mail | "confirmei" → fechar R-01 |
| SPEC-222 compra de teste | Stripe teste: chave + webhook secret no `.env.staging` | "colei" → compra de teste, fechar 222 |
| SPEC-222/197 domínio de produção | comprar domínio e apontar DNS para a Vercel | "comprei X" → URLs, CORS, checklist |
| SPEC-197 | contas pagas, Stripe live, go/no-go ([lista](docs/spec197/decision-request.md)), incluindo o teto de gasto de produção | "go" → checklist production e release; spec de cold start |
| SPEC-198 | Play Console (taxa), package ID, service account | "criei" → upload interno |
| Logs externos (Axiom) | token Axiom no `.env.staging` | "faz" → envio do app |
| SPEC-104 (cloud Railway) | conta Railway + orçamento | "libera" → certificação |
| Auth staging/prod (343) | confirmar e-mail obrigatório + captcha na Vercel | "confirmei" → fechar enumeração |
| Branch remota `spec-380` | apagar no GitHub (já pousada) | — |
| Sessão `rpg-ia-master-da` | está parada em `waiting` (prompt de permissão); a 401 já foi assumida e pousada pelo coordenador, então pode fechar a sessão | — |
| PR #42 (TypeScript 7) | nada: aguarda typescript-eslint suportar TS 7 | — |
| Lore 312 D1 / 313 D8 | ler `data/world/rumor_seed_overrides.json`, `lore_quests.json` | ajustes → reindexar |

Decididas em 09/11 pelo coordenador, com delegação ("confio em vc nas decisoes"): D-363-1 (mantém o crítico por dupla), D-363-2 (R$ 5/dia no staging), D-364-2 (teto exato), D-367-2 (8 reescritas), D-391-9/10. Veto do dono continua possível, registrado na spec.

## Decisões recentes (≤ 1 dia)

Gerado por `spec_index.py recent` (`/spec-land`, `/estado`); não edite entre os marcadores.

<!-- recent:start -->
- 2026-11-10 · SPEC-403 `done` — deps-dependabot-minor-patch-11
- 2026-11-10 · SPEC-402 `done` — guarda-gatilho-normalizado
- 2026-11-10 · SPEC-401 `done` — Bestiário: recalibrar odre, armador e escuta
- 2026-11-10 · SPEC-398 `done` — Cartas: contrato da mão coerente com o alvo, motivo do desfecho de objetivo falho, Vitalidade 0 no chip e inimigos ocultos juntos
- 2026-11-10 · SPEC-391 `done` — Reforço de combate no tabuleiro de cartas ("Chamado do Bando" do líder de matilha)
- 2026-11-09 · SPEC-399 `done` — Dependabot: triagem e pouso dos 8 PRs de versão major
- 2026-11-09 · SPEC-367 `done` — Cartas: acabamento do 5º smoke real (cotação por nome parcial, chip do retrato depois de confirmar, presságio na voz do jogador, retrato de inimigo de fallback, condição de inimigo que termina, ouro na narração da compra, timeout do pool dos scripts de operação)
- 2026-11-09 · SPEC-364 `done` — Cartas: correções do 4º smoke real (trilha da fuga, consulta do mercado, débito do retrato, tempo do resumo, voz do registro e cenários não verificados)
- 2026-11-09 · SPEC-363 `done` — Cartas: correções do 3º smoke real (retrato pago coerente, texto de morte, autoria do resumo, mira, fuga, ids e cenários raros)
<!-- recent:end -->

## Notas da onda em curso (coordenador)

Só o coordenador escreve aqui (≤ 6 linhas por frente); nova onda → mover para `CHANGELOG.md`.

<!-- onda:inserir-aqui -->
- Notas 27/10–05/11 → `CHANGELOG.md`.
- 09–10/11: o coordenador serializou os pousos 398 → 402 draft → 399 → 401 → 402. A sessão `da` travou em `waiting`, e a 401 foi retomada por executor próprio (r2 APPROVED). O autor de eval fez o registro protegido em commit separado. A 398 não repetiu a suíte completa pós-rebase (CI `a24bcd2a` verde).

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
