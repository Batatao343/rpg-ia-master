# SPEC-379 — revisão independente da spec `draft` (antes da aprovação)

> **Veredito:** `SAFE-WITH-CHANGES` (equivale a `CHANGES_REQUIRED` na spec, não no código: não há P0. Há 2 P1 que fazem o oráculo central R2.3 falhar ou enfraquecer guardas, e precisam entrar no texto antes de `approved`)
> **Revisor:** Sol (Opus, `spec-reviewer`) · **Data:** 2026-11-03 · **Commit revisado:** `main` em `bcddd605` (a spec cita `5fd2e920`)

## Escopo

Revisei só `specs/SPEC-379-refactor-testes-fabricas-cobertura.md`, contra o source da `main`, a
auditoria §6/§6.5 e as specs vizinhas 375, 380, 381 e 383. Não há código implementado. Não editei
spec, código, testes, `pyproject.toml` nem `uv.lock`. As sondas foram `uv run --frozen --with
pytest-cov` (ambiente efêmero, lock intocado), um script de scratchpad com saves e cache isolados
em tmp e um pytest focado `-n 2`.

## Verificação por requisito

| Req. | Situação | Evidência |
|---|---|---|
| §1 contagens | OK (deriva pequena) | Hoje: 711 arquivos `test_*.py` (spec: 696); 7.238 `def test_` (7.145); `def _state(` em 82 (81); `def _player(` em 33; 130 `def with_structured_output` em 96 arquivos (128/94); 0 `MagicMock`; `assert True` em `test_error_envelope.py:163` confirmado. A suíte cresce em paralelo; os números são "≈". |
| R1.1 lock/requirements | OK | Nenhuma branch aberta toca `pyproject.toml` nem `uv.lock` (W1 rodada 2×). `coverage` não está no lock hoje, então entra como pacote novo. pytest 9.1.1, pluggy 1.6.0 e xdist 3.8.0 já satisfazem pytest-cov 7.1.0 / coverage 7.17.1 (resolvidos pela sonda): sem bump esperado. `requirements.txt` sai de `uv export --frozen --no-dev` e não muda. `test_spec192_vercel_packaging.py:41-53` e `test_api_fuzz_harness.py:114-119` continuam válidos. **Não existe `requirements-vercel.txt`.** Nenhum teste compara lock × requirements além do "subconjunto". |
| R1 xdist/conftest | OK | Sonda: `-n 2 --cov=services.chronicle --cov-branch tests/test_fase31.py` verde em 25 s com o basetemp curto do conftest. Com pytest-cov 7, subprocessos não são medidos (bate com D5) e nenhum teste usa `settrace`/`sys.monitoring`/`COV_CORE`. Efeito colateral: grava `.coverage` na raiz do checkout. Removi o arquivo; o R1.3 resolve. |
| R1.4 contratos de workflow | OK com lacunas (P1-3) | `test_workflows_contract.py:19-40`, `test_ci_docs_only.py:107-111` e `scripts/release/checklist.py:306-325` (mesma higiene) conferidos. Faltam `uv sync --extra anthropic` e `timeout-minutes`. |
| R1.2 denominador | P2-1 | `source=["."]` lista também arquivos **nunca importados**. Na máquina local isso puxa `.tmp/spec176-clean*/api.py` (cópias antigas), `playtest_runs/`, `saves*/`, `project_index/`, `frontend/`, `infra/` e `de/`. |
| R2.1 divergência api × runner | OK | 13 campos confirmados por grep (`api.py:5330-5460` × `playtest/runner.py:370-525`). |
| R2.3 paridade via `api.game_graph` | **Viável, mas falha como escrito (P1-1)** | O seam funciona (`POST /game/new` → 200, 67 ms, grafo de captura). Só que **dois `POST /game/new` idênticos já dão `world` diferente**: `world.season`, `world.date.*` e `world_sim.calendar.epoch_offset` (135 × 95) dependem do `game_id` (`world_calendar.init_new_game` → `create_calendar(game_id, day)`, `services/world_calendar.py:111,641`). |
| R2.5 sem LLM × R2.3 | OK hoje, frágil (P2-2) | A API chama o criador com `use_llm_flavor=True` (`api.py:5343`; a sonda contou 1 `get_llm`). A fábrica usa `False`. Sob MockLLM o inventário sai igual (`Kit de Viajante` vem do equipamento canônico), mas isso só vale enquanto o flavor do MockLLM não trouxer item novo. |
| R3.3 `failing()` | Correto, com dois buracos (P2-3, P2-4) | `FallbackLLM` (`llm_setup.py:398-420`) tem `is_fallback=True`, não tem `stream_structured` e `invoke(self, _input)` aceita 1 argumento. O `RoutedLLM` esgotado tem `is_fallback=False`, **tem** `stream_structured`/`stream_text` e devolve `AIMessage("")` (`:1357-1424`). `failing()` com o default é um híbrido: exercita o guard `isinstance`, mas não o caminho de stream do produto. |
| R4 migração | OK | W1 não acha travas sobre os 18 candidatos da §3.5. A regra R4.3 (ausência de chave ⇒ não migra) e o R4.4 (`F811` ignorado) estão corretos. |
| R6 inventário | Incompleto e com 2 (b) errados (P1-2, P2-5) | Ver achados. |
| Choques 375/380/381/383 | OK | 375 mexe em `eval-gates.yml`/`validate.yml`, não no `coverage.yml` novo. 380 deixa a cobertura para a 379. 381:209,491 espera a 379 para os testes de AST. 383 §3.5:218-222 tem fallback ("se a 379 R6 ainda não tiver tratado"). Há uma divergência menor: a 383 diz que `design.test.mjs:108-111` fica "sem mudança (fica no App)", e a 379 o reancora em `web/src/**`. As duas são compatíveis. |

