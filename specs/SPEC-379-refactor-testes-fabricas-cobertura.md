# SPEC-379 — Testes: fábricas de estado, fake único de LLM, cobertura real e testes que leem código-fonte

> **Status:** `draft`
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** auditoria de qualidade de 03/11, [docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md](../docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md) §4.6 (itens 1–3 e "Cobertura") e §5 letras **H + I**; regras da onda **W1–W8** (§6.2). Fica de fora o que a §6.4 retirou: **não** renomear os 299 `test_specNNN_*`.
> **Depende de:** nada para começar (§6.3 da auditoria: "pode começar já"). Cada etapa passa pela trava **W1** antes de começar. **W6**: é a única spec de refatoração da onda em voo enquanto estiver `in-progress`.
> **Desbloqueia:** **SPEC-383** (front: hooks e e2e). A 383 depende do **R6** desta: os testes que leem `web/src/App.tsx` precisam estar resolvidos antes de ela fatiar o `App.tsx`. Também deixa pronto o terreno da SPEC-381 (lista dos testes que leem `api.py`, coluna "trava" da §3.6).
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma etapa por vez · **REVIEW_MODEL:** `Sol` (Opus, `spec-reviewer` independente) · **REVIEW_REQUIRED:** `true` (W7: o revisor refaz por conta própria a prova de equivalência do R4 em pelo menos 1 arquivo migrado)
> **EVAL_AUTHORING_REQUIRED:** `false`. Nenhum evaluator, expected, dataset de regressão, baseline ou caminho de `evals/protected-paths.txt` muda (W5). `tests/test_spec360_eval.py` e `tests/fixtures/spec330_legacy_golden.json` ficam intocados.

Rótulos: **[F]** fato verificado no source (checkout principal, `main` em `5fd2e920`, 03/11) · **[H]** hipótese com evidência, que a Etapa 0 ou o primeiro teste confirma ou derruba · **[D]** decisão do dono (§8, com default).

---

## 1. Contexto & Objetivo

A suíte é grande e honesta: **[F]** 696 arquivos `tests/test_*.py`, 7.145 funções `def test_` (contagem por Grep; o total coletado é maior por causa do `parametrize`), zero `MagicMock`/`unittest.mock` e um único `assert True` (`tests/test_error_envelope.py:163`). O problema não é a qualidade da asserção. O problema é a **duplicação de andaime** e a falta de medida:

1. **Construtores de estado copiados** — **[F]** `def _state(` aparece em 81 arquivos e `def _player(` em ~32. Há ainda `make_state`/`base_state`/`_base_state`/`make_player` em +16, incluindo **helpers por spec que já existem** (`tests/spec299_helpers.py:10`, `spec300_helpers.py:44`, `spec301_support.py:11`, `spec302_helpers.py:15`, `spec305_helpers.py:12`, `spec310_helpers.py:15`, `spec312_helpers.py:18`, `spec325_helpers.py:12`). Cada um inventa seus próprios defaults: `tests/test_fase26.py:26-35` usa `"current_location": "nova_arcadia"` (um id no campo de nome), `tests/test_checkpoints.py:23-45` ainda usa `known_abilities`, que saiu do schema na troca para Cartas.
2. **Fakes de LLM copiados** — **[F]** 128 definições de `with_structured_output` em 94 arquivos. `_FakeStoryLLM` aparece em `test_fase26.py:331`, `test_fase33.py:298` e `test_mvp.py:216`, mais a variante `_FakeStoryLLM34` em `test_fase34.py:264`. `_CountingLLM` aparece em `test_day_digest_inline.py:18`, `test_conflito_tatica.py:13`, `test_interlocutor.py:13` e `test_spec302_perception.py:119`. `_FakeLLM` aparece em `test_encounter_identity_repro.py:37`, `test_spec301_llm.py:20` e `test_spec325_objects.py:134`. `ScriptedLLM` está em `test_prompt_injection_corpus.py:29`. Nenhum desses fakes tem um modo que devolva `AIMessage`, como faz o `FallbackLLM` (`llm_setup.py:398-420`). Por isso o guard obrigatório (AGENTS.md, "Guard de resiliência") quase nunca é exercitado pelos fakes.
3. **Testes que leem código-fonte** e procuram substring ou posição de texto. Eles quebram em refatoração pura e não provam comportamento. O exemplo mais frágil é `tests/test_frontend_auth_bootstrap.py:4-9`, que compara as **posições** de três strings dentro de `web/src/App.tsx`. A SPEC-383 vai fatiar exatamente esse arquivo.
4. **Sem cobertura medida** — **[F]** o grupo `dev` (`pyproject.toml:49-54`) não tem `pytest-cov`. A auditoria chutou de 70 a 85 % no núcleo, sem número real.

O objetivo é dar ao repositório **uma** fábrica de estado e **um** fake de LLM, provar que os dois servem migrando no máximo ~20 arquivos sem mudar nenhuma asserção, medir a cobertura toda semana sem virar gate e resolver os testes que leem fonte, começando pelos que travam a SPEC-383. **Não** é migração em massa. O dono pediu muito cuidado para não quebrar nada, e há sessões paralelas adicionando testes agora (branches `spec-367`, `spec-368`, `spec-370` a `spec-374` e `bst-*`; **[F]** `.git/refs/heads/`).

**Estimativa honesta de linhas.** A auditoria estimou −5.000 (§4.6) para a migração **completa** dos 127 construtores, dos 128 fakes e dos ~29 testes de substring. Esta spec migra no máximo ~20 arquivos, então o saldo fica bem menor:

- **Entra:** fábricas e fake (~330), os testes deles (~270), o script de resumo de cobertura e o teste dele (~140), o workflow (~55), as configurações em `pyproject.toml`/`.gitignore` (~25), a documentação (~80) e os e2e que substituem leitura de fonte (~100–150). Total de **+1.000 a +1.050**.
- **Sai:** os helpers e fakes locais dos ≤ 20 arquivos (~15–30 linhas por arquivo, −300 a −550) e os testes de substring apagados ou trocados (−80 a −150). Total de **−380 a −700**.
- **Saldo líquido: ≈ +300 a +650 linhas.** O repositório **cresce** nesta spec. O ganho é estrutural: o próximo teste não copia andaime. O −3.000 a −5.000 só aparece se a migração continuar oportunisticamente em specs futuras (R5), arquivo a arquivo, quando cada um for tocado por outro motivo.

## 2. Requisitos

### R1 — Cobertura real, semanal, sem gate

