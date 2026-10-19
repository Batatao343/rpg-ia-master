# SPEC-290 — Sobrevivência do Chefe: LLM e laboratório

> **Status:** `approved` (autorização do dono de 19/10 para tudo que não exige ação externa dele)
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Origem:** follow-up P2-2 da revisão da SPEC-287 (`handoffs/SPEC-287-review.md`, `docs/spec287/README.md`)
> **Depende de:** SPEC-287 (`done`) · **Paralela a:** SPEC-289 (não toca `world_utils.check_encounter`/`pick_encounter_enemy`)
> **EXECUTOR_MODEL:** `Sonnet` · **REVIEW_REQUIRED:** `false` (ajuste pequeno, Python determinístico)

---

## 1. Contexto & Objetivo

A SPEC-287 deu a Chefe/Nomeado um bônus de Vitalidade por Nível do Encontro
(`agents/bestiary.apply_encounter_survival`, campo `vitalidade_por_nivel_encontro`
gravado só pelo gerador `scripts/migrate_bestiary_v4.py`). O bônus não vale para
(a) Chefes gerados pelo LLM (`generate_new_enemy`, overlay runtime de bestiário),
que nunca recebem o campo, e (b) o laboratório de combate (SPEC-090), que copia a
ficha do `gamedata.BESTIARY` sem aplicar o bônus — o que enviesa as medições.

## 2. Requisitos

- **R1** — `apply_encounter_survival` trata Chefe/Nomeado (por `normalize_categoria`)
  sem o campo como se tivesse o valor canônico 12 (`SOBREVIVENCIA_POR_NIVEL_ENCONTRO`),
  de forma determinística. Campo presente vence o default. Outras categorias: sem bônus.
- **R2** — `materialize_enemy_concept` de categoria `chefe` grava o campo (12), e
  `generate_new_enemy` (geração nova, fallback e overlay legado) aplica o bônus do
  Nível do Encontro na ficha devolvida. O overlay salvo guarda a base (sem bônus),
  para não acumular entre encontros.
- **R3** — O laboratório (`api._build_combat_simulator_state`) aplica o mesmo bônus a
  cada inimigo pelo Nível do Encontro da arena (`compute_encounter_level` do
  `danger_level` da categoria).
- **R4** — Saves/overlays antigos sem o campo carregam; nada em Python depende do campo existir.

### Fora de escopo
`world_utils.check_encounter`/`pick_encounter_enemy` (SPEC-289); valores do bônus.

## 3. Design técnico

- `agents/bestiary.py`: constante `DEFAULT_SURVIVAL_PER_LEVEL = {"chefe": 12, "nomeado": 12}`
  (espelha o gerador; teste de paridade); `apply_encounter_survival` com default por
  categoria; `materialize_enemy_concept` grava o campo para chefe; `generate_new_enemy`
  aplica o bônus em cópia após `save_enemy`.
- `api.py`: laboratório chama `apply_encounter_survival(enemy, encounter_level)` antes
  de `vitalidade = max_vitalidade`.

## 4. Plano

1. Testes em `tests/test_spec290_chefe_sobrevivencia.py`: default sem campo; campo
   presente vence; não-chefe sem bônus; LLM novo/fallback chefe escala; overlay salvo é
   base; laboratório Chefe nível alto tem mais Vitalidade que o template, Lacaio igual.
2. Implementação conforme §3.
3. Escopo + suíte completa.

## 5. Critérios de aceite

- [x] R1–R4 cobertos por testes
- [x] Suíte completa verde (exceto índice stale esperado)
- [x] Guard de FallbackLLM inalterado (nenhum `with_structured_output` novo)
- [x] Saves antigos carregam

## 6. Smoke com LLM real
Não aplicável: mecânica Python determinística, sem novo structured output.

## 7. Riscos
Chefe LLM fica mais resistente no nível 3+ (intencional, igual aos curados). Laboratório
passa a refletir o jogo real.