## Fatos errados ou desatualizados

- Branches: `spec-367` e `spec-368` **não existem mais** em `refs/heads`. As abertas com commits à frente da `main` são `spec-359`, `370`, `371`, `372`, `373`, `374`, `bst-*` (10), mais as velhas `spec-214` (toca `api.py`), `spec-349-pre-sync` (68 commits), `feat/*`, `refactor/*` e `idx5`. **O comando W1 trata essas branches velhas como travas** e vai bloquear etapas à toa. O executor precisa de uma lista de branches mortas excluídas (decisão do coordenador).
- W1 real hoje: `spec-371` toca `character_creator.py` e `playtest/runner.py` (reação inicial da Postura em `_resolve_starting_cards`/`keep_starting_reaction`) e `web/e2e/dossiers.spec.ts`. `spec-370` toca `world_utils.py`. Nenhuma delas toca arquivo que a 379 escreve, mas são **peças que a fábrica compõe**. Quando pousarem, a ficha muda e a paridade R2.3 acompanha automaticamente (é o objetivo). Os ids de cartas em testes migrados podem mudar; a prova R4.2 tem de ser refeita depois do rebase.
- O "único leitor de `App.tsx` fora do pytest" está certo, mas `tests/test_ci_eval_gates.py:21` cita `web\src\App.tsx` como string. Não lê o arquivo, então é "não se aplica".
- R6.4 incompleto (leitores de `api.py`): faltam `tests/test_spec299_prisoner_api.py:72`, `test_spec305_perception.py:154`, `test_spec352_creature_portraits.py:409` e `silent_except_scan.py:16`.
- R6.1 incompleto (leitores de `web/src` não citados): `tests/test_error_envelope.py:179` (`errorCodes.json`, contrato Python↔TS → (c)) e `tests/test_frontend_visual_contracts.py:25,52` (`styles.css`, opt-in `browser_local` → (c)). Os Greps do R6.1 não pegam `.json`; é preciso incluir essa extensão.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | spec R2.3, §3.3 (`make_state`/`_base`) | O calendário é seedado pelo `game_id` (`services/world_calendar.py:111`, `init_new_game` em `:631-641`). Comparar "o `world` inteiro" com um `POST /game/new` (uuid4) falha por estação/mês/`epoch_offset`. Além disso, `_base` em cache por `(class, race, region, level)` com `s["game_id"]=game_id` **depois** gera estado incoerente: `make_state(game_id="g1")` fica com o calendário de outro id, coisa que o produto nunca produz. Teste de calendário ou estação migrado passaria por outra razão. | (1) No R2.3, fixar o uuid da API (`monkeypatch.setattr(api.uuid, "uuid4", lambda: UUID(...))`) e chamar `make_state(game_id=str(esse uuid))`, sem normalizar `world`/`world_sim`. (2) Pôr `game_id` na chave do cache e rodar `init_new_game` com o `game_id` final, ou proibir override de `game_id` depois do cache. (3) Novo teste `test_calendar_follows_game_id`: dois `game_id` distintos dão `world_sim.calendar` igual ao da API com os mesmos ids. (4) Normalizar `name` só se o teste usar outro nome; melhor usar o mesmo nome, porque `narrative_summary` e `messages` também o contêm. |
| P1-2 | P1 | spec §3.6, linha de `test_spec361_integracao.py:324` | Classificado como (b). As asserções `:316-323` chamam `api._drain_creature_gen()` **direto**: provam que a drenagem é rápida, não que `_execute_action` deixou de drenar sob o lock. O `getsource` é a única guarda da regra "nada drena sob o lock do jogo" (R2-P1-2 da 361). As asserções restantes são de tempo (< 0,2 s), que a própria §7 aponta como frágeis sob cobertura. | Reclassificar para **(c)**, com trava **381** (lê `api._execute_action`; a 381 só reancora se o nome mudar). Se quiser (a), o teste novo tem de executar `_execute_action` com um job lento e provar que o lock fica livre. |
| P1-3 | P1 | spec R1.4 | O workflow não diz como instalar. `validate.yml:57` usa `uv sync --extra anthropic` porque a suíte cobre o builder Anthropic. Sem o extra, o job de cobertura gera falhas falsas (D4 as engole como `::warning`, e a baseline R1.7 fica com "testes que falham só sob cobertura" que na verdade falham por dependência). Também falta `timeout-minutes`: o `test` do validate tem 30, e com o tracer de 1,5 a 3× o tempo pode estourar. | R1.4: `uv sync --extra anthropic` (igual ao `test` do validate), `timeout-minutes: 60`, `checkout` com `persist-credentials: false` e upload do artefato com `if: always()`. Para a D4, usar `continue-on-error` no step do pytest mais um step que falha se `coverage.json` não existir. |
| P2-1 | P2 | spec R1.2/D2 | `source=["."]` reporta arquivos não importados em diretórios fora da lista de omit (`.tmp/`, `playtest_runs/`, `saves*/`, `project_index/`, `frontend/`, `infra/`, `de/`, `config/`, `assets/`, `readiness_artifacts/`). A baseline local (alternativa D3) sai poluída. | Trocar por `source` explícito (`agents`, `services`, `infrastructure`, `workers`, `playtest`, `evals` mais os módulos da raiz via `include`) ou acrescentar esses diretórios ao `omit`. |
| P2-2 | P2 | spec R2.1/R2.5 | A API cria a ficha com `use_llm_flavor=True`; a fábrica, com `False`. Hoje dá igual sob MockLLM, mas a igualdade depende do conteúdo do MockLLM. | Declarar na spec: "a paridade R2.3 roda sob MockLLM. Se o flavor do mock passar a acrescentar item, a fábrica adota `use_llm_flavor=True` sob mock ou o R2.3 normaliza só `inventory` com justificativa". |
| P2-3 | P2 | spec R3.1, §3.4 | `invoke(self, messages, *a, **k)` aceita kwargs que o `FallbackLLM.invoke(self, _input)` e o `RoutedLLM.invoke(self, input)` **rejeitam**. Um nó novo que chame `.invoke(msgs, config=...)` passa no fake e quebra no produto. | `invoke(self, input, /)`, com 1 posicional e sem kwargs. Se algum fake atual precisar de mais, o arquivo não migra. O mesmo vale para o `invoke` do objeto devolvido por `with_structured_output`. |
| P2-4 | P2 | spec R3.3 | (a) O teste `test_failing_matches_fallback_llm_in_product_guard` não distingue "devolveu AIMessage" de "levantou exceção": o criador cai no mesmo default nos dois casos, e também com `use_llm_flavor=False`. (b) Não há modo que imite o `RoutedLLM` esgotado (`is_fallback=False` **com** `stream_structured` devolvendo `AIMessage("")`), que é o caso real de produção em `narrative_sink.py:341,379`. | (a) Afirmar também `isinstance(llm.with_structured_output(X).invoke(m), AIMessage)` e `len(llm.calls)==1`. (b) `ScriptedLLM.failing(streaming=True)`: `stream_structured`/`stream_text` devolvem `AIMessage(text)` sem chamar `on_delta`. Mais um teste no `test_scripted_llm.py`. |
| P2-5 | P2 | spec §3.6, `test_spec303_hook.py:82-84` (b) e `test_frontend_accessibility_contracts.py` (b) | (1) O `boom` monkeypatcha `wd.request_crisis_slot` e roda um único cenário (`run(st,2,30)`). Um `from ... import request_crisis_slot` em `world_calendar` escaparia do patch; a varredura do texto pega. (2) A regra `image-alt` do axe só exige que exista `alt`. Não prova `alt={scene.asset.alt}` (o alt vem do dado). A proibição de `aria-label` em `div` sem `role` depende das regras e do nível de impacto que a suíte axe do repo bloqueia. | (1) Manter como **(c)** (proibição de chamada, categoria já prevista no R6.2). (2) O e2e de `visual-cue` afirma `toHaveAttribute('alt', <alt da fixture>)` e, se o axe do repo não bloquear `aria-prohibited-attr`, afirma ausência de `aria-label` no contêiner `.scene-art`. Só então (b). |
| P2-6 | P2 | spec §7, W1 | As branches velhas (`spec-214`, `spec-349-pre-sync`, `feat/*`, `refactor/*`, `spec-176-*`, `spec-348`, `spec-350-fix`, `idx5`) entram no W1 e travam etapas sem motivo. `spec-214` "toca" `api.py`. | Etapa 0: o coordenador publica a lista de branches mortas excluídas do W1, sem apagar nenhuma (W8). |
| P2-7 | P2 | spec R1.1 | A asserção "sem `-version = `" não pega mudança de `[package.metadata.requires-dev]` nem de `revision`. | Acrescentar: `git diff uv.lock` só pode ter linhas `+`, fora as do bloco `requires-dev` do projeto e a lista `dev` em `[package.dev-dependencies]`. |

