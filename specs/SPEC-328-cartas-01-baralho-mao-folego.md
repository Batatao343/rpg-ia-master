# SPEC-328 — Cartas #01: Baralho, Mão e Fôlego (o conflito vira jogo de cartas)

> **Status:** `in-progress` (aprovada pelo dono 2026-10-27; implementação pronta atrás de `RPG_CARD_DECK=off`, falta revisão independente e calibração da arena)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327 (visão: combate de cartas de Valoria)
> **Depende de:** SPEC-063, SPEC-065, SPEC-067, SPEC-209, SPEC-325 (todas `done`)
> **Desbloqueia:** SPEC-330 (gramática — `comprar`/`descartar`/`Guardar`), SPEC-333 (espólio), SPEC-334 (front)
> **EXECUTOR_MODEL:** `Terra` (Sonnet), por fase · **REVIEW_MODEL:** `Sol` (Opus) · **REVIEW_REQUIRED:** `true` (motor de conflito + save/load)
> **EVAL_AUTHORING_REQUIRED:** `true` — jornadas novas (comprar, jogar 2+ cartas, encerrar rodada, reação com Fôlego guardado) em `web/e2e/critical-journeys.yaml`; autoria em tarefa separada.

Rótulos: **[F]** fato no source (HEAD `a8361681`) · **[D]** decisão do dono (pendente = **[D?]**) · **[R]** recomendação · **[H]** hipótese.

---

## 1. Contexto & Objetivo

[F] Hoje o jogador tem um Acervo (`known_cards`) e 4–7 **Cartas preparadas** (`prepared_cards`, `services/cards.py:307-319`). Em combate, toda rodada mostra **as mesmas** preparadas; o limite é a `frequencia` (`livre|turno|cena|descanso_*`, contador em `card_usage`) e o custo é Entropia (`custo_entropia`, 0–7). O turno tem **uma** ação principal (`TurnDeclaration.acao`, `services/conflict_turn.py:34-49`) + pré/pós de movimento.

[F] Isso é uma **lista de magias preparadas** (modelo D&D), não um jogo de cartas: não há compra, mão, descarte, nem orçamento por rodada que force escolha entre cartas. A rodada ideal tende a ser sempre a mesma ("jogo a carta mais forte que ainda está pronta"). A pesquisa (SPEC-327 §3) aponta que a tensão de um combate de cartas nasce de três coisas que faltam aqui: **variância controlada da mão**, **orçamento por turno que não cobre tudo** e **descarte/reciclagem** que dá valor a cartas baratas.

Objetivo: introduzir **Baralho de Conflito → Mão → Descarte** e um recurso por rodada, **Fôlego**, mantendo o esqueleto (2d10+Virtude, Vitalidade/Ferimentos, Reações, Entropia/Carga, zonas, IA inimiga determinística). A Entropia deixa de ser o único custo e vira o **custo de tentação**: dá para pagar o Fôlego que falta com Entropia — o Abismo empresta, cobra depois.

## 2. Requisitos

**Baralho**
- **R1** — `player["deck"]: list[str]` (ids, cópias permitidas) é o **Baralho de Conflito**. Tamanho 12–24 [D?]. Fora de combate é editável quando `can_reorganize(state)` (mesma regra de hoje).
- **R2** — Toda Postura (classe) recebe **3 cartas básicas** novas, em `data/cards/basicas.json`: um golpe (Fôlego 1, dano baixo), uma guarda (Fôlego 1, proteção) e uma carta-assinatura barata da classe (ex.: Arcanista "Vazão" — esfria a caldeira; Sangromante "Corte Raso" — paga 2 Vitalidade, gera Entropia). Baralho inicial = 4 golpes + 4 guardas + 1 assinatura + as cartas ativas/reação do Acervo inicial.
- **R3** — Migração de save (idempotente): sem `deck`, monta `deck = básicas + prepared_cards (ativas/reações/utilitárias)`; passivas e Cartas de Virtude **não** entram no baralho (seguem como talentos permanentes, como hoje).
- **R4** — `prepared_cards` continua existindo e passa a ser derivado (`set(deck)`), para não quebrar `combat_targeting`, `api._cards_block` e a IA de reação até o front migrar.

**Rodada**
- **R5** — Início do conflito: embaralha com o `rng` da cena (semente persistida → replay determinístico), compra 5. Início de cada rodada do jogador: descarta a mão não guardada, compra até 5 (`MAO_BASE`), recebe **Fôlego 3** (`FOLEGO_BASE`).
- **R6** — Toda carta jogável ganha `custo_folego: 0..3`. Default derivado (sem reescrever o acervo): `0` se `frequencia == "livre"` e sem dano; `1` comum; `2` se `tier ≥ 3` ou `dano_base ≥ 8`; `3` se `apex` ou `frequencia == "descanso_longo"`. Valor explícito no JSON sobrescreve.
- **R7** — Na rodada, o jogador joga **quantas cartas o Fôlego permitir**, em ordem; cada uma resolve em sequência no motor atual (mesmo `_resolve_actor_turn`, uma jogada por vez). Movimento (pré/pós) continua grátis 1×/rodada como hoje.
- **R8** — **Pacto do Abismo:** se faltar Fôlego, pode pagar **cada Fôlego faltante com 2 Entropia** (máx. 2 Fôlego emprestados/rodada) [D?]. Passa por `_entropy_event` e pelos gatilhos de classe já existentes, logo pode disparar Carga/Abismo — tentação com preço real.
- **R9** — Monte de compra vazio → embaralha o descarte e gera **1 Fardo** (carta "Estilhaço de Cinza": injogável, Fôlego —, some ao fim da cena) no novo monte. Pune ciclos infinitos sem proibi-los.
- **R10** — `custo_entropia` existente continua sendo pago **além** do Fôlego (cartas fortes da classe seguem perigosas).

