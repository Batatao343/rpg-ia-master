# SPEC-422 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> Histórico: rodada 1 em `59dcdeca` (follow-ups P2-1, P3-1..P3-4); rodada 2 em `f1caa481` (follow-ups tratados, aprovada); rodada 3 em `436197b8` (extração `state_archive.py`; só o follow-up P3-5, de registro do arquivo novo, que não bloqueia o pouso).
> **Revisor:** Opus 5.5 / Sol (spec-reviewer) · **Data:** 2026-11-22 · **Commit revisado:** `436197b8`

## Conferência da rodada 3 (`436197b8`, `ArchiveMarks` em `state_archive.py`)

Motivo: o `land_check` recusou `state.py` 1082 → 1083. As três marcas (`archive_due`, `archive_low`,
`archive_record`) saíram para `state_archive.ArchiveMarks(TypedDict)` e `GameState` passou a herdar dele.
Conferido com evidência; nenhum arquivo do worktree foi editado (scripts e plugin em scratchpad).

1. **Chaves e grafo real.**
   - `typing.get_type_hints(GameState)` com o `state.py` da `main` × o da branch: mesmo conjunto (99 → 100;
     só entra `archive_record`, `dict | None`) e mesmos tipos (a diferença é só o nome do módulo carregado).
   - `__total__` `True`/`True`; `__required_keys__` só ganha `archive_record`; `__optional_keys__` idêntico.
   - No Python 3.13, `GameState.__annotations__` inclui as chaves herdadas.
   - Grafo real (`main.app`, MockLLM, `RPG_ARCHIVE_RECORD=on`): `app.channels` contém as três chaves.
   - Num descanso, a marca emitida pelo `storyteller` chega ao `archivist` por
     `storyteller → enrich → archivist` e vale T1 de ponta a ponta. Ela foi forçada via spy em
     `story_marks`, porque a ação do primeiro turno do mock traz `quests` e corretamente não marca.
   - O spy em `decide` viu `archive_record={'kind':'rest','turn':1}` e `archive_due=True`, e o resumo final
     termina com "O herói descansou em Nova Arcádia; …".
2. **Introspecção e consumidores.**
   - `Grep` de `__annotations__`/`get_type_hints`/`__required_keys__`/`__optional_keys__` no repo inteiro:
     só testes. Os quatro que leem `GameState.__annotations__` (`test_archived_state_persistence`,
     `test_art_state_persistence`, `test_spec300_persistence_api`, `test_spec304_roster`) estão verdes.
   - `project_index/generator.py` não extrai campos de `GameState` (o `ClassDef` só vira símbolo e
     escopo), e `state_ownership.yaml` é curado e não cita as três marcas. O índice não perde nada e nenhum
     gate depende disso.
   - Mas quatro listas de texto que nomeiam `state.py` não conhecem o arquivo novo (P3-5).
3. **Persistência.** `git diff main -- persistence.py` vazio. `archive_due` continua salvo e carregado
   (`persistence.py:680`, `:1030`); `archive_low`/`archive_record` continuam fora da lista explícita; save
   antigo carrega (testes de persistência verdes).
4. **Tipos.**
   - `type_gate.py --files state.py state_archive.py` rc 0; `basedpyright state.py state_archive.py`
     = 0 errors.
   - A herança não cria erro nem relaxa nada: a totalidade e as chaves obrigatórias são idênticas.
   - **Não rodei** o gate cheio (`land_check --only types`): ele pede ≥ 3 GB livres e não pode rodar em
     paralelo com pytest, e havia 1,9–2,0 GB com a suíte completa rodando neste worktree. Fica com o
     coordenador no pouso.
5. **Import.** `state_archive.py` só importa `typing` (o teste AST confere), e o único importador é
   `state.py:8`. Não há ciclo, e quem faz `from state import GameState` não muda.
6. **Regressão.**
   - `git diff main -- tests/fixtures/spec382_node_golden.json` vazio; golden SPEC-382 isolado: 66 passed.
   - `baseline_growth.py --base main`: "nenhum baseline cresceu".
   - 25 mutações por plugin (controle NOOP verde): 24/24 mortas.
   - Escopo pedido + `test_state_archive_marks` + os 3 leitores de `__annotations__`: 123 passed.
