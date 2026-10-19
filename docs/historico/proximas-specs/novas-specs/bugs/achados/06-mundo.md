# Auditoria de bugs funcionais — Área 06: Mundo (2026-10-15)

**Escopo coberto:** `world_utils.py` (inteiro), `services/npc_layers.py`, `party.py`, `agents/npc.py` (estado de NPC/quests/relação), trechos de `agents/storyteller.py` (viagem/descanso/encontro/quests/reputação), `agents/router.py::_combat_gate`, `agents/combat.py` (fuga/`_apply_flee_travel`, `_reflect_scene_allies`, budget), `services/quest_log.py`, `services/objectives.py`, `services/event_processor.py`, `services/world_validators.py`, `services/rule_engine.py`, `services/graph_resolver.py`, `services/ecology.py`, `services/exploration.py`, `services/social_direction.py`, `agents/world_simulator.py`, `data/world_map.json` (checado programaticamente), `data/weather.json` (consistência).

**Não coberto (tempo):** `services/discovery.py` (bestiary knowledge), `data/traits.json` (só uso), `services/chronicle.py` além de `append_entry`, `api.py` views de mapa/fações, cascata `world_rules.json` regra a regra.

**Resumo:** 0 crítica · 2 alta · 9 média · 6 baixa (17 achados) + descartados.

Mapa: 35 nós, ids únicos, arestas simétricas, `travel_times` simétricos, interiores com saída só pelo pai, tudo alcançável a partir do início, `weather.json` consistente (sem pesos zero, todos os `start` válidos). Nada a reportar nessas checagens (ver Descartados).

---

### BUG-06-01 — `is_travel_intent` casa ações que não são viagem e o storyteller responde "Não há rota direta"
- **Severidade:** alta
- **Categoria:** regra-divergente
- **Local:** `world_utils.py:69-98` (regex), consumido em `agents/storyteller.py:299-319`
- **Evidência:** a regex aceita verbo de movimento + até 5 palavras + `(para|ate|a|rumo a|em|n[oa]s?)` + qualquer token. `a` e `em` são preposições genéricas ("volto **a** falar", "sigo **em** frente", "entro **em** combate"). Com `travel_intent=True` e nenhum destino conectado, `invalid_travel_message` devolve a recusa e o storyteller **retorna sem chamar a LLM** (mensagem fixa, sem avançar o turno narrativo).
- **Reprodução (executada):** `is_travel_intent` → `True` para `"volto a falar com o ferreiro"`, `"sigo em frente"`, `"entro em combate com o guarda"`, `"Eu atravesso a ponte devagar"`. Em `nova_arcadia`, `invalid_travel_message(w, "sigo em frente")` = `"Não há rota direta a partir de Nova Arcádia. Saídas conectadas: Anel Dourado, ..."`.
- **Impacto:** o jogador digita uma ação de exploração/cena comum (rota STORY) e recebe uma recusa de viagem enlatada; a ação é perdida.
- **Correção sugerida:** exigir destino resolvível: só tratar como intenção de viagem quando o token após a preposição casar um nome de local do mapa (ou `find_travel_destination`), ou remover `a|em|n[oa]s?` do conjunto genérico. Recusar apenas quando o alvo parece um topônimo desconhecido.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_fase0.py`, `tests/test_mapa_interiores.py`, `tests/test_grounding_boundaries.py` (nenhum cobre "sigo em frente"/"volto a falar").

### BUG-06-02 — "Vou ao <local>" (contração "ao") não é reconhecido como viagem; a narração descreve chegada sem mover o jogador
- **Severidade:** alta
- **Categoria:** estado-inconsistente
- **Local:** `world_utils.py:96` (alternativa `(?:para|ate|a|rumo\s+a|em|n[oa]s?)` sem `ao|aos|pro|pra|pela`)
- **Evidência:** `_fold_txt` transforma "à" em "a", mas "ao" permanece "ao" e não casa nenhuma alternativa.
- **Reprodução (executada):** em `nova_arcadia`, `is_travel_intent("vou ao Anel Dourado")` = `False`, enquanto `find_travel_destination(w, "vou ao Anel Dourado")` acha `na_anel_dourado`; "vou para ..." e "Vou até ..." = True. Com intent False o storyteller não chama `apply_travel` (`storyteller.py:302-305`): relógio, `visited`, `current_location_id`, clima, fações e reset de cena não mudam, mas a LLM é instruída a narrar o turno normal (pode descrever a chegada).
- **Impacto:** "Vou ao mercado/porto/templo" é a forma mais comum em PT-BR; divergência entre narrativa e estado canônico (local, hora).
- **Correção sugerida:** incluir `ao|aos|pro|pra|pelo|pela|a[oà]s?` no conjunto de preposições (ou testar `find_travel_destination` independentemente da preposição quando há verbo de movimento).
- **Confiança:** confirmado por execução (intent) / provável (narração de chegada)
- **Testes existentes relacionados:** nenhum (`rg "vou ao" tests` vazio).

### BUG-06-03 — Eventos derivados da cascata (`rule_engine`) são gravados com `turn = 0`
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `services/rule_engine.py:239-248` (`_new_event` fixa `"turn": 0`); `services/event_processor.py:295-298` e `:201-202` (só anexa ao log; nunca carimba o turno)
- **Evidência:** `_new_event(...)` → `"turn": 0`; o `event_processor` faz `event_log.append(d)` sem ajustar.
- **Reprodução (executada):** estado com `turn_count=42`, `npc_killed` de `npc_valerius` → `event_log` = `[(42, npc_killed, npc_valerius, storyteller), (0, location_control_changed, nova_arcadia, rule_engine)]`.
- **Impacto:** milestone da crônica sai com turno 0 (`_chronicle_milestone(d, ...)` usa `ev.get("turn", 0)`), ordenação/recência do `context_builder` trata a consequência como evento antiquíssimo (pode ser descartado do contexto), dedupe de "mesmo turno" do validador não enxerga o derivado.
- **Correção sugerida:** em `run_rules`, propagar `turn=event.get("turn")` para cada derivado (`_new_event(..., turn=...)`).
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_fase27.py` (não assertam `turn`).

