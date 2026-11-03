# ESTADO_ATUAL — 2026-11-02

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- staging = `fae9a4e` (cartas `off`; 3 smokes verdes 28/10). 296–326 `done` exceto épico de cartas.
- Épico cartas 327–362 na `main` (`b186db3a`), flags `off`; combate sem LLM nas rodadas (346). 342–357/362 só esperam o smoke real §6 em staging com cartas `on`.
- Balanço: Arcanista 49,7 % (362, vitalidade 8); Sangromante acima do teto aceito pelo dono; `bomba_estopim` dominante (follow-up).
- **Latência** (316–319 `done`): 1ª narração p50 2,6 s; turno inteiro ~10 s.
- Flags: `config/flags.yaml` (340); staging `scripts/staging/staging_flags.json`.
- Máquina: e2e `--workers=1`; sem `uv run` em worktree.
- 02/11 (main `5528fc69`, suíte completa verde por pouso): 349 bestiário 12 regiões (689 Cartas, arena 253/281), 350 tramas NA, 351 abertura, 360 fauna NA, 361 criatura runtime, 366 follow-ups. Flags novas off/legacy: `RPG_PLOT_THREADS`, `RPG_FAUNA`/`_SINAIS`, `RPG_CREATURE_GEN`; `RPG_OPENING_THREAD` on.

## Próximos 3 passos

1. Deploy staging com cartas `on` + smoke LLM real (fecha §6 de 342–357/362; 1–3 retratos pagos; `/game/history` do Livro).
2. Follow-ups: `bomba_estopim` dominante; Corruptor sem carta anti-emboscada; recalibrar ref. v2 (358); turno ~10 s; 319 P2-1.
3. Revisar 10 artes do staging (326 D2); `summary.lifecycle` (seeds 25/32); 57 oklch (322).
4. Bestiário/tramas: smoke real §6 de 349/359/360/361; reindex de `faiss_rules_index` (Jina 429); ligar flags novas (dono); 361 D11 (lint_primeira ≥ 70 %, limiar de latência do job); filhas 360-B/C/D; 336 (teto de usos de família); 9 chefes `on` < 45 %.

## Bloqueios no dono

Só ação externa do dono; "quando ele disser" = o que o coordenador executa na hora.

| Item | Ação do dono | Quando ele disser… |
|---|---|---|
| Conta no staging (R-01) | criar/entrar em https://rpg-ia-master-staging.vercel.app e confirmar o e-mail | "confirmei e loguei" → fechar R-01 no risk register + checklist |
| SPEC-222 compra de teste | criar conta Stripe (modo teste) e colar `STRIPE_SECRET_KEY=sk_test_…` + webhook secret no `.env.staging` | "colei a Stripe" → env no staging, compra de teste, `purchase_token IS NULL`, fechar 222 (exceto domínio) |
| SPEC-222/197 domínio de produção | comprar domínio e apontar DNS para a Vercel | "comprei o domínio X" → URLs legais, CORS/cookies, checklist |
| SPEC-197 | contas pagas (Vercel/Supabase Pro), Stripe live, go/no-go ([lista](docs/spec197/decision-request.md)) | "go do beta" → checklist `--env production` e release; Vercel paga → spec de cold start (19–59 s; bundle, Fluid, aquecimento) |
| SPEC-198 | Play Console (taxa), package ID, service account | "criei o Play Console" → `applicationId`, upload interno, licença real |
| Logs externos (Axiom) | criar conta Axiom e colar o token no `.env.staging` | "faz o Axiom" → envio direto do app, retenção ~30 d |
| SPEC-104 (cloud Railway) | conta Railway + orçamento | "libera a 104" → certificação cloud |
| Auth staging/prod (343) | confirmar `RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED=1` e captcha `gotrue` na Vercel | "confirmei" → fechar achado de enumeração; Stripe live → virar gate `livemode` |
| Plugins não usados | desligar em claude.ai → Settings → Plugins | — |
| Worktree `rpg-spec-350` contaminado (stash pop acidental; nada a perder, 350 pousou via `spec-350-fix`) | autorizar remoção forçada | "pode apagar" → `git worktree remove --force` + apagar branch `spec-350` |
| Flags novas (350/360/361) | decidir quando ligar `RPG_PLOT_THREADS` / `RPG_FAUNA` / `RPG_CREATURE_GEN` | "liga X" → staging_flags + smoke real |
| PR #42 (TypeScript 7) | nada: aguarda typescript-eslint suportar TS 7 | — |
| Rumores da lore (312 D1) e rotas de entrega (313 D8) | ler `data/world/rumor_seed_overrides.json` e `data/world/lore_quests.json` | ajustes → editar e reindexar |

