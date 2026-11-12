# SPEC-415 — workspace-pouso-sem-surpresa

> **Status:** `in-progress`
> **Criada:** 2026-11-12 · **Atualizada:** 2026-11-12
> **Depende de:** SPEC-414 (`done` antes deste pouso: as duas mexem em `.claude/skills/spec-land/SKILL.md` e `scripts/dev/wt.sh`, ver §7.1).
> **Desbloqueia:** nada direto. É a proposta W-B de `docs/auditorias/auditoria-workspace-2026-11-11.md:42-43`, executada por decisão do dono (12/11, delegada ao coordenador).
> **Risco:** `médio`. Não é `baixo` porque `wt.sh sync`/`land` é o caminho por onde **toda** spec chega à `main` (um falso negativo faz pouso errado; um falso positivo trava a onda; ver memória "land pode falhar silencioso e drop apaga a branch") e porque `wt.sh ci` faz `git push` de branch. Nenhum código de produto. Revisor Sonnet (`spec-reviewer`, papel `terra`).
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet) · **EVAL_AUTHORING_REQUIRED:** `false`
> **Evidência:** (a) `tests/test_wt_sh.py::test_sync_fails_on_collision_with_dirty_main` roda o `wt.sh` real num repositório temporário: hoje `sync` sai 0 com o arquivo sujo no principal, depois sai 1 e lista o arquivo; (b) `tests/test_workspace_hooks.py::test_context_size_points_to_handoff_file` falha hoje (a mensagem não cita `.tmp/handoff-`); (c) `tests/test_workspace_docs.py::test_ruff_format_excludes_specs_and_handoffs` falha hoje (`pyproject.toml:71` não tem `specs/**`/`handoffs/**`); (d) `land_check.py`, `red_green.py` e `handoff.py` são novos: os testes unitários deles falham por ausência do módulo e, além disso, cada um tem um caso que reproduz um atrito real de 11/11 (§4).

---

## 1. Contexto & Objetivo

A onda 405–413 de 11/11 pousou nove specs, e cinco atritos de processo apareceram só no fim, quando já custavam caro. (1) Edições não commitadas de outra sessão no checkout principal impediram tocar `docs/guias/*`, descoberto só no `ff` (auditoria item 12; `wt.sh:99-104`: `land` faz `sync` e `merge --ff-only` sem olhar o principal; o mesmo problema forçou o desvio registrado em `specs/SPEC-407-size-budget-catraca.md:3`). (2) `ruff format --check .` falhou por bloco Python dentro de `.md` de spec (item 7; `pyproject.toml:71` só exclui evals e contratos e2e). (3) `/spec-land` não confere RAM nem a existência do handoff de revisão quando `Risco` é médio/alto (B3; `.claude/skills/spec-land/SKILL.md:11-14`, que só olha status, árvore limpa e `ruff check`). (4) A revisão independente pegou todos os bugs graves e os testes do executor nenhum (item 16): só na SPEC-412 foram três bugs de cancelamento (`handoffs/SPEC-412-terra-review.md:7-33`), e o template não tem seção de concorrência nem de "o que não rodou" (item 10; `specs/TEMPLATE.md` não tem nenhuma das duas). (5) A sessão do coordenador passou de 450 K tokens e o handoff foi improvisado em `.tmp/` (item 15; `.tmp/handoff-semana-seguranca-2026-11-11.md` acumulou 8 seções "Atualização"), e o hook de contexto não diz onde gravar (`.claude/hooks/context_size.py:63-66`).

Há também dois atritos de papel: o nome do handoff do revisor Sonnet ficou fora do lint porque nada diz que Sonnet é `terra` (item 8; `scripts/check_handoff_names.py:18-19` aceita só `sol|astra|terra|luna`, e `.claude/agents/spec-reviewer.md:21` não dá o mapa), e o `spec-author` sem shell errou uma contagem enquanto o `spec-executor` sem web travou (item 9; `.claude/agents/spec-author.md:5` não tem `Bash`). Por último, a evidência "teste que falha antes" é hoje uma saída colada pelo executor no hand-back (`SPEC-407:68`, "evidência no hand-back"), que o revisor não reproduz (`spec-reviewer.md:12` manda só rodar testes focados na branch).

Objetivo: pôr as pré-checagens do pouso num lugar só (`scripts/dev/land_check.sh NNN`), executadas cedo (`wt.sh sync`) e de novo no `land`; dar ao template as seções que teriam pego os bugs de 412; criar o guia de casos adversos que o revisor pede, alimentado por ele mesmo; fazer o revisor **reproduzir** o vermelho/verde; fixar o formato do handoff de sessão; e deixar desenhado, desligado por padrão, o CI pré-pouso para `Risco: alto`. É a correção mínima de cada item da auditoria, sem lock entre sessões e sem web no executor (`auditoria…:47`, "Não fazer").

## 2. Requisitos

Linhas citadas = `main` em `ef5d1607`.

### Bloco A — `land_check` (itens 7, 12, B3)

