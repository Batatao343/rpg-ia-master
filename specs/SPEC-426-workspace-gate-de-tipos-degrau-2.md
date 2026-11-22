# SPEC-426 — workspace-gate-de-tipos-degrau-2

> **Status:** `approved` (22/11, pelo coordenador, por delegação do dono; D-426-1 a D-426-5 como recomendado; veto do dono continua possível)
> **Criada:** 2026-11-22 · **Atualizada:** 2026-11-22
> **Depende de:** SPEC-418 (`done`; gate bloqueante desde 22/11, `docs/spec418/medicao.md:81`).
> **Desbloqueia:** degraus 4-5 da SPEC-418 (`routes/` + `api.py`, `reportUnnecessaryTypeIgnoreComment`); follow-up do `storyteller` (§2 Fora de escopo).
> **Risco:** `médio` — nenhum comportamento de runtime muda (um `Protocol` novo, anotações de parâmetro/retorno, import sob `TYPE_CHECKING`, config, baseline e uma flag de CLI no `type_gate.py`). Não é `baixo`: amplia um gate **bloqueante** de pouso e CI para 14 arquivos novos (falso positivo trava a onda) e mexe em assinaturas de `services/` usadas por `agents/combat.py`. Não é `alto`: nada de combate, persistência, auth, API pública, estado de jogo ou eval muda de comportamento. Revisor Sonnet.
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet) · **EVAL_AUTHORING_REQUIRED:** `false`
> **Requer:** nada (versão do checador já pinada, `basedpyright==1.40.2`; a opção de CLI de R7 se confirma com `--help` local na Etapa 0)
> **Domínios de revisão:** llm-structured (`docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` § llm-structured)
> **Evidência:** teste que falha antes: `tests/test_type_gate.py::test_llm_param_unguarded_is_rejected` (`types_e2e`) escreve em `tmp_path` `def f(llm: LLMClient) -> str: return llm.with_structured_output(Cena).invoke("x").titulo` e afirma rc 1 com `reportAttributeAccessIssue` **na linha do acesso**; hoje o import de `services.llm_protocol` não resolve, `llm` vira `Unknown` e o único diagnóstico é `reportMissingImports` na linha do import, então a asserção de linha+regra falha. O controle `test_untyped_llm_param_is_blind` (mesmo corpo, `llm` sem tipo → rc 0) documenta o ponto cego. Para R7: `test_checker_cmd_pins_interpreter` falha hoje (`type_gate.py:91` não passa interpretador). Oráculo de equivalência AST para "só anotações" (I1).

---

## 1. Contexto & Objetivo

O gate da SPEC-418 só enxerga o guard crítico (`FallbackLLM.with_structured_output(X).invoke()` devolve `AIMessage`, `llm_setup.py:415-422`; `AGENTS.md` § Convenções) quando o tipo flui de `get_llm` (`docs/spec418/medicao.md:38`). O escopo final (`pyproject.toml:163-172`) cobre 4 dos ~19 arquivos de produção com `with_structured_output(` e nenhum de `agents/` (fechamento da 418, `specs/SPEC-418-workspace-gate-de-tipos.md:244`; revisão `handoffs/SPEC-418-terra-review.md:24`).

Contagem (Grep `with_structured_output\(` em código de produção, 22/11): `agents/` 9 arquivos com chamada real (`archivist.py:1004`, `bestiary.py:657`, `campaign_manager.py:248`, `combat.py:863,1343`, `librarian.py:86`, `loot.py:330`, `npc.py:508`, `router.py:685`, `world_simulator.py:132,299`) + `storyteller.py`, que chama por `narrate_structured` (`agents/storyteller.py:2314-2317`); `services/` 8; `character_creator.py:416`; `llm_setup.py`/`mock_llm.py` são os implementadores. Em `agents/` o receptor vem de `get_llm` direto (visível) em todos, salvo o `storyteller` (`_StoryTurn.llm: Any`, `agents/storyteller.py:1236`, e `mediated_stream.narrate -> Any`, `services/mediated_stream.py:100`). Em `services/` há 4 pontos cegos confirmados no source: `death_flow.py:348` (`llm` sem tipo; aceita `None`, `:357`), `encounter_preparation.py:445`, `tactical_profile.py:605` e `:627`, `narrative_sink.py:359` (`llm: Any`; o retorno de `narrate_structured` é inferido `Any`, então o `npc.py:1298` também fica cego). Parciais já no escopo: `shared_pool.py:430` e `chronicle_compression.py:77` (`llm=None` sem tipo; o ramo `get_llm` é visível).