## Decisões recentes (≤ 1 dia)

Gerado por `spec_index.py recent` (`/spec-land`, `/estado`); não edite entre os marcadores.

<!-- recent:start -->
- 2026-11-02 · SPEC-368 `draft` — cartas-fechamento-epico
- 2026-11-02 · SPEC-367 `draft` — cartas-smoke5-acabamento
- 2026-11-02 · SPEC-366 `done` — abertura-followups
- 2026-11-02 · SPEC-365 `done` — deps-eslint-minimatch
- 2026-11-02 · SPEC-364 `in-progress` — Cartas: correções do 4º smoke real (trilha da fuga, consulta do mercado, débito do retrato, tempo do resumo, voz do registro e cenários não verificados)
- 2026-11-02 · SPEC-363 `in-progress` — Cartas: correções do 3º smoke real (retrato pago coerente, texto de morte, autoria do resumo, mira, fuga, ids e cenários raros)
- 2026-11-02 · SPEC-362 `in-progress` — Balanço do Arcanista Cinzento pós-SPEC-355 (piso de 45 % com folga; exceções do Sangromante definitivas)
- 2026-11-02 · SPEC-361 `done` — Criatura gerada em jogo com ficha de Valoria: few-shot, trama, gate U1–U13, variante antes de nova e revisão Opus antes do pool
- 2026-11-02 · SPEC-360 `done` — Criaturas vivas no mundo: sinal antes da luta, ecologia determinística, tramas e telegrafo visível (guarda-chuva; Fase 1 executável)
- 2026-11-02 · SPEC-359 `approved` — Bestiário de Valoria, onda 2: Pântano da Melancolia
- 2026-11-02 · SPEC-351 `done` — Abertura ligada às tramas do mundo (1º arco, 1 NPC pessoal + 1 NPC da trama)
- 2026-11-02 · SPEC-350 `done` — Mundo povoado por tramas: NPCs nomeados com papel concreto, por região, em ondas
- 2026-11-02 · SPEC-349 `done` — Bestiário de Valoria: esteira por região de ameaças físicas, com gate de unicidade (onda 1: Nova Arcádia)
- 2026-11-01 · SPEC-358 `done` — Arena de Cartas por substituição (`lote-v2`) e uso do bot como aviso
- 2026-11-01 · SPEC-357 `in-progress` — Cartas neutras na loja do mercador e como recompensa de missão
- 2026-11-01 · SPEC-355 `in-progress` — Cartas: pendências abertas do épico (regras do motor, conteúdo e balanço final)
<!-- recent:end -->

## Notas da onda em curso (coordenador)

Só o coordenador escreve aqui (≤ 6 linhas por frente); nova onda → mover para `CHANGELOG.md`.

<!-- onda:inserir-aqui -->
- 27/10: 337/338/340 `done`; 38 flags `release` vencem 25/01/2027 (renovar antes).
- 27/10 segurança: inspeção geral sem crítico/alto. 343 (reauth trava na 6ª falha, login 50/h por e-mail, OIDC `aud`, RLS `embedding_profiles`) e 344 (entrada do jogador delimitada em loot/combate, teste XSS `mdLite`) `done`.
- 03/11: SPEC-375–385 `draft` (refatoração; plano e regra W1 anti-conflito em `docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md` §6).
- 28/10–02/11 cartas: 342–357 e 362 pousadas (352 migration aplicada no staging); 358 `done` (protocolo `lote-v2` opt-in); smoke LLM real ao fim.


## Como rodar

- Python 3.13 via `uv` (global é 3.14). Git Bash: `export PATH="$APPDATA/Python/Python314/Scripts:$PATH"`; sempre `PYTHONUTF8=1` (ou `bash scripts/dev/py.sh …`).
- `uv sync --all-extras` · `uv run pytest -q` · `uv run uvicorn api:app --port 8000` · `cd web && npm run build`. Camadas: `docs/guias/TESTES.md`.

## Limitações conhecidas

- Perfil `legacy` serializa por processo e não tem login (por design; hosted é fail-closed).
- Cloud de produção não certificada (SPEC-104 on hold); só staging.
- `saves/` local mistura fixtures e campanhas reais (limpeza só com o dono).
- Long-runs são opt-in (free tiers não sustentam).
- Arquivista `inline` no Vercel (`post_response` não compensa, 213).
- FAISS via `langchain-community` descontinuado (migração exige spec).
- Flake conhecido: `WinError 5` no `os.replace` sob OneDrive (há retry).
