# Melhorias do workspace — revisão de 2026-10-19

Revisão independente (Fable + 5 ajudantes Sonnet, só leitura) sobre **como este
workspace gasta tokens e tempo**: histórico completo das 3 sessões do Claude Code
(10-12 → 10-19; 912 MB de transcritos, ~270 subagentes), scripts do scratchpad
do coordenador, `CLAUDE.md`/`AGENTS.md`/`ESTADO_ATUAL.md`/`ROADMAP.md`,
`.claude/`, Ruff/pytest/CI/Playwright, `project_index/`, governança de evals,
memória do usuário. **Nada foi alterado** fora desta pasta; tudo aqui é proposta
com evidência, esforço e risco.

## Os 5 números que resumem o problema

| Número | O que significa |
|---|---|
| **127.100 tokens** de contexto na 1ª chamada da sessão, antes de qualquer trabalho | `ESTADO_ATUAL.md` (172 KB, 69 % anterior a outubro) é injetado inteiro via `@` no CLAUDE.md; mais ~140 skills listadas |
| **1,016 bilhão** de tokens de cache-read para **1,6 M** de saída (630 : 1) na sessão coordenadora | contexto viveu 3 dias acima de 900 K, 1 compactação em 4 dias; subagentes somaram 46 M de contexto para 623 K de saída |
| **80 turnos vazios** do Stop hook do `/goal` ("Continuo esperando você") ≈ 45 M tokens | meta que dependia do dono não tinha saída "bloqueado no humano" |
| **268 execuções da suíte completa** (6–11 min cada) por 80 subagentes numa onda | mais 112 estouros de 120 s, 317 `sleep`, 91 agentes em loop de espera |
| **65 commits "chore: rebuild project index"** (22 %) + 113 commits tocando ESTADO/ROADMAP (38 %) + 14 conflitos nos mesmos 3 arquivos | o processo de pouso de spec é manual e colide nos arquivos de status |

## Top 10 recomendações (impacto ÷ esforço)

| # | Recomendação | Ganho estimado | Esforço | Arquivo |
|---|---|---|---|---|
| 1 | **Encolher `ESTADO_ATUAL.md` para ≤ 8 KB** (TL;DR 48 h + como rodar + bloqueios); histórico em bloco para `docs/historico/`; regra "substituir, nunca anexar" | **−40–50 K tokens** por sessão iniciada **e** por subagente que o lê (42 agentes na onda); ~−60 M cache-read por sessão longa | 1 h | `01`, `05` P1 |
| 2 | **`/goal` nunca com condição que dependa do dono** + **`/compact` por marco** (após cada spec pousar) + `/clear` entre ondas com handoff em arquivo | −45 M tokens dos 80 turnos vazios; contexto mediano 572 K → < 300 K (cada chamada custa metade) | 0 (disciplina) + 1 linha no CLAUDE.md | `01` T3–T4 |
| 3 | **Status de spec com uma fonte só**: `specs/index.yaml` gerado no pouso (`spec_index.py build`), bloco "decisões recentes" do ESTADO gerado (`recent --days 7`); subagente não edita index/ESTADO/ROADMAP | fim dos conflitos em index.yaml/ESTADO/ROADMAP e dos 9 scripts de scratchpad (48 execuções); −117 commits/296 tocando o index | 2 h | `05` P3 |
| 4 | **Project Index**: hash só de arquivos rastreados + rebuild dentro do `/spec-land` (+ parar de commitar o grafo de 12,7 MB) | −65 commits, −482 K linhas de diff, 0 CI vermelho por arquivo solto, fim do ritual "worktree limpo" | 1 h (+1 h) | `04` C3 |
| 5 | **Suíte em camadas + `pytest-xdist`/`timeout`**: subagente roda só o escopo; completa 1× por spec no coordenador em background com `timeout` longo | −60–70 min de parede e −~200 execuções por onda; 667 s → ~3 min local | 30 min + brief | `04` C1–C2 |
| 6 | **Tipos de subagente** (`spec-executor` Sonnet, `spec-reviewer` Opus, `code-locator`/`ci-watcher` Haiku) com regras fixas: `Read` antes de `Edit`, `Grep` tool, hand-back único, nunca terminar "esperando", não ler transcritos de outros agentes | −111 erros de Edit, −11 K tokens de prompt repetido, −30 % do volume de tool-results, −~100 reacordares × 300 K | 2 h | `03` §3–4 |
| 7 | **Fim de linha e encoding**: `.gitattributes` `*.md`/`text=auto eol=lf`, `.editorconfig`, `autocrlf=false`, `longpaths`, `PYTHONUTF8=1`, `py.sh` | −363 avisos CRLF (118 agentes), −30 agentes com `cp1252`, −27 `No module named`, −2 worktrees falhando; scripts sem `\r\n` manual | 30 min | `02` L3 |
| 8 | **Governança de evals em 1 clique**: `EVALUATOR_CHANGE_APPROVED` como variável permanente do environment, autoria de evals em lote por onda, `/eval-publish` que imprime o comando de aprovação para o dono | 10 ciclos de 15–60 min → ~5 min + 1 clique | 30 min | `04` C4 |
| 9 | **Skills versionadas** (`/spec-new`, `/spec-land`, `/estado`, `/reindex`, `/eval-publish`, `/staging-deploy`, `/status-dono`) + `.claude/settings.json` aplicado (hoje só `proposed`) + podar 15 skills de design e plugins não usados | −83 chamadas manuais de `wt.sh` por onda; −6–8 K tokens de listagem por sessão e por subagente; prompts de permissão a menos | 4 h (scripts já existem no scratchpad) | `03` §2, §5 |
| 10 | **Ruff incremental** (`F`,`B`,`I`,`UP` + per-file-ignores) + pre-commit + `npm run typecheck`/eslint | 445 achados de classe-bug visíveis em 2 s (hoje só na suíte); bloqueia mídia > 500 KB e marcador de conflito antes do commit | 3 h | `02` L1, L4, L5 |

