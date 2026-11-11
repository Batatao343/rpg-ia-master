# SPEC-407 — size-budget-catraca

> **Status:** `in-review` (11/11, executor; antes `approved`) (11/11: aprovada pelo coordenador por delegação do dono, "as decisões deixo para vc"; decisões do §8 = recomendações; veto do dono segue possível) · antes `draft`
> **Criada:** 2026-11-11 · **Atualizada:** 2026-11-11
> **Depende de:** nenhuma. **Ordem:** pousar **depois** de 405 e 406 (ver §7): elas encolhem arquivos da baseline e, com a catraca já ativa, cada uma teria de regravar o `size_budget.json` na própria branch (conflito certo entre as duas). Depois delas, uma só regravação (Etapa 2) cobre tudo.
> **Desbloqueia:** nada (uma das 4 follow-ups de qualidade, SPEC-405..408)
> **Risco:** `baixo` (tooling + 1 arquivo JSON de baseline; nenhum código de produto) → testes + lint bastam, sem revisor obrigatório.
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet) · **EVAL_AUTHORING_REQUIRED:** `false`
> **Evidência:** teste que falha antes: baseline folgada e entrada órfã passam hoje em `problems()` e devem falhar depois (Etapa 1, vermelho antes do código); mais `size_budget.py` limpo sobre a baseline regravada.

---

## 1. Contexto & Objetivo

O gate da SPEC-386 R6 diz "encolher é livre" (`specs/SPEC-386-workspace-guardrails.md:39-41`), mas isso o torna uma trava e não uma catraca: `problems()` só reclama quando `size > baseline` (`scripts/dev/size_budget.py:84`). Quando um arquivo ou função encolhe, a baseline velha continua valendo e o código pode crescer de volta até o valor antigo sem o gate reclamar. Medido pelo coordenador em 11/11: `web/src/App.tsx` consta 1156 em `tests/size_budget.json:40` e tem 950 linhas (206 de folga); `routes/turn.py` consta 1915 (`:24`) e tem 1907. A revisão independente contou ~10 entradas com folga. Também podem existir entradas órfãs (arquivo/função que caiu abaixo do limite ou foi removido): `problems()` itera só `current` (`:79`), então nunca as vê, e a docstring (`:5`) promete que somem "no próximo `--update`", o que ninguém roda.

Objetivo: fechar a catraca com a menor mudança correta: (1) o teste falha quando a baseline está folgada além de uma tolerância pequena ou tem entrada órfã; (2) um modo `--tighten` que só desce (sempre permitido) separado do `--update` que também sobe (exige motivo); (3) regravar a baseline atual apertando as entradas folgadas.

## 2. Requisitos

Linhas abaixo = estado da `main` em `9f21ef4a`.