- **R1.1** `pytest-cov` entra no grupo `dev` de `[dependency-groups]` (`pyproject.toml:49`). A instalação é `uv add --dev pytest-cov`, e `uv.lock` muda no mesmo commit. O diff de `uv.lock` se limita a acrescentar `pytest-cov`, `coverage` e a lista do grupo `dev`. **Nenhum** pacote existente muda de versão (asserção: `git diff uv.lock` sem nenhuma linha `-version = ` de outro pacote). **`requirements.txt` não muda**: ele é o export de runtime, e `tests/test_spec192_vercel_packaging.py:41-53` exige que seja um subconjunto do lock e não contenha `pytest`.
- **R1.2** `[tool.coverage.run]` em `pyproject.toml` define `branch = true`, `relative_files = true`, `source = ["."]` e `omit`, conforme o denominador da **D2**. `[tool.coverage.report]` define `skip_empty = true` e `precision = 1`. Sem `fail_under`.
- **R1.3** `.gitignore` passa a ignorar `.coverage`, `.coverage.*`, `coverage.xml`, `coverage.json` e `htmlcov/` (asserção: `git check-ignore -q` devolve 0 para cada um).
- **R1.4** Um workflow novo, `.github/workflows/coverage.yml`, roda com `schedule` semanal (cron da **D6**) e `workflow_dispatch`. Ele executa `uv run pytest -q -n auto -p no:cacheprovider --cov --cov-branch --cov-report=xml --cov-report=json`, publica um artefato (`coverage.xml`, `coverage.json` e o log do pytest) com `retention-days: 30` e escreve no `$GITHUB_STEP_SUMMARY` o total de linhas e de ramos mais a tabela dos **20 módulos menos cobertos**. **Não** há gate de porcentagem. A conduta quando um teste falha sob cobertura segue a **D4**. O workflow precisa passar nos contratos que já existem para todos os `*.yml`:
  - `permissions` no topo (`tests/test_workflows_contract.py:19-23`);
  - actions pinadas por SHA com comentário `# vN` (`:31-40`; usar os mesmos SHAs de `validate.yml:22,39,67`);
  - sem `pull_request_target` (`:26-28`);
  - `runs-on: ubuntu-24.04`, nunca `ubuntu-latest` (`tests/test_ci_docs_only.py:107-111`).
- **R1.5** `scripts/dev/coverage_summary.py <coverage.json> --top N [--min-statements K]` imprime em Markdown uma tabela `módulo | linhas | % linhas | ramos | % ramos`, em ordem crescente de `% linhas` e com empate desempatado pelo caminho, mais uma linha de total. A saída é determinística para a mesma entrada. Ele é testado por `tests/test_coverage_summary.py` com um `coverage.json` sintético.
- **R1.6** `docs/guias/TESTES.md` ganha a seção "Cobertura". Ela traz o comando local **com escopo** (`bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 --cov=<pacote> --cov-branch --cov-report=term-missing:skip-covered tests/test_<escopo>*.py`), deixa claro que a cobertura da suíte completa é do coordenador ou do CI, nunca de subagente (regra de RAM), e lista os limites conhecidos: subprocessos não medidos (**D5**) e testes de tempo sensíveis ao tracer (§7).
- **R1.7** A baseline fica registrada em `docs/spec379/coverage-baseline.md`, com data, SHA, comando, total de linhas e de ramos, o top 20, o tempo da suíte com e sem cobertura e os testes que falharam só sob cobertura, se houver. A fonte da baseline segue a **D3**.

### R2 — `tests/factories.py`: estado a partir das peças canônicas do produto

- **R2.1** **[F] Não existe uma função canônica única de estado inicial no produto.** O estado de jogo novo é montado **inline** em dois lugares que divergem:
  - `api._create_game`, dict literal em `api.py:5350-5456` (seguido de `normalize_player_progression` e `world_calendar.init_new_game` em `:5457-5460`);
  - `playtest/runner._build_initial_state` (`playtest/runner.py:370-521`), cuja docstring diz "MESMO shape de api.new_game".

  O runner **não** tem os campos de topo `processed_action_ids`, `visual_seen_entity_ids`, `visual_cue_ledger`, `game_over`, `death_pending`, `event_rejections`, `art_arc_budgets` e `art_generation_ledger`, nem os campos de player `race_id`, `origin_region_id`, `vitalidade_max_penalty`, `appearance` e `visual_exclusions`. Também não chama `normalize_player_progression`.

  As **peças** canônicas são:
  - `character_creator.create_player_character(user_input, *, use_llm_flavor=...)` (`character_creator.py:308`). Com `use_llm_flavor=False` ele **não chama `get_llm`** e é determinístico (`:343`, `:372-376`);
  - `gamedata.sync_vitality` (`gamedata.py:444`, chamado em `api.py` antes de montar o estado);
  - `world_utils.starting_world(region, level)` (`world_utils.py:1924-1944`);
  - `gamedata.seed_factions()` (`gamedata.py:149`);
  - `progression.normalize_player_progression` (`progression.py:275`);
  - `services.world_calendar.init_new_game(state)` (`services/world_calendar.py:631`);
  - os defaults de personagem do próprio produto: `playtest.runner._DEFAULT_CHAR` (`runner.py:332-338`: Devoto do Abismo, Humano, Nova Arcádia, nível 1) e o nome default `"Herói"` do criador (`character_creator.py:311`).

  `make_state` compõe **essas peças**, na mesma ordem de `api._create_game`, sem inventar defaults. A única exceção declarada é o `game_id` (constante `"factory-game"`, porque o produto usa `uuid4`). A forma da composição segue a **D1**.
- **R2.2** Assinaturas:
  - `make_player(*, class_name=None, race=None, region=None, level=1, **overrides) -> dict`;
  - `make_world(*, region=None, level=1, **overrides) -> dict`;
  - `make_state(*, game_id="factory-game", class_name=None, race=None, region=None, level=1, player=None, world=None, **overrides) -> dict`.

  Em `make_state`, `player`/`world` fazem merge raso sobre o canônico e cada chave de `overrides` substitui a chave de topo inteira.
- **R2.3** **Paridade com o produto (oráculo de comportamento, sem ler fonte).** `tests/test_factories.py::test_make_state_matches_api_new_game` troca `api.game_graph` por um grafo que captura o `initial_state` recebido (o mesmo seam de `tests/test_hardening_persistencia_sse.py:105`). Depois faz `POST /game/new` via `TestClient` com o mesmo personagem e afirma igualdade das chaves de topo, das chaves de `player`, do `world` inteiro e dos valores de `player` (normalizando `game_id`, `name` e `appearance`). Se o `api._create_game` ganhar ou perder um campo, esse teste falha. Esse é o guard contra deriva.
- **R2.4** Isolamento: duas chamadas devolvem objetos independentes (mutar `make_state()["player"]["inventory"]` não afeta a próxima chamada). A base fica em cache por `(class_name, race, region, level)` e cada chamada devolve `copy.deepcopy`, para a fábrica não pesar na suíte.
- **R2.5** Sem LLM: com `character_creator.get_llm` trocado por uma função que levanta exceção, `make_state()` funciona.
- **R2.6** Round-trip: `persistence.save_game_state(make_state())` seguido de `load_game_state(<arquivo>)` devolve o mesmo `player` e o mesmo `world`. O `conftest.py` já isola `saves/` (`tests/conftest.py:78-98`).

### R3 — `tests/fakes/scripted_llm.py`: um fake de LLM para a suíte

