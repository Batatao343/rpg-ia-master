# SPEC-335 — revisão sol (review)

> **Veredito Lote 3 (Devoto, `8874f777`):** `APPROVED_WITH_FOLLOWUPS` (0 P0/P1; 4 P2)
> **Veredito Lote 2 (Sangromante):** `APPROVED_WITH_FOLLOWUPS` na re-revisão de `8364eaa7` (a 1ª rodada, em `b3f5e743`, deu `CHANGES_REQUIRED` com 3 P1 e 7 P2)
> **Veredito Lotes 0–1 (`565b0d0b`):** `APPROVED_WITH_FOLLOWUPS` (histórico abaixo, inalterado)
> **Revisor:** Sol (Claude Opus 5.5, spec-reviewer) · **Data:** 2026-10-27
>
> Nota de nome: o coordenador pediu `handoffs/SPEC-335-sol-review-lote2.md`, mas esse nome
> reprova `scripts/check_handoff_names.py` / `tests/test_handoff_names.py` (o padrão é
> `SPEC-NNN[-papel]-tipo.md`, sem sufixo). Por isso a revisão do Lote 2 entrou neste arquivo.

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
