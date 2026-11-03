# SPEC-379 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus / Sol (`spec-reviewer`, independente) · **Data:** 2026-11-03 · **Commit revisado:** `b87c3e4d`

## Escopo

Pouso **parcial** da branch `spec-379` (`main...b87c3e4d`, 13 commits, 20 arquivos). A spec
continua `in-progress`. O que foi revisado:

- Etapa 1: `tests/factories.py` e `tests/test_factories.py`.
- Etapa 2: `tests/fakes/scripted_llm.py` e `tests/test_scripted_llm.py`.
- Etapa 3: `pyproject.toml`, `uv.lock`, `.gitignore`, `.github/workflows/coverage.yml`,
  `scripts/dev/coverage_summary.py` e `tests/test_coverage_summary.py`.
- Etapa 7: `docs/guias/TESTES.md` e `docs/guias/BRIEF_SUBAGENTE.md`.
- Etapa 0, parcial: `docs/spec379/fonte_inventario.md`.
- Etapa 6, parcial: `test_fase26`, `test_fase33`, `test_fase34`, `test_mvp`, `test_dossiers` e
  `test_checkpoints`.

Ficou fora de propósito, sem reprovar: Etapas 4/5 (e2e e R6), o resto da Etapa 6 e a Etapa 8
(baseline). O que está na branch pousa sozinho: nenhum arquivo de produto foi tocado, nada quebra
sem as etapas pendentes e o workflow novo só roda por `schedule`/`workflow_dispatch`.

Conferências pedidas:

- **W7 / R4.2, refeita por mim em 2 arquivos.** Rodei a versão de `main` (via `git show`) e a da
  branch, cada uma no mesmo lugar, e restaurei com `git checkout`.
  - `test_checkpoints.py`: 13 coletados nas duas versões e as 13 ids `PASSED` idênticas.
  - `test_fase33.py`: 32 coletados nas duas versões e as 32 ids `PASSED` idênticas.
  - Nos 6 arquivos migrados, o diff não tem nenhuma linha `+`/`-` com `assert`,
    `pytest.raises` ou `approx`.
  - Em `test_fase33.py:367` mudou uma única linha que não é asserção (`fake.received` passou a
    `fake.calls[-1][1]`). O valor é o mesmo: as mensagens do último invoke.
- **`uv.lock` só aditivo.** O diff tem zero linhas `-` (entram `coverage` 7.17.1 e `pytest-cov`).
  `requirements.txt`, `tests/conftest.py` e `evals/` não têm diff. O `--name-status` não tem `R`
  (nenhum arquivo renomeado), e todos os caminhos estão na lista branca da §3.2.
- **`coverage.yml` não vira gate nem roda em PR.** Os gatilhos são só `schedule`
  (`17 4 * * 0`) e `workflow_dispatch`, sem `fail_under`. O passo do pytest tem
  `continue-on-error`, e o job só falha se o `coverage.json` não existir (D4). Também conferi:
  `permissions` no topo, SHAs pinados, `ubuntu-24.04`, `persist-credentials: false`,
  `--extra anthropic`, `timeout-minutes: 60` e upload com `if: always()`. Os testes de contrato de
  workflow passam.
- **As fábricas não disparam rede nem LLM.**
  - `playtest/runner` só importa a stdlib no topo.
  - `create_player_character` é chamado com `use_llm_flavor=False`.
  - `test_make_state_never_calls_llm` troca `get_llm` por uma função que levanta e limpa o cache
    da ficha antes de chamar.
  - A paridade com `POST /game/new` vale em `level=1` e `level=3` e compara `world`/`world_sim`
    sem normalizar nada. O calendário segue o `game_id`.
- **O desvio R2.6 da §10 é aceitável.**
  - Por que: as chaves a mais (`player.vitalidade_base_bonus` e `world.shelter=None`) vêm do
    backfill do `load_game_state`, e não da fábrica. O R2.3 prova que a fábrica produz o mesmo
    estado que o `POST /game/new`, então um jogo novo do produto tem o mesmo round-trip.
  - O que o teste fixa: as chaves originais voltam iguais, e a lista do que pode ser acrescentado
    é exata.
  - Se o loader mudar, o teste falha alto, sem esconder nada.
