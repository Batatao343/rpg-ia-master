# SPEC-385 — revisão independente (spec draft)

> **Veredito:** `DEFER` (com a spec reescrita nos pontos P0/P1 abaixo antes de qualquer execução; executada como está = `UNSAFE`: o teste R4 fica instável na suíte default)
> **Revisor:** Opus (spec-reviewer, independente; não escreveu a spec) · **Data:** 2026-11-03 · **Commit revisado:** `2a6e0945` (main)
> Nome do arquivo: pedido como `SPEC-385-spec-review.md`, mas esse nome reprova `tests/test_handoff_names.py`
> (padrão `SPEC-NNN[-papel]-(review|independent-review|eval-authoring|port-review).md`). Por isso usei `-independent-review`.
> O `SPEC-385-sol-review.md` fica livre para a revisão de código (REVIEW_MODEL Sol).

## Escopo

Revisão da spec `specs/SPEC-385-contrato-api-tipos.md` (status `draft`), não de código. Conferi os fatos [F]/[H]
no source. Também medi a estabilidade de `app.openapi()` e da forma real das respostas (MockLLM, `TestClient`),
com sondas em scratchpad fora do repo. Nada no repo foi alterado, exceto este arquivo.

## Fatos conferidos

| Afirmação da spec | Resultado |
|---|---|
| 16 campos `Any` (10 `dict` + 6 `list[dict]`) + 4 `dict[str,str]`; só `visual` tipado | **Confere** (`api.py:2093-2136`; as linhas estão ~4 abaixo do citado `2089-2132`). 51 `dict[str, Any]` no arquivo: confere |
| `format_response` faz `model_dump()`→`model_validate()` | **Confere** em `api.py:2208` (citado 2204) |
| `response_model=GameResponse` em 4 rotas | Confere: `api.py:4009, 5285, 6923, 6943` (as citações estão de 4 a 25 linhas fora) |
| `web/e2e/contracts/` protegido e inexistente | Confere (`evals/protected-paths.txt:13`; o diretório não existe). Obs.: `web/e2e/critical-journeys.yaml` **não** é protegido, ao contrário do que R8 dá a entender. Ser conservador ali não custa nada |
| `ci_eval_scope.py:28` marca `web/` como frontend | Confere. **Falta o fato da linha 29:** `FRONTEND_FILES = {"api.py", …}`. Mudar `api.py` **já** dispara `frontend-selective`. O argumento de R9 só vale para mudança de forma vinda de `services/*` |
| R8 [H] `frontend_eval_report.py --check` exige mapear todo spec do e2e | **Falso, resolvido.** O check só conta testes cujo título casa `^F\d\d\s` (`frontend_eval_report.py:19,51`) e `complete = set(journeys) == JOURNEY_IDS`. Um spec sem `page` e com título fora desse padrão não afeta o gate. Com isso, R8 não para a execução |
| uv no job do front (`validate.yml:54`, `eval-gates.yml:120`) | Confere. O job `test` do `validate.yml` **não** roda `test:e2e` (só `npm test`, `typecheck:e2e`, `lint`, `build`). R5 só roda em `frontend-selective`, quando o escopo for frontend |
| `fixtures.ts:12-53` `gameState`, `:90` `DeterministicBackend`, `:368-376` stream | Confere. `gameState()` só é chamado dentro de `fixtures.ts`, então a rede R5 cobre o backend falso central de verdade |
| `types.ts:1` "Espelha os DTOs" e 127 exports | Confere |
| MAP_PATHS candidato `combat.wounds.slots` | **Provável erro:** na forma real, `slots` tem chaves fixas `leve/grave/critico` (não é um mapa por id). Na sonda não apareceu nenhuma chave dinâmica (id como chave) em `/game/new` + 2 turnos |
| [H] "nenhum bug de contrato real registrado" | **Confirmado.** Grep em `CHANGELOG.md`, `handoffs/` e `git log` desde 01/09 não achou drift de chave fixture×backend visto em staging. O caso mais próximo é `SPEC-323` P1-1: um teste unitário usava uma descrição de beat que a API redige como "Etapa N". É divergência de **valor** (string × string), e a opção (a) **não** pegaria |

