# SPEC — Itens vivos (passivas + ativas) + sistema de Luz/Visibilidade

> **Status:** `in-progress` (2026-07-19 — mecânica+dados+HUD `done` e testados (20 testes); falta só o smoke real da prosa, adiado p/ não colidir com o playtest longo no Jina)
> **Criada:** 2026-07-19 · **Atualizada:** 2026-07-19
> **Depende de:** Fase 4.2 (buffs mecânicos) · 4.3 (inventário/slots) · 6.4 (detection_check) · 6.5 (clima) — todas `done`
> **Desbloqueia:** conteúdo de itens com identidade mecânica; ambientação de masmorra

---

## 1. Contexto & Objetivo

Auditoria 2026-07-19 (3 perguntas do usuário) revelou 3 lacunas — todas com o
schema pronto mas o motor/dados vazios:

1. **Itens com habilidade ATIVA (stun/sleep) não existem.** `use_item_in_combat`
   só aplica `mechanics.heal` e buffs no PRÓPRIO usuário; não há item ofensivo
   (atordoar/adormecer um inimigo). Dados: só 2 poções têm `active_ability`.
2. **Passivas de item NÃO são lidas pelo motor.** Todo item tem
   `mechanics.passive_effects: []`, e `combat_mechanics.player_passives` funde só
   passivas de CLASSE + HABILIDADES aprendidas — nunca as do EQUIPAMENTO. Um
   acessório de percepção/resistência/luz não teria efeito algum.
3. **Não há sistema de LUZ.** Existe o período "Noite" no relógio, mas
   `detection_check` (percepção) só soma WIS + clima. Escuridão (noite/masmorra)
   não dificulta ver nada; não há fonte de luz (tocha/lanterna) que importe.

Objetivo: **fiar o que o schema já promete** — passivas de item viram efeito
real; itens ativos podem atingir o inimigo (stun/sleep); e um **sistema de luz
determinístico** onde escuridão penaliza percepção (e combate leve) a menos que
o herói carregue luz. Tudo Python (mecânica), IA só narra. Popular DADOS de
exemplo p/ não repetir o "schema vazio".

Princípios: "Mecânica é Python", "dado declara capacidade → motor FIA"
(ver [[fiacao-regras-orfas-classes]] — mesmo padrão de bug).

## 2. Requisitos

- **R1 — Passiva de item fiada.** `player_passives` inclui `mechanics.passive_effects`
  dos itens EQUIPADOS (slots weapon/armor/accessory — não o inventário inteiro),
  com o MESMO vocabulário das passivas de classe (`trigger: always/damage_type/
  resist/...`). Inimigo não ganha (não tem equipment de jogador). Um acessório
  `{trigger:"resist", name:"veneno"}` passa a resistir veneno; `{trigger:"always",
  stat:"ac", delta:1}` soma AC — via o pipeline existente.
- **R2 — Trigger `perception`.** Novo trigger de passiva lido por
  `detection_check`: soma dos `perception` de classe + habilidades + itens
  equipados entra na rolagem (item "óculos de batedor" +2 percepção).
- **R3 — Sistema de Luz determinístico.** Função pura
  `light_level(world, player) -> {"dark": bool, "lit": bool, "perception_mod": int,
  "label": str}`:
  - **Escuro** quando: período ∈ {Anoitecer, Noite} OU local com tag `dark`
    (interiores/masmorras), E o local NÃO é abrigado/urbano (cidade tem tochas).
  - **Fonte de luz** anula o escuro: item equipado/no inventário com passiva
    `{trigger:"light"}` OU tag `luz` (tocha, lanterna).
  - Escuro sem luz → `perception_mod` negativo (`DARK_PERCEPTION_PENALTY`,
    `[BALANCEAR]` = −3) somado em `detection_check`; com luz → 0.
- **R4 — Escuro no combate (leve).** Escuro sem luz aplica um pequeno
  `combat_attack_mod` negativo simétrico (herói E inimigos erram mais no escuro),
  somado no `resolve_enemy_turn`/ataque do herói como o clima já faz
  (`DARK_COMBAT_PENALTY`, `[BALANCEAR]` = −1). Fonte de luz do herói ilumina o
  lado dele (herói não sofre; inimigos sim → vantagem de carregar luz).
- **R5 — Item ATIVO ofensivo/utilitário.** `use_item_in_combat` aceita um alvo:
  `mechanics.effects` com `kind ∈ {debuff,dot,control}` aplica no INIMIGO
  (com save se `save_stat`), reusando `apply_condition`/`_split_typed_effects`.
  Buffs (`kind:"buff"`)/heal seguem no próprio usuário. Item consumível gasta 1
  qty (Fase 4.3).
