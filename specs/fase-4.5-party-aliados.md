# SPEC — Fase 4.5: Party — aliados em combate

> **Status:** `draft`
> **Criada:** 2026-07-03 · **Atualizada:** 2026-07-03
> **Depende de:** Fase 4.2 (condições/modificadores simétricos — aliado usa o mesmo motor)
> **Desbloqueia:** Fase 4.6 (orçamento de encontro considera tamanho da party); passiva "aliados adjacentes" do Cavaleiro vira real (nota da 4.2)

---

## 1. Contexto & Objetivo

`CompanionState` existe em `state.py:71` (`{name, hp, max_hp, active, stats}`) e
`party: List[CompanionState]` está no GameState e na persistência — **zero lógica
consome isso**. NPCs têm `relationship` (Fase 2) que também não desagua em nada
mecânico. Meta da fase (ROADMAP): **eu + 3 NPCs vs 5 orcs resolve sem crash**.

Esta spec: recrutamento por relacionamento, generalização do loop de combate para
N vs N (aliados agem com os perfis de comportamento da 2.5b; inimigos escolhem
alvo taticamente), morte de aliado com consequência de mundo, e comandos básicos
fora de combate.

Princípio: aliado é resolvido pelo MESMO motor determinístico do inimigo
(`choose_enemy_attack`/`resolve_enemy_turn` generalizados) — não é um segundo
sistema de combate.

## 2. Requisitos

- **R1 (ficha)** — `CompanionState` expandido: `id` (canônico se NPC do grafo),
  `name`, `hp/max_hp`, `attributes`, `defense`, `attacks` (formato do bestiário),
  `behavior` (perfis 2.5b: tatico/feroz/covarde/implacavel), `active`,
  `active_conditions`, `origin_npc: str|None`. Companion criado por
  `make_companion_from_npc(npc, name)` determinístico: arquétipo por
  palavras-chave da descrição do NPC (guerreiro/arqueiro/curandeiro/mago →
  templates em `data/companions.json`), fallback template `capanga`.
- **R2 (recrutamento)** — convite via rota NPC: jogador pede ("junte-se a mim") →
  `npc_actor` identifica intenção de recrutamento (campo novo no structured
  output existente, dentro do guard) → **gate determinístico em Python**:
  `relationship >= 60` E `len(party ativos) < 3` E NPC não é de fação com
  disposition hostil ao jogador. Falha do gate = NPC recusa (narração usa o
  motivo). LLM não decide se aceita — só narra.
- **R3 (combate N vs N)** — `roll_initiative(player, enemies, allies=[])` inclui
  aliados no lado `hero`; no loop de rounds, turno de aliado resolve via
  `resolve_ally_turn(ally, enemies, ...)` reutilizando `choose_enemy_attack`
  (perfil decide agressividade/fuga/foco). Tick de condições/DoT roda para
  aliados (motor 4.2, simétrico).
- **R4 (alvo tático dos inimigos)** — `resolve_enemy_turn` recebe
  `targets: List[Dict]` (player + aliados ativos) em vez de só player. Escolha por
  perfil: `tatico` → alvo de menor HP%; `feroz` → alvo que causou mais dano no
  round anterior (fallback: aleatório); `covarde` → alvo de menor defense;
  `implacavel` → player sempre. Determinístico e testável.
- **R5 (morte de aliado)** — hp ≤ 0: `active=False`, log mecânico, narração de
  morte; se `origin_npc` é canônico → evento `npc_killed`
  (`actor_id="enemy"`) no pipeline 2.6 → crônica/rule_engine/quests órfãs já
  reagem de graça (sistemas 2.7/3.3 existentes).
- **R6 (fora de combate)** — comandos determinísticos: `esperar` (active=False,
  fica no local — registra `waiting_at`), `seguir` (active=True),
  `dispensar` (sai da party; se NPC canônico, volta ao pool de NPCs com
  relationship preservado). Router identifica intenção party (rota NPC existente
  serve — sem nó novo no grafo).