### BUG-06-04 — `apply_travel` ignora `danger_overrides`: `danger_level` volta ao valor-base do mapa
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `world_utils.py:168` (`world["danger_level"] = dest.get("danger", ...)`) vs `_effective_danger` (`:531`), `_raise_danger` (`:318`), `world_simulator._apply_danger_shift`
- **Evidência:** ascensão de facção (`elevar_perigo`/`invocar_entidade`) e `world_simulator` gravam override por local; só atualizam `danger_level` se o jogador já está lá. Ao chegar depois, `apply_travel` escreve o perigo base.
- **Reprodução (executada):** `danger_overrides={"na_anel_dourado": 4}` (base 1); `apply_travel(...)` → `danger_level = 1`, `_effective_danger = 4`.
- **Impacto:** o gatilho do encontro usa o efetivo (4), mas `recovery_rest_safe` (resultado `True` no teste), `detection_check` (DC), `roll_encounter_type`, dano de armadilha, chance de clima global e `_apply_encounter_budget` (fallback) usam `danger_level` base: descanso "seguro" de early-game num local que a ascensão tornou perigo 4.
- **Correção sugerida:** `world["danger_level"] = _effective_danger(world, dest["id"])` em `apply_travel` (e em `ensure_world`).
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum cobre travel + override.

