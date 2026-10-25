# ESTADO_ATUAL — 2026-10-25

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- `main` = `5d7b6c5` (25/10). **Onda 2 do mundo vivo pousada**: 308 regra de ouro, 309 mundo percebido no narrador, 310 NPC sabe de si, 311 planner/preço/RAG por contexto, 312 rumores com semente, 313 quests ancoradas em lore — todas `done` com revisão Sol + smoke real DeepSeek (~US$ 0,25 na onda). Visão: [docs/mundo-vivo/VISAO.md](docs/mundo-vivo/VISAO.md).
- Onda 1 (296–307) `done`; **297** pool entre mundos `in-progress` (fecha na 1ª promoção observada no staging).
- **Novas `draft` aguardando o dono:** 314 (fações secretas vazam plano no prompt do NPC e no lore público; D1–D6) e 315 (rumor adotado pelo motor: LLM propõe alegação, motor decide verdade e materializa; D1–D8).
- Suíte offline verde no pouso da 313 (`-n 2`, sem `test_session_hardening_local`, que trava em `supabase status`).
- Staging `db11b93` (25/10, 3 smokes verdes): mundo vivo `on`; `RPG_RUMORS=shadow` e `RPG_LORE_QUESTS=shadow` até observar no real; Jev `primary`.
- Regra (24/10): não disparar agentes em rajada; subagente só testes do escopo com `-n 2` e nunca `uv run` direto no worktree (cria `.venv` parcial); checar RAM (ver `CLAUDE.md`).

## Próximos 3 passos

1. Dono: aprovar 314 e 315 (ou ajustar decisões) → implementar 314 primeiro (vazamento ativo; a 311 só mitiga), depois 315.
2. Staging: observar rumores/quests de lore em `shadow` → `on`; SPEC-297 fechar `done` na 1ª promoção.
3. Follow-ups: 313 ver caça/entrega/escolta concluídas no real (bot que persegue a quest); 311 medir tokens do planner; 312 maiúsculas no nome de criatura; relock eval `npc_knowledge`; grant por coluna p/ `rpg_api` antes de 297 em produção; 304 P2s.

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
| SPEC-314 / 315 | ler e aprovar as decisões (padrões recomendados em negrito) | "aprovo a 314/315" → implementar |
| Rumores da lore (312 D1) e rotas de entrega (313 D8) | ler `data/world/rumor_seed_overrides.json` e `data/world/lore_quests.json` | ajustes → editar e reindexar |

## Decisões recentes (≤ 7 dias)

Gerado por `uv run python scripts/spec_index.py recent --days 7 --write ESTADO_ATUAL.md`
(roda dentro de `/spec-land` e `/estado`). Não edite à mão entre os marcadores.

<!-- recent:start -->
- 2026-10-25 · SPEC-315 `draft` — Rumores adotados pelo motor (a LLM inventa o conteúdo; o motor decide se é verdade e o materializa)
- 2026-10-25 · SPEC-314 `draft` — Fações do mundo sob a regra de ouro (o NPC não entrega o plano secreto)
- 2026-10-25 · SPEC-313 `done` — Quests ancoradas em lore (caça, entrega, escolta, rumor, mortos)
- 2026-10-25 · SPEC-312 `done` — Rumores com semente (lore → motor sorteia → LLM costura; boato falso nunca vira fato)
- 2026-10-25 · SPEC-311 `done` — Planner que vê o mundo percebido, preço com motivo e RAG de lore contextual
- 2026-10-25 · SPEC-310 `done` — O NPC sabe de si (fação, patente, agenda, o que ouviu, motivações)
- 2026-10-25 · SPEC-309 `done` — Mundo percebido no narrador: templates do motor, memória do dia e `<MUNDO_PERCEBIDO>`
- 2026-10-24 · SPEC-308 `done` — Regra de ouro para eventos do motor de mundo
- 2026-10-24 · SPEC-307 `done` — Calendário de Valoria: 7 meses, semana de 5 dias, data exibida
- 2026-10-24 · SPEC-306 `done` — Expansão das tabelas de semente de NPC (+25 por tabela)
- 2026-10-24 · SPEC-305 `done` — Quests de mundo com prazo (nascem do estado, falham com consequência)
- 2026-10-24 · SPEC-304 `done` — NPCs off-screen: agenda, viagem, troca de lado e morte telegrafada
- 2026-10-24 · SPEC-303 `done` — Calendário: estações, passos de montanha e festas da lore
- 2026-10-24 · SPEC-301 `done` — Fações com patente: entrar, subir, sair, trair (e mover o mundo)
- 2026-10-24 · SPEC-300 `done` — Companheiros com alma
- 2026-10-24 · SPEC-299 `done` — Lei e crime por região
- 2026-10-23 · SPEC-302 `done` — Motor de mundo: tick diário, pressões regionais e curva de tensão
- 2026-10-23 · SPEC-298 `done` — Reputação em quatro níveis (NPC, fação, local, raça/origem)
- 2026-10-23 · SPEC-297 `in-progress` — Pool compartilhado entre mundos (NPCs, criaturas, itens, locais)
- 2026-10-23 · SPEC-296 `done` — mundo-vivo-onda0-religacoes
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
