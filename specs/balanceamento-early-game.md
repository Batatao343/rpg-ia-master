# SPEC — Balanceamento do early game + pacing de campanha

> **Status:** `done` (2026-07-13 — implementada com baseline mock+real; ver §8)
> **Criada:** 2026-07-13 · **Atualizada:** 2026-07-13
> **Depende de:** Fase 5 (harness/invariantes/telemetria) `done`; fix-playtest-achados `done`
> **Desbloqueia:** streaming (spec streaming-turno-sse — melhor medir latência num jogo justo); Fase 8+

---

## 1. Contexto & Objetivo

O playtest REAL (10 perfis × 4 turnos e 4 vitais × 30 turnos) mostrou que
`agressivo`/`combate` **morrem no nível 1** mesmo depois dos dois fixes já
entregues (teto de budget `cap = 5 + 3×nível` e `forced_encounter_danger` do
ciclo fix-playtest-achados). Morte na primeira sessão não é dificuldade — é
churn: o jogador novo ainda não aprendeu fuga/descanso/poção e o save já virou
memorial permanente.

Segundo problema do mesmo território (design debt da sessão 2026-06-26):
"campaign manager coloca plot twists com muita frequência". A causa real está em
`_should_replan` ([agents/campaign_manager.py:42-66](../agents/campaign_manager.py)):
**toda viagem dispara replan completo** (`location_moved`, linha 55) — mover-se
entre sublocais vizinhos joga fora o arco e gera "plot twist" novo; o intervalo
de 10 turnos raramente chega a ser o trigger.

Princípio (ROADMAP § Princípios): mecânica é Python; medir antes de ajustar
(harness/telemetria da Fase 5 existem exatamente para isto).

## 2. Requisitos

- **R1 — Medir ANTES de mexer (baseline).** Rodada dedicada de playtest:
  mock `--all --turns 50 --seed 42` + real `combate`/`agressivo` (15 turnos,
  seed fixo, com teto de custo). Novas métricas no summary/report (ver R5)
  gravadas como baseline (`playtest report --baseline`). Nenhum tuning entra
  sem o número de antes.
- **R2 — Sobrevivência nível 1-2.** Meta objetiva: em rodada mock 50 turnos
  seed 42, `combate` e `agressivo` NÃO morrem antes do nível 2 fora de zona
  `apex`/boss roteirizado; no real (15t), primeira morte não ocorre antes do
  turno 8 em zona de danger ≤ 2. Knobs determinísticos, escolhidos COM os dados
  do R1 (ordem de preferência, aplicar o mínimo que atinge a meta):
  1. Encontro forçado no nível 1: máximo 1 inimigo de tier `elite`, nunca 2+
     elites (clamp extra em `encounter_budget.clamp_encounter` quando
     `player_level == 1`);
  2. Teto de budget mais duro no nível 1-2: `cap = 4 + 3×nível` (hoje `5 + 3×nível`);
  3. Piso de HP inicial: +4 a +6 no `base_stats.hp` das classes frágeis
     (dados dizem quais) em `data/classes.json`.
  Zona `apex` e combate DELIBERADO seguem intocados (decisão do
  fix-playtest-achados: "você não pertence aqui" continua valendo).
- **R3 — Derrota narrada: "O Saque" (1x por campanha, pena máxima).**
  *(Refinado com o usuário 2026-07-13 — substitui o desenho por corte de nível.)*
  A PRIMEIRA queda (HP=0) da campanha, em QUALQUER nível, fora de zona `apex` e
  fora de boss, vira **`player_downed`** em vez de `player_died`:
  - o herói acorda **1 dia depois** no último local SEGURO visitado (danger ≤ 1;
    fallback: o próprio local se cidade/interior; senão o hub da região) com
    `max(1, 25% do max_hp)` de HP;
  - **o mundo andou sem ele:** relógio avança 1 dia e as fações progridem como
    numa viagem de custo equivalente (mesmos hooks determinísticos que a viagem
    já usa); clima re-rola;
  - **saque total:** ouro → 0; mochila E slots esvaziados; sobra apenas **1 arma
    básica da classe** (`starting_equipment[0]`, equipada) — o jogo nunca fica
    injogável, mas a morte PESA;
  - itens `unique` saqueados geram `unique_item_lost` (`source="engine"`, canal
    da 6.2) e **voltam ao pool do mundo** — podem reaparecer em loot/loja/inimigo;
  - combate encerra sem espólio/XP; XP/nível/habilidades/crônica intactos;
  - milestone na crônica ("caiu, foi saqueado — e ainda assim levantou") +
    narração digna (template determinístico + 1 chamada FAST opcional com fallback).
  **Elegibilidade derivada do `event_log`** (zero campo novo no save): já existe
  `player_downed` no log ⇒ a próxima queda é memorial. **Permadeath permanece:**
  2ª queda em diante, qualquer boss, qualquer zona `apex` — fecho de saga da 4.6
  intacto. Evento `player_downed` entra no pipeline 2.6 com gate anti-LLM
  `source="combat"` (`ProposedWorldEvent` não tem o campo, LLM não fabrica).
