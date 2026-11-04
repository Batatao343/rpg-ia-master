# SPEC-380 — revisão astra (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 / Astra (régua de eval, contexto independente; não escreveu o diff) · **Data:** 2026-11-04 · **Commit revisado:** `54c96db6`

## Escopo

Branch `spec-380`, `d0b5eb25..54c96db6` (8 commits, 17 arquivos), worktree
`C:\Users\guilh\AppData\Local\Temp\claude\rpg-spec-380`. Revisado:
`evals/core/cards_combat.py`, `evals/datasets/regression/cards_combat.jsonl` (29 casos),
`evals/core/adapters.py` (registro), `evals/manifest.lock.json`, `evals/protected-paths.txt`,
`.pre-commit-config.yaml`, `.github/workflows/eval-gates.yml`,
`.github/workflows/llm-playtest-weekly.yml`, `tests/test_eval_cards_combat.py`,
`tests/test_eval_baseline.py`, `tests/test_ci_eval_gates.py`, docs (README, SKILL, política de
tiers, AGENTS.md), `config/flags.yaml`. Ficou fora: o commit B (baseline do CI, ainda não existe)
e o smoke §6 (depende de D2).

### Régua `cards_combat`

- **Caso do golden 330 (100 %, 1 de 1: `cards.condicao.antitoxina-sem-alvo`, jsonl:19).** O
  `input` reproduz `tests/spec330_equivalence.py::run_card` no cenário base: `random.seed(11)`
  (`global_seed: 11`), `rng=Random(7)`, player `ensure_combat_sheet` com `class_name` = classe
  da Carta (`Médico de Campo`, `data/cards/exemplos_extra.json:299`), entropy 99/99, level 20, Mira
  `{dot 0, duration 9, stat attack, delta 40}` aplicada depois da ficha; `e` e `ally`
  (`companheiro`, `transient`) com `is_player=False`; ordem de `place` player→e→ally; `freeze`;
  alvo `player` porque `purga_condicao` ∈ `_SUPPORT_EFFECTS` (`services/conflict_turn.py:248`);
  `sides` idêntico. `expected`: `n_attacks 0` ← `res: []` (`res` = lista de `resultado` por ataque,
  `spec330_equivalence.py:154`); `entropy 98` ← log citado exato `Usa Antitoxina (-1 Entropia)`;
  `condicoes ["Mira"]` ← log citado `Antitoxina: nenhuma condição para remover.` (ver P3-1). Fonte
  do golden é o motor **pré-330**: oráculo independente do código atual. OK pela R2.3(b).
- **Amostra dos demais: conferi 28 de 28**, não só 5. Os 8 `damage` (jsonl:1–8) batem
  campo a campo com `tests/test_conflito_dano.py:50-153` (alvo, armadura, tipo, base e os
  asserts citados). Os 8 `resolve_turn` (jsonl:9–16) reproduzem `tests/test_conflito_turno.py`
  (`_combatant`, `distance_state proximo`, `_hit` = `[10,8,9,7]`, `_miss` = `[1,3,2,4]`, `state`
  com `combat.scene`, `fill_critical_but_one` = o laço de Críticos da linha 131). `resolve_card`
  (jsonl:17–18) = `test_card_effects_grammar.py:258-323` (`Random(1)`, sides, Vitalidade 60;
  `55 = 60 − 5`; `dot 3`). `round` (jsonl:20–22) = `test_conflito_orquestrador.py:140-225`
  (fichas, seeds 7/3/11, tetos 12/10/15). `intent` (jsonl:23–25) =
  `test_enemy_intent.py:145-166`. `folego` jsonl:26 = `test_spec377_folego.py:51-55`;
  jsonl:27–29 ver P2-1.
- **Tautologia:** nenhum `expected` é recomputado pelo adapter; o adapter só projeta campos
  do produto. Única derivação no lado do eval: `vencedor` (`cards_combat.py:249`, P3-2), que é
  função transparente de `ended`/`player_dead` do produto.