- **R3.1** `ScriptedLLM` substitui o que `get_llm()` devolve nos testes. Ele **não** substitui nem duplica o `MockLLM` (`mock_llm.py:1024`), que é do produto e gera conteúdo plausível para jogar offline. O `ScriptedLLM` devolve **só o que o teste roteirizou** e falha alto quando falta roteiro. Interface:
  - `with_structured_output(schema, *a, **k)` devolve um objeto com `invoke`. Recusa `include_raw=True` com `NotImplementedError`, porque nenhum nó usa isso fora de `llm_setup.py:832-1001`;
  - `with_retry(*a, **k)` e `bind_tools(*a, **k)` devolvem `self`;
  - `invoke(messages, *a, **k) -> AIMessage`;
  - `stream(messages, *a, **k)` gera `AIMessageChunk`s cuja concatenação é o texto roteirizado.
- **R3.2** Respostas são **roteirizadas por schema**: `responses={StoryUpdate: ..., "NPCResponse": ...}`, com a chave sendo a classe ou `__name__`. Cada valor pode ser:
  - uma instância;
  - um `dict`, validado com `schema.model_validate`;
  - um callable `(messages, schema) -> objeto`;
  - uma `Exception`, que é levantada;
  - um `AIMessage`, devolvido como está;
  - uma lista desses valores, consumida em ordem. Quando a lista acaba, o fake levanta `AssertionError` com o nome do schema, a menos que `repeat_last=True`.

  Schema sem roteiro também levanta `AssertionError`, nunca inventa conteúdo.
- **R3.3** **Modo fallback:** `ScriptedLLM.failing(text="", *, is_fallback=False)` faz **todo** `with_structured_output(...).invoke` e todo `invoke` devolverem `AIMessage(content=text)`. É o mesmo contrato de `FallbackLLM.with_structured_output(...).invoke` (`llm_setup.py:410-417`). Por default `is_fallback=False`, para exercitar o guard `isinstance`/`try` e não o atalho `getattr(llm, "is_fallback")` (`agents/archivist.py:106`, `agents/combat.py:1784,1876`, `agents/loot.py:334`). O teste `test_failing_matches_fallback_llm_in_product_guard` afirma que `create_player_character(...)` produz a **mesma ficha** com `ScriptedLLM.failing()` e com `llm_setup.FallbackLLM("x")` (guard em `character_creator.py:362-370`).
- **R3.4** **Neutralidade de atributos.** Por default o fake **não** expõe `stream_structured`/`stream_text`, para que `services/narrative_sink.py:341,379` (`getattr(llm, "stream_structured", None)`) siga o caminho de `invoke`, igual aos fakes de hoje. Os dois métodos só existem com `streaming=True`. Também não expõe `is_mock` (`services/prologue.py:433` e `services/shared_pool.py:398-406` tratam mock de forma especial). Teste: `not hasattr(ScriptedLLM(), "stream_structured")` e `getattr(ScriptedLLM(), "is_mock", False) is False`.
- **R3.5** Gravação: `llm.calls` guarda uma lista de `(schema_name | None, messages, kwargs)` por invoke. Isso cobre os `_CountingLLM`/`_CaptureLLM`/`_SpyLLM` atuais.
- **R3.6** `patch_get_llm(monkeypatch, llm, *modules)` faz `monkeypatch.setattr(m, "get_llm", ...)` em cada módulo e registra `(temperature, tier)` em `llm.get_llm_calls`.

### R4 — Migração-prova, no máximo ~20 arquivos

- **R4.1** Migrar **no máximo 20** arquivos para `make_*`/`ScriptedLLM`, escolhidos por (i) **nenhuma branch aberta tocar o arquivo (W1)** e (ii) maior duplicação. Os candidatos estão na §3.5 e a Etapa 0 confirma a lista com o comando W1.
- **R4.2** **Um commit por arquivo (W4).** Cada commit traz no corpo a prova "antes/depois":
  - `pytest --collect-only -q <arquivo> | tail -1` com a mesma contagem;
  - a lista ordenada de ids que passaram (`pytest -q -rA <arquivo>`) idêntica;
  - `git diff` do arquivo mostrando que **nenhuma linha com `assert`/`pytest.raises`/`pytest.approx` mudou** (W3). Só podem mudar a definição e o uso de helpers e fakes.
- **R4.3** **Preservação de intenção.** Toda chave que o helper antigo fixava explicitamente é passada como override com o **mesmo valor** (ex.: `make_state(factions=[], quests=[], world={"turn_count": 5, ...})`). As chaves extras do canônico são aceitas só se o arquivo passar sem mudar asserção. Se algum teste depender da **ausência** de uma chave (`"x" not in state`, `state == {...}`, `len(state)`), esse arquivo **não migra** e entra no hand-back como "não migrável".
- **R4.4** Antes de remover um helper, faça Grep de `from tests.<arquivo> import` e `import tests.<arquivo>` em `tests/` (ex.: `tests/prompt_capture.py:10` importa `_story_state` de `test_ambient_consumers`). Se houver importador, o nome antigo continua no arquivo como alias da fábrica ou o arquivo não migra. Atenção: `F811` está ignorado em `tests/**` (`pyproject.toml:80`), então o ruff **não** avisa sobre redefinição silenciosa.
- **R4.5** Nenhum arquivo `test_specNNN_*` muda de nome. Nenhum arquivo de `evals/protected-paths.txt` é tocado.

### R5 — Regra para o futuro

- **R5.1** `docs/guias/TESTES.md` ganha a seção "Onde mora um teste novo":
  - teste novo vai para `tests/test_<modulo>.py` (ex.: `tests/test_conflict_orchestrator.py`) ou para um arquivo de **feature** (`tests/test_<feature>.py`), nunca para um `tests/test_specNNN_*.py` novo;
  - o número da spec vai na docstring do teste (`"""SPEC-379 R2.3: ..."""`) ou no marker da **D9**;
  - estado vem de `tests/factories.py` e LLM vem de `tests/fakes/scripted_llm.py`;
  - helper local só entra quando a fábrica não serve, com uma linha de comentário explicando o porquê;
  - teste que lê código-fonte só entra no caso (c) da §3.6, com a justificativa no docstring.
- **R5.2** `docs/guias/BRIEF_SUBAGENTE.md` § Testes ganha 3 linhas com a mesma regra e um link para a seção de TESTES.md.
- **R5.3** Na mesma edição, consertar o parágrafo quebrado de `docs/guias/TESTES.md:29-31`: a linha do fuzz (SPEC-338) foi inserida no meio do item sobre markers `*_local`. O conteúdo não muda.
- **R5.4** Um gate automático da regra (lista congelada dos nomes `test_specNNN` que só encolhe) fica para depois da onda (**D10**). Agora a regra é só documentação.

### R6 — Testes que leem código-fonte