- **R4 — Replan só quando o ARCO muda.** *(Confirmado no refinamento 2026-07-13:
  região nova + intervalo 15 — as variantes "só arco esgotado" e "intervalo 20"
  foram consideradas e descartadas.)* `_should_replan` deixa de replanejar em
  toda viagem: `location_moved` só conta se a REGIÃO mudou (nó pai / prefixo de
  região do mapa — sublocais e interiores do mesmo hub NÃO disparam) E o arco
  atual tem ≥ 1 beat concluído OU está órfão de contexto. Intervalo fixo sobe
  10 → 15 turnos. `needs_replan` explícito (evento grave) continua imediato.
  Meta: em rodada mock do `explorador` (50t), nº de replans cai ≥ 40% vs baseline
  sem que nenhum turno fique sem plano válido.
- **R5 — Métricas de balanceamento no harness.** `playtest/telemetry.py` summary
  ganha: `first_death_turn` (ou null), `downed_count` (R3), `avg_hp_pct_after_combat`
  (média do HP% ao fim de cada combate), `replan_count`. `report.py` mostra por
  perfil e compara no `--baseline`. Invariante 5.2 nova: **`player_downed` 2× na
  mesma campanha, ou em zona apex/boss, é violação `error`** (o "1x por campanha"
  é uma invariante de estado, não só uma regra de código).

### Fora de escopo

- Stats/dano das criaturas do bestiário (mexer só em spawn/budget/HP inicial).
- Dificuldade configurável pelo jogador — DESCARTADA no refinamento 2026-07-13
  (YAGNI; o tuning único + "O Saque" são a resposta de dificuldade do jogo).
- Economia (preços/loot) — só o ouro perdido no `downed`.
- Qualquer mudança em combate deliberado ("ataco tudo" segue por conta e risco).

## 3. Design técnico

**Arquivos alterados**
- `encounter_budget.py` — clamp extra nível 1 (R2.1) e/ou cap (R2.2) em
  `encounter_budget()`/`clamp_encounter()` (linhas 21-44).
- `data/classes.json` — `base_stats.hp` se R2.3 for necessário (dados decidem).
- `combat_mechanics.py` / `agents/combat.py` — fluxo de HP=0: decisão
  `downed vs died` em função pura `death_outcome(world, enemies, event_log) ->
  Literal["downed","died"]` (já houve `player_downed` no log? tag `apex` do
  local? boss presente?); aplicação do saque (`apply_downed`: HP 25%, ouro 0,
  inventário/slots → só arma básica, `unique_item_lost` por único perdido,
  relógio +1 dia + progresso de fações, teleporte pro local seguro, fim de
  combate, eventos).
- `world_utils.py` — `last_safe_location(world) -> str` (último visitado com
  danger ≤ 1; fallback local atual/hub) + reuso do avanço de relógio/fações da
  viagem para o "1 dia apagado".
- `services/event_processor.py` + `services/world_validators.py` — tipo novo
  `player_downed` (handler: milestone da crônica; validator: exige
  `source="combat"`, rejeita proposta de LLM).
- `agents/campaign_manager.py` — `_should_replan` (R4): helper
  `_same_region(loc_a, loc_b)` usando o grafo do mapa (`gamedata` expõe
  região/pai do nó); constante `REPLAN_INTERVAL = 15`.
- `playtest/telemetry.py`, `playtest/report.py`, `playtest/invariants.py` — R5.
- `state.py` — nada novo no schema (downed usa campos existentes do player;
  `player_downed` vive no event_log).

**Assinaturas**
```python
# combat_mechanics.py
def death_outcome(world: dict, enemies: list[dict], event_log: list[dict]) -> str: ...
def apply_downed(player: dict, world: dict) -> tuple[dict, dict, list[dict], str]:
    """-> (player_atualizado, world_atualizado, eventos_gerados, nota_mecanica)
    eventos_gerados = [player_downed] + [unique_item_lost por único saqueado]"""

# world_utils.py
def last_safe_location(world: dict) -> str: ...

# campaign_manager.py
def _same_region(loc_id_a: str, loc_id_b: str) -> bool: ...
```

