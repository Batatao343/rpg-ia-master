# SPEC-386 — Workspace: guardrails de qualidade e de tokens para os agentes

> **Status:** `done`
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** [auditoria do workspace 03/11](../docs/auditorias/auditoria-workspace-2026-11-03.md) · aprovação do dono 03/11 ("pode executar tudo"; refatoração fica nas 375–385)
> **Depende de:** nenhuma
> **Desbloqueia:** SPEC-375..385 rodam sob os guardrails (código novo já nasce sob gate)
> **EXECUTOR_MODEL:** coordenador (Opus) · **REVIEW_REQUIRED:** `true` (revisor independente, Sonnet)
> **EVAL_AUTHORING_REQUIRED:** `false` (não toca `evals/`)

## 1. Contexto & Objetivo

A auditoria do workspace (03/11) mediu 725 transcritos. Os subagentes geram 97 % do texto
que volta das ferramentas. O desperdício é evitável: `cat`/`Read` de arquivo inteiro de
50 KB, Edit sem Read (295 erros), pytest `-n auto` em subagente (200×), `cd` repetido e
CI consultado direto. No código, a geração não tem freio contra crescimento de god-file nem
contra helper duplicado.

Esta spec **não refatora produto**. Ela arma o entorno: hooks, wrappers, brief dos agentes,
gate de tamanho e radar de duplicação, para que as specs 375–385 e as seguintes rodem mais
baratas e não reintroduzam o que estão limpando.

## 2. Requisitos

- **R1 — Formatação por edição.** Hook `PostToolUse` (Edit|Write) roda `ruff format` e
  `ruff check --fix` no `.py` editado. Violação restante volta ao agente como contexto
  (≤ 10 linhas). Sem ruff disponível, não faz nada (nunca bloqueia).
- **R2 — Guarda de leitura.** Hook `PreToolUse`:
  - nega `Read` sem `offset`/`limit` em arquivo > 40 KB, sugerindo `Grep` + recorte;
  - nega `Read` de transcrito `.jsonl` em `~/.claude/projects/` e de `tasks/*.output`;
  - nega Bash `cat`/`type`/`Get-Content` sem recorte de arquivo > 40 KB.
- **R3 — Guarda de pytest.** O mesmo hook nega `pytest … -n auto` (ou `-n` > 2) quando
  o chamador é subagente (`agent_id` no stdin). O coordenador segue livre.
- **R4 — Wrappers.** `scripts/dev/pt.sh` (pytest enxuto, `-n 2`, log completo em arquivo,
  saída ≤ 60 linhas), `scripts/dev/cap.sh N cmd…` (teto de linhas para qualquer comando) e
  `scripts/dev/ram.sh` (RAM livre + pytest/python órfãos).
- **R5 — Spec por seção.** `spec_index.py show NNN [--section <título>]` imprime o
  cabeçalho e só a seção pedida.
- **R6 — Gate de tamanho.** `tests/test_size_budget.py` + `tests/size_budget.json`:
  arquivo de código > 1.000 linhas e função > 100 linhas só passam se estiverem na
  baseline, e nunca acima do valor dela. Encolher é livre. Gerador:
  `scripts/dev/size_budget.py [--update]`.
- **R7 — Radar de duplicação.** `scripts/dev/dup_helpers.py [--diff <rev>]` lista funções
  novas do diff cujo nome já existe em outro módulo de produção.
- **R8 — Aviso de sessão grande.** Hook `UserPromptSubmit` lê o `usage` do último turno
  (cauda do transcrito). Acima de 350 K tokens de contexto na sessão principal, injeta
  lembrete de `/compact`.
- **R9 — Brief e agentes.** `BRIEF_SUBAGENTE.md` ganha § Qualidade e § Eficiência.
  `spec-executor` roda `ruff format` + `check`. `spec-reviewer` ganha checklist de qualidade.
  `AGENTS.md` ganha § Convenções de qualidade (≤ 12 linhas, inclui revisão por risco e
  evidência de equivalência). `specs/TEMPLATE.md` ganha campos de risco e de evidência.
- **R10 — Allowlist.** `.claude/settings.json` cobre os wrappers e consultas recorrentes.
- **R11 — Medição.** `scripts/dev/agent_stats.py` (métricas dos transcritos, `--since`)
  fica versionado para medir antes/depois.

### Fora de escopo

- Refatorar god-files, helpers ou testes (SPEC-375..385).
- Novas regras do ruff + regerar `ruff-baseline.toml` (conflita com a R14 da SPEC-376;
  vira follow-up após 376).