Segundo problema, operacional: `type_gate.py` chama `sys.executable -m basedpyright` sem dizer ao checador qual interpretador usar (`scripts/dev/type_gate.py:91`). O `py.sh` aponta o venv do principal e **ignora** o `.venv` do worktree (`scripts/dev/env.sh:14-21`), mas o checador, rodando com `cwd` no worktree, resolve o ambiente sozinho e pega o `.venv` velho: acusa import faltando (`ESTADO_ATUAL.md:19,26`). A hipótese (o basedpyright procura `.venv` na raiz do projeto quando não há `venv`/`pythonpath` configurado) é confirmada na Etapa 0 antes da correção.

Objetivo: tipar o cliente LLM com um `Protocol` mínimo, anotar os parâmetros `llm` cegos de `services/`, trazer os 10 arquivos de `agents/` + `character_creator.py` + os 4 de `services/` para o escopo com o legado em baseline, e fixar o interpretador do checador. Tudo dentro de um orçamento de RAM/tempo medido, com critério de corte escrito antes da medição, como na 418.

## 2. Requisitos

Linhas citadas = `main` em `8013f5d2`.

### Protocolo e anotações

- **R1 — `services/llm_protocol.py` (novo, ≤ 40 linhas, só `typing`).** Dois `Protocol` sem `runtime_checkable`:
  - `StructuredInvoker`: `def invoke(self, input: Any, /) -> object: ...`
  - `LLMClient`: `def invoke(self, input: Any, /) -> Any: ...` e `def with_structured_output(self, schema: Any, /, *args: Any, **kwargs: Any) -> StructuredInvoker: ...`
  Retorno estruturado `object` (não `AIMessage | BaseModel`, D-426-1): `object` não tem campo, então `resultado.campo` sem `isinstance` reprova, e qualquer implementador satisfaz o protocolo (a inferência de `MockLLM`/`RoutedLLM` já dá `object | AIMessage | Unknown`, `medicao.md:38`; um retorno mais estreito faria `get_llm()` deixar de ser aceito como `LLMClient`). `invoke` simples fica `Any`: o guard é do caminho estruturado; tipar texto puro é outro degrau.
- **R2 — Implementadores satisfazem o protocolo.** `get_llm(...)`, `MockLLM()`, `FallbackLLM("x")` e `RoutedLLM` são atribuíveis a `LLMClient` sem `cast` nem mudança em `llm_setup.py`/`mock_llm.py` (os dois têm mais de 1.000 linhas e estão na baseline de tamanho).
- **R3 — Anotações dos pontos cegos de `services/`.** `llm: LLMClient` em `encounter_preparation.prepare_encounter` (`:445`), `tactical_profile.generate_tactical_profile` (`:605`) e `get_or_generate_profile` (`:627`); `llm: LLMClient | None` em `death_flow.generate_scar` (`:348`), `shared_pool.evaluate` (`:430`) e `chronicle_compression.compress_chapter` (`:77`); `llm: LLMClient` em `narrative_sink.narrate_structured` (`:359`) e `narrate_text` (`:412`), e `-> object` no retorno de `narrate_structured`. Import sob `if TYPE_CHECKING:` (nenhum import novo em runtime); anotação entre aspas nos 3 arquivos sem `from __future__ import annotations` (`death_flow`, `encounter_preparation`, `tactical_profile`).
- **R4 — Achado revelado pela anotação ou pelo escopo novo.** Cada diagnóstico novo de `reportAttributeAccessIssue`/`reportOptionalMemberAccess` que cite `object` ou `AIMessage` é classificado em `docs/spec426/medicao.md` como bug real, guard fraco ou falso positivo. Corrige-se nesta spec **só** quando, juntos: (a) a correção é trocar/estreitar o guard por `isinstance(x, Schema)` sem mudar o resultado observável (ex.: `librarian.py:89-91`, guard negativo `not isinstance(result, BaseMessage)`; `character_creator.py:417-418`, `stats.model_dump()` protegido só por `try`); (b) um teste existente ou novo cobre o caminho `AIMessage` daquele ponto e passa antes e depois; (c) o arquivo não cresce se tiver > 1.000 linhas. Fora disso o diagnóstico vai para a baseline e vira linha de follow-up (spec própria; regra da 418, `SPEC-418:91`).