- **R1 — Ponto único.** `scripts/dev/land_check.sh NNN [--only <check>[,<check>]]` é um invólucro fino (`bash scripts/dev/py.sh scripts/dev/land_check.py "$@"`) e toda a lógica fica em `scripts/dev/land_check.py` (testável em Python, sem bash nos testes unitários). Roda no worktree da spec (`wt.sh path NNN`) e descobre o principal como `wt.sh:21` (`git worktree list --porcelain`, 1ª entrada). Saída: uma linha por check, `OK|WARN|FAIL <check>: <detalhe>`; rc 0 se nenhum `FAIL`, 1 se algum, 2 para uso errado (spec inexistente, branch inexistente). Checks: `collision`, `format`, `ram`, `review`, `measure`, `ci`, nessa ordem; todos rodam mesmo após um `FAIL` (relatório completo numa passada).
- **R2 — `collision`.** Conjunto B = `git diff --name-only main...spec-NNN` (rodado no worktree). Conjunto D = caminhos de `git -C <principal> status --porcelain -z --untracked-files=normal` (modificados, adicionados, renomeados nos dois lados do rename, e não rastreados). Entrada de D terminada em `/` (diretório não rastreado colapsado, como `?? docs/descricao_projeto/aulas/` no status atual) colide com todo caminho de B que comece com ela. `FAIL` lista B ∩ D com a frase "o `ff` da main vai recusar; commite/descarte no principal ou tire da branch". Caso vazio: `OK`.
- **R3 — `collision` também no `sync`.** `wt.sh sync` chama `land_check.sh NNN --only collision` **depois** do rebase e do commit de índice (`wt.sh:72-86`), de modo que `specs/index.yaml` entra em B. `FAIL` faz o `sync` sair 1 (a branch fica rebaseada e com o commit de índice; nada é desfeito). `wt.sh land` chama `land_check.sh NNN` (todos os checks) entre o `sync_branch` e o `merge --ff-only` (`wt.sh:100-103`); `FAIL` → não faz o `ff`, sai 1.
- **R4 — `format`.** Arquivos `.py` de B que existem na branch (exclui deletados): `ruff format --check --force-exclude <arquivos>`. O `--force-exclude` é obrigatório: sem ele, caminho passado explicitamente ignora o `exclude` do `pyproject.toml` e os evals protegidos (`pyproject.toml:71`) seriam cobrados. Nenhum `.py` em B → `OK (nada a checar)`. `FAIL` lista os arquivos e o comando de correção.
- **R5 — Specs e handoffs fora do `ruff format`.** `[tool.ruff.format].exclude` (`pyproject.toml:71`) ganha `"specs/**"` e `"handoffs/**"`. `ruff format --check .` na `main` depois do pouso não lista nenhum arquivo nessas pastas. Medido (12/11): ruff 0.17.4, `1994 files already formatted`; a exclusão é preventiva (`docs/spec415/medicoes.md` item 1).
- **R6 — `ram`.** Lê a saída de `bash scripts/dev/ram.sh` (`scripts/dev/ram.ps1:3`: `RAM livre: {0:N1} GB de …`, separador decimal da cultura do Windows, vírgula em pt-BR). Livre < `RPG_LAND_MIN_RAM_GB` (default `3.0`, o "~3 GB" de `CLAUDE.md` § Memória) → `FAIL` com o valor; sem conseguir ler → `WARN` (não bloqueia). Processos `pytest`/`python` órfãos listados pelo `ram.sh` → `WARN` com os PIDs. `RPG_LAND_SKIP=ram` transforma o `FAIL` em `WARN "ram ignorada (RPG_LAND_SKIP)"`, para as sessões em que o dono libera o piso (memórias `sem-trava-ram-*`). `RPG_LAND_SKIP` só aceita `ram` e `ci`; outro valor → rc 2.
- **R7 — `review`.** Lê `Risco` do cabeçalho da spec (`> **Risco:** \`<valor>\``, primeiro valor entre crases; o texto literal do template `` `baixo` | `médio` | `alto` `` conta como **não preenchido**). Não preenchido → `FAIL`. `baixo` → `OK (sem revisor obrigatório)`. `médio` → exige ao menos um `handoffs/SPEC-NNN-<papel>-review.md` ou `…-independent-review.md` na branch, com nome aceito por `scripts/check_handoff_names.py:18-19`. `alto` → idem, mas o papel tem de ser `sol` ou `astra` (Opus; AGENTS.md § Qualidade: `alto` → `spec-reviewer` obrigatório). Em ambos: o **último** veredito do arquivo (última ocorrência de `APPROVED_WITH_FOLLOWUPS|APPROVED|CHANGES_REQUIRED`, com ou sem crase e com ou sem `> **Veredito:**`, porque `handoffs/SPEC-412-terra-review.md:3` e `:62` usam formatos diferentes) não pode ser `CHANGES_REQUIRED`; e o arquivo tem a seção `## Evidência verificada` (R20) não vazia.
- **R8 — `measure`.** A spec não pode conter marcador de medição pendente (R15): `<MEDIR:` que **não** esteja precedido de crase. A menção em código inline (como nesta frase) não conta, para que specs que falam da convenção, como esta, possam pousar. Encontrado → `FAIL` com as linhas.
- **R9 — `ci` (desligado por padrão).** Só para `Risco: alto`. Com `RPG_WT_PUSH` diferente de `1`: `WARN "CI pré-pouso desligado (aguarda autorização do dono para push de branch); registre em 'Não rodou e por quê'"`. Com `RPG_WT_PUSH=1`: consulta `gh run list --workflow audit-local.yml --branch spec-NNN --json headSha,conclusion,status,event --limit 10` e exige um run com `headSha` = `git rev-parse spec-NNN`, `event` = `workflow_dispatch`, `conclusion` = `success`. Ausente, em curso ou falho → `FAIL` com o estado e o comando `wt.sh ci NNN`. `gh` ausente com `RPG_WT_PUSH=1` → `FAIL`. Risco ≠ `alto` → `OK (não exigido)`.
- **R10 — `wt.sh ci NNN`.** Subcomando novo. Sem `RPG_WT_PUSH=1`: imprime "push de branch desligado: precisa de autorização permanente do dono (ver SPEC-415 §7)" e sai 3, sem tocar o remoto. Com `RPG_WT_PUSH=1`: `git -C <wt> push --force-with-lease origin spec-NNN` (a branch é rebaseada a cada `sync`), `gh workflow run audit-local.yml --ref spec-NNN`, e imprime o sha e a linha para o `ci-watcher` (`gh run list --commit <sha> …`, `.claude/agents/ci-watcher.md:9`). Nunca empurra `main`. O `workflow_dispatch` já existe (`.github/workflows/audit-local.yml:5`) e, sem `before`, `scripts/ci_docs_only.py:38` trata a base vazia como "não é só docs": o run é completo, como queremos.

### Bloco B — template, guia de casos e revisão (itens 8, 9, 10, 14, 16)