- **R1 — Folga falha (opção a, com tolerância da opção b).** `problems()` passa a reportar `baseline folgada: KEY BASE -> ATUAL (-N); rode size_budget.py --tighten` quando `baseline - atual > SLACK` (constantes `SLACK_FILE = 25`, `SLACK_FUNC = 10`, em `scripts/dev/size_budget.py`). Folga ≤ tolerância passa (uma edição que remove 2 linhas ou o `ruff format` mexendo em 1–3 linhas não exige regravar). Justificativa dos valores: cobrem ruído de formatação sem deixar crescimento relevante escondido (≤ 25 linhas em ≥ 1000; ≤ 10 em ≥ 100).
- **R2 — Órfã falha.** Entrada da baseline sem correspondente em `current` (arquivo removido/renomeado, função renomeada, ou item que caiu abaixo do limite) gera `entrada órfã na baseline: KEY (BASE); rode size_budget.py --tighten`. Sem tolerância (a entrada não tem mais o que medir). Vale para `files` e `functions`.
- **R3 — `--tighten`.** Novo modo de CLI: regrava a baseline só **descendo**: para cada chave da baseline presente em `current` usa `min(base, atual)`; remove órfãs; **nunca** adiciona chave nova nem sobe valor. Se existir item novo acima do limite ou crescimento (o que `problems()` ainda reprova), imprime a lista, não grava e sai com rc 1 ("extraia para módulo próprio ou use --update com motivo"). Sai com rc 0 e imprime o diff (`chave: antes -> depois`, `removida: chave`) quando grava. Idempotente.
- **R4 — `--update` mantém o contrato** (regrava com as medidas atuais, pode subir e adicionar). A mensagem final de `main()` e a do `test_repo_respects_size_budget` passam a citar os dois caminhos: encolheu → `--tighten`; exceção justificada → `--update` + motivo na mensagem do commit. A `_doc` da baseline (`write_baseline`) diz "Só encolhe; `--tighten` desce, `--update` sobe com motivo".
- **R5 — Docstring do script** (`:1-12`) e `SPEC-386` R6 não ficam contraditórios: a docstring troca "Encolher é livre; item que caiu... some no próximo `--update`" por "Encolher exige `--tighten` no mesmo commit (tolerância SLACK_*); órfã falha". A spec 386 é `done`: não editar; esta spec é a emenda.
- **R6 — Regravação inicial.** Rodar `--tighten` na `main` já com 405 e 406 pousadas; a baseline resultante é o estado verde. O executor lista antes/depois (entradas apertadas e órfãs removidas) em `docs/spec407/tighten.md` (R9 abaixo).
- **R7 — Fluxo.** `--tighten` entra onde o executor já roda o gate: `.claude/agents/spec-executor.md:17` (hoje "…e `bash scripts/dev/py.sh scripts/dev/size_budget.py` sem estouro") ganha "rode `size_budget.py --tighten` se o gate pedir e commite `tests/size_budget.json` junto"; `docs/guias/BRIEF_SUBAGENTE.md:37` ganha a mesma frase curta. `docs/guias/TESTES.md` ganha 3 linhas na seção do gate de tamanho (criar subseção "Orçamento de tamanho" se não houver): o que o gate checa, `--tighten` × `--update`, tolerância. **Nenhuma skill muda** (`/spec-land` e `/wrap-up` não citam o gate; a suíte completa do pouso já o roda e o `--tighten` acontece antes, na branch).
- **R8 — Funções TS/TSX: não-objetivo.** O script só mede função em `.py` (`size_budget.py:65`); `.tsx` entra só por linhas de arquivo (a catraca de R1 cobre `App.tsx` por arquivo). Medir `App()` (884 linhas) fica com a SPEC-392 `draft`. Sem gancho barato (exigiria parser TS).
- **R9 — Prova de ruído.** O teste do R1 inclui um caso de tolerância (folga = SLACK passa, SLACK+1 falha) para fixar o valor.

### Fora de escopo

- Reduzir limites (`FILE_LIMIT`/`FUNC_LIMIT`), mudar `PATTERNS`/`SKIP_PREFIXES`.
- Regravar automaticamente em `/spec-land` ou `wt.sh sync` (opção c, rejeitada: esconde crescimento e mexe no histórico durante rebase).
- Medir funções TS/TSX (SPEC-392).
- Qualquer refatoração dos arquivos da baseline (405/406/392 e a onda 375–385).
- Impor o "motivo no commit" do `--update` por hook (continua convenção + revisor).

## 3. Design técnico

- **Arquivos alterados:**
  - `scripts/dev/size_budget.py`: `SLACK_FILE`, `SLACK_FUNC`; `problems()` ganha os dois ramos (folga, órfã) iterando também `baseline` sem par em `current`; nova `tightened(current, baseline) -> dict` (puro, testável: `min`, só chaves existentes, descarta órfãs); `main()` com `--tighten` (mutuamente exclusivo com `--update` via `add_mutually_exclusive_group`); docstring e `_doc` (R4, R5). Função nova ≤ 60 linhas; arquivo hoje 133 linhas.
  - `tests/test_size_budget.py`: ver Etapa 1.
  - `tests/size_budget.json`: regravado (Etapa 2).
  - `.claude/agents/spec-executor.md:17`, `docs/guias/BRIEF_SUBAGENTE.md:37`, `docs/guias/TESTES.md` (R7).
