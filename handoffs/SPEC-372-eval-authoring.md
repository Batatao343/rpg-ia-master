# SPEC-372 — autoria de eval (eval-authoring)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (avaliador congelado; publicação depende do environment `eval-governance`)
> **Autor de eval:** Claude Opus 5.5 (papel autor de eval; não executa o produto desta spec) · **Data:** 2026-11-03 · **Base:** `67d38084` (main) + `221b931c` (spec approved)
> **EVAL_AUTHORING_REQUIRED:** `true`. O commit mexe em `evals/protected-paths.txt` (que também é protegido), então o push dispara o job `protected-evaluator-review` do `eval-gates` e precisa de aprovação do environment `eval-governance`. Comando: `/eval-publish` (`bash scripts/dev/py.sh scripts/dev/eval_publish.py --base origin/main`), junto com as outras autorias de eval da onda.

## Escopo

Só a Etapa 1 da SPEC-372 (R15, D10 = sim). Arquivos:

- `scripts/fauna/eval_tramas.py`: avaliador T1–T8 (novo, protegido);
- `tests/test_spec372_eval.py`: limiares literais + testes do próprio avaliador (novo, protegido);
- `evals/protected-paths.txt`: as duas linhas acima.

Nenhum código de produto. O relatório `docs/spec372/eval-tramas-nova_arcadia.md` é gerado pelo executor na Etapa 6 (`bash scripts/dev/py.sh scripts/fauna/eval_tramas.py`).

## Como o avaliador evita usar o produto como oráculo

- O estágio é **literal**. `stage_cases()` monta 16 estados sintéticos (um por regra da R1, negativos, combinação, o caso R2 de quest `failed` e o estado `maximo`), cada um com o estágio esperado escrito à mão. `max_stages()` é literal por construção: a trama com `secret_ids` fica `revelada`, a sem `secret_ids` fica `investigada`. O teste `test_avaliador_estagio_maximo_literal` fixa esse resultado para as 7 tramas de NA.
- T1–T6 entregam ao motor o mapa de estágios literal (`trama_stages=`), não o que o `plot_stage` calcula. O `day_hook` deriva o estágio de `ctx.state`, e esse estado é o mesmo do T8: vazio quer dizer todas `dormente`, e `maximo` quer dizer `max_stages()`.
- Os tokens proibidos (T5) saem dos dados: `plot_threads.json` (`secret_ids`, `core`), `data/graph/entities.json` (nome + aliases) e `SECRET_SIGNATURES`. O lint E22 do produto não entra.
- A normalização de `tramas` (D1/D2: string solta vale `desde: tocada`) é do próprio avaliador e lê `fauna.json` direto.
- Known-good e known-bad do avaliador, sem produto: stubs de `plot_stage` por tabela (devem dar 0 erro), sempre `dormente` (devem errar os casos positivos) e um stub que muta o estado (deve ser pego). Rodei também um produto falso no scratchpad, fora do repo: o correto deu T1–T5 e T8 verdes; sem portão nem puxão, T1, T2 e T3 falharam (fatia 0,08, 17 presenças, razão 1,0).

## Contrato que o executor precisa satisfazer

1. `services.plot_threads.plot_stage(state, thread_id) -> str` e `plot_stages(state, region_id) -> Mapping[str, str]`, com **todas** as tramas da região como chave. São puras (o estado não pode mudar; T8 compara o JSON antes e depois), e trama inexistente devolve `dormente`.
2. Leitura dos sinais exatamente como a R1, nas formas que o T8 usa:
   - NPC: `state["npcs"][<anchor_npc_id>]` com `known_by_player: True` **ou** `knowledge_source == "met"`; `"mentioned"` com `known_by_player: False` não conta.
   - Rumor: `world_sim.rumors[]` com `seed_id`, `perceived_day > 0` e `resolution == "confirmado"`.
   - Quest: `{"world_kind": "investigar_rumor", "status": "active"|"completed", "lore_anchor": {"type": "rumor", "id": <rumor_id>}}`, com `rumor_id` → `seed_id` pela linha de `world_sim.rumors`. `failed` não conta (R2).
   - Fio de abertura: `campaign_plan.opening_thread.thread_refs` com id de **porta** (`<thread>__pN`) ou de trama.
   - Segredo: `event_log` `{"type": "secret_revealed", "target_id": X}` via `accepted_secret_ids`. Vale tanto o id literal (`"corpos"`) quanto a entidade mapeada (`"npc_valerius"` → `pacto_valerius`). Outro `type` não revela.
