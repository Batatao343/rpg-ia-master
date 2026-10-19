# SPEC-275 — Impasse eterno no conflito: inimigo oculto "ataca" com Carta de suporte recusada

> **Status:** `done` (revisão Astra APPROVED 2026-10-19 com 4 correções — [handoff](../handoffs/SPEC-275-ASTRA-review.md))
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** revisão SPEC-272 2026-10-18 (achado: `combat.no_progress` em `playtest run --profile combate --turns 200`, offline)
> **Depende de:** —
> **Desbloqueia:** playtest `combate` 200 turnos estável como gate de regressão do motor de conflito
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Astra` (≡ Opus) · **REVIEW_REQUIRED:** `true` — toca a IA tática do motor de conflito
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Na revisão da SPEC-272 o perfil `combate` (MockLLM, 200 turnos) travou um conflito
por ~130 rodadas com `combat.no_progress` (133 violações `error`) e o mesmo comando
"com cache quente" deu 0/0. O diagnóstico desta spec mostra que **o cache de runtime
não é a causa**: o bug é intermitente em qualquer checkout. No mesmo worktree limpo,
três execuções seguidas sem `.env` deram 138/0/0 violações, e `PYTHONHASHSEED` fixo
também não estabiliza (hs=0 deu 0 e 0; hs=1 deu 0 e 133; hs=4 deu 153). A
variação vem de o harness gerar `game_id = uuid4()` por campanha
([playtest/runner.py:354](../playtest/runner.py)), e vários sub-RNGs do jogo
derivam do `game_id` (ids de conflito/encontro, traits de NPC por sha256 —
[services/npc_layers.py:47](../services/npc_layers.py)). `--seed` sozinho não reproduz
a campanha.

**Causa raiz (produto).** Repro no save travado (`Viúva do Lodo` emboscadora +
`Mosquito de Éter` covarde, jogador Devoto nível 4 com Vitalidade 4/18, round 143,
os dois inimigos `ocultacao: escondido` e `hidden_from: ["player"]`):

1. Os dois inimigos estão ocultos para o jogador, então
   `derive_tactical_scene_state` calcula `has_flank=True` → `sem_flanco=False` /
   `descoberto=False` ([services/conflict_orchestrator.py:384-407](../services/conflict_orchestrator.py)).
   A Viúva cai na prioridade `sempre → attack` e o Mosquito em
   `sempre → flank`. Como `sem_flanco=False`, o flank vira `attack`
   (`conflict_orchestrator.py:460`).
2. Para `attack`, `enemy_declaration` chama `_enemy_offensive_card`
   (`conflict_orchestrator.py:504`), que devolve a **primeira Carta usável de
   qualquer efeito**, apesar do nome. O filtro descarta só `esconder` quando o
   ator já está escondido (`:510-526`). As Cartas ofensivas reais (`bst_golpe_sombras`
   dano e `bst_lodo_melancolia` dot) já foram gastas no encontro: frequência por
   conflito em `cards.can_use_enemy_card`, [services/cards.py:394-397](../services/cards.py).
   A função então devolve uma Carta de **suporte**: `bst_carregar_ruina`
   (`reposicionar`) para a Viúva e `bst_coro_colmeia` (`buff_acerto`) para o
   Mosquito. As duas saem com `target_id` = o jogador.
3. `_resolve_attack_step` classifica a Carta como suporte (`_SUPPORT_EFFECTS`,
   [services/conflict_turn.py:159-163](../services/conflict_turn.py)), e
   `_invalid_target_reason` recusa com "Playtest-combate é hostil — Carta de suporte
   recusada." (`conflict_turn.py:236-237`). Pela SPEC-232 R5 a recusa acontece
   **antes de cobrar** (`conflict_turn.py:308-314`), então Entropia e frequência ficam
   intactas e a mesma Carta continua "usável" na rodada seguinte. Resultado: **o
   inimigo nunca age**, em loop determinístico. A Carta de assinatura da emboscadora
   ("Ataca da ocultação… e some") nunca vira ataque.
4. O jogador também fica sem saída mecânica:
   - "Ataco X" é recusado com "X sem posição conhecida — não pode mirar direto."
     (`conflict_turn.py:247-249`), também antes do custo.
   - "Procurar" revela a Viúva, mas ela volta a se esconder na mesma rodada, porque
     `descoberto → flank` vira manobra de flanco que reaplica ocultação
     ("mon_viuva_lodo_1 se esconde (flanco tático)" no replay). O Mosquito continua
     oculto.
   - Só a **fuga** encerra o conflito.

   Ninguém causa nem sofre dano, e o conflito não termina sozinho.

**Produto ou harness?** É **bug de produto**. Um jogador real nessa cena fica preso
num conflito inerte: os inimigos nunca atacam, o ataque dele é recusado e a busca é
desfeita. A única saída é fugir, e nada na UI sugere isso. O harness **amplifica e
esconde** o bug de três formas:
- o perfil `combate` não reage a alvo oculto (não procura nem foge após impasse);
- `--seed` não reproduz a campanha, porque o `game_id` é aleatório;
- a afirmação "cache quente = 0/0" foi coincidência de amostragem.

Evidência de execução está em §8.

## 2. Requisitos

- **R1 — Carta "ofensiva" do inimigo é ofensiva.** `_enemy_offensive_card` só pode
  devolver Carta cujo `efeito.kind ∈ _ATTACK_EFFECTS`
  ([services/conflict_turn.py:156](../services/conflict_turn.py)). Sem Carta
  ofensiva usável, a declaração é `attack` básico (sem Carta) no mesmo alvo.
- **R2 — Carta de suporte do inimigo mira o próprio lado.** Se a IA tática escolher
  uma Carta de suporte (fluxo `support`, ou uma escolha futura), o `target_id` é o
  próprio ator ou um aliado vivo, nunca um ator do lado oposto.
- **R3 — Recusa de alvo de inimigo não é no-op silencioso.** Se a declaração de um
  inimigo for recusada por `_invalid_target_reason`, o turno dele cai em **um**
  fallback válido e determinístico na mesma rodada: ataque básico no alvo, ou
  `pass` quando nem isso é válido. O fallback é registrado em log/telemetria
  (`enemy_declaration_fallback`). Sem recursão nem segunda recusa.
- **R4 — Emboscador ataca da ocultação.** Inimigo oculto do alvo e com o alvo
  visível consegue resolver ataque básico (ou Carta ofensiva) contra ele. A regra de
  revelar ao atacar segue o que já existe em `conflict_scene`. Cobre "Ataca da
  ocultação o alvo desprevenido e some".
- **R5 — Guarda anti-impasse no motor (decisão do dono, ver §7).** Depois de
  `K = 6` rodadas consecutivas sem mudança mecânica no conflito (a mesma noção do
  `combat_progress_fingerprint` do harness, mas calculada em produção sobre
  Vitalidade/status/Ferimentos/condições/posições), o motor quebra o impasse de
  forma determinística: inimigos com perfil `covarde_*` fogem e os demais perdem a
  ocultação para o jogador. A quebra gera evento `conflict_stalemate_broken`.
- **R6 — Harness reproduzível por seed.** `playtest run --seed S` usa `game_id`
  derivado do seed (`uuid5(NAMESPACE, f"{profile}:{seed}:{index}")`). Duas execuções
  com o mesmo perfil, seed e turnos produzem JSONL idêntico, ignorando
  latência/timestamps.
- **R7 — Perfil `combate` lida com alvo oculto.** Quando todos os inimigos ativos
  estão `hidden_from` o jogador, o perfil declara `maneuver=procurar`. Com streak de
  no-progress ≥ 3, ele tenta fuga. O objetivo é exercitar o caminho, não mascarar R1–R5:
  o aceite de R1/R3 é medido com o perfil **sem** essa mudança (§5).

### Fora de escopo

- Rebalancear frequência, custo e Entropia das Cartas de inimigo (SPEC-049 / letalidade).
- Mudar a regra SPEC-232 R5 (validar alvo antes de cobrar) para o **jogador**. Ela
  continua valendo.
- UI de "valid_targets" para alvo oculto (SPEC-205). Se precisar, vira spec própria.
- Ligar Jev ou qualquer LLM em combate. Toda a mecânica continua Python.

## 3. Design técnico

- **`services/conflict_orchestrator.py`**
  - `_enemy_offensive_card`: adicionar filtro `effect_kind in ct._ATTACK_EFFECTS`.
    Manter a exclusão de `esconder` (Mimetismo Morto, matriz A), que fica redundante
    mas é inofensiva.
  - `enemy_declaration`: Carta de suporte só com alvo do próprio lado (R2).
  - Novo `_stalemate_guard(scene, combat_meta, actors_by_id, sides) -> list[str]`
    (R5), chamado por `run_round` antes de montar as declarações. Contador em
    `combat["stalemate_rounds"]`, que reseta quando o fingerprint muda.
- **`services/conflict_turn.py`**
  - Em `_resolve_attack_step`, no ramo `if reason:` (`:311-314`): se o ator **não** é
    o jogador, reescrever o step para ataque básico no mesmo alvo e revalidar
    **uma vez**. Se a nova declaração também for recusada, registrar `pass`.
    O jogador mantém o comportamento atual (recusa sem custo, SPEC-232 R5 / SPEC-205
    409 `invalid_target`).
- **`playtest/runner.py`**: `game_id = str(uuid.uuid5(_PLAYTEST_NS, f"{profile}:{seed}:{idx}"))`
  quando `--seed` for passado. O default sem seed continua aleatório.
- **`playtest/profiles.py`** (`combate`, e `agressivo` se compartilhar a lógica):
  ler `combat.scene.positions[*].hidden_from` → `procurar`. Usar o streak do
  contexto → fuga (R7).
- **Schema:** só o campo aditivo `combat.stalemate_rounds: int` (default 0), sem bump
  de `SCHEMA_VERSION`. Saves antigos carregam com default.

## 4. Plano passo a passo

### Etapa 1 — Reprodução congelada (testes primeiro)
1. **Fixture** `tests/fixtures/combat_stalemate_hidden_support.json`, um estado
   mínimo derivado do save do §8:
   - Viúva do Lodo e Mosquito de Éter `escondido`, com `hidden_from:["player"]`;
   - `enemy_card_usage` com as Cartas ofensivas já gastas;
   - jogador Vitalidade 4/18.
2. `tests/test_spec275_stalemate.py`:
   - `test_enemy_offensive_card_never_support`: com só `reposicionar`/`buff_acerto`
     usáveis, `_enemy_offensive_card` devolve `None` e `enemy_declaration` devolve
     `attack` sem `card_id`.
   - `test_enemy_refused_declaration_falls_back_once`: uma Carta de suporte injetada
     contra o jogador resolve como ataque básico (ou `pass` logado), sem recursão.
   - `test_hidden_ambusher_attacks_visible_player`: em ≤ 3 rodadas da fixture, o
     jogador recebe pelo menos uma rolagem de ataque (`out["attacks"]` não vazio).
   - `test_stalemate_guard_breaks_after_k_rounds` (R5): com ataques forçados a errar
     ou recusados, na rodada K+1 o encontro deixa de ser idêntico (fuga do covarde
     ou revelação).
   - `test_player_refusal_still_free` (regressão SPEC-232 R5): ataque do jogador em
     alvo oculto continua recusado sem custo.
3. `tests/test_playtest_harness.py::test_seed_reproduces_campaign` (R6): duas
   campanhas `combate` de 30 turnos com o mesmo seed dão `game_id` e sequência de
   `resolved_action`/`player_vitality` idênticos.

### Etapa 2 — Correção do motor (R1–R4)
Implementar §3 em `conflict_orchestrator.py`/`conflict_turn.py` e rodar a Etapa 1.

### Etapa 3 — Guarda anti-impasse (R5), se aprovada pelo dono

### Etapa 4 — Harness (R6, R7)

### Verificação
`uv run pytest` verde. Depois o laço de aceite do §5.

## 5. Critérios de aceite

- [x] Testes da Etapa 1 escritos antes do código e verdes depois.
- [x] **Sem mudar o perfil** (só R1–R4): 10 execuções consecutivas de
      `uv run --frozen python -m playtest run --profile combate --turns 200` em
      checkout limpo (sem `saves_playtest/`, sem `data/runtime/`) dão **0**
      `combat.no_progress`.
- [x] Com R6: `--seed 0` repetido 3× produz o mesmo `summary.json`, ignorando
      latência e timestamps.
- [x] `--all --turns 50` sem novas violações `error` em relação à main.
- [x] Nenhum teste de combate existente regride. Em especial: SPEC-232 R5 (recusa sem
      custo do jogador), Mimetismo Morto (`esconder` repetido), SPEC-203 (manifesto)
      e SPEC-205 (`valid_targets`).
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Saves antigos com conflito ativo continuam carregando (`stalemate_rounds` ausente = 0).

## 6. Smoke test com LLM real

O motor é Python puro, então o LLM só narra.
1. Carregar a fixture num jogo real via `/game/action` e mandar "Ataco a Viúva do
   Lodo." três vezes. A narração deve descrever ataques/dano reais, sem rodada inerte.
2. Mandar "Procuro os inimigos escondidos." e confirmar que o conflito progride.

## 7. Riscos & compatibilidade

- **Letalidade:** inimigos que antes ficavam inertes passam a atacar, então a
  dificuldade efetiva sobe (como na SPEC-232). Medir no playtest `--all` e, se
  preciso, levar para SPEC-049.
- **R5 é decisão de design.** A alternativa é só R1–R4 mais o fim do conflito por
  fuga. **Decisão do dono (2026-10-18): "Corrige com R5"** — R5 implementado com o default da spec (covarde foge; demais revelam e atacam; K=6 rodadas sem dano; contador em `scene["stalemate"]`, não em `combat`, pois `run_round` só recebe a cena). R7 não implementado (opcional). R1–R4 já resolvem o impasse observado.
- **Harness:** com o `game_id` determinístico (R6), duas campanhas com o mesmo seed
  na mesma run colidem no save, então o índice da campanha entra no `uuid5`.
- **MockLLM / FallbackLLM:** nenhum caminho novo de structured output.

## 8. Evidência do diagnóstico (2026-10-18)

Worktree limpo `no-progress` sobre `757665f`, MockLLM, sem `data/runtime/`:

| execução | violações err/warn |
|---|---|
| cold, sem `.env` | 0/0 |
| warm (2ª execução) | 0/0 |
| cold, `.env` completo | 76/0 |
| cold, só `JEVMODEL_API_KEY` | 124/0 → repetido: 0/0, 0/0 |
| cold, sem `.env`, 3× | 138 / 0 / 0 |
| `PYTHONHASHSEED` 0,1,2,3,4,5,0,1 | 0,0,0,0,153,0,0,133 |

A variação não depende do cache nem do `.env`. É o `game_id` aleatório.

Run `20261018-192452-296716` (133 erros): conflito iniciado no turno 58
(`origin: regional_danger`, Viúva do Lodo + Mosquito de Éter via `budget_fill`). O
Mosquito usou `bst_fuga_suja` (esconder) e a Viúva fez flanco. Do turno 63 ao
turno 200, Vitalidade do jogador 4, inimigos 12/12 e 10/10, `combat.round` chegou a
143, e o conflito continuou ativo no fim da campanha.

Replay de uma rodada do save final via `combat_node` (instrumentando `run_round`):
```
logs: ['mon_mosquito_eter_2 sem posição conhecida — não pode mirar direto.',
       'Playtest-combate é hostil — Carta de suporte recusada.',
       'Playtest-combate é hostil — Carta de suporte recusada.']
attacks: []
```
Cartas usáveis no impasse:
- Viúva: `bst_carregar_ruina` (reposicionar ✔), `bst_golpe_sombras`/`bst_lodo_melancolia` ✘ (já gastas).
- Mosquito: `bst_fuga_suja` (esconder, pulada por já estar oculto), `bst_coro_colmeia` (buff_acerto ✔).

Com `procurar`, o jogador encontra a Viúva, e ela se esconde de novo na mesma rodada
quando age depois dele.
