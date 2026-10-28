# ESTADO_ATUAL — 2026-10-27

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- staging = `0e01677` (`lean`, stream `on`, hedge `0`; smokes verdes). 296–315 e 320–326 `done`.
- Épico cartas 327–345 (`-69`), flags `off`.
- **Latência** (316–319 `done`, [A/B](docs/spec316/staging-measure-2026-10-27.md)): 1ª narração p50 → 2,6 s; turno inteiro ~10 s.
- Flags: `config/flags.yaml` (340); staging `scripts/staging/staging_flags.json`.
- Máquina: e2e `--workers=1`; sem `uv run` em worktree; RAM (CLAUDE.md)

## Próximos 3 passos

1. Turno inteiro (~10 s até o `state`): investigar arquivista/commit após a narração.
2. 319 P2-1 medir `replace` no combate.
3. Revisar 10 artes do staging (326 D2); `summary.lifecycle` (seeds 25/32); 322 botões 3×3 + 57 oklch.

## Bloqueios no dono

Só o que exige **ação externa** do dono (autorizações internas já foram dadas em 19/10).
Coluna "quando ele disser" = o que o coordenador executa na hora.

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
| PR #42 (TypeScript 7) | nada: aguarda typescript-eslint suportar TS 7 | — |
| Rumores da lore (312 D1) e rotas de entrega (313 D8) | ler `data/world/rumor_seed_overrides.json` e `data/world/lore_quests.json` | ajustes → editar e reindexar |

## Decisões recentes (≤ 1 dia)

Gerado por `uv run python scripts/spec_index.py recent --days 1 --write ESTADO_ATUAL.md`
(roda dentro de `/spec-land` e `/estado`). Não edite à mão entre os marcadores.

<!-- recent:start -->
- 2026-10-27 · SPEC-345 `in-progress` — Bugs do teste no navegador (cartas off e on): roster, texto interno, mech log e layout mobile
- 2026-10-27 · SPEC-344 `done` — Segurança: delimitação da entrada do jogador no loot e no combate + prova de XSS do `mdLite`
- 2026-10-27 · SPEC-343 `done` — Segurança: trava de falhas no reauth, balde por e-mail no login, `aud` estrito no OIDC e RLS em `embedding_profiles`
- 2026-10-27 · SPEC-342 `in-progress` — Cartas: acabamento do front do combate por cartas (destrava as flags)
- 2026-10-27 · SPEC-341 `done` — Balanço de poder das Cartas pós-SPEC-339 (Sangromante avaro/silencioso, dominantes novas, controles de duração)
- 2026-10-27 · SPEC-340 `done` — Registro de feature flags com validade
- 2026-10-27 · SPEC-339 `done` — Controle aplicado por oponente expira antes de valer (tick de duração)
- 2026-10-27 · SPEC-338 `done` — Fuzz da API com Schemathesis in-process (legacy + perfil DB offline), job `api-fuzz` bloqueante
- 2026-10-27 · SPEC-337 `done` — Testes HTTP dinâmicos de segurança (headers, cookies, CORS, vazamento, IDOR) + correções L1/L2/L4
- 2026-10-27 · SPEC-336 `in-progress` — Cartas #09: Esteira contínua de autoria de cartas (sempre crescer, nunca repetir)
- 2026-10-27 · SPEC-335 `in-progress` — Cartas #08: Expansão do Acervo, onda 1 (identidade por Postura, +220 cartas)
- 2026-10-27 · SPEC-334 `in-progress` — Cartas #07: Clareza do combate no front (mão, Fôlego, presságio, preview e log)
- 2026-10-27 · SPEC-333 `in-progress` — Cartas #06: Espólio de cartas, Forja do baralho, Ferimentos e Cicatrizes como cartas
- 2026-10-27 · SPEC-332 `in-progress` — Cartas #05: Baralhos de inimigo por família e facção (com padrão de intenção)
- 2026-10-27 · SPEC-331 `in-progress` — Cartas #04: A LLM monta a cena, a cena vira tabuleiro (Cartas de Cena, Objetivo e Relógio)
- 2026-10-27 · SPEC-330 `in-progress` — Cartas #03: Gramática de efeitos e palavras-chave de Valoria
- 2026-10-27 · SPEC-329 `in-progress` — Cartas #02: Presságio (intenção do inimigo visível antes da jogada)
- 2026-10-27 · SPEC-328 `in-progress` — Cartas #01: Baralho, Mão e Fôlego (o conflito vira jogo de cartas)
- 2026-10-27 · SPEC-327 `approved` — Cartas #00: Visão — o conflito de Valoria como jogo de cartas estratégico
- 2026-10-27 · SPEC-319 `done` — Latência: streaming de tokens do `narrative` e hedge na cauda do narrador
- 2026-10-27 · SPEC-318 `done` — Latência: trabalho pós-narração fora do nó narrador e gate do arquivista
- 2026-10-27 · SPEC-317 `done` — Latência: CLASSIFY mais rápido, contexto em paralelo, caches e ordem do prompt
- 2026-10-27 · SPEC-316 `done` — Latência: narração entregue antes do arquivista e do commit (stream aberto)
<!-- recent:end -->

## Notas da onda em curso (coordenador)

Só o coordenador escreve aqui (≤ 6 linhas por frente); nova onda → mover para `CHANGELOG.md`.

<!-- onda:inserir-aqui -->
- 27/10: 337/338/340 `done`; 38 flags `release` vencem 25/01/2027 (renovar antes).
- 27/10 segurança: inspeção geral sem crítico/alto. 343 (reauth trava na 6ª falha, login 50/h por e-mail, OIDC `aud`, RLS `embedding_profiles`) e 344 (entrada do jogador delimitada em loot/combate, teste XSS `mdLite`) `done`..
- 27/10 cartas: 328–336 `off`; 339/341 `done`; 342/345 pousadas; falta smoke LLM (staging)


## Como rodar

- Python 3.13 via `uv` (o `python` global do Windows é 3.14 — errado). `uv` fica em
  `%APPDATA%\Python\Python314\Scripts`; no Git Bash: `export PATH="$APPDATA/Python/Python314/Scripts:$PATH"`.
- Sempre `PYTHONUTF8=1` (evita `UnicodeEncodeError: 'charmap'`); rode Python a partir
  da raiz do repo (ou `bash scripts/dev/py.sh …`, que faz as duas coisas).
- `uv sync --all-extras` · `uv run pytest -q` (offline, MockLLM) ·
  `uv run uvicorn api:app --port 8000` · `cd web && npm run build`.
- Suíte em camadas e paralelismo: `docs/guias/TESTES.md`.
- Worktree por spec: `/spec-new` (ver `CLAUDE.md` § Fluxo de spec).
- `.env` com `override=True`. Detalhes: `docs/historico/ESTADO_ATUAL-ate-2026-10-19.md`, `.env.example`.

## Limitações conhecidas

- Perfil `legacy` serializa por processo e não tem login (por design; hosted é fail-closed).
- Cloud de produção não certificada (SPEC-104 on hold); só staging.
- `saves/` local mistura fixtures históricas e campanhas reais — limpeza só com seleção humana.
- Free tiers (Groq/Gemini) não sustentam playtest real longo; long-runs são opt-in.
- `post_response` do arquivista não compensa no Vercel (SPEC-213): staging fica `inline`.
- Aviso de descontinuação do FAISS via `langchain-community` (migração exige spec).
- Flake conhecido: `WinError 5` no `os.replace` sob OneDrive (há retry).
