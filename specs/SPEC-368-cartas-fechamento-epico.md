# SPEC-368 — Cartas: fechamento do épico (bug do rollback, conteúdo faltante, métricas nunca medidas e smoke dos §6 não verificados)

> **Status:** `done` (04/11, coordenador, autorização do dono "manda bala"; fechamento na nota final)
> **Criada:** 2026-11-02 · **Atualizada:** 2026-11-02
> **Depende de:** SPEC-364 `done`; SPEC-367 (achados do smoke final) pode correr em paralelo — arquivos disjuntos exceto `agents/combat.py` (rebase)
> **Desbloqueia:** fechar como `done` as specs 327–333, 335, 336, 345–347, 352, 355 e 357 do épico de cartas

---

## 1. Contexto & Objetivo

O épico de cartas (327–364) está na `main` e `on` no staging desde 02/11. A auditoria de fechamento de 02/11
(coordenador, só leitura, contra §5/§6 de cada spec, revisões em `handoffs/` e os smokes
`docs/spec363/achados-smoke3.md`, `docs/spec364/achados-smoke4.md`, `docs/spec364/smoke-final.md`) fechou
334/342/353/354/362/363/364 e deixou 15 specs abertas por quatro motivos:

1. **Um bug ainda aberto** — R-4 da revisão da 328 (`handoffs/SPEC-328-sol-review.md:63`): o rollback
   `RPG_CARD_DECK` `on → off` só roda dentro do nó de combate (`agents/combat.py:2184`,
   `services/card_piles.py:122` `deactivate_deck`). Fora de combate, com a flag já `off`, `api._cards_block`
   (`api.py:~2550`) e `set_prepared` ainda veem as Preparadas derivadas do baralho até o próximo conflito.
   (R-1, R-2, R-3 e R-5 da mesma revisão foram conferidos corrigidos em 02/11: `apply_pact` debita Entropia,
   `undo_pact` desfaz só o delta, recusa não rerrola o Presságio em `agents/combat.py:2916`.)
2. **Conteúdo faltante declarado nas próprias specs** — 332: 4 facções do bestiário sem baralho
   (`tribos_devoradores_sol`, `bandos_nomades`, `colmeia_hospedeiros`, `mercadores_escravos_pradaria`);
   333: "Dor Surda" sem a opção "1 Fôlego para descartar" e `essencia_de_cinza` sem fonte de drop;
   330 D-13: escolha do descartar na UI, `_bump` (335) e Fardo por evento do Abismo.
3. **Métricas de aceite nunca medidas** — 327 §6 (≥ 2 Cartas por rodada, ≥ 60 % das rodadas com ≥ 3 escolhas,
   uso > 60 %, p95 ≤ 10 rodadas), 331 (p95 ≤ 10 rodadas), 329 ("arena `on`: dano recebido cai" — só `shadow`
   medido), 355 item 19 (319 P2-1, `replace` do stream medido).
4. **Itens de §6 que nenhum smoke real viu** — listados no §6 desta spec.

Objetivo: corrigir 1 e 2 com TDD, medir 3 de forma determinística (arena/bot, sem LLM), executar 4 num smoke real
único e roteirizado, e então fechar as 15 specs com evidência. Princípio: **mecânica é Python, não LLM**; a medição
é do motor; o smoke real só confirma o que o motor já prova.

## 2. Requisitos

### A. Rollback `on → off` fora de combate (328 R-4)

- **R1** — Com `RPG_CARD_DECK=off`, todo ponto que lê Preparadas fora de combate (`api._cards_block`,
  `set_prepared`, carregamento de save) vê as Preparadas de antes do baralho (`prepared_cards_pre_deck`), nunca as
  derivadas do baralho. Implementação idempotente: `deactivate_deck` chamado no load do save e no `_cards_block`
  quando `mode() == "off"` e o jogador ainda tem marca de baralho ativo.
- **R2** — `off → on → off` fora de combate é round-trip exato das Preparadas (save/load incluído).
- **R3** — Com `on`, nada muda (teste de não-regressão do caminho `on`).

### B. Conteúdo faltante (332, 333, 330 D-13)

