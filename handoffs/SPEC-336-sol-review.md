# SPEC-336 — revisão sol (review)

> **Veredito:** `APPROVED` (re-revisão de `58220923`; a 1ª rodada em `9e7ae471` foi `CHANGES_REQUIRED`)
> **Revisor:** Sol (Opus 5.5, spec-reviewer) · **Data:** 2026-10-27 · **Commit revisado:** `9e7ae471` (1ª rodada) · `58220923` (re-revisão)

## Escopo

Revisei `main...spec-336` (commits `31c77267` e `9e7ae471`, 25 arquivos): `services/cards.py` (loader),
`services/card_lint.py`, `services/card_telemetry.py`, `services/content_validator.py`, `services/card_deck_round.py`,
`progression.py`, `observability/events.py`, `docs/operacao/EVENTOS_DE_LOG.md`, `scripts/cards/{draft,lint,sim,promote,metrics,painel}.py`,
`data/cards/_roda_posturas.json`, `_lexico_valoria.txt`, os testes `tests/test_card_{lint,sim,draft}.py` e a spec, incluindo os desvios da §8.
Ficaram fora: o conteúdo do guia/PAINEL (texto), `docs/spec336/arena_folego_full.py` (script de medição) e o smoke real (§6, do dono).

Conferido e ok:
- **(a) Catálogo idêntico ao da main:** comparei o loader antigo (glob de topo, o último vence) com o novo `_load_cards()`.
  Resultado: 323 = 323 cartas, mesmos ids, mesmo conteúdo materializado. Não há ids duplicados no acervo atual, nenhuma carta
  tem `versao` e `data/cards/` não tem subpastas além de `_rascunhos/`. Com `versao` igual, a regra `>=` mantém o "último
  vence" da main. Saves com id antigo continuam resolvendo.
- **(b) Telemetria:** `card_telemetry` só emite `card_id`/`pile`/`picked` (ids de catálogo, sem PII). Não muda o retorno de
  `apply_choice` nem o de `resolve_player_plays`/`reaction_commit`, porque `destino` já era o retorno de `play_to_pile`.
  Os 5 eventos estão no catálogo `observability/events.py` e em `EVENTOS_DE_LOG.md`, e `test_log_event_registry` está verde.
  `reaction_commit` só atua nas pilhas do jogador.
- **(c) CI:** `validate_content.py` passa com 0 erros. O lint pleno só vale para cartas com `onda`, e o acervo legado segue com as regras antigas.
  O CI está ligado em `.github/workflows/validate.yml`.
- **(d) `draft.py`:** MockLLM/FallbackLLM (`is_mock`/`is_fallback`) devolvem lote vazio com aviso. O guard
  `isinstance(result, BaseMessage) or not isinstance(result, LoteRascunho)` e o try/except em volta do invoke estão presentes.
  Os valores do LLM passam por clamp (`custo_entropia`, `tier`, `level_req`, `tipo`) e por `fx.validate_card`. A saída vai só para `_rascunhos/`.
