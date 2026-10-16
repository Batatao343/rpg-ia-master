# SPEC-232 evidência

## O que mudou
- **R1** `combat_mechanics.combat_modifiers` (condições + passivas estáticas) entra em `resolve_attack` (campo `modificador`),
  `compute_esquiva` (fichas salvas guardam só a base), dano (`conflict_turn`/`_basic_attack`), Proteção extra em
  `resolve_damage_and_wounds`, `advantage` por sinal e iniciativa (`_side_roll`). Buff/debuff tipado expira ao **fim** do
  turno do portador e só se já estava ativo no início dele (duração 1 aplicada no próprio turno vale para o próximo).
- **R2 (D-B default)** `learned_passives` real: Cartas `passiva` do Acervo e `virtude` (Estágio vivo da Virtude + Maestria)
  normalizadas; estáticas → damage/ac/initiative/dot/heal/protection/perception/vitality/social; tier 7/8 com custo viram
  passivas de gatilho (`on_attack` vantagem, `on_hit` dano/condição, `on_hit_taken` contra-ataque) pagas por
  `cards.use_passive` (frequência + Entropia). `vitality` entra em `sync_vitality`; `social` reduz o requisito de recrutamento.
- **R3** `_resolve_reaction_effect`: contra_ataque/dano rolam ataque do reagente; cura/buff/Proteção no reagente;
  condição/empurrão no atacante; reembolso de Entropia/uso se a oferta falhar. Gatilhos autorados fora do vocabulário
  (`ao_ser_alvo_distancia`, `ao_inimigo_engajar`, `ao_sofrer_dano_sobrenatural`, `ao_ser_flanqueado`,
  `ao_aliado_ser_atacado`, `aliado_cai`, `ao_aliado_perder_acao`, `apos_auto_dano`) ganharam semântica determinística;
  `aliado_atacado` (antes nunca casava por faltar `allies_of`) passou a funcionar.
- **R4** `tests/test_mecanica_orfa.py`: inventário de 102 chaves (card tipo×kind, condição nomeada, gatilho, classe,
  item, trait) × 104 testes de efeito observável. Condições nomeadas ganharam catálogo fechado `NAMED_CONDITIONS`
  (exposto, cego, enfraquecido, …). Lacunas aceitas só fora do combate: `trait.dc:comercio|insight|intimidacao`.
  `HANDLED_KINDS` mantido como registro legado (testes antigos o usam).
- **R5** alvo validado antes de cobrar (vivo, hostil/aliado conforme `sides`, mirável, não o próprio ator); nó de combate
  usa `_card_target_for`; **borda da API** `_apply_action_options` usa `_default_card_target` para Carta sem `target_id`
  (ex-SPEC-199 R12: cura não vai mais ao inimigo). Silenciado bloqueia Cartas; Marca dá Vantagem; purga remove a
  primeira condição **nociva**.
- **R6** Guarda expira em `reset_turn_budget`. **R7** `bypass_armor` (DoT, clima, caldeira). **R8** golpe corpo a corpo
  que acerta engaja os dois; Desengajar antes do movimento evita AoO. **R9** iniciativa early-game só na rodada 1;
  `_maybe_abyss` valida o EffectSpec antes de gastar; `_default_card_target` usa `_SUPPORT_EFFECTS` (inclui a Purga).
- **R10 (D-A default)** `prepare_encounter` (guard FallbackLLM existente + try) só com Carga ≥ leve ou inimigo
  Elite/Chefe/Nomeado; demais encontros seguem em `fallback_safe_scene` sem invoke. **Pós-smoke real (revisão Sol):**
  o 1º smoke caía SEMPRE no fallback (schema com dicts abertos + `ctx` cru no prompt → ~1,8k tokens fora do contrato,
  DeepSeek em timeout, cena sem `base_narrativa`). `PreparedScene` virou enxuto/tipado (zonas, objetos+interação do
  catálogo, ≤1 evento do Abismo, objetivos), truncagem e `gatilho` em Python, prompt compacto com ids válidos e teto
  `RPG_PREP_TIMEOUT_SECONDS` (12 s). Smoke real (3 chamadas, FAST): 3/3 cenas VÁLIDAS (não fallback) em 7,2 / 2,8 /
  2,9 s, cada uma com 3 zonas, 2 objetos e 1 evento do Abismo.

## Testes
- `tests/test_bug_combate_modificadores.py` (21) — todos vermelhos no HEAD 646f77e, verdes agora.
- `tests/test_mecanica_orfa.py` (106). Ajustes justificados: `test_balance_classes_v4_runtime.py` (alvo rendido deixou
  de ser alvo válido → boneco que passa o turno), `test_conflito16_frontend.py` (contra-ataque da reação consome RNG;
  desconta Entropia ganha pela classe).
- Suíte completa `pytest -q --ignore=tests/test_project_index.py`: exit 0. Ruff limpo nos arquivos tocados.
- Repro r4: `attack +20` → 200/200 acertos; `ac +20` → só Críticos por dupla (≤30/200; o ≤10 da spec é inatingível
  porque dupla sempre acerta — desvio registrado). r2: `entropy 10`, uso 0. DoT 1 vs Proteção 2: `10→9`.