- Enxugar o `AGENTS.md` (a SPEC-375 edita linhas dele; follow-up após 375).
- Teste anti-`_fold` (depende do `services/text.py` da SPEC-378).
- Mods e skills/plugins globais: ficam fora do repo (pasta de mods do usuário e
  `~/.claude`), registrados no relatório.

## 3. Design técnico

- **Arquivos novos:** `.claude/hooks/guard_tools.py` (R2, R3), `.claude/hooks/ruff_after_edit.py`
  (R1), `.claude/hooks/context_size.py` (R8) — stdlib, Python ≥ 3.11, saem com 0 em
  qualquer erro interno (hook nunca derruba sessão). `scripts/dev/{pt,cap,ram}.sh`,
  `scripts/dev/{size_budget,dup_helpers,agent_stats}.py`, `tests/size_budget.json`,
  `tests/test_size_budget.py`, `tests/test_workspace_hooks.py`.
- **Arquivos alterados:** `.claude/settings.json` (hooks + allowlist),
  `.claude/agents/spec-executor.md`, `.claude/agents/spec-reviewer.md`,
  `docs/guias/BRIEF_SUBAGENTE.md`, `AGENTS.md` (§ nova, sem tocar as linhas que a 375 cita),
  `CLAUDE.md` (fim: tipos de agente + instruções de compactação), `specs/TEMPLATE.md`,
  `scripts/spec_index.py` (subcomando `show`), `tests/test_spec_index.py`.
- **Protocolo dos hooks:** stdin JSON (`tool_name`, `tool_input`, `agent_id?`, `cwd`,
  `transcript_path`). Negação = stdout `{"hookSpecificOutput": {"hookEventName":
  "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": …}}`.
- **Escopo do gate de tamanho:** `git ls-files` `*.py`, `web/src/**/*.ts(x)`; fora `tests/`,
  `web/e2e/`, `evals/`, `playtest_runs/`. Chave de função: `caminho::Qual.nome`.

## 4. Plano passo a passo

1. Testes dos hooks (`tests/test_workspace_hooks.py`): subprocess com stdin JSON para cada
   caso de R1–R3/R8 (nega, permite, erro interno ⇒ permite).
2. Hooks + registro em `settings.json`.
3. Wrappers (R4) + `show` (R5, teste em `tests/test_spec_index.py`).
4. Gate de tamanho (R6): teste asserta baseline atual verde, crescimento ⇒ falha,
   arquivo novo > limite ⇒ falha (fixtures em `tmp_path`).
5. Radar (R7) e medição (R11).
6. Brief, agentes, AGENTS.md, CLAUDE.md, TEMPLATE (R9) e allowlist (R10).
7. Revisão independente; suíte completa 1×; pouso.

## 5. Critérios de aceite

- [x] R1–R3, R8: testes de hook verdes; teste vivo na sessão do coordenador.
- [x] R4/R5/R7/R11: rodam no checkout principal e no worktree.
- [x] R6: suíte verde com a baseline gerada; crescimento sintético falha.
- [x] R9/R10: textos curtos; `tests/test_agents_contract.py` e `test_dev_tooling.py` verdes.
- [x] `uv run pytest` verde (suíte completa offline).

## 6. Smoke test com LLM real

Não se aplica (tooling de desenvolvimento, sem caminho de LLM do jogo). O smoke é o teste
vivo dos hooks na sessão do coordenador após o pouso (Read grande negado, edição formatada).

## 7. Riscos & compatibilidade

- Revisão independente (Sonnet, papel terra): `APPROVED_WITH_FOLLOWUPS`
  ([handoff](../handoffs/SPEC-386-terra-review.md)). P2-1 (caminho Windows sem aspas) e P2-3
  (ruff no evals protegido) corrigidos com teste; P2-2 (heredoc multilinha) aceito; P2-4: a
  SPEC-375 deve localizar linhas do AGENTS.md por texto, não por número.
- Baseline de medição (subagentes, 27/10–03/11, `agent_stats.py --since 2026-10-27`):
  45 M chars de tool_result, 239 `cat` inteiro, 104 Edit sem Read, 43 Read > 40 KB sem limit.

- Hook com bug pode travar agentes: todos saem 0 em exceção e têm `timeout` 5–20 s.
- Gate de tamanho pode barrar specs em voo que engordam `api.py`: a mensagem orienta
  extrair para módulo novo; exceção justificada = atualizar `tests/size_budget.json` no
  commit com o motivo.
- Codex não lê `.claude/`: as convenções em `AGENTS.md` e o gate em teste valem para ele.
