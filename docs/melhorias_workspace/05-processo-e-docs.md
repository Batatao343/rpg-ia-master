# 05 — Processo e documentação

Foco: formato de `ESTADO_ATUAL.md`/`ROADMAP.md`, registro de numeração de specs,
`specs/index.yaml`, handoffs, `CLAUDE.md` × `AGENTS.md`, memória, higiene de
commits. Números medidos no worktree `b05932e` (main de 2026-10-19).

## 1. Diagnóstico com números

### Os dois documentos "obrigatórios" viraram o changelog

| Métrica | Valor |
|---|---|
| `ESTADO_ATUAL.md` | 172,6 KB · 2.218 linhas · **212** parágrafos `> **…` de status · ~51 K tokens |
| Parte realmente necessária ao iniciar (notas de 18/10 + "Como rodar" + convenção crítica + checklist) | **~21 KB (12 %)** |
| Conteúdo anterior a outubro | 118 KB (**69 %**) |
| Menções a contagem de testes | **102** (a regra "atualizar contagem" foi aplicada por *append*, não por substituição) |
| Regra escrita no `/wrap-up` (`.claude/skills/wrap-up/SKILL.md:21-24`) | "manter ENXUTO (~5 KB); detalhe vai para o CHANGELOG" → **34× acima** |
| `CHANGELOG.md` | parou nas sessões antigas: **0** parágrafos do ESTADO aparecem nele |
| `ROADMAP.md` | 142 KB · 1.813 linhas · ~42 K tokens · **~90 % histórico de entregas**, cabeçalho "Revisado 2026-09-27", sem lista "próximos" compacta (um único `> Próximo:` na linha 564) |
| Commits desde 01/10 que tocam ESTADO / ROADMAP | **113 / 113 de 296 (38 %)** |
| Commits docs-only desde 12/10 | **120 de 260 (46 %)** |

Causa raiz: a regra "Ao FINALIZAR … atualizar ESTADO_ATUAL.md **e** ROADMAP.md,
sempre" (`CLAUDE.md:349-352`). Com 10–15 specs/dia em worktrees paralelos, isso
gera:

- **Conflitos de rebase sempre nos mesmos 3 arquivos**: `ESTADO_ATUAL.md` ×2,
  `ROADMAP.md`, `specs/index.yaml` (14 `CONFLICT` reais no coordenador; 24
  textos "só nas linhas de status que a 227 e a 229 inseriram no mesmo ponto").
