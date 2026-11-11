# SPEC-406 — api-imports-mortos

> **Status:** `approved` (11/11: aprovada pelo coordenador por delegação do dono, "as decisões deixo para vc"; decisões do §8 = recomendações; veto do dono segue possível) · antes `draft`
> **Criada:** 2026-11-11 · **Atualizada:** 2026-11-11
> **Depende de:** nenhuma. **Ordem recomendada: depois da SPEC-405** (a 405 R2 apaga `api.py:242–251`, `_CODE_RE` + `_error_code_of`, e com isso o único `F811` do arquivo; ver §7).
> **Desbloqueia:** nada (follow-up R17b da SPEC-381 `done`; uma das 4 follow-ups de qualidade 405..408).
> **Risco:** `alto` (API pública pela régua do `AGENTS.md`: `api.py` é o ponto de entrada `uvicorn api:app`/`vercel_app.py` e é lido por `playtest/`, `evals/` e ~160 arquivos de teste). `spec-reviewer` (Sol) **obrigatório**.
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet), uma etapa por vez · **REVIEW_MODEL:** `Sol` (`spec-reviewer`, Opus), obrigatório, sobre o diff final e a tabela do R0.
> **EVAL_AUTHORING_REQUIRED:** `false` (nenhum evaluator, expected, dataset ou baseline de `evals/` é tocado; `ruff-baseline.toml` não é baseline de eval).
> **Evidência:** refatoração pura (W2). Oráculo de equivalência em 4 camadas: (1) teste de caracterização novo que fixa os atributos de `api` lidos por consumidores (verde antes e depois); (2) `patch_liveness` A = B; (3) `api_surface_dump` byte-igual nos dois perfis, inclusive `modules.json` (efeito colateral de import); (4) `evals compare` + `playtest run --all --turns 10 --seed 0` sem diferença, no molde da SPEC-405 R7. Mais o gate: `F401` sai da entrada de `api.py` em `ruff-baseline.toml`.

---

## 1. Contexto & Objetivo

A SPEC-381 moveu as rotas de `api.py` para `routes/*.py`, `api_core.py`, `api_models.py` e `api_presenters.py`. O que sobrou em `api.py` é um bloco de imports de 130 linhas (`api.py:9–225`) escrito para o arquivo de 8.000 linhas de antes. A revisão Sol da 381 (P2-1, `handoffs/SPEC-381-sol-review.md:86`) mediu "ruff sem baseline 76 → 200" e a 381 fechou com o item pendente (`specs/SPEC-381-refactor-api-routers.md:586`, "R17(b): ~106 imports mortos em `api.py`"). A revisão independente de 11/11 reencontrou o caso. Medido pelo coordenador em 11/11: `ruff check --isolated --select F401,F811,F841 api.py` → **109 erros**, todos mascarados porque `ruff-baseline.toml:21` lista `F401` para `api.py` (`"api.py" = ["BLE001", "E402", "F401", "I001", "UP035"]`).

Por que é risco alto e não "só apagar import": o ruff vê "sem uso **dentro** de `api.py`", e não vê quem lê `api.<nome>` de fora. Medido nesta spec (Grep, 11/11): `tests/` faz `api.<nome>` em 163 arquivos (560 acessos), `playtest/invariants.py:2177,2528,2630,2901` e `evals/core/adapters.py:1194` leem `api.format_response`/`_npcs_block`/`_world_block`/`_combat_block`, e `scripts/` e `vercel_app.py:16` usam `api.app`/`from api import app`. As leituras de `playtest/invariants.py` estão em `try/except Exception` com `# silent-ok` (381 R9 [F]): se um reexport sumir, a invariante **para de checar sem erro**. Dos 109, uma parte é alvo vivo de leitura e fica; o resto é morto de verdade.

Os patches já não são o problema principal: depois da 381, os `monkeypatch.setattr` apontam para os módulos-lar (`api_core`, `api_presenters`, `routes.*`), e a R10 da 381 proíbe `api.py` de reexportar nome patchado. A varredura desta spec achou **um único** patch literal em `api` (`monkeypatch.setattr(api, "_DOCS_PATHS", …)`, `tests/test_http_security_headers.py:155`, nome definido no próprio `api.py`, fora dos 109) e **zero** `setattr(api, "<import>")`. O risco real são as **leituras** (`api.X`, `from api import X`).

