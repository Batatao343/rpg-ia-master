# SPEC-277 — revisão sol (review)

> **Veredito:** `APPROVED` (após 1 correção P1 aplicada pelo revisor nesta branch)
> **Revisor:** Opus (papel Sol) · **Data:** 2026-10-19 · **Commit revisado:** `d048475` (branch `spec-277`)

## Escopo

`git diff main...spec-277`: `evals/__main__.py`, `evals/core/runner.py`, `evals/manifest.lock.json`
(caminhos protegidos), `tests/test_eval_harness.py`, cabeçalho/plano da spec. Também investigado o
flake `tests/test_jev_router_port.py::test_missing_key_falls_back_to_classify` sob xdist (pedido do
coordenador). Fora: execução do `eval-gates` no GitHub e aprovação do environment `eval-governance`.

## Verificação por requisito

- **R1** (stderr com suíte, `case_id`, traceback ≤ 40 linhas, sem locals): ok — `_report_case_error`
  em `evals/core/runner.py`, chamado só no `except` do caso.
- **R2** (`error_type` sem a mensagem): ok no JSON do CLI (`_error_rows` corta no primeiro `:` do
  diagnóstico). **Mas o stderr vazava a mensagem** (achado P1-1, corrigido).
- **R3** (contagem): ok — o bloco de contabilidade (`error_case_ids`, `diagnostics`,
  `hard_failures`) não mudou; só uma chamada de impressão foi acrescentada. O teste confirma
  `error_case_ids == [case]` e `skipped_case_ids == []`; o run limpo devolve `errors: []` e stderr vazio.
- **R4** (relock): `governance lock` com os 11 datasets do manifesto; o diff do lock contra a `main`
  são exatamente as 2 linhas `ruler_sources` (`__main__.py`, `core/runner.py`); `governance check`
  verde. Falta só o `eval-gates` verde com aprovação do dono — a spec segue `approved`, não `done`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `evals/core/runner.py` `_report_case_error` | `traceback.format_exception` inclui a última linha `KeyError: '<mensagem>'` (e mensagens de `__cause__`/`__context__`). A mensagem pode carregar conteúdo de caso/expected; `run_eval` também roda no companion do holdout privado (`eval-protected.yml`, passo "without case-level output"), cujo stderr vai para o log público do Actions. O teste só checava `secret not in captured.out`. | Aplicada: só `traceback.format_tb` (frames) + `"<Classe> (message omitted)"`, sem cadeia de causas; teste ganhou `assert secret not in captured.err`. Relock refeito. |
| P2-1 | P2 | `evals/core/runner.py` `_report_case_error` | O `case_id` sai no stderr também no holdout privado (identificador, não conteúdo; exigido por R1). | Follow-up: se o dono quiser holdout 100 % agregado, suprimir o header por flag/env no companion. Não bloqueia. |
| P2-2 | P2 | `services/jev_rollout.py:222` `_default_backend` | Causa do flake (abaixo) é também um defeito de produto: o `httpx.Client()` compartilhado (SSL context) é criado dentro do prazo de 1 s do Jev, então o 1º turno em `primary`/`shadow` de uma instância fria pode cair em `timeout` espúrio. | Follow-up de spec própria: aquecer o client antes do relógio (como `_frozen()`). |

### Flake `test_missing_key_falls_back_to_classify` (xdist)

Reproduzido 2/2 com `-n auto` nos testes jev/router/spec217/eval_harness: `assert 'timeout' ==
'configuration'`. Não é env compartilhado (as chaves são removidas e `load_dotenv` é stub): sob
contenção de CPU, `_evaluate` cria `httpx.Client()` (contexto SSL) e disputa o pool global de 4
threads **dentro** do prazo de 1 s, estourando antes de `_api_key` levantar `configuration`. O teste
também não removia o hook de telemetria. Correção (só teste): `_client` placeholder, pool privado de
1 worker, hook removido em `finally`. Depois: 3/3 verdes no mesmo conjunto com `-n auto`.

## Correções aplicadas

Commit do revisor nesta branch (`fix(evals): omit exception message from case traceback; deflake jev
missing-key test`): P1-1 + relock + isolamento do teste jev.

## Pendências

- `eval-gates` verde no GitHub com aprovação do environment `eval-governance` (dono) → então `done`.
- P2-1 e P2-2 acima (dono decide; P2-2 merece spec curta).
- Pré-existente, sem mudança: o JSON do run gravado em disco (`diagnostics`) ainda guarda
  `"<Classe>: <mensagem>"`; para o holdout isso fica no artefato privado, não no log.

## Comandos rodados

```text
py.sh -m evals.core.governance check --root .            → falhou (hash do runner) antes do relock; "valid: 11 dataset(s)" depois
py.sh -m evals.core.governance lock --root . --dataset ×11 → locked 11; diff vs main = 2 linhas ruler_sources
py.sh -m pytest tests/test_eval_harness.py tests/test_jev_router_port.py tests/test_eval_governance.py → 59 passed
py.sh -m pytest -n auto tests/test_jev_*.py tests/test_router_interlocutor.py tests/test_spec217_j{1,2}.py tests/test_eval_harness.py → antes 2/2 FAILED; depois 3/3 "188 passed"
```