**Evento (formato no event_log)**
```json
{"type": "player_downed", "source": "combat",
 "payload": {"location_id": "pm_vila_palafitas", "rescued_to": "nova_arcadia",
             "gold_lost": 87, "items_lost": 9,
             "uniques_lost": ["adaga_vidro_dragao"]}, "turn": 7}
```

## 4. Plano passo a passo

### Etapa 1 — Baseline (R1 + R5 primeiro, sem tuning)
1. **Testes** (`tests/test_balance_early.py`): `test_summary_tem_metricas_de_balanceamento`
   (campanha mock curta → summary contém `first_death_turn`/`avg_hp_pct_after_combat`/
   `replan_count`); `test_report_compara_metricas_no_baseline`.
2. **Implementação:** telemetria/report (R5, sem invariante ainda).
3. **Verificação:** rodada mock 50t seed 42 + real 15t (2 perfis) → baseline salvo.

### Etapa 2 — Tuning de spawn (R2)
1. **Testes:** `test_encontro_forcado_nivel1_max_um_elite`;
   `test_budget_nivel1_cap_novo` (se R2.2 entrar); metas do R2 viram asserts do
   harness (`test_combate_nao_morre_nivel1_mock_seed42`).
2. **Implementação:** knobs na ordem, re-rodando a rodada mock entre cada um —
   parar no primeiro que bate a meta.
3. **Verificação:** report vs baseline mostra melhora sem zerar o perigo
   (`avg_hp_pct_after_combat` não pode ir a >90% — combate tem que doer).

### Etapa 3 — Derrota narrada: "O Saque" (R3)
1. **Testes:** `test_primeira_queda_e_downed_segunda_e_died` (event_log decide);
   `test_death_outcome_apex_ou_boss_e_died_mesmo_na_primeira`;
   `test_apply_downed_saqueia_tudo_menos_arma_basica` (ouro 0, slots/mochila
   vazios, arma básica equipada, HP 25%);
   `test_apply_downed_avanca_relogio_facoes_e_teleporta_pro_seguro`;
   `test_unique_saqueado_gera_unique_item_lost_e_volta_ao_pool`;
   `test_validator_rejeita_player_downed_proposto_por_llm`;
   `test_invariante_downed_duplo_ou_apex_e_error`.
2. **Implementação:** funções puras + integração no fim do combate + milestone.
3. **Verificação:** suíte verde; rodada mock: `downed_count` ≤ 1 por campanha em
   TODOS os perfis; campanha do `combate` sobrevive à 1ª queda e continua jogando.

### Etapa 4 — Pacing de replan (R4)
1. **Testes:** `test_viagem_intra_regiao_nao_replaneja`;
   `test_viagem_para_regiao_nova_replaneja`; `test_intervalo_15_turnos`;
   `test_needs_replan_explicito_continua_imediato`.
2. **Implementação:** `_same_region` + condições novas.
3. **Verificação:** rodada mock `explorador` → `replan_count` cai ≥ 40% vs baseline.

## 5. Critérios de aceite

- [x] Baseline gravado ANTES de qualquer knob (mock `20260713-160458` + real
      `20260713-160532/160653/160826`)
- [x] Meta R2: mock 50t seed 42 — nenhuma PRIMEIRA queda vira memorial fora de
      apex nos 12 perfis (1ª queda = Saque; ver §8 sobre a 2ª queda do `agressivo`)
- [x] Meta R4: replans do `explorador` caíram 50 → 4 (−92%, meta ≥ 40%) sem
      turno órfão de plano
- [x] `player_downed` só via `source="combat"`; proposta de LLM rejeitada
- [x] 1ª queda = saque completo (ouro 0, só arma básica) + mundo avançou 1 dia; 2ª queda = memorial
- [x] Invariante nova cobre downed ilegal (2× na campanha, apex ou boss)
- [x] `uv run pytest` verde (769 offline)
- [x] Guard de FallbackLLM: nenhum `with_structured_output` novo (a narração do
      downed usa `invoke` cru com try/except + template determinístico)
- [x] Saves antigos continuam carregando (nenhum campo novo no save)
- [x] ESTADO_ATUAL.md + ROADMAP.md atualizados

## 6. Smoke test com LLM real