- **R11 — Template.** `specs/TEMPLATE.md` ganha:
  - no cabeçalho: `> **Requer:** nada | web: <o que buscar> | staging | dono: <o quê>` e `> **Domínios de revisão:** <0+ de: concorrência, sql-rls, api, persistência, llm-structured>`;
  - seção `## Invariantes` (entre Requisitos e Design): o que nunca pode ser falso antes, durante e depois da mudança, cada um com o teste que o prova;
  - seção `## Concorrência` (depois de Design): tabela `| Evento | Estado no momento | Resultado esperado | Teste |`, com a regra escrita no próprio template: "preencha quando a spec cria ou muda thread, `asyncio`, cancelamento, timeout, retry ou lock; caso contrário escreva `N/A — sem thread/async/cancelamento`". Exemplo de linha no template, tirado de 412: `cancelamento durante await to_thread(finance.admit) | ticket admitido no thread, evento ainda não anexado | finish espera o admit e registra evento cancelled | test_cancelar_durante_admit`;
  - seção `## Não rodou e por quê` (depois do Smoke): lista do que a spec pedia e não foi executado (SQL sem Postgres, smoke sem chave, CI desligado), com motivo e quem roda depois. Foi o caso de 410 e 413 (`handoffs/SPEC-410-sol-review.md:145`: "Migração, pgTAP e `test_rls_effective.py` nunca rodaram").
  As seções antigas ficam na mesma ordem e com o mesmo título (nenhuma spec existente precisa mudar; `scripts/spec_index.py:40` só lê `Status`).
- **R12 — `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md`.** Uma seção `## <domínio>` para cada um dos 5 domínios de R11, na ordem; cada seção com no máximo 12 linhas de item (`- `), cada item terminando com a fonte entre parênteses (`(SPEC-412 P1)`, `(AGENTS.md)`). Semeado com os itens do §3.3 (achados reais dos handoffs 410–413). Cabeçalho do guia com 3 regras: (a) o executor de spec `médio`/`alto` lê as seções dos `Domínios de revisão` da spec antes de escrever o primeiro teste e cobre cada item aplicável ou o marca "não se aplica" no hand-back; (b) a cada `CHANGES_REQUIRED`, o revisor acrescenta **uma** linha no domínio do achado mais grave; (c) seção cheia (12) → o revisor funde dois itens parecidos em vez de passar do teto.
- **R13 — Union merge.** `.gitattributes` ganha `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md merge=union`, para que duas branches que acrescentam linha no mesmo domínio não parem o `rebase_main` de `wt.sh:37-65` (que só autorresolve `specs/index.yaml` e `project_index/`).
- **R14 — `spec-reviewer.md`.** (a) Mapa de papel: "Opus → `sol` (ou `astra`, quando o pedido é checkpoint conceitual ou semântica de evaluator); Sonnet → `terra`; Haiku não revisa. O coordenador passa o papel no prompt; sem papel, use o do seu modelo." (b) Novo passo: rodar `bash scripts/dev/red_green.sh NNN` (R18) e colar a tabela em `## Evidência verificada` do handoff. (c) `CHANGES_REQUIRED` → acrescentar a linha do R12(b) em `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` no worktree revisado (por isso `tools` ganha `Edit`); o revisor continua sem editar código. (d) O passo 4 atual (`spec-reviewer.md:14-15`) passa a dizer "e os itens dos `Domínios de revisão` da spec no guia de casos".
- **R15 — `spec-author.md`.** `tools` ganha `Bash`, com a regra no corpo: "Bash só leitura: `git log/show/diff/grep`, `wc`, `bash scripts/dev/py.sh scripts/spec_index.py summary|show|check`, `size_budget.py` sem `--update`/`--tighten`, `ruff check` sem `--fix`. Nada que escreva fora da spec, nada de rede, nada de pytest." E a convenção: "número que você não mediu vai como `<MEDIR: comando>`; o coordenador (ou a Etapa 0 do executor) troca pelo valor antes de `approved`; `land_check` reprova spec com `<MEDIR:` sobrando (R8)." E: "spec que depende de fato externo (preço, versão de API, doc de terceiro) declara `Requer: web: <o quê>`".
- **R16 — `spec-executor.md`.** Três linhas novas: (a) "Gates que reprovam no pouso: catraca de tamanho (`size_budget.py`, `--tighten` ao encolher), `F401` fora da baseline em `api.py` (SPEC-406), ruff `S` em código de produto (SPEC-411 R4b, `pyproject.toml:89-91`), `ruff format --check` do diff (`land_check`)." (b) "Spec com `Requer: web` e sem `docs/specNNN/fontes.md`: não busque nem invente; hand-back pedindo ao coordenador." (c) "Spec `médio`/`alto`: leia os domínios dela em `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` antes do primeiro teste."
- **R17 — `Requer: web` é do coordenador.** Antes de disparar o executor, o coordenador busca o que a spec pede e grava `docs/specNNN/fontes.md` (URL, data de acesso, trecho citado ≤ 10 linhas por fonte). Regra registrada numa linha de `CLAUDE.md` § Subagentes (e não no BRIEF: é regra do coordenador). Sem mudança de `tools` no executor (auditoria: "web no executor: não", `auditoria…:47`).

### Bloco C — evidência reproduzida pelo revisor (item 16)

- **R18 — `scripts/dev/red_green.sh NNN [--allow-green <nodeid>]… [--equivalence]`.** Invólucro de `scripts/dev/red_green.py`. Procedimento (o mais barato que não mexe no worktree da spec):
  1. T = arquivos de teste novos ou alterados: `git diff --name-only --diff-filter=AM main...spec-NNN -- tests/` (inclui `conftest.py`, `factories.py` e fakes alterados, que o teste novo pode precisar).
  2. N = testes **novos**: para cada arquivo em T, nomes `test_*` (funções de módulo e métodos de `Test*`) presentes na versão da branch e ausentes na da `main` (AST de `git show main:<f>` × `git show spec-NNN:<f>`; arquivo novo → todos). Parametrização não muda o nome; o resultado do nome é "passou" só se todos os casos passaram.
  3. Worktree descartável da `main`: `git worktree add --detach <RPG_WT_ROOT>/rpg-redgreen-NNN main`, depois `git -C <tmp> checkout spec-NNN -- <T>` (só os testes vêm da branch; o produto é o da `main`).
  4. Roda `bash scripts/dev/py.sh -m pytest <T> -p no:cacheprovider -n 2 --junitxml=<tmp>/main.xml -q` no worktree temporário e o mesmo no worktree da spec (`branch.xml`). Teto de tempo: 600 s por lado.
  5. Remove o temporário (`git worktree remove --force`), inclusive em erro (`finally`).
  6. Classifica cada nome de N: `vermelho→verde` = OK; `verde→verde` = FAIL "não prova a mudança", exceto se listado em `--allow-green` (o revisor justifica no handoff); `*→vermelho` = FAIL "não passa na branch"; erro de coleta na `main` (módulo novo ausente) conta como vermelho, marcado `(import)`.
  7. Saída: tabela markdown `| teste | main | branch | veredito |` + linha final `red_green: K/N OK`; rc 0 se todos OK, 1 caso contrário.