- **R4** — As 4 facções sem baralho ganham baralho próprio em `data/cards/` no formato dos baralhos de facção
  existentes, cada uma com ≥ 1 Carta que nenhuma outra família/facção tem, passando `card_lint`, orçamento
  (`fx.budget_error is None`) e a gramática da 330. Voz das Cartas: aprovação em bloco do dono de 27/10
  (memória `cartas-autorizacao-dono`). Tema de cada facção a partir do Codex/bestiário (Grep, nunca Read inteiro).
- **R5** — Critério da 332 "cada família e facção com ≥ 1 Carta exclusiva" vira teste sobre o catálogo real
  (11 famílias + **toda facção que tem criatura no bestiário**, derivada do `data/bestiary.json`, sem lista fixa nem
  exceção; 24 facções em 03/11: as 14 da 332/368 e as 10 que a 349 trouxe).
- **R6** — "Dor Surda" ganha a jogada "1 Fôlego para descartar" (contrato aditivo na view da mão; botão na UI do
  combate; sem LLM). Fôlego insuficiente → recusa explicada sem gasto.
- **R7** — `essencia_de_cinza` ganha ≥ 1 fonte de drop determinística (tabela de espólio existente), coberta por
  teste de que é obtível.
- **R8** — 330 D-13: (a) escolha do descartar na UI (o mesmo mecanismo do R6, generalizado para efeitos que pedem
  descarte); (b) `_bump` da 335 — confirmar no source; se já resolvido, registrar com arquivo:linha, senão corrigir;
  (c) Fardo por evento do Abismo — confirmar se algum evento do Abismo deve gerar Fardo pela 330; implementar se a
  spec prometeu, ou registrar a decisão de não fazer com motivo.

### C. Métricas medidas (327, 329, 331, 355)

- **R9** — Script determinístico `docs/spec368/metricas_epico.py` (sobre o bot/arena existentes; sem tocar em
  `scripts/cards/sim.py`, `docs/spec3*/arena_*.py`, orçamento nem golden — integridade de eval) mede nas sementes
  0–19 com cartas `on`: Cartas jogadas por rodada (média e p50), % de rodadas com ≥ 3 escolhas válidas, % de
  Cartas da mão usadas, p95 de rodadas por conflito, por Postura e total. Saída em
  `docs/spec368/metricas-0-19.json`.
- **R10** — 329: dano recebido pelo herói por conflito `on` (Presságio visível) vs `off`, mesmas sementes; registrar
  Δ. Se `on` não reduzir, registrar o número e abrir follow-up (não ajustar balanço nesta spec).
- **R11** — 355 item 19: medir o `replace` do stream (319 P2-1) com o harness de latência existente e registrar.
- **R12** — Os números do R9–R11 vão para o §9 das specs 327/329/331/355 como evidência; meta não atingida →
  registrar o número e o follow-up, sem mudar o critério (o critério é do dono).

### D. Smoke real dos §6 não verificados

- **R13** — Cenários determinísticos (sem LLM) para cada situação do §6. (a) `tests/fixtures/spec368_seed.py::seed_save(item, variant=)`
  grava um **save `legacy` real** (jogo criado e conflito aberto pela API, receita aplicada, `save_game_state`) para os itens
  1–7, 12–14, com teste de round-trip save → load → `/game/state` (`tests/test_spec368_seed.py`); o espólio do item 6 sai
  determinístico (`variant="espolio"`). (b) `tests/fixtures/spec368_scenarios.py` prova as mesmas situações no motor.
  (c) Itens 8–11 (draft.py, modo `off`, router esgotado, retrato/concorrência) não têm save: roteiro executável no §9.

### Fora de escopo

- Balanço (Arcanista/Sangromante/`bomba_estopim`) — follow-ups próprios.
- Achados A1–A7 do smoke final → SPEC-367.
- SPEC-359/360/361 (bestiário/criaturas) — outra sessão.

## 3. Design técnico

- **Alterados:** `services/card_piles.py` (rollback idempotente exposto p/ API), `api.py` (`_cards_block`, load),
  `persistence.py` só se o load for o ponto certo (confirmar na Etapa 0), `data/cards/<faccao>.json` ×4 (ou o
  diretório onde vivem os baralhos de facção — confirmar), `data/cards/status_e_maldicoes.json` (Dor Surda),
  tabela de espólio de `essencia_de_cinza`, view da mão + `web/src/combat/*` (botão "Descartar (1 Fôlego)").
