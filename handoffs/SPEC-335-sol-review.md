# SPEC-335 — revisão sol (review)

> **Veredito resíduos (`14dce909`):** `APPROVED_WITH_FOLLOWUPS` (só `momento` mudou; pousar já e adiar o ajuste por Postura para depois da SPEC-339, com o critério 45–75 % aberto)
> **Veredito Lote 6 + R6 (`3e59ef20`):** `APPROVED_WITH_FOLLOWUPS` (0 P0/P1; 5 P2; meta "≥ 520" da spec com a conta errada: a base correta dá 483, entregue 499)
> **Veredito Lote 5 (Médico de Campo):** `APPROVED_WITH_FOLLOWUPS` na re-revisão de `72f82c23` (a 1ª rodada, em `75452e54`, deu `CHANGES_REQUIRED` com 2 P1 e 4 P2; o bugfix de motor fica na SPEC-339)
> **Veredito Lote 4 (Corruptor):** `APPROVED_WITH_FOLLOWUPS` na re-revisão de `7a40ae9d` (a 1ª rodada, em `25b00b3f`, deu `CHANGES_REQUIRED` com 1 P1 e 4 P2)
> **Veredito Lote 3 (Devoto, `8874f777`):** `APPROVED_WITH_FOLLOWUPS` (0 P0/P1; 4 P2)
> **Veredito Lote 2 (Sangromante):** `APPROVED_WITH_FOLLOWUPS` na re-revisão de `8364eaa7` (a 1ª rodada, em `b3f5e743`, deu `CHANGES_REQUIRED` com 3 P1 e 7 P2)
> **Veredito Lotes 0–1 (`565b0d0b`):** `APPROVED_WITH_FOLLOWUPS` (histórico abaixo, inalterado)
> **Revisor:** Sol (Claude Opus 5.5, spec-reviewer) · **Data:** 2026-10-27
>
> Nota de nome: o coordenador pediu `handoffs/SPEC-335-sol-review-lote2.md`, mas esse nome
> reprova `scripts/check_handoff_names.py` / `tests/test_handoff_names.py` (o padrão é
> `SPEC-NNN[-papel]-tipo.md`, sem sufixo). Por isso a revisão do Lote 2 entrou neste arquivo.

# Resíduos da SPEC-335 (`14dce909`)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`. Concordo em pousar já e deixar o ajuste de poder por
> Postura para depois da SPEC-339, com as condições da seção "Pousar agora?".

## Conferido

1. **Só `momento` mudou: OK.** Comparei `14dce909~1` com `14dce909` Carta a Carta em
   `bestiario.json` e `exemplos.json`. Mudaram 45 Cartas, e só em `momento`/`momento_placeholder`;
   ids e ordem são os mesmos. Passam o golden e o snapshot da 330 (`test_card_effects_grammar`),
   `test_enemy_decks` e `test_conflito_autoria_bestiario` (baralhos de inimigo da 332), além de
   `test_card_variety`.
2. **A remoção do placeholder não quebra nada: OK.**
   - Nenhum código de `services/`, dos scripts ou do validador lê `momento_placeholder`; só os
     testes, que agora exigem 0.
   - `gen_tiers_5_plus.KEEP_FIELDS` perdeu o campo sem efeito colateral.
   - `check_voice` recusa `descricao` vazia (`""`, espaços, `None`), e o teste varre o pool
     inteiro (mais de 500 Cartas) atrás de descrição vazia ou de frase-modelo.
   - `validate_content` dá 0/0.
   - **Incidente meu, já desfeito:** ao testar o gerador, rodei `gen_tiers_5_plus.py` sem
     argumentos. Mesmo sem `--force`, ele **reescreveu 10 arquivos de dados** (`basicas.json`,
     `tiers_5_plus.json`, os das Posturas e `classes.json`) com CRLF, ordem de chaves diferente e
     listas expandidas. Não mudou nenhum valor, mas sujou o diff. Restaurei com `git checkout`, e a
     árvore está limpa. Ver P2-1.
3. **A arena por Postura não basta para decidir balanceamento.** Ela serve como alarme, não como
   régua, por estes motivos:
   - **Viés de ordem do `full_deck`**: no mesmo tier, a escolha segue o id, não a qualidade.
   - **A linha "todas as subclasses"** usa um baralho impossível para o jogador (mistura as 3
     subclasses). É dessa linha que vêm o Devoto a 77,1 % e o Médico a 75,0 %.
   - **Amostra pequena**: 4 criaturas por categoria. A variância está mais na escolha das criaturas
     do que nas 20 sementes, então o erro real é maior que os ±3 pp do relatório.
   - **O bot** não usa reações nem pondera controle.
   - **Provocar e Marca de `duracao` 1 não fazem nada** até a SPEC-339, o que pesa sobretudo no
     Devoto e no Sangromante.

   Dois sinais são robustos o bastante para guiar a próxima rodada:
   - **Sangromante acima de 75 % no padrão em todas as subclasses** (79,2 / 80,0 / 81,7).
   - **Corruptor/alma no fundo** (44,6 no padrão / 34,4 com elite).

   No Devoto, por subclasse só o consagrado passa de 75 % (76,7), dentro do erro.

## Pousar agora?

**Concordo em pousar e adiar o ajuste.** Mexer no poder agora seria refeito: com a SPEC-339,
Provocar e Marca passam a valer e os números mudam. Condições:

- O critério "45–75 %" fica **aberto** na spec, como está. A 335 **não** vai para `done` enquanto
  ele não for fechado ou passado formalmente a outra spec: a SPEC-339 (critério de aceite: refazer
  a arena das Posturas depois do bugfix) ou a 336.
- Antes da próxima medição: ordenar o `full_deck` por poder ou por amostra com semente (P2-3 do
  Lote 5), usar só as linhas **por subclasse** e aumentar as criaturas (`--per-cat` ≥ 8) ou as
  sementes.
- Registrar no ESTADO o risco do Sangromante a ~80 %. As Cartas de onda já estão no jogo `off`
  como opção de Acervo; o baralho `on` e o espólio continuam desligados.

## Achados

| ID | Sev. | Arquivo | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `scripts/gen_tiers_5_plus.py` (ferramenta, anterior a este commit) | Rodar sem argumentos regrava 10 arquivos de dados com CRLF, outra ordem de chaves e listas expandidas, apesar do "sem `--force` só preenche o que falta". O risco é alguém commitar um diff enorme sem mudança semântica. | Escrever com `newline="\n"` e o mesmo formato dos arquivos (ou não gravar se nada mudou), e acrescentar `--check` sem escrita. 336. |
| P2-2 | P2 | `docs/spec335/RELATORIO-arena-posturas.md` | A tabela principal usa a linha "todas as subclasses", que não é um baralho possível de jogador. | Pôr as linhas por subclasse em destaque e registrar que o critério será medido por subclasse, com o `full_deck` corrigido, depois da SPEC-339. |

## Comandos rodados (resíduos)

```text
scratchpad/sol7_cmp.py (14dce909~1 × 14dce909: bestiario.json, exemplos.json) → 45 Cartas, só momento/momento_placeholder
grep momento_placeholder (.py/.json/.yaml fora de docs/historico e handoffs) → só tests/test_card_acervo_reparo.py
pytest -q -n 2 test_card_acervo_reparo, test_card_effects_grammar, test_card_lint, test_enemy_decks, test_conflito_autoria_bestiario, test_card_variety, test_handoff_names → exit 0
scripts/validate_content.py → 0 erros, 0 avisos
scripts/gen_tiers_5_plus.py (sem argumentos, por engano) → regravou 10 arquivos (CRLF/formato); restaurados com git checkout; árvore limpa
arena_posturas.py: não rodei de novo (cerca de 9.600 lutas); leitura do script e do JSON
```

# Lote 6 + R6 (`main...3e59ef20`)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`. Não há P0 nem P1; ficam 5 P2. A meta "≥ 520" da
> spec está com a conta errada (P2-1).

## Escopo

Commit `3e59ef20`, sobre a `main` com os Lotes 1–5. Entram `data/cards/valoria_neutras.json` (40
`neu1_*`), os 5 `posturas/*_tronco.json` (16 `*_tro_*`), `_ondas.yaml`, `services/card_rewards.py`,
`services/content_validator.py`, os testes `test_card_variety`, `test_card_acervo_reparo` e
`test_card_rewards`, e `docs/spec335/` (relatório, 3 scripts e 4 JSON). Nada em `evals/`.

## Os 6 pontos do coordenador

**1. `roll_rewards` com `region_id`: não muda nada no `off` e mantém o determinismo.**
- **`off`:** `RPG_CARD_REWARDS` vale `off` por padrão e não está no preset do staging. Nesse modo,
  o gancho (`card_rewards.py:188`) devolve antes de rolar.
- **Alcance da mudança:** só acrescenta uma string ao `set` `region_ids`, que é lido **apenas** por
  pertencimento em `_pools` (`regiao in region_ids`). Os pools são `sorted` e o RNG é
  `Random(f"{seed}:espolio")`, então não há ordem de hash nem aleatoriedade nova.
- **Quem é afetado:** só Cartas com `regiao`, ou seja, as neutras. As de `status_e_maldicoes` têm
  `regiao` de corpo (`cabeca`/`torso`), que nunca é `region_id`, e `_eligible` já exclui status.
- **Com `on`:** o espólio passa a ter um pool `neutra` não vazio. É o efeito pretendido do lote, e a
  mesma semente com o mesmo estado continua dando o mesmo espólio.

**2. As neutras não vazam: OK.**
- `cards_for_class(Postura)` só aceita `classe` igual à Postura ou vazia, e as neutras têm
  `classe: Neutra`.
- `progression.eligible_cards` e a criação usam `cards_for_class(class_name)`.
- `test_card_variety` e `test_card_acervo_reparo` provam que nenhum `neu1_` aparece no Acervo nem no
  baralho inicial.
- Exceção teórica: `cards_for_class("")` devolve tudo, neutras incluídas. Só um teste de cena usa
  isso, e nenhum jogador tem `class_name` vazio (P2-5).

**3. As 16 de tronco não mudam o caminho automático do `off`.**
- Rodei `character_creator._resolve_starting_cards` nos níveis 1 e 2, com e sem as `*_tro_` no
  catálogo, para as 5 Posturas. O Acervo inicial (6), as Preparadas e as Virtudes saem
  **idênticos**. As canônicas `conflito-14` vêm primeiro e já enchem as 6 vagas.
- O que muda no `off` é só a **escolha**: elas aparecem como opção no assistente e entram em
  `eligible_cards` nos níveis 1–2. É conteúdo novo à escolha do jogador, como nos Lotes 1–5.
- Os testes de progressão e de `cards_prepare` passam.
- Ressalva: `arc1_tro_lance_calculado` só faz `comprar 1`, que não faz nada com o baralho `off`
  (vira `pendente_pilhas`). Uma Carta de tronco de nível 1 que o jogador de hoje pode escolher e
  não faz nada (P2-3).

**4. O R6 não está afrouxado nos números, mas a definição precisa ficar explícita na spec.**
- O teste é **mais estrito** que a spec em um eixo: conta por **subclasse** (15 combinações), não
  pela Postura inteira. Exclui básicas, Ápice, Virtude, status e neutras, e tem um teste que obriga
  as faixas a cobrirem todo `level_req`. Os números ≥ 10 / ≥ 4 / ≥ 3 não mudaram.
- Em outro eixo ele é **cumulativo** (`level_req ≤ nível`), enquanto a spec diz "por tier".
- Medi a leitura por faixa, contando só as Cartas novas de cada faixa: **119 de 135 casos
  falhariam** (por exemplo Devoto/consagrado: 1 Carta nova no nível 12, 0 no 20). Com 12 Cartas
  por subclasse, essa leitura é inatingível, então a cumulativa é a única viável. Mas ela esconde
  que os tiers altos quase não ganham Carta.
