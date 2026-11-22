# SPEC-422 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> Rodada 1 (única). Pouso com `RPG_ARCHIVE_RECORD=off` liberado; P2-1 antes de promover a `on`.
> **Revisor:** Opus 5.5 / Sol (spec-reviewer) · **Data:** 2026-11-22 · **Commit revisado:** `59dcdeca`

## Escopo

Branch `spec-422`, `git diff main...HEAD` (commits `9f7d7afd`, `7371770d`, `c465f1bd`, `1379a1b9`,
`59dcdeca`; `f3e39f77` só aprova a spec). Lidos inteiros: `services/archive_record.py`,
`tests/test_archive_record.py`, o diff de `agents/archivist.py`, `agents/storyteller.py`, `state.py`,
`services/latency_flags.py`, `config/flags.yaml`, `observability/events.py`, `docs/operacao/EVENTOS_DE_LOG.md`,
`docs/spec422/eval-r12a.md`, `tests/size_budget.json`, `tests/fixtures/spec382_node_golden.json`.
Lidos no source para conferir as alegações: ramo de sucesso, fallback de texto e `except` de
`_archive_node` (`archivist.py:927-1204`), `_story_rest_passage`, `_story_roll_encounter`,
`_story_fauna_to_signal`, `_apply_proposed_rumors`, `enrich_node`, `persistence._state_to_save_data`/`_raw_to_state`,
incremento de `turn_count` (`campaign_manager.py:351`, `turn_pipeline.py:41`).
Fora: smoke com chave real e staging (§6, pendentes por desenho), playtest offline da Etapa 5 e o
`evals run` de R12(a) (alegações do executor, não reproduzidas: RAM em 2,8 GB).

## Respostas aos pontos do coordenador

1. **`off` = hoje.** (a) O diff do golden só toca as 8 linhas `"events"` dos 8 casos `campaign_*`;
   nenhum `state`/`result`/`trace`/`files` mudou. (b) Reproduzido: com o `_log_event(... "trigger" ...)`
   de `archivist.py:662-667` removido e o golden da `main` restaurado, `test_spec382_node_golden.py -k campaign`
   = 8 passed. A diferença é só o log novo. (c) Regravar é aceitável: R9 manda logar o gatilho sempre que o
   gate mantém, sem depender da flag, e I1 fala de estado e chamadas ao LLM, não de logs. O golden é
   fixture de `tests/` (não `evals/` protegido), e a regravação ficou restrita ao digest que o log muda.
   Se o coordenador quiser I1 estrito também nos logs, a alternativa é logar `archivist.trigger` só com
   `shadow`/`on`: a medição de R9 acontece na fase `shadow` (§6.5), então nada se perde. Não acho
   necessário. O payload é `reasons=[...]` de `TRIGGER_REASONS` (`archive_record.py:25-34`, `:231-250`):
   só nomes fixos, sem texto de jogador nem de NPC.
2. **Extrações.** `summary_rejection_rows` é a soma dos três blocos e cobre os três sites (inicial,
   fallback de texto, sucesso). O golden `spec422_rejection_rows_golden.json` exercita os três cenários com
   linhas não vazias (o teste exige `memory_rejections` não vazio), e o oráculo literal cobre as 5
   combinações e o `turn` em string. `story_marks`/`_archive_low_mark`: as 28 combinações
   (2 políticas × 7 variações × 2 regiões) comparam contra a cópia literal, e cada conjunção da condição
   antiga tem uma variação que a derruba. Não achei ramo extraído sem cobertura. A mutação M4a ("marca sempre")
   é morta por esse oráculo.
3. **T1.** Fatos canônicos: `authoritative_records` (eventos novos + `memory_canonical_facts`) passam pelo
   mesmo `persist_records` (`archivist.py:1117-1125`). I2 confere o mesmo conjunto de `memory_id`, e a
   mutação M2b (T1 sem registros) é morta. A fila de NPC é drenada antes da decisão (`_drain_npc_memory`,
   `:733-747`). O retry é anterior (`:670-731`), e `archive_due` é o de hoje (`:1198`); M2c é morta. Exclusões: encontro com
   combate retorna antes de `_story_assemble_quests`; armadilha/rastro/social deixam `t.enc` (M3a morta);
   sinal de fauna, morte, beat, NPC introduzido, missão, evento proposto e rumor têm teste (M3b–M3h, M3g mortas);
   conflito e cadência excluem no arquivista (M5, M6 mortas); conflito com `suppress` nunca vira T0 (M11 morta).
   Virada de dia com fatos e evento de mundo **não** excluem T1, como a spec declara (tabela de R1): os fatos
   vão ao ledger, mas o resumo do descanso não os menciona (P3-4). `enrich` depois do narrador só cria fichas de
   NPC introduzido (já exclui) e replan pós-entrega: não abre gancho novo num descanso.