Princípio: "menor mudança correta" (AGENTS.md § Qualidade). Nenhuma mudança de comportamento; nenhum arquivo além de `api.py`, `ruff-baseline.toml`, um teste novo e, no máximo, três testes que leem `api.gamedata`.

## 2. Requisitos

Linhas e contagens = estado da `main` em `9f21ef4a`. As contagens abaixo vêm de `Grep` (esta spec não rodou o ruff); **o executor as reproduz com o ruff na Etapa 0** e a tabela do R0 prevalece.

- **R0 — tabela de liveness por nome (W1).** Antes de apagar, `docs/spec406/README.md` lista **cada um dos 109 diagnósticos** (regra F401/F811/F841, linha, nome, módulo de origem) com uma classe: `morto` (apagar), `leitura` (fica, R3), `patch` (fica, R3, nenhum esperado), `efeito` (fica, R4). A classe vem de evidência, não de palpite: (a) uso dentro do corpo de `api.py` depois da linha 226; (b) varredura AST de `tests/`, `playtest/`, `evals/`, `scripts/`, `services/`, `routes/`, `api_*.py`, `agents/`, `infrastructure/`, `observability/` e `vercel_app.py` por `api.<nome>` (inclusive alias `import api as x`, `import` dentro de função), `from api import <nome>`, `getattr(api, "<nome>")`, string de alvo `"api.<nome>"` em `setattr`/`patch`; (c) `git grep -nw <nome>` em `*.sh`, `*.yaml`, `*.toml`, `*.json` (carga dinâmica). Nome com **qualquer** acerto em (b) ou (c) não é `morto`.
- **R1 — teste de caracterização, primeiro.** `tests/test_api_surface.py::test_api_attributes_read_by_consumers_exist` percorre por AST os mesmos consumidores do R0(b) (exceto `api.py`) e afirma `hasattr(api, nome)` para todo `api.<nome>` e todo `from api import <nome>` encontrado (conjunto vazio de faltantes; mensagem lista `arquivo:linha nome`). Deve passar na `main` **antes** de qualquer poda (prova de que cobre o que existe hoje) e é a rede da Etapa 2. Limites declarados no docstring: não vê `getattr` com nome computado nem módulo importado por `importlib` com string dinâmica (cobertos por R7 e pelos testes do escopo). Se o teste de AST de consumidores já existir em outro arquivo, estender em vez de duplicar (`Grep "ast.parse" tests/test_spec381_*`).
- **R2 — apagar o morto.** Remover de `api.py` somente os imports classificados `morto` no R0 (estimativa por Grep: **89 de 109** F401: 26 de stdlib/terceiros, 31 de `gamedata`/`persistence`/`services.*`/`world_utils`/`character_creator`/`progression`, 8 de `api_models`, 18 de `api_core`, 6 de `api_presenters`, ver §3), mais o `F811` de `import re` em `api.py:248` **somente se a 405 R2 ainda não o tiver removido** (hoje só a 405 mexe em `:242–251`; ver §7). Importa-se por linha (`from x import (a, b, c)` perde só os nomes mortos; o parêntese some quando sobra um nome e o `ruff format` o reduz). Não reordenar imports, não "consertar" `I001`/`E402`/`UP035` à mão.
- **R3 — o que é lido de fora fica, explicitado no bloco de reexports.** Os nomes `leitura`/`patch` ficam em `api.py`. Forma escolhida: **movê-los para o bloco que já existe** (`# --- reexports (SPEC-381 R9) … # --- fim dos reexports ---`, `api.py:167–226`) na forma `from <lar> import X as X`, que o ruff trata como reexport explícito (sem `F401`, sem `noqa`) e que o `test_reexports_are_identical_and_not_rebound` (`tests/test_spec381_structure.py:102–128`) já valida (`api.X is <lar>.X`, não religado por `global`, fora de `patch_lars.json`). Estimativa: **18 nomes**, 17 deles `from … import … as …`:
  - `api_models`: `ActionRequest`, `GameResponse`, `CreateCharacterRequest`, `CombatSimulatorRequest`, `ArtQuoteRequest`, `ArtConfirmRequest`, `ArtQualityRequest`;
  - `api_core`: `_begin_state_mutation`, `_llm_log_fields`, `_meter_auxiliary_operation`, `_release_failed`, `_turn_logger`;
  - `api_presenters`: `_cards_block`, `_prepared_slots`, `_public_art_refs`, `format_response`;
  - `gamedata`: `load_json_data` (`tests/test_hardening_persistencia_sse.py:250`).
  O 18º é o **módulo** `gamedata` (`api.gamedata.CLASSES/BESTIARY` em `tests/test_combat_simulator.py:35,40`, `tests/test_hardening_persistencia_sse.py:22,24,249`, `tests/test_latency_metrics_compat.py:117,119`): o bloco só aceita `ImportFrom` (`test_spec381_structure.py:121`), então esses 3 testes passam a fazer `import gamedata` e ler `gamedata.CLASSES` (troca de prefixo, **nenhuma asserção muda**, W3). Alternativa descartada: deixar `import gamedata as gamedata` solto em `api.py`, que perpetua um reexport de módulo sem teste de identidade.