### BUG-06-05 — Revisitar local com baú curado re-sorteia achado ambiental a cada visita (loot farmável)
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `agents/storyteller.py:337` (`if first_visit or dest.get("treasure")`) + `services/exploration.py:104-116` (se `resolve_treasure` devolve None cai no passo 2 `roll_discovery`)
- **Evidência:** spec/doc do módulo: "achado só na 1ª visita". Para `pm_profundezas` e `ae_ruinas_submersas` (únicos nós com `treasure`), a condição `dest.get("treasure")` é verdadeira em toda chegada; com o baú já em `looted_locations`, `discover_on_arrival` ignora o baú e rola `roll_discovery` com rng seedado por turno.
- **Reprodução (executada):** `looted_locations=["pm_profundezas"]`, 200 turnos distintos → **86/200 chegadas geram achado** (item/ouro) numa revisita.
- **Impacto:** farm de ouro/itens indo e voltando a esses dois locais; viola a regra de fog of war do loot de exploração.
- **Correção sugerida:** em `discover_on_arrival`, só rolar o passo 2 quando `first_visit` (passar o flag) — o baú curado entra independente, o ambiental não.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/` de loot-exploracao não cobrem revisita pós-baú.

### BUG-06-06 — Quest conclui com duas ações quase idênticas (fingerprint = texto cru, pontuação conta)
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `services/quest_log.py:176,195-210`
- **Evidência:** `fingerprint = NFKC(action).casefold()` — "ações distintas" é comparação de string exata, incluindo pontuação/espaços/caixa.
- **Reprodução (executada):** quest ativa no local, `location_reached` registrado; `sync_action_progress(..., "Investigo a pista", turn=5)` e depois `"Investigo a pista."` (turn=6) → `ready == ['q1']` (completion_ready). Gera `quest_completed` + XP + 20 de ouro.
- **Impacto:** a regra "duas investigações distintas" é contornável com um ponto final; recompensa/XP em 2 turnos triviais. Também `generic_reference` ("pista", "missão", "investigo") torna *qualquer* quest do local "relevante".
- **Correção sugerida:** normalizar o fingerprint (sem acento/pontuação, palavras ≥4 ordenadas) e exigir Jaccard < ~0.6 entre ações para contar como distinta; opcionalmente exigir turnos não consecutivos.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_fase33.py` (cobre o caminho feliz).

### BUG-06-07 — `relationship` 0 vira 5 por `int(x or 5)`: NPC que odeia o jogador passa no gate de recrutamento
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `party.py:268` (`scene_allies`) e `party.py:291` (`recruitment_decision`)
- **Evidência:** `rel = int(npc.get("relationship", 5) or 5)` — `0` é falsy. `relationship` é clampado em `[0,10]` (`agents/npc.py:549`), logo 0 é alcançável.
- **Reprodução (executada):** NPC `relationship=0` com trait `pele_de_febre` (persuasao −3 ⇒ `required=5`): `recruitment_decision` → `{'ok': True, 'relationship': 5, 'required_relationship': 5}`. Recruta quem tem relação mínima.
- **Impacto:** traits que baixam o DC permitem recrutar NPC no relacionamento mínimo; `hint`/UI mostram relação 5.
- **Correção sugerida:** `rel = npc["relationship"] if isinstance(npc.get("relationship"), int) else 5` (checar `None`, não falsidade). Mesmo padrão em `playtest/` (fora de escopo).
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_aliados_combate.py` (não cobre rel=0).

### BUG-06-08 — `NPCResponse.relationship_change` sem limite: um turno de LLM pode levar a relação de 0 a 10
- **Severidade:** média
- **Categoria:** guard-fallback
- **Local:** `agents/npc.py:114` (`relationship_change: int = 0`), `:549`
- **Evidência:** sem `ge/le` e sem teto por turno; só o clamp final `[0,10]`. O gate de recrutamento (≥7) e de aliado de cena (≥6) depende desse valor, violando "mecânica é Python".
- **Reprodução:** leitura (mock devolve −1..+1; um LLM real pode devolver +5).
- **Impacto:** recrutamento/aliado de cena em 1 turno de conversa por alucinação ou por manipulação do jogador no prompt.
- **Correção sugerida:** `max(-1, min(1, res.relationship_change))` (ou ±2) antes de aplicar; idealmente derivar do sentimento por regra.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** `tests/test_fase28.py`, `tests/test_fase33.py` (usam 0/1).

### BUG-06-09 — Tag `dark` nunca existe no mapa e masmorras têm tag `abrigo`: `light_level` jamais dá "escuro" em dungeon
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `world_utils.py:792,888-909` (`_SHELTER_TAGS` + `"dark" in tags`), `data/world_map.json`
- **Evidência:** o spec itens-vivos-e-luz promete "escuro sem luz = noite OU local `dark`". Varredura do mapa: **nenhum** nó tem `dark`; as masmorras interiores (`pm_cripta_afogada`, `ae_camara_seca`, `ma_forja_profunda`) têm `['abrigo','masmorra']` ⇒ `sheltered=True` ⇒ nunca escuro, nem à noite.
- **Reprodução (executada):** script de varredura (`dark:` não imprimiu nenhum nó; lista de interiores mostra `abrigo`+`masmorra`).
- **Impacto:** a mecânica de luz (percepção −3, acerto −1, tocha/lanterna) só funciona ao ar livre à noite; item de luz é inútil em masmorra; o bloco `<AMBIENTE_DE_LUZ>` nunca descreve o breu de dungeons.
- **Correção sugerida:** tratar tag `masmorra`/`caverna` como `dark` (e `dark` ter precedência sobre abrigo), ou taguear os nós.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** testes de luz usam tag `dark` sintética.

### BUG-06-10 — `disabled_edges` não afeta `dynamic_edges`: controlador dinâmico nunca é "desativado"
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `services/graph_resolver.py:107-114`; produtores `services/rule_engine.py:283-292` (`disable_controls_edges`) e `services/event_processor.py:86-92`
- **Evidência:** só `load_base_edges()` é filtrado por `disabled_ids`; `projection["dynamic_edges"]` é apendado sem filtro, mas `disable_controls_edges`/`location_control_changed` registram também ids de edges dinâmicas (`dyn_*`) em `disabled_edges`.
- **Reprodução (executada):** `dynamic_edges=[{id: dyn_abc, controls, source: mao_sombria, target: nova_arcadia}]` → `get_current_controller` = `mao_sombria`; após `disabled_edges=[{edge_id: dyn_abc}]` continua `mao_sombria`.
- **Impacto:** se uma facção tomou um local por evento e seu líder morre sem rival disponível (regra emite zero eventos), o local segue "controlado" por ela para HUD/encontros/hostilidade (`_hostile_ruler`). Em controle em cadeia a "última vence" mascara o bug.
- **Correção sugerida:** filtrar `effective` inteiro (base + dynamic) por `disabled_ids`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_fase25.py` (só base edges).