## Playtest offline (MockLLM, seed 232, 40 turnos)
Colunas: run · perfil · classe · turnos · erros · violações · mortes · 1ª morte · quedas · %Vit pós-combate · turnos de combate · nível · %ativa · Entropia/turno.

Antes (HEAD 646f77e):
| 20261016-024002-010943 | combate | Devoto | 40 | 0 | 0/0 | 1 | 37 | 1 | 0.0 | 25 | 1 | 27.6 | 0.14 |
| 20261016-023911-623897 | combate | Sangromante | 40 | 0 | 0/0 | 0 | — | 0 | 33.3 | 18 | 2 | 45.0 | 0.30 |
| 20261016-023914-829656 | combate | Corruptor | 40 | 0 | 0/0 | 1 | 21 | 1 | 50.0 | 16 | 3 | 31.6 | 0.21 |
| 20261016-024005-116958 | combate | Arcanista | 40 | 0 | 0/0 | 1 | 36 | 1 | 61.9 | 23 | 2 | 37.0 | 0.11 |
| 20261016-024007-899744 | combate | Médico | 40 | 0 | 0/0 | 0 | — | 0 | 68.8 | 37 | 1 | 38.5 | 0.38 |
| 20261016-023920-580673 | explorador | Devoto | 40 | 0 | 0/0 | 0 | — | 0 | 0.0 | 5 | 3 | 0.0 | 0.0 |

Depois:
| 20261016-030004-390845 | combate | Devoto | 40 | 0 | 0/0 | 1 | 25 | 1 | 0.0 | 20 | 2 | 21.7 | 0.17 |
| 20261016-030008-072808 | combate | Sangromante | 40 | 0 | 0/0 | 1 | 26 | 1 | 0.0 | 36 | 1 | 42.1 | 0.32 |
| 20261016-030011-362922 | combate | Corruptor | 40 | 0 | 0/0 | 0 | — | 0 | 27.8 | 17 | 2 | 21.1 | 0.11 |
| 20261016-030015-021621 | combate | Arcanista | 40 | 0 | 0/0 | 1 | 23 | 1 | 64.3 | 22 | 2 | 18.5 | 0.07 |
| 20261016-030018-826354 | combate | Médico | 40 | 0 | 0/0 | 0 | — | 0 | 81.2 | 31 | 2 | 45.5 | 0.45 |
| 20261016-030022-909878 | explorador | Devoto | 40 | 0 | 0/0 | 2 | 28 | 2 | 0.0 | 7 | 3 | 0.0 | 0.0 |

Leitura: mortes 3→4 (combate ×5) e 0→2 (explorador); 1ª morte mais cedo em Devoto/Arcanista. Debuffs e a Reação
`bst_defesa_instintiva` (Proteção 1 + Desvantagem) agora contam — letalidade subiu. Essa Reação existe só nos inimigos
gerados pela LLM (`agents/bestiary.py::materialize_enemy_concept`, anterior a esta spec); nenhuma das 124 criaturas
curadas a tem. Toda Reação inimiga ofertada rende o `protected` genérico (Desvantagem no próximo ataque) **mais** o efeito
real da Carta — por design da R3 ("além de `protected`"); a confirmar no rebalanceamento da SPEC-049. Revide
(`contra_ataque`/`dano`) sem atacante vivo na cena não é cobrado (revisão Sol). Amostra de 1 seed:
é baseline, não decisão. Knobs `[BALANCEAR]` intactos; remedir `letalidade-early-game-v2`/SPEC-049 com este baseline.

## Limites / pendente
- Smoke §6 com LLM real não executado (proibido nesta onda); revisão independente Sol (REVIEW_REQUIRED) pendente.
- Equipamento v4: `combat_stats` (ac_bonus/attack_bonus/damage_dice) dos itens não alimenta o motor v2 — fora do
  escopo; candidato a spec própria. `broche_arauto` declara dano "Psíquico", que não é tipo v4 (passiva casa só por nome).

## Revisão e smoke real (2026-10-16, coordenador)

Revisão Sol independente: APPROVED_WITH_FOLLOWUPS — 21/21 testes falhavam em 646f77e; corrigidos reuso de `id()` em
condições, revide sem atacante não cobra, e o schema `PreparedScene` (antes caía sempre no fallback com LLM real após
~24 s). Smoke real (FAST/DeepSeek), `prepare_encounter` com Elite/Chefe: 3/3 cenas válidas (3 zonas, 2 objetos,
1 evento do Abismo), 2,8–7,2 s; teto dedicado `RPG_PREP_TIMEOUT_SECONDS`=12 s com fallback. Itens 1–3 da §6 são Python
puro, cobertos pelos testes listados na revisão. Letalidade sobe porque efeitos antes inertes passaram a valer —
novo baseline para SPEC-049/letalidade-early-game-v2.
