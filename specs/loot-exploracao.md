# SPEC — Explorar recompensa: achados, baús e itens pelo mundo

> **Status:** `approved`
> **Criada:** 2026-07-20 · **Atualizada:** 2026-07-20
> **Depende de:** Fase 0 (viagem/fog of war, `world_utils`) · Fase 4 (economia/inventário) ·
> Fase 6 (itens únicos + claim engine) — todas `done`
> **Desbloqueia:** sensação de mundo rico (achado do playtest longo 2026-07-14)

---

## 1. Contexto & Objetivo

O playtest longo (`docs/playtest-longrun-2026-07-14.md`) registrou: **explorador
visitou 23 locais → 0 quest, ouro 0, level 3.** Explorar rende só prosa; nenhum
loot ou descoberta mecânica. O codex/bestiário progressivo existe mas não vira
recompensa SENTIDA. O jogador atravessa 23 lugares e não acha nada.

Decisão do usuário (2026-07-20): quests puxarem pra fora da cidade NÃO vale mexer
agora (Nova Arcádia já é rica). Mas **explorar deveria dar loot** — achar baús e
itens por aí. Ajuste (2026-07-20): a 1ª versão desta spec ficou avara demais.
**Explorar tem que às vezes VALER A PENA de verdade** — não é chuva de item
lendário, mas a exploração deve poder render coisas legais (um item bom, um
equipamento notável, às vezes um raro escondido num lugar perigoso), pra
INCENTIVAR o jogador a andar pelo mundo. O objetivo: descoberta ambiental
determinística, ancorada na lore, com **escada de raridade** — a maioria dos
achados é modesta, mas a cauda tem coisa que anima, e um punhado de locais
perigosos/escondidos guarda algo realmente bom.

Princípio: **"Mecânica é Python"** — a descoberta é sorteio determinístico
(mesmo modelo de `check_encounter`: gatilho por local/perigo/fog of war), não
invenção do LLM. O narrador só descreve o que a mecânica concedeu; o item entra
no inventário por código (nunca confiar no LLM pra criar/valorar item — a lição
do sinal do ouro em `loot.py`).

## 2. Requisitos

- **R1 — Descoberta na primeira visita.** Ao entrar num local NOVO (não em
  `world.visited`), há chance determinística de um achado ambiental. Escala com o
  perigo/riqueza do local: zona segura de cidade rende trivial (moedas),
  ruína/masmorra rende mais e melhor. Cooldown para não pingar em toda viagem.
- **R2 — Escada de raridade (a exploração às vezes VALE).** O achado vem de uma
  tabela determinística por tipo de local (`data/exploration_loot.json` novo)
  com **pesos por raridade** (`comum` / `incomum` / `raro`):
  - `comum` (maioria): consumível, material, punhado de ouro — o "sal" que faz o
    mundo parecer habitado;
  - `incomum` (cauda média): equipamento decente, poção boa, item de flavor com
    efeito real — o achado que ANIMA;
  - `raro` (cauda curta, mais provável em local perigoso/escondido): equipamento
    notável ou item bom de verdade. **Não é lendário spam** — a chance é baixa e
    escala com o perigo, então o jogador é recompensado por ir a lugares difíceis.
  Sem teto rígido de valor, mas a raridade é gated por perigo do local + nível
  (um item raro num ermo seguro nível 1 é improvável, não impossível), pra não
  inflar a economia com sorte trivial.
- **R2b — Único escondido é possível, mas raríssimo e curado.** Um punhado de
  locais perigosos/escondidos pode guardar um item ÚNICO via a claim engine da
  Fase 6 (condição deliberada = chegar lá e vasculhar), reforçando "vale a pena
  explorar o perigo". NÃO é sorteio da tabela aleatória de R2 — é curado por
  local (R3), one-shot, e respeita o claim (o único não duplica). A exploração
  passiva comum (R1/R2) nunca cospe lendário por acaso.
- **R3 — Baús explícitos em locais marcados.** Locais do mapa podem declarar um
  `treasure` no `data/world_map.json` — de um baú comum a um cofre com item raro
  ou o único de R2b. Entrar/vasculhar concede o conteúdo UMA vez (marca consumido,
  `world.looted_locations`). Curado por local; é onde mora a recompensa BOA
  (o design escolhe o quê e onde), distinto do achado aleatório de R1/R2.