- **R6.1** A Etapa 0 gera o **inventário completo** em `docs/spec379/fonte_inventario.md`, com uma linha por **função** de teste: arquivo:linha, o que lê, decisão e justificativa. O inventário usa estes Greps sobre `tests/`:
  - `inspect.getsource`;
  - `\.read_text\(` ou `read_bytes\(` cujo alvo é `.py`, `.ts`, `.tsx`, `.css`, `.html`, `.mjs` ou `__file__`;
  - `ast.parse(` sobre arquivo do produto;
  - variáveis `_SRC`/`SRC`/`source`/`src` alimentadas por `read_text`.

  Também entra o único leitor de `App.tsx` fora do pytest: `web/tests/design.test.mjs:91,108`. Falsos positivos (ex.: `tests/test_spec198_rename_package.py`, que lê arquivos que ele mesmo escreveu num repositório temporário) ficam listados como "não se aplica".

  **[F] A auditoria subestimou o número.** Os Greps acima já acham **≥ 45 arquivos** de pytest, não ~29. Exemplos: 40 arquivos com `src/source = ...read_text(`, 8 com `getsource` e os guards AST de `test_spec303_calendar.py:44,130`, `test_spec307_calendar.py:80,208`, `test_spec312_birth.py:171,183`, `test_spec315_truth.py:143` e `test_structured_output_guards.py:10-12`. A maioria desses leitores é guard legítimo, caso (c).
- **R6.2** Para cada função, a decisão é uma de três:
  - **(a)** trocar por teste de comportamento;
  - **(b)** apagar, citando qual teste ou e2e já cobre o mesmo comportamento (arquivo::função);
  - **(c)** manter, porque o fato só é verificável pelo fonte: proibição de import ou de chamada, guarda de segurança ou RLS, CSP e fontes self-hosted, integridade de eval ou contrato entre linguagens. Um (c) que depende da **posição** de texto ou do **nome do arquivo** é reancorado para não depender disso quando der (ex.: varrer `web/src/**` em vez de `App.tsx`).
- **R6.3** **Pré-requisito da SPEC-383:** todo teste que lê `web/src/App.tsx` fica resolvido e pousado na `main` **antes** de a 383 começar. São eles: `tests/test_frontend_auth_bootstrap.py:4-9`, `tests/test_visual_assets.py:207-217` e `web/tests/design.test.mjs:105-112`. A permissão por nome em `design.test.mjs:91` fica (c), mas o hand-back avisa a 383 que arquivos novos que importarem `motion` precisam entrar na allowlist.
- **R6.4** Os testes (c) que leem `api.py` por caminho são marcados na coluna "trava" com **381** e **não** são reancorados aqui (**D7**). Exemplos: `test_abuse_policy.py:158,386,408`, `test_abuse_logging.py:185`, `test_api_fuzz_harness.py:41`, `test_error_envelope.py:13`, `test_rls_runtime_config.py:257` e `test_structured_output_guards.py:12`.
- **R6.5** Toda troca (a) e toda remoção (b) é um commit próprio (W4). Uma troca (a) só entra quando o teste novo **falha** com o comportamento quebrado. A prova é feita localmente, sem commitar a quebra, e a quebra aplicada fica descrita no corpo do commit.

### Fora de escopo

- Renomear, fundir ou mover qualquer `test_specNNN_*` existente (§6.4 da auditoria). Consolidar 325/297/363/364 também fica de fora.
- Migrar mais de ~20 arquivos. A migração dos outros ~200 construtores e fakes é oportunística, em specs futuras (R5).
- Qualquer arquivo de produto: `api.py`, `agents/`, `services/`, `playtest/`, `mock_llm.py`, `llm_setup.py`, `character_creator.py`. Em particular, extrair `build_initial_state()` para o produto e unificar `api._create_game` com `playtest.runner._build_initial_state` fica de fora (**D1** opção B, spec futura depois da 381).
- `tests/conftest.py`: nenhuma mudança que altere isolamento (saves, memória, cache de runtime, embeddings, exposure env, basetemp do xdist).
- Caminhos de `evals/protected-paths.txt` (`tests/fixtures/spec330_legacy_golden.json`, `tests/test_spec360_eval.py`, `web/e2e/contracts/`, `scripts/fauna/eval.py`, `evals/core`…), conforme W5.
- Gate de cobertura (`--cov-fail-under`), cobertura do front (`web/`) e cobertura de subprocessos (**D5**).
- Os testes de leitura de fonte em `web/tests/*.mjs` que **não** leem `App.tsx` (`deck.test.mjs`, `storyLog.test.mjs`, `build.test.mjs`…).
- O `assert True` de `tests/test_error_envelope.py:163`.
- Corrigir a divergência de shape entre `api._create_game` e o runner de playtest. Ela só é registrada (R2.1), para virar follow-up.

## 3. Design técnico

### 3.1 Arquivos novos

| Caminho | Responsabilidade |
|---|---|
| `tests/factories.py` | `make_player`, `make_world`, `make_state` (R2) |
| `tests/fakes/scripted_llm.py` | `ScriptedLLM`, `patch_get_llm` (R3). O pacote `tests/fakes/` **já existe** (**[F]** `tests/fakes/__init__.py`, `fake_image_generator.py`, `local_auth.py`…) |
| `tests/test_factories.py` | R2.3–R2.6 |
| `tests/test_scripted_llm.py` | R3.2–R3.6 |
| `scripts/dev/coverage_summary.py` | R1.5 |
| `tests/test_coverage_summary.py` | R1.5 com um `coverage.json` sintético |
| `.github/workflows/coverage.yml` | R1.4 |
| `docs/spec379/fonte_inventario.md` | R6.1 |
| `docs/spec379/coverage-baseline.md` | R1.7 |
| `web/e2e/auth-bootstrap.spec.ts` (nome **[H]**, a Etapa 0 confere colisão) | R6 (a) de `test_frontend_auth_bootstrap.py` |
| `web/e2e/visual-cue.spec.ts` (nome **[H]**) | R6 (a) de `test_visual_assets.py:207-217` e (b) de `test_frontend_accessibility_contracts.py` (axe no mesmo cenário) |

### 3.2 Arquivos alterados

- `pyproject.toml`: `pytest-cov` no grupo `dev`, `[tool.coverage.run]` e `[tool.coverage.report]`. **Não** acrescentar `default-groups` (`tests/test_api_fuzz_harness.py:119` proíbe).
- `uv.lock`: só as adições de R1.1.
- `.gitignore`: R1.3.
- `docs/guias/TESTES.md`: seções "Cobertura" e "Onde mora um teste novo", mais o conserto de `:29-31`.
- `docs/guias/BRIEF_SUBAGENTE.md`: § Testes, +3 linhas.
- `web/tests/design.test.mjs:105-112`: o regex de `<MotionConfig reducedMotion="user"` deixa de ler `App.tsx` e passa a varrer `web/src/**/*.tsx` (ao menos um arquivo casa). O mesmo vale para o regex de `transition`.
- `tests/test_frontend_auth_bootstrap.py` e `tests/test_frontend_accessibility_contracts.py`: apagados depois que o e2e substituto passar (R6.5).
- `tests/test_visual_assets.py`: só a função `test_frontend_contract_contains_visual_flow` sai. O resto do arquivo fica.
- Os ≤ 20 arquivos do R4 e os arquivos com decisão (a)/(b) do R6.