- **Arquivos novos:** `docs/spec407/tighten.md` (antes/depois da Etapa 2).
- **Assinaturas:**
  - `problems(current, baseline) -> list[str]` (inalterada; mais mensagens)
  - `tightened(current: dict[str, dict[str, int]], baseline: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]`
- **Mudança de contrato de teste:** `test_growth_and_new_offenders_fail_shrink_passes` (`tests/test_size_budget.py:27-41`) afirma hoje `sb.problems(current, bigger) == []  # encolher é livre` (`:41`) com `bigger` = `god.py` +99 e `fn.py::big` = 500. Esse assert é **invertido**: com folga de 49 (> 25) e 395 (> 10) o resultado passa a ter 2 mensagens "baseline folgada". O teste é renomeado `test_growth_and_new_offenders_fail` (sem "shrink passes") e o caso de encolher vira os novos testes abaixo.

## 4. Plano passo a passo

Executor roda só `tests/test_size_budget.py` (e `ruff`), via `bash scripts/dev/pt.sh`/`py.sh`; nunca a suíte completa.

### Etapa 0 — Medição (sem código de produto)
1. Com 405 e 406 já na `main` (ou, se o dono mandar pousar antes, no estado atual), medir **sem gravar** (não rodar `--update`) com um snippet `py.sh -c` que usa `measure`/`load_baseline` e imprime, para cada chave da baseline, `base`, `atual`, `base-atual` e as órfãs. Colar a tabela (só linhas com folga > 0 ou órfã) em `docs/spec407/tighten.md` seção "Antes". Esperado ≥ 10 folgadas (ex.: `web/src/App.tsx` 1156 → 950, `routes/turn.py` 1915 → 1907).

### Etapa 1 — Testes primeiro (vermelhos)
Em `tests/test_size_budget.py`, com fixtures `tmp_path`/dicts como as existentes:
1. `test_slack_baseline_fails_beyond_tolerance`: `current={"files":{"a.py":1100},"functions":{"a.py::f":120}}`; baseline `files` 1100+`SLACK_FILE` e `functions` 120+`SLACK_FUNC` ⇒ `problems == []`; com `+1` em cada ⇒ 2 mensagens contendo "baseline folgada" e "--tighten".
2. `test_orphan_baseline_entries_fail`: baseline com `"gone.py": 1200` e `"gone.py::f": 150` ausentes de `current` ⇒ 2 mensagens "entrada órfã".
3. `test_tightened_only_lowers_and_drops_orphans`: `tightened` devolve `min`, remove órfãs, **não** adiciona item novo nem sobe valor crescido; idempotente (`tightened(c, tightened(c,b)) == tightened(c,b)`).
4. `test_cli_tighten_refuses_growth` (monkeypatch de `ROOT`/`BASELINE`/`measure` ou `main` chamando funções injetáveis; se `main` não for testável sem git, extrair o núcleo em `run_tighten(current, baseline_path) -> int`): com crescimento ⇒ rc 1 e arquivo intacto; sem crescimento ⇒ rc 0 e arquivo regravado.
5. Ajustar o teste existente (§3, inversão do `:41`) e a mensagem do `test_repo_respects_size_budget`.
6. Rodar: 1, 2 e o teste invertido **falham** com o código atual (evidência no hand-back).

### Etapa 2 — Implementação e regravação
1. Implementar R1–R5 em `scripts/dev/size_budget.py`. Testes da Etapa 1 verdes.
2. `test_repo_respects_size_budget` fica **vermelho** na baseline atual (as folgas): prova de que a catraca pega o estado real.
3. `bash scripts/dev/py.sh scripts/dev/size_budget.py --tighten`; commit separado "chore: tighten size budget baseline"; preencher "Depois" em `docs/spec407/tighten.md` (cada chave: antes → depois; órfãs removidas). `size_budget.py` (sem flag) rc 0; `test_size_budget.py` verde.

