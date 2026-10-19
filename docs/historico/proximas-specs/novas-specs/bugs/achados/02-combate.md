# Auditoria de bugs funcionais — Área 02: Combate (motor de conflitos Valoria v2 + nó de combate)

Data: 2026-10-15. Subagente Sonnet. Somente leitura + scripts offline (MockLLM).
Scripts de reprodução: `C:\Users\guilh\AppData\Local\Temp\claude\c--Users-guilh-OneDrive--rea-de-Trabalho-rpg-ia-master\3422f347-bfc9-4363-bbd6-73dd1453d495\scratchpad\combate\r1.py ... r11.py`
(rodar da raiz com `PYTHONPATH=. PYTHONIOENCODING=utf-8 uv run python <script>`).

## Cobertura
- **Lidos por inteiro:** `agents/combat.py`, `services/conflict_orchestrator.py`, `services/conflict_turn.py`,
  `services/conflict_resolution.py`, `services/conflict_damage.py`, `services/cards.py`, `services/reactions.py`,
  `services/conflict_scene.py`, `services/death_flow.py`, `services/chase.py`, `services/conflict_summary.py`,
  `services/combat_origin.py`, `encounter_budget.py`.
- **Lidos parcialmente:** `combat_mechanics.py` (condições, Entropia/Carga, passivas), `services/encounter_preparation.py`
  (nível do encontro, potência, fallback_safe_scene), `services/tactical_profile.py` (pick_action), `services/abyss_events.py`
  (select/trigger), `party.py` (`scene_allies`, `recruitment_decision`), `progression.py` (`xp_for_kills`), `world_utils.py` (descanso).
- **NÃO cobertos (tempo):** `services/tactical_profile.py` (geração/normalização de perfil, ~250 linhas), `services/encounter_preparation.py`
  (validação de cena/normalização), `services/abyss_events.py` (can_trigger), `inventory.use_item_in_combat`, `agents/bestiary.py`,
  modo `combat_simulation` além do que `combat_node` mostra, UI de reação (`api.py` contrato combate).

## Contagem por severidade
| Severidade | Qtde |
|---|---|
| crítica | 0 |
| alta | 8 |
| média | 6 |
| baixa | 6 |

(Já coberto por specs draft e NÃO detalhado: SPEC-199 R12 — carta de cura sem alvo cura inimigo; ver BUG-02-21 só como adendo.)

---

### BUG-02-01 — XP e abates do bestiário são re-concedidos a CADA rodada para todo inimigo já morto
- **Severidade:** alta
- **Categoria:** contabilidade
- **Local:** `agents/combat.py:905-929` (`dead = [...]`, `disc.record_kills`, `pg.xp_for_kills(dead)`), `agents/combat.py:984` (`"enemies": [] if combat_over else enemies`), `agents/combat.py:1005` (`_kill_events(dead)`)
- **Evidência:**
  ```python
  dead = [e for e in enemies if e.get("dead") or e.get("status") == "morto"]   # TODOS os mortos do estado, não só os desta rodada
  if dead:  bestiary_knowledge = disc.record_kills(bestiary_knowledge, dead, turn)
  ...
  if dead and not player_dead and not is_simulation:
      xp = pg.xp_for_kills(dead); player, level_up_events = pg.grant_xp(player, xp)
  ```
  O nó devolve `enemies` COM os mortos enquanto o combate continua; na rodada seguinte `state["enemies"]` ainda contém o morto, que entra de novo em `dead`.
  O docstring de `xp_for_kills` diz "mortos NESTE round", mas nada filtra por rodada/`xp_granted`.
- **Reprodução (executada, `r9.py`):** 2 Minions (goblin_1 já `dead`, goblin_2 com Vitalidade 999). 3 rodadas de "Ataco o Goblin 2":
  ```
  round 1 xp 50  ... 'defeated': 1
  round 2 xp 100 ... 'defeated': 2
  round 3 xp 150 ... 'defeated': 3
  ```
  Esperado: XP constante (0 enquanto ninguém novo morre) e `defeated` fixo. Observado: +50 XP e +1 `defeated` por rodada por cadáver. Também re-emite `npc_killed` em `pending_world_events` (kills canônicas duplicadas) quando o inimigo tem entidade.