**Frequência → regras de pilha**
- **R11** — `frequencia` vira regra de pilha, sem apagar o campo: `livre`/`turno` → vai ao descarte; `cena` → **Exaurir** (sai até o fim do conflito); `descanso_curto`/`descanso_longo` → Exaurir + a carta só volta ao baralho após o descanso correspondente (`card_usage` reaproveitado).

**Reações**
- **R12** — Carta `tipo == "reacao"` na mão pode ser jogada na janela de reação (`_open_reaction_window`) pagando o Fôlego **que sobrou** da rodada. Guardar Fôlego para reagir é uma escolha real. Sem carta de reação na mão → só as reações básicas de hoje.

**Contrato e narração**
- **R13** — `TurnDeclaration` ganha `jogadas: list[TurnStep]` (ordem importa); `acao` vira atalho de `jogadas[0]` para compatibilidade. A API aceita a lista inteira **em um request** ("Encerrar turno").
- **R14** — **Uma** narração por rodada (o narrador recebe todas as jogadas resolvidas). Nenhuma chamada LLM nova por carta. Latência por rodada ≤ hoje (medir com o roteiro da SPEC-316).
- **R15** — Texto livre continua valendo: o parser CLASSIFY mapeia a frase para uma lista de `card_id` **da mão**, validada; carta fora da mão/sem Fôlego → rejeição explicada, sem gastar nada.
- **R16** — Estado persistido em `combat["pilhas"] = {compra, mao, descarte, exaurida, guardadas, folego, folego_emprestado, seed}`; round-trip save/load testado; combate antigo sem `pilhas` continua no modo atual até terminar.
- **R17** — Flag `RPG_CARD_DECK=off|shadow|on` (padrão `off`), no estilo de `combat_flags`. `shadow` roda as pilhas e registra no trace (SPEC-251) sem mudar o resultado.

### Fora de escopo
Intenção visível do inimigo (SPEC-329), keywords/combos (SPEC-330), espólio/edição de baralho por recompensa (SPEC-333), UI nova (SPEC-334), novas cartas além das básicas (SPEC-335).

## 3. Design técnico

- **Novo** `services/card_piles.py` — puro, sem LLM: `start_piles(player, seed) -> dict`, `draw(piles, n, rng)`, `begin_round(piles, rng)`, `can_pay(piles, player, card) -> PayPlan`, `pay(...)`, `discard_hand(piles)`, `exhaust(piles, card_id)`, `reshuffle(piles, rng)`, `migrate_deck(player)`. `PayPlan = {folego: int, emprestado: int, entropia_extra: int, ok: bool, motivo: str}`.
- **Novo** `data/cards/basicas.json` (15 cartas: 3 × 5 Posturas) — nomes e descrições na voz de Valoria; validadas pelo `content_validator` existente.
- **Alterado** `services/cards.py` — `custo_folego(card)` (regra R6), `set_deck(state, deck)` com validação (subconjunto do Acervo + básicas, tamanho, cópias ≤ 2 para comum, ≤ 1 rara+).
- **Alterado** `services/conflict_turn.py` — `jogadas` (R13).
- **Alterado** `services/conflict_orchestrator.py::run_round` — com flag `on`, itera `jogadas` do jogador com `card_piles.pay` antes de cada `_resolve_actor_turn`; janela de reação consulta a mão (R12).
- **Alterado** `api.py` — `POST /game/action` aceita `jogadas`; resposta inclui `combat.pilhas` público (mão completa; contagem de compra/descarte/exaurida — nunca a ordem do monte).
- **Alterado** `agents/combat.py` — catálogo do prompt passa a ser a **mão**, não as preparadas.

## 4. Plano passo a passo (TDD)

1. **Pilhas puras** — `tests/test_card_piles.py`: compra determinística por seed; descarte no fim da rodada; reshuffle gera 1 Fardo; Exaurir; `custo_folego` default por regra; Pacto 2:1 com teto 2.
2. **Migração** — `tests/test_deck_migration.py`: save antigo ganha deck idempotente; passivas fora; `prepared_cards` derivado.
3. **Rodada com várias jogadas** (`shadow`) — `tests/test_round_multi_play.py`: 2 cartas em ordem resolvem em sequência; Fôlego insuficiente rejeita sem efeito colateral; reação paga com Fôlego restante.
4. **API + parser** — `tests/test_api_jogadas.py`: lista inteira num request; carta fora da mão rejeitada com motivo.
5. **Save/load** — round-trip no meio do conflito.
6. **Arena** — rodar a arena da SPEC-285/090 `off` × `on`: duração média de conflito e taxa de vitória por classe dentro de ±15 % do `off` (calibrar `FOLEGO_BASE`/`MAO_BASE`, não as cartas).

