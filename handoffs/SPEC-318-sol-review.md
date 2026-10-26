# SPEC-318 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (papel Sol, revisão independente) · **Data:** 2026-10-25 · **Commit revisado:** `4f88cc3e`

## Escopo

Branch `spec-318`, `git diff main...spec-318` (1 commit, 28 arquivos): `main.py` (nó `enrich`,
`turn_prepare → campaign_manager` condicional), `agents/enrich.py`, `agents/storyteller.py`
(stub de NPC, digest inline, `archive_low`), `agents/npc.py` (memória diferida), `agents/archivist.py`
(`_should_archive` legacy/lean/shadow, `_drain_npc_memory`, fallback FAST), `agents/campaign_manager.py`
(`needs_inline_plan`, `replan_after_delivery`, reforço FAST), `agents/loot.py`, `agents/world_simulator.py`,
`services/latency_flags.py`, `services/memory_retry.py`, `state.py`, `playtest/invariants.py`,
`observability/*`, `scripts/staging/vercel_env.py` e os testes novos/alterados.
Fora: medição de staging (§6), `evals compare` de `memory_context.jsonl`, frontend.

O que está correto:
- Topologia: narrador → `enrich` → `archivist` → `turn_finalizer`; `enrich` nunca devolve `messages`;
  cada metade tem `try/except` próprio. SSE: a narração antecipada (SPEC-316) sai da update do nó
  narrador, `enrich` não está em `NARRATING_NODES`, então a narração sai antes de `enrich`/`archivist`
  e uma vez só.
- Replan: só o 1º plano roda antes do router. O `enrich` não replaneja em combate ativo nem com
  `game_over`/`death_pending`. Não há replan duplo (o plano inline grava `last_planned_turn` e zera
  `needs_replan`). O `world_replan_trigger` da SPEC-311 (`needs_replan` do storyteller) é consumido no
  `enrich` do mesmo turno, então o próximo turno já usa o plano novo.
- `archive_low`: fora da whitelist de `_state_to_save_data` (não persiste, sem drift no save); só é
  escrito com `lean`/shadow; vale só no próprio turno (comparação com `turn`).
- Fila `pending_npc_memory`: `attempts` só aparece depois de uma falha (formato antigo intacto), tem
  teto de 99, a fila é limitada por `MAX_PENDING_NPC_MEMORY` e a drenagem também roda no caminho
  `lean` quando o arquivista pula a chamada.
- `sheet_status` faz round-trip no save; save antigo sem o campo carrega como ficha completa.
- **Paridade R7, prova real contra `main`:** `git archive main` + o mesmo roteiro rodado nos dois
  códigos (não na topologia reconstruída do teste), 4 cenários × 3 turnos (exploração/descanso,
  loot, conversa com NPC, viagem + descanso + NPC), comparando `persistence._state_to_save_data`
  inteiro (world, npcs, campaign_plan, pending_npc_memory, memória). Resultado: **0 diferenças**
  com as flags legadas, e o controle main × main também deu 0. Com as flags padrão, a única diferença
  foi `attempts` na fila e o texto de `rag_persistence_error`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `agents/storyteller.py:737-773` (`_ROLE_HINTS`/`_infer_role`); `agents/enrich.py:76-77` | O papel do stub sai de busca de **substring em qualquer frase que cite o nome**. Reproduzido: "Marta aguarda em silêncio" → `Guarda`; "O guarda acena; Marta sorri" → `Guarda`; "veio da capital" → `Capitão`; "um cão ladra… ladrilhos" → `Ladrão`. Esse papel é tratado como "já mostrado ao jogador": `_merge_full` o impõe sobre a ficha completa para sempre. E tem efeito mecânico: `services/interlocutor.py:572` resolve "falo com o guarda" pelo `role`. Isso viola a regra de ouro, porque o stub inventa um papel que o texto não deu, e cria uma contradição permanente com a ficha. | Casar com limite de palavra (`\b`) e exigir aposto/adjacência ao nome ("o guarda Marta", "Marta, a estalajadeira"). Na dúvida, `Desconhecido`, para a ficha completa decidir. Só travar o papel em `_merge_full` quando a inferência for de alta confiança. Testes negativos: aguarda, capital, ladra, outra pessoa na mesma frase. |
