# SPEC-374 — revisão sol (review)

> Nome do arquivo: `handoffs/SPEC-374-sol-review.md` (lint `scripts/check_handoff_names.py`).
> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (rodada 4, `1ce2fd12`; rodadas 1 e 3 foram `CHANGES_REQUIRED`, rodada 2 `APPROVED_WITH_FOLLOWUPS`)
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

## Rodada 2 (2026-11-03, commits `e1829a8f`..`fb1414b8`)

**Veredito da rodada 2:** `APPROVED_WITH_FOLLOWUPS`. Os dois P1 estão fechados no source, e as medidas v2 são íntegras.

- **P1-1 fechado.** O gerador (`scripts/gen_world_living_npcs.py:327`, `:341-344`) escreve em `extra[npc_id]` e
  tira o id do canônico (`entities.pop`). O migrate só regera `entities.json`. Agora há um só dono, e os
  dois concordam: o canônico nunca tem `npc_mv_`. `test_roundtrip_gerador_migrate_um_dono` roda o
  gerador (via `RPG_ROOT`, conferido em `:18`, então escreve na cópia e não no worktree) e depois o
  migrate. Resultado: 36 ids na união, nenhum em `entities.json`, `base & extra` vazio, doc público
  preservado. `validate_faction_membership` (`content_validator.py:1716`) passou a ler `_merged_entities`.
  `test_spec300_values` lê a união e mantém `== 36` e a checagem do gancho. O invariante é o mesmo,
  agora sobre o dono certo, então não houve afrouxamento. O que ainda lê só `entities.json`
  (`creature_gen._faccoes_validas`, `shared_pool_validators._secret_names`, `curadoria.py:234`) procura
  facções e segredos, que não incluem `npc_mv_`. Sem impacto.
- **P1-2 fechado.** `janela_minima_s()` tem default `prazo_s() + 3` (33 s), e a flag foi atualizada em
  `config/flags.yaml`. `test_drain_real_com_defaults_adia_o_job` usa o `drain_jobs` real com os defaults
  e orçamento de 20 s: `deferred == 1`, LLM não chamado, `attempt == 0`. O §6.6 fica coerente com o
  código. O corte `min(prazo, janela − 3)` só vale com a env baixada, e esse caso está testado.
- **P2 de código fechados:** aspas internas (`t[0] not in t[1:-1]`); nome limpo no `{nome}` e no id;
  `padroes_livres` em lista única; `ValueError` em `reindex_global`; `info["lint_primeira_msgs"]`
  gravado junto do `lint_primeira` e antes do reparo, sem mudar a medida. Também saiu o teste do enum
  dos seis eixos no schema saturado e a §9 foi corrigida.
- **Testes da 361 ajustados (`tests/test_spec361_prompt.py`):** não enfraquecem o que importa.
  (a) `REGRAS+PAPEL ≤ LIM_REGRAS + 1100`: hoje dá 3 388 com linha e 3 262 saturado, para um teto de 3 600.
  O limiar duro da spec (`prompt_chars ≤ 14 000`) segue assertado, e as medidas v2 registram 13 915.
  (b) "≥ 1 exemplo" vale só no caso de `montar_prompt(feedback=...)` com 8 × 900 caracteres. Nenhum
  chamador de produção passa `feedback=` (busca em `services/agents/scripts/workers`), porque a 2ª
  tentativa usa `montar_prompt_correcao`. O caso normal da maior região continua `== 2` exemplos.