## Riscos

- O R3 não mascara bug de guard no produto: o `ScriptedLLM` só substitui fakes de teste. O risco é o contrário: o fake ser mais permissivo que o produto (P2-3).
- A migração R4 fica mais fraca quando o estado canônico torna verdadeira uma condição que o helper parcial deixava falsa. O R4.3 cobre isso. O P1-1 adiciona o caso do calendário: estação diferente do helper antigo, que não tinha `world_sim`.
- Sessões paralelas: `tests/test_spec367_fallback_portrait.py` estava modificado e não commitado no checkout principal durante a revisão (outra sessão). Os executores da 379 trabalham só em worktree.

## Pendências

- Antes de `approved`: incorporar P1-1, P1-2 e P1-3 no texto. Os P2 podem entrar como ajuste do executor na Etapa 0 ou 1.
- W7 (refazer a prova do R4.2) não se aplica a esta revisão de spec; fica para a revisão do código.

## Comandos rodados

```text
W1 (git diff --name-only main...$b por branch, 2×) → nenhuma trava sobre arquivos escritos pela 379; 371 toca character_creator/runner/dossiers.spec.ts; 370 toca world_utils
uv run --frozen --with pytest-cov python -c "import pytest_cov,coverage" → 7.1.0 / 7.17.1; uv.lock e pyproject sem diff
uv run --frozen --with pytest-cov pytest -q -p no:cacheprovider -n 2 --cov=services.chronicle --cov-branch tests/test_fase31.py → verde, 25 s, cov 52 %; .coverage na raiz removido
probe (scratchpad, saves/cache em tmp): 2× POST /game/new com grafo de captura → 200; world/world_sim diferem por game_id; criador chamado com 1 get_llm; inventário igual com use_llm_flavor True/False sob MockLLM
git grep (getsource / ast.parse / read_text / web/src / api.py) em tests e web/tests → lacunas do inventário listadas acima
```
