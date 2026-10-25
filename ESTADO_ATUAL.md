# ESTADO_ATUAL — 2026-10-24

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- `main` = `b6592b3` (24/10). **Iniciativa mundo vivo concluída em código**: specs 296–307 na main; visão em [docs/mundo-vivo/VISAO.md](docs/mundo-vivo/VISAO.md).
- `done`: 296 onda 0, 298 reputação, 299 lei/crime, 300 companheiros, 301 patentes, 302 motor de mundo, 303 estações/festas, 304 NPCs off-screen, 305 quests de mundo, 306 sementes +150, 307 calendário de Valoria (7 meses × 20 dias, Cinco Sinos, Ano 112 da Era 7). **297** pool entre mundos `in-progress` (falta leitura do dono das sementes → `on`).
- Suíte offline: **~5.509 passed, 249 skipped** (24/10, SPEC-304, `-n 3`). `test_session_hardening_local` trava em `supabase status` com o stack local meio de pé (follow-up).
- Smokes reais DeepSeek feitos para 296/298–307 (~US$ 0,10 no total). Bug achado e corrigido: NPC do narrador herdava relação do LLM fora de 0..10.
- Staging `839f23f` (24/10): DeepSeek, Jev `primary`, teto R$ 5; **tudo do mundo vivo `on`** (dono aprovou 24/10): `RPG_NPC_KNOWLEDGE`, `RPG_WORLD_ENGINE`, `RPG_SHARED_POOL`, `RPG_LAW`, `RPG_NPC_WORLD`; companheiros e quests de mundo no default (`on`). SPEC-308 (regra de ouro dos eventos do motor) na main e no staging.
- Regra (24/10): não disparar agentes em rajada; subagente só testes do escopo com `-n 2`; checar RAM (ver `CLAUDE.md`).

## Próximos 3 passos

1. Onda 2 do mundo vivo (specs 308–313, todas aprovadas; 308 `done`): implementar 309 (mundo percebido no narrador) → 310/311 (NPC sabe de si; planner/preço/RAG) → 312 (rumores com semente) → 313 (quests ancoradas em lore). Revisão: [docs/mundo-vivo/REVISAO-ORQUESTRADA-2026-10-24.md](docs/mundo-vivo/REVISAO-ORQUESTRADA-2026-10-24.md).
2. SPEC-297: pool `on` no staging; fechar `done` quando a 1ª promoção (hold 24 h + avaliação) for observada. Cláusula de termos (D3) aprovada pelo dono em 24/10 → escrever no texto legal (SPEC-222).
3. Follow-ups: relock eval `npc_knowledge` (298 R23); grant por coluna p/ `rpg_api` antes de 297 `on` em produção; D7 (criaturas do pool em encontros); 301 F-1; 299 derrota→prisão; 304 P2-2/P2-5/P2-8; bot `faccionario` ir ao posto.

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

## Decisões recentes (≤ 7 dias)

Gerado por `uv run python scripts/spec_index.py recent --days 7 --write ESTADO_ATUAL.md`
(roda dentro de `/spec-land` e `/estado`). Não edite à mão entre os marcadores.

<!-- recent:start -->
- 2026-10-24 · SPEC-313 `draft` — quests-ancoradas-em-lore
- 2026-10-24 · SPEC-312 `draft` — rumores-com-semente
- 2026-10-24 · SPEC-311 `draft` — planner-preco-rag-contextual
- 2026-10-24 · SPEC-310 `draft` — npc-sabe-de-si
- 2026-10-24 · SPEC-309 `draft` — mundo-percebido-no-narrador
- 2026-10-24 · SPEC-308 `done` — Regra de ouro para eventos do motor de mundo
- 2026-10-24 · SPEC-307 `done` — Calendário de Valoria: 7 meses, semana de 5 dias, data exibida
- 2026-10-24 · SPEC-306 `done` — Expansão das tabelas de semente de NPC (+25 por tabela)
- 2026-10-24 · SPEC-305 `done` — Quests de mundo com prazo (nascem do estado, falham com consequência)
- 2026-10-24 · SPEC-304 `done` — NPCs off-screen: agenda, viagem, troca de lado e morte telegrafada
- 2026-10-24 · SPEC-303 `done` — Calendário: estações, passos de montanha e festas da lore
- 2026-10-24 · SPEC-301 `done` — Fações com patente: entrar, subir, sair, trair (e mover o mundo)
- 2026-10-24 · SPEC-300 `done` — Companheiros com alma
- 2026-10-24 · SPEC-299 `done` — Lei e crime por região
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
