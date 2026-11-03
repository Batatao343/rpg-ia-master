# SPEC-385 — Contrato front↔back: forma real das respostas × backend falso do e2e

> **Status:** `draft` · **Prioridade:** BAIXA (opcional)
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** auditoria de qualidade 03/11, `docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md` §3 R7, §5 letra O, §6 (W1–W8)
> **Depende de:** SPEC-381 (`api.py` em routers + `api_models.py`) e SPEC-383 (e2e por feature) **pousadas**
> **Desbloqueia:** preparação de contrato antes da SPEC-198 (Android); opções (b)/(c) desta spec
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`. Só vale enquanto **nada** for criado ou alterado em
> `web/e2e/contracts/` (caminho protegido, `evals/protected-paths.txt:13`). Se a solução precisar
> desse diretório, a spec passa a `true` e o fluxo vai para `/eval-publish`. O desenho abaixo evita isso.

Rótulos: **[F]** fato conferido no source (arquivo:linha) · **[H]** hipótese a confirmar na etapa ·
**[D]** decisão do dono (§8).

---

## 1. Contexto & Objetivo

**[F]** O front tipa a API à mão. `web/src/types.ts:1` diz "Espelha os DTOs da API (api.py ::
GameResponse / blocos auxiliares)". São 127 `export`s. O backend falso do e2e também é escrito à
mão: `web/e2e/fixtures.ts:12-53` monta `gameState(): GameResponse` com o tipo do próprio front, e
`DeterministicBackend` (`fixtures.ts:90` em diante) responde `/game/*` (`:202`, `:368-376` no stream).
Na prática o e2e confere o front contra a ideia que o front tem do backend. Se o backend
renomeia um campo, o `types.ts`, o fixture, o `tsc` e o Playwright continuam verdes. A quebra só
aparece no staging.

**[F] Contagem real dos campos sem forma** em `GameResponse` (`api.py:2089-2132`). A auditoria fala
em ~18. Pela contagem no source:
- **16 campos com `Any`:** 10 `dict[str, Any]` (`player_stats`, `world`, `quest`, `combat`, `death`,
  `continuity`, `combat_simulation`, `turn_outcome`, `combat_result`, `projections`) e 6
  `list[dict[str, Any]]` (`inventory`, `last_turn_log`, `npcs`, `chronicle`, `factions`, `party`);
- **mais 4 sem forma, só de `str`:** `speaker: dict[str, str]`, `art_offers`, `art_generations` e
  `reputation_notices` (`list[dict[str, str]]`);
- só `visual: VisualResponse` (`:2132`) é tipado de verdade. São **20 de 21 blocos estruturados**
  sem schema. No `api.py` inteiro aparecem 51 ocorrências de `dict[str, Any]`.

**[F]** O schema OpenAPI hoje não diz quase nada sobre o miolo. `response_model=GameResponse` está em
`/game/new` (`api.py:5276`), `/game/action` (`:6898`), `/game/death` (`:6918`) e
`/game/combat-simulator` (`:4002`). Mesmo assim, `player_stats.cards[]` (`:2273`) ou `combat.enemies[]`
saem como `object` livre. O fuzz da SPEC-338 já desligou a checagem de conformidade de resposta
(`tests/test_api_fuzz_schemathesis.py:5-6`), e `web/e2e/contracts/` está listado como protegido,
mas o diretório **não existe** (`handoffs/SPEC-321-sol-review.md:45`).

**Objetivo:** pegar o drift entre o backend falso e o real com o menor custo, sem mudar nenhum byte
do JSON que o backend devolve. A auditoria sugere tipar tudo em Pydantic e gerar TS. Esta spec
escolhe, por padrão, uma rede mais barata (opção **a**) e deixa (b)/(c) como etapas condicionais
(D1). Tipar 20 blocos mexe no caminho de serialização de toda resposta de turno, e nenhum bug de
contrato real foi registrado até hoje **[H: confirmar no CHANGELOG/handoffs na Etapa 0]**.

### Opções (custo × risco × o que pegam)

| | O que é | Custo | Risco | Pega rename aninhado (`combat.enemies[].vitalidade`)? |
|---|---|---|---|---|
| **(a) recomendada** | snapshot versionado de `app.openapi()` + **snapshot de forma** (árvore de chaves e tipos JSON) de respostas reais do backend em N cenários offline (MockLLM). Teste no Playwright sem navegador: toda chave do fixture tem que existir na forma real | ~1–2 dias, sem tocar o backend | baixo: só arquivos novos e testes | **sim**, nos cenários cobertos. Os 20 blocos `Any` deixam o OpenAPI frouxo, e é o snapshot de forma que cobre esse buraco |
| (b) | tipar os 20 blocos em Pydantic, um bloco por commit | ~1–2 semanas | **alto**: a serialização muda o JSON em silêncio (§7) | sim, e em todos os estados, não só nos cenários |
| (c) | (b) + `openapi-typescript` gerando `web/src/api-types.gen.ts`, com `types.ts` virando aliases | (b) + ~3 dias | (b) + acoplar o build do front ao Python | sim, e ainda tira o espelho manual |

**Limitação honesta de (a):** a forma vem só dos cenários que a suíte consegue montar offline.
Uma chave que só aparece em estado raro (por exemplo `death` em Estado Terminal ou `chase` ativo)
gera falso positivo ou falta de cobertura. Os falsos positivos ficam numa allowlist com motivo
(R6). A falta de cobertura fica registrada, e o smoke real (§6) amplia a amostra. A opção (a)
também não substitui o `types.ts` manual. Ela só garante que o fixture não usa chave que o backend
real não produz.

## 2. Requisitos

Requisitos da opção (a), que é o padrão:

- **R1 [F→teste]** — `scripts/dev/api_contract.py dump` grava
  `web/api-contract/openapi.json`, que é `app.openapi()` serializado com `sort_keys=True`, `indent=2`
  e LF. `tests/test_api_contract_snapshot.py::test_openapi_snapshot_fresh` falha, com a mensagem
  "rode `bash scripts/dev/py.sh scripts/dev/api_contract.py dump`", se o arquivo diferir do
  gerado na hora.
- **R2** — O mesmo script grava `web/api-contract/game_response.shape.json`, a forma das respostas
  reais de `POST /game/new`, `POST /game/action` e `POST /game/death`, via `TestClient` e MockLLM, em
  **≥ 6 cenários**: jogo novo; turno de história; início de combate com o baralho na configuração
  default; combate de cartas com flags de cartas `on` (por override de env no teste); loot/loja; morte
  (`death_pending`); level up (`pending_choices` não vazio). Cada cenário reaproveita um teste
  existente que já monta o estado, citado no docstring. Se algum cenário não puder ser montado
  offline, ele fica listado no arquivo como `"uncovered"`, com o motivo, e nunca é omitido em silêncio.
- **R3** — Formato da forma: cada caminho (`player_stats.cards[].valid_targets`) mapeia para o
  conjunto de tipos JSON vistos (`string|number|boolean|null|object|array`). Listas fazem a união
  dos elementos. Lista vazia em todos os cenários vira `"array<unknown>"`. Os caminhos de **mapa
  dinâmico** (chave é id, não nome de campo) são declarados em `MAP_PATHS` no script e viram
  `path.*`. Candidatos **[H: confirmar no source]**: `player_stats.ferimentos`, `world.controlled`,
  `world.danger_overrides`, `combat.cooldowns`, `combat.wounds.slots` e
  `combat.enemies[].recursos_visiveis`.
- **R4** — `test_shape_snapshot_fresh` faz para a forma o mesmo que R1 faz para o OpenAPI. Roda na
  suíte default (job `test` de `validate.yml:47-94`, que sempre roda), offline, em < 20 s
  **[H: medir]**.
- **R5** — `web/e2e/api-contract.spec.ts` é um Playwright **sem `page`**, sem navegador e sem rede.
  Ele importa `gameState()` e as respostas do `DeterministicBackend` (os pós-ação de história,
  combate, loot e morte) e afirma três coisas:
  (i) toda chave de topo do fixture existe em `components.schemas.GameResponse.properties` do
  `openapi.json`, e todo `required` está presente;
  (ii) **todo caminho do fixture existe na forma real** com tipo compatível (`null` só passa se o
  real já mostrou `null` ou se o campo é opcional no OpenAPI);
  (iii) a mensagem de falha mostra o caminho e o tipo esperado.
  Chave real que o fixture **não** tem não é erro (fixture incompleto é aceito). O teste só conta
  essas chaves no relatório.
- **R6** — Os falsos positivos de R5 ficam em `web/api-contract/shape-allowlist.json`, cada entrada
  com `{path, reason, kind: "scenario_not_covered"|"real_bug_tracked", ref}`. Uma entrada `real_bug`
  sem `ref` (spec ou issue) falha o teste. A allowlist inicial é **triada uma a uma** na Etapa 2.
  Divergência que for bug real não entra como "não coberto".
- **R7** — Nenhum byte do JSON de resposta muda: `api.py`/`api_models.py` e `format_response`
  ficam intactos (W3). Prova: o diff do `openapi.json` gerado antes e depois da spec é vazio,
  conforme o W2.4 (`auditoria §6.2`).
- **R8** — Nada é criado ou alterado em `web/e2e/contracts/`, `evals/` nem `critical-journeys.yaml`.
  Se `scripts/frontend_eval_report.py --check` exigir mapear todo spec do e2e para uma jornada
  **[H: confirmar]**, o executor **para e reporta**. Mapear o spec novo em arquivo protegido exige
  `EVAL_AUTHORING_REQUIRED: true`.
- **R9** — Cadeia no CI: uma mudança só de backend que altera a forma faz R4 falhar no job `test`.
  Regerar grava em `web/api-contract/`, e isso marca o escopo `frontend`
  (`scripts/ci_eval_scope.py:28`, prefixo `web/`), o que dispara `frontend-selective`
  (`eval-gates.yml:111-136`), onde R5 roda. Um teste Python afirma que
  `ci_eval_scope` classifica `web/api-contract/openapi.json` como `frontend`.

Requisitos condicionais, **só se D1 = (b) ou (c)**:

- **R10 (b)** — Cada bloco (`_cards_block`, `combat`, `world`, `quest`…) vira um modelo Pydantic com
  `model_config = ConfigDict(extra="allow")`, um bloco por commit (W4). Antes do primeiro bloco
  entra um **golden de respostas** com ≥ 10 cenários (os de R2 mais: rodada de combate com reação,
  fuga, loja com compra, retrato pago, save antigo carregado, `game_over`), comparado **byte a byte**
  com `json.dumps(sort_keys=True)` antes e depois de cada commit. O golden fica fora de `evals/`.
- **R11 (b)** — Nenhum campo novo `Optional` pode aparecer como `null` onde antes estava ausente.
  Avaliar `response_model_exclude_unset=True` ou `exclude_none` **por rota**. Teste que afirma "chave
  ausente continua ausente" para os 3 campos mais lidos com `in`/`?.` no front
  **[H: levantar via Grep em `web/src`]**. `int`/`float` mantêm o tipo exato do JSON atual (2 ≠ 2.0
  no golden).
- **R12 (c)** — `openapi-typescript` entra como devDependency. `npm run gen:api` gera
  `web/src/api-types.gen.ts` a partir de `web/api-contract/openapi.json`, que é **versionado**: o
  build do front não chama Python. O CI falha se o gerado estiver desatualizado. `types.ts`
  reexporta e cria aliases aos poucos, um bloco por commit, sem mudar nenhum nome exportado usado
  em `web/src`.

### Fora de escopo

- Validar as respostas do stream SSE (`/game/action/stream`, `fixtures.ts:368-376`) além do payload
  final. Fica como follow-up se (a) pousar.
- As outras rotas além das 4 com `GameResponse`: conta, pagamentos, mapa, saves, arte.
- Ativar a conformidade de resposta do Schemathesis (SPEC-338).
- Apagar ou reescrever `types.ts` (na opção (a) ele continua manual).
- Qualquer mudança de comportamento ou de JSON no backend (fica para (b), sob D1).
- Criar `web/e2e/contracts/`.

## 3. Design técnico

**Arquivos novos (a):**
- `scripts/dev/api_contract.py` com `dump(out_dir: Path) -> None`, `shape_of(payloads:
  list[dict]) -> dict[str, list[str]]` e `check(out_dir: Path) -> list[str]` (as diferenças). O
  `MAP_PATHS: tuple[str, ...]` fica aqui. Roda offline com `RPG_FORCE_MOCK=1` e saves em `tmp_path`.
- `web/api-contract/openapi.json`, `game_response.shape.json` e `shape-allowlist.json`, todos
  versionados. A diferença aparece no PR, o que é o ponto: renomear um campo fica visível na revisão.
- `tests/test_api_contract_snapshot.py`, com R1, R4 e R9.
- `web/e2e/api-contract.spec.ts`, com R5 e R6. Se `fixtures.ts` não exportar as respostas pós-ação,
  o executor exporta um helper **sem mudar o comportamento** do backend falso.

Exemplo do formato da forma:

```json
{
  "scenarios": ["new_game", "story_turn", "combat_cards_on", "loot_shop", "death_pending", "level_up"],
  "uncovered": [{"scenario": "estado_terminal", "reason": "sem fixture offline"}],
  "paths": {
    "player_stats.vitalidade": ["number"],
    "player_stats.cards[].valid_targets": ["array", "null"],
    "combat.enemies[].revealed_cards": ["array<unknown>"],
    "player_stats.ferimentos.*": ["array"]
  }
}
```

**Arquivos alterados (a):** `web/e2e/fixtures.ts`, no máximo export de helper. Os workflows **não**
mudam, porque `validate.yml:47-94` já tem uv e node no mesmo job e `frontend-selective` já roda o
`test:e2e`.

**(b)/(c):** `api_models.py` (pós-381) com os modelos por bloco, `web/package.json` (devDependency e
script) e `web/src/types.ts`. O detalhe vai numa revisão desta spec quando D1 for decidido.

## 4. Plano passo a passo

Cada etapa segue o W1 (trava de arquivos): cruzar com as branches abertas antes de começar. O W4
vale também: um commit por mudança mecânica.

### Etapa 0 — Levantamento (sem código)
1. Confirmar que 381 e 383 pousaram e anotar onde `GameResponse` mora agora.
2. Procurar no `CHANGELOG.md` e em `handoffs/` bug de contrato front↔back já visto em staging. Se
   houver, citar no hand-back, porque isso pesa no D1.
3. Ler `scripts/frontend_eval_report.py` e decidir R8 (para se precisar de arquivo protegido).

### Etapa 1 — Snapshot do OpenAPI e da forma (testes primeiro)
1. **Testes:** `test_openapi_snapshot_fresh` e `test_shape_snapshot_fresh` (vermelhos sem os
   arquivos); `test_shape_of_merges_list_elements` e `test_shape_of_map_paths` (unitários de
   `shape_of` com dicts sintéticos); `test_scope_marks_api_contract_as_frontend`.
2. **Implementação:** `api_contract.py` e o primeiro `dump`.
3. **Verificação:** só esses testes, `-n 2` no máximo.

### Etapa 2 — Checagem fixture × real e triagem
1. **Teste:** `web/e2e/api-contract.spec.ts` (rodar só ele: `npx playwright test
   e2e/api-contract.spec.ts --workers=1`).
2. Rodar e **triar cada divergência**. Bug real: registrar no hand-back e abrir follow-up, nunca
   corrigir o backend aqui. Cenário não coberto: entrada na allowlist com motivo.
3. Prova de sensibilidade (mutação manual, não commitada): renomear `vitalidade` em
   `combat.enemies[]` no `api.py` local faz R4 falhar, e com a forma regerada faz R5 falhar. Anotar a
   saída no hand-back.

### Etapa 3 — Documentação
1. Um parágrafo em `docs/guias/TESTES.md` explicando como regerar o contrato e quando a allowlist é
   aceita.

### Etapas 4+ — só se D1 = (b)/(c)
Revisar esta spec antes de começar: golden de 10+ cenários (R10), depois um bloco por commit na
ordem `turn_outcome` → `combat_result` → `quest` → `world` → `player_stats.cards` → `combat`
(do menor para o mais lido), com o golden byte-igual a cada commit. Para (c), por último, R12.

## 5. Critérios de aceite

- [ ] R1–R9 com teste. Saída das etapas 1 e 2 no hand-back.
- [ ] Prova de sensibilidade da Etapa 2.3 executada e registrada.
- [ ] Allowlist com toda entrada triada. Nenhuma `real_bug_tracked` sem `ref`.
- [ ] `openapi.json` byte-igual antes/depois (R7, W2.4). `git diff main -- api.py api_models.py` vazio.
- [ ] `git diff main -- web/e2e/contracts evals/ web/e2e/critical-journeys.yaml` vazio (R8).
- [ ] `uv run pytest` verde (coordenador, 1×, no pouso) e `npm run typecheck:e2e` verde.
- [ ] Revisão independente `Sol` (W7) rodando de novo a prova de sensibilidade.
- [ ] Saves antigos: sem efeito (nenhum writer novo).

## 6. Smoke test com LLM real

**(a):** sem LLM no caminho. A rede é offline, mas a amostra MockLLM é pobre, então vale um smoke
barato de amostragem:
1. No staging, jogar pelo front 1 jogo novo, 3 turnos de história e 1 combate de cartas até o fim.
2. Salvar as 5 ou mais respostas JSON da aba Network em `$SCRATCH` (fora do repo, sem dados de conta).
3. Rodar `api_contract.py check --extra-payloads <dir>` e registrar quais caminhos do fixture **só**
   o real confirmou ou contradisse.

**(b)/(c):** obrigatório e igual a esse, mas comparando o JSON real de staging **antes** do deploy
com o de **depois**. Mesmos cenários (3 turnos e 1 combate), e o front tem que jogar sem erro de
console.

## 7. Riscos & compatibilidade

- **Mudança silenciosa de JSON (só b/c, crítico).** `format_response` já faz `model_dump()` e
  depois `model_validate()` (`api.py:2204`), e o FastAPI serializa pelo `response_model`. Ao tipar
  os blocos, o Pydantic: adiciona chaves `None` que antes não existiam (o front que testa `in` ou
  `!== undefined` muda de ramo); com o `extra="ignore"` default, **descarta chaves extras sem
  aviso**; converte `int`↔`float` (2 vs 2.0); pode reordenar chaves. Mitigação: R10 e R11, com
  golden byte-igual, `extra="allow"` e um bloco por commit.
- **Acoplamento do build do front ao Python (c).** Mitigado em R12, com `openapi.json` versionado
  e o gerador lendo o arquivo, sem chamar o backend. O CI já tem uv nos dois jobs de front
  (`validate.yml:54`, `eval-gates.yml:120`). O build local do front continua sem Python.
- **(a) com falsa segurança:** cobre só os cenários amostrados (§1, limitação). A allowlist pode
  virar lixeira. Mitigação: `kind` e `ref` obrigatórios (R6) e o revisor confere a triagem.
- **Atrito:** toda mudança no shape da resposta exige regerar e commitar 2 arquivos. É o custo
  pretendido, porque o diff fica visível no PR.
- **Conflito com outras sessões:** `fixtures.ts` e `types.ts` são arquivos quentes (W1). Esperar 383.
- MockLLM/FallbackLLM: sem efeito, porque nenhum nó de LLM muda. Quota/latência: zero na suíte
  e +<20 s **[H]** no pytest.

## 8. Decisões do dono

- **D1 — Qual opção?** (a) agora [recomendado]; (b) tipar os blocos; (c) (b) + TS gerado.
  Recomendação: **(a)**. Fazer (b)/(c) só se (i) aparecer um bug de contrato real em staging, ou
  (ii) antes do lançamento Android (SPEC-198), quando um segundo cliente passar a consumir a API
  e o espelho manual deixar de ser suficiente.
- **D2 — Esta spec entra na onda 375–384 ou fica na fila depois dela?** Recomendação: fila. É de
  prioridade baixa e depende de 381 e 383.
- **D3 — Bug real achado na triagem (Etapa 2.2):** abrir uma spec de correção por bug ou juntar
  todos numa só? Recomendação: juntar numa só, se forem até 3 bugs.
