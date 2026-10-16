# SPEC-203 — Revisão independente Astra (2026-10-16)

**Veredito:** APPROVED com correções (aplicadas antes do merge em `30f1a80`).

## Achados corrigidos
1. **R6 sequestrava a intenção (médio).** No 1º turno após o desfecho, o router mandava toda mensagem não hostil
   para STORY antes do CLASSIFY, impedindo NPC/LOOT ("pergunto ao bandido rendido", "saqueio"). Agora o CLASSIFY
   roda e só COMBAT sem hostilidade explícita é rebaixado a STORY; `explore_resumed` marcado via `_resumed()`.
2. **`species_drift` apagava prosa legítima (médio).** Termos comuns de prosa de combate (fumaça, faísca, vigia,
   sentinela, saqueador…) estavam entre as "cabeças" de espécie; foram para `_NON_SPECIES_HEADS`
   (`services/prose_guard.py`). A troca real de espécie (bandido→lobo) continua detectada.

Teste: `tests/test_encounter_astra_review.py` (4 casos).

## Verificado sem defeito
Espécie/elenco estáveis por rodadas e reloads (`assert_immutable` + `validate_roster`); intruso sem manifesto vira
evento `cut/roster_violation`; clamp protege o alvo canônico; nenhum LLM escreve no manifesto; SPEC-199/226/231/232
intactas; painel de desfecho volta após reload e "Continuar" não envia `/game/action`; perfil Postgres reconstrói
manifesto `legacy_migrated` no `combat_node`.

## Ressalva aceita
Após "Continuar", um reload reexibe o painel (dismiss local, D-C).

## Gate de eval
§5 exigia corpus autorado em tarefa separada: suíte `encounter_manifest` (31 casos) em `cce8d85`.
Publicar exige aprovação do environment `eval-governance`.
