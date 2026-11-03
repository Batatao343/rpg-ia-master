# Auditoria do workspace Claude Code — 2026-11-03

Objetivo: preparar o workspace (hooks, skills, plugins, mods, prompts, guardrails) para que,
ao executar as specs de refatoração SPEC-375..385 e depois delas, o código gerado nasça
mais limpo, com menos retrabalho e menos tokens. Nada foi alterado nesta auditoria.

Método: 3 subagentes (Sonnet: transcritos; Sonnet: qualidade/guardrails; Haiku: doc oficial
de mods/hooks/plugins) + inventário direto de `.claude/`, `~/.claude/` e tamanhos de contexto.
O 4º agente (inventário Haiku) caiu no limite de 5 h da conta; o coordenador cobriu.
Script de métricas dos transcritos: scratchpad desta sessão (`transcript_stats.py`), reutilizável.

---

## 1. Resumo executivo

1. **Os subagentes são 97 % do volume de contexto de ferramenta** (102 M de 107 M chars em
   713 sessões de subagente vs 12 principais). O ganho de eficiência está no brief, nos
   wrappers e nos hooks que os subagentes usam — não na sessão principal.
2. **Custo dominante é a sessão longa**: 3 sessões (20/10, 15/10, 27/10) = 82 % dos 2,44 bi de
   `cache_read`; uma delas tem 3.590 turnos a ~230 K tokens por turno. A regra "compact por
   marco" existe no CLAUDE.md mas não é forçada por nada.
3. **Qualidade do código novo é razoável**; o problema é estrutural: god-files crescem
   (`api.py` 7.965 linhas, `combat.py` 3.661, `conflict_orchestrator.py` 2.999,
   `storyteller.py` 2.720) e helpers se duplicam (87 `def _fold` fora de `tests/`) porque
   não há gate de tamanho, não há mapa de helpers e o ruff roda com 6 famílias de regra.
4. **Contexto fixo por turno**: `AGENTS.md` 23 KB + `ESTADO_ATUAL.md` 7 KB + `CLAUDE.md` 2 KB
   (~8–9 K tokens) + descrições de ~100 skills (47 globais + plugins claude.ai de finanças,
   jurídico, suporte, PM, design, vídeo…) carregadas em toda sessão sem uso neste projeto.
5. **Mods** são viáveis já (Claude Code 2.1.314 ≥ 2.1.287): um único mod de "guarda de tool
   call" substitui 4 hooks e um painel "cockpit" resolve RAM/órfãos/bloqueios/specs num lugar só.

## 2. O que funciona bem (manter)

- Fluxo de spec (`/spec-new` → worktree → TDD → `/spec-land` → `/estado`) e status no cabeçalho
  da spec como fonte única; `spec_index.py` como gerador.
- Subagentes tipados com modelo certo (`code-locator`/`ci-watcher` Haiku, executor Sonnet,
  reviewer/author Opus), prompts curtos (11–21 linhas) apontando para `BRIEF_SUBAGENTE.md`.
- `Grep` disciplinado: nenhum resultado > 20 KB sem `head_limit` em 3.693 usos.
- 64 % dos comandos de subagente já usam `| head/tail`; 73 % dos pytest usam `-q`.
- Testes-guardrail que vigiam convenções (`test_no_silent_except`, `test_mecanica_orfa`,
  gate de flags SPEC-340, lints de conteúdo 349/350/360) — o padrão certo, só falta ampliar.
- `ruff-baseline.toml` por arquivo: dívida congelada "só encolhe".
- Memória do projeto (`memory/`) com decisões do dono; `ESTADO_ATUAL.md` ≤ 8 KB com gate.

## 3. Achados

### 3.1 Transcritos (eficiência)

| # | Achado | Número |
|---|---|---|
| T1 | `cat` de arquivo inteiro em subagente (spec, lore, scratchpad) | 19,5 M chars = 28 % do Bash dos subagentes |
| T2 | `Read` de 50–56 KB sem offset (SPEC-302 3×, SPEC-312, `styles.css`, `brekmar.yaml`, transcritos `.jsonl` de outras sessões) | top-20 resultados, todos Read |
| T3 | Erro "File has not been read yet" em `Edit` | 295 em subagentes (85 % dos erros de Edit) + 28 "modified since read" |
| T4 | pytest em subagente com `-n auto` (viola regra de RAM) | 200 execuções; saída de pytest 3,2 M chars |
| T5 | Prefixo `cd "<caminho>"` em 6 grafias diferentes | ~4.700 comandos; quebra allowlist |
| T6 | `sleep N` em loop manual apesar do hook que bloqueia | 1.266 comandos, 17 bloqueios; 31 erros de `Monitor` mal chamado |
| T7 | `gh run` chamado direto por subagente em vez de `ci-watcher` | 944 chamadas, 17 falhas de rede |
| T8 | `Agent` sem tipo do projeto (`general-purpose` 206 + sem tipo 65) | 45 % das 603 chamadas; `code-locator` 0× |
| T9 | Consulta de RAM com o mesmo `powershell -c "(Get-CimInstance…"` repetido | 422 vezes |
| T10 | Sessões principais > 2.000 turnos | 3 sessões = 82 % do cache_read |
| T11 | Negações do classificador de auto mode | 13 + 14 sem veredito; allowlist desatualizado |

