# 03 — Skills, subagentes e automação do fluxo

Foco: transformar os rituais que o coordenador repetiu à mão (e os scripts que
ficaram no scratchpad da sessão) em skills/scripts versionados; definir tipos de
subagente com papel e modelo fixos; padrões de trabalho em worktree e de tarefas
em background.

## 1. O que existe hoje

| Item | Estado | Evidência |
|---|---|---|
| Skills do projeto | `qa`, `wrap-up` — **não versionadas** (`.gitignore:35` ignora `.claude/skills/`) e com o caminho do checkout principal hardcoded (`cd "c:/Users/guilh/OneDrive/…/rpg-ia-master"`) → quebram em worktree | `.claude/skills/qa/SKILL.md:11`, `wrap-up/SKILL.md:13` |
| Outras 15 skills no projeto | design visual (brandkit, impeccable, stitch, taste…), nunca usadas nas sessões de spec | `ls .claude/skills` |
| Tipos de agente | nenhum em `.claude/agents/`; 164 spawns = `general-purpose` (157), `Explore` 5, `Plan` 1, 1 `nonexistent-wait` | transcrito do coordenador |
| Hooks | `reindex-reminder.js` escrito, mas o `settings.proposed.json` nunca virou `settings.json` → inativo | `.claude/settings.proposed.json` |
| Worktree | `isolation: "worktree"` nunca usado (0/164); `wt.sh new/land/drop` à mão (83 chamadas) | scratchpad `wt.sh` |
| Rebuild do índice | `reindex.sh` no scratchpad (não versionado); memória `project-index-clean-build.md`; 65 commits "chore: rebuild project index" | `git log` |
| Briefs | 6 arquivos `brief_*.md` no scratchpad (3,7–6,4 KB), lidos 80× por subagentes; repetem regras de CLAUDE/AGENTS | miner B §7 |
| Pouso de spec | `wt.sh land` (10×) + `resolve_status.sh` (14×) + `resolve_docs.py` (12×) + `stateline.py` (22×) + `reindex.sh` | miner A §3 |
| Governança de eval | `gh variable set EVALUATOR_CHANGE_APPROVED` em loops `for t in 1 2 3`, `gh run watch`, unset — **10 ciclos**, 15–60 min cada | miner A §3 |
| Espera | 317 `sleep` (2,2 h), 228 `Monitor`, 66 `TaskStop`, 112 "moved to background after 120 s", 91/212 agentes em loop de espera | miner B §2, §6 |

## 2. Skills a criar (todas em `.claude/skills/<nome>/SKILL.md`, **versionadas**)

Pré-requisito: tirar `.claude/skills/` do `.gitignore` (manter ignoradas só as
15 de design, ou movê-las para `~/.claude/skills`).

| Skill | O que faz | Substitui | Modelo/efeito |
|---|---|---|---|
| **`/spec-new <slug>`** | reserva o próximo `SPEC-NNN` (`scripts/next_spec_id.py`), cria o arquivo do `TEMPLATE.md`, commit de reserva na `main`, cria worktree `spec-NNN` fora do OneDrive com junção de `web/node_modules`, imprime o caminho | `wt.sh new` + numeração manual + `promote.py` | evita colisão 207/213 |
| **`/spec-land NNN`** | no worktree: `ruff check` nos arquivos tocados → `pytest` focado → rebase na `main` → regenera `specs/index.yaml` e `project_index` **na própria branch** → suíte completa 1× (background com `timeout` longo) → ff na `main` → remove worktree | `wt.sh land` + `resolve_*` + `stateline.py` + `reindex.sh` + commit separado de índice | −65 commits de índice; −48 execuções de scripts de conflito |
| **`/estado`** | regenera o bloco "Decisões recentes" do `ESTADO_ATUAL.md` a partir de `specs/index.yaml` (`spec_index.py recent --days 7`), atualiza contagem de testes **substituindo** a linha, data e sha; abre diff para o coordenador revisar | edição manual de 2 docs em cada spec | mantém ESTADO ≤ 8 KB |
| **`/qa`** (corrigir) | sem `cd` hardcoded (usa `git rev-parse --show-toplevel`); `uv run --frozen pytest -q -x --lf` por default; opção `--full` em background com `timeout 1200` e `Monitor` | — | funciona em worktree |
| **`/wrap-up`** (corrigir) | mesmo caminho relativo; chama `/estado`; CHANGELOG por dia; `git add` seletivo; `caveman-commit` | — | — |
| **`/eval-publish NNN`** | fluxo de governança: confirma que só `evals/` mudou, `gh variable set EVALUATOR_CHANGE_APPROVED=1` (com retry), push, `gh run watch` do workflow correto, unset da variável, resumo em ≤ 5 linhas; exige confirmação explícita do dono antes de ligar a variável | 10 ciclos manuais de 15–60 min | ver `04` § governança |
| **`/reindex`** | `project_index build` em worktree limpo de `HEAD` + `check`; commit só se mudou | `reindex.sh` + memória `project-index-clean-build` | — |
| **`/staging-deploy`** | `scripts/staging/*` + `vercel_env.py` + `/health` sha + `e2e_session` (ver `04`) | ~24 chamadas `vercel` + 17 `scripts/staging/*` por sessão | — |
| **`/status-dono`** | gera a lista "o que o dono precisa fazer" (bloqueios, abas para abrir, chaves) a partir de `ESTADO_ATUAL.md § Bloqueios` — o dono pediu isso ≥ 6× ("me fala em que momento estamos", "o que eu tenho que fazer") | listas feitas à mão a cada pedido | — |