- **Os outros desvios também são aceitáveis.** O helper `story_update_llm` cobre as 3 variantes de
  `StoryUpdate` que dependem de flag. A não migração do `test_day_digest_inline` segue o W3.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `.github/workflows/coverage.yml:34` | O `echo "::warning::…"` está dentro do bloco `{ … } >> "$GITHUB_STEP_SUMMARY"`. O texto vai para o arquivo de resumo, não para o stdout, e por isso **não** vira anotação de warning. Além disso, a D4 pede "uma lista no resumo" das falhas sob o tracer, e hoje o resumo só aponta para o artefato. | Mover o `::warning::` para fora do redirecionamento. Acrescentar ao resumo algo como `grep -E '^(FAILED\|ERROR)' pytest-cov.log \| head -50` quando `steps.pytest.outcome != success`. Dá para fazer junto da Etapa 8, antes da 1ª baseline. |
| P2-2 | P2 | `tests/test_dossiers.py:33` | `make_state(game_id=…, player=…, world=…, **base)`, com `base` vindo de `**extra`. Um caller futuro `_state(player=…)`, `_state(world=…)` ou `_state(game_id=…)` levantaria `TypeError` (multiple values). Antes, a chave inteira era substituída. Nenhum caller atual faz isso (conferi os ~40 usos), então o risco é latente. | Tirar `player`/`world`/`game_id` de `extra` antes da chamada (com `extra.pop(...)`) e repassá-los como parâmetros nomeados. Ou registrar no docstring que essas chaves não são aceitas. |
| P2-3 | P2 | corpo dos commits `a7378f48`…`b105d8c6` | O R4.2 pede "no corpo" a contagem coletada e a lista de ids. Os corpos trazem só a afirmação ("collected 13 and passed ids identical"), sem a lista e sem um hash dela. A prova reproduzida aqui confirma a afirmação nos 2 arquivos amostrados. | Nos próximos commits de migração, incluir `N tests collected` e a lista ordenada das ids (ou o sha256 da lista). Os commits já feitos não precisam ser reescritos. |

Sem P0/P1. Também verifiquei e não encontrei problema:

- Nenhuma função nova passa de 60 linhas. O `test_size_budget` passa.
- O `ruff check` passa nos 12 arquivos.
- Não há `except` largo.
- Nenhum valor de LLM é consumido sem validação: o `ScriptedLLM` valida `dict` com
  `model_validate`, e o `failing()` exercita o guard real do `character_creator`.
- Não há segredo em log.
- `dup_helpers` só acusou colisões de nome genérico (`_pct`, `_row`, `render`) em scripts
  standalone. Não é duplicação relevante.

## Correções aplicadas

Nenhuma até aqui: a revisão é anterior às correções.

## Pendências

- Etapas 4/5 (e2e `auth-bootstrap`/`visual-cue`, R6 (a)/(b)): executor da 379, em coordenação
  com a SPEC-383.
- Resto da Etapa 6 (até 20 arquivos): executor da 379. A prova R4.2 dos arquivos já migrados
  precisa ser refeita depois do rebase sobre 370/371 (R4.1).
- Etapa 8 (baseline via `coverage.yml` na `main`, D3): coordenador. P2-1 de preferência antes
  dela.
- P2-2 e P2-3: executor, na próxima leva da Etapa 6.

## Comandos rodados

```text
git diff main...HEAD --stat → 20 arquivos, todos na lista branca §3.2
git show main:tests/test_checkpoints.py (no lugar) + pytest --collect-only / -rA -n 2 → 13/13, ids PASSED idênticas à branch
git show main:tests/test_fase33.py (no lugar) + pytest --collect-only / -rA -n 2 → 32/32, ids PASSED idênticas à branch
git diff main...HEAD -- <6 arquivos migrados> | grep assert|raises|approx → vazio
git diff main...HEAD -- uv.lock | grep '^-' → vazio; requirements.txt/conftest.py/evals → sem diff
bash scripts/dev/pt.sh tests/test_factories.py tests/test_scripted_llm.py tests/test_coverage_summary.py tests/test_fase26.py tests/test_fase33.py tests/test_fase34.py tests/test_mvp.py tests/test_dossiers.py tests/test_checkpoints.py tests/test_workflows_contract.py tests/test_ci_docs_only.py tests/test_spec192_vercel_packaging.py tests/test_api_fuzz_harness.py tests/test_size_budget.py → 238 passed
ruff check <12 arquivos novos/alterados> → All checks passed
scripts/dev/dup_helpers.py --diff main...HEAD → só colisões de nome genérico em script standalone
git status --short (após a prova) → limpo, exceto este handoff
```
