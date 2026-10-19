# ESTADO_ATUAL — 2026-10-19

> **Regra deste arquivo: substituir, nunca anexar.** Teto de 8 KB
> (`uv run python scripts/spec_index.py estado-size` falha acima disso).
> Histórico completo até 19/10: [docs/historico/ESTADO_ATUAL-ate-2026-10-19.md](docs/historico/ESTADO_ATUAL-ate-2026-10-19.md).
> Diário por dia: `CHANGELOG.md`. Plano: `ROADMAP.md`. Status de spec: o cabeçalho
> da própria spec (fonte única) → `specs/index.yaml` é gerado no pouso.

## Estado em 10 linhas

- `main` = `4c4167b` (19/10). Única branch não mergeada: `spec-214` (NO_GO, fica fora).
- Suíte offline: **4.023 passed, 229 skipped** (19/10, branch `workspace-improve`; ~4 min serial, ~1m45 com `-n auto`). Atualize
  **substituindo** este número.
- Specs (gerado por `spec_index.py summary`): 258 `done` · 12 `draft` · 5 `in-progress`
  (197 gate de release, 198 Google Play, 222 LGPD, 225 supply chain, 236 FinOps).
- Staging: https://rpg-ia-master-staging.vercel.app (Vercel `gru1` + Supabase
  `uzeagzcyvxzrpjgrhaql`), `hardened=true`, DeepSeek real, Jev `primary` ativo no router.
- LLM: DeepSeek primário em todos os tiers (Groq/OpenAI/Anthropic/Gemini de fallback);
  embeddings Jina. Sem chave → MockLLM.
- Logging P0+P1 na `main` (JSON em stdout, `request_id` ponta a ponta, código de suporte).
- Frontend: `web/` React+Vite (shell chat + painel; mobile single-pane < 900px).

## Próximos 3 passos

1. Fechar as 5 specs `in-progress` (bloqueios abaixo).
2. Aprovar/ordenar os 12 drafts: logging P2 (244, 246, 251–253, 256, 258–261), 104
   (cloud portátil, on hold) e 273 (não recomendada pelo dono).
3. Rebalancear letalidade (SPEC-049): subiu com SPEC-232 e SPEC-275.

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
<!-- recent:end -->

## Notas da onda em curso (coordenador)

O **coordenador** insere aqui, logo abaixo do marcador, no máximo um parágrafo de
≤ 6 linhas por frente/spec da onda atual. Subagentes **não** editam este arquivo:
devolvem o parágrafo no hand-back. Ao abrir a próxima onda, mova estas notas para
`CHANGELOG.md` (seção `## AAAA-MM-DD`) e esvazie a seção.

<!-- onda:inserir-aqui -->

- **19/10 — SPEC-259 `done` + staging `65c0f23`:** a versão do app Android agora chega no access log (`app_version=1.0.0+1`, `client=android`): a leitura do plugin `App` tenta de novo por até 3 s sem bloquear o boot. Smoke no AVD `rpg34` verde. Staging redeployado em `65c0f23` (Jev `primary`, teto R$ 5; post_deploy/vercel_smoke/e2e verdes); 1ª chamada Jev pós-deploy 285 ms, sem timeout (SPEC-281).

- **19/10 — SPEC-282 `done`:** o "timeout do axe" no M07 mobile não era a11y nem app: cada jornada leva 4–12 s sozinha e estourava o teto default de 30 s com a CPU disputada. Teto de 90 s no arquivo `mobile-single-pane` (asserções serious/critical intactas); 14/14 em 3 repetições. Achado: nesta máquina o Playwright completo leva ~8 min e timeouts de 30 s aparecem em outras specs sob carga; no CI passa.

- **19/10 — SPEC-225 `done`:** CI verde com secret-scan/pip-audit/npm audit, Dependabot ativo, 4 environments só `main` + reviewer (`post-deploy-smoke` ganhou reviewer); 1º scan semanal do gitleaks tinha 3 falsos positivos (caminhos renomeados) → `.gitleaksignore`, 568 commits limpos. Critério da compra de license tester movido para a SPEC-198. **SPEC-259 reaberta:** no AVD `rpg34` R1–R3 ok, mas o app nunca envia `X-RPG-App-Version` (plugin do Capacitor registra ~200 ms depois da leitura).

- **19/10 — SPEC-281 `done`:** o client HTTP do Jev é construído antes do prazo de 1 s (1º turno de instância fria não dá mais timeout falso); falha ao construir o client ou ao importar a política congelada cai no CLASSIFY em vez de derrubar o turno; `off` intacto. Revisão Opus APPROVED com 1 P1 corrigido ([parecer](handoffs/SPEC-281-review.md)). Vale no staging no próximo deploy.

- **19/10 — Workspace, 2ª passada:** CI em Node 22 (`web/.nvmrc`) e runners fixos `ubuntu-24.04`; porta do Playwright por checkout (`RPG_E2E_PORT`), dois worktrees rodam e2e juntos; push só de docs pula a suíte pesada (job `docs-only`; `eval-gates` intacto); Dependabot agrupa minor/patch; lint de nome de handoff; `proximas-specs/` → `docs/historico/proximas-specs/`. Achado: M07 mobile (timeout do axe) já falhava na main.

- **19/10 — SPEC-277 `done`:** CLI de evals mostra no stderr suite, `case_id` e traceback (≤ 40 linhas, só frames + classe, **sem a mensagem**, para não vazar caso do holdout no log do Actions); JSON ganha `errors:[{case_id,error_type}]`. Relock só dos 2 hashes; revisão Opus APPROVED com 1 correção ([parecer](handoffs/SPEC-277-review.md)). Flake do teste Jev sem chave sob xdist corrigido.

- **19/10 (onda):** workspace, logs P2/P3 (+ staging), SPEC-222 delete com arte, SPEC-236 §6.2 dia 1, SPEC-276 (Vite 8/Playwright 1.64), SPEC-278 (React 19), SPEC-279/280 (gasto sobrevive ao delete; órfãos) — todos na main com CI verde. Detalhe por frente em `CHANGELOG.md` § 2026-10-19. Pendente: SPEC-236 §6.2 dia 2 (20/10, [roteiro](docs/staging-wave-2026-10-17/spec236-s62-plano.md)).

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