- **R4 — import por efeito colateral.** `import main  # noqa: F401  # SPEC-381 …` (`api.py:68`) fica como está. Para cada módulo cuja única importação na cadeia de `api` era uma linha `morto` (ex.: `progression`, `persistence_module`, `character_creator`, `services.combat_flags`, `services.state_views`), a comparação de `modules.json` (R7) decide: se o módulo sumir de `sys.modules` após `import api`, o import **fica** com `# noqa: F401  # efeito: <motivo>` (menor mudança) e a classe vira `efeito`. Só se apaga e se aceita a diferença quando o R0 provar, por AST, que nada depende do módulo estar carregado no import de `api` (registrar no README).
- **R5 — não tocar no que é de outra spec ou fora do alvo.** `api.py:242–251` é da SPEC-405 (não editar). Não resolver `E402`, `I001`, `BLE001` nem `UP035` por edição manual (mas ver R6 sobre `UP035`).
- **R6 — gate: `F401` sai da baseline.** Última etapa (nunca antes, ver §7): regenerar `ruff-baseline.toml` com `bash scripts/dev/py.sh scripts/dev/ruff_baseline.py` (cabeçalho: "do not edit by hand"), de modo que a entrada de `api.py` perca `F401` e, se o ruff passar a não reclamar, `F811` e `UP035` (os `Dict/List/Optional` de `typing` saem junto com o morto). `E402`, `I001` e `BLE001` ficam. `bash scripts/dev/py.sh scripts/dev/ruff_baseline.py --check` verde. `bash scripts/dev/py.sh -m ruff check --isolated --select F401,F811,F841 api.py` → `All checks passed` (com a 405 pousada) ou exatamente 1 `F811` (`re`, `:248`) se a 406 pousar antes.
- **R7 — oráculo de equivalência (A = B).** A é capturado na `main` limpa antes da Etapa 1; B ao fim de cada lote (Etapas 3–5) e no fechamento.
  - `patch_liveness`: `PYTHONPATH=scripts/dev LIVENESS_OUT=<json> bash scripts/dev/py.sh -m pytest -p patch_liveness -n 2 <os testes do inventário de docs/spec381/patch_inventory.json>` antes e depois; os dois JSON **iguais** (nenhum `True` virou `False`, nenhuma chave sumiu). O plugin só rastreia os 34 nomes de `docs/spec381/patch_lars.json`: serve para provar que o lar não mudou; a cobertura de **leitura** é o R1. Repetir a mutação de não-chamáveis (`LIVENESS_MUTATE=1`) uma vez: mesmo desfecho antes e depois.
  - `bash scripts/dev/py.sh scripts/dev/api_surface_dump.py --out <dir>` (perfis `legacy` e `hosted`): `openapi.json`, `routes.json`, `middleware.json`, `handlers.json`, `lifecycle.json` e `modules.json` **byte-iguais** (`diff -r`). `modules.json` (`sys.modules` adicionado por `import api`) é o detector de efeito colateral do R4.
  - `evals run` das suítes do `eval-gates.yml` com `--seed 7` + `evals compare` sem diferença (`evals/core/adapters.py:1194` lê `api.format_response`); `playtest run --all --turns 10 --seed 0` com as mesmas violações e desfechos por perfil (as 4 leituras de `playtest/invariants.py` estão em `silent-ok`).
