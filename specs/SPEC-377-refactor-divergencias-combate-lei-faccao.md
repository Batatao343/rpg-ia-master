# SPEC-377 — Divergências de regra: poda da lei, custo de Fôlego, "vivo" no combate e esconder facção

> **Status:** `draft`
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** `docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md` §3 (R2–R5) e §6 (letra C → SPEC-377; regras W1–W8)
> **Depende de:** SPEC-299 (`done`), SPEC-302 (`done`), SPEC-293/314 (`done`), SPEC-328/330 (`done`). Itens 2 e 3 só depois que a branch `spec-368` pousar (W1).
> **Desbloqueia:** SPEC-378 (helpers comuns: começa depois de 376/377, §6.3 da auditoria)
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true` · **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato conferido no código em 03/11 (arquivo:linha) · **[H]** hipótese que a Etapa 0 do item prova ou derruba · **[D]** decisão do dono (§8).

---

## 1. Contexto & Objetivo

A auditoria de 03/11 achou quatro pontos onde o mesmo conceito tem duas regras. Ao contrário das
outras specs da onda, esta **muda comportamento de propósito**. Por isso nenhum item pode ser
tratado como refatoração pura (W2/W3 não bastam). Cada item segue a mesma ordem:

1. **caracterização:** testes que fotografam o comportamento atual dos dois lados;
2. **medição:** script ou tabela que mostra quantos casos reais divergem;
3. **decisão do dono** (§8) sobre qual regra vale;
4. só então a mudança, num commit próprio e revertível (W4).

Se a medição der **zero** divergência na prática, a mudança é trivial e não precisa de decisão.

Na conferência, a auditoria errou em três pontos. As correções estão nos itens abaixo:
- o `daily_tick` **muda o jogo**, não só o tamanho do save;
- o custo de Fôlego das lutas da arena **já** usa a regra do jogo;
- `_side_of` com `"hero"`/`"heroes"` **não** é bug, e existem mais de 3 semânticas de "vivo".

## 2. Requisitos

### Item 1 — poda de `wanted` (lei)

- **R1** [F] `services/law.py:1719 daily_tick(state, day) -> dict` não tem chamador. A docstring
  diz "Gancho da SPEC-302". `specs/SPEC-299-lei-crime-por-regiao.md:7,291,517` diz que a 302 o
  consome, mas a SPEC-302 não cita `law` nem `daily_tick`. `services/world_engine.py:735-738` só
  registra `calendar`/`npc_world`/`fauna`/`rumors`. Também não há teste de `daily_tick`.
- **R2** [F] A auditoria disse que registrar o hook "só poda o save". **Isso é falso.** O
  decaimento de `heat` é calculado na leitura (`effective_heat`, `law.py:295-304`), mas uma
  entrada de `wanted` com heat efetivo 0 e `bounty` 0 continua sendo lida. Isso acontece, por
  exemplo, depois de um suborno: `resolve_bribe` chama `_clear_wanted(keep_heat=heat//2)`, que
  zera o bounty e **mantém** `known_at`/`signals_shown`/`hunters_last_clock`
  (`law.py:1353-1357`, `1135-1143`). Essa entrada altera o jogo em quatro pontos:
  - (a) `_spread_known_at` usa `min(known.get(loc), arrive)` (`law.py:733,741`). Num crime novo
    na mesma jurisdição, a notícia "já chegou" nos locais antigos, sem esperar o mensageiro;
  - (b) `"perguntaram_por_voce"` continua em `signals_shown`. O aviso telegrafado não volta a
    aparecer, mas o caçador pode vir (`law.py:913,1081`);
  - (c) `first = min(known_at.values())` (`law.py:1078`) faz o atraso dos caçadores já contar
    como vencido;
  - (d) `law["wanted"]` não vazio mantém `last_loc` atualizado (`law.py:850`). Isso muda quando
    `recognition_check` roda.
  Podar reinicia tudo isso. Na prática, o hook **corrige** a memória residual do crime antigo.
- **R3** Com o hook registrado e o motor de mundo `on`, as entradas com `effective_heat == 0`,
  sem `capital` e sem `bounty` somem na virada do dia. As demais ficam byte-iguais.
- **R4** `level()`/`effective_heat()` de toda jurisdição que **continua** no save dá o mesmo
  valor antes e depois do hook. Uma jurisdição podada passa a ler `limpo`/0, como já lia antes.
- **R5** Save antigo (sem `law_state`, ou com `wanted` cheio de entradas decaídas) carrega por
  `normalize_law` (`law.py:262`) e é podado no primeiro dia simulado, sem erro.
- **R6** Com `RPG_WORLD_ENGINE` diferente de `on`, com `RPG_LAW=off` ou com `ctx.state is None`,
  o hook devolve `DayHookResult()` vazio. O modelo é o guard de `npc_world.day_hook`
  (`npc_world.py:721-723`): o modo shadow nunca escreve `law_state`.

### Item 2 — `custo_folego` duplicado

- **R7** [F] Existem duas funções com o mesmo nome:
  - `services/cards.py:442`, usada pelo jogo: `card_piles.py:496,508,528,654`,
    `card_rewards.py:661`, `agents/combat.py:1102`;
  - `services/card_effects.py:1595`, usada pelo lint, pelo orçamento e pelo relatório:
    `card_lint.py:169,352`, `card_effects.py:1695,1708` (faixa do orçamento),
    `scripts/cards/sim.py:303,434`, `scripts/bestiario/gerar_mecanica.py:220`.

  Elas divergem em três pontos:
  - (a) `dano_base >= 8` → 2 vale para **qualquer** kind no jogo, mas só para `kind == "dano"`
    no lint;
  - (b) Carta `livre` de kind `dot`/`contra_ataque` custa 1 no jogo (`_DAMAGE_KINDS`,
    `cards.py:439,461`) e 0 no lint;
  - (c) o jogo lê `card["efeito"]`, e o lint lê `primary_effect(card)` (`card_effects.py:193`),
    que prefere `efeitos`. No catálogo, `cards._load_cards` chama `card_effects.materialize`
    (`cards.py:182`, `card_effects.py:217`), que preenche `efeito` só quando ele falta. Uma Carta
    com `efeito` **e** `efeitos` diferentes, ou a Ruptura de `effective_card` (`cards.py:251-252`,
    que troca `efeito` e mantém `efeitos`), lê efeitos diferentes nos dois lados.
- **R8** [F] Correção da auditoria: as **lutas** da arena pagam Fôlego pela regra do jogo.
  `scripts/cards/sim.py:161,243,267` usa `card_piles`, que chama `cards.custo_folego`. A regra do
  lint só entra no relatório "dano/proteção por Fôlego" (`sim.py:301-320`), no lint e na faixa
  do orçamento. Logo, a taxa de vitória por Postura **não** muda se a regra do jogo for a
  vencedora.
- **R9** Etapa 0 obrigatória: `docs/spec377/folego_divergencias.py` (só importa e lê) passa por
  todas as Cartas. Ele roda em três modos:
  - (i) bruto, como o lint vê;
  - (ii) catálogo `cards.all_cards()`, como o jogo vê;
  - (iii) `effective_card` com Ruptura e com evolução A/B.

  O script grava `docs/spec377/folego_divergencias.json` e a tabela
  `id | arquivo | jogo | lint | motivo (a/b/c)`. Hoje 470 das ~1.421 Cartas têm `custo_folego`
  explícito e ficam fora da divergência. [H] As divergências que sobrarem se concentram nos
  arquivos legados sem custo explícito (`arcanista.json`, `bestiario.json`, `tiers_5_plus.json`,
  `inimigos/*`).
- **R10** Zero divergências nos modos (ii)/(iii) e no modo (i) → unificar sem mudar nenhum
  número. Com divergência → [D2] escolhe a regra. A Etapa 0 também mede quais Cartas mudam de
  faixa no orçamento (`card_effects.py:1695`), quantos avisos do `card_lint` aparecem ou somem e
  o relatório por Fôlego do `sim.py`.
- **R11** No fim, só existe **uma** implementação. O outro nome vira um alias de uma linha
  (`custo_folego = card_effects.custo_folego`, ou o inverso), para preservar os importadores e
  os `monkeypatch`. Não há ciclo de import: hoje `card_effects` só importa `cards` dentro de
  função (`card_effects.py:909,1005,1166,1183,1453`) e `cards` só importa `card_effects` dentro
  de função (`cards.py:177,233`).
- **R12** Valor explícito inválido (`"custo_folego": "x"`) não pode quebrar nenhum dos dois
  caminhos. Hoje o jogo ignora o valor e deriva o custo (`cards.py:446-449`), e o lint levanta
  `ValueError` (`card_effects.py:1597-1598`). A regra única segue o jogo e trata o valor como
  ausente.

### Item 3 — "vivo" e "lado" no combate

- **R13** [F] Há **cinco** predicados de participação, não três:

  | Predicado | Arquivo | Exclui |
  |---|---|---|
  | `card_effects._alive` | `card_effects.py:296` | `dead`, `estado_terminal`, `incapacitated`, `fled`; **não** exclui `surrendered`/`status` |
  | `conflict_orchestrator._alive` | `conflict_orchestrator.py:164` | `dead`, `fled`, `surrendered`, inconsciente, `incapacitated`, status `morto`/`fugiu`/`rendido`; **mantém** `estado_terminal` |
  | `scene_cards._alive` | `scene_cards.py:341` | delega a `card_effects._alive` |
  | `companion_orders._alive` | `companion_orders.py:56` | `dead` ou `status != "ativo"` |
  | `conflict_turn._targetable` | `conflict_turn.py:310` | `dead`, `fled`, `surrendered`, status `morto`/`fugiu`/`rendido`/`incapacitado` |

- **R14** [F] `_side_of` devolve `"heroes"` em `card_effects.py:391-395` e `"hero"` em
  `conflict_turn.py:291-300`. **Não há cruzamento.** As duas são privadas, nenhum outro módulo,
  teste ou script as importa, e cada uma só é comparada dentro do próprio módulo
  (`card_effects.py:399-408`, `conflict_turn.py:303-307`). Ação: renomear para deixar o
  contrato explícito (`_card_side`/`_turn_side`) e adicionar um teste de que cada uma é coerente
  dentro do módulo. Os literais não mudam.
- **R15** [H] Candidato a bug real: o inimigo que se rende é marcado com `actor["surrendered"] =
  True` na declaração (`conflict_orchestrator.py:694,2750`). Depois disso, `card_effects._alive`
  ainda o conta em `_opponents`/`_allies` (`card_effects.py:398-415`). Na mesma rodada, um
  efeito de Carta em área ou "todos os inimigos" pode atingir quem já se rendeu. A Etapa 0 prova
  ou derruba isso com um teste de caracterização.
- **R16** [H] `estado_terminal` fora de `card_effects._alive` e dentro de `orchestrator._alive`
  parece intencional: o ator terminal só reage ou estabiliza (`conflict_orchestrator.py:177-179`;
  `death_flow.py:130`) e não é alvo de efeito novo. A Etapa 0 confirma com teste e com a spec de
  origem. Se for intencional, **não** unificar.
- **R17** Regra do item: unificar **só** o que a Etapa 0 provar que é bug, com teste vermelho
  antes. O que for contexto diferente de propósito só muda de nome
  (`can_be_targeted_by_card`, `in_fight`, `can_receive_order`, ...), e cada nome ganha uma
  docstring de uma linha. Os nomes antigos ficam como alias se houver `monkeypatch` ou import
  externo; hoje não há, segundo o grep de 03/11.

### Item 4 — esconder facção

- **R18** [F] As duas regras atendem a **specs diferentes**. A auditoria tratou como duplicação
  algo que foi desenhado assim:
  - **SPEC-293** (`faction_display.py:33 display_label`, via `world_utils.py:898-916
    concealed_faction`) esconde o **nome de combatente** que carrega o nome de **qualquer**
    facção que o jogador não conhece (`intel[fid].known` falso), seja ela pública ou secreta. A
    máscara vale em todo payload para o jogador: `api.py:2202,2376,4221,7893,7944`,
    `dossiers.py:433`, `player_knowledge.py:475`, `turn_delivery.py:59` e a narração em
    `narrative_sink.py:172`. O mapa só tem nomes de combatentes (bestiário, `enemies`,
    manifesto: `faction_display.py:53-84`), não nomes de facção soltos.
  - **SPEC-314** (`faction_gate.py:27 is_secret`, `:51 known_to_player`, `:59
    display_faction`, `:155 mask_secret_names`) esconde a facção **secreta** desconhecida no
    bloco do NPC, no contexto, na crônica, no RAG, no prólogo, nas missões de lore e nos rumores
    (`agents/npc.py:1195-1575`, `context_builder.py:358-931`, `chronicle.py:158`,
    `lore_quests.py:415-444`, `prologue.py:224-227`, `rumor_adoption.py:107-109`,
    `secret_signatures.py:127-129`, `opening_threads.py:161`, `npc_self.py:96-98`).
  - [F] Ninguém começa conhecendo facção alguma: `faction_intel` só ganha `known=True` por
    revelação (`world_utils.py:569`, `faction_membership.py:373`).
- **R19** [F] A divergência visível fica nas facções **públicas**. Exemplo: o combatente da
  `legiao_ferro` aparece como "Soldado" no HUD até a revelação, enquanto o NPC pode dizer
  "Legião de Ferro" no texto, porque o bloco do NPC lista facções públicas
  (`faction_gate.py:295-303`). Nas 4 secretas do catálogo (`data/faction_membership.json`:
  `mao_sombria`, `filhos_chama_azul`, `druidas_renegados`, `cultistas_destilacao`, mais as que o
  grafo marcar `visibility != public`), as duas regras escondem. Elas só diferem no texto da
  máscara ("Iniciado" ou "Combatente desconhecido" contra "[facção desconhecida]" ou "uma facção
  desconhecida").
- **R20** Etapa 0: `docs/spec377/faccao_matriz.py` gera, para cada uma das 19 facções de
  `data/factions.json` em três estados de intel (`{}`, `known`, `known+knows_goal`), a tabela:

  `fid | secreta? | display_label do 1º combatente do bestiário | display_faction | mask_secret_names("<nome>") | concealed_name_map tem?`

  e grava em `docs/spec377/faccao_matriz.md`. O documento também lista os pontos de uso de
  cada regra (R18).
- **R21** Depois da [D4]:
  - (a) duas políticas mantidas, só com nomes explícitos (recomendado): `faction_display` e
    `faction_gate` ganham uma docstring de topo que cita a outra e diz qual superfície cada uma
    cobre, e um teste fixa a matriz da R20. Nenhum arquivo é movido;
  - (b) ou (c) uma regra só: criar `services/faction_visibility.py` com a regra escolhida e
    deixar `faction_gate.py`/`faction_display.py` como fachadas que reexportam os nomes. O
    teste `tests/test_spec315_claim.py:166-173` faz `monkeypatch` em `faction_gate.is_secret` e
    `known_to_player`, e `tests/test_spec351_checks.py:149` em `faction_gate.beat_leaks`. A
    fachada precisa manter esses alvos efetivos (os chamadores internos passam pelo módulo
    fachada) ou os testes mudam só o alvo (W3).

### Comum

- **R22** Cada item é um commit (ou série curta) revertível sozinho por `git revert` (W4). Os
  itens são independentes entre si.
- **R23** Antes de cada etapa, rodar a trava W1 (`auditoria §6.2`) com a lista de arquivos da
  etapa. Interseção não vazia ⇒ a etapa espera. Em 03/11, a `spec-368` edita `services/cards.py`,
  `card_effects.py`, `card_piles.py` e `card_deck_round.py`, e a `spec-371` edita
  `agents/combat.py`, `enemy_intent`, `enemy_decks` e `playtest/*`.
- **R24** Integridade de eval: mudar `card_effects.custo_folego` muda uma métrica do avaliador
  congelado (`scripts/cards/sim.py`, congelado pelas SPEC-341 R1/355 R50/362). O item 2 **não**
  mexe em nenhuma Carta, orçamento, faixa ou baseline no mesmo commit. Também não edita
  `sim.py`, `docs/spec335/arena_posturas.py` nem `data/cards/_orcamento.json`. O relatório
  antes/depois vai em `docs/spec377/`.

### Fora de escopo

- As ~60 cópias de `_fold` (R6 da auditoria): ficam na SPEC-378.
- Rebalancear Cartas ou mexer no orçamento por causa da regra de Fôlego escolhida. Se a [D2]
  mover Cartas de faixa, o ajuste vira uma spec de balanço separada.
- Mascarar na narração nomes de facção soltos (só os de combatente já são mascarados). É uma
  política nova; se o dono quiser, vira outra spec.
- Mudar a semântica de `estado_terminal`, rendição ou fuga no orquestrador.
- Tocar `agents/combat.py` (spec-371) e mover `world_utils.concealed_faction`.
- Teste de `law.daily_tick` fora do hook (shadow/on do `RPG_LAW` já é coberto pela SPEC-299).

## 3. Design técnico

**Arquivos novos**
- `docs/spec377/folego_divergencias.py` e `.json`: Etapa 0 do item 2. Só importa e lê; roda com
  `bash scripts/dev/py.sh docs/spec377/folego_divergencias.py`.
- `docs/spec377/alive_consumidores.md`: Etapa 0 do item 3. Mapa
  `chamador | predicado | o que decide (alvo, ordem, fim de luta, ordem de aliado)`.
- `docs/spec377/faccao_matriz.py` e `.md`: Etapa 0 do item 4.
- `tests/test_spec377_law_prune.py`, `tests/test_spec377_folego.py`,
  `tests/test_spec377_alive.py`, `tests/test_spec377_faccao.py`.
- Só se [D4] = (b) ou (c): `services/faction_visibility.py`.

**Arquivos alterados**
- Item 1: `services/world_engine.py`, que ganha uma linha em `_register_default_hooks`
  (`world_engine.py:729-738`), e `services/law.py`, que ganha o adaptador:
  ```python
  # services/law.py
  def day_hook(ctx) -> "DayHookResult":  # SPEC-377 R3/R6
      """Hook `post` do world_engine: devolve state_patch {"law_state": ...} ou vazio."""
  # services/world_engine.py
  register_day_hook("law", law.day_hook, stage="post", order=30)
  ```
  O `state_patch` entra no estado do turno em `agents/storyteller.py:1364-1368`, antes de
  `law.turn_updates` (`agents/turn_finalizer.py:69`), que lê `{**state, **updates}`. A ordem é
  segura porque só esse hook escreve `law_state`. A ordem 30 roda depois de `rumors`
  (`world_engine.py:738`); a poda não depende dos outros hooks. Em viagem de vários dias, o
  `carry` (`world_engine.py:508,514`) leva o estado podado para o dia seguinte. O
  `daily_tick(state, day)` existente continua sendo o núcleo puro.
- Item 2: `services/cards.py:442-463` e `services/card_effects.py:1595-1608`. Uma das duas vira
  alias (R11). Sugestão, se [D2] = regra do jogo: a implementação mora em `card_effects.py`
  (perto de `primary_effect`) e lê `card.get("efeito") or primary_effect(card) or {}`. No
  catálogo isso é idêntico ao jogo de hoje; no lint de Carta bruta, é idêntico ao `materialize`.
  `cards.custo_folego` vira alias. `FOLEGO_MAX_CARTA`/`DANO_BASE_FOLEGO_2` continuam em
  `cards.py` (há importadores), e `card_effects` passa a usá-los.
- Item 3: `card_effects.py`, `scene_cards.py`, `companion_orders.py`, `conflict_turn.py`,
  `conflict_orchestrator.py`, só com nomes e docstrings e, se R15 for provado, a correção pontual
  em `card_effects._alive`.
- Item 4: `faction_display.py` e `faction_gate.py`, com docstrings (a) ou fachadas (b/c).

**Formatos**: `folego_divergencias.json` = `[{"id": "bomba_estopim", "arquivo":
"data/cards/...json", "modo": "catalogo|bruto|ruptura|evo_a|evo_b", "jogo": 1, "lint": 0,
"motivo": "b"}]` (o id é só exemplo de formato; o script lista o real).

## 4. Plano passo a passo

Cada item é independente. Antes de cada etapa: W1 + RAM livre ≥ 3 GB. Os testes do escopo rodam
com `-n 2` no máximo; a suíte completa é do coordenador, no pouso.

### Item 1 — lei (pode começar já, se a W1 der vazio para `law.py`/`world_engine.py`)

1. **Caracterização** (`tests/test_spec377_law_prune.py`, com `RPG_LAW=on` e
   `RPG_WORLD_ENGINE=on` via monkeypatch):
   - `test_wanted_residual_altera_known_at_hoje`: uma entrada decaída pós-suborno com
     `known_at` antigo, seguida de um crime novo, deixa `known_at` ≤ clock nos locais antigos.
     Fotografa o efeito (a) da R2;
   - `test_wanted_residual_mantem_sinal_e_atraso_de_cacador`: efeitos (b) e (c);
   - `test_daily_tick_poda_so_decaidas`: `capital`/`bounty`/heat > 0 ficam byte-iguais.
2. **Testes do hook**:
   - `test_hook_registrado_post_order_30`;
   - `test_hook_vazio_em_shadow_off_e_sem_state` (R6);
   - `test_leitura_derivada_identica` (R4: `level`/`effective_heat` de toda jurisdição antes e
     depois);
   - `test_save_antigo_carrega_e_e_podado` (R5: sem `law_state`; e com 3 entradas decaídas e 1
     viva);
   - `test_viagem_multidia_poda_uma_vez` (carry);
   - `test_pos_poda_crime_novo_comeca_do_zero`. Este teste **inverte** a foto do passo 1 e só é
     escrito depois da [D1].
3. **Implementação:** `law.day_hook` mais o registro.
4. **Verificação:**
   - `pytest tests/test_spec377_law_prune.py tests/test_spec299_*.py tests/test_spec302*.py -n 2`;
   - playtest curto com `RPG_LAW=on`:
     `bash scripts/dev/py.sh -m playtest run --all --turns 10 --seed 0`. Violações `law.*`
     por perfil iguais ou menores que antes; diferença registrada no hand-back.
5. Commit `fix(law): register daily wanted prune as world day hook (SPEC-377)`.

### Item 2 — Fôlego (espera a `spec-368`)

1. **Etapa 0:** `folego_divergencias.py` (R9). Em seguida, medir R10:
   - `card_lint` antes/depois simulado: o script troca a função via `monkeypatch` em memória,
     sem editar produto;
   - faixa do orçamento;
   - `sim.py --lote` em 1 arquivo de Postura, só para o relatório por Fôlego.
2. **Decisão:** zero divergências → passo 4 direto. Com divergências → tabela no hand-back e
   pedido da [D2].
3. **Se [D2] escolher a regra do lint** (muda o jogo): arena por Postura antes e depois,
   `bash scripts/dev/py.sh docs/spec355/arena_spec355.py base --seeds 0:20 --out
   docs/spec377/arena-{antes,depois}.json`, em série, `run_in_background`, com timeout
   (~40 min). Faixa aceita pelo dono: 45–85 %. Postura que sair da faixa ⇒ para e reporta. A
   escolha também é revista se a Etapa 0 mostrar que a regra do lint baixa custo de Carta usada
   em jogo.
4. **Testes** (`tests/test_spec377_folego.py`):
   - `test_uma_implementacao` (`cards.custo_folego is card_effects.custo_folego`, ou um chama o
     outro);
   - `test_paridade_catalogo`: para toda Carta do catálogo, o valor novo é igual ao valor do
     jogo de hoje. Se [D2] = jogo, o oráculo é o `.json` da Etapa 0;
   - `test_valor_invalido_nao_quebra` (R12);
   - `test_card_piles.py:51-66` continua verde sem mudar asserção.
5. **Implementação** (R11). **Verificação:** `pytest tests/test_card_piles.py
   tests/test_card_effects_grammar.py tests/test_card_sim_v2.py tests/test_card_acervo_reparo.py
   tests/test_card_lint*.py tests/test_spec377_folego.py -n 2`. Depois,
   `git diff --exit-code main -- scripts/cards/sim.py docs/spec335/arena_posturas.py
   data/cards/_orcamento.json` (R24).
6. Commit `refactor(cards): single custo_folego implementation (SPEC-377)`.

### Item 3 — "vivo"/"lado" (espera a `spec-368`; W1 também para `conflict_orchestrator.py`)

1. **Etapa 0:** `alive_consumidores.md`, com cada chamador dos 5 predicados (grep
   `_alive(`/`_targetable(` em `services/`) e o que ele decide.
2. **Caracterização** (`tests/test_spec377_alive.py`):
   - `test_carta_em_area_ignora_rendido_hoje` (R15): monta a cena pelo orquestrador, com um
     inimigo que se rende na declaração e uma Carta de efeito em todos os inimigos. Fotografa se
     o rendido recebe o efeito;
   - `test_terminal_nao_e_alvo_de_carta` (R16);
   - `test_side_of_coerente_por_modulo` (R14).
3. **Decisão:** R15 provado ⇒ [D3a]. R16 intencional ⇒ só renomear.
4. **Implementação:** renomes com alias se preciso; a correção de R15, se aprovada, inverte o
   teste do passo 2. **Verificação:** `pytest tests/test_card_effects*.py tests/test_conflict*.py
   tests/test_scene_cards*.py tests/test_companion_orders*.py tests/test_spec377_alive.py -n 2`.
   Arena da Postura de controle/área mais afetada, só se R15 mudar comportamento:
   `arena_spec355.py base --seeds 0:20`, faixa 45–85 %.
5. Dois commits: `refactor(combat): explicit names for liveness predicates` (puro, W3) e, se
   houver, `fix(cards): surrendered actors are not card targets (SPEC-377)`.

### Item 4 — facção (pode começar já, se a W1 der vazio)

1. **Etapa 0:** `faccao_matriz.py` e `.md` (R20).
2. **Caracterização** (`tests/test_spec377_faccao.py`):
   - `test_matriz_atual` fixa a tabela da R20 para as 4 secretas e 2 públicas (`legiao_ferro`,
     `clas_combate`);
   - `test_narracao_mascara_combatente_de_publica_desconhecida`;
   - `test_bloco_npc_lista_publica_e_oculta_secreta`.
3. **Decisão [D4].**
4. **Implementação:** (a) docstrings e o teste viram contrato; (b)/(c) `faction_visibility.py`
   com fachadas, e os testes de `test_spec293_*`, `test_spec294_*`, `test_spec298_*`,
   `test_spec314_*`, `test_spec315_*` e `test_spec351_checks.py` verdes sem mudar asserção, salvo
   as que a regra escolhida inverter (listadas no hand-back).
5. **Verificação:** os arquivos acima com `-n 2`, mais o playtest curto (W2.3), com mesma
   contagem de `e:concealed_faction_name:*` (`faction_display.py:221-235`).
6. Commit único do item.

## 5. Critérios de aceite

- [ ] Item 1: hook registrado; R2–R6 com testes; playtest curto sem violação `law.*` nova
- [ ] Item 2: Etapa 0 publicada (`docs/spec377/folego_divergencias.json`); uma implementação;
      paridade com o catálogo ou arena 45–85 % após [D2]; R24 sem diff
- [ ] Item 3: mapa publicado; R14 renomeado; R15/R16 com teste; só bug provado mudou
- [ ] Item 4: matriz publicada; [D4] aplicada; testes 293/294/298/314/315/351 verdes
- [ ] W1 registrada no hand-back de cada etapa; um commit por item (W4)
- [ ] Revisão independente `spec-reviewer` (Opus), que reroda pelo menos 1 caracterização (W7)
- [ ] `uv run pytest` verde (suíte completa, coordenador, 1× no pouso)
- [ ] Saves antigos continuam carregando (R5; nenhum campo novo no save)
- [ ] Nenhum `with_structured_output` novo (não se aplica)

## 6. Smoke test com LLM real

Só os itens 3 e 4 tocam o que o jogador vê ou o que o LLM narra. O item 1 é determinístico e o
item 2 é número de Fôlego, ambos cobertos offline. São ≤ 6 requests no total, na API local com
as chaves de `ROUTES` (DeepSeek primário), `RPG_CARD_DECK=on`, `RPG_LAW=on` e
`RPG_WORLD_ENGINE=on`:

1. Novo jogo e um encontro com combatente de facção **secreta** desconhecida (`filhos_chama_azul`).
   O HUD e a narração de abertura mostram o papel ou "Combatente desconhecido", nunca "Chama
   Azul". Jogar 1 rodada de Cartas com uma Carta de área; se o item 3 mudou algo, um inimigo
   rendido não recebe dano.
2. Conversar 2 turnos com um NPC na região de `mao_sombria`. O texto do NPC não nomeia a Mão
   Sombria, e o bloco `faction_block` registra `hidden_secret ≥ 1` na telemetria.
3. Pedir ao NPC "quem manda aqui?". Se [D4] = (b)/(c), conferir que a regra escolhida vale no
   texto e no HUD.
4. Registrar no hand-back: provider/modelo, requests, trechos que provam 1–3.

## 7. Riscos & compatibilidade

- **Saves antigos:** item 1 poda entradas decaídas no 1º dia simulado (R5; sem campo novo nem
  bump). Itens 2–4 não tocam schema. A Carta continua sendo salva só pelo id; o custo é derivado
  na leitura.
- **Arena/balanço:** se [D2] = regra do jogo, a vitória não muda (R8) e só mudam o relatório por
  Fôlego e a faixa do lint. Se [D2] = lint, é obrigatório medir a arena 45–85 % antes e depois. O
  R15 pode mudar a taxa de Posturas de área: medir antes de pousar. O avaliador congelado não é
  editado (R24).
- **Strings derivadas de ids:**
  - o nome do hook `"law"` entra no `log_fallback(... hook=name)` (`world_engine.py:140`);
  - o rótulo de combatente vem de `_theme_stems` sobre o nome da facção e é preciso evitar
    mudar `GENERIC_LABEL`/`UNKNOWN_FACTION`/`MASK_TEXT`, que os oráculos e o e2e procuram como
    texto;
  - os ids de facção nos aliases de `faction_gate._EXTRA_ALIASES`;
  - evento de telemetria novo exige registro em `observability/events.py`
    (`gen_event_catalog.py`). O item 1 não cria evento; se criar, registrar.
- **Sessões paralelas:** W1 antes de cada etapa. Os itens 2 e 3 esperam a `spec-368`. Nada em
  `agents/combat.py` (`spec-371`).
- **Monkeypatch:** aliases e fachadas preservam `cards.custo_folego` e `faction_gate.*`
  (`test_spec315_claim.py:166-173`, `test_spec351_checks.py:149`).
- **MockLLM/FallbackLLM:** nada muda. **Quota/latência:** zero no caminho do turno (um hook
  O(n) em `wanted` por dia simulado).

## 8. Decisões do dono

- **D1 — Poda da lei.** (a) Registrar o hook (**recomendado**). Isso corrige a notícia
  instantânea, o caçador sem novo aviso e o atraso vencido herdados de crime antigo (R2) e
  limpa o save. (b) Apagar `daily_tick` e manter a memória residual como está. A recomendação
  muda o jogo no staging (`RPG_LAW=on` em `scripts/staging/staging_flags.json:11`) só depois de
  suborno ou pena com heat zerado.
- **D2 — Qual regra de Fôlego vale** (só se a Etapa 0 achar divergência). (a) A regra do jogo
  (`cards.py`): todo kind de dano conta, e `dot`/`contra_ataque` livre custa 1
  (**recomendado**). A arena não muda (R8); só o lint e a faixa do orçamento passam a ver o custo
  real. (b) A regra do lint: dano só de `kind == "dano"`. Algumas Cartas ficam mais baratas no
  jogo e a arena precisa ser medida. Em qualquer caso, mudança de faixa vira spec de balanço
  separada.
- **D3 — "Vivo" no combate.**
  - (a) Se R15 se provar, o rendido deixa de ser alvo de efeito de Carta (**recomendado**;
    alinha com `conflict_turn._targetable`).
  - (b) Se R16 se confirmar, Estado Terminal continua fora do alvo de Carta (**recomendado**:
    manter).
  - Fora (a) e (b), só renomes.
- **D4 — Esconder facção.**
  - (a) Manter as duas políticas: o combatente de qualquer facção desconhecida ganha um rótulo
    de papel (SPEC-293), e o NPC/contexto escondem só a secreta (SPEC-314). Só nomes explícitos,
    docstring e teste de matriz, sem mover arquivo (**recomendado**). São decisões de spec
    distintas, há 28 importadores e há `monkeypatch`.
  - (b) Uma regra, "só secreta": o HUD passa a mostrar "Soldado da Legião de Ferro" desde o 1º
    turno.
  - (c) Uma regra, "qualquer desconhecida": o NPC deixa de citar facções públicas até a
    revelação, o que é uma mudança grande no diálogo.
  - (b) e (c) criam `faction_visibility.py` com fachadas.
- **D5 — Ordem.** Os itens 1 e 4 já (se a W1 der vazio); os itens 2 e 3 depois que a
  `spec-368` pousar (**recomendado**). Um commit por item.
