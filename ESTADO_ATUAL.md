# ESTADO_ATUAL — 2026-10-26

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- `main` = `bb101f8` (26/10). Mundo vivo 296–315 `done` (exceto 297). Onda latência+frontend+arte 316–326 **pousada**; specs `in-progress` só por medição/visual no staging.
- **Latência:** 316 narração antes do arquivista (`on` no staging), 317 classify/cache (shadow), 318 trabalho fora do caminho crítico, 319 streaming de tokens + hedge (shadow). Staging: 1ª narração p50 7,5/6,7 s (era 11,1 s), p95 21–27 s (era 35–44 s).
- **Frontend:** 320 espera do turno, 321 celular/toque/safe-area, 322 tokens/contraste/ícones (créditos em `/creditos/`), 323 "Crônicas de Valoria" + sigilo + marginália, 324 títulos/atalhos Alt+1…6. Falta conferência visual no staging.
- **325** mecânicas dormentes: fases A (não-letal, resistência), B (fuga), C (objetos, ordens) com gate R17 verde; A+B `on` no staging; C pronta; **D (reforços) falha o gate (+26 a +37 pp) → `shadow`, decisão do dono**. Etapa 8 (telemetria/bots) pendente.
- **326** arte dinâmica fiel a Valoria: smoke real 8/8 (US$ 0,56), price profiles publicados no staging, **arte `on` no staging** `e9b5f00`.
- Staging `e9b5f00` (26/10): preset versionado `scripts/staging/staging_flags.json` (rodar `vercel_env.py` sem flags = estado aprovado).
- Regras de máquina: e2e só `--workers=1` um arquivo por vez; nunca `uv run` direto em worktree; checar RAM (ver memória).

## Próximos 3 passos

1. Dono decide a Fase D da 325 (reforço só com folga de orçamento [rec.] / aceitar letalidade / desistir).
2. Staging: medir 317 (200 decisões shadow), 319 (`would_replace` < 5 % → `on`); conferência visual 320–324 (390 e 1440); revisar as 10 primeiras artes reais (326 D2).
3. Follow-ups: 325 Etapa 8; `summary.lifecycle` pré-existente (seeds 25/32); 322 botões 3×3 + 57 oklch; SPEC-297 fechar na 1ª promoção.

## Bloqueios no dono

Só o que exige **ação externa** do dono (autorizações internas já foram dadas em 19/10).
Coluna "quando ele disser" = o que o coordenador executa na hora.

| Item | Ação do dono | Quando ele disser… |
|---|---|---|
| Conta no staging (R-01) | criar/entrar em https://rpg-ia-master-staging.vercel.app e confirmar o e-mail | "confirmei e loguei" → fechar R-01 no risk register + checklist |
| SPEC-222 compra de teste | criar conta Stripe (modo teste) e colar `STRIPE_SECRET_KEY=sk_test_…` + webhook secret no `.env.staging` | "colei a Stripe" → env no staging, compra de teste, `purchase_token IS NULL`, fechar 222 (exceto domínio) |
| SPEC-222/197 domínio de produção | comprar domínio e apontar DNS para a Vercel | "comprei o domínio X" → URLs legais, CORS/cookies, checklist |
| SPEC-197 | contas pagas (Vercel/Supabase Pro), Stripe live, go/no-go ([lista](docs/spec197/decision-request.md)) | "go do beta" → checklist `--env production` e release |
| SPEC-198 | Play Console (taxa), package ID, service account | "criei o Play Console" → `applicationId`, upload interno, licença real |
| Logs externos (Axiom) | criar conta Axiom e colar o token no `.env.staging` | "faz o Axiom" → envio direto do app, retenção ~30 d |
| SPEC-104 (cloud Railway) | conta Railway + orçamento | "libera a 104" → certificação cloud |
| Plugins não usados | desligar em claude.ai → Settings → Plugins | — |
| PR #42 (TypeScript 7) | nada: aguarda typescript-eslint suportar TS 7 | — |
| SPEC-325 Fase D (reforços) | escolher: (1) só com folga de orçamento [rec.] / (2) aceitar +26–37 pp / (3) desistir | "opção N" → implementar, gate R17, staging |
| Rumores da lore (312 D1) e rotas de entrega (313 D8) | ler `data/world/rumor_seed_overrides.json` e `data/world/lore_quests.json` | ajustes → editar e reindexar |