- **R19 — Refatoração pura.** Com `--equivalence` (spec cujo campo `Evidência` declara oráculo de equivalência), a regra inverte: todo teste de T tem de ser **verde nos dois lados** (o oráculo prova que o comportamento não mudou); vermelho em qualquer lado → FAIL. Se N está vazio e não é `--equivalence`, rc 1 com "spec sem teste novo: declare `--equivalence` ou peça teste ao executor".
- **R20 — Handoff.** `docs/templates/handoff-review.md` ganha a seção `## Evidência verificada` (entre Achados e Correções aplicadas) com a instrução: "saída do `red_green.sh NNN`, ou `N/A — Risco baixo`". É o que R7 confere.

### Bloco D — handoff de sessão (item 15)

- **R21 — `scripts/dev/handoff.py [--out <caminho>] [--check <caminho>]`.** Sem `--check`: grava `.tmp/handoff-<AAAA-MM-DD>.md` (data local; `--out` sobrescreve o caminho). Se o arquivo já existe, ele vira `.tmp/handoff-<data>.prev.md` (um nível; o anterior `.prev` é apagado) e o novo é escrito. Formato fixo, nesta ordem, refletindo as "Compact instructions" de `CLAUDE.md`:
  1. `# Handoff do coordenador — <data> <hora>`
  2. `## main` — sha e assunto do `git log -1`, `git rev-list --count origin/main..main` à frente (automático);
  3. `## Worktrees e specs ativas` — `git worktree list` + status do cabeçalho de cada spec com worktree (automático);
  4. `## Testes rodados` — `<PREENCHER: comando → resultado>`;
  5. `## Decisões do dono nesta sessão` — `<PREENCHER>`;
  6. `## Bloqueios` — `<PREENCHER>` + "ver ESTADO_ATUAL.md § Bloqueios";
  7. `## Próximo passo` — `<PREENCHER: 1 a 3 itens>`;
  8. `## Não refazer` — `<PREENCHER: lições/armadilhas desta sessão>`.
  Com `--check <caminho>`: rc 1 se sobrar `<PREENCHER` ou faltar uma das 8 seções.
- **R22 — `/estado --handoff`.** `.claude/skills/estado/SKILL.md` ganha a variante: roda `bash scripts/dev/py.sh scripts/dev/handoff.py`, o coordenador preenche os `<PREENCHER>` à mão, roda `--check` e só então `/compact` ou `/clear`. Sem `--handoff`, o `/estado` não muda.
- **R23 — Hook aponta.** A mensagem de `.claude/hooks/context_size.py:63-66` passa a terminar com "Handoff: `/estado --handoff` grava `.tmp/handoff-<AAAA-MM-DD>.md` (data de hoje no texto)". Resto do hook inalterado (limites, estado por sessão, silêncio em subagente).

### Bloco E — integração no `/spec-land`

- **R24 — `spec-land/SKILL.md`.** O passo 1 (`:11-14`) vira "`bash scripts/dev/land_check.sh NNN` (no worktree) + o status do cabeçalho"; a linha do `ruff check` fica (land_check cobre `format`, não `check`). Entre os passos 2 e 3: "`Risco: alto` com `RPG_WT_PUSH=1`: `wt.sh ci NNN` e um `ci-watcher` (Haiku) para o run; sem a variável, registre na spec em 'Não rodou e por quê'". O passo 4 diz que `wt.sh land` repete o `land_check` e recusa o `ff` se falhar.

### Fora de escopo

- `scripts/dev/full.sh`, `basetemp` por PID, venv de worktree, `guard_tools.py`, hook de `Agent`, e o comando da suíte no passo 3 de `/spec-land` (SPEC-414).
- `DECISOES_FIXAS.md`, pgTAP no CI, catraca de relógio em teste, baseline do ruff por contagem, default de `--out` (SPEC-416).
- Catraca de teste enfraquecido e Hypothesis (SPEC-417); gate de tipos (SPEC-418).
- Imposição do "Bash só leitura" do `spec-author` por hook (seria em `guard_tools.py`, da SPEC-414; aqui fica regra de prompt, ver §8 D-415-3).
- Lock entre sessões e web no executor (auditoria, "Não fazer").
- `git push` de qualquer coisa por padrão; autorização de push (decisão do dono, §7.3).
- Editar `docs/guias/BRIEF_SUBAGENTE.md` (a linha de gates vai no `spec-executor.md`, como pede o item 14; o BRIEF fica para quando o dono quiser).
- Reescrever specs antigas para o template novo.
- `ruff check` das specs/handoffs (não há `.py` lá; só o `format`).

## 3. Design técnico

### 3.1 Arquivos

**Novos**
- `scripts/dev/land_check.sh` (≤ 10 linhas) e `scripts/dev/land_check.py` — R1–R9.
- `scripts/dev/red_green.sh` (≤ 10 linhas) e `scripts/dev/red_green.py` — R18–R19.
- `scripts/dev/handoff.py` — R21.
- `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` — R12 (semente no §3.3).
- `tests/test_land_check.py`, `tests/test_red_green.py`, `tests/test_handoff_file.py`, `tests/test_wt_sh.py`, `tests/test_workspace_docs.py` — §4.

**Alterados**
- `scripts/dev/wt.sh` — `sync_branch` (fim, depois de `:86`): chama `land_check --only collision`; `land` (`:99-104`): `land_check` completo antes do `merge`; novo `ci` (R10); comentário de uso (`:2-17`) com a linha do `ci` e o `sed -n '2,17p'` (`:18`, `:117`) ajustado ao novo tamanho do comentário.
- `pyproject.toml:71` — R5.
- `.gitattributes` — R13 (uma linha ao fim).
- `specs/TEMPLATE.md` — R11.
- `docs/templates/handoff-review.md` — R20.
- `.claude/agents/spec-reviewer.md` (R14), `.claude/agents/spec-author.md` (R15), `.claude/agents/spec-executor.md` (R16).
- `CLAUDE.md` § Subagentes — uma linha (R17).
- `.claude/skills/spec-land/SKILL.md` (R24), `.claude/skills/estado/SKILL.md` (R22).
- `.claude/hooks/context_size.py:63-66` (R23).
- `tests/test_workspace_hooks.py` — 1 teste novo (R23).