## Sondas de estabilidade

- `app.openapi()` com `sort_keys=True, indent=2`, gerado 2× em processos separados (hash seed aleatório):
  **byte-igual** (104 466 B). As rotas condicionais por env ficam fora do schema (`/docs` e `/metrics` com
  `include_in_schema=False`, cron router fora). A estabilidade Windows×Linux não foi testada **[H]**.
- **Forma real (R2/R3)**, com `/game/new` (Sangromante, Nova Arcádia) + 2× `/game/action` e MockLLM, rodada 5×:
  **4 formas distintas** (375, 395, 400, 400 e 415 caminhos; 87 dos 436 caminhos não aparecem em todas as
  rodadas). O que varia: o combate às vezes não começa (`combat.enemies[]`, `combat.scene.*`), às vezes
  termina (`combat_result.*`, `combat.encounter_view.participants[]`), e `quest.side[]` e
  `chronicle[].entries[]` às vezes vêm vazios. A causa é RNG sem semente e ids/uuid que semeiam o encadeamento.
  Cada rodada levou ~6 s, então o orçamento de < 20 s de R4 é plausível.

## Achados

| ID | Sev. | Onde (spec) | Problema | Correção |
|---|---|---|---|---|
| P0-1 | P0 | R2, R4 | O snapshot de forma gerado com MockLLM **não é determinístico** (sonda: 4 formas em 5 rodadas). `test_shape_snapshot_fresh` na suíte default viraria flake em todo PR, inclusive nos que não tocam a API. Isso quebra a regra "nada quebra" | Exigir semente explícita (fixar `random`/RNG do motor e `uuid`/`game_id` por cenário), cenários montados por **estado injetado** (save fixo carregado), não por "jogar até cair em combate", e um teste que rode o dump 2× no mesmo processo e afirme igualdade. Sem isso, R4 não pode estar na suíte default |
| P1-1 | P1 | R1 × SPEC-381 R6/§3.6 | A SPEC-381 já cria `scripts/dev/api_surface_dump.py`, `docs/spec381/before/openapi.json` (`sort_keys=False, indent=1`) e `tests/test_spec381_api_surface.py` na suíte default. R1 cria um **segundo** snapshot de OpenAPI, em outro formato e em `web/`. Toda mudança de rota teria de regenerar dois arquivos. A 381 também não diz se o teste dela é aposentado no pouso | Uma fonte só: a 385 reaproveita o dumper da 381 e substitui o teste congelado dela por um snapshot vivo (ou vice-versa). Registrar isso nas duas specs |
| P1-2 | P1 | §7 "Atrito", R1/R4 | O churn está subestimado. Nos últimos 30 dias, `web/src/types.ts` mudou em 49 commits e `fixtures.ts` em 19, e ~16 commits de `api.py` mexeram em rota ou modelo. Com 11 branches `spec-*` e 19 worktrees abertos, `game_response.shape.json` vira ponto quente de conflito. Regenerar exige Python + MockLLM em qualquer sessão que mude um bloco de `format_response`, inclusive vindo de `services/*` | Não versionar a forma. Gerar a forma **efêmera** no CI: no `frontend-selective`, um passo `uv run python scripts/dev/api_contract.py dump --out "$RUNNER_TEMP/contract"` antes do `test:e2e`, com o caminho passado ao spec por env. Localmente, o spec faz `skip` se o arquivo não existir. Fica só o invariante fixture ⊆ real, sem nenhum arquivo para regenerar nem conflito de merge |
| P1-3 | P1 | R9 | O premissa "mudança só de backend faz R4 falhar, e regerar marca escopo frontend" depende do snapshot versionado (P1-2). E `api.py` já está em `FRONTEND_FILES` (`ci_eval_scope.py:29`). A cadeia de R9 é frágil: uma mudança em `services/*` só dispara R5 indiretamente | Com a forma efêmera, a mudança em `services/*` que altera a forma não é pega fora do escopo frontend. Ou se aceita isso explicitamente (o drift aparece no próximo PR de front), ou o passo de dump+check (só Python, contra um JSON de fixture exportado) entra no job `test` |
| P2-1 | P2 | R5 (ii) | "Tipo compatível" com `number` não distingue int/float, e uma lista vazia no fixture (`enemies: []`, `cooldowns: {}`) não verifica nada abaixo dela. A cobertura real se limita ao `gameState()` base mais as respostas pós-ação do backend falso. Os overrides por teste (ex.: `card-shop-357.spec.ts` monta `player_stats`) ficam de fora | Declarar isso na limitação honesta de §1 e listar quais objetos do backend falso entram (pelo nome do método/helper) |
| P2-2 | P2 | R3 MAP_PATHS | `combat.wounds.slots` não é mapa dinâmico (as chaves são fixas). Os demais candidatos não apareceram na sonda | Confirmar cada candidato lendo o builder no source, não por amostra |
| P2-3 | P2 | §2 R6, R8 | `critical-journeys.yaml` não é protegido, e o [H] de R8 já está resolvido (ver tabela) | Trocar o [H] por [F] com a citação `frontend_eval_report.py:19,51,73` |
| P2-4 | P2 | Cabeçalho, deps | A dependência da 381 não é necessária para a (a), que não toca `api.py`; ela só define onde o `GameResponse` mora. A dependência da 383 **é** necessária, porque `fixtures.ts` é o arquivo que a 383 reorganiza | Depender só da 383. Contra a 381, apenas coordenar o dumper (P1-1) |
| P2-5 | P2 | Linhas citadas | As referências a `api.py` estão 4 a 25 linhas fora (a `main` andou) | Recitar na Etapa 0 (a própria spec já prevê isso) |