- **Known-bad realmente falham quando deviam** (probe em memória, sem editar nada): sem o
  `hide`, `alvo-escondido` dá `n_attacks 1` ≠ 0; trocando a passiva por `raio_cinza`,
  `passiva-como-acao` dá `{n_attacks 1, entropy 4}` ≠ `{0, 5}`. Antitoxina com um `Veneno` ativo
  remove o veneno e mantém Mira (a projeção pegaria remoção indevida de Mira).
- **Determinismo:** os 29 casos rodados 2× dão saída idêntica e = `expected`; os 3 `round`
  são invariantes a `global_seed` ∈ {1,2,3,7,99} (o dado vem só do `rng` do caso); `_pinned`
  restaura env e `random` global (teste `test_adapter_restaura_env_e_random_global`).
- **Denominador/exclusões:** sem exclusões; `test_corpus_passes_fully` exige
  `len(results) == len(cases)` e `error_case_ids == []`. Os 29 casos entram em
  `state_transition_pass_rate` (agregação por oráculo, R2.6) — muda o denominador dessa
  métrica, como a spec previu; a baseline do commit B fixa o novo denominador via
  `case_selection_hash`/`dataset_hashes`.
- **Fail-closed:** operação desconhecida, flag ausente, `projection` vazia ou caminho
  inexistente ⇒ `AdapterError` (testados). Nenhum oráculo de texto (`sinal`, `logs` fora; só
  `sinal_presente` bool).

### Governança e CI

- `manifest.lock.json`: +1 dataset (`cards_combat.jsonl`), `core/adapters.py` re-hash,
  +`core/cards_combat.py` em `ruler_sources`; `evaluator_version` e `metrics-registry.yaml`
  inalterados. `adapters.py`: só import + registro (+3 linhas). `protected-paths.txt`:
  +`evals/baselines`. `git diff --stat main...HEAD -- evals/datasets evals/evaluators` só mostra
  o jsonl novo. `evals/baselines` não entra em `_ruler_hashes` (`governance.py:186-196`), então o
  commit B não invalida a si mesmo.
- `eval-gates.yml:69-95`: `python-version: "3.13.18"` no `setup-uv` (input existe no SHA
  pinado, Etapa 0); ordem `run` → `pytest tests/test_eval_baseline.py` → `compare`. Os dois
  últimos com `if: always()` para o artefato sair entre A e B (desvio declarado, correto). Falha
  fechado: qualquer passo ≠ 0 reprova o job; `product_sha` não entra na compatibilidade, então PR
  de produto fica verde enquanto a régua não muda.
- `llm-playtest-weekly.yml`: só `workflow_dispatch` + `schedule` atrás de
  `vars.RPG_WEEKLY_LLM_PLAYTEST == 'true'`; `environment: llm-playtest`; `RPG_NO_MOCK: "1"`;
  `test -n` dos 3 secrets; `--turns 5 --max-requests 60 --max-cost 0.25` por perfil;
  exit code registrado, não propagado; falha só se nenhum `summary.json` tiver `mock false` e
  provider registrado; `permissions: contents: read`, `persist-credentials: false`, actions por
  SHA. Nenhum `echo` de secret; os secrets não são interpolados em `run:` (vão por env).
- Integridade (contrato 08): zero arquivo de produto no diff (`agents/`, `services/`,
  `infrastructure/`, `workers/`, `web/src/`, `routes/`, arquivos-raiz de `eval_publish.py`).
  `config/flags.yaml` é registro de flag (gate de flags), não produto.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `evals/datasets/regression/cards_combat.jsonl:27-29` | Os 3 casos de Fôlego com Carta sintética (`custo_folego 5→3`, `dano_base 8→2`, `livre/cura→0`) tiram o `expected` da leitura à mão da função congelada `_jogo_antigo` (`tests/test_spec377_folego.py:9-29`), não de um `assert` existente nem do golden 330. É oráculo independente (cópia literal pré-377, lado do teste) e os 3 valores conferem, mas fogem da regra fechada R2.3 e o desvio não está em § Execução. | Antes do `/eval-publish`: registrar em § Execução da spec o desvio ("R2.3(c): avaliação manual da regra congelada `_jogo_antigo`, sem rodar o produto") ou trocar por Cartas do catálogo cobertas pelo `test_paridade_catalogo_com_jogo`. Não mexer no dataset sem nova revisão Astra. |
