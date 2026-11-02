# SPEC-349 (onda Aethelgard) — revisão de unicidade (§3.9), rodada 1

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (spec-reviewer, revisor de unicidade) · **Data:** 2026-11-01 · **Commit revisado:** `9783888f`
> Nome do arquivo: pedido pelo coordenador. `scripts/check_handoff_names.py` **não** aceita
> `-aethelgard-uniqueness-`; ao reservar a spec-filha, renomear para
> `handoffs/SPEC-NNN-independent-review.md` (como a 359 fez no Pântano).

## Escopo

`data/bestiario/fichas/aethelgard.yaml` (21 `nova` + 4 `reinventada` + 5 retro) e
`docs/spec349/conceitos-aethelgard.md`. Comparado com: a própria região, as 27 de
`nova_arcadia.yaml`, as 22 de `pantano_melancolia.yaml`, os 31 docs `data/codex/monsters/` que
citam Aethelgard e a lore (locations:237-265, creatures:1266-1410, npcs:64-70/317-323/419-427/1830-1853,
races:449-466, timeline:26-32/110-128/278/342, secrets:23-36/138-144/267-274/414-421).
Fora: números (Etapa 5), lint (já verde) e pytest (não rodados, por instrução).

Resumo: o tabuleiro de eixos está bom e as âncoras de lore são fortes. O problema são os
**pares que o lint não pega**. Há dois moldes de Cria já usados (Skarath e Dorrhen), um corpo que
repete o Fole de Costela e sete assinaturas mecânicas iguais às de NA ou do Pântano, inclusive no
`contra_jogo`. Só o slot do Golem chega perto de segredo, e por inferência (P1).

## Achados