4. **T0.** Confirmado no código: com `suppress_free_facts` e sem conflito, o ramo de sucesso usa
   `current_summary` (`archivist.py:1137-1139`), zera os fatos `inference` (`:1115`) e só grava prosa com
   `not suppress_free_facts` (`:1191`). O fallback de texto também não faz a segunda chamada (`:1027-1029`).
   A resposta é descartada inteira e I3 prova com `on == off` em dicionário inteiro. A única diferença real
   fica no caminho de **exceção** do LLM (P3-3).
5. **Estado e persistência.** `state.py:933` só tipa. `persistence.py` não tem diff e salva por lista explícita,
   sem `archive_record` (`_state_to_save_data`, `persistence.py:650-680`). O teste I4 afirma `"archive_record" not in raw`
   com o campo presente no estado, então a afirmação não é vazia. Os presenters também não expõem `archive_*`.
   A marca não vaza para o turno seguinte: não é salva, e mesmo em memória `_valid_rest_mark` exige
   `turn == turn_count`, que sobe todo turno (M4b morta). Não há writer novo: `archive_record.py` só calcula.
   O teste I4 basta para esta entrega (P3-2 sobre o rótulo).
6. **`shadow`.** `decide` loga e devolve `None` (`archive_record.py:151-162`): o LLM é chamado e o resultado
   gravado é o dele (`archivist_last_run` avança, testado). A mutação M9 ("shadow aplica") é morta.
   `record_shadow` só leva `kind`, `would_skip` e `reason` (strings fixas).
7. **Desvios.** `"blocked"` só aparece no descanso bloqueado e alimenta só a frase de R4: aceitável. O
   `trigger` em `_archive_node` não muda a decisão, e o caminho adiado continua sem log: aceitável.
   `llm = None` em T0/T1: os únicos usos depois são `:1012` (só no `else`) e `:1032` (só quando
   `result` não é `MemoryUpdate`, impossível com o registro em Python; uma `ValidationError` cairia no
   `except`). Nada depende do objeto.
8. **Mutações** (rodadas por mim, 23): 21 mortas. Sobreviveram M3i (remover `not t.dest`, mutante equivalente:
   descanso e viagem são `if/elif` em `storyteller.py:1365-1368`) e **M3j** (`rumor_new=False` no
   narrador; P2-1). As quatro pedidas (`decide` sempre `None` = M1; T1 sem registros = M2a/M2b; T1 aceitando
   gancho = M3a–M3h; marca sempre presente = M4a) foram todas mortas.
9. **Evals.** `git diff --stat main...HEAD -- evals/` está vazio. `docs/spec422/eval-r12a.md` diz com
   honestidade que `memory_context` não exercita o arquivista e que a igualdade vem da construção.
10. **Guard/tamanho/flags.** `isinstance(result, MemoryUpdate)` e `try/except` intactos, e nenhum
    `with_structured_output` novo. `size_budget.json`: `archivist.py` 1237→1204, `storyteller.py` 3020→3019,
    `_archive_node` 666→626, `state.py` +1 com o motivo no commit. Funções novas ≤ 60 linhas. A flag está
    registrada (`release`, `off`, 2027-02-28) e os 3 eventos estão em `observability/events.py` e
    `EVENTOS_DE_LOG.md`. `test_clock_asserts.py` está verde. `dup_helpers`: só colisão de nome (`classify`,
    `decide`), sem duplicata semântica.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `agents/storyteller.py:2941-2948`; `tests/test_archive_record.py:319-338` | A ligação `rumor_new = updates["world_sim"] is not _sim_before` não tem teste. Trocá-la por `rumor_new=False` (M3j) deixa a suíte verde. O código está certo pela leitura (`_apply_proposed_rumors` só reatribui `world_sim` quando aceita, `storyteller.py:967-968`). Mas a §4 Etapa 2 pedia as variantes no nível do narrador, e as de fauna, morte, beat, missão, evento e rumor ficaram só no `SimpleNamespace`. Os nomes de atributo existem em `_StoryTurn` (conferido), então o único fio não provado é o do rumor. | Teste no `storyteller_node` com `RPG_RUMORS_PROPOSED=on` e um `proposed_rumors` aceito num descanso, afirmando a marca ausente. Pode entrar junto com a spec R12(b); é obrigatório antes de promover a `on`. Com `off` não há efeito. |
