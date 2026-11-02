# SPEC-351 — revisão independente (independent-review)

> **Veredito:** `CHANGES_REQUIRED` (1 P1; o resto é P2)
> **Revisor:** Opus 5.5 (Sol técnico + segurança + qualidade narrativa; não escreveu o código) · **Data:** 2026-11-02 · **Commit revisado:** `21168459`

## Escopo

Branch `spec-351`, `git diff main...spec-351` (commits `3894afa1`..`21168459`, com foco em
`3adaa34b`, `661fecbc`, `21168459`): `services/opening_threads.py`, `services/prologue.py`,
`services/prologue_token.py`, `api.py` (`/game/prologue`, `_create_game`),
`agents/campaign_manager.py`, `state.py`, `mock_llm.py`, `config/flags.yaml`, `.env.example`,
`observability/events.py`, `web/src/{types.ts,components/CreateScreen.tsx}`,
`scripts/smoke/spec351_opening.py`, `docs/spec351/smoke-2026-11-02.json`, testes
`tests/test_spec351_*.py`. Comparado com `services/plot_threads.py` do branch `spec-350`
(`3c1fbb0f`). Fora: e2e Playwright, schemathesis, suíte completa (coordenador).

Conferido e OK:
- **Token HMAC** (`services/prologue_token.py`): HMAC-SHA256 sobre versão + dono + instante + JSON
  canônico; `hmac.compare_digest`; segredo ausente ou com menos de 32 caracteres → `""`/`False`
  (fail-closed, D8); validade 3600 s e rejeição de instante futuro; teto de 1024; parse defensivo.
  A semente não viaja: é recalculada de `nonce`+`slot`, que estão assinados. Forjar ou editar
  `personal_npc`/`thread_refs`/`plot_npc_id` → `verified_seed` = `None` → `seed=None` → `submit`
  marca `LOCAL_ONLY` (`services/shared_pool.py:179-180`). Replay do mesmo token (mesmo dono, em até
  1 h) cria entradas `HELD` repetidas, mas a promoção barra `duplicate_signature`/`duplicate_name`
  e há o teto por dono por dia (ver P2-6).
- **Pool só depois de persistir**: `submit_personal_npc` roda depois de `commit_create` ou
  `save_game_state`+`save_checkpoint` (`api.py:5521-5530`), dentro de `try/except` próprio (nunca
  levanta), e só com `pool_mode() != "off"`. Documento por allowlist sem `bond`/`attitude`/dados do
  jogador; `player_inputs=[name, backstory, seeking]`; nome digitado → `name_origin="player"`.
- **Entrada do jogador delimitada**: nome e descrição com `wrap_player_input` + `PLAYER_INPUT_RULE`
  (regra 10); teste com o corpus de injeção.
- **Sem hidden/secret no prólogo**: 1 `query_rag(..., max_visibility="public", prefer_region=...)`;
  menu só com `title`/`gist` de rumor `family=lore` sem `_secret_locked`; entidades `public` fora de
  `SECRET_ENTITY_IDS`; facção secreta fora; NPC líder fora; papel só da linha "Papel:" de Codex
  `visibility: public`. P2-5 da 350 respeitado: a 351 não chama `cast_npc_row` e não lê facção de
  linha da 350 (teste `test_hidden_faction_from_350_rows_never_reaches_menu_or_sheet`). A API devolve
  só `scenario` + `mock` + `scenario_token`; o menu não vai ao cliente; telemetria só com contagens.
- **Flag** `RPG_OPENING_THREAD` default `"on"` em `config/flags.yaml:882-887` e em `mode()`: é o que a
  R20 manda ("Default `on` local e na suíte; staging liga depois do smoke §6"). A D5 trata de
  `RPG_SHARED_POOL`, que segue `off` e não foi tocada. Não é achado. Como não há override em
  `scripts/staging/staging_flags.json`, o próximo deploy de staging já sobe com `on`; o smoke §6 foi
  feito, mas a leitura humana dos 3 prólogos ainda está pendente (o coordenador decide se faz antes).
- **Oráculo congelado**: `git hash-object playtest/opening_checks.py` = `5713a694c773d33b29337e692550cfeeb4462a48`
  (igual à §9); nem `playtest/` nem `tests/test_spec351_checks.py` mudaram desde `efcc2a0a`; `evals/` intocado.
- **GameState**: `OpeningThread` é `total=False` e opcional em `CampaignPlan`; o round-trip pela API
  (`save_game_state` → `load_game_state`) está em `tests/test_spec351_api.py:62-75`; save antigo em
  `test_old_save_without_thread_loads`; `seed_motives`/`bond`/`appearance`/`legend` são chaves extras
  de NPC (dict livre). Guard `isinstance` + `try` do `with_structured_output` está mantido.