### Escopo e custo

- **R5 — Escopo novo.** `include` ganha `services/llm_protocol.py`, os 4 de `services/` (`death_flow`, `encounter_preparation`, `narrative_sink`, `tactical_profile`), `character_creator.py` e os 10 de `agents/` (`archivist`, `bestiary`, `campaign_manager`, `combat`, `librarian`, `loot`, `npc`, `router`, `storyteller`, `world_simulator`), **salvo o que o corte de R6 tirar**. Caminhos explícitos, nunca `"agents"` inteiro (os outros `agents/*.py` não chamam LLM estruturado e só custariam RAM). Nada mais em `[tool.basedpyright]` muda (mesmas regras e níveis, `pyproject.toml:173-194`).
- **R6 — Orçamento e critério de corte (escrito antes da medição).** Medido no Windows, checador sozinho, RAM livre ≥ 3 GB antes (`bash scripts/dev/ram.sh`), frio e quente, como `medicao.md:18-24`:
  1. teto local: pico ≤ 2,0 GB (mesmo de E0.7.3 da 418; D-426-2) e quente ≤ 60 s;
  2. estourou → tirar arquivos de `agents/` nesta ordem, medindo após cada um: `storyteller.py` (3.017 linhas, e continua cego pelo `Any` de `:1236`, então o ganho é quase nulo), depois o maior restante (`combat.py` 3.944, `npc.py` 1.604, `archivist.py` 1.237…); o que sair vira "degrau 3" registrado;
  3. o núcleo (`llm_protocol` + os 4 de `services/` + `character_creator.py`) nunca é cortado; se só o núcleo já passar do teto, a Etapa 0 para, registra os números e o coordenador decide (nunca subir o teto em silêncio);
  4. baseline > 500 KB → mesmo corte de 2 (R8 da 418);
  5. CI: job `types` inteiro ≤ 5 min (metade do `timeout-minutes: 10`, `.github/workflows/validate.yml:145`); estourou → mesmo corte de 2.
- **R7 — Interpretador fixo.** `run_checker` passa ao checador o interpretador que roda o `type_gate.py` (`--pythonpath <sys.executable>`, nome da opção confirmado em E0.1), montado numa função pura `checker_cmd(paths, baseline, python) -> list[str]`. Com isso um `.venv` velho no worktree não muda a resolução de imports; quem escolhe o venv continua sendo o `py.sh`/`env.sh` (SPEC-414).

### Baseline e quem grava

