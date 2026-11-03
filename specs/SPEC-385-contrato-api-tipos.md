# SPEC-385 — Contrato front↔back: forma real das respostas × backend falso do e2e

> **Status:** `draft` — ADIADA (revisão independente 03/11: DEFER, `handoffs/SPEC-385-independent-review.md`)
> **Prioridade:** BAIXA (opcional)
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Gatilho de reabertura:** (i) o 1º bug de contrato front↔back (drift de chave/forma) visto em staging
> ou em smoke real; **ou** (ii) o início da SPEC-198 (Android, segundo cliente da API). Antes disso, não
> executar. Sem o gatilho, a rede custa mais do que pega (§9).
> **Origem:** auditoria de qualidade 03/11, `docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md` §3 R7, §5 letra O, §6 (W1–W8)
> **Depende de:** SPEC-383 pousada (reorganiza `web/e2e/fixtures.ts`). A SPEC-381 só precisa de
> coordenação, não de pouso: a fonte do dump OpenAPI fica unificada (R1, P1-1).
> **Desbloqueia:** preparação de contrato para a SPEC-198; opções (b)/(c) desta spec
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`. Só vale enquanto **nada** for criado ou alterado em
> `web/e2e/contracts/` (protegido em `evals/protected-paths.txt:13`, diretório inexistente) nem em
> outro caminho de `evals/protected-paths.txt`. Se precisar, a spec passa a `true` e o fluxo vai para `/eval-publish`.

Rótulos: **[F]** fato conferido no source (arquivo:linha na `main` `2a6e0945`) · **[H]** hipótese a
confirmar · **[D]** decisão do dono (§8). As linhas do `api.py` andam rápido. A Etapa 0 recita todas.

---

## 1. Contexto & Objetivo

**[F]** O front tipa a API à mão. `web/src/types.ts:1` diz "Espelha os DTOs da API (api.py ::
GameResponse / blocos auxiliares)" e tem 127 `export`s. O backend falso do e2e também é escrito à
mão. `web/e2e/fixtures.ts:12-53` monta `gameState(): GameResponse` com o tipo do próprio front, e
`DeterministicBackend` (`fixtures.ts:90` em diante) responde `/game/*` (`:202`; stream em `:368-376`).
`gameState()` só é chamado dentro de `fixtures.ts`. Na prática, o e2e confere o front contra a ideia
que o front tem do backend. Um campo renomeado no backend passa em `tsc` e no Playwright e só quebra
no staging.

**[F] Contagem real** em `GameResponse` (`api.py:2093-2136`):
- **16 campos com `Any`:** 10 `dict[str, Any]` (`player_stats`, `world`, `quest`, `combat`, `death`,
  `continuity`, `combat_simulation`, `turn_outcome`, `combat_result`, `projections`) e 6
  `list[dict[str, Any]]` (`inventory`, `last_turn_log`, `npcs`, `chronicle`, `factions`, `party`);
- **mais 4 só de `str`:** `speaker`, `art_offers`, `art_generations`, `reputation_notices`;
- só `visual: VisualResponse` é tipado. São **20 de 21 blocos estruturados sem schema**. No `api.py`
  há 51 `dict[str, Any]`.

**[F]** `response_model=GameResponse` aparece em 4 rotas (`api.py:4009, 5285, 6923, 6943`). O
OpenAPI, porém, descreve o miolo como `object` livre. `format_response` faz `model_dump()` e depois
`model_validate()` (`api.py:2208`). O fuzz da SPEC-338 desligou a conformidade de resposta
(`tests/test_api_fuzz_schemathesis.py:5-6`).

**[F] Por que está adiada.** Não há registro de drift de chave fixture×backend em staging (grep em
`CHANGELOG.md`, `handoffs/` e `git log` desde 01/09, feito na revisão). O caso mais próximo, SPEC-323
P1-1, é divergência de **valor** (descrição de beat redigida como "Etapa N"), e nenhuma opção daqui o
pegaria. O churn é alto: em 30 dias, `types.ts` teve 49 commits, `fixtures.ts` 19 e `api.py` 138.
Qualquer arquivo versionado de contrato vira ponto quente para as outras sessões.

**Objetivo (quando reabrir):** pegar drift de **chave e forma** entre o backend falso e o real com o
menor custo, sem mudar nenhum byte do JSON nem criar arquivo que outras sessões tenham de regenerar.

### Opções (custo × risco × o que pegam)

| | O que é | Custo | Risco | Pega rename aninhado? |
|---|---|---|---|---|
| **(a′) recomendada ao reabrir** | forma real **efêmera**, gerada no CI a partir de **estados injetados com semente fixa**, mais um teste que exige que o fixture seja subconjunto do real. Nada versionado | ~1 dia | baixo: arquivos novos, nenhum hot spot além de 1 export em `fixtures.ts` | **sim**, nos objetos cobertos (§1, limitação) |
| (b) | tipar os 20 blocos em Pydantic, um por commit | ~1–2 semanas | **alto**: JSON muda em silêncio (§7) | sim, em todo estado |
| (c) | (b) + `openapi-typescript` gerando TS | (b) + ~3 dias | (b) + acoplamento do build | sim, e tira o espelho manual |

**Limitação honesta de (a′):**
- cobre só os objetos que o teste percorre: `gameState()` base e as respostas pós-ação do
  `DeterministicBackend`. Os overrides montados dentro de specs (como `card-shop-357.spec.ts`, que
  monta `player_stats`) ficam de fora;
- lista ou dict vazio no fixture (`enemies: []`, `cooldowns: {}`) não verifica nada abaixo dele;
- `number` não distingue int de float;
- não pega divergência de valor;
- a forma real vem dos estados injetados, e chave que só aparece em estado raro e não injetado fica
  sem cobertura.

## 2. Requisitos — opção (a′)

- **R1 — Fonte única de OpenAPI (P1-1).** Esta spec **não** cria um segundo snapshot de OpenAPI. Ela
  reaproveita o dumper da SPEC-381 (`scripts/dev/api_surface_dump.py`, que gera
  `docs/spec381/before/openapi.json`, checado por `tests/test_spec381_api_surface.py`)
  **[H: confirmar nomes quando a 381 pousar]**. Se a 381 aposentar o teste congelado no pouso
  (pendência do coordenador), a 385 lê `app.openapi()` em memória. As duas specs registram a escolha.
- **R2 — Estados injetados, não jogados (P0-1).** A forma real vem de `format_response(state)`, com
  `cue_action_key` fixo, aplicada a **estados de jogo montados a partir de saves fixos** (fixtures de
  teste já existentes, citadas no docstring) para ≥ 6 cenários: jogo novo; turno de história;
  combate ativo com flags de cartas na configuração default; combate de cartas `on` por override de
  env; loja/loot; `death_pending`; level up (`pending_choices` não vazio). Nunca "jogar até cair em
  combate" com MockLLM. Cenário impossível de montar fica em `uncovered`, com motivo.
- **R3 — Determinismo.** `random` e o RNG do motor ficam semeados, e `game_id` e `uuid` fixos por
  cenário. `test_shape_dump_deterministic` gera a forma 2× no mesmo processo e mais 1× num subprocesso
  com outro `PYTHONHASHSEED`, e afirma igualdade byte a byte. Sem esse teste verde, nenhum outro
  teste desta spec entra na suíte default. Na sonda da revisão, o caminho jogado deu 4 formas
  distintas em 5 rodadas.
- **R4 — Formato da forma.** Cada caminho (`player_stats.cards[].valid_targets`) mapeia para o
  conjunto de tipos JSON vistos. Listas fazem a união dos elementos, e lista sempre vazia vira
  `array<unknown>`. Mapas de chave dinâmica (id como chave) ficam em `MAP_PATHS` e só entram se o
  **builder no source** mostrar chave por id (P2-2). `combat.wounds.slots` **não** entra, porque as
  chaves são fixas (`leve/grave/critico`). Os demais candidatos (`player_stats.ferimentos`,
  `world.controlled`, `world.danger_overrides`, `combat.cooldowns`,
  `combat.enemies[].recursos_visiveis`) ficam **[H]** até a leitura do builder.
- **R5 — Forma efêmera (P1-2).** Nada é versionado: sem `shape.json` e sem allowlist de forma no
  repo. No job `frontend-selective` (`eval-gates.yml:111-136`), um passo antes do `test:e2e` roda
  `uv run python scripts/dev/api_contract.py dump --out "$RUNNER_TEMP/contract"` e passa o caminho
  ao Playwright em `RPG_API_SHAPE`. Localmente, sem a env, o spec faz `skip` com a mensagem de como
  gerar.
- **R6 — Checagem fixture ⊆ real.** `web/e2e/api-contract.spec.ts` é um Playwright **sem `page`**,
  com título **fora** do padrão `^F\d\d\s`. Assim fica fora do gate de jornadas
  (`scripts/frontend_eval_report.py:19,51,73`). O teste afirma três coisas:
  (i) toda chave de topo do fixture existe em `GameResponse.properties` do OpenAPI, e todo
  `required` está presente;
  (ii) todo caminho do fixture existe na forma real com tipo compatível;
  (iii) a mensagem de falha mostra caminho e tipo.
  Chave real que o fixture não tem não é erro. Os objetos percorridos são listados pelo nome do
  helper ou método no próprio spec (P2-1).
- **R7 — Exceções com rastro.** Os falsos positivos ficam numa constante no próprio spec (não num
  arquivo à parte), cada uma com `{path, reason, kind: "scenario_not_covered"|"real_bug_tracked",
  ref}`. Um `real_bug_tracked` sem `ref` falha o teste.
- **R8 — Escopo (P1-3) [F].** `scripts/ci_eval_scope.py:28-29` marca como `frontend` tanto `web/`
  quanto `FRONTEND_FILES` (inclui `api.py`). Mudança de forma vinda de `api.py` dispara R5/R6.
  Mudança vinda só de `services/*` **não** dispara, e o drift aparece no próximo PR de front.
  Isso é aceito de forma explícita, com custo zero. Alternativa sob **[D2]**: um passo só Python no
  job `test` (`validate.yml:47-94`) que compara a forma contra um JSON do fixture exportado. Isso
  exigiria versionar esse JSON, o que reintroduz parte do churn.
- **R9 — Zero mudança de JSON e de caminhos protegidos.** `api.py`/`api_models.py` e
  `format_response` ficam intactos (W3). `git diff main -- web/e2e/contracts evals/` fica vazio.
  `web/e2e/critical-journeys.yaml` **não** é protegido **[F]** e mesmo assim não é tocado
  (conservador).

Requisitos condicionais, **só se D1 = (b) ou (c)**:

- **R10 (b)** — Um modelo Pydantic por bloco, com `extra="allow"`, um bloco por commit (W4). Antes do
  primeiro bloco entra um golden de ≥ 10 cenários, a partir dos estados injetados de R2 mais combate
  com reação, fuga, compra, retrato pago, save antigo e `game_over`. O golden compara byte a byte
  (`json.dumps(sort_keys=True)`) antes e depois de cada commit e fica fora de `evals/`.
- **R11 (b)** — Nenhum campo `Optional` novo aparece como `null` onde antes estava ausente. Avaliar
  `response_model_exclude_unset`/`exclude_none` por rota. Teste "chave ausente continua ausente"
  para os campos lidos com `in`/`?.` no front **[H: Grep em `web/src`]**. `int`/`float` mantêm o
  tipo exato.
- **R12 (c)** — `openapi-typescript` como devDependency. Gera `web/src/api-types.gen.ts` a partir
  da fonte única de R1, e `types.ts` passa a aliasar aos poucos sem renomear export. O CI falha se o
  gerado estiver desatualizado. Aqui o arquivo versionado é inevitável. O churn (P1-2) é o custo
  aceito de (c) e entra no D1.

### Fora de escopo

- Stream SSE além do payload final.
- Rotas sem `GameResponse`.
- Conformidade Schemathesis (SPEC-338).
- Reescrever `types.ts` em (a′).
- Qualquer mudança de JSON fora de (b).
- Criar `web/e2e/contracts/`.
- Pegar divergência de valor (como o caso SPEC-323 P1-1).

## 3. Design técnico (a′)

- **Novos:**
  - `scripts/dev/api_contract.py`, com `build_states() -> dict[str, dict]` (os cenários de R2,
    semeados), `shape_of(payloads: list[dict]) -> dict[str, list[str]]`, `dump(out: Path) -> None`
    (grava `shape.json` e lê o OpenAPI conforme R1) e `MAP_PATHS`;
  - `tests/test_api_contract_shape.py`, com `test_shape_dump_deterministic` (R3),
    `test_shape_of_merges_list_elements`, `test_shape_of_map_paths` e
    `test_scope_marks_api_py_frontend` (fixa o fato de R8);
  - `web/e2e/api-contract.spec.ts` (R6/R7).
- **Alterados:**
  - `web/e2e/fixtures.ts`: no máximo um export de helper que devolva as respostas pós-ação, sem
    mudar o comportamento;
  - `.github/workflows/eval-gates.yml`: um passo de dump no `frontend-selective`, antes do
    `test:e2e`. **[H]** Conferir se mudar workflow aciona algum gate protegido.

Exemplo de `shape.json` efêmero:

```json
{
  "seed": 7,
  "scenarios": ["new_game", "story_turn", "combat_default", "combat_cards_on", "loot_shop", "death_pending", "level_up"],
  "uncovered": [{"scenario": "estado_terminal", "reason": "sem save fixo"}],
  "paths": {
    "player_stats.vitalidade": ["number"],
    "player_stats.cards[].valid_targets": ["array", "null"],
    "combat.wounds.slots.leve": ["array"]
  }
}
```

## 4. Plano passo a passo (ao reabrir)

W1 (trava de arquivos) antes de cada etapa e W4 (um commit por mudança mecânica).

### Etapa 0 — Levantamento
1. Confirmar o gatilho de reabertura e citar o bug ou o início da SPEC-198.
2. Recitar as linhas de `api.py` e confirmar o estado da 381 (dumper e destino do teste congelado, R1).
3. Ler os builders dos candidatos de `MAP_PATHS` (R4).
4. Listar os saves e fixtures de teste que montam cada cenário de R2.

### Etapa 1 — Forma determinística (testes primeiro)
1. **Testes:** `test_shape_dump_deterministic` (vermelho até semear e injetar), os unitários de
   `shape_of` e `test_scope_marks_api_py_frontend`.
2. **Implementação:** `api_contract.py`.
3. **Verificação:** só esses testes, `-n 2` no máximo, e o determinismo rodado 3× seguidas.

### Etapa 2 — Checagem fixture ⊆ real
1. **Teste:** `api-contract.spec.ts` (`npx playwright test e2e/api-contract.spec.ts --workers=1`,
   com `RPG_API_SHAPE` apontando para um dump local).
2. Triar cada divergência. Bug real: follow-up com `ref`, sem corrigir o backend aqui. Cenário não
   coberto: exceção com motivo.
3. Prova de sensibilidade, local e não commitada: renomear `vitalidade` em `combat.enemies[]` faz R6
   falhar com o caminho certo. Registrar no hand-back.

### Etapa 3 — CI e docs
1. Passo de dump no `frontend-selective` (R5).
2. Um parágrafo em `docs/guias/TESTES.md`.

### Etapas 4+ — só se D1 = (b)/(c)
Revisar a spec antes de começar. O golden (R10) vem primeiro. Depois, um bloco por commit na ordem
`turn_outcome` → `combat_result` → `quest` → `world` → `player_stats.cards` → `combat`. (c) por último.

## 5. Critérios de aceite

- [ ] Gatilho de reabertura citado.
- [ ] R1–R9 com teste. `test_shape_dump_deterministic` verde 3× seguidas e com outro `PYTHONHASHSEED`.
- [ ] Prova de sensibilidade da Etapa 2.3 registrada.
- [ ] Nenhum arquivo de contrato versionado em (a′). `git diff main -- api.py api_models.py web/e2e/contracts evals/` vazio.
- [ ] `uv run pytest` verde (coordenador, 1×, no pouso), `npm run typecheck:e2e` verde e `frontend-selective` verde.
- [ ] Revisão `Sol` (W7) rodando de novo o determinismo e a prova de sensibilidade.
- [ ] Saves antigos: sem efeito.

## 6. Smoke test com LLM real

**(a′):** sem LLM no caminho. Smoke de amostragem:
1. No staging, pelo front, jogar 1 jogo novo, 3 turnos e 1 combate de cartas até o fim.
2. Salvar as respostas JSON em `$SCRATCH`, fora do repo e sem dados de conta.
3. Rodar `api_contract.py check --extra-payloads <dir>` e registrar os caminhos que o real
   contradisse ou que só o real confirmou.

**(b)/(c):** obrigatório. Mesmos cenários, comparando o JSON real de staging antes e depois do
deploy, e o front jogando sem erro de console.

## 7. Riscos & compatibilidade

- **Mudança silenciosa de JSON (b/c, crítico).** O `model_dump()`→`model_validate()` de
  `api.py:2208` e o `response_model` passariam a: adicionar chaves `None`; descartar extras com o
  `extra="ignore"` default; converter `int`↔`float`; reordenar chaves. Mitigação em R10/R11.
- **Flake (a′).** Uma forma não determinística quebraria todo PR de front (P0-1). R3 é bloqueante,
  e o teste não entra na suíte sem ele.
- **Churn e conflito.** Em (a′), zero arquivo versionado de contrato (R5). Em (c), inevitável: entra no D1.
- **Ponto cego de `services/*`** (R8). Aceito, ou resolvido pelo D2.
- **Acoplamento do build do front (c).** O CI já tem uv nos jobs de front (`validate.yml:54`,
  `eval-gates.yml:120`). O build local não chama Python.
- **Falsa segurança.** Ver a limitação de §1. Exceções com `kind`/`ref` obrigatórios.
- MockLLM/FallbackLLM: sem efeito. Latência na suíte: ~6 s por cenário jogado na sonda. Com estados
  injetados deve cair **[H]**.

## 8. Decisões do dono

- **D1 — Ao reabrir, qual opção?** (a′) efêmera [recomendado]; (b) tipar os blocos; (c) (b) + TS
  gerado. Recomendação: (a′). (b)/(c) só se o gatilho for a SPEC-198 ou se o bug achado for de forma
  em estado não coberto por amostragem.
- **D2 — Ponto cego de `services/*` (R8):** aceitar [recomendado, custo zero] ou pagar com um JSON
  de fixture versionado e um check no job `test`.
- **D3 — Agora:** manter ADIADA, fora da onda 375–384 [recomendado]; ou executar (a′) já.
- **D4 — Bugs da triagem:** uma spec por bug ou uma só (recomendado: uma só, se forem até 3).

## 9. Resposta à revisão (`handoffs/SPEC-385-independent-review.md`, DEFER)

| Achado | Resposta |
|---|---|
| Veredito DEFER / ponytail | **Aceito.** Status ADIADA, com gatilhos (i) e (ii) no cabeçalho. D3 recomenda não executar agora |
| P0-1 forma não determinística | **Aceito.** R2 (estados injetados por save fixo, nada jogado) e R3 (semente, ids fixos, teste de igualdade 2× + subprocesso), bloqueante |
| P1-1 OpenAPI duplicado com a 381 | **Aceito.** R1 usa fonte única (dumper da 381). O destino do teste congelado da 381 é pendência do coordenador e fica registrado nas duas specs |
| P1-2 churn de arquivo versionado | **Aceito.** R5: forma efêmera no CI (`$RUNNER_TEMP`), `skip` local, sem allowlist em arquivo (R7 a põe no spec). Em (c) o churn é inevitável e está declarado |
| P1-3 cadeia R9 e `ci_eval_scope.py:29` | **Aceito.** Virou R8: `api.py` já é frontend [F]. Ponto cego de `services/*` explícito, sob D2 |
| P2-1 cobertura de R6 | **Aceito.** Limitação ampliada em §1. R6 exige listar os objetos percorridos |
| P2-2 `combat.wounds.slots` | **Aceito.** Removido de `MAP_PATHS`. Os candidatos só entram com leitura do builder |
| P2-3 R8 [H] falso, `critical-journeys.yaml` | **Aceito.** Virou [F] com `frontend_eval_report.py:19,51,73` em R6. `critical-journeys.yaml` está corrigido como não protegido em R9 |
| P2-4 dependência da 381 | **Aceito.** Depende só da 383; com a 381, coordenação |
| P2-5 linhas | **Aceito.** Recitadas na `main` `2a6e0945` (`api.py:2093-2136, 2208, 4009, 5285, 6923, 6943`). A Etapa 0 recita de novo |
