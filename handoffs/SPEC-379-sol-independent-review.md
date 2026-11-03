# SPEC-379 — revisão sol (review, ciclo 2)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 / sol (spec-reviewer) · **Data:** 2026-11-03 · **Commit revisado:** `3b255884`

## Escopo

`git diff main...HEAD` no worktree `rpg-spec-379` (24 commits, `a594bd67..3b255884`, 27 arquivos):

- **Etapa 4:** os e2e novos `web/e2e/auth-bootstrap.spec.ts` e `web/e2e/visual-cue.spec.ts`; a remoção de
  `tests/test_frontend_auth_bootstrap.py`, `tests/test_frontend_accessibility_contracts.py` e
  `test_visual_assets.py::test_frontend_contract_contains_visual_flow`; o R5 de `web/tests/design.test.mjs`, reancorado em `web/src/**`.
- **Etapa 5:** os testes de comportamento que substituem leitura de fonte em spec297, spec303_passes,
  bug_api_pending_erros, spec352 (linha 462) e spec192.
- **Etapa 6:** 14 migrações para `make_state`/`ScriptedLLM` (fase28, fase61, fase62, fase31, map_view,
  player_knowledge, archivist_policy, replan_after_delivery, mediation_secret, npc_knowledge, dossier_leak,
  context_prefetch, spec301_llm, prompt_injection_corpus).
- Atualizações de `docs/spec379/fonte_inventario.md` e do status da spec.

Ficou fora desta revisão o que o ciclo 1 já cobriu (`handoffs/SPEC-379-sol-review.md`, na `main`).

## Verificação por foco

**(1) Cada teste de fonte removido tem substituto que pega a mesma regressão.**

| Teste antigo (lia fonte) | Substituto | Pega a mesma regressão? |
|---|---|---|
| `test_frontend_auth_bootstrap` (ordem de 3 strings em App.tsx) | `auth-bootstrap.spec.ts`: sem sessão, zero `/game/saves` e `protectedBeforeAuth == 0`; depois do login, pelo menos um `/game/saves` | Sim, e mais forte: testa o efeito em vez da posição do texto. |
| `test_scene_art_nao_rotula_div_sem_role_e_imagem_tem_alt` | `visual-cue.spec.ts` #1: `img` com `alt` igual ao do asset e `.scene-art` sem `aria-label` | Sim, as duas condições. |
| `test_frontend_contract_contains_visual_flow` (4 substrings) | `visual-cue.spec.ts` #2 (cue da ação → `.msg__visual img`) e #3 (arte de raça e de classe vindas de `/data/options`); a arte de cena no chat fica no #1 | Sim. **Mutação refeita aqui:** troquei `r.visual?.cue`, `visual.cue` e `pendingVisual.current?.cue` por `undefined` em App.tsx e o #2 falhou. Depois restaurei. |
| R5 de `design.test.mjs` (lia App.tsx) | O mesmo regex, agora sobre tudo de `web/src/**/*.ts(x)` | Equivalente. Continua passando depois que a 383 fatiar o App.tsx. |
| spec297: getsource `[-3:]` | `storyteller_node` com 5 falas: `player_inputs == ("fala 3","fala 4","fala 5")` | Sim. **Mutação refeita:** com `[-3:]→[-2:]` o teste falha. |
| spec303: getsource `world_calendar.CROSSING_NOTE` | Viagem pelo passo: `CROSSING_NOTE` aparece no prompt no inverno e não aparece no verão | Sim, e mais forte. **Mutação refeita:** sem a nota no `travel_note` (storyteller.py:1333), o teste falha. |
| bug_api_pending: `"{req.backstory}" not in getsource(api)` | `POST /game/new` com `backstory=None`; um spy no `game_graph.invoke` confirma que `"None"` não aparece no resumo nem nas mensagens | Sim, para a superfície que o teste antigo cobria (interpolação no texto). |
| spec352: `"shared_blob_store = blob_store" in runtime.py` | `build_database_runtime` portable/s3 com pool e boto3 falsos → `shared_blob_store is blob_store` | Sim (identidade em runtime). |
| spec192: `count('RPG_RUNTIME_PROFILE…') >= 3` em persistence e `>= 2` em rag | `save_game_state` em `hosted-supabase` → `GameStore.create` e nada escrito em `SAVES_DIR` | Parcial. Ver o item (4). |

**(2) W7, prova R4.2 refeita em 2 das 14 migrações** (`git show main:<arquivo>` no lugar do arquivo, rodar, depois `git checkout`):

- `tests/test_map_view.py`: 21 passaram antes e 21 depois. O sha256 da lista ordenada de ids (separada por `\n`) é
  `c09eb28f…e742a` nos dois lados, igual ao do commit `9166ab67`.
- `tests/test_spec301_llm.py`: 16 passaram antes e 16 depois, com sha256 `7bcf2699…cb777` nos dois lados, igual ao do commit `882c346a`.
- Varri as linhas `+`/`-` das 14 migrações procurando `assert`, `pytest.raises` e `pytest.approx`: **nenhuma ocorrência**. Nenhum assert mudou.
- No `ScriptedLLM`, um schema sem roteiro levanta `AssertionError`, e o nó pode engolir esse erro no `try/except`
  dele. Os fakes de spec301 e do corpus de injeção roteirizam as 4 variantes que o fake antigo atendia (StoryUpdate×3 e NPCResponse),
  então o caminho é equivalente. O sha idêntico confirma isso.