- **Impacto:** inflação de XP/nível em combates com 2+ inimigos (qualquer sobrevivente prolongando a luta), grau de conhecimento do bestiário inflado, eventos de mundo `npc_killed` duplicados (mundo vivo/crônica).
- **Correção sugerida:** marcar `xp_granted`/`kill_recorded` no inimigo ao conceder (ou calcular `dead` como `mortos_agora = ids mortos em out["deaths"]`); filtrar `dead` por `e["id"] in out["deaths"]`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum cobre multi-rodada com sobrevivente (`tests/test_combat_lifecycle.py`, `tests/test_aliados_combate.py` rodam 1 rodada).

### BUG-02-02 — Aliados nunca estabilizam o protagonista em Estado Terminal (lado "hero" só contém o player)
- **Severidade:** alta
- **Categoria:** regra-divergente
- **Local:** `services/conflict_orchestrator.py:1059-1072` (`_stabilizer_for`), construção de `sides` em `agents/combat.py:731`
- **Evidência:** `sides = {"hero": [player], "ally": ally_ids, "enemy": [...]}`; `_stabilizer_for` procura aliados só na PRIMEIRA lista que contém `down_id` (`for side, ids in sides.items(): if down_id in ids: same_side = ids; break`) — para o player isso é `["player"]`, nunca `"ally"`. Outras partes (`_opposing_ids`, `_same_side_ids`) tratam `hero+ally` como um lado; esta não.
- **Reprodução (executada, `r1.py`):** player em `estado_terminal`, companheiro vivo em `sides["ally"]`:
  ```
  stabilizer: None
  player_dead: True [{'actor_id':'player','revived':False,'dead':True,'cause':'sem aliado próximo e capaz',...}]
  ```
  Esperado (spec conflito-07 R3): até 2 tentativas de estabilização por aliado capaz.
