# SPEC — Fase 2.5b: Valoria nos dados mecânicos (mapa, fações, raças, bestiário) + combate com comportamento

> **Status:** `done` (2026-07-14 — smoke real §6 executado, 3/3: ① `/game/new`
> com raça Cinzéu → ficha com traits `Corpo Silencioso`/`Contemplação`;
> ② viagem Skallgard → Fortaleza de Vorr com narrativa usando o lore da região;
> ③ tático `Lobo das Geleiras` a 2/18 HP FUGIU no turno dele — combate encerrou,
> `threat_alerts` registrou `enemy_lobo_invernal` na região, narração real ok)
> **Criada:** 2026-07-01 · **Atualizada:** 2026-07-14
> **Depende de:** [SPEC-001-fase-2.5-codex-world-state.md](SPEC-001-fase-2.5-codex-world-state.md)
> **Desbloqueia:** [SPEC-003-fase-2.6-structured-events.md](SPEC-003-fase-2.6-structured-events.md) (jogável de verdade), 2.7, 2.8

---

## 1. Contexto & Objetivo

A Fase 2.5 trocou a fonte de lore para o universo reescrito de `lore_nova/` (Valoria):
Codex + grafo de entidades. Mas os **dados mecânicos** continuam do universo antigo —
`world_map.json` (9 locais), `factions.json` (selo_palido, culto_clareira...),
`origins.json`, `bestiary.json`. Resultado: o RAG narra Valoria enquanto viagem,
simulador de fações, encontros e origens rodam um mundo que não existe mais.

Esta spec fecha a lacuna: reescreve os dados mecânicos para Valoria, usando os
**mesmos IDs canônicos** de `data/graph/entities.json` (fonte única de identidade
criada na 2.5). Princípio: *mecânica é Python/dados, não LLM; identidade vem do grafo*.

**Adição (2026-07-02, pedido do usuário):** combates devem *sentir* diferente por
criatura — 3 guardas da Legião têm técnicas, táticas e fogem quando a maré vira;
um urso-titã não conhece o conceito de fuga e luta até a morte. Hoje
`resolve_enemy_turn` sempre usa `attacks[0]` e nenhum inimigo jamais foge.
Isso vira os requisitos R8–R10 (perfis de comportamento + moral + fuga com
consequência de mundo), resolvidos 100% em Python determinístico.

## 2. Requisitos

- **R1** — `data/world_map.json` reescrito: as **12 macro-regiões** de Valoria
  (`nova_arcadia`, `pantano_melancolia`, `deserto_zhur`, `floresta_sussurros`,
  `selva_xylos`, `skallgard`, `aethelgard`, `ophidia`, `costa_negra`,
  `montanhas_afiadas`, `pradaria_ruinas`, `brekmar` — exatamente as 12 locations
  de `entities.json`; *não existe* `ermo_branco` no grafo) + sublocais-chave jogáveis
  (ex.: anéis de Nova Arcádia), com `connections`, `danger`, `region`, `lore_seed`
  derivados do Codex. Todo id de local existe na união de entidades (teste). Grafo conexo (teste).
- **R2** — `data/factions.json` reescrito: subset de ~12–14 das 28 fações de Valoria
  (as com agência regional — ex.: `legiao_ferro`, `mao_sombria`, `filhos_chama_azul`
  + 1–2 por região relevante) com a mecânica da Fase 2 (goal/pace/progress/
  disposition/reputation/ascension). IDs = ids do grafo (teste).
- **R3** — `data/origins.json` reescrito com **6 raças jogáveis** de `lore_nova/races.txt`
  (`race_humanos`, `race_elfos`, `race_anoes_fuligem`, `race_vrel`, `race_cinzeus`,
  `race_osshari`; Vampiros/Lycans/Hospedeiros/Povo-recife ficam NPC-only);
  `character_creator` e wizard continuam funcionando.
- **R4** — `data/bestiary.json` realinhado: criaturas de `lore_nova/creatures.txt`
  (ids `mon_<slug>` do grafo; combatentes de fação mantêm `enemy_<slug>` registrados
  em `entities_extra.json`) com stats determinísticos + campos novos `regions` e
  `behavior`; encontros da Fase 2 sorteiam do bestiário novo por região (R11).
