# SPEC — Playtest mede a economia de Entropia (agente curioso + telemetria de gasto)

> **Status:** `done` (2026-08-02)
> **Criada:** 2026-07-20 · **Atualizada:** 2026-08-02
> **Depende de:** [refatoracao-sistema-classes](refatoracao-sistema-classes.md) `done` ·
> [arvores-habilidade-classes](arvores-habilidade-classes.md) `done` ·
> [balanceamento-classes-pos-playtest](balanceamento-classes-pos-playtest.md) `in-progress` (instrumentação)
> **Desbloqueia:** [balanceamento-classes-pos-playtest](balanceamento-classes-pos-playtest.md) Etapa 3
> (tuning dos 8 knobs `[BALANCEAR]`) · [letalidade-early-game-v2](letalidade-early-game-v2.md)
> (dado de letalidade limpo, sem o viés do agente suicida)

---

## 1. Contexto & Objetivo

O playtest longo de balanceamento (`run_id 20260719-160014`, 15 campanhas reais,
0 erro) provou que **a telemetria de Entropia é cega e o harness não exercita o
recurso**. Dois defeitos encadeados:

1. **A métrica é degenerada.** `flooding=100%` e `starvation=0%` em TODAS as 15
   campanhas (inclusive reais). Minerando o JSONL cru, a Entropia fica **`16/16`
   em TODO turno de combate**, do t3 ao t30. Causa: `telemetry.build_summary`
   mede o **snapshot no fim do turno** (`player.entropy`), e o gatilho de
   Entropia (`on_damage_taken` etc.) reenche o pool ATÉ O TETO antes do snapshot
   — o jogador leva dano todo turno → sempre cheio. A métrica nunca vê **gasto**.

2. **O agente de teste nunca usa habilidade.** Os perfis (`playtest/profiles.py`)
   emitem, em combate, strings fixas — `Agressivo` → "Ataco {alvo} com toda a
   força."; `Combate` → "Ataco o inimigo mais próximo.". **Nenhum perfil lê
   `player.known_abilities` nem nomeia uma das 101 habilidades.** O
   `combat_agent` parseia todo turno como `ataque_basico` (custo de Entropia 0)
   → o pool nunca drena, a Carga só sobe pelos gatilhos passivos (por isso só o
   Devoto acumula Carga). O sistema de classes inteiro (Entropia/Carga/árvore)
   **não é tocado pelo harness**.

