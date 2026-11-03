# SPEC-374 — revisão sol (review)

> Nome do arquivo: `handoffs/SPEC-374-sol-review.md` (lint `scripts/check_handoff_names.py`).
> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (papel Sol, revisão técnica independente; não escreveu o produto) · **Data:** 2026-11-03 · **Commit revisado:** `534a642f`

## Escopo

Branch `spec-374`, `git diff main...HEAD` (50 arquivos). Produto: `58a3843f`, `a05df69c`, `0c899fde`,
`35bd9be5`, `c5806b48`, `534a642f`. Avaliador `d3019102` (outro autor) conferido só quanto à integridade
(R1/R2), não reavaliado. Lido: `services/creature_gen.py` (schema, `_moldar`, `eixos_da_linha`,
`ficha_runtime`, `normalizar_forma`, `reparar_eixos`, `gerar_nova`, `_invocar`, `_resposta_para_ficha`),
`services/creature_gen_jobs.py`, `workers/drain.py` + `workers/job_worker.py` + `defer` das duas filas,
`services/cron_internal.py` (orçamento), `rag.py` (`--only`), `services/content_validator.py`
(`validate_curated_secrets`), `data/graph/entities{,_extra}.json` (movimento dos 36 `npc_mv_`),
`mock_llm.py`, `config/flags.yaml`, `tests/test_spec361_gate.py` (diff), testes `test_spec374_*`,
registros `docs/spec374/eval-medido-{1,2}.json`. Fora: texto do prompt (parecer separado em
`handoffs/SPEC-374-astra-review.md`), rodadas reais (não rodadas), smoke §6.

## O que está certo (conferido no source)

- **R1/R2 (integridade):** `git log main..HEAD -- <avaliador, testes do eval, fixtures, eval_geracao.py, protected-paths>`
  mostra só `d3019102`. sha256 do set da 361 = `baf38310…db6dbc`; do set de ajuste = `13ec924e…a3df`
  (igual à §9). As duas rodadas medidas gravam `commit: c5806b488d1d`, `real: true`, `mock: false`,
  `pedidos_sha256` do set da 361; entre `c5806b48` e `534a642f` só mudaram docs/spec.
- **`lint_primeira` antes de qualquer reparo:** `creature_gen.py:1723-1724` grava `not issues` logo depois
  do 1º `lint(ficha)`; `reparar_padrao` (`:1726`) e `reparar_eixos` (`:1731`) vêm depois; PRAZO/SCHEMA na
  1ª tentativa gravam `False` (`:1704-1715`). O que roda antes do lint (`normalizar_forma` + linha→eixos)
  é o que a D3 manda contar. Travado por `test_reparo_eixos_nao_conta_lint_primeira` e
  `test_lint_primeira_conta_linha_e_forma`.
- **Rodada com fallback para o Groq contando no `lint_primeira`:** legítimo. O produto em jogo é o
  `RoutedLLM` com fallback; o protocolo R6 exige DeepSeek **primário** em `ROUTES` (cumprido), não
  "só DeepSeek". A ficha `zhur_colmeia_nova` (rodada 2, `provider: groq`, 20,0 s) passou na 1ª. E o
  critério sobrevive mesmo contando-a como falha: 9 + 7 = 16/22, piso 7/11. Registrado na §9.
- **Guard de structured output:** `_invocar` (`:1540`) só deixa passar `FichaCriaturaGerada`/`CorrecaoFicha`;
  as classes novas são subclasses (`FichaCriaturaGeradaEixosLivres(FichaCriaturaGerada)`,
  `CorrecaoFichaEixosLivres` com `__base__=CorrecaoFicha`), então o `isinstance` cobre as quatro.
  `_resposta_para_ficha` (`:1741-1756`) escolhe a classe da mescla pela presença de `plano_corporal` e
  devolve `None` em `ValueError`. `test_guard_fallback` cobre o `AIMessage`.
