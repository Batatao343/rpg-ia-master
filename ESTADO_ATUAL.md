# ESTADO_ATUAL — 2026-10-24

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- `main` = `629c791` (24/10, CI verde). Iniciativa **mundo vivo**: [docs/mundo-vivo/VISAO.md](docs/mundo-vivo/VISAO.md).
- Na main: **296** onda 0, **298** reputação, **302** motor de mundo (`done`); **297** pool entre mundos, **299** lei/crime, **300** companheiros, **301** patentes (revisão Sol aprovada; faltam smoke real §6).
- Suíte offline: **~5.120 passed, 249 skipped** (24/10, SPEC-301, `-n 3`; `test_session_hardening_local` falha também na main por `supabase status` travado — follow-up de ambiente).
- Em revisão: **305** quests de mundo; **303+307** calendário (estações/festas + calendário de Valoria: 7 meses de 20 dias, semana dos Cinco Sinos, Ano 112 da Era 7). Pendentes: **306** sementes de NPC +150 (spec aprovada), **304** NPCs off-screen.
- Staging `35b9576`: DeepSeek, Jev `primary`, teto R$ 5, `RPG_NPC_KNOWLEDGE=on`, `RPG_WORLD_ENGINE=on`, `RPG_SHARED_POOL=shadow` (migração 297 aplicada). Flags novas (`RPG_LAW`, `RPG_COMPANION_SOUL`, `RPG_WORLD_QUESTS`) ainda não configuradas lá.
- Regra nova (24/10): não disparar agentes em rajada; subagente só testes do escopo com `-n 2`; checar RAM (máquina de 16 GB travou). Ver `CLAUDE.md`.

## Próximos 3 passos

1. Pousar 305 e 303+307 após revisão; implementar 306 e 304.
2. Smoke real §6 das specs 297/299/300/301/305/303/307 (DeepSeek, US$ ≤ 3/dia) e staging com as flags novas em `shadow` → `on`.
3. Follow-ups: relock eval `npc_knowledge` (298 R23), grant por coluna p/ `rpg_api` antes de 297 `on` em produção, D7 (criaturas do pool em encontros), 301 F-1 (missão no local conta no turno seguinte), derrota p/ lei → prisão (299), teste local de sessão travando.

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
| Termos (SPEC-297 D3) | cláusula: NPC promovido ao pool fica no mundo desvinculado do autor | "aprovo a cláusula" → texto legal + SPEC-222 |

## Decisões recentes (≤ 7 dias)

Gerado por `uv run python scripts/spec_index.py recent --days 7 --write ESTADO_ATUAL.md`
(roda dentro de `/spec-land` e `/estado`). Não edite à mão entre os marcadores.

<!-- recent:start -->
- 2026-10-24 · SPEC-307 `draft` — calendario-de-valoria
- 2026-10-24 · SPEC-306 `draft` — sementes-npc-expansao
- 2026-10-24 · SPEC-301 `in-progress` — Fações com patente: entrar, subir, sair, trair (e mover o mundo)
- 2026-10-24 · SPEC-300 `in-progress` — Companheiros com alma
- 2026-10-24 · SPEC-299 `in-progress` — Lei e crime por região
- 2026-10-23 · SPEC-305 `draft` — quests-de-mundo-com-prazo
- 2026-10-23 · SPEC-304 `draft` — npcs-agenda-morte-offscreen
- 2026-10-23 · SPEC-303 `draft` — calendario-estacoes-festas
- 2026-10-23 · SPEC-302 `done` — Motor de mundo: tick diário, pressões regionais e curva de tensão
- 2026-10-23 · SPEC-298 `done` — Reputação em quatro níveis (NPC, fação, local, raça/origem)
- 2026-10-23 · SPEC-297 `in-progress` — Pool compartilhado entre mundos (NPCs, criaturas, itens, locais)
- 2026-10-23 · SPEC-296 `done` — mundo-vivo-onda0-religacoes
- 2026-10-23 · SPEC-236 `done` — FinOps/wallet/jobs: custo fantasma de falhas, teto diário cross-day, reservas órfãs, STT incerto, refund parcial pré-crédito, lease e poison jobs
<!-- recent:end -->

## Notas da onda em curso (coordenador)

O **coordenador** insere aqui, logo abaixo do marcador, no máximo um parágrafo de
≤ 6 linhas por frente/spec da onda atual. Subagentes **não** editam este arquivo:
devolvem o parágrafo no hand-back. Ao abrir a próxima onda, mova estas notas para
`CHANGELOG.md` (seção `## AAAA-MM-DD`) e esvazie a seção.

<!-- onda:inserir-aqui -->

- **20–23/10 (mundo vivo):** auditoria (5 frentes) + entrevista; specs 296–305 aprovadas; SPEC-236 e SPEC-296 `done`; staging com notícias entre NPCs `on`; pillow 13/certifi (CVE). Detalhe em `CHANGELOG.md` § 2026-10-20/23. Lição: script Python no Windows grava CRLF → índice diverge do CI; usar `newline=""`.

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