- **Impacto:** com companheiro ou aliado transitório na cena, o jogador morre (`death_pending`) no 1º Estado Terminal exatamente como se estivesse sozinho; a mecânica de "aliado estabiliza" é inalcançável para o player. Inverso: aliado caído também não é ajudado pelo player/outros lados.
- **Correção sugerida:** em `_stabilizer_for` usar `_same_side_ids(down_id, sides)` (hero+ally juntos).
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_death_flow.py` testa `attempt_stabilization` com helper explícito; nenhum teste passa por `resolve_terminals` com `sides` de produção.

### BUG-02-03 — Companheiros/aliados viram categoria "padrao" (sem Última Ação/Estado Terminal) e ainda ganham carta e política de inimigo
- **Severidade:** alta
- **Categoria:** regra-divergente
- **Local:** `party.py` (`make_companion_from_npc` → `categoria: "padrao"`), `services/conflict_orchestrator.py:98-119` (`ensure_combat_sheet`, ramo não-player), `services/death_flow.py:21` (`FULL_FLOW_CATEGORIES` inclui `companheiro`, ninguém atribui)
- **Evidência:** `_CATEGORIA_ALIAS` mapeia `companheiro`→`companheiro`, mas a ficha do companheiro chega com `categoria == "padrao"`; o ramo de ensure só cai em `"companheiro"` se o dado já trouxer isso.
- **Reprodução (executada, `r11.py`):**
  ```
  raw categoria: padrao type: None
  sheet categoria: padrao full_flow: False pursuit nao_persegue
  ```
  Spec 07 R7: "Jogador e Nomeado/**companheiro**/Elite/Chefe SEMPRE" usam o fluxo completo. Companheiro Padrão morre ao preencher o último Crítico (`_check_terminal` ramo `not uses_full_death_flow`).
- **Impacto:** aliado cai/morre direto sem Última Ação nem chance de estabilização (agravado por BUG-02-02); como o ramo `categoria != "companheiro"` roda, aliados também recebem `pursuit_policy`, `max_entropy` de inimigo e a carta reativa `bst_defesa_instintiva`.
- **Correção sugerida:** `make_companion_from_npc` (e `scene_allies`) devem gravar `categoria="companheiro"`; ou `ensure_combat_sheet(..., is_ally=True)` forçar a categoria.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum.

### BUG-02-04 — Aliados transitórios (`scene_allies`) curam-se totalmente e ressuscitam a cada rodada
- **Severidade:** alta
- **Categoria:** estado-inconsistente
- **Local:** `agents/combat.py:719-722, 761, 976-980, 1001-1002` (`scene_tr = combat_meta.get("scene_allies") or party_mod.scene_allies(...)`; `combat_meta["scene_allies"] = scene_tr`)
- **Evidência:** a cada rodada `allies = [ensure_combat_sheet(dict(a)) for a in scene_tr]` a partir do SNAPSHOT guardado em `combat["scene_allies"]` (criado na rodada 1). O que é persistido em `combat_meta["scene_allies"]` é o snapshot original (`scene_tr`), não as fichas mutadas (`allies`). Só `_reflect_scene_allies` copia a Vitalidade final para o NPC, mas a rodada seguinte relê o snapshot (campos top-level `vitalidade`/`dead`/`status` não são compartilhados pela cópia rasa).
- **Reprodução (executada, `r8.py`, injetando dano no fim da rodada 1 e morte na 2):**
  ```
  round 1 npc after: 2 None
  round 2 npc after: 2 morto
  [('start', 8, None), ('start', 8, None)]   # rodada 2 começa com Bors em 8/8 de novo
  ```
  Esperado: rodada 2 começa com Bors em 2.
- **Impacto:** o aliado de cena é efetivamente imortal/autocurável durante o combate ("sem aliado imortal" é requisito explícito do `_reflect_scene_allies`); a Vitalidade refletida no NPC só vale a última rodada; um aliado morto reaparece lutando na rodada seguinte.
- **Correção sugerida:** persistir `combat_meta["scene_allies"] = [a for a in allies if a.get("transient")]` (fichas pós-rodada) e usá-las como fonte nas rodadas seguintes.
- **Confiança:** confirmado por execução (dano injetado; mecanismo é leitura direta do código)
- **Testes existentes relacionados:** `tests/test_aliados_combate.py::test_aliado_transitorio_entra_no_combate_e_nao_persiste` (1 rodada) e `::test_dano_e_morte_transitorios_refletem_no_npc` (chama `_reflect_scene_allies` isolado).

### BUG-02-05 — Buffs/debuffs tipados (`stat`/`delta`) das condições não afetam nenhuma rolagem do motor v2
- **Severidade:** alta
- **Categoria:** estado-inconsistente (mecânica morta)
- **Local:** `services/conflict_turn.py:354-362` (cria condição `stat: attack|ac|damage|protection|advantage`), `services/conflict_resolution.py:135-170` (`resolve_attack`: só Virtude + vantagem), `services/conflict_resolution.py:47-49` (`compute_esquiva`: sem `ac`), `combat_mechanics.py:233` (`condition_modifiers` só é lido por `api.py:3523` e `inventory.py:255`)
- **Evidência:** `grep condition_modifiers` não encontra consumidor em `services/conflict_*`; o dano em `_damage_from` ignora `stat: damage`. Também mortos por tabela: debuffs `fear` (-2 ataque), `Colapso` (Recidiva, attack -4), `Transformação` (ac/save -N, Corruptor), `buff_acerto/buff_dano/buff_defesa/protecao/vantagem` (≈38 cartas ativas + reações).
- **Reprodução (executada, `r4.py`; 200 ataques, mesmo seed):**
  ```
  base                  (138 acertos, soma de totais 2646)
  attack +20            (138, 2646)
  ac +20 no alvo        (138, 2646)
  ```
  Esperado: +20 de ataque faz acertar quase sempre; +20 de Esquiva quase nunca.
- **Impacto:** jogador gasta Entropia/Ação em cartas de buff/debuff e em consumíveis que "funcionam" no log mas não mudam nada; consequências de Carga do Abismo (Transformação, Colapso) e Medo não têm efeito mecânico; HUD (`api.py:3523`) exibe valores que não refletem o combate.
- **Correção sugerida:** em `resolve_attack`/`compute_esquiva`/`_damage_from` somar `cm.condition_modifiers(actor)` (attack/ac/damage) ao total/Esquiva/dano; respeitar `duration`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum (`condition_modifiers` não é referenciado em `tests/`).

### BUG-02-06 — Cartas passivas, de Virtude e efeito de Reação não têm consumidor; `learned_passives` devolve `[]` (regressão das passivas de árvore)
- **Severidade:** alta
- **Categoria:** estado-inconsistente (mecânica morta) / REGRESSÃO de SPEC-047 `arvores-habilidade-classes` (`done`) e conflito-02/14
- **Local:** `combat_mechanics.py:194-200` (`learned_passives` → `[]` "resolvidas pelo motor de Cartas"), `services/conflict_orchestrator.py:569-572` (reação só concede `protected`), `services/cards.py` (nenhum tratamento de `tipo == "passiva"|"virtude"`)
- **Evidência:** inventário do catálogo (`r5.py`): 308 cartas; `passiva` ≈ 38 (buff_defesa, buff_dano, vantagem, aplicar_condicao, dano, contra_ataque, buff_iniciativa, buff_dot, buff_cura, perception, bonus_*_por_estagio), `virtude` 6 (`bonus_*_por_estagio`), `reacao` 27 com kinds contra_ataque/dano/buff/cura/aplicar_condicao/empurrao. `grep '"passiva"'` em `services/ agents/ combat_mechanics.py api.py progression.py` não acha consumidor (só validador/context_builder para `utilitaria`). Em `_open_reaction_window` qualquer reação válida só chama `grant_tactical_modifier(scene,"protected",rid,rid)` — o `efeito` da carta (contra_ataque, dano, cura…) nunca roda, mas a Entropia é debitada. Os triggers de passiva `entropy_on_kill`, `entropy_cost_reduction`, `charge_discount`, `entropy_max_bonus`, `melee_retaliate`, `basic_attack_dot`, `initiative_attr`, `heal_bonus_low`, `hp_as_mana` constam em `HANDLED_KINDS` mas só `class_passives` e `item_passives` os alimentam; passivas "aprendidas" (a árvore rica da SPEC-047) morreram no cutover.
- **Reprodução:** leitura + `r5.py` (inventário) + `r4.py` (nenhuma condição modifica rolagem). `learned_passives(...)` → `[]` sempre.
- **Impacto:** o jogador escolhe Cartas passivas/de Virtude no level-up e criação (6 Virtudes iniciais + Cartas) que não têm nenhum efeito; Reações "contra-atacam" sem causar dano; o teste anti-órfão (`test_cutover_audit`/R4 de SPEC-050) dá falsa segurança porque só compara nomes em `HANDLED_KINDS`.
- **Correção sugerida:** (a) agregar passivas de `known_cards` com `tipo in {"passiva","virtude"}` num `learned_passives` real e consumir em `resolve_attack`/dano/iniciativa; (b) resolver `reaction.efeito` (contra_ataque/dano/cura) em `_open_reaction_window`; (c) teste anti-órfão que exija consumidor (não só presença em `HANDLED_KINDS`).
- **Confiança:** confirmado por leitura (+ execução parcial)
- **Testes existentes relacionados:** `tests/test_cutover_audit.py`, teste anti-órfão `HANDLED_KINDS` (não detecta ausência de consumidor).

### BUG-02-07 — `last_stand_resolved` e `stabilization_attempts` nunca são zerados: o 2º quase-morte vira morte instantânea (e a 1ª falha de estabilização já usa a DC 15)
- **Severidade:** alta
- **Categoria:** estado-inconsistente
- **Local:** `services/death_flow.py:134-141, 190-192` (flags só setadas), `services/conflict_orchestrator.py:726-740` (`_check_terminal` ramo `last_stand_resolved`), `services/actor_lifecycle.py:118` (único reset; só no restore de checkpoint), `world_utils.py:~214` (descanso trata Críticos mas não limpa flags)
- **Evidência:** após `_revive`, `last_stand_resolved=True` e `stabilization_attempts=N` permanecem. `grep last_stand_resolved|stabilization_attempts` em código de produção: nenhum reset em descanso/fim de combate/cura de Crítico.
- **Reprodução (executada, `r1.py`):** Médico com kit sobrevive ao Terminal; `rest_treat_wounds(..., has_kit=True, is_medic=True)` remove o Crítico; novo preenchimento do último Crítico:
  ```
  revive: True resolved flag: True attempts 0
  crit now []
  2nd near-death -> dead: True pending: False     # sem Última Ação, sem Estado Terminal, sem estabilização
  ```
- **Impacto:** depois do primeiro fluxo terminal, qualquer novo "último Crítico" (mesmo semanas depois, com Ferimento já tratado) mata na hora, sem as 2 tentativas; se `stabilization_attempts` já valia 1, a próxima estabilização começa na DC 15 com uma única chance. (Sem tratamento do Crítico a regra "não concede imortalidade" é intencional; o bug é a persistência do flag após o Ferimento ser removido.)
- **Correção sugerida:** zerar `last_stand_resolved`/`stabilization_attempts` quando o Ferimento Crítico é removido (`rest_treat_wounds`/cura) e ao fim de cada conflito sobrevivido sem Crítico cheio.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum (testes em `test_death_flow.py` não repetem o ciclo).

### BUG-02-08 — Detecção de fuga por regex solta: "recuperar", "retirar", "recusar" disparam a perseguição e anulam a ação do jogador
- **Severidade:** alta
- **Categoria:** regra-divergente
- **Local:** `agents/combat.py:741` (`re.search(r"\bfuj|fugir|escap|retir|recu|corr[oe]\b", intent.lower())`), efeito em `agents/combat.py:746-757, 818-826`
- **Evidência:** só `\bfuj` e `corr[oe]\b` têm borda; `recu`, `retir`, `escap`, `fugir` casam como substring em qualquer palavra. Se `flee_requested`, a ação declarada/parseada é descartada (`TurnDeclaration(kind="pass")`) e o jogador gasta o turno numa tentativa de fuga.
- **Reprodução (executada, `r3.py`):**
  ```
  True  Uso a poção de cura para recuperar minhas forças
  True  Retiro a espada da bainha e ataco
  True  Recuso a oferta e ataco o goblin
  False Ataco o goblin
  ```
  Esperado: nenhuma é fuga.
- **Impacto:** em texto livre (e em qualquer intent com "recuperar/retirar/recusar/escapulário"), o jogador perde a ação, inicia `chase` (consome tentativa do teto de 6) e os inimigos agem; pode até "fugir" sem querer (teto de 6 => escapa automaticamente).
- **Correção sugerida:** regex com fronteiras e formas verbais (`\b(fujo|fugir|fugi|foge|escap(o|ar|e)|corro|recuo|recuar)\b`), ou depender só de `declaration.acao.kind == "flee"`/`combat_flee_attempt` do router.
- **Confiança:** confirmado por execução (regex); caminho de código por leitura
- **Testes existentes relacionados:** `tests/test_combat_lifecycle.py` (fuga explícita) — não cobre falsos positivos.

### BUG-02-09 — Custo/frequência da Carta é cobrado ANTES de validar alvo e mira; ação inválida queima Entropia e o uso
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `services/conflict_turn.py:211-245` (cobrança em `use_card`/`use_ruptura`) vs. `:247-259` (alvo inexistente / `occlusion_attack_modifier.can_target == False` retornam depois), `agents/combat.py:837-843` (alvo de carta só é validado contra `set(actors_by_id)` — inclui mortos e o próprio player)
- **Evidência / Reprodução (executada, `r2.py`):** carta ofensiva `arc_descarga` com `target_id="ghost"`:
  ```
  ['Usa Descarga do Instrumento (-1 Entropia)', 'Ataque sem alvo válido.'] entropy now 9  used_this_scene: 1
  ```
  Esperado: nenhuma cobrança (ou reembolso). Mesmo para alvo escondido sem posição conhecida (`can_target False`). Cartas de frequência 1×cena/descanso ficam bloqueadas sem ter feito nada. Em `combat_node`, um `target_id` de carta vindo do CLASSIFY que seja um inimigo já morto (ou `"player"`) passa na validação (`valid_ids = set(actors_by_id)`) e a Carta é gasta num cadáver ou contra o próprio jogador.
- **Impacto:** recurso perdido por erro de parse; um alvo morto consome a Carta de "1×cena".
- **Correção sugerida:** resolver/validar alvo (vivo, hostil, mirável) antes de `use_card`; em `combat_node` restringir alvo hostil a `active` ids.
- **Confiança:** confirmado por execução (alvo inexistente); provável (alvo morto/player via LLM)
- **Testes existentes relacionados:** nenhum.

### BUG-02-10 — Guarda (`guarding`) nunca expira: Desvantagem permanente nos ataques de quem guardou (e dos atacantes contra ele)
- **Severidade:** média
- **Categoria:** off-by-one (duração) / estado-inconsistente
- **Local:** `services/conflict_scene.py:409-441` (`guard` seta, só `stop_guard` limpa), `reset_turn_budget` (`:57`) não zera; nenhum caller de `stop_guard` em produção (`grep stop_guard`)
- **Evidência:** SPEC-067 R8: "Pode ser abandonado livremente antes de agir (perde a proteção)" — implica expirar ao início do próximo turno do ator. `guard_offense_modifier` aplica -1 em TODOS os ataques do guardião pelo resto do conflito; `guard_defense_modifier` idem para quem o ataca.
- **Reprodução:** leitura (`guard()` → `pos["guarding"]=True`; `reset_turn_budget` só restaura o orçamento). Não executada em script separado.
- **Impacto:** um único "guardar" do jogador deixa seu ataque em Desvantagem até o fim do conflito (e protege indefinidamente); decisão tática vira armadilha.
- **Correção sugerida:** limpar `guarding` em `reset_turn_budget` (início do turno do próprio ator) a menos que ele guarde de novo.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** `test_guardar_desvantagem_nos_dois_lados` (conflito-06) — não testa expiração.

### BUG-02-11 — DoT (Sangramento/veneno/condições) e clima atravessam armadura apesar de `defensavel=False`
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `services/conflict_damage.py:239` (`if compativel and (defensavel or not use_shield)`), chamadores `services/conflict_orchestrator.py:161-169` (`_apply_dot_v4`, docstring: "ignoram armadura"), `agents/combat.py:1116-1124` (clima), `combat_mechanics.py:294-302`
- **Evidência:** com `use_shield=False`, `not use_shield` é True, então `defensavel=False` nunca desativa a armadura (só atua no escudo).
- **Reprodução (executada, `r2.py`):** alvo com armadura Proteção 2, DoT 1:
  ```
  dot1 vs armor prot2: 10 -> 10 ['dano 1×1=1', 'Proteção -1 -> 0', 'Vitalidade 10 -> 10 (excedente 0)']
  ```
- **Impacto:** Sangramento (1 dano) nunca fere quem usa qualquer armadura (e gasta Integridade); DoTs de cartas e dano de clima ficam anulados/amortecidos por armadura, contra a intenção declarada do código.
- **Correção sugerida:** passar um parâmetro explícito `bypass_armor=True` para DoT/clima (ou tratar `defensavel=False` como "ignora armadura e escudo").
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum cobre DoT vs. armadura.

### BUG-02-12 — `narrative_or_fallback` descarta a narração por falso positivo ("escapa/foge/vivo" a ≤80 chars do nome de um morto)
- **Severidade:** média
- **Categoria:** guard-fallback
- **Local:** `services/conflict_summary.py:306-325` (`validate_narrative_text`), chamada em `agents/combat.py:965`
- **Reprodução (executada, `r10.py`):** `"Goblin 1 desaba com um estertor; o vento escapa pelas frestas e a lâmina de Kael sai limpa. Vitória."` com `mortos=["Goblin 1"]` → resultado: `"Mortos: Goblin 1."` (narração inteira trocada pelo texto seco).
- **Impacto:** no fim de combate, prosa legítima ("um grito escapa", "o outro foge") é substituída pelo resumo canônico curto; perde-se a narração mais importante do combate.
- **Correção sugerida:** exigir o sujeito ser o nome e o verbo adjacente (`nome + até 20 chars + verbo`) e checar fronteira de sentença; ou só bloquear termos inequívocos ("vivo", "ergueu-se").
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_conflict_summary_lifecycle.py` (casos positivos).

