# ESTADO_ATUAL — 2026-11-04

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- staging = `70c7ebc3` (cartas `on`, preset `staging_flags.json`; smokes pós-deploy verdes 04/11). `image_generation` off.
- **Épico de cartas fechado (04/11):** 327–336, 345–347, 352, 355, 357, 367, 368, 387, 389, 390 `done` após auditoria critério × evidência (8 smokes reais; notas "Fechamento" com ressalvas só-por-teste em cada spec).
- Últimos smokes: Carta de cena serverless ok; oferta de retrato 12/12 em 3 instâncias (`docs/spec389/offer-measure-20261104.json`); quest de entrega fecha pela rota NPC; 0 LLM por rodada; débito 8 ≤ 15 milli.
- **SPEC-369** (balanço, 3 fases): Fase A (régua, `docs/spec369/`) e B1/B2 (`draft.py` com ajuste de orçamento; Carta `cor1_tro_faro_do_abismo`) na `main`. Base: 1,915 Cartas/rodada, 15 Cartas > 60 %, Médico p95 19, leitor de Presságio 103,4 % do cego, 5 células de família fora. B3+ espera o gate do dono.
- Balanço: Arcanista 49,7 %; Sangromante acima do teto (exceção do dono registrada na 335).
- Latência: 1ª narração p50 2,6 s; abertura de combate ~13 s (staging).
- Project Index não é mais versionado (`51c70d85`): nada de reindex por commit.

## Próximos 3 passos

1. SPEC-369 B3–B6 e Fase C, depois do gate do dono em `docs/spec369/BASE.md`.
2. Follow-ups das ressalvas só-por-teste (morte no staging, "Vasculho o corpo", chefe `unico`, `trade_prose_rejected`, `replace` real) num smoke dedicado.
3. Refatoração 375–385 (outra sessão); artes do staging (326 D2); smoke §6 de 349/359/360/361.

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
| SPEC-369 gate R9c | responder os 6 itens no fim de `docs/spec369/BASE.md` (D-369-2/3/7, legadas, `predador_apice`, guarda básica) | "ok/defaults" → B3–B6 + Fase C |
| Decisões abertas | D-363-1 (crítico em dupla abaixo da defesa), D-363-2 (teto diário R$ 5), D-364-2 ("até 0,015 Estilhas"), D-367-2 (8 frases do Presságio em "você"), veto D-387-1..11 / D-389-1..8 | dono responde → registrar na spec |
| Flags novas (350/360/361) | decidir quando ligar `RPG_PLOT_THREADS` / `RPG_FAUNA` / `RPG_CREATURE_GEN` | "liga X" → staging_flags + smoke real |
| PR #42 (TypeScript 7) | nada: aguarda typescript-eslint suportar TS 7 | — |
| Lore 312 D1 / 313 D8 | ler `data/world/rumor_seed_overrides.json`, `lore_quests.json` | ajustes → reindexar |

## Decisões recentes (≤ 1 dia)

Gerado por `spec_index.py recent` (`/spec-land`, `/estado`); não edite entre os marcadores.

<!-- recent:start -->
- (nenhuma spec alterada na janela)
<!-- recent:end -->

## Notas da onda em curso (coordenador)

Só o coordenador escreve aqui (≤ 6 linhas por frente); nova onda → mover para `CHANGELOG.md`.

<!-- onda:inserir-aqui -->
- Notas 27/10–02/11 → `CHANGELOG.md`.
- 04/11: 375/376/377/378/381/388 `done` (377 item 2: Fôlego unificado, nada protegido a publicar), 379 pousada. **381**: `api.py` 7.970 → 1.082 l. (`api_core`/`api_models`/`api_presenters`/`routes/*`); trava do `api.py` liberada; follow-ups: podar ~106 imports mortos (R17b), §6 no próximo deploy. Próximas: 383 (`App.tsx`), 382 (espera 372), 391 `draft` (reforço em cartas, D-391 com o dono). **Index local** (375): `python -m project_index build`.


## Como rodar

- Python 3.13 via `uv` (global é 3.14). Git Bash: `export PATH="$APPDATA/Python/Python314/Scripts:$PATH"`; sempre `PYTHONUTF8=1` (ou `bash scripts/dev/py.sh …`).
- `uv sync --all-extras` · `uv run pytest -q` · `uv run uvicorn api:app --port 8000` · `cd web && npm run build`. Camadas: `docs/guias/TESTES.md`.

## Limitações conhecidas

- `legacy` sem login, serializa por processo (por design).
- Cloud de produção não certificada (SPEC-104 on hold); só staging.
- Arquivista `inline` no Vercel (`post_response` não compensa, 213).
- FAISS via `langchain-community` descontinuado (migração exige spec).
- Flake conhecido: `WinError 5` no `os.replace` sob OneDrive (há retry).
