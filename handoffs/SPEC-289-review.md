# SPEC-289 — revisão (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (revisão independente) · **Data:** 2026-10-19 · **Commit revisado:** `ab812ea`

## Escopo

Branch `spec-289`, `git diff main...HEAD` (`da21995`, `ab812ea`): `world_utils.py`
(`_theme_stems`, `threat_faction`, `threat_sphere`, `threat_theme_match`,
`pick_encounter_enemy(theme=)`, ramo `looming_threat` de `check_encounter`, carimbo em
`resolve_faction_completions`), `state.py`, `tests/test_spec289_ameaca_tematica.py`, spec §6.
Fora: playtest 200t não reexecutado (evidência da spec aceita); suíte completa (coordenador).

Conferência R1–R7:

- R1: `world_utils.py:447` grava a fação só junto do texto; `threat_faction` resolve campo →
  texto nas vivas → seeds; ignora itens não-dict e `factions` como dict (sondado). OK.
- R2: esfera = região do alvo ∪ região de origem; probe: Corvane `{aethelgard}`, Chama Azul
  `{nova_arcadia}`. OK.
- R3/R4: porte estrito (`world_utils.py:859-863`) usa o `eff` de `forced_encounter_danger`;
  `is_boss` já filtrou o pool antes; ≥4 não cai em Minion temática (fallback regional). Sem
  migrantes quando temático (`:882`). No ponderado o peso é ×pontuação e `hunt_pressure` tem
  piso 0,1, então `weighted_pick` nunca devolve `None` no subconjunto temático. Probe dos
  radicais: dentro de `aethelgard` só casam Faísca/Afogado/Quimera/Cultista (todos coerentes);
  Afogado da Batalha e Cervo Afogado casam o radical mas estão no pântano, fora da esfera. OK.
- R5: fora da esfera a criatura é a regional e o flavor é emoldurado (`:1016-1017`). OK.
- R6: determinístico (sem RNG no caminho legado; `sorted` por id; conjuntos só para interseção);
  manifesto `systemic` testado. OK.
- R7: `theme=None` é byte-idêntico (o bloco não roda); texto sem dono → `tfac=None`, flavor cru,
  sorteio antigo. Local sem `region_id` → `pick` devolve `None`, hint genérico como antes. OK.
- Sem LLM, sem `with_structured_output` novo. `looming_threat_faction` não é exposto: a API
  usa allowlist (`api.py` `_world_block`/`services/map_view.py` só publicam `looming_threat`).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | world_utils.py:1006-1017 | Dentro da esfera mas sem temática no porte (ex.: Chama Azul em `na_anel_dourado` nível 5/9 → Golem de Lixo), o flavor continua o texto cru da ameaça ao lado de uma criatura sem relação — o descompasso original da SPEC-288 P2-3 persiste nesse caso. `pick_encounter_enemy` não informa se o resultado foi temático. | Follow-up: devolver/derivar o sinal "temático" (ex.: `theme(entry) > 0` no chamador) e, quando 0, emoldurar o flavor como eco ("a ameaça está perto; isto é fauna atraída por ela"). |
| P2-2 | P2 | world_utils.py:860-882 | Com um único candidato temático (porte Minion em `aethelgard` = só Faísca da Destilação), a pressão de caça da Fase 6.3 vira inócua: o peso 0,1 do candidato farmado é o único peso, e os migrantes estão desligados. O jogador encontra sempre a mesma criatura no ramo. Aceito pela spec (R4 "sem migrantes"), mas é efeito colateral no ecossistema. | Follow-up opcional: se o subconjunto temático tiver todos os pesos ≤ limiar de rareamento, cair no pool não-temático. |
| P2-3 | P2 | world_utils.py:1013 (hint) | Não-onisciência: o combatente da fação ("Iniciado da Chama Azul", "Cultista da Destilação") nomeia a fação no `hint` mesmo sem `intel[fid].known`. Precedente igual no ramo `controlled` (hint = nome da criatura também quando a fação é desconhecida) e o texto de Corvane já cita a Destilação, então não é regressão de política; para Malagor o texto não nomeia a fação. | Registrar; se o dono quiser rigor, aplicar a mesma regra de intel do ramo `controlled` ao flavor (o nome da criatura é canônico do bestiário e precisa ficar). |

Sem P0/P1.

## Correções aplicadas

Nenhuma exigida.

## Pendências

P2-1/P2-2/P2-3 como follow-ups (dono decide spec de destino; candidato natural: próxima spec de
encontros sistêmicos).

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -W ignore tests/test_spec289_ameaca_tematica.py tests/test_spec288_causa_morte.py tests/test_spec287_encounter_scale.py tests/test_fase2.py tests/test_fase63.py tests/test_encounter_manifest.py tests/test_encounter_astra_review.py tests/test_fase0.py → rc=0, todos passaram (219)
probe (scratchpad, PYTHONPATH=.) → radicais/esferas por fação, fações não-dict/dict, local inexistente, caminho ponderado com pressão de caça
```