### BUG-06-11 — NPC morto (`status: "morto"`) permanece no contexto do narrador e em `npcs_in_scene`
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `services/npc_layers.py:91-139` (`npcs_in_scene`, `npcs_for_context`, `is_in_scene`); marca de morte em `agents/combat.py:1205-1207`
- **Evidência:** nenhum helper consulta `status/dead`. `_reflect_scene_allies` seta `status="morto"`, `in_scene=False`, mas mantém `home_location_id`; `npcs_for_context` inclui "quem tem `home == loc`" (linha 137) ⇒ continua em `existing_npcs` do prompt do storyteller. Se `in_scene` estiver `True`/ausente (legado, ou morte via outro caminho), também entra em `npcs_in_scene` (alvo da rota NPC) e `scene_allies`.
- **Reprodução (executada):** `npcs={"Grum": {status:"morto", in_scene:False, home:"nova_arcadia"}}` → `npcs_for_context` = `['Grum']`; com `in_scene=True` → `npcs_in_scene` = `['Grum']`. `npc_actor` ainda responde "Grum não está aqui. Foi visto pela última vez em ..." (trata morto como ausente).
- **Impacto:** narrador "ressuscita" aliado/NPC morto em combate; o jogador pode tentar falar com cadáver.
- **Correção sugerida:** filtro único `_alive(npc)` (`not dead and status != "morto"`) em `is_in_scene`, `npcs_in_scene`, `npcs_for_context`, `scene_allies`, `visible_npc_view` (marcar morto).
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum.

