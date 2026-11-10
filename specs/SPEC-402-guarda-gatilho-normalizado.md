# SPEC-402 — guarda-gatilho-normalizado

> **Status:** `done` (10/11, coordenador; revisão Sol APPROVED `b3e6a34c`; suíte completa no pouso) — antes: `approved` (10/11, coordenador com delegação do dono: "confio em vc nas decisoes" / "aprovar tudo conforme suas recomendações"; D1–D3 nos defaults; executar só depois da 401 pousar, com executor no papel de autor de eval)
> **Criada:** 2026-11-09 · **Atualizada:** 2026-11-10
> **Depende de:** SPEC-400 (`done`), SPEC-395, SPEC-373
> **Desbloqueia:** nada (endurece guarda; origem N-1 de `handoffs/SPEC-400-sol-review.md:29`)
> **Risco:** `médio`. Só testes, nenhum diff de produto, e a mudança só aperta a guarda. Não é `baixo` porque mexe no oráculo R3 da 395/400, que segura a regra "absoluta não foge" (combate). Revisor Sonnet, que não seja o autor.
> **Evidência:** a fixture com gatilho `"Muito Ferído "` passa na guarda atual (escapa) e reprova na nova; o bestiário curado continua verde.
> **EVAL_AUTHORING_REQUIRED:** `true`. É o oráculo R3 da 395/400. O arquivo não está em `evals/protected-paths.txt`, mas o assert saiu do autor de eval (N-2 da revisão). Quem otimiza o produto não mexe aqui.

## 1. Contexto & Objetivo

`normalize_runtime_profile` (`services/tactical_profile.py:548`) normaliza o gatilho com `_normalize_archetype` (`:513-516`: NFKD → ASCII → `lower().strip()` → `-`/espaço viram `_`) antes de olhar a tabela (`:565-566`). O assert R3 (`tests/test_tactical_archetypes_runtime.py:540-541`) consulta `_ENEMY_ARCHETYPE_ACTIONS` com o gatilho **cru**. Com `"Muito Ferido"` num `bruto`, o produto lê `muito_ferido` → `flee` e troca para a chave de `sempre`. O assert lê `actions.get("Muito Ferido")`, cai em `sempre` = `attack`, não vê fuga e **pula a exigência sem avisar**. Hoje passa só porque os gatilhos curados já vêm canônicos.

Verificação de `chave_absoluta_esperada` (`tests/test_spec373_montagem.py:44-53`): o helper **não lê gatilho**. Ele exige a chave de `sempre` em toda `absoluta` de `fichas`. Lê `arquetipo` cru (`:49`, `:67`), mas um arquétipo fora do formato canônico dá `None` → reprova (`:68-69`). Isso falha fechado: no pior caso é um falso vermelho, nunca um escape. O R3 também lê `arquetipo` cru (`:532`, KeyError = falha fechado), e o `:518-520` já exige grafia canônica no dado.

Objetivo: o R3 normaliza o gatilho igual ao produto, sem chamar `normalize_runtime_profile` (D2 da SPEC-400).

## 2. Requisitos

- **R1** — Extrair o miolo do R3 para um helper puro de teste, `erros_absoluta(arquetipo, priorities) -> list[str]`, em `tests/test_tactical_archetypes_runtime.py`. O gatilho é normalizado com `tp._normalize_archetype(priority.get("trigger") or "sempre")`. O teste do bestiário passa a fazer `assert erros_absoluta(...) == [], enemy_id`.
- **R2** — Teste que falha antes (`test_erros_absoluta_normaliza_gatilho`): `bruto` com uma prioridade `absoluta`, gatilho `"Muito Ferído "` e `action_key="flank"` → devolve 1 erro. Com a lógica crua, o mesmo caso devolve `[]` (registrar esse vermelho no commit/hand-back).
- **R3** — Mutações em `test_erros_absoluta_known_good_e_bad`. Known-good: `"muito_ferido"`/`attack`, `"Muito-Ferido"`/`attack`, `flexivel` com `flee`, e `absoluta` com gatilho que leva a não-fuga (`guardiao`, `"Muito Ferido"`, `protect`). Known-bad: `"MUITO FERIDO"`/`flank`, `absoluta`/`flee`, `absoluta`/`surrender`, e `conjurador` `"Cercado"`/`attack` (o esperado é `control`).
- **R4** — Pino da normalização (`test_normalizacao_de_gatilho_pinada`): `tp._normalize_archetype` aplicada a `"Muito Ferído "`, `"muito-ferido"` e `"MUITO_FERIDO"` dá `"muito_ferido"`. Isso pega a deriva da função compartilhada (D1).
- **R5** — `ficha_vs_base`/`chave_absoluta_esperada` sem mudança (D3), e o snapshot da 373 continua batendo.