- **9 scripts de scratchpad só para isso**: `stateline.py` (22 execuções),
  `resolve_status.sh` (14), `resolve_docs.py` (12), `docs_edit.py`, `append.py`,
  `spec_update.py`, `resolve.sh` — todos com âncoras literais ("38 specs `draft`
  aguardando") e tratamento manual de CRLF.
- Toda sessão e todo subagente que "lê o topo do ESTADO" paga 40–50 K tokens.

### Numeração e registro de specs

| Métrica | Valor |
|---|---|
| Specs | **275** (`SPEC-001`…`SPEC-275`, sem lacunas, sem duplicatas, index em sincronia) |
| Status (index.yaml) | done 247 · draft 23 · in-progress 5 (cabeçalhos dizem in-progress 9 → deriva) |
| `specs/index.yaml` | **158 KB**, derivado do git, 15 campos por entrada, tocado em **117 de 296 commits (40 %)**, lido/grepado **193 vezes por 96 subagentes**, conflito em rebase |
| Regra de numeração | só prosa em `AGENTS.md:297` ("próximo ID nunca utilizado"); `CLAUDE.md:260` ainda diz `specs/<nome>.md` (estala, e é o arquivo que o Claude Code carrega) |
| Ferramenta de reserva de número | **nenhuma** (`promote.py` hardcoda `n = 218`) |
| Colisão observada | 10-15 19:26: "207 e 213 ambas propõem migração de save v8→v9" (duas sessões em paralelo no mesmo checkout) |
| `proximas-specs/` | 4,2 MB · 64 arquivos; os rascunhos SEC/BUG já foram promovidos a SPEC-218+ e os originais continuam lá |
| `handoffs/` | 85 arquivos; 5 padrões de nome e casing inconsistente (`SOL`/`sol`/`Sol`, `ASTRA`/`Astra`) |
| `docs/specNNN/` | 63 pastas de evidência; `docs/auditoria/` **e** `docs/auditorias/` coexistem |

### Commits e Project Index

| Métrica | Valor |
|---|---|
| Commits desde 28/09 | 296 |
| `chore: rebuild project index…` | **65–69 (22 %)** |
| Linhas alteradas em `project_index/` desde 12/10 | **482.520**; pasta de 12,5 MB |
| Commits que só mexem em project_index/index.yaml | 69 de 260 (27 %) |
| Commits/dia 15–18/10 | 31 · 72 · 61 · 72 (dos quais ~1/4 são rebuild de índice) |

### CLAUDE.md × AGENTS.md

- `AGENTS.md` = `CLAUDE.md` copiado (362 linhas idênticas) + bloco de 36 linhas
  "Operação de specs e evals" (ordem de retomada, integridade de eval, roteamento
  Luna/Terra/Sol/Astra, `MODEL_HANDOFF_REQUIRED`, long-runs opt-in).
- `CLAUDE.md` **não referencia** `AGENTS.md`; o Claude Code nunca vê essas regras
  — por isso os briefs as repetem a cada subagente.
- `CLAUDE.md:270-328` são changelog puro ("792/945/970/1001 testes" vs 3.842 hoje),
  `:8` "Fase 0 entregue; Fases 1–3 mapeadas", `:232` "30 nós" (são 35), `:25`
  "13 perfis" (são 14), `:245` lista testes que não existem mais, e a árvore de
  pastas não tem `evals/`, `infrastructure/`, `supabase/`, `workers/`,
  `observability/`, `project_index/`.
- Faltam no CLAUDE.md justamente as regras operacionais que o coordenador
  reenvia a cada brief: worktree por spec, `SPEC-NNN`, rebuild do índice,
  `handoffs/`, integridade de eval, "não leia ESTADO inteiro".

### Memória do usuário (`~/.claude/projects/…/memory/`)

| Arquivo | Estado |
|---|---|
| `project-index-clean-build.md` | válido e o mais valioso — devia ser skill/script do projeto, não memória |
| `env-setup.md` | válido; `.env` com `override=True` e "Bash não vê env do Windows" não estão no CLAUDE.md |
| `autonomia-specs-191-198.md` | válido só para aquela iniciativa (já encerrada) — expirar |
| `always-test-and-update-docs.md` | duplica CLAUDE.md + `/wrap-up` |
| `gemini-quota.md` | obsoleto (DeepSeek é o primário) |
| `gameplay-feedback.md` (06-26) | obsoleto (tudo entregue) |
| `cutover-conflito13-adiado.md` | obsoleto (épico concluído) |

## 2. Proposta

### P1 — ESTADO_ATUAL.md enxuto, com formato fixo (≤ 8 KB)

```
# ESTADO_ATUAL — <data>
## Estado em 10 linhas        (branch/sha, suíte N passed, staging sha, specs in-progress, último deploy)
## Próximos 3 passos
## Bloqueios no dono           (lista curta, cada item com "o que o dono faz")
## Decisões recentes (≤ 7 dias) (1 linha por spec `done`, gerada por script — ver P3)
## Como rodar                  (10 linhas + link docs/guias/AMBIENTE.md)
## Limitações conhecidas       (≤ 10 bullets)
```

- Mover **em bloco** as linhas 42–2037 para `docs/historico/ESTADO_ATUAL-ate-2026-10-18.md`
  (1 commit, sem reescrever nada). O `CHANGELOG.md` passa a receber 1 seção por
  dia de trabalho (`## 2026-10-19`), copiada do bloco "Decisões recentes".
- Trocar a regra do CLAUDE.md para: *"ESTADO: só substituir o TL;DR (nunca
  anexar). ROADMAP: só quando o plano muda."*

Ganho: −40 K tokens por sessão e por subagente orientado; some a família
`stateline/resolve_*`. Esforço: 1 h. Risco: baixo (histórico preservado).

### P2 — ROADMAP.md = plano, não diário

- Cabeçalho: tabela de fases (nome · status · spec-âncora · próximo marco) com
  ≤ 40 linhas; seção "Próximas 5 specs (ordem)" (hoje só existe em
  `proximas-specs/ORDEM_SPECS_2026-10-15.md`); backlog por tema.
- Entregas (`## ✅ ENTREGUE …`, linhas 618–1700) → `docs/historico/ROADMAP-entregas.md`.
- Resultado: ~12 KB. Atualizado quando o plano muda, não a cada spec.

### P3 — Status de spec tem UMA fonte: o cabeçalho da spec

- `specs/index.yaml` vira **gerado** (já é derivado do git) pelo passo de pouso:
  `python scripts/spec_index.py build` dentro de `wt.sh land`. Subagentes param
  de editar o arquivo à mão ("só o campo status; preserve CRLF" sai do brief).
