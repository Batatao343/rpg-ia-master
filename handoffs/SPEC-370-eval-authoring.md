# SPEC-370 — parecer do autor de eval (Etapa 1)

- **Papel:** autor de eval (Opus, `claude-opus-5-5`), agente separado do executor de produto.
  Não tocou em código de produto, `fauna.json`, fichas nem `fauna_config.json`.
- **Base:** `1187162e` (branch `spec-370`). Data: 2026-11-03.
- **Status:** `EVAL_AUTHORING_REQUIRED`. Os dois arquivos protegidos (`scripts/fauna/eval.py`,
  `evals/protected-paths.txt`) e o novo `tests/test_spec370_eval.py` disparam o job
  `protected-evaluator-review` (`.github/workflows/eval-gates.yml:39-55`, environment
  `eval-governance`). Para publicar, o dono aprova o environment (skill `/eval-publish`).
  Segui o padrão da D6 da SPEC-360 (`fa2fefbd`): o novo teste entra em
  `evals/protected-paths.txt` no mesmo commit do avaliador.

## O que mudou no avaliador (R16-R20)

| Req. | Mudança | Onde |
|---|---|---|
| R16 | `--regiao <r>` (choices = 12 regiões) e `--todas`. Sem flag: caminho da 360 inalterado (NA, `eval-nova_arcadia.md`, mesmo código de saída). `run(seeds, days, region, *, m7)` e `run_all`. Região de 1 nó: a "chegada" volta ao mesmo nó (só muda quando não há outro nó; NA intacta). | `scripts/fauna/eval.py` `run`, `run_all`, `main`, `_simulate` |
| R16 N/A | M4 N/A com < 2 nós raiz (`M4_MIN_NOS = 2`); M3 N/A só quando **nem** `m3_up` **nem** `m3_down` têm par elegível; com um lado só, o lado presente tem que passar. Motivo vai no relatório (`spec370.na`). | `_spec370` |
| R17 | `global_m5(results)`: combates de fauna por 100 ações somando as regiões, on × off, mesmas seeds; barra em [−0,20, +0,05]. Por região o M5 é informativo, alerta fora de [−0,30, +0,10] (D5). | `global_m5`, `M5_REGIAO_ALERTA_*` |
| R18 | Oráculo próprio do M1: cada texto devolvido por `scene_block`, `convert_to_signal` e `track_signal` é atribuído à criatura cujo texto de `sinais` (marca/rastro/resto/som/cheiro), lido de `data/world/fauna.json`, aparece nele. Combate precedido = existe sinal daquela criatura numa ação anterior, no mesmo local ou num nó do `territorio` dela (lido do mesmo arquivo), depois do último combate com ela e não antes do dia de nascimento da presença. O estado do produto só **estreita** a janela (`born_day`) e identifica a presença (`presence_id`); nunca conta sinal. `sinais_mostrados` sai do oráculo. O relatório mostra os dois números, as divergências e os textos sem dono. | `attribute_sign`, `precedido_oraculo`, `_simulate` |
| R19 | M7 no tamanho do relatório: `run(..., m7=True)` roda a simulação 2× e compara o SHA-256 do resultado. Teste: 3 × 12 por região; 20 × 60 só em NA (D6). | `_digest`, `run` |
| R20 | M8 = ações com ≥ 1 texto de sinal novo (cena + conversão + rastro) / ações, com `on`; ≤ 0,40 (D7). | `_simulate` (`acoes_com_sinal`) |

**Byte a byte (Etapa 1.1).** `eval.py` sem flag gera um `eval-nova_arcadia.md` idêntico ao da
360 no HEAD (`diff` vazio, conferido). O relatório novo de NA (`--regiao nova_arcadia`) começa
com esse corpo, sem mudança, e acrescenta a seção SPEC-370. O teste
`test_nova_arcadia_caminho_360_e_relatorio_fresco` exige que o relatório publicado comece com
`render(run(20, 60))`; quando a Etapa 2 mudar NA (F-16), o executor regenera o relatório
pelo script (o `docs/spec360/` não é protegido), nunca à mão.

