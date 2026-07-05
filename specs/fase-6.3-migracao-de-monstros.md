# SPEC — Fase 6.3: Migração de monstros — população reage à caça e ao poder

> **Status:** `draft`
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** Fase 2.5b (pick_encounter_enemy/behavior) · 3.2 (bestiary_knowledge) · 4.4 (loot tables) · 4.6 (fill_encounter)
> **Desbloqueia:** mundo que responde ao estilo de jogo (farm tem consequência)

---

## 1. Contexto & Objetivo

Hoje a composição de encontros por região é ESTÁTICA: `pick_encounter_enemy`
sorteia sempre do mesmo pool, com o mesmo peso, pra sempre. Matar 15 ratos do
Anel de Lama não muda nada — o 16º aparece igual. A 2.5b adicionou reforço
pontual (`threat_alerts`), mas população não reage.

Esta spec faz a composição REAGIR ao histórico — 100% view derivada de dados que
JÁ existem (`bestiary_knowledge` conta kills por criatura desde a 3.2;
`world_projection` sabe controle; `threat_alerts` sabem fugas): criatura muito
caçada fica RARA na região (pressão de caça) e abre espaço pra vizinhas
(migração); fação hostil no controle puxa criaturas da fação. Zero estado novo,
zero LLM, zero simulação oculta — pesos determinísticos auditáveis.

## 2. Requisitos

- **R1 (pressão de caça)** — `services/ecology.py::hunt_pressure(enemy_id,
  bestiary_knowledge, turn) -> float`: kills RECENTES da criatura (campo
  `defeated` + `last_seen_turn` da 3.2) rebaixam o peso dela no sorteio:
  0 kills → 1.0; 3+ kills nos últimos 20 turnos → 0.3; 6+ → 0.1 (quase extinta
  localmente). Janela desliza: parar de caçar → população volta (decay por
  distância de `last_seen_turn`, sem timer novo).
- **R2 (sorteio ponderado)** — `pick_encounter_enemy` (world_utils) passa a
  sortear com pesos: base 1.0 × `hunt_pressure` × `faction_boost` (criatura da
  fação que CONTROLA o local — projection — pesa ×2). Assinatura ganha
  `state`-lite opcional (bestiary_knowledge + projection); call sites atualizam.
  Sem os dados → comportamento atual (retrocompatível).
- **R3 (migração)** — criatura sob pressão < 0.3 numa região abre vaga: o
  sorteio pode puxar criatura de REGIÃO CONECTADA (connections do mapa, rotas
  bloqueadas da 6.1 respeitadas) com peso 0.5 — "os lobos desceram a serra
  porque os ratos sumiram". Determinístico, no máximo 1 migrante por sorteio.
- **R4 (loot acompanha)** — `roll_loot` (4.4): pool `comum` da região perde
  temporariamente itens droppados por criaturas quase-extintas (mapeamento
  criatura→loot já existe no bestiário, campo `loot`). Peles somem quando os
  bichos somem.
- **R5 (visibilidade)** — narrador ciente: nota no context pack quando a região
  está sob pressão ("a caça anda escassa por aqui") ou recebendo migrantes;
  Codex do jogador (3.2) mostra grau de raridade na entrada da criatura
  ("quase não se vê mais por aqui").
- **R6** — Tudo offline-testável com `bestiary_knowledge`/projection sintéticos.

### Fora de escopo

- População numérica simulada (contadores de indivíduos) — é peso, não census.
- Extinção PERMANENTE (decay sempre recupera — mundo não esvazia).
- Migração de BOSS (ficam onde o Codex os pôs).
- Reação de fações à ecologia (caçadores contratando o player — gancho de quest futuro).

## 3. Design técnico

### Arquivo novo

- **`services/ecology.py`** (puro): `hunt_pressure(...)`, `faction_boost(enemy,
  location_id, projection)`, `weighted_pick(candidates, weights, rng)`,
  `migrant_candidates(loc, projection)`, `suppressed_loot(region_bk, bestiary)`.

### Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `world_utils.py` | `pick_encounter_enemy(loc, danger, turn, faction_id, *, bestiary_knowledge=None, projection=None, rng=None)` — sorteio ponderado + migrante |
| `agents/combat.py` (fill 4.6) + `world_utils` encounters | repassam bestiary_knowledge/projection |
| `services/economy.py` | `roll_loot` aceita supressão R4 |
| `services/context_builder.py` | nota de pressão/migração |
| `services/discovery.py` (codex 3.2) | rótulo de raridade regional na entrada |
| `tests/test_fase63.py` | suíte |

### Fórmulas (constantes em ecology.py — chute declarado, playtest ajusta)

```
recent_kills = kills com last_seen_turn > turn - 20
pressure     = 1.0  se 0     · 0.6 se 1–2 · 0.3 se 3–5 · 0.1 se 6+
faction_boost= 2.0  se enemy.faction == controlador do local, senão 1.0
migrant      = habilitado se pressure média do pool local < 0.3
```

### Decisões

1. **`bestiary_knowledge` é o census** — a 3.2 já conta kills por criatura com
   turno; reutilizar é zero estado novo e o jogador VÊ a mesma verdade no Codex.
2. **Peso, não remoção** — criatura nunca sai do pool (0.1 ≠ 0): mundo raro,
   não vazio; e o decay devolve.
3. **Migração respeita o grafo** — vem de connection (e rotas bloqueadas da 6.1
   também bloqueiam bicho — coerência barata entre as fatias).

## 4. Plano passo a passo

1. **Etapa 1 — ecology.py (TDD):** `test_pressure_faixas`, `test_decay_janela`,
   `test_faction_boost`, `test_weighted_pick_rng_semeado`.
2. **Etapa 2 — sorteio integrado:** `test_pick_respeita_pressao` (criatura
   caçada 6× quase não sai em 200 sorteios semeados), `test_migrante_entra`,
   `test_sem_dados_comportamento_legado`, `test_rota_bloqueada_barra_migrante`.
3. **Etapa 3 — loot suprimido:** `test_loot_some_com_extincao_local`,
   `test_loot_volta_com_decay`.
4. **Etapa 4 — visibilidade:** context pack + Codex (rótulo).
5. Suíte completa verde + build.

## 5. Critérios de aceite

- [ ] Matar a mesma criatura 6× em 20 turnos → quase some dos encontros da região; parar de caçar → volta
- [ ] Fação hostil no controle → criaturas dela dominam os encontros do local
- [ ] Migrante só de região conectada e alcançável (6.1 respeitada)
- [ ] Loot regional perde os drops da criatura suprimida
- [ ] Codex do jogador reflete a raridade; narrador comenta a escassez
- [ ] `uv run pytest` verde; zero LLM novo; saves antigos ok (dados opcionais)

## 6. Smoke test com LLM real

1. Save com pressão alta forjada → viajar/explorar → narração menciona escassez
   e o encontro sorteia coerente (1 request de storyteller + 1 de combate).

## 7. Riscos & compatibilidade

- **Assinatura de `pick_encounter_enemy` muda** — kwargs opcionais com default
  preservam call sites/testes antigos.
- **RNG em teste** — todas as funções aceitam `rng` injetável (padrão 4.4).
- **Percepção de "mapa vazio"** se as constantes forem agressivas — pesos são
  constantes nomeadas; playtest calibra.