### BUG-06-12 — Membro de party morto/em espera pode conversar em qualquer local (gate `in_party` ignora estado)
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `agents/npc.py:340-349`
- **Evidência:** `in_party` é verdadeiro para qualquer entrada em `state["party"]` (inclui `active=False, waiting_at=<outro local>` e `dead=True`); o gate de camada 3 ("NPC fora de cena não conversa") é então contornado.
- **Reprodução:** leitura (`set_waiting` mantém o companheiro em `party`; combate também mantém `dead` em `party`).
- **Impacto:** companheiro "esperando em Brekmar" responde no Pântano; companheiro morto fala. Também bloqueia re-recrutar (`already_member`) um companheiro morto.
- **Correção sugerida:** `in_party` só para `active` e não `dead/fled`; waiting só no próprio `waiting_at`; morto → remover da party ou recusar.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** nenhum.

### BUG-06-13 — Vários `faction_impacts` da mesma fação no turno aplicam reputação N× e divergem do `event_log`
- **Severidade:** baixa
- **Categoria:** contabilidade
- **Local:** `agents/storyteller.py:782-792` + `services/world_validators.py:238-246`
- **Evidência:** cada impacto chama `apply_reputation` (+12/−12 cada, sem teto por turno) *antes* da validação; o validador depois rejeita o 2º `reputation_changed` do mesmo `type+target+turn` como duplicata. Resultado: `factions[i].reputation` moveu 24+, o log só tem 1 evento.
- **Reprodução:** leitura (a LLM pode listar a mesma fação duas vezes).
- **Impacto:** reputação/`disposition` mudam mais do que a timeline mostra; um turno pode cruzar o limiar de aliado/hostil.
- **Correção sugerida:** deduplicar `faction_impacts` por `faction_id` (último/primeiro) antes de aplicar.
- **Confiança:** provável
- **Testes existentes relacionados:** nenhum.

### BUG-06-14 — `encounter_eff_danger` fica "grudado" em `world` quando nenhum encontro de combate ocorre
- **Severidade:** baixa
- **Categoria:** estado-inconsistente
- **Local:** `world_utils.py:745-746`; consumo único em `agents/combat.py:227` (`world.pop`)
- **Evidência:** `check_encounter` grava a flag sempre que passa do cooldown, mesmo retornando `None`, suprimido por dedupe ou convertido em armadilha/rastro/social; o `world` é persistido pelo storyteller. O comentário diz "one-shot como encounter_surprise".
- **Reprodução (executada):** `check_encounter` num local seguro retorna `None` e deixa `world["encounter_eff_danger"] == 1`.
- **Impacto:** o próximo combate deliberado (ataque do jogador) usa o orçamento de perigo/nível do último check (pode ser de outro local ou nível), mais fraco ou mais forte que o atual.
- **Correção sugerida:** setar a flag só quando `check_encounter` retornar encontro; limpar no storyteller quando `enc is None` ou virou não-combate.
- **Confiança:** confirmado por execução (flag) / provável (efeito)
- **Testes existentes relacionados:** nenhum.

### BUG-06-15 — Alerta de reforços é consumido e depois suprimido pelo dedupe de encontro
- **Severidade:** baixa
- **Categoria:** estado-inconsistente
- **Local:** `world_utils.py:581-593,749-755` (`_pop_active_alert` remove o alerta), `agents/storyteller.py:428-430` (suprime se `hint == last_encounter_id` no mesmo local)
- **Evidência:** o `hint` de reforço é o nome-base do fugitivo, que é exatamente o `hint` do encontro anterior naquele local. Voltar ao local ⇒ reforço suprimido e o alerta já foi descartado.
- **Reprodução (executada):** `register_flee_alert("Lobo Sombrio 2")` → `check_encounter` devolve `reinforcements`/`"Lobo Sombrio"` e `threat_alerts` fica `[]`; (supressão em seguida: leitura).
- **Impacto:** a promessa "o fugitivo volta com reforços" some silenciosamente.
- **Correção sugerida:** não aplicar o dedupe a `reason == "reinforcements"|"controlled"` ou só consumir o alerta quando o encontro for efetivado.
- **Confiança:** provável
- **Testes existentes relacionados:** `tests/test_fase25*`/`test_combat_lifecycle.py` não cobrem a combinação.