### BUG-02-13 — Preparação de cena por LLM nunca roda: objetos, eventos do Abismo, reforços e condições de fim não existem em combate real
- **Severidade:** média
- **Categoria:** outro (mecânica morta; spec `done` não entregue em produção)
- **Local:** `agents/combat.py:286` (`scene = prep.fallback_safe_scene(ctx)`); `prepare_encounter` não é chamado por nenhum código de produção (`grep prepare_encounter` → só definição/testes); `scene["abyss_events"] = []`, `objects = []` (`services/encounter_preparation.py:287-296`)
- **Evidência:** comentário: "Mecânica é Python: geometria mínima... não precisa de um segundo invoke FAST". Decisão defensável, mas desativa `_maybe_abyss` (conflito-10), interação com objetos (`kind="object"`, conflito-03), gatilhos de reforço e `ending_conditions` (conflito-11). `abyss_events` nunca é populado ⇒ `select_event` sempre `None`.
- **Impacto:** a Carga do Abismo acumula mas nunca dispara evento de cena; nenhum objeto interativo aparece; specs 03/10/11 marcadas `done` sem efeito real.
- **Correção sugerida:** ou chamar `prepare_encounter` (com o guard existente) no 1º round, ou declarar oficialmente os recursos como desativados (spec + remover chips/lore que prometem).
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** `tests/test_conflito_*` testam os módulos isolados.