- **Novos:** `docs/spec368/metricas_epico.py`, `docs/spec368/metricas-0-19.json`,
  `tests/fixtures/spec368_scenarios.py`, `tests/test_spec368_*.py`, `docs/spec368/smoke-final.md` (coordenador).
- **Contrato:** aditivo; `web/e2e/contracts` e golden da 330 intocados; nenhuma flag nova.

## 4. Plano passo a passo

### Etapa 0 — Confirmação (sem código de produto)
Confirmar no source e anotar no §9: pontos de leitura de Preparadas fora de combate; onde vivem os baralhos de
facção; estado de `_bump` e do Fardo por evento do Abismo; harness de latência do R11.

### Etapa 1 — Rollback (R1–R3)
Testes primeiro: `test_off_outside_combat_restores_pre_deck`, `test_round_trip_off_on_off_with_save`,
`test_on_path_unchanged`.

### Etapa 2 — Conteúdo (R4–R8)
Testes primeiro: `test_every_family_and_faction_has_exclusive_card`, `test_new_faction_decks_lint_and_budget`,
`test_dor_surda_discard_costs_one_folego`, `test_dor_surda_discard_refused_without_folego`,
`test_essencia_de_cinza_obtainable`. Depois Cartas e UI (node test do botão).

### Etapa 3 — Métricas (R9–R12)
Script + JSON; teste que o script roda em 2 sementes e produz o schema esperado.

### Etapa 4 — Cenários (R13)
Uma fixture por item do §6; teste offline de cada uma (estado chega à situação pedida).

## 5. Critérios de aceite

- [x] Etapa 0 anotada em §9
- [x] R1–R3 com testes verdes, incluindo save/load
- [x] R4–R8 com testes verdes; lint e orçamento limpos; voz conferida pelo revisor
- [x] R9–R12: JSON gerado e números registrados nas specs 327/329/331/355
- [x] R13: fixtures testadas offline
- [x] 0 LLM por rodada; golden da 330 sem diff; `web/e2e/contracts` sem diff; sem flag nova; saves antigos carregam
- [x] Guard de FallbackLLM mantido; nenhum `with_structured_output` novo
- [x] `uv run pytest` verde (suíte completa, coordenador, no pouso) — escopo verde no executor; [x] `npm run typecheck`, `typecheck:e2e`, `lint`, `test` verdes; [x] `ruff format --check .` e `ruff check .` limpos
- [x] Revisão independente `Sol` sem achado aberto
- [x] **Smoke real §6 (coordenador)** registrado em `docs/spec368/smoke-final.md`

## 6. Smoke test com LLM real (coordenador; `seed_save` do R13 leva o jogo real a cada cena dos itens 1–7, 12–14; itens 8–11 pelo roteiro do §9)

Local `legacy` com o preset do staging (cartas `on`) salvo onde indicado. Registrar provider/modelo/custo.

1. **328 §6.2** — Pacto do Abismo: emprestar Fôlego debita Entropia e soma Carga 1×/rodada; recusa não rerrola o
   Presságio. **R1–R3** ao vivo: desligar `RPG_CARD_DECK` fora de combate e ver as Preparadas antigas.
2. **329 §6.2/§6.3** — família estudada mostra faixa e nome; presságio frustrado.
3. **330 §6** — combo Eco; Rachadura + golpe com número igual ao texto.
4. **331 §6.2** — escolta com `proteger`.
5. **332 §6** — assinatura da Legião, padrão visível, troca de fase do chefe; 1 combate com facção nova do R4.
6. **333 §6.1/§6.3** — espólio da Mão Sombria com Carta da facção; descanso longo para Esquecer; Dor Surda
   descartada por 1 Fôlego (R6).
7. **335 §6** — 1 conflito com Corruptor e 1 com Médico.
8. **336 §6** — `draft.py` com chave real → lint → sim → promover → jogar (1 Carta; custo registrado).
9. **345 §6.1** — modo `off` no staging (deploy com cartas `off` só para este item, depois volta `on`) — ou local
   com o preset `off`, registrando a escolha.
