# SPEC-384 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED` (1 P1 com correção de ~6 linhas; o resto é P2/P3)
> **Revisor:** Opus 5.5 / papel Sol (spec-reviewer) · **Data:** 2026-11-04 · **Commit revisado:** `15a6d244` (branch `spec-384`, 9 commits sobre `main` `478478fa`)

## Escopo

Revisei `git diff main...HEAD` inteiro (26 arquivos, +88/−688): D6 (CLI `game_engine.py`), D7 (`set_deck`), D8 (`/art/player/confirm`), D9 (`rpg_sse_first_event_seconds`), as três reclassificações do D1 e o registro de execução na spec. Também conferi se faz sentido barrar as 7 aposentadorias por R1.2b. D3, D4 e D5 não foram tocados, como o dono pediu, e eu confirmei isso.

**Prova de zero chamadores, refeita pelo revisor** (`git grep` na HEAD, árvore versionada inteira menos `specs/`, `handoffs/`, `docs/historico/`, `CHANGELOG.md` e `uv.lock`; mais `web/src`, `web/e2e` e o build Android local não versionado):

- `set_deck`: 0 chamadores. Sobra só o teste novo `test_set_deck_removido` e uma linha na auditoria de 03/11. Não existe endpoint, então o web não tem como chamar a função.
- `game_engine`: 0 imports e 0 invocações em produção, `scripts/`, `playtest/`, `web/`, `.github/`, `vercel.json`, `Procfile` e `pyproject.toml`. O nome continua só em texto de docs (ver P2-1 e P3-3).
- `art/player/confirm`: 0 em `web/src`, `web/e2e`, `scripts/` (staging/smoke/android), `.github` e `vercel.json`. O build Android local (`web/android/app/src/main/assets/public/assets/index-CUkFp7vO.js`, não versionado) usa `art/confirm` e não contém o alias. O nome ainda aparece em dois regex mortos (P3-1, P3-2), nos snapshots históricos `docs/spec381/before/**` e em docs descritivas.
- `rpg_sse_first_event_seconds`: 0 em `observability/` (dashboards, alertas), `docs/operacao/`, `scripts/`, `web/` e `.github`. Fica só no teste negativo e em docs antigas (P3-3).

**Conclusão: o "garanta que ninguém chama" do dono vale para D7, D8 e D9 (e para D6).**

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `tests/test_forge.py:184-190` (teste apagado `test_maldicao_da_cicatriz_nao_se_esquece_nem_sai_do_baralho_por_set_deck`, `main:tests/test_forge.py:190-199`) | O teste apagado misturava duas coisas. A primeira asserção, `assert not cr.forget(st, "mld_cicatriz_braco", "templo")["ok"]`, protege uma guarda **viva** de produção: `services/card_rewards.py:484-485`, SPEC-333 R8, "Uma Cicatriz não se esquece: só sai com Purgar". Procurei em `tests/` (`forget(`, `se esquece`, `mld_cicatriz`) e nenhum outro teste cobre essa guarda. Com o apagamento, a guarda fica sem teste. Isso descumpre "testes apagados: só os que existiam para a coisa apagada". | Manter um teste só com a parte viva, por exemplo `test_maldicao_da_cicatriz_nao_se_esquece` com `_cicatriz(st)`, `assert p["deck"].count("mld_cicatriz_braco") == 1` e `res = cr.forget(st, "mld_cicatriz_braco", "templo"); assert not res["ok"] and "Purgar" in res["error"]`. No mesmo commit, corrigir na spec a contagem "5 testes" do D7. |
| P2-1 | P2 | `docs/guias/ARQUITETURA.md:139` | O guia de arquitetura, que está vivo e que o `AGENTS.md` manda ler sob demanda, ainda lista `game_engine.py # CLI interativo (wizard + loop)`. | Tirar a linha. |
| P2-2 | P2 | `specs/SPEC-384-…md` § Execução, linha D6 | A R6.2 manda pôr a nota "removido (SPEC-384)" em `docs/descricao_projeto/**`. O executor não pôs, chamou isso de "histórico" e não registrou como desvio aprovado. Essas docs também citam `/art/player/confirm` (`explore_04_api_front.md:112, 394`; `guia_interativo.html:581`) e a métrica (`explore_04_api_front.md:41`). | Aplicar a nota, ou registrar o desvio na spec (R0 manda atualizar a spec no mesmo commit quando há desvio). |
| P3-1 | P3 | `services/abuse_policy.py:57` | O regex do rate limit ainda tem a alternativa `player/confirm`. É inofensivo, porque a rota responde 404 antes de qualquer cobrança, mas não corresponde a nenhuma rota. | Trocar por `(quote\|confirm)`. `tests/test_abuse_policy.py` já não tem o caso do alias. |
| P3-2 | P3 | `tests/test_api_fuzz_schemathesis.py:37` | O regex de escopo ainda tem `player/confirm`. | Mesma limpeza. |
| P3-3 | P3 | `docs/spec200/README.md:41`; `docs/spec219/README.md:30` | Docs de spec ainda dizem que a métrica "continua registrada e observada" e listam `/player/confirm`. | Pôr uma nota de 1 linha "removida em SPEC-384 D9/D8", ou deixar como histórico de propósito. |