- **R5** — `data/world_lore.txt` removido (fonte morta desde a 2.5); `rag.py` sem
  referência a ele.
- **R6** — Saves antigos ainda **carregam** sem exceção (backfill via
  `world_utils.ensure_world`), mas mundo antigo é declarado incompatível —
  documentar em ESTADO_ATUAL que saves pré-2.5b devem ser arquivados.
- **R7** — `data/class_themes.json` e `data/artifacts.json` revisados no mínimo para
  não contradizer Valoria (renomeações pontuais; profundidade fica para fase futura).
- **R8** — **Perfis de comportamento de combate** (novo): todo inimigo tem
  `behavior.profile` ∈ {`tatico`, `feroz`, `covarde`, `implacavel`} que controla,
  em Python determinístico (`combat_mechanics.py`): escolha de ataque, moral
  (fuga por HP baixo / aliados caídos via `flee_below` + `pack_morale`) e frenesi
  (`feroz` ganha bônus de dano com HP < 50%). `feroz`/`implacavel` **nunca** fogem.
  Inimigo fugido (`status="fugiu"`) sai do combate, não conta para vitória nem loot.
- **R9** — **Traits raciais mecânicos** (novo): cada uma das 6 raças jogáveis tem
  1–2 traits derivados da lore com efeitos que o engine já entende (bônus de
  atributo/recursos/defesa, resistência a condições, bônus de save, itens/ouro
  iniciais), aplicados deterministicamente na criação e respeitados por
  `combat_mechanics` (saves e condições).
- **R10** — **Fuga vira alerta de mundo** (novo): quando ≥1 inimigo foge, registra-se
  `world["threat_alerts"]`; um alerta ativo na região dispara encontro de reforços
  (1x, com flavor próprio, validade ~6 turnos), depois é consumido.
- **R11** — Encontros determinísticos sorteiam criatura CONCRETA do bestiário por
  região/perigo/fação dominante (`pick_encounter_enemy`), e o `hint` passa a ser o
  nome exato — spawn cai no cache do bestiário (menos 1 chamada LLM).

### Fora de escopo

- Eventos estruturados propostos pelo LLM (2.6), propagação (2.7), ranking de contexto (2.8).
- Reescrever classes jogáveis/habilidades (mantêm-se; só gating temático revisado).
- Sub-mapa completo de cada região (começar com 12 regiões + sublocais de Nova Arcádia
  e 1–2 por região; demais sublocais entram sob demanda).
- Fuga do PLAYER (mecânica de escapar de combate) — fase futura.
- IA de posicionamento/alvos múltiplos (não há grid; alvo é sempre o player).

## 3. Design técnico

### 3.1 Identidade — `data/graph/entities_extra.json` (novo)

`scripts/migrate_lore_nova.py` **sobrescreve** `entities.json`; curadoria manual
(sublocais do mapa, combatentes de fação do bestiário) vive em
`data/graph/entities_extra.json` — mesmo schema de entidade
(`id/type/name/aliases/tags/visibility/components`). O script não o toca.

`services/graph_resolver.load_entities()` retorna a **união** dos dois arquivos;
em conflito de id, o canônico (`entities.json`) vence e o extra é ignorado.
Teste de integridade cruzada: todo id usado em `world_map.json`, `factions.json`,
`bestiary.json` e `origins.json` (races) existe na união.

### 3.2 Mapa (R1)

Schema de nó inalterado (`gamedata.py` não muda):
`{id, name, region, coords{x,y}, danger(1-4), tags[], connections[], lore_seed, start?}`.
1 nó `start: true` por região (exigência de `REGION_START_ID`);
`start_location` global = nó inicial de Nova Arcádia. Sublocais novos usam prefixo
da região (ex.: `na_anel_lama`) e entram em `entities_extra.json`.

### 3.3 Fações (R2)

Schema da Fase 2 inalterado. Conteúdo (goal/pace/disposition/ascension) escrito à mão
a partir de `data/codex/factions/`; `ascension.target` aponta para ids do mapa novo;
tipos de ascensão existentes (`dominar_local`, `expandir_regiao`, `invocar_entidade`,
`elevar_perigo`, `eliminar_faccao`) são suficientes — sem tipo novo.

### 3.4 Raças + traits (R3, R9)