### BUG-02-14 — Engajamento nunca é criado no fluxo real: Ataque de Oportunidade é inerte (e o AoO ignora Desengajar na mesma declaração)
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `agents/combat.py:289-296` (`cs.place(...)`, `engaged_with: []`), `services/conflict_orchestrator.py:501-529` (`_declaration_leaves_engagement` + AoO antes de resolver), `engage()` só via manobra explícita (`conflict_turn.py:125`); `enemy_declaration` nunca engaja
- **Evidência / Reprodução:** por leitura — `trigger_opportunity_attack` itera `pos["engaged_with"]`, sempre vazio salvo manobra "engajar" do jogador; ataque corpo a corpo não engaja. Além disso o AoO é calculado antes de `resolve_turn`: uma declaração com `pre_acao=desengajar` + `pos_acao=move afastar` ainda dispara AoO de cada engajado (R7: Desengajar evita o AoO).
- **Impacto:** a regra de AoO (R5) quase nunca ocorre; quando o jogador usa Desengajar+afastar na mesma declaração leva AoO indevido.
- **Correção sugerida:** engajar ao atacar corpo a corpo/ao receber ataque; checar `disengage` nos slots anteriores em `_declaration_leaves_engagement`.
- **Confiança:** provável (leitura)
- **Testes existentes relacionados:** `tests/test_conflito_reacoes.py` (motor isolado).