### BUG-06-16 — Duração do clima global conta chamadas de `advance_weather`, não períodos; descanso bloqueado avança fações 2× o relógio
- **Severidade:** baixa
- **Categoria:** off-by-one
- **Local:** `world_utils.py:840-844` (`periods_left` −1 por chamada), `:154-176,179-265`; `agents/storyteller.py:367` (`advance_factions(factions, 2)` fixo)
- **Evidência:** viagem de 3 períodos e descanso de 2 períodos chamam `advance_weather` 1×, então `duration_periods` (ex.: Tempestade de Éter = 4) é na prática 4 *eventos de tempo*; viagem longa não expira o evento. No descanso bloqueado por clima o relógio avança 1 período (`:188`) mas as fações avançam 2.
- **Reprodução:** leitura.
- **Impacto:** efeitos de clima global duram mais do que o autor espera; desequilíbrio leve nas fações.
- **Correção sugerida:** passar `steps` a `advance_weather` (tickar `steps` vezes) e usar o delta real do relógio para fações.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** testes de weather-global testam 1 tick.

### BUG-06-17 — `world_simulator`: `danger_shift` do LLM empurra o perigo de cidades sem limite de decaimento/piso por tipo de local
- **Severidade:** baixa
- **Categoria:** guard-fallback
- **Local:** `agents/world_simulator.py:66-78,120-138`
- **Evidência:** a cada descanso/viagem a LLM propõe −1/0/+1 e o override é permanente (só clamp [1,4]); nada devolve o perigo ao base nem protege locais `cidade/seguro`. Combinado com BUG-06-04, o `danger_level` e o efetivo divergem.
- **Reprodução:** leitura.
- **Impacto:** 3 descansos com viés da LLM podem transformar a cidade inicial em perigo 4 (encontros `high_danger` permanentes dentro de cidade).
- **Correção sugerida:** limitar o drift a ±1 em torno do base por local e decair 1 por N turnos; ignorar shift positivo em locais com tag de abrigo.
- **Confiança:** provável
- **Testes existentes relacionados:** `tests/test_fase2*` cobrem clamp, não o acúmulo.

---

## Descartados / falsos positivos
- **`blocked_routes` não barra a viagem do jogador:** `find_travel_destination` ignora rota bloqueada, mas `specs/SPEC-017-fase-6.1-economia-viva.md` §fora-de-escopo declara explicitamente que a viagem do player não é bloqueada (afeta comércio/ecologia). Não é bug.
- **Mapa:** nenhum id duplicado, sem arestas assimétricas/ausentes, `travel_times` simétricos, interiores só com saída para o pai, 0 nós inalcançáveis, `danger` presente em todos (script `world_map` rodado). 44 pares sem `travel_times` caem no default 1 (documentado).
- **Rollover do relógio:** `advance_clock` calcula `idx//5` corretamente para custos >5; `time_of_day` e `world_clock.period` são atualizados juntos (único escritor é `advance_clock`/`starting_world`).
- **`_apply_flee_travel` com destino de cliente:** validado por `_is_valid_flee_destination` (`combat.py:536,798`); o reset de cena da fuga existe (`:1166`).
- **Quest `completed` sem `location_reached`:** o caminho do LLM (`quest_completed` por proposta) é válido por design (`_v_quest_completed`); só o caminho Python exige `reached`. `quest_completed` duplo/XP duplicado: já reportado na área 03 (não repetido).
- **`weather.json`:** todas as regiões têm tabela, sem pesos zero (`rng.choices` não estoura), alvos de transição válidos.
- **`maybe_start_global_weather` com evento ativo:** retorna `None` (sem 2º evento simultâneo); reiniciar logo após expirar é aceitável.
- **Rest em `apply_rest`:** Entropia recompõe até `max_entropy` (não excede), Insônia reduz cura como especificado; marcas `downed_recente` foram aposentadas (spec checkpoints-morte).
- **`weighted_pick`/`maybe_start_global_weather` com RNG global:** não determinístico em produção, mas só variação de sorteio (baixa; sem estado inconsistente).
- **`visible_npc_view` usa `in_scene` default False vs `is_in_scene` default True:** divergência cosmética de view para saves legados, sem efeito de jogo.
