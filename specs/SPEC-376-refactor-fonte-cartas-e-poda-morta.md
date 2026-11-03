# SPEC-376 — Refatoração: fonte única de Cartas/classes (geradores-armadilha) e poda de scripts e código sem chamador

> **Status:** `draft`
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** auditoria de qualidade de 03/11 ([relatório](../docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md)): §3 R1, §4.2 itens 4 e 6, §4.3 item 5, §4.4 itens 3–4; plano da onda §6 (regras **W1–W8**, ordem §6.3, itens que saíram §6.4). Letra **B** do §5 mais a parte "sem chamador" de D/§4.
> **Depende de:** nenhuma spec para começar (§6.3: "já"). Cada etapa obedece à **W1 revisada** (R1). A SPEC-368 já pousou (`dff4c27c`, `061c330b`), então a C5 (opcional, D5) não espera mais por ela, só pela W1. A etapa A4 (`_meta` dos JSON de classe) espera a SPEC-367, que commita **direto na `main`** (`b278f6af`, `4b03a430`), e a SPEC-369 (`draft`, balanço de Cartas). A etapa A3 espera a SPEC-374, que hoje trava `docs/guias/AUTORIA.md`. A C2 tem ordem com a SPEC-377 item 1 (mesmo `services/world_engine.py`, R19).
> **Desbloqueia:** SPEC-378 (helpers comuns), que começa depois de 376/377 (§6.3).
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma etapa por vez (**W6**) · **REVIEW_MODEL:** `Sol` (`spec-reviewer`, Opus), que refaz por conta própria o W2 de pelo menos um item de C e a medição da Etapa 0 de pelo menos um gerador (**W7**) · **REVIEW_REQUIRED:** `true`. Motivo: apaga fonte de dados e código do motor, e a SPEC-273 já foi julgada UNSAFE por isso uma vez.
> **EVAL_AUTHORING_REQUIRED:** `false`. Nenhum evaluator, expected, dataset, baseline ou caminho protegido de `evals/` é tocado (**W5**).

Rótulos: **[F]** fato no source (checkout principal, `main` em `5fd2e920`, lido em 03/11; a revisão independente reconferiu tudo em `b278f6af`, [handoff](../handoffs/SPEC-376-independent-review.md)) · **[H]** hipótese com evidência, que a Etapa 0 ou o primeiro teste confirma ou derruba · **[D]** decisão do dono (§8).

---

## 1. Contexto & Objetivo

Três tipos de peso morto, com riscos diferentes.

**A. Geradores-armadilha.** `scripts/gen_cards_v4.py` (2.553 linhas) e `scripts/gen_classes_v2.py`
(1.623 linhas) regravam do zero arquivos que hoje são curados à mão. **[F]** O gerador de Cartas grava
`data/cards/{devoto,sangromante,corruptor,arcanista,medico}.json` e `virtude_sugeridas.json`
(`scripts/gen_cards_v4.py:2511-2533`). Ele não conhece `momento`, `raridade` nem `apex` (0 ocorrências no
script), mas esses campos existem nos 5 arquivos que ele sobrescreve: 30 a 31 `"momento"` em **cada** um
(arcanista 31, corruptor 31, sangromante 31, devoto 30, medico 30). Mesmo assim, `docs/design/CARTAS.md:4-6,105-106`
manda "editar a fonte em `gen_cards_v4.py`" e regerar. **[F]** O gerador de classes não tem `main` nem
guarda: grava `data/player_abilities.json` e `data/classes.json` assim que é importado ou executado
(`scripts/gen_classes_v2.py:1605-1608`). O `player_abilities.json` foi removido no cutover, e
`tests/test_cutover_audit.py:78` exige que ele **não exista**. `docs/design/CLASSES.md:132` já manda não
rodar esse gerador. A SPEC-273 (revisão de 18/10, `specs/SPEC-273-scripts-geradores-avulsos.md:61-77`) julgou
UNSAFE apagar geradores porque eram uma pipeline obrigatória
(`gen_classes_v2 → gen_cards_v4 → gen_tiers_5_plus`, R2). Por isso esta spec **não apaga sem prova**: a
Etapa 0 roda cada gerador num worktree descartável e mede a deriva. Gerador sem deriva continua como fonte.
Gerador com deriva destrutiva sai, e `data/` vira a fonte declarada.

**B. Scripts de evidência já executada.** São 11 scripts (1.915 linhas medidas, não as ~2.000 nem os "17"
da auditoria). Nem todos são órfãos: a verificação desta spec achou 4 com uso vivo ou pendente (§2.B).

**C. Código sem chamador de produção.** São funções substituídas, leitores de API que nunca ganharam
consumidor, helpers que nunca foram chamados e stubs `try/except ImportError` para módulos do próprio repo.
É refatoração pura (**W2**, **W3**). Ficam de fora tudo o que a SPEC-272 decidiu manter (tabela "(c) manter",
`specs/SPEC-272-capacidades-conflito-so-testadas.md:120-131`), `services/gameplay_oracles.py`,
`cards.set_deck` (vai para a SPEC-384), `law.daily_tick` (vai para a SPEC-377) e qualquer coisa em `evals/`.

Princípio: o source é a verdade e o git guarda o histórico (**W8**, nada de reescrever). Apagar é
`git rm` num commit revertível sozinho (**W4**).

## 2. Requisitos

### Transversais

- **R1 — W1 revisada antes de cada etapa.** O executor roda o script da **W1 revisada** (auditoria §6.2) com
  a lista de arquivos da etapa (§4). O script junta três fontes: (1) branches vivas (à frente da `main` e com
  commit nos últimos 7 dias); (2) `git -C <wt> status --porcelain` de **todos** os worktrees, inclusive o
  checkout principal; (3) `git log --since=2.days --name-only main`, que cobre specs como a 367, que commitam
  direto na `main`. O executor também roda `git log --oneline <sha da main no início da etapa>..main --
  <arquivos>`, que tem que sair vazio na hora do commit. A saída vai para o log da etapa, em
  `docs/spec376/README.md`. Se a interseção não for vazia, a etapa **espera**: não começa e não "resolve no
  rebase". As outras etapas podem seguir. As branches paradas que a W1 exclui (ex.: `spec-349-pre-sync`, 401
  arquivos, 30 h sem commit) são listadas no log para o coordenador arquivar.
- **R2 — W4.** Um commit por mudança mecânica: um gerador, um grupo de scripts ou uma função com seus testes.
  Cada commit tem que poder ser revertido sozinho com `git revert <sha>`.
- **R3 — Re-grep antes de apagar.** Para cada símbolo ou arquivo, rodar `git grep -n -w <nome>` no repo
  inteiro, incluindo `.github/`, `.claude/`, `docs/`, `tests/`, `evals/`, `playtest/`, `config/`, `*.yaml`,
  `*.json`, `*.toml` e `*.sh`. O `rg` pula diretórios ocultos por padrão, então para `.github/` e `.claude/`
  use `git grep` ou `rg --hidden`. Também procurar o nome como string (`"nome"`, `'nome'`), em `getattr`, em
  alvo de `monkeypatch` e em registros (`HANDLED_KINDS`, `SURVIVING_FUNCTIONS`). A saída vai para
  `docs/spec376/README.md`. Qualquer referência nova fora de `specs/`, `handoffs/`, `docs/specNNN/` e
  `docs/historico/` ⇒ **não apaga** e registra. Os hits em `project_index/` são esperados: o índice é
  regenerado no `wt.sh sync` e não bloqueia.
