# 01 — Tokens e contexto

Revisão de 2026-10-19 sobre as 3 sessões do Claude Code deste workspace
(10-12 → 10-19; 912 MB de transcritos, 1 sessão coordenadora + 2 anteriores +
~270 transcritos de subagentes). Todos os números abaixo foram medidos nos
`.jsonl` ou no repo; a fórmula de estimativa de tokens é `chars / 3,5`
(pt-BR acentuado costuma ficar um pouco acima, então os valores são piso).

## 1. O que entra no contexto antes de qualquer trabalho

| Bloco injetado a cada sessão | Tamanho | Tokens (≈) | Observação |
|---|---|---|---|
| `CLAUDE.md` | 23,4 K chars | 6,7 K | metade é histórico de fases (ver `05`) |
| `@ESTADO_ATUAL.md` (linha `@` dentro do CLAUDE.md) | **145 K chars** em 10-15; **168 K chars hoje** | **41 K → 51 K** | 84 % de todo o conteúdo injetado; 172 KB em disco, 69 % anterior a outubro; só ~21 KB (12 %) são necessários ao iniciar |
| `MEMORY.md` (memória do usuário) | 1 K | 0,3 K | ok |
| `gitStatus`, e-mail, atribuição | 2,7 K | 0,8 K | ok |
| **Subtotal do primeiro user-message** | **172,7 K chars** | **≈ 49 K** | medido no primeiro `api-request-blob` da sessão `3422f347` |
| System prompt + schemas de ferramentas + listagem de **~140 skills** + instruções MCP + agentes | — | ≈ 78 K | diferença entre os 127.100 tokens da 1ª chamada e os ≈49 K acima |
| **Contexto na 1ª chamada, sem nenhum trabalho feito** | — | **127.100** | sessões anteriores: 115 K (10-12) e 100 K (10-15) |

Evidência: `3422f347…jsonl`, primeira linha `type=assistant` → `usage` = 127.100
tokens; `api-request-blob` nº 1 → conteúdo de 172.667 chars, com `# ESTADO_ATUAL.md`
ocupando os offsets 23.752 → 168.257.

O que isso custa: cada uma das 1.827 chamadas da sessão coordenadora releu esse
bloco (cache read). Só o histórico do `ESTADO_ATUAL.md` (~35 K tokens que não são
TL;DR nem "como rodar") somou **≈ 64 M tokens de cache-read** em 4 dias, sem
nenhuma utilidade para 99 % dos turnos.

### Listagem de skills (≈ 8–10 K tokens por sessão)

- 47 skills de usuário (`~/.claude/skills`) + 17 no projeto (`.claude/skills/`,
  **gitignored**) + plugins de marketplace (finance, legal, customer-support,
  product-management, enterprise-search, data, design, productivity, videodb,
  pdf-viewer, anthropic-skills).
- Dos 17 do projeto, **15 são skills de design visual** (brandkit, brutalist,
  impeccable, stitch, taste…) que nunca aparecem nos transcritos de trabalho;
  só `qa` e `wrap-up` são do produto.
- 24 servidores MCP listados "requerem autenticação" em toda sessão (Canva,
  Notion, HubSpot, Figma, Linear, Slack…) — texto morto no prompt.

## 2. Como o contexto cresce dentro da sessão

| Métrica (sessão coordenadora `3422f347`, 10-15 → 10-19) | Valor |
|---|---|
| Chamadas de modelo | 1.827 (todas Opus 5.5) |
| Contexto mediano / máximo | **572 K / 966 K** tokens |
| Dias vivendo acima de 900 K | 3 (10-16, 10-17, 10-18) |
| Compactações automáticas | **1** (10-17 00:54, após "response stopped arriving") |
| Tokens de saída totais | 1,6 M |
| Tokens de cache-read acumulados | **1,016 bilhão** |
| Razão cache-read : output | **≈ 630 : 1** |

Sessões anteriores: `8e18f089` chegou a 768 K e `8b2bbc3d` a 714 K, **zero**
compactações. O padrão é claro: a sessão nunca é compactada por escolha, só por
colapso.

### O pior desperdício isolado: o Stop hook do `/goal`