- Pior caso da leitura cumulativa: 13 Cartas, 7 kinds, **3** palavras-chave, no limite.
- Ver P2-2.

**5. A meta "≥ 520" está errada; a entrega está certa.** A spec soma "308 + 180 + 40", mas as 308
legadas (o conjunto de `legacy_cards()`) incluem **40 Cartas de inimigo e 5 de Virtude**, que não
são Acervo de jogador. Recontei no catálogo:

| Conta | Total |
|---|---|
| Base correta: legadas de Postura | 263 |
| Meta com a base correta: 263 + 180 + 40 | **483** |
| Entregue: 263 + 196 (180 + 16 de tronco) + 40 neutras | **499** (459 de Postura + 40) |
| Os 448 do executor: só baralho (ativa, reação, utilitária) | 408 + 40 = 448 |

Os 448 deixam de fora as **51 passivas**, que também são Acervo (aprendidas, não vão para o
baralho). A meta da spec tem de ser corrigida (P2-1).

**6. Checagens de sempre: OK.**
- Neutras com raridade 20/12/6/2 (R3 do lote de 40 = 20/12/6/2) e onda `aprovada` com a nota "sem
  leitura"; tronco também `aprovada`.
- Nenhum nome nem id colide nos 732 objetos nomeados (40 neutras e 16 de tronco conferidos).
- `validate_content` dá 0/0 e recusa `origem_lore` fora do codex, com teste.
- Joguei as 56 Cartas no motor (`ct.resolve_turn`): todas aplicam o que o texto diz, com a
  ressalva de `lance_calculado` no `off`.
- A arena do tronco (`confirmar_tronco_lote6.py`), rodada de novo, saiu **idêntica** ao JSON.
- O teste de equivalência das 308 legadas e o snapshot da 330 passam (sem mudança em Carta
  legada).

## Achados

| ID | Sev. | Arquivo | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `specs/SPEC-335…md` §5 | A meta "≥ 520 (308 + 180 + 40 − cortes)" usa uma base 308 que contém 40 Cartas de inimigo e 5 de Virtude. | Trocar por "Acervo de jogador ≥ 483 (263 legadas de Postura + 180 + 40 − cortes)" e marcar como cumprido: 499, incluindo 51 passivas e 16 de tronco. Registrar também a conta "só baralho" (448) para não haver ambiguidade. |
| P2-2 | P2 | `specs/SPEC-335…md` R6; `tests/test_card_variety.py` | A spec diz "por tier"; o teste mede a oferta **cumulativa**. Escolha defensável e mais estrita por subclasse, mas não está na spec e esconde tiers altos vazios (0–1 Carta nova por subclasse do nível 12 em diante). | Escrever na R6 "oferta cumulativa por faixa de nível, por subclasse". Acrescentar um piso por faixa (por exemplo, cada faixa a partir do 4 traz ≥ 1 Carta nova por subclasse) só se a 336/onda 2 assumir isso. Registrar o vazio dos tiers altos como insumo da onda 2. |
| P2-3 | P2 | `data/cards/posturas/arcanista_cinzento_tronco.json` (`arc1_tro_lance_calculado`) | Carta de tronco de nível 1 que só faz `comprar 1`, um efeito de pilha que não faz nada com o baralho `off` (o jogo de hoje). Já estava disponível no assistente e em `eligible_cards`. As duas do Lote 1 com o mesmo problema (`arc1_cal_compasso`, `arc1_des_corrente`) foram aceitas antes, mas eram de subclasse. | Dar um efeito que valha no `off`, junto do `comprar`, ou esconder Cartas só de pilha do Acervo enquanto o baralho estiver `off`. 336/328: lint de aviso para Carta cujo único efeito é de pilha. |
| P2-4 | P2 | spec R2 | A R2 pede neutras "por espólio, loja e quest", mas só o espólio existe (registrado pelo executor). Com `RPG_CARD_REWARDS=off` em produção e staging, **as 40 neutras não aparecem em jogo nenhum hoje**. | Deixar claro na spec. Ligar o espólio fica com a 333 ou o dono; loja e quest, numa spec futura. |
| P2-5 | P2 | `services/cards.py:287` (`cards_for_class("")`) | Com `class_name` vazio, devolve todas as Cartas, neutras incluídas. Hoje não há caminho de jogador que chegue aí. | Excluir `classe: Neutra` também nesse caminho, ou documentar. 336. |

## Comandos rodados (Lote 6 + R6)

```text
git diff main...3e59ef20 (21 arquivos) → card_rewards.py, content_validator.py, test_card_variety.py, spec lidos
grep region_ids/regiao em card_rewards.py → só pertencimento; pools sorted; RNG com semente; off devolve antes
character_creator._resolve_starting_cards (5 Posturas, nível 1/2, com/sem *_tro_) → idêntico
contagem do catálogo → legado: 263 de Postura, 40 inimigo, 5 virtude (= 308); onda: 196 de Postura + 40 neutras; Postura 459 (51 passivas)
R6 por faixa não cumulativa → 119/135 falhariam; cumulativa: pior caso (13, 7, 3)
scratchpad/sol6_play.py (40 neu1_ + 16 *_tro_ por ct.resolve_turn) → só lance_calculado (comprar) sem efeito no off
confirmar_tronco_lote6.py --out <scratchpad> → idêntico a sim-lote6-tronco.json
nomes/ids (732 objetos) → 0 colisões; raridade das neutras 20/12/6/2
pytest -q -n 2 test_card_variety, test_card_rewards, test_card_acervo_reparo, test_card_effects_grammar, test_card_lint, test_card_sim, test_mecanica_orfa, test_handoff_names, test_card_piles, test_scene_cards_extra → exit 0
pytest -q -n 2 test_cards_prepare_api, test_progression_20, test_progression_v4 → exit 0
scripts/validate_content.py → 0 erros, 0 avisos
```

# Lote 5 — re-revisão (`e81a4cdb..72f82c23`)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`. Os 2 P1 estão resolvidos no que cabe ao lote; o
> bugfix de motor fica na SPEC-339. A allowlist provisória é aceitável, com uma trava (P2-5).

## Conferência

| ID | Situação |
|---|---|
| P1-1 | **Resolvido.** Os 4 híbridos passaram para `cena`, e o DoT da agulha caiu de 2 para 1 rodada. Reproduzi com 320 lutas: agulha **+6,2 pp**, cotovelo **+4,1 pp**, iguais ao JSON de confirmação. Também golpe_e_pulso +4,1 e pinça +5,9. Todos abaixo de +8 e perto dos controles de dano da subclasse (+0,3 / +5,6 / +10,0). O teste do lote passou a exigir `cena` em incomum com dano. |
| P1-2 (lote) | **Resolvido.** Giz Vermelho ficou com `duracao: 2` e `cena`. Numa rodada real (`orch.run_round`, baralho `off`) a Marca **sobrevive** ao turno do inimigo, quando antes "terminava" antes de valer. |
| P1-2 (motor) | Fica na SPEC-339. Entrou o lint provisório `check_controle_duracao`: recusa `taunt`/`marca` com `duracao` < 2 em Carta de onda, com teste. |
| P2-1 | **Resolvido.** Tala Rígida e Giz Vermelho em `cena`. O teste exige `cena` em toda Carta de Fôlego 0 do lote. |
| P2-2 | **Revertido com razão.** Não cobrar sem Carga mudava `med_bot_purga` no golden. Fica a descrição de Sal na Sombra ("haja Carga ou não") e o texto gerado sem o custo extra. Continua follow-up na SPEC-339 ou 325, junto com o golden. |
| P2-3 | Registrado no relatório como limitação, com follow-up na 336. |
| P2-4 | **Resolvido.** O relatório traz os controles e o efeito de `cena`, e por subclasse no padrão dá 64,2 / 63,7 / 67,1 %, abaixo do alvo de 70 %. O Ferro saiu de 73,3 %. |

## A allowlist `CONTROLE_DURACAO_PENDENTES` até a SPEC-339

**Aceitável.**
- **Lista exata.** Conferi no catálogo: as Cartas de onda com `taunt`/`marca` de `duracao` < 2 são
  exatamente as 9 da lista (6 de Provocar e 3 de Marca dos Lotes 2–3). Não falta nem sobra
  nenhuma.
- **Por que esperar faz sentido.** As 9 já estão na `main`. Hoje o Provocar não faz nada e a
  Marca de `duracao` 1 só vale na mesma rodada; isso já era assim antes do lote, então a lista
  não cria regressão. Corrigir as Cartas agora, com `duracao` 2 e `versao` 2, e depois desfazer
  quando o motor mudar seria trabalho em dobro: com a SPEC-339, `duracao` 1 passa a valer e uma
  `duracao` 2 viraria buff. Esperar o motor é o caminho mais barato.
- **Condição: a lista tem de travar** (P2-5).

| ID | Sev. | Arquivo | Problema | Correção |
|---|---|---|---|---|
| P2-5 | P2 | `services/card_lint.py` (`CONTROLE_DURACAO_PENDENTES`) | Nada impede a lista de crescer nem de envelhecer. Um id novo pode entrar para escapar do lint, e um id que já foi corrigido continua isento. Também não há ligação explícita com a SPEC-339. | Teste: (a) cada id da lista existe e ainda tem `taunt`/`marca` com `duracao` < 2, para que entrada velha falhe; (b) `len(...) <= 9`, para que a lista só encolha. Comentário: "remover junto com a SPEC-339". Na SPEC-339, critério de aceite: lista vazia e lint removido ou com limite 1. |

## Comandos rodados (re-revisão do Lote 5)

```text
git diff e81a4cdb..72f82c23 (14 arquivos) → lidos card_lint.py, testes, 3 JSON de Cartas, relatório
sim.py --lote data/cards/posturas/medico_boticario.json --protocolo lote --out <scratchpad> → idêntico a sim-lote5-boticario.json
scratchpad/sol5_ctl2.py (sementes 20–99): agulha +6,2 pp, cotovelo +4,1 pp → iguais à confirmação
scratchpad/sol5_tick.py (run_round, baralho off): Giz Vermelho segue no inimigo depois da rodada 1
varredura do catálogo: Cartas de onda com taunt/marca de duracao < 2 = exatamente as 9 da allowlist
pytest -q -n 2 (7 arquivos de cartas e handoff) → exit 0; validate_content → 0/0
```

# Lote 5 — 1ª rodada (`main...75452e54`)

> **Veredito:** `CHANGES_REQUIRED` (2 P1, 4 P2). Os 4 híbridos estão fortes de verdade, e há um
> bug de motor anterior a este lote que zera Provocar e encurta a Marca com `duracao` 1.

## Escopo

Commit `75452e54`, sobre a `main` com os Lotes 1–4. Entram as 3
`data/cards/posturas/medico_{boticario,cirurgiao_ferro,cirurgiao_trincheira}.json` (36
`med1_*`), os 4 legados com `momento`, `_ondas.yaml`, `docs/spec335/` (relatório, 2 scripts e 5
JSON), a spec e `tests/test_card_acervo_reparo.py`. Nada em `evals/`, `services/` ou `sim.py`.

## Checagens de sempre

- **Legadas e golden: OK.** Em `exemplos`, `exemplos_extra`, `medico` e `tiers_5_plus` mudaram 52
  Cartas, só em `momento`/`momento_placeholder`. Golden e snapshot da 330 passam.
