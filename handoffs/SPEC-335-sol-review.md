# SPEC-335 — revisão sol (review)

> **Veredito Lote 2 (Sangromante, `b3f5e743`):** `CHANGES_REQUIRED` (3 P1, 7 P2)
> **Veredito Lotes 0–1 (`565b0d0b`):** `APPROVED_WITH_FOLLOWUPS` (histórico abaixo, inalterado)
> **Revisor:** Sol (Claude Opus 5.5, spec-reviewer) · **Data:** 2026-10-27
>
> Nota de nome: o coordenador pediu `handoffs/SPEC-335-sol-review-lote2.md`, mas esse nome
> reprova `scripts/check_handoff_names.py` / `tests/test_handoff_names.py` (o padrão é
> `SPEC-NNN[-papel]-tipo.md`, sem sufixo). Por isso a revisão do Lote 2 entrou neste arquivo.

# Lote 2 — Sangromante (`main...b3f5e743`)

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

(nenhuma ainda; o executor preenche por commit)

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