- **R4 — Adendo na spec de origem** (precedente da SPEC-272 R5). Toda função apagada que foi requisito de uma
  spec `done` ganha uma linha datada na spec de origem: "removida pela SPEC-376 (sem chamador)". Os casos
  estão listados por item no §2.C.

### A. Geradores-armadilha

- **R5 — Etapa 0: medir a deriva num diretório temporário fora de qualquer repo.** Revisão P0-1: `RPG_ROOT`
  **não** protege nada. `scripts/dev/env.sh:6,17` sobrescreve `RPG_ROOT` com o toplevel git do cwd e faz `cd`
  para lá, e o cwd do subagente volta ao checkout principal a cada chamada de Bash. O `gen_classes_v2` grava
  **ao ser importado** (`:1605-1608`). Por isso a Etapa 0 **não usa** `py.sh`, `uv run` nem worktree git
  para rodar geradores. O procedimento é:
  1. **Snapshot antes**, no checkout principal: `git status --porcelain -- data/` e `git stash list`, gravados
     no log. `$MAIN` é o caminho do checkout principal.
  2. **Diretório temporário** `$TMP/spec376-deriva/` (scratchpad, fora do OneDrive e de qualquer repo), com
     `data/` copiado do `git archive main data` (não do disco do principal) e as **cópias** dos 4 scripts em
     `$TMP/spec376-deriva/scripts/`. O `gen_tiers_5_plus` resolve a raiz por `Path(__file__).parents[1]`
     (`:15-17`); o `migrate_bestiary_v4` faz `import gamedata`, então copiar também `gamedata.py` e o que ele
     importa, ou rodar o `migrate` só no modo (b) abaixo. Faça uma cópia limpa (`data.orig/`) para comparar.
  3. **Cada comando numa única chamada de Bash**, com `cd "$TMP/spec376-deriva" && test ! -d .git &&
     RPG_ROOT="$PWD" "$MAIN/.venv/Scripts/python.exe" -I scripts/<gerador>.py …`. Os geradores de Cartas e
     classes só importam `json`/`os`. Depois de cada rodada, `git diff --no-index --stat data.orig/ data/` e as
     contagens do R6.
  4. **Medições (i), cada gerador sozinho**, partindo de `data/` restaurado de `data.orig/`:
     `gen_cards_v4.py`; `gen_classes_v2.py`; `gen_tiers_5_plus.py` (default `--check`, só relatório,
     `:3-6,233-311`); `migrate_bestiary_v4.py` (só análise, R11).
  5. **Medição (ii), a cadeia completa** documentada na SPEC-273 R2, na ordem e partindo de `data.orig/`:
     `gen_classes_v2.py` → `gen_cards_v4.py` → `gen_tiers_5_plus.py --write`. O `--write` só é permitido
     **aqui**, no diretório temporário (revisão P1-1).
  6. **Testes que ficariam vermelhos** (revisão P2-4): por leitura, registrar as asserções que dependem dos
     campos ou arquivos perdidos (no mínimo `tests/test_cutover_audit.py:78` para o `player_abilities.json` e
     as de `momento`/`raridade` em `tests/test_conflito_autoria_cartas.py`). Opcionalmente, copiar o `data/`
     da cadeia (ii) para dentro de um worktree descartável e rodar lá
     `tests/test_cutover_audit.py tests/test_conflito_autoria_cartas.py -q` (sem `-n`), com
     `cd "$WT" && test "$(git rev-parse --show-toplevel)" = "$WT" && …` na **mesma** chamada.
  7. **Snapshot depois** no principal, igual ao do item 1 (assert do log). Apagar `$TMP/spec376-deriva/`.
- **R6 — `docs/spec376/deriva.md`.** Uma seção por medição (i) e uma para a cadeia (ii), cada uma com o
  comando, o `diff --stat` e, para cada arquivo escrito, as Cartas (ou classes) antes e depois e os campos
  removidos com contagem. A lista mínima de campos tem dois grupos:
  - **"da cadeia"**, que o `gen_tiers_5_plus --write` devolve (`:248-288`): `tier`, `level_req`, `apex`,
    `late_entropy_curve`, `playstyle`, `tradeoff` e `preview_card_ids`;
  - **"curados fora da cadeia"**: `momento`, `raridade`, `onda`, `descricao`, `contrapartida`,
    `vitalidade_bonus`, qualquer Carta ou classe a mais ou a menos e arquivos recriados (`player_abilities.json`).

  **O veredito sai da cadeia (ii)**, gerador a gerador. Um campo que a cadeia devolve não conta como
  destrutivo, porque esse foi o erro que tornou a SPEC-273 UNSAFE. As medições (i) são só contexto.
  - **Diff da cadeia vazio**, ou só cosmético (ordem de chaves, espaço, `_meta`): o gerador **ainda é
    fonte**. Não apaga; só corrige a doc para apontar a ordem correta.
  - **A cadeia remove campo "curado fora da cadeia", Carta ou classe, ou recria arquivo removido**: o
    gerador responsável sai (R7). A atribuição é feita pelas medições (i).
- **R7 — Apagar o gerador com deriva destrutiva** (só com o veredito do R6 e a D1):
  `git rm scripts/gen_cards_v4.py` e/ou `git rm scripts/gen_classes_v2.py`, em commits separados. **[F]**
  Nenhum teste nem módulo importa os dois. Os únicos hits fora de `specs/`, `handoffs/` e `docs/` são o
  docstring `tests/test_conflito_autoria_cartas.py:3-4`, o `_meta` dos 5 JSON de classe e o `project_index/`
  (gerado, R3).
- **R8 — Docs passam a declarar `data/` como fonte** (só para o gerador apagado):
  - `docs/design/CARTAS.md:4-7`: a fonte é `data/cards/{classe}.json`, curado à mão. As ondas por Postura
    ficam em `data/cards/posturas/`, alimentadas pela esteira da SPEC-336 (`scripts/cards/draft.py` →
    `lint.py` → `sim.py` → `promote.py`). O motor é `services/cards.py`.
  - `docs/design/CARTAS.md:103-113` ("Como reautorar"): editar o JSON ou usar a esteira, depois
    `scripts/cards/lint.py` e `tests/test_conflito_autoria_cartas.py`. Sai a menção a `STARTING_RECOMENDADO`,
    que só existia no gerador.
  - `docs/design/CLASSES.md:132`: `data/classes.json` é a fonte, e o gerador foi removido pela SPEC-376.
    `gen_tiers_5_plus.py` fica só em `--check`, e `--write` exige seleção humana (SPEC-355 R6).
  - `docs/guias/AUTORIA.md`: seção nova e curta, "Cartas e classes", com a pipeline vigente. Hoje o guia não
    tem uma palavra sobre Cartas **[F]** (grep `gen_|data/cards` só acha `gen_world_living_npcs`). A SPEC-273
    R2 nunca foi aplicada.
  - Docstring de `tests/test_conflito_autoria_cartas.py:3-4`: "Valida o Acervo autoral curado em
    `data/cards/{classe}.json`". Mexe só no docstring; nenhuma asserção muda (W3).
  - Uma linha datada no cabeçalho da SPEC-273: "R2 superado para `gen_cards_v4`/`gen_classes_v2` pela
    SPEC-376 (deriva em `docs/spec376/deriva.md`)".