- **R6 — DADOS de exemplo (fim do schema vazio).** Popular ≥5 itens reais:
  (a) uma fonte de luz (a "Lanterna dos Suspiros" ganha `{trigger:"light"}` +
  narração); (b) um acessório de percepção (`{trigger:"perception", delta:2}`);
  (c) uma resistência passiva (`{trigger:"resist", name:"medo"}`); (d) uma bomba
  de atordoamento (consumível, `effects:[{kind:"control",control:"stun",
  duration:1}]`, `save_stat:"con"`); (e) um pó do sono (`control:"sleep"` →
  mapeado p/ stun-like, ver §3).
- **R7 — Superfície narrativa + HUD.** O storyteller recebe um bloco curto de
  luz (`<AMBIENTE_DE_LUZ>`: claro/escuro + se o herói tem luz) e a ficha/HUD
  mostram um chip de luz e as passivas de item equipado.
- **R8 — Ampliar catálogo + variedade de habilidades (ancorado na lore).** Subir
  a quantidade de itens e, principalmente, a VARIEDADE mecânica agora que o motor
  fia passivas/ativas/luz. Meta: **+20 itens** cobrindo os novos vocabulários,
  cada um ancorado na lore de Valoria (região/fação/criatura/artefato do Codex —
  ex.: algo do Deserto de Zhur, da Forja de Vorr, dos Nascidos do Gelo, do
  Pântano). Distribuir os efeitos: fontes de luz (tocha comum, lanterna élfica,
  cristal de éter), passivas (percepção/resist/AC/dano por tipo/`carga_embrace`
  temático), ativas ofensivas/utilitárias (bomba de atordoamento, pó do sono,
  fumaça — fuga, óleo incendiário — `dot`), e itens de suporte (bênção — buff).
  Sem inventar entidade fora do Codex; itens únicos entram no claim engine (6.2)
  quando `unique`. Seguir `docs/AUTORIA.md` (lint `validate_content.py` quando
  aplicável). Balance dos números marcado `[BALANCEAR]`.

### Fora de escopo

- Visão no escuro racial (darkvision) — pode virar trait racial depois (o
  vocabulário `light`/`perception` já deixa a porta aberta).
- Stealth/furtividade do jogador (esconder-se) — só percepção/detecção de
  encontro por ora.
- Novos slots de equipamento (usa weapon/armor/accessory da 4.3).
- Re-curar TODOS os 44 itens legados p/ o vocabulário novo (só os de exemplo do
  R6 + os +20 do R8; o resto do legado segue com stats flat, migração passiva).
- Arte dos itens (Fase 8).
- `sleep` como condição totalmente nova — v1 trata `sleep` como um `stun` com
  flavor (perde o turno); condição de sono "acorda ao tomar dano" fica p/ depois.

## 3. Design técnico

**Arquivos alterados**
- `combat_mechanics.py` —
  - `item_passives(player, *, artifacts_db=None) -> List[Dict]`: passive_effects
    dos itens EQUIPADOS (lê `equipment` slots; fallback inventário legado só se
    não houver slots, como `compute_player_combat_stats`).
  - `player_passives` = `class_passives + learned_passives + item_passives` (R1).
  - `resolve_player_action`/`resolve_enemy_turn`: somar `DARK_COMBAT_PENALTY` no
    acerto quando `world` em escuro sem luz do lado do atacante (R4). (Passar o
    `light` já computado, como `env_dot`/clima já fluem ao combat_node.)
  - `HANDLED_KINDS["passive_trigger"]` ganha `perception`, `light` (o teste
    anti-órfão da spec fiacao passa a cobrir os triggers novos).
- `world_utils.py` — `light_level(world, player)` (R3) puro; usa `time_of_day`,
  tags do local (`get_location`), `_SHELTER_TAGS` (reuso 6.5) e a checagem de
  fonte de luz. Constantes `DARK_PERCEPTION_PENALTY`, `DARK_COMBAT_PENALTY`.
  `detection_check` soma `light_level().perception_mod` + passivas `perception`.
- `inventory.py` — `use_item_in_combat(player, item_ref, target=None)`: aplica
  `mechanics.effects` hostis no `target` (com save), buffs/heal no self (R5).
- `agents/combat.py` — computa `light` do turno; passa a penalidade aos
  resolvers; passa `target` ao `use_item_in_combat` (o alvo de combate atual).