- **Integridade das medidas v2:** os dois JSON têm `commit: 7828e73be680`, `real: true`, `mock: false`
  e `pedidos_sha256 = baf38310…db6dbc`. Entre `7828e73b` e `fb1414b8` só entram os 3 arquivos de
  medida e a §9 (`git diff --stat`), então não houve retune entre as rodadas. Nada mudou no avaliador
  (o `git log` dos caminhos protegidos segue só com `d3019102`). `--protocolo` dá 16/22 com piso 7/11
  respeitado (7 e 9). Os outros limiares passam em cada rodada, mas a rodada 1 fica no limite:
  `lint_final` 0,9091 (≥ 0,9) e `fallback` 0,0909 (≤ 0,1).

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R2-P2-1 | P2 | spec §9 / D6 | A mudança de texto (`80ed7ee2`) foi motivada por fichas do **set medido** (rodadas v1 da 361), o que contamina de leve o R2, que manda iterar só no set de ajuste. As mudanças são gerais (acento, rótulo, ruído de lista), não específicas de pedido, e o resultado caiu (17 → 16/22), então não há sinal de overfitting. A v2 é a medida que vale para o código final; o critério passou no mínimo exato. | O coordenador registra na §9 que a v2 é a oficial e que a margem é zero. O smoke §6 e a D11 item 3 devem tratar 16/22 como "passou sem folga". Opcional: 1 rodada no set de ajuste com o texto novo, só para registro. |
| R2-P2-2 | P2 | `docs/spec374/eval-medido-v2-1.json` | Rodada 1 teve um fallback (`deserto_zhur`: SCHEMA + PRAZO). `fallback` = 9,1 % e `lint_final` = 90,9 % ficam exatamente no limite. | Olhar no smoke §6 (provider por chamada, latência). Nenhuma ação nesta spec. |

Comandos da rodada 2:

```text
py.sh -m pytest -q tests/test_spec374_*.py tests/test_spec361_*.py tests/test_flag_registry.py tests/test_job_logging.py tests/test_spec192_cron_endpoints.py tests/test_spec300_values.py tests/test_fase25.py tests/test_spec348_canon.py tests/test_fase71.py tests/test_fase72.py tests/test_fase73.py → 340 passed, exit 0 (sem -n)
py.sh scripts/validate_content.py → 0 ERRO, 29 AVISO
grep '"commit"|"mock"|"pedidos_sha256"' eval-medido-v2-{1,2}.json → 7828e73be680 / false / baf38310…
git diff 7828e73b fb1414b8 --stat → só eval-medido-v2-* e a spec
git status --short (depois dos testes) → limpo
```

## Rodada 3 (2026-11-03, commits `cf710d21`..`c7ff5e1d`: v3 revertida, U14 `a8d19167`, ajuste 6, medidas v4, decisão do dono)

**Veredito da rodada 3:** `CHANGES_REQUIRED`. A U14 está correta, é determinística e não afrouxa o U13. As medidas v4 são íntegras. Fica um P1 novo na Composição da arte.

- **U14, correção:** `services/axis_text.py` tem duas regras.
  - Material por dominância: o material declarado tem ≤ 1 raiz distinta no léxico amplo, e outro material tem ≥ 3 raízes do léxico forte e ≥ h + 2.
  - Locomoção `nada` por ausência de qualquer raiz de água ou nado.
  - Sondei offline: `(?:na|sob a|…) agua` sobrevive ao `_fold` (só tira acento); `\b` no início evita "possui" casar "oss"; o "Ouvido de Sal" reprova nos dois eixos.
  - As raízes são cobradas no texto inteiro (inclui gancho e contra_jogo), o que é conservador no sentido certo: mais texto só aumenta o h do declarado.
- **U14, determinismo:** não há aleatoriedade nem chamada a LLM, e o cache de regex é por chave. O empate em `max(fortes, ...)` desempata pela ordem de inserção de `FORTE`, que é fixa.
- **U14, falso positivo:** 7/281 = 2,5 %, travado em teste com teto de 4 % sobre `fichas_aprovadas()`. As 7 marcadas são mistura real de matérias (lista em `docs/spec374/u14-falso-positivo.md`).
  - Limite assumido e registrado: percepção, plano e escala não são cobrados. A 3ª contradição do curador (`respiracao`) passa. Não é achado: a versão de três eixos reprovava 45,6 %.