- **R4 — Idempotência (anti-farm).** Um local já saqueado não rende de novo
  (R3 marca consumido; R1 só dispara na PRIMEIRA visita via fog of war). O perfil
  `loot_abuser` não consegue duplicar achado revisitando.
- **R5 — Integração com inventário/economia.** O item concedido entra pelo
  caminho canônico de inventário (`{id, qty}` / slots da Fase 4); ouro soma
  determinístico. Aparece no HUD. Nada de item fantasma só na prosa.
- **R6 — Narração descreve, não decide.** O storyteller recebe uma nota do tipo
  "o jogador ENCONTROU: {item}" (como `travel_note`) e descreve o achado; o
  estado já foi mutado por código antes da narração.

### Fora de escopo

- **Quests apontando pra fora da cidade** — decisão do usuário: não mexer agora.
- **Loot de combate** (Fase 6) — inalterado. (A claim engine é REUSADA em R2b
  para uns poucos únicos escondidos, sem alterar o mecanismo de claim.)
- **Reescrever a economia global** — adiciona uma fonte de loot com escada de
  raridade; não mexe em preços/escassez existentes. Se o dado do harness mostrar
  inflação, ajustar pesos/chance (constantes determinísticas).
- **Geração de item via LLM** — a tabela é curada/determinística.
- **Recompensa de quest / XP de exploração** — fora; só loot material/ouro/equip.

## 3. Design técnico

> **Nota de implementação (2026-07-20): desvio do plano original — REUSO da
> engine de loot da Fase 6 em vez de um `data/exploration_loot.json` novo.** A
> escada de raridade por perigo, o pool regional e o claim de único JÁ existem em
> `services/economy.roll_loot(region_id, danger, rng, …)` (bandas `1-2`/`3-4`,
> suprime únicos reclamados, pool de `ARTIFACTS_DB`). Criar uma tabela paralela
> seria duplicação. Os requisitos (R1–R6) são idênticos; só o mecanismo mudou.

**Arquivos novos**
- `services/exploration.py` — puro/determinístico:
  - `discovery_chance(danger) -> float` — chance modesta que escala com perigo
    (`min(0.5, 0.12 + 0.08*danger)`).
  - `roll_discovery(world, loc, player_level, rng) -> Optional[dict]` — na 1ª
    visita (fog of war checado pelo caller): chama `economy.roll_loot`; se o item
    for ÚNICO, **descarta** (passiva nunca dá único, R2b); devolve
    `{item_id, qty, gold, rarity}` ou `None`. A raridade vem das bandas do
    `roll_loot` (gate por perigo — R2).
  - `resolve_treasure(world, loc) -> Optional[dict]` — baú curado (`treasure` no
    world_map): one-shot via `world.looted_locations`; pode conter único.
  - `discover_on_arrival(player, world, loc, level, rng) -> (nota, eventos)` —
    entrypoint: baú curado tem prioridade; muta `player.inventory`/`gold` +
    `world.looted_locations`; devolve a nota pro narrador (R6) + eventos de claim.

**Arquivos alterados**
- `agents/storyteller.py` — no ramo de viagem: `first_visit` computado ANTES do
  `apply_travel` (que carimba `visited`); após mover, chama
  `exploration.discover_on_arrival` (muta player/world in-place — viagem sem
  descanso não substitui o player no updates parcial). A nota entra no
  `faction_note` (já vai pro prompt via `eventos_turno`); os eventos de claim
  entram no `pending`/`pending_world_events` (inclusive no early-return de
  encontro).
- `data/world_map.json` — campo opcional `treasure: {gold, items:[id...]}` em
  nós de ruína/espólio selecionados (curado; `pm_profundezas`,
  `ae_ruinas_submersas`). Itens são ids reais não-únicos de `ARTIFACTS_DB`.
- `state.py` — documenta `world.looted_locations: List[str]` (baú curado
  consumido) — persistido. `world.visited` já existe (fog of war).
- `tests/test_loot_exploracao.py` (novo).

**Assinaturas:**
```python
def roll_discovery(world: dict, loc: dict, player_level: int,
                   rng: random.Random) -> Optional[dict]: ...
def resolve_treasure(world: dict, loc: dict) -> Optional[dict]: ...  # baú curado, R3
```

## 4. Plano passo a passo