- **R8 — o app sobe.** `bash scripts/dev/py.sh -c "import api"` nos dois perfis (já coberto pelo dump); `uvicorn api:app --port <livre>` responde `GET /health`; `bash scripts/smoke_api.sh` verde; `importlib.reload(api)` segue verde (`tests/test_boot_policy.py:134,341`).
- **R9 — gates e commits.** `ruff format --check` e `ruff check` limpos em `api.py`, no teste novo e nos 3 testes migrados; `scripts/dev/dup_helpers.py --diff main...HEAD` sem helper novo; `tests/test_size_budget.py` verde (`tests/size_budget.json:12` limite de `api.py` = 1081; o arquivo só encolhe, **reduzir o limite no mesmo commit** se o gate/convenção pedir); um commit por etapa, inglês, Conventional Commits (`test:`/`refactor:`/`chore:`).

### Fora de escopo (com motivo)

- **`api_presenters.py` e `routes/turn.py` (`F841` na baseline, `ruff-baseline.toml:24,87`).** `F841` é variável local sem uso: pode esconder erro de lógica (resultado descartado), não é "import morto", e exige leitura de cada função. Vira spec própria. `api_core.py`, `api_models.py`, `routes/{art,auth,billing,ops,play,read,saves}.py` e `api_presenters.py` **não** têm `F401` na baseline (`ruff-baseline.toml:22–24,81–87`): F401 já está limpo neles. O executor confirma com `ruff check --isolated --select F401,F811 api_core.py api_models.py api_presenters.py routes/` e registra o número de `F841` no README para o follow-up (esta spec não conseguiu medi-lo).
- Migrar as ~560 leituras `api.X` dos testes para o módulo-lar (a 381 R9 decidiu manter leitura reexportada; migrar só valeria com spec própria e não reduz risco).
- `__all__` em `api.py`: não existe hoje (`Grep` vazio) e mudaria a semântica de `from api import *` sem ganho; o bloco `X as X` já declara a superfície (R3).
- `_CODE_RE`/`_error_code_of` (`api.py:242–251`): SPEC-405 R2.
- `I001`, `E402`, `BLE001`, `UP035` à mão; reordenar imports; mover `import main`.
- Qualquer mudança de rota, middleware, contrato OpenAPI, comportamento ou caminho protegido de `evals/`.
- `scripts/dev/patch_liveness.py` e `api_surface_dump.py` ficam (a 405 também os mantém).

## 3. Design técnico

- **Arquivos novos:** `tests/test_api_surface.py` (R1); `docs/spec406/README.md` (tabela do R0, capturas A/B do R7 com sha e caminhos, número de `F841` do fora-de-escopo). Nenhum código de produto.
- **Arquivos alterados:** `api.py` (só o bloco de imports `9–225` e, se necessário, nenhum corpo de função); `ruff-baseline.toml` (regenerado pelo script, R6); `tests/test_combat_simulator.py`, `tests/test_hardening_persistencia_sse.py`, `tests/test_latency_metrics_compat.py` (só `api.gamedata` → `gamedata`, mais `import gamedata`); possivelmente `tests/size_budget.json` (R9).
- **Contagem esperada (Grep, a confirmar pelo ruff):**

