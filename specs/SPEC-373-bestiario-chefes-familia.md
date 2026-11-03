# SPEC-373 — Bestiário: chefes na faixa com Cartas `on` e teto de uso das Cartas de família de volta

> **Status:** `approved` (dono, 03/11: "transforme em spec e execute agora"; decisões do autor em §8 valem como aprovadas e são revogáveis)
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Épico:** SPEC-349 (bestiário) · SPEC-327 (Cartas)
> **Depende de:** SPEC-349 (`done`: 281 criaturas, `scripts/bestiario/{arena,calibrar,gerar_mecanica}.py`), SPEC-332 (baralhos de família/facção, `services/enemy_decks.py`), SPEC-358 (`done`: `lote-v2` opt-in), SPEC-362 (`done`: Arcanista 49,7 % na 180–259). SPEC-336 (`in-progress`) **não** bloqueia: esta spec escreve as Cartas de família que a 336 deixou pendentes.
> **Desbloqueia:** ligar `RPG_ENEMY_DECKS=on` sem exceção de chefe; SPEC-349 §9 item 8 (a) e (b); follow-ups do ESTADO "bomba_estopim dominante" e "Corruptor sem carta anti-emboscada" (Parte C, ver D9).
> **EXECUTOR_MODEL:** `Terra` (motor, calibragem, arena) · autoria de Cartas novas: **Opus**
> **REVIEW_MODEL:** `Sol` (motor, arena, integridade) + **Opus** (voz e unicidade das Cartas novas) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` (só a Etapa E: `--seed-inicio` no `arena.py` e a volta do teto 15 nos testes da 332, por agente diferente do executor)

Rótulos: **[F]** fato com evidência · **[H]** hipótese a confirmar na Etapa 0 · **[D]** decisão (§8) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

[F] **Nove chefes da esteira estão fora de 45–85 % na arena do bestiário** (L5, 40 sementes × 5 Posturas, `scripts/bestiario/arena.py`; `specs/SPEC-349-bestiario-valoria-esteira.md:640-671`, `docs/spec349/arena-*.md`):

| chefe | região | `off` | `on` | dials hoje (`data/bestiario/mecanica/_ajustes.yaml`) |
|---|---|---|---|---|
| `mon_borda_que_anda` | pantano_melancolia | 75 % | **41 %** | corpo −7, dano −7, forca −7, sig −7 (`:252-257`) |
| `mon_chifres_travados` | pradaria_ruinas | 64 % | **29 %** | todos −7 (`:380-385`) |
| `mon_casco_de_costelas` | brekmar | 63 % | **32 %** | todos −7 (`:342-347`) |
| `enemy_aranha_de_cristal` (slot) | deserto_zhur | 53 % | **28 %** | dano −7 (`:5-10`) |
| `enemy_boss_general_escorpiao` (slot) | deserto_zhur | **90 %** | 56 % | dano −7, sig −2 (`:21-26`) |
| `mon_hospede_do_estomago` | costa_negra | **42 %** | **32 %** | corpo/dano/forca −7, sig 0 (`:672-677`) |
| `mon_toldo_das_clareiras` | floresta_sussurros | 47 % | **32 %** | corpo/dano/forca −7, sig 0 (`:1127-1132`) |
| `mon_peso_dos_vencidos` | montanhas_afiadas | 66 % | **26 %** | todos −7 (`:922-927`) |
| `mon_escavador_das_camaras` | selva_xylos | 66 % | **30 %** | todos −7 (`:552-557`) |

Os outros 4 chefes da esteira estão na faixa (`mon_cacao_de_lastro` 70/61, `mon_roda_de_mandibulas` 65/54, `mon_mastro_dos_ultimos` 78/52, `mon_colecionador_de_poses` 63/48; `docs/spec349/arena-{aethelgard,nova_arcadia,ophidia,skallgard}.md`).

[F] **Os dials acabaram.** O `calibrar.py` move só `dano`/`forca` em chefe (`scripts/bestiario/calibrar.py:144-152`), com limite ±7 (`:34-35`). O Corpo fica em 2 pelo invariante "chefe tem mais Vitalidade que lacaio" (`SPEC-349:615`, `:697`). A Vitalidade por nível de encontro (12) é travada por teste para todo chefe (`tests/test_spec287_encounter_scale.py:125-130`).

[F] **A diferença `off` × `on` vem do baralho de família.** Com `on`, a criatura monta `próprias + 3–5 da família + 0–3 da facção`, e a assinatura da família entra primeiro (`services/enemy_decks.py:229-265`, `:248`, `:250-251`). Toda criatura da esteira já tem 2–4 Cartas autorais próprias (`cartas_autorais`; ex. `data/bestiary.json:23535-23539`) e uma `assinatura` no perfil, que tem precedência sobre a da família (`enemy_decks.py:323-341`). Para essas, a família soma 3–5 Cartas fortes a um baralho que já tem identidade, e o chefe joga 2 ações por rodada (`services/conflict_orchestrator.py:2489-2498`, `:2854-2860`). A leitura do executor da 349 é a mesma: "o baralho de família e as 2 ações por rodada dominam" (`SPEC-349:671`, `:697`).

[F] **O teto de 15 usos por Carta de família (critério da 332) está suspenso.** Com 373 entradas no bestiário, o uso chega a 31. Os 3 testes da 332 pulam `origem == bestiario-349` (`tests/test_enemy_decks.py:298-308`, `:358-371`, `:453-468`) e um teste novo fixa o teto em 36 (`tests/test_spec349_mecanica.py:226-237`). As famílias têm 8 Cartas cada (predador 12) e 2 assinaturas (`data/cards/inimigos/*.json`; `tests/test_enemy_decks.py:290-295`). Cada criatura leva a assinatura da família **sempre** (`enemy_decks.py:177-183`, `:250-251`), então cada assinatura cai em ~metade da família: com ~34 criaturas por família, ~17 usos por assinatura em média. A pendência foi registrada para a 336 (`SPEC-349:695`, `:701`), que não tem etapa de Cartas de inimigo além da meta "+20 por onda" (`specs/SPEC-336-cartas-09-esteira-continua-autoria-cartas.md:47`).

[F] **Dois follow-ups de Cartas de jogador** (`ESTADO_ATUAL.md`, Próximos passos 2):
- `arc1_imp_bomba_estopim` acusa `dominante` no protocolo `lote` (+9,4 pp, uso 55 %) mesmo na v1 (`specs/SPEC-362-balanco-arcanista.md:334`, `:351`); a Carta está em `data/cards/posturas/arcanista_cinzento_improvisador.json:185-210` (`dano_base` 4 + `dano` 3 em `inimigos`, Fôlego 1, Entropia 1, `cena`);
- o Corruptor é a única Postura sem Carta `buff_iniciativa`, então a contrapartida de emboscada (SPEC-355 R17) não vale para ele: 44,2 % realista nas 0–19 e 45,2 % na 20–99 (`specs/SPEC-355-cartas-pendencias-abertas.md:185-189`, `:555-561`).

**Objetivo.**
1. **Parte A:** os 9 chefes dentro de 45–85 % em `off` **e** `on` (L5, arena do bestiário), sem regredir as outras 272 criaturas.
2. **Parte B:** nenhuma Carta `inf_*` em mais de 15 criaturas, na população inteira (373 entradas), com os testes da 332 sem exceção.
3. **Parte C (D9):** `bomba_estopim` sem bandeira `dominante` no `lote` e o Corruptor com contrapartida de emboscada, sem tirar nenhuma Postura de 45–85 %.

Princípios: mecânica é Python (o motor monta o baralho; o LLM não entra); avaliadores congelados; Carta nova é autoria Opus com revisão Opus; `off` byte-idêntico.

## 2. Requisitos

### Integridade (valem para todas as etapas)

- **R1 — Avaliadores congelados.** Saem byte-idênticos à `main`, salvo o que a Etapa E muda (por outro agente):
  - `scripts/bestiario/arena.py`, `docs/spec332/arena_familias.py`, `docs/spec285/arena_lethality.py`;
  - `scripts/cards/sim.py`, `docs/spec335/arena_posturas.py`, `docs/spec341/arena_spec341.py`, `docs/spec355/arena_spec355.py`, `docs/spec362/arena_spec362.py`;
  - `data/cards/_orcamento.json`, `tests/fixtures/spec330_legacy_golden.json`, `tests/fixtures/spec330_card_text_snapshot.json`;
  - `tests/test_card_sim.py`, `tests/test_spec341_balanco.py`, `tests/test_spec355_arena.py`, `tests/test_spec287_encounter_scale.py`, `tests/test_spec290_chefe_sobrevivencia.py`, `tests/test_spec295_chefe_no_topo.py`.

  A faixa 45–85 %, o delta de 8 pp dos slots (`arena.py:42-43`, `:62-76`), os limiares do `sim.py` (`:48-54`) e o teto de 75 % por subclasse não mudam. Prova no pouso: `git diff --exit-code main -- <caminhos>`. Se o executor achar que precisa mexer num deles, para e registra para o dono.
- **R2 — `off` intocado.** Com `RPG_ENEMY_DECKS=off`, a montagem e a ficha de toda criatura **cuja ficha numérica não foi recalibrada** (R8) são idênticas às da `main`. Prova: teste que compara `ensure_combat_sheet` de todas as entradas do bestiário com `off` antes × depois (snapshot gerado na Etapa 0, antes de qualquer mudança).
- **R3 — Sementes.** Ajuste com as sementes **0–39** da arena do bestiário (as mesmas dos relatórios da 349). Confirmação com as sementes **40–119**, **uma vez**, depois do commit do pacote final (Etapa 6). Ajustar até passar na confirmação é proibido. Para as Posturas (Parte C): ajuste 0–19; confirmação **260–339** uma vez (0–259 já foram usadas pela 341/355/362).
- **R4 — Fora do alcance desta spec.** `acoes_por_rodada`, `vitalidade_por_nivel_encontro`, a regra de Corpo ≥ 2 do chefe, `tier`/`level_req`/`patamar`/`raridade` de Carta existente e qualquer Carta legada (`data/cards/{devoto,sangromante,corruptor,medico,arcanista,basicas,bestiario,exemplos,exemplos_extra,tiers_5_plus}.json`) não mudam.

### Etapa 0 — diagnóstico (nenhum arquivo de produto muda)

- **R5 — Snapshot e base.** `docs/spec373/base/`:
  - snapshot `off` de R2 (`ensure_combat_sheet` de todas as entradas, JSON ordenado);
  - arena dos 13 chefes da esteira, L5, sementes 0–39, `off,on` (`arena.py --ids …`), comparada célula a célula com `docs/spec349/arena-*.json`. Divergência não bloqueia; a causa provável vai para `docs/spec373/RELATORIO.md`;
  - arena das 4 Posturas de referência nas 0–19 (`docs/spec355/arena_spec355.py base --seeds 0:20`), para provar depois que as Partes A/B não mexem nela.
- **R6 — Decomposição do `on` dos chefes.** Novo `docs/spec373/diag_chefes.py` (importa `arena_familias.fight` e `enemy_decks` sem modificá-los; monkeypatch só dentro do processo, restaurado no `finally`). Para os 13 chefes, L5, sementes 0–39, `on`, cinco braços:
  - (a) atual;
  - (b) sem Cartas de família (`próprias + facção + fases`);
  - (c) família reduzida pela regra do R9 (simulada);
  - (d) sem a assinatura da família (as outras Cartas da família ficam);
  - (e) `acoes_por_rodada = 1`.

  Grava `docs/spec373/diag-chefes-0-39.json` e uma tabela no relatório. É diagnóstico: não vira critério.
- **R7 — Inventário de uso.** `docs/spec373/uso_familia.py` mede, para a população inteira com `on`, sementes 0–11 e ids de instância (`f"{bid}_1"` e `zlib.crc32(f"game-x|3|{bid}")`, como `tests/test_enemy_decks.py:358-371`):
  - criaturas por família (`family_key`) e por facção;
  - uso de cada `inf_*` (máximo por semente), separado em assinatura de família, Carta comum de família e Carta de facção;
  - para cada família: Cartas comuns e assinaturas que faltam para o máximo ficar ≤ 15 **depois do R9**, pela regra do R14.

  Grava `docs/spec373/uso-familia.json`.

### Parte B1 — regra de montagem para criatura com Cartas autorais (motor)

- **R8 — Recalibração numérica permitida.** Só pelos dials existentes do `calibrar.py` (`corpo`, `forca`, `dano`, `sig`; slots só `dano`/`sig`), dentro de ±7, mais a exceção do D4 (`dano`/`sig` de chefe até −9). Toda mudança fica em `data/bestiario/mecanica/_ajustes.yaml` com a leitura de arena que a motivou, e o bestiário é regenerado por `gerar_mecanica.py`. Criatura recalibrada sai do snapshot de R2 (lista explícita no relatório).
- **R9 — Família como tempero, não como baralho.** Em `build_enemy_deck`, com `on`, se a criatura tem **≥ 2** ids em `cartas_autorais` **e** `tactical_profile.assinatura` com `carta` própria:
  - a assinatura da família **não** entra no baralho (a da criatura já vale, `enemy_decks.py:323-341`);
  - a família contribui `1 + _h(cid, seed, "fam") % 2` Cartas comuns (1–2), escolhidas como hoje (hash, `_fits_creature`, sem as assinaturas);
  - a facção segue como hoje (0–3);
  - a reposição de ataque da curadoria (`_curate_shared`, `:253-257`) continua valendo dentro da cota.

  Criaturas sem Cartas autorais (a população da 332) montam **exatamente** como hoje. `family_signature` continua igual (o Presságio e o `padrao_publico` não mudam para elas).
- **R10 — Save e reconstrução.** O marcador `_deck332` e a reconstrução por `known & own >= 3` (`enemy_decks.py:275-290`) passam a usar o mínimo da regra nova: uma ficha montada pelo R9 pode ter só 1 Carta dos pools. A regra de "já montada" vira: `_deck332` presente **ou** (criatura do R9 e ≥ 1 Carta dos pools) **ou** (≥ 3 Cartas dos pools). Um save com baralho montado pela regra antiga (3–5) carrega com esse baralho, sem remontar.

### Parte A — chefes

- **R11 — Ordem das alavancas.** Depois do R9 (que vale para os 13 chefes e para as 281 criaturas da esteira):
  1. medir os 13 chefes (`off,on`, 0–39);
  2. para os que seguem fora: `calibrar.py --ids <ids>` (R8). Com o `on` mais perto do `off`, o calibrador pode **devolver** dials (subir de −7 em direção a 0);
  3. só se algum chefe seguir com `on` < 45 % depois de 1 e 2: R12;
  4. o que sobrar fora é registrado em §9 com a leitura, sem outra alavanca.
- **R12 — Ação extra do chefe (condicional).** Com `on`, na ação extra (`extra_actions > 0`, `conflict_orchestrator.py:2854-2860`) o chefe declara só Carta própria (`cartas_autorais` ou `baralho_extra` da fase) ou o ataque básico; Carta de família e de facção só na 1ª ação. `off` não muda. Entra **só** se o R11.3 acionar, com teste próprio (Etapa 4).
- **R13 — Metas da Parte A** (sementes 0–39, `arena.py` sem mudança):
  - os 9 chefes da tabela de §1 dentro de 45–85 % em `L5|off` e `L5|on`;
  - os 4 chefes que já estavam na faixa continuam nela;
  - os slots (`enemy_aranha_de_cristal`, `enemy_boss_general_escorpiao`) passam também no veredito completo do `arena.py` (faixa e delta contra `docs/spec349/arena-slots-baseline.json`; o delta só vale quando o slot estava na faixa antes, `arena.py:62-76`).

### Parte B2 — Cartas de família novas (conteúdo)

- **R14 — Quantas.** Pelo `uso-familia.json` medido **depois** do R9: para cada família `f` com `N_f` criaturas que ainda montam pela regra antiga e `M_f` pela regra do R9:
  - assinaturas: `S_f ≥ ceil(N_f / 8)` (mínimo 2, como hoje);
  - comuns: `P_f ≥ ceil((3·N_f + 1,5·M_f) / 8)`.

  Média de ~8 usos por Carta deixa folga para a variância do hash até 15. O número final é o menor que deixa o máximo ≤ 15 em todas as sementes 0–11 (R16); o relatório registra `N_f`, `M_f`, `S_f`, `P_f` antes e depois. [H] Pela conta com ~34 criaturas por família, são de 2 a 6 Cartas novas por família (≈ 25–60 no total), menos que as ~110 que seriam precisas sem o R9.
- **R15 — Autoria e revisão (Opus).** Cartas novas em `data/cards/inimigos/<familia>.json` (comuns) e em `_decks.json` `familias.<f>.assinaturas` (assinaturas, com `a_cada_n ≥ 2` e `telegrafo` com `{nome}`, `tests/test_enemy_decks.py:290-295`):
  - id `inf_<familia>_<slug>`, `classe: "Inimigo"`, `origem: "cartas-373"`, `patamar: inicial`, vocabulário da SPEC-330;
  - orçamento: `fx.budget_error(card) is None` na faixa `comum` (como a 332, `SPEC-332:70-71`); nenhuma Carta nova acima da Carta mais forte que já existe na família (`power_score`), para não endurecer as criaturas da 332;
  - voz: `card_lint` sem erro e sem aviso (≤ 4 palavras no nome, sem número no texto, léxico de Valoria), nome único no catálogo inteiro (`test_enemy_card_names_are_unique_across_the_whole_catalog`);
  - unicidade: nenhuma Carta nova com a mesma assinatura mecânica `(kinds, palavras-chave, gatilho, condição, custo)` de outra da mesma família (lint de redundância da 336);
  - nada de reforço/invocação (`test_enemy_cards_never_call_reinforcements`), nada de dano arcano/abissal/elemental em família só-melee sem conferir `_fits_creature`.

  Autor: subagente Opus (`model: "opus"`). Revisor: outro subagente Opus, com o checklist acima e veredito por Carta em `handoffs/SPEC-373-cartas-review.md`. O executor (Terra) não escreve texto de Carta.
- **R16 — Meta da Parte B.** Com a população inteira (sem pular `bestiario-349`), `on`, nenhuma `inf_*` em mais de 15 criaturas, nas sementes 0–11 e nos ids de instância (`tests/test_enemy_decks.py:358-371`); `bst_bote_certeiro` ≤ 15 como hoje (`:453-468`).
- **R17 — Regressão das 272.** Arena completa (12 regiões, 0–39, `off,on`) depois de B1+B2+A:
  - `off`: idêntico à base para toda criatura não recalibrada (R2);
  - nenhuma criatura que passava no veredito do `arena.py` passa a falhar por mais de 3 pp fora da faixa;
  - no máximo 5 criaturas passam a falhar por até 3 pp (borda), listadas no relatório e recalibradas pelo R8 se o executor conseguir em até 2 rodadas do `calibrar.py`;
  - o total de criaturas que passam no veredito completo fica ≥ 247 + 9 = **256 de 281** (base da 349: 247, `SPEC-349:672`).
- **R18 — Posturas intactas pelas Partes A/B.** `arena_spec355.py base --seeds 0:20` dá o mesmo JSON da Etapa 0 (R5), célula a célula. Se divergir, o executor registra a causa (a arena das Posturas usa criaturas do bestiário como encontro) e para.

### Parte C — Cartas de jogador (D9)

- **R19 — `bomba_estopim` (medir antes).** Sementes 0–19, `sim.py --protocolo lote` e `--protocolo lote-v2` para `arc1_imp_bomba_estopim`, mais a atribuição do Arcanista (`docs/spec362/arena_spec362.py atribuicao`). Resultado em `docs/spec373/bomba-0-19.json`. Se no `lote` a Carta já não tiver `dominante`, nada muda e o item fecha com a leitura.
- **R20 — Nerf da `bomba_estopim`.** Só número e custo, no mesmo objeto, até 2 passos, `versao` + 1 uma vez (`docs/guias/CARTAS.md`): −1 em `dano_base` (4 → 3) ou em `valor` (3 → 2) do efeito em área, +1 em `custo_folego`, ou `frequencia` um degrau mais restrita. Ordem: primeiro o efeito em área (`valor` 3 → 2). Metas, sementes 0–19:
  - `lote`: sem `dominante` (delta ≤ +8,0 pp e uso ≤ 60 %);
  - Arcanista `todas` total ≥ 46,5 % e `improvisador` padrão ≤ 75 %;
  - se o nerf derrubar o Arcanista abaixo de 46,5 %, reverte e registra para o dono (não há compensação nesta spec).
- **R21 — Corruptor: Carta `buff_iniciativa` (Opus).** Uma Carta nova do Corruptor em `data/cards/posturas/corruptor_tronco.json` (vale para todas as subclasses), `tipo: ativa`, efeito principal `buff_iniciativa`, `level_req` 1, `patamar`/`raridade` que a façam entrar em `sim.full_deck("Corruptor", L, sub)` para L ∈ {1, 3, 5} e todas as subclasses (o R17 da 355 só conta Carta presente no `full_deck`, `SPEC-355:182-183`). Voz da Postura (a Corrupção que antecipa), orçamento na faixa, `card_lint` sem aviso, `nota_voz` em `_ondas.yaml`. Autor e revisor Opus, como no R15.
- **R22 — Metas da Parte C.** Sementes 0–19, depois confirmação 260–339 uma vez:
  - Corruptor: emboscada realista (`arena_spec355.py emboscada`) ≥ 46,5 % nas 0–19 e ≥ 45,0 % na confirmação; total e subclasses dentro das faixas de sempre (45–85 % total, ≤ 75 % padrão por subclasse);
  - a Carta nova não acusa `dominante` no `lote` (o `em_branco` por uso é esperado em Carta que o bot não joga e fica registrado, como na 358);
  - Arcanista `todas` ≥ 45,0 % na confirmação;
  - as outras 3 Posturas com células idênticas às da Etapa 0.

### Fora de escopo

- Mudar avaliador, limiar, faixa, denominador, sementes do protocolo, `PROTOCOLO_LOTE`/`PROTOCOLO_LOTE_V2` ou trocar o default da esteira para o `lote-v2` (D5 da 358, spec própria).
- Recalibrar a referência do `lote-v2` (follow-up da 358 no ESTADO).
- As 19 criaturas não-chefe fora da faixa (`SPEC-349:642-669`), salvo as que o R17 obrigar; os efeitos que o motor não suporta (`SPEC-349:674-691`).
- `acoes_por_rodada`, `vitalidade_por_nivel_encontro`, Corpo de chefe, fases de chefe (`_decks.json` `fases`) e Cartas de fase (`data/cards/inimigos/chefes.json`).
- Baralhos das 4 facções sem deck (`SPEC-332:56`).
- Cartas de jogador fora da Parte C; Sangromante; `EXCECOES_TETO`.
- Ligar `RPG_ENEMY_DECKS=on` em staging/produção (decisão do coordenador depois do smoke §6).

## 3. Design técnico

**Arquivos novos**
- `docs/spec373/diag_chefes.py` (R6), `docs/spec373/uso_familia.py` (R7): scripts de diagnóstico, só importam.
- `docs/spec373/RELATORIO.md`, `docs/spec373/base/*.json`, `diag-chefes-0-39.json`, `uso-familia.json`, `arena-<regiao>.{json,md}` (pós), `confirmacao-40-119.json`, `bomba-0-19.json`, `posturas-0-19.json`, `confirmacao-posturas-260-339.json`.
- `tests/test_spec373_montagem.py`, `tests/test_spec373_cartas.py`, `tests/test_spec373_artefatos.py` (e `tests/test_spec373_acao_extra.py` se o R12 acionar).
- `handoffs/SPEC-373-cartas-review.md` (Opus), `handoffs/SPEC-373-sol-review.md`.

**Arquivos alterados**
- `services/enemy_decks.py`: `_autoral(creature) -> bool` (R9: ≥ 2 `cartas_autorais` e `tactical_profile.assinatura.carta`); `build_enemy_deck` com o ramo do R9; `apply_deck` com a regra de "já montada" do R10.
- `data/cards/inimigos/<familia>.json` e `_decks.json` (`familias.*.assinaturas`): Cartas da Parte B2.
- `data/bestiario/mecanica/_ajustes.yaml` + `data/bestiary.json` (via `gerar_mecanica.py`) + `data/cards/criaturas/*.json` (só se um dial de `dano`/`sig` mudar o número de uma Carta de criatura).
- `scripts/bestiario/calibrar.py`: `LIMITE_DANO_CHEFE = 9` (D4) só para `categoria == "chefe"` em `dano`/`sig`. É ferramenta de ajuste, não avaliador (`calibrar.py:11`).
- `data/cards/posturas/arcanista_cinzento_improvisador.json` (R20) e `corruptor_tronco.json` (R21), `data/cards/_ondas.yaml`.
- `services/conflict_orchestrator.py`: só se o R12 acionar (filtro da ação extra do chefe com `on`).
- **Etapa E (outro agente):** `scripts/bestiario/arena.py` (`--seed-inicio`, default 0) e os testes de teto (`tests/test_enemy_decks.py`, `tests/test_spec349_mecanica.py`).

**Assinaturas**
```python
# services/enemy_decks.py
def _autoral(creature: dict) -> bool: ...          # R9
def build_enemy_deck(creature: dict, seed: int | str = 0) -> list[str]: ...  # assinatura pública inalterada
```

**Exemplo (R9), `mon_peso_dos_vencidos` (`predador_apice`, 3 autorais, assinatura própria `cri_peso_dos_vencidos_soco_de_cima`):** hoje `3 próprias + assinatura da família + 2–4 comuns` (5–8 Cartas da família/facção); depois `3 próprias + 1–2 comuns de predador_apice + 0–3 da facção`.

## 4. Plano passo a passo

Python sempre por `bash scripts/dev/py.sh …`. Testes do escopo com `-n 2` no máximo. Arena completa (Etapa 5) uma região por vez, em background com timeout, nunca em paralelo com outra arena.

### Etapa E — autoria de eval (agente diferente do executor, antes da Etapa 0)

1. **Testes** (`tests/test_spec373_artefatos.py::test_arena_seed_inicio_default_identico`): `arena.py --ids enemy_gargula_ferro --seeds 2` com e sem `--seed-inicio 0` dá o mesmo JSON; `--seed-inicio 40 --seeds 2` usa as sementes 40 e 41.
2. **Implementação:** `--seed-inicio` em `scripts/bestiario/arena.py` (`range(inicio, inicio + seeds)`), sem outra mudança. Commit próprio "eval: arena seed offset (SPEC-373)". Se o caminho estiver em `evals/protected-paths.txt` no dia, seguir `/eval-publish`.
3. **Verificação:** o teste acima; `git diff main -- scripts/bestiario/arena.py` só com o argumento novo.

### Etapa 0 — base e diagnóstico (Terra)

1. **Testes** (`tests/test_spec373_montagem.py`): `test_snapshot_off_existe_e_bate` lê o snapshot da R5 e compara com `ensure_combat_sheet` de todas as entradas (`off`).
2. R5, R6, R7. Relatório com: tabela dos braços (a)–(e) por chefe; uso por família; `N_f`/`M_f`; a leitura da R18.
3. **Ponto de decisão registrado no relatório:** se o braço (c) não aproximar o `on` do `off` em pelo menos 6 dos 9 chefes, o executor registra o achado e segue (o R11 continua valendo), sem inventar alavanca nova.

### Etapa 1 — R9/R10 (TDD)

1. **Testes** (`tests/test_spec373_montagem.py`):
   - `test_autoral_sem_assinatura_da_familia`: criatura da esteira com `on` não tem nenhuma assinatura de família no baralho;
   - `test_autoral_familia_1_ou_2`: o baralho tem 1–2 Cartas comuns da família, determinístico por id+seed;
   - `test_populacao_332_identica`: para toda entrada sem `cartas_autorais`, `build_enemy_deck` igual ao da `main` (fixture gerada na Etapa 0) nas sementes 0–11;
   - `test_off_identico`: snapshot `off` igual (R2);
   - `test_save_antigo_nao_remonta`: ficha com baralho antigo (3–5 da família) e sem `_deck332` não remonta; ficha do R9 com 1 Carta de pool e sem marcador também não;
   - `test_round_trip_save_load_on`: `save_game_state`/`load_game_state` com um chefe da esteira montado pelo R9 mantém `cartas` e `fase_idx`.
2. **Implementação:** `enemy_decks.py`.
3. **Verificação:** `tests/test_spec373_montagem.py tests/test_enemy_decks.py tests/test_boss_phases.py tests/test_spec349_mecanica.py -n 2`.

### Etapa 2 — chefes (R11, R13)

1. Arena dos 13 chefes (0–39). Para os fora: `calibrar.py --regioes <r> --ids <ids> --seeds 40 --rodadas 6` (o `calibrar` chama o `arena.py`, `calibrar.py:56-72`). Registrar cada rodada no relatório.
2. Se o R11.3 acionar: Etapa 4 antes de seguir.
3. **Verificação:** `tests/test_spec349_*.py tests/test_spec287_encounter_scale.py tests/test_spec290_chefe_sobrevivencia.py tests/test_spec295_chefe_no_topo.py -n 2` verdes; `validate_content.py` com 0 erro.

### Etapa 3 — Cartas de família (R14–R16)

1. **Testes** (`tests/test_spec373_cartas.py`):
   - `test_cartas_373_vocabulario_orcamento_voz`: toda `origem == "cartas-373"` passa vocabulário, orçamento, voz e lint sem aviso;
   - `test_cartas_373_nao_mais_fortes_que_a_familia`: `power_score` ≤ o máximo da família na `main`;
   - `test_assinaturas_373_telegrafo`: toda assinatura nova tem `a_cada_n ≥ 2`, `{nome}` no telegrafo e a Carta no pool da família;
   - `test_uso_populacao_inteira_ate_15` (informativo durante a autoria, com `xfail(strict=False)` até a Etapa E2).
2. **Autoria:** subagente Opus escreve as Cartas pelo número do R14; subagente Opus revisor dá o veredito (R15). Cartas `CHANGES` voltam ao autor; o executor só aplica as aprovadas.
3. **Verificação:** os testes acima + `tests/test_enemy_decks.py tests/test_card_lint.py -n 2`; `uso_familia.py` refeito, com máximo ≤ 15.

### Etapa 4 — ação extra do chefe (só se o R11.3 acionar)

1. **Testes** (`tests/test_spec373_acao_extra.py`): com `on`, a ação extra do chefe nunca declara Carta de família/facção; com `off`, a declaração é igual à da `main` (mesma seed); a 1ª ação segue podendo jogar a Carta de família.
2. **Implementação:** filtro no ponto em que a ação extra escolhe Carta (`conflict_orchestrator.py`, após `:2854`).
3. **Verificação:** `tests/test_spec295_chefe_no_topo.py tests/test_enemy_decks.py tests/test_spec373_*.py -n 2`.

### Etapa 5 — regressão completa (R17, R18)

1. `arena.py --regiao <r> --seeds 40 --modo off,on --baseline docs/spec349/arena-slots-baseline.json --json docs/spec373/arena-<r>.json --md docs/spec373/arena-<r>.md`, uma região por vez.
2. Tabela antes × depois por região no relatório (mesmo formato de `SPEC-349:624-638`), lista de regressões (borda e fora), e a R18.
3. Regressões de borda: até 2 rodadas do `calibrar.py` nas criaturas afetadas; regenerar e remedir só elas.

### Etapa 6 — confirmação da Parte A/B (uma vez)

1. Commit do pacote final. Depois: `arena.py --ids <13 chefes + recalibradas> --seed-inicio 40 --seeds 80 --modo off,on --json docs/spec373/confirmacao-40-119.json`.
2. Fora da faixa na confirmação: registrar em §9, **sem reajuste** (R3).

### Etapa E2 — teto de volta nos testes (agente diferente do executor)

1. Remover o `continue` de `origem == bestiario-349` nos 3 testes de `tests/test_enemy_decks.py` (`:304-305`, `:366-367`, `:463-464`); em `tests/test_spec349_mecanica.py:226-237`, teto 36 → 15, com docstring citando esta spec (`SUPERADO_POR: SPEC-373`). Tirar o `xfail` da Etapa 3.
2. Commit próprio "test: restore family card cap (SPEC-373)".
3. **Verificação:** `tests/test_enemy_decks.py tests/test_spec349_mecanica.py tests/test_spec373_cartas.py -n 2`.

### Etapa 7 — Parte C (R19–R22)

1. R19 (medição). Se houver `dominante`: R20, um passo por vez, remedindo só o Arcanista (`todas` + 3 subclasses) e a Carta no `lote` (0–19).
2. R21: autoria Opus + revisão Opus; teste `test_corruptor_tem_buff_iniciativa_no_full_deck` (L1/L3/L5 × subclasses) em `tests/test_spec373_cartas.py`; teste de que a Carta não é legada (`origem` de onda).
3. Arena das Posturas nas 0–19 (`arena_spec355.py base` e `emboscada`) → `docs/spec373/posturas-0-19.json`.
4. Commit do pacote. Confirmação 260–339 uma vez → `docs/spec373/confirmacao-posturas-260-339.json`. Sem reajuste.
5. **Verificação:** `tests/test_spec341_balanco.py tests/test_spec355_arena.py tests/test_spec362_*.py tests/test_card_lint.py tests/test_spec373_cartas.py -n 2` (o 341 trava versões: se a `bomba_estopim` estiver nas `versoes` da 341, parar e devolver, como a D17 da 355).

### Etapa 8 — revisões

1. Opus: Cartas novas (R15/R21), já feito nas Etapas 3/7; o registro fica em `handoffs/SPEC-373-cartas-review.md`.
2. Sol: motor (R9/R10/R12), integridade (R1, R3), artefatos e relatório → `handoffs/SPEC-373-sol-review.md`.

## 5. Critérios de aceite

- [ ] R1: `git diff --exit-code main` vazio nos avaliadores (exceto o `--seed-inicio` da Etapa E, em commit de outro agente)
- [ ] R2: snapshot `off` igual para toda criatura não recalibrada (lista das recalibradas no relatório)
- [ ] R9/R10: regra de montagem com testes; população da 332 idêntica; save antigo não remonta
- [ ] R13: 9 chefes em 45–85 % em `off` e `on` nas 0–39; os 4 que estavam na faixa continuam; slots passam no veredito completo
- [ ] R16: nenhuma `inf_*` acima de 15 na população inteira, sementes 0–11 e ids de instância; testes da 332 sem exceção (Etapa E2, outro agente)
- [ ] R15: Cartas novas aprovadas por revisor Opus, com veredito por Carta registrado
- [ ] R17: ≥ 256 de 281 no veredito completo; zero regressão > 3 pp; ≤ 5 de borda, listadas
- [ ] R18: arena das Posturas 0–19 idêntica depois das Partes A/B
- [ ] Confirmação 40–119 gravada uma vez, com o resultado em §9 (fora da faixa = registro, não reajuste)
- [ ] Parte C (se não migrar para a 369, D9): R19–R22, confirmação 260–339 gravada uma vez
- [ ] `validate_content.py` com 0 erro; `card_lint` sem aviso nas Cartas novas
- [ ] `uv run pytest` verde (suíte completa, pelo coordenador, no pouso)
- [ ] Guard de FallbackLLM: N/A (nenhum `with_structured_output` novo)
- [ ] Saves antigos continuam carregando (R10, `test_save_antigo_nao_remonta`, `test_round_trip_save_load_on`)
- [ ] Smoke §6 executado e registrado em §9

## 6. Smoke test com LLM real

Feito pelo coordenador (ou pelo executor com a chave), com `RPG_ENEMY_DECKS=on RPG_ENEMY_INTENT=on` e as Cartas `on` (staging ou `uvicorn` local). São ~10–15 requests de turno (DeepSeek primário), sem custo relevante. As rodadas do conflito não chamam LLM (SPEC-346), então o ponto do smoke é a montagem real, o texto e o fim do combate narrado.

1. **Chefe da esteira em jogo:** jogo novo, levar o personagem a `mon_peso_dos_vencidos` (ou outro dos 9) por ação de combate em `montanhas_afiadas` (ou usar o caminho de spawn do smoke da 349). Conferir no `/game/state`: baralho do chefe = próprias + 1–2 da família + facção, sem assinatura de família; o telegrafo da assinatura **própria** aparece 1 rodada antes.
2. **Duas ações e fase:** jogar até a troca de fase (60 %). A narração da fase aparece; a ação extra da rodada (e, se o R12 acionou, sem Carta de família) aparece no registro do combate.
3. **Criatura da 332:** um encontro com uma criatura sem Cartas autorais (ex.: `enemy_gargula_ferro`): baralho com 3–5 da família, como antes.
4. **Carta nova de família:** um encontro em que uma Carta `cartas-373` cai no baralho; o texto aparece no painel com nome e descrição sem número.
5. **Parte C:** um conflito com o Corruptor em que a Carta `buff_iniciativa` nova está na mão numa emboscada (inimigo age primeiro): a emboscada é anulada. Um conflito com o Arcanista improvisador com a `bomba_estopim` na mão mostra o número novo (se o R20 acionou).

Registrar `game_id`, provider por chamada e `mock=False` em `docs/spec373/smoke.md`.

## 7. Riscos & compatibilidade

- **O R9 muda o `on` de 281 criaturas.** É a maior mudança desta spec. O `on` dessas criaturas tende a subir em direção ao `off` (hoje 253 de 281 têm o `off` na faixa). Defesas: arena completa (R17) com critério de regressão fixado aqui, não pelo executor; recalibração só por dials registrados; a população da 332 fica idêntica (teste).
- **Ruído.** Cada célula da arena do bestiário tem 200 lutas (erro padrão ~3,5 pp). Por isso a borda de 3 pp no R17 e a confirmação 40–119 (400 lutas por célula). Com 281 criaturas, algumas trocas de borda são esperadas por acaso; o teto de 5 as contém.
- **Dials que voltam.** Com o `on` mais fácil, o calibrador pode subir dials que estavam em −7. Isso muda o `off` dessas criaturas: elas saem do snapshot de R2 e o relatório lista.
- **Cartas novas endurecem a 332.** As comuns entram no pool que as 124 criaturas antigas também sorteiam. Defesas: teto de `power_score` (R15) e a arena completa (R17), que inclui as criaturas da 332 presentes nas regiões.
- **Assinaturas novas mudam o Presságio das criaturas da 332.** `family_signature` escolhe por hash entre `len(sigs)`; com mais assinaturas, parte das criaturas antigas troca de assinatura. É o custo do teto (a 332 já sabia: "uma de duas, para que nenhuma carta fique em mais de ~15", `enemy_decks.py:178-179`). O `padrao_publico` e o `bestiary_knowledge` não guardam a assinatura, então não há migração.
- **Saves.** Instâncias em combate guardam `cartas` e `_deck332`; o R10 impede remontagem. Templates do bestiário não guardam baralho.
- **Parte C e o gate de versões da 341.** Hoje `arc1_imp_bomba_estopim` não aparece em `docs/spec341/arena-{final,confirmacao}.json` (conferido por busca em 03/11). Se aparecer no dia da execução, a Etapa 7 para (D17 da 355).
- **MockLLM/FallbackLLM:** sem impacto (nenhum LLM novo). **Quota/latência:** nenhuma chamada nova; o custo é de CPU local (arena completa ~112 mil lutas; rodar por região, sem paralelo, por causa da RAM).

## 8. Decisões

### Do dono

- **03/11 — "transforme em spec e execute agora".** A spec nasce `approved`.
- **27/10 — arena 45–85 % aprovada** (memória `cartas-autorizacao-dono`); **28/10 — autoria e revisão de conteúdo com Opus**, nunca Fable.

### Do autor (valem como aprovadas; revogáveis pelo dono)

- **D1 — Família como tempero para quem tem Cartas autorais (R9).** É uma emenda ao R3 da 332 ("3–5 da família"), só para criaturas com identidade própria. Ataca as duas pendências de uma vez: tira do chefe as Cartas que dominam o `on` e divide o uso por ~3 nas 281 criaturas da esteira. A alternativa de manter 3–5 e só escrever Cartas pediria ~110 Cartas novas (R14 sem o R9) e não resolveria os chefes.
- **D2 — Sem mexer em `acoes_por_rodada`, Vitalidade por nível ou Corpo (R4).** São regras de outras specs (295, 287, 290) travadas por teste. A ação extra só ganha filtro (R12) se o resto não bastar.
- **D3 — R12 condicional.** Mudar o que a ação extra declara muda a leitura do combate de todo chefe; só entra com evidência da Etapa 2.
- **D4 — `dano`/`sig` de chefe até −9.** Só para chefe, registrado no `_ajustes.yaml`. Os dials de chefe estão todos em −7; dar 2 passos extras é a menor mudança numérica que sobra antes do R12.
- **D5 — Sementes:** 0–39 para ajuste (as mesmas dos relatórios da 349, comparação direta) e 40–119 para confirmação. O `--seed-inicio` é mudança de avaliador e fica com outro agente (Etapa E).
- **D6 — Critério de regressão fixado na spec (R17):** borda de 3 pp e no máximo 5 casos. Fixar aqui impede o executor de desenhar o critério que vai cumprir.
- **D7 — Teto de volta por outro agente (Etapa E2),** como o `EXCECOES_PISO` da 362 (D7 de lá): quem escreve as Cartas não edita o gate.
- **D8 — Conta de Cartas pela fórmula do R14,** com o número final medido. Se passar de 60 Cartas novas, o executor para depois da Etapa 0 e registra (é mais que 3 ondas da 336).
- **D9 — Parte C nesta spec.** `bomba_estopim` e o Corruptor são Cartas de jogador e usam outra arena (Posturas); não dependem das Partes A/B, que só precisam provar que não as mexem (R18). Ficam aqui porque o coordenador pediu e o processo é o mesmo (autoria Opus, avaliador congelado, confirmação uma vez). **Se a SPEC-369 (`cartas-balanco-metas-epico`, reservada em `draft`) for escrita para cobrir esses dois itens, a Parte C sai desta spec** e o coordenador apaga a Etapa 7 antes de despachar o executor.
- **D10 — `lote` (v1) é o gate da `bomba_estopim`; o `lote-v2` é só informativo.** A 358 deixou o v1 como default (D5 de lá), e o revisor Sol avisou que a referência do v2 é forte demais para provar que uma Carta é boa (`SPEC-358:344`).
- **D11 — Nerf da `bomba_estopim` pelo efeito em área primeiro.** O dano em `inimigos` é o que escala com grupo, e a arena tem encontros de grupo.

### Para o dono confirmar (não bloqueiam a execução)

1. D1 (emenda ao R3 da 332 para criaturas com Cartas autorais).
2. D9: Parte C aqui ou na 369.
3. D8: teto de 60 Cartas novas antes de parar.

## 9. Registro de execução

_(vazio; o executor preenche: commits, números da Etapa 0, rodadas do calibrador, Cartas aprovadas/recusadas, confirmação, smoke)_
