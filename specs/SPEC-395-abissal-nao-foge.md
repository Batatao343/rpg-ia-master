# SPEC-395 — Tabela tática respeita `resistance: absoluta` (abissal e outras que não fogem)

> **Status:** `done` — dono, 04/11: "Executar com padrões" (D1–D4 nos defaults); Lençol de Chaminé deixa de fugir (ajuste de texto em spec futura).
> **Criada:** 2026-11-04 · **Atualizada:** 2026-11-04
> **Épico:** SPEC-349 (bestiário) · SPEC-327 (Cartas)
> **Depende de:** SPEC-394 (`in-review`; diagnóstico em `rpg-spec-394/docs/spec394/RELATORIO.md:7-35`, dials atuais do `_ajustes.yaml`), SPEC-373 `done` (congela `arena.py`)
> **Desbloqueia:** retirar a exceção nominal do `mon_portao_que_morde` (SPEC-394 §9); `RPG_ENEMY_DECKS=on` sem essa exceção
> **Risco:** `alto` (combate: decisão de turno do inimigo)
> **Evidência:** teste novo em `tests/test_tactical_archetypes_runtime.py` falha hoje: `ensure_combat_sheet(mon_portao_que_morde)` dá `action_key: "flee"` à prioridade `muito_ferido` com `resistance: absoluta`. Equivalência: hash de `ensure_combat_sheet` (`off`/`on`) idêntico para toda criatura fora do conjunto `A` (R3).
> **EXECUTOR_MODEL:** `Terra` (Sonnet) · **REVIEW_MODEL:** `Sol` (`spec-reviewer`, Opus) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`. O oráculo é o `veredito` do `scripts/bestiario/arena.py` (faixa 45–85 %, `arena.py:42`, `:65`), que está congelado (`evals/protected-paths.txt:26`), e os limiares ficam fixados nesta spec. O teste da 394 (`tests/test_bestiario_calibragem.py`) continua valendo como está. Esta spec só remove o portão das exceções, sem tocar no teste.

## 1. Contexto & Objetivo

`nao_foge: true` na mecânica (`data/bestiario/mecanica/nova_arcadia.yaml:374`) vira, no gerador, a prioridade `muito_ferido` com `resistance: "absoluta"` (`scripts/bestiario/gerar_mecanica.py:265-291`). O validador também lê `absoluta` como "não-fuga intencional" (`services/content_validator.py:977`, `:1111`). Em runtime, porém, `normalize_runtime_profile` (`services/tactical_profile.py:545-566`) preenche o `action_key` de cada prioridade sem chave usando só `_ENEMY_ARCHETYPE_ACTIONS[arquetipo][trigger]` (`:206-255`), sem olhar `resistance`.

O commit `e208f189` (02/11, "full-suite failures after SPEC-349") acrescentou `"abissal": {"muito_ferido": "flee", "sempre": "attack"}` (`tactical_profile.py:247-248`). O teste que motivou a mudança é, por inferência, `test_todo_bestiario_curado_normaliza_para_action_keys_fechadas` (`tests/test_tactical_archetypes_runtime.py:512-528`). Ele exige que todo `arquetipo` do bestiário esteja na tabela e que toda prioridade saia com `action_key` fechado. A 349 criou 5 criaturas `abissal`, e o teste quebrou. **O teste estava certo, o valor escolhido estava errado.** A Etapa 0 confirma isso com `git show`.

**Duas consequências** (`services/conflict_orchestrator.py:696-705`):
- Um `flee` explícito vira a manobra `flee`, que tira o inimigo da luta e conta como vitória do herói (RELATORIO 394:23-24).
- O caminho legado, sem `action_key`, só fazia `move afastar`, e só quando a prosa tinha "foge/recua" (`tactical_profile.py:569-580`).

Por isso o Portão ("Não sai do batente", `data/bestiary.json:25866-25870`) passou de atacar a fugir: 61/63 → 91/93,5. O Lacrador ("Recua e foge", `flexivel`, `bestiary.json:20077-20081`) passou de recuar para fugir de fato: 56/81,5 → 64,5/89.

**O defeito não é só da `abissal`.** Ele vale para toda prioridade `absoluta` cujo gatilho a tabela mapeia para `flee`. Hoje, 8 criaturas formam o conjunto **A** (linha da prioridade `absoluta` em `bestiary.json`):
- `portao_que_morde` (abissal, :25869)
- `odre_de_oleo` (conjurador, :14612)
- `sorvedouro_do_codigo` (conjurador, :25097)
- `pavio_da_lista` (conjurador, :25194)
- `fervente_de_ferrugem` (bruto, :18762)
- `porca_da_queda` (bruto, :24902)
- `dedos_de_colheita` (covarde_oportunista, :21499)
- `lencol_de_chamine` (predador, :24618)

Não entram em A:
- `morto_vivo_implacavel` e `predador_apice` (chefes): não têm `muito_ferido` na tabela e caem em `sempre`.
- `guardiao` (`fila_de_grilhoes`, `bucho_de_praia`): vira `protect`, que não é fuga.

**Objetivo.** Prioridade `absoluta` nunca recebe `flee`/`surrender` da tabela. Depois, remedir as 5 abissais e o conjunto A e recalibrar pelos dials do `calibrar.py` quem sair da faixa, no padrão da 394.

## 2. Requisitos

- **R1 — Regra.** Em `normalize_runtime_profile`, uma prioridade com `resistance == "absoluta"` cujo mapeamento da tabela seria `flee` ou `surrender` recebe o `action_key` de `sempre` do arquétipo (`attack` se não houver). Um `action_key` explícito e válido no perfil continua tendo precedência (`:562`). A regra não interpreta prosa.
- **R2 — Tabela `abissal`.** Fica `{"muito_ferido": "flee", "sempre": "attack"}`: uma abissal `flexivel` com "Recua e foge" continua fugindo (D1). O teste de `e208f189` continua verde sem afrouxar, e ganha um assert: nenhuma prioridade `absoluta` do bestiário sai com `flee`/`surrender`.
- **R3 — Equivalência fora de A.** Os hashes de `ensure_combat_sheet` `off` e do baralho `on` (sementes 0–11, `snapshot.py` da 394) de todas as criaturas fora de A ficam idênticos antes e depois de R1. Em A, só muda o `action_key` da prioridade `absoluta`.
- **R4 — Base pós-correção.** Rodar `arena.py --ids <A ∪ 4 abissais restantes> --seeds 40 --modo off,on` sobre a `main` com R1 aplicado. A saída vai para `docs/spec395/base.json`/`.md`. **F** = os ids sem `ok`. Esperado: Portão perto de 61/63,5, e lacrador, estivador, mastro e monte iguais aos de hoje (por R3).
- **R5 — Recalibração só pelos dials.** Igual à 394 R4: `calibrar.py --regioes <de F> --ids <F> --seeds 40 --rodadas 6`, no máximo 2 execuções, só `corpo`/`dano`/`forca`/`sig` em ±7. Cada passo fica no `_ajustes.yaml` com a leitura da arena, e a regeneração é feita por `gerar_mecanica.py`. Nada à mão em `bestiary.json`, ficha, Carta ou `tactical_profile`.
- **R6 — Meta.** Cada id de F sai com `ok` (L3 `off` e `on` em 45–85 %, sementes 0–39) em `docs/spec395/arena-final.json`. Quem não entrar fica com o melhor ajuste e vira exceção nominal na §9 (D2 da 394).
- **R7 — Confirmação.** Uma rodada `--seed-inicio 40 --seeds 80` sobre F, sem reajuste. O resultado vai para a §9.
- **R8 — Avaliador congelado.** `git diff --exit-code main --` em `scripts/bestiario/arena.py`, `calibrar.py` e no restante de `evals/protected-paths.txt`. O teste da 394 também não muda.

### Fora de escopo

- `legacy_action_key` e o caminho legado `move afastar` (`conflict_orchestrator.py:702-705`).
- `guardiao` `absoluta` → `protect` e qualquer outro gatilho não-fuga.
- `resistance: resistente`/`autonoma` (o significado delas em runtime é outra spec).
- Perfis de NPC/companheiro (`_NPC_TACTICAL_PROFILES`, `companion_orders.py`).
- Mudar o texto ou o `nao_foge` das fichas, emitir `action_key` no gerador (D2).
- Chefes da 373, faixa, sementes e avaliadores.

## 3. Design técnico

- **Alterado:** `services/tactical_profile.py`, só dentro de `normalize_runtime_profile` (≤ 8 linhas). A constante `_NO_RETREAT_ACTIONS = frozenset({"flee", "surrender"})` fica ao lado da tabela. A tabela não muda.
- **Testes** em `tests/test_tactical_archetypes_runtime.py`, docstring "SPEC-395":
  - `test_absoluta_nao_vira_fuga_pela_tabela`: perfil `abissal` sintético com `muito_ferido`/`absoluta` → `attack`; com `flexivel` → `flee`.
  - `test_portao_ferido_nao_foge`: `enemy_declaration` com o portão a `vitalidade ≤ 35 %` não declara a manobra `flee`. Usa os helpers `_actor`/`_scene` do próprio arquivo.
  - O assert novo em `test_todo_bestiario_curado_normaliza_para_action_keys_fechadas`.
- **Novos:** `docs/spec395/{base,arena-final,confirmacao-40-119}.{json,md}`, `{base,final}-snapshot.json` e `RELATORIO.md`. O `snapshot.py` da 394 é reutilizado por caminho, sem cópia.
- **Alterado se F ≠ ∅:** `data/bestiario/mecanica/_ajustes.yaml` (entradas de F) e o que `gerar_mecanica.gerar` regenera.

## 4. Plano passo a passo

### Etapa 0 — confirmar a causa (nenhum produto muda)
1. `git show --stat e208f189` e `git show e208f189 -- services/tactical_profile.py tests/`: registrar no RELATORIO qual teste falhava e se o commit tocou mais algo de combate.
2. `snapshot.py --out docs/spec395/base-snapshot.json`.

### Etapa 1 — testes primeiro
1. Escrever os 3 testes da §3 e commitá-los sozinhos. Esperado: os 3 vermelhos (o portão sai com `flee`).
2. `bash scripts/dev/pt.sh tests/test_tactical_archetypes_runtime.py`.

### Etapa 2 — correção
1. Aplicar R1. Rodar os 3 testes e `tests/test_enemy_decks.py`, `tests/test_spec349_mecanica.py` e `tests/test_bestiario_calibragem.py` com `-n 2`: todos verdes.
2. R3: `snapshot.py --out docs/spec395/fix-snapshot.json --excluir <A>` idêntico à base.

### Etapa 3 — medição e recalibração
1. R4, uma região por vez, em background.
2. Se F ≠ ∅: R5, depois `arena-final.json` (R6) e o snapshot final excluindo A ∪ F.
3. Atualizar `RELATORIO.md`. Tirar o portão das exceções da 394 só se ele tiver `ok`.

### Etapa 4 — confirmação
R7, uma vez. A §9 recebe a tabela antes/depois e os dials.

## 5. Critérios de aceite

- [x] Os 3 testes novos falham na base e passam depois (commit de testes separado)
- [x] R3: snapshot fora de A idêntico; em A, só muda o `action_key` da prioridade `absoluta`
- [x] R4/R6: `base.json` e `arena-final.json` gravados; F com `ok` ou exceção nominal na §9
- [x] R7 (odre_de_oleo fora em 40-119, ver §9): `confirmacao-40-119.json` na §9, sem reajuste
- [x] R8: `git diff --exit-code` no avaliador e no teste da 394
- [x] `validate_content.py` verde; `uv run pytest` verde (coordenador, no pouso)
- [x] Saves antigos carregam: `ensure_combat_sheet` renormaliza o perfil ao montar a ficha (`conflict_orchestrator.py:132`)

## 6. Smoke test

Sem LLM: as rodadas de Cartas não chamam IA e a arena é determinística, então R7 é o smoke de balanço. Integração local com MockLLM:
1. `uv run uvicorn api:app` e `/game/new` em Nova Arcádia com `RPG_ENEMY_DECKS=on`.
2. Forçar o encontro com `mon_portao_que_morde` e levá-lo a ferido: ele segue atacando, o log não mostra fuga e o combate fecha sem erro.
3. O mesmo com `mon_lacrador_de_saidas`: ele ainda foge quando muito ferido (D1).

## 7. Riscos & compatibilidade

- **Saves com combate em curso:** o perfil é renormalizado ao montar a ficha. Um ator já montado mantém o `flee` também na remontagem (Sol P2-1): `ensure_combat_sheet` grava o perfil normalizado no ator e, ao remontar, esse `flee` conta como `action_key` explícito. Só afeta combates salvos antes da correção. É só balanço, sem risco de corromper o save. Marcar a origem da chave fica para uma spec futura.
- **`lencol_de_chamine`:** a dica é "foge do fogo aceso", mas a prioridade é `absoluta`. Pela R1 ele deixa de fugir, porque o dado vence a prosa. Se a intenção era fugir, a correção é na ficha e vai para outra spec.
- **A pode sair da faixa:** as 7 criaturas que não são abissais estavam calibradas fugindo. Algumas podem precisar dos dials, o que aumenta o custo da arena em cerca de 2–3 min por região.
- **MockLLM/quota:** nenhum impacto (caminho determinístico).

## 8. Decisões abertas (default entre parênteses)

- **D1 — Abissal `flexivel` foge?** (**Sim**: o dado autoral manda, então o lacrador, o estivador, o mastro e o monte continuam fugindo e ficam na faixa.) Alternativa: abissal nunca foge (tirar `muito_ferido` da tabela). Nesse caso o lacrador cai para 0,5/1 % (RELATORIO 394:26) e exigiria recalibração ou Carta.
- **D2 — Onde corrigir.** (**No runtime, R1**: cobre saves e o bestiário inteiro.) Alternativa: o gerador emitir `action_key: attack` quando `nf`. Isso não cobre saves nem entradas curadas à mão.
- **D3 — `surrender` também.** (**Sim**: `absoluta` também bloqueia a rendição.)
- **D4 — Escopo da recalibração.** (**F = quem sair da faixa em A ∪ abissais**.) Alternativa: só o portão e o lacrador, deixando o resto de A como exceção.

## 9. Resultado

Ver `docs/spec395/RELATORIO.md`. Correcao R1 em `normalize_runtime_profile` (8 criaturas em A, nao 5: so o
portao e abissal; as outras 7 sao conjurador/bruto/predador/covarde com `absoluta`+`muito_ferido`).
F = sorvedouro, pavio, porca, dedos: de 2-12 % para a faixa em 1 execucao do `calibrar.py` (so dials).
Portao 61/63,5: sai das excecoes da 394. Confirmacao 40-119: tudo `ok` exceto **odre_de_oleo** (L3 off 37 %,
nao recalibrado por R7; excecao nominal / candidato a ajuste futuro). Avaliador e teste da 394 sem diff.
Ids recalibrados (para `recalibracoes_posteriores.json`): mon_sorvedouro_do_codigo, mon_pavio_da_lista,
mon_porca_da_queda, mon_dedos_de_colheita.
Ids de A com ficha `off` mudada sem dial (R3, secao `fichas` do registro, so o snapshot R2 da 373
desconta): mon_portao_que_morde, mon_odre_de_oleo, mon_fervente_de_ferrugem, mon_lencol_de_chamine.
- **Decisão do dono (04/11): `mon_odre_de_oleo` fica como exceção nominal.** Nas sementes 0–39 deu 56,5/53; na confirmação 40–119, 37,2/45,8; na soma das 120 sementes, `off` ≈ 43,6 %, fora da faixa. Pela revisão Sol (P2-2) isso não é variância: é efeito real da R1, porque a fuga dava margem a ele. A recalibração dele vai para um follow-up junto com `armador_de_fosso` e `escuta_do_sinal` (exceções da 394).
- **Follow-ups da revisão Sol (`handoffs/SPEC-395-sol-review.md`):**
  - P2-1: texto da §7 corrigido.
  - P2-4: o campo `arena` de fervente/lençol/odre em `_ajustes.yaml` mostra a leitura de antes da correção; fica para o follow-up.
  - P2-5: um ator sem arquétipo tabelado, com prioridade `absoluta` e dica "foge", ainda foge pelo legado `move afastar` (`conflict_orchestrator.py:702-705`). Hoje nenhuma criatura curada cai nesse caso; vira follow-up.
  - P2-6: a citação das 4 ids de `fichas` na §9 foi escrita pelo autor de eval; conteúdo conferido pelo coordenador.
- **Smoke de integracao (04/11, §6):** `docs/spec395/smoke.md`. Portao (3/10) atacou ate morrer, sem fuga; lacrador (5/16) fugiu na rodada 2 (`final_status: fugiu`). MockLLM, save editado so para pôr a criatura ferida (declarado no arquivo).
- **Revisão Sol rodada 2 (945dc8fd):** APPROVED_WITH_FOLLOWUPS. P2-7 (a guarda `ficha_vs_base` aceita qualquer chave não-fuga em vez de exigir a de `sempre`) fica de follow-up, junto com os outros P2.