- **R8 — Branch sem crescimento de baseline.** O branch `spec-426` não acrescenta entrada à `.basedpyright/baseline.json` (o `--land` reprova crescimento, `type_gate.py:214-219`; o hook nega `--update` em subagente, `.claude/hooks/guard_tools.py:143`, D-418-6). No branch o `include` ganha só `services/llm_protocol.py` (arquivo novo, tem de sair limpo, R13 da 418); anotações em arquivos já no escopo (`shared_pool`, `chronicle_compression`) que criarem erro são corrigidas (R4) ou o arquivo volta sem a anotação e vira follow-up. Entrada que sumir → `type_gate.py --tighten` (livre para executor).
- **R9 — Ampliação do escopo é commit do coordenador na `main`.** Depois do pouso do branch, o coordenador, sozinho na máquina, faz **um** commit `chore(types): widen scope to agents and LLM callers, raise baseline (SPEC-426)` com: `include` de R5 (já cortado por R6), `type_gate.py --update --reason "SPEC-426 escopo agents + services LLM"`, a linha em `docs/spec418/baseline_log.md` e a asserção de R10 sobre o `include`. É a única entrada de baseline desta spec e fica auditável pelo log.
- **R10 — Testes.** Em `tests/test_type_gate.py`:
  - default (sem checador): `test_checker_cmd_pins_interpreter` (`checker_cmd` contém a opção de R7 seguida do `python` dado, com e sem baseline); `test_llm_protocol_has_only_typing_imports` (AST de `services/llm_protocol.py`: imports só de `typing`/`__future__`); asserção nova em `test_basedpyright_config_matches_spec` de que `include` contém `services/llm_protocol.py` (branch) e os arquivos de R5 (commit de R9).
  - `types_e2e`: `test_llm_param_unguarded_is_rejected`, `test_llm_param_guarded_passes` (`isinstance(r, Cena)` → rc 0), `test_untyped_llm_param_is_blind` (controle, rc 0), `test_real_clients_satisfy_protocol` (`a: LLMClient = get_llm(0.1, ModelTier.FAST)`, `MockLLM()`, `FallbackLLM("x")` → rc 0). Mesmo helper `_gate_files` (`tests/test_type_gate.py:210-216`).

### Fora de escopo

- `agents/storyteller.py` além de entrar no `include`: tipar `_StoryTurn.llm`/`update` (`:1236`) e `mediated_stream.narrate` (`:100`) muda o tipo de dezenas de leituras num god-file; follow-up próprio.
- `agents/archivist.py:104` (`_extract_summary_plain(llm, …)`, texto puro, e o arquivo tem 1.237 linhas: o import custaria linha).
- Qualquer mudança em `llm_setup.py`, `mock_llm.py`, `tests/fakes/`, `routes/`, `api.py`, `evals/`.
- Resto de `services/` (≈ 235 arquivos), degraus 1, 4 e 5 da 418; `strict`; tipar `invoke` de texto puro.
- Conserto de legado fora de R4; `except Exception` existentes.
- `.basedpyright/baseline.json` no `scripts/dev/baseline_growth.py` (`:21-26` não a lista; R12.3 da 418 ficou só no hook). O `--land` já cobre crescimento; follow-up se o dono quiser a terceira camada.
- P2-4/P2-5 da revisão da 418 (e2e com baseline sintética; `mkdtemp` sem `rmtree`, `type_gate.py:143`).

### Invariantes

- **I1 — Só anotação.** Para cada `.py` de produto tocado, o AST com anotações removidas (`arg.annotation`, `returns`, bloco `if TYPE_CHECKING:`) é igual ao da `main`, salvo correções de R4 listadas em `medicao.md` (teste: oráculo `.tmp/spec426/ast_equiv.py` na Etapa 3, saída colada no hand-back; testes existentes dos 6 módulos verdes).
- **I2 — Baseline só cresce no commit de R9**, com linha no log (teste: `type_gate.py --land --base main` no branch → `OK`; `test_land_fails_when_baseline_grew` segue verde).
- **I3 — Tamanho.** Nenhum arquivo > 1.000 linhas cresce, nenhuma função > 100 cresce (`tests/test_size_budget.py`).
- **I4 — `get_llm()` é `LLMClient`** (teste: `test_real_clients_satisfy_protocol`).

## 3. Design técnico

- **Novo:** `services/llm_protocol.py` (R1); `docs/spec426/medicao.md` (Etapa 0, R4, R6).
- **Alterados:** os 6 de `services/` (R3, só assinaturas + import sob `TYPE_CHECKING`); `scripts/dev/type_gate.py` (R7: `checker_cmd` + uso em `run_checker`; arquivo tem 271 linhas, função nova ≤ 15); `pyproject.toml` (`include`: branch só `services/llm_protocol.py`; R9 o resto); `tests/test_type_gate.py` (R10); `.basedpyright/baseline.json` + `docs/spec418/baseline_log.md` (só R9); `docs/guias/TESTES.md` § Tipos: uma linha sobre `LLMClient` em parâmetro novo e o limite do `storyteller`.
- **Assinatura:** `def checker_cmd(paths: list[str] | None, baseline: Path | None, python: str = sys.executable) -> list[str]`.

