# SPEC-373: parecer de autoria de eval (Etapas E e E2)

- **Papel:** autor de eval (Opus, `claude-opus-5-5`), agente separado do executor de produto.
  Não toquei em código de produto, Cartas, `_ajustes.yaml` nem `bestiary.json`.
- **Branch:** `spec-373`, worktree `C:/Users/guilh/AppData/Local/Temp/claude/rpg-spec-373`,
  rebaseada na `main` `9468d058` (produto medido = esse SHA).
- **Commit do avaliador:** `1729475d` "test(eval): arena seed offset, family card cap 15 and frozen
  gates (SPEC-373)". Entrou antes de qualquer commit de produto (a branch só tinha a spec).
  Linha de base e este parecer vão num 2º commit (`test(eval): frozen baseline …`).
- **Status:** `EVAL_AUTHORING_REQUIRED`. Nenhum caminho tocado era protegido no dia, mas segui o
  padrão da 360/370/374: o avaliador novo entra em `evals/protected-paths.txt` no mesmo commit.
  Editar essa lista dispara o job `protected-evaluator-review` (environment `eval-governance`):
  para publicar, o dono aprova pelo `/eval-publish`.

## 1. O que mudou

| Req. | Onde | O quê |
|---|---|---|
| Etapa E / D5 | `scripts/bestiario/arena.py` | `--seed-inicio N` (default 0): `range(N, N + seeds)`. Com 0, o JSON sai igual ao de antes (sem chave nova); com N ≠ 0 o payload grava `seed_inicio`, para a confirmação provar a faixa de sementes. Faixa, delta e veredito sem mudança. |
| Etapa E2 / R16 | `tests/test_enemy_decks.py` | os 3 testes de teto da 332 sem o `continue` de `origem == bestiario-349` |
| Etapa E2 / R16 | `tests/test_spec349_mecanica.py` | `test_uso_das_cartas_de_familia_escala_com_o_bestiario`: teto 36 → 15, docstring `SUPERADO_POR: SPEC-373` |
| R13/R17/R18/R3 | `tests/test_spec373_artefatos.py` (novo) | portões congelados, ver §2 |
| integridade | `evals/protected-paths.txt` | + `scripts/bestiario/arena.py`, `tests/test_spec373_artefatos.py`, `docs/spec373/base/eval` |
| linha de base | `docs/spec373/base/eval/` | `arena-<regiao>.{json,md}` (12 regiões) e `posturas-0-19.json`, ver §3 |

A linha de base fica em `base/eval/` (protegida), não em `base/`, para não colidir com os
artefatos do R5 que o executor grava em `docs/spec373/base/` na Etapa 0.

## 2. Portões (`tests/test_spec373_artefatos.py`)

Limiares no topo do arquivo. Denominador: as 281 criaturas da base (mesmos ids, nenhuma excluída).
Unidade: vitória do herói por célula, 5 Posturas × 40 sementes = 200 lutas.

| Teste | Lê | Passa se |
|---|---|---|
| `test_portao_veredito_cheio_250_de_281` | `docs/spec373/arena-<r>.json` × 12 | mesmos 281 ids da base; `ok` do `arena.py` em **≥ 250** (decisão do dono 04/11; era 256) |
| `test_portao_regressoes_de_borda` | idem + base | para quem tinha `ok` na base e perdeu: excesso ≤ **3,0 pp** e no máximo **5** casos. Excesso = pior célula fora de 45–85 %, ou \|delta\| − 8 pp nos slots de `arena-slots-baseline.json` cujo valor antes estava na faixa (a mesma regra do `arena.py`). O teste confere também que a leitura bate com o `ok` gravado. |
| `test_portao_off_identico_fora_das_recalibradas` | idem + `docs/spec373/recalibradas.json` | toda célula `|off` igual à base, salvo os ids da lista (R8; `[]` se nenhum) |
| `test_portao_chefes_na_faixa_off_e_on` | idem | os 13 chefes com `L5|off` e `L5|on` em 45–85 %; os 2 slots com `ok` (R13) |
| `test_portao_posturas_identicas_depois_de_a_e_b` | `docs/spec373/posturas-ab-0-19.json` | `posturas` idêntico, célula a célula, a `base/eval/posturas-0-19.json` (R18; gerar depois de A/B e **antes** da Parte C) |
| `test_portao_confirmacao_40_119_gravada` | `docs/spec373/confirmacao-40-119.json` | gerado pelo `arena.py` com `seed_inicio == 40`, `seeds == 80`, os 13 chefes com `L5|off`/`L5|on`. Só a forma: o resultado vai para a §9 sem reajuste (R3). |