### BUG-02-15 — `_early_game_reaction_initiator` vale 2 rodadas (compara a rodada ANTES do incremento)
- **Severidade:** baixa
- **Categoria:** off-by-one
- **Local:** `agents/combat.py:248-267` (`combat_round <= 1`, lido de `state["combat"]["round"]`) e `:758` (incremento depois)
- **Evidência:** 1ª chamada: `state.combat.round==0`; 2ª chamada: `round==1` ainda `<=1`. Docstring: "somente o primeiro round é seu". Se o herói errou/não foi ferido na rodada 1, ganha iniciativa de novo na rodada 2.
- **Reprodução:** leitura. **Confiança:** provável. **Testes:** nenhum.
- **Correção sugerida:** comparar `combat_round < 1` (ou usar o valor pós-incremento `== 1`).

### BUG-02-16 — Carta `estabilizar` marca `scar_pending` mas não registra em `scars_pending`; Cicatriz fica pendente indefinidamente
- **Severidade:** baixa
- **Categoria:** estado-inconsistente
- **Local:** `services/conflict_turn.py:328-335` (seta `scar_pending=True`, sem `out["scars_pending"]`), `agents/combat.py:900-903` (só gera Cicatriz para `sid in out["scars_pending"]`)
- **Impacto:** quem é reanimado por carta fica com `scar_pending=True` até outro reanimar via `resolve_terminals`; a Cicatriz obrigatória (R6) não é gerada no conflito. A carta também não reseta `last_stand_pending`/contagem (`stabilization_attempts` intacto, ver BUG-02-07).
- **Confiança:** confirmado por leitura. **Testes:** nenhum.