| P1-2 | P1 | `agents/enrich.py:118-127`; `agents/storyteller.py:700-713` | A dedupe do librarian e o bloqueio de NPC morto foram adiados para o `enrich`, mas lá contam como **falha**. Quando a ficha resolve para um NPC já existente (o caso `Skriit` → `Skriit Mil-olhos` citado no próprio código) ou para um NPC morto do grafo, `_with_new_npc` não devolve chave nova. O `enrich` então soma `sheet_attempts`, descarta a atualização do canônico (`in_scene`/`last_seen`), chama a fábrica 3× e deixa um **stub duplicado e vivo, em cena, para sempre**. Reproduzido: depois de 3 tentativas ficam `{'Skriit Mil-olhos': in_scene False, 'Skriit': stub/3/in_scene True}`; no legado o resultado é só `Skriit Mil-olhos` com `in_scene True`. Regressão de SPEC-304 R8 ("morto não volta vivo") e da mitigação da §7 ("librarian continua deduplicando"). | Em `_complete_sheet`: sem chave nova mas com `find_runtime_npc_key(others, name, tpl)` encontrado, fundir o stub no canônico (memória, `interaction_count`, `in_scene`, `last_seen_turn`), remover a chave do stub, remapear o `npc_id` em `pending_npc_memory` e contar como concluído. Com `dead_graph_npc(state, tpl)`: remover o stub ou marcá-lo ausente, sem retry. Teste com o cenário acima. |
| P1-3 | P1 | `agents/storyteller.py:958-964` + `_deterministic_story_fallback` (`:574`), usado em `:1993` e no `except` `:2478` | No modo `inline` (o padrão), `world_note` passou a ser **instrução de prompt** ("teça estes fatos na narração em 1 a 3 frases…", linhas `FATO:`/`BOATO:`). Quando o narrador cai no FallbackLLM ou levanta exceção, o fallback determinístico mostra as notas ao jogador, e `_player_facing_note` não remove nada disso. Reproduzido: a saída é literalmente `'O herói percebeu, enquanto o tempo passava: teça estes fatos na narração… FATO: A ponte caiu. BOATO: Dizem…'`. No legado a nota era prosa narrada. É vazamento de prompt no caminho de erro (item 8). | Guardar à parte uma versão para o jogador (os textos de template, boato com "Dizem que…") e passá-la ao fallback, ou remover cabeçalho, instrução e prefixos em `_player_facing_note`. Teste: virada de dia com o narrador em FallbackLLM, sem "teça"/"FATO:" na mensagem. |
| P2-1 | P2 | `agents/enrich.py:25-45` | `_KEEP_FROM_STUB` não inclui `vitalidade`, `max_vitalidade`, `ferimentos` nem `ferimento_espacos`, que estão em `entity_identity._NPC_DYNAMIC_FIELDS`. Se a ficha completa só chegar num turno seguinte, depois de combate ou dano no stub, a fusão cura o NPC. A `relationship` alterada por outra via, sem interação, também se perde. | Usar `_NPC_DYNAMIC_FIELDS` ∪ a lista atual. |
| P2-2 | P2 | `agents/enrich.py:73-76` | Em cache-hit do `npc_database`/pool, a ficha fundida fica com o `id` do stub (`npc_<nome>`) e perde o id canônico do cache. | Manter o id da ficha completa quando nada foi indexado ainda pelo id do stub; senão, remapear. |
| P2-3 | P2 | `tests/test_enrich_node.py:29-114,176-224` | O teste R7 reconstrói a topologia do HEAD com o código de agentes **da branch**: prova a topologia, não a paridade dos agentes. Os 3 roteiros não cobrem virada de dia, replan (troca de região/intervalo) nem NPC introduzido pelo storyteller. A minha comparação contra o `main` real passou (0 diferenças), mas com a mesma lacuna de cenários. | Follow-up: fixture dourada (save JSON gerado no `main`) com cenários de viagem entre regiões, descanso com virada de dia e apresentação de NPC. |
| P2-4 | P2 | `agents/campaign_manager.py:236-238`; `agents/archivist.py:1029-1031` | O tier FAST no reforço "beat em inglês" e no fallback em texto do arquivista **não depende de flag**: com as flags legadas o provider/tier muda mesmo assim. O MockLLM não mostra isso, e o R7 promete paridade. | Registrar em §9 que esses dois pontos são incondicionais, ou atrelá-los às flags. |
| P2-5 | P2 | `scripts/staging/vercel_env.py:135-139` | `RPG_NPC_TWO_PHASE` e `RPG_REPLAN_AFTER` caem no conjunto padrão `off/shadow/on`. `shadow` passa na validação, mas `latency_flags` o trata como inválido e liga `on`. | Adicionar `("off", "on")` para as duas em `WORLD_FLAG_VALUES` e cobrir em `test_spec192_vercel_env.py`. |
| P2-6 | P2 | `agents/world_simulator.py:254-264` | `digest_prompt_lines` não tem teto total. O legado limitava a `NARRATION_MAX_CHARS` no total; aqui cada item tem o seu teto, mas o número de linhas é livre (dias pulados). | Cortar em `DAY_FACTS_MAX` linhas e/ou num orçamento de caracteres. |
| P2-7 | P2 | `agents/action_guard.py:43` | Turno de reparo bloqueado (vai a END) com `needs_replan=True`: com `REPLAN_AFTER=on`, o replan agora acontece **depois** da narração do turno seguinte, e não antes. Aceitável pela D2, mas não está documentado. | Mencionar em §7/§9. |
| P2-8 | P2 | `agents/archivist.py` (`_drain_npc_memory`) | Com a memória diferida, o texto de `rag_persistence_error` muda ("…de npc_x" em vez de "…de sessão") e a promoção sai como `canonical_source` em vez de `npc_claim_direct_write`. Só cosmético/auditoria. | Usar o motivo `npc_claim_direct_write` quando a entrada era nova. |