Os artefatos são exigidos (o teste falha, não pula): a branch fica vermelha nesses 6 testes
até o executor entregar. Hoje todos falham com `artefato ausente`. Testes do avaliador, verdes:
known-good/known-bad de `excesso_pp` e `regressoes` (dentro, borda, 6 de borda, 5 pp, quem já
falhava), `--seed-inicio 0` igual ao default (lutas reais, `enemy_gargula_ferro`, 2 sementes),
`--seed-inicio 40 --seeds 2` usa 40 e 41, forma da base (12 regiões), `test_avaliador_protegido`.
Conferido na própria base: a leitura do portão bate com o `ok` do `arena.py` nas 281, e
base × base dá zero regressão.

Teto de 15 (R16), hoje vermelho como deve: na semente 0, máximo 33
(`inf_tatico_apontar_a_falha`) por id simples e 34 (`inf_predador_salto_presa`) com ids de
instância; o teste das sementes 0–11 acusa várias `covarde_oportunista` em 22–26. O executor
não edita esses testes: a Etapa E2 já está feita, e o `xfail` da Etapa 3 deixou de ser
necessário (o `test_uso_populacao_inteira_ate_15` do executor fica informativo, se ele quiser).

## 3. Linha de base (`main` `9468d058`, sementes 0–39, `off,on`, L3/L5)

Comando por região: `arena.py --regiao <r> --seeds 40 --modo off,on --baseline
docs/spec349/arena-slots-baseline.json --json … --md …`, uma por vez (~29 min no total).

**Veredito cheio: 241 de 281** (a SPEC-349 registrou 247). 32 criaturas mudaram de célula desde
a 349 e 8 trocaram de veredito: 7 saíram (`mon_anzolado_da_casa`, `mon_lacrador_de_saidas`,
`mon_bracos_de_tenaz`, `mon_armador_de_fosso`, `mon_portao_que_morde`,
`mon_carregador_de_ganchos`, `mon_escuta_do_sinal`; quase todas por `L3|on` acima de 85 %) e 1
entrou (`mon_aguadeiro_de_bucho`). A causa provável são as mudanças do motor de combate depois da
349 (SPEC-387, `1e208ac9`/`03d457dc`/`3f0be849`); não investiguei além disso.

Por região (ok/total): aethelgard 24/25, brekmar 17/20, costa_negra 21/22, deserto_zhur 21/26,
floresta_sussurros 19/25, montanhas_afiadas 20/27, nova_arcadia 23/27, ophidia 18/20,
pantano_melancolia 20/22, pradaria_ruinas 19/22, selva_xylos 20/22, skallgard 19/23.

**Chefes (L5):**

| chefe | `off` | `on` | 349 (`off`/`on`) | veredito |
|---|---|---|---|---|
| `mon_borda_que_anda` | 76,0 % | **40,5 %** | 75 / 41 | fora (`on`) |
| `mon_chifres_travados` | 64,5 % | **29,5 %** | 64 / 29 | fora (`on`) |
| `mon_casco_de_costelas` | 63,0 % | **35,0 %** | 63 / 32 | fora (`on`) |
| `enemy_aranha_de_cristal` (slot) | 61,0 % | **32,0 %** | 53 / 28,5 | fora (`on`) |
| `enemy_boss_general_escorpiao` (slot) | **91,0 %** | 60,5 % | 90,5 / 56,5 | fora (`off`) |
| `mon_hospede_do_estomago` | **43,5 %** | **32,5 %** | 42 / 32,5 | fora (os dois) |
| `mon_toldo_das_clareiras` | 46,0 % | **32,5 %** | 47 / 32 | fora (`on`) |
| `mon_peso_dos_vencidos` | 68,0 % | **27,5 %** | 66,5 / 26 | fora (`on`) |
| `mon_escavador_das_camaras` | 65,5 % | **31,5 %** | 66,5 / 30,5 | fora (`on`) |
| `mon_cacao_de_lastro` | 69,5 % | 62,5 % | 70 / 61 | ok |
| `mon_roda_de_mandibulas` | 65,5 % | 55,0 % | 65 / 53,5 | ok |
| `mon_mastro_dos_ultimos` | 78,5 % | 52,5 % | 77,5 / 52,5 | ok |
| `mon_colecionador_de_poses` | 64,0 % | 47,0 % | 63 / 48,5 | ok |

O quadro da §1 da spec se mantém: 9 fora, 4 dentro (o `colecionador` com só 2 pp de folga no `on`).

**Posturas** (`arena_spec355.py base --seeds 0:20`, total `todas`): Devoto 60,2 %, Sangromante
65,0 %, Corruptor 51,9 %, Arcanista 55,8 %, Médico 45,8 %. Arquivo: `base/eval/posturas-0-19.json`.

## 4. Portão do veredito cheio: 250/281 (decisão do dono 04/11)

O R17 fixava 256 = 247 + 9, com a base da 349. A base de hoje (`main` `9468d058`) é 241. O dono
decidiu em 04/11: o portão passa a **250 = 241 + 9** e a deriva vai para uma spec própria. A
emenda está em `tests/test_spec373_artefatos.py` (`MIN_OK`) e na spec (R17 e critério de
aceite), num commit próprio de eval, antes de qualquer produto. As regressões já contavam
contra a base de hoje; nada mais mudou.