**(3) Os e2e são determinísticos.** Não há `waitForTimeout` nem `setTimeout`. Tudo passa pelo `DeterministicBackend`
(`fixtures.ts`) ou por `page.route` com resposta fixa. As imagens são SVG em `data:`, sem rede e sem LLM. As esperas são as asserções
automáticas do Playwright (`toBeVisible`, `waitFor`). Rodados com `--workers=1`: 4 passaram em 9,8 s.

**(4) O desvio da spec192 na §10 é aceitável.** O teste antigo era fraco de verdade: persistence.py tem **8** checagens de perfil e
rag.py tem **9**, contra os limiares ≥ 3 e ≥ 2. Seria preciso remover 6 ou 8 checagens para ele falhar. Na prática, ele não pegava a
regressão de um caminho isolado. O substituto é mais forte para `save_game_state`. Fica o gap registrado: o `rag.py` hosted e o
`load_game_state`/`list` hosted não têm teste de comportamento nesta suíte. A §10 cita só o `rag.py`, e o FU-1 completa.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `handoffs/SPEC-379-sol-review-2.md` (este arquivo) | O nome pedido pelo coordenador não casa com o `PATTERN` de `scripts/check_handoff_names.py:18-19`, que aceita só `…-(review\|independent-review\|eval-authoring\|port-review)\.md`. `tests/test_handoff_names.py` roda na suíte default, então o pouso fica vermelho. | Antes do pouso, renomear para um nome válido ainda livre (ex.: `handoffs/SPEC-379-sol-independent-review.md`) ou anexar o conteúdo a `SPEC-379-sol-review.md` como seção "Ciclo 2". Não editei o lint porque está fora do escopo do revisor. |
| P2-1 | P2 | `tests/test_spec192_vercel_packaging.py:77-109` | O substituto cobre só o save hosted. Falta comportamento para `load_game_state` hosted (`persistence.py:445` e seguintes) e para memória/RAG hosted (`rag.py:999` e seguintes). | Follow-up na 378 (FU-1): um teste de load hosted que não lê `SAVES_DIR` e um de `add_memory_to_session` hosted que não cria `data/saves_memory/`. |
| P2-2 | P2 | `tests/test_spec297_review_fixes.py:188`, `tests/test_spec303_passes.py:86`, `tests/test_spec352_creature_portraits.py:471` | Testes novos importam helpers privados de outros módulos de teste (`tests.test_grounding_boundaries._story_state`, `tests.test_s3_blob.FakeS3`). É acoplamento entre arquivos de teste: renomear o helper de origem quebra o importador. | Levar `_story_state` para `tests/factories.py` (ou `tests/fakes/`) e `FakeS3` para `tests/fakes/` numa etapa futura de R4. Não bloqueia. |
| P2-3 | P2 | `tests/test_bug_api_pending_erros.py:144-169` | O spy confere resumo e mensagens, mas não `initial_state["player"]["backstory"]` (api.py:5338). Uma regressão `str(req.backstory)` ali passaria. O teste antigo também não pegava esse caso, então a cobertura não caiu. | Opcional: `assert seen_player_backstory == ""`. |

Nada em `evals/` protegido. Não há writer persistente novo nem segredo em log. `dup_helpers --diff main...HEAD` não acusou nada.
Nenhuma função nova passa de 60 linhas.

## Correções aplicadas

Nenhuma ainda (revisão de ciclo 2; o revisor só escreveu este arquivo).

## Pendências

- **P1-1:** renomear este handoff antes de `wt.sh land` (dono: coordenador).
- **FU-1 (P2-1):** testes de comportamento hosted para load/list em `persistence.py` e para memória em `rag.py` (spec de destino: SPEC-378).
- **FU-2 (P2-2):** centralizar `_story_state`/`FakeS3` em `tests/factories.py`/`tests/fakes/` (próxima rodada de R4, SPEC-379 ou sucessora).
- **FU-3 (P2-3):** opcional, junto com a 381.

## Comandos rodados

```text
git diff main...HEAD --stat → 27 arquivos, +316/-110
bash scripts/dev/pt.sh tests/test_spec297_review_fixes.py tests/test_spec303_passes.py tests/test_bug_api_pending_erros.py tests/test_spec352_creature_portraits.py tests/test_spec192_vercel_packaging.py tests/test_visual_assets.py tests/test_spec301_llm.py tests/test_prompt_injection_corpus.py → 133 passed
mutação storyteller.py:1333 (sem CROSSING_NOTE) → test_crossing_note_reaches… FAILED; git checkout
mutação storyteller.py:2378 ([-3:]→[-2:]) → test_player_inputs_are_last_three… FAILED; git checkout
prova R4.2 test_map_view.py (main × branch) → 21/21, sha256 c09eb28f… idêntico ao commit; git checkout
prova R4.2 test_spec301_llm.py (main × branch) → 16/16, sha256 7bcf2699… idêntico ao commit; git checkout
grep assert/pytest.raises/approx nas linhas +/- das 14 migrações → 0
npx playwright test e2e/auth-bootstrap.spec.ts e2e/visual-cue.spec.ts --workers=1 → 4 passed (9.8s)
mutação App.tsx (cue → undefined) + visual-cue -g "visual.cue" → 1 failed; git checkout
dup_helpers.py --diff main...HEAD → nenhuma função nova com nome já usado
git status --short (fim) → limpo, exceto este handoff
```