### 3.2 Qualidade de código (o que a geração repete)

| # | Causa raiz | Evidência |
|---|---|---|
| Q1 | God-file sem gate de tamanho; toda feature engorda o mesmo arquivo | `api.py` 7.965, `agents/combat.py` 3.661, `conflict_orchestrator.py` 2.999, `storyteller.py` 2.720, `world_utils.py` 1.944, `llm_setup.py` 1.928; `types.ts` 1.260, `App.tsx` 1.141 |
| Q2 | Helper duplicado por subagente que não sabe que já existe | 87 `def _fold` fora de tests; variantes `_fold_text`, `_fold_hostile`, `_last_human_text` 3× |
| Q3 | Função longa em código recente (sem regra no prompt) | `round_log.py` 4 funções > 60 linhas; `prologue.py` 3; `loot_node` 276 linhas |
| Q4 | `# noqa: BLE001` decorativo (regra não está em `select`) | `prologue.py:419,522,675,687`, `opening_threads.py:231,389,447`, `loot.py:555` |
| Q5 | Ruff com só `E4,E7,E9,F,B,I,UP`; sem C901/PLR/SIM/BLE | violações atuais: C901 322, PLR0912 184, PLR0915 114, SIM 101, BLE001 436 |
| Q6 | Executor roda `ruff check` mas não `ruff format`; CI roda `format --check` | `spec-executor.md:14`; `validate.yml:61-62` |
| Q7 | Idioma misto em identificadores (`custo_folego` × `_fold`) sem convenção escrita | — |
| Q8 | Reviewer sem checklist de qualidade (tamanho, duplicação, god-file) | `spec-reviewer.md` passo 4 |

### 3.3 Tooling do workspace

- **Hooks do projeto**: só `reindex-reminder.js` (PostToolUse Edit|Write). Nenhum guard de Read,
  de pytest, de ruff, de tamanho de resultado, de turnos.
- **Skills do projeto**: 9 enxutas (19–38 linhas, boas). `taste` (1.207 linhas) e `impeccable`
  (168) são skills genéricas de frontend copiadas para o repo; a descrição entra em todo turno
  e o corpo de `taste` é o maior arquivo de `.claude/`. Mover para `~/.claude/skills` ou apagar.
- **Skills globais**: 47 (superpowers completo, caveman ×7, ponytail ×6, docx/pptx/xlsx,
  brag, slack-gif, algorithmic-art…). Plugins claude.ai ligados: finance, legal,
  customer-support, product-management, enterprise-search, data, design, videodb,
  pdf-viewer — ~60 skills/tools sem uso aqui, 11 servidores MCP exigindo auth a cada sessão.
- **Allowlist**: 17 entradas; não cobre `git -C`, `gh run watch`, `bash scripts/dev/*.sh`
  genérico, `uv run python scripts/spec_index.py`.
- **Contexto fixo**: `AGENTS.md` 23 KB (doc oficial recomenda < 200 linhas de CLAUDE.md);
  blocos que são histórico/referência: tabela de ROUTES com notas datadas, bloco de
  structured output do smoke 2026-07-06, árvore de pastas de 90 linhas, seção RAG/persistência.

## 4. Recomendações (prioridade = impacto ÷ custo)

### P0 — fazer antes de executar SPEC-375..385 (1 sessão, "onda 0 do workspace")

1. **Hook PostToolUse `ruff format` + `ruff check --fix` no `.py` editado** (Edit|Write).
   Fecha Q6, reduz retrabalho de CI. Script Python stdlib em `.claude/hooks/`.
2. **Hook PreToolUse de leitura**: nega `Read` sem `offset/limit` em arquivo > 40 KB e qualquer
   Read de `~/.claude/projects/**/*.jsonl`; nega `Bash` que comece com `cat ` em `specs/`,
   `lore_nova/`, `data/codex/`, `data/*.json`. Fecha T1/T2 (≈ 25 M chars evitados).
3. **Hook PreToolUse de pytest**: em subagente (`agent_id` no stdin), nega `-n auto` e
   exige `-q`; sugere `scripts/dev/pt.sh`. Fecha T4.