**Pontos verificados sem achado:**

- **Golden da 381:** no `main`, os dois decoradores ficavam no mesmo `confirm_player_art` (`routes/art.py:249-250`). A resposta 404 era a mesma pelas duas rotas. O golden é indexado pelo nome do caso (`"confirm"`), não pelo path, então trocar para `/art/confirm` mantém a mesma asserção sobre o mesmo handler sem esconder regressão. Rodei `test_spec381_not_found_golden.py` e passou.
- **OpenAPI:** comparei `api.app.openapi()["paths"]` da HEAD com `docs/spec381/before/legacy/openapi.json`. Removido: só `/game/{game_id}/art/player/confirm`. Adicionado: nada. `/auth/logout` e `/auth/refresh/logout` continuam presentes. Nenhum arquivo de auth entrou no diff. `tests/test_removed_routes.py` fixa as duas pontas.
- **D1, reclassificação:** só mudou `config/flags.yaml` (`kind`, sem `expires`, `note`). Nenhum arquivo de `services/` ou `agents/` mudou para essas flags, então o ramo `off` está intacto. A nota do PREFETCH confere com `services/context_prefetch.py:31-36`. O gate `test_flag_registry.py` passou, com os 3 testes novos.
- **D1, barramento das 7 por R1.2b:** está correto. O staging atual é `3cd58353` (confere com o `ESTADO_ATUAL` do worktree). Os smokes reais registrados (`docs/spec389`, `docs/spec387`) são de cartas e rodaram no `70c7ebc3`. Não achei smoke de rumores, quests, calendário, alma de companheiro, duas fases ou replan no deploy atual (`git grep` em docs/handoffs). Barrar é a leitura certa da R1.2b.
- **D9:** a variável `stream_started` só era usada pela métrica apagada. O `import time` continua em uso em `routes/turn.py`. O teste agora afirma que a métrica não aparece em `/metrics` e que `rpg_sse_ack_seconds` continua, como pede a R9.2.
- **D6:** os 2 testes CLI apagados só exercitavam `game_engine`. Os testes de API de checkpoint e morte continuam em `tests/test_bug_morte_checkpoint.py`. Allowlist, `ruff-baseline`, coverage `source` e `size_budget.json` foram limpos.
- **D7, `test_purgar_tambem_limpa_prepared_cards`:** as 3 linhas removidas só exercitavam `set_deck`. As asserções de Purgar seguem em `tests/test_forge.py:333-336`.
- `evals/` não foi tocado. Não há writer persistente novo, segredo em log, structured output nem `except` novo. Nenhuma função nova passa de 60 linhas.

## Correções aplicadas

(nenhuma ainda; o executor preenche commit por item)

## Pendências

- P1-1 antes do pouso.
- P2-1 e P2-2 podem entrar no mesmo commit de correção, ou virar follow-up do coordenador.
- P3-1 a P3-3 são opcionais.
- A edição do `AGENTS.md` (linha 78) entrou na branch (`15a6d244`). A R6.2 manda essa troca para o coordenador, que precisa aceitar ou não. A troca em si está correta.

## Comandos rodados

```text
git diff main...HEAD --stat → 26 arquivos, +88/−688
git grep (set_deck | game_engine | art/player/confirm | player/confirm | rpg_sse_first_event | sse_first_event) HEAD, exclusões acima → só os itens listados
grep build Android local (não versionado) → usa art/confirm; sem player/confirm
grep tests/ "forget(" / "se esquece" / "mld_cicatriz" → guarda card_rewards.py:484 sem teste (P1-1)
pt.sh test_removed_routes test_flag_registry test_card_piles test_forge test_latency_metrics_compat test_no_print_in_production test_spec381_not_found_golden test_abuse_policy test_bug_morte_checkpoint test_size_budget → rc=0 (1 skip)
pt.sh test_api_fuzz_schemathesis -k scope → rc=5 (módulo pulado: schemathesis ausente neste venv)
ruff check routes/turn.py routes/art.py observability/metrics.py services/cards.py tests/… → All checks passed
py: openapi paths HEAD × docs/spec381/before/legacy → removido só /game/{game_id}/art/player/confirm; /auth/logout e /auth/refresh/logout presentes
```
