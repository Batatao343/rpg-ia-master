# SPEC — Fase 4.6: Dificuldade, IA de combate e morte

> **Status:** `draft`
> **Criada:** 2026-07-03 · **Atualizada:** 2026-07-03
> **Depende de:** Fase 4.1 (nível do player p/ orçamento) · 4.2 (condições — habilidades de inimigo aplicam) · 4.5 (party no orçamento de encontro)
> **Desbloqueia:** fecha a Fase 4 (Gameplay Core)

---

## 1. Contexto & Objetivo

Três buracos: (1) **spawn sem teto** — `EncounterScanner` (agents/combat.py:67)
deixa o LLM decidir QUANTOS inimigos entram na cena, sem clamp ("uma horda de
orcs" → o que o LLM quiser); (2) **inimigos burros** — campo `abilities` do
bestiário é decorativo; todo inimigo só usa `attacks` básicos; perfis 2.5b
decidem QUANDO fugir, mas não O QUE fazer de especial; (3) **morte do player
sem narrativa** — CLI imprime "💀 VOCÊ MORREU." seco (game_engine.py:241),
frontend só tela de morte; a campanha termina sem fecho (bug conhecido).

Esta spec fecha a Fase 4: dificuldade previsível (orçamento determinístico por
nível/danger/party), inimigos que usam as próprias habilidades, boss com fases,
e morte com fecho narrativo + capítulo final da crônica.

## 2. Requisitos

- **R1 (clamp de spawn)** — Depois do `EncounterScanner`, Python clampa o
  encontro por **orçamento de pontos**: `budget = base(danger) +
  nivel_player + 2×(companions ativos)`; custo: minion 2, elite 5, boss 12
  (`type` do bestiário). `base(danger)`: 1→2, 2→4, 3→7, 4→10. Corte
  determinístico: remove instâncias excedentes (mantém pelo menos 1). LLM nunca
  decide quantidade final.
- **R2 (piso)** — Encontro também tem piso (`budget/2`): scanner detectou pouco
  em local danger 4 → completa com `pick_encounter_enemy` regional (world_utils,
  2.5b) — dificuldade sobe E desce deterministicamente.
- **R3 (habilidades de inimigo)** — bestiário: entradas ganham `abilities`
  mecânicas opcionais no MESMO schema de habilidade do player (custo em
  stamina/mana do inimigo, `damage_formula`, `conditions`/`effects` 4.2,
  cooldown). `choose_enemy_attack` evolui: perfil decide quando usar habilidade
  vs ataque básico (`tatico`: habilidade quando vantajosa — ex. controle no
  alvo mais forte; `feroz`: maior dano disponível; `covarde`: debuff e
  distância; `implacavel`: rotação fixa). Resolução 100% no motor (simetria 4.2
  já pronta).
- **R4 (curadoria)** — 1ª leva: ~15 inimigos-chave ganham 1–2 habilidades cada
  (elites e bosses das 4 regiões iniciais); minions continuam só com attacks.
- **R5 (boss fights)** — bosses (`type: BOSS`) ganham `phases` no behavior:
  `[{below: 0.5, add_abilities: [...], profile: "implacavel", once_log: "..."}]`
  — threshold de HP% troca perfil/habilidades e emite log de fase (o narrador
  transforma em momento). Determinístico.
- **R6 (morte do player)** — hp ≤ 0: em vez de terminar seco —
  1. motor monta resumo mecânico da queda (quem matou, onde, round);
  2. **1 chamada SMART** narra a morte como fecho de saga (com crônica/context
     pack como contexto; guard de fallback: sem LLM → template determinístico
     digno);
  3. capítulo final da crônica: milestone `player_died` (evento Python, padrão
     3.4) + prosa da queda;
  4. CLI imprime narrativa ANTES da tela de morte; API: `game_over: true` +
     `death_narrative` no response; frontend: tela de morte exibe a narrativa
     + crônica completa (a saga que ficou).
- **R7 (game over limpo)** — save marcado `game_over: true` (não deletado — a
  crônica vira memorial consultável); `/game/action` num save morto → 409 com
  mensagem clara; `/game/new` continua criando sessão nova.
- **R8** — Tudo offline-testável: orçamento, piso, fases, template de morte —
  zero dependência de LLM para a mecânica.

### Fora de escopo

- Modos de dificuldade selecionáveis (fácil/normal/difícil) — v2, vira
  multiplicador do budget.
- Morte de companion com narrativa dedicada (4.5 já loga; fecho épico só p/ player).
- Permadeath com herança/new game+ — backlog.
- IA de inimigo com memória entre combates.
- Rebalancear TODOS os 84 inimigos (só a leva R4).

## 3. Design técnico

### Arquivos novos

- **`encounter_budget.py`** (raiz, puro): `encounter_budget(player_level, danger,
  allies_count) -> int`, `clamp_encounter(enemies, budget) -> (kept, cut_log)`,
  `fill_encounter(enemies, budget, loc, danger) -> list` (piso R2, usa
  `pick_encounter_enemy`), `TIER_COST = {"minion": 2, "elite": 5, "boss": 12}`.
- **`tests/test_fase46.py`**.

### Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `agents/combat.py` | `_spawn_enemies_integrated` → clamp/fill pós-scanner; hook de morte do player (R6); troca de fase de boss no loop |
| `combat_mechanics.py` | `choose_enemy_attack` considera `abilities` mecânicas (custo/cooldown do inimigo — reusa `spend_resources` generalizado); aplicação de fase (R5) |
| `data/bestiary.json` | `abilities` mecânicas na leva R4; `phases` nos BOSS |
| `services/chronicle.py` | `player_died` em `CHRONICLE_EVENT_TYPES` + template "Aqui termina a saga de {name}." |
| `services/event_processor.py` | nada estrutural (fallthrough já cobre `player_died`) — conferir |
| `game_engine.py` | narrativa antes da tela de morte |
| `api.py` | `death_narrative` no response; 409 em save morto; `game_over` persistido |
| `persistence.py` | flag `game_over` (default False no backfill) |
| `web/` | tela de morte com narrativa + crônica |

### Formatos

`bestiary.json` — habilidade de inimigo (mesmo schema do player) e fases:

```json
"abilities": [
  {"id": "grito_de_guerra", "name": "Grito de Guerra",
   "cost": 5, "resource_type": "Estamina", "cooldown": 3,
   "damage_formula": "0", "damage_type": "Debuff",
   "effects": [{"kind": "control", "stat": null, "delta": 0,
                "duration": 1, "control": "fear"}]}
],
"behavior": {
  "profile": "implacavel",
  "phases": [
    {"below": 0.5, "profile": "feroz",
     "add_abilities": ["fenda_abissal"],
     "once_log": "O colosso desperta de verdade."}
  ]
}
```

Template determinístico de morte (fallback sem LLM):

```
"{name}, {class_name}, caiu em {location} no dia {day}, diante de {killer}.
A crônica guarda o que a estrada levou."
```

### Decisões

1. **Orçamento em pontos, não contagem** — 1 boss ≠ 6 minions; pontos escalam
   com nível E party (fecha o desequilíbrio deixado pela 4.5).
2. **Clamp DEPOIS do scanner** — narrativa continua livre ("horda"), mecânica
   corta; o log de corte ("apenas 3 alcançam você") vira material de narração,
   não contradição.
3. **Habilidade de inimigo = schema do player** — um resolvedor só; 4.2 fez a
   simetria de condições, aqui só a seleção de ação muda.
4. **Morte gasta 1 request SMART** — único uso de LLM da spec; momento raro e de
   alto valor emocional; template digno cobre mock/fallback/quota (convenção
   CRÍTICA respeitada: try/except em volta).
5. **Save morto vira memorial** — crônica 3.1 já guarda a saga; deletar seria
   jogar fora o produto do jogo inteiro.

## 4. Plano passo a passo

### Etapa 1 — Orçamento de encontro (TDD)

1. **Testes:** `test_budget_formula` (níveis/dangers/party);
   `test_clamp_corta_excedente` (horda de 10 → cabe no budget, ≥1 sobra);
   `test_clamp_prioriza_variedade` (mantém o elite, corta minions repetidos);
   `test_fill_completa_piso` (danger 4 + 1 minion → reforço regional);
   `test_boss_nao_e_cortado`.
2. **Implementação:** `encounter_budget.py` + integração no spawn.

### Etapa 2 — Habilidades de inimigo

1. **Testes:** `test_enemy_ability_custo_cooldown`;
   `test_tatico_usa_controle`; `test_feroz_maior_dano`;
   `test_ability_aplica_condicao_42` (fear no player → -2 acerto);
   `test_minion_sem_ability_segue_attacks`.
2. **Implementação:** `choose_enemy_attack` + `spend_resources` generalizado
   (inimigo tem stamina/mana desde o spawn — combat.py:103 já seta defaults).

### Etapa 3 — Curadoria (leva R4)

1. **Testes:** `test_abilities_bestiario_schema_valido` (ids únicos, formulas
   parseáveis, effects tipados 4.2).
2. **Implementação:** ~15 elites/bosses com 1–2 habilidades temáticas
   (coerentes com região/fação — tom do mundo, sem spoiler; mesmo critério da 4.1b).

### Etapa 4 — Boss phases

1. **Testes:** `test_fase_troca_perfil_no_threshold`; `test_fase_once_log_unico`;
   `test_fase_adiciona_habilidade`; `test_boss_sem_phases_ok`.
2. **Implementação:** aplicação de fase no loop de rounds.

### Etapa 5 — Morte do player

1. **Testes:** `test_morte_gera_player_died_e_capitulo_final`;
   `test_template_morte_sem_llm` (mock/fallback → template digno, sem crash);
   `test_save_morto_marca_game_over`; `test_action_em_save_morto_409`.
2. **Implementação:** hook de morte, chamada SMART com guard, chronicle,
   api/CLI/web.
3. **Verificação:** suíte completa + smoke_api + `npm run build`.

## 5. Critérios de aceite

- [ ] "Uma horda infinita" narrada vira encontro dentro do orçamento (assert no clamp)
- [ ] Encontro fraco em local perigoso é reforçado até o piso
- [ ] Elite/boss usa habilidade própria com custo/cooldown; condição chega ao player
- [ ] Boss abaixo de 50% HP muda de fase (perfil + habilidade nova + log único)
- [ ] Morte do player: narrativa de fecho (LLM real) OU template digno (sem chave) + capítulo final da crônica + tela de morte com a saga
- [ ] Save morto é memorial: não aceita ações, crônica consultável
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM na narração de morte (única chamada nova)
- [ ] Saves antigos carregam (`game_over` default False)
- [ ] `ESTADO_ATUAL.md` + `ROADMAP.md` atualizados — **Fase 4 completa**

## 6. Smoke test com LLM real

1. Provocar horda em local danger baixo → scanner detecta muitos, jogo spawna
   clampado, narração coerente com o corte.
2. Combate com elite da leva R4 → habilidade especial usada e narrada.
3. Morrer de propósito → narrativa de morte digna do Gemini (SMART) + crônica
   fechada no frontend.

(≈ 4 requests; morte usa 1 SMART.)

## 7. Riscos & compatibilidade

- **Saves antigos:** `game_over`/`phases` defaults — sem migração.
- **MockLLM:** morte cai no template determinístico — testável offline;
  narrativa real só no smoke.
- **Clamp vs narrativa:** LLM narrou 10, motor manteve 4 — decisão 2 resolve
  (log de corte alimenta o narrador); conferir no smoke 1.
- **Boss balance:** custos/fases da leva R4 são chute inicial — mesmo racional
  da 4.1 (ajustar constante, não arquitetura).
- **`spend_resources` generalizado** (player→qualquer entidade) — regressão
  possível em cooldowns do player; suíte existente cobre.