10. **346 §6.5/§6.6/§6.7** — router esgotado (provider forçado a falhar), CLASSIFY só no Groq, rodada `off`; morte
    real vista ao vivo.
11. **347 §6.5 / 352 §6.1/§6.4/§6.5** — importar imagem pelo script; "Agora não" sem cotação e sem request; chefe
    `unico:{game}` isolado entre duas contas; duas confirmações concorrentes (só uma cobra). Custo do provedor da
    imagem registrado. `image_generation` ligado só durante o item e desligado no fim (conferir com `list`).
12. **354** — toast a 1440 no instante da vitória.
13. **355 §6** — Voto em Ketil, Leitura de Pressão, Armadura Comprometida, Renegado, vitória com Reação.
14. **357 §6.5** — quest de lore `justa` entregando técnica.

## 7. Riscos & compatibilidade

- Saves: R1 é idempotente e só restaura um campo já existente (`prepared_cards_pre_deck`); saves sem baralho não mudam.
- Integridade de eval: R9 é ferramenta nova em `docs/spec368/`; avaliadores, orçamento, golden e arenas antigas ficam intocados.
- Custo: smoke ~40 turnos + 1 Carta por `draft.py` + 1–2 imagens; dentro do teto diário (R$ 5) se feito em 1 dia — senão em 2.

## 8. Decisões

- **D-368-1 (coordenador):** métricas que não atingirem a meta são registradas com número e follow-up; o critério
  numérico não muda sem o dono.
- **D-368-2 (coordenador):** o item 9 do §6 pode rodar local com preset `off` em vez de um deploy `off` no staging.

## 9. Registro de implementação

### Etapa 0 — Confirmação no source (02/11)

- **Leitura de Preparadas fora de combate:** `api._cards_block` (`api.py:2540`, usa `prepared_cards`/`deck`), `cards.set_prepared` (`services/cards.py:412`) e o load do save (`persistence.load_game_state`, fim da função). Antes só o nó de combate rodava `deactivate_deck` (`agents/combat.py:2181`).
- **Baralhos de facção:** `data/cards/inimigos/faccao_<id>.json` lidos por `enemy_decks._pools()` (stem `faccao_`); 10 existiam, faltavam as 4 do R4. O catálogo de "facções" do R5 = os 14 arquivos (a ligação ao bestiário é por `faction` → `_fold`).
- **`_bump` (330 D-13b):** `services/card_effects.py:943`; segue mexendo na 1ª chave de `valor/dano_base/n`. Nenhuma Carta do catálogo tem 2 chaves (checado em 02/11, 6 Cartas com Ressoar), então não havia bug vivo; **fixado na autoria** com `validate_card` (erro "Ressoar exige uma só chave de valor") + teste do catálogo.
- **Fardo por evento do Abismo (330 D-13c):** **decisão: não fazer.** O Abismo já planta Fardo pela 333 R9 (Sussurro do Abismo que apodrece em Estilhaço de Cinza, `card_status._rot_sussurro`) e a 330 só cita "efeito de inimigo/Abismo" no glossário (não é R). Um gatilho novo por evento mudaria o dano medido pela arena da 362 sem decisão do dono; fica como follow-up de balanço se o dono quiser.
- **Harness do R11:** não há harness de latência para o `replace` (o `latency_journeys.py` mede turnos, não stream); a medição offline é `tests/test_spec368_replace.py` (ver SPEC-355 §10).

### Entregue