3. `world_utils.encounter_distribution(..., trama_stages=None)` e `world_utils.check_encounter(..., trama_stages=None)`: kwargs keyword que chegam a `EcoCtx.trama_stages`. O chamador de jogo (`agents/storyteller.py`) passa `plot_stages(state, regiao)`. Com a flag `off`, o produto ignora o kwarg: o modo `off` do avaliador passa o mapa `maximo` e espera o comportamento de hoje.
4. `services.fauna.day_hook(ctx)` deriva o estágio de `ctx.state` (R3). Presença `origem == "dia"` de criatura ligada e atingida nasce com `locais ⊆ ⋃ locations` das tramas atingidas e com `trama_id` entre elas. Com a flag `off`, nenhuma presença tem a chave `trama_id`.
5. Flag `RPG_FAUNA_TRAMAS` (`off`|`on`). O avaliador liga `RPG_FAUNA`, `RPG_FAUNA_SINAIS`, `RPG_PLOT_THREADS` e `RPG_WORLD_ENGINE` em todos os modos e só varia esta.
6. Metas (limiares em `test_limiares_congelados`):
   - T1: fatia 0 em todo local × período de NA com o mapa todo `dormente` e com o mapa "um abaixo do `desde`"; 0 presença, 0 `track` e 0 escolha de ligada no modo `dormente`.
   - T2: razão on/off da fatia nos `locations` das tramas atingidas ≥ 1,5 no mapa `maximo`, para **toda** ligada; nenhuma ligada inalcançável. Exemplo de inalcançável: `desde: revelada` numa trama sem `secret_ids`, que nunca passa de `investigada`.
   - T3: 100 % das presenças `dia` de ligada atingida dentro dos locais e com `trama_id`; n > 0.
   - T4: gatilhos iguais nos 3 modos; Δ de combates de fauna por 100 ações entre −10 % e +5 % para `dormente` e para `maximo`.
   - T5: 0 token de segredo ou de núcleo, tanto nos sinais de ligada em `fauna.json` quanto em todo texto da simulação atribuído a uma ligada.
   - T6: `render` byte-idêntico em duas execuções.
   - T7: o relatório da 360 com `RPG_FAUNA_TRAMAS=off` e `RPG_PLOT_THREADS=on` é idêntico a `docs/spec360/eval-nova_arcadia.md`. Baseline de hoje: sha256 `8005b2534e8720cb32c83d849848f344b2b89b75063b44e2bcb294dd4f67b8d4`, que bate com uma execução na base. O revisor Sol confere que esse arquivo não mudou na branch.

## Estado na entrega (antes do produto)

`tests/test_spec372_eval.py`: 9 passed (limiares, 7 testes do avaliador e T7), 3 xfailed strict (T1–T3, "sem ligação autorada"), 2 failed (T6 e T8) e 2 errors (T4 e T5). Os vermelhos são esperados: é `RuntimeError: contrato SPEC-372 ausente`, com a lista do que falta. T8 fica verde na Etapa 2, e T4–T6 na Etapa 5. T1–T3 saem do xfail sozinhos quando `fauna.json` tiver `tramas` (Etapa 4). Se continuarem verdes sem ligação, é XPASS strict e o teste falha.

## Pendências

- **Registro da flag.** `tests/test_flag_registry.py::test_repo_registry_is_complete` fica vermelho até a Etapa 5 registrar `RPG_FAUNA_TRAMAS` em `config/flags.yaml`, porque o avaliador já cita a flag. O registro é código de produto (R12) e fica com o executor.
- **Quest de porta.** O critério `quest_hint` da R1 fica fora do T8: nenhuma porta de NA tem `quest_hint` de `investigar_rumor`, e a âncora de `entregar_material` não tem forma definida na spec. A cobertura fica para o teste unitário do executor.
- **SPEC-370 antes da 372.** Se a 370 pousar antes e mudar a fauna de NA, ela regenera `docs/spec360/eval-nova_arcadia.md` e o T7 continua valendo contra o arquivo novo. O sha acima fica só como registro.
- **Publicação.** EVAL_AUTHORING_REQUIRED. O coordenador faz o push e roda `/eval-publish`, e o dono aprova o environment `eval-governance`.

## Comandos rodados

```text
git rebase main → ok (spec-372 sobre 67d38084)
bash scripts/dev/py.sh -m ruff format/check scripts/fauna/eval_tramas.py tests/test_spec372_eval.py → limpo
bash scripts/dev/py.sh -m pytest tests/test_spec372_eval.py -q -p no:randomly → 9 passed, 3 xfailed, 2 failed, 2 errors (esperado; contrato ausente)
produto falso (scratchpad, fora do repo) run(20,30): correto → T1–T5/T8 ok; sem portão → T1/T2/T3 FALHOU
bash scripts/dev/py.sh scripts/check_handoff_names.py → ok
```

## Correção do T7 após o rebase sobre a SPEC-370 (2026-11-04)

**Motivo.** A SPEC-370 passou a gerar o baseline `docs/spec360/eval-nova_arcadia.md` pelo `main()` do avaliador da 360/370 com `--regiao nova_arcadia`, que acrescenta a seção "SPEC-370 — por região" no fim. O T7 ainda montava o texto com `ev.render(ev.run())`, o caminho só da 360, e por isso faltavam as linhas finais no diff. O relatório da 360 em si não mudou.

**Correção.** `baseline_360_identical()` agora chama `ev.main(["--regiao", "nova_arcadia", "--out", <tmp>])`, o mesmo caminho que gera o baseline. A chamada roda com `RPG_FAUNA_TRAMAS=off` e `RPG_PLOT_THREADS=on`, e o **arquivo inteiro** é comparado byte a byte com o baseline. Não houve afrouxamento: nenhum limiar, cenário ou medida mudou. A comparação ficou mais estrita, porque passa a cobrir também a seção da 370. O código de saída do `main()` vai no resultado só como informação.

**Baseline novo.** sha256 `dcb03ea52e0febb623b4314121717cd3b381be36fa7899217373d6bda4fca02e`. O revisor Sol confere que esse arquivo não muda na branch.

```text
bash scripts/dev/py.sh -m pytest tests/test_spec372_eval.py -q -p no:randomly → 16 passed (T1–T8 verdes no tip 8eabcb43 + esta correção)
```
