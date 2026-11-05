# ESTADO_ATUAL — 2026-11-04

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- staging = `72b7605b` (05/11; cartas `on` + `RPG_PLOT_THREADS`/`RPG_FAUNA`/`RPG_CREATURE_GEN` `on` pelo preset `staging_flags.json`; post_deploy, vercel_smoke e e2e_session verdes). `image_generation` off.
- **Épico de cartas fechado (04/11):** 327–336, 345–347, 352, 355, 357, 367, 368, 387, 389, 390 `done` após auditoria critério × evidência (8 smokes reais; notas "Fechamento" com ressalvas só-por-teste em cada spec).
- Últimos smokes: Carta de cena serverless ok; oferta de retrato 12/12 em 3 instâncias (`docs/spec389/offer-measure-20261104.json`); quest de entrega fecha pela rota NPC; 0 LLM por rodada; débito 8 ≤ 15 milli.
- **SPEC-369** `done` (05/11): balanço em 3 fases; confirmação 260–339 passou (`docs/spec369/CONFIRMACAO.md`); limites registrados pelo dono (D-369-10 a 13). **SPEC-397** `done`: corte do `draft.py`, abertura narra emboscada, passiva por recompensa vale sem ocupar Preparação.
- **SPEC-393** `done` (04/11): smoke real das ressalvas do épico (`docs/smoke-ressalvas-cartas/`) + correções: texto de morte aceita, golpe final com vários alvos, guard da prosa de morte, compra "com minhas últimas moedas", aviso do import de arte.
- **Bestiário (04/11), na `main`:** 370, 371, 372, 373, 374, 394 e 395 `done`.
  - 373: veredito 253/281; chefes hospede/escavador fora da faixa por decisão do dono (D-373); R21 migrou para o Faro da 369; `bomba_estopim` nerfada.
  - 395: `absoluta` não foge.
  - Exceções nominais: odre, armador e escuta.
- Balanço: Arcanista 49,7 %; Sangromante acima do teto (exceção do dono registrada na 335).
- Latência: 1ª narração p50 2,6 s; abertura de combate ~13 s (staging).
- Project Index não é mais versionado (`51c70d85`): nada de reindex por commit.

## Próximos 3 passos

1. SPEC-398 (a escrever): contrato da mão (reação sem alvo vem `jogavel`), rótulo `defeat` no objetivo de cena falho, inimigos ocultos juntos, chip de Vitalidade 0, e o item 4 do smoke 369 (2º conflito contra a mesma família) com driver corrigido. Base: `docs/spec369/diagnostico-combate-travado.md`.
1c. Follow-up do bestiário (ainda sem spec): recalibrar odre, armador e escuta; P2 da 395 (guarda `ficha_vs_base` exige a chave de `sempre`; `move afastar` legado com `absoluta`; campo `arena` desatualizado).
2. Chefe `unico` entre 2 contas só no staging.
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
| Decisões abertas | D-363-1 (crítico em dupla abaixo da defesa), D-363-2 (teto diário R$ 5), D-364-2 ("até 0,015 Estilhas"), D-367-2 (8 frases do Presságio em "você"), veto D-387-1..11 / D-389-1..8 | dono responde → registrar na spec |
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
- 04/11: 375/376/377/378/381/383/388 `done` (383 parcial: hooks auth/turno → SPEC-392, rascunho em `spec-383-etapa4-wip`) (377 item 2: Fôlego unificado, nada protegido a publicar), 379 pousada. **381**: `api.py` 7.970 → 1.082 l. (`api_core`/`api_models`/`api_presenters`/`routes/*`); trava do `api.py` liberada; follow-ups: podar ~106 imports mortos (R17b), §6 no próximo deploy. **382** `done`: `storyteller_node` 1.553→118, `_combat_node` 1.037→125, `_run_round` 484→82 (golden reforçado 66 casos; W2 A=B; smoke real); follow-ups: helpers para módulo próprio, golden sem rede (Jina via `.env` muda eventos). **384** parcial: CLI `game_engine.py`, `set_deck`, alias `/art/player/confirm` e métrica SSE antiga apagados (zero chamadores provado); 3 flags reclassificadas; 7 aposentadorias esperam smoke real por flag no staging atual; D4 vira spec própria (G2: default `RPG_CARD_DECK=on` é decisão do dono). **380** pousada e publicada (eval-gates `41841868897` aprovado pelo dono): `cards_combat` 29 casos + baseline do CI com `compare`; dono ainda cria environment `llm-playtest` (3 chaves) e, após smoke, `RPG_WEEKLY_LLM_PLAYTEST=true`. **391** pousada dormente (flag `off`): gate §8 reprovou após L1+L2+L3 (Δ morte +10,4 pp, Corruptor +17,4; `docs/spec391/gate-resultado.md`) → decisão do dono. **Deps 04/11**: 45 bumps pip via `uv lock` + setup-uv + Dependabot `uv`; otel 1.45.2 (CVE); PR #55 (axe 4.14) espera SPEC-396 (`draft` escrita: ~11 aria-label em 9 componentes; D-396-1..4 com o dono). 392 `draft`. **Index local** (375): `python -m project_index build`.


## Como rodar

- Python 3.13 via `uv` (global é 3.14). Git Bash: `export PATH="$APPDATA/Python/Python314/Scripts:$PATH"`; sempre `PYTHONUTF8=1` (ou `bash scripts/dev/py.sh …`).
- `uv sync --all-extras` · `uv run pytest -q` · `uv run uvicorn api:app --port 8000` · `cd web && npm run build`. Camadas: `docs/guias/TESTES.md`.

## Limitações conhecidas

- `legacy` sem login, serializa por processo (por design).
- Cloud de produção não certificada (SPEC-104 on hold); só staging.
- Arquivista `inline` no Vercel (`post_response` não compensa, 213).
- FAISS via `langchain-community` descontinuado (migração exige spec).
- Flake conhecido: `WinError 5` no `os.replace` sob OneDrive (há retry).