Esforço total: ~4 h (os scripts já existem no scratchpad; é parametrizar o
caminho do repo e versionar).

## 3. Tipos de subagente (`.claude/agents/*.md`)

Hoje todo spawn é `general-purpose` com um prompt de ~2 K chars que repete o
papel. Com tipos definidos, o prompt vira "SPEC-NNN + worktree".

| Agente | Modelo | Ferramentas | Papel (frontmatter `description`) | Regras fixas no corpo |
|---|---|---|---|---|
| `spec-executor` | **Sonnet** | todas menos `Agent` | implementa UMA spec no worktree indicado | TDD; `Read` antes de `Edit`; `Grep`/`Glob`, não `grep -r`; nunca editar `evals/`, `project_index/`, `ESTADO`, `ROADMAP`, `index.yaml`; suíte **focada**; hand-back **único** ≤ 20 linhas; nunca terminar turno "esperando" |
| `spec-reviewer` | **Opus** (papel Sol/Astra) | `Read`, `Grep`, `Glob`, `Bash` só leitura + pytest focado | revisão técnica independente; veredito APPROVED / CHANGES_REQUIRED | não deixa processo em background ao devolver (8 casos de revisor preso 60–95 min esperando testes que ele mesmo disparou); escreve `handoffs/SPEC-NNN-<papel>-review.md` pelo template |
| `spec-author` | **Opus** | `Read`, `Grep`, `Write` só em `specs/` | escreve spec `draft` a partir de achados | usa `TEMPLATE.md`; não numera (recebe o ID reservado) |
| `code-locator` | **Haiku** | `Read`, `Grep`, `Glob` | localiza símbolos/arquivos; devolve caminhos + linhas, sem dumps | ≤ 15 linhas |
| `audit-reader` | **Sonnet** | só leitura | auditoria read-only (segurança/bugs) com achados numerados | nunca lê `.env`; nunca lê transcritos `.jsonl`/`tool-results` |
| `ci-watcher` | **Haiku** | `Bash` (`gh`) | acompanha 1 run do GitHub até concluir, com `gh run watch --exit-status`; devolve conclusão + job falho | 1 chamada, sem `sleep` em loop |

Escolha de modelo (dados da onda): Sonnet entregou as specs com 1,6–15 K tokens
de saída; Opus foi usado em 92 agentes, incluindo **execução** ("Leia e siga…")
onde Sonnet bastaria — só revisão/autoria pedem Opus. Haiku foi usado 2× (SQL),
e é o modelo certo para localizar código e vigiar CI.

Padrão de prompt (≤ 300 chars):

```
SPEC-231 · worktree /c/Users/guilh/AppData/Local/Temp/claude/rpg-spec-231 ·
decisões do dono: default da §8 · entregue hand-back único.
```

## 4. Padrões de worktree e de background