### 3.2 Assinaturas (`land_check.py`, funções puras testáveis)

```text
dirty_paths(porcelain_z: str) -> list[str]           # parse de status --porcelain -z (renames: os 2 lados)
collisions(branch: list[str], dirty: list[str]) -> list[str]   # prefixo para entradas terminadas em "/"
parse_risk(spec_text: str) -> str | None             # "baixo"|"médio"|"alto"|None (template literal = None)
last_verdict(handoff_text: str) -> str | None
review_problems(risk: str | None, handoffs: dict[str, str]) -> list[str]   # nome -> texto
pending_measures(spec_text: str) -> list[str]
parse_free_ram_gb(ram_output: str) -> float | None   # aceita "3,2" e "3.2"
ci_problem(runs: list[dict], head_sha: str) -> str | None
main(argv: list[str] | None = None) -> int           # orquestra; git/gh/ram via subprocess injetável
```

`red_green.py`: `added_tests(old_src: str | None, new_src: str) -> set[str]`; `junit_outcomes(xml: str) -> dict[str, str]` (nome base → `pass|fail|error`, agregando parametrizados); `classify(added, main_res, branch_res, allow_green, equivalence) -> list[Row]`; `main(argv) -> int`. `handoff.py`: `render(facts: dict, now: datetime) -> str`; `check(text: str) -> list[str]`; `main(argv) -> int`. Toda função ≤ 60 linhas; subprocess sempre com lista de argumentos (sem `shell=True`, ruff `S` vale fora de `scripts/**` mas a regra é a mesma).

### 3.3 Semente do guia de casos (R12)

Cada linha abaixo vira um item; fonte entre parênteses.

**concorrência**
- Cancelamento durante cada `await to_thread(...)` com efeito (financeiro ou de arquivo): o thread termina sozinho; o `finally` não pode rodar em paralelo com ele. Teste: fake lento + cancelar no meio + afirmar ordem (SPEC-412 P1, `services/speech_to_text.py:326`).
- Flag "já começou" (`begun = True`) só depois do `await`: cancelado no meio, o efeito existe e o fechamento não roda. Teste do cancelamento em `begin` (SPEC-412 P2).
- Recurso de `with` (diretório temporário, arquivo) liberado enquanto o thread ainda o usa: shield-e-espera também no passo não financeiro (SPEC-412 rodada 2 P2, `prepare_audio`).
- Espera em teste (`while not evento: await sleep`) sempre com teto (`asyncio.timeout`): regressão não pode pendurar a suíte (SPEC-412 rodada 2 P3).
- Duplo cancelamento e exceção do thread durante a espera: um teste cada (SPEC-412 rodada 2 P3).
- Exceção do thread engolida no cancelamento: `logger.warning`, nunca silêncio (SPEC-412 rodada 2 P3).

**sql-rls**
- `throws_ok(…, '42501')` não distingue RLS, falta de grant e trigger de tombstone: afirme a mensagem (`throws_like '%row-level security%'`) (SPEC-410 P3-2).
- Comentário de migração sobre roles/grants conferido contra os `grant` reais das migrações anteriores (SPEC-410 P3-1).
- Rollback é migração nova (ou `migration repair`), nunca SQL avulso: senão `schema_migrations` mente e um `db reset` reaplica (SPEC-410 P3-4, SPEC-413 P3-4).
- Migração e pgTAP que nunca rodaram em Postgres: listar em "Não rodou e por quê" e não chamar de "coberto pelo CI" se nenhum workflow roda (SPEC-413 P2-2, SPEC-410 P3-6).
- Modo `off` de flag nova tem de ser byte a byte o comportamento anterior; o que já muda em `off` vai na spec e no smoke (SPEC-410 P2-1).

**api**
- Smoke de "não exposto" afirma o status e o código exatos (404 `PGRST202`), nunca `status >= 400` (SPEC-413 P2-1, `scripts/staging/smoke_ab.py:326`).
- Guard de boot/config de produção: o checklist de release recusa o marcador de staging também, não só a flag perigosa (defesa em duas camadas) (SPEC-411 P2-1).
- Guard mais largo que o uso documentado: um caso parametrizado com os valores "quase válidos" (`"true"`, `" 1 "`) (SPEC-411 P3-3).
- Rota nova num arquivo já inventariado pelo teste AST: o inventário chaveia por `arquivo::símbolo`, senão passa sem revisão (SPEC-410 P3-3).

**persistência**
- Asserção vacuamente verdadeira (`balance == 0` de quem nunca teve conta): prove o gate pelo caminho que existe (SPEC-413 P3-1).
- "Trava" de allowlist = conjunto exato esperado, não só regex e unicidade (SPEC-411 P3-1).
- Writer persistente novo: round-trip save/load e save antigo carregando (AGENTS.md § Operação).

**llm-structured**
- `with_structured_output(X).invoke()` pode devolver `AIMessage`: `isinstance` ou `try/except` antes de ler campo (AGENTS.md, guard de FallbackLLM).
- MockLLM devolve instância válida e esconde erro de nome/tipo de campo: o caminho novo tem smoke com chave real (AGENTS.md).
- Número vindo do LLM (ouro, dano, sinal) é validado em Python antes de mudar estado (AGENTS.md, mecânica é Python).

## 4. Plano passo a passo

Executor roda só os testes desta spec, via `bash scripts/dev/pt.sh <arquivos>` (`-n 2`); nunca a suíte completa. Todo teste que cria repositório git usa `tmp_path` e `git -c user.name=t -c user.email=t@t`; nada toca o repositório real.

### Etapa 0 — Medições (sem código)
Resolver os `<MEDIR:>` do R5 e do §6 e trocar pelo valor nesta spec, no mesmo commit da Etapa 1. Conferir se a SPEC-414 já pousou (`git log main --oneline -- scripts/dev/wt.sh .claude/skills/spec-land/SKILL.md | head -5`) e rebasear sobre ela antes de editar esses dois arquivos.