**Lista branca do diff da branch:** os caminhos acima mais os arquivos de `tests/` listados no inventário e na §3.5. `git diff --name-only main...spec-379` não pode ter nenhum caminho fora de `tests/`, `docs/`, `scripts/dev/coverage_summary.py`, `.github/workflows/coverage.yml`, `pyproject.toml`, `uv.lock`, `.gitignore`, `web/e2e/` (fora de `web/e2e/contracts/`) e `web/tests/design.test.mjs`.

### 3.3 `tests/factories.py` (esboço da composição, D1 = A)

```python
from playtest.runner import _DEFAULT_CHAR  # defaults do produto (runner.py:332)
from character_creator import create_player_character
from gamedata import seed_factions, sync_vitality
from world_utils import starting_world
import progression
from services import world_calendar


@functools.lru_cache(maxsize=64)
def _base(class_name, race, region, level) -> dict: ...


#  1. char = create_player_character({**_DEFAULT_CHAR (sem backstory de harness), class/race/region/level},
#                                     use_llm_flavor=False); sync_vitality(char)
#  2. state = mesmas chaves e mesmos valores derivados do dict de api._create_game (api.py:5350-5456),
#     com req.* substituído pelos argumentos; messages = as mesmas duas mensagens de abertura
#  3. state["player"] = progression.normalize_player_progression(state["player"])
#  4. world_calendar.init_new_game(state)


def make_state(
    *,
    game_id="factory-game",
    class_name=None,
    race=None,
    region=None,
    level=1,
    player=None,
    world=None,
    **overrides,
) -> dict:
    s = copy.deepcopy(_base(...))
    s["game_id"] = game_id
    s["player"].update(player or {})
    s["world"].update(world or {})
    s.update(overrides)
    return s
```

`race_id`/`origin_region_id` vêm de `services.reputation.resolve_race_id`/`resolve_region_id` (`api.py:5315-5318`, `_reputation_ids`). A fábrica chama as mesmas funções e não importa o helper privado da API. O teste R2.3 garante que a cópia da lista de chaves não deriva.

### 3.4 `tests/fakes/scripted_llm.py` (assinaturas)

```python
class ScriptedLLM:
    is_fallback: bool  # False por default; nunca define is_mock
    calls: list[tuple[str | None, list, dict]]
    get_llm_calls: list[tuple[float | None, object | None]]

    def __init__(
        self,
        responses: Mapping[type | str, object] | None = None,
        *,
        text: str | Sequence[str] = "",
        repeat_last: bool = False,
        streaming: bool = False,
        is_fallback: bool = False,
    ) -> None: ...
    @classmethod
    def failing(cls, text: str = "", *, is_fallback: bool = False) -> "ScriptedLLM": ...
    def with_structured_output(self, schema, *a, **k) -> "_Bound": ...
    def with_retry(self, *a, **k) -> "ScriptedLLM": ...
    def bind_tools(self, *a, **k) -> "ScriptedLLM": ...
    def invoke(self, messages, *a, **k) -> AIMessage: ...
    def stream(self, messages, *a, **k) -> Iterator[AIMessageChunk]: ...

    # só com streaming=True: stream_structured(messages, schema, *, on_delta=None, on_reset=None, key=None)
    #                        stream_text(messages, *, on_delta=None, on_reset=None)
    #   (mesma assinatura do MockLLM, mock_llm.py:1053,1071)


def patch_get_llm(monkeypatch, llm: ScriptedLLM, *modules) -> ScriptedLLM: ...
```

Os fakes de hoje recebem `invoke(self, _msgs)` posicional (ex.: `test_fase26.py:344`). O `ScriptedLLM` aceita `*a, **k`, então é compatível com os dois estilos.

### 3.5 Candidatos do R4 (**[H]**, a Etapa 0 roda o W1 e corta o que estiver travado)

| # | Arquivo | O que migra | Evidência |
|---|---|---|---|
| 1–4 | `test_fase26.py`, `test_fase33.py`, `test_fase34.py`, `test_mvp.py` | `_FakeStoryLLM`/`_FakeStoryLLM34` → `ScriptedLLM({StoryUpdate: callable})` | `:331`, `:298`, `:264`, `:216` |
| 5–8 | `test_day_digest_inline.py`, `test_conflito_tatica.py`, `test_interlocutor.py`, `test_spec302_perception.py` | `_CountingLLM` → `ScriptedLLM(...).calls` | `:18`, `:13`, `:13`, `:119` |
| 9–10 | `test_encounter_identity_repro.py`, `test_spec301_llm.py` | `_FakeLLM` | `:37`, `:20` |
| 11 | `test_prompt_injection_corpus.py` | `ScriptedLLM` local → fake único (callable que valida o payload) | `:29-49` |
| 12–16 | `test_fase26.py`, `test_fase28.py`, `test_fase33.py`, `test_fase61.py`, `test_fase62.py` | `_state` → `make_state(**chaves fixadas)` (R4.3) | `:26`, `:24`, `:23`, `:28`, `:28` |
| 17–18 | `test_dossiers.py`, `test_checkpoints.py` | `_state` → `make_state` | `:18-40`, `:23-45` |

Ficam **fora** por W1 provável (cartas e combate em `spec-367`/`368`/`371`): `test_spec325_objects.py`, `test_card_shop.py` (`_state`/`_player` em `:25,38`), `test_conflito_*.py` e `test_card_*.py`. O teto é 20 arquivos distintos. Os arquivos 1/12 e 3/14 são o mesmo arquivo, com dois commits (um para o fake, outro para o estado).

### 3.6 R6: decisão preliminar (a Etapa 0 completa e confirma no inventário)