- `python scripts/spec_index.py recent --days 7` gera o bloco "Decisões recentes"
  do ESTADO e a seção do CHANGELOG. Zero edição manual de linha de status.
- Ganho: some o conflito mais frequente da onda (index.yaml + 2 docs); −117
  commits/296 tocando o index.

### P4 — Registro de número de spec

- `python scripts/next_spec_id.py --slug <slug>`: lê `specs/`, `index.yaml`,
  **branches `spec-*` e worktrees abertos** (`git worktree list`,
  `git branch --list 'spec-*'`), devolve o próximo ID e cria o arquivo a partir
  do `TEMPLATE.md` com um commit de reserva na `main` ("spec: reserve SPEC-276
  <slug>"). Reserva antes do worktree = sem colisão entre sessões.
- Corrigir `CLAUDE.md:260` para a regra `SPEC-NNN-<slug>.md`.

### P5 — Handoffs e evidências com nome previsível

- Padrão único: `handoffs/SPEC-NNN-<papel>-<tipo>.md` com `papel ∈ {sol, astra,
  terra, luna}` minúsculo e `tipo ∈ {review, independent-review, eval-authoring,
  port-review}`; template em `docs/templates/handoff-review.md` (seções: escopo,
  veredito, achados P0/P1/P2, correções aplicadas, pendências, comandos rodados).
- Lint barato em `scripts/validate_content.py`: nome de handoff fora do padrão =
  aviso (não erro).

### P6 — CLAUDE.md como fonte única; AGENTS.md apontando para ele

- `AGENTS.md` (Codex) fica com o conteúdo completo; `CLAUDE.md` passa a ser
  `@AGENTS.md` + 10 linhas específicas do Claude Code (skills `/qa`, `/wrap-up`,
  subagentes). Um só arquivo para manter, dois leitores. Alternativa se o `@`
  não for aceitável: teste em CI `tests/test_docs_sync.py` que falha se
  `AGENTS.md` ≠ `CLAUDE.md` nas seções compartilhadas.
- Limpeza: remover `:270-328` (vira `docs/historico/`), corrigir os 6 itens
  estalados listados acima, acrescentar seção **"Fluxo de spec em 8 linhas"**
  (reserva de ID → worktree → TDD → suíte focada → land → index → ESTADO 10
  linhas → commit) e a regra "não leia ESTADO/ROADMAP inteiros; leia o TL;DR".

### P7 — Higiene de árvore e memória

- **Feito 19/10 (workspace-2):** movido para `docs/historico/proximas-specs/` (sem sufixo de data: caminho mais curto; nenhum link Markdown apontava para lá, só caminhos em texto, atualizados nas specs). Proposta original: `proximas-specs/` → `docs/historico/proximas-specs-2026-10-15/`
  (ou apagar os 18 rascunhos já promovidos). O `.zip` solto na raiz
  (`git status`: `?? docs/PROXIMA_ONDA…zip`) entra no hash do Project Index e
  deixou o CI vermelho 3× em 15/10 — adicionar `*.zip` da raiz/docs ao
  `.gitignore` ou movê-lo para fora do repo.
- `docs/descricao_projeto/` (15,9 MB de mp3/mp4/png) contradiz o commit
  `cfe21ce` "remove rendered MP4s" → Git LFS ou fora do repo.
- Unificar `docs/auditoria/` + `docs/auditorias/`.
- Memória: apagar 4 notas obsoletas; converter `project-index-clean-build` em
  skill (ver `03`); acrescentar ao CLAUDE.md as 2 dicas de `env-setup` que ele
  não tem.

### P8 — Project Index: rebuild dentro do pouso, não como commit separado

- `wt.sh land` → rebase → `project_index build` **na própria branch** → amend/
  commit único → ff. Elimina ~65 commits "chore: rebuild…" e os 482 K de diff
  separados. Se o `check` exigir árvore limpa, o build roda no worktree da spec
  (que já é limpo). Detalhe técnico em `04` § Project Index.

## 3. Ordem sugerida (1 dia de trabalho, sem tocar código de produto)

| Passo | Tempo | Depende de |
|---|---|---|
| P1 mover histórico do ESTADO + formato fixo | 1 h | — |
| P6 CLAUDE.md/AGENTS.md fonte única + limpeza | 1 h | P1 |
| P3 `spec_index.py build/recent` + tirar edição manual do brief | 2 h | — |
| P4 `next_spec_id.py` | 1 h | P3 |
| P8 index no `land` | 1 h | ver `04` |
| P2 ROADMAP enxuto | 1 h | P1 |
| P5 handoff template + lint | 1 h | — |
| P7 árvore/memória | 30 min | — |