### Concorrência

N/A — sem thread/async/cancelamento (o `_invoke_with_deadline` de `encounter_preparation.py:497` não muda).

## 4. Plano passo a passo

Executor: só `tests/test_type_gate.py`, os testes dos 6 módulos de `services/` e `tests/test_size_budget.py`, `pt.sh` com `-n 2`; checador uma vez por vez, nunca junto de pytest, RAM livre ≥ 3 GB. Worktree `C:/Users/guilh/AppData/Local/Temp/claude/rpg-spec-426`.

### Etapa 0 — Medição (saída em `.tmp/spec426/`, resultado em `docs/spec426/medicao.md`)

- **E0.1** `basedpyright --help`: nome da opção de interpretador na 1.40.2: <MEDIR: bash scripts/dev/py.sh -m basedpyright --help | grep -i python>.
- **E0.2 Reproduzir o `.venv` velho.** No worktree, `uv venv .tmp/spec426/stale` e junção/cópia como `.venv`; `type_gate.py --check` → <MEDIR: rc e nº de reportMissingImports com .venv velho, sem R7>; com `--pythonpath` à mão → <MEDIR: rc com R7>. Não reproduziu → registrar e manter R7 mesmo assim (é determinismo barato), dizendo isso no hand-back.
- **E0.3 Contagem** com o `include` de R5 numa config provisória (sem gravar baseline no repo): <MEDIR: erros por arquivo e por regra no escopo novo>; diagnósticos citando `object`/`AIMessage`: <MEDIR: n e lista arquivo:linha>, classificados por R4.
- **E0.4 Tempo e RAM**, frio/quente, escopo atual vs R5: <MEDIR: tempo e pico (node + launcher) por rodada>; aplicar R6 e registrar cada corte.
- **E0.5 Baseline** provisória (`--writebaseline` em `.tmp/`): <MEDIR: entradas e KB>.
- **E0.6 Duração dos `types_e2e`** (8 testes): <MEDIR: tempo de pytest tests/test_type_gate.py -m types_e2e, sozinho>.

### Etapa 1 — Testes primeiro

`tests/test_type_gate.py` com R10 (exceto a asserção de `include` do R9). Vermelhos esperados: `checker_cmd` não existe; `services/llm_protocol.py` não existe (os `types_e2e` falham na asserção de linha/regra, não por exceção); o controle `test_untyped_llm_param_is_blind` já passa (é controle, declarado ao `red_green.sh` com `--allow-green`).

### Etapa 2 — Protocolo e interpretador

`services/llm_protocol.py` (R1), `include` + esse arquivo, `checker_cmd` (R7). `pt.sh tests/test_type_gate.py` verde; `-m types_e2e` verde (uma vez).

### Etapa 3 — Anotações

R3 nos 6 arquivos; correções de R4 permitidas. `type_gate.py --check` rc 0 (ou `--tighten`); oráculo I1; `pt.sh` dos testes dos 6 módulos (`Grep "from services.(death_flow|encounter_preparation|narrative_sink|tactical_profile|shared_pool|chronicle_compression)" tests/`) e `tests/test_size_budget.py`; `ruff check`. Hand-back com E0, tabela de R4, corte de R6 e o `include` final para R9.

### Etapa 4 — Coordenador, após o pouso

Commit de R9 na `main` (checador sozinho, RAM ≥ 3 GB), `type_gate.py --check` rc 0, push, job `types` verde (§6.4). Linha de `TESTES.md`.

## 5. Critérios de aceite

- [ ] `docs/spec426/medicao.md` com E0.1-E0.6 e nenhum `<MEDIR:` na spec.
- [ ] `services/llm_protocol.py` só com `typing`; `get_llm()`, `MockLLM`, `FallbackLLM` aceitos como `LLMClient`.
- [ ] 8 parâmetros `llm` anotados (R3), retorno `object` em `narrate_structured`; oráculo I1 igual.
- [ ] `type_gate.py` com interpretador fixo; `test_checker_cmd_pins_interpreter` verde.
- [ ] Branch: baseline sem entrada nova, `--land` → `OK types:`; R4 classificado, follow-ups listados.
- [ ] Commit de R9 na `main` com linha no `baseline_log.md`; `--check` rc 0; job `types` verde ≤ 5 min.
- [ ] `tests/test_type_gate.py` verde (default e `-m types_e2e`); `tests/test_size_budget.py` verde.
- [ ] `uv run pytest` verde (suíte completa, coordenador no pouso).
- [ ] Nenhum `with_structured_output` novo (o guard de FallbackLLM não se aplica); saves intocados.

