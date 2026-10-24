# rpg-ia-master — instruções do Claude Code

As instruções do projeto ficam em **um só arquivo**, `AGENTS.md` (lido também pelo
Codex), importado abaixo. Este arquivo só acrescenta o que é específico do Claude Code.
O conteúdo antigo daqui (cópia de `AGENTS.md` + changelog) está preservado em
`docs/historico/AGENTS-specs-entregues-ate-2026-10-19.md` e no histórico do git.

@AGENTS.md

---

## Específico do Claude Code

**Skills do projeto** (versionadas em `.claude/skills/`):
`/qa` (testes em camadas, token-lean) · `/wrap-up` (fim de tarefa) · `/spec-new` ·
`/spec-land` · `/estado` · `/reindex` · `/eval-publish` · `/staging-deploy` ·
`/status-dono` ("o que o dono precisa fazer").

**Subagentes** (`.claude/agents/`): use o tipo certo em vez de `general-purpose` —
`spec-executor` (Sonnet) implementa, `spec-reviewer` (Opus) revisa código que não
escreveu, `spec-author` (Opus) escreve spec, `code-locator`/`ci-watcher` (Haiku)
localizam código e vigiam CI, `audit-reader` (Sonnet) audita só leitura. O prompt
leva só `SPEC-NNN · worktree · decisões do dono`; regras comuns em
`docs/guias/BRIEF_SUBAGENTE.md`.

**Memória da máquina (regra do dono, 24/10 — máquina de 16 GB; já travou):**
- Não há teto fixo de agentes; o problema é **exagerar em rajada**. Dispare aos
  poucos, conforme o trabalho pede, e não abra muitos executores/revisores de uma vez
  só porque há vaga.
- Subagente **nunca** roda a suíte completa nem `-n auto`: só os testes do escopo,
  com no máximo `-n 2`. A suíte completa é do coordenador, **uma por vez**, no pouso.
- Antes de disparar executor/revisor e a cada marco: medir RAM livre
  (`Get-CimInstance Win32_OperatingSystem` → `FreePhysicalMemory`). Abaixo de
  ~3 GB, não dispara nada novo e enfileira.
- Depois de reinício de sessão ou agente morto: procurar e matar por PID (árvore,
  `taskkill /T /F /PID`) os `pytest`/`supabase status`/`python -` órfãos. Nunca
  `taskkill /IM python.exe`.

**Sessões longas (custo de contexto):**
- `/goal` **nunca** com condição que dependa do dono (chave, aprovação, texto legal,
  decisão). Se a meta pode travar no humano, escreva a condição com a saída
  "…ou até ficar bloqueado por decisão do dono" — ou não use `/goal`. Travou no
  dono: registre o bloqueio no `ESTADO_ATUAL.md` § Bloqueios e encerre o turno.
- `/compact <resumo do estado>` **a cada marco** (spec pousada na `main`, onda
  fechada). Entre ondas: handoff em arquivo + `/clear`. Não deixe a sessão viver
  dias acima de ~500 K de contexto.
- Comando > 2 min: `run_in_background` + timeout explícito; espere com uma
  notificação (nunca `sleep` em loop).

**Ambiente:** `.claude/settings.json` define `PYTHONUTF8=1`, o allowlist de comandos
de leitura/teste e o hook que lembra de reindexar o RAG ao editar lore.

@ESTADO_ATUAL.md