- **U13 não fica mais fraco.** A U14 só acrescenta erros. `reparar_padrao` segue exigindo só U13, e `reparar_eixos` só U2/U3/U14. Uma ficha com U13 e U14 juntos não é reparada por nenhum dos dois e vai para a correção curta: o gate ficou mais duro, não mais frouxo.
  - O reparo da U14 troca a linha e mantém a prosa. Só aceita linha que passa no lint inteiro, então só cai numa linha coerente com o corpo.
- **Mock dos testes da 361 (`mock_llm.py:718`):** escrever "Vive nadando, de nadadeiras moles" quando a locomoção é `nada` só mantém a prosa sintética coerente com o gate, que é o mesmo papel de antes ("Corpo de {material}"). Não mascara bug da U14: ela tem oráculo próprio com prosa real (o "Ouvido de Sal") e a medida de falso positivo sobre 281 fichas reais. O mock nunca foi oráculo do gate. Os `test_spec361_*` não mudaram nesta rodada.
- **Medidas v4:** os dois JSON têm `commit: 32086220a00e`, `real: true`, `mock: false` e `pedidos_sha256 = baf38310…`.
  - Entre `a8d19167` e `32086220` só entra o registro do ajuste 6; entre `32086220` e `65d785a9`, só as medidas e a §9. Não houve retune entre as rodadas.
  - O avaliador segue intocado: o `git log` dos caminhos protegidos continua só com `d3019102`.
  - `--protocolo` dá `passou: false` (13/22; rodada 2 com 5/11). A §9 registra isso sem maquiar, e registra a decisão do dono "Aceitar e ligar" (desvio da D11 item 3).
  - A v3 (texto sem exemplos, 13/22) foi revertida conforme o R2. Certo.
- **Leitura da integridade:** a U14 entra no `lint_primeira` porque roda na 1ª leitura, como manda a D3. Isso deixa o gate mais duro, então a v4 não é comparável com a v2. A §9 deixa claro que a v2 (16/22) mede o código **sem** U14 e que o código que pousa é o da v4. É honesto. O dono aceitou com esse quadro.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R3-P1-1 | P1 | `scripts/bestiario/pool_revisao.py:109-137` (`_LUGAR`, `lugar_do_texto`, `_composicao`) | **A Composição da arte quase sempre recebe um "lugar" que não é lugar.** A regex pega o primeiro `em/na/no/sob/entre/dentro de` seguido de qualquer palavra. Rodei `lugar_do_texto` sobre as 281 aprovadas: devolve algo em 277, e as 20 primeiras incluem `azul`, `placas`, `lábios`, `tecido`, `costelas`, `que`, `meia`, `S`, `listras`, `ombro de um`, `peso do braço`, `pele`, `pescoço`. A Composição vira "Lábios (Costa Negra), luz baixa; …", que vai para o doc de arte e daí para o retrato pago. Antes ela usava o nome do habitat do mapa. É regressão para quase toda ficha importada. O teste só cobre o "Ouvido de Sal" e um caso sem lugar. | Aceitar o lugar do texto só se o núcleo for um **substantivo de lugar** de uma lista fechada (cisterna, poço, gruta, caverna, galeria, mina, margem, praia, poça, pântano, brejo, ruína, cripta, porão, esgoto, doca, cais, ponte, estrada, floresta, mata, duna, deserto, campo, forja, oficina, torre, farol, câmara, túnel, salão, beco…). Fora da lista, volta para `habitat_nome`. Teste sobre `fichas_aprovadas()`: todo lugar extraído tem núcleo na lista, ou vem vazio. Manter `"Cisterna de pedra (Deserto de Zhur)"` para o "Ouvido de Sal". |
| R3-P2-1 | P2 | `services/creature_gen.py` (`gerar_nova`, código `"U2U3-eixos-reparados"`) | O reparo da U14 grava o mesmo código do reparo de colisão, e o relatório não distingue os dois. | Gravar `"U14-eixos-reparados"` quando o issue reparado for U14 (o eval só conta códigos, então isso não mexe em métrica). |
| R3-P2-2 | P2 | spec §9 | A medida oficial do D6 (v2) não mede o código que pousa (v4, com U14). O aceite do dono cobre isso. Falta registrar o que observar no staging. | O coordenador registra um gatilho de revisão: `fallback` > 10 % ou `lint_final` < 90 % em jogo real com a flag `on` → reabrir. A rodada 2 da v4 ficou no limite dos dois. |

