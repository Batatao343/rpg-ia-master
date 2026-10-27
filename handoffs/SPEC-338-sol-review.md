# SPEC-338 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (re-revisão de `d921b917` + `b8f0b1b0`; 1ª rodada foi `CHANGES_REQUIRED`)
> **Revisor:** Claude Opus 5.5 / Sol (spec-reviewer) · **Data:** 2026-10-27 · **Commits revisados:** `f227219b` (1ª rodada) · `d921b917` + `b8f0b1b0` (re-revisão)

## Escopo

Branch `spec-338`, `git diff main...HEAD`: `pyproject.toml`, `uv.lock`, `.github/workflows/validate.yml`,
`tests/conftest.py`, `tests/fakes/api_fuzz.py`, `tests/fakes/two_principals.py`,
`tests/test_api_fuzz_harness.py`, `tests/test_api_fuzz_schemathesis.py`, `docs/guias/TESTES.md`
e a spec. O job no CI ficou fora: quem roda é o agente do PR.

Para responder "o fuzz prova algo?", rodei o fuzz com um plugin de pytest descartável,
guardado no scratchpad e fora do repositório. Ele registrou `(status, início do corpo)` de cada
resposta, por operação. Segue o resumo.

## O que está correto

- **Cobertura do schema:** são 57 operações. As exclusões são exatamente as 8 do R7: webhook,
  transcriptions, stream, art confirm, player/confirm, quality, checkout e google verify. O
  legacy roda as outras 49 (45 rápidas e 4 de grafo) e o DB-offline roda 20, o que dá 69 itens.
  Uma rota nova entra sozinha no legacy, porque a exclusão é uma denylist. O `GET …/cost` saiu
  só do perfil DB e continua no legacy.
- **Oráculo:** `check_response` (`tests/fakes/api_fuzz.py:59`) rejeita qualquer status ≥ 500
  que não seja um 503 com `detail` na allowlist. Também roda `assert_security_headers` e
  `forbidden_leak` da 337. A allowlist está travada por regex sobre `api.py`
  (`test_intentional_503_allowlist_matches_source`).
- **Bloqueio real:** o smoke com `raise RuntimeError` em `/data/options` (commit `b0c180d5`, já
  retirado da branch) deixou o item vermelho.
- **R11:** o sorteio por `crc32(repr((path, query, body))) % 3 == 0` é determinístico com
  `derandomize`. Na prática, 11 de 25 exemplos usaram o id real nas rotas de leitura, então
  funciona.
- **Isolamento:** `network_blocked` fica em autouse e testado, os saves vão para o `tmp_path`
  do conftest e o MockLLM está ativo. Ligar `RPG_SESSION_SECRET` no legacy não esconde nada:
  sem ele, `/auth/*` devolve `server_misconfigured`, que é o comportamento esperado. A sessão
  do DB-offline chega ao handler: as rotas de leitura devolvem 200 com o estado de A.
- **Dependências:**
  - o `requirements.txt` reexportado é idêntico, salvo a linha de comentário com o comando;
  - o `uv.lock` só tem adições (0 linhas removidas);
  - o grupo `fuzz` não está em `default-groups`;
  - `test_spec192_vercel_packaging` passa.
- **CI:** o job `api-fuzz` é bloqueante e as actions estão fixadas por SHA, os mesmos do job
  `test`. `RPG_API_FUZZ_REQUIRED=1` faz `import` direto do pacote. O pip-audit roda sobre
  `--only-group fuzz`, há upload em `failure()` e o job não usa `-n`. A suíte default não
  coleta o módulo: `pytest_ignore_collect` resolve isso e a execução padrão sai com rc=5,
  sem nenhum item.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `tests/fakes/api_fuzz.py:72-94`, `tests/test_api_fuzz_schemathesis.py:101-103` | No DB-offline, **as 6 rotas que alteram estado nunca chegam ao handler**. Os 25 de 25 exemplos param no gate de 400. `equip`, `levelup`, `death` e `cards/prepare` param em `action_id é obrigatório neste perfil` ou `action_id inválido`. `/game/action` para no 400 de `action_id` ou no 422. `DELETE /game/save/{game_id}` para em `Idempotency-Key UUID é obrigatório`: o header nem está no schema. O R11 só semeia `game_id`, então `FakeTurnCoordinator` e o caminho de claim/commit (o objetivo do R10) nunca são exercitados. | Junto do `game_id`, na mesma fração do crc32, semear `action_id` (body) e o header `Idempotency-Key` com um UUID determinístico, por exemplo `uuid.UUID(int=digest)` ou `uuid5`. Depois, provar com um teste ou uma anotação no Histórico que cada rota de escrita teve ao menos um status fora de {400, 422}. |