**As 7 criaturas que derivaram** (tinham `ok` na 349 e não têm na base de hoje; L3, `off`/`on`):

| criatura | região | 349 | hoje | motivo |
|---|---|---|---|---|
| `mon_anzolado_da_casa` | brekmar | 72,5 / 83,0 | 72,5 / 86,0 | `on` acima de 85 % |
| `mon_lacrador_de_saidas` | deserto_zhur | 56,0 / 81,5 | 64,5 / 89,0 | `on` acima (e `off` +8,5 pp) |
| `mon_bracos_de_tenaz` | montanhas_afiadas | 59,5 / 72,0 | 59,5 / 87,0 | `on` acima |
| `mon_armador_de_fosso` | montanhas_afiadas | 78,5 / 78,5 | 78,5 / 96,5 | `on` acima |
| `mon_portao_que_morde` | nova_arcadia | 61,0 / 63,0 | 91,0 / 93,5 | `off` e `on` acima |
| `mon_carregador_de_ganchos` | pradaria_ruinas | 54,5 / 82,0 | 54,5 / 86,0 | `on` acima |
| `mon_escuta_do_sinal` | skallgard | 46,5 / 83,0 | 46,5 / 89,5 | `on` acima |

(No outro sentido, `mon_aguadeiro_de_bucho` entrou: `on` 88,0 → 75,0.)

**Causa provável** (não investigada a fundo): as mudanças do motor de combate depois da 349,
na SPEC-387 (`3f0be849` "one playable predicate…", `03d457dc` "registry order, phase lines…
off fallback", `1e208ac9` "attacker downed by a Reaction does not resolve its attack"). Cinco
das sete mudaram só no `on` (o herói ficou mais forte contra baralho de Cartas), o que bate com
o atacante derrubado por Reação não resolver o ataque. `mon_portao_que_morde` e
`mon_lacrador_de_saidas` mudaram também no `off`, então há uma segunda causa (o fallback do
`off` ou dado da criatura); vale conferir na spec própria.

## 5. Comandos para o executor

Python por `bash scripts/dev/py.sh`; arena um processo por vez, em background.

```bash
# Etapa 5 (R17), uma região por vez; saída em docs/spec373/ (não em base/eval/)
bash scripts/dev/py.sh scripts/bestiario/arena.py --regiao <r> --seeds 40 --modo off,on \
  --baseline docs/spec349/arena-slots-baseline.json \
  --json docs/spec373/arena-<r>.json --md docs/spec373/arena-<r>.md
# R8: ids recalibrados (o portão do off lê esta lista; [] se nenhum)
echo '["mon_x", "..."]' > docs/spec373/recalibradas.json
# R18, depois de A/B e antes da Parte C
bash scripts/dev/py.sh docs/spec355/arena_spec355.py base --seeds 0:20 --out docs/spec373/posturas-ab-0-19.json
# Etapa 6 (R3), uma vez, depois do commit do pacote final
bash scripts/dev/py.sh scripts/bestiario/arena.py --ids <13 chefes + recalibradas> \
  --seed-inicio 40 --seeds 80 --modo off,on --json docs/spec373/confirmacao-40-119.json
# portões
bash scripts/dev/py.sh -m pytest tests/test_spec373_artefatos.py tests/test_enemy_decks.py \
  tests/test_spec349_mecanica.py -n 2 -q
```

Os 13 chefes: `mon_borda_que_anda,mon_chifres_travados,mon_casco_de_costelas,enemy_aranha_de_cristal,enemy_boss_general_escorpiao,mon_hospede_do_estomago,mon_toldo_das_clareiras,mon_peso_dos_vencidos,mon_escavador_das_camaras,mon_cacao_de_lastro,mon_roda_de_mandibulas,mon_mastro_dos_ultimos,mon_colecionador_de_poses`.

## 6. Regra daqui em diante

Depois destes commits o executor não toca em `scripts/bestiario/arena.py`,
`tests/test_spec373_artefatos.py`, `docs/spec373/base/eval/` nem nos testes de teto de
`tests/test_enemy_decks.py`/`tests/test_spec349_mecanica.py`. Se achar que precisa, para e
registra para o dono (R1). Revisor Sol: conferir `git diff 1729475d~1 1729475d` (só avaliador)
e que nenhum commit de produto mexe nesses caminhos.

## 7. Testes rodados

- `tests/test_spec373_artefatos.py -n 2`: 18 passed, 6 failed (os 6 portões, `artefato ausente`).
- `tests/test_enemy_decks.py tests/test_spec349_mecanica.py -n 2`: 4 failed (os 4 de teto, como esperado), 574 passed.
- `tests/test_eval_governance.py tests/test_ci_eval_gates.py`: verdes; `evals.core.governance check` válido.
- `ruff check`/`format` limpos nos arquivos tocados.
