# Auditoria do workspace — 2026-11-11

Somente leitura (Sonnet `audit-reader`, a pedido do dono), ao fim da onda 405–413. Pergunta: por que o
processo deixou passar os atritos do dia e qual a menor correção. Nada foi alterado por esta auditoria.
Decisões já tomadas em `auditoria-workspace-2026-11-03.md` e na SPEC-386 não são reabertas aqui.

## Atritos de 11/11 e correção mínima

| # | Atrito | Por que passou | Correção mínima |
|---|---|---|---|
| 1 | Auditoria por LLM reabriu 8 itens já decididos | não há índice de decisões; `audit-reader` não manda consultar | `docs/guias/DECISOES_FIXAS.md` (uma linha por item) lido por `audit-reader` e `spec-author` |
| 2 | Exit code de pytest mascarado por pipe | `/qa`, `/wrap-up`, `/spec-land` mandam `pytest … \| tail`; `pt.sh` acerta mas tem `-x` e `-n 2` fixos | skills usam o wrapper do item 3 |
| 3 | `-n auto` com pouca RAM: worker morto vira `FAILED` (12 falsos numa rodada) | nenhum wrapper escolhe `-n` pela RAM | `scripts/dev/full.sh`: `-n` pela RAM livre, exit code real, rerun dos ids de worker morto |
| 4 | Dois pytest simultâneos colidem no `basetemp` | `tests/conftest.py:53-56`: `pt-<sha1 do checkout>` igual para todo run | sufixo com PID + limpeza de `pt-*` antigo |
| 5 | `.venv` sem extras; `uv run` criou `.venv` dentro de worktree | `env.sh:14-18` prefere o venv do worktree; `AGENTS.md` ensina `uv sync` sem `--all-extras` | `env.sh` usa sempre o venv do principal em worktree; `wt.sh` avisa; doc com `--all-extras` |
| 6 | Testes com relógio real (rate card venceu; `test_prazo_real_por_thread`) | sem lint; ≥ 9 asserções de tempo de parede | catraca AST de `assert` com `perf_counter/monotonic/time.time`; baseline que só encolhe |
| 7 | `ruff format --check .` falhou por bloco Python em `.md` de spec | hook cobre só `.py`; `spec-author` sem shell | `specs/**` e `handoffs/**` fora do `ruff format`; `format --check` do diff no pré-pouso |
| 8 | Nome de handoff fora do lint | regex aceita `sol\|astra\|terra\|luna`; nada diz o papel do revisor Sonnet | mapa no `spec-reviewer.md` (Opus = sol, Sonnet = terra); coordenador passa o nome |
| 9 | `spec-author` sem shell errou contagem; `spec-executor` sem web bloqueou | `tools` dos agentes × o que a spec pede | `Bash` só leitura no `spec-author`; `<MEDIR: comando>`; `Requer: web` resolvido pelo coordenador |
| 10 | 3 bugs de cancelamento ao mover código para thread (SPEC-412) | `specs/TEMPLATE.md` sem seção de concorrência nem "o que não rodou" | template: tabela evento × estado × resultado; seção "Não rodou e por quê" |
| 11 | SQL e pgTAP revisados sem nunca rodar (413, 410) | `supabase/tests/*.sql` não é referenciado por nenhum workflow | passo `supabase test db --local` no `audit-local.yml` |
| 12 | Edições não commitadas de outra sessão impediram tocar `docs/guias/*` | `wt.sh land` só falha no fim | preflight em `wt.sh sync/land`: diff da branch ∩ arquivos sujos do principal |
| 13 | `migrations.py` sem `--out` sobrescreve `docs/spec191/evidence/` | `scripts/staging/common.py:118`: default versionado | default `.tmp/evidence/`; `docs/` só com `--out` |
| 14 | Gates novos (catraca de tamanho, `F401` em `api.py`, ruff `S`) fora do BRIEF | doc adiada pelo item 12 | uma linha em `.claude/agents/spec-executor.md`; BRIEF quando o checkout limpar |
| 15 | Sessão do coordenador > 450 K tokens; handoff improvisado em `.tmp/` | sem formato nem lugar padrão | `/estado --handoff` grava `.tmp/handoff-<data>.md`; hook de contexto aponta para ele |
| 16 | Revisão independente pegou todos os bugs graves; teste do executor, nenhum | BRIEF pede TDD, não classes de caso adverso | `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md`, alimentado a cada `CHANGES_REQUIRED` |

## Achados próprios

- B1: `guard_tools.py:95-97` nega qualquer comando de subagente com a palavra "pytest" e um `-n <número>` em
  qualquer lugar (falso positivo com `sed -n 80,200p … grep pytest`). Casar só quando o comando é pytest.
- B2: baseline do ruff é por arquivo × regra, não por contagem: arquivo baselinado aceita violação nova
  ilimitada da regra (`BLE001` em 135 arquivos, `C901` em 71). Comparar contagem.
- B3: `/spec-land` não confere RAM nem a existência do handoff de revisão quando `Risco` é médio/alto.
  `scripts/dev/land_check.sh NNN` reúne as pré-checagens.
- B4: `/qa` e `/wrap-up` mandam `-n auto`, que o hook nega em subagente: marcar "só coordenador".
- B7: `size_budget.py --update` (sobe) fica ao alcance do executor; revisor confere o diff do JSON.

## Proposta: três specs de workspace

- **W-A Pytest confiável:** `full.sh`, skills usando-o, `basetemp` por PID, venv único em worktree, B1.
- **W-B Pouso sem surpresa:** `land_check.sh` (preflight de colisão, `format --check`, handoff por risco),
  template com concorrência / "não rodou" / casos adversos, mapa de papel do revisor, `/estado --handoff`.
- **W-C Gates que cobram:** `DECISOES_FIXAS.md`, pgTAP no `audit-local.yml`, catraca de relógio em teste,
  default de `--out` fora de `docs/`, baseline do ruff por contagem.

Não fazer: lock entre sessões (o preflight resolve); web no executor (injeção de prompt); Postgres/Docker
local nesta máquina; `DTZ` global no ruff; hook que bloqueie todo `| tail`.

Preservar: `pt.sh`, catraca do `size_budget`, hooks da SPEC-386, `wt.sh`, regra de `-n 2`, `PIPESTATUS` no
CI, revisão proporcional ao risco, teto de 8 KB do `ESTADO_ATUAL.md`.

Não verificado: se `audit_local_gate.py` já exercita `supabase/tests`; demais scripts com saída default em
caminho versionado; bytes carregados por sessão; segurança de reusar o venv do principal em worktree.
