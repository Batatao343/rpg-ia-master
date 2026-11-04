# SPEC-381 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (papel Sol, W7) · **Data:** 2026-11-04 · **Commit revisado:** `1af98ad8` (branch `spec-381`, base `52e0908e`)

## Escopo

Revisado: `52e0908e..1af98ad8` (19 commits): `api.py` fatiado em `api_core.py`, `api_models.py`,
`api_presenters.py` e `routes/{art,auth,billing,ops,play,read,saves,turn}.py`; oráculos em
`docs/spec381/`; `tests/api_sources.py`; os 13 scanners; retarget dos testes; `ruff-baseline.toml`,
`tests/size_budget.json`, allowlist de silent-except; gates R16; R18 (`_load_or_404`) com golden.
Fica de fora (com o coordenador): W2 de evals/playtest/catálogo de eventos, a suíte completa, o smoke
local (`uvicorn` e `python api.py`), o §6 em staging e o commit que apaga `test_spec381_api_surface.py`.

Fiz cada prova por conta própria, a partir de um worktree destacado em `52e0908e` (no scratchpad,
já removido):

- **R6 refeito.** Rodei `api_surface_dump.py` no base e na ponta, em subprocessos limpos, nos perfis
  legacy e hosted. Os 10 arquivos (openapi, routes, middleware, handlers, lifecycle) ficaram
  **byte-iguais** a `docs/spec381/before/` nos dois lados. As regenerações do `before` (`9542c801`,
  `32492fe7`) aconteceram antes de qualquer mudança em `api.py`; conferi que
  `git diff 52e0908e 32492fe7 -- api.py` sai vazio.
- **R7a refeito.** Com o mesmo interpretador, `import api` na ponta carrega exatamente os módulos do
  base mais `api_core`, `api_models`, `api_presenters`, `routes` e `routes.*`. Nenhum módulo some.
  Diff informativo da ordem de primeiro import: idêntica nos 1.399 módulos que já existiam, salvo a
  ordem relativa de `_codecs_{tw,cn,jp,hk}` (codecs CJK, sem efeito).
- **R7b refeito.** 7 pares intercalados de `-X importtime`, base × ponta. Mediana 2.654 ms × 2.703 ms,
  razão **1,018** (limite 1,05).
- **Equivalência de corpo (minha, por AST).** Comparei as 273 funções e classes do `api.py` base com a
  versão movida. Normalizei só o prefixo de lar (`api_core.X`/`routes.<m>.X` → `X`) e
  `@app.` → `@router.`. No commit anterior à R18 (`b9ddf5ce`), só 2 funções diferem, `stripe_webhook`
  e `account_transcription`, e a diferença é exatamente `routes=app.routes` → `routes=request.app.routes`
  em 4 sites (a exceção permitida pela R21). Na ponta, as outras 22 diferenças são os 22 sites da R18.
  Nenhuma função sumiu. As 2 novas são `_mount_router` e `_load_or_404`.
- **patch_liveness.** O `before` e o `after` commitados são idênticos (378 chaves). Rodei o plugin de
  novo, eu mesmo, em 8 arquivos, no base e na ponta (194 chaves, 104 `True`): **iguais** entre si e
  iguais ao subconjunto do `before`. A mutação dos não-chamáveis também é idêntica antes e depois
  (19 falham, 5 passam).
- **Patch de volta para `api.X` (amostragem de 3).** O teste falhou com `AttributeError` nos três:
  `tests/test_account_api.py:30` (`_database_profile`), `tests/test_error_envelope.py:148`
  (`_execute_action`) e `tests/test_spec352_creature_quote_api.py:100` (`_portrait_store`).
  Revertido; `git status` limpo.
- **Lar único em runtime.** Cada um dos 35 nomes de `patch_lars.json` existe só no seu lar, entre
  os 12 módulos da API. Há só dois `global`: `_CODE_RE` em `api` e `_FAKE_GOOGLE` em `routes.billing`,
  e nenhum dos dois é reexportado. Todo `api.X` lido em tests/playtest/evals/scripts existe em `api`.
- **W3.** Normalizei o diff de `tests/` (prefixo de lar → `api.`, sem linhas de import). Sobra só
  quebra de linha do `ruff format` (o prefixo ficou maior), a troca de alvo dos scanners para
  `api_source_text()`/`API_FILES`/`api_rel_files()` (D3) e as chaves da allowlist
  `api.py::f::n` → `<novo>::f::n` (as mesmas 17 `(f, n)`). **Nenhuma asserção mudou.**