| grupo de origem | F401 | mortos | leitura |
|---|---|---|---|
| stdlib/terceiros (`contextvars hashlib logging queue threading Counter contextmanager nullcontext deepcopy Annotated Dict List Literal Optional Callable Iterator HTTPException Response StreamingResponse AIMessage HumanMessage SystemMessage BaseModel ConfigDict Field field_validator`) | 26 | 26 | 0 |
| `gamedata`, `persistence`, `progression`, `character_creator`, `llm_setup`, `observability`, `infrastructure`, `services.*`, `world_utils` | 33 | 31 | 2 (`gamedata`, `load_json_data`) |
| `api_models` | 15 | 8 (`ArtBriefRequest ChronicleSearchRequest EquipRequest EspolioRequest ForjaRequest LevelUpRequest LojaCartasRequest PrepareCardsRequest`) | 7 |
| `api_core` | 23 | 18 | 5 |
| `api_presenters` (módulo + 9 nomes) | 10 | 6 (módulo `api_presenters`, `_card_reward_blocks _inventory_block _levelup_block _portrait_manifest_ctx _simulation_manifest`) | 4 |
| **total** | **107** | **89** | **18** |

  Medido pelo coordenador com o ruff em 11/11 (`--statistics`): os **109 são todos `F401`**, nenhum `F811`/`F841` em `api.py` (o `import re` de `:248` conta como `F401`). A contagem por Grep acima achou 107; os 2 que faltam o executor identifica na Etapa 0 e classifica pelo R0. Nos vizinhos (`routes/`, `api_presenters.py`, `api_core.py`, `api_models.py`): 0 `F401` e **2 `F841`** no total, fora de escopo (D3). Usados no corpo e que **ficam** (não são diagnóstico): `uuid`, `json`, `re`, `os`, `sys`, `time`, `Any`, `deque`, `defaultdict`, `APIRouter`, `FastAPI`, `Request`, `JSONResponse`, `StaticFiles`, `_log_event`, `_error_response`, `_enforce_owner_budget`, `_llm_turn_events`, `_llm_attempt_events`, `QuotaExceeded`, `api_core`, etc.
- **Schemas/assinaturas:** nenhum. Os nomes lidos mantêm o **mesmo objeto** (`api.X is <lar>.X`), garantido pelo teste de identidade da 381.
- **Forma do reexport (decisão):** `X as X` dentro do bloco existente, e não `__all__` (muda `import *`, não há hoje) nem comentário `# noqa: F401` por linha (esconde do gate futuro). Vantagens: zero código novo, já coberto por teste de identidade, e o ruff passa a **impedir** import morto novo (R6).

## 4. Plano passo a passo

Executor roda só os testes da etapa (`bash scripts/dev/pt.sh`, máx. `-n 2`); suíte completa é do coordenador no `/spec-land`. A cada lote, B do R7 (dump + liveness) antes do commit.

### Etapa 0 — Linha de base (sem código de produto)
1. Criar `docs/spec406/README.md`. Capturar A: `api_surface_dump` (2 perfis), `patch_liveness` (+ mutação), `evals run --seed 7`, `playtest run --all --turns 10 --seed 0`, tudo com o sha da `main`.
2. Rodar `ruff check --isolated --select F401,F811,F841 api.py --output-format concise` e montar a tabela do R0 (109 linhas) com a classe de cada nome (AST de consumidores + corpo). Registrar o número de `F841` de `api_presenters.py`/`routes/turn.py`.
3. Verificação: tabela completa, nenhum nome sem classe; qualquer divergência das contagens do §3 é anotada (a tabela prevalece).

### Etapa 1 — Teste de caracterização (R1), antes de qualquer poda
1. **Teste:** `tests/test_api_surface.py::test_api_attributes_read_by_consumers_exist` (AST; mensagem com `arquivo:linha nome`); `test_scanner_sees_known_reads` asserta que o scanner **encontra** `format_response`, `_npcs_block`, `app` e `health_check` (prova que não passa vazio).
2. **Verificação:** verde na `main`; temporariamente apagar `format_response` do bloco local e ver o teste falhar, depois reverter (anotar no README).

### Etapa 2 — Mover o que é lido para o bloco de reexports (R3)
1. Mover os 17 nomes `leitura` (ImportFrom) para `from <lar> import X as X` dentro de `# --- reexports …` (agrupando por módulo de origem, ordem alfabética como já está) e **apagar a linha de origem antiga** só do nome movido (ainda sem apagar mortos).
2. Migrar os 3 testes de `api.gamedata` → `gamedata`.
3. Testes: `tests/test_api_surface.py tests/test_spec381_structure.py tests/test_combat_simulator.py tests/test_hardening_persistencia_sse.py tests/test_latency_metrics_compat.py tests/test_api_attempt_telemetry.py tests/test_fallback_logging.py tests/test_bug_api_pending_erros.py tests/test_spec353_misc.py tests/test_image_quotes_local.py -q`. B (dump) igual a A.