- **R1–R3** (commit `c9a4aa78`): `card_piles.sync_deck_mode` (idempotente) chamado no load do save, em `_cards_block` (sobre cópia, sem mutar o chamador) e em `set_prepared`. Testes: `tests/test_spec368_rollback.py` (off fora de combate, round-trip off→on→off com save/load, caminho `on` intacto).
- **R4/R5**: 4 baralhos (`tribos_devoradores_sol`, `bandos_nomades`, `colmeia_hospedeiros`, `mercadores_escravos_pradaria`), 6 Cartas cada, voz de Valoria, temas tirados das criaturas do bestiário; `tests/test_spec368_content.py` (11 famílias + 14 facções, cada uma com ≥ 1 Carta exclusiva, sem exceção; lint + orçamento limpos).
- **R6/R8a**: jogada `discard` (`PlayStepRequest.action_kind="discard"`), campo autoral `descartar_folego` (Dor Surda = 1) paga só Fôlego próprio (sem Pacto), tira a Carta do ciclo (exaurida); recusa explicada sem gasto; a mão ganha `descartar_folego`/`descarta_escolha` (aditivos). `descartar` com `escolha` aceita as Cartas marcadas na UI (`PlayStepRequest.descartar`, ≤ 4) e completa pela política antiga. UI: botão "Descartar (N Fôlego)" e chips "Descartar até N" na mira. Testes: `tests/test_spec368_discard.py`, `web/tests/deck-368-discard.test.mjs`.
- **R7**: `essencia_de_cinza` entra no pool `raro` da tabela `default` de `data/loot_tables.json`; teste de que é obtível por `roll_loot`.
- **R9–R12**: `docs/spec368/metricas_epico.py` + `metricas-0-19.json`; números em 327 §7, 329 §8, 331 §10 e 355 §10 (resumo abaixo). Teste: `tests/test_spec368_metricas.py`.
- **R13**: `tests/fixtures/spec368_scenarios.py` (14 itens do §6) + `tests/test_spec368_scenarios.py`.

### Números (1800 conflitos, sementes 0–19, cartas `on`)

Cartas/rodada 1,92 (meta ≥ 2: **não**, −0,08) · rodadas com ≥ 3 escolhas 87,7 % (meta ≥ 60 %: **sim**) · Cartas com uso > 60 %: 14 (meta 0: **não**; uso geral 38,4 %) · p95 do conflito 12 (meta ≤ 10: **não**, Médico de Campo 19) · R10 dano recebido `on` +10,1 % (meta "cai": **não**).

### Desvios / follow-ups

- Metas 327/329/331 **não atingidas**, registradas sem mudar o critério (D-368-1). Follow-ups: bot que lê a faixa do Presságio; Médico de Campo (p95 19, 4,4 % de timeouts); Cartas de uso > 60 % são aviso desde a 358.
- Smoke real §6 é do coordenador (`docs/spec368/smoke-final.md`); `seed_save` leva o jogo real aos itens 1–7 e 12–14, os itens 8–11 seguem o roteiro abaixo.
- Revisão independente `Sol` pendente (não autoaprovada); suíte completa é do coordenador.

### Correções da revisão Sol (03/11, `handoffs/SPEC-368-sol-review.md`)

- **P1-1 (R13):** `tests/fixtures/spec368_seed.py::seed_save(item, variant=, saves_dir=)` grava o save real (legacy, MockLLM, cartas `on`,
  conflito aberto pela API e elenco/mão/Fôlego/espólio trocados na receita) e `view(game_id)` devolve o `/game/state`. Variantes:
  1 `rollback`; 3 `rachadura`; 5 `chefe`/`nova`; 6 `espolio` (Mão Sombria derrotada, `espolio_pendente` com Carta da facção, Esquecer
  disponível); 7 `medico`; 13 `leitura`/`armadura`/`renegado`/`reacao`. Uso: `bash scripts/dev/py.sh -c "from tests.fixtures.spec368_seed import seed_save; print(seed_save(3, variant='rachadura'))"`
  (grava em `./saves`; passe `saves_dir` para outro lugar) e abrir o jogo com o `game_id` devolvido. 22 testes de round-trip em
  `tests/test_spec368_seed.py`, inclusive uma rodada jogada pela API real a partir do save do item 12.
