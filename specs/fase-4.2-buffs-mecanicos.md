# SPEC — Fase 4.2: Buffs, passivas e condições mecânicas de verdade

> **Status:** `in-progress` — **Etapas 1–5 implementadas** (2026-07-04, 382 testes
> verdes); falta SÓ o smoke com LLM real (§6) para `done`.
> **Criada:** 2026-07-03 · **Atualizada:** 2026-07-03
> **Depende de:** Fase 4.1 (schema `effects` tipado nas habilidades; árvores da 4.1b o preenchem)
> **Desbloqueia:** Fase 4.5 (aliados usam o mesmo motor de condições), 4.6 (habilidades de inimigos com efeitos)

---

## 1. Contexto & Objetivo

O motor de condições existe e funciona para DoT: `combat_mechanics.py` tem
`apply_condition`/`tick_conditions` com schema `{name, dot, duration, source}`
(combat_mechanics.py:12). Mas **modificadores nunca são lidos**: "Juramento de
Sangue: +5 Dano por 3 turnos" vira uma condição com `dot=0` que só ocupa espaço —
`resolve_damage_formula` e `compute_player_combat_stats` ignoram `active_conditions`
por completo. Buff é texto. Passiva de classe idem: "Muralha Humana: +2 de Defesa"
é string decorativa em `classes.json`.

Esta spec faz os números lerem as condições: buff/debuff de dano/AC/acerto/save,
condições de controle (atordoado, enredado, medo) e passivas data-driven — para
player E inimigos (simetria). A Fase 4.1 definiu o formato `effects` tipado nas
habilidades; aqui ele ganha motor.

Princípio: mecânica é Python. Zero structured output novo.

## 2. Requisitos

- **R1** — Schema `Condition` (state.py) estendido: além de `{name, dot, duration,
  source}`, campos opcionais `stat` (`"damage"|"ac"|"attack"|"save"`), `delta` (int)
  e `control` (`"stun"|"root"|"fear"|None`). Retrocompatível: condição antiga
  (só dot) continua válida.
- **R2** — Nova função `condition_modifiers(entity) -> {"damage": int, "ac": int,
  "attack": int, "save": int}` soma os deltas das condições ativas. Consumida em:
  dano do player (`resolve_player_action`), AC efetiva (player e inimigo), rolagem
  de ataque (player e inimigo), DC/save. **"+5 Dano por 3 turnos" passa a dar +5.**
- **R3** — Habilidade com `effects` (4.1) aplica condições tipadas ao usar:
  `kind=buff/debuff` → condição com `stat`/`delta`; `kind=dot` → DoT (caminho atual);
  `kind=control` → condição de controle; `kind=heal` → cura (caminho atual).
  O parser legado de strings (`parse_condition_string`) continua como fallback para
  as `conditions` textuais antigas.
- **R4** — Condições de controle com efeito real, simétrico (player e inimigo):
  - `stun` — perde o turno (pula ação na ordem de iniciativa; tick ainda roda)
  - `root` — não pode fugir (tentativa de fuga falha com log claro)
  - `fear` — `-2` em rolagens de ataque enquanto durar