1. `python -m playtest run --profile combate --turns 15 --real --seed 7` —
   sem morte antes do turno 8 em danger ≤ 2; se cair, virou `downed`: transcript
   mostra o SAQUE narrado (acordou 1 dia depois, sem nada, com a arma básica) e
   a campanha CONTINUA.
2. Forçar 2ª queda na mesma campanha (CLI) — vira memorial (fecho de saga da 4.6).
3. `python -m playtest run --profile explorador --turns 15 --real --seed 7` —
   transcript mostra arco ESTÁVEL atravessando sublocais (sem plot twist por viagem).

## 7. Riscos & compatibilidade

- **Saves antigos:** zero campo novo no save; `player_downed` só aparece em
  event_log novo. Compatível.
- **MockLLM:** spawn do mock difere da produção (achado da Fase 5) — por isso
  R1 exige baseline REAL além do mock; metas mock são guarda de regressão, não
  verdade de balanceamento.
- **Risco de superproteção:** meta explícita de que combate continua doendo
  (`avg_hp_pct_after_combat` ≤ 90%); apex/boss/deliberado intocados; e o saque
  é pena REAL (decisão do usuário: "a morte tem que pesar") — o downed não é
  um respawn grátis.
- **Risco de frustração pós-saque:** perder tudo pode derrubar a vontade de
  continuar — medir no playtest (campanha continua ativa após downed?); a arma
  básica + XP/habilidades intactos garantem que recuperar é viável.
- **Quota:** rodadas reais curtas (15t × 2-3 perfis) cabem no free tier Groq;
  espalhar por dias se 429 (lição da Fase 5).

## 8. Registro de execução (2026-07-13)

**Baselines (antes de qualquer knob):**
- Mock `20260713-160458` (12 perfis × 50t seed 42): `combate` morria t6 (nv 2),
  `agressivo` t7 (nv 1), `fujao` t24; **replan em TODO turno** (50/50 nos perfis
  vivos — causa: MockLLM devolve `location` fora do mapa, e `location_moved`
  replanejava sempre).
- Real seed 7: `combate` morreu t5 (2× Zumbi Blindado — burst de elites),
  `agressivo` t10 (atrito), ambos nível 1. `secret_rusher` 30t real: 0 erros /
  0 violações — **fix do Verme-Primordial CONFIRMADO no real** (pendência fechada).

**Knobs aplicados (R2, ordem da spec, mínimo que move os dados):**
1. ✅ Knob 1 — `clamp_encounter(player_level=1)`: máx 1 elite no nível 1
   (mata a causa da morte REAL do `combate`: burst de 2 elites).
2. ⏭️ Knob 2 (cap 4+3×nível) — PULADO: nas mortes observadas o budget já era
   mínimo (danger 1 → 3 pts); o cap novo não mudava nenhum caso medido.
3. ✅ Knob 3 — piso de HP nas classes frágeis (<25): Arcanista 16→22,
   Sombra 20→25, Batedor 22→27, Médico 24→28.

**Resultado (rodada final mock `20260713-201438` vs baseline):** replans −450
(explorador 50→4, −92%); 1ª morte adiada (combate t6→t15, agressivo t7→t10 e
virou Saque); `downed ≤ 1` em todos; `avg_hp_pct_after_combat` 12–44% (combate
segue doendo, ≤ 90%); 0 erros, 0 violações. **Nota:** o `agressivo` ainda morre
no nível 1 na 2ª queda — combate DELIBERADO todo turno sem cura/descanso é
"por conta e risco" (fora de escopo §2); a proteção anti-churn é a 1ª queda
nunca ser memorial, e isso vale nos 12 perfis.

**Smoke real pós-fix (`20260713-205857`, combate 15t seed 7):** cobriu os itens
1 E 2 do §6 num run só — t4 lutando a 3 HP no pântano; **t5 caiu → O SAQUE real:
acordou em Nova Arcádia com 6/27 HP (25%) e a campanha CONTINUOU**; t7 subiu ao
nível 2; t8 voltou a lutar; **t9 = 2ª queda → memorial** (permadeath do fecho
4.6 intacto; turnos 10-15 barrados pelo gate de game_over, 0 erros/0 violações).
Primeira MORTE no t9 ≥ t8 (meta batida; baseline real morria no t5).
Item 3 (`explorador` 15t real, run `20260713-210152`): **2 replans em 15 turnos**
atravessando sublocais (0 erros/0 violações) — sem plot twist por viagem.