**Known-bad do oráculo.** `test_oraculo_nao_confia_em_sinais_mostrados` silencia o texto das
três funções de sinal (o estado continua gravando `sinais_mostrados`): o oráculo antigo conta
precedidos, o próprio dá 0 e o M1 reprova. `test_precedido_oraculo_bom_e_ruim` cobre criatura
errada, janela, mesmo turno e local fora do território.

## Achado durante a autoria (para o coordenador, não corrigido)

- **M7 e o baseline `off`.** `services/ecology.py:59` usa `random.Random()` sem semente quando
  `rng is None`. Com `RPG_FAUNA=off`, `pick_encounter_enemy` (`world_utils.py:1007-1008`)
  chega aí, então **quem** sai no `off` muda entre execuções no mesmo processo (medido:
  `off.combats_with_entry` 711 × 702 em NA 20 × 60). **Quantos** (gatilhos, combates) não
  muda, então o M5 e o R9 da 360 continuam exatos. O hash do M7 cobre todo o resultado `on`,
  a distribuição, as métricas e, do `off`, só as contagens que entram em métrica
  (`M7_OFF_KEYS`). É comportamento legado do produto; registrar como follow-up, não mexi.
  O mesmo vale para o `on` em pool sem nenhuma entrada de fauna (`world_utils.py:993`,
  `why` vazio): não ocorre em região com fauna.
- **Marcador `slow`.** O `pyproject.toml` não registra `slow`. Em vez de marcar (warning) ou
  editar a configuração, o M7 cheio de NA sai da mesma execução do relatório no fixture
  (uma simulação extra, ~15 s). Custo do arquivo: ~45 s com só NA coberta.
- **M8 de NA.** 0,3146, não 0,298 como a §9 da 360 cita: a 360 contava cena + conversão
  (1205 + 223 = 1428); o R20 inclui o rastro (+82). Fica abaixo de 0,40.

## Métricas de Nova Arcádia (HEAD `1187162e`, 20 seeds × 60 dias)

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos, oráculo próprio | **0,7508** (449/598) | ≥ 0,70 | ok |
| M1 precedidos, oráculo antigo | 0,7542 (451/598) | ≥ 0,70 | ok |
| Divergências M1 | só o antigo: 2 · só o próprio: 0 | — | — |
| M1 aproximação | 1,0000 | ≥ 1,0 | ok |
| M2 pior razão fora/dentro | 0,289 | ≤ 0,35 | ok |
| M3 presa sobe (mín.) / predador cai (máx.) | 1,7459 / 0,5545 | ≥ 1,5 / ≤ 0,6 | ok |
| M4 território | 0,8544 | ≥ 0,80 | ok |
| M5 (região, informativo; = global com só NA) | −0,1687 | [−0,20, +0,05] | ok |
| M6 vazamentos | 0 | 0 | ok |
| M7 (20 × 60) | `955a19f0c54236a2` = `955a19f0c54236a2` | iguais | ok |
| M8 densidade | 0,3146 (1510/4800) | ≤ 0,40 | ok |
| Textos de sinal sem dono / multi-dono | 0 / 0 | — | — |

M1 do oráculo novo ≥ 0,70: a execução **não** para (R22). Nenhum limiar foi ajustado.

## Testes

`bash scripts/dev/py.sh -m pytest tests/test_spec370_eval.py tests/test_spec360_eval.py
tests/test_eval_governance.py` → 41 passed, 99 skipped (as 11 regiões sem fauna, com motivo).
`python -m evals.core.governance check --root .` válido. `ruff check`/`format` limpos.

## Regra daqui em diante (R21)

Depois deste commit o executor não toca em `scripts/fauna/eval.py`,
`tests/test_spec360_eval.py` nem `tests/test_spec370_eval.py`. O Sol confere no pouso que
`git diff <este commit>..HEAD` desses caminhos está vazio. Ajuste de produto só por conteúdo
(autor + revisor) ou constante `[BALANCEAR]` registrada na §9.