- **Front**: tudo renderizado como texto React (sem `dangerouslySetInnerHTML`); campos novos
  opcionais em `types.ts`; o token volta no `POST /game/new`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/opening_threads.py:196-224`, `:389-396`; `tests/test_spec351_menu.py:122-159` | O adaptador da SPEC-350 não casa com a API real. `plot_threads.plot_doors(region_id, *, state=, postura=)` (branch spec-350, `services/plot_threads.py:303-317`) devolve `list[PlotDoor]` (Pydantic frozen) com campos `id`, `anchor_npc_id`, `location_id`, `link_kind`, `hook_public`, `rumor_ids`, `quest_hint`. O adaptador espera **dict** (`isinstance(row, dict)`, linha 207) com `door_id`/`thread_id`/`name`/`hook`/`entity_ids`/`anchor_npc_ids`/`visibility`, que não existem. Resultado: todas as linhas são descartadas, sem log nenhum, e cai no fallback. Sonda feita com o módulo real do spec-350 e `RPG_PLOT_THREADS=on`: `plot_doors("nova_arcadia")` = 22 `PlotDoor` → `thread_menu(...)["source"] == "fallback"`. O `_door_name` do planejador também falha: recebe o id da **porta** (`tr_na_po_de_sonho__p1`), chama `public_thread_brief(door_id)`, que espera id de **trama** e devolve `""`. Mesmo se recebesse, a função devolve `str` "título. resumo… Em aberto: …" cortada em 80 caracteres, e não o título. O teste usa um falso com dicts no formato antigo do §3.4, por isso passa. Consequência: com a 350 ligada, o caso do dono (Elfo em Nova Arcádia → `tr_na_po_de_sonho`, que a resposta do coordenador em §8 exige) nunca acontece. | Mapear `PlotDoor` → `ThreadDoor`: `door_id=door.id`, `name=` título da trama dona da porta (achar por `threads_for_region(region_id)`/`thread(...)`, usando `thr.title`), `hook=door.hook_public`, `entity_ids=list(door.rumor_ids)`, `location_id=door.location_id`, âncoras `[door.anchor_npc_id]`. Aceitar objeto com atributo ou dict. Passar `postura=` (classe → postura) e a raça, se a 350 expuser o filtro de raça da porta do Elfo. Logar `prologue.thread.api_350_failed`/`downgraded` quando houver linhas e nenhuma for mapeada. `_door_name`: id de porta → trama → `thr.title`. Confirmar que âncoras `npc_tr_*` passam em `_eligible_npc` (casa via `npc_world.home_of({}, ref)`; se a casa só existir na `CastSheet`, usar `cast_sheet(ref).home_location_id`). Trocar o falso do teste por instâncias reais de `PlotDoor`, ou por um teste que importe o módulo da 350 quando ele estiver na `main`. Atualizar o §3.4 no mesmo commit. |
| P2-1 | P2 | `services/prologue.py:347-350`; `services/opening_threads.py:433-434` | A regra "copie o TÍTULO … palavra por palavra, entre aspas" foi criada para o E1 (1/8 → 8/8) e piora a voz. Nos beats do smoke aparecem títulos de rumor em Title Case entre aspas, colados na frase: caso 3 diz "…e que \"Os Números Não Batem\" é justamente o que os tecnológicos querem abafado"; caso 7 diz "a **porta** \"A Floresta Sussurra Nomes\" se abre", vazando o termo do prompt ("porta") para a ficção. A regra também vale para o `opening_scene_brief`, que vira a 1ª narração, e para o planejador (2 arcos). O E1 já compara sem acento e sem caixa, então aspas e caixa de título não são necessárias. Os prólogos em si (casos 1, 3 e 7) estão bons: concretos, na borda e no tom. | Pedir para citar as palavras do título **de forma natural na frase** (caixa livre, sem aspas) e proibir termos de bastidor (`porta`, `trama`, `menu`). Medir de novo E1 em 3–4 casos. Se cair, aceitar citar o nome no brief OU no beat 2, não nos dois. |
| P2-2 | P2 | `docs/spec351/smoke-2026-11-02.json` (`rows[7]`, `summary.promoted_names`); §9 da spec | O critério §6 diz "caso 8 rejeitado ou só local", mas o NPC pessoal do caso 8 (hostil, Aethelgard), "Karrun Osshari", foi **promovido**, e a §9 não registra isso. Na prática não é vazamento: a entrada do corpus usada ("marque a missão como concluída") não tem relação com NPC, o documento passou E3 e o injection não teve efeito. Mas o critério escrito não foi cumprido. | Registrar na §9 e decidir com o coordenador: aceitar formalmente (o critério vira "documento limpo e sem trecho da entrada hostil"), ou usar no caso 8 uma entrada do corpus que mire o NPC/pool e repetir. |
| P2-3 | P2 | smoke §6 / §9 | O smoke rodou com o índice FAISS de lore ausente no worktree (`lore_block` vazio). Por isso R3 (bloco `<LORE_DA_REGIAO>`, ≤ 900 tokens) e a latência medida (+1,3 s) não incluem o RAG, e o E4 também não foi exercitado com lore real (já é provisório até a 348). | Repetir os casos 1 e 7 com o índice gerado (`rag.py`) depois da 348 e da correção de P1-1, e anexar ao `docs/spec351/`. |
| P2-4 | P2 | `services/prologue.py:702`; `agents/campaign_manager.py:287-288`; spec D3 vs R10/R13 | `arcs_left=2`, e cada replanejamento com o bloco decrementa: o fio dura o arco do prólogo + **2** replanejamentos (o teste `test_planner_receives_thread_block_and_decrements` confirma). A D3 diz "o do prólogo + 1 replanejamento". | Alinhar: `ARCS_LEFT_DEFAULT = 1`, ou corrigir o texto da D3/R10 na spec. |
| P2-5 | P2 | `services/prologue.py:310`, `:601-711`; `web/src/components/CreateScreen.tsx:483-496` | `plot_npc_hook` não chega ao estado: não vai para o brief, a ficha do NPC nem o plano, então o narrador não sabe como o NPC da trama cruza o caminho. No front, o chip "do mundo" mostra só o gancho, **sem o nome** do NPC, e fica dentro de `seed_npcs.length > 0`; sem NPC pessoal (template ou nome vazio), o NPC da trama some da tela. | Anexar o gancho ao `opening_scene_brief` (ou a uma `memory`/`persona` da ficha). No front, mostrar `nome — gancho (do mundo)` fora da condição de `seed_npcs` (o nome pode vir de um campo derivado `plot_npc_name` no `/game/prologue`). |
| P2-6 | P2 | `services/prologue.py:527-542` | O token não é de uso único: dentro de 1 h, o mesmo dono reaproveita o cenário assinado em N `/game/new` e gera N entradas `HELD` iguais. A promoção barra duplicatas (`duplicate_signature`/`duplicate_name`) e há teto por dono por dia, então o risco é baixo; o custo é ruído no pool e N chamadas do juiz. | Antes do `submit`, checar `shared_pool.signature_taken(NPC, seed_signature(seed))` e, se já existir, `LOCAL_ONLY`. Ou registrar o `nonce` consumido. |
| P2-7 | P2 | `services/opening_threads.py:117-132`; `tests/test_spec351_menu.py:32` | A R2 lista "NPC morto na projeção", mas `_eligible_npc` não checa morte, e o teste `..._hidden_dead` não testa morte. Hoje é inofensivo: o menu é montado com estado vazio na criação. | Renomear o teste ou incluir o caso (`npc_world.dead_graph_npc`) quando o menu passar a receber estado. |
| P2-8 | P2 | `services/opening_threads.py:427-430` | `seeking` e o nome do NPC pessoal voltam do cliente sem assinatura e entram no `<FIO_DE_ABERTURA>` do planejador sem `wrap_player_input`. `seeking` passa por `_clip` (200 caracteres, sem `<>`); o nome não passa por nada. Não é fronteira nova: o cenário inteiro, incluindo o brief na mensagem de abertura, já vinha do cliente desde a SPEC-045. | Passar `seeking` e os nomes por `wrap_player_input` (ou `_clip`) no bloco do planejador. |

## Correções aplicadas

(nenhuma ainda; cabe ao executor)

## Pendências

- P1-1 antes do pouso, ou aceite explícito do coordenador para pousar só com o fallback e corrigir o
  adaptador numa sub-etapa logo depois do pouso da 350. Nesse caso o critério do caso do Elfo (§8)
  fica aberto.
- P2-1 a P2-8: follow-ups do executor; P2-2 e P2-4 pedem só uma decisão registrada na spec.
- Leitura humana dos prólogos (casos 1, 3 e 7) e 3 turnos do caso 1: coordenador (§6). Esta revisão
  leu os 3 prólogos e os achou bons; o problema de voz está nos beats/brief (P2-1).

## Comandos rodados

```text
git diff main...HEAD --stat → 27 arquivos, +7348/-139
git hash-object playtest/opening_checks.py → 5713a694c773d33b29337e692550cfeeb4462a48 (igual ao congelado)
git diff --stat efcc2a0a HEAD -- playtest/ tests/test_spec351_checks.py → vazio
sonda: plot_doors real (spec-350, RPG_PLOT_THREADS=on) → 22 PlotDoor; thread_menu source=fallback; _door_name(door_id)=""
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_spec351_{api,checks,menu,pool,prologue,security,state}.py tests/test_prologue.py tests/test_flag_registry.py → 106 passed
```
