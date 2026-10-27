# ESTADO_ATUAL — 2026-10-27

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- staging = `0e01677` (`lean`, stream `on`, hedge `0`; smokes verdes). 296–315 e 320–326 `done`.
- Épico cartas 327–336 em execução (sessão `-69`), tudo atrás de flag `off`.
- **Latência** ([A/B 27/10](docs/spec316/staging-measure-2026-10-27.md)): 1ª narração p50 8,2–11,4 → 2,6 s; turno inteiro sem ganho (~10 s). **316–319 `done`**.
- Flags: registro `config/flags.yaml` (340); preset do staging `scripts/staging/staging_flags.json`.
- Máquina: e2e `--workers=1`; sem `uv run` em worktree; checar RAM (CLAUDE.md).

## Próximos 3 passos

1. Turno inteiro (~10 s até o `state`): investigar arquivista/commit após a narração.
2. Bugfix 316 F-1 (`[RESULTADO]` cru, pré-existente); 319 P2-1 medir `replace` no combate.
3. Revisar as 10 primeiras artes reais do staging (326 D2); `summary.lifecycle` pré-existente (seeds 25/32); 322 botões 3×3 + 57 oklch.

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
| Plugins não usados | desligar em claude.ai → Settings → Plugins | — |
| PR #42 (TypeScript 7) | nada: aguarda typescript-eslint suportar TS 7 | — |
| Rumores da lore (312 D1) e rotas de entrega (313 D8) | ler `data/world/rumor_seed_overrides.json` e `data/world/lore_quests.json` | ajustes → editar e reindexar |

## Decisões recentes (≤ 1 dia)

Gerado por `uv run python scripts/spec_index.py recent --days 1 --write ESTADO_ATUAL.md`
(roda dentro de `/spec-land` e `/estado`). Não edite à mão entre os marcadores.

<!-- recent:start -->
- 2026-10-27 · SPEC-340 `done` — Registro de feature flags com validade
- 2026-10-27 · SPEC-339 `draft` — controle-duracao-tick
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
- 2026-10-26 · SPEC-326 `done` — Arte dinâmica consistente com Valoria (estética, lore e raça)
- 2026-10-26 · SPEC-325 `done` — Ligar as mecânicas de conflito dormentes (fuga com escolhas, golpe não-letal, resistência revelada, objetos de cena, ordens a companheiro, reforços)
- 2026-10-26 · SPEC-324 `done` — Front: a11y estrutural (headings) e atalhos de teclado
- 2026-10-26 · SPEC-323 `done` — Front: livro, não chat (marginália, HUD, copy, criação, mapa, sigilo)
- 2026-10-26 · SPEC-322 `done` — Front: tokens de cor, contraste, raio, ícones e tipografia
- 2026-10-26 · SPEC-321 `done` — Front: casca mobile, alvos de toque e safe-area
- 2026-10-26 · SPEC-320 `done` — Front: espera do turno, typewriter e banner de erro
<!-- recent:end -->

## Notas da onda em curso (coordenador)

Só o coordenador escreve aqui (≤ 6 linhas por frente); nova onda → mover para `CHANGELOG.md`.

<!-- onda:inserir-aqui -->
- 27/10: cartas na sessão `-69`; suíte 1 por vez (avisar). 337/338/340 `done`; 38 flags `release` vencem 25/01/2027 (renovar antes).
- 27/10 cartas: pousadas `off` 328 (Fôlego 2), 329–334, 335 lotes 0–5, 336. Voz aprovada em bloco pelo dono (27/10, sem leitura). Falta: 335 lote 6, 339 (bug tick de controle, `draft` aguardando dono), e2e/smoke real antes de `on`.


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