## 5. Critérios de aceite
- [x] R1–R17 com teste nomeado (`tests/test_card_piles.py`, `test_deck_migration.py`, `test_round_multi_play.py`, `test_api_jogadas.py`)
- [ ] Arena `on` sem classe com vitória < 35 % ou > 80 % no encontro padrão — **NÃO atingido** com Fôlego 3/mão 5 (vitória ~98 % em L1 padrão; ver `docs/spec328/arena-results-2026-10-27.md`); depende de decisão do dono (Fôlego 2, ou pressão inimiga via SPEC-329). O próprio `off` já fica fora de 35–80 % nessa arena.
- [x] Narração: 1 chamada LLM por rodada (`test_uma_narracao_por_rodada_com_varias_jogadas`)
- [x] Testes do escopo verdes (suíte completa é do coordenador); saves antigos carregam (combate sem `pilhas` segue no modo atual); guard de FallbackLLM no parser (`test_parser_guard_do_fallback_llm`)
- [ ] Flag `on` no staging só depois de SPEC-334 (UI) pronta

## 5b. Desvios e decisões de implementação (executor, 27/10)
- Flag `RPG_CARD_DECK` vive em `services/card_piles.mode()` (padrão `off`), **não** em `combat_flags.CAPS` (os testes da SPEC-325 fixam 8 capacidades e o default `shadow`).
- Mão da rodada seguinte é comprada ao **fim** da rodada (`begin_round` no nó de combate) para a UI já mostrá-la; `run_round` não compra.
- Jogadas que não são Carta: `attack`/`item`/`maneuver` (exceto `mover`)/`object` custam **1 Fôlego**; `move`/`pass` são grátis. Lista inválida é recusada **inteira** antes de gastar (`deck_refused`, rodada não consumida).
- Cartas básicas não têm teto de cópias (R2 pede 4 golpes + 4 guardas); `origem: "cartas-328"` é validada por `validate_cards`.
- **Pacto do Abismo (revisão Sol R-1, coordenador):** Entropia é combustível. Para TODAS as Posturas, cada Fôlego emprestado **gasta 2 Entropia** (precisa ter; sem Entropia → lista recusada sem efeito), teto 2 Fôlego/rodada, e **+1 Carga do Abismo** 1×/rodada se houve empréstimo (o Abismo dispara pelas regras de fim de rodada). Sem `on_channel` nem teto de gatilho de classe; registra `pacto_abismo`. Reembolso (Carta não resolveu) desfaz só o delta do Pacto (Fôlego, Entropia, Carga), preservando ganhos legítimos. Recusa de ação (`action_refused`) preserva `pressagios`/`pressagios_publicos` da SPEC-329 (sem reroll).
- R-4 (follow-up): pendente da re-revisão Sol (ver handoff).
- P1-1: `extra_card_ids` só no schema CLASSIFY com baralho `on`. P1-3: `start_piles` não muda a ficha (shadow limpo); `on` guarda `prepared_cards_pre_deck` e `off` restaura; `use_card` só aceita o `deck` com a flag `on`.
- P2-1 nome mais longo vence no parser. P2-2: a Guarda dura a rodada (restaurada entre jogadas); gatilhos de classe "por turno" já usam o contador zerado 1×/rodada em `run_round`. P2-5: `last_player_action.plays` (aditivo, só com >1 jogada).
- Calibração: derivação R6 com `dano_base ≥ 5` não mudou a arena (ver `docs/spec328/arena-results-2026-10-27.md`); mantida a de 8.
- Reação do jogador continua exigindo `reaction_card_id` da UI; com baralho `on` a carta precisa estar na mão e há Fôlego sobrando (sem Pacto). Auto-reação por mão fica para a SPEC-334.
- Sem endpoint HTTP de edição de baralho (só `cards.set_deck`); a UI/endpoint entra com a SPEC-334.

## 6. Smoke com LLM real
1. Conflito novo: mão de 5 aparece, jogar 2 cartas por texto livre ("corto e me protejo").
2. Pacto do Abismo: jogar sem Fôlego, conferir Entropia +2 e narração mencionando o custo.
3. Recarregar no meio do conflito: mão e pilhas idênticas.

## 7. Riscos & compatibilidade
- Maior mudança de sensação do jogo desde o Conflito v2 → por isso `shadow` + arena antes de `on`.
- Balanceamento: a curva de cartas atual foi feita para "1 ação/rodada"; com Fôlego 3, cartas baratas podem empilhar dano. Mitigação: arena (Etapa 6) e custo derivado conservador.
- Latência: requests por rodada não aumentam (R13/R14).
- Inimigos não mudam nesta spec (seguem `enemy_declaration`).
