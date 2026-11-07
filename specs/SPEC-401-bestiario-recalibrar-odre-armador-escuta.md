# SPEC-401 — Bestiário: recalibrar odre, armador e escuta; fechar os P2 de motor da 395

> **Status:** `approved` — dono, 07/11: "aprovo 401"; D1–D3 nos defaults.
> **Criada:** 2026-11-07 · **Atualizada:** 2026-11-07
> **Épico:** SPEC-349 (bestiário) · SPEC-327 (Cartas)
> **Depende de:** SPEC-394 `done` (exceções nominais de armador e escuta), SPEC-395 `done` (exceção nominal do odre; revisão Sol `handoffs/SPEC-395-sol-review.md`), SPEC-373 `done` (`arena.py` congelado)
> **Desbloqueia:** veredito cheio do bestiário sem as 3 exceções nominais; `RPG_ENEMY_DECKS=on` com menos ressalvas
> **Risco:** `alto`. As etapas 1 e 2 mudam o motor de combate (`services/tactical_profile.py`, `services/conflict_orchestrator.py`). A etapa 3 sozinha seria `médio`.
> **Evidência:** a etapa 1 tem teste que falha antes: um ator sem arquétipo tabelado, com prioridade `absoluta` e dica "foge", declara `move afastar`. A etapa 2 também: um perfil já materializado com `action_key: flee` numa prioridade `absoluta` continua fugindo depois da remontagem. Na etapa 3, `arena.py` grava `ok` para os 3 ids (sementes 0–39) e a confirmação 40–119 entra na faixa. Equivalência: os hashes de `ensure_combat_sheet` (`off`/`on`) das demais criaturas curadas não mudam.
> **EXECUTOR_MODEL:** `Terra` (Sonnet) · **REVIEW_MODEL:** `Sol` (`spec-reviewer`, Opus), outro agente · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`. O oráculo é o `veredito` de `scripts/bestiario/arena.py` (faixa 45–85 %), que segue congelado. O P2-3/P2-7 da 395, sobre a guarda `ficha_vs_base` em `tests/test_spec373_montagem.py`, é eval e fica fora (§2).

---

## 1. Contexto & Objetivo

Três criaturas curadas seguem fora da faixa 45–85 % do `arena.py` como exceção nominal registrada pelo dono:

| id | região | leitura registrada | origem |
|---|---|---|---|
| `mon_odre_de_oleo` | — | 0–39: 56,5/53 · 40–119: 37,2/45,8 · soma 120: `off` ≈ 43,6 % | SPEC-395 §9 (decisão do dono 04/11). A R1 tirou a fuga, que dava margem a ele (P2-2 da revisão Sol). |
| `mon_armador_de_fosso` | montanhas_afiadas | 49,5/86 · conf. 41,7/79,5 | SPEC-394 §9 (D2). Os dials são parciais, e o `off` sobreajustou. |
| `mon_escuta_do_sinal` | skallgard | 41,5/87,5 · conf. 42,7/82 | SPEC-394 §9 (D2). O `on` fica 36–46 pp acima do `off`. |

A 394 parou nelas porque os dials (`corpo`, `dano`, `forca`, `sig`) movem os dois modos juntos. Ela deixou a recalibração para depois da 395. A 395 já pousou, e a revisão Sol dela deixou dois furos de motor na mesma regra ("`absoluta` não foge"):

- **P2-5.** Um ator sem arquétipo tabelado, com prioridade `absoluta` e dica "foge/recua", ainda cai em `tp.legacy_action_key` → `flee` → `move afastar` (`services/conflict_orchestrator.py:650`, `:702-705`). `normalize_runtime_profile` sai cedo quando não há arquétipo na tabela (`services/tactical_profile.py:557-558`), e por isso o override da 395 (`:569-570`) não roda. Os curados estão cobertos por teste, mas os gerados por `creature_gen`/`creature_variants` não.
- **P2-1.** Um perfil já materializado mantém o `flee`. `ensure_combat_sheet` grava o perfil normalizado em `actor["tactical_profile"]`. Na remontagem, `action_key in TACTICAL_ACTION_KEYS` conta como explícito (`tactical_profile.py:565`) e pula o override. Num save com o inimigo montado antes da 395, ele foge pelo resto da vida daquele ator.

A revisão também pediu atualizar as leituras `arena:` antigas de `_ajustes.yaml` (P2-4: fervente, lençol, odre).

**Objetivo:** fazer "`absoluta` não foge" valer em todos os caminhos, depois recalibrar as 3 criaturas sobre o motor corrigido e atualizar as leituras velhas. O motor vem primeiro porque a etapa 1/2 pode mudar o `off` delas.

## 2. Requisitos

- **R1 — Legado sem arquétipo (P2-5).** Quando a prioridade escolhida por `tp.pick_action` é `absoluta` e o resultado (explícito ou de `legacy_action_key`) está em `_NO_RETREAT_ACTIONS`, o ator declara ataque no alvo canônico. Se não houver alvo, declara `pass`. Nunca declara `tactic flee` nem `move afastar`. Isso vale com ou sem arquétipo tabelado.
- **R2 — Perfil já materializado (P2-1).** A remontagem (`ensure_combat_sheet` → `normalize_runtime_profile`) de um perfil persistido com `action_key ∈ {flee, surrender}` numa prioridade `absoluta` produz a mesma chave que uma montagem do zero produziria (D1).
- **R3 — Sem efeito colateral.** Prioridades não `absoluta` mantêm o comportamento de hoje, incluindo fuga/rendição tabelada. Os hashes de `ensure_combat_sheet` (`off`/`on`) das criaturas curadas fora dos 3 ids ficam iguais aos de `main` antes desta spec. Se R1/R2 mudarem algum hash curado, o executor para e reporta: é sinal de que a 395 não cobria um caso.
- **R4 — Inventário dos gerados.** Contar quantos atores de `creature_gen`/`creature_variants`, amostrados de forma determinística (sementes fixas, N ≥ 200), caíam no caminho do R1 antes da correção. O número vai para `docs/spec401/RELATORIO.md`. Não é portão.
- **R5 — Recalibração.** Ajustar os dials de `data/bestiario/mecanica/_ajustes.yaml` só dos 3 ids, pelo `scripts/bestiario/calibrar.py`. A meta: as duas células L3 em 45–85 % nas sementes 0–39 (`ok` do `arena.py`) e também na confirmação 40–119, rodada uma vez e sem reajuste. Se um id não fechar em 2 execuções do `calibrar.py`, fica o melhor ajuste visto, ele segue como exceção nominal com a leitura nova e a §9 registra o motivo (D2).
- **R6 — Leituras `arena:` (P2-4).** Os campos `arena:` dos 3 ids e de `mon_fervente_de_ferrugem`/`mon_lencol_de_chamine` passam a trazer a leitura atual. Nos dois últimos, os dials não mudam. Confirmar que `ids_com_dial_mudado` (`tests/test_spec373_artefatos.py:277`) não conta mudança só de `arena:`.
- **R7 — Texto da 395.** Corrigir na §7 da SPEC-395 o trecho "mantém o `flee` até a próxima montagem", que fica falso depois do R2, com uma nota "corrigido pela SPEC-401".

### Fora de escopo

- Avaliador, faixa, sementes, `arena.py`, `calibrar.py`, `evals/` e `tests/test_spec373_montagem.py`. O P2-3/P2-7 (guarda `ficha_vs_base` exigir a chave de `sempre`) fica para uma spec de eval própria, com o autor de eval.
- Criar dials novos ou mexer em Carta/mecânica da criatura. Se a D2 apontar que precisa, abre-se outra spec.
- Outras exceções nominais, como o chefe hospede/escavador (D-373).
- Ligar flag no staging.

## 3. Design técnico

- **`services/conflict_orchestrator.py`** (perto de `:650` e `:695-705`): depois de calcular `action_key`, se `decision` vier de prioridade `absoluta` e `action_key in tp._NO_RETREAT_ACTIONS`, troque por `"attack"`. O ramo `target is None → pass` já existe. Para isso, `tp.pick_action` precisa expor a `resistance` da prioridade escolhida, se ainda não expõe. Conferir antes, sem duplicar helper (`Grep "def pick_action"`).
- **`services/tactical_profile.py`** (`normalize_runtime_profile`, `:555-570`): com a D1 no default, aplicar o override de `_NO_RETREAT_ACTIONS` também às prioridades que já têm `action_key` explícito, e também quando não há arquétipo tabelado. Para isso, o `if not actions: return normalized` tem que passar pelo laço de override, com `fallback = "attack"`.
- **`data/bestiario/mecanica/_ajustes.yaml`**: dials dos 3 ids e `arena:` dos 5 ids.
- **Novos:** `tests/test_spec401_absoluta_legado.py` e `docs/spec401/{RELATORIO.md, arena-final.json, confirmacao-40-119.json}`.
- O arquivo `conflict_orchestrator.py` está acima de 1.000 linhas e não pode crescer (`tests/test_size_budget.py`). A lógica nova vai num helper em `tactical_profile.py`, e o orquestrador só chama esse helper.

## 4. Plano passo a passo

### Etapa 0 — Leitura de base

`arena.py` dos 3 ids em `main` (sementes 0–39), gravada em `docs/spec401/base.json`, mais os hashes `off`/`on` de todas as curadas. É o "antes" de R3 e de R5.

### Etapa 1 — R1 (TDD)

1. **Testes:** `test_absoluta_sem_arquetipo_nao_recua` monta um ator sem arquétipo tabelado, com prioridade `absoluta` e `action_hint` "foge", e afirma que a declaração não é `move afastar` nem `tactic flee`. `test_nao_absoluta_sem_arquetipo_segue_recuando` faz o mesmo com resistência comum e afirma que o `move afastar` legado continua.
2. **Implementação:** o helper e a chamada da §3.
3. **Verificação:** os testes do escopo (`tests/test_spec395*`, `tests/test_spec401*`, `tests/test_tactical*`), com `-n 2` no máximo.

### Etapa 2 — R2 (TDD)

1. **Testes:** `test_remontagem_perfil_materializado_flee_absoluta` grava um perfil com `action_key: flee` em prioridade `absoluta`, chama `ensure_combat_sheet` de novo e afirma que a chave é igual à de uma montagem do zero. `test_save_pre_395_carrega` carrega um save com o perfil antigo e afirma que carrega sem erro e já sem `flee`.
2. **Implementação:** a mudança em `normalize_runtime_profile`.
3. **Verificação:** os mesmos testes, mais o R3: hashes das curadas iguais aos da Etapa 0, fora os 3 ids.

### Etapa 3 — R4, R5 e R6

1. Inventário R4.
2. `calibrar.py` nos 3 ids, no máximo 2 execuções por id, seguido de `arena.py` 0–39 (`arena-final.json`) e da confirmação 40–119 uma vez.
3. `tests/test_spec401_calibragem.py` lê o `ok` gravado pelo `arena.py` para os ids fechados e confere os hashes das outras curadas (o mesmo padrão de `tests/test_bestiario_calibragem.py`).
4. Atualizar os campos `arena:` (R6) e a §7 da 395 (R7).

## 5. Critérios de aceite

- [ ] R1 e R2 com testes que falham em `main` e passam depois.
- [ ] R3: hashes das curadas fora dos 3 ids iguais aos da Etapa 0.
- [ ] R4: número no `RELATORIO.md`.
- [ ] R5: os 3 ids `ok` em 0–39 e na confirmação, ou exceção nominal com leitura nova e motivo (D2).
- [ ] R6 e R7 feitos; `ids_com_dial_mudado` não conta `arena:`.
- [ ] `test_size_budget` verde; ruff limpo.
- [ ] `uv run pytest` verde (suíte completa offline, no pouso).
- [ ] Saves antigos carregam (R2).
- [ ] Revisão `spec-reviewer` APPROVED.

## 6. Smoke test com LLM real

As rodadas do baralho não usam LLM (decisão do dono), então o smoke é local, com MockLLM:

1. Um combate contra cada um dos 3 ids pela API local (`/game/new` → `/game/action` até o fecho), sem 500 e com desfecho coerente.
2. Um combate contra uma criatura gerada que caía no R1 (do inventário R4), em que o inimigo não recua.
3. Um save antigo com inimigo montado antes da 395, carregado e jogado por 3 rodadas, em que ele não foge.

## 7. Riscos & compatibilidade

- **Saves:** o R2 muda o comportamento de atores já montados em saves antigos, que deixam de fugir. É o comportamento pretendido pela 395. O formato do save não muda.
- **Balanço:** o R1 pode mexer no `off` de criaturas geradas. Como o `arena.py` só mede curadas, o R4 dá a ordem de grandeza.
- **MockLLM/FallbackLLM:** não se aplica, não há LLM no caminho.
- **Quota/latência:** nenhuma.

## 8. Decisões do dono

Defaults em negrito. O executor segue o default se o dono não responder.

- **D1 — Chave `flee` explícita em `absoluta`.** (**Sempre sobrescrever**: `absoluta` nunca foge, venha a chave da tabela ou explícita; hoje o bestiário não tem `action_key` explícito, conforme a P2-7.) Alternativa: marcar a origem (`action_key_source: "table"`) e só refazer as que vieram da tabela, preservando a fuga autoral explícita.
- **D2 — Id que não fecha.** (**Melhor ajuste visto + exceção nominal com a leitura nova**, como a 394.) Alternativa: abrir spec de Carta/mecânica para a criatura.
- **D3 — Ordem.** (**Motor (R1/R2) antes da recalibração.**) Alternativa: recalibrar primeiro e corrigir o motor numa spec separada. É mais rápido, mas a calibração pode ficar velha.

## 9. Resultado

(preencher no fechamento)
