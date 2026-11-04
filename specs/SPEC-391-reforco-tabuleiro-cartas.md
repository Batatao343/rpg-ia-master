# SPEC-391 — Reforço de combate no tabuleiro de cartas ("Chamado do Bando" do líder de matilha)

> **Status:** `approved` (04/11, dono: "391 concordo com tudo" — D-391-1..8 = recomendações da spec)
> **Criada:** 2026-11-04 · **Atualizada:** 2026-11-04 (Etapas 0 e 1 feitas: §4 "Execução")
> **Depende de:** SPEC-381 pousada (`api.py` em routers: o bloco `reinforcement_warning` muda de arquivo);
> SPEC-371/372 sem conflito em `agents/combat.py` (371 `done`; 372 `draft`: conferir W1 antes da Etapa 3);
> SPEC-369 sem conflito em `data/cards/inimigos/lider_matilha.json` e `_decks.json` (a 369 pode mexer em
> cartas de inimigo pelo R20 dela: esta spec **não** edita os arquivos de família, ver R6).
> SPEC-325 R16 (código desligado e preservado, `done` como "encerrado sem ligar") e SPEC-384 D3 = **não**.
> **Desbloqueia:** reforço em outras famílias (fora de escopo); fecha o "reforço no tabuleiro de cartas vira
> spec própria" do cabeçalho da SPEC-384.
> **Risco:** `alto` (combate, estado persistido no meio do conflito, payload público de combate)
> **Evidência:** testes novos em `tests/test_reinforcement_cards.py` que falham antes (sem o fluxo de Carta, o
> líder a ≤ 50 % não joga "Chamado do Bando" e não há presságio de chamado); oráculo de equivalência da arena
> nova contra `scripts/cards/sim.py::_fight` com a flag `off` (Etapa 1); gate de letalidade §8; smoke §6.
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true` · **EVAL_AUTHORING_REQUIRED:** `true`
> (a arena da Etapa 1 é avaliador novo: quem a escreve não ajusta as alavancas da Etapa 5)

Rótulos: **[F]** fato conferido no source em 04/11 (arquivo:linha; `agents/combat.py` e `api.py` estão sendo
editados por outras sessões, então as linhas deles são aproximadas, ≈) · **[H]** hipótese a confirmar pelo
executor na Etapa 0 · **[D]** decisão do dono pendente (§9) · **[R]** recomendação desta spec.

---

## 1. Contexto & Objetivo

A SPEC-325 R16 implementou reforços de combate: todo `lider_matilha` registra 1 gatilho antes de congelar a
cena; na 1ª vez que fica com Vitalidade ≤ 50 % o log avisa; no fim da rodada seguinte, se o líder ainda age,
chega 1 Lacaio `distante`, 1 vez por conflito, limitado ao orçamento do encontro; matar, incapacitar, render
ou fazer o líder fugir antes cancela [F `services/reinforcements.py:1-10`, `:135-154`, `:164-224`]. O gate
de letalidade da Fase D não passou: a célula `lider_matilha` subiu a morte em +26 a +37 pp contra o teto de
+3 pp, e atrasar a chegada (2 ou 3 rodadas) quase não mudou nada, porque corpos extras são superlineares
[F `specs/SPEC-325-ligar-mecanicas-dormentes.md:640-648`]. Em 26/10 o dono desistiu da Fase D
[F `SPEC-325…md:829`] e o default virou `off` [F `services/combat_flags.py:45-47`, `config/flags.yaml:182-187`].

Desde então o combate de cartas virou o padrão no staging [F `scripts/staging/staging_flags.json:26-29`:
`RPG_CARD_DECK`, `RPG_ENEMY_INTENT`, `RPG_ENEMY_DECKS` = `on`]. Em 04/11 o dono decidiu que gosta da mecânica:
a SPEC-384 D3 ficou **não** ("código fica desligado e preservado; reforço no tabuleiro de cartas vira spec
própria") [F `specs/SPEC-384-poda-decisoes-dono-flags-perfis.md:13`].

O R16 não conversa com o tabuleiro. O aviso é só uma linha de log mais o chip "Passos se aproximam" da
`CombateTab` [F `web/src/combat/conflictChips.ts:11, 31-32`; `web/src/workspace/tabs/CombateTab.tsx:357-358`].
O líder não gasta nada para chamar, e o gatilho fica escondido (50 % de Vitalidade). O tabuleiro já tem as
peças para um chamado legível: Cartas de inimigo por família [F `services/enemy_decks.py:1-19`], assinatura
telegrafada uma rodada antes, com promessa cumprida ou frustrada [F `services/enemy_decks.py:387-510`], e o
presságio público com `prenuncio` no chip do inimigo [F `web/src/types.ts:544-547`,
`web/src/components/combat/DeckCombat.tsx:95-98`]. A família `lider_matilha` já tem padrão com
`reforco_proprio` e um "Uivo de Reunião" cujo texto diz "chama os seus", mas o efeito é só `buff_acerto` +1
[F `data/cards/inimigos/_decks.json:159-178`; `data/cards/inimigos/lider_matilha.json:5-21`]. O perfil tático
da família já descreve "chama reforço quando pode" [F `scripts/migrate_bestiary_v4.py:501`], e o `sempre`
dele é `support` [F `services/tactical_profile.py:231-235`].

**Objetivo.** Reviver o reforço **dentro do combate de cartas**. O chamado vira uma Carta do líder
("Chamado do Bando"), telegrafada no presságio uma rodada antes e jogada como ação do líder, com a janela de
contra-jogo do R16 (focar o líder cancela). Tudo decidido em Python, 0 LLM por rodada (memória do dono
"combate-cartas-sem-ia"). A spec só fecha com gate de letalidade numérico na arena de cartas. Com a flag
`off`, tudo fica byte-idêntico.

## 2. Requisitos

Notação: rodada **N** = fim da rodada em que o líder cruza ≤ 50 % de Vitalidade; **N+1** = rodada em que joga o
Chamado; **N+2** = rodada da chegada [D-391-2 define a chegada; o texto abaixo usa a recomendação].

### Gatilho e telegrafo (Python decide)

- **R1 — Elegibilidade.** O fluxo de Carta só vale com a flag do reforço `on` [D-391-3], `RPG_CARD_DECK=on`
  **e** `RPG_ENEMY_DECKS=on`. Fora disso: com a flag `on` e o baralho `off`, roda o R16 legado sem mudança
  (`tests/test_spec325_reinforcements.py` segue verde); com a flag `off`, nada muda (R14). Assert: matriz
  3 flags × modo de baralho → caminho esperado.
- **R2 — Gatilho igual ao R16.** O gatilho continua sendo planejado em `_prepare_scene` antes de `cs.freeze`
  [F `agents/combat.py:≈1099-1100`, `:≈386-408`], só para `lider_matilha` [F `services/reinforcements.py:33-35`],
  1 por conflito, com orçamento `encounter_budget(nível, danger, aliados)` [F `agents/combat.py:≈397-402`]. A
  condição também é a mesma: ao fim da rodada N, o líder `acts()` com Vitalidade ≤ 50 %
  [F `services/reinforcements.py:38-50`, `:149-153`].
- **R3 — Telegrafo na rodada N (substitui o "aviso" do R16).** Ao fim de N, o motor:
  (a) registra o chamado `combat_meta["reinforcement"] = {"trigger_id", "leader_id", "stage": "telegraphed",
  "telegraphed_round": N, "call_round": N+1, ...}`;
  (b) põe a Carta de chamado em `leader["cartas"]`, se ainda não estiver lá (idempotente; mesmo padrão do
  `baralho_extra` de fase, [F `services/enemy_decks.py:575-581`]);
  (c) grava a promessa na cena, `scene["prenuncios"][leader_id] = {"carta": <id do chamado>, "rnd": N+1,
  "fase_idx": …, "tipo": "chamado"}`, como a assinatura faz [F `services/enemy_decks.py:404-420`];
  (d) faz o presságio público da rodada N+1 do líder sair com `prenuncio` = telegrafo do chamado
  (ex.: "{nome} enche o peito para chamar o bando.").
  Assert: depois de N, `public_round` do líder tem `prenuncio` com o nome dele, e **não** há
  `reinforcement_warning` nem inimigo `_r1`.
- **R4 — Precedência sobre a assinatura.** Na rodada N+1 o líder tem no máximo 1 promessa. O chamado substitui
  a assinatura que cairia na mesma rodada. A substituída sai sem virar `pressagios_frustrados` (ela nunca foi
  pública: o presságio da rodada N+1 é calculado depois do avanço do reforço [F `agents/combat.py:≈2793` antes
  de `:≈2993`]). Assert: com assinatura e chamado na mesma rodada, a linha pública mostra só o chamado, e
  `out["pressagios_frustrados"]` não cita o líder.

### Jogada e contra-jogo

- **R5 — O Chamado é a ação do líder em N+1.** Na declaração do inimigo, com chamado pendente para a rodada,
  o líder joga a Carta de chamado em vez do plano normal. Isso vale mesmo se o gatilho do perfil for
  `alvo_vulneravel` (hoje o plano de baralho só vale com o `sempre` [F `services/conflict_orchestrator.py:666-677`]).
  Não vale se `action_key` for `flee`/`surrender` ou se houver `_forced_attack`
  [F `services/conflict_orchestrator.py:663-665`]. A Carta **ocupa o turno**: nada de ataque extra na rodada.
  Assert: líder com chamado, alvo vulnerável e Fôlego qualquer → declaração com a Carta de chamado e 0 dano
  causado pelo líder nessa jogada (fora o efeito próprio da Carta, R6).
- **R6 — A Carta.** Uma Carta de inimigo nova, `inf_chamado_do_bando` [D-391-6 nome/voz], em arquivo próprio
  `data/cards/inimigos/chamados.json`, **fora** dos pools de família. Para o arquivo não ser tratado como órfão,
  `chamados` entra em `_EXTRA_FILES` [F `services/enemy_decks.py:77`, `:113-128`]. A Carta só existe no baralho
  do líder depois do telegrafo (R3b), então `build_enemy_deck` não muda [F `services/enemy_decks.py:229-265`].
  O efeito mecânico da Carta usa um `kind` **já existente** do catálogo fechado [F `services/cards.py:27-67`]:
  [R] `protecao` pequena em si mesmo ("se fecha enquanto chama"). O chamado em si **não** é efeito de Carta:
  quem o decide é `services/reinforcements.py` (R7), e por isso `services/card_effects.py` (> 1.000 linhas)
  não cresce. A Carta passa no lint de Cartas e no `validate_content.py`, com `oculta: true` como as irmãs.
  Assert: `edk._pools()` não contém a Carta; `cards.get_card("inf_chamado_do_bando")` existe;
  `card_lint` sem erro.
- **R7 — Chamado feito.** Quando a declaração **efetiva** do líder em N+1 joga a Carta (o mesmo ponto em que
  `note_declaration` cumpre a promessa [F `services/enemy_decks.py:479-492`]), o estado vira
  `stage: "called"`, `called_round: N+1`. O log ganha uma linha legível ("{nome} chama o bando: passos ao
  longe.") e a telemetria emite `combat.reinforcements_warned` com `via="carta"` (R12). A partir daqui o
  payload tem o aviso (R10). Assert: depois de N+1, `stage == "called"` e o evento foi emitido 1×.
- **R8 — Chamado frustrado (contra-jogo 1).** Se o líder não joga a Carta em N+1, a promessa fecha como
  frustrada com motivo legível, pelo caminho que já existe [F `services/enemy_decks.py:430-476`, `:495-510`].
  Isso inclui: morto, fugido, rendido, capturado, incapacitado, atordoado na 1ª ação, `flee` ou ferido demais
  pelo critério de R5. O reforço passa a `cancelled` e emite `combat.reinforcements_cancelled` com
  `cause="frustrado"`. Não há segunda tentativa no conflito (1×/conflito, R16). Assert: um teste por causa
  (morto, fuga, rendição, atordoado) → `cancelled`, 0 `_r1`, linha de frustração no log.
- **R9 — Chegada ou cancelamento (contra-jogo 2).** Ao fim de N+2 [D-391-2]: se o líder ainda `acts()`, chega
  1 reforço por `rf.spawn` [F `services/reinforcements.py:111-132`] (mesmo template, Lacaio da facção ou
  "Capanga do bando" [F `:82-108`], id `<base>_r<N>`, posição `distante` [F `:157-161`], `joined` no manifesto
  [F `agents/combat.py:≈431-438`]). Se o líder parou de agir entre N+1 e N+2, cancela
  (`cause="lider_caido"`). Se o orçamento não comporta, também cancela (`cause="budget"`)
  [F `services/reinforcements.py:120-123`, `:206-211`]. Assert: chegada no fim de N+2 e nunca antes; matar o
  líder em N+2 cancela; orçamento curto cancela.

### Tabuleiro, payload e UI

- **R10 — Payload.** Com o fluxo de Carta `on`, o bloco de combate expõe `reinforcement` como objeto público
  mínimo: `{"stage": "telegraphed"|"called", "leader_id", "chega_na_rodada": int|null}`. Só aparece entre o
  telegrafo e a chegada ou o cancelamento. O `reinforcement_warning: true` legado continua existindo, mas só
  em `stage == "called"` (compatível com o invariante `conflict.golden_reinforcement`
  [F `playtest/invariants.py:2941-2945`]), e passa a ler `called_round` em vez de `warned_round`, ou o estado
  grava os dois [H: escolher na Etapa 0 o que não quebra o invariante]. Nada sobre o template do reforço
  (nome, ficha, id) aparece antes da chegada (regra de ouro do R16 [F `api.py:≈3259-3266`]). Assert:
  telegrafado → sem `reinforcement_warning`; chamado → com; chegado/cancelado → sem os dois.
- **R11 — UI do tabuleiro (web).** No `DeckCombat` (o tabuleiro, não só a `CombateTab`):
  (a) o chip do líder mostra o `prenuncio` do chamado em N (já existe para assinatura
  [F `DeckCombat.tsx:95-98`]);
  (b) entre o chamado e a chegada, aparece uma nota no tabuleiro ("Reforço a caminho: chega no fim da
  próxima rodada. Derrube {líder} para impedir."), com `role="note"`;
  (c) o recém-chegado aparece como inimigo normal (chip, alvo, presságio da rodada seguinte), com marca
  "acabou de chegar" na rodada da chegada e posição `distante` na Arena/zonas;
  (d) cancelado: a nota some e o registro da rodada mostra a frustração.
  Retrato do recém-chegado: o mesmo caminho dos outros inimigos (bestiário/pool). **Nunca** geração de imagem
  nem oferta de retrato no meio do conflito. Assert: teste de unidade web (`web/tests/…test.mjs`) para a nota
  e para a marca; e2e só se o dono pedir (D-391-8).

### Baralho do recém-chegado, determinismo, persistência e telemetria

- **R12 — Baralho do recém-chegado.** Inimigo não tem pilhas: `card_piles` é só do herói
  [F `services/card_piles.py:179-270`, todas as funções recebem `player`/`piles` do herói]. O "baralho" do
  reforço é `cartas` montado por `apply_deck` na normalização da ficha
  [F `services/conflict_orchestrator.py:143-152`]. Hoje o `spawn` não passa `deck_seed`, e a montagem usa a
  semente 0 [F `services/reinforcements.py:128-132`, `services/enemy_decks.py:287-289`]. **R12** fixa:
  o reforço herda o `deck_seed` do líder, monta o baralho pela família dele, entra no presságio da rodada
  seguinte (forecast depois do avanço [F `agents/combat.py:≈2993`]) e começa a contagem de padrão/assinatura
  na rodada da chegada. Assert: mesmo conflito, duas execuções → mesmo `cartas` no `_r1`; o presságio da rodada
  N+3 tem linha do `_r1`.
- **R13 — Determinismo.** Nenhum `random` novo: gatilho, telegrafo, jogada, chegada e template são funções
  puras do estado (hoje `check` já é pura [F `tests/test_spec325_reinforcements.py:339`]). Mesmo save e mesmas
  ações → mesmo desfecho, byte a byte, no `combat_meta`. 0 chamada de LLM nas rodadas do chamado (contador de
  LLM do teste = 0, como na SPEC-346 R2 [F `agents/combat.py:≈2796-2800`]).
- **R14 — Flag `off` byte-idêntica.** Com a flag em `off` (default), nenhum gatilho, Carta, promessa, payload
  ou evento novo. `sim.py`, a arena da SPEC-285 e a arena por família da SPEC-332 ficam idênticas nas células
  atuais. O fluxo nasce só no nó de combate (`_prepare_scene`/fim de rodada) e na arena nova da Etapa 1; o
  `run_round` puro, sem gatilho na cena, nunca chama. Assert: oráculo da Etapa 1 e
  `git diff --exit-code` dos JSONs de arena das specs 285/332/355/368 regerados no pouso.
- **R15 — Save/load em cada estágio.** Salvar e carregar em `telegraphed` e em `called` continua o fluxo
  sem duplicar a Carta, a promessa nem o reforço. Saves antigos com `combat_meta["reinforcement"]` do R16
  (`warned_round`, sem `stage`) continuam pelo caminho legado [F estado R16 `services/reinforcements.py:193-198`].
  Saves sem o campo também carregam. Assert: três testes de round-trip (`persistence` save → load → próxima
  rodada).
- **R16 — Telemetria.** Reusa os 4 eventos [F `observability/events.py:153-156`] e acrescenta o campo `via`
  (`"carta"`|`"legado"`) a `warned`/`fired`/`cancelled`, mais o evento novo `combat.reinforcements_telegraphed`.
  Os campos ficam registrados em `observability/events.py` e as linhas, em `docs/operacao/EVENTOS_DE_LOG.md`.
  Assert: teste de catálogo de eventos verde; 1 evento por transição.
- **R17 — Playtest.** O cenário `combate_reforco` e o bot `decide_aguarda_reforco`
  [F `playtest/capability_bots.py:137, 201, 219`; `playtest/scenarios.py:44, 413`] rodam também com o baralho
  `on` e terminam com chamado e chegada (ou cancelamento) sem violação. Assert: `playtest run` do cenário com
  0 violação (Etapa 4).

### Gate e flag

- **R18 — Gate de letalidade na arena de cartas (§8).** A flag só pode ir a `on` no staging depois de o gate
  passar com o critério que o dono fixar [D-391-4]. Gate não passou e as alavancas pré-declaradas também não
  resolveram [D-391-5]: a flag fica `off`, o código fica, e a medida vai para a spec.
- **R19 — Registro da flag.** [D-391-3, R: reusar] `RPG_COMBAT_REINFORCEMENTS` (`off|shadow|on`). Em
  `config/flags.yaml`: `spec: SPEC-391`, `note` nova, `expires` revisto, default `off`. O gate de flags da
  SPEC-340 fica verde. `shadow` no fluxo de Carta só registra `reinforcements_shadow` com
  `phase="would_telegraph"`, sem mudar estado [F padrão `services/reinforcements.py:178-181`].
- **R20 — `test_enemy_decks.py:311-316`.** Hoje esse teste garante que nenhuma Carta de **família** fale em
  reforço [F `tests/test_enemy_decks.py:311-316`, `:258-262` lê só `edk._pools()["familias"]`]. A Carta de
  chamado mora fora dos pools (R6), então o teste continua verdadeiro sem mudança. [R] Manter a asserção,
  trocar só o comentário ("o chamado mora em `chamados.json`, SPEC-391") e somar um teste positivo: a única
  Carta de inimigo que chama reforço é a de `chamados.json`, e ela não está em pool. [D-391-7]

### Fora de escopo

- Reforço para outras famílias além de `lider_matilha` e mais de 1 reforço por conflito.
- Mudar o template do reforço (Lacaio da facção / "Capanga do bando") fora das alavancas do §8.
- Apagar ou alterar o R16 legado (SPEC-384 D3 = não). Ele continua o caminho com baralho `off`.
- O encontro de mundo `reason="reinforcements"`, `reforco_proprio` das fichas/padrão e as primitivas da
  SPEC-272 (`add_reinforcement_trigger`, `fire_reinforcement`, `spawn_reinforcement`): **outra mecânica, não
  tocar** [F `SPEC-384…md:202-216`]. Só são **usadas** como hoje.
- `kind` novo em `CARD_EFFECT_KINDS`, palavra-chave nova no glossário, mudança em `card_effects.py`.
- Editar `scripts/cards/sim.py`, `docs/spec285/arena_lethality.py`, `docs/spec332/arena_familias.py`,
  `docs/spec368/metricas_epico.py`, os testes de arena protegidos pela SPEC-369 R2 e os arquivos de família
  `data/cards/inimigos/<familia>.json` / `_decks.json`.
- Ligar a flag no staging/produção (só depois do gate e do "liga" do dono).
- Oferta/geração de retrato para o recém-chegado; LLM narrando o chamado por rodada.

## 3. Design técnico

### 3.1 Alternativas (para D-391-1)

| Opção | Como | Prós | Contras |
|---|---|---|---|
| **A [R]** Carta forçada por gatilho | O gatilho de 50 % (R16) vira telegrafo no presságio; o líder **joga** "Chamado do Bando" na rodada seguinte; a chegada vem depois | Legível no tabuleiro; custa o turno do líder (menos dano na rodada); dois pontos de contra-jogo (impedir a jogada e derrubar antes da chegada); reaproveita promessa/frustração da 355 | Mexe na precedência da declaração do inimigo (R5); toca `enemy_decks.py` e `conflict_orchestrator.py` (este > 1.000 linhas: não pode crescer) |
| B Assinatura periódica | O Chamado entra como 3ª assinatura da família (`a_cada_n`), sem gatilho de Vitalidade | Usa só dado (`_decks.json`); "costuma: …" já ensina o padrão | Dispara cedo (rodada 2+) com o líder inteiro: mais letal que o R16 que já reprovou; muda todos os líderes; conflita com a 369 em `_decks.json` |
| C R16 com UI de tabuleiro | Mantém aviso/chegada do R16, só leva a nota para o `DeckCombat` | Menor mudança (só payload/web) | O líder não paga nada; o telegrafo não passa pelo presságio; o gate de 26/10 já reprovou essa mecânica |

### 3.2 Arquivos

- **Novo `services/reinforcement_cards.py`** (≤ 250 l., funções ≤ 60 l.): a máquina de estados do fluxo de
  Carta (`telegraph`, `on_declaration`, `advance_card_flow`, `public_view`). Ela chama `reinforcements.spawn`,
  `acts` e `_arrival_position` sem duplicar nada. Fica em módulo próprio para `services/reinforcements.py`
  não virar dois modos misturados. [H: pode ser `reinforcements.py` mesmo, se ficar < 400 l.; o executor
  decide e registra.]
- **Novo `data/cards/inimigos/chamados.json`**: a Carta `inf_chamado_do_bando` (R6) e os telegrafos (R3d).
- **Novo `docs/spec391/arena_reforco_cartas.py`**: o avaliador do gate (§8, Etapa 1). Importa `sim` e a arena
  285 como `sim.py:37-45` faz; **não** os edita.
- **Novo `tests/test_reinforcement_cards.py`**: testes de R1–R16 e R20.
- **`services/enemy_decks.py`** (< 1.000 l.): `_EXTRA_FILES` ganha `chamados`. `plan(actor, rnd, scene=None)`
  devolve `assinatura = <Carta do chamado>` quando `scene["prenuncios"][id]` tem `tipo == "chamado"` e
  `rnd` da rodada (precedência R4). `note_declaration` avisa o módulo novo quando a promessa cumprida é de
  chamado. `_frustrate_promise` aceita o `tipo` `chamado` (motivo legível próprio).
- **`services/conflict_orchestrator.py`** (> 1.000 l., **não cresce**): a guarda de `enemy_declaration`
  [F `:666-677`] passa `scene` a `plan` e deixa o chamado valer com gatilho ≠ `sempre` (R5). Crescimento
  líquido 0: compensar extraindo um helper para `enemy_decks.py`.
- **`agents/combat.py`** (> 1.000 l., **não cresce**, travado por 381/371/372): `_advance_reinforcements`
  [F `:≈411-438`] escolhe entre o fluxo legado e o de Carta com 1 chamada (`reinforcement_cards.advance_card_flow`
  quando R1 vale). O espelho de vitais, o saber e o `joined` seguem iguais. `_plan_reinforcements` não muda.
- **Router de combate pós-381** (hoje `api.py:≈3259-3266`): o bloco `reinforcement` público (R10).
- **`web/src/types.ts`**, **`web/src/components/combat/DeckCombat.tsx`**, **`web/src/combat/conflictChips.ts`**:
  R11. Os testes ficam em `web/tests/conflict-chips.test.mjs` ou em um arquivo novo.
- **`observability/events.py`**, **`docs/operacao/EVENTOS_DE_LOG.md`**: R16.
- **`config/flags.yaml`**, **`services/combat_flags.py`** (só comentário/default se D-391-3 mudar): R19.
- **`tests/test_enemy_decks.py:311-316`**: só o comentário (R20, se D-391-7 = manter).
- **`playtest/capability_bots.py`/`scenarios.py`**: só se o cenário precisar do baralho `on` (R17).

### 3.3 Estado (`combat_meta["reinforcement"]`, persistido no save)

```python
class ReinforcementCallState(TypedDict, total=False):
    trigger_id: str  # "reinf_<leader_id>" (igual ao R16)
    leader_id: str
    via: Literal["carta", "legado"]  # ausente = legado (saves do R16)
    stage: Literal["telegraphed", "called"]
    telegraphed_round: int  # N
    call_round: int  # N+1
    called_round: int  # N+1, só depois da jogada efetiva
    arrival_round: int  # N+2 [D-391-2]
    warned_round: int  # espelho de called_round (compat. invariante/API legado) [H, R10]
    fired: bool
    cancelled: bool
    cause: str  # "frustrado" | "lider_caido" | "budget"