- **R9 — `virtude_sugeridas.json` continua como dado.** É lido por `cards.suggested_virtue_cards`
  (mantido pela SPEC-272 (c)) e testado por `test_conflito_autoria_cartas.py`. Não é apagado nem regravado.
- **R10 — `_meta` "Gerado por scripts/gen_cards_v4.py"** nos 5 JSON de classe: só se a D2 aprovar, numa
  etapa própria (A4) com W1 limpo e depois da 367 (que commita direto na `main`) e da 369. **[F]** Nenhum teste ou módulo lê o `_meta` desses arquivos (o grep de
  `["_meta"]`/`get("_meta")` só acha `docs/spec358/*`, `scripts/cards/*`, `scripts/bestiario/*` e
  `tests/test_card_sim_v2.py:64`, que lê o `_meta` do golden). Efeito colateral conhecido: o `motor_hash`
  (`docs/spec358/gerar_golden_v1.py:84-112`) inclui `data/cards/**/*.json`, então
  `tests/test_card_sim_v2.py` cai no ramo estrutural. Isso **não** é falha (docstring de `motor_files`), e o
  mesmo vale para qualquer mudança em `services/**/*.py` (etapas C).
- **R11 — `migrate_bestiary_v4.py` fica; só análise.** **[F]** `main()` reescreve `data/bestiary.json`
  inteiro. Para **toda** criatura, inclusive as das SPEC-349/359, ele sobrescreve `virtudes`,
  `max_vitalidade`, `resistances`, `cartas` e `tactical_profile` (`scripts/migrate_bestiary_v4.py:1262-1308,1322-1327`).
  Ele também regrava `data/cards/bestiario.json` a partir de `ENEMY_CARDS` (`:1331-1343`), onde não há
  `momento` de Carta (1 ocorrência no script, numa frase de perfil, `:538`), contra 40 em
  `data/cards/bestiario.json`. **[H]** Rodar o script hoje apaga curadoria do bestiário. A Etapa 0 mede. Se
  for destrutivo: aviso no docstring (⚠️ "não é passo da pipeline; sobrescreve curadoria das SPEC-335/349") e,
  pela D3, `main()` passa a exigir `--write` (default: imprime o aviso e sai 2), no mesmo padrão do
  `gen_tiers_5_plus` (SPEC-355 R6). Corrigir também `docs/HANDOFF-PROXIMA-SESSAO.md:40` ("dados só pelos
  geradores oficiais (`migrate_bestiary_v4.py`)"). **[F]** Três testes carregam o módulo. O 287 usa só a
  constante `SOBREVIVENCIA_POR_NIVEL_ENCONTRO` (`tests/test_spec287_encounter_scale.py:114-130`). O 290
  carrega em `test_spec290_chefe_sobrevivencia.py:29`. O 295 **chama `gen.migrate_creature`**
  (`test_spec295_chefe_no_topo.py:87-88`, teste de idempotência; correção da revisão P2-3). Nenhum chama
  `main()`. Por isso a A5 **não** muda `migrate_creature`, `NEW_CREATURES`, `ENEMY_CARDS` nem nenhuma
  constante do módulo: só o docstring (incluindo a linha "Uso:" em `:15`, que passa a mostrar `--write`) e
  `main()`/`__main__`. Os comentários em `agents/bestiary.py:360` e `scripts/bestiario/gerar_mecanica.py:51`
  não mudam (descrevem origem de campo).
- **R12 — `gen_tiers_5_plus.py` fica.** É testado (`tests/test_spec355_conteudo.py:11,40-82`) e já é seguro
  por default. A saída do `--check` vai para o `deriva.md` como relatório, e o `--write` roda só dentro da
  cadeia (ii) no diretório temporário (R5). **[F]** O próprio docstring
  diz que ele já sai 1 na `main` (`basicas.json`, `tiers_5_plus.json`). Corrigir essa deriva fica fora de
  escopo.

### B. Scripts de evidência

- **R13 — Lista com o re-grep feito nesta spec (03/11).** Linhas medidas. "Refs vivas" = fora de `specs/`,
  `handoffs/`, `docs/specNNN/`, `docs/historico/` e `docs/staging-wave-*`.

  | Script | Linhas | Refs vivas | Recomendação |
  |---|---|---|---|
  | `scripts/staging/spec236_daily_cap.py` | 250 | só `ruff-baseline.toml:82`; plano da onda 17/10 | **B1 apagar** |
  | `scripts/staging/spec279_usage_survives_delete.py` | 169 | só `ruff-baseline.toml:83`; `handoffs/SPEC-279-review.md` | **B1 apagar** |
  | `scripts/staging/jev_primary_measure.py` | 192 | nenhuma (`docs/spec217/primary-staging-2026-10-18.md:34`) | **B1 apagar** |
  | `scripts/staging/security_wave_smoke.py` | 243 | nenhuma; SPEC-273 "Fora de escopo" e auditoria de 18/10 "Não podar" chamam `scripts/staging/*` de runbook da SPEC-197 | **B2: D4** |
  | `scripts/staging/browser_voice_smoke.py` | 167 | nenhuma (evidência em `docs/spec197/evidence/`) | **B2: D4** |
  | `scripts/staging/stt_fallback_smoke.py` | 192 | nenhuma (`docs/staging-wave-2026-10-17/README.md:173`) | **B2: D4** |
  | `scripts/smoke_local_profile.py` | 118 | nenhuma (lista de ferramentas de operação em `docs/descricao_projeto/…/explore_06_qualidade.md:340`) | **B2: D4** |
  | `scripts/staging/spec222_art_purge.py` | 308 | **`docs/spec364/smoke-final.md:98`** (02/11): opção do coordenador para purgar o retrato `tipo:fallback_criatura_hostil` | **B3 manter** |
  | `scripts/smoke/spec351_opening.py` | 246 | editado pela SPEC-366 (R4: grava `replan.planner_cited`); a medição real da adesão "fica para o próximo smoke" (SPEC-366, fora de escopo) | **B3 manter** |
  | `scripts/migrate_embedding_profile.py` | 17 | **único ponto de entrada** de `PgvectorMemoryStore.migrate_legacy_profile` (`infrastructure/pgvector_memory.py:102`); SPEC-234 manda "rodar no deploy" (`docs/spec234/README.md:27`), e a validação em ambiente real está pendente (`specs/SPEC-234…:191`); produção nunca subiu | **B3 manter** |
  | `scripts/bestiario/arena_todas.sh` | 13 | laço da arena das 12 regiões (SPEC-349 R26); as ondas e os follow-ups de chefes (359, 373) podem rodar de novo | **B3 manter** (ganho de 13 linhas) |

- **R14 — Apagar só B1 e o que a D4 liberar de B2**, um commit por script (W4). Junto, regenerar
  `ruff-baseline.toml` com `bash scripts/dev/py.sh scripts/dev/ruff_baseline.py` (as linhas 82-83 apontam
  para os scripts de B1). Rodar `--check` verde. **Trava (revisão P2-2):** regerar a baseline inteira
  absorveria em silêncio dívida de lint nova que outra sessão tenha posto na `main`. Por isso
  `git diff ruff-baseline.toml` tem que mostrar **só** a remoção das linhas dos scripts apagados. Se aparecer
  qualquer outra linha, a etapa para e reporta, sem commitar a baseline. O `ruff_baseline.py` (inclusive o
  `--check`) reescreve o arquivo por um instante (`scripts/dev/ruff_baseline.py:40-54`), então rode-o só no
  worktree da spec. Alternativa equivalente: apagar à mão só as linhas 82-83 e conferir com `--check`.
- **R15 — Sem cascata.** Módulos que ficam sem importador depois de B (ex.: `jev_shadow_measure`,
  `projection_measure`, importados por `jev_primary_measure.py:20-21`) **não** saem nesta spec. Eles são
  listados no `docs/spec376/README.md` como candidatos.
- **R16 — Ficam sempre**, fora da lista: `incident_drill`, `finops_margin_sim`, `vercel_bundle_check`,
  `restore_local` e `retire_creature_portrait` (este a SPEC-367 está editando).

### C. Código sem chamador (refatoração pura: W2 + W3)

- **R17 — `combat_mechanics.tick_conditions`** (`combat_mechanics.py:535-579`, **45 linhas**). **[F]** Nenhum
  chamador fora de testes. O laço v4 usa `_tick_conditions_v4` (`services/conflict_orchestrator.py:357-361`).
  A auditoria deu o intervalo `535-645`, mas `:599-643` são `_ABYSS_TIERS`, `_DOC_ONLY_SPECIAL_RULES` e
  `HANDLED_KINDS`, que estão **vivos** (lidos por `tests/test_mecanica_orfa.py`, `test_itens_vivos.py` e
  `test_conflito_virtudes.py`) e **não podem** ser apagados. Os testes também mudam, como único caso
  permitido (D7):
  `tests/test_mvp.py:336-342` (`test_condition_tick_applies_dot_and_expires`, que testa só essa função) sai,
  e `"tick_conditions"` sai de `SURVIVING_FUNCTIONS` (`tests/test_cutover_audit.py:29`), como foi feito com
  `resolve_damage_formula` na SPEC-272. O docstring de `conflict_orchestrator.py:358-361` **não** muda (é
  arquivo quente e o texto continua historicamente correto). Adendo (R4): SPEC-012 e SPEC-074.
- **R18 — `npc_world.escort_stop`** (`services/npc_world.py:1517-1526`). **[F]** 0 referências fora de
  specs, nem em teste. SPEC-313 R22 diz que o `escort_sync` encerra a escolta e que o `event_processor` não
  chama `escort_stop` (`specs/SPEC-313…:829-831`). Adendo: SPEC-313.
- **R19 — `world_engine.region_pressure`** (`services/world_engine.py:201-204`) e
  **`faction_relations.faction_relation`/`relation_label`** (`services/faction_relations.py:63-77`). **[F]**
  0 referências fora de specs, nem em teste, nem no próprio módulo. São leitores prometidos pela SPEC-302 §3
  "para specs consumidoras" (`specs/SPEC-302…:344,499,515-516`) que nunca ganharam consumidor. Apagar depende
  da D6. Adendo: SPEC-302. **Ordem com a SPEC-377:** o item 1 da 377 edita `services/world_engine.py:729-738`
  (`register_day_hook` de `law`). A W6 serializa as duas specs, mas os números de linha citados mudam: quem
  vier depois relocaliza por `git grep -n`, não pela linha.
- **R20 — `agents/bestiary.py:_overlay_path`** (`:193-196`) e **`agents/npc.py:_npc_db_path`** (`:260-263`).
  **[F]** 0 referências no repo, nem em teste nem em alvo de `monkeypatch`.
- **R21 — `_infer_tier_from_name` vira constante.** **[F]** As duas cópias fazem `del name` e devolvem
  `ModelTier.FAST` (`agents/bestiary.py:321-324`, `agents/npc.py:438-442`; decisão da SPEC-223 R7). Os
  chamadores ficam `get_llm(..., tier=ModelTier.FAST)` (`agents/bestiary.py:663`, `agents/npc.py:539`), com
  um comentário de uma linha citando a SPEC-223 R7. **[F]** Nenhum teste referencia o nome. A SPEC-378:203
  deixa `_infer_tier_from_name` e os stubs `ImportError` explicitamente de fora; a 376 é a dona dos dois. O
  coordenador registra essa nota na 378.
- **R22 — Stubs `try/except ImportError` para módulos do repo**, em `agents/bestiary.py:20-25` (`rag`),
  `agents/npc.py:52-67` (`rag`) e `:120-126` (`agents.librarian`) e `agents/world_simulator.py:22-30` (`rag`).
  Saem **só** depois da prova do R23. **Os nomes `RAG_AVAILABLE` continuam como constante de módulo**
  (`RAG_AVAILABLE = True`). **[F]** São 8 linhas em 7 arquivos com `monkeypatch.setattr(npc, "RAG_AVAILABLE", False)`
  (contagem corrigida pela revisão P2-3): `tests/test_context_npc_gate.py:182,225`, `test_spec301_llm.py:181`,
  `test_spec310_npc_prompt.py:47`, `test_spec311_integration.py:82`, `test_spec314_no_leak.py:49`,
  `test_spec314_npc_proposals.py:36` e `test_spec350_npc_prompt.py:118`. Os outros `setattr` são em `cb`
  (`context_builder`, fora do escopo), e nenhum teste faz `setattr` em `world_simulator.RAG_AVAILABLE`.
  `agents/npc.py:1400,1403` e `agents/world_simulator.py:190` leem a flag. Sem o atributo, `setattr` quebra. **Fora deste requisito**:
  `character_creator.py:20-24` e `services/context_builder.py:33-37`, que têm o mesmo padrão. O
  `context_builder` é alvo de `evals/core/adapters.py:1058` (W5).
- **R23 — Prova de que nenhum stub evita um ciclo de import.** Rodar tudo num **subprocess novo** por
  combinação, com `RPG_FORCE_MOCK=1`, antes e depois da mudança, no worktree da spec. Ordens de import
  (primeiro módulo carregado): `∅`, `rag`, `main`, `api` e `agents.librarian`; em seguida, `agents.bestiary`,
  `agents.npc` e `agents.world_simulator`. Os imports soltos dão 0 erro antes e depois. Isso **não basta**
  (revisão P1-2): se houvesse ciclo, o stub o engoliria e o "antes" também daria 0 erro. Por isso, em cada
  ordem, **antes** da mudança:
  - `agents.npc.RAG_AVAILABLE is True` e `agents.world_simulator.RAG_AVAILABLE is True`;
  - `agents.npc.query_rag is rag.query_rag` e `agents.bestiary.query_rag is rag.query_rag`;
  - `agents.world_simulator.add_memory_to_session is rag.add_memory_to_session`;
  - `agents.npc.find_existing_entity is agents.librarian.find_existing_entity`.

  Todas têm que ser `True`, o que prova que o stub nunca é usado. A revisão sondou 4 dessas ordens em
  `b278f6af` e todas deram `True`. **Depois** da mudança, as mesmas asserções continuam `True`. Saída em
  `docs/spec376/README.md`. Evidência estática **[F]**:
  `rag.py` não importa `agents.*` no topo (imports de topo `:17-41`); `agents/librarian.py:6-13` só importa
  `llm_setup`, `observability` e libs; `agents/bestiary.py:28` já importa `agents.librarian` **sem**
  guarda. `faiss-cpu` e `langchain-community` são dependências obrigatórias (`pyproject.toml:9,12`) e estão em
  `requirements.txt:45,99` (bundle da Vercel), então o `except ImportError` também não protege contra
  dependência opcional ausente. **[H]** Não há ciclo. Se alguma identidade der `False` ou algum import der
  erro em qualquer combinação, o stub daquele módulo **fica**, com um comentário dizendo por quê.
- **R24 — Itens que saem da lista C** depois da verificação (eram da auditoria ou do brief):
  - `card_effects.glossary_for_prompt` (`services/card_effects.py:1276`): **vivo**. **[F]**
    `scripts/cards/draft.py:113` o chama na esteira da SPEC-336. Não apagar.
  - `cards.valid_effect_kind` (`services/cards.py:86`): é o oráculo do teste de conteúdo
    `tests/test_conflito_autoria_cartas.py:54,59`. Apagar obrigaria a reescrever a asserção, o que a W3
    proíbe. Recomendação: manter (D5).
  - `card_effects.resolve_card` (`services/card_effects.py:1085-1097`): interface declarada da SPEC-330 §3
    (`specs/SPEC-330…:58`). O teste `tests/test_card_effects_grammar.py:279` exercita a **ordem da gramática**
    (custos → efeitos → gatilhos, `se`) por ela, não "só a função". Recomendação: manter (D5). Se a D5 mandar
    apagar, vira a etapa C5 (a 368 já pousou; só a W1 vale), que exige reescrever o teste sobre o caminho vivo
    (deixa de ser pura).
  - Seams de teste (`reload_*`, `reset_*`, `card_shop.reload_config`), `RAG_AVAILABLE`, tudo da SPEC-272 (c),
    `gameplay_oracles`, `cards.set_deck`, `law.daily_tick` e `evals/`.
- **R25 — Oráculo W2** em cada etapa C. Antes da primeira etapa C, capturar A
  (`evals run` das 12 suítes do `eval-gates.yml` com `--seed 7`; `playtest run --all --turns 10 --seed 0`).
  Depois de cada etapa C, capturar B. Exigir `evals compare --current B --baseline A` **sem diferença** e a
  mesma contagem de violações e o mesmo desfecho por perfil. A suíte completa é do coordenador, 1× no pouso.
  O executor roda só os testes do escopo (§4), com no máximo `-n 2`.
- **R26 — W3.** Em C, os testes só mudam nos casos do R17 (apagar teste que testa **só** a função apagada e
  tirar o nome de `SURVIVING_FUNCTIONS`). Qualquer outra asserção que precise mudar ⇒ a etapa para e é
  reportada.

### Fora de escopo

- Corrigir a deriva pré-existente do `gen_tiers_5_plus --check` (`basicas.json`, `tiers_5_plus.json`) e a
  forma como ele regrava `playstyle`/`tradeoff`/`preview_card_ids` em `classes.json`.
- Apagar `migrate_bestiary_v4.py`, `gen_tiers_5_plus.py`, `gen_world_living_npcs.py`, `migrate_lore_nova.py`
  ou `import_visual_assets.py`.
- Os stubs `ImportError` de `character_creator.py` e `services/context_builder.py`; a cascata de módulos
  órfãos depois de B (R15).
- Tudo do §6.4 da auditoria e as exclusões listadas no R24. `law.daily_tick` (SPEC-377), `cards.set_deck`
  (SPEC-384), `_fold`, `_pool_enabled` e `_last_human_text` (SPEC-378).
- Mudar `_meta` de `data/cards/bestiario.json` (gerado por `migrate_bestiary_v4`, que fica) e editar docs
  históricos (`docs/descricao_projeto/**`, `docs/historico/**`, `docs/spec355/pendencias.md:21`, que cita o
  caminho errado `scripts/cards/gen_tiers_5_plus.py`).

## 3. Design técnico

- **Arquivos novos:** `docs/spec376/deriva.md` (R6), `docs/spec376/README.md` (logs de W1, re-grep, matriz de
  import e W2 A/B) e `tests/test_spec376_fonte_dados.py` (só para A e B, que não são refatoração pura de
  runtime). Os testes são:
  - `test_geradores_apagados_nao_existem`: os arquivos apagados pelo R7 não existem;
  - `test_docs_nao_mandam_rodar_gerador_apagado`: em `CARTAS.md`, `CLASSES.md` e `AUTORIA.md`, nenhuma linha
    casa `python\S*\s+scripts/gen_(cards_v4|classes_v2)\.py` (comando de rodar) nem
    `\]\((\.\./)*scripts/gen_(cards_v4|classes_v2)\.py\)` (link para o arquivo). A frase "o gerador
    `gen_classes_v2.py` foi removido pela SPEC-376" continua permitida (revisão P2-1);
  - `test_migrate_bestiary_sem_write_nao_grava` (se a D3 aprovar): com `RPG_ROOT=tmp_path` (cópia de
    `data/bestiary.json` e `data/cards/bestiario.json`), carrega o módulo via `importlib` depois do
    `monkeypatch.setenv`, chama `main([])` e verifica `rc != 0` e os bytes dos dois arquivos iguais.
- **Arquivos alterados:** listados por etapa no §4 (é a lista que entra na W1).
- **Assinatura nova (só com a D3):** `scripts/migrate_bestiary_v4.main(argv: list[str] | None = None) -> int`.
  Sem `--write`, imprime o aviso e devolve 2. Com `--write`, faz o comportamento de hoje. O `__main__` passa
  `sys.argv[1:]`.
- Nenhum schema, save, flag, rota ou prompt muda.

## 4. Plano passo a passo

Ordem: 0 → A → B → C. A, B e C são independentes entre si **depois** da Etapa 0. Cada etapa começa pelo R1
(W1) com a lista "Arquivos" dela.

### Etapa 0 — Medir a deriva (sem commit em `data/`)
- **Arquivos:** `docs/spec376/deriva.md`, `docs/spec376/README.md`. Geradores só no diretório temporário do
  R5. **Nunca** via `py.sh`/`uv run`, e nunca com o cwd num repo.
- R5/R6 completos, com as medições (i) e a cadeia (ii). O hand-back da etapa traz o veredito por gerador. **Para aqui** até a D1 ser respondida
  com o `deriva.md` na mão.

### Etapa A1 — `gen_cards_v4.py` (se o veredito for "sai")
- **Arquivos:** `scripts/gen_cards_v4.py` (rm), `docs/design/CARTAS.md`,
  `tests/test_conflito_autoria_cartas.py` (só o docstring), `tests/test_spec376_fonte_dados.py`.
1. **Testes:** `test_geradores_apagados_nao_existem` (parte das Cartas) e `test_docs_nao_mandam…` ficam
   vermelhos.
2. `git rm`; editar `CARTAS.md` e o docstring (R8).
3. Rodar `tests/test_spec376_fonte_dados.py tests/test_conflito_autoria_cartas.py tests/test_spec355_conteudo.py -q`.

### Etapa A2 — `gen_classes_v2.py` (se o veredito for "sai")
- **Arquivos:** `scripts/gen_classes_v2.py` (rm), `docs/design/CLASSES.md`, `tests/test_spec376_fonte_dados.py`.
- Mesmo roteiro da A1. Rodar `tests/test_cutover_audit.py tests/test_spec348_canon.py tests/test_mecanica_orfa.py -q`.

### Etapa A3 — Guia de autoria e adendo da 273
- **Arquivos:** `docs/guias/AUTORIA.md`, `specs/SPEC-273-scripts-geradores-avulsos.md` (só uma linha no
  cabeçalho). Testes: `test_docs_nao_mandam…`. **Espera a SPEC-374**, que hoje trava `docs/guias/AUTORIA.md`
  (W1 da revisão: única interseção em 03/11).

### Etapa A4 — `_meta` dos 5 JSON de classe (só com a D2 aprovada; espera a 367, que commita na `main`, e a 369)
- **Arquivos:** `data/cards/{devoto,sangromante,corruptor,arcanista,medico}.json` (só a string `_meta`).
- Rodar `tests/test_conflito_autoria_cartas.py tests/test_card_sim_v2.py tests/test_spec362_arcanista.py -q`.
  O `test_card_sim_v2` cai no ramo estrutural (R10), e isso não conta como falha.

### Etapa A5 — `migrate_bestiary_v4.py` (só se a Etapa 0 provar que é destrutivo)
- **Arquivos:** `scripts/migrate_bestiary_v4.py` (docstring e, com a D3, o `--write`),
  `docs/HANDOFF-PROXIMA-SESSAO.md`, `tests/test_spec376_fonte_dados.py`.
1. **Teste:** `test_migrate_bestiary_sem_write_nao_grava` vermelho.
2. Aviso no docstring, a linha "Uso:" (`:15`) e o `--write` (D3), só em `main()`/`__main__`.
   `migrate_creature` e as constantes ficam byte-iguais (o 295 os usa). Corrigir o `HANDOFF-PROXIMA-SESSAO.md:40`.
3. Rodar `tests/test_spec287_encounter_scale.py tests/test_spec290_chefe_sobrevivencia.py tests/test_spec295_chefe_no_topo.py tests/test_conflito_autoria_bestiario.py tests/test_spec376_fonte_dados.py -q`.

### Etapa B1 — Scripts de evidência (lista final da D4)
- **Arquivos:** os scripts liberados (R13) e `ruff-baseline.toml`.
1. R3 de novo para cada script, e um commit por script.
2. `ruff_baseline.py`, depois `ruff_baseline.py --check` e `ruff check .` verdes. `git diff ruff-baseline.toml`
   mostra só as linhas dos scripts apagados (R14). Rodar
   `tests/test_spec192_staging_scripts.py tests/test_spec191_staging_tools.py tests/test_session_hardening.py -q`.

### Etapa C0 — Linha de base W2 (A)
- **Arquivos:** só `docs/spec376/README.md`. Captura A do R25 e matriz de import "antes" do R23.

### Etapa C1 — `tick_conditions`
- **Arquivos:** `combat_mechanics.py`, `tests/test_mvp.py`, `tests/test_cutover_audit.py`,
  `specs/SPEC-012-…md`, `specs/SPEC-074-…md` (só o adendo).
- Rodar `tests/test_mvp.py tests/test_cutover_audit.py tests/test_mecanica_orfa.py tests/test_conflito_virtudes.py tests/test_itens_vivos.py -q`.
  W2 B.

### Etapa C2 — Leitores de serviço sem consumidor (R18, R19 com a D6)
- **Arquivos:** `services/npc_world.py`, `services/world_engine.py`, `services/faction_relations.py`, adendos
  em `specs/SPEC-313-…md` e `specs/SPEC-302-…md`.
- Rodar os testes de `npc_world`, `world_engine` e `faction_relations` (`tests/test_spec302*`,
  `tests/test_spec313*`, `tests/test_spec304*`). W2 B. Ordem com a SPEC-377 item 1 em `world_engine.py` (R19).

### Etapa C3 — Helpers de agentes (R20, R21)
- **Arquivos:** `agents/bestiary.py`, `agents/npc.py`. **[H]** As branches de fauna e bestiário (370–373)
  podem estar tocando `agents/bestiary.py`; a W1 decide.
- Rodar `tests/test_context_npc_gate.py tests/test_spec350_npc_prompt.py tests/test_spec287_encounter_scale.py`
  e os testes de `bestiary`/`npc` do escopo. W2 B.

### Etapa C4 — Stubs de import (R22, R23)
- **Arquivos:** `agents/bestiary.py`, `agents/npc.py`, `agents/world_simulator.py`, `ruff-baseline.toml` (se
  F401 mudar).
1. Matriz de import "antes" (já da C0).
2. Remover os stubs, mantendo `RAG_AVAILABLE = True`.
3. Matriz "depois", com as asserções de identidade do R23, igual à de antes. Rodar os 7 arquivos que fazem
   monkeypatch de `npc.RAG_AVAILABLE` (`tests/test_context_npc_gate.py`, `test_spec301_llm.py`,
   `test_spec310_npc_prompt.py`, `test_spec311_integration.py`, `test_spec314_no_leak.py`,
   `test_spec314_npc_proposals.py`, `test_spec350_npc_prompt.py`) e os testes de `world_simulator`. W2 B.

### Etapa C5 — Opcional (só se a D5 mandar apagar `resolve_card`/`valid_effect_kind`; a 368 já pousou, vale só a W1)
- **Arquivos:** `services/card_effects.py`, `services/cards.py` e os testes do R24. **Não é pura** (W3):
  exige a revisão `Sol` antes do commit.

### Pouso
- O coordenador roda a suíte completa 1× (W2.1), `validate_content.py` e `spec_index.py build`.
  `ESTADO_ATUAL.md` só pelo coordenador.

## 5. Critérios de aceite

- [ ] `docs/spec376/deriva.md` com as medições (i) e a cadeia (ii), e um veredito por gerador tirado da
      cadeia (R5/R6). Snapshot de `git status --porcelain -- data/` e `git stash list` do principal igual
      antes e depois.
- [ ] Só saiu gerador com deriva destrutiva provada (R7), com a D1 registrada.
- [ ] `CARTAS.md`, `CLASSES.md`, `AUTORIA.md` e o docstring do teste declaram `data/` como fonte (R8). Adendo
      na SPEC-273.
- [ ] `migrate_bestiary_v4.py` analisado; aviso e `--write` conforme a D3 (R11).
- [ ] Scripts de B apagados só da lista final da D4. Re-grep registrado (R3). `ruff-baseline.toml`
      regenerado, com diff só das linhas apagadas, e `--check` verde (R14).
- [ ] C1–C4 com W1 registrado, re-grep registrado e W2 sem diferença (evals compare vazio, playtest com as
      mesmas violações e desfechos). Matriz de import com as identidades `True` antes e depois (R23).
- [ ] Testes alterados só nos casos do R17. Nenhuma outra asserção mudou (W3).
- [ ] Adendos datados nas SPEC-012, 074, 302 e 313 para o que saiu (R4).
- [ ] Um commit por mudança mecânica (W4); nenhum force-push (W8).
- [ ] `uv run pytest` verde (suíte completa offline, coordenador, 1×).
- [ ] Saves antigos continuam carregando: nenhum campo de save muda. `tests/test_fase0.py`,
      `tests/test_fase25.py` e o round-trip de `persistence` no escopo.
- [ ] Revisão independente `Sol` APPROVED, com o W2 refeito pelo revisor em pelo menos 1 item de C (W7).

## 6. Smoke test com LLM real

**N/A, com justificativa por parte:**

- **A e B:** não mudam código de runtime. Os geradores e scripts apagados não são importados por `api.py`,
  `main.py`, `agents/` nem `services/` (R3, **[F]** grep). O que fica alterado em runtime é zero. A prova é
  a Etapa 0 (deriva medida) mais os testes de conteúdo. O `migrate_bestiary_v4.py` só ganha o `--write`, e
  ele não roda em jogo.
- **C:** é refatoração pura de código sem chamador (e, no R21/R22, troca de uma função constante por uma
  constante e de um import guardado por um import direto que já funcionava). Nenhum prompt, tier, rota de
  LLM ou campo de structured output muda: `get_llm` continua recebendo `ModelTier.FAST` nos mesmos dois
  pontos. **O W2 basta.** Um smoke real não acrescenta sinal que o `evals compare` e o playtest
  determinístico já não deem.
- Se a D5 mandar apagar `resolve_card` (C5), a etapa deixa de ser pura. Ainda assim não toca LLM; o W2 e a
  revisão `Sol` continuam suficientes.

## 7. Riscos & compatibilidade

- **Apagar um gerador que alguém ainda usa.** Mitigação: a Etapa 0 mede a deriva antes, e o diff vazio
  mantém o gerador (R6). Re-grep em `.github/`, `.claude/` e `docs/` (R3). O histórico git guarda o script, e
  o rollback é `git revert` de um commit só (W4). Risco residual: uma sessão paralela com o guia antigo
  aberto roda o gerador antes do pouso. Por isso a A1/A2 corrigem a doc **no mesmo commit** do `git rm`.
- **O próprio teste de deriva estragar dados.** O `gen_classes_v2.py` grava ao ser importado
  (`:1605-1608`, sem `main`). **`RPG_ROOT` não protege:** `scripts/dev/env.sh:6,17` o sobrescreve com o
  toplevel do cwd, e o cwd do subagente volta ao checkout principal a cada chamada de Bash, onde a 367 trabalha
  direto na `main` (revisão P0-1). Mitigação (R5): rodar no diretório temporário fora de qualquer repo, com o
  python do venv chamado direto (`-I`), `test ! -d .git` na mesma chamada e snapshot de
  `git status`/`git stash list` do principal antes e depois. O `gen_tiers_5_plus --write` só roda na cadeia
  (ii), dentro do diretório temporário.
- **Chamada dinâmica que escapa do grep** (`getattr`, nome em YAML/JSON, alvo de `monkeypatch` em string).
  Mitigação: o R3 cobre string, `getattr` e registros, e o W2 (evals + playtest) pega caminhos de runtime
  que o grep não vê. A auditoria admite que não descartou chamadas dinâmicas (Anexo); esta spec descartou
  para os itens de C (0 hits do nome em qualquer forma), mas o executor refaz isso no dia (o código muda).
- **Medir a deriva da forma errada** (o erro da SPEC-273). Mitigação: o veredito sai da cadeia completa
  (ii); campo que o `gen_tiers_5_plus` devolve não conta como destrutivo (R6).
- **Stub de import que evitava ciclo.** Mitigação: a matriz de subprocess do R23, em 5 ordens, com
  asserções de **identidade** stub × real (um ciclo mascarado pelo stub também daria 0 erro); em caso de
  dúvida, o stub fica. A seam `RAG_AVAILABLE` é preservada (R22), porque sem ela 7 arquivos de teste (8
  `setattr`) quebram por atributo inexistente.
- **Apagar o intervalo errado de `combat_mechanics.py`.** O intervalo da auditoria (`535-645`) inclui
  `HANDLED_KINDS`, que está vivo. O R17 fixa `535-579`, e `test_mecanica_orfa` está no escopo da C1.
- **Conflito com as sessões paralelas** (a 367 commita direto na `main`; 369 Cartas; 370–374 fauna e
  bestiário; 374 em `AUTORIA.md`; 377 em `world_engine.py`; 379 em `test_mvp.py`; 381/384 regeneram
  `ruff-baseline.toml`). Mitigação: a W1 revisada, com as três fontes (R1); A3, A4 e C2 esperam
  explicitamente; diff restrito da baseline (R14).
- **`motor_hash` muda** com qualquer edição em `services/**` ou `data/cards/**`. O
  `tests/test_card_sim_v2.py` cai no ramo estrutural por desenho, e isso não é regressão (R10).
- **Saves, MockLLM e FallbackLLM:** sem impacto. Nenhum campo de estado, guard de structured output ou
  caminho de fallback muda. **Quota e latência:** zero.

**Estimativa honesta de linhas** (o "−6.000" da auditoria para a letra B é otimista):

| Parte | Recomendado | Máximo |
|---|---|---|
| A (dois geradores, se a deriva se confirmar) | −4.176 + ~40 de doc/aviso | idem |
| B | −611 (B1) | −1.331 (B1+B2); B3 (584) fica |
| C (produto) | ≈ −120 (`tick_conditions` 45, leitores SPEC-302/313 ~30, helpers ~10, `_infer_tier` ~8 líquido, stubs ~25 líquido) | ≈ −135 com `resolve_card` |
| C (testes) | −8 | ≈ −30 com C5 |
| **Total** | **≈ −4.9 K** | **≈ −5.6 K** |

## 8. Decisões do dono

- **D1 — Apagar o gerador cuja deriva destrutiva for provada?** As opções são (a) `git rm` e `data/` vira a
  fonte declarada; (b) mover para `scripts/_arquivo/` com `raise SystemExit` no topo. **Recomendação: (a).**
  O histórico git guarda o script (W8), e (b) mantém 4 K linhas que ninguém pode rodar. Se a Etapa 0 der diff
  vazio para algum gerador, ele **fica**, e esta D não se aplica a ele.
- **D2 — Trocar o `_meta` "Gerado por scripts/gen_cards_v4.py" nos 5 JSON de classe?** **Recomendação: sim,
  na etapa A4**, depois que a 367 (que commita direto na `main`) e a 369 pousarem (W1; a 368 já pousou). Nenhum teste lê esse campo, e deixá-lo mente sobre a
  fonte. Se as branches de Cartas não pousarem nesta onda, a A4 é cancelada sem prejuízo (o `CARTAS.md` já
  diz a verdade).
- **D3 — `migrate_bestiary_v4.py` passa a exigir `--write`?** (só se a Etapa 0 provar que ele é destrutivo.)
  **Recomendação: sim.** É o mesmo padrão do `gen_tiers_5_plus` (SPEC-355 R6, depois de um incidente que
  reescreveu 10 arquivos). Nenhum dos testes que importam o módulo chama `main()`; o 295 usa `migrate_creature`,
  que não muda. Alternativa mínima: só o
  aviso no docstring.
- **D4 — Lista final de B.** **Recomendação:** apagar B1 (`spec236_daily_cap`, `spec279_usage_survives_delete`,
  `jev_primary_measure`). **Manter B2** (`security_wave_smoke`, `browser_voice_smoke`, `stt_fallback_smoke`,
  `smoke_local_profile`) até o go/no-go do beta (SPEC-197): a revisão de 18/10 os tratou como ferramenta de
  runbook, e re-rodar smoke de segurança e voz antes de produção é plausível. **Manter B3** com os motivos do
  R13. Se você disser "apaga B2 também", são mais −720 linhas.
- **D5 — `resolve_card` e `valid_effect_kind`.** **Recomendação: manter os dois.** O primeiro é interface
  declarada da SPEC-330 e é por onde o teste da gramática prova a ordem dos efeitos. O segundo é o oráculo do
  teste de conteúdo. Apagar qualquer um muda asserção (W3), e o ganho é de 18 linhas.
- **D6 — Leitores da SPEC-302 sem consumidor** (`region_pressure`, `faction_relation`, `relation_label`).
  **Recomendação: apagar, com adendo na SPEC-302.** São 4 a 10 linhas cada, sem teste, e quem precisar
  reescreve em 1 minuto. Não há spec aberta (370–385) que os cite.
- **D7 — Exceção à W3 em C1.** Apagar `test_condition_tick_applies_dot_and_expires` e tirar
  `"tick_conditions"` de `SURVIVING_FUNCTIONS` muda teste numa etapa "pura". **Recomendação: aceitar.** É o
  precedente da SPEC-272 (R2 e o `resolve_damage_formula`), e o teste testa só a função apagada.

---

### Achados desta verificação que corrigem a auditoria ou o brief (para o coordenador)

1. "31 `"momento"` só em `arcanista.json`": errado. **Cada** JSON de classe tem 30–31, o que reforça o R1.
2. `combat_mechanics.py:535-645` como intervalo de `tick_conditions`: errado. A função é `535-579`, e o
   resto é `HANDLED_KINDS`, que está vivo.
3. `glossary_for_prompt` "sem chamador": errado. `scripts/cards/draft.py:113` o usa.
4. `handoffs/SPEC-362-sol-review.md:47` ("regerar desfaz o buff do Arcanista"): desatualizado. O gerador já
   tem `vitalidade_bonus: 8` (`scripts/gen_classes_v2.py:1509`). O risco real do `gen_classes_v2` é recriar
   `data/player_abilities.json` (quebra `test_cutover_audit.py:78`) e o que a Etapa 0 medir.
5. Segundo arquivo do `gen_classes_v2`: `data/player_abilities.json`.
6. `migrate_bestiary_v4` é importado por 3 testes (287, 290, 295), não só pelo 287. O 295 chama
   `migrate_creature`.
7. Dos 11 scripts de B, 4 não são órfãos (`spec222_art_purge`, `spec351_opening`, `migrate_embedding_profile`
   e, de forma plausível, `arena_todas.sh`). O total é 1.915 linhas, não ~2.000 em "17 scripts".

---

## Resposta à revisão

Revisão: [handoffs/SPEC-376-independent-review.md](../handoffs/SPEC-376-independent-review.md) (Opus,
03/11, `main` em `b278f6af`, SAFE-WITH-CHANGES). **Todos os achados foram aceitos; nenhum foi rejeitado.**

| ID | Onde foi aplicado |
|---|---|
| P0-1 (`RPG_ROOT` sobrescrito por `env.sh`; risco de gravar no principal) | R5 reescrito: diretório temporário fora de repo, python do venv direto com `-I`, `test ! -d .git` na mesma chamada, snapshot antes e depois. §4 Etapa 0 e §7 atualizados |
| P1-1 (medir gerador sozinho conta como perda o que a cadeia devolve) | R5 itens 4–5 (medições (i) e cadeia (ii)); R6 com os campos em dois grupos e o veredito pela cadeia; risco novo no §7 |
| P1-2 (a matriz de import não detecta ciclo mascarado) | R23 com 5 ordens, `RPG_FORCE_MOCK=1` e asserções de identidade stub × real; C4 e §5 |
| P1-3 (W1 cega a commits direto na `main` e a worktrees sujos; branch morta) | R1 passa a usar a W1 revisada da auditoria §6.2 (3 fontes) + `git log <sha>..main -- <arquivos>`; `spec-349-pre-sync` registrada para o coordenador arquivar |
| P2-1 (critério do teste de docs) | §3: regex de comando e de link; a frase "foi removido" é permitida |
| P2-2 (baseline do ruff absorve dívida alheia) | R14 e B1: `git diff ruff-baseline.toml` só com as linhas apagadas, ou parar |
| P2-3 (fatos errados) | R11 (295 chama `migrate_creature`; a A5 não toca nele nem nas constantes; linha "Uso:"), R22 (8 linhas em 7 arquivos, listados), cabeçalho (368 já pousou) |
| P2-4 (testes não rodam no diretório temporário) | R5 item 6: registro por leitura, ou cópia do `data/` da cadeia para um worktree descartável com guarda de toplevel |
| Notas da tabela (R3 `project_index/`; R19 ordem com a 377; R21 nota na 378; C5 sem trava da 368; A3 espera a 374) | Aplicadas. A nota na SPEC-378 fica com o coordenador (esta spec não edita outro arquivo) |