- **R7 (persistência/HUD)** — party completa no save (já serializa; conferir
  campos novos); `GET /game/state` expõe party com HP; frontend: HP bars da
  party no HUD de combate.
- **R8** — Meta observável: teste de integração `test_4v5_sem_crash` — player +
  3 companions vs 5 inimigos, rounds até acabar, sem exceção, vencedor coerente.

### Fora de escopo

- XP/level up de companion (fichas fixas por arquétipo; revisar pós-4.6).
- Equipamento/inventário de companion.
- Ordens táticas em combate ("foca no mago") — aliado age pelo perfil; v2.
- Companion com árvore de habilidades (usa `attacks` estilo bestiário).
- Romance/loyalty além do `relationship` existente.
- Passiva "aliados adjacentes" do Cavaleiro (4.2 nota) — ATIVAR aqui:
  trigger `always` vira `party_ativa >= 1` (item pequeno, entra no plano).

## 3. Design técnico

### Arquivos novos

- **`party.py`** (raiz, puro): `make_companion_from_npc(npc: dict, name: str) ->
  CompanionState`, `can_recruit(state, npc_name) -> tuple[bool, str]` (gate R2),
  `recruit(state, npc_name) -> dict parcial`, `dismiss(state, name)`,
  `set_waiting(state, name)`, `active_allies(state) -> list`.
- **`data/companions.json`** — 4–5 templates de arquétipo (guerreiro, arqueiro,
  curandeiro, mago, capanga): attacks, attributes, hp, behavior.
- **`tests/test_fase45.py`**.

### Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `state.py` | `CompanionState` expandido (R1) — campos novos opcionais p/ compat |
| `combat_mechanics.py` | `roll_initiative(..., allies)`; `resolve_enemy_turn(enemy, targets, ...)`; `resolve_ally_turn` novo; seleção tática de alvo (R4) |
| `agents/combat.py` | loop de rounds inclui aliados; morte de aliado → `npc_killed` (reusa `_kill_events` generalizado); logs de party p/ narrador |
| `agents/npc.py` | intenção de recrutamento no structured output existente (**dentro do guard**); chama `party.can_recruit`/`recruit` |
| `agents/router.py` | palavras de party (esperar/seguir/dispensar) roteiam p/ NPC |
| `persistence.py` | backfill: party antiga (schema mínimo) ganha defaults dos campos novos |
| `api.py` / `game_engine.py` / `web/` | party no state; HP bars |
| `data/classes.json` | passiva do Cavaleiro: trigger `party_ativa` (fecha nota da 4.2) |

### Assinaturas-chave

```python
# combat_mechanics.py
def resolve_ally_turn(ally: Dict, enemies: List[Dict], rnd: int) -> List[str]: ...
    # perfil 2.5b decide ação (choose_enemy_attack reusado com lado invertido);
    # muta ally/enemies; retorna logs

def pick_target(enemy: Dict, targets: List[Dict], last_damage: Dict[str, int]) -> Dict: ...
    # R4 — determinístico por perfil; targets = [player] + aliados ativos
```

### Decisões

1. **Companion ≈ inimigo do lado hero** — mesma estrutura de dados do bestiário
   (attacks/behavior/attributes), mesmo resolvedor. Um motor, dois lados; a 4.6
   melhora IA dos dois de uma vez.
2. **Gate de recrutamento em Python** — `relationship >= 60` (limiar único,
   constante em `party.py`), teto de 3 ativos. LLM narra o "sim/não", não o decide.
3. **Morte de aliado canônico alimenta o mundo** — `npc_killed` dispara os
   sistemas existentes (crônica 3.1, quests órfãs 3.3, cascata 2.7). De graça.
4. **Sem nó novo no grafo** — recrutamento/comandos passam pela rota NPC; combate
   já é um nó. (Checklist CLAUDE.md: sem agente novo → nada a conectar ao archivist.)