- **R5** — Passivas de classe viram efeito data-driven: `classes.json` ganha
  `passive_effects` tipado por classe (ver §3). As 10 passivas atuais são mapeadas;
  as que dependem de contexto que o motor não rastreia ainda (ex.: "aliados
  adjacentes" antes da Fase 4.5) ganham a aproximação declarada na tabela do §3 —
  nenhuma permanece 100% decorativa.
- **R6** — Simetria: inimigo também recebe buff/debuff/controle (habilidades do
  player que debuffam inimigo funcionam; base para 4.6 dar habilidades a inimigos).
- **R7** — Saves antigos carregam (condições sem os campos novos = default
  `stat=None, delta=0, control=None`).
- **R8** — Log mecânico continua alimentando o narrador: cada modificador aplicado
  gera linha de log curta ("+5 dano de Juramento de Sangue"), narração fica honesta
  com os números.

### Fora de escopo

- Habilidades de inimigos como ações mecânicas (Fase 4.6 — aqui inimigos só
  RECEBEM condições).
- Buffs fora de combate (poção de buff antes da luta — Fase 4.3 cobre uso de item).
- Auras de party/adjacência real (Fase 4.5; aqui aproximação declarada).
- Rebalancear valores das habilidades (números vêm da 4.1b como estão).

## 3. Design técnico

### Arquivos alterados (sem arquivo novo — motor já existe)

| Arquivo | Mudança |
|---|---|
| `state.py` | `Condition` ganha `stat`/`delta`/`control` opcionais (docstring) |
| `combat_mechanics.py` | `condition_modifiers()`; leitura nos pontos de dano/AC/ataque/save; `stun`/`root`/`fear` na resolução de turno; aplicação de `effects` tipado em `resolve_player_action`; passivas em `compute_player_combat_stats`/dano |
| `data/classes.json` | `passive_effects` por classe (tabela abaixo) |
| `data/player_abilities.json` | nada estrutural (a 4.1b já preencheu `effects`) |
| `agents/combat.py` | fuga checa `root`; ordem de iniciativa pula `stun`; logs novos passam ao narrador |

### `condition_modifiers` (assinatura)

```python
def condition_modifiers(entity: Dict) -> Dict[str, int]:
    """Soma delta das active_conditions por stat. Ex.: {"damage": 5, "ac": 0,
    "attack": -2, "save": 0}. fear embute -2 em attack."""

def has_control(entity: Dict, kind: str) -> bool:
    """True se condição ativa com control == kind ("stun"/"root"/"fear")."""
```

Pontos de integração (todos existentes):

- `resolve_player_action` — dano final += `condition_modifiers(player)["damage"]`;
  rolagem de ataque += `["attack"]`; AC do inimigo alvo += `condition_modifiers(enemy)["ac"]`
- `compute_player_combat_stats` — `ac` += `condition_modifiers(player)["ac"]` + passiva
- `resolve_enemy_turn` — espelho: dano/ataque do inimigo modificados; AC do player idem
- loop de rounds em `agents/combat.py` — antes da ação de cada combatente:
  `has_control(x, "stun")` → log "atordoado, perde o turno", pula
- fluxo de fuga — `has_control(player, "root")` → fuga negada

### `passive_effects` — mapeamento das 10 passivas

Formato:

```json
"passive_effects": [
  {"trigger": "always" | "hp_below_25" | "melee_attacked" | "damage_type",
   "stat": "ac" | "damage" | "attack" | null,
   "delta": 2,
   "damage_type": "Fogo",        // só p/ trigger=damage_type
   "retaliate": "1d4 veneno",    // só p/ melee_attacked
   "note": "aproximação declarada, se houver"}
]
```

| Classe | Passiva atual (texto) | Efeito mecânico 4.2 |
|---|---|---|
| Cavaleiro da Vigília | Muralha Humana: +2 Defesa c/ aliados adjacentes | `always: ac+2` (nota: vira condicional a party na 4.5) |
| Batedor das Fronteiras | Oportunista: +1d6 vs distraídos | `always: damage+2` (média aproximada; vira condicional real na 4.6 c/ estados de inimigo) |
| Arcanista Cinzento | Iniciativa por INT | `roll_initiative` usa max(dex,int) p/ a classe |
| Sangromante | 2 HP = 1 Mana | `spend_resources`: sem mana → paga 2×custo em HP (implementar de verdade) |
| Inquisidor da Cinza | Imune a Medo; +2 dano de fogo | `condition_resists: ["medo"]` (motor 2.5b já existe!) + `damage_type Fogo: damage+2` |
| Pastor de Pragas | Retaliação 1d4 veneno melee | `melee_attacked: retaliate 1d4` |
| Sombra da Corte | Armas aplicam veneno fraco | `always`: ataque básico anexa DoT 1/2 turnos |
| Sapador da Fuligem | Dano dobrado vs estruturas | fica declarativo (motor não tem estruturas) — nota explícita, único caso |
| Médico de Campo | Cura +5 se alvo < 25% HP | `_heal`: bônus se `hp/max_hp < 0.25` |
| Guardião Selvagem | (conferir no JSON na implementação) | mapear na mesma passada |

`condition_resists` racial (2.5b) já resolve imunidades — reusar, não duplicar.

## 4. Plano passo a passo

### Etapa 1 — `condition_modifiers` + integração de dano/AC/ataque (TDD)

1. **Testes** (`tests/test_fase42.py`): `test_condition_modifiers_soma`;
   `test_buff_dano_aplica` (Juramento de Sangue: dano observável +5);
   `test_debuff_ac_no_inimigo`; `test_condicao_legada_so_dot_segue_ok`;
   `test_save_antigo_sem_campos_novos_carrega`.
2. **Implementação:** `condition_modifiers`, integração nos 4 pontos.

### Etapa 2 — `effects` tipado → condição

1. **Testes:** `test_effects_buff_vira_condicao`; `test_effects_control_vira_condicao`;
   `test_fallback_parser_string_legado`.
2. **Implementação:** em `resolve_player_action`, `effects` da habilidade têm
   precedência sobre o parse textual de `conditions`.

### Etapa 3 — Controle (stun/root/fear)

1. **Testes:** `test_stun_pula_turno` (inimigo atordoado não age no round);
   `test_stun_simetrico_player`; `test_root_bloqueia_fuga`; `test_fear_penaliza_acerto`;
   `test_resist_racial_anula_controle` (motor 2.5b).
2. **Implementação:** `has_control` + hooks no loop de rounds e fuga.

### Etapa 4 — Passivas data-driven

1. **Testes:** um por classe mapeada (ex.: `test_muralha_humana_ac`;
   `test_sangromante_hp_por_mana`; `test_inquisidor_imune_medo`;
   `test_medico_cura_bonus_25`; `test_arcanista_iniciativa_int`;
   `test_pastor_retaliacao`); `test_passive_effects_schema` (validador).
2. **Implementação:** `passive_effects` no JSON + leitura no motor.
3. **Atenção:** passiva do Sangromante muda `spend_resources` — conferir cooldowns.

### Etapa 5 — Narração honesta

1. **Testes:** `test_logs_incluem_modificadores` (log contém a linha do buff).
2. **Implementação:** logs novos; conferir que `_narrate` os recebe.
3. **Verificação:** `uv run pytest` completo verde.

## 5. Critérios de aceite

- [ ] "+5 Dano por 3 turnos" muda o número de dano observável (assert no teste)
- [ ] Atordoado perde turno; enredado não foge; medo dá -2 de acerto — player E inimigo
- [ ] 9/10 passivas com efeito mecânico real (Sapador = única declarativa, documentada)
- [ ] Condições antigas (só DoT) e saves antigos seguem funcionando
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Zero structured output novo (guard N/A)
- [ ] `ESTADO_ATUAL.md` + `ROADMAP.md` atualizados

## 6. Smoke test com LLM real

1. Combate real: usar habilidade de buff (ex.: Juramento de Sangue) → turno seguinte,
   conferir dano maior no log E narração mencionando o buff.
2. Habilidade de controle em inimigo → inimigo perde o turno, narração coerente.
3. Classe Sangromante sem mana → conjurar pagando HP (passiva) — narração + números.

(3 requests; flash + pro.)

## 7. Riscos & compatibilidade

- **Saves antigos:** campos novos opcionais com default — sem migração de dados.
- **MockLLM:** condições vêm do motor, não do LLM — teste offline cobre tudo;
  risco de mapeamento LLM zero (nenhum schema novo).
- **Balanceamento:** stun em cadeia pode travar inimigo/player — mitigação simples:
  aplicar `stun` refresca (não acumula) e `apply_condition` já refresca duração;
  observar no playtest.
- **Passiva aproximada** (Batedor +2 flat): documentada no JSON via `note`; revisar
  quando 4.6 der estados aos inimigos.