### BUG-02-17 — `relationship == 0` é tratado como 5 (`or 5`) em `scene_allies` e `recruitment_decision`
- **Severidade:** baixa
- **Categoria:** off-by-one / valor-falsy
- **Local:** `party.py:268` (`int(npc.get("relationship", 5) or 5)`), `party.py:~291`
- **Evidência:** NPC com relationship 0 (inimigo declarado) vira 5; com `trait_dc_modifier` negativo, `required` = `max(3, …)` ≤ 5 ⇒ recrutável apesar de relação 0. Em `scene_allies` o piso 6 ainda barra.
- **Confiança:** confirmado por leitura. **Testes:** nenhum. **Correção:** `npc.get("relationship"); 5 if None`.

### BUG-02-18 — `encounter_budget.tier_cost` usa `type` legado: 2 criaturas do bestiário v4 têm custo errado
- **Severidade:** baixa
- **Categoria:** contabilidade
- **Local:** `encounter_budget.py:16-18`
- **Evidência (executado, `r3.py`):** `data/bestiary.json`: `type` `"Monstrosidade (Gigante)"` (categoria `chefe`) e `"Humanoid (Human)"` (`nomeado`) caem no custo de minion (2) e `Standard` (`padrao`) custa 2 (mesmo de lacaio). Um chefe com type não-"BOSS" é cortado por `clamp_encounter` como minion (a regra "boss nunca é cortado" não o protege).
- **Correção sugerida:** derivar o custo de `categoria` canônica (lacaio=2, padrao=3, elite=5, chefe/nomeado=12).
- **Confiança:** confirmado por execução. **Testes:** nenhum.

### BUG-02-19 — `_maybe_abyss` gasta Cargas e usos mesmo quando o efeito é rejeitado
- **Severidade:** baixa
- **Categoria:** contabilidade
- **Local:** `services/conflict_orchestrator.py:1087-1096` + `apply_effect_spec` (`:1099-1111`)
- **Evidência:** `trigger_event` já decrementa `usos_restantes`; o orquestrador debita `abyss_charge` antes de `apply_effect_spec`, que pode retornar "Efeito mecânico rejeitado: potência ou alvo inválido." (alvo ausente). Hoje inalcançável por BUG-02-13, mas fica latente.
- **Confiança:** provável. **Testes:** nenhum.