| P3-1 | P3 | `specs/SPEC-422-…md` §3 "Desvios (4)" | O texto diz que só `campaign_combate_off` mudou. O commit `59dcdeca` regravou os 8 casos `campaign_*` (só o digest `events`). | Corrigir o texto para "8 casos `campaign_*`, só `events`; revertido o log, o golden antigo passa". |
| P3-2 | P3 | `tests/test_archive_record.py:691-697`, `:713-714` | `test_off_identico_ao_head` não é o roteiro de 4 turnos de I1: só compara estado com e sem marca, em `off`. Na prática, a prova de I1 é o golden da SPEC-382 (66 casos, state/result/trace inalterados). Em I4, "save antigo sem o campo carrega" tira `archivist_last_run`, não o campo novo, e fica verdadeiro por construção. | Registrar na spec que I1 se apoia no golden da SPEC-382 e trocar o comentário de I4 por "persistence.py sem diff; o campo nunca é salvo". |
| P3-3 | P3 | `agents/archivist.py:1202-1204` | Com `on`, T0 deixa de passar pelo `except`. Hoje, quando o LLM levanta, o nó devolve só `event_updates`: `narrative_rejections` sobrevive e os registros não são gravados. Com `on`, T0 grava como no ramo de sucesso. A mudança vai na direção segura, mas I3 só cobre o sucesso. | Uma linha em §7 Riscos. |
| P3-4 | P3 | `services/archive_record.py:177-199` | O resumo T1 não cita os fatos do dia nem os eventos do tick do descanso (eles ficam só no ledger, como R1 declara). R4 diz "sem número na superfície", mas `clock_label` legado rende "Dia N · Período". A spec se contradiz; I8 passa. | Incluir os dois casos nas fixtures da suíte R12(b) (continuidade iv) e ajustar o texto de R4. |

## Evidência verificada

```text
| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_archive_record.py::test_archivist_rejeicoes_iguais_ao_golden_do_head | verde | verde | FAIL: nao prova a mudanca |
| tests/test_archive_record.py::test_bump_archive_deterministic | vermelho | verde | OK |
| tests/test_archive_record.py::test_descanso_bloqueado_usa_frase_do_clima | vermelho | verde | OK |
| tests/test_archive_record.py::test_descanso_com_cadencia_vencida_usa_llm | verde | verde | FAIL: nao prova a mudanca |
| tests/test_archive_record.py::test_descanso_com_conflito_usa_llm | verde | verde | FAIL: nao prova a mudanca |
| tests/test_archive_record.py::test_descanso_com_indice_fora_mantem_pendentes | vermelho | verde | OK |
| tests/test_archive_record.py::test_descanso_cronica_so_marcos | vermelho | verde | OK |
| tests/test_archive_record.py::test_descanso_drena_fila_de_npc_como_hoje | vermelho | verde | OK |
| tests/test_archive_record.py::test_descanso_nao_chama_llm_do_arquivista | vermelho | verde | OK |
| tests/test_archive_record.py::test_descanso_registra_todos_os_fatos_canonicos | vermelho | verde | OK |
| tests/test_archive_record.py::test_dois_descansos_nao_acumulam_frase | vermelho | verde | OK |
| tests/test_archive_record.py::test_fallback_llm_off_e_shadow_como_hoje | verde | verde | FAIL: nao prova a mudanca |
| tests/test_archive_record.py::test_flag_registrada_default_off | vermelho | verde | OK |
| tests/test_archive_record.py::test_frase_de_descanso_sobrevive_aos_saneadores | vermelho | verde | OK |
| tests/test_archive_record.py::test_marca_ausente_com_off | verde | verde | FAIL: nao prova a mudanca |
| tests/test_archive_record.py::test_marca_ausente_por_gancho_estruturado | vermelho | verde | OK |
| tests/test_archive_record.py::test_marca_ausente_quando_ha_gancho_ou_encontro | verde | verde | FAIL: nao prova a mudanca |
| tests/test_archive_record.py::test_marca_de_outro_turno_ignorada | verde | verde | FAIL: nao prova a mudanca |
| tests/test_archive_record.py::test_marca_rest_bloqueada_pelo_clima | vermelho | verde | OK |
| tests/test_archive_record.py::test_marca_rest_so_no_descanso_sem_gancho | vermelho | verde | OK |
| tests/test_archive_record.py::test_marca_shadow_tambem_e_emitida | vermelho | verde | OK |
| tests/test_archive_record.py::test_off_identico_ao_head | verde | verde | FAIL: nao prova a mudanca |
| tests/test_archive_record.py::test_projecao_adiada_sem_efeito | verde | verde | FAIL: nao prova a mudanca |
| tests/test_archive_record.py::test_rejeicao_sem_conflito_igual_ao_llm | vermelho | verde | OK |
| tests/test_archive_record.py::test_round_trip_depois_do_registro_deterministico | vermelho | verde | OK |
| tests/test_archive_record.py::test_shadow_chama_llm_e_registra_would_skip | vermelho | verde | OK |
| tests/test_archive_record.py::test_story_marks_archive_low_igual | vermelho | verde | OK |
| tests/test_archive_record.py::test_summary_rejection_rows_igual_ao_bloco_antigo | vermelho | verde | OK |
| tests/test_archive_record.py::test_trigger_reasons_lista_fixa | vermelho | verde | OK |
red_green: 20/29 OK
```