7. **Desenho: aceito.** Não é maquiagem.
   - É a rota que a regra de tamanho prescreve ("código novo vai em módulo próprio"), e a fronteira tem
     sentido: as três são marcas transitórias de grafo, escritas pelos emissores e lidas pelo arquivista.
     Só `archive_due` é persistida, e a herança mantém o contrato idêntico.
   - As alternativas são piores: subir o teto não é permitido, e cortar uma linha qualquer de `state.py`
     seria maquiagem.
   - O custo real é a dispersão do esquema em dois arquivos, que as listas de tooling ainda não conhecem
     (P3-5).

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P3-5 | P3 | `scripts/ci_eval_scope.py:16`, `scripts/dev/eval_publish.py:30-38`, `project_index/domains.yaml:53-57`, `pyproject.toml:163-172` | `state.py` está nomeado nessas listas (escopo de eval do CI, `PRODUCT_FILES` do publish, domínio `state_rules`, `include` do basedpyright) e `state_archive.py` não. Uma mudança futura só nele não dispara o escopo de eval de IA nem o gate de tipos. | Acrescentar `state_archive.py` às quatro listas, no próximo toque ou numa spec de tooling (o `ci_eval_scope` pode pedir o papel de governança de eval). Não bloqueia o pouso. |

## Conferência da rodada 2 (`c991efa6..f1caa481`)

Decisão do coordenador (22/11): `archivist.trigger` só sai com `shadow`/`on`. Conferido com evidência:

1. **Golden SPEC-382 intocado.** `git diff --stat main -- tests/fixtures/spec382_node_golden.json` vazio;
   `SPEC382_REGEN` ausente do ambiente; `tests/test_spec382_node_golden.py` isolado (`-n 0`) = 66 passed.
2. **`archive_record.log_trigger`** (`services/archive_record.py:166-172`): retorna cedo com `off`; com
   `shadow`/`on` loga `reasons=trigger_reasons(...)` (só nomes de `TRIGGER_REASONS`). `_should_archive`
   sem diff: a única mudança em `archivist.py` é trocar o `_log_event` inline pela chamada ao helper
   (`:662`). Mutação por plugin `-p` (re-exec do fonte mutado em memória, nenhum arquivo do worktree
   editado), "logar sempre": `test_off_nao_emite_eventos_de_registro` reprova. `record`/`record_shadow`
   com `off` já eram impossíveis (`decide` retorna `None` antes de logar) e o teste confere os três.
   O teste de `shadow` afirma só a presença de `archive_due`; a pertinência à lista fixa vem de
   `test_trigger_reasons_lista_fixa`. Suficiente.
3. **P2-1 fechado.** `test_marca_ausente_com_rumor_aceito_no_descanso` roda o `storyteller_node` com
   `RPG_RUMORS_PROPOSED=on` e rumor aceito (controle sem rumor emite a marca). Mutação M3j
   (`rumor_new=False`) por plugin: reprova esse teste. Sem mutação: verde.
4. **Spec.** R9 (só `shadow`/`on`), desvio (4), Riscos (T0 e exceção, P3-3), R12(b) (fixtures de fatos do
   dia/tick e `clock_label` legado, P3-4), I1 (prova = golden SPEC-382) e I4 (sem "save antigo") batem com
   o código. P3-1..P3-4 fechados.
5. **Regressão.** Mutações anteriores rodadas de novo por plugin (resultado em Evidência verificada).

Observação sem severidade: no worktree, `agents/archivist.py`, `services/archive_record.py` e
`tests/test_archive_record.py` estão com CRLF na cópia de trabalho (`git ls-files --eol`: `i/lf w/crlf`).
O índice e o commit estão em LF (`.gitattributes eol=lf`), então nada chega à `main`; só não estranhe
diff de EOL local.

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