### Etapa 3 — Lote 1: stdlib e terceiros mortos (26)
1. Apagar os 26 do §3 linha 1. `Request`/`JSONResponse`/`Any` etc. **não** entram (usados no corpo).
2. Testes: `tests/test_api*.py tests/test_http_*.py tests/test_boot_policy.py tests/test_spec381_*.py -q`. Dump + liveness B = A (módulos de terceiros já carregados por `fastapi`/`pydantic`: `modules.json` igual).

### Etapa 4 — Lote 2: `services.*`, `gamedata`, `persistence`, `world_utils`, `character_creator`, `progression` (31 mortos)
1. Apagar por linha de origem. Onde `modules.json` mudar (R4), restaurar a linha com `# noqa: F401  # efeito: <motivo>` e anotar `efeito` no README.
2. Testes: os do lote 1 + `tests/test_abuse_policy.py tests/test_streaming.py tests/test_prologue.py tests/test_spec197_daily_cap.py tests/test_card_shop_api.py tests/test_error_envelope.py -q`. Dump (2 perfis) + liveness B = A. `playtest` curto (`--turns 10`) B = A.

### Etapa 5 — Lote 3: `api_models`, `api_core`, `api_presenters` mortos (32)
1. Apagar os 8 + 18 + 6 do §3; remover `import api_presenters` (módulo) se `morto`. Conferir que o bloco de reexports (`api.py:167–226`) não perdeu nada.
2. Testes: lote 2 + `tests/test_cards_prepare_api.py tests/test_spec352_creature_quote_api.py tests/test_image_quotes.py tests/test_portrait_offer_causes.py tests/test_spec363_portrait_offer.py tests/test_combat_targeting.py -q`. B = A (dump, liveness, `evals compare`, `playtest`).

### Etapa 6 — Gate (R6) e fechamento
1. Regenerar `ruff-baseline.toml` pelo script; conferir no diff que **só** a linha de `api.py` mudou (`F401` e possivelmente `F811`/`UP035` saem). `ruff_baseline.py --check` verde; `ruff check --isolated --select F401,F811,F841 api.py` conforme R6.
2. Prova do gate: reintroduzir um `import hashlib` descartável em `api.py` e ver o `ruff check` reprovar; reverter (anotar no README).
3. Capturar B final (todas as camadas do R7); `uvicorn api:app` + `/health`; `bash scripts/smoke_api.sh`; `ruff format --check`; `dup_helpers.py --diff main...HEAD`; `git diff --stat main...HEAD` (saldo de `api.py` ≈ −100 a −110 linhas).
4. Revisão Sol obrigatória (diff de `api.py`, README R0, A×B). Depois o coordenador: `/spec-land` (suíte completa 1×).

## 5. Critérios de aceite

- [ ] R0: `docs/spec406/README.md` com os 109 diagnósticos classificados por evidência; todo `morto` sem acerto em AST/grep de consumidores.
- [ ] R1: `tests/test_api_surface.py` verde na `main` antes da poda e depois; mutação (apagar `format_response`) o reprova.
- [ ] `bash scripts/dev/py.sh -m ruff check --isolated --select F401,F811,F841 api.py` → `All checks passed` (com a 405 pousada) ou só o `F811` de `re` (406 antes da 405).
- [ ] `ruff-baseline.toml`: entrada de `api.py` sem `F401`; `ruff_baseline.py --check` verde; mais nenhuma entrada alterada.
- [ ] `patch_liveness` A = B (mesmas chaves, nenhum `True`→`False`); mutação dos não-chamáveis igual.
- [ ] `api_surface_dump` byte-igual (6 arquivos × 2 perfis, incluindo `modules.json`); exceções de efeito colateral só as listadas no README, cada uma com `noqa` e motivo.
- [ ] `evals compare` A × B sem diferença; `playtest run --all --turns 10 --seed 0` com mesmas violações e desfechos.
- [ ] `uvicorn api:app` sobe e `/health` responde; `smoke_api.sh` verde; `importlib.reload(api)` verde.
- [ ] `tests/test_spec381_structure.py` e testes do escopo (contagem no hand-back) verdes; nenhuma asserção de teste mudou (só os 3 prefixos `api.gamedata` → `gamedata`).
- [ ] `ruff format --check`, `ruff check`, `test_size_budget.py` verdes; saldo de linhas negativo; sem helper novo.
- [ ] Revisão Sol (`spec-reviewer`) APPROVED.
- [ ] `uv run pytest` verde (suíte completa offline, 1× pelo coordenador no pouso).
- [ ] Saves antigos continuam carregando (nenhum `GameState` ou persistência tocado).