### Etapa 1 — Testes primeiro (vermelhos)
1. `tests/test_land_check.py`:
   - `test_dirty_paths_parses_renames_and_untracked_dirs`: porcelain `-z` com ` M a.py`, `R  novo.md\0velho.md`, `?? docs/aulas/` → os 4 caminhos.
   - `test_collisions_by_path_and_dir_prefix`: B = `docs/guias/TESTES.md`, `docs/aulas/x.md`, `api.py`; D = `docs/guias/TESTES.md`, `docs/aulas/` → as duas primeiras (reproduz o atrito de 11/11 em `docs/guias/*`).
   - `test_parse_risk`: `` `médio` `` → `médio`; o literal do template → `None`; cabeçalho sem a linha → `None`; texto depois da crase (`` `médio`. Não é baixo… ``, como nesta spec) → `médio`.
   - `test_last_verdict_handles_two_rounds_and_formats`: texto com `Veredito: CHANGES_REQUIRED` e depois `**Veredito: APPROVED_WITH_FOLLOWUPS**` (formato de `handoffs/SPEC-412-terra-review.md:3,62`) → `APPROVED_WITH_FOLLOWUPS`.
   - `test_review_problems_by_risk`: `baixo` sem handoff → `[]`; `médio` sem handoff → 1 problema; `alto` com só `SPEC-999-terra-review.md` → 1 problema (papel); `alto` com `-sol-` e último veredito `CHANGES_REQUIRED` → 1 problema; `alto` com `-sol-`, `APPROVED` e sem `## Evidência verificada` → 1 problema; completo → `[]`.
   - `test_pending_measures`: spec com o marcador cru `<MEDIR: wc -l x>` (sem crase antes) → 1 linha; com a menção em código inline (crase antes do `<`) → 0; o texto desta própria spec depois da Etapa 0 → 0.
   - `test_parse_free_ram_gb_comma_and_dot`: `RAM livre: 2,9 GB de 15,7 GB` → 2.9; com ponto → idem; lixo → `None`.
   - `test_ram_below_floor_fails_unless_skipped`: `main` com `ram.sh` injetado devolvendo 2,5 → rc 1; com `RPG_LAND_SKIP=ram` → rc 0 e `WARN`; `RPG_LAND_SKIP=format` → rc 2.
   - `test_ci_off_by_default_warns_for_alto`: sem `RPG_WT_PUSH` e Risco `alto` → `WARN ci`, rc não afetado.
   - `test_ci_problem`: lista de runs sem o sha → problema; com sha, `workflow_dispatch`, `success` → `None`; com sha e `failure` → problema; com sha e evento `push` → problema.
   - `test_format_check_uses_force_exclude`: o comando montado para `["evals/core/x.py", "a.py"]` contém `--force-exclude` (subprocess injetado registra argv).
2. `tests/test_wt_sh.py` (pula se `shutil.which("bash")` for `None`): fixture monta em `tmp_path` um repo `principal` com `main`, copia o `scripts/dev/wt.sh` real e os `land_check.*` reais (quando existirem), um `scripts/dev/py.sh` de teste (`exec "<sys.executable>" "$@"`) e um `scripts/spec_index.py` de teste que só sai 0 (o índice real não interessa aqui); `RPG_WT_ROOT=<tmp>/wt`.
   - `test_sync_fails_on_collision_with_dirty_main`: `wt.sh new 999`; commit em `spec-999` mudando `docs/x.md`; no principal, `docs/x.md` modificado sem commit; `wt.sh sync 999` → rc 1 e a saída cita `docs/x.md`. **Hoje sai 0** (vermelho real, não por ausência).
   - `test_land_refuses_ff_on_collision`: mesmo cenário, `wt.sh land 999` → rc 1 e `git -C principal rev-parse main` inalterado. Hoje o `merge --ff-only` é que falha, com outra mensagem; o teste afirma a mensagem do `land_check`.
   - `test_sync_clean_passes`: sem arquivo sujo → rc 0.
   - `test_ci_is_off_without_env`: `wt.sh ci 999` sem `RPG_WT_PUSH` → rc 3 e nenhum remoto consultado (o repo de teste não tem `origin`; se tentasse, o erro seria outro).
3. `tests/test_red_green.py`:
   - `test_added_tests_ast`: versão antiga com `test_a`, nova com `test_a`, `test_b` e `TestX.test_c` → `{test_b, TestX::test_c}`; arquivo novo (`old_src=None`) → todos.
   - `test_junit_outcomes_aggregates_params`: XML com `test_b[1]` pass e `test_b[2]` fail → `test_b: fail`; erro de coleta do arquivo → todos os nomes do arquivo `error`.
   - `test_classify_rules`: vermelho→verde OK; verde→verde FAIL salvo `allow_green`; →vermelho FAIL; `error` na main conta vermelho `(import)`; `equivalence=True`: verde→verde OK e vermelho em qualquer lado FAIL; N vazio sem `equivalence` → FAIL.
   - `test_temp_worktree_removed_on_error`: `main` com o runner injetado lançando exceção → o `git worktree remove` é chamado (registro de chamadas).
4. `tests/test_handoff_file.py`:
   - `test_render_has_fixed_sections_in_order`: `render` com fatos fixos e `now` fixo → as 8 seções na ordem de R21, título com a data.
   - `test_check_flags_placeholders_and_missing_sections`.
   - `test_existing_file_rotates_to_prev`: em `tmp_path`, arquivo do dia existe → vira `.prev.md`; `.prev` antigo some.
5. `tests/test_workspace_hooks.py::test_context_size_points_to_handoff_file`: no cenário de aviso do teste existente (`:178`), a mensagem contém `/estado --handoff` e `.tmp/handoff-<data de hoje>.md`. **Hoje falha.**
6. `tests/test_workspace_docs.py`:
   - `test_ruff_format_excludes_specs_and_handoffs`: `tomllib` em `pyproject.toml` → `specs/**` e `handoffs/**` em `tool.ruff.format.exclude`. **Hoje falha.**
   - `test_template_has_new_sections`: `specs/TEMPLATE.md` tem `## Invariantes`, `## Concorrência`, `## Não rodou e por quê`, `**Requer:**`, `**Domínios de revisão:**`, e as 7 seções antigas na ordem antiga.
   - `test_reviewer_cases_guide_shape`: o guia tem os 5 domínios na ordem; ≤ 12 itens cada; todo item termina com `(…)`.
   - `test_cases_guide_is_union_merge`: `.gitattributes` tem a linha de R13.
   - `test_agent_docs_mention_new_rules`: `spec-reviewer.md` cita `sol`, `terra`, `red_green.sh` e `CASOS_QUE_O_REVISOR_PEDE`; `spec-author.md` tem `Bash` no `tools` e `<MEDIR:`; `spec-executor.md` cita `size_budget`, `F401`, `Requer: web`. (Teste de documento, não de código-fonte: caso permitido por `docs/guias/TESTES.md` § "Onde mora um teste novo".)