| Teste (arquivo:linha) | Lê | Decisão | Cobertura ou justificativa | Trava |
|---|---|---|---|---|
| `test_frontend_auth_bootstrap.py:4-9` | posição de 3 strings em `App.tsx` | **(a)** | e2e novo com o backend de fixture (`web/e2e/fixtures.ts:299` `authRequired/authenticated`, `:322` `/game/saves`): registra as requisições e afirma zero `/game/saves` antes do login e ao menos uma depois. **[F]** nenhum e2e atual afirma isso (Grep por `getSaves`/`/game/saves` em `web/e2e` só acha a fixture) | **383** |
| `test_visual_assets.py:207-217` | substrings em `App.tsx`, `CreateScreen.tsx`, `StoryLog.tsx`, `ChatSurface.tsx` | **(a)** | e2e novo: a fixture devolve `visual.cue` na ação e o teste afirma a arte de cena no chat e as imagens de raça/classe na criação. **[F]** nenhum e2e atual cobre `cue`/`scene-art` | **383** |
| `web/tests/design.test.mjs:105-112` | regex `<MotionConfig reducedMotion="user"` em `App.tsx` | **(c) reancorado** em `web/src/**` | o efeito do `reduce` em `motion/react` é difícil de observar; o comportamento CSS já é coberto em `web/e2e/effects.spec.ts:14` | **383** |
| `web/tests/design.test.mjs:90-103` | allowlist por nome de quem importa `motion` | **(c)** | proibição de import; avisar a 383 | 383 (aviso) |
| `test_frontend_accessibility_contracts.py:4-7` | `alt=` em `SceneArtwork.tsx` | **(b)** depois do e2e de `visual-cue` com `AxeBuilder` (regra `image-alt`) | o cenário de arte de cena passa a rodar sob axe | — |
| `test_spec297_review_fixes.py:183-187` | `getsource(storyteller_node)` contém `[-3:]` | **(a)** | storyteller com 5 `HumanMessage`, afirmando que `player_inputs` recebe as 3 últimas. O mesmo arquivo já captura `player_inputs` em `:170-180` | 382 |
| `test_spec303_passes.py:78-84` | `getsource(storyteller)` contém `world_calendar.CROSSING_NOTE` | **(a)** | viagem pela passagem fechada no inverno pelo storyteller, afirmando a nota no contexto do turno **[H]** | 382 |
| `test_bug_api_pending_erros.py:142-145` | `getsource(api)` sem `{req.backstory}` | **(a)** | `POST /game/new` com `backstory=None`, afirmando que `"None"` não aparece em `narrative_summary`/`messages` | 381 |
| `test_spec361_integracao.py:324` | `creature_gen` fora de `getsource(api._execute_action)` | **(b)** | coberto pelas asserções de comportamento do mesmo teste (`:316-323`: devolve em < 0,2 s, lock livre, job drenado) | 381 |
| `test_spec303_hook.py:82-84` | `request_crisis_slot` fora de `world_calendar.py` | **(b)** só da linha de fonte | o mesmo teste já monkeypatcha `boom` e prova o comportamento (`:86-…`) | — |
| `test_spec352_creature_portraits.py:462-463` | `shared_blob_store = blob_store` em `infrastructure/runtime.py` | **(a)** | montar o runtime e afirmar identidade dos objetos (`is`) **[H]** | — |
| `test_spec192_vercel_packaging.py:77-82` | contagem de `RPG_RUNTIME_PROFILE", "legacy"` em `persistence.py`/`rag.py` | **(b)** só das contagens, **[H]** | o mesmo teste prova o comportamento hosted com `tmp_path` | 378 |
| `test_bug_memoria_resiliencia.py:405-417` | `count(...) == 2` em `postgres_turns` | **(a)** se houver seam com pool fake; senão **(c)** | guarda de perfil de embedding | 378 |
| `test_dynamic_art_jobs.py:212`, `test_spec196_finops.py:669`, `test_spec279_usage_retention.py:49-54`, `test_postgres_claim_idempotency.py:4-12` | SQL dentro do código | **(c)**, ou **(b)** se um `*_local` (infra_local) cobrir a mesma consulta **[H]** | SQL sem banco na suíte default | — |
| `test_rls_runtime_config.py:243-260`, `test_abuse_policy.py:158,386,408`, `test_abuse_logging.py:185` | guardas de RLS e rate limit | **(c)** | segurança | 381 (api.py) |
| `test_spec313_catalog.py:102-118`, `test_spec347_creature_art.py:175-180`, `test_spec352_creature_portraits.py:413-418`, guards AST de 303/307/312/315/305, `test_structured_output_guards.py`, `test_agents_contract.py`, `silent_except_scan.py` | proibição de import, chamada ou padrão | **(c)** | convenção do projeto ("Mecânica é Python", "guard de FallbackLLM", sem `random` global) | 381/382 onde ler `api.py`/`agents/` |
| `test_spec347_creature_art.py:183-186` | chaves de ícone em `icons.tsx` | **(c)** | contrato entre Python e TS | — |
| `test_vercel_config.py:42-46` | `codex_body(` em `discovery.py` | **(c)** | guarda declarada da decisão D5 de deploy | — |
| `test_spec238_loot.py:342-344`, `test_spec217_j1.py:276` | integridade de experimento de eval | **(c)** | integridade de eval | — |
| `test_spec222_transparency.py:23-37` | fontes self-hosted (`index.html`, `fonts.css`, `main.tsx`) | **(c)** | privacidade e CSP | — |
| `test_eval_frontend.py` (vários) | higiene dos próprios e2e | **(c)** | contrato do harness de eval front | — |
| `test_spec198_rename_package.py` | arquivos escritos no repositório temporário | não se aplica | não lê o fonte real | — |

## 4. Plano passo a passo

Cada etapa começa pelo comando **W1** (§6.2 da auditoria), com os arquivos da etapa num `etapa_arquivos.txt`. Se a interseção não for vazia, **a etapa espera** e as outras podem seguir. Subagente roda só os testes do escopo, com no máximo `-n 2`, via `bash scripts/dev/py.sh -m pytest`. A suíte completa (W2.1) é do coordenador, uma vez, no pouso. W2.2 a W2.4 (evals, playtest, OpenAPI) **não se aplicam**: nenhum arquivo de produto muda, e a lista branca da §3.2 prova isso.

### Etapa 0 — Inventário, travas e linha de base (sem código)

1. Rodar o W1 com a lista inteira de candidatos (§3.5 e §3.6) e cortar os travados.
2. Gravar `pytest --collect-only -q | tail -1` (contagem total) e, para cada candidato do R4, a contagem por arquivo e a lista de ids que passam. Fica no scratchpad e entra no corpo de cada commit do R4.
3. Gerar `docs/spec379/fonte_inventario.md` (R6.1) com a decisão de cada função. Confirmar ou derrubar cada **[H]** da §3.6, citando o teste que cobre em cada (b).
4. Confirmar a versão de `pytest-cov`/`coverage` que o `uv` resolve e o comportamento com xdist (**[H]**: pytest-cov 7 removeu o suporte automático a subprocesso via `.pth`, e o caminho atual é `[tool.coverage.run] patch = ["subprocess"]`, o que importa só se a D5 mudar).
5. **Verificação:** commit `docs(spec-379): source-reading test inventory`.

### Etapa 1 — R2 fábricas (testes primeiro)

1. **Testes** (`tests/test_factories.py`):
   - `test_make_state_matches_api_new_game` (R2.3) afirma igualdade de chaves e valores com o `initial_state` capturado do `POST /game/new`;
   - `test_make_state_is_isolated` (R2.4) afirma que mutar uma chamada não vaza para a próxima;
   - `test_make_state_never_calls_llm` (R2.5) afirma que o `get_llm` que levanta exceção nunca é chamado;
   - `test_make_state_round_trip_save_load` (R2.6) afirma `player`/`world` iguais depois de save e load;
   - `test_overrides_merge_player_world_replace_top` (R2.2) afirma merge raso em `player`/`world` e substituição no topo;
   - `test_level_3_matches_api_level_3` afirma que a paridade vale também com `level>1`.