Rodada 1 (`59dcdeca`). Todos fechados em `f1caa481`; ver "Conferência da rodada 2" e "Correções aplicadas".

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
| tests/test_archive_record.py::test_marca_ausente_com_rumor_aceito_no_descanso | vermelho | verde | OK |
| tests/test_archive_record.py::test_off_nao_emite_eventos_de_registro | verde | verde | FAIL: nao prova a mudanca |
| tests/test_archive_record.py::test_shadow_emite_trigger_com_motivos | vermelho | verde | OK |
red_green: 22/32 OK
```

A tabela continua válida na rodada 3 (`436197b8`): o commit só move três anotações de `state.py` e não
mexe em `test_archive_record.py`. Mutações rodadas de novo por plugin sobre `436197b8`:

```text
NOOP_AR (controle) ...................................... SURVIVED (esperado)
LOGALWAYS M3j M1 M2a M2b M2c M3a-M3h M4a M4b M5-M11 M13 ... 24/24 KILLED (todas rc=1)
grafo real main.app: canais archive_due/archive_low/archive_record presentes; marca do storyteller chega ao archivist (T1 de ponta a ponta)
get_type_hints(GameState) main x branch: só + archive_record; __total__ igual; __optional_keys__ igual
```

As três últimas linhas vêm da rodada 2 (`f1caa481`); as outras 29 ficaram iguais à rodada 1.
`test_off_nao_emite_eventos_de_registro` é a décima guarda verde/verde: com `off`, nada de log
novo, o que vale também na `main`. Foi validada por mutação ("logar sempre" a reprova).

Mutações da rodada 2 (plugin `-p mutplug` em scratchpad: re-exec do fonte mutado em memória, nenhum
arquivo do worktree editado; controles `NOOP_AR/AV/ST` verdes; todos os kills com rc=1, ou seja,
teste que falha, não erro de configuração):

```text
LOGALWAYS (log_trigger loga com off) ... KILLED (test_off_nao_emite_eventos_de_registro)
M3j rumor_new=False no narrador ........ KILLED (test_marca_ausente_com_rumor_aceito_no_descanso)
M1 M2a M2b M2c M3a-M3h M4a M4b M5 M6 M7 M8 M9 M10 M11 M13 ... 22/22 KILLED (M3g agora também pelo teste de rumor)
```

Os 9 verde/verde (rodada 1) são guardas de "não muda": equivalência de extração, `off`, cadência, conflito,
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

Todas em `f1caa481` (executor), conferidas na rodada 2:

- P2-1: `test_marca_ausente_com_rumor_aceito_no_descanso` (nível `storyteller_node`, rumor aceito + controle).
- P3-1: desvio (4) reescrito; o golden da SPEC-382 voltou ao da `main` (decisão do coordenador: trigger só em `shadow`/`on`).
- P3-2: I1 aponta o golden da SPEC-382 como prova; comentário de I4 corrigido.
- P3-3: linha em §7 Riscos (T0 e exceção do LLM).
- P3-4: R12(b) pede fixtures com fatos do dia/tick e `clock_label` legado.

## Pendências

- Nenhuma de código para o pouso com `off`.
- P3-5 (rodada 3): registrar `state_archive.py` em `ci_eval_scope.py`, `eval_publish.py`, `domains.yaml` e `[tool.basedpyright].include`.
- Gate de tipos cheio (`land_check --only types`): com o coordenador no pouso (não rodado aqui por RAM).
- Promoção a `on` continua dependendo de R12(b) (`EVAL_AUTHORING_REQUIRED`), `shadow` em staging, A/B e smoke §6 com chave (D1).

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
--- rodada 2 (f1caa481) ---
git diff --stat main -- tests/fixtures/spec382_node_golden.json → vazio; SPEC382_REGEN ausente
pt.sh -n 0 tests/test_spec382_node_golden.py → 66 passed
runmut.sh NOOP_AR NOOP_AV NOOP_ST LOGALWAYS M3j → controles verdes; LOGALWAYS e M3j KILLED
runmut.sh M1..M13 (22 mutações anteriores, por plugin) → 22/22 KILLED
pt.sh -n 0 test_archive_record test_archivist_policy test_archivist_facts test_npc_memory test_memory_provenance test_archived_state_persistence test_size_budget test_clock_asserts test_flag_registry test_log_event_registry test_telemetry_redaction → 163 passed
bash scripts/dev/red_green.sh 422 → 22/32 OK (10 guardas verde/verde, todas validadas por mutação)
--- rodada 3 (436197b8) ---
cmpkeys.py (state.py da main × branch) → hints: só + archive_record; total/optional iguais
pytest scratch test_realgraph_marks.py (main.app, MockLLM, on) → 1 passed (canais + marca chega ao archivist)
type_gate.py --files state.py state_archive.py → rc 0; basedpyright state.py state_archive.py → 0 errors
land_check --only types → NÃO rodado (RAM 1,9 GB, suíte completa em paralelo; gate pede ≥ 3 GB)
git diff main -- persistence.py tests/fixtures/spec382_node_golden.json → vazio
baseline_growth.py --base main → nenhum baseline cresceu
pt.sh -n 0 tests/test_spec382_node_golden.py → 66 passed
pt.sh -n 0 test_archive_record test_archivist_policy test_archived_state_persistence test_state_archive_marks test_size_budget test_art_state_persistence test_spec300_persistence_api test_spec304_roster → 123 passed
runmut.sh (25 mutações por plugin) → controle verde, 24/24 KILLED
```