4. **`scripts/dev/pt.sh`** (pytest `-q -x --tb=line -n 2`, saída cortada em 60 linhas, resto
   em arquivo), **`cap.sh`** (limita qualquer comando a N linhas) e **`ram.sh`** (1 linha). Fecha
   T4/T9 e parte de T1.
5. **`spec_index.py show NNN --section plano|criterios`** e executor recebe só essas seções.
   Fecha T2 (specs de 55 KB lidas 3×).
6. **`BRIEF_SUBAGENTE.md` § Qualidade + § Eficiência** (≤ 12 linhas): Grep antes de criar
   helper; função ≤ 60 linhas; god-file não cresce; `ruff format`+`check` antes do hand-back;
   `noqa` só de regra ativa; **Read antes de Edit, inclusive arquivo que você criou via Bash**;
   sem `cd` (cwd já é o worktree); sem `sleep`; CI é do `ci-watcher`; pytest via `pt.sh`.
   Fecha T3/T5/T6/T7 e Q2/Q3.
7. **`spec-reviewer.md` passo 4 + checklist de qualidade**: função nova > 60 linhas; helper já
   existente (`git grep "def _"`); `git diff --stat` em god-file; `except` largo; teste que só
   afirma o mock. Fecha Q8.
8. **Allowlist** via `/fewer-permission-prompts` com os prefixos reais (`py.sh`, `pt.sh`,
   `git -C`, `gh run`, `spec_index.py`). Fecha T11.

### P1 — guardrails automáticos (junto com 375/376/378, que já mexem nesses arquivos)

9. **`tests/test_size_budget.py` + `size-baseline.json`**: falha se `.py`/`.tsx` de produção
   passar de 1.000 linhas fora da lista, ou se arquivo da lista **crescer**; função > 100
   linhas via `ast`. Não bloqueia o legado, impede crescimento. Fecha Q1.
10. **Ruff: ligar `C901` (max-complexity 15), `SIM`, `PERF`, `C4`, `PIE`, `RET`, `ERA`, `BLE001`**
    e rodar `ruff_baseline.py` uma vez. Novo arquivo nasce sob regra; legado isento. Não ligar
    agora `E501`, `PLR2004`, `T20`, `ARG`, `PLR0913`, `N`. Fecha Q4/Q5.
11. **`docs/guias/HELPERS.md`** (gerado por script: nome, módulo, 1 linha) + teste que falha em
    novo `def _fold*`/`_norm*` fora de `services/text.py` após a SPEC-378. Fecha Q2 para sempre.
12. **`AGENTS.md` § Convenções de qualidade** (≤ 10 linhas; texto no §5 abaixo).

### P2 — contexto e processo

13. **Enxugar `AGENTS.md` para < 200 linhas** (~−4 K tokens por turno em toda sessão e
    subagente): mover ROUTES detalhado, notas de structured output, árvore de pastas e RAG/
    persistência para `REFERENCE.md`/`docs/guias/`, deixando 1 linha + link cada.
14. **`.claude/rules/*.md` com `paths`**: regras de `web/**` só carregam ao tocar o frontend;
    regras de `agents/**` e `services/**` idem. Alternativa oficial a inflar o AGENTS.md.
15. **Hook `Stop` que avisa a cada 150 turnos** sem `/compact` e **hook `PreCompact`** que
    injeta o resumo padrão (estado, spec ativa, bloqueios). Fecha T10.
16. **Tipos de agente**: `general-purpose` só com justificativa; `code-locator` para localizar;
    `model` sempre explícito (regra já em memória). Fecha T8.
17. **Plugins/skills**: desligar em claude.ai os plugins finance, legal, customer-support,
    product-management, enterprise-search, data, videodb, pdf-viewer (nenhum uso neste repo).
    Nas skills globais, mover para `skills-disabled`: brag, brag-slim, slack-gif-creator,
    algorithmic-art, canvas-design, theme-factory, internal-comms, mcp-builder,
    web-artifacts-builder, docx/pptx/xlsx (ligar sob demanda). Manter superpowers só com
    `test-driven-development`, `systematic-debugging`, `verification-before-completion`,
    `requesting-code-review`, `using-git-worktrees`; caveman e ponytail ficam (ponytail-review
    é útil nas specs 376/378). Mover `taste`/`impeccable` do repo para global ou apagar.
18. **Instalar**: plugin de language server (`code-intelligence`: pyright/typescript) do
    marketplace oficial — navegação por símbolo e erro de tipo pós-edição sem rodar nada;
    `code-review` já está disponível como skill (usar `/code-review medium` no pouso).

### P3 — mods (customização do Claude Code; `plugin-authoring`, hot reload com permissão do dono)