## Ponytail: vale existir agora?

Não. Não há nenhum bug de drift de chave registrado em staging. O único caso parecido (SPEC-323 P1-1) é de
valor, e (a) não o pegaria. O gatilho declarado para (b)/(c), o segundo cliente da SPEC-198 Android, está
bloqueado no dono (Play Console). A (a) como escrita custa 1–2 dias mais um imposto contínuo sobre todas as
sessões (P1-2) e traz um flake (P0-1). Recomendo manter a spec em `draft`, fora da onda (D2 = fila), com dois
gatilhos de reabertura: (i) o primeiro bug de contrato visto em staging ou em smoke real; (ii) o início da
SPEC-198. Se o dono quiser a rede antes disso, a versão segura é a (a) **efêmera** de P1-2 (sem arquivo
versionado, com semente fixa de P0-1). Ela custa ~1 dia, e o único arquivo quente que toca é `fixtures.ts`
(export de helper), depois da 383. (b)/(c) seguem condicionais, e a análise de risco de §7 para elas está correta.

## Correções aplicadas

Nenhuma (revisão de spec; o autor ajusta).

## Pendências

- Autor da spec: P0-1, P1-1 a P1-3 antes de `approved`; os P2 podem entrar no mesmo ajuste.
- Coordenador: decidir se o teste congelado da SPEC-381 (`test_spec381_api_surface.py`) é aposentado no pouso
  dela. Isso afeta a 385 e qualquer PR que mexa em rota.

## Comandos rodados

```text
grep/sed em api.py, web/e2e/fixtures.ts, web/src/types.ts, scripts/ci_eval_scope.py, scripts/frontend_eval_report.py, .github/workflows/{validate,eval-gates}.yml → fatos da tabela
uv run --frozen python -c "api.app.openapi() → json sort_keys" 2× (scratchpad) → byte-igual, 104466 B
uv run --frozen python scratchpad/p385/shape_probe.py 5× (/game/new + 2 ações, MockLLM, saves em tmp) → 4 formas distintas, ~6 s cada
grep CHANGELOG.md/handoffs + git log --grep (field|payload|shape|contract) → nenhum drift de chave em staging; SPEC-323 P1-1 (valor)
git log --since=2026-10-04 -- web/src/types.ts | web/e2e/fixtures.ts | api.py → 49 | 19 | 138 commits
```
