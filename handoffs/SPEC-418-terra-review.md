# SPEC-418 — revisão terra (review)

> **Veredito:** APPROVED_WITH_FOLLOWUPS
> **Revisor:** Sonnet (terra) · **Data:** 2026-11-12 · **Commit revisado:** `296dfead`

## Escopo

Branch `spec-418` (`main...HEAD`, 13 arquivos, +1317): `scripts/dev/type_gate.py`, check `types` do `land_check.py`, `[tool.basedpyright]`, `.basedpyright/baseline.json`, job `types` no `validate.yml`, `uv.lock`, testes e docs. Fora: run do job `types` no CI (o coordenador empurra depois do pouso).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `.claude/hooks/guard_tools.py:140` | O hook não nega `type_gate.py --update` em subagente: `BASELINE_SCRIPTS` não tem `type_gate`. É o D-418-6 (emenda da 416 pelo coordenador), então não é desvio. Até lá a única barreira é o `growth` do `--land`. | Coordenador acrescenta `"type_gate": ("--update",)` e `.basedpyright/baseline.json` no `baseline_growth.py` após o pouso. |
| P2-2 | P2 | `pyproject.toml` `include`, `docs/spec418/medicao.md` E0.6 | Cobertura do risco original é pequena (ver resposta 3). O gate só prova valor em `chronicle_compression`, `creature_gen`, `prologue`, `shared_pool`. | Degrau seguinte: `agents/` e o resto de `services/`, em spec própria. |
| P2-3 | P2 | `scripts/dev/type_gate.py` `cmd_land` | Sem basedpyright no venv o `--land` dá WARN e passa. Se o venv do checkout principal não for sincronizado com `--all-extras`, o gate nunca roda no pouso. Previsto na spec, mas é brecha permanente. | Coordenador confirma que o venv principal tem a dependência; opcional promover WARN a FAIL depois da calibração. |
| P2-4 | P2 | `tests/test_type_gate.py` | Nenhum teste automático cobre `--check`/`--land` com baseline real e erro novo na mesma regra de arquivo já baselinado; o e2e usa `--files`, sem baseline. Verifiquei à mão (abaixo): funciona. | Acrescentar caso `types_e2e` com baseline sintética. |
| P2-5 | P2 | `type_gate.py` `evaluate` | `tempfile.mkdtemp` nunca é removido (vaza uma pasta pequena por check). | `shutil.rmtree` ao final. |

### Respostas às perguntas do coordenador

1. **type_gate.** `--check` na branch limpa dá rc 0 ("baseline justa"). Erro novo de `reportArgumentType` em `persistence.py` (arquivo e regra já baselinados) reprova, rc 1: a baseline por arquivo×regra não o engole. Arquivo novo em `infrastructure/` reprova, rc 1. Arquivo renomeado conta como novo (a chave é o caminho): mais estrito, não mais frouxo. `--update` sem `--reason` devolve rc 2 (teste). Binário ausente devolve rc 2 com mensagem; saída não-JSON levanta `RuntimeError` e vira rc 2; no `--land`, sem linha `OK|WARN|FAIL`, o `land_check` converte em FAIL ("sem saida legivel"). Nunca vira OK. Hook negando `--update`: não (P2-1).
2. **land_check.** `needs_check` dispara para qualquer `.py` e para `pyproject.toml`/`uv.lock`/baseline: cobre os 5 de `services/` e `infrastructure/**` (e mais). WARN sem checador: P2-3. Sem baseline na `main` o `growth` é pulado; depois do pouso a `main` tem baseline e o buraco fecha sozinho.
3. **Corte do escopo.** Seguiu o critério escrito (E0.7.3: pico > 2 GB; cortar para `infrastructure`, `state.py`, `persistence.py` e os `services/` que importam `llm_setup`), com medições (2 741/2 382 MB no cheio, 1 796 MB no final). Não foi escolha por conveniência. Cobertura do risco original: dos cerca de 19 arquivos de produção que chamam `with_structured_output` (Grep: `agents/` 10, `services/` 8, `character_creator.py`, `llm_setup.py`, `mock_llm.py`) o escopo inclui 4, ou seja, cerca de um quinto dos chamadores, e nenhum de `agents/` (storyteller, router, combat, npc, archivist, loot...), onde está a maior parte do risco; 4 de `services/` têm `llm` sem tipo e ficam cegos, assumido em `medicao.md` e `TESTES.md`.
4. **pyproject.** As 7 regras e `reportIgnoreCommentWithoutRule` estão `error`; 6 em `warning` com contagem em `medicao.md` E0.2 (InvalidTypeForm 15, OptionalCall 4, IncompatibleVariableOverride 3, AssignmentType 2, OperatorIssue 1, Redeclaration 1), justificadas pelo critério de R5 (contagem > 0). `git diff main...HEAD -- '*.py'` só toca `scripts/dev/*` e `tests/*`: zero mudança de produto, zero `type: ignore` novo.
5. **validate.yml.** Só acrescenta o job `types` (`continue-on-error: true`, `needs: scope`, mesmo `if` de `docs_only`, timeout 10). SHAs de `checkout` e `setup-uv` iguais aos do restante do arquivo. `uv sync --all-extras` como o job `test`; outros jobs intactos.
6. **Testes.** Os casos `types_e2e` provam o valor (sem `isinstance` reprova na linha 12 citando `AIMessage`; guardado passa; padrão autocontido; `type: ignore` sem regra). Não os reexecutei (as 3 rodadas permitidas do checador foram para as provas manuais). Mutações em `type_gate.py`, revertidas com `git checkout --` e `git status` limpo: (a) `growth` com `+ 5` quebra `test_growth_against_base`; (b) `slack` com `if False` quebra `test_slack_flags_fixed_entries_only`. Não há skip condicional no arquivo (o marcador é opt-in via `addopts`), então `reason=` não se aplica.
7. **Dependência.** `basedpyright==1.40.2` só no grupo `dev`; `uv.lock` ganha `basedpyright` e `nodejs-wheel-binaries` (30 linhas, nenhuma versão existente trocada); `requirements.txt` e Vercel intactos.