- **R18.** `_load_or_404` (`api_core.py:748`) resolve `_resolve_save_file` e os loaders pelo
  namespace do lar na hora da chamada. Tem 22 chamadores: art 4, billing 2, play 4, read 7,
  saves 2, turn 3. O único site não convertido é `routes/turn.py:1245` (recarga `fresh`, que não
  dá 404). O golden (`b9ddf5ce`) nasceu antes do helper e não mudou depois.
- **R4/R5/R2.** As chamadas de efeito colateral (`assert_boot_policy`, `configure_logging`,
  `log_boot_once`, os 2 hooks de telemetria, `app.middleware("http")`) continuam em `api.py`. Nos
  módulos novos, o nível de módulo só tem constantes e o `router`. `api.py` tem 1.082 linhas.
- **R16/R15.** Os três gates por caminho incluem `routes/` e `api_*.py`. Bundle coberto pelo teste.
- `ruff check`, `ruff format --check` e `ruff_baseline.py --check` estão verdes.
  `dup_helpers --diff` só aponta nomes que já existiam (movidos). `evals/`, `web/`, `services/`,
  `agents/`, `persistence.py`, `playtest/` e `project_index/` não foram tocados.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `ruff-baseline.toml:21`; `api.py:9-98` | A R17(b) não foi cumprida. Com config sem baseline, as violações de `api.py`+módulos novos sobem de 76 para 200: F401 3→109, E402 4→12, I001 2→13 e F811 0→1. Quase todos os F401 são imports mortos que ficaram no topo de `api.py`, provavelmente de propósito, para manter a ordem de import (R7a). O efeito é que o F401 da baseline esconde ~106 imports sem uso. O E402 +8 vem das montagens no ponto exato (é desvio já registrado). | Registrar no "Registro de execucao" da spec que os imports ficaram por causa da ordem (R7a), com a contagem 76→200 explicada. Abrir follow-up (spec própria, depois da 379) para podar os imports mortos de `api.py` com o oráculo R7a. |
| P2-2 | P2 | `api.py:153`; `ruff-baseline.toml:21` (F811) | `from api_models import GameResponse` aparece duas vezes (`:111` e `:153`). Isso põe um código novo, o F811, na baseline de `api.py`, e ele não vem de movimento. | Apagar a linha 153 (sem efeito: o módulo já foi carregado na `:99`) e regenerar a baseline. |
| P2-3 | P2 | `ruff-baseline.toml:294` e +20 entradas `tests/*` com `I001` | 21 arquivos de teste ganharam `I001` na baseline porque o `import api_core`/`routes.X` novo ficou fora de ordem. Isso é dívida nova, não movimento. A proibição de `--fix` da R17 vale para código movido, não para os imports dos testes. | Ordenar o bloco de imports desses testes (`ruff check --select I --fix tests/<arquivo>`) e regenerar a baseline. Ou registrar a exceção na spec. |
| P2-4 | P2 | `tests/test_spec381_api_surface.py:37`; `<worktree>/.venv` | A parte `modules.json` do teste depende do ambiente. Neste worktree apareceu um `.venv` próprio às 05:23 de hoje, criado durante a revisão; não deu para atribuir a origem. Ele tem 192 pacotes contra 256 no `.venv` principal e não tem `rich`/`opentelemetry`. Nesse ambiente, `uv run pytest` faz `test_http_surface_is_byte_identical[legacy]` falhar ("import api deixou de carregar modulos": 105 módulos de rich/otel/pygments). Não é regressão: com o mesmo interpretador, base e ponta carregam os mesmos módulos. Com `UV_PROJECT_ENVIRONMENT` apontando para o `.venv` principal, tudo fica verde. | Coordenador: antes da suíte, apagar `C:\Users\guilh\AppData\Local\Temp\claude\rpg-spec-381\.venv` (ou exportar `UV_PROJECT_ENVIRONMENT` para o venv principal). Apagar o teste agora, como manda a Etapa 15. |
| P3-1 | P3 | `docs/spec381/not_found_golden.json` | Em `quote:unknown` e `confirm:unknown` o golden recebe 503 (`image_quotes_unavailable`, flag off). Assim, `create_image_quote` (`routes/art.py:192`) e `confirm_player_art` (`routes/art.py:264`) não chegam ao loader. Esses 2 dos 22 sites só têm a prova de AST. `history:omitted`, `chron_search:omitted` (422) e `world_map:omitted` (200) também não exercitam o 404. | Opcional: acrescentar um caso com a flag de quotes ligada. A troca nesses sites é mecânica e a AST confirma a sequência. |
| P3-2 | P3 | `tests/size_budget.json:10,57,156` | O `--update` também apertou entradas fora do escopo: `agents/npc.py` 1605→1604, `npc_actor_node` 779→778, `round_registry` 123→117. Só encolhem, então não fazem mal, mas podem conflitar no rebase. | Nenhuma, ou devolver essas 3 linhas ao valor da `main` no `wt.sh sync` se houver conflito. |
| P3-3 | P3 | `specs/SPEC-381-refactor-api-routers.md:3` | O cabeçalho ainda diz "faltam R13b/R18", mas as duas já foram feitas. Os critérios do §5 estão sem marca. A spec cita `docs/spec381/readers.json` (Etapa 0 item 2), que não existe: os leitores fora de `tests/` estão no próprio `patch_inventory.json`. | Atualizar o cabeçalho e marcar os critérios no pouso. Mencionar que os readers estão dentro do inventário. |
| P3-4 | P3 | `docs/spec381/patch_mutation_*.json` | A R13b pede que os testes mutados falhem. 5 de 24 passam, antes e depois (ex.: `test_lock_wait_measured`). Como é igual nos dois lados, não indica regressão, mas esses 5 testes não dependem do valor patchado. | Só registrar na spec. |
| P3-5 | P3 | `api.py:349-353`; `api_core.py:745` | `_CORS_ORIGINS` virou uma lista única preenchida no lugar. Depois de `reload(api)`, um `app` antigo, se ainda houver referência a ele, passa a ver as origens novas. No base, cada reload criava uma lista nova. Isso já está registrado no "Registro de execucao" e é inofensivo. | Nenhuma. |