| Regra | Por quê (evidência) |
|---|---|
| Worktrees sempre em `%LOCALAPPDATA%\Temp\claude\rpg-<spec>` (fora do OneDrive); clones nunca dentro do repo (`.tmp/spec176-clone` → "dubious ownership", `Permission denied`, pastas `.pytest-spec*` indeletáveis) | miner C §6 |
| `web/node_modules` por junção (já no `wt.sh`); `uv` com `UV_PROJECT_ENVIRONMENT` do checkout principal (já feito 102×) — **colocar em `.envrc`/script**, não no prompt | 3 agentes caíram em `ERR_MODULE_NOT_FOUND` em worktree novo |
| Um worktree por spec **e** por sessão de Claude: duas sessões no mesmo checkout geraram "34 commits à frente que não são meus" e a colisão 207/213 | miner C §6 |
| Caminhos longos: `proximas-specs/pacote-prompts-…/13-jev-investiga-o-futura-somente-com-justificativa.md` fez `git worktree add` falhar com "Filename too long" (2 agentes) → `git config core.longpaths true` + encurtar nomes | miner B §4 |
| Comando > 2 min: **sempre** `run_in_background: true` + `timeout` explícito, ou foreground com `timeout: 900000`; nunca deixar o harness converter aos 120 s e depois fazer `sleep 5` em loop (112 conversões, 317 `sleep`) | miner B §2 |
| Esperar resultado = `Monitor` com condição (arquivo FIN, `gh run watch`), 1 chamada; não encerrar turno "Waiting." (reacordar custa ~300 K de releitura) | miner B §6 |
| Subagente entrega **um** hand-back; coordenador ignora o 2º (7 agentes mandaram 2–3) | miner A §4 |
| Fan-out ≤ 6 agentes simultâneos: a auditoria de 15/10 (16+ agentes de uma vez) bateu no limite de sessão e matou 16 agentes `<synthetic>` | miner B §1 |
| Subagente não lê `tool-results/`, `.jsonl` de outros agentes nem `tasks\*.output` (181 chamadas; leituras de 40–56 K) | miner B §7 |

## 5. Hooks e permissões (proposta de `.claude/settings.json` versionado)

Base: o `settings.proposed.json` existente, revisado:

- `permissions.allow`: `Bash(uv run --frozen pytest*)`, `Bash(uv run --frozen ruff*)`,
  `Bash(git status*)`, `Bash(git diff*)`, `Bash(git log*)`, `Bash(git worktree list)`,
  `Bash(gh run list*)`, `Bash(gh run view*)`, `Bash(npm run build)` — a skill
  `/fewer-permission-prompts` do Claude Code gera essa lista a partir dos
  transcritos; rodá-la uma vez.
- `hooks.PostToolUse` (`Edit|Write`): manter o `reindex-reminder.js` (RAG) e
  acrescentar um lembrete equivalente para `specs/**` → "regenerar index.yaml
  no land" (ou nada, se P3 de `05` tornar o index gerado).
- `hooks.Stop`: **não** usar `/goal` com condição que dependa do dono (ver `01`).
- Caveman: `SessionStart` só; `UserPromptSubmit` com timeout 10 s ou desligado.

## 6. Scripts a versionar em `scripts/dev/`

| Script | Origem | Ajuste |
|---|---|---|
| `wt.sh` → `scripts/dev/wt.sh` | scratchpad | `MAIN=$(git rev-parse --show-toplevel)`; `core.longpaths`; `--no-junction` opcional |
| `reindex.sh` → `scripts/dev/reindex_clean.sh` | scratchpad | idem; sem commit automático quando chamado pelo `land` |
| `next_spec_id.py` | novo (ver `05` P4) | — |
| `spec_index.py build/recent` | novo (ver `05` P3) | substitui edição manual + `stateline.py` |
| `transcript_stats.py` | `miner_A/B/C` desta revisão | medir contexto/tokens/erros por sessão (base para acompanhar as metas de `01`) |
| `land.sh` | `wt.sh land` + `resolve_docs.py` (até P3 existir) | — |

Risco geral: baixo — nada aqui altera o produto. O ganho composto estimado por
onda de 10 specs: **−60 a −90 min de parede** (pousos, índice, governança) e
**−2 a −3 M tokens** (prompts, leituras de orientação, esperas).