## 4. Plano passo a passo

### Etapa 1 — Ficha + templates (TDD)

1. **Testes:** `test_make_companion_arquetipo` (descrição "arqueiro élfico" →
   template arqueiro); `test_make_companion_fallback_capanga`;
   `test_companions_json_schema`.
2. **Implementação:** `party.py` (ficha) + `companions.json` + `state.py`.

### Etapa 2 — Recrutamento + comandos

1. **Testes:** `test_can_recruit_relationship_baixo_nega`;
   `test_can_recruit_teto_3`; `test_recruit_move_npc_para_party`;
   `test_dismiss_preserva_relationship`; `test_esperar_seguir`.
2. **Implementação:** gates + integração `npc.py`/`router.py` (campo novo no guard).

### Etapa 3 — Combate N vs N

1. **Testes:** `test_iniciativa_inclui_aliados`; `test_ally_turn_ataca_por_perfil`;
   `test_pick_target_tatico_menor_hp`; `test_pick_target_implacavel_player`;
   `test_dot_ticka_em_aliado`; **`test_4v5_sem_crash` (R8, critério da fase)**.
2. **Implementação:** `combat_mechanics.py` generalizado + loop em `combat.py`.
3. **Atenção:** assinaturas de `roll_initiative`/`resolve_enemy_turn` mudam —
   atualizar TODOS os call sites e testes existentes (test_mvp, test_combat_heal...).

### Etapa 4 — Morte de aliado + mundo

1. **Testes:** `test_morte_aliado_desativa_e_loga`;
   `test_morte_aliado_canonico_gera_npc_killed`;
   `test_quest_orfa_por_morte_de_companion` (integração 3.3 de graça).
2. **Implementação:** hook no loop + `_kill_events` generalizado.

### Etapa 5 — Persistência/HUD + passiva do Cavaleiro

1. **Testes:** `test_save_load_party_completa`; `test_backfill_party_antiga`;
   `test_muralha_humana_com_party` (trigger real).
2. **Implementação:** persistence/api/CLI/web; `npm run build`.

## 5. Critérios de aceite

- [ ] Player + 3 companions vs 5 inimigos resolve sem crash (critério da Fase 4)
- [ ] NPC com relationship < 60 recusa; ≥ 60 junta; teto de 3 respeitado
- [ ] Inimigo tático ataca o alvo de menor HP% (não sempre o player)
- [ ] Morte de companion canônico gera `npc_killed` → crônica + quests órfãs reagem
- [ ] Esperar/seguir/dispensar funcionam e persistem
- [ ] HP bars da party no frontend
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Campo novo de recrutamento dentro do guard existente do npc_actor
- [ ] Saves antigos (party vazia/schema mínimo) carregam
- [ ] `ESTADO_ATUAL.md` + `ROADMAP.md` atualizados

## 6. Smoke test com LLM real

1. Conversar com NPC de relationship alto → "junte-se a mim" → campo de
   recrutamento mapeado pelo Gemini real (MockLLM esconderia), NPC aceita.
2. Entrar em combate com 1 companion → narração menciona o aliado agindo
   (log de ally chega ao narrador).
3. Pedir recrutamento a NPC hostil → recusa com motivo do gate.

(3 requests.)

## 7. Riscos & compatibilidade

- **Mudança de assinatura em combat_mechanics** — maior risco de regressão da
  fase; mitigação: default `allies=[]`/`targets=[player]` mantém call sites
  antigos válidos durante a migração, suíte completa como rede.
- **Saves antigos:** party `[]` ou schema mínimo — backfill de defaults.
- **MockLLM:** adicionar intenção de recrutamento ao mock p/ testes offline.
- **Narração com 9 combatentes:** log mecânico cresce — truncar/resumir logs por
  round no prompt do narrador (orçamento já existe via context pack 2.8).
- **Balanceamento:** 4 vs N desequilibra encontros atuais — aceitável até a 4.6
  (orçamento de encontro considera party).