## 6. Smoke test com LLM real

Não se aplica: nenhuma etapa muda `with_structured_output`, prompt, roteamento, campo de modelo ou caminho de LLM; só nomes importados em `api.py`. O oráculo (R7: superfície HTTP byte-igual, `patch_liveness`, evals e playtest MockLLM) substitui o smoke, no molde da SPEC-376 §6 e da 405. Verificação de infra equivalente: `uvicorn api:app` + `GET /health` e `bash scripts/smoke_api.sh` offline após a Etapa 5.

## 7. Riscos & compatibilidade

- **Leitura silenciosa perdida (maior risco).** `playtest/invariants.py` lê `api.format_response/_npcs_block/_world_block/_combat_block` dentro de `try/except … # silent-ok`; se o nome sumir, a invariante deixa de checar sem erro. Mitigação: R1 (AST fixa `hasattr`), identidade da 381, `playtest` A = B (R7). O nome `_npcs_block`/`_world_block`/`_combat_block` já estão no bloco e **não** entram na poda.
- **Hook de `ruff --fix` apagando o que é vivo.** `.claude/settings.json` roda `ruff check --fix` a cada edição de `.py`. Enquanto `F401` está na baseline de `api.py` o hook não age; **tirar `F401` da baseline antes da Etapa 2 faria o `--fix` apagar imports lidos por testes**. Por isso R6 é a **última** etapa e a Etapa 2 (mover o vivo para `X as X`) vem antes de qualquer poda. O executor não edita a baseline à mão.
- **Efeito colateral de import / ordem / ciclo.** Remover um `import m` pode tirar `m` de `sys.modules` depois de `import api` (registro, hook, cache de módulo). Detector: `modules.json` byte-igual nos dois perfis; default conservador é manter com `noqa` e motivo (R4). `api.py` mantém `E402` e a ordem atual; não há reordenação, então ciclos entre `api` → `api_core`/`routes.*` não mudam (o teste da 381 que veta `import api` em módulos novos segue verde).
- **Conflito com a 405 (`api.py:242–251`).** A 405 R2 apaga `_CODE_RE` e `_error_code_of` e, com a função, o `F811` de `import re` (`:248`). Ordem recomendada: 405 → 406. Se a 406 for primeiro: não tocar `:242–251`, aceitar 1 `F811` residual (R6/critério) e, quando a 405 pousar, ela reaplica seu R2 com os números de linha deslocados (re-grep W1 por símbolo, já previsto na 405 R0). Ambas editam `api.py`: nunca em paralelo no mesmo checkout.
- **Teste que passa por motivo errado.** `modules.json`/`patch_liveness` só cobrem o que já existe; por isso o R1 e a mutação "apagar `format_response`" provam que a rede pega.
- **`UP035`.** Sair de `typing.Dict/List/Optional` pode zerar a regra na entrada; só o script de baseline decide (R6), sem edição manual.
- Saves/persistência: nenhum formato muda. MockLLM/FallbackLLM: sem mudança. Quota/latência: nenhuma (menos imports, tempo de import igual ou menor; `scripts/dev/api_importtime.py` é da 405 R3 e pode já não existir).

## 8. Decisões do dono

Nenhuma bloqueante. Para confirmar na aprovação:
- **D1** — Forma do reexport: `X as X` no bloco existente (recomendado) em vez de `__all__` ou `noqa` por linha? Proposta: sim.
- **D2** — O módulo `gamedata` lido por 3 testes: migrar os testes para `import gamedata` (recomendado, 7 trocas de prefixo, nenhuma asserção) em vez de manter `import gamedata as gamedata` em `api.py`? Proposta: migrar.
- **D3** — Registrar `F841` de `api_presenters.py`/`routes/turn.py` como follow-up (SPEC-407/408 já reservadas são de outro assunto; pode ser uma 409) e manter fora desta spec? Proposta: sim.
- **D4** — Aceitar o oráculo (superfície byte-igual + `patch_liveness` + evals/playtest MockLLM) no lugar do smoke real (§6), como na SPEC-376/405? Proposta: sim.