### Etapa 1 — Achado determinístico (testes primeiro)

1. **Testes** (`tests/test_loot_exploracao.py`):
   - `test_primeira_visita_pode_dar_loot`: local novo tipo ruína, seed fixa →
     `roll_discovery` devolve item do pool; item entra no inventário.
   - `test_revisita_nao_da_loot`: local já em `visited` → `roll_discovery` = None.
   - `test_raridade_escala_com_perigo`: mesmo tag, `danger` alto → probabilidade
     de `raro` maior que `danger` baixo (a cauda existe e é gated por perigo).
   - `test_ermo_seguro_nivel1_raro_improvavel`: peso `raro` baixíssimo em zona
     segura de nível 1 (improvável, não impossível — não infla por sorte trivial).
   - `test_bau_curado_uma_vez`: local com `treasure` → concede 1×; 2ª vez →
     nada (`looted_locations`).
   - `test_unico_escondido_respeita_claim`: baú R2b com item único → concede via
     claim engine 1×; não duplica (claim respeitado).
   - `test_sem_item_fantasma`: o item concedido está no inventário do estado (não
     só na nota do narrador).
2. **Implementação:** `services/exploration.py` + `data/exploration_loot.json` +
   fiação no storyteller (R1/R3/R5).
3. **Verificação:** `uv run pytest` verde.

### Etapa 2 — Narração + baús curados no mapa

1. **Testes:** `test_discovery_note_no_prompt` (nota de achado chega ao prompt do
   storyteller); `test_world_map_treasure_valido` (nós com `treasure` referenciam
   itens existentes).
2. **Implementação:** curar poucos `treasure` em `data/world_map.json`;
   `discovery_note` no prompt (R6).
3. **Verificação:** `uv run pytest` verde + harness `--profile explorador` mock
   mostra ouro/itens subindo (era 0).

## 5. Critérios de aceite

- [ ] Primeira visita a local novo pode render achado (comum na maioria; teste)
- [ ] Escada de raridade funciona: `raro` escala com perigo, improvável (não
      impossível) em zona segura nível 1 (testes)
- [ ] Único escondido (R2b) concede via claim engine 1×, não duplica (teste)
- [ ] Revisita não farma; baú curado concede 1× (testes de idempotência)
- [ ] Item/ouro entram pelo caminho canônico de inventário, aparecem no HUD
- [ ] Narrador descreve o achado que a mecânica concedeu (sem item fantasma)
- [ ] Harness `explorador`: ouro/itens finais > 0 (era 0 no baseline); nenhum
      achado lendário por sorte trivial (só via R2b curado)
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM: N/A (descoberta é determinística, sem structured
      output novo — narrador só recebe nota de texto)
- [ ] Saves antigos continuam carregando (`looted_locations` default `[]`)

## 6. Smoke test com LLM real

1. API real: viajar por 3–4 locais novos → em algum, o narrador descreve um
   achado E o inventário/ouro reflete no `/game/state`.
2. Revisitar um local já saqueado → sem novo loot.
3. Entrar num local com `treasure` curado → conteúdo concedido 1×; 2ª visita nada.

## 7. Riscos & compatibilidade

- **Saves antigos:** `world.looted_locations` default `[]`; `visited` já existe.
  Sem migração; personagem antigo só passa a poder achar loot em locais NOVOS
  dali pra frente.
- **MockLLM:** descoberta é determinística e independe do LLM → testável em mock;
  o narrador mock ignora a nota mas o estado é mutado por código (o que importa).
- **Economia / equilíbrio da escada:** o risco novo é a cauda `raro` inflar. Duas
  travas: (a) `raro` é gated por perigo do local + nível (sorte trivial em zona
  segura quase nunca dá raro); (b) o achado só ocorre na PRIMEIRA visita
  (fog of war) — o total de raros é limitado pelo nº de locais novos, não é fonte
  infinita. Se o harness mostrar inflação, baixar `pesos.raro`/`chance`
  (constantes determinísticas). O BOM de verdade mora nos baús curados (R3/R2b),
  onde o design controla o quê e o quanto.
- **Anti-farm:** fog of war (R1) + `looted_locations` (R3) garantem que revisitar
  não rende; o único de R2b respeita o claim (não duplica). O perfil
  `loot_abuser` é o teste de estresse.