Qualidade: `type_gate.py` com 271 linhas (a spec pedia ≤ 220, sem gate), funções ≤ 60; sem `except` largo; sem segredo em log.

## Evidência verificada

Saída de `bash scripts/dev/red_green.sh 418` (sem `--allow-green`: nada já passava na `main`):

| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_land_check.py::test_types_check_relays_gate_line | vermelho | verde | OK |
| tests/test_type_gate.py::test_bare_type_ignore_is_rejected | vermelho (import) | error | FAIL: nao passa na branch (types_e2e fora do addopts) |
| tests/test_type_gate.py::test_basedpyright_config_matches_spec | vermelho (import) | verde | OK |
| tests/test_type_gate.py::test_ci_has_types_job | vermelho (import) | verde | OK |
| tests/test_type_gate.py::test_entries_reads_checker_baseline_format | vermelho (import) | verde | OK |
| tests/test_type_gate.py::test_growth_against_base | vermelho (import) | verde | OK |
| tests/test_type_gate.py::test_guarded_structured_output_passes | vermelho (import) | error | FAIL: idem (types_e2e) |
| tests/test_type_gate.py::test_is_shrink_only_rejects_any_new_entry | vermelho (import) | verde | OK |
| tests/test_type_gate.py::test_land_fails_when_baseline_grew | vermelho (import) | verde | OK |
| tests/test_type_gate.py::test_land_line_format | vermelho (import) | verde | OK |
| tests/test_type_gate.py::test_land_prints_ok_when_diff_is_not_python | vermelho (import) | verde | OK |
| tests/test_type_gate.py::test_land_warns_when_checker_missing | vermelho (import) | verde | OK |
| tests/test_type_gate.py::test_needs_check_filters_changed_files | vermelho (import) | verde | OK |
| tests/test_type_gate.py::test_self_contained_fallback_pattern_is_rejected | vermelho (import) | error | FAIL: idem (types_e2e) |
| tests/test_type_gate.py::test_slack_flags_fixed_entries_only | vermelho (import) | verde | OK |
| tests/test_type_gate.py::test_unguarded_structured_output_is_rejected | vermelho (import) | error | FAIL: idem (types_e2e) |
| tests/test_type_gate.py::test_update_requires_reason | vermelho (import) | verde | OK |

`red_green: 13/17 OK`. Os 4 "error" são exatamente os `types_e2e`, deselecionados pelo `addopts` (`not types_e2e`); precisam de `-m types_e2e`, que o job `types` do CI roda. Não os reexecutei (limite de RAM).

Provas manuais do checador (3 rodadas, uma de cada vez): `--check` limpo rc 0; erro novo `reportArgumentType` em `persistence.py` rc 1; arquivo novo `infrastructure/probe_new.py` rc 1. Tudo revertido, `git status` limpo.

## Correções aplicadas

Nenhuma (revisor não edita código).

## Pendências

- P2-1: emenda do hook e do `baseline_growth.py` (D-418-6), coordenador, após o pouso.
- P2-2: spec do degrau seguinte (`agents/` e resto de `services/`).
- P2-3, P2-4, P2-5: coordenador decide se viram spec pequena; nenhum bloqueia o pouso.
- Run verde do job `types` no CI (D-418-3) segue pendente do push.

## Comandos rodados

```text
git diff main...HEAD --stat → 13 arquivos, +1317
bash scripts/dev/red_green.sh 418 → 13/17 OK (4 e2e fora do addopts)
mutação growth (+5) + pt.sh tests/test_type_gate.py → 1 failed (esperado); revertido
mutação slack (if False) + pt.sh tests/test_type_gate.py → 1 failed (esperado); revertido
type_gate.py --check (limpo) → rc 0
type_gate.py --check (erro novo em persistence.py) → rc 1
type_gate.py --check (arquivo novo em infrastructure/) → rc 1
git status --short → limpo (exceto este handoff)
```
