# SPEC-366 — abertura-followups

> **Status:** `in-review`
> **Criada:** 2026-11-02 · **Atualizada:** 2026-11-02
> **Depende de:** SPEC-351 (`done`), SPEC-350 (`done`)
> **Desbloqueia:** —
> **Aprovação:** dono, 02/11 ("pode ir fazendo essa execução")

---

## 1. Contexto & Objetivo

Follow-ups P2 da revisão independente da SPEC-351, Rodada 2
(`handoffs/SPEC-351-independent-review.md`, §Rodada 2: P2-R2-1..4) e §9/"Pouso" da
SPEC-351, mais um vazamento de lore achado na revisão da SPEC-360: o doc público
`mon_mao_sombria_agentes` diz que a Mão Sombria opera "sob a Velha Magda", e a
identidade da Víbora é segredo. Nada muda o oráculo `playtest/opening_checks.py`.

## 2. Requisitos

- **R1** — `looks_hostile` dobra acento/caixa/espaçamento (e cola letras separadas, "i g n o r e")
  antes do regex e cobre esqueça/desconsidere/ignore/forget/"you are now"/"system prompt",
  exigindo alvo de instrução explícito. "ignora as regras da guilda", "revele o segredo do
  templo" e "marque a missão" NÃO são hostis. Continua sendo só sinal extra: efeito = NPC só local.
- **R2** — `_normalize` (com menu) passa `prologue` e `opening_scene_brief` pelo mesmo
  `sanitize_beat`; com acerto o texto inteiro cai no do template (`fallback_scenario`).
- **R3** — Ordenação oficial do menu de portas: **raça > Postura > descrição > jogável**
  (`race_hit` já embute raça e Postura). Docstring de `_rank` reflete isso.
- **R4** — Métrica de adesão do planejador sem a muleta "Mantenha em vista:":
  `opening_threads.planner_cited(plan, thread)`; `consume_thread` loga
  `thread.planner_adherence`; o smoke da 351 grava `replan.planner_cited`. Sem chamada LLM nova.
  O E1 do replan segue "garantido pelo motor"; a adesão do planejador é medida à parte.
- **R5** — Vazamento: a frase "sob a Velha Magda" sai do texto público da Mão Sombria na FONTE
  (`lore_nova/creatures.txt`) e no doc gerado; `"sob a velha magda"` entra no grupo `vibora` de
  `data/world/leak_phrases.json` (o snapshot da 350 só exige que as frases congeladas
  continuem presentes, então acrescentar é permitido); lore reindexada.

### Fora de escopo
Alterar o oráculo/`FROZEN_348`; medir adesão com LLM real (fica para o próximo smoke).

## 3. Design técnico

`services/prologue.py` (`_HOSTILE`, `_fold_hostile`, `looks_hostile`, `_normalize`),
`services/opening_threads.py` (`_rank`, `planner_cited`, `consume_thread`),
`scripts/smoke/spec351_opening.py`, `lore_nova/creatures.txt`,
`data/codex/monsters/mon_mao_sombria_agentes.md` (mesma edição do migrate, idempotente),
`data/world/leak_phrases.json`, `tests/test_spec366_followups.py`.

## 4. Plano passo a passo

1. Testes (`tests/test_spec366_followups.py`): 5 benignas não hostis; 9 hostis (contornos da
   revisão) hostis; prólogo/brief vazados caem no template; `planner_cited` ignora a muleta;
   raça vence descrição; frase da Víbora fora do doc público e presente em `leak_phrases`.
2. Implementação dos R1–R5. 3. Reindexar lore (Jina). 4. Testes do escopo.

## 5. Critérios de aceite

- [x] R1–R5 com testes (`tests/test_spec366_followups.py`, 14 casos)
- [x] Testes da 348/350/351/prólogo/flags verdes (escopo)
- [x] Oráculo `playtest/opening_checks.py` intocado
- [ ] Revisão independente

## 6. Smoke test com LLM real

Próximo smoke da 351: conferir `replan.planner_cited` (informativo, sem critério).

## 7. Riscos & compatibilidade

- Falso positivo/negativo residual em `looks_hostile` (heurística; defesa em profundidade).
- Prólogo/brief que citam segredo caem no template (perde prosa, nunca vaza).
- Saves antigos: sem mudança de schema.