- `agents/storyteller.py` (+ `services/context_builder.py`) — bloco
  `<AMBIENTE_DE_LUZ>` (R7).
- `data/artifacts.json` — itens de exemplo do R6.
- `data/world_map.json` — tag `dark` nos interiores/masmorras que fazem sentido.
- Frontend (`web/`) — chip de luz + passivas de item na ficha (R7).

**Vocabulário de passiva novo (lido determinístico):**
| trigger | efeito | onde lê |
|---|---|---|
| `perception` (delta) | +/- na rolagem de detecção | `detection_check` |
| `light` | marca o item como fonte de luz (anula escuro) | `light_level` |

**Assinaturas:**
```python
def item_passives(player: Dict, *, artifacts_db=None) -> List[Dict]: ...
def light_level(world: dict, player: dict) -> dict:
    # {"dark": bool, "lit": bool, "perception_mod": int, "combat_mod": int, "label": str}
def use_item_in_combat(player: Dict, item_ref: str, target: Optional[Dict] = None) -> Tuple[Dict, List[str]]: ...
```

## 4. Plano passo a passo

### Etapa 1 — Passiva de item fiada (R1/R2)
1. **Testes** (`tests/test_itens_vivos.py`): `test_item_passive_soma_ac`
   (acessório `{always,ac,+1}` sobe AC via player_passives); `test_item_resist`
   (item `{resist,"veneno"}` faz `is_condition_resisted` True);
   `test_item_perception_na_deteccao` (item `{perception,+2}` sobe o roll de
   `detection_check`); `test_inimigo_nao_ganha_passiva_de_item`.
2. **Implementação:** `item_passives` + fusão em `player_passives`;
   `detection_check` lê `perception`; `HANDLED_KINDS` atualizado.
3. **Verificação:** `uv run pytest` verde.

### Etapa 2 — Sistema de Luz (R3/R4)
1. **Testes:** `test_noite_sem_luz_penaliza_percepcao`;
   `test_luz_anula_escuro` (item `{light}` no inventário → perception_mod 0);
   `test_cidade_iluminada_a_noite` (tag abrigo/urbano → não escurece);
   `test_masmorra_dark_sem_luz`; `test_escuro_penaliza_acerto_simetrico`.
2. **Implementação:** `light_level` + integração em `detection_check` e nos
   resolvers de combate.
3. **Verificação:** verde.

### Etapa 3 — Item ativo ofensivo (R5)
1. **Testes:** `test_bomba_atordoa_inimigo` (usar bomba → alvo com condição
   stun, respeitando save); `test_item_buff_segue_no_self`; `test_consumivel_gasta_qty`.
2. **Implementação:** `use_item_in_combat(target=...)` + combat_node passa o alvo.
3. **Verificação:** verde.

### Etapa 4 — Dados de exemplo + narrativa + HUD (R6/R7)
1. **Testes:** `test_lanterna_e_fonte_de_luz` (item de dado real tem `light`);
   `test_bomba_de_exemplo_valida`; `test_bloco_ambiente_de_luz` (o context block
   reflete claro/escuro/com-luz).
2. **Implementação:** `data/artifacts.json` (R6) + `world_map.json` tags `dark`
   + bloco `<AMBIENTE_DE_LUZ>` + HUD (`npm run build`).
3. **Verificação:** suíte + build verdes.

### Etapa 5 — Ampliar catálogo ancorado na lore (R8)
1. **Testes:** `test_todo_item_com_effects_kind_valido` (todo `mechanics.effects[].kind`
   ∈ vocabulário do motor — anti-órfão de dado); `test_todo_passive_trigger_valido`
   (todo `passive_effects[].trigger` ∈ `HANDLED_KINDS`); `test_fontes_de_luz_min`
   (≥3 fontes de luz distintas); `test_variedade_de_ativos` (≥1 de cada:
   control/dot/buff em `active_ability`); `test_ids_unicos_e_regiao` (ids novos
   únicos; itens com âncora de lore têm `origin`/tag de região/fação válida).
2. **Implementação:** **+20 itens** em `data/artifacts.json`, ancorados no Codex
   (regiões/fações/criaturas de Valoria), distribuindo os efeitos (§R8). Rodar
   `uv run python scripts/validate_content.py` se tocar em ids do grafo.
3. **Verificação:** suíte + lint verdes.

## 5. Critérios de aceite