2. **Implementação:** `tests/factories.py` (§3.3).
3. **Verificação:** `bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_factories.py` verde, mais `ruff check`/`ruff format --check` dos arquivos novos.

### Etapa 2 — R3 fake único (testes primeiro)

1. **Testes** (`tests/test_scripted_llm.py`):
   - `test_dict_response_is_validated_by_schema`;
   - `test_sequence_is_consumed_in_order_and_fails_loud_when_exhausted`;
   - `test_unscripted_schema_fails_loud`;
   - `test_callable_receives_messages_and_schema`;
   - `test_exception_response_is_raised`;
   - `test_failing_returns_aimessage_for_structured_and_plain`;
   - `test_failing_matches_fallback_llm_in_product_guard` (R3.3);
   - `test_no_stream_structured_unless_streaming_and_no_is_mock` (R3.4);
   - `test_stream_concatenates_to_text`;
   - `test_calls_are_recorded`;
   - `test_patch_get_llm_records_tier`;
   - `test_include_raw_is_refused`.
2. **Implementação:** `tests/fakes/scripted_llm.py` (§3.4).
3. **Verificação:** os testes da etapa verdes.

### Etapa 3 — R1 cobertura

1. **Testes:** `tests/test_coverage_summary.py` cobre ordem crescente, desempate por caminho, `--top`, `--min-statements`, a linha de total e a saída idêntica em duas execuções. A suíte que já existe valida o workflow novo: `tests/test_workflows_contract.py` e `tests/test_ci_docs_only.py::test_ci_pins_runner_image_and_node_from_nvmrc`. `tests/test_gitignore_contract.py` não muda; o R1.3 é verificado com `git check-ignore` no hand-back.
2. **Implementação:**
   - `uv add --dev pytest-cov` (conferir o diff do lock, R1.1);
   - configuração de coverage no `pyproject.toml`;
   - `.gitignore`;
   - `scripts/dev/coverage_summary.py`;
   - `.github/workflows/coverage.yml`;
   - seção "Cobertura" em TESTES.md.
3. **Verificação:**
   - os testes da etapa verdes, mais `tests/test_workflows_contract.py tests/test_ci_docs_only.py tests/test_spec192_vercel_packaging.py tests/test_api_fuzz_harness.py`;
   - `git diff --stat requirements.txt` vazio;
   - 1 execução local **com escopo** (`-n 2 --cov=services.chronicle tests/test_fase31*.py` ou equivalente) prova que pytest-cov e xdist funcionam com o `conftest.py` (o basetemp curto de `tests/conftest.py:38-56` continua valendo).

### Etapa 4 — R6, grupo `App.tsx` (pré-requisito da 383; pousa antes do resto se a 383 estiver na fila)

1. **Testes:** os dois e2e novos (§3.1). Rodar com `npm run test:e2e -- <arquivo> --workers=1` (regra da máquina; o CI usa a porta 4173). Antes de commitar, provar localmente que cada e2e **falha** com a quebra correspondente: remover o `return` do guard de login, e depois remover o repasse de `visual.cue`. A quebra não é commitada (R6.5).
2. **Implementação:**
   - apagar `tests/test_frontend_auth_bootstrap.py`;
   - apagar `test_frontend_contract_contains_visual_flow` de `tests/test_visual_assets.py`;
   - apagar `tests/test_frontend_accessibility_contracts.py`, depois que o axe cobrir a cena;
   - reancorar `web/tests/design.test.mjs:105-112`.
3. **Verificação:** `npm test` (web) verde, os e2e novos verdes, e `bash scripts/dev/py.sh -m pytest -q tests/test_visual_assets.py` verde.

### Etapa 5 — R6, restante (a)/(b)

1. Uma função por commit. Para cada (a), o teste novo é escrito antes e a quebra é provada. Para cada (b), o commit cita o teste que cobre.
2. **Verificação:** os arquivos tocados verdes.

### Etapa 6 — R4 migração-prova

1. Um arquivo por commit (§3.5, depois do corte do W1), com a prova de R4.2 no corpo, R4.3 e R4.4 aplicados e no máximo 20 arquivos distintos.
2. **Verificação:** em cada commit, a contagem coletada é igual, os ids que passam são iguais e o diff das linhas de asserção é vazio. Ao final, os ≤ 20 arquivos juntos com `-n 2`.

### Etapa 7 — R5 regra para o futuro

1. TESTES.md ("Onde mora um teste novo", mais o conserto de `:29-31`) e BRIEF_SUBAGENTE.md.
2. **Verificação:** `uv run python scripts/check_md_links.py --baseline scripts/md_links_baseline.txt` verde.

### Etapa 8 — Baseline (depois do pouso, segundo a D3)

1. O coordenador dispara `coverage.yml` (`gh workflow run coverage.yml --ref main`) ou roda localmente, segundo a D3. Transcreve o resumo em `docs/spec379/coverage-baseline.md` com o tempo com e sem cobertura.
2. Commit de docs na `main`. A spec só vira `done` depois desse commit.

## 5. Critérios de aceite

- [ ] R1: `pytest-cov` no grupo `dev`; diff do `uv.lock` só com adições; `requirements.txt` intocado; `coverage.yml` passa em `test_workflows_contract.py` e `test_ci_docs_only.py`; o resumo traz o top 20; nenhum gate de porcentagem.
- [ ] R1.7: `docs/spec379/coverage-baseline.md` commitado, com total de linhas e ramos e o top 20.
- [ ] R2: `tests/test_factories.py` verde, incluindo a paridade com `POST /game/new` em `level=1` e `level=3`.
- [ ] R3: `tests/test_scripted_llm.py` verde, incluindo `ScriptedLLM.failing()` equivalente ao `FallbackLLM` no guard do `character_creator`.
- [ ] R4: no máximo 20 arquivos migrados, cada um em um commit com contagem coletada igual, mesmos ids passando e zero linha de asserção alterada; a lista de "não migráveis" está no hand-back.
- [ ] R5: TESTES.md e BRIEF_SUBAGENTE.md com a regra; o parágrafo de TESTES.md:29-31 consertado.
- [ ] R6: `docs/spec379/fonte_inventario.md` com uma decisão por função; todos os leitores de `App.tsx` resolvidos e pousados; cada (a) com a quebra provada e cada (b) com o teste que cobre citado.
- [ ] `git diff --name-only main...spec-379` dentro da lista branca da §3.2 (zero arquivo de produto, zero caminho protegido de eval).
- [ ] `tests/conftest.py` sem diff.
- [ ] Nenhum `test_specNNN_*` renomeado (`git diff --name-status` sem `R`).
- [ ] `uv run pytest` verde (suíte completa offline, pelo coordenador, uma vez no pouso), com contagem coletada total = contagem da Etapa 0 − testes apagados no R6(b) + testes novos (a conta fica no hand-back).
- [ ] Guard de FallbackLLM: não se aplica a código de produto (nenhum `with_structured_output` novo no produto); o R3.3 o exercita nos testes.
- [ ] Saves antigos continuam carregando: não se aplica (persistência intocada); o R2.6 prova o round-trip do estado da fábrica.
- [ ] Revisão independente (`spec-reviewer` Opus) refez a prova do R4.2 em pelo menos 1 arquivo (W7).