| Mod | O que faz | Substitui |
|---|---|---|
| **guard** (`tool.call`) | nega Read > 40 KB sem limit, Read de `.jsonl`, `cat` de spec/lore, `-n auto` em subagente; `$.ui.log` quando resultado > 8 KB | hooks 2 e 3 (um módulo TS em vez de 3 scripts) |
| **cockpit** (pane) | RAM livre, órfãos `pytest`/`python -`, bloqueios do dono (lê `ESTADO_ATUAL.md`), `spec_index.py summary`, specs `in-progress`; atualiza por `$.clock` | `ram.sh` manual, `/status-dono` para olhada rápida |
| **token meter** (status line) | tokens de cache/turno via `turn.step`; aviso em 150 turnos | hook `Stop` do item 15 |
| **ask destrutivo** (`$.ui.ask`) | pergunta antes de `git reset --hard`, `taskkill /IM`, `worktree remove --force` | prompt manual |
| **brief injector** (`prompt.compose`) | injeta § Qualidade do BRIEF só em sessões de executor/reviewer (`agent_type`) | repetir texto nos .md dos agentes |

Ordem sugerida: guard → cockpit → token meter. Cada um ≈ 1 h; validar com
`claude plugin validate` + `claude plugin test`. Hooks clássicos (P0) continuam valendo onde
o mod não carregou (`claude -p`, CI).

## 5. Texto pronto para `AGENTS.md` (≤ 10 linhas)

```
## Convenções de qualidade
- Função ≤ 60 linhas; arquivo novo ≤ 600. God-files (api.py, agents/combat.py,
  agents/storyteller.py, services/conflict_orchestrator.py, web/src/App.tsx, types.ts)
  não crescem: código novo vai em módulo próprio (gate: tests/test_size_budget.py).
- Helper genérico (fold de texto, leitor de flag, JSON com cache, structured output):
  Grep antes; um só dono em services/ (docs/guias/HELPERS.md). Nunca recopiar.
- ruff format + ruff check rodam por edição (hook) e antes do hand-back.
- except Exception só com log ou `# silent-ok: motivo`; noqa só de regra ativa.
- Docstrings/comentários em português; identificadores novos em inglês.
- Teste novo no arquivo do módulo; estado e LLM falsos via tests/factories (SPEC-379).
```

## 6. Ordem de execução proposta

1. Onda 0 (workspace, 1 sessão): itens 1–8 + 17 + spec curta `SPEC-NNN-workspace-guardrails`
   (hooks, wrappers, brief, allowlist). Medir: chars de tool_result por subagente antes/depois
   com `transcript_stats.py`.
2. Mods guard + cockpit (1 sessão), quando o dono responder "Turn them on".
3. Onda 1: SPEC-375/376/378 com itens 9–12 dentro (ruff, size budget, HELPERS.md).
4. Onda 2: 377/379/381/382 (god-files) já sob o gate de tamanho.
5. Itens 13–15 (contexto) em qualquer brecha; ganho imediato em todas as sessões.

## 7. Limitações

- Tokens de subagentes não somados (usage em arquivos separados); a proporção 97 % é por
  chars de tool_result.
- Contagens do ruff: `--isolated`, só produção, aproximadas; sem aplicar o baseline.
- Tamanho de função medido em 5 arquivos recentes; duplicação medida só para `_fold`/`_last_human_text`.
- Hooks propostos não foram testados no Windows nesta sessão (nome do campo `file_path` do
  Read: confirmar com `/hooks`).
- "Toast" como superfície de mod não consta na doc oficial; a skill local oferece `$.ui.toast`;
  `$.ui.log` é a alternativa documentada.

## 8. Execução (03/11, aprovada pelo dono)

- **Feito (SPEC-386, `done`):** itens 1–7, 10 (allowlist), 9 (gate de tamanho), radar de
  duplicação (`scripts/dev/dup_helpers.py`), medição (`scripts/dev/agent_stats.py`), revisão por
  risco + campo `Evidência` no TEMPLATE, aviso de contexto (hook) e instruções de compactação.
- **Feito fora do repo:** 13 skills globais → `~/.claude/skills-disabled/global-2026-11-03/`;
  7 plugins synced desligados só neste projeto; `pyright-lsp` instalado (escopo local);
  mod `~/.claude/mods/rpg-cockpit` (painel) validado e com `tsc` limpo.
- **Adiado por conflito com a onda:** enxugar AGENTS.md (após 375), regras C901/SIM/PERF/BLE001
  no ruff (após 376), teste anti-`_fold` (após 378). `taste`/`impeccable` mantidas (escolha do dono).
- **Mod guard:** não feito; os hooks clássicos cobrem o mesmo e valem também em `claude -p`.
- **Baseline para comparar:** subagentes 27/10–03/11 = 45 M chars de tool_result, 239 `cat`
  inteiro, 104 Edit sem Read, 43 Read > 40 KB sem limit.