### Fora de escopo

Produto (`services/`), `data/bestiary.json`, `_ajustes.yaml`, `evals/`, normalizar `arquetipo` nos oráculos (D3), validador de conteúdo que rejeite gatilho não canônico (D2).

## 3. Plano (testes primeiro)

1. **Vermelho:** escrever R2 contra um `erros_absoluta` que copia a lógica crua atual → `1 != 0` (falha). Guardar a saída.
2. **Verde:** trocar para `_normalize_archetype` (R1), adicionar R3/R4 e religar o teste do bestiário ao helper.
3. **Verificação:** `bash scripts/dev/pt.sh tests/test_tactical_archetypes_runtime.py tests/test_spec373_montagem.py tests/test_spec373_artefatos.py tests/test_size_budget.py` (`-n 2`) verde, mais `ruff check` nos 2 arquivos. Sem §6 (não há LLM nem infra).

## 4. Critérios de aceite

- [x] Vermelho de R2 registrado com a lógica crua; verde com a normalizada.
- [x] R3: todos os known-good dão `[]` e todos os known-bad dão erro não vazio.
- [x] R4 pina a normalização; o bestiário curado continua verde.
- [x] `git diff main -- services/ data/ evals/ tests/test_spec373_montagem.py` vazio.
- [x] Nenhuma chamada a `normalize_runtime_profile` dentro de `erros_absoluta`.
- [x] Suíte completa verde no pouso (coordenador); revisão Sonnet independente.

## 5. Decisões abertas (com default)

- **D1 — Circularidade de `_normalize_archetype`.** (**Default: reutilizar + pino R4.**) Não é circular no sentido da D2/400: a função testada é a regra "absoluta → `sempre`", e `_normalize_archetype` é só a canonização da chave. O risco residual: se ela mudar, produto e guarda mudam juntos. O pino R4 cobre isso. Alternativa: uma cópia local da normalização no teste, que fica independente mas pode divergir do produto em silêncio.
- **D2 — Validador de conteúdo** que reprove gatilho não canônico no `bestiary.json`. (**Default: não**; se quiser, vira spec de conteúdo própria.)
- **D3 — Normalizar `arquetipo`** em `chave_absoluta_esperada` e no R3. (**Default: não**: hoje falha fechado, e o `:518` já exige grafia canônica.) Mexer na guarda da 373 sem escape real só aumenta a superfície.

## 6. Execução (10/11, executor no papel de autor de eval)

- Vermelho de R2 com a lógica crua (`str(trigger or "sempre")`): `test_erros_absoluta_normaliza_gatilho` falhou com `assert 0 == 1` (`erros_absoluta('bruto', [{'trigger': 'Muito Ferído ', 'action_key': 'flank', ...}]) == []`); o known-bad `MUITO FERIDO`/`flank` também escapou. 2 failed, 3 passed.
- Verde com `tp._normalize_archetype`: `test_tactical_archetypes_runtime`, `test_spec373_montagem`, `test_spec373_artefatos`, `test_size_budget` = 89 passed (`-n 2`); ruff format/check limpos.
- `git diff main -- services/ data/ evals/ tests/test_spec373_montagem.py` vazio. Sem desvios. Suíte completa e revisão Sonnet: coordenador.