## Decisões recentes (≤ 7 dias)

Gerado por `uv run python scripts/spec_index.py recent --days 7 --write ESTADO_ATUAL.md`
(roda dentro de `/spec-land` e `/estado`). Não edite à mão entre os marcadores.

<!-- recent:start -->
- 2026-10-26 · SPEC-326 `in-progress` — Arte dinâmica consistente com Valoria (estética, lore e raça)
- 2026-10-26 · SPEC-325 `in-progress` — Ligar as mecânicas de conflito dormentes (fuga com escolhas, golpe não-letal, resistência revelada, objetos de cena, ordens a companheiro, reforços)
- 2026-10-26 · SPEC-324 `in-progress` — Front: a11y estrutural (headings) e atalhos de teclado
- 2026-10-26 · SPEC-323 `in-progress` — Front: livro, não chat (marginália, HUD, copy, criação, mapa, sigilo)
- 2026-10-26 · SPEC-322 `in-progress` — Front: tokens de cor, contraste, raio, ícones e tipografia
- 2026-10-26 · SPEC-319 `in-progress` — Latência: streaming de tokens do `narrative` e hedge na cauda do narrador
- 2026-10-26 · SPEC-318 `in-progress` — Latência: trabalho pós-narração fora do nó narrador e gate do arquivista
- 2026-10-26 · SPEC-316 `in-progress` — Latência: narração entregue antes do arquivista e do commit (stream aberto)
- 2026-10-25 · SPEC-321 `in-progress` — Front: casca mobile, alvos de toque e safe-area
- 2026-10-25 · SPEC-320 `in-progress` — Front: espera do turno, typewriter e banner de erro
- 2026-10-25 · SPEC-317 `in-progress` — Latência: CLASSIFY mais rápido, contexto em paralelo, caches e ordem do prompt
- 2026-10-25 · SPEC-315 `done` — Rumores adotados pelo motor (a LLM inventa o conteúdo; o motor decide se é verdade e o materializa)
<!-- recent:end -->

## Notas da onda em curso (coordenador)

O **coordenador** insere aqui, logo abaixo do marcador, no máximo um parágrafo de
≤ 6 linhas por frente/spec da onda atual. Subagentes **não** editam este arquivo:
devolvem o parágrafo no hand-back. Ao abrir a próxima onda, mova estas notas para
`CHANGELOG.md` (seção `## AAAA-MM-DD`) e esvazie a seção.

<!-- onda:inserir-aqui -->


## Como rodar

- Python 3.13 via `uv` (o `python` global do Windows é 3.14 — errado). `uv` fica em
  `%APPDATA%\Python\Python314\Scripts`; no Git Bash: `export PATH="$APPDATA/Python/Python314/Scripts:$PATH"`.
- Sempre `PYTHONUTF8=1` (evita `UnicodeEncodeError: 'charmap'`); rode Python a partir
  da raiz do repo (ou `bash scripts/dev/py.sh …`, que faz as duas coisas).
- `uv sync --all-extras` · `uv run pytest -q` (offline, MockLLM) ·
  `uv run uvicorn api:app --port 8000` · `cd web && npm run build`.
- Suíte em camadas e paralelismo: `docs/guias/TESTES.md`.
- Worktree por spec: `/spec-new` (ver `CLAUDE.md` § Fluxo de spec).
- `.env` é carregado com `override=True`; o Git Bash não enxerga variáveis de ambiente
  do Windows definidas depois que ele abriu.
- Ambiente/quotas/providers em detalhe: `docs/historico/ESTADO_ATUAL-ate-2026-10-19.md`
  § "Como rodar" e `.env.example`.

## Limitações conhecidas

- Perfil `legacy` serializa por processo e não tem login (por design; hosted é fail-closed).
- Cloud de produção não certificada (SPEC-104 on hold); só staging.
- `saves/` local mistura fixtures históricas e campanhas reais — limpeza só com seleção humana.
- Free tiers (Groq/Gemini) não sustentam playtest real longo; long-runs são opt-in.
- `post_response` do arquivista não compensa no Vercel (SPEC-213): staging fica `inline`.
- Aviso de descontinuação do FAISS via `langchain-community` (migração exige spec).
- Flake conhecido: `WinError 5` no `os.replace` sob OneDrive (há retry).