## Correções aplicadas

Nenhuma ainda (aguardando o executor).

## Pendências

- P1-1, P1-2 e P1-3 bloqueiam o pouso: as três ficam no caminho padrão `on`/`inline`.
- P2-3 (fixture dourada de paridade) pode virar follow-up desta spec ou da SPEC-319.
- §6 (staging) e `evals compare` de `memory_context.jsonl` seguem com o coordenador; `lean` continua opt-in.

## Comandos rodados

```text
git diff main...spec-318 --stat → 28 files, +1800/-128
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_enrich_node.py tests/test_npc_two_phase.py tests/test_replan_after_delivery.py tests/test_day_digest_inline.py tests/test_archivist_policy.py tests/test_spec192_vercel_env.py tests/test_streaming.py tests/test_conflict_summary_lifecycle.py tests/test_npc_fallback.py tests/test_review_blockers_npc_preparation.py tests/test_spec302_perception.py tests/test_turn_delivery.py → exit 0 (161 testes, todos verdes)
paridade externa: git archive main → scratchpad; o mesmo roteiro (4 cenários × 3 turnos, MockLLM, seeds fixos) em main e spec-318 com flags legadas; diff de _state_to_save_data → 0 diferenças (controle main×main: 0)
sonda _infer_role("Marta", …) → Guarda/Guarda/Capitão/Ladrão nas 4 frases sem papel
sonda _complete_sheet com cache-hit de NPC existente → 3 falhas, stub duplicado permanente (legado: só o canônico, em cena)
sonda _deterministic_story_fallback com nota [ECOS DO MUNDO] inline → instrução "teça…" e "FATO:/BOATO:" visíveis
```