- `/goal` (10-16 03:57) instalou um Stop hook cuja condição ("executar até a
  SPEC-198 e commitar") não podia ser satisfeita sem o dono (chaves, texto legal).
- Resultado: **80 `stop_hook_summary`** (74 só em 10-18), 82 `goal_status`
  `met:false`, 7 avisos "A hook blocked the turn from ending 9 consecutive times",
  17 respostas literais "Continuo esperando você." e variantes.
- Custo: 80 re-invocações × ~570 K de contexto = **≈ 45 M tokens de cache-read**
  para produzir ~11 K tokens de texto, sem nenhum progresso. Na sessão `8b2bbc3d`
  o mesmo hook disparou 10 vezes em 19 segundos.

### Subagentes (212 transcritos da sessão coordenadora)

| Métrica | Valor |
|---|---|
| Modelos | Sonnet 99 · Opus 92 · `<synthetic>` 16 (mortos por limite de sessão) · Fable 3 · Haiku 2 |
| Soma dos contextos máximos | **46,2 M tokens** (média 218 K/agente; pico ~390 K) |
| Tokens de saída totais | 623 K (razão contexto:output ≈ 74:1) |
| Turnos de assistente / chamadas de ferramenta | 19.029 / 11.371 |
| Agentes com `sleep`/Monitor/espera | **91 de 212**; 317 `sleep` somando 2,2 h |
| "Command did not complete within 120s → moved to background" | **112 vezes em 76 agentes** |
| Execuções da suíte Python completa | **268 comandos, por 80 agentes** (64 parseáveis: 72 min de parede, mediana 10,7 min) |
| Resultados de ferramenta ≥ 10 K chars | 708 (6 %) = **41 % do volume** (12,1 M de 29,6 M chars) |
| `Read` sem `offset/limit` | 301 de 610 (49 %); 31 leituras > 1.000 linhas (`wallet.py` ×3, `storyteller.py`, `archivist.py` ×2, `App.tsx`, `combat.py`, `api.py`) |
| Bash como fração das chamadas | **81 %** (9.169); `cat/sed/head/tail` 7.896; `grep/find` 5.341 vs **Grep tool 71** |
| Leituras dos docs de orientação | `specs/index.yaml` 193 (96 agentes) · `ROADMAP.md` 79 (41) · `ESTADO_ATUAL.md` 71 (42) · `AGENTS.md` 20 (20) |

Padrões que inflam o contexto dos subagentes (com evidência):

1. **Esperar em vez de terminar.** Agentes encerram o turno com "Waiting on the
   full suite." e são reacordados por notificação: cada reacordar relê ~300 K de
   contexto. Sete agentes entregaram 2–3 hand-backs cada; cada hand-back chega
   **duas vezes** ao coordenador (mensagem + task-notification = 159 + 97 linhas
   injetadas).
2. **Spill de resultados.** `tool-results/` tem 35 arquivos (1,8 MB; dois de
   250 K). Subagentes depois **leram esses arquivos e até transcritos `.jsonl` de
   outros agentes** (181 chamadas de 59 agentes; leituras de 40–56 K chars).
3. **Leituras de arquivo inteiro** de 33–43 K chars (`agents/archivist.py`,
   `web/src/App.tsx`, `agents/storyteller.py`, `infrastructure/wallet.py`).
4. **Grep recursivo via Bash no OneDrive** ("Grep was slow (OneDrive); use the
   Grep tool", `a1e1b5ef`; "Too noisy from .tmp", `aa94fa50`).
5. **Logs sem teto**: `Supabase query_logs` devolveu 44 K e 33 K; `git add` com
   avisos CRLF rendeu o maior tool-result do coordenador (14 K).
6. **Screenshots de falha do Playwright** (`test-failed-1.png`) lidos 18 vezes.

### Prompts dos subagentes

- 164 spawns no coordenador: mediana **1.848 chars**, total 321.936 chars (≈ 80 K
  tokens só de prompt).
- 34 começam com "Leia e siga: <brief>" e 17 com "Leia primeiro o brief comum" —
  bom (o brief fica fora do prompt). Mas **~22 prompts de revisor Sol/Astra**
  repetem o mesmo papel/regras (~2 K chars cada ≈ 11 K tokens evitáveis).
- `subagent_type` sempre `general-purpose` (157/164); `isolation: worktree`
  **nunca usado** (0/164) — worktrees foram criados à mão via `wt.sh`.
- `brief_execucao.md` foi lido 39 vezes, `brief_autoria.md` 18 — repetem regras
  que já estão em CLAUDE.md/AGENTS.md (ver `05`).

## 3. Hooks e modos que custam tokens sem retorno

| Item | Evidência | Efeito |
|---|---|---|
| Caveman `UserPromptSubmit` | injetou "CAVEMAN MODE ACTIVE…" **235 ×**; `SessionStart` reinjeta o regulamento inteiro; hook estourou o timeout de 5 s 4 × (rodou 5,5–7 s) | As mensagens finais ao dono saem em português normal de qualquer jeito — o modo não comprimiu o que importa, mas custou ~1 K tokens por prompt |
| `silent_turn_reminder` | 14 | sinal de turnos longos de orquestração sem feedback |
| `/goal` Stop hook | ver acima | ≈ 45 M tokens perdidos |
| `settings.proposed.json` | existe no repo, **nunca foi aplicado** (não há `.claude/settings.json`); o hook `reindex-reminder.js` e o allowlist `uv run pytest` estão inativos | prompts de permissão e lembrete de reindex que o dono já desenhou, mas não valem |
| `.claude/settings.local.json` | 1 entrada de allow apontando para um script de scratchpad de sessão antiga | lixo |

## 4. Recomendações (ordenadas por impacto/esforço)

| # | Mudança | Ganho estimado | Esforço | Risco |
|---|---|---|---|---|
| T1 | **Encolher `ESTADO_ATUAL.md` para ≤ 8 KB** (TL;DR de 48 h + "como rodar" + limitações). Mover todo o histórico para `docs/historico/ESTADO_2026-10.md` + `CHANGELOG.md`. A regra já existe no `/wrap-up` ("manter ENXUTO ~5 KB") e foi ignorada: o arquivo cresceu 35× | **−38 K tokens por sessão iniciada e por subagente que o lê**; ~−60 M cache-read por sessão de 4 dias | 1 h | baixo — nada se perde, só muda de arquivo |
| T2 | **Não auto-carregar o histórico**: trocar `@ESTADO_ATUAL.md` no CLAUDE.md por "leia `ESTADO_ATUAL.md` ao retomar" (o arquivo já é curto após T1) ou manter o `@` só do arquivo enxuto | reforça T1; permite que o CLAUDE.md fique < 15 K chars | 10 min | nenhum |
| T3 | **`/goal` só com saída "bloqueado no humano"**: usar `/goal` apenas para metas que o agente consegue fechar sozinho; quando depender do dono, limpar a meta (`/goal clear`) ou escrever a condição com "ou até ficar bloqueado por decisão humana" | elimina os 80 turnos vazios (≈ 45 M tokens) | 0 (disciplina) | nenhum |
| T4 | **Compactar por marco**: `/compact <resumo do estado>` após cada spec pousar na `main` e `/clear` + handoff em arquivo entre ondas; nunca deixar a sessão viver dias acima de 500 K | contexto mediano cai de 572 K para ~250 K ⇒ cada chamada custa metade; menos "response stopped arriving" (15 ECONNRESET, 1 travamento de 10 h) | disciplina + 1 linha no CLAUDE.md | baixo |
| T5 | **Regra de ferramenta para subagentes**: `Read` com `offset/limit` em arquivos > 400 linhas; `Grep`/`Glob` em vez de `grep -r`/`find` via Bash; `Read` obrigatório antes de `Edit` (111 falhas "File has not been read yet" em 55 agentes); proibir ler `tool-results/`/`.jsonl` de outros agentes | −30 % do volume de tool-results (≈ 4 M chars ≈ 1,1 M tokens na onda) | 20 min (texto no brief/skill) | nenhum |
| T6 | **Nunca terminar turno "esperando"**: subagente roda suíte com `timeout` ≥ 900 s em foreground ou usa `Monitor` com condição, e só faz hand-back **uma vez**; coordenador não aceita 2º hand-back | −112 conversões para background, −91 agentes em loop de `sleep`, −~100 reacordares × 300 K | regra no brief + template de agente | baixo |
| T7 | **Suíte completa só no coordenador** (ou 1 vez por spec no fim): subagente roda só os testes do seu escopo + `--lf` | −~70 das 268 execuções completas por onda; −60 min de parede por onda | regra no brief | médio: detecta regressão cruzada mais tarde — mitigar com CI |
| T8 | **Podar skills/plugins**: tirar as 15 skills de design do `.claude/skills` do projeto (ou mover para `~/.claude/skills` desativadas) e desinstalar plugins não usados (finance, legal, customer-support, enterprise-search, videodb, pdf-viewer, productivity, data) | −6–8 K tokens por sessão **e** por subagente (cada um recebe a listagem) ⇒ ≈ −1,5 M tokens numa onda de 200 agentes | 15 min | nenhum |
| T9 | **Template de prompt de revisor/executor** (ver `03`): papel e regras num `agents/*.md` do projeto; o prompt só carrega "SPEC-NNN + worktree" | −11 K tokens de prompt repetido por onda; prompts de 2 K → 300 chars | 30 min | nenhum |
| T10 | **Caveman**: manter `lite` (ou desligar o `UserPromptSubmit` e deixar só o `SessionStart`) e subir o timeout do hook para 10 s | −235 injeções/sessão; 0 `hook_cancelled` | 5 min | nenhum |
| T11 | Aplicar (depois de revisar) o `settings.proposed.json` como `.claude/settings.json` versionado, sem o allow de scratchpad; ver `03` para a lista de permissões | menos prompts de permissão; lembrete de reindex RAG volta a funcionar | 10 min | baixo |

## 5. Números para acompanhar depois das mudanças

- Contexto na 1ª chamada de uma sessão nova: hoje **127 K**; meta **< 70 K**.
- Contexto mediano da sessão coordenadora: hoje **572 K**; meta **< 300 K**.
- Execuções de suíte completa por onda de 10 specs: hoje **~270**; meta **< 30**.
- `stop_hook_summary` sem progresso: hoje **80**; meta **0**.
- Resultados de ferramenta ≥ 10 K: hoje **41 % do volume**; meta **< 15 %**.

Como medir: os scripts dos ajudantes desta revisão ficaram em
`C:\Users\guilh\AppData\Local\Temp\claude\c--Users-guilh-OneDrive--rea-de-Trabalho-rpg-ia-master\3422f347-bfc9-4363-bbd6-73dd1453d495\scratchpad\miner_A\`,
`…\miner_B\`, `…\miner_C\` e `…\wsimprove\first_request.py` — vale promover a
versão limpa para `scripts/dev/transcript_stats.py` (proposta em `03`).