### BUG-02-20 — `_default_card_target` não cobre `reduzir_carga_aliado` (adendo a SPEC-199 R12)
- **Severidade:** baixa
- **Categoria:** estado-inconsistente
- **Local:** `agents/combat.py:330-338` (conjunto `friendly` sem `reduzir_carga_aliado`)
- **Evidência:** a Purga do Médico sem alvo explícito cai em `enemies[0]` e `cm.reduce_ally_abyss(actor, <inimigo>)` gasta 2 Entropia sem benefício. Coberto em essência por SPEC-199 R12 (cura sem alvo) — incluir este kind ao corrigir.
- **Confiança:** confirmado por leitura. **Testes:** nenhum.

---

## Descartados / falsos positivos (e verificações sem bug)
- **Crítico/Supercrítico por dupla (R5):** `_crit_from_kept` — dupla 1–9 crítico, 10-10 supercrítico, 1-1 é Crítico (não falha crítica) — bate com SPEC-065 R5. Vantagem 3d10 mantém os 2 maiores; Ruptura soma +1 de Vantagem. Sem bug.
- **`net_advantage` vs. soma de modificadores:** o código soma fontes (+/−) e usa só o sinal; o teste `net_advantage(2,1)==1` confirma que "magnitude não acumula" significa comparar contagens. Sem bug.
- **Ordem fixa de dano (R8):** dano×crítico → imunidade/res/vuln → Proteção → Integridade → Vitalidade → Ferimento está na ordem da spec; Perfurante -1 Proteção, Corrosivo 2×, Ígneo +2, Impactante -1 Integridade conforme R2/R3. Agravamento/escala/teto de Crítico em `apply_wound` coerente (reproduzido mentalmente; sem divergência).
- **Sacrifício do Sangromante (`sacrifice_vitality`):** armadura não protege, déficit vira Ferimento. OK.
- **Frequência das Cartas:** `use_card` bloqueia no 2º uso de 1×cena/descanso; `reset_card_usage(state,"turno")` por rodada e `"cena"` no fim do combate; cascata correta. `entropy_cost_reduction` não é testável (passivas aprendidas mortas — BUG-02-06). Entropia nunca fica abaixo de 0 em `use_card`; `apply_entropy_trigger` clampa em `max_entropy`.
- **Reações:** limite de 1 reação comum por personagem é por CADEIA (uma janela por ataque) — coerente com SPEC-067 R3; `reaction-responde-reação` não é chamada em produção (sem loop). Sem bug além do já citado (efeito ignorado).
- **Patamares da Carga:** `abyss_tier` usa `thresholds` com `>=`, único ponto de verdade também para o HUD/API (`api._abyss_tier_view`). Coerente.
- **Tabela de potência (`potency_by_level.json`):** fórmula `base + inc*(nivel-1)`, sem buracos para níveis 1–20.
- **HP ↔ Vitalidade:** escritas em `hp` diretas restantes (`inventory.py:231`, `world_utils.py:256, 1080`, `progression.py:151`) estão em ramos `not is_v4`/legados; `sync_legacy_hp_aliases` usado nos caminhos v4. Nenhum caminho v4 sem sincronização encontrado.
- **Modo `combat_simulation`:** XP e eventos de mundo são suprimidos (`is_simulation`); sem concessão indevida encontrada na leitura (não executei o modo).
- **Fuga/chase:** trilha, `can_resume`, teto de 6 tentativas (`>=6`) e `apply_travel`+`reset_scene` consistentes; fuga a Vitalidade 0 passa pelo gate `_can_attempt_flee` e `_register_environmental_damage_terminal`. Observação (hipótese, não reportada como bug): fuga bem-sucedida sem `destination_id` (texto "fujo") encerra o combate sem viajar nem resetar cena.
- **`idle_turns`/ordem de iniciativa/reforços:** `seq` é calculado 1× por rodada e filtra `_can_act`; sem reforço em produção (BUG-02-13), então estável.
- **Origem do combate:** `materialize(combat_meta, hint)` poderia reutilizar origem antiga, mas o router sempre define `combat_origin_hint`; não reproduzível.
- **Já coberto por specs draft:** SPEC-199 R12 (cura sem alvo → inimigo), SPEC-203 (manifesto/elenco/desfecho), SPEC-205 (gesto de alvo).
