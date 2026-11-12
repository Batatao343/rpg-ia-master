# SPEC-416 — revisão terra (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sonnet (spec-reviewer, papel terra) · **Data:** 2026-11-12 · **Commit revisado:** `b2c061af`

## Escopo

Branch `spec-416` (8 commits sobre `eea14cdc`, 37 arquivos, +3157): workflow `audit-local.yml` +
`dev_stack.py test-db`, `clock_asserts.py` + baseline, `ruff_baseline.py` por contagem, hook
`guard_tools.py`, `baseline_growth.py` + check `growth`, defaults `.tmp/evidence/` em
`scripts/staging/*`, `docs/guias/DECISOES_FIXAS.md`. Fora: pgTAP real no CI (exige push) e
`actionlint` (não instalado). Nada rodou em background.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `docs/spec191/README.md:6`, `docs/spec192/README.md:15` | Runbooks ainda dizem que os scripts gravam por padrão em `docs/spec191/evidence/` e `docs/spec192/evidence/smoke.json`; o default agora é `.tmp/evidence/`. Quem seguir o runbook procura o arquivo no lugar errado. | Trocar o texto para `.tmp/evidence/` (`--out docs/…` para versionar). |
| P2-2 | P2 | `scripts/dev/clock_asserts.py:_has_clock` | Falso negativo: alias de função (`clock = t.time; n = clock(); assert n`) não é detectado (só chamadas diretas a nome canônico). Alias de módulo/`from`, `datetime.now()` e cadeia por atribuição foram provados e funcionam. Falso positivo: `self.t0 = time.time()` contamina `self` (todo assert que cita `self` no mesmo método conta). | Aceitável para catraca; registrar a limitação na docstring ou tratar `Attribute` como alvo só com o nome do atributo. |
| P2-3 | P2 | `.claude/hooks/guard_tools.py:_raises_baseline` | `ruff_baseline.py --help` por subagente é negado (a regra é "tudo exceto --check/--tighten"). Sem falso positivo em leitura (`grep -n "--update" …`, `cat …`, `git commit -m "… --update"` passam; `uv run python -m scripts.dev.clock_asserts --update` e `… --update --check` são negados). | Liberar `--help`/`-h`. |
| P2-4 | P2 | `docs/guias/DECISOES_FIXAS.md` D-36 | A fonte (`auditoria-workspace-2026-11-11.md:47`) diz só "Postgres/Docker local nesta máquina" como não fazer; "Postgres só no CI" e o gatilho "máquina nova" são inferência do autor. D-10, D-31, D-32, D-35, D-22 conferem com a fonte. | Ajustar o texto à fonte ou citar a decisão que fala de CI. |

Sem P0/P1.

## Evidência verificada

```text
| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_audit_local_workflow.py::test_audit_local_runs_pgtap | vermelho | verde | OK |
| tests/test_baseline_growth.py (4 testes) | vermelho (import) | verde | OK |
| tests/test_clock_asserts.py (8 testes) | vermelho (import) | verde | OK |
| tests/test_decisoes_fixas.py (6 testes) | vermelho | verde | OK |
| tests/test_dev_stack.py::test_test_db_* (3 testes) | vermelho | verde | OK |
| tests/test_land_check.py::test_growth_check_reports_rc | vermelho | verde | OK |
| tests/test_ruff_counts.py (7 testes) | vermelho | verde | OK |
| tests/test_staging_evidence_default.py (3 testes) | vermelho | verde | OK |
| tests/test_workspace_hooks.py::test_subagente_nao_sobe_baseline | vermelho | verde | OK |
| tests/test_staging_evidence_default.py::test_write_evidence_out_explicito_respeitado | verde | verde | FAIL: nao prova a mudanca (regressão: --out explícito já funcionava) |
| tests/test_workspace_hooks.py::test_tighten_check_e_coordenador_liberados | verde | verde | FAIL: nao prova a mudanca (regressão: liberação já valia) |
red_green: 34/36 OK
```

As 2 linhas FAIL são testes de regressão legítimos (comportamento que não pode mudar); aceitos
como `--allow-green` (os dois ids acima).

Mutações (cada uma revertida com `git checkout --`; `git status` limpo ao final):
- tirar `time.perf_counter` de `CLOCKS` → `test_detecta_relogio_com_alias` e `test_repo_respeita_baseline` vermelhos.
- `elif n > old` → `elif False` em `ruff_baseline.problems` → `test_contagem_nova_no_arquivo_baselinado_falha` e `test_tighten_recusa_crescimento` vermelhos.
- `_raises_baseline` do ruff devolvendo `False` → 2 casos de `test_subagente_nao_sobe_baseline` vermelhos.

## Verificação por ataque

1. Workflow: ordem `start` (id `stack`) → `test-db` → gate. O gate tem `!cancelled() && steps.stack.outcome == 'success'`, então roda mesmo com pgTAP vermelho; o passo pgTAP vermelho deixa o job vermelho (sem `continue-on-error`; `main` devolve rc 2 em `StackError`). Stack falha → pgTAP e gate pulados, job vermelho. Nenhum caminho verde com pgTAP falho. `supabase test db --local` existe na CLI e o código ainda confere `--local` no `--help` antes de rodar; recusa stack linkada.
2. Clock: ver P2-2. Renomear/mover teste da baseline gera "órfã" + "novo"; `--tighten` recusa por causa do "novo", então só o coordenador resolve com `--update` (conservador, correto). Arquivos via `git ls-files`, então teste não rastreado só entra no `git add`.
3. Ruff: uma violação nova da mesma regra em arquivo baselinado reprova ("cresceu"); arquivo/par novo reprova ("par novo"); violação removida exige `--tighten` ("folgada"/"órfão"). `ruff check .` limpo e `ruff_baseline.py --check` "current"; a linha removida de `guard_tools.py = ["BLE001"]` não desliga nada (o arquivo agora tem `# noqa: BLE001` pontual, regra ativa).
4. Hook: ver P2-3; falha aberto com `print` em stderr preservado (`main`, linhas 256-261).
5. Growth: compara `main:<arquivo>` com o worktree nas três baselines + pares do toml. `--ignore-new-files` só pula baseline ausente na `main` (criação); `size_budget.json` já existe na `main`, então não abre brecha para subir teto.
6. Defaults: nenhum default restante em `docs/` em `scripts/staging/*` (o teste varre); `.tmp/` é ignorado pelo git. Referências a caminhos antigos só em docs históricos/registro de risco (fatos passados) e nos dois runbooks do P2-1. `incident_drill` ganhou `--out` coerente com leitura do `prior`.
7. DECISOES_FIXAS: amostra de 5 linhas conferida (ver P2-4).

## Correções aplicadas

Nenhuma (revisor não edita código).

## Pendências

P2-1 a P2-4: follow-ups pequenos, podem entrar no pouso pelo coordenador ou em spec de docs.
pgTAP real no CI: coordenador valida após o push.

## Comandos rodados

```text
git diff main...HEAD --stat → 37 arquivos, +3157
bash scripts/dev/red_green.sh 416 → 34/36 OK (2 regressões verdes na main)
ruff check . / ruff_baseline.py --check / clock_asserts.py / baseline_growth.py → limpos
3 mutações + git checkout -- → vermelhas, status limpo
bash scripts/dev/pt.sh (10 arquivos do escopo) → 140 passed
```