Bônus (barato, 1 h): `CLAUDE.md` como fonte única com `AGENTS.md` (hoje 362
linhas duplicadas, regras de eval/modelo só no AGENTS que o Claude nunca lê,
changelog nas linhas 270–328, 6 itens estalados) e limpar 4 notas obsoletas da
memória — `05` P6–P7.

Ganho composto estimado por onda de 10 specs: **−2 a −3 M tokens de contexto
dos subagentes, −60 M+ de cache-read do coordenador, −2 a −3 h de parede** e
~40 % menos commits.

## Índice

| Arquivo | Conteúdo |
|---|---|
| [01-tokens-e-contexto.md](01-tokens-e-contexto.md) | O que entra no contexto (medido), crescimento por sessão, Stop hook do `/goal`, subagentes (contexto, esperas, leituras), hooks caveman/settings, 11 recomendações T1–T11, metas numéricas |
| [02-linters-e-checks.md](02-linters-e-checks.md) | Ruff (contagem por família de regra), tipagem, `ruff format`, CRLF/encoding/longpaths, pre-commit, tsc/eslint no web |
| [03-skills-e-subagents.md](03-skills-e-subagents.md) | Skills a criar (de `wt.sh`/`reindex.sh`/`stateline.py`…), tipos de agente com modelo, padrões de worktree e background, `settings.json`, scripts a versionar |
| [04-testes-e-ci.md](04-testes-e-ci.md) | Suíte (4.145 testes, durações reais), camadas, xdist, Playwright entre worktrees, Project Index no CI, aprovação `eval-governance`, cache/filtros/dependabot |
| [05-processo-e-docs.md](05-processo-e-docs.md) | Formato de ESTADO/ROADMAP, fonte única de status, registro de número de spec, handoffs, CLAUDE.md × AGENTS.md, memória, higiene da árvore, ordem de execução |

## Ordem sugerida (2 dias, sem tocar código de produto)

1. Dia 1 manhã: #1 ESTADO enxuto → #7 CRLF/encoding → #9 settings + skills
   `/spec-new`/`/spec-land` (com #3 e #4 dentro do `land`).
2. Dia 1 tarde: #6 tipos de subagente + brief versionado → #5 camadas + xdist.
3. Dia 2: #8 governança → #10 Ruff/pre-commit/typecheck → bônus CLAUDE.md/AGENTS.md.
4. Depois de 1 onda com tudo ligado: medir de novo com `scripts/dev/transcript_stats.py`
   (metas em `01` §5) e decidir se vale parar de commitar `repo_graph.json`.

## Método e limites

- Transcritos lidos por script (`json.loads` linha a linha), nunca inteiros;
  contagens por padrão de texto podem incluir falsos positivos quando o padrão
  aparece em arquivos lidos por um agente (ex.: "CONFLICT" como identificador de
  código) — os números citados usaram padrões estritos onde isso importava.
- Tokens estimados por `chars / 3,3–3,5`; o tokenizador real em pt-BR tende a
  dar mais. Os tokens de contexto por chamada vêm de `message.usage` (exatos).
- Dados pessoais vistos nos transcritos (CPF/nome em mensagens do dono de 17/10)
  e segredos de `.env` **não** foram copiados para cá.
- Os scripts de medição ficaram no scratchpad desta sessão
  (`…\3422f347-…\scratchpad\miner_A|miner_B|miner_C|miner_E|wsimprove\`); valem
  ser promovidos a `scripts/dev/transcript_stats.py`.