- **Motor real, as 36 Cartas** (`ct.resolve_turn`, jogador com Carga 3 e Entropia 10):
  - A cura, a Proteção, a Vigília e os buffs (Defesa, Acerto, Dano) vão para o próprio Médico em
    luta solo; `protecao`/`purga` com `alvo: aliados` incluem o próprio Médico (`_allies`).
  - Torpor, Cego, Enredado, Exposto, Desarme, DoT e empurrão chegam ao inimigo. Num principal de
    suporte, o Torpor extra cai no 1º oponente, sem rolagem.
  - `reduzir_carga_aliado` tira Carga do próprio Médico.
  - As 3 reações têm `gatilho` válido e efeito com ramo em `_resolve_reaction_effect`.
  - A regra nova de "uma condição de stat por Carta" se cumpre.
  - **Exceção: Giz Vermelho (P1-2).**
- **Raridade e nomes: OK** (20/10/4/2). Lint sem aviso; nenhum nome nem id colide nos 676 objetos
  nomeados.
- **Voz:** `aprovada`, com a `nota_voz` "sem leitura". `validate_content` dá 0/0.
- **Arena reproduzível:** rodei de novo `--protocolo lote` em `medico_cirurgiao_ferro.json`, e o
  JSON saiu idêntico.
- **Testes:** os 7 arquivos do escopo passaram com `-n 2` (exit 0).

## Os 5 pontos do coordenador

**1. Fôlego 0 em 11 comuns: aceitável com `cena`, frágil com `turno`.** A R6 da 328 já dá
Fôlego 0 a Carta sem dano, e com `cena` é uma jogada grátis por cena, limitada pela vaga na mão.
O problema é que **a Entropia não pesa**: com custo de Entropia 2 em vez de 1, os híbridos dão
exatamente o mesmo delta (golpe_e_pulso +15,0 = +15,0; agulha +16,6 = +16,6), porque o jogador
ganha Entropia ao sofrer dano. Com isso, Fôlego 0 + `turno` vira efeito grátis **todo turno**:
- `fer_tala_rigida`: +2 de Defesa renovada, 90 % de uso;
- `bot_giz_vermelho`: Marca, 87 % de uso.

Passar as duas para `cena` ou Fôlego 1 (P2-1). As outras 9 ficam como estão.

**2. Os híbridos são fortes de verdade, não efeito do braço base.** Comparei com controles de mesma
subclasse e mesmo custo, com 320 lutas por braço:

| Carta | Delta | Controle (mesma subclasse) | Sobra acima do controle |
|---|---|---|---|
| `tri_golpe_e_pulso` (dano 3 leve) | +15,0 | dano 3 leve: +5,6 | **+9,4** |
| `bot_agulha_envenenada` (dano 3 leve) | +16,6 | dano 3 leve: +0,3 | **+16,3** |
| `fer_cotovelo_de_aco` (dano 4 marcial) | +20,0 | dano 4, do executor: +10,0 | **+10,0** |
| `fer_pinca_de_aco` (dano 4 marcial) | +17,5 | dano 4, do executor: +10,0 | **+7,5** |

O que pesa é a frequência `turno`, a mesma alavanca da Bênção do Aço no Lote 3. Com `cena`:
golpe_e_pulso **+4,1**, cotovelo **+4,1**, pinça **+5,9**, agulha **+9,1**. Custo de Entropia 2
não muda nada. Ver P1-1.

**3. Os 74,6 % só no padrão: risco moderado, e é o subclasse Ferro (73,3 %) que preocupa, não a
linha "todas".** A linha que mistura as subclasses não é um baralho real de jogador. O Ferro é a
subclasse de `cotovelo` e `pinca`, as duas mais fortes; passá-las para `cena` deve tirar o Ferro
da borda. Refazer `arena_postura_medico.py` depois do P1-1 e registrar os números. Sugiro alvo
≤ 70 % no padrão por subclasse, com o jogador real tendo uma só.

**4. A ordem no `full_deck` distorce a arena da Postura, mas não o delta por Carta.** Dentro do
mesmo tier, `pool.sort(-tier, id)` escolhe **pela ordem alfabética do id**, não pela qualidade:
`med1_…` vem antes de `med_…` e depois de legadas como `antitoxina`/`estabilizar`, e as comuns
ocupam 2 vagas.
- Em L5 "todas", o baralho "depois" tem 13 `med1` + 2 legadas + 9 básicas; 44 Cartas ficam fora.
- O "antes × depois" da Postura mede então "o lote preenche o baralho", não "o melhor baralho".
- No protocolo por Carta (`build_arms`, `com = sem + Carta`) a ordem não importa.

Follow-up na 336 (P2-3): ordenar por poder do orçamento, ou por amostra com semente, em vez do
id. Isso vale também para os Lotes 1–4.

**5. `reduzir_carga_aliado` cobra 2 de Entropia mesmo sem Carga.**
`cm.reduce_ally_abyss(cost=2)` debita antes de olhar a Carga, e o custo não aparece no texto
gerado. Confirmado: `sal_na_sombra` (Entropia 0 na Carta) leva de 10 para 8; o Elixir custa 5 + 2.
Como a Entropia quase não pesa (ponto 1), o impacto é pequeno. Mas o texto mente sobre o custo e,
sem Carga, a Carta gasta à toa. P2-2.

## Achados

| ID | Sev. | Arquivo | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `medico_cirurgiao_trincheira.json` (`golpe_e_pulso`), `medico_boticario.json` (`agulha_envenenada`), `medico_cirurgiao_ferro.json` (`cotovelo_de_aco`, `pinca_de_aco`) | Os 4 híbridos `turno` ficam 7,5 a 16,3 pp **acima** do controle de dano da mesma subclasse e do mesmo custo (tabela no ponto 2). É poder da Carta, não braço base fino. Contraria o precedente da Bênção do Aço (Lote 3), que passou de `turno` para `cena`. | `frequencia: cena` nos 4, medido: +4,1 / +9,1 / +4,1 / +5,9 pp. Agulha ainda fica em +9,1: tirar 1 rodada do DoT ou 1 de dano. Depois, rodar de novo `confirmar_lote5.py` e `arena_postura_medico.py`. |
| P1-2 | P1 (motor, anterior ao lote) | `services/conflict_orchestrator.py:240-268` (`_tick_conditions_v4`) e `:2416`; afeta `med1_bot_giz_vermelho` | **Controle com `duracao` 1 aplicado pelo jogador expira no início do turno do inimigo, antes de valer.** `marca` e `taunt` têm `control`, então não são "stat puro" e são descontados no tick do **começo** do turno de quem os carrega. Numa rodada real (`orch.run_round`, baralho `off`), Giz Vermelho, Livro de Dívidas e Ciúme Aberto mostram "ganha condição X" e logo "X terminou" antes de o inimigo agir. **Provocar com `duracao` 1 nunca vale**: some antes de o inimigo escolher o alvo. São as 21 Cartas de `taunt` do catálogo, todas com `duracao` 1, incluindo a básica `bas_dev_voto`. **A Marca com `duracao` 1 não chega ao turno seguinte do jogador**; com o baralho `on` ainda vale para jogadas da mesma rodada e para aliados que agem antes do inimigo. São 26 Cartas. Isso corrige o que escrevi nos Lotes 3 e 4: Provocar não "só vale com aliados", não vale nunca. Cego, que é stat puro, funciona. | Neste lote: `duracao: 2` em Giz Vermelho (como `arc1_imp_parafuso`) ou passá-la para `cena`. Bugfix de motor, em spec própria ligada à 330/232: controle aplicado por um oponente não pode ser descontado no 1º tick do portador. Uma forma é marcar `aplicado_em` e pular o primeiro tick, como `_expire_stat_conditions` já faz com `present_at_start`. Teste com `run_round`. Até lá, o lint deveria recusar `taunt`/`marca` com `duracao` < 2 em Carta de onda. |
| P2-1 | P2 | `medico_cirurgiao_ferro.json` (`tala_rigida`), `medico_boticario.json` (`giz_vermelho`) | Fôlego 0 + `turno` + Entropia barata dá efeito grátis todo turno (ponto 1). | `cena` ou Fôlego 1. Na 336, lint: Fôlego 0 só com `cena` ou mais raro. |
| P2-2 | P2 | `combat_mechanics.py:850-863`; `card_effects` (texto gerado) | `reduzir_carga_aliado` cobra 2 de Entropia sem Carga a tirar, e o texto gerado não mostra o custo extra (ponto 5). | No motor, não cobrar quando `abyss_charge == 0`, conferindo se não mexe em legada ou golden. No texto, "(custa 2 de Entropia)". 325/336. |
| P2-3 | P2 | `scripts/cards/sim.py:93` (`full_deck`) | No mesmo tier, a escolha do baralho completo segue a ordem alfabética do id; a arena da Postura não mede o melhor baralho (ponto 4). | 336: ordenar por poder ou por amostra com semente; registrar a limitação nos relatórios da Postura. |
| P2-4 | P2 | `docs/spec335/RELATORIO-arena-lote5.md` | O relatório diz "Entropia paga" e "braço base fino" como freio e explicação. Os dois foram refutados acima (Entropia 2 = 1; o controle de dano 3 sobe só +0,3/+5,6). | Atualizar o relatório junto com o P1-1. |

## Pendências

- P1-1, a parte de Carta do P1-2, P2-1 e P2-4: executor, nesta branch.
- O bugfix de motor do P1-2 (controle com `duracao` 1): spec nova, coordenador. Pega Lotes 1–5 e
  legado. Até lá, as Cartas de Provocar continuam sem efeito.
- P2-2 e P2-3: 325/336.

## Comandos rodados (Lote 5)

```text
scratchpad/sol3_cmp.py (main × HEAD, 4 legados) → 52 Cartas, só momento/momento_placeholder
scratchpad/sol5_play.py (36 med1_* por ct.resolve_turn, Carga 3) → efeitos conferem; sal_na_sombra Entropia 10→8
scratchpad/sol5_tick.py (orch.run_round, baralho off: giz_vermelho, livro_de_dividas, ciume_aberto, po_nos_olhos) → marca/taunt "terminou" antes de o inimigo agir; cego vale
contagem de taunt/marca por duracao no catálogo → taunt d1: 15 legado + 6 onda; marca d1: 22 legado + 4 onda
scratchpad/sol5_ctl.py + sol5_ctl2.py (sementes 20–99, 320 lutas por braço) → controles dano 3 leve: +5,6 (trincheira) / +0,3 (boticário); cena: golpe_e_pulso +4,1, agulha +9,1, cotovelo +4,1, pinça +5,9; Entropia 2 = sem mudança
full_deck do Médico (L1/L5, todas/ferro) → L5 todas: 9 básicas + 13 med1 + 2 legado; 44 fora
sim.py --lote data/cards/posturas/medico_cirurgiao_ferro.json --protocolo lote --out <scratchpad> → idêntico
pytest -q -n 2 (7 arquivos de cartas e handoff) → exit 0; validate_content → 0/0; lint → só "id já existe"
```

# Lote 4 — re-revisão (`fb2c2d42..7a40ae9d`)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`. O P1 está resolvido e os P2 aplicados. Ficam 2 P2
> novos de texto/registro, que não bloqueiam.

## Conferência