| ID | Sev. | Criatura (arquivo:linha) | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | Boia Traidora (aethelgard.yaml:1849) | **Corte.** É o molde do Cordão de Medida (Pântano, Skarath): um apoio de confiança (corda-guia ou boia) feito de **cordão de tendão com mãos/dedos** que prende quem se apoia. Mesmo demônio, gatilho e material, mesmo papel (`emboscador`). | Cortar. Substituto: cria de **Maalrek**, o único dos 13 sem cria em nenhuma onda (timeline:28, "espelho de quem sofria, mais nítido quanto mais intenso"). Sugestão: **Novelo de Anzóis**: linhas, anzóis e redes em que mergulhadores morreram presos devagar, enroladas em pele num novelo do tamanho de um homem. Fica mais cortante quanto mais o alvo sofre (dano cresce com os Ferimentos do alvo). Contra-jogo: mandar à frente o mais inteiro e fechar Ferimentos antes. Se preferir manter Skarath, o gatilho não pode ser "apoio/guia". |
| P1-2 | P1 | Escada de Braços (:1925) | Mesmo molde da Cavadeira de Unhas (NA, Dorrhen): **membros de quem procurava a saída, indo para uma saída**. Também cansa o motivo "montagem de braços" (Fila de Grilhões, Fardo de Espólio, Mãos no Rosto e, aqui, a Encomenda). | Manter Dorrhen, a subida para a luz e a mecânica (o peso encarece o Fôlego), mas **tirar a carne humana**. Por exemplo: o resíduo toma as cracas e os mexilhões que vieram com o sal, numa coluna viva que sobe qualquer parede atrás de uma abertura, cai e sobe de novo, e se incrusta em quem está subindo. |
| P1-3 | P1 | Peito de Sino (:1235) | Reskin do Fole de Costela (NA): tórax alargado que infla e sopra. O texto diz "pulmões incham como foles". O `contra_jogo` é quase literal: "golpear o fole quando infla; esvaziado, não sopra" × "golpear pelas rachas enquanto ele enche; vazio, precisa encher". | Trocar o sopro pelo que só ele tem, o ar de meia hora: **agarra e mergulha junto**. Submerso, o alvo perde Fôlego a cada rodada e ele não. Contra-jogo: lutar onde dá pé ou em terra; abrir as rachas o faz perder o ar. Tirar "foles" do texto. Com a Boia cortada, o "puxar ao fundo" fica livre. |
| P1-4 | P1 | Encomenda Costurada, slot `enemy_golem_carne` (:532) | (a) Ainda lê como o golem de carne genérico: cadáveres costurados com braços e cabeças a mais. (b) "Carne branca e cerosa" de afogado guardião repete o Estaqueiro Afogado (Pântano: cera de cadáver, `cera_sebo`). (c) Lore e gancho dizem que Vane "paga também por eles" porque **não apodrecem**. Isso o aproxima de secrets:138-144 (Vane recebe corpos humanos como matéria-prima e tenta reativar tecido morto). O público só diz "partes de corpos de **monstros**" (npcs:70). | Reancorar: Vane compra parte de monstro, como é público. Os **saqueadores** costuram três Afogados num "bicho" só para vender **como monstro, por peso** (uma fraude de embarque). O que os põe de pé é o Lago, como em todo Afogado, nunca algo de Vane. Tirar "partes que não apodrecem" e "estudos". Corpo: tirar a cera. A leitura dominante passa a ser o **corpo dobrado para caber no caixote**: ângulos retos, membros dobrados em juntas erradas, ripas pregadas como talas. Ele se desdobra para lutar e foge do Frankenstein. Trocar `material` e rodar de novo o `--vagas`. |
| P2-1 | P2 | Avesso de Oghma (:216) | (a) A explosão ao morrer em quem está colado já existe no Lençol de Chaminé (NA) e na Mula de Lágrimas (Pântano), com o mesmo contra-jogo "matar de longe". (b) Costelas abertas com os pulmões à vista é a imagem do Fole de Costela. | Manter a inversão (de quatro, barriga para cima). A gaiola **fecha** sobre o braço ou a perna de quem está na frente; ele morre preso ali, e o osso trava o membro (o alvo perde a Reação) até alguém abrir a gaiola. Contra-jogo: não deixá-lo chegar, ou quebrar as costelas antes. Arte: costelas curvas para cima como dedos, **sem pulmões à mostra**. |
| P2-2 | P2 | Lesma de Penacho (:848) | Roubar uma Carta da mão é a assinatura da Gralha de Crematório (NA), também `lacaio`/`saqueador`/`covarde_oportunista`. | Ficar com o que o nudibrânquio dá: o **primeiro efeito de Éter/magia** que a atinge não a fere; vai para as pontas do penacho e é descarregado em quem a tocar corpo a corpo. Contra-jogo: aço ou arremesso, não feitiço. Ajustar papel e eixos no `--vagas`. |
| P2-3 | P2 | Ouriço de Lajedo (:926) | "Cravado que piora até gastar a ação para arrancar" é o Casaco de Sanguessugas (Pântano). O contra-jogo é quase o mesmo texto ("mesmo custando/perdendo a ação"). Ainda ecoa o Dentado na própria região. | Os espinhos que **erram** cravam na laje e crescem ali, e o chão vira espinheiro: cada movimento por ele fere. Contra-jogo: não pisar onde ele já atirou; contornar por tábua ou água funda. O Dentado fica com o "arrancar". |
| P2-4 | P2 | Aspirante de Coral (:1463) | "Endurece a cada rodada até travar; espere" é o Caído do Cadinho (NA). Além disso, `arquetipo: covarde_oportunista` não combina com "ataca com raiva de afogado". | O coral engrossa **sobre o lugar do último golpe**: golpes repetidos do mesmo atacante rendem menos a cada vez, e revezar quem bate quebra o padrão. Fora da água ele sufoca. Rever o arquétipo. |
| P2-5 | P2 | Fervido da Corrente (:293) | Retaliar golpe corpo a corpo é a assinatura do Pajem de Obsidiana (NA), com o mesmo contra-jogo ("de longe"). | Trocar por uma **aura que cresce**: cada Ferimento que ele leva vaza mais cinza, e quem começa a rodada colado nele perde Vitalidade, mais a cada Ferimento. Contra-jogo: poucos golpes grandes, ou tirá-lo da água. |
| P2-6 | P2 | Pernalta do Conselho (:1694) × Véu Faminto (:1772) | Par mecânico **dentro da região**: "o alvo perde a defesa e os reforços" × "os reforços e a defesa do alvo passam para o Véu". Os dois ecoam o Cisne de Pátina (a defesa perde grau). A ficha da Pernalta também não registra a inspiração "pernaltas" que o doc de conceitos cita. | Pernalta **rebaixa**: afunda o mais inteiro, que fica de joelhos na água e só age depois de todos na rodada seguinte; ela sempre troca para quem ficou mais inteiro. Registrar a inspiração (R12). Véu: tirar "defesa" e ficar só com os **reforços**, que ficam visíveis dentro do sino e voltam quando os véus são cortados. |
| P2-7 | P2 | Aranha de Bolha (:768) | "Não recua nem troca de lugar até cortar/quebrar" é o Romeiro de Âmbar (Pântano). | A assinatura vira o **puxão para dentro do sino**: o preso sai da fila e luta sozinho com ela, longe dos aliados, até cortar o fio. O contra-jogo atual (lutar no ar, dentro do sino) já serve. |