```

Promessa na cena (mesmo dicionário da SPEC-355, chave = id do líder):
`{"carta": "inf_chamado_do_bando", "rnd": N+1, "fase_idx": 0, "tipo": "chamado"}`.

### 3.4 Carta (formato; valores finais pelo lint)

```json
{
  "_meta": "SPEC-391: Cartas de chamado (fora dos pools de família; só entram no baralho pelo telegrafo).",
  "cards": [
    {
      "id": "inf_chamado_do_bando",
      "name": "Chamado do Bando",
      "origem": "cartas-391",
      "classe": "Inimigo",
      "subclasse": "lider_matilha",
      "tipo": "ativa",
      "patamar": "inicial",
      "custo_entropia": 0,
      "frequencia": "cena",
      "virtude_permitida": [],
      "efeito": {"kind": "protecao", "valor": 1, "alvo": "eu"},
      "descricao": "Chama os seus e se fecha enquanto o bando não chega.",
      "oculta": true
    }
  ],
  "telegrafos": {
    "fera": "{nome} ergue o focinho e enche o peito para chamar o bando.",
    "humanoide": "{nome} leva a mão à boca para chamar os seus."
  }
}
```

[H] O lint aceita a chave extra `telegrafos` no topo do arquivo, ou ela vai para `_decks.json` em chave nova
`"chamados"`. Este segundo caminho conflita com a 369: só usar se a 369 já tiver pousado. O critério
fera/humanoide é um campo determinístico do bestiário, a confirmar na Etapa 0 (ex.: `type`/`tags`).

### 3.5 Assinaturas

```python
# services/reinforcement_cards.py
def eligible() -> bool: ...  # R1
def telegraph(scene: dict, leader: dict, combat_meta: dict, round_: int) -> list[str]: ...  # R3
def on_declaration(
    scene: dict, actor_id: str, card_id: str | None, round_: int, combat_meta: dict
) -> None: ...  # R7 (chamado por enemy_decks.note_declaration)
def advance_card_flow(
    scene: dict,
    enemies: list[dict],
    actors_by_id: dict,
    sides: dict,
    combat_meta: dict,
    round_: int,
    *,
    mode: str,
) -> dict[str, Any]:
    ...
    # mesmo contrato de reinforcements.advance: {"logs", "spawned", "warned", "telegraphed"}