Comandos da rodada 3:

```text
py.sh -m pytest -q tests/test_spec374_*.py (inclui test_spec374_u14.py) tests/test_spec361_*.py tests/test_flag_registry.py tests/test_spec300_values.py → 198 passed, exit 0 (sem -n)
py.sh (offline) axis_text.incoerencias em casos sintéticos → regex de água e \b ok; Ouvido de Sal reprova
py.sh (offline) pool_revisao.lugar_do_texto sobre as 281 aprovadas → 277 com "lugar"; amostra: azul, placas, lábios, que, S, pescoço (R3-P1-1)
grep commit/mock/sha em eval-medido-v4-{1,2}.json → 32086220a00e / false / baf38310…
git diff a8d19167 32086220 --stat → só eval-ajuste-6.json; git log dos caminhos protegidos 534a642f..HEAD → vazio
```

## Rodada 4 (2026-11-03, commits `24090b3f`, `a3ee74f8`, `1ce2fd12`)

**Veredito da rodada 4:** `APPROVED_WITH_FOLLOWUPS`. O R3-P1-1 está fechado.

- **R3-P1-1 fechado.** `lugar_do_texto` percorre todos os casamentos (`finditer`) e só aceita o sintagma
  cujo núcleo, sem acento, está em `SUBSTANTIVOS_DE_LUGAR` (lista fechada). Fora dela, a Composição volta
  para o habitat do mapa. Rodei de novo sobre as 281 aprovadas: 19 lugares extraídos, todos lugares de
  verdade (ponte, margem, Poço das Dívidas, porto, duna, trilha, Forja, Catedral, Pântano, Pradaria,
  ruína, selva). Os casos ruins de antes (azul, lábios, que, S) sumiram. O "Ouvido de Sal" mantém
  "Cisterna de pedra (Deserto de Zhur)", e há teste sobre as 281.
- **R3-P2-1 fechado.** O reparo por U14 grava `U14-eixos-reparados`, e o de U2/U3 continua com o código
  antigo.
- **R3-P2-2 fechado.** O gatilho de staging está na §9: `fallback` > 10 % ou `lint_final` < 90 % com a
  flag `on` em jogo real reabre a spec.
- **Integridade da v5 (informativa):** os dois JSON têm `commit: a3ee74f87574`, `mock: false` e
  `pedidos_sha256 = baf38310…`. Entre `a3ee74f8` e `1ce2fd12` só entram as medidas e a §9, então não
  houve retune. Nenhum caminho protegido mudou depois de `534a642f`. O protocolo dá `passou: false`
  (12/22, 6 + 6), com `lint_final` 1,0 e `fallback` 0 nas duas rodadas. A §9 registra isso como
  informativo, sob o desvio que o dono já aceitou.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R4-P2-1 | P2 | `scripts/bestiario/pool_revisao.py` (`SUBSTANTIVOS_DE_LUGAR`) | "caminho" é figurado na maioria dos 4 casos ("caminho da luta"). Além disso, "farol" e "gruta" estão duplicados na lista, o que é inócuo num `frozenset`. | Tirar "caminho" (e, se preferir, "passagem") da lista. Não bloqueia. |

Comandos da rodada 4:

```text
py.sh -m pytest -q tests/test_spec374_u14.py tests/test_spec374_eixos.py tests/test_spec374_forma.py tests/test_spec361_prompt.py tests/test_spec361_gate.py → 80 passed, exit 0 (sem -n)
py.sh (offline) lugar_do_texto sobre as 281 aprovadas → 19 lugares, todos substantivos de lugar
grep commit/mock/sha em eval-medido-v5-{1,2}.json → a3ee74f87574 / false / baf38310…; git diff a3ee74f8 1ce2fd12 --stat → só medidas + spec
```