| P1-2 | P1 | `tests/test_api_fuzz_schemathesis.py:40`, `:96-97` | **3 das 4 rotas de grafo (R8) nunca executam o grafo.** `/game/new`, `/game/prologue` e `/game/combat-simulator` devolvem 422 em 5 de 5 exemplos (`race` ou `class_name` fora do catálogo, validado no Pydantic e não declarado como enum no schema). Só `/game/art/brief` chega a 200. O item mais caro fica verde sem testar nada além do validador. | Em parte dos exemplos, trocar `race`, `class_name` e `region` por valores válidos (os mesmos do `two_principals`: Humano, Devoto do Abismo, Nova Arcádia), no mesmo esquema do seed. Outra opção é declarar `Literal`/enum no modelo, mas isso é mudança de produto e precisa de decisão. |
| P1-3 | P1 | `tests/test_api_fuzz_harness.py:72`, `.github/workflows/validate.yml:110` | **O R15 (`test_harness_flags_injected_500`) nunca roda no CI.** O job `test` faz `uv sync` sem `--group fuzz`, então o `importorskip` pula o teste. O job `api-fuzz` só roda `tests/test_api_fuzz_schemathesis.py -m api_fuzz`. Se o harness quebrar e ficar sempre verde, nada acusa. A própria spec diz: "sem isso, um harness quebrado passaria verde". | No job `api-fuzz`, adicionar o passo `RPG_API_FUZZ_REQUIRED=1 uv run pytest tests/test_api_fuzz_harness.py -p no:cacheprovider`. No harness, fazer `importorskip` respeitar `RPG_API_FUZZ_REQUIRED=1`, com `import` direto como no módulo de fuzz. Estender `test_api_fuzz_job_contract` para cobrir esse passo. |
| P1-4 | P1 | `tests/test_api_fuzz_schemathesis.py:43-48`; `api.py:4306-4307` | `GET /game/{game_id}/operations/{operation_id}` está na allowlist do DB, mas usa `runtime.resources[0].connection()`, e o fake tem `resources=()`. Isso contraria o R10 ("rota que dependa de `runtime.resources[0]` fica fora"). Hoje fica verde só porque os 25 exemplos dão 400 (`game_id`/`ID inválido`). Basta corrigir o P1-1 com UUIDs válidos, ou mudar a versão do Hypothesis, para aparecer um `IndexError` → 500 vindo do fake, sem bug de produto, num job bloqueante. O comentário da linha 43 cita apenas o `/cost`. | Tirar a rota da allowlist do DB, com o motivo no comentário (o legacy continua cobrindo), ou dar ao fake um recurso de conexão. Corrigir o Histórico da spec: "18 DB offline" deve ser 20, ou 19 depois da correção. |
| P2-1 | P2 | `tests/test_api_fuzz_schemathesis.py:34-50` | As exclusões e a allowlist não estão travadas por teste. Alargar o `EXCLUDED_RE`, ou uma alternativa do `DB_ALLOWED_RE` deixar de casar com qualquer rota, passa em silêncio. | Num teste do módulo `api_fuzz` (só roda com o pacote instalado), afirmar que o conjunto excluído é igual às 8 operações do R7 e que `DB_OPS` é igual à lista fechada, com a contagem. |
| P2-2 | P2 | `tests/test_api_fuzz_schemathesis.py:84-92` | O legacy não semeia campanha. As rotas com `game_id` (`state`, `map`, `codex`, `history`, `operations`, `cost`, `art/{generation_id}`, `audit-export` etc.) só veem 400 ou 404, e nenhum handler legacy com estado real é exercitado. | Opcional: criar uma campanha pelo `/game/new` legacy na fixture e passar `seed=` ao `fuzz_operation`, como já é feito no DB. |
| P2-3 | P2 | `tests/fakes/api_fuzz.py:109` | `suppress_health_check=list(HealthCheck)` silencia todos os health checks. O R16 lista só três. | Restringir aos três da spec, ou registrar o desvio no Histórico. |

Não encontrei problemas nestes pontos:

- guard de structured output: a mudança não chama nenhum `with_structured_output`;
- valor de LLM sem validação;
- writer persistente novo: o `JsonRuntimeCatalogStore` do fake é um adapter já existente;
- segredo em log: só aparece o segredo fake `"s"*32`;
- `evals/` protegido: não foi tocado.

## Correções aplicadas

Feitas pelo executor em `d921b917` e `b8f0b1b0`. Conferi cada uma no diff e rodei o fuzz de novo.