### Etapa 3 — Fluxo e docs (R7)
Editar as 3 linhas de docs/agente; `ruff format --check` e `ruff check` nos `.py` tocados.

## 5. Critérios de aceite

- [x] `uv run pytest tests/test_size_budget.py -q` verde; os testes 1, 2 e o teste invertido da Etapa 1 foram vistos falhando antes da implementação.
- [x] `bash scripts/dev/py.sh scripts/dev/size_budget.py` rc 0 na baseline regravada; `... --tighten` rodado de novo não altera o arquivo (idempotente: `git diff --exit-code tests/size_budget.json`).
- [x] `git grep -n "wt.sh sync\|--tighten" -- .claude docs/guias` mostra `--tighten` apenas nos 3 pontos do R7; nenhuma skill alterada.
- [x] `docs/spec407/tighten.md` lista antes/depois, com ≥ 10 entradas apertadas, e informa órfãs removidas (ou "nenhuma").
- [x] Nenhum valor da baseline subiu nem chave nova entrou no diff de `tests/size_budget.json` (`git diff` só tem linhas `-`/`+` com valor menor, ou `-` de órfã).
- [x] `ruff format --check` e `ruff check` limpos nos arquivos tocados; `dup_helpers.py --diff main...HEAD` sem helper novo.
- [ ] `uv run pytest` verde (suíte completa, 1× pelo coordenador no pouso).

## 6. Smoke test com LLM real

Não se aplica: tooling de repositório, sem LLM, prompt, persistência ou rota. O oráculo é `size_budget.py` rc 0 sobre o repo real mais os testes sintéticos.

## 7. Riscos & compatibilidade

- **Atrito em onda paralela:** a catraca obriga a regravar quando uma edição encolhe > tolerância; dois worktrees encolhendo arquivos diferentes alteram linhas diferentes do JSON (merge limpo, o JSON é ordenado, uma chave por linha); no mesmo arquivo, conflito trivial — resolução: `git checkout --theirs`/rebase e rodar `--tighten` de novo (idempotente). Mitigação: tolerância 25/10; `--tighten` nunca falha por crescimento alheio.
- **Ordem (decisão):** depois de 405/406. Se pousasse antes, cada uma encolheria `routes/turn.py`, `api.py`, `world_utils.py`, `state.py`, `services/*` e falharia o gate novo até regravar, gerando 2 commits de baseline em conflito. Depois, a Etapa 2 as absorve de uma vez. Contra-argumento (pousar antes para cobrá-las): o ganho é ~zero, porque o diff delas é só remoção e cai na Etapa 2.
- **`ruff format`/hook mudando contagem:** coberto pela tolerância; se um arquivo grande oscilar além disso, é sinal real de mudança.
- **`--update` ainda sobe:** inalterado; a defesa continua o revisor + mensagem do commit (R4). `--tighten` separado evita que o caminho comum (encolher) use o botão que também sobe.
- **Falso positivo de órfã por renomeação** de função grande: obriga `--tighten`/`--update` no mesmo commit do rename — desejado (a função renomeada entra como "nova" e só passa via `--update` com motivo).
- Saves, MockLLM, quota: nenhum impacto.

## 8. Decisões do dono

Nenhuma bloqueante; para confirmar na aprovação:
- **D1** — Tolerância `SLACK_FILE=25` / `SLACK_FUNC=10`? Proposta: sim. Alternativa: 0 (catraca estrita, mais atrito) ou 50/20 (mais frouxa).
- **D2** — Pousar depois de 405 e 406? Proposta: sim (§7).
- **D3** — Rejeitar a regravação automática no pouso (opção c)? Proposta: sim.