- **Valor do LLM validado:** `linha_eixos` passa por `_linha` (fora de 1..8 ou ilegível → 1) no
  `model_validator(mode="before")` e por `eixos_da_linha` (`n > len(livres)` → linha 1). Os seis eixos do
  template saem do Python. `nums == ["linha_eixos"]` é índice, não valor de jogo.
- **`JobDeferred` não gasta tentativa:** Postgres `defer` = `attempts=greatest(attempts-1,0)` +
  `available_at=now()+delay` (`infrastructure/postgres_jobs.py:285-289`), e o `lease` faz `attempts+1`
  (`:169`, `:197`); a soma é zero. Inline: `attempt-1` (`local_adapters.py:506`). O teste da fila Postgres
  é só por `inspect.getsource` (substring do SQL): aceitável como trava, porque o contrato é o par
  lease(+1)/defer(−1) e não há fake de Postgres no repo; o fluxo completo foi provado na `InlineJobQueue`
  (`test_adiado_nao_vira_dead`, 3 adiamentos com `max_attempts=2`, depois `succeeded`).
- **contextvar da janela:** `job_window_scope` só em volta de `worker.run_once` (`drain.py:74-75`); o
  handler roda síncrono na mesma thread (`job_worker.py:70`), então o valor chega; fora do dreno é `None`.
  `MIN_JOB_WINDOW_S`/`SAFETY_MARGIN_S` intactos (`test_outros_jobs_janela_inalterada`).
- **Flag:** `RPG_CREATURE_GEN_MIN_WINDOW_S` em `config/flags.yaml:922-926` (`kind: ops`, default `"12"`);
  `test_flag_registry.py` verde.
- **`rag.py --only`:** lint roda nos três modos antes de ingerir; `rules` não importa `ingest_codex`; o
  backoff da 356 fica no `__main__` (vale para os três). Teste verde.
- **Migrate seguro:** `test_migrate_nao_apaga_curados` e `test_migrate_idempotente` rodam o `main()` do
  migrate numa cópia (`monkeypatch.chdir(tmp_path)`); os 17 segredos têm `curated: true`;
  `validate_curated_secrets` está em `validate_all` e dá ERRO; `validate_content.py`: 0 ERRO.
  Runtime não perde os `npc_mv_`: `graph_resolver` (`:48-49`) une `entities.json` ∪ `entities_extra.json`,
  e `entity_identity`/`npc.py` resolvem por ele; os validadores de alias/visibilidade/plot usam
  `_merged_entities`.