Os 9 verde/verde são guardas de "não muda": equivalência de extração, `off`, cadência, conflito,
projeção adiada, FallbackLLM e marca ausente. Têm de passar na `main` por definição. Todos foram
validados por mutação: M5, M6, M7, M9, M11, M12 e M4b os derrubam.

Mutações (script em scratchpad, arquivos restaurados com `git checkout` depois; worktree limpo):

```text
M1 decide sempre None ............ KILLED (test_descanso_nao_chama_llm_do_arquivista)
M2a T1 sem frase ................. KILLED   M2b T1 sem registros autoritativos ... KILLED (I2)
M2c T1 zera archive_due .......... KILLED (I5)
M3a encontro ..................... KILLED   M3b fauna ... KILLED   M3c beat ... KILLED
M3d NPC introduzido .............. KILLED   M3e missão .. KILLED   M3f evento . KILLED
M3g rumor (helper) ............... KILLED   M3h morte ... KILLED
M3i sem `not t.dest` ............. SURVIVED (equivalente: rest/travel são if/elif)
M3j rumor_new=False no narrador .. SURVIVED  -> P2-1
M4a marca sempre presente ........ KILLED   M4b marca ignora turno ... KILLED
M5 sem cadência .. KILLED   M6 sem conflito .. KILLED   M7 ignora adiada .. KILLED
M8 T1 avança last_run ... KILLED   M9 shadow aplica ... KILLED   M10 frase acumula ... KILLED
M11 T0 com conflito ..... KILLED   M12 marca com off .. KILLED   M13 T1 grava prosa/fato ... KILLED
golden SPEC-382 sem o log `archivist.trigger` + fixture da main: 8 passed (-k campaign)
```

## Correções aplicadas

Nenhuma nesta rodada (revisão só leitura).

## Pendências

- P2-1: teste do fio `rumor_new` no narrador, antes da promoção a `on` (executor da SPEC-422 ou spec R12(b)).
- P3-1..P3-4: texto da spec e nota de risco; fixtures de R12(b) com fatos do dia e evento de tick num descanso.
- Fora desta revisão por desenho: smoke §6 com chave, `shadow` em staging e A/B (D1, `EVAL_AUTHORING_REQUIRED`).

## Comandos rodados

```text
bash scripts/dev/red_green.sh 422 → 20/29 OK (9 guardas verde/verde, todas validadas por mutação)
pt.sh -n 0 tests/test_spec382_node_golden.py → 66 passed (isolado)
pt.sh -n 0 test_spec382_node_golden.py -k campaign (sem log trigger + golden da main) → 8 passed
pt.sh -n 0 test_archive_record test_archivist_policy test_archivist_facts test_npc_memory test_memory_provenance test_archived_state_persistence test_size_budget test_clock_asserts → 136 passed
pt.sh -n 0 test_flag_registry test_log_event_registry test_telemetry_redaction test_npc_two_phase → 53 passed
mut422.py (23 mutações, test_archive_record.py, -n 0) → 21 killed, 2 survived (M3i equivalente, M3j = P2-1)
git diff --stat main...HEAD -- evals/ → vazio
dup_helpers.py --diff main...HEAD → só colisões de nome (classify, decide)
ruff check / format --check nos arquivos tocados → limpos
```
