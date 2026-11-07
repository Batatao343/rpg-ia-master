# SPEC-400 — Follow-ups da 395: `absoluta` em saves, no legado e nas guardas

> **Status:** `done` (aprovada: dono, 07/11: "ok aprovado" D1–D5 nos defaults).
> **Criada:** 2026-11-07 · **Atualizada:** 2026-11-07
> **Épico:** SPEC-349 (bestiário) · **Depende de:** SPEC-395 `done`
> **Desbloqueia:** fechar P2-1, P2-4, P2-5 e P2-7 de `handoffs/SPEC-395-sol-review.md`
> **Risco:** `alto`. Muda a decisão de turno do inimigo (`enemy_declaration`) e a renormalização de perfil em saves com combate em curso. É combate e estado (AGENTS.md § Qualidade).
> **Evidência:** um teste vermelho na base para P2-1, P2-5 e P2-7, mais uma mutação M9 que precisa reprovar. P2-4 é só texto e se prova por comando (D4). O hash de `ensure_combat_sheet` fica idêntico para as 373 ids curadas (R5).
> **EXECUTOR_MODEL:** `Terra` (Sonnet) · **REVIEW_MODEL:** `Sol` (`spec-reviewer`, Opus) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true`, só para a R4 (D3). `tests/test_spec373_montagem.py` não está em `evals/protected-paths.txt` (as linhas 27–29 cobrem `test_spec373_artefatos.py`, `docs/spec373/base/eval` e o registro). Mas a `ficha_vs_base` é o oráculo R2 da 373, e quem mexe no produto (R1/R2) não mexe no oráculo na mesma tarefa.

## 1. Contexto & Objetivo

A 395 fez a prioridade `absoluta` deixar de herdar `flee`/`surrender` da tabela (`services/tactical_profile.py:569-570`). A revisão Sol deixou quatro resíduos pequenos. A recalibração de odre, armador e escuta está fora: o dono decidiu que não precisa.
- **P2-1.** `ensure_combat_sheet` grava o perfil normalizado no ator (`services/conflict_orchestrator.py:132-134`). Na remontagem, o `flee` que já estava gravado passa no `if priority.get("action_key") in TACTICAL_ACTION_KEYS: continue` (`tactical_profile.py:565-566`) como se fosse explícito. Um inimigo montado antes da 395 continua fugindo pelo resto da vida.
- **P2-5.** Sem arquétipo tabelado, `normalize_runtime_profile` devolve o perfil sem chave (`:557-559`). Aí `enemy_declaration` usa `legacy_action_key(action_hint)` (`conflict_orchestrator.py:650`), e uma dica "foge" vira `move afastar` (`:699-702`) mesmo em prioridade `absoluta`. `pick_action` já devolve `resistance` (`tactical_profile.py:396`).
- **P2-7.** `ficha_vs_base` (`tests/test_spec373_montagem.py:43-62`) aceita qualquer chave não-fuga na `absoluta`. A mutação M9 (odre `flank` em vez de `control`) passa. O assert do bestiário curado (`tests/test_tactical_archetypes_runtime.py:529-532`) também só barra `flee`/`surrender`.
- **P2-4.** O campo `arena` de fervente (`data/bestiario/mecanica/_ajustes.yaml:633`), lençol (`:779`) e odre (`:890`) ainda mostra 74/81, 69/74 e 68/76, a leitura de antes da 395. A leitura final é 58/68, 60/60 e 56/53 (`docs/spec395/arena-final.md:8,11,14`).

**Objetivo.** `absoluta` não foge por nenhum caminho de tabela nem pelo legado, inclusive em save antigo. As guardas exigem a chave certa, e os registros do `_ajustes.yaml` mostram a leitura atual.

## 2. Requisitos

- **R1 — Remontagem (P2-1).** Em `normalize_runtime_profile`, uma prioridade `absoluta` cuja `action_key` está em `_NO_RETREAT_ACTIONS` e é igual ao valor cru da tabela para aquele gatilho (`actions.get(trigger, fallback)`, antes da regra da 395) é tratada como vinda da tabela e recebe a chave da R1 da 395. Isso deixa `normalize(normalize(p)) == normalize(p)` para todo perfil. Fora desse caso, uma chave explícita continua tendo precedência (D1).
- **R2 — Legado (P2-5).** Quando a decisão não traz `action_key` e `legacy_action_key` daria `flee`/`surrender` numa prioridade `absoluta`, a ação é `attack`. A regra mora em `tactical_profile.py`, num helper (ex.: `resolve_action_key(decision) -> str`), e substitui a `:650` linha por linha. O `conflict_orchestrator.py` (teto de 3283 linhas) e o `enemy_declaration` (teto de 157, `tests/size_budget.json:28,131`) não crescem.
- **R3 — Assert curado (P2-7).** Em `test_todo_bestiario_curado_normaliza_para_action_keys_fechadas`, toda `absoluta` cujo gatilho a tabela leva a fuga ou rendição sai com `_ENEMY_ARCHETYPE_ACTIONS[arq].get("sempre", "attack")`, ou `attack` se esse valor também for fuga ou rendição.
- **R4 — `ficha_vs_base` (P2-7, autor de eval).** A guarda exige essa mesma chave esperada, calculada pela tabela a partir de `sheet["arquetipo"]` e não por `normalize_runtime_profile` (D2). A M9 tem de reprovar. M0, M7, M8 e M10 da rodada 2 continuam como estão.
- **R5 — Equivalência.** `docs/spec394/snapshot.py` antes e depois dá hashes `off` e `on` idênticos para todas as ids curadas. O motivo: o bestiário não tem `action_key` explícito (`data/bestiary.json`, 0 ocorrências), então R1 e R2 não mudam ficha curada. A única exceção prevista é a R6, que não entra em `bestiary.json`.
- **R6 — Leituras (P2-4).** Só o campo `arena` das 3 entradas muda, para `L3|off 58% | L3|on 68%`, `L3|off 60% | L3|on 60%` e `L3|off 56% | L3|on 53%`, com o sufixo `(SPEC-395 pós-R1, 40 seeds)`. O odre ganha também `; 40-119: 37%/46%, exceção nominal` (D5). Nenhum dial muda: `ids_com_dial_mudado` ignora `arena` (`tests/test_spec373_artefatos.py:274`).

### Fora de escopo

- A recalibração de `odre_de_oleo`, `armador_de_fosso` e `escuta_do_sinal` (decisão do dono).
- A tabela `_ENEMY_ARCHETYPE_ACTIONS`, `resistente`/`autonoma`, os perfis de NPC/companheiro e o texto das fichas (lençol).
- P2-2, P2-3 e P2-6 (já fechados ou registrados na 395 §9), `arena.py`, `calibrar.py`, `test_bestiario_calibragem.py`, `test_spec373_artefatos.py` e `evals/`.
- Um campo novo de origem (`action_key_source`) gravado em toda prioridade. Ele muda o hash das 373 ids e não corrige save antigo (D1).

## 3. Design técnico

- `services/tactical_profile.py`: a regra R1 fica dentro de `normalize_runtime_profile` (≤ 6 linhas), e a função nova `resolve_action_key` (≤ 15) cumpre a R2. Não entra constante nova além de `_NO_RETREAT_ACTIONS`.
- `services/conflict_orchestrator.py:650`: a expressão passa a chamar o helper. O saldo de linhas é 0.
- Os testes ficam em `tests/test_tactical_archetypes_runtime.py`, com docstring "SPEC-400", e usam os helpers `_actor`/`_scene`/`_player` do arquivo:
  - `test_absoluta_remontada_nao_mantem_fuga_da_tabela`: um perfil abissal com `muito_ferido`/`absoluta`/`action_key: "flee"` já gravado vira `attack` na renormalização. Um `flee` gravado numa `flexivel` continua `flee`.
  - `test_portao_salvo_antes_da_395_nao_foge`: a ficha do portão com o `flee` reinjetado na `absoluta` passa por `ensure_combat_sheet` e depois por `enemy_declaration` ferido, e não sai nem `maneuver flee` nem `move`.
  - `test_legado_absoluta_sem_arquetipo_nao_foge`: um ator com `arquetipo` fora da tabela e prioridade `absoluta` com dica "foge" não declara `move`. Com `flexivel`, a mesma dica dá `move afastar`.
  - Assert R3 no teste curado.
- A R4 vai em `tests/test_spec373_montagem.py`: `ficha_vs_base` e um caso novo em `test_ficha_vs_base_known_good_e_bad` (conjurador com `flank` na `absoluta` → erro).

## 4. Plano passo a passo

1. **Base.** `snapshot.py --out <scratch>/base-snapshot.json` na `main`.
2. **Testes do produto.** Escrever os 3 testes novos e o assert R3, e commitá-los sozinhos. Os 3 testes ficam vermelhos (o assert R3 é verde na base e se prova pela M9 na revisão). Rodar `bash scripts/dev/pt.sh tests/test_tactical_archetypes_runtime.py`.
3. **Correção.** Aplicar R1 e R2. Rodar com `-n 2` `test_tactical_archetypes_runtime`, `test_conflito_tatica`, `test_enemy_decks`, `test_spec349_mecanica`, `test_size_budget` e `test_spec373_montagem`: tudo verde.
4. **R5.** Rodar `snapshot.py --out <scratch>/fix-snapshot.json` e conferir que é idêntico à base, id por id.
5. **R4 (autor de eval, commit separado).** A prova de vermelho é a mutação M9: ela passa na base `fca76cda` e reprova depois de `f7fdac05` (o caso novo não é o vermelho). `ficha_vs_base` passa a exigir a chave esperada.
6. **R6.** Editar o texto das 3 entradas. Rodar `test_spec373_artefatos` e `test_bestiario_calibragem` (verdes, sem diff) e `validate_content.py`, que precisa terminar sem erros.

## 5. Critérios de aceite

- [x] Os 3 testes novos falham na base e passam depois, em commit de testes separado
- [x] A M9 reprova `ficha_vs_base`, e M0/M7/M8/M10 se comportam como na rodada 2
- [x] R5: o snapshot `off`/`on` tem as 373 ids idênticas antes e depois
- [x] R6: só o campo `arena` das 3 ids muda (`git diff` do `_ajustes.yaml` mexe em 3 linhas) e `bestiary.json` fica sem diff
- [x] `git diff --exit-code main --` limpo em `arena.py`, `calibrar.py`, `test_bestiario_calibragem.py`, `test_spec373_artefatos.py` e `evals/`
- [x] `test_size_budget` verde e `uv run pytest` verde (coordenador, no pouso)
- [x] Saves antigos carregam, e um portão montado antes da 395 deixa de fugir na remontagem

## 6. Smoke test

Não há LLM nesse caminho: as rodadas de Cartas e a declaração do inimigo são determinísticas. O smoke é de integração local, com MockLLM e `RPG_ENEMY_DECKS=on`, no padrão de `docs/spec395/smoke.md`:
1. Abrir um save com combate contra `mon_portao_que_morde`, com a `absoluta` editada para `action_key: "flee"` (simula um save de antes da 395, e isso fica declarado no arquivo). Recarregar e levar o portão a ferido: ele ataca até o fim e o log não mostra fuga.
2. Fazer o mesmo com `mon_lacrador_de_saidas` (`flexivel`): ele ainda foge.
3. Registrar o resultado em `docs/spec400/smoke.md`.

## 7. Riscos & compatibilidade

- **Saves.** A R1 só reescreve `flee`/`surrender` em `absoluta` quando o valor coincide com o da tabela. Nos outros casos, o save fica como está.
- **`creature_gen`/`creature_variants`.** Hoje caem em arquétipos tabelados (`creature_gen.py:1160`, o default é `equilibrado`). A R2 cobre qualquer exceção futura.
- **MockLLM, quota e latência:** nenhum impacto.

## 8. Decisões abertas (default entre parênteses)

- **D1 — Como reconhecer chave da tabela.** (**Pela igualdade com o valor cru da tabela, R1**: não muda nenhum hash e corrige saves que já existem.) Alternativa: gravar `action_key_source: "tabela"` em cada prioridade. Isso muda o hash das 373 ids e obriga a refazer `docs/spec373/base/snapshot-off.json` com autor de eval. E não corrige save antigo, que não tem a marca. Efeito colateral do default: um `flee` explícito numa `absoluta`, igual ao da tabela, também vira ataque. Esse dado é incoerente (`content_validator.py:977` lê `absoluta` como não-fuga), e hoje nenhuma ficha o tem.
- **D2 — Oráculo da R4.** (**A tabela**, independente do produto.) Alternativa: `normalize_runtime_profile` sobre a ficha crua. Nesse caso o oráculo fica circular, porque a guarda passaria a usar a mesma função que deveria checar.
- **D3 — Quem escreve a R4.** (**Um autor de eval, em commit separado**.) Alternativa: o próprio executor, já que o arquivo não é protegido. Só é aceitável porque a mudança aperta a guarda e não a afrouxa.
- **D4 — Prova da R6.** (**Comando de conferência e portões da 373 verdes, sem teste permanente.**) Um teste que fixasse o texto quebraria na próxima vez que o `calibrar.py` reescrevesse o campo (`calibrar.py:143,147,183`).
- **D5 — Odre com a confirmação 40–119 no texto.** (**Sim**: a próxima calibração precisa ver que ele está fora da faixa.)

## 9. Registro de execução (07/11)

- Commits de produto: testes vermelhos, depois R1 (`normalize_runtime_profile`) e R2 (`resolve_action_key`); R6 no `_ajustes.yaml`; smoke em `docs/spec400/smoke.md`.
- Passo 5: a prova de vermelho do P2-7 é a M9 (passa em `fca76cda`, reprova depois de `f7fdac05`), não o caso novo de `test_ficha_vs_base_known_good_e_bad`.
- Desvio R6: o texto do odre usa `40-119 = 37%/46%, exceção nominal` (em vez de `40-119: 37%/46%`), porque `: ` dentro de escalar YAML sem aspas quebra o parse do arquivo.
- R5: snapshot `off`/`on` idêntico (373 ids) antes e depois, inclusive após o R6.
- Smoke feito em processo (sem uvicorn); ver o arquivo.
- **Revisão Sol (07/11, `handoffs/SPEC-400-sol-review.md`, 8434e02c): APPROVED.**
  - N-2: o assert R3 do bestiário curado era do executor no plano. Saiu no commit do autor de eval (f7fdac05), deixando a guarda mais estrita.
  - N-1 (opcional, follow-up): o assert R3 usa o gatilho cru, mas o produto normaliza o gatilho.
