# SPEC-402 - revisao Sol

Veredito: APPROVED

Escopo: `git diff main...HEAD` = spec + `tests/test_tactical_archetypes_runtime.py`. `git diff main -- services data evals tests/test_spec373_montagem.py` vazio.

## Verificacoes
1. Vermelho de R2 reproduzido: trocando `tp._normalize_archetype(...)` por `str(...)` falham `normaliza_gatilho`, `known_bad[MUITO FERIDO-flank]` e `known_bad[conjurador-Cercado-attack]`. Restaurado; `git status` limpo.
2. R3 coberto por completo (4 known-good, 4 known-bad parametrizados, 2 testes em vez de 1) e R4 com 3 grafias.
3. `erros_absoluta` nao chama `normalize_runtime_profile` (so `_normalize_archetype`, D1/R4).
4. Religamento do bestiario: o assert antigo (fuga/rendicao + chave de `sempre`) foi preservado no helper, com gatilho normalizado (so aperta). `except`/KeyError de arquetipo cru continua falhando fechado (D3).
5. Testes focados (`-n 2`): tactical_archetypes_runtime, spec373_montagem, spec373_artefatos, size_budget, handoff_names verdes.

## Achados
- Nenhum P0/P1.
- P2 (opcional): `known_bad[bruto-sempre-flee/surrender]` falham pela checagem explicita de fuga, nao pela de gatilho; ok, cobre o caso listado.