- **(e) `sim.py`:** usa `random.seed` por luta, com string determinística. `RPG_CARD_DECK` fica restrito a um context manager e o catálogo
  injetado é restaurado (`test_sim_is_deterministic` e `test_sim_restores_catalog` verdes).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/card_lint.py:386` + `scripts/cards/promote.py:127` | O critério (f) falha. `lint_batch` tira do `base` toda carta do pool com o mesmo id de alguma carta do lote, então `check_names` nunca vê a versão existente. Reproduzi com uma carta `med_teste_trama` v1 no pool e um lote com o mesmo id e `versao: 1`, mas efeito diferente: `promote.evaluate` aprova e `promote` acrescentaria uma segunda entrada. No loader (`>=`) vence o arquivo que vier depois na ordenação dos caminhos (`posturas/…` fica depois de `medico.json`/`devoto.json` etc.), o que é exatamente a "edição silenciosa" que a R7 proíbe. O mesmo vale para um id que colida com uma carta legada. | Em `lint_batch`, manter no `base` as cartas do pool com o mesmo id: `check_names` já trata `versao` maior como bump legítimo, e o teste `test_version_bump_replaces_instead_of_colliding` cobre esse caminho. Acrescentar um teste: lote com id existente e `versao` igual ou menor gera erro `nome`, e `promote` recusa. |
| P1-2 | P1 | `services/content_validator.py:723` e `:829` | O CI também não pega o mesmo caso. Cartas `onda-N` dão `continue` antes do check `seen_ids` (id duplicado), e no lint de onda `others` exclui toda carta com id de onda (`o["id"] not in ids or o["id"] < card["id"]`; quando os ids são iguais, a carta sai). Reproduzi com o mesmo id e `versao: 1` em `medico_onda.json` e em `posturas/m.json`, com efeitos diferentes: `validate_cards` devolve 0 achados. | Acrescentar um check global de `(id, versao)` único em todo o pool, legado e onda, e exigir `versao` estritamente crescente para id repetido. Um id de onda que repete um legado sem `versao` maior deve dar erro. Teste no `tmp_path`, como `test_content_validator_runs_card_lint_for_wave_cards`. |
| P2-1 | P2 | `progression.py:393` (via `auto_resolve_choices`, `:480`) | `auto_resolve_choices` (criação em nível alto, SPEC-227 R9) chama `apply_choice` e escolhe sempre `elig[0]`, a primeira carta por id. Isso emite `card_offered`/`card_picked` como se fosse escolha do jogador e enviesa o pick rate da R7: as cartas alfabeticamente primeiras parecem populares e as demais acumulam ofertas sem escolha, o que vira corte injusto. Também gera rajadas de log (uma linha por carta elegível × cada escolha) ao criar personagem no nível 20. | Passar um flag (`telemetry=False`, ou `source="auto"` filtrado em `metrics.py`) no caminho automático. |
| P2-2 | P2 | `services/cards.py:175` | `int(c.get("versao", 1) or 1)` fica fora do `try`. Uma `versao` não numérica (`"2a"`) derruba o carregamento do catálogo inteiro. Hoje o schema só valida `versao` nas cartas com `onda`. | Fazer coerção defensiva (helper `_versao(c)` com try → 1) ou validar `versao` em toda carta no `content_validator`. |
| P2-3 | P2 | `services/cards.py:146-153` × `services/card_lint.py:102-109` | Os dois walkers divergem: o do loader inclui arquivos `_*.json` de topo (`_glossario`, `_orcamento`, `_roda_posturas`), e o do lint/validator os ignora. Hoje é inofensivo, porque esses arquivos não têm `cards`. | Fazer o loader usar `card_lint.iter_card_files` (fonte única). |

## Correções aplicadas

Commit `58220923` (re-revisado só o delta sobre `c15faa85`):

- **P1-1, fechado.** `lint_batch` agora mantém no pool as cartas de mesmo id (`card_lint.py:383`). Refiz o probe: lote com o mesmo id e `versao: 1` é recusado (erro `nome`); com `versao: 2` é promovido.
- **P1-2, fechado.** O `validate_cards` ganhou uma checagem global de `(id, versao)` duplicado e de `versao` não crescente. A checagem vale para legado e onda e roda antes do `continue` das cartas de onda. Probe: o mesmo id com `versao: 1` em dois arquivos agora dá erro, e a troca legítima v1 → v2 (v2 em `posturas/`) passa sem achado.
- **P2-1, fechado.** `card_telemetry.source_scope("auto")` via `contextvars` envolve o `apply_choice` dentro de `auto_resolve_choices`. `card_offered`/`card_picked` levam `source`, que está no catálogo regenerado, e o `metrics.py` descarta `source == "auto"`. O campo `source` é um rótulo fixo, sem PII.
- **P2-2, fechado.** `card_effects.versao()` faz a coerção (`"2a"`/`True` → 1) e é usado no loader e no lint. O validator dá aviso (`warning`) quando a `versao` é inválida.
- **P2-3, fechado.** O loader usa `card_lint.iter_card_files` como fonte única, e os `_*.json` do topo ficam fora.
- **Catálogo:** refiz a comparação loader `main` × branch. São 323 cartas nos dois, com os mesmos ids, o mesmo conteúdo, 0 duplicados e 0 com `versao`.
- **`observability/events.py`:** `ruff format --check` deu "already formatted" e `ruff check` passou.

Observação, não bloqueante: a checagem "versao não crescente" depende da ordem do `os.walk`, que lê primeiro os arquivos do topo e depois as subpastas. Ela daria falso positivo se uma v2 ficasse num arquivo de topo e a v1 em `posturas/`. O `promote` sempre grava em `posturas/`, então hoje isso não acontece. Se acontecer um dia, basta reduzir a checagem à unicidade de `(id, versao)`.

## Pendências

- Os 5 achados foram fechados em `58220923` (ver acima). Nenhum bloqueio para o pouso.
- Já registrado na §8: coluna de vitória do `metrics.py` sem evento de fim de conflito, hoje via `--resultados`.
- Smoke real §6 (com chave, custo SMART) continua com o dono.

## Comandos rodados

```text
git diff main...HEAD --stat → 25 arquivos, +2694/-16
py.sh scratchpad/cmp_cards.py (loader main × branch) → 323/323, mesmos ids, mesmo conteúdo, 0 ids duplicados, 0 com versao
py.sh scratchpad/probe_promote.py → mesmo id e versao=1: promote aprova; validate_cards com duplicata (id, versao) → 0 achados
py.sh -m pytest -q -p no:cacheprovider tests/test_card_{lint,sim,draft}.py tests/test_log_event_registry.py tests/test_no_silent_except.py tests/test_card_piles.py tests/test_cards_prepare_api.py tests/test_progression_20.py tests/test_progression_v4.py → verde (113 passed, serial; RAM livre 2,2 GB)
py.sh scripts/validate_content.py → 0 ERRO(S) · 0 AVISO(S)
```

Re-revisão (`58220923`):

```text
py.sh scratchpad/probe2.py → P1-1: v1 recusada / v2 promovida; P1-2: (id, versao) duplicado = erro; bump v1→v2 sem achado; versao("2a")=1
py.sh scratchpad/cmp_cards.py → 323/323, mesmos ids e conteúdo, 0 duplicados, 0 com versao
py.sh -m ruff format --check (events.py, card_*, cards.py, content_validator.py, card_effects.py, progression.py, scripts/cards, testes) → 16 files already formatted; ruff check → All checks passed
py.sh -m pytest -q -n 2 tests/test_card_{lint,sim,draft}.py test_card_piles test_cards_prepare_api test_progression_{20,v4} test_log_event_registry test_no_silent_except → 121 passed
py.sh -m pytest -q tests/test_eval_governance.py tests/test_handoff_names.py → verde
py.sh scripts/validate_content.py → 0 ERRO(S) · 0 AVISO(S)
```