### Veredito por criatura

| Criatura | Veredito | Nota |
|---|---|---|
| Doador Inacabado | APPROVED | Âncora forte (timeline:126); "inacabado" é a frase única. |
| Dentado de Eras | APPROVED | Fica no limite com o corte nº 11 (Ouvinte de Bocas). Passa porque é físico: dentes que viram placas e racham a armadura. Não reforçar o "murmura em línguas" (é da Voz-de-Thessrak). |
| Avesso de Oghma | CHANGES | P2-1 |
| Fervido da Corrente | CHANGES | P2-5 (a origem, Corrente de creatures:1298, está ótima) |
| Iniciado Refratado (slot esqueleto mago) | APPROVED | Não lê como esqueleto: é gente seca com prismas. A luz como munição é única. |
| Nadador Transparente (slot fantasma) | APPROVED | Follow-up: uma linha dizendo que **não** é um dos Afogados de patrulha (Thessrak não fala por ele), para não virar variante do retro. |
| Encomenda Costurada (slot golem) | CHANGES | P1-4 |
| Cação de Lastro (chefe) | APPROVED | A troca de fase por flutuação é única. Convive bem com a Tartaruga-Ruína e o Caranguejo-Relíquia, porque aqui a pedra é lastro, não casco. |
| Biguá de Vidro | APPROVED | |
| Aranha de Bolha | CHANGES | P2-7 |
| Lesma de Penacho | CHANGES | P2-2 |
| Ouriço de Lajedo | CHANGES | P2-3 |
| Cupinzeiro de Vidro | APPROVED | Material e papel iguais aos do Vigia de Caco (retro), mas o corpo (ninho séssil) e a mecânica (parede para qualquer aliado) são outros. |
| Camarão Faxineiro | APPROVED | |
| Ariranha de Arcada (slot quimera) | APPROVED | Não lê como quimera. Follow-up: `habitat` só tem `aethelgard`, mas o texto a põe nas galerias das Correntes; incluir `ae_ruinas_submersas`. |
| Peito de Sino | CHANGES | P1-3 |
| Mão de Oghma | APPROVED | É o inverso do Sorvedouro do Código (passa Entropia, não suga). A "transferência do custo" é pública (timeline:118). |
| Alambique de Carne | APPROVED | |
| Aspirante de Coral | CHANGES | P2-4 |
| Comedor de Alga | APPROVED | Deriva do efeito público da Alga (creatures:1369); a marca em quem conjura é única. |
| Lambedor de Abóbada | APPROVED | Não vaza secrets:414-421. Nota tonal, opcional: "lambe mais depressa" puxa contra o Morvath que "não destrói rápido". Não inverter para "se ele morre, o teto cai": isso sim ecoaria o segredo. |
| Pernalta do Conselho | CHANGES | P2-6 |
| Véu Faminto | CHANGES | P2-6 (leve) |
| Boia Traidora | **CORTE** | P1-1 → Maalrek |
| Escada de Braços | CHANGES | P1-2 |

**Segredos:** nada entrega secrets:267-274 (o aprendiz aparece só como quem apagou a contenção)
nem :414-421. O único risco é o P1-4 (Vane). **Retro:** nenhuma nova é variante direta dos 5,
salvo a nota do Nadador.

## Correções aplicadas

(nenhuma; o revisor não edita fichas)

## Pendências

- Rodada 2: conferir P1-1…P2-7 e rodar de novo `lint.py --vagas` depois das trocas de eixo
  (Encomenda, Lesma, Boia/Maalrek).
- Renomear este arquivo quando a spec-filha for reservada (lint de nomes).
- `conceitos-aethelgard.md` §3: registrar o corte da Boia (C-R) e o substituto.

## Comandos rodados