7. Rodar tudo: todos vermelhos. Guardar a saída de `pt.sh` para o hand-back (o revisor vai reproduzir com `red_green.sh`, ver Etapa 5).

### Etapa 2 — `land_check` e `wt.sh`
1. `scripts/dev/land_check.py` + `.sh` (R1–R9). `tests/test_land_check.py` verde.
2. `wt.sh`: `sync` chama `--only collision`; `land` chama o completo; `ci` (R10); uso e `sed` ajustados. `tests/test_wt_sh.py` verde.
3. `pyproject.toml` (R5), `.gitattributes` (R13).

### Etapa 3 — `red_green` e handoff de revisão
1. `scripts/dev/red_green.py` + `.sh` (R18–R19). `tests/test_red_green.py` verde.
2. `docs/templates/handoff-review.md` (R20).

### Etapa 4 — Template, guia, agentes, skills, hook
1. `specs/TEMPLATE.md` (R11); `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` (R12, com a semente do §3.3).
2. `.claude/agents/spec-reviewer.md`, `spec-author.md`, `spec-executor.md` (R14–R16); `CLAUDE.md` (R17).
3. `scripts/dev/handoff.py` (R21); `.claude/skills/estado/SKILL.md` (R22); `context_size.py` (R23); `.claude/skills/spec-land/SKILL.md` (R24).
4. Verificação: os 5 arquivos de teste da Etapa 1 + `tests/test_workspace_hooks.py` + `tests/test_handoff_names.py` verdes; `ruff format --check` e `ruff check` nos `.py` tocados; `bash scripts/dev/py.sh scripts/dev/size_budget.py` limpo.

### Etapa 5 — Dogfooding (revisor)
O revisor (`terra`) roda `bash scripts/dev/red_green.sh 415` sobre esta própria branch e cola a tabela em `handoffs/SPEC-415-terra-review.md` § Evidência verificada. Os testes de `test_wt_sh.py`, `test_workspace_hooks.py` e `test_workspace_docs.py` têm de sair `vermelho→verde` sem `(import)`; os de módulos novos saem `(import)`, o que é aceito.

## 5. Critérios de aceite

- [ ] R1–R24 implementados; os testes da Etapa 1 foram vistos vermelhos (pelo executor) e reproduzidos pelo revisor com `red_green.sh 415`.
- [ ] `bash scripts/dev/land_check.sh 415` sai 0 no worktree desta spec antes do pouso (inclui `review`: existe `handoffs/SPEC-415-terra-review.md` aprovado com `## Evidência verificada`; e `measure`: nenhum `<MEDIR:` restante).
- [ ] `ruff format --check .` na `main` depois do pouso: nenhum arquivo em `specs/` ou `handoffs/`.
- [ ] `wt.sh ci 415` sem `RPG_WT_PUSH` sai 3 e não toca o remoto.
- [ ] `scripts/check_handoff_names.py` verde; `scripts/spec_index.py check` verde com o template novo.
- [ ] Nenhuma função nova > 60 linhas; `size_budget.py` limpo.
- [ ] `uv run pytest` verde (suíte completa offline, rodada pelo coordenador no pouso).
- [ ] Não se aplicam: guard de FallbackLLM (nenhum structured output novo) e saves antigos (nenhum writer).

## 6. Smoke test (infra real, sem LLM)

Rodado pelo coordenador no checkout real, sem push:

1. `bash scripts/dev/land_check.sh 415` no worktree desta spec, com o checkout principal no estado atual (o `git status` de 12/11 tem `docs/descricao_projeto/video/*` modificado e vários `??`): esperado `OK collision` (a branch não toca essas pastas), linha `ram` com o valor real, `review` coerente com o handoff. Medido: 7,9 s.
2. Colisão real: no principal, `touch` sem commit num arquivo que a branch altera (por exemplo uma linha em branco em `specs/TEMPLATE.md`), `wt.sh sync 415` → rc 1 citando o arquivo; desfazer a edição; `sync` → rc 0.
3. `bash scripts/dev/red_green.sh 415` → tabela com todos OK; conferir que `git worktree list` não tem `rpg-redgreen-415` ao fim. Medido: 39,4 s.
4. `bash scripts/dev/py.sh scripts/dev/handoff.py --out .tmp/handoff-smoke.md` → arquivo com as 8 seções; `--check` → rc 1 (placeholders); apagar o arquivo.
5. `bash scripts/dev/ram.sh | head -3` para conferir o separador decimal que o `parse_free_ram_gb` recebe nesta máquina. Medido: `RAM livre: 2,8 GB de 15,7 GB` (vírgula).
6. `gh --version` (pré-requisito do R9 quando o dono ligar o CI). Medido: gh 2.95.0.

## 7. Riscos & compatibilidade

### 7.1 Conflito com a SPEC-414 (pousa antes)

- `.claude/skills/spec-land/SKILL.md`: a 414 troca o comando da suíte no **passo 3** (`:21-25`, por `full.sh`); esta spec muda o **passo 1** (`:11-14`), insere o passo de CI entre 2 e 3 e acrescenta uma frase ao **passo 4** (`:26-27`). Trechos vizinhos: rebase manual provável, sem conflito semântico. Esta spec não toca o texto do passo 3.
- `scripts/dev/wt.sh`: a 414 mexe no `new` (`:90-96`, aviso de venv de worktree) e talvez no `py()` (`:27-29`); esta spec mexe no fim de `sync_branch` (`:86`), no `land` (`:99-104`), acrescenta o caso `ci` e altera o comentário de uso (`:2-17`). Os dois podem crescer o comentário de uso: o executor ajusta o `sed -n '2,Np'` (`:18`, `:117`) depois de rebasear sobre a 414.
- `docs/guias/BRIEF_SUBAGENTE.md` e `guard_tools.py`: só a 414 (esta spec não toca).