| ID | Situação |
|---|---|
| P1-1 | **Resolvido.** `cor1_bio_ler_a_carne` → `revelar resistencias`; `san1_sil_olho_no_pulso` → `revelar cartas` (v2). Os dois campos gravam no bestiário (`_persist_revelation`) e aparecem no painel. O lint `check_revelar_publico` recusa `vitalidade` (erro) e avisa `intencao`, para Carta de qualquer origem; `test_revelar_de_campo_publico_e_recusado` cobre. |
| P2-1 | **Resolvido.** `pele_podre` agora custa 1 de Fôlego e 3 de Entropia. `check_reacao_folego` vale só para Cartas de onda; as legadas ficam como estão. |
| P2-2 | **Resolvido.** `check_marca_dano` monta `[primary_effect] + extra_effects`, a ordem real do motor, e tem teste. |
| P2-3 | **Resolvido.** Saíram Ponto Fraco e Ler o Metal; entraram Gancho de Ferro (`mover_alvo_zona aproximar`) e Medir a Fadiga (`buff_dano 2`, `turno`). |
| P2-4 | **Resolvido.** A `descricao` de Nome Apagado agora diz "o próximo golpe", e a Entropia subiu de 3 para 4. |

## As 2 Cartas novas no motor, em luta solo

- **Medir a Fadiga (`buff_dano`): funciona.** Com o baralho `off`, cada turno é uma ação, mas
  `_expire_stat_conditions` só desconta buffs que já existiam no início do turno. O buff jogado
  no turno vale então para o golpe do turno seguinte: dano médio de 5,5 → 7,7 em 20 sementes.
  Com o baralho `on`, vale já para o golpe seguinte da mesma rodada.