```text
git log -1 → 9783888f
grep/sed nas fichas de NA e do Pântano, nos docs do Codex e na lore (trechos) → pares acima
(lint e pytest não rodados, por instrução)
```

## Rodada 2 (commit `77ea54e9`)

> **Veredito da rodada 2:** `CHANGES_REQUIRED` — **um único item** (R2-1); todo o resto `APPROVED`.

**Errata da rodada 1.** O P1-1 dizia que Maalrek era "o único dos 13 sem cria em nenhuma onda".
Está errado: Nova Arcádia já tem a **Roda de Mandíbulas** (Maalrek, nova_arcadia.yaml:1015). O
substituto que sugeri levou o Novelo para a mecânica dela.

| ID | Sev. | Criatura | Problema | Correção |
|---|---|---|---|---|
| R2-1 | P1 | Novelo de Anzóis (`cri_novelo_de_anzois_farpa_na_ferida`) | Mesmo demônio e mesma assinatura da Roda de Mandíbulas (NA): "cada Ferimento que já havia na fila dobra a mordida", contra-jogo "não deixar Ferimentos abertos" × "o dano cresce com cada Ferimento do alvo", contra-jogo "mandar à frente o mais inteiro". O corpo (rede, linha, anzóis, pele) é novo e fica. | Trocar só a mecânica pelo "espelho" de Maalrek que o texto já sugere ("toma a forma torta de quem prendeu por último"). **Refém:** prende um alvo nas linhas e toma a forma dele; enquanto o alvo estiver preso, metade de todo dano que o grupo causa no Novelo vai para o preso. Contra-jogo: soltar o preso antes de bater (cortar as linhas, ou fogo na linha, que desenrola), ou bater pouco e certeiro. Não há par em NA nem no Pântano: a Fila de Grilhões absorve golpes *pelos aliados*, não fere o refém. Ajustar `comportamento`/`lore`/`como_se_luta`/`telegrafo`/composição de arte (o companheiro inteiro à frente vira alguém cortando a linha do preso). |

**APPROVED (rodada 2):**

- **Subida de Cracas** (Dorrhen). Saiu do molde de membros humanos da Cavadeira. Crosta de cracas *no
  alvo* (peso que encarece o Fôlego) é outra ideia, diferente do coral *em si* do Aspirante. Lê
  bem em arte.
- **Peito de Sino**: "agarra e afunda junto" é só dele. O Bagre de Varal (NA) também afoga, mas
  limita Cartas e não drena Fôlego; o par fica aceitável.
- **Encomenda Costurada**: o segredo de Vane saiu (compra "partes de bicho, a peso", em linha com
  npcs:70; quem costura são os saqueadores e o Lago a põe de pé). A cera saiu, e o corpo dobrado
  em ângulo de caixa já não lê como golem de carne.
- **Avesso de Oghma**: a gaiola que fecha e tira a Reação é física e única; os pulmões à vista
  saíram.
- **Lesma de Penacho**: não rouba mais Carta. Nota sem bloqueio: "o que a atinge volta" encosta no
  Vira-Costas (NA) e no Cordão de Medida (Pântano), mas aqui é só magia, absorvida e descarregada
  no toque. Aceito.
- **Ouriço de Lajedo**: o espinheiro na laje é terreno, não "cravado até arrancar". É único.
- **Aspirante de Coral**: crosta no lugar do último golpe, revezar quem bate, arquétipo `bruto`.
  Ok, e já não ecoa o Caído do Cadinho.
- **Fervido da Corrente**: uma aura que cresce com os Ferimentos dele não é a retaliação do Pajem.
- **Pernalta do Conselho**: "age por último" não tem par nas três regiões, e a inspiração foi
  registrada. **Véu Faminto**: ficou só com os reforços, e o par interno se desfez.
- **Aranha de Bolha**: puxar para o sino e isolar é só dela, e "furar o sino" é um bom contra-jogo.
- Notas aplicadas: Nadador fora das patrulhas dos Afogados; Ariranha com `ae_ruinas_submersas`.

Segredos (rodada 2): nada novo entrega secrets:23-36, :138-144, :267-274 ou :414-421.

Fechamento: com o R2-1 aplicado como descrito, a onda fica **APPROVED** sem uma 3ª rodada. A
troca é só de mecânica, e o coordenador pode conferir.