### 7.2 Comportamento

- Falso positivo em `collision` trava o pouso: a saída diz o caminho exato, e a correção é sempre do lado de quem sujou o principal (commitar ou descartar), nunca pular o check. Não há `RPG_LAND_SKIP=collision` de propósito.
- Diretório não rastreado colapsado (`?? pasta/`) colide por prefixo: uma pasta não rastreada grande no principal (hoje `docs/descricao_projeto/video/public/*`) bloqueia qualquer branch que crie arquivo dentro dela. É o comportamento correto (o `ff` também recusaria por "untracked working tree files would be overwritten").
- `wt.sh land` já re-sincroniza (`:100`): se a `main` andou depois do run de CI, o sha muda e `ci` (quando ligado) reprova até um novo `wt.sh ci`. Custo aceito; o `WARN`/`FAIL` diz isso.
- `red_green` roda pytest duas vezes com `-n 2`: dentro da regra de memória do `CLAUDE.md`. Worktree temporário usa o venv do principal via `py.sh` (o mesmo caminho que a 414 consolida).
- `merge=union` no guia: duas linhas novas no mesmo domínio entram as duas, podendo passar de 12; `test_reviewer_cases_guide_shape` acusa na suíte do pouso seguinte e o revisor funde (R12c).
- Specs antigas sem as seções novas continuam válidas (`spec_index.py` só lê `Status`); `land_check` só exige `Risco` preenchido, o que as specs pousadas desde a 386 já têm. Medido: 197, 198, 222, 297, 359, 379, 380, 384 estão `approved`/`in-progress` sem `Risco`; precisam do campo antes de pousar (`docs/spec415/medicoes.md` item 6).
- `spec-author` com `Bash`: a regra "só leitura" é de prompt, sem guarda técnica nesta spec (D-415-3).

### 7.3 Bloqueio no dono: push de branch

O passo de CI pré-pouso (R9, R10) precisa de autorização **permanente** do dono para `git push` de branches `spec-NNN` para `origin` (hoje toda a onda de 11/11 está sem push, `ESTADO_ATUAL.md` § Bloqueios). Até lá: `RPG_WT_PUSH` ausente, `wt.sh ci` sai 3, `land_check` só avisa para `Risco: alto`, e cada spec `alto` registra "CI pré-pouso não rodou: push de branch não autorizado" em `## Não rodou e por quê`. **Ativação** quando o dono disser "pode empurrar branch de spec": o coordenador exporta `RPG_WT_PUSH=1` na sessão (ou o põe em `.claude/settings.json` `env`, se o dono quiser permanente), roda `wt.sh ci NNN`, dispara um `ci-watcher` (Haiku) para o run e só pousa com `land_check` verde. O coordenador acrescenta o item à tabela de Bloqueios do `ESTADO_ATUAL.md` ao pousar esta spec.

## 8. Decisões tomadas pelo autor (veto do dono possível)

- **D-415-1 — Lógica em Python, `.sh` só como entrada.** Teste unitário sem bash; só `test_wt_sh.py` precisa de bash (e pula sem ele).
- **D-415-2 — Revisor edita o guia de casos no worktree revisado** (como pede o item 16), com `merge=union` para não travar rebase; a alternativa (linha no handoff, coordenador copia) foi descartada porque depende de um passo manual a mais.
- **D-415-3 — "Bash só leitura" do `spec-author` por prompt.** A guarda técnica seria em `guard_tools.py` (SPEC-414); fica como follow-up se o autor escrever fora da spec. Dúvida aberta: se o input do hook traz o tipo do agente (`agent_type`) para distinguir `spec-author` de outros subagentes.
- **D-415-4 — `alto` exige revisor Opus (`sol`/`astra`) no `land_check`**, codificando a regra de AGENTS.md § Qualidade que hoje é só texto.
- **D-415-5 — `Risco: médio`** desta própria spec (motivo no cabeçalho), o que a faz passar pelo próprio `land_check` com handoff `terra`.
- **D-415-6 — Handoff de sessão: um arquivo por dia**, o anterior vira `.prev.md` (um nível), em vez de anexar seções "Atualização" como em `.tmp/handoff-semana-seguranca-2026-11-11.md`.
- **D-415-7 — `Requer: web` grava `docs/specNNN/fontes.md`** (versionado, com URL e data), para o revisor conferir a mesma fonte que o executor usou.
- **Aprovação (2026-11-12):** aprovada pelo coordenador por delegação do dono ("executa as mudanças", 12/11). Decisões do autor aceitas como escritas. Executa só depois da SPEC-414 pousar (conflito em `spec-land` e `wt.sh`). CI pré-pouso segue desligado até o dono autorizar push de branch.

## 9. Execução (12/11, executor Terra) — desvios e pendências

- `junit_outcomes` devolve chaves `arquivo::[Classe::]nome` (e não só o nome base), para não colidir testes homônimos de arquivos diferentes; erro de coleta = nomes ausentes do XML, tratados como `error` em `classify`.
- `default_run` (land_check/red_green) resolve o executável por `shutil.which`: no Windows, `subprocess` acha o `bash` do WSL (System32) antes do Git Bash. Achado de execução, ver `docs/spec415/medicoes.md`.
- `wt.sh`: o `sed -n` do uso passou de `2,17p` (que imprimia até `set -euo`) para `2,15p` (só o comentário).
- `review_problems` aprova se ao menos um handoff válido (nome aceito, papel certo, último veredito ≠ `CHANGES_REQUIRED`, evidência preenchida) existir; rodadas antigas reprovadas não travam o pouso.
- Não rodou: `wt.sh ci` com `RPG_WT_PUSH=1` e o `ci` do `land_check` com `gh` (sem push autorizado, §7.3); só o caminho desligado é testado.
- Pendente para o pouso: handoff `handoffs/SPEC-415-terra-review.md` com `## Evidência verificada` (revisor Sonnet); `Risco` preenchido nas 8 specs listadas em `docs/spec415/medicoes.md`; critérios abaixo ficam desmarcados até a revisão e a suíte completa do coordenador.