Não encontrei P0 nem P1. Não há structured output novo, valor de LLM, writer persistente, segredo em
log, `evals/` alterado nem `except` amplo novo (os de `api_core`/`routes` são movidos e continuam na
allowlist).

## Correções aplicadas

Nenhuma: a revisão não edita código.

## Pendências

- P2-1..P2-3: o executor ou o coordenador resolve antes do pouso, ou registra na spec (P2-1 vira
  follow-up de spec própria para podar imports mortos de `api.py`).
- P2-4: o coordenador apaga o `.venv` do worktree antes da suíte e apaga `test_spec381_api_surface.py`
  (Etapa 15).
- Ainda com o coordenador: W2 de evals, playtest e catálogo; a suíte completa 1×; o smoke local
  (`uvicorn api:app` e `python api.py` + `smoke_api.sh` + `smoke_local_profile.py`); o §6 em
  staging (anotar o cold start).

## Comandos rodados

```text
git worktree add --detach <scratch>/base381 52e0908e → base independente (removido no fim)
api_surface_dump.py base e ponta (legacy+hosted) → 10/10 byte-iguais ao before; módulos: só +12 novos
ordem de sys.modules base × ponta → idêntica salvo 4 codecs CJK
-X importtime 7 pares intercalados → mediana 2654 × 2703 ms (1,018)
eqv.py (AST) base × b9ddf5ce → 2 diffs (R21 request.app.routes); base × ponta → +22 (R18)
w3.py (diff tests normalizado) → só reformatação, alvo de scanner e chaves da allowlist
mutação 3× setattr(api, X) → AttributeError nos 3; revertido
patch_liveness -n 0, 8 arquivos, base e ponta → 194 chaves iguais entre si e ao before
ruff check / format --check / ruff_baseline --check → verdes; ruff sem baseline → 76 → 200 (P2-1)
pt.sh -n 0: spec381_{api_surface,structure,route_label,bundle,not_found_golden}, spec192, boot_policy, fase10 → 168 passed
pt.sh -n 2: 27 arquivos de scanner/turno/gates → 443 passed, 2 skipped
pt.sh -n 2: 23 arquivos de arte/billing/play/leitores → 380 passed, 4 skipped
dup_helpers --diff main...HEAD → só nomes movidos
```