- [ ] Passiva de item equipado afeta AC/acerto/resist/percepção (Etapa 1)
- [ ] Noite/masmorra sem luz dificulta perceber; tocha/lanterna anula; cidade à noite fica iluminada
- [ ] Escuro sem luz penaliza o acerto (simétrico; luz do herói protege o lado dele)
- [ ] Bomba de atordoamento aplica stun no inimigo (com save); buff/cura seguem no self
- [ ] ≥5 itens de exemplo populados (luz, percepção, resist, bomba, pó do sono)
- [ ] **+20 itens** novos ancorados na lore, com variedade de efeitos (R8), lint verde
- [ ] Storyteller descreve claro/escuro; HUD mostra chip de luz + passivas de item
- [ ] Teste anti-órfão (`HANDLED_KINDS`) cobre `perception`/`light`
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM: N/A (mecânica pura; nenhum structured output novo)
- [ ] Saves antigos continuam carregando (campos novos são opcionais)

## 6. Smoke test com LLM real

1. Viajar até a Noite / entrar numa masmorra `dark` SEM tocha → narração diz que
   está escuro e o encontro pega o herói mais fácil (perception penalizada).
2. Equipar/carregar a Lanterna → narração muda (luz), penalidade some.
3. Usar a bomba de atordoamento num inimigo em combate real → log/narração
   mostram o inimigo atordoado (perde o turno).
4. Equipar o acessório de percepção → detecção melhora (menos emboscadas).

## 7. Riscos & compatibilidade

- **Saves antigos:** itens sem `passive_effects`/tags = comportamento atual
  (listas vazias); `light_level` com world sem período = "claro" default. Sem
  migração.
- **MockLLM/FallbackLLM:** tudo determinístico; MockLLM não afeta (mecânica é
  Python). O teste anti-órfão pega trigger novo sem handler.
- **Balance:** penalidades marcadas `[BALANCEAR]` (percepção −3, acerto −1);
  fáceis de ajustar. Entram na rodada de balanceamento futura.
- **Playtest/determinismo:** `light_level` é puro (sem RNG); não muda a
  reprodutibilidade do harness.

## 8. Registro de execução (2026-07-19)

Todas as 5 etapas implementadas, **+20 testes** (`tests/test_itens_vivos.py`),
suíte **950 → 970 verdes**. Autoria em Fable.

- **Etapa 1 (R1/R2):** `combat_mechanics.item_passives` (slots equipados, só
  passivas TIPADAS — filtra strings de flavor legado tipo `corda`); fundido em
  `player_passives` (classe + habilidades + itens). `detection_check` lê o
  trigger `perception`. `HANDLED_KINDS["passive_trigger"]` += `perception`,
  `light` (o teste anti-órfão da spec fiacao cobre os novos).
- **Etapa 2 (R3/R4):** `world_utils.light_level(world, player)` puro — escuro =
  período {Anoitecer,Noite} OU tag `dark` do local, E não abrigado/urbano; fonte
  de luz (passiva `light` ou tag `luz`, equipada OU no inventário) anula.
  `DARK_PERCEPTION_PENALTY=-3`, `DARK_COMBAT_PENALTY=-1` (`[BALANCEAR]`).
  Integrado em `detection_check` (via storyteller) e no combate (`env_atk` do
  combat_node, simétrico como o clima).
- **Etapa 3 (R5):** `use_item_in_combat(player, item_ref, target=None)` aplica
  `mechanics.effects` hostis (control/dot/debuff) no inimigo com save
  (`save_stat`/`save_dc`); buff/heal seguem no self. combat_node passa o alvo.
- **Etapa 4/5 (R6/R7/R8):** **+22 itens** em `data/artifacts.json` ancorados na
  lore (Forja de Vorr, Nascidos do Gelo, Druidas Cinzentos, Zhur, Xylos,
  Ophídia, Brekmar, Chama Azul, Arauto/Abismo): 4 fontes de luz, 9 passivas
  (percepção/resist/AC/ataque/damage_type/carga_embrace), 6 ativos ofensivos
  (stun/sono/fogo/ácido/medo/fumaça), 3 suportes (buff/heal). A "Lanterna dos
  Suspiros" virou fonte de luz de verdade. Bloco `<AMBIENTE_DE_LUZ>` no prompt
  do storyteller; `/game/state.world.light` + chip no HUD (PlayScreen);
  `npm run build` verde. Teste anti-órfão de DADO (todo kind/trigger de item ∈
  motor).
- **Achado colateral corrigido:** `corda` (legado) tinha passiva como STRING —
  `item_passives`/`_has_light_source` agora filtram não-dicts (robustez).
- **Pendente p/ `done`:** smoke real §6 (prosa de escuridão + item ofensivo em
  combate real) — adiado para não colidir com o playtest longo no Jina.
