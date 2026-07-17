# SPEC — Dedupe/cooldown de encontros e NPCs reciclados

> **Status:** `draft`
> **Criada:** 2026-07-16 · **Atualizada:** 2026-07-16
> **Depende de:** npcs-3-camadas (`done`), Fase 2.8 context builder (`done`)
> **Desbloqueia:** —

---

## 1. Contexto & Objetivo

Playtest longo 2026-07-14 (achado G): o NPC gerado **"Sobrevivente moribundo"**
apareceu 3× em 6 turnos no run do explorador — em caverna de Morrakh, nas
Profundezas de Morrakh e no Anel Dourado — com a MESMA fala (mina/colmeia,
"algo despertou") quase verbatim. Quebra de imersão grave: o mundo parece um
carrossel de templates.

Causa provável (verificar na implementação): NPCs/encontros gerados entram no
cache (`data/npc_database.json` / `npcs` do estado) e são reinjetados no
contexto do storyteller sem filtro de localização nem cooldown, e o LLM os
reusa porque estão "à mão".

## 2. Requisitos

- **R1** — NPC gerado ganha vínculo de local: `home_location_id` (local onde
  foi criado). Contexto do storyteller/context_pack só inclui NPCs cujo
  `home_location_id` é o local atual OU que estejam `in_scene`/party.
- **R2** — Cooldown de reuso: NPC "descartável" (gerado por encontro, não
  curado) que já apareceu em cena não reaparece por
  `ENCOUNTER_COOLDOWN_TURNS = 20` turnos (`last_seen_turn` no registro do NPC),
  a menos que o jogador o procure nominalmente.
- **R3** — Encontros do storyteller sorteiam evitando o último template usado:
  registro `world["last_encounter_id"]` — o mesmo id não repete 2× seguidas no
  mesmo local.
- **R4** — Invariante de playtest `narrative.recycled_npc` (`warning`): mesmo
  NPC gerado aparecendo em ≥3 locais distintos em janela de 10 turnos.

### Fora de escopo

- NPCs curados do Codex (podem legitimamente estar onde a curadoria mandar).
- Migração/movimento de NPC entre locais (feature, não bug).
- Dedupe semântico de entidades (já existe: `librarian.find_existing_entity`).

## 3. Design técnico

- **`agents/npc.py`** (`generate_new_npc`) — gravar `home_location_id` e
  `created_turn` no registro do NPC (cache `data/npc_database.json` + estado).
- **`services/npc_layers.py`** — view/filtros: função
  `npcs_for_context(state) -> list` aplicando R1+R2 (usada pelo storyteller e
  pelo `context_builder`).
- **`services/context_builder.py`** — trocar a fonte de NPCs pela view acima.
- **`agents/storyteller.py`** — ao materializar encontro com NPC gerado:
  atualizar `last_seen_turn`; R3 no sorteio de encontro.
- **`playtest/invariants.py`** — R4 (rastrear `(npc, location)` por turno).
- Saves antigos: registros sem `home_location_id` → tratados como "sem
  vínculo" (aparecem só via `in_scene`, nunca injetados por localização).

## 4. Plano passo a passo

### Etapa 1 — vínculo de local + view filtrada
1. **Testes** (`tests/test_encontros_dedupe.py`):
   `test_npc_gerado_ganha_home_location`;
   `test_context_exclui_npc_de_outro_local`;
   `test_party_e_in_scene_sempre_entram`.
2. **Implementação:** generate_new_npc + npcs_for_context + context_builder.
3. `uv run pytest` verde.

### Etapa 2 — cooldown + anti-repetição de encontro
1. **Testes:** `test_cooldown_20_turnos`; `test_procura_nominal_ignora_cooldown`;
   `test_encontro_nao_repete_template_consecutivo` (RNG semeado).
2. **Implementação:** last_seen_turn + last_encounter_id.
3. `uv run pytest` verde.

### Etapa 3 — invariante
1. **Testes:** `test_invariante_recycled_npc` (fixture com NPC em 3 locais/10
   turnos → warning).
2. **Implementação:** check 5.2.
3. Playtest mock `explorador` 50 turnos: zero `narrative.recycled_npc`.

## 5. Critérios de aceite

- [ ] R1–R4 com testes
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Saves antigos continuam carregando (campos novos opcionais)
- [ ] Cache `npc_database.json` antigo continua legível (campos ausentes ok)

## 6. Smoke test com LLM real

1. Run real `explorador` 20–30 turnos cruzando 3+ regiões: nenhum NPC gerado
   repetido em locais diferentes (conferir no `transcript`).
2. Voltar ao local de origem de um NPC gerado após 20+ turnos → ele PODE
   reaparecer (cooldown expira).

## 7. Riscos & compatibilidade

- Contexto mais magro pode deixar o storyteller com menos material — aceitável:
  ele inventa local-consistente em vez de reciclar global.
- MockLLM: filtros são determinísticos; suíte offline cobre tudo exceto a
  tendência do LLM de reusar — essa só o smoke real pega.
- `data/npc_database.json` é cache runtime (pendência conhecida de isolamento
  em teste) — testes usam tmp_path, não o arquivo real.