- **P1-1:** `seed_idempotency` coloca `action_id` (UUID v5 derivado do digest) e `Idempotency-Key` no DELETE; o seed passa a valer em exemplos alternados. Distribuição medida no DB-offline:
  - `action`: 200 em 13 exemplos;
  - `cards/prepare`: 200 em 8;
  - `DELETE save`: 200 em 1 e 404 em 12;
  - `death`: 409 `no_pending_death` em 13;
  - `levelup`: `levelup_rejected` em 13;
  - `equip`: `equip_rejected` em 2 e `equip_request_invalid` em 11.

  `_assert_reached` com `GATE_CODES` transforma em teste a exigência de que pelo menos um exemplo passe do gate em cada rota de `MUST_REACH_HANDLER`. **Julgamento:** basta que `equip`, `levelup` e `death` cheguem à regra de negócio. Os três códigos saem depois de `load_game_state` e de `_begin_state_mutation`, isto é, depois do claim, dentro de `operation_scope` (`api.py:6782-6817`). Assim o caminho de claim e de `_fail_operation` fica exercitado. O commit (`commit_game`) é exercitado por `action` e `cards/prepare`, que chegam a 200.
- **P1-2:** `seed_catalog` preenche race, class_name, region e enemy_id com valores válidos. Resultado: `new`, `prologue` e `combat-simulator` dão 200 em 3 de 5 exemplos cada; `art/brief` dá 200 em 5 de 5.
- **P1-3:** o job `api-fuzz` ganhou o passo `RPG_API_FUZZ_REQUIRED=1 uv run pytest tests/test_api_fuzz_harness.py`. O harness respeita a variável, e `test_api_fuzz_job_contract` cobre o passo novo.
- **P1-4:** `operations/{operation_id}` saiu da allowlist do DB, com o motivo no comentário; o legacy continua cobrindo. `DB_OPS` passou a ter 19 operações.
- **P2-1:** `test_scope_is_locked` fixa as 8 exclusões, as 4 rotas de grafo e as 19 operações do DB.
- **P2-2:** o legacy semeia uma campanha real pela fixture `legacy_seed`. Exemplo: o DELETE legacy deu 200 em 1 e 404 em 12.
- **P2-3:** o health check só suprime os três itens do R16.

**O fake novo não mascara 500 de produto.** O `commit_game` de `tests/fakes/two_principals.py` grava no `FileGameStore` e devolve o recibo, sem `try/except`: qualquer erro de store ou de conflito sobe para o handler e aparece como 5xx. Ele aceita `**_kwargs` (custo, latência, `record_turn`), que não têm efeito offline. O `_NoRowsConnection` em `resources[0]` só é consultado, nas rotas da allowlist, pelo gate de falhas pendentes (`api.py:5223`), e sempre devolve "sem falha". O efeito é uma lacuna de cobertura, não uma máscara: o ramo "falha pendente bloqueia o turno" não roda no fuzz e segue com os testes da 316/337 e com o `infra_local`. SQL inválido também passaria por ele, o que é aceitável num perfil offline que não pretende validar SQL. As rotas que usam `admin_connection(resources[0])` ou repositórios Postgres continuam fora da allowlist.

## Pendências

- Follow-up opcional (P2): semear um `item_id` do inventário de A em `equip` e um caso com XP suficiente em `levelup`, para que essas duas rotas também cheguem ao `commit_game`. Hoje o commit só é exercitado por `action` e `cards/prepare`.
- Follow-up opcional (P2): o comentário do `DB_ALLOWED_RE` justifica a exclusão de `operations/{id}` por depender de `resources[0]`. O fake agora tem `resources[0]`, mas sem linhas; o motivo continua válido e o texto pode dizer isso explicitamente.
- O job `api-fuzz` verde no PR e o registro da duração seguem com o agente do PR.

## Comandos rodados

```text
# re-revisão (b8f0b1b0)
py.sh -m pytest tests/test_api_fuzz_schemathesis.py -m api_fuzz -s → rc=0, 69 passed em 41 s; STATUS por operação conforme acima
RPG_API_FUZZ_REQUIRED=1 py.sh -m pytest tests/test_api_fuzz_harness.py → 8 passed, 0 skipped
# 1ª rodada (f227219b)
git diff main...HEAD --stat → 10 arquivos, +775/-2
uv export --frozen --no-dev … | diff - requirements.txt → só a linha de comentário do comando difere
git diff main...HEAD -- uv.lock | grep '^-[^-]' → 0 linhas removidas
py.sh -m pytest -n 2 tests/test_api_fuzz_harness.py tests/test_workflows_contract.py tests/test_spec192_vercel_packaging.py → rc=0, 32 passed, 0 skip
py.sh -m pytest tests/test_api_fuzz_schemathesis.py (default) → rc=5, nenhum item coletado (correto)
py.sh -m pytest --collect-only -m api_fuzz tests/test_api_fuzz_schemathesis.py → 69 itens
py.sh -m pytest tests/test_api_fuzz_schemathesis.py -m api_fuzz -p statplug338 (plugin no scratchpad) → 68 passed, 1 failed (/data/options = smoke injetado pelo outro agente em b0c180d5, depois retirado)
```