def public_view(combat_meta: dict) -> dict | None: ...  # R10
```

## 4. Plano passo a passo

Executor = Terra; a arena da Etapa 1 é escrita e congelada **antes** da Etapa 2, por agente diferente de quem
ajusta as alavancas da Etapa 5 (EVAL_AUTHORING_REQUIRED). Subagente: só os testes do escopo, `-n 2` no máximo.

### Etapa 0 — Conferência (sem código de produto)

1. Recontar as linhas de `agents/combat.py`/`conflict_orchestrator.py`/`api.py` (ou router) e reconfirmar os
   [F] com ≈. Confirmar que a 381 pousou (bloqueante para a Etapa 3) e o W1 da 372/369.
2. Listar `leader_pool()` [F `docs/spec285/arena_lethality.py:106-112`] com categoria/facção e o campo que
   separa fera/humanoide (R6/§3.4). Hoje há 11 `lider_matilha` em `data/bestiary.json` (contagem por grep),
   entre eles `enemy_soldado_legiao_ferro` (Elite, `legiao_ferro`) [F `data/bestiary.json:202-269`].
3. Fechar os [H] do R10 (`warned_round`) e do §3.4 (onde moram os telegrafos). Registrar na spec.

### Etapa 1 — Avaliador do gate (antes de qualquer código de produto)

1. **Testes** (`tests/test_reinforcement_cards.py`):
   `test_arena_reforco_off_equivale_sim_fight` assegura que, com a flag `off`, `arena_reforco_cartas.fight(...)`
   devolve o mesmo `(desfecho, rodadas)` de `sim._fight(...)` em 20 lutas fixas (5 Posturas × 2 líderes ×
   2 sementes, L3), com `RPG_ENEMY_DECKS=on`/`RPG_ENEMY_INTENT=on` nas duas pontas (oráculo de equivalência);
   `test_arena_reforco_saida_tem_campos` assegura que cada célula tem
   `death/win/timeout/fights/avg_rounds/per_class` e os contadores `telegraphed/called/fired/cancelled`.
2. **Implementação:** `docs/spec391/arena_reforco_cartas.py` = laço de `sim._fight` [F `scripts/cards/sim.py:224-268`]
   com o baralho completo (`sim.full_deck_decl`) e o líder sozinho (célula `lider_matilha`, como
   `arena_lethality.py:115-117`). Planeja o gatilho como `_prepare_scene` e, no fim de cada rodada, chama a
   **mesma** função do nó (`advance_card_flow`; antes de ela existir, um stub `off`). CLI:
   `seeds`, `--levels 3,5,8`, `--classes`, `--json`.
3. **Verificação:** só os 2 testes. **Commit separado.** Desse ponto em diante o arquivo é congelado (diff
   vazio exigido no pouso, R14).

### Etapa 2 — Núcleo determinístico (sem web, sem API)

1. **Testes** (antes): `test_eligibility_matrix` (R1); `test_telegraph_on_half_vitality_records_promise`
   (R3, a–d); `test_call_overrides_signature_same_round` (R4); `test_leader_plays_call_even_with_vulnerable_target`
   e `test_call_consumes_leader_turn` (R5); `test_call_card_outside_family_pools`, `test_call_card_lints`
   (R6); `test_call_played_sets_called_stage_and_event` (R7);
   `test_call_frustrated_{dead,fled,surrendered,stunned}` (R8);
   `test_arrival_end_of_n2_never_before`, `test_leader_down_after_call_cancels`, `test_budget_cancels` (R9);
   `test_reinforcement_inherits_deck_seed_and_forecast` (R12); `test_card_flow_pure_and_zero_llm` (R13);
   `test_off_byte_identical_combat_meta` (R14); `test_save_load_{telegraphed,called}`,
   `test_old_r16_save_continues_legacy` (R15); `test_events_registered_with_via` (R16);
   `test_family_pools_still_never_call` + o positivo do R20.
2. **Implementação:** `services/reinforcement_cards.py`, `chamados.json`, o que muda em `enemy_decks.py` e a
   guarda de `conflict_orchestrator.py` (sem crescer).
3. **Verificação:** `tests/test_reinforcement_cards.py tests/test_spec325_reinforcements.py
   tests/test_enemy_decks.py tests/test_size_budget.py` (`pt.sh`, `-n 2`).

### Etapa 3 — Nó de combate e payload (bloqueada até a SPEC-381 pousar)

1. **Testes:** `test_node_card_flow_end_to_end` (nó real, `ScriptedLLM`, líder levado a ≤ 50 %, telegrafo →
   chamado → chegada `_r1` → `joined` no manifesto → XP do `_r1` ao morrer);
   `test_payload_reinforcement_stages` (R10: os três estados); `test_payload_never_leaks_template`.
2. **Implementação:** `_advance_reinforcements` com a escolha de fluxo (crescimento 0 em `agents/combat.py`);
   bloco público no router de combate.
3. **Verificação:** os testes do escopo + `tests/test_spec325_*` + o teste do gate de flags.

### Etapa 4 — Web e playtest

1. **Testes:** unidade web para a nota do tabuleiro (R11b) e a marca "acabou de chegar" (R11c); `npm run
   build` limpo; `playtest run` do cenário `combate_reforco` com baralho `on` e 0 violação (R17).
2. **Implementação:** `types.ts`, `DeckCombat.tsx`, `conflictChips.ts`; o cenário do playtest, se precisar.

### Etapa 5 — Gate de letalidade (coordenador roda; §8)

1. Rodar o §8 com o avaliador congelado. Se reprovar, aplicar **só** as alavancas aprovadas no D-391-5, na
   ordem, uma por vez, medindo após cada uma. Registrar tudo na spec.
2. Gate passou → R19 (flag no registro) e §6. Gate não passou depois das alavancas → flag `off`, spec
   registra a medida e volta para o dono.

### Execução — Etapas 0 e 1 (04/11, autor de eval; base `main` `55b85c2c`)

**Etapa 0 — conferência.**

1. **Linhas recontadas.** `agents/combat.py` 3.957 l.: `_plan_reinforcements` `:387-409`,
   `_advance_reinforcements` `:412-440`, `_prepare_scene` `:1050` (planeja em `:1102`, `cs.freeze` em `:1103`).
   O avanço do reforço roda em `_combat_aftermath` (`:3381`, chama `:3402`), e o presságio em
   `_combat_close_round_meta` (`:2626`, `forecast_round` em `:2645`). A ordem das chamadas é `:2437` e depois
   `:2440`, então o forecast vem **depois** do avanço, e o R4/R12 valem como escritos.
   `services/conflict_orchestrator.py` 3.049 l.: `enemy_declaration` `:629`, `_forced_attack` `:663-665`,
   guarda do plano `:669-677`, `apply_deck` na ficha `:152`. `services/enemy_decks.py` 677 l.: `_EXTRA_FILES`
   `:78`, `_pools` `:108-131`, `build_enemy_deck` `:237`, `apply_deck` `:281`, `plan` `:406`, `record_promise`
   `:455`, `_frustrate_promise` `:511`, `note_declaration` `:527`. `services/reinforcements.py` 224 l.
   (`spawn` `:111`, `check` `:135-157`, `advance` `:166-224`). `observability/events.py:154-157` (4 eventos).
   **SPEC-381 pousou:** `api.py` 1.081 l., e o bloco `reinforcement_warning` mora em
   `api_presenters.py:1144-1151` (não em `routes/`). A Etapa 3 mexe no presenter. W1: 369/394/359 não tocam
   `combat.py`, `enemy_decks.py` nem `conflict_orchestrator.py` (coordenador). `tests/test_enemy_decks.py:310-316`
   segue igual (R20).
2. **Pool de líderes.** No bestiário há 11 `arquetipo: lider_matilha`, e `leader_pool()` (só Elite) devolve **7**:

   | id | categoria | `faction` | `familia_valoria` | natureza (leitura da descrição) |
   |---|---|---|---|---|
   | `enemy_bandido_capitao` | elite | — | — | humanoide |
   | `enemy_soldado_legiao_ferro` | elite | `legiao_ferro` | — | humanoide |
   | `mon_auroque_ruinas` | elite | — | — | fera |
   | `mon_capita_corda` | elite | — | — | humanoide (pirata afogada) |
   | `mon_carranca_de_proa` | elite | — | `demonio_encarnado` | humanoide (busto de madeira com braços de homem) |
   | `mon_parelha_carmesim` | elite | — | `corpo_reescrito` | fera (cães de trenó) |
   | `mon_tropel_sem_saida` | elite | — | `demonio_encarnado` | fera (bichos pisoteados) |

   Fora do pool ficam `enemy_nomade_canibal`, `mon_saltador_de_palafita` e `mon_tatuzinho_de_afogado`
   (lacaio) e `mon_hiena_sol` (padrão). Só 1 dos 7 tem facção, então os outros 6 recebem o "Capanga do bando"
   no `spawn`. Para o gate isso quer dizer que a alavanca L3 só muda o `enemy_soldado_legiao_ferro`.
3. **[H] fera/humanoide (§3.4), fechado: não há campo determinístico.** O bestiário não tem `type` de
   natureza (`type` é Elite/Standard/Minion), nem `tags`, `natureza` ou `especie`. `familia_valoria` falta em
   4 dos 7, e `humanoide_preco` não aparece em nenhum. O prefixo do id também não serve: `mon_capita_corda` é
   humanoide. **[R] para a Etapa 2:** `chamados.json` ganha um mapa explícito `natureza_por_id`
   (`{id: "fera"|"humanoide"}` para os 7 do pool), com default `fera` para id fora do mapa. É dado,
   determinístico e não toca o bestiário.
4. **[H] onde moram os telegrafos (§3.4), fechado: na chave extra `telegrafos` de `chamados.json`.**
   `card_lint.load_pool`, `cards._load_cards`, `content_validator.validate_cards` e `enemy_decks._pools` leem
   só `data["cards"]` e ignoram chaves extras no topo. A chave extra passa no lint sem tocar `_decks.json`, que
   é o arquivo onde a 369 mexe. Os telegrafos de assinatura de hoje moram em `_decks.json`
   (`familias.*.assinatura.telegrafo`) e em `tactical_profile.assinatura.telegrafo` do bestiário. Nenhum dos
   dois é usado pelo chamado.
5. **[H] R10 `warned_round`, fechado: o estado grava os dois.** Na transição para `called`, `warned_round`
   passa a ser o espelho de `called_round`. Em `telegraphed` ele **não** existe. Assim o presenter de hoje
   (`warned_round is not None and not fired and not cancelled`, `api_presenters.py:1146-1151`) e o invariante
   `conflict.golden_reinforcement` (`playtest/invariants.py:2951-2955`: aviso sem `warned_round` ou com
   `fired` é erro) seguem corretos sem mudar: telegrafado fica sem aviso, chamado fica com aviso, e chegado ou
   cancelado fica sem aviso. Consequência para a Etapa 2: o despacho legado × Carta é feito por
   `via == "carta"`, nunca pela presença de `warned_round`. O fluxo de Carta também **não** pode passar pelo
   `rf.check`, porque ele trataria o `warned_round` espelhado como aviso legado e dispararia em N+2 pelo
   `ARRIVAL_DELAY = 1`.
6. **[H] neutralidade do §8, fechado.** O JSON da arena 285 e o de `metricas_epico.py` trazem `elapsed_s`,
   então `diff` cru nunca dá vazio. A comparação usa só `.cells` (285) ou o JSON sem `elapsed_s` (368).
   Comando fixado no §8.

**Etapa 1 — avaliador** (commit `d0298e51`, congelado daqui em diante; diff vazio exigido no pouso).
`docs/spec391/arena_reforco_cartas.py` refaz o laço de `sim._fight` (importa `sim.py` e, por ele, a arena
285, sem editá-los) na célula `lider_matilha` (pool acima, `n = 1`). O baralho é `sim.full_deck`, o bot é
`sim.full_deck_decl` e a tag de semente é `"391"`. O fluxo só entra com a flag ≠ `off` **e** com
`services.reinforcement_cards.advance_card_flow` importável. Nesse caso o gatilho é planejado como no
`_plan_reinforcements` (só em `on`), e `advance_card_flow(..., mode=mode)` roda no fim de cada rodada, com
`combat_meta["round"] = rnd`. Sem o módulo, o `ImportError` vira stub `off`. Os contadores
`telegraphed/called/fired/cancelled` são lidos do `combat_meta["reinforcement"]` final de cada luta
(`telegraphed_round`, `called_round`, `fired`, `cancelled`). **A Etapa 2 precisa gravar esses nomes.** A saída
não traz tempo (o tempo vai para o stderr), então o JSON é determinístico. Testes:
`test_arena_reforco_off_equivale_sim_fight` (20 lutas, 2 líderes `enemy_soldado_legiao_ferro`/
`mon_auroque_ruinas`) e `test_arena_reforco_saida_tem_campos`, **2 passed**. Medida de sanidade com flag
`off` e 2 sementes: L3 morte 35,7 %, vitória 62,9 %; L5 morte 28,6 %, vitória 68,6 %. Com a flag `on` e sem
o módulo, o resultado sai idêntico ao `off` (`card_flow: false`).

### Execução — Etapas 2, 3 e 4 (04/11, executor; commits `61a465d2`, `83252abf` e o da Etapa 4)

- **Módulo:** `services/reinforcement_cards.py` (~260 l.). `advance` é a porta do nó (escolhe legado × Carta
  por `via == "carta"`, nunca por `warned_round`); `advance_card_flow` é a da arena. O nó só trocou o import
  `reinforcements as rf` → `reinforcement_cards as rf` em `_advance_reinforcements` (combat.py 3.957 → 3.957).
  `conflict_orchestrator.py` 3.049 → 3.046 (o guard do plano virou `enemy_decks.declaration_plan`).
- **Desvio 1 (assinatura):** `on_declaration(scene, actor_id, card_id, rnd)` sem `combat_meta`: o orquestrador
  não o conhece. Ela grava `scene["chamado_jogado"]`; `advance_card_flow` consome a marca no fim da rodada e
  põe `stage: "called"`/`called_round`/`warned_round` (R7). `telegraph` recebe também o `trigger`.
- **Desvio 2 (R10, presenter):** o bloco virou `reinforcement_cards.payload_fields(meta)` (o `api_presenters.py`
  é > 1.000 l. e não cresce); inclui o aviso legado (`warned_round`) e o objeto `reinforcement`.
- **Desvio 3 (R11c):** a marca "acabou de chegar" é uma nota `role="note"` do `DeckCombat`
  (`data-arrived`), alimentada por `chegou_na_rodada` no `EnemyView`; não é um selo dentro do chip do alvo.
  A nota legada de `CombateTab` cede quando existe `combat.reinforcement`.
- **R12:** o reforço herda `deck_seed` (parâmetro novo `deck_seed` em `rf.spawn`, só o fluxo de Carta passa) e
  guarda `chegou_na_rodada`; `plan`/`_sig_falls_on` contam o padrão a partir dela (`off` byte-idêntico: chave ausente).
- **R4:** `plan(actor, rnd, scene)` devolve o chamado; `record_promise` não sobrescreve a promessa de chamado;
  `enemy_intent.public_round` põe o telegrafo do chamado na linha da Carta. `check_promises` passa uma cena
  mínima ao `plan`, porque a promessa já saiu da cena nesse ponto.
- **Eventos:** `via` em `warned/fired/cancelled` (legado grava `"legado"`) + `combat.reinforcements_telegraphed`;
  catálogo regenerado por `scripts/gen_event_catalog.py`. `config/flags.yaml`: `spec: SPEC-391`, nota nova.
- **Arena (só observação, sem gate):** com `RPG_CARD_DECK/ENEMY_DECKS/ENEMY_INTENT=on` a arena exige os 3 `on`
  (sem `RPG_ENEMY_DECKS` o chamado nunca é jogado e tudo cancela). 2 sementes, L3: 70 lutas, 70 telegrafados,
  70 chamados, 47 chegadas, 0 cancelados; morte 51 % (OFF de sanidade da Etapa 1: 35,7 %). O gate §8 é do coordenador.
- **Playtest (R17):** `combate_reforco` com os 3 `on` e a flag: 8 turnos, 0 erro, 0 violação, `fired via=carta`.

## 5. Critérios de aceite

- [x] R1–R20 com teste verde (lista da Etapa 2/3/4; `tests/test_reinforcement_cards.py`, 32 testes; R11 por unidade web)
- [x] Oráculo da Etapa 1 verde; `docs/spec391/arena_reforco_cartas.py` sem diff desde o commit da Etapa 1 (diff vazio nas Etapas 2-4)
- [ ] Flag `off`: JSONs regerados das arenas 285/332/355/368 idênticos à `main` de partida (R14)
- [ ] `scripts/cards/sim.py`, as arenas antigas e os arquivos de família de `data/cards/inimigos/` byte-idênticos
- [x] `tests/test_size_budget.py` verde (Etapas 2-4): `agents/combat.py`, `conflict_orchestrator.py`, `card_effects.py` e
      o router de combate com crescimento líquido ≤ 0
- [ ] Gate §8 aprovado pelo critério do D-391-4 (ou flag `off` com a medida registrada)
- [ ] `config/flags.yaml` atualizado; gate de flags (SPEC-340) verde
- [ ] `uv run pytest` verde (suíte completa offline, coordenador, 1×)
- [x] Nenhum `with_structured_output` novo (não há LLM no fluxo); 0 LLM por rodada medido
- [x] Saves antigos (sem campo e com estado do R16) continuam carregando
- [ ] Smoke §6 feito e registrado
- [ ] Revisão independente `spec-reviewer` (Sol/Opus) APPROVED

## 6. Smoke test real

O fluxo não tem LLM por rodada. O smoke real valida o caminho completo com o LLM real na abertura e no
resumo do combate, a API e a UI. Rodar no local com chave (ou no staging depois do "liga" do dono), com
`RPG_CARD_DECK=on RPG_ENEMY_DECKS=on RPG_ENEMY_INTENT=on RPG_COMBAT_REINFORCEMENTS=on`.

1. Abrir combate com um `lider_matilha` cujo orçamento comporte o reforço: cenário `combate_reforco`
   (perigo 3) ou `enemy_soldado_legiao_ferro`. Conferir que a abertura narra sem erro e que não há aviso.
2. Bater no líder até ≤ 50 %. Conferir no payload: `reinforcement.stage == "telegraphed"`, chip do líder com o
   `prenuncio` do chamado, sem `reinforcement_warning`. **Salvar e recarregar** aqui.
3. Próxima rodada: o líder joga "Chamado do Bando" (registro da rodada). Payload em `called`, nota no
   tabuleiro. Fim da rodada seguinte: `_r1` aparece `distante`, com retrato do pool e presságio na rodada
   seguinte. Telemetria: `telegraphed → warned(via=carta) → fired`, 0 chamada de LLM nas rodadas.
4. Segundo combate: derrubar o líder depois do Chamado e antes da chegada. Esperado: `cancelled`
   (`lider_caido`), nenhum `_r1`, a nota some.
5. Terceiro (opcional): atordoar ou matar o líder na rodada do Chamado. Esperado: promessa frustrada com
   motivo, `cancelled` (`frustrado`).

Registrar `game_id`, rodadas e eventos em `docs/spec391/smoke-AAAAMMDD.md`.

## 7. Riscos & compatibilidade

- **Letalidade (principal).** O mesmo efeito estrutural que reprovou o R16 (+26 a +37 pp) continua aqui.
  O custo do turno do líder (R5) e a janela maior (D-391-2) ajudam, mas podem não bastar. Por isso o gate
  (§8) e as alavancas ficam pré-declarados (D-391-5), e há a saída "flag `off`".
- **Saves:** campos novos são opcionais. Estado do R16 sem `via` segue o legado (R15). A Carta adicionada a
  `leader["cartas"]` persiste com o inimigo. Carregar com a flag `off` e um chamado pendente: o estado fica
  inerte, sem chegada e sem payload [H: teste explícito na Etapa 2].
- **MockLLM/FallbackLLM:** irrelevantes nas rodadas (0 LLM). A abertura e o resumo seguem os caminhos atuais.
- **Quota/latência:** nenhuma chamada nova; custo de CPU de 1 checagem por rodada.
- **Conflito de arquivos (W1):** `agents/combat.py` e `api.py` (381); `data/cards/inimigos/` e `_decks.json`
  (369; esta spec cria só arquivo novo); `web/src/types.ts` (quente em 368/371); `enemy_decks.py` (371 tocou
  `fauna_saber` aqui: rebase cuidadoso).
- **Size budget:** três arquivos > 1.000 linhas no caminho. Qualquer linha nova neles exige extração
  equivalente.

## 8. Gate de letalidade (coordenador roda; subagente não)

Um de cada vez, sem `-n`. As duas pontas usam o baralho de cartas e os baralhos de inimigo `on`; a única
diferença é a flag do reforço.

```bash
BASE="RPG_CARD_DECK=on RPG_ENEMY_DECKS=on RPG_ENEMY_INTENT=on"
env $BASE RPG_COMBAT_REINFORCEMENTS=off bash scripts/dev/py.sh docs/spec391/arena_reforco_cartas.py 20 --levels 3,5,8 --json > docs/spec391/gate-off.json
env $BASE RPG_COMBAT_REINFORCEMENTS=on  bash scripts/dev/py.sh docs/spec391/arena_reforco_cartas.py 20 --levels 3,5,8 --json > docs/spec391/gate-on.json
# neutralidade: células sem líder idênticas (sim.py inalterado; flag não alcança run_round sem gatilho).
# Etapa 0: o JSON da 285 tem elapsed_s; compara-se só `.cells` (default sem lider_matilha).
env $BASE RPG_COMBAT_REINFORCEMENTS=off bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 > docs/spec391/neutro-285-off.json
env $BASE RPG_COMBAT_REINFORCEMENTS=on  bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 > docs/spec391/neutro-285-on.json
bash scripts/dev/py.sh -c "import json;a,b=(json.load(open(f'docs/spec391/neutro-285-{m}.json',encoding='utf-8'))['cells'] for m in ('off','on'));assert a==b,'285 nao neutra'"
# 368: mesmo par off/on de docs/spec368/metricas_epico.py --out ...; comparar o JSON sem `elapsed_s`.
```

L1 fica fora: o orçamento do nível 1 (3) não comporta Elite + Lacaio, então ali o reforço nunca chega
[F `SPEC-325…md:782-784`, `:644`].

**Critério [D-391-4; R = opção 2]:**

1. Células sem líder: Δ = 0,0 pp (sempre, todas as opções).
2. Célula `lider_matilha` (5 Posturas × L3/L5/L8 × líderes do pool × sementes 0–19):
   - opção 1 (estrito, igual ao R17 da 325): morte ON − OFF ≤ **+3 pp** agregado;
   - **opção 2 [R]:** morte ON − OFF ≤ **+8 pp** agregado e ≤ +12 pp em cada Postura, e vitória ON de cada
     Postura dentro da faixa **45–85 %** travada pelo dono (SPEC-369 R2/(d)). Sangromante segue a exceção já
     registrada na 335;
   - opção 3 (só faixa): vitória ON dentro de 45–85 % por Postura, sem teto de Δ.
3. Contra-jogo funciona: `cancelled / telegraphed` ≥ 25 % (o bot do baralho foca o líder sozinho; se ficar
   abaixo, o contra-jogo não é real) [R; o dono pode tirar].
4. `timeout` reportado junto de `death` (D-P2-6 da 325).

**Alavancas pré-declaradas [D-391-5; R = na ordem, parar na 1ª que passar]:**

- L1 — Chegada só com **folga** de orçamento: restante ≥ custo do reforço + 1 Lacaio (opção 1 recomendada ao
  dono em 26/10 [F `SPEC-325…md:810`]).
- L2 — O reforço chega "recuperando o fôlego": não age na rodada seguinte à chegada (status determinístico de
  1 rodada, visível no chip).
- L3 — O reforço é sempre o "Capanga do bando" de Lacaio (nunca o Lacaio da facção, mais forte).
- Nenhuma alavanca mexe no avaliador, nas sementes, no bot ou no denominador. Se as três falharem, a flag
  fica `off` e o dono decide.

## 9. Decisões do dono (pendentes)

- **D-391-1 — Forma do chamado.** A [R] Carta forçada por gatilho de 50 % · B assinatura periódica · C R16 com
  UI de tabuleiro (§3.1).
- **D-391-2 — Tempo.** [R] telegrafo no fim de N, Chamado em N+1, chegada no fim de N+2 (duas chances de
  contra-jogo) · alternativa: chegada no fim de N+1, logo após o Chamado (mais rápido e mais letal).
- **D-391-3 — Flag.** [R] reusar `RPG_COMBAT_REINFORCEMENTS` (com baralho `on` = Carta; `off` = R16 legado)
  · alternativa: flag nova `RPG_CARD_REINFORCEMENTS` (liga a Carta sem reviver o legado; +1 flag no registro).
- **D-391-4 — Critério do gate.** opção 1 (+3 pp) · **opção 2 [R]** (+8 pp agregado, +12 pp por Postura,
  vitória 45–85 %) · opção 3 (só faixa). Também: manter ou tirar o piso de contra-jogo (≥ 25 % cancelados).
- **D-391-5 — Alavancas.** Aprovar L1–L3 (ou parte) e a ordem; e o que fazer se todas falharem
  ([R] flag `off`, medida registrada).
- **D-391-6 — Nome e voz da Carta.** [R] "Chamado do Bando", neutra, com telegrafo por natureza
  (fera/humanoide) · alternativa: "Uivo de Chamado" para todos (destoa no `enemy_soldado_legiao_ferro`) ·
  alternativa: reaproveitar o "Uivo de Reunião" existente (mexe em arquivo de família, conflita com a 369).
  Pendência relacionada: D-367-2 (frases do Presságio em "você").
- **D-391-7 — `test_enemy_decks.py:311-316`.** [R] manter a asserção sobre os pools de família, trocar só o
  comentário e somar o teste positivo · alternativa: apagar o teste.
- **D-391-8 — Ligar e e2e.** Depois do gate e do smoke, ligar no `staging_flags.json` só com o "liga" do dono
  ([R]); e2e Playwright do chamado: [R] não (unidade web basta), ou sim.