- **`legacy`:** nada do caminho legacy chama o código novo; `test_spec361_*` verdes.
- **Segredo em log:** nenhum. `prazo_na_janela` loga só `restante_s`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `tests/test_spec300_values.py:82-85`; `scripts/gen_world_living_npcs.py:314-343`; `data/graph/entities.json` | **Regressão na suíte.** Mover os 36 `npc_mv_*` para `entities_extra.json` quebra `test_hook_mundo_vivo_em_entities` (`assert len(mv) == 36` → `0 == 36`; rodado nesta revisão). E o gerador `gen_world_living_npcs.py` faz o contrário de propósito: escreve os `npc_mv_` em `entities.json` e dá `extra.pop(npc_id)` (comentário em `:340-342`: "o Codex e os contratos legados exigem entidades autorais no grafo canônico", de `ff018c26`). Rodar o gerador de novo desfaz o R16; rodar o migrate depois apaga os ids do canônico outra vez. Dois writers persistentes com donos opostos para os mesmos ids. A §9 não registra o desvio, e a pergunta "quem lia `entities.json` perdeu os ids?" tem resposta: este teste e o gerador. | Escolher um dono e registrar na spec. Recomendado (segue o R16): `gen_world_living_npcs.py` passa a escrever em `entities_extra.json` (sem o `pop` e com o comentário atualizado) e `test_hook_mundo_vivo_em_entities` passa a ler a união `entities.json ∪ entities_extra.json`, mantendo o `== 36` e a checagem do gancho. É mudança de contrato: registrar como desvio na §9 (não é expected de eval). Acrescentar um teste de round-trip: gerador → migrate na cópia → os 36 ids continuam na união e nenhum aparece nos dois arquivos. De quebra, `content_validator.py:1716` (`faction_membership`) lê só `entities.json` para `npc_ids`; hoje não há `npc_mv_` em `faction_membership.json`, mas trocar por `_merged_entities(GRAPH_DIR)` evita o mesmo buraco amanhã. |
| P1-2 | P1 | `services/creature_gen_jobs.py:135-159`; `workers/drain.py:71`; `services/cron_internal.py:59-67`; spec §6.6 | **O adiamento por janela curta não acontece com os defaults, e o corte do prazo troca um caso recuperável por fallback permanente.** O dreno só começa job com `stop_at − clock ≥ 15 s` e `stop_at` já desconta os 3 s de margem; o handler chama `prazo_na_janela()` logo no início. Então `restante` chega ≥ ~15 s e o limiar default de 12 s nunca dispara: `JobDeferred("janela_curta")` é código morto em produção (os testes só o exercitam com `min_job_window_s=0` ou janela forjada). O que acontece de fato é `prazo = min(30, restante − 3)`, ou seja, 12 a 30 s. O p95 medido do job é 17,1 s (rodada 2) e o da 361 foi 19,1 s: perto do fim do dreno a geração estoura o prazo curto, vira `fallback`, e o docstring do módulo diz que fallback não tem nova tentativa (dedupe permanente, `SPEC-361:751`). O smoke §6.6 como escrito também falha: `RPG_CRON_BUDGET_SECONDS=20` → `stop_at` = 17 s → o job roda com prazo de 14 s em vez de sair `deferred`. | Adiar sempre que a janela não comporta o prazo cheio: `if restante − FOLGA_JANELA_S < cg.prazo_s(): raise JobDeferred("janela_curta", 60)`. Equivale a default `RPG_CREATURE_GEN_MIN_WINDOW_S = prazo_s() + 3` (33 s), mantendo a env para baixar. Com isso o `min(...)` fica só como cinto de segurança. A criatura não tem pressa (a substituta já está em jogo), e o adiamento não gasta tentativa. Atualizar a flag em `config/flags.yaml`, a §8/R14 da spec (desvio do default 12 s) e um teste que use o `drain_jobs` real com os defaults (`min_job_window_s=15`, margem 3) e orçamento de 20 s → `deferred == 1`, `processed` sem chamada ao LLM. Assim o §6.6 passa como está. |
| P2-1 | P2 | `tests/test_spec361_gate.py` (diff) | A §9 diz "entrada dos testes, não expected". Não é só entrada: mudaram asserções (`"U2" in prompts[1] and "mon_saltador_de_palafita"` → `"R20" in prompts[1]`; `nums == []` → `["linha_eixos"]`; a correção de `test_retry_e_correcao_curta` deixou de provar a troca de eixos; `test_schema_enum_quase_certo` trocou `escala` por `estilo_ataque`; o "enum fechado" trocou `material` por `familia`). **Não enfraquece o que a 361 travava no caminho novo:** com linha fechada, U2/U3 na 1ª tentativa deixa de existir por desenho, e os casos equivalentes estão em `test_spec374_eixos.py` (`test_regiao_saturada_*`, `test_correcao_recebe_linhas`, `test_reparo_eixos_troca_linha`). Ficou um buraco pequeno: o enum quase certo e o enum fechado **dos seis eixos** só existem no schema da região saturada e nenhum teste os exercita lá. | Corrigir a frase da §9 ("entrada e asserções do caminho `on`, cujo schema mudou; legacy intocado"). Acrescentar em `test_spec374_eixos.py` um caso `FichaCriaturaGeradaEixosLivres(escala="Pequena")` → `"pequena"` e `material="aco_inox"` → `ValueError`. |
| P2-2 | P2 | `services/creature_gen.py:1585-1590` | `_limpar_forma` tira aspas das pontas quando o 1º e o último caractere são aspas iguais, sem conferir se elas embrulham o campo inteiro: `'"Abre" e depois "fecha"'` vira `'Abre" e depois "fecha'` (conferido). Para uma função que promete "só forma", isso estraga texto. Probabilidade baixa. | Só tirar quando não houver outra aspa do mesmo tipo no miolo (`t[0] not in t[1:-1]`). Teste com o caso acima. |
| P2-3 | P2 | `services/creature_gen.py:1715-1720` | `normalizar_forma(..., nome=gen.nome)` e `id_nova(gen.nome, ...)` usam o nome **antes** da limpeza, e a ficha grava o nome limpo. Se o nome vier com espaço duplo ou aspas curvas, o `{nome}` do telégrafo não casa e o id sai do nome sujo. | Normalizar primeiro e usar `gen_anterior["nome"]` nas duas chamadas. |
| P2-4 | P2 | `services/creature_gen.py:876-907` (`padroes_livres`) | Quando nenhuma cadência colide, as duas listas (lacaio/padrão e elite/chefe) saem idênticas (conferido em `costa_negra`): cerca de 170 caracteres repetidos, num prompt que já corta a lore para caber em 14 000. | Se as duas listas forem iguais, emitir uma só ("qualquer categoria: …"). Detalhe no parecer do prompt. |
| P2-5 | P2 | `rag.py:1740` | `reindex_global(only=...)` com valor fora de `all/rules/lore` (chamada programática) roda o lint e não faz nada, em silêncio. O CLI está protegido pelo `choices` do argparse. | `raise ValueError` para valor desconhecido. |
| P2-6 | P2 | `docs/spec374/RELATORIO.md:5-8` | O R9 não pôde listar os termos do R20 porque os registros não guardam a mensagem do lint da 1ª tentativa. `costa_negra` reprovou por R20 na 1ª tentativa nas **duas** rodadas medidas, e de novo não dá para saber o termo. | Follow-up do produto (não do avaliador): `info` passa a carregar as mensagens do 1º lint (`info["lint_primeira_msgs"]`, cortadas a 120 caracteres). O `eval_geracao.py` só as grava se o autor de eval aceitar (é caminho protegido). |
| P2-7 | P2 | `handoffs/` + spec §3 | A spec cita `handoffs/SPEC-374-prompt-review.md`, que reprova no `check_handoff_names.py` (o papel `prompt` não existe). O parecer do prompt foi gravado como `handoffs/SPEC-374-astra-review.md`. | O coordenador atualiza a referência na §3/§9 no pouso. |

