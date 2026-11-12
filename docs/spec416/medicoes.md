# SPEC-416 — medições da Etapa 0 (12/11, shell local, worktree `rpg-spec-416`)

| Medição | Resultado |
|---|---|
| Semente da catraca de relógio (`clock_asserts.py --update`) | 24 funções, 33 asserts; contém `tests/test_spec361_gate.py::test_prazo_real_por_thread` |
| Override `--config "lint.per-file-ignores = {}"` limpa só o toml? | Sim: 987 pares arquivo×regra, idênticos aos de `current_debt()` antigo (diferença vazia nos dois sentidos). `plain` (sem override) = 0 violações |
| Pares no `ruff-baseline.toml` da `main` | 988 em 488 arquivos; 1 obsoleto (`.claude/hooks/guard_tools.py` × `BLE001`, consertado pela SPEC-414). `--check` já dava "stale" na `main`; a regravação o removeu (487 arquivos, 987 pares) |
| Tempo de `ruff check --exit-zero --output-format json --config … .` | 1,3 s (≤ 5 s) -> R26 no ramo "teste na suíte" (`tests/test_ruff_counts.py::test_repo_respeita_contagens`), sem passo novo no `validate.yml` |
| Tamanho de `ruff-baseline-counts.json` | 34 096 bytes (< 40 KB) |
| Inventário de default em `docs/` (Grep em `scripts/`) | Os da §3.4, mais geradores determinísticos de documento versionado que ficam: `bestiario/{arena,calibrar,eval_geracao,gerar_docs}.py`, `fauna/arena_saber.py`, `gen_error_codes_doc.py`, `gen_event_catalog.py`, `project_index_ab_harness.py`. Nenhum script de staging novo |
| `actionlint .github/workflows/audit-local.yml` | Não rodou: `actionlint` não está instalado nesta máquina. O teste `tests/test_audit_local_workflow.py` valida o YAML (ordem, `id`, `if`) |
| Duração do passo pgTAP no CI | Não medida: depende do primeiro run (push, D-416-4) |