Consequência: os 8 knobs `[BALANCEAR]` das classes são **indecidíveis por
telemetria** — não porque falte instrumentação, mas porque (a) o número medido é
sempre 100/0 e (b) o comportamento medido nunca gasta o recurso. A spec de
balanceamento adiou o tuning por isso mesmo ("mock não mede economia de
Entropia... exige rodada real dedicada"). Esta spec ataca as duas raízes.

Princípio: **"Mecânica é Python"** — a telemetria de gasto é hook determinístico
sobre o resultado do combate (`combat_mechanics` já resolve tudo em código); zero
mudança de regra de jogo. O agente curioso é política determinística (perfil PURO
com `rng` próprio), como todo perfil existente.

## 2. Requisitos

- **R1 — Perfil de combate usa habilidade.** Em combate, os perfis que atacam
  (`agressivo`, `combate`; e por extensão qualquer perfil em combate) leem
  `player.known_abilities`, resolvem os ids ATIVOS que gastam Entropia (via
  `gamedata.ABILITIES`, `ability_kind == "active"` e custo de Entropia > 0) e,
  com probabilidade determinística, emitem a ação nomeando a habilidade e o alvo
  ("Uso {nome} em {alvo}."). Sem habilidade ativa elegível (ou Entropia
  insuficiente para qualquer uma) → cai no ataque básico atual. Continua PURO
  (mesmo `(profile, seed)` → mesma sequência).
- **R2 — Agente não é suicida cego.** Perfil em combate com HP baixo
  (`hp/max_hp <= limiar`, ex. 30%) prioriza um consumível de cura do inventário
  ("Bebo a poção de cura.") quando existe, ou tenta fuga se o perfil suporta;
  fora de combate, com HP baixo e local seguro, descansa em vez de buscar o nó
  mais perigoso. Objetivo: remover o viés "morre porque nunca cura", que polui
  tanto a economia de Entropia quanto o dado de letalidade. **Não** transforma o
  perfil `combate`/`fujao` em covarde — só evita a morte trivialmente evitável.
- **R3 — Telemetria de GASTO de Entropia (não snapshot).** O loop de combate
  registra, por turno, quanta Entropia foi de fato **consumida** por ação do
  jogador e se a ação foi habilidade ativa vs ataque básico. Fonte: hook
  determinístico em `combat_mechanics.resolve_player_action` (ou retorno
  estruturado) — a mecânica já sabe o custo pago; só precisa expô-lo. Campos
  novos por turno no JSONL: `entropy_spent` (int, gasto no turno),
  `used_active_ability` (bool), `ability_id` (str|None).
- **R4 — Métricas agregadas redefinidas.** `summary.json` ganha, sob `entropy`:
  - `spent_total` / `spent_per_combat_turn` (média);
  - `pct_combat_turns_ability_used` (turnos de combate com `used_active_ability`);
  - `pct_combat_turns_basic_only` (o complementar — ataque básico só);
  - `starvation_pct_combat` **REDEFINIDO**: turnos de combate em que o jogador
    QUIS/precisou de uma ativa mas tinha Entropia < custo mínimo das suas ativas
    (recurso faltou), não "snapshot == 0";
  - `flooding_pct_combat` **REDEFINIDO**: turnos de combate que terminaram com
    ataque básico E Entropia cheia (recurso sobrou e não foi usado) — mede
    gatilho/pool irrelevante, não "snapshot == max".
  Os campos snapshot antigos (`peak_abyss_charge`, Carga) permanecem — a Carga
  não sofre do bug; só flooding/starvation mudam de definição.
- **R5 — Relatório reflete a economia.** `playtest report` (seção Classes) troca
  as colunas flooding/starvation degeneradas pelas novas + `%ativa` (uso de
  habilidade). A matriz classe × métricas passa a distinguir uma classe que gasta
  bem o recurso de uma que nunca gasta.
- **R6 — Rodada de validação.** Rodada REAL curta pós-mudança (perfis vitais ×
  algumas classes × ~30 turnos, tetos `--max-cost`) demonstrando: (a)
  `pct_combat_turns_ability_used > 0` em toda classe que tem ativa elegível; (b)
  Entropia efetivamente drena mid-combate (snapshot varia, não fica travado em
  max); (c) as novas flooding/starvation deixam de ser 100/0 uniforme. Run_id
  registrado na spec de balanceamento como o baseline que destrava o tuning.
- **R7 — Alvo útil e acervo v4.** O perfil escolhe alvo compatível com o efeito:
  cura/suporte nunca mira inimigo e não é gasto sem alvo útil. Personagem novo
  prioriza as Cartas autorais `conflito-14` da própria classe, não os exemplos
  legados carregados antes por ordem de arquivo.

### Fora de escopo

- **Tuning dos 8 knobs** — segue na spec de balanceamento (esta só faz o dado
  existir; não muda nenhum número de classe).
- **Tuning de letalidade de early-game** — spec própria
  ([letalidade-early-game-v2](letalidade-early-game-v2.md)); esta só remove o
  viés do agente suicida que contamina aquele dado.
- **Mudança de mecânica de combate/Entropia** — nada de gatilho/regra nova; só
  expor o custo que a mecânica JÁ paga.
- **Perfis novos** — reusa os 12 existentes; muda a política de combate deles,
  não adiciona perfil.
- **Comportamento do MockLLM** — mock não parseia nome de habilidade (sempre
  `ataque_basico`); a economia só aparece em `--real`. Isso é esperado e já é a
  premissa da spec de balanceamento (mock = regressão relativa, real = juiz).

## 3. Design técnico

**Arquivos alterados**

- `playtest/profiles.py`
  - Helper compartilhado `_combat_ability_action(state, rng) -> Optional[str]`:
    lê `player.known_abilities`, filtra por `ABILITIES[aid]` com
    `ability_kind == "active"` e custo de Entropia > 0 e custo <= `player.entropy`
    atual; se houver candidatas, escolhe uma com o `rng` e devolve
    `f"Uso {ABILITIES[aid]['name']} em {alvo}."` (alvo = inimigo ativo escolhido,
    reusando a lógica de `Agressivo`). Devolve `None` se nada elegível.
  - Helper `_low_hp(state, frac=0.3) -> bool` e `_heal_action(state) -> Optional[str]`
    (procura consumível de cura no inventário → "Bebo a poção de cura.").
  - `Agressivo.next_action` / `Combate.next_action`: em combate, ordem de
    preferência → (1) `_heal_action` se `_low_hp`; (2) `_combat_ability_action`
    com prob. determinística (ex.: `rng.random() < 0.6`); (3) ataque básico atual.
    Fora de combate: `combate` com HP baixo e local seguro descansa em vez de
    buscar perigo (R2). Todos os ramos continuam PUROS.
  - Custo de Entropia de uma habilidade: ler do schema de `ABILITIES[aid]`
    (campo de custo — confirmar a chave exata no catálogo gerado; hoje o combat
    resolve custo em `combat_mechanics`). Um único helper
    `entropy_cost(aid) -> int` centraliza a leitura.

- `combat_mechanics.py`
  - `resolve_player_action(...)` passa a devolver (ou registrar em estrutura já
    retornada) o **custo de Entropia efetivamente pago** e o `ability_id` usado.
    Se hoje já há um dict/log de retorno, anexar `entropy_spent`/`ability_id`
    ali; senão, adicionar um retorno estruturado mínimo SEM mudar a resolução.
    Determinístico, sem LLM.

- `playtest/runner.py`
  - `TurnRecord` ganha `entropy_spent: int = 0`, `used_active_ability: bool = False`,
    `ability_id: Optional[str] = None`.
  - `_fill_state_metrics` (ou um novo `_fill_combat_metrics`) lê o custo pago do
    resultado do turno de combate. Como o runner invoca o grafo inteiro, a via
    mais limpa é o `combat_node` carimbar no estado um campo efêmero por turno
    (ex.: `state["_last_combat_spend"] = {"entropy_spent": n, "ability_id": aid}`)
    que o runner lê e zera — mesmo padrão de `encounter_eff_danger`. Documentar
    o campo efêmero em `state.py` como "runtime-only, não persistido".

- `playtest/telemetry.py`
  - `turn_to_record`: serializa os 3 campos novos.
  - `build_summary`: bloco `entropy` reescrito conforme R4 (spent_total,
    spent_per_combat_turn, pct_ability_used, pct_basic_only, novas
    flooding/starvation baseadas em gasto).

- `playtest/report.py` — seção Classes usa as colunas novas (R5).

- `state.py` — documentar o campo efêmero `_last_combat_spend` (runtime-only).

- `tests/test_balance_classes.py` (ou `tests/test_playtest_harness.py`) —
  cobertura dos itens (ver Plano).

**Formato JSONL (linha de turno — campos novos):**
```json
{"turn": 12, "route": "combat_agent", "entropy": 9, "max_entropy": 16,
 "entropy_spent": 5, "used_active_ability": true, "ability_id": "punho_do_abismo",
 "abyss_charge": 7, "abyss_tier": "leve"}
```

**Bloco `entropy` do summary (novo):**
```json
"entropy": {
  "spent_total": 84, "spent_per_combat_turn": 3.5,
  "pct_combat_turns_ability_used": 61.0, "pct_combat_turns_basic_only": 39.0,
  "starvation_pct_combat": 12.0, "flooding_pct_combat": 22.0,
  "peak_abyss_charge": 7, "final_abyss_charge": 4, "final_abyss_tier": "leve"
}
```

**Ponto de verdade do custo após o cutover v4:** o custo de Entropia vive nas
Cartas de `data/cards/` e é consultado por `services.cards.get_card`. O catálogo
legado `data/player_abilities.json` foi removido pelo `conflito-13`; o runner
emite uma declaração atômica `kind="card"`, e o mesmo `card_id` resolvido é
registrado no campo de compatibilidade `ability_id` da telemetria.

## 4. Plano passo a passo

### Etapa 1 — Telemetria de gasto (dado antes de comportamento)

1. **Testes** (`tests/test_balance_classes.py`):
   - `test_combat_registra_gasto_entropia`: um turno de combate onde o jogador
     usa ativa com custo N → `TurnRecord.entropy_spent == N`,
     `used_active_ability is True`, `ability_id` correto.
   - `test_ataque_basico_gasta_zero`: ataque básico → `entropy_spent == 0`,
     `used_active_ability is False`.
   - `test_summary_metricas_gasto`: summary agrega spent_total/pct_ability_used;
     flooding/starvation usam a definição nova (não snapshot).
2. **Implementação:** retorno de custo em `combat_mechanics.resolve_player_action`
   → campo efêmero no `combat_node` → `TurnRecord` → `telemetry`.
3. **Verificação:** `uv run pytest` verde.

### Etapa 2 — Agente curioso + não-suicida

1. **Testes** (`tests/test_playtest_profiles.py` ou existente):
   - `test_agressivo_usa_habilidade_quando_tem_entropia`: estado com ativa
     elegível + Entropia suficiente → alguma seed produz "Uso {nome} em {alvo}.".
   - `test_agressivo_cai_pro_basico_sem_entropia`: Entropia 0 → volta ao ataque
     básico (nunca emite ação inválida).
   - `test_perfil_cura_com_hp_baixo`: HP < 30% + poção no inventário → ação de
     cura; sem poção → não trava (fuga/básico).
   - `test_determinismo_preservado`: mesma `(profile, seed)` → mesma sequência
     de ações (regressão do contrato PURO).
2. **Implementação:** helpers + ramos de decisão em `profiles.py` (R1/R2).
3. **Verificação:** `uv run pytest` verde; harness mock 12×50t roda sem erro.

### Etapa 3 — Relatório + validação real

1. **Testes:** `test_report_secao_classes_gasto` (markdown tem colunas novas).
2. **Implementação:** `report.py` (R5).
3. **Verificação:** rodada real curta (R6); anexar run_id + números aqui e na
   spec de balanceamento (§8) como o baseline que destrava o tuning.

## 5. Critérios de aceite

- [x] Perfil de combate emite ação de habilidade quando há ativa elegível (teste)
- [x] Perfil cura/recua com HP baixo em vez de morrer trivialmente (teste)
- [x] Determinismo `(profile, seed)` preservado (teste de regressão)
- [x] JSONL por turno tem `entropy_spent`/`used_active_ability`/`ability_id`
- [x] `summary.entropy` traz spent/pct_ability_used + flooding/starvation NOVOS
- [x] `playtest report` mostra as colunas de gasto na seção Classes
- [x] Rodada REAL: `pct_combat_turns_ability_used > 0` e Entropia drena
      mid-combate (não travada em max); run_id registrado
- [x] Médico usa Carta de suporte em alvo aliado útil; acervo inicial usa IDs v4
- [x] `uv run pytest` verde (suíte completa offline)
- [x] Guard de FallbackLLM em todo `with_structured_output` novo (nenhum esperado —
      spec é determinística/telemetria)
- [x] Saves antigos continuam carregando (nenhuma mudança de schema persistido;
      `_last_combat_spend` é efêmero)

## 6. Smoke test com LLM real

1. `uv run python -m playtest run --profile combate --class sangromante --real
   --turns 30 --max-cost 0.05` — completa sem erro; o JSONL mostra
   `used_active_ability: true` em ≥1 turno e `entropy_spent > 0`; a Entropia no
   snapshot VARIA entre turnos de combate (não fica 16/16).
2. `report` do run: seção Classes mostra `%ativa > 0` e as novas
   flooding/starvation ≠ 100/0.
3. Um Médico de Campo (`--class medico_de_campo`) usa uma ativa de suporte e o
   gasto é contabilizado; confirma que não é só classe de dano que registra.

**Evidência real de aceite (2026-08-02):**

- `20260802-161001-110214`, Médico de Campo, 20/20, `mock=false`, zero
  erro/violação, 60 sucessos de rede, US$ 0,0168. O save nasceu com
  `med_sutura`/`med_torniquete`; no turno 13, Sutura de Campo mirou o próprio
  jogador, gastou 1 Entropia e a Vitalidade pós-rodada passou de 6 para 7.
- `20260802-161653-555279`, Sangromante, 30/30, `mock=false`, zero
  erro/violação, 69 sucessos de rede, US$ 0,01932. Cartas `san_*`, 30% dos
  turnos de combate com ativa, 2 de Entropia gastos, flooding 35% e starvation
  0%; a Entropia variou 19→17.
- Regressão completa após os fixes: **1299 passed, 1 skipped, 14 deselected**.

## 7. Riscos & compatibilidade

- **Saves antigos:** nenhum campo persistido muda; `_last_combat_spend` é
  runtime-only. Carregam intactos.
- **MockLLM após o cutover v4:** o runner entrega `TurnDeclaration` atômica ao
  motor, portanto Carta/custo também são exercitados offline sem depender do
  parser de texto. O LLM real continua necessário para validar o grafo completo,
  narração e telemetria de provider.
- **Determinismo:** o ramo novo consome do `rng` do perfil — mudar a política
  muda as sequências gravadas de baselines antigos; aceitável (baselines
  pré-mudança ficam obsoletos, como já previsto na spec de balanceamento). Fixar
  a ordem de consumo do `rng` para reprodutibilidade dentro da nova política.
- **Quota/custo:** validação real curta com teto (~$0.05 no DeepSeek). Groq free
  de fallback.
- **Risco de overfit:** o agente curioso ainda é determinístico; usar ≥2 seeds e
  perfis distintos por classe (como a spec de balanceamento já exige).