- **Gancho de Ferro (`mover_alvo_zona aproximar`): funciona, mas o uso em luta solo é
  estreito.** Com o inimigo visível em `distante`, ele volta para `proximo`. A distância, porém,
  não restringe ataque no motor (não existe regra de alcance para o golpe do jogador). O efeito
  real em luta solo é **cortar a fuga**, porque o inimigo só escapa ao chegar a `separado`. Num
  inimigo **escondido** a Carta nem pode ser jogada ("sem posição conhecida — não pode mirar
  direto"). Ver P2-5.

## A v2 de `olho_no_pulso` quebra save, replay ou golden?

**Não.**
- **Save:** o save guarda só o **id** (decks, `known_cards`, uso); o motor lê a Carta vigente.
- **Versão:** `fx.versao` é só metadado, e nenhum código busca Carta por versão (os únicos
  leitores são `content_validator` e `card_lint`).
- **Golden/snapshot da 330:** cobre só as 308 legadas.
- **Replay:** não há fixture nem replay que cite `san1_sil_olho_no_pulso`.
- O efeito muda para quem já a tem no baralho, mas isso é o esperado (R7 da 336: "motor lê
  versão vigente"), e a Carta antiga não fazia nada.

## Achados novos

| ID | Sev. | Arquivo | Problema | Correção |
|---|---|---|---|---|
| P2-5 | P2 | `corruptor_inorganica.json` (`cor1_ino_gancho_de_ferro`) | A `descricao` ("ao alcance de qualquer lâmina") e o `momento` ("o arqueiro inimigo se esconde atrás da linha") prometem alcance e tirar o inimigo do esconderijo. Não existe regra de alcance para o golpe, e alvo escondido não pode ser mirado. O uso real é impedir a fuga. | Reescrever para o uso real (por exemplo, "puxa de volta quem tenta fugir"). Na 336, decidir se a distância deve pesar no golpe; hoje Mão no Peito (Lote 3) e Pé no Vazio têm o mesmo limite. |
| P2-6 | P2 | `_ondas.yaml` | Gancho de Ferro, Medir a Fadiga e a v2 de Olho no Pulso entraram **depois** da aprovação de voz em bloco do dono, e a onda continua `aprovada`. | Acrescentar à `nota_voz` da onda do Lote 4, e da do Lote 2 pelo Olho no Pulso, que as substituições de 27/10 vieram depois da aprovação, ou levá-las ao dono na próxima amostra. |

A arena não mede `revelar`, `mover_alvo_zona` nem `buff_dano`, como avisou o executor: o
delta das 2 Cartas novas (0,0 e −3,7 pp) diz pouco. O freio é o orçamento, e as duas passam.

## Comandos rodados (re-revisão do Lote 4)

```text
git diff fb2c2d42..7a40ae9d (11 arquivos) → lidos card_lint.py, 4 JSON de Cartas, testes, relatório
scratchpad/sol4b.py: Medir a Fadiga (turno seguinte, 20 sementes) → dano médio 5,5 → 7,7; Gancho em inimigo visível distante → proximo; em inimigo escondido → "não pode mirar direto"
grep versao em services/, scripts/, api, persistence → só metadado (validator e lint); nenhuma fixture cita olho_no_pulso
sim.py --lote data/cards/posturas/corruptor_inorganica.json --protocolo lote --out <scratchpad> → idêntico a sim-lote4-inorganica.json
scripts/cards/lint.py corruptor_{alma,biologia,inorganica}.json → só "id já existe"
pytest -q -n 2 test_card_acervo_reparo, test_card_effects_grammar, test_card_lint, test_card_sim, test_mecanica_orfa, test_handoff_names, test_card_piles → exit 0
scripts/validate_content.py → 0 erros, 0 avisos
```

# Lote 4 — 1ª rodada (`main...25b00b3f`)

> **Veredito:** `CHANGES_REQUIRED` (1 P1, 4 P2). A correção é pequena: um campo de uma Carta,
> mais a mesma correção numa Carta do Lote 2 que já está na `main`.

## Escopo

Commit `25b00b3f`, sobre a `main` com os Lotes 1–3. Entram as 3
`data/cards/posturas/corruptor_{alma,biologia,inorganica}.json` (36 `cor1_*`), os 4 arquivos
legados com `momento`, `_ondas.yaml`, `docs/spec335/` (relatório, script e 4 JSON), a spec e
`tests/test_card_acervo_reparo.py`. Nada em `evals/`, `services/` ou `sim.py`.

## Conferido

- **Legadas e golden da 330: OK.** Comparei `main` e HEAD em `exemplos`, `exemplos_extra`,
  `corruptor` e `tiers_5_plus`. Mudaram 53 Cartas, só em `momento`/`momento_placeholder`.
  Golden e snapshot passam.
- **Motor real, as 36 Cartas** (`ct.resolve_turn`):
  - Rachadura, Torpor, Marca do Abismo (com Vantagem pelo controle `marca`) e os DoTs aparecem
    no alvo.
  - As condições `amedrontado`/`medo` → `fear` (−2 de acerto), `enraizado` → `root`,
    `silenciado` → `silence` (bloqueia Carta em `conflict_turn.py:405`), `desmoralizado`,
    `exposto` e `desarmado_risco` têm efeito mecânico.
  - O dano condicional (`se alvo_tem desmoralizado/rachadura`) vem sempre com dano
    incondicional.
  - O Chamado 3/4 só dispara com Entropia suficiente.
  - Toda `escala` está em efeito extra e vale: Colheita Podre conta a condição nova, 1 → 2.
  - Não há Eco nem Provocar, e as 3 reações têm `gatilho`.
  - `revelar cartas` e `revelar resistencias` gravam no bestiário (`_persist_revelation`) e
    aparecem no painel (`revealed_cards`/`revealed_resistances`).
  - **Exceção: `revelar vitalidade` (P1-1).**
- **`guardar` no motor: funciona, mas só com o baralho `on`.** Com `RPG_CARD_DECK=on`,
  `card_deck_round.end_round` chama `mark_guardadas`. Testei direto: mão [Ponto Fraco, Sussurro
  Rouco] → `discard_hand` mantém só Ponto Fraco. Com o baralho `off`, que é o padrão hoje,
  `guardar` não faz nada, e Ponto Fraco e Ler o Metal ficam diferentes das irmãs só no custo
  (P2-3).
- **Regra da Marca do Abismo com dano:** nenhuma Carta do lote junta Marca e `dano` no mesmo
  efeito, e na prática a regra se cumpre. O teste, porém, olha a ordem da lista, não a ordem em
  que o motor resolve (P2-2).
- **Reações com Fôlego 0:** a única do catálogo inteiro (49 reações) é `cor1_bio_pele_podre`
  (P2-1).
- **Orçamento e raridade: OK** (20/10/4/2). O teste exige lint sem aviso, e nenhum nome nem id
  colide nos 640 objetos nomeados.
- **Voz:** a onda tem `aprovada`, `revisor_voz: dono` e a `nota_voz` "sem leitura".
  `validate_content` dá 0 erros e 0 avisos.
- **Arena reproduzível:** rodei `--protocolo lote` de novo em `corruptor_biologia.json`, e o
  JSON saiu idêntico. Nenhum delta passa de +8 pp; Banquete de Vermes foi de +7,5 para −1,2 pp
  com 320 lutas. As bandeiras de uso (4 `dominante` e 1 `em_branco`) são artefato do bot, como
  nos lotes anteriores.

## Achados

| ID | Sev. | Arquivo | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `data/cards/posturas/corruptor_biologia.json:115` (`cor1_bio_ler_a_carne`); **também** `data/cards/posturas/sangromante_silencioso.json:118` (`san1_sil_olho_no_pulso`, Lote 2, já na `main`) | **`revelar vitalidade` não faz nada.** A Vitalidade do inimigo já é pública: `bestiary_knowledge._PUBLIC_FIELDS` traz `vitalidade`/`max_vitalidade`, e `api.py:2854` sempre a envia ao painel. O efeito só grava `_revelado`, que ninguém lê, e `_persist_revelation` ignora o campo. As duas Cartas, que só fazem isso, são Cartas em branco. Deixei passar no Lote 2. | Trocar o `campo` (`resistencias` ou `cartas`, diferenciando da irmã por custo ou `guardar`) ou dar um efeito real. No catálogo, tirar `vitalidade` de `REVELAR_CAMPOS` ou fazer o lint recusar, com teste. Conferir também `intencao`: o presságio já é visível (329), e nenhuma Carta o usa hoje. |
| P2-1 | P2 | `corruptor_biologia.json` (`cor1_bio_pele_podre`) | É a única reação de Fôlego 0 entre as 49 do catálogo. A R12 da 328 diz "Guardar Fôlego para reagir é uma escolha real", e `can_pay` aceita a Carta com 0 de Fôlego sobrando. Ela escapa dessa troca; o único freio é 2 de Entropia e `turno`. | `custo_folego: 1`, baixando a Entropia para 1 se o orçamento pedir. Lint na 336: `reacao` exige Fôlego ≥ 1. |
| P2-2 | P2 | `tests/test_card_acervo_reparo.py` (`test_lote4_licoes…`) | A regra "sem dano depois da Marca" olha a ordem da **lista**, mas o motor resolve primeiro o efeito principal (`fx.primary_index`: o primeiro `ao_jogar` incondicional de kind legado) e depois os extras. `[dano (com se), marca]` passa no teste e consome a Marca (a principal vira a Marca, e o dano condicional vem depois). `[marca, dano]` é recusado, mas é seguro (o dano é o principal). | Montar a ordem real, `[primary_effect] + extra_effects`, e checar `dano` depois da `marca_do_abismo` nela. De preferência como regra do `card_lint`, que vale para todos os lotes. |
| P2-3 | P2 | `corruptor_inorganica.json` (`ponto_fraco`, `ler_o_metal`) | A diferença para as irmãs vem de `guardar`, que só funciona com o baralho `on`. Com o padrão `off` de hoje, sobra só a diferença de custo. | Nada no lote. Registrar na 336/R6 (`test_card_variety`) que a variedade não pode depender só de palavra-chave de pilha. |
| P2-4 | P2 | `corruptor_alma.json` (`nome_apagado`, `semente_de_culpa`) | "vira a marca de **todos** os golpes": a Marca do Abismo dá Vantagem por 3 rodadas, mas o bônus de dano e a Entropia só valem no **próximo** dano e então a Marca some. | Ajustar a `descricao` de Nome Apagado. A de Semente de Culpa ("o próximo golpe pesa mais") está correta. |

`armadura_comprometida` sem label continua como follow-up, já registrado pelo executor.

## Pendências

- P1-1 (as duas Cartas, mais a regra de `REVELAR_CAMPOS`/lint) e P2-1: executor, nesta
  branch, antes do pouso.
- P2-2: executor (teste) ou 336 (`card_lint`).
- P2-3 e P2-4: opcionais (336 e texto).

## Comandos rodados (Lote 4)

```text
scratchpad/sol3_cmp.py (main × HEAD, 4 legados) → 53 Cartas, só momento/momento_placeholder
scratchpad/sol3_play.py (36 cor1_* por ct.resolve_turn + render_card_text) → só revelar vitalidade inerte
grep _PUBLIC_FIELDS / api.py:2854 / _persist_revelation → vitalidade sempre pública; _revelado sem leitor
card_piles: mark_guardadas + discard_hand (mão [ponto_fraco, sussurro_rouco]) → mantém só ponto_fraco
card_piles.can_pay(pele_podre, folego=0) → ok=True; reações com Fôlego 0 no catálogo: 1 de 49
sim.py --lote data/cards/posturas/corruptor_biologia.json --protocolo lote --out <scratchpad> → idêntico a sim-lote4-biologia.json
scratchpad/sol4_names.py (640 objetos nomeados) → 0 colisões
pytest -q -n 2 test_card_acervo_reparo, test_card_effects_grammar, test_card_lint, test_card_sim, test_mecanica_orfa, test_handoff_names, test_card_piles → exit 0
scripts/validate_content.py → 0 erros, 0 avisos
```

# Lote 3 — Devoto do Abismo (`main...8874f777`)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`. Não há P0 nem P1; ficam 4 P2 de texto/semântica.
> A Bênção do Aço não precisa de ajuste: a parte do delta que passa do limiar vem da arena,
> não do poder da Carta (ver abaixo).

## Escopo

Commit `8874f777`, sobre a `main` com os Lotes 1–2 já pousados. Entram as 3
`data/cards/posturas/devoto_{consagrado,enlutado,zeloso}.json` (36 `dev1_*`), os 4 arquivos
legados com `momento`, `_ondas.yaml`, `docs/spec335/` (relatório, script e 6 JSON), a spec e os
testes `test_card_acervo_reparo` e `test_mecanica_orfa`. Nada em `evals/`, `services/` ou
`sim.py`.

## Conferido

- **Legadas e golden da 330: OK.** Comparei `main` e HEAD Carta a Carta em `exemplos`,
  `exemplos_extra`, `devoto` e `tiers_5_plus`. Mudaram 52 Cartas, e só em
  `momento`/`momento_placeholder`; ids e ordem são os mesmos. Golden e snapshot passam.
- **Motor real, as 36 Cartas.** Joguei cada uma por `ct.resolve_turn`: as de suporte em si
  mesmo, as hostis no inimigo, com Mira +40. Tudo faz o que o texto gerado diz:
  - Vigília acumula e Proteção, Defesa e Acerto valem pelas rodadas indicadas.
  - Rachadura, Torpor, Marca do Abismo e o DoT aparecem no alvo; Medo vem de `amedrontado`
    (controle `fear`, −2 de acerto).
  - `revelar resistencias` funciona, e Interromper arma.
  - Os gatilhos `ao_receber_dano`, `inicio_rodada` (disparado em
    `conflict_orchestrator.py:2320`), `ao_derrubar`, `ao_aliado_sofrer` e
    `ao_pressagio_frustrado` armam em `gatilhos_armados`.
  - A cura com `alvo_tem: desmoralizado` de Consolo Roubado cura (Vit 6 → 9), porque o
    principal aplica a condição antes de o extra ser checado.
  - A `escala por condicoes_alvo` de Peso dos Ausentes está num efeito **extra**, então vale.
  - Não há Eco, e não há `escala` no efeito principal.
  - As 4 reações têm `gatilho` válido (`ao_ser_atacado`, `ao_ser_alvo_distancia`,
    `ao_sofrer_dano_sobrenatural`), e os efeitos delas (`protecao`, `buff_defesa`,
    `aplicar_condicao`) têm ramo em `_resolve_reaction_effect`.
  - **Nenhum efeito inerte.**
- **Provocar:** as 3 Cartas com `taunt` (Ciúme Aberto, Corpo Entre, Ninguém Mais) têm outro
  efeito que vale em luta solo. Ver P2-1 e P2-2.
- **Orçamento e raridade: OK.** 20/10/4/2, testado. O lint das 3 subclasses não dá nenhum
  aviso além de "id já existe" (nenhum par redundante). Nenhum nome nem id colide nos 604
  objetos nomeados de `data/cards/**`.
- **Voz:** as 3 ondas trazem `revisor_voz: dono`, `voz_status: aprovada` e `nota_voz:
  "aprovação geral do dono em 27/10, sem leitura da amostra (não atesta leitura)"`.
  `validate_content` dá 0 erros e 0 avisos.
- **Arena reproduzível:** rodei de novo `--protocolo lote` em `devoto_zeloso.json`, e o JSON
  saiu idêntico a `sim-lote3-zeloso.json`.

## Bênção do Aço a +8,4 pp: precisa de ajuste?

**Não.** Rodei sementes independentes (100–199, 400 lutas por braço) e duas variantes:

| Versão | Sementes | Lutas por braço | Delta |
|---|---|---|---|
| atual | 20–99 (relatório) | 320 | +8,4 pp |
| atual | 100–199 | 400 | +10,2 pp |
| dano 4 → 3 | 0–99 | 400 | +8,8 pp |
| Vigília 2 → 1 | 100–199 | 400 | +9,2 pp |

Juntando as rodadas da versão atual, o delta fica em ~+9,4 pp, só ~1,4 pp acima do limiar de
+8, dentro de 1 erro-padrão. Cortar dano ou Vigília quase não mexe no número. O que pesa é a
Carta **existir** no baralho de nível 4: o braço "sem" fica fino porque o protocolo tira todas
as irmãs do lote, e por isso vence só 33–38 %. A irmã Ciúme Aberto, também com dano 4 (o
Provocar dela não vale sozinho), dá +7,2 pp. Um nerf não tiraria a bandeira sem descaracterizar
a Carta. **Recomendação:** aceitar e registrar os números acima no relatório. Follow-up da 336:
medir o delta por **substituição** (trocar uma básica de mesmo custo pela Carta) em vez de
acréscimo, ou montar o braço base com as irmãs, para não superestimar Cartas de nível ≥ 4.

## Achados

| ID | Sev. | Arquivo | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `devoto_zeloso.json` (`ciume_aberto`, `ninguem_mais`) | As `descricao` prometem Provocar em grupo ("havendo mais de um inimigo, todos olham para o zeloso"; "os inimigos o seguem"). O `taunt` só pega o alvo atingido e só faz diferença quando o inimigo tem **outro** alvo, ou seja, quando o jogador tem aliados (`_taunt_target`, 50 % × multiplicador). | Reescrever para o alvo único ("o inimigo atingido tende a te escolher"). O texto gerado do `taunt` ("precisa atacar você") continua pendente na 336, como no P2-5 do Lote 2. |
| P2-2 | P2 | `devoto_zeloso.json` (`corpo_entre`) | O efeito principal é suporte (Proteção em si), então o `taunt` extra cai em `_targets_for` → `opp[:1]`, o **primeiro** oponente. Com vários inimigos o jogador não escolhe quem provoca, e a `descricao` fala em "os olhos hostis" no plural. | Aceitar e ajustar o texto ("o inimigo mais próximo se volta"), ou pôr o `taunt` como principal com a Proteção de extra (aí o jogador mira, mas precisa acertar). |
| P2-3 | P2 | `devoto_zeloso.json` (`ferro_antes_do_ferro`) | A `descricao` diz "o alívio vem em fôlego", mas o gatilho é `cura` 3 de Vitalidade. | Trocar para "vem em sangue estancado" ou usar `ganhar_folego` (aí rodar o orçamento de novo). |
| P2-4 | P2 | `devoto_enlutado.json` (`pranto_lento`, `cortejo_de_cinzas`) | `dano_tipo: abissal` no `dot` é só cosmético: `_apply_attack_card_effect` monta a condição sem `damage_type`, e `tick_conditions` ignora resistência. O texto gerado ("dano abissal por rodada") sugere que o tipo conta. | Nada no lote. Registrar na 330/336: ou o DoT passa a levar o tipo, ou o texto omite o tipo. |

Observação, sem achado: Véu de Incenso (Proteção 4, 0 de Fôlego, `turno`, 1 de Entropia) tem
93 % de uso e +2,8 pp com 320 lutas. Está dentro do orçamento, mas vale olhar na telemetria
real, porque o 0 de Fôlego por turno é raro no acervo.

## Pendências

- P2-1 a P2-3: executor, nesta branch ou no Lote 4 (só texto, sem mudar mecânica).
- P2-4, o texto do `taunt` e o delta por substituição na arena: SPEC-336 (e 330, no caso do
  DoT tipado).

## Comandos rodados (Lote 3)

```text
scratchpad/sol3_cmp.py (main × HEAD, 4 legados) → 52 Cartas, só momento/momento_placeholder
scratchpad/sol3_play.py (36 Cartas por ct.resolve_turn + render_card_text) → sem efeito inerte
scratchpad/sol3_names.py (604 objetos nomeados em data/cards/**) → 0 colisões
scripts/cards/lint.py data/cards/posturas/devoto_{consagrado,enlutado,zeloso}.json → só "id já existe"
sim.py --lote data/cards/posturas/devoto_zeloso.json --protocolo lote --out <scratchpad> → idêntico a sim-lote3-zeloso.json
scratchpad/sol3_more.py (Bênção: atual s100–199; dano3 s0–99; vigilia1 s100–199; 400 lutas) → +10,2 / +8,8 / +9,2 pp
pytest -q -n 2 test_card_acervo_reparo, test_card_effects_grammar, test_card_lint, test_card_sim, test_mecanica_orfa, test_handoff_names → exit 0 (~224 testes)
scripts/validate_content.py → 0 erros, 0 avisos
```

# Lote 2 — re-revisão (`00efe0e4..8364eaa7`)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`. Os 3 P1 foram resolvidos e os P2 aplicados. Restam
> 2 follow-ups da arena, de responsabilidade da SPEC-336, que não bloqueiam o pouso.

## Conferência dos achados

| ID | Situação |
|---|---|
| P1-1 | **Resolvido.** A `escala` foi para um efeito extra em Juros do Primeiro e Execução da Dívida. Medido no motor: o extra escala com a Entropia (Juros: 1 → 3 → 4 com Entropia 2 → 6 → 20; Execução: 3 → 12 com Entropia 6 → 20). O lint `escala_inerte` (`services/card_lint.py`, erro no principal `dano`/`contra_ataque`) tem teste em `tests/test_card_lint.py`. |
| P1-2 | **Resolvido.** Arterial Fina ficou sem Eco e com Sangria 5, dentro do orçamento. |
| P1-3 | **Resolvido.** `sim.build_arms` monta o braço "sem" com a Carta fora do catálogo e `com = sem + cópias` (reserva de vagas); os dois braços usam a tag `par` (sementes pareadas) e `_fight` ordena o deck. O teste `test_bracos_diferem_so_na_carta_testada` cobre isso. O relatório do Lote 2 tirou a causa falsa e registra o histórico. Reproduzi `sim-lote1-calibrado.json` byte a byte com o `sim.py` novo. |
| P2-1 | Resolvido: as 3 reações têm `gatilho: ao_ser_atacado`. |
| P2-2 | Resolvido: Aplauso de Ferro virou `reacao` `contra_ataque` 3 com `ao_ser_atacado`, e o revide agora é real (`_resolve_reaction_effect`). |
| P2-3 | Resolvido: as `descricao` de Gole Rubro e Poupar Ferida passaram a dizer o que as Cartas fazem. |
| P2-4 | Resolvido em grande parte: os pares foram diferenciados por custo, palavra-chave ou valor. Mão Fechada e Pé de Pluma ainda têm o mesmo efeito (+2 Esquiva) e só diferem no custo; aceitável. |
| P2-5 | Resolvido: Veia à Mostra ganhou um golpe de 3 e já vale em luta solo. O texto do `taunt` ("precisa atacar você") continua prometendo demais; isso é da 336. |
| P2-6 | O executor corrigiu o próprio desvio: não existe legada `ativa`+`buff_esquiva` (as 7 são `reacao`). Nada a registrar. |
| P2-7 | Resolvido: `san1_exp_selo_de_dor` / "Selo de Dor", e `_ondas.yaml` foi atualizado. |

O orçamento e a raridade continuam 20/10/4/2 (testados). O golden e o snapshot da 330 seguem intactos.

## (a) As bandeiras de uso do Lote 2 bloqueiam?

**Não bloqueiam. São um artefato do bot.** `full_deck_decl` joga todo golpe da mão que caiba
no Fôlego, em ordem de `dano_base`, e a taxa de uso só divide "jogada" por "na mão". Numa Postura
de dano, o golpe mais forte de custo 1 sai quase sempre que aparece, seja qual for o poder.
O executor mostrou isso: tirou 1–2 de dano e o uso não mudou. Quem diz se uma Carta domina é o
**resultado**, e nenhuma das 10 tem delta acima de +8 pp (vão de −7,5 a +3,7). `em_branco` em
Poupar Ferida também é efeito do bot, que só cura abaixo de 50 % de Vitalidade. O "> 60 % →
nerf" da R7 da 336 fala de *pick rate* em ofertas reais (telemetria), não do uso na arena.
**Follow-up (336):** na arena, rebaixar `dominante` por uso a aviso (ou exigir uso > 60 % **e**
delta > 0 com amostra) e documentar no `CARTAS.md`.

## (b) `arc1_des_raio_livre` a +11,2 pp passa da R8?

**Não passa, e não precisa de ajuste.** A R8 da 335 fala da taxa de vitória **por Postura**
(±10 % da linha de base), não do delta de cada Carta. Por Carta, o que vale é a bandeira
`dominante` da 336 (delta > +8 pp), e ela disparou. Com 80 lutas, 1 luta vale 1,25 pp e +11,2 pp
são 9 lutas, cerca de 1,4 erro-padrão. Rodei de novo com as **sementes 20–99** (320 lutas
independentes por braço, mesmo protocolo): raio_livre deu **+6,6 pp** e folga **+0,3 pp**,
ambas sem bandeira. Juntando com as 80 lutas do protocolo (400 por braço): raio_livre +7,5 pp,
folga +1,5 pp. Os dois ficam abaixo de +8 pp. **Recomendação:** não mexer nas Cartas e registrar
os números acima no `RELATORIO-arena-lote1.md`. **Follow-up (336):** quando uma bandeira de
delta cair a menos de 2 erros-padrão do limiar, confirmar com mais sementes antes de exigir
nerf.

Observação (P2, 336): no processo do protocolo, `arc1_cal_folga` dá +8,8 pp. Isolada no meu
script, com as mesmas sementes 0–19, deu +6,2 pp. O resultado de uma Carta depende do que rodou
antes no mesmo processo (algum cache ou estado global entre lutas). Como o protocolo completo é
reproduzível byte a byte, isso não invalida o lote, mas a 336 deve isolar esse estado.

## Comandos rodados (re-revisão)

```text
git diff 00efe0e4..HEAD (18 arquivos) → lido: sim.py, card_lint.py, 3 posturas, relatórios, spec, testes
scratchpad/txt.py + play.py (Juros/Execução, Entropia 2/6/20) → escala vale no extra
sim.py --lote …/arcanista_cinzento_calibrado.json --protocolo lote --out <scratchpad> → idêntico a docs/spec335/sim-lote1-calibrado.json
scratchpad/more.py (raio_livre e folga, sementes 0–19 e 20–99) → raio_livre +11,2 / +6,6 pp; folga +6,2 / +0,3 pp
pytest -q (sem -n; RAM 1,1–1,9 GB livre) test_card_acervo_reparo, test_card_effects_grammar, test_card_lint, test_card_sim, test_mecanica_orfa, test_handoff_names → 214 passed, exit 0
scripts/validate_content.py → 0 erros, 2 avisos (voz pendente das ondas)
```

# Lote 2 — 1ª rodada (`main...b3f5e743`)

## Escopo

Branch `spec-335`, commit `b3f5e743` sobre `main` `fc2479c4`. 16 arquivos: as 3
`data/cards/posturas/sangromante_{exposto,avaro,silencioso}.json` (36 Cartas `san1_*`), os 4
arquivos legados com `momento` reescrito (`exemplos.json`, `exemplos_extra.json`,
`sangromante.json`, `tiers_5_plus.json`), `_ondas.yaml`, `docs/spec335/` (relatório, script e
3 JSON da arena), spec, `tests/test_card_acervo_reparo.py` e `tests/test_mecanica_orfa.py`.
Nenhum arquivo em `evals/` foi tocado. O motor (`services/`) e o `sim.py` não mudaram no diff,
mas foram lidos e exercitados porque as Cartas dependem deles.

### Conferido de forma independente

- **Legadas sem mudança mecânica (item 1 do pedido): OK.** Comparei `main` × HEAD carta a
  carta nos 4 arquivos legados (mesmos ids, mesma ordem, mesmas chaves de topo). Mudaram 53
  Cartas, e em todas a única chave diferente é `momento`/`momento_placeholder`. O golden e o
  snapshot da 330 (`test_card_effects_grammar`, incluindo
  `test_texto_gerado_snapshot_das_308_cartas`) passam sem regenerar.
- **Cada Carta nova no motor real (item 2).** Joguei as 36 por `ct.resolve_turn` com o ator e a
  cena de `tests/test_mecanica_orfa.py` (Mira +40 para acertar sempre), com Entropia variável
  e, para as de suporte, alvo `player`. Funcionam como o texto gerado diz: Sacrifício desconta
  Vitalidade antes dos efeitos; Sangria, Marca, Provocar, Proteção, Vantagem, buff de Dano,
  `revelar vitalidade` (`out.revelacoes` e `_revelado`), Chamado 4/6 (só dispara com Entropia
  ≥ k), `ao_receber_dano` (Teatro de Facas) e `ao_derrubar` (Cofre sem Fundo) armam em
  `scene.gatilhos_armados`, e a cura condicional de Silêncio Cobrado só cura com Sangria no
  alvo (Vit 4 → 4 sem Sangria, 4 → 8 com). Eco de Segundo Ato e Bis de Cicatriz repete o dano
  pela metade. As reações `Mão Fechada`/`Pé de Pluma` caem em
  `conflict_orchestrator._resolve_reaction_effect` (`buff_esquiva` → condição `ac` +2 no
  reator), que `conflict_resolution.py:74` consome; o desvio `ativa` → `reacao` está correto,
  porque em `conflict_turn` o kind `buff_esquiva` não é nem ataque nem suporte. **Achados
  inertes: P1-1 e P1-2.**
- **Os −20 pp de `credencial_de_dor` (item 3): é bug da arena, não do motor nem da Carta.** Ver
  P1-3.
- **Orçamento e raridade (item 4): OK.** 20/10/4/2 em 36 fica a ±2 de cada faixa da R3
  (18/10,8/5,4/1,8). Somando Lotes 1 e 2, 36/23/9/4 em 72 contra o alvo 36/21,6/10,8/3,6: o
  P2-7 do Lote 1 foi compensado. O teste do lote passa `fx.budget_error is None` e
  `check_raridade` nas 36. Ressalva: o orçamento cobra por `escala` e `eco` que, nas Cartas do
  P1-1 e do P1-2, não fazem nada.
- **Arena reproduzível (item 5): OK.** Rodei `sim.py --lote …/sangromante_exposto.json
  --protocolo lote --out <scratchpad>`, e o JSON sai idêntico a
  `docs/spec335/sim-lote2-exposto.json`. Não repeti avaro e silencioso por falta de RAM (havia
  1,2 GB livres). Reproduzível, porém sem validade como medida de delta: ver P1-3.
- **Lint e nomes contra o pool inteiro (item 6): OK, com avisos.** Varri os 492 objetos com
  `id` e nome em `data/cards/**/*.json`, incluindo `inimigos/` da 332, `bestiario`, básicas,
  status e cena, com nome normalizado (sem acento e em minúsculas): nenhum nome das 36 colide
  e não há id duplicado. `scripts/cards/lint.py <lote>` não dá nenhum erro além de "id já
  existe" (esperado depois da promoção), mas aponta avisos de redundância e de voz (P2-4).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `data/cards/posturas/sangromante_avaro.json:89` (`san1_ava_juros_do_primeiro`) e `:354` (`san1_ava_execucao_da_divida`) | **A `escala` no efeito PRINCIPAL de dano é inerte.** O golpe com rolagem tira o dano de `conflict_turn._damage_from` (`services/conflict_turn.py:261-288`), que lê só `dano_base`/`categoria_arma` e nunca chama `fx.scaled_value`; a `escala` só vale em `card_effects._apply_on` (efeitos extras ou disparados). Medido: Juros do Primeiro causa 2 de dano com Entropia 2, 4 ou 20, e Execução da Dívida causa 8 com Entropia 4 ou 20. Mesmo assim o texto gerado promete "(+0,5 por Entropia, máx. +3/+4)" e `_orcamento` cobra `max × peso × mult.escala` (`services/card_effects.py:1636-1638`). Juros perde a identidade inteira ("a dívida que ele cria é que cresce no escuro"). | Do lado da Carta, que basta para este lote: passar o dano escalado para um efeito **extra** (`[{dano leve 2}, {dano valor 0, escala{…max 3}}]` ou parecido), que passa por `_apply_on` e escala de verdade, ou tirar a `escala` e rebalancear. Rodar de novo `fx.budget_error` e a arena. Prevenção: um lint em `card_lint` (ou um teste) que recuse `escala` no efeito principal de `dano`/`contra_ataque` enquanto o motor não a aplicar no golpe. A correção no motor (aplicar `scaled_value` em `_damage_from`) é da 330 e mexe no golden; não fazer neste lote. |
| P1-2 | P1 | `data/cards/posturas/sangromante_silencioso.json:260` (`san1_sil_arterial_fina`) | **O Eco é inerte numa Carta cujo efeito principal é só Sangria.** O Eco repete o principal pela metade (Sangria 2), mas `cm.apply_condition` funde condições de mesmo nome com `max(dot)`/`max(duration)` (`combat_mechanics.py:522-526`), e a Sangria 2 some dentro da Sangria 4 que a própria Carta acabou de aplicar. Medido: depois de outra Carta da Postura, o alvo fica com Sangria 4, igual a sem Eco. O orçamento cobra o Eco. | Trocar o Eco por algo que faça efeito (Ressoar não resolve, porque também cai no `max`; melhor um `dano` pequeno no principal com a Sangria como extra, ou subir a Sangria e tirar o Eco). Prevenção: um aviso de lint para `eco` com efeito principal de condição sem acúmulo (`sangria`/`rachadura`/`torpor`/`marca`/`taunt`). |
| P1-3 | P1 | `scripts/cards/sim.py:313` e `:370-372`; `docs/spec335/RELATORIO-arena-lote2.md:58,63` | **O braço "sem" da arena contém a própria Carta medida, então o `delta_pp` é ruído.** O lote já mora em `data/cards/posturas/`, e `simulate_protocolo_lote` só tira do catálogo as **irmãs** (`ids - {card["id"]}`). Por isso `full_deck(cls, lvl, sub)` do "sem" inclui a Carta. Medido em `credencial_de_dor`: os decks "sem" e "com" são o **mesmo multiconjunto**, com 2 cópias da Carta em cada, e só a ordem muda. Vitória "sem" (com a Carta) 0,625 contra "com" 0,425. Com o mesmo deck "com" e a mesma tag de semente "sem", dá 0,45, então só a ordem do deck move ~18 pp. Com o braço "sem" **verdadeiro** (Carta fora do catálogo), a vitória é 0,45 contra 0,425, ou seja, **−2,5 pp** (ruído). A causa registrada no relatório ("a arena não modela Sacrifício") é falsa: `pay_costs` roda dentro de `run_round` → `conflict_turn` (linha 486), e o Sacrifício desconta Vitalidade na arena. Consequência: nenhum `delta` dos Lotes 1 e 2 mede a Carta, e a bandeira `dominante` por delta não tem como disparar com sentido. A taxa de uso (bandeiras `em_branco`/`dominante` por uso) continua válida, porque vem só do braço "com". | (a) Neste lote: corrigir as linhas 58 e 63 do relatório com a causa real e retirar a frase sobre Sacrifício. Os ajustes de poder de Arterial Fina, Silêncio Cobrado e Credencial foram feitos para "mover o delta", que era ruído; registrar isso. (b) SPEC-336, dona do `sim.py`, antes da arena do Lote 3: no "sem", tirar a Carta medida do catálogo (`base.pop(cid)` ao montar o deck "sem"), usar a mesma tag de semente nos dois braços (pareado) e fixar a ordem do deck (por exemplo, ordenar o deck antes de `start_piles`). Teste: `Counter(sem)[cid] == 0`. Depois, rodar de novo os protocolos dos Lotes 1 e 2. O pouso do Lote 2 fica a critério do coordenador. Recomendo não pousar com o relatório dizendo "sem bandeira" como evidência de balanço sem essa ressalva. |
| P2-1 | P2 | `sangromante_avaro.json:200`, `sangromante_silencioso.json:69` | As reações `Mão Fechada`/`Pé de Pluma` vêm sem `gatilho`, o que equivale a `"sempre"` (`services/reactions.py:54`). Com a Carta escolhida, ela é gasta no 1º ataque do lado oposto, mesmo que o alvo seja o companheiro, e o +2 de Esquiva vai para o jogador, sem efeito útil. A legada `san_esquiva` usa `ao_ser_atacado`. | Acrescentar `"gatilho": "ao_ser_atacado"` às duas. |
| P2-2 | P2 | `sangromante_exposto.json:102` (`san1_exp_aplauso_de_ferro`) | `contra_ataque` numa `ativa` é só um golpe imediato de 3 (igual a `dano`), mas o texto gerado diz "Revida com 3 de dano" e a `descricao` fala em "Cada pancada recebida vira palmas". Promete um revide que não existe. | Ou trocar para `kind: dano` e reescrever a `descricao`, ou fazer dela uma `reacao` com `gatilho: ao_ser_atacado` (o que muda o papel; rodar orçamento e arena de novo). |
| P2-3 | P2 | `sangromante_exposto.json:196` (`gole_rubro`), `sangromante_avaro.json:105` (`poupar_ferida`) | A `descricao` promete mecânica que não existe: Gole Rubro fala em sangue "do inimigo" que volta (dreno), e o efeito é uma cura 2 incondicional; Poupar Ferida diz "Só quem já está quebrado… e ganha uma cicatriz nova", e o efeito é cura 4 sem condição e sem cicatriz. | Reescrever as duas `descricao` para o que a Carta faz, ou dar a Gole Rubro um `se: alvo_tem sangria` (com efeito incondicional junto, como no desvio declarado). |
| P2-4 | P2 | Lint `redundancia` | Pares de subclasses diferentes com mecânica idêntica ou quase: `livro_de_dividas` = `marca_de_unha` (Marca 2, custo 0, `cena`, comum); `mao_fechada` = `pe_de_pluma`; `gole_rubro` ≈ `poupar_ferida`; `sangue_na_areia` ≈ `veneno_vermelho`. Há ainda 4 avisos de "descrição sem termo de sabor de Valoria". Isso pesa contra a R6 (`test_card_variety`), que vai fechar depois. | Diferenciar ao menos um de cada par (custo, frequência, palavra-chave da subclasse). Opcional neste lote. |
| P2-5 | P2 | `sangromante_exposto.json:39` (`veia_a_mostra`) | Provocar vale só quando o inimigo tem outro alvo (`_taunt_target`: 50 % × multiplicador, só entre candidatos). Sozinho, a Carta paga Sacrifício 1 por nada, e o texto gerado ("ele precisa atacar você") promete mais do que o motor faz. O `valor` do `taunt` não é lido. Semântica pré-existente (legadas também têm). | Registrar a limitação no `CARTAS.md`/336 (o texto gerado do `taunt` precisa dizer "pode"); considerar dar à Carta um efeito útil sozinho. |
| P2-6 | P2 | spec §4.1 | O desvio declarado ("7 legadas `ativa`+`buff_esquiva` inertes") não está registrado na spec nem como follow-up. | Registrar na spec como achado, com destino (330 ou lote de reparo). |
| P2-7 | P2 | `sangromante_exposto.json` (`san1_exp_credencial_de_dor`) | O id diverge do nome ("Selo de Cicatriz"), e três nomes do Exposto giram em torno de "Cicatriz" (Cicatriz Aberta, Bis de Cicatriz, Selo de Cicatriz). | Cosmético. Opcional. |

## Correções aplicadas

Executor (Lote 2, commit `fix(cards): SPEC-335 Lote 2 review`): P1-1, P1-2, P1-3 (a)+(b: `sim.py` corrigido e arenas dos Lotes 1/2 refeitas), P2-1 a P2-7 aplicados; detalhes na §4.1 da spec. Correção ao P2-6: não há legadas `ativa`+`buff_esquiva` (as 7 são `reacao`).

## Pendências

- P1-1, P1-2, P1-3(a), P2-1 a P2-3, P2-6: executor da 335, nesta branch, antes do pouso do Lote 2.
- P1-3(b), a correção do `sim.py` (braço "sem" sem a Carta, sementes pareadas, ordem fixa) e a nova rodada dos protocolos dos Lotes 1 e 2: SPEC-336, com o coordenador, antes da arena do Lote 3.
- P1-1 prevenção no motor (`escala` no golpe): SPEC-330, follow-up; mexe no golden.
- P2-4, P2-5, P2-7: opcionais; P2-5 vai para a 336 (texto de `taunt`).
- Voz do Lote 2: `pendente-dono` (amostra de 7 ids), como no Lote 1.

## Comandos rodados

```text
scratchpad/cmp.py (main × HEAD, 4 arquivos legados, chaves por Carta) → 53 Cartas mudadas, só momento/momento_placeholder
scratchpad/play.py + play2.py (36 Cartas por ct.resolve_turn; Entropia 2/4/8/10/20; suporte em si; Eco; Silêncio com/sem Sangria) → P1-1, P1-2; demais conforme o texto
scratchpad/txt.py (fx.render_card_text das 36) → textos gerados conferidos
scratchpad/deck.py (full_deck "sem"/"com" no protocolo) → multiconjuntos idênticos, 2 cópias da Carta nos dois braços
scratchpad/fix.py (credencial_de_dor: sem verdadeiro / sem do sim / com / com com tag "sem") → 0,45 / 0,625 / 0,425 / 0,45
sim.py --lote data/cards/posturas/sangromante_exposto.json --protocolo lote --out <scratchpad> → JSON idêntico a docs/spec335/sim-lote2-exposto.json
scratchpad/names.py (492 Cartas nomeadas em data/cards/**, incluindo inimigos/) → 0 colisões de nome e de id
scripts/cards/lint.py data/cards/posturas/sangromante_{exposto,avaro,silencioso}.json → só "id já existe" (esperado) + avisos de redundância/voz
scripts/validate_content.py → 0 erros, 2 avisos
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -p no:warnings tests/test_card_acervo_reparo.py tests/test_card_effects_grammar.py tests/test_card_lint.py tests/test_card_sim.py tests/test_mecanica_orfa.py → 207 passed, exit 0 (sem -n, por RAM: 1,2–2,3 GB livres)
```

# Lotes 0–1 (histórico; revisão anterior, inalterada)

## Escopo

Branch `spec-335`. 1ª rodada: `main...bb8a8ce0` — Lote 0 (reparo R5 das 308 legadas), Lote 1
(36 Cartas do Arcanista, `data/cards/posturas/arcanista_cinzento_*.json`, `_ondas.yaml`),
`services/card_lint.py`, testes. Re-revisão: só o delta do commit `565b0d0b` (35 arquivos):
`scripts/cards/{promote,sim}.py`, `services/{card_lint,card_effects,content_validator}.py`,
`data/cards/_orcamento.json`, `_ondas.yaml`, Cartas do Lote 1, `momento_placeholder` nas legadas,
`scripts/gen_tiers_5_plus.py`, `docs/spec335/*`, `docs/guias/CARTAS.md`, testes
(`test_card_acervo_reparo`, `test_card_sim`, `test_mecanica_orfa`, `test_card_lint`,
`test_card_effects_grammar`, `test_conflito_autoria_cartas`). O que veio da SPEC-332 pelo
rebase ficou fora.

### Conferido de forma independente (vale para as duas rodadas)

- **Lote 0 continua sem mudança mecânica** depois das correções. Comparei `main` (`fda7b39a`)
  com HEAD carta a carta nos 9 arquivos legados, excluindo só
  `descricao/contrapartida/raridade/momento/momento_placeholder`: nenhuma diferença. Nenhuma
  fixture de golden ou snapshot mudou. A nova faixa `abissal` do `_orcamento.json` é idêntica
  à `epica` (`[-1, 32]` para 0–3 de Fôlego), e `fx.raridade` só a usa quando o `patamar` já
  dava `epica`. Logo o orçamento das legadas `lendario/mitico` não muda, e as `apice` seguem
  pela faixa `apice`.
- **Arena reproduzida byte a byte.** Rodei `sim.py --lote … --protocolo lote --out <scratchpad>`
  nas 3 subclasses: os 3 JSON saem **idênticos** aos de `docs/spec335/sim-lote1-*.json`, todos
  com exit 0 e 0 bandeiras.
- **O `--protocolo lote` só fixa parâmetros.** O diff de `sim.py` acrescenta
  `PROTOCOLO_LOTE = {categories: [padrao], per_cat: 4, seeds: 20}` e `simulate_protocolo_lote`,
  que chama `simulate_batch` sem mudança, uma Carta por vez, com as irmãs do lote fora do
  catálogo e no `level_req` da Carta. Limiares, fórmulas e bandeiras ficam intocados, e
  `test_protocolo_lote_e_preset_dos_parametros_existentes` fixa os 4 limiares.
- **Roda e voz:** nenhum Sacrifício nem provocar. Nomes com até 4 palavras, sem dígito na
  `descricao`, `descricao` com até 140 caracteres. Os `momento` do Arcanista são distintos,
  com similaridade máxima 0,54.

## Achados

### 1ª rodada (`bb8a8ce0`) e o que a re-revisão encontrou

| ID | Sev. | Problema (1ª rodada) | Situação em `565b0d0b` |
|---|---|---|---|
| P1-1 | P1 | `_ondas.yaml` gravava `revisor_voz: dono (…revisão posterior)` sem revisão; o guard do `promote.py` só recusava a string literal `pendente` (viola a R8). | **Resolvido.** `_ondas.yaml` agora tem `revisor_voz: null` e `voz_status: pendente-dono`. O `promote.py` exige um identificador real (regex `^[A-Za-z0-9][A-Za-z0-9_.-]{1,39}$` e lista negra com `pendente/posterior/amostra/depois/tbd/todo/null/none`); sem revisor, só passa com `--voz-pendente`, e as duas opções juntas são recusadas. O `validate_content` emite AVISO para a onda pendente. Os testes `test_promote_voz_pendente_so_com_bandeira_e_sem_texto_livre` e `test_validate_content_avisa_onda_com_voz_pendente` cobrem isso. Restos menores em P2-6. |
| P1-2 | P1 | A arena aprovava conforme os parâmetros (11, 2 ou 1 bandeiras), o relatório não estava versionado e o poder estava em efeitos não medidos. | **Resolvido.** Há um protocolo único, preset e versionado, com relatório, comando e limitações em `docs/spec335/`, reproduzido byte a byte (ver acima). O `promote.py` sem `--sim-report` usa o mesmo protocolo. A limitação de os efeitos secundários não pesarem na decisão do bot está declarada no relatório e no `CARTAS.md`. Resto em P2-5. |
| P1-3 | P1 | Havia 10 comuns com mais de 1 efeito (R3) e nenhum lint. | **Resolvido.** `card_lint.check_raridade` cobre comum (≤ 1 efeito e ≤ 1 palavra-chave), incomum (≤ 2), abissal (Exaurir mais custo) e `raridade` × `patamar`, e só se aplica a Cartas de onda. As 10 Cartas foram reduzidas a 1 efeito ou subidas para incomum (`arc1_cal_estilhaco` e `arc1_imp_gambiarra` foram para `avancado`, nível 4). A distribuição ficou 16/13/5/2; ver P2-7. |
| P1-4 | P1 | O Lote 0 estava marcado `[x]` com os `momento` das outras 4 Posturas duplicados. | **Resolvido.** O Lote 0 virou `[~] PARCIAL` na spec. As 255 Cartas levam `momento_placeholder: true`, e o teste `test_momento_distinto_por_postura_com_excecoes_que_so_encolhem` exige 0 duplicata e 0 par ≥ 0,60 nas Posturas fora da lista. Restos em P2-8. |
| P2-1 | P2 | Contagem fixa 359. | **Resolvido.** O legado fica fixo em 323 (sem `onda` e sem `inf_`), e as ondas entram como `⊆ ids`. Isso é robusto à SPEC-332. |
| P2-2 | P2 | Na `mecanica_orfa`, `vigilia`, `revelar` e `mover_alvo_zona` eram testados fora do caminho de Carta. | **Resolvido.** Os três passam por `_play_active` com a Carta real e o observável correto; `comprar` e `descartar` reaproveitam os testes de pilhas, que já são pelo caminho de Carta. |
| P2-3 | P2 | `gen_tiers_5_plus.py` sobrescrevia o reparo. | **Resolvido.** O gerador preserva `KEEP_FIELDS` por id e só sobrescreve com `--force`; o lint recusa a frase-modelo da `contrapartida`. |
| P2-4 | P2 | Havia dois vocabulários de raridade. | **Resolvido.** A faixa `abissal` existe, com o mesmo valor da `epica`, e o `_meta` do orçamento documenta isso. |

### Achados da re-revisão (todos P2, não bloqueiam)

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-5 | P2 | `docs/spec335/RELATORIO-arena-lote1.md:50` | A descrição dos ajustes não bate com o diff entre `7ab09380` e `565b0d0b`. Para `arc1_des_palma` o relatório diz "dano 3 → 2", mas o diff troca o 2º efeito (dano escalado por Entropia, até +2) pela palavra-chave **Eco**. Para `arc1_des_corrente` diz "Fôlego livre → …", mas o diff troca `descartar 1 + comprar 1` por `descartar 2 (escolha)`, sem mexer na frequência. A frase "não movi poder para efeitos que a arena não mede" é verdadeira em termos líquidos: em `des_dedos` o poder caiu de 1,1 para −0,6 e em `des_corrente` de 1,0 para −0,5. Já em `des_palma` o poder trocou um secundário por outro (escala → Eco, que o próprio relatório lista como não pesando no bot), passando de 1,0 para 1,5. Em `arc1_des_faisca`, reescrita pela R3, foi de 0,7 para 2,5 (`cena` → `livre` + Ressoar 1). Tudo continua dentro da faixa comum `[-2, 9]` e sem bandeira (delta +2,5 e +6,2 pp). | Corrigir o texto dos ajustes no relatório para o diff real e dizer explicitamente que `palma` e `faisca` ganharam palavra-chave (Eco, Ressoar) cujo único freio é o orçamento. Incluir as duas na próxima amostra de voz e de balanço do dono. |
| P2-6 | P2 | `tests/test_card_effects_grammar.py:485`; `tests/test_conflito_autoria_cartas.py:257`; `services/content_validator.py:889` | Os dois testes que exigiam `validate_cards() == []` agora filtram só erros, e com isso **qualquer** aviso novo de Cartas (de qualquer origem) passa calado. O afrouxamento é legítimo em intenção (o aviso de voz pendente é esperado), mas largo demais. Além disso, o validador trata `voz_status` ausente como `aprovada` e não reaplica `revisor_valido`, então uma entrada antiga com texto livre em `revisor_voz` passaria por aprovada. | Forma estrita: `fs = validate_cards(); assert [f for f in fs if f.severity == "error"] == []; assert {(f.severity, f.code) for f in fs if f.severity != "error"} <= {("warning", f"onda-{o['onda']}") for o in load_ondas() if o.get("voz_status") == "pendente-dono"}`, e cada aviso deve conter `"voz pendente"`. No validador, considerar pendente quando `voz_status != "aprovada"` **ou** `not promote.revisor_valido(revisor_voz)` (mover `revisor_valido` para `services/card_lint.py` e importar dos dois lados). Acrescentar o AVISO de voz pendente à checklist de release/staging como bloqueio do lote, porque as 36 Cartas já estão no catálogo. |
| P2-7 | P2 | `tests/test_card_acervo_reparo.py:79-84` | A distribuição 16/13/5/2 (44/36/14/6 %) se afasta da R3 (50/30/15/5 = 18/11/5,4/1,8 em 36). A diferença é de 2 Cartas entre comum e incomum, efeito de subir `estilhaco` e `gambiarra`. Aceitável para um lote, mas não há tolerância declarada. | Declarar a tolerância na spec (por exemplo, ±2 Cartas por faixa em cada lote, com o acumulado das 5 Posturas fechando em ±1 ponto percentual) e compensar nos Lotes 2–5. Opcional: um teste do acumulado quando R6 fechar. |
| P2-8 | P2 | `tests/test_card_acervo_reparo.py:106,112` | `MAX_PLACEHOLDERS = 255` com `<=` impede crescer, mas não obriga a encolher: se o Lote 2 reescrever 55 `momento` e ninguém baixar a constante, a folga de 55 pode ser reaproveitada. Nada impede uma Carta de onda nova de se marcar `momento_placeholder: true` numa Postura ainda isenta e escapar da R4. | Usar `== MAX_PLACEHOLDERS`, obrigando a atualizar a constante a cada lote. Acrescentar `assert not any(c.get("momento_placeholder") for c in pool if c.get("onda") is not None)` e, se possível, fazer o `check_schema` do lint recusar `momento_placeholder` em Carta de onda. |
| P2-9 | P2 | `services/card_lint.py:221-226` | `check_raridade` não tem teste unitário próprio: só é exercido pelo lint do Lote 1, em que tudo passa. | Testar diretamente: comum com 2 efeitos é recusada; incomum com 3 é recusada; abissal sem Exaurir ou sem custo é recusada; `raridade` incoerente com o `patamar` é recusada; Carta legada (sem `onda`) é ignorada. |
| P2-10 | P2 | `data/cards/posturas/arcanista_cinzento_*.json` | Cartas que mudaram de efeito continuam com `versao: 1`, contra a regra do `_meta` do orçamento ("mudar o poder = nova versão"). Aceitável **só** porque o Lote 1 nunca chegou à `main` nem a jogadores. | Nada agora. Registrar na spec que, a partir do pouso, qualquer ajuste de poder numa Carta do Lote 1 sobe a `versao`. |
| P2-11 | P2 | `scripts/cards/sim.py` (`PROTOCOLO_LOTE`) | O protocolo avalia cada Carta só no seu `level_req`; com o default antigo (níveis 1, 3 e 5) havia 11 bandeiras. Uma comum de nível 1 nunca é medida no nível 5, onde o deck é outro. O comentário diz "fixado pelo coordenador/SPEC-336", mas o registro dessa decisão está só no comentário e no `CARTAS.md`. | Registrar a decisão do protocolo na SPEC-336 (é dona da ferramenta) com data e autor. Follow-up 336: medir também em `level_req + 3` e criar a bandeira `fraca` para delta ≤ −10 pp (hoje `arc1_imp_gambiarra` está em −10,0). |

## Correções aplicadas

- `565b0d0b` — P1-1 (`--voz-pendente`, revisor real, AVISO no validador), P1-2 (protocolo de lote mais relatório e script versionados, 3 Cartas reescritas), P1-3 (`check_raridade`, 10 comuns), P1-4 (Lote 0 parcial, `momento_placeholder`, teste com exceções), P2-1 a P2-4.

## Pendências

- Voz do Lote 1: o dono revisa a amostra de 7 ids (mais `arc1_des_palma` e `arc1_des_faisca`, por P2-5) e o coordenador roda o registro com `revisor_voz: dono` / `voz_status: aprovada`. Até lá, o AVISO no `validate_content` deve bloquear a release.
- P2-5 a P2-9: executor da 335, no próximo lote (Lote 2) ou antes do pouso, a critério do coordenador.
- P2-11 e a bandeira `fraca`: SPEC-336 (coordenador).
- `arc_imp_maquina` (nome com 5 palavras, pré-existente): lote do Arcanista ou da 336.

## Comandos rodados

```text
# 1ª rodada (bb8a8ce0)
pytest -n 2 (12 arquivos de cartas + log_event_registry + no_silent_except) → 330 passed, exit 0
validate_content → 0 erros; sim.py default → 11 `dominante`; variantes por level_req → 2 / 1
# re-revisão (565b0d0b)
scratchpad/eqcheck.py (main fda7b39a × HEAD, campos mecânicos das 308 legadas) → 0 diferenças
sim.py --lote …/arcanista_cinzento_{calibrado,descoberto,improvisador}.json --protocolo lote --out <scratchpad> → exit 0 ×3; JSON idêntico a docs/spec335/sim-lote1-*.json
scratchpad/power.py (power_score 7ab09380 × 565b0d0b das Cartas alteradas) → todas dentro da faixa; palma 1,0→1,5, faisca 0,7→2,5, dedos 1,1→−0,6, corrente 1,0→−0,5
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_card_acervo_reparo.py tests/test_card_draft.py tests/test_card_effects_grammar.py tests/test_card_effects_piles.py tests/test_card_effects_review_spec330.py tests/test_card_lint.py tests/test_card_piles.py tests/test_card_sim.py tests/test_cards_prepare_api.py tests/test_mecanica_orfa.py tests/test_conflito_autoria_cartas.py tests/test_log_event_registry.py tests/test_no_silent_except.py tests/test_eval_governance.py tests/test_handoff_names.py tests/test_spec_index.py → 372 passed, exit 0
bash scripts/dev/py.sh scripts/validate_content.py → 0 erros, 1 aviso (onda-1 voz pendente do dono)
```