## Correções aplicadas

Nenhuma ainda (o revisor só escreve este arquivo).

## Pendências

- P1-1 e P1-2: executor de produto, nesta spec, antes do pouso. O P1-2 muda o default de uma flag `ops`
  e não toca na geração nem no lint, então não invalida as rodadas medidas (o eval chama `gerar_nova`
  direto, fora do dreno). O P1-1 também não toca no caminho medido.
- P2-1 a P2-5: mesma spec, se couber; senão, follow-up.
- P2-6: follow-up (spec futura da D11 ou smoke §6).
- Smoke §6 itens 2–7 e reindex real (§6.3): coordenador.

## Comandos rodados

```text
git log --format='%h %an %s' main..HEAD -- <caminhos do avaliador> → só d3019102
sha256sum tests/fixtures/spec361_pedidos.yaml tests/fixtures/spec374_pedidos_ajuste.yaml → baf38310…db6dbc / 13ec924e…a3df
py.sh -m pytest -q tests/test_spec374_*.py tests/test_spec361_*.py tests/test_flag_registry.py tests/test_job_logging.py tests/test_spec192_cron_endpoints.py → 197 passed, exit 0
py.sh -m pytest -q tests/test_spec300_values.py tests/test_fase25.py tests/test_spec348_canon.py tests/test_bug_memoria_resiliencia.py tests/test_fase71.py tests/test_fase72.py tests/test_fase73.py → 1 failed (test_hook_mundo_vivo_em_entities: 0 == 36), resto verde
py.sh scripts/validate_content.py → 0 ERRO, 29 AVISO
py.sh (sondas offline) _limpar_forma / normalizar_forma / montar_prompt(costa_negra) → ver P2-2, P2-4
```