```json
{"id": "race_anoes_fuligem", "name": "Anão da Fuligem", "desc": "...",
 "traits": [{"id": "pulmoes_de_fornalha", "name": "Pulmões de Fornalha",
   "desc": "Gerações na fumaça: veneno e miasma mordem menos.",
   "effects": {"attr_bonus": {"con": 2}, "hp_bonus": 5,
               "condition_resist": ["veneno", "doenca"], "save_bonus": {"con": 2},
               "start_items": [], "gold_bonus": 0}}]}
```

Chaves de `effects` (todas opcionais): `attr_bonus{attr:int}`, `hp_bonus`,
`mana_bonus`, `stamina_bonus`, `defense_bonus`, `condition_resist[str]`
(match por substring no nome da condição), `save_bonus{attr:int}`,
`start_items[str]`, `gold_bonus`.

Aplicação: `character_creator.py` aplica `effects` **em Python, pós-LLM**
(`apply_racial_traits(sheet, race_id)`); ficha ganha `racial_traits: List[str]`
(nomes p/ narração/HUD) — campo novo em `PlayerStats` (`state.py`), backfill `[]`.
`combat_mechanics`: saving throws somam `save_bonus` racial;
`apply_condition` no player ignora condições em `condition_resist`.

### 3.5 Bestiário + behavior (R4, R8)

Entrada ganha:

```json
"regions": ["skallgard"],
"behavior": {"profile": "tatico", "flee_below": 0.35, "pack_morale": true}
```

- `profile`: `tatico` (escolhe ataque por situação, foge por moral),
  `feroz` (maior dano, frenesi +2 dano com HP<50%, nunca foge),
  `covarde` (ataque mais seguro, foge cedo — HP<60% ou 1º aliado morto),
  `implacavel` (rotaciona ataques, nunca foge — bosses/aberrações).
- Defaults por tag do grafo quando não curado: `humanoide_hostil`→`tatico`,
  `bestial`→`feroz`, `aberracao`/`assombracao`→`implacavel`; minions fracos→`covarde`.
- `agents/bestiary.EnemySchema` ganha `behavior`/`regions` opcionais (LLM também
  preenche p/ criaturas novas; fallback `feroz`). Spawn copia `behavior` p/ instância.
- `state.EnemyStats` ganha `behavior: Optional[Dict]`.

### 3.6 Engine de comportamento (R8) — `combat_mechanics.py`

Funções novas, puras/determinísticas, chamadas por `resolve_enemy_turn` e pelo loop
do `combat_node`:

```python
def choose_enemy_attack(enemy: Dict, player_ac: int, rnd: int) -> Dict: ...
def check_morale(enemy: Dict, allies: List[Dict]) -> Optional[str]:  # log de fuga ou None
```

- `check_morale` roda no início do turno do inimigo; se foge: `status="fugiu"`,
  não ataca. Fugido não conta como `ativo` (vitória = nenhum `ativo`), não entra
  no loot e não recebe XP.
- `agents/combat.py`: coleta fugitivos do round e devolve
  `fled_enemies` para o registro de alerta (R10); narração recebe o log de fuga.

### 3.7 Fuga → alerta (R10) — `world_utils.py`

```python
world["threat_alerts"] = [{"loc_id": str, "hint": str, "faction_id": str|None, "turn": int}]
def register_flee_alert(world, fled, faction_id, turn) -> dict
```

`check_encounter`: se há alerta com `turn_atual - turn <= 6` no local/região atual,
dispara encontro (respeitando cooldown) com `reason="reinforcements"`, flavor de
reforços, e **consome** o alerta. Alertas expirados são descartados. Backfill `[]`
em `ensure_world`.

### 3.8 Encontro por região (R11) — `world_utils.py`

```python
def pick_encounter_enemy(loc: dict, danger: int, reason: str, factions, turn: int) -> dict|None
```

Determinístico (seed derivada do turno): `reason="controlled"`/`"reinforcements"`
com fação → combatente da fação no bestiário; senão criatura com `regions`
contendo a região e porte compatível com `danger` (minion ≤2, elite 3, boss 4).
`check_encounter` devolve `hint` = nome exato da entrada → `generate_new_enemy`
acerta o cache.

## 4. Plano passo a passo

