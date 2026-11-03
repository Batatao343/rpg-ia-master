# SPEC-377 — Divergências de regra: poda da lei, custo de Fôlego, "vivo" no combate e esconder facção

> **Status:** `approved` (03/11 noite, dono: "vai executando o que puder"; D1=a, D3=a+b, D4=a, D5=1→3→4. **Item 2 (Fôlego) fica com o dono**: depende de publicar `lote-v2` via `/eval-publish`)
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03 (rodada 2: revisão independente aplicada, ver §9)
> **Origem:** `docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md` §3 (R2–R5) e §6 (letra C → SPEC-377; regras W1–W8, com a W1 revisada)
> **Depende de:** SPEC-299, 302, 293, 314, 328 e 330 (`done`). A SPEC-368 já pousou (`712f0228` na `main`), então os itens 2 e 3 não esperam mais. A W1 roda de novo no início de cada etapa.
> **Desbloqueia:** SPEC-378 (helpers comuns), SPEC-380 R2.5 (casos de custo de Fôlego em `cards_combat`, D3 da 380)
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true` · **EVAL_AUTHORING_REQUIRED:** `true` (só no item 2: muda a saída do protocolo `lote-v2` do avaliador `scripts/cards/sim.py`, R8/R24, e a SPEC-380 conta com isso)

Rótulos: **[F]** fato conferido no código em 03/11 (arquivo:linha) · **[H]** hipótese que a Etapa 0 do item prova ou derruba · **[D]** decisão do dono (§8) · **[R]** confirmado por sonda na revisão independente (`handoffs/SPEC-377-independent-review.md`).

---

## 1. Contexto & Objetivo

A auditoria de 03/11 achou quatro pontos onde o mesmo conceito tem duas regras. Ao contrário das
outras specs da onda, esta **muda comportamento de propósito**. Por isso nenhum item pode ser
tratado como refatoração pura (W2/W3 não bastam). Cada item segue a mesma ordem:

1. **caracterização:** testes que fotografam o comportamento atual dos dois lados;
2. **medição:** script ou tabela que mostra quantos casos reais divergem;
3. **decisão do dono** (§8) sobre qual regra vale;
4. só então a mudança, num commit próprio e revertível (W4).

A conferência e a revisão independente corrigiram a auditoria em cinco pontos:
- o `daily_tick` **muda o jogo**, mas só depois de um suborno;
- o hook novo colide com `mark_hunters` no `storyteller`;
- só **2** Cartas divergem no custo de Fôlego;
- o protocolo `lote-v2` da arena usa a regra do lint dentro da luta;
- `_side_of` com `"hero"`/`"heroes"` **não** é bug, mas o inimigo rendido continua alvo de Carta
  por três caminhos.

## 2. Requisitos

### Item 1 — poda de `wanted` (lei)

- **R1** [F] `services/law.py:1719 daily_tick(state, day) -> dict` não tem chamador nem teste.
  A docstring diz "Gancho da SPEC-302". `specs/SPEC-299-lei-crime-por-regiao.md:7,291,517` diz
  que a 302 o consome, mas a SPEC-302 não cita `law`. `services/world_engine.py:735-738` só
  registra `calendar`/`npc_world`/`fauna`/`rumors`.
- **R2** [F][R] O hook muda o jogo, mas **só depois de suborno**. `resolve_bribe` chama
  `_clear_wanted(keep_heat=heat//2)` (`law.py:1353-1357`), que zera o bounty e **mantém**
  `known_at`/`signals_shown`/`hunters_last_clock` (`law.py:1135-1143`). Quando o heat decai a 0,
  a entrada continua sendo lida. Num crime novo na mesma jurisdição, isso causa três efeitos:
  - (a) `_spread_known_at` usa `min(...)` (`law.py:733,741`), então a notícia "já chegou" nos
    locais antigos;
  - (b) `"perguntaram_por_voce"` continua mostrado, e o caçador vem sem novo aviso
    (`law.py:913,1081`);
  - (c) `first = min(known_at.values())` (`law.py:1078`) faz o atraso dos caçadores já contar
    como vencido.

  A sonda da revisão confirmou: sem poda, o caçador aparece no **mesmo clock** do crime novo e
  nenhum sinal novo é dado; com a poda, `known_at` é recalculado, a lista de sinais fica vazia e
  não há caçador.

  Há também um efeito (d): `law["wanted"]` vazio deixa `last_loc` parado (`law.py:850`), e o
  crime seguinte roda `recognition_check` no local atual, como no 1º crime.

  Os outros caminhos não mudam com a poda:
  - pena, multa e prisão chamam `_clear_wanted(keep_heat=0)` (`law.py:1140-1143`), que já zera
    os três campos;
  - no decaimento natural, `bounty > 0` mantém a entrada (`daily_tick` exige `bounty` 0).
- **R3** Com o hook registrado e o motor de mundo `on`, as entradas com `effective_heat == 0`,
  sem `capital` e sem `bounty` somem na virada do dia. As demais ficam byte-iguais.
- **R4** `level()`/`effective_heat()` de toda jurisdição que fica no save dá o mesmo valor antes
  e depois do hook. A jurisdição podada continua lendo `limpo`/0. O decaimento é monotônico e o
  hook avalia no período 0 do dia [R].
- **R5** Save antigo, sem `law_state` ou com entradas decaídas, carrega por `normalize_law`
  (`law.py:262`) e é podado no 1º dia simulado, sem erro.
- **R6** `law.day_hook` devolve `DayHookResult()` vazio em quatro casos:
  - `world_engine.mode() != "on"`, checado **dentro do hook**: o modo shadow nunca escreve
    `law_state`;
  - `law.mode() == "off"`;
  - `ctx.state is None`;
  - `daily_tick` sem mudança.

  O guard de `npc_world.day_hook` (`npc_world.py:721-723`) **não** serve de modelo [R]. Ele só
  olha `RPG_NPC_WORLD`, e o `storyteller` mescla `state_patch` sem olhar o modo
  (`agents/storyteller.py:1364-1368`).
- **R7** [F][R] **Colisão com `mark_hunters`.** No turno de emboscada por caçadores, a ordem é:
  1. `updates.update(_law_mod.mark_hunters(state, ...))` (`agents/storyteller.py:1691-1698`)
     grava `law_state` com `hunters_last_clock`;
  2. `updates.update({k: v for k, v in sim_updates.items() if k != "npcs"})` (`:1708`)
     **sobrescreve** esse valor com o `law_state` podado do `state_patch` (`:1367`), que não tem
     a marca.

  Resultado: se uma jurisdição for podada no mesmo dia em que os caçadores de outra atacam,
  `hunters_last_clock` some, e a próxima viagem pode trazer outra onda sem o espaçamento
  (`law.py:1083`). A correção é aplicar o `mark_hunters` **depois** do merge de `sim_updates`.
  Isso é seguro: `mark_hunters` já parte do `state` podado (`:1368`). Os outros escritores de
  `law_state` no `storyteller` já leem o estado podado e são aplicados depois de `**sim_updates`:
  `scene_block` (`:2008`, aplicado em `:2417`) e `apply_claims` (`:2314`, aplicado em `:2418`).
  O fallback (`:2656-2657`) só usa `sim_updates`. Esses três pontos não mudam.

### Item 2 — `custo_folego` duplicado

- **R8** [F] Existem duas funções com o mesmo nome:
  - `services/cards.py:447`, usada pelo jogo: `card_piles.py:525,537,588,738`,
    `card_rewards.py:661`, `agents/combat.py:1102`;
  - `services/card_effects.py:1596`, usada pelo lint, pelo orçamento e pelo avaliador:
    `card_lint.py:169,352`, `budget_band` em `card_effects.py:1689`, `scripts/cards/sim.py:303,434`,
    `scripts/bestiario/gerar_mecanica.py:220`.

  Os motivos possíveis de divergência são cinco:
  - (a) `dano_base >= 8` → 2 vale para qualquer kind no jogo, mas só para `kind == "dano"` no
    lint;
  - (b) Carta `livre` de `dot`/`contra_ataque` custa 1 no jogo (`cards.py:439,461`) e 0 no lint;
  - (c) o jogo lê `card["efeito"]` e o lint lê `primary_effect` (`card_effects.py:193`). Isso
    pesa na Ruptura de `effective_card` (`cards.py:251-252`) e numa Carta com `efeito` e
    `efeitos` diferentes;
  - (d) valor explícito inválido levanta erro no lint;
  - (e) o `tier` default é 1 no jogo e 0 no lint, o que não tem efeito.

  **Onde a regra do lint entra em luta** [R]:
  - a arena base paga Fôlego pela regra do jogo (`sim.py:161,243,267` → `card_piles`);
  - o protocolo **`lote-v2`** (SPEC-358) monta a Carta de referência com
    `"custo_folego": fx.custo_folego(card)` (`sim.py:434`). Essa referência luta e paga esse
    valor explícito. O protocolo também escolhe o X pela faixa `fx.budget_band` (`sim.py:454`).

  Unificar muda `vitoria_ref`/`delta_pp`/`dominante` do `lote-v2` para as Cartas divergentes.
- **R9** [R] Medição da revisão: 1.505 Cartas em `data/cards/**`, 470 com custo explícito.
  - Modos bruto e catálogo: **só 2 divergências**, as duas do motivo (b):
    - `cor_toque` (`data/cards/corruptor.json`, dot livre: jogo 1, lint 0);
    - `toque_corrosivo` (`data/cards/exemplos.json`, idem).
  - Os motivos (a) e (c) deram zero.
  - `check_budget`/`budget_error` **não mudam** para essas duas: a faixa vai de (0,7) para
    (-2,9), com score 2,4 e 4,2, dentro nas duas regras.
  - A hipótese da rodada 1, de concentração nos arquivos legados, foi refutada.
  - O modo (iii), `effective_card` com Ruptura e evolução A/B, **não foi medido**. Ele continua
    obrigatório na Etapa 0.
- **R10** A Etapa 0, com `docs/spec377/folego_divergencias.py` (só importa e lê), faz três
  coisas:
  1. reproduz o número da R9 nos modos (i) bruto e (ii) catálogo;
  2. mede o modo (iii), `effective_card` com `ruptura=True` e com `evolved_cards` A/B, para toda
     Carta com `ruptura`/`evolucao`;
  3. roda o `lote-v2` de `cor_toque` e de `toque_corrosivo` com a função atual e com a nova
     (monkeypatch em memória), e grava `vitoria_ref`/`delta_pp`/bandeiras.

  Saída: `docs/spec377/folego_divergencias.json` + `.md`. Se o modo (iii) achar divergência nova,
  a etapa para e reporta antes de implementar.
- **R11** No fim há **uma** implementação. O outro nome vira um alias de uma linha, para
  preservar importadores e `monkeypatch`. Não há ciclo: os imports entre `cards` e
  `card_effects` são todos locais [R].
- **R12** Valor explícito inválido (`"custo_folego": "x"`) é tratado como ausente, como no jogo
  (`cards.py`, `try/except`). Hoje o lint levanta `ValueError`. `dano_base` não numérico também
  não pode levantar.

### Item 3 — "vivo" e "lado" no combate

- **R13** [F] Há **cinco** predicados de participação:

  | Predicado | Arquivo | Exclui |
  |---|---|---|
  | `card_effects._alive` | `card_effects.py:296` | `dead`, `estado_terminal`, `incapacitated`, `fled`; **não** exclui `surrendered`/`status` |
  | `conflict_orchestrator._alive` | `conflict_orchestrator.py:164` | `dead`, `fled`, `surrendered`, inconsciente, `incapacitated`, status `morto`/`fugiu`/`rendido`; **mantém** `estado_terminal` |
  | `scene_cards._alive` | `scene_cards.py:341` | delega a `card_effects._alive` |
  | `companion_orders._alive` | `companion_orders.py:56` | `dead` ou `status != "ativo"` |
  | `conflict_turn._targetable` | `conflict_turn.py:310` | `dead`, `fled`, `surrendered`, status `morto`/`fugiu`/`rendido`/`incapacitado`; **aceita** `estado_terminal` |

- **R14** [F] `_side_of` devolve `"heroes"` em `card_effects.py:391` e `"hero"` em
  `conflict_turn.py:291`. Não é bug: as duas são privadas, nenhum outro arquivo as importa, e
  cada uma só é comparada no próprio módulo (`card_effects.py:398-415`,
  `conflict_turn.py:303-307`). Ação: renomear (`_card_side`/`_turn_side`) e adicionar um teste de
  coerência por módulo. Os literais não mudam.
- **R15** [R] **Bug confirmado** na unidade: o inimigo rendido continua alvo de Carta. A marca é
  `surrendered=True`, gravada em `conflict_orchestrator.py:694,2750` e persistida entre rodadas
  pelo manifesto (`agents/combat.py:2404`). São três caminhos:
  - (1) `alvo == "inimigos"` inclui o rendido;
  - (2) uma Carta hostil sem alvo cai em `opp[:1]` (`card_effects.py:668-673`) e escolhe o
    rendido quando o id dele vem primeiro na ordenação;
  - (3) `_allies` de um inimigo (`card_effects.py:413-415`) inclui o rendido, então a cura ou o
    buff do baralho inimigo pode cair nele.

  Isso vale na rodada da rendição e nas seguintes. `orchestrator._alive` e `ct._targetable` já
  dão `False` para o rendido.
- **R16** [R] `estado_terminal` é intencional, com nuance:
  - `card_effects._alive` exclui o ator terminal de alvo de Carta;
  - `ct._targetable` **aceita** alvo terminal no ataque declarado (`conflict_turn.py:310-320`);
  - `orchestrator._can_act` impede o terminal de declarar turno (`conflict_orchestrator.py:177-181`).

  Ou seja, um ataque declarado num alvo terminal passa, mas uma Carta de área não o atinge. Fica
  como está (fora de escopo mudar). O teste de caracterização fotografa as três linhas.
- **R17** Regra do item: unificar **só** o que for bug provado, com teste vermelho antes. Hoje
  isso é só o R15. O que for contexto diferente de propósito muda apenas de nome, e cada nome
  ganha uma docstring de uma linha. Exemplos: `can_be_targeted_by_card`, `in_fight`,
  `can_receive_order`.

### Item 4 — esconder facção

- **R18** [F][R] As duas regras são **duas políticas de propósito**, de specs aprovadas pelo
  dono:
  - **SPEC-293**, a não-onisciência da Fase 2 (`faction_display.py:33 display_label`, via
    `world_utils.py:898-916 concealed_faction`). O **nome de combatente** de qualquer facção não
    conhecida, pública ou secreta, vira papel ou "Combatente desconhecido". A máscara vale em
    todo payload para o jogador: `api.py:2202,2376,4221,7893,7944`, `dossiers.py:433`,
    `player_knowledge.py:475`, `turn_delivery.py:59` e a narração em `narrative_sink.py:172`.
  - **SPEC-314** (`faction_gate.py:27,51,59,155`). O NPC, o contexto, a crônica, o RAG, o
    prólogo, as missões de lore e os rumores escondem só a facção **secreta** desconhecida
    (`agents/npc.py:1195-1575`, `context_builder.py:358-931`, `chronicle.py:158`,
    `lore_quests.py:415-444`, `prologue.py:224-227`, `rumor_adoption.py:107-109`,
    `secret_signatures.py:127-129`, `opening_threads.py:161`, `npc_self.py:96-98`). A D1 da
    SPEC-314 decidiu que "a facção pública desconhecida aparece no bloco do NPC, com nome e
    região".
  - [F] Ninguém começa conhecendo facção alguma: `known=True` só vem por revelação
    (`world_utils.py:569`, `faction_membership.py:373`).
- **R19** [F] A diferença visível fica nas facções **públicas**. Exemplo: o HUD mostra "Soldado"
  para o combatente da `legiao_ferro`, enquanto o NPC diz "Legião de Ferro". Nas 4 secretas do
  catálogo (`mao_sombria`, `filhos_chama_azul`, `druidas_renegados`, `cultistas_destilacao`), as
  duas políticas escondem; só o texto da máscara muda.
- **R20** A Etapa 0, com `docs/spec377/faccao_matriz.py`, gera para as 19 facções de
  `data/factions.json`, em três estados de intel (`{}`, `known`, `known+knows_goal`), a tabela:

  `fid | secreta? | display_label do 1º combatente | display_faction | mask_secret_names | concealed_name_map tem?`

  O resultado vai para `docs/spec377/faccao_matriz.md`, com a lista de pontos de uso da R18.
- **R21** O que fazer depende da [D4]:
  - (a), recomendado: manter as duas políticas. Cada módulo ganha uma docstring de topo que cita
    o outro e diz qual superfície cobre, e um teste fixa a matriz da R20. Nenhum arquivo é
    movido;
  - (b) ou (c): criar `services/faction_visibility.py` e deixar fachadas nos nomes antigos que
    mantenham efetivos os alvos de `monkeypatch` (`tests/test_spec315_claim.py:166-173`,
    `tests/test_spec351_checks.py:149`).

### Comum

- **R22** Cada item é um commit (ou série curta) revertível sozinho por `git revert` (W4). Os
  itens são independentes entre si.
- **R23** Antes de cada etapa, rodar a **W1 revisada** (auditoria §6.2), com três fontes cruzadas
  com os arquivos da etapa:
  1. branches vivas: com commit à frente da `main` e com commit nos últimos 7 dias;
  2. `git status --porcelain` de todos os worktrees, **inclusive o checkout principal**;
  3. specs `in-progress` que trabalham direto na `main` (arquivos da §3 delas + `git log
     --since=2.days --name-only main`).

  Interseção não vazia ⇒ a etapa espera. Em 03/11 [R], a única interseção é `world_utils.py`
  (`spec-370`), que o item 4 **só lê**. `agents/combat.py` (`spec-371`) não é editado por
  nenhum item.
- **R24** Integridade de eval:
  - o item 2 muda a **saída** do avaliador congelado no protocolo `lote-v2` das Cartas
    divergentes (R8), mesmo com `scripts/cards/sim.py` byte-igual;
  - por isso `EVAL_AUTHORING_REQUIRED: true`. O relatório antes/depois (R10) é registrado e
    publicado por `/eval-publish`, por um agente que **não** é o executor do produto (W5);
  - o item 2 não altera Carta, `data/cards/_orcamento.json`, faixa, baseline, `sim.py` nem
    `docs/spec335/arena_posturas.py`;
  - os casos de custo de Fôlego de `cards_combat` são da SPEC-380 (R2.5), não desta spec.

### Fora de escopo

- As ~60 cópias de `_fold` (R6 da auditoria): ficam na SPEC-378.
- Rebalancear Cartas e mexer no orçamento. Se a [D2] mover alguma faixa, isso vira uma spec de
  balanço separada.
- Mascarar na narração nomes soltos de facção. É uma política nova.
- Mudar a semântica de `estado_terminal`, fuga ou rendição no orquestrador. A R16 fica como está.
- Editar `agents/combat.py` e `world_utils.py`.
- Escrever os casos de eval de custo de Fôlego (SPEC-380).

## 3. Design técnico

**Arquivos novos**
- `docs/spec377/folego_divergencias.py`, `.json` e `.md` (R10).
- `docs/spec377/alive_consumidores.md` (Etapa 0 do item 3).
- `docs/spec377/faccao_matriz.py` e `.md` (R20).
- `tests/test_spec377_law_prune.py`, `tests/test_spec377_folego.py`,
  `tests/test_spec377_alive.py`, `tests/test_spec377_faccao.py`.
- `services/faction_visibility.py`, só se [D4] = (b) ou (c).

**Arquivos alterados**
- Item 1: `services/law.py` (adaptador), `services/world_engine.py` (uma linha) e
  `agents/storyteller.py` (só a ordem do `mark_hunters`, R7):
  ```python
  # services/law.py
  def day_hook(ctx) -> "DayHookResult":  # SPEC-377 R3/R6
      """Hook `post`: state_patch {"law_state": ...}; vazio se world_engine != on, lei off ou sem state."""
  # services/world_engine.py (_register_default_hooks, :729-738)
  register_day_hook("law", law.day_hook, stage="post", order=30)
  # agents/storyteller.py (:1691-1708): mover o bloco `if enc.get("reason") == "bounty_hunters":
  # updates.update(_law_mod.mark_hunters(...))` para DEPOIS de
  # `updates.update({k: v for k, v in sim_updates.items() if k != "npcs"})`
  ```
  A ordem 30 é indiferente: nenhum outro hook escreve `law_state` [R]. Em viagem de vários dias,
  o `carry` (`world_engine.py:508,514`) leva o estado podado ao dia seguinte. A SPEC-382 também
  extrai partes do `storyteller`; se este item pousar antes, a 382 herda a ordem nova (o
  coordenador sequencia).
- Item 2: `services/cards.py:447-468` e `services/card_effects.py:1596-1609`. Com [D2] = (a), a
  implementação mora em `card_effects.py` e lê `card.get("efeito") or primary_effect(card) or {}`.
  Ela usa `_DAMAGE_KINDS` e `DANO_BASE_FOLEGO_2` com as semânticas do jogo e protege `int()`
  (R12). `cards.custo_folego` vira alias. As constantes de `cards.py` ficam onde estão.
- Item 3: só nomes e docstrings em `card_effects.py`, `scene_cards.py`, `companion_orders.py`,
  `conflict_turn.py` e `conflict_orchestrator.py`, mais a correção do R15 em
  `card_effects._alive`: excluir `surrendered` e status `rendido`/`morto`/`fugiu`, mantendo a
  exclusão de `estado_terminal`.
- Item 4: docstrings em (a); fachadas em (b)/(c).

**Formato** de `folego_divergencias.json`:
`[{"id": "cor_toque", "arquivo": "data/cards/corruptor.json", "modo": "bruto|catalogo|ruptura|evo_a|evo_b", "jogo": 1, "lint": 0, "motivo": "b", "lote_v2": {"antes": {...}, "depois": {...}}}]`

## 4. Plano passo a passo

Antes de cada etapa: W1 revisada (R23) e RAM livre ≥ 3 GB. Os testes do escopo rodam com
`-n 2` no máximo; a suíte completa é do coordenador, no pouso.

### Item 1 — lei

1. **Caracterização** (`tests/test_spec377_law_prune.py`; `RPG_LAW=on` e `RPG_WORLD_ENGINE=on`
   via monkeypatch):
   - `test_residual_pos_suborno_hoje`: refaz a sonda da revisão. Entrada pós-suborno decaída,
     depois um crime entregue por patrulha: `known_at` antigo, `perguntaram_por_voce` já
     mostrado e `hunter_encounter` não vazio no mesmo clock;
   - `test_pena_e_multa_ja_zeram_residuo` (R2);
   - `test_daily_tick_poda_so_decaidas`.
2. **Testes do hook e da colisão**:
   - `test_hook_registrado_post`;
   - `test_hook_vazio_em_shadow_off_sem_state` (R6, com `RPG_WORLD_ENGINE=shadow` explícito);
   - `test_leitura_derivada_identica` (R4);
   - `test_save_antigo_carrega_e_e_podado` (R5);
   - `test_viagem_multidia_poda_uma_vez`;
   - `test_poda_e_cacadores_mesmo_turno_preserva_hunters_last_clock` (R7, pelo `storyteller_node`
     com emboscada `bounty_hunters` numa jurisdição e poda em outra);
   - `test_pos_poda_crime_novo_comeca_do_zero`, que inverte o 1º teste do passo 1. Este só é
     escrito depois da [D1].
3. **Implementação:** `law.day_hook` + registro + reordenação no `storyteller` (R7).
4. **Verificação:**
   - `pytest tests/test_spec377_law_prune.py tests/test_spec299_*.py tests/test_spec302*.py
     tests/test_storyteller*.py -n 2`;
   - playtest curto `--all --turns 10 --seed 0` com `RPG_LAW=on`, só como **guarda de
     regressão**: dificilmente exercita o caminho suborno → decaimento → crime. A prova são os
     testes dos passos 1–2 [R].
5. Commit `fix(law): register daily wanted prune as world day hook (SPEC-377)`.

### Item 2 — Fôlego

1. **Etapa 0** (R10): reproduz as 2 divergências, mede o modo (iii) e roda o `lote-v2` das
   2 Cartas antes/depois. Se o modo (iii) achar divergência nova, para e reporta.
2. Com [D2] = (a) e o modo (iii) limpo, **não** rodar a arena base. O jogo não muda (paridade de
   catálogo) e o lint dessas 2 Cartas também não [R].
3. **Testes** (`tests/test_spec377_folego.py`):
   - `test_uma_implementacao`;
   - `test_paridade_catalogo_com_jogo` (oráculo: o `.json` da Etapa 0, coluna `jogo`);
   - `test_dot_livre_custa_1_no_lint` (`cor_toque`, `toque_corrosivo`);
   - `test_valor_invalido_nao_quebra` (R12);
   - `tests/test_card_piles.py` (parametrizado de custo) verde sem mudar asserção.
4. **Implementação** (R11).
5. **Verificação:** `pytest tests/test_card_piles.py tests/test_card_effects_grammar.py
   tests/test_card_sim_v2.py tests/test_card_acervo_reparo.py tests/test_card_lint*.py
   tests/test_spec377_folego.py -n 2`, depois `git diff --exit-code main -- scripts/cards/sim.py
   docs/spec335/arena_posturas.py data/cards/_orcamento.json`.
6. **Eval authoring (W5):** outro agente publica o antes/depois do `lote-v2` por `/eval-publish`.
7. Commit `refactor(cards): single custo_folego implementation (SPEC-377)`.

### Item 3 — "vivo"/"lado"

1. **Etapa 0:** `alive_consumidores.md`, com cada chamador dos 5 predicados e o que ele decide.
2. **Caracterização** (`tests/test_spec377_alive.py`):
   - `test_rendido_alvo_de_carta_hoje`, com os 3 caminhos do R15 (área, fallback `opp[:1]`,
     `_allies` inimigo), na rodada da rendição **e na seguinte** (flag persistida);
   - `test_terminal_hoje`, com `fx._alive(terminal) is False`, `ct._targetable(terminal) is True`
     e `orch._can_act(terminal) is False` (R16);
   - `test_side_of_coerente_por_modulo` (R14).
3. **Implementação:**
   - commit puro (W3) só com renomes;
   - depois da [D3], commit de correção do R15, que inverte só os asserts do rendido.
4. **Verificação:** `pytest tests/test_card_effects*.py tests/test_conflict*.py
   tests/test_scene_cards*.py tests/test_companion_orders*.py tests/test_spec377_alive.py -n 2`.
   Em seguida, arena base `bash scripts/dev/py.sh docs/spec355/arena_spec355.py base
   --seeds 0:20 --out docs/spec377/arena-{antes,depois}.json`, em série, com
   `run_in_background` e timeout, porque a correção muda a escolha de alvo na luta. Faixa aceita
   pelo dono: 45–85 %. Postura fora da faixa ⇒ para e reporta.

### Item 4 — facção

1. **Etapa 0:** `faccao_matriz.py` e `.md` (R20).
2. **Caracterização** (`tests/test_spec377_faccao.py`):
   - `test_matriz_atual` (4 secretas + `legiao_ferro`, `clas_combate`);
   - `test_narracao_mascara_combatente_de_publica_desconhecida`;
   - `test_bloco_npc_lista_publica_e_oculta_secreta`.
3. **Decisão [D4]** e implementação (R21).
4. **Verificação:** `tests/test_spec293_*`, `test_spec294_*`, `test_spec298_*`,
   `test_spec314_*`, `test_spec315_*`, `test_spec351_checks.py` e `test_spec377_faccao.py`, com
   `-n 2`.
5. Commit único do item.

## 5. Critérios de aceite

- [ ] Item 1: hook registrado com guard `world_engine.mode()=="on"`; R2–R7 com testes, incluindo
      a colisão `mark_hunters`; playtest curto sem violação `law.*` nova
- [ ] Item 2: Etapa 0 publicada com o modo (iii); uma implementação; paridade com o catálogo do
      jogo; `lote-v2` antes/depois publicado via `/eval-publish` (W5); R24 sem diff de arquivo
- [ ] Item 3: mapa publicado; R14 renomeado; R15 corrigido nos 3 caminhos e nas rodadas
      seguintes; R16 fotografado e intacto; arena 45–85 %
- [ ] Item 4: matriz publicada; [D4] aplicada; testes 293/294/298/314/315/351 verdes
- [ ] W1 revisada registrada por etapa; um commit por item (W4)
- [ ] Revisão independente (Opus) que reroda pelo menos 1 caracterização (W7)
- [ ] `uv run pytest` verde (suíte completa, coordenador, 1× no pouso)
- [ ] Saves antigos continuam carregando (R5)
- [ ] Nenhum `with_structured_output` novo (não se aplica)

## 6. Smoke test com LLM real

Os itens 3 e 4 tocam o que o jogador vê. São ≤ 6 requests, na API local com `ROUTES`
(DeepSeek), `RPG_CARD_DECK=on`, `RPG_LAW=on` e `RPG_WORLD_ENGINE=on`.

1. **Combate.** Encontro com combatente de `filhos_chama_azul` (secreta e desconhecida): o HUD e
   a narração mostram o papel ou "Combatente desconhecido", nunca "Chama Azul". Jogar 1 rodada
   de Cartas com Carta de área. A rendição depende do LLM e não é garantida: se não houver
   rendição, o R15 fica provado só offline, e o hand-back declara isso.
2. **NPC.** 2 turnos com um NPC na região da `mao_sombria`: o texto não nomeia a Mão Sombria, e
   o evento `faction_block` traz `hidden_secret ≥ 1`.
3. **Pergunta direta.** Perguntar ao NPC "quem manda aqui?": a facção pública aparece pelo nome
   (SPEC-314 D1) e a secreta não. Se [D4] for (b) ou (c), conferir a regra nova no texto e no HUD.
4. **Registro no hand-back:** provider/modelo, número de requests e os trechos que provam 1–3.

## 7. Riscos & compatibilidade

- **Saves antigos:** o item 1 poda entradas decaídas no 1º dia simulado. Não há campo novo nem
  bump de schema. Os itens 2–4 não tocam schema.
- **Arena/balanço:**
  - item 2 com [D2] = (a): o jogo não muda; o `lote-v2` muda só para 2 Cartas legadas, e isso é
    medido e publicado;
  - item 3: a correção do R15 muda a escolha de alvo, por isso a arena roda antes e depois;
  - o avaliador congelado não é editado.
- **Ordem no storyteller:** a colisão do R7 é coberta por teste. A SPEC-382 herda a ordem nova.
- **Strings derivadas de ids:**
  - o nome do hook `"law"` aparece no `log_fallback(... hook=name)` (`world_engine.py:140`);
  - não mudar `GENERIC_LABEL`/`UNKNOWN_FACTION`/`MASK_TEXT`, que oráculos e e2e procuram como
    texto;
  - os aliases por id de facção em `faction_gate._EXTRA_ALIASES` ficam como estão;
  - evento novo de telemetria exige registro em `observability/events.py`.
- **Sessões paralelas:** a W1 revisada roda antes de cada etapa. `world_utils.py` (`spec-370`)
  só é lido.
- **Monkeypatch:** os aliases e as fachadas preservam `cards.custo_folego` e `faction_gate.*`.
- **MockLLM/FallbackLLM:** sem mudança. **Quota/latência:** um hook O(n) em `wanted` por dia
  simulado.

## 8. Decisões do dono

- **D1 — Poda da lei.** (a) Registrar o hook e corrigir a ordem do `mark_hunters`
  (**recomendado**). O efeito no jogo se limita a **depois de um suborno**: o crime novo deixa de
  herdar a notícia instantânea, o caçador sem aviso e o atraso vencido. Isso foi confirmado por
  sonda, e o alcance é pequeno. No staging a lei está `on` (`scripts/staging/staging_flags.json:11`).
  (b) Apagar `daily_tick` e manter o resíduo.
- **D2 — Regra de Fôlego.** (a) A regra do jogo (`dot`/`contra_ataque` livre custa 1). É
  **recomendada e tratada como adotada na aprovação da spec, salvo objeção**: o jogo não muda, o
  lint das 2 Cartas não muda, e a SPEC-328 R6 diz "0 se livre e sem dano" (dot é dano). Só muda o
  `lote-v2` de `cor_toque`/`toque_corrosivo`, que é publicado. (b) A regra do lint: as duas
  Cartas ficam mais baratas **no jogo**, e a arena precisa ser medida.
- **D3 — "Vivo" no combate.**
  - (a) O rendido deixa de ser alvo de Carta nos 3 caminhos do R15 (**recomendado**; é bug
    confirmado e alinha com `orchestrator._alive`/`ct._targetable`).
  - (b) Estado Terminal continua como está: fora da Carta, dentro do ataque declarado
    (**recomendado**; mudar isso é outra spec).
- **D4 — Esconder facção.**
  - (a) Manter as duas políticas (**recomendado**). As duas são decisões suas já aprovadas: a
    SPEC-293 (o combatente de facção não conhecida mostra o papel) e a SPEC-314 D1 (o NPC cita a
    pública pelo nome e esconde a secreta).
  - (b) "Só secreta": **desfaz a SPEC-293**. O HUD mostra "Soldado da Legião de Ferro" desde o
    1º turno.
  - (c) "Qualquer desconhecida": **contradiz a SPEC-314 D1**. O NPC para de citar facções
    públicas.
- **D5 — Ordem.** A 368 já pousou, então os 4 itens podem seguir em qualquer ordem, um por vez
  (W6), cada um depois da W1 revisada. Recomendado: 1 → 3 → 4 → 2. O item 2 depende do
  publicador de eval.

## 9. Resposta à revisão

Revisão: `handoffs/SPEC-377-independent-review.md` (`SAFE-WITH-CHANGES`). Todas as mudanças
pedidas foram aplicadas:

| ID | O que mudou na spec |
|---|---|
| P1-1 | R7 e §3: `agents/storyteller.py` entrou no item 1 (reordenar `mark_hunters`). Novo teste `test_poda_e_cacadores_mesmo_turno_preserva_hunters_last_clock`. Também conferi os outros escritores de `law_state` (`:2008/2417`, `:2314/2418`, fallback `:2657`): já leem o estado podado e ficam como estão. |
| P1-2 | R8/R24: o `lote-v2` muda de saída. `EVAL_AUTHORING_REQUIRED` passou para `true`, com publicação pela W5, e a medição antes/depois entrou na R10. |
| P2-1 | R9/R10: número real (2 Cartas, motivo (b), lint igual). D2 fica recomendada como adotada na aprovação e a arena base saiu do item 2. **Ressalva:** o modo (iii) (Ruptura/evolução) continua obrigatório, porque a revisão não o mediu. |
| P2-2 | R6: guard `world_engine.mode()=="on"` dentro do hook; a frase do modelo `npc_world` saiu. |
| P2-3 | R2/D1: o efeito é "só após suborno"; pena, multa e decaimento natural não mudam. |
| P2-4 | §4 item 1 passo 4: o playtest é guarda de regressão, não prova. |
| P2-5 | R15: 3 caminhos mais a rodada seguinte; a arena do item 3 virou obrigatória. |
| P2-6 | R13/R16: a nuance de `ct._targetable(terminal) is True` entrou na tabela e no teste. |
| P3-1 | Números de linha atualizados depois do pouso da 368 (`cards.py:447`, `card_effects.py:1596`, `card_piles.py:525,537,588,738`). |
| P3-2 | "Depende de", R23 e D5: a 368 pousou; W1 revisada; única interseção é `world_utils.py` (só leitura). |

Nenhum achado foi rejeitado.