## 6. Smoke test real (sem LLM; infra = máquina local e CI)

1. Depois de R9, worktree limpo, RAM ≥ 3 GB: `type_gate.py --check` → rc 0, tempo e pico dentro de R6.
2. Na cópia de trabalho (sem commit), em `services/tactical_profile.py:619` trocar `isinstance(result, TacticalProfileModel) and result.priorities` por `result.priorities` → `--check` rc 1 apontando `:619`; `git checkout --` → rc 0. Repetir em um arquivo de `agents/` que sobreviveu ao corte (ex.: `agents/router.py:707`, tirando o `isinstance`).
3. `.venv` velho no worktree (E0.2) → `--check` rc 0 com R7.
4. CI: run do `validate` com o commit de R9; registrar run id, duração do job `types` e rc em `docs/spec426/medicao.md`.

## Não rodou e por quê

- Autor da spec não rodou checador nem pytest (RAM): todos os números estão em `<MEDIR:>` da Etapa 0.
- §6.4 depende de push (coordenador, após R9).

## 7. Riscos & compatibilidade

- **Runtime, saves, MockLLM, quota:** nada muda (I1; `Protocol` sem `runtime_checkable`, import só sob `TYPE_CHECKING`).
- **RAM:** `combat.py`/`storyteller.py` puxam inferência de muitos módulos; mitigação é o corte de R6 e rodar só por comando e no pouso (R15 da 418).
- **`land_check` usa o `type_gate.py` e o Python do principal** (`scripts/dev/land_check.py:346-348`): com R7, worktree com `uv.lock` diferente (venv próprio, `env.sh:21`) é checado com as dependências do principal; dependência nova só no branch pode virar `reportMissingImports`. Registrado; o job de CI usa o venv do próprio commit.
- **Assinaturas de `services/` com tipo:** chamadores em `tests/` passam fakes (`ScriptedLLM`, `MagicMock`); `tests/` está fora do escopo, sem efeito.
- **Conflito com specs em voo:** `pyproject.toml` (`include`) e `.basedpyright/baseline.json`; R9 na `main` depois do pouso evita conflito no branch.

## 8. Decisões para o dono (recomendação primeiro)

- **D-426-1 — Retorno estruturado do protocolo.** `object` (aceita todos os implementadores sem tocar `llm_setup.py`) contra `AIMessage | BaseModel` (mensagem mais legível, mas `MockLLM`/`RoutedLLM` deixam de satisfazer o protocolo sem anotar `llm_setup.py`/`mock_llm.py`). Recomendação: `object`.
- **D-426-2 — Teto de RAM.** (a) 2,0 GB, igual à 418, cortando `agents/` pela ordem de R6; (b) 2,5 GB, porque o gate roda sozinho e só com ≥ 3 GB livres. Recomendação: (a); a máquina já travou e o corte preserva o núcleo.
- **D-426-3 — Quem amplia a baseline.** (a) coordenador, um commit na `main` após o pouso (R9); (b) coordenador roda `--update` no branch e pousa com o `types` do `land_check` em FAIL aceito. Recomendação: (a); (b) ensina a ignorar o gate.
- **D-426-4 — `storyteller.py` no escopo.** (a) entra se couber em R6 (pega erro novo no corpo, mas o narrador segue cego por `Any`); (b) fica fora até o follow-up de `_StoryTurn`. Recomendação: (a), sabendo que é o primeiro a sair no corte.
- **D-426-5 — `.basedpyright/baseline.json` no `baseline_growth.py`.** Follow-up (o `--land` já cobre) contra incluir aqui. Recomendação: follow-up.