- **Roteiro executável dos itens 8–11 (sem save):**
  - **8 (336):** `bash scripts/dev/py.sh scripts/cards/draft.py --postura "Médico de Campo" --subclasse boticario --n 4 --raridades comum --onda 368`
    (chave real; custo de 1 chamada SMART) → `scripts/cards/lint.py --lote data/cards/_rascunhos/<arquivo>.json` →
    `scripts/cards/sim.py --lote … --json` → `scripts/cards/promote.py --lote …` → jogar 1 Carta (`seed_save(7, variant="medico")`
    ou jogo novo de Médico). Registrar o custo.
  - **9 (345):** API local `legacy` com `RPG_CARD_DECK=off RPG_ENEMY_INTENT=off RPG_ENEMY_DECKS=off RPG_SCENE_CARDS=off RPG_CARD_REWARDS=off`
    (`bash scripts/dev/py.sh -m uvicorn api:app --port 8000`), jogo novo, 1 conflito; conferir ausência de `pilhas` em `/game/state`.
  - **10 (346):** mesma API com `RPG_ROUTES='{"classify":[["groq","openai/gpt-oss-20b"]],"fast":[["groq","llama-3.3-70b-versatile"]],"smart":[["groq","openai/gpt-oss-120b"]]}'`
    e `GROQ_API_KEY=invalida` (router esgotado, CLASSIFY só no Groq); depois `RPG_CARD_DECK=off` e uma rodada; a morte real vem de
    `seed_save(1)` com o herói a 1 de Vitalidade (editar `player.vitalidade` no save) ou de um conflito jogado até cair.
  - **11 (347/352):** `bash scripts/dev/py.sh scripts/import_bestiary_art.py <pasta>` (PNG 512×512 em `<pasta>/criaturas/enemy_goblin.png`);
    "Agora não" sem cotação/request; duas contas no staging para o chefe `unico:{game}`; duas confirmações concorrentes com
    `curl` em paralelo usando `action_id` distintos; `image_generation` ligado só durante o item e conferido com `list` no fim.
- **P2-1 (R5):** o teste deriva as facções do bestiário (`tests/test_spec368_content.py`); as 10 facções da 349 sem baralho
  (`casa_mares_dominio_lyss`, `goblins_mineiros`, `ultimos_anoes_reino`, `clas_tecnologicos`, `tres_sindicatos_comercio`,
  `cidades_estado_sobreviventes_vaelorn_solvhen`, `cultos_despertar_dispersos`, `encapuzados_fornalha`, `mercadores_curiosidades`,
  `druidas_ciclo_cinzento`) ganharam 6 Cartas cada (tema das criaturas do bestiário; lint, orçamento e gramática limpos).
- **P2-2:** resolução do D-13 registrada na SPEC-330.
- **P3:** `move` revalida a fila (descarte não passa para depois de Pacto, aviso ao jogador); a nota "Nenhuma carta responde" não aparece
  com Descartar disponível; "Disparo de Tendão" sem promessa de escalada; `pre_acao`/`pos_acao` presos às jogadas que agem (teste);
  docstring das métricas corrigida (Cartas *declaradas*, todas as rodadas); R10 com rng próprio do Presságio (pareado por semente) e JSON
  regerado; R11 é **sintético** (replay canned), a taxa real de `replace` da rota de combate fica para o smoke §6 (telemetria do staging).
- **Números regerados (R10 pareado):** R9 idêntico (1,92 cartas/rodada; 87,7 %; 14 Cartas > 60 %; p95 12). R10: `off` 11,96 × `on` 13,17
  (+10,1 %, vitória 64,6 → 57,6 %) — mesmo total; por Postura Devoto 10,20→11,24 e Sangromante 11,74→13,19 (antes 11,26/13,18).

- **Fechamento:** Auditoria de fechamento (04/11, coordenador; auditor só leitura cruzou cada critério com evidência): revisão Sol final aprovada (`handoffs/SPEC-368-sol-review.md` quando existe), suíte completa verde nos pousos, smokes reais: `docs/spec363/achados-smoke3.md`, `docs/spec364/achados-smoke4.md`, `docs/spec364/smoke-final.md`, `docs/spec367/smoke-{local,staging}.md`, `docs/spec368/smoke-local.md`, `docs/spec387/smoke-{local,staging}.md`, `docs/spec389/smoke{,-local}.md`, `docs/spec390/smoke.md`. Métricas não atingidas do épico ficam registradas (D-368-1) e seguem para a SPEC-369. Smoke §6 em `docs/spec368/smoke-local.md` + 367 staging (item 11); parciais fechados nas 387/389. Métricas D-368-1 → SPEC-369.