## 6. Smoke test com LLM real

**Não se aplica.** Esta spec não muda nenhum caminho de produto, prompt, schema de structured output nem chamada a provider: toda mudança está em `tests/`, `docs/`, CI e tooling (lista branca da §3.2). O risco que o smoke real cobre ("MockLLM esconde bugs de mapeamento de campo") não muda, porque nenhum nó, schema ou campo novo entra no produto. O `ScriptedLLM` substitui só fakes de teste, não o `MockLLM` nem o `RoutedLLM`. A verificação equivalente é o oráculo de paridade R2.3 (estado da fábrica igual ao do `POST /game/new`) e o R3.3 (`failing()` igual ao `FallbackLLM` no guard real). Nenhuma quota é gasta.

## 7. Riscos & compatibilidade

- **Conflito com sessões paralelas (W1).** Branches abertas: `spec-367`, `368`, `370`, `371`, `372`, `373`, `374`, `spec-359` e `bst-*` (**[F]** `.git/refs/heads/`). Durante a escrita desta spec, `api.py` mudou de linha no checkout principal (`_create_game` estava em 5321 e foi para 5328), sinal de edição ativa por outra sessão. Mitigação: o W1 roda por etapa, e esta spec não toca `api.py`.
- **Estado mais rico muda o caminho do teste sem mudar a asserção (R4).** Os helpers atuais são parciais de propósito (ex.: `test_fase26.py:26-35` sem `factions`). Mitigação: R4.3 (chaves fixadas viram overrides com o mesmo valor; quem depende de ausência não migra) e revisão W7.
- **Shadowing silencioso.** `F811` está ignorado em `tests/**` (`pyproject.toml:80`). Um `make_state` local que sobra pode sombrear o importado. Mitigação: R4.4 e Grep por `def make_state|def _state` no arquivo migrado.
- **Importação cruzada entre testes** (`tests/prompt_capture.py:10`, `tests/spec304_helpers.py:14`, `tests/spec325_chase_helpers.py:10-12`). Mitigação: R4.4.
- **Cobertura e tempo.** O tracer deixa a suíte mais lenta (**[H]** de 1,5 a 3×). Há asserções de tempo que podem falhar só sob cobertura: `test_spec361_integracao.py:318` (< 0,2 s), `test_spec361_gate.py:268` (< 0,55 s), `test_jev_router_port.py:525,541`, `test_jev_decision_backend.py:162,180`. O `timeout = 300` por teste (`pyproject.toml:97`) continua valendo. Mitigação: workflow separado, sem gate e com a conduta da D4; o pytest normal do `validate.yml` não muda.
- **Subprocessos.** 28 arquivos chamam `subprocess.*` (ex.: `test_lazy_imports.py`, que mede import em processo filho). Medir o filho alteraria o tempo e o ambiente. Por isso o default da D5 é não medir.
- **Dispatch de workflow novo.** **[H]** O `workflow_dispatch` só aparece depois que o arquivo existe na branch default. Por isso a baseline é pós-pouso (D3).
- **Os e2e novos rodam só quando o front muda** (`eval-gates.yml:111-136`, job `frontend-selective`), enquanto o pytest apagado rodava em todo push. Isso é aceitável porque o comportamento mora no front (D8). O `scripts/frontend_eval_report.py --check` conta `requestfailed:`, então o e2e novo não pode deixar requisição falhando.
- Compatibilidade com saves antigos: não muda. Comportamento no MockLLM/FallbackLLM: não muda (produto intocado). Impacto em quota e latência: zero no produto; CI ganha um job semanal de ~10–20 min **[H]**.

## 8. Decisões do dono

Cada item tem um default. O executor segue o default se o dono não disser nada na aprovação.

- **D1 — Construtor canônico do estado.** **[F]** ele não existe como função única (R2.1).
  - **(A, default):** a fábrica compõe as peças canônicas do produto na ordem de `api._create_game` e trava contra deriva pela paridade R2.3, sem tocar produto.
  - **(B):** spec futura, depois da 381, extrai `build_initial_state()` para o produto, usado por `api._create_game`, `playtest.runner._build_initial_state` e a fábrica. Isso elimina também a divergência api × runner (13 campos).
- **D2 — Denominador da cobertura.**
  - **Default:** entram os `*.py` da raiz, `agents/`, `services/`, `infrastructure/`, `workers/`, `playtest/` e `evals/`; saem `tests/`, `scripts/`, `web/`, `docs/`, `supabase/`, `data/`, `lore_nova/`, `.venv/` e `observability/`.
  - **Alternativa:** incluir `scripts/` (tem tooling testado, como `spec_index.py`, mas também geradores órfãos que a SPEC-376 vai apagar).
- **D3 — Fonte da baseline.**
  - **Default:** primeira execução do `coverage.yml` na `main` depois do pouso, sem RAM local. A spec fica `in-progress` até o commit da baseline.
  - **Alternativa:** execução local do coordenador, com a suíte completa sob cobertura (1×, `-n auto`).
- **D4 — Teste que falha só sob cobertura.**
  - **Default:** o job fica verde se o `coverage.json` foi gerado. As falhas viram `::warning` e uma lista no resumo (é medida, não gate).
  - **Alternativa:** o job fica vermelho.
- **D5 — Cobertura de subprocessos.**
  - **Default:** não medir.
  - **Alternativa:** `patch = ["subprocess"]`, com o risco de `test_lazy_imports.py` e testes de tempo.
- **D6 — Horário do cron.**
  - **Default:** `17 4 * * 0` (domingo, 04:17 UTC), longe do secret scan de segunda às 06:23 (`validate.yml:7`).
- **D7 — Testes (c) que leem `api.py` por caminho.**
  - **Default:** só marcados para a 381 (R6.4), que os reancora junto com os routers.
  - **Alternativa:** reancorar já aqui, para `api.py` mais um diretório futuro de routers.
- **D8 — Trocar pytest-de-fonte por e2e que só roda quando o front muda.**
  - **Default:** aceitar.
  - **Alternativa:** manter também um (c) reancorado em `web/src/**`.
- **D9 — Onde vai o número da spec no teste novo.**
  - **Default:** docstring (`"""SPEC-NNN R#: …"""`), sem configuração.
  - **Alternativa:** marker `@pytest.mark.spec(NNN)` registrado em `[tool.pytest.ini_options].markers`.
- **D10 — Gate automático da regra R5** (lista congelada dos `test_specNNN` que só encolhe).
  - **Default:** depois da onda, porque as branches 367, 368 e 370 a 374 ainda criam `test_specNNN` e quebrariam no pouso.
  - **Alternativa:** já nesta spec, com allowlist regenerada no pouso.
- **D11 — Teto do R4.**
  - **Default:** 20 arquivos distintos.
  - **Alternativa:** reduzir para ~10 se o dono quiser a prova mais curta.