TDD: testes de cada etapa escritos antes do código. Suíte nova em
`tests/test_fase25b.py`; testes existentes repinados na etapa que os quebra.

1. **Etapa 1 — identidade:** `entities_extra.json` + merge em `load_entities()` +
   testes de merge e integridade cruzada (falham até etapas 2–5 entregarem os dados).
2. **Etapa 2 — mapa:** `world_map.json` Valoria (12 regiões + sublocais, ~25-30 nós);
   atualizar `tests/test_fase0.py`; teste de grafo conexo.
3. **Etapa 3 — fações:** `factions.json` (~12-14); atualizar `tests/test_fase2.py`,
   `tests/test_world_sim.py`.
4. **Etapa 4 — raças/traits:** `origins.json` + `apply_racial_traits` no creator +
   hooks de save/condição + `racial_traits` no estado; testes de efeitos.
5. **Etapa 5 — bestiário:** curadoria + `behavior`/`regions` + `EnemySchema`;
   testes de cobertura regional e validade de behavior.
6. **Etapa 6 — engine:** `choose_enemy_attack`/`check_morale`/frenesi + fluxo
   `fugiu` no `combat_node`; testes de moral/fuga/vitória/loot.
7. **Etapa 7 — alertas:** `register_flee_alert` + `check_encounter` reforços; testes.
8. **Etapa 8 — sorteio regional:** `pick_encounter_enemy` + hint exato; testes.
9. **Etapa 9 — limpeza:** remover `world_lore.txt`, comentários de `rag.py`,
   revisão leve de `class_themes.json`/`artifacts.json`.
10. **Etapa 10 — fechamento:** pytest verde, ESTADO_ATUAL + ROADMAP, smoke real.

## 5. Critérios de aceite

- [x] Todo id de `world_map.json`, `factions.json`, `bestiary.json`, `origins.json`
  existe na união `entities.json` ∪ `entities_extra.json` (`tests/test_fase25b.py`)
- [x] Novo jogo nasce em Valoria (start em Nova Arcádia nova) e viaja pelo grafo novo (conexo)
- [x] Simulador de fações roda com fações de Valoria (goal/ascension coerentes com Codex)
- [x] 6 raças jogáveis com traits mecânicos aplicados na ficha e respeitados em combate
- [x] Perfis de comportamento: tático foge por moral; feroz/implacável lutam até a morte;
  fugido não conta como vitória/loot; fuga gera alerta que dispara reforços 1x
- [x] Encontro sorteia criatura concreta do bestiário por região/fação (hint exato)
- [x] `uv run pytest` verde (146 testes offline, 2026-07-02)
- [x] Guard de FallbackLLM em todo `with_structured_output` novo (não há novos — EnemySchema
  já é blindado em `generate_new_enemy`)
- [x] Saves antigos continuam carregando (backfill `threat_alerts`/`racial_traits` via
  `ensure_world`/`dict.get`; mundo antigo declarado incompatível — arquivar saves pré-2.5b)
- [ ] Smoke test com Gemini real (§6) — pendente (quota do usuário)

## 6. Smoke test com LLM real

1. `/game/new` + criação de personagem com raça nova (`race_cinzeus`) — ficha válida
   com traits aplicados.
2. 1 turno de viagem entre regiões novas — narrativa usa lore do Codex da região.
3. 1 encontro de combate — inimigo vem do bestiário novo, resolve em `combat_mechanics`,
   e um inimigo `tatico` com HP baixo foge (verificar narração + alerta).

## 7. Riscos & compatibilidade

- **Saves antigos:** locais/fações antigos não existem mais no mapa — carregar não pode
  crashar (defaults/backfill em `ensure_world`; id inexistente → start novo), mas a
  sessão fica narrativamente órfã. Documentar "arquivar saves pré-2.5b".
- **MockLLM:** dados novos são estáticos — suíte continua offline; behavior default
  garante que inimigo gerado pelo mock tenha perfil.
- **Volume:** 12 regiões + fações + bestiário + traits é conteúdo autoral extenso —
  execução em etapas com commit por etapa.
- **Quota:** sem impacto (dados estáticos); só o smoke consome requests.
- **`migrate_lore_nova.py` re-rodado** não pode apagar curadoria → sublocais/combatentes
  vivem em `entities_extra.json`, que o script não toca.