| P3-1 | P3 | `evals/datasets/regression/cards_combat.jsonl:19` | `condicoes: ["Mira"]` é inferência do log "nenhuma condição para remover" (o golden não guarda a lista de condições). Inferência forte e a string está citada, mas é a exceção da R2.3, não o campo `res`. | Aceito como está; se a 330 for regenerada um dia, guardar as condições no golden. |
| P3-2 | P3 | `evals/core/cards_combat.py:249` | `vencedor` é derivado no adapter (`ended`/`player_dead`); `reason` do produto (`conflict_orchestrator.py:3038`) não é projetado, então "inimigo fugiu" e "inimigo morreu" dão o mesmo `hero`. | Follow-up: expor `reason` no `actual` e projetar em `fim.*` na próxima autoria de eval. |
| P3-3 | P3 | `.github/workflows/llm-playtest-weekly.yml:27-31` | Secrets no `env` do **job**: ficam visíveis a `uv sync` (scripts de build de dependência) e ao passo de resumo, que não precisam deles. | Mover os 3 secrets para o `env` dos passos "Require provider secrets" e "Run the 4 vital profiles". |
| P3-4 | P3 | `.github/workflows/eval-gates.yml:89,95` | `if: always()` roda baseline/compare também em cancelamento e quando `uv sync`/`governance check` falharam (erro duplicado, sem efeito no veredito do job). | `if: ${{ !cancelled() }}` ou `success() \|\| failure()`. Opcional. |
| P3-5 | P3 | `evals/core/cards_combat.py:98,190,279` | Entrada malformada dá `AttributeError`/`KeyError` em vez de `AdapterError` (`row` não-dict, `actor_id` ausente); `campos_internos` é calculado e nenhum caso o projeta (a garantia "sem `declaration`/`carta_id`/`idx` na visão pública" fica sem caso). | Validar `row`/`actor_id` com `AdapterError`; acrescentar `campos_internos: []` à projeção de um `pressagio.*` na próxima autoria. |
| P3-6 | P3 | `evals/datasets/regression/cards_combat.jsonl:25` | `arc_descarga` é Carta de classe (Arcanista, em esteira de balanço da 369); o caso só depende do nome "Descarga do Instrumento" e da ordem da faixa, não de número — risco baixo, mas contra a letra da R2.4b. | Aceito; renomear a Carta exige eval authoring (já é a regra). |

Sem P0/P1. `test_eval_baseline.py::test_baseline_bate_com_a_regua_atual` falha por design até o
commit B (§3.1) — não é achado.

## Correções aplicadas

Nenhuma (revisão só leitura; este arquivo é o único editado).

## Pendências

- Coordenador: P2-1 (registrar o desvio na spec) antes do `/eval-publish`; depois commit B
  (baseline do CI copiada sem editar) e aprovação do dono no `eval-governance` (D6).
- Follow-ups P3-2/P3-5 na próxima autoria de eval de Cartas (ex.: a da 369); P3-3/P3-4 podem
  ir num commit de workflow não protegido nesta mesma branch.
- Smoke §6 após D2 (environment `llm-playtest` + 3 secrets).

## Comandos rodados

```text
git diff main...HEAD --stat → 17 arquivos, +857/−3; datasets/evaluators: só cards_combat.jsonl
bash scripts/dev/pt.sh -n 0 tests/test_eval_cards_combat.py tests/test_eval_baseline.py tests/test_ci_eval_gates.py tests/test_eval_governance.py tests/test_workflows_contract.py tests/test_ci_docs_only.py --deselect ...::test_baseline_bate_com_a_regua_atual → 65 passed, 1 deselected
bash scripts/dev/pt.sh -n 0 tests/test_size_budget.py → 4 passed
bash scripts/dev/pt.sh -n 0 tests/test_flag_registry.py → 15 passed
scripts/dev/dup_helpers.py --diff main...HEAD → nenhuma função nova com nome já usado
probe (scratchpad, só leitura): 29/29 determinísticos e = expected; known-bad mutados reprovam; round invariante a global_seed
```
