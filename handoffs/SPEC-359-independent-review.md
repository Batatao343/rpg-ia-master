# SPEC-359 — revisão de unicidade (independent-review)

> **Veredito (rodada 2, 2026-11-01):** `APPROVED_WITH_FOLLOWUPS`. C-1 (Estaqueiro Afogado) e C-2 (Banhado do Centro) foram corrigidos, e P2-5 também. As 22 fichas estão aprovadas. Seguem como follow-up, sem bloquear, P2-1, P2-2, P2-3 e P2-6. P2-4 caiu junto com C-1.
> Veredito da rodada 1: `CHANGES_REQUIRED` (C-1, C-2).
> **Revisor:** Opus (spec-reviewer, revisor de unicidade independente; o autor é `opus`, outro agente) · **Data:** 2026-10-28
> **Commit revisado:** `d780660a` (branch `spec-359`) · rodadas 1 e 2 (a 2 só confere as correções). Por pedido do dono, só cortes graves.

## Escopo

Revisei as 22 fichas não-retro de `data/bestiario/fichas/pantano_melancolia.yaml`: 21 `nova` e o slot
`enemy_zumbi_blindado`, reinventado como Curtido da Turfeira. Usei o checklist da SPEC-349 §3.9 e a
R6 da SPEC-359, que proíbe dizer em texto público quem afundou os afogados e que eles eram druidas.

**Contra o que comparei:**
- as 8 fichas `retro` do Pântano;
- os docs `data/codex/monsters/` do Pântano (tag `nova_arcadia`);
- as 27 fichas de `data/bestiario/fichas/nova_arcadia.yaml`;
- os cortes do autor em `docs/spec349/conceitos-pantano_melancolia.md`;
- o segredo de Saelwen (`lore_nova/npcs.txt:1161`) e o tom público da Cripta (`lore_nova/locations.txt:119`).

**Fora do escopo:** números, Cartas, arena e gate determinístico (o `lint.py` já está verde, não rodei de novo).

## Parecer por criatura

| # | Criatura | Veredito | Motivo (1 linha) |
|---|---|---|---|
| 1 | Estaqueiro Afogado | **CHANGES** (C-1) | O cordão de medir, as estacas e o "hábito" são ferramentas e roupa exclusivas dos druidas, e ele aparece "marcando a borda de uma coisa que cresce" (ofício do Ciclo, ver Castor, Borda e `rumors.txt:73`). Somado a "não se afogou sozinho", isso diz que eram druidas. |
| 2 | Romeiro de Âmbar | APPROVED | O vício no chá do Ciclo e o âmbar com insetos lhe dão identidade própria. O efeito de prender o pé lembra o Velório de Sal (P2-1). |
| 3 | Banhado do Centro | **CHANGES** (C-2) | É reskin do Caído do Cadinho (NA, `nova_arcadia.yaml:1547`): mesmo homem largo e curvado, mesmas placas negras nos ombros, peito e costas sobre músculo vermelho, mesma origem (Ferrugem e sangue de Malagor) e o mesmo eixo de luta, crosta contra carne viva. |
| 4 | Castor de Estacas | APPROVED | Ele cria a represa que parte a cena, e a água fica acima do nível, que é física torta. Não é monstro de manual. |
| 5 | Patinador de Óleo | APPROVED | A película de óleo e Éter que o sustenta é do Pântano. O bate-e-volta é único na região. |
| 6 | Cágado de Geada | APPROVED | O frio de Éter que "bebe o calor" tira o bicho do casco-de-ruínas da Tartaruga-Ruína. A mordida trava ataque e passagem. |
| 7 | Fundeiro da Poça | APPROVED | Peixe-arqueiro cujo jato vira pedra na água grossa de Éter. O cuspe ácido do Sapo-Boi é outro corpo e outro efeito. |
| 8 | Tritão de Sobra | APPROVED | Os membros desencontrados vêm do ciclo acelerado. A defesa "fogo fecha a ferida" é a da hidra (P2-2). |
| 9 | Musaranho de Dente Vermelho | APPROVED | A fome de Éter que desfaz a comida é física e Valoria. O drenador que se gasta quando não morde é único. |
| 10 | Borda que Anda | APPROVED | Barranco com crista de estacas, separado da Raiz-Mãe pelo próprio texto. O "afunda e perde o movimento" repete a Porca da Queda (P2-3). |
| 11 | Podador do Ciclo | APPROVED | Ossos dos antebraços viram podões pelo ofício da amputação. A Poda (tira o Ferimento e leva a Carta) é inédita. |
| 12 | Jardineiro de Tumores | APPROVED | É o Renegado que carrega o canteiro no corpo. Usa o Tumor-do-Pântano como arma em vez de copiá-lo. |
| 13 | Mula de Lágrimas | APPROVED | Contrabandista de barriga translúcida, com a carga que racha quando ele morre. Corpo e gancho são próprios. |
| 14 | Casaco de Sanguessugas | APPROVED | Ele veste as Sanguessugas-Braço para não sentir o Pântano. Retro e Verme-Mestre ficam como fonte, não como cópia. |
| 15 | Turno Vencido | APPROVED | A cabeça vira um pote de argila ritual e ele protege os outros. Druida público da Borda, sem tocar a Cripta. |
| 16 | Regaço da Margem (Solvhara) | APPROVED | Massa de turfa morna com colo e quatro braços. A anatomia não repete o Velório de Sal, e embalar e roubar a ação é próprio. |
| 17 | Cordão de Medida (Skarath) | APPROVED | É a corda-guia traidora de tendões e punhos, e devolve a jogada. A silhueta colide com o cordão do Estaqueiro, o que se resolve em C-1 (P2-4). |
| 18 | Mãos no Rosto (Veleth) | APPROVED | Corpo físico de braços a mais sobre o mesmo rosto, que luta com os dois braços de baixo. O efeito sobre a Virtude é de cria, aceitável. |
| 19 | Cisne de Pátina (Morvath) | APPROVED | Cisne de seda de estandarte com bico que envelhece a defesa. Distinto da Garça-Pálida. |
| 20 | Arraia de Lodo (Thessavar) | APPROVED | Disco pardo que turva o presságio. A nuvem do Fole de Costela tira a visão e não esconde a intenção dos inimigos. |
| 21 | Fardo de Espólio (Daruun) | APPROVED | Escudo de torre sobre oito braços de afogado e pedágio de Fôlego. Corpo e efeito sem par. |
| 22 | Curtido da Turfeira (slot `enemy_zumbi_blindado`) | APPROVED | O corpo de turfeira sem ossos substitui bem o zumbi genérico, e o gancho dos sete corpos é público (`rumors.txt:73`). Ver P2-5 sobre a corda no pescoço. |

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção mínima sugerida |
|---|---|---|---|---|
| C-1 | P1 | `data/bestiario/fichas/pantano_melancolia.yaml:74,76,80,109,111,113-114,122` (Estaqueiro Afogado; e o Codex e o doc de arte gerados a partir dele) | Vaza o segredo da Cripta, contra a R6. O "cordão de medir", o par de estacas e o "hábito", junto com "como quem marca a borda de uma coisa que cresce", identificam os afogados como druidas do Ciclo. "Nenhum deles tinha o rosto de quem se afogou sozinho", na sequência, fecha a leitura. O cordão entre duas estacas também é a silhueta do Cordão de Medida (P2-4). | Tirar o cordão e o ofício de medir, e trocar o hábito por roupa neutra. Anatomia: "Um cordão de medir está atado ao pulso e afundou na carne até o osso" → "Uma tira de couro atada ao pulso afundou na carne até o osso". "O hábito que veste" → "A roupa que veste". Comportamento: "finca duas estacas e estica o cordão entre elas, como quem marca a borda de uma coisa que cresce" → "finca estacas em fila diante dos outros, como quem fecha uma passagem". Mecânica e contra-jogo: "estica o cordão entre duas estacas" → "finca uma fileira de estacas"; "cortar o cordão no nó do pulso" → "arrancar as estacas da fileira". Lore: remover "tem um cordão de medir atado ao pulso e" e trocar a última frase por "Os que voltaram da Cripta dizem que eles esperam como quem foi posto ali." (no tom de `locations.txt:119`). Em `aparencia` e `arte.visual`: "hábito" → "roupa longa", "cordão de medir/cânhamo" → "tira de couro". Depois, regerar o Codex e o doc de arte. |
| C-2 | P1 | `data/bestiario/fichas/pantano_melancolia.yaml:236-260,276-278` (Banhado do Centro) × `data/bestiario/fichas/nova_arcadia.yaml:1547-1585` (Caído do Cadinho) | Reskin do Caído do Cadinho. Os dois são velhos largos e curvados, vítimas do sangue de Malagor ou da Ferrugem, com placas negras nos ombros, peito e costas sobre músculo vermelho exposto. Os dois lutam trocando crosta por carne viva (o Caído fecha a crosta e a parte; o Banhado a perde e ganha força). Também fica colado ao Romeiro, outra vítima de Malagor ou da Ferrugem com placas sobre carne viva na mesma onda. | Manter o conceito (veterano banhado, vivo, que guarda a lama da sua linha) e trocar a forma como a ferrugem aparece no corpo e na luta. Proposta: a ferrugem negra não forma placas e escorre dele como suor grosso. Quem o fere de lâmina vê a ferrugem subir pela arma. Mecânica: "Cada golpe de lâmina que o acerta leva a ferrugem negra para a arma: o próximo ataque dessa arma tira menos, até ser limpa no descanso". Contra-jogo: pancada, arma de reserva ou mantê-lo longe. Silhueta sem "lascas pretas". O autor reescreve anatomia, silhueta, mecânica, contra-jogo, `aparencia`, `como_se_luta` e `arte` com a mesma direção. Também serve outra mudança que tire o par placas-sobre-músculo e o eixo crosta contra carne viva. |
| P2-1 | P2 | `pantano_melancolia.yaml` Romeiro (mecânica) × `nova_arcadia.yaml:1819` (Velório de Sal) | Os dois prendem com crosta: o alvo não troca de lugar até quebrá-la. | Opcional: o âmbar prende a mão em vez do pé, por exemplo "a próxima Carta jogada com a mão presa custa +1 Fôlego até quebrar". Ou manter, já que o Velório também bloqueia cura e drena. |
| P2-2 | P2 | Tritão de Sobra (mecânica e contra-jogo) | "Cada corte brota, fogo cauteriza" é o contra-jogo da hidra do manual, embora o corpo não seja de hidra. | Opcional: trocar "só fogo" por algo de Valoria que pare o ciclo, por exemplo "ervas do Ciclo ou sal na ferida, ou um golpe que esmaga em vez de cortar". |
| P2-3 | P2 | Borda que Anda (mecânica) × `nova_arcadia.yaml:598` (Porca da Queda) | O efeito final é o mesmo: afunda e perde o movimento. A Porca já foi o motivo do corte do conceito 26. | Opcional: manter o encolhimento da cena e trocar o efeito na faixa, por exemplo "quem estiver nela fica preso até gastar a ação para sair e não pode jogar Reação". |
| P2-4 | P2 | Cordão de Medida (silhueta, nome) | A silhueta "corda esticada entre duas estacas" duplica a do Estaqueiro. "Medida" também ecoa o cordão de medir dele. | C-1 já resolve, porque o Estaqueiro perde o cordão. Se C-1 for aplicado de outro jeito, renomear para "Corda de Punhos". |
| P2-5 | P2 | Curtido da Turfeira (anatomia, `arte`) | A "corda fina no pescoço" veio do Homem de Tollund e sugere execução. Isso contradiz "deitou por vontade própria" e abre uma leitura de assassinato que a lore pública não tem. | Opcional: remover a corda, ou trocar por "um cordão de amuleto". |
| P2-6 | P2 | Curtido, Tritão, Romeiro, Turno Vencido (contra-jogo) | Quatro contra-jogos são "pancada, não lâmina". | Opcional, ao fazer C-2: variar pelo menos um. |

## Correções aplicadas

Nenhuma. O revisor só escreve este arquivo; o autor e o coordenador aplicam C-1 e C-2 e regeram o
Codex e o doc de arte com `scripts/bestiario/gerar_docs.py`.

## Pendências

- C-1 e C-2 antes de mudar `revisao: aprovada` no Estaqueiro e no Banhado. Não pedem nova rodada:
  o coordenador confere o texto contra a correção sugerida.
- Os P2 ficam a critério do autor e do coordenador, na SPEC-359 ou na Etapa 5.
- As outras 20 fichas podem receber `revisao: aprovada` e `revisor_unicidade: opus-spec-reviewer`.

## Comandos rodados

```text
git diff main...HEAD --stat → 73 arquivos (fichas, Codex, docs da 349/359)
leitura (sed/grep) de pantano_melancolia.yaml, nova_arcadia.yaml, codex/monsters do Pântano, secrets/npcs/locations/rumors → sem Python nem pytest (máquina com pouca RAM)
```

## Rodada 2 (2026-11-01, só as correções)

Conferi o `git diff` (ainda sem commit) de `data/bestiario/fichas/pantano_melancolia.yaml`, de
`data/codex/monsters/{mon_estaqueiro_afogado,mon_banhado_do_centro,enemy_zumbi_blindado}.md`, de
`data/bestiary.json` (só a `appearance` do Curtido) e de `docs/arte/bestiario-349/pantano_melancolia.md`.
Não rodei Python nem pytest.

- **C-1 resolvido.** O Estaqueiro não tem mais cordão de medir, hábito, capuz nem a frase "a borda de uma coisa que cresce", nem "se afogou sozinho". Agora usa uma tira de couro no pulso e roupa neutra sem insígnia, e o `evitar` proíbe "manto de monge". A mecânica é uma fileira de estacas (`cri_estaqueiro_afogado_fileira_de_estacas`), e o contra-jogo é arrancar as estacas ou derrubá-lo. A lore fecha com "esperam como quem foi posto ali". A R12 também perdeu o "medir" e o "Ciclo". A silhueta não colide mais com a do Cordão de Medida, então P2-4 está fechado.
- **C-2 resolvido.** O Banhado não tem mais placas, lascas, músculo exposto nem o eixo crosta contra carne viva. Agora é suor negro de ferrugem com veias pretas. A mecânica (`cri_banhado_do_centro_suor_de_ferrugem`) enferruja a arma que o fere até o descanso, e o contra-jogo é ferir com o que não enferruja ou trocar de arma. O `evitar` proíbe placas, crosta e escamas. Ele se afasta do Caído do Cadinho e do Romeiro, e o contra-jogo dele não repete "pancada, não lâmina", o que alivia em parte o P2-6.
- **P2-5 resolvido.** A corda no pescoço do Curtido virou cordão de amuleto na ficha, no Codex, no `bestiary.json` e no doc de arte, e saiu da R12.
- Os IDs de carta antigos (`…_cordao_esticado`, `…_crosta_arrancada`) não aparecem fora da ficha. As 22 fichas têm `revisao: aprovada`.
- Observação sem achado: a silhueta do Banhado ("poço de piche") convive com o `evitar` "criatura de piche". A imagem é de comparação e não pede mudança. O druida com cordão no doc de arte da Borda que Anda é da Borda, que é pública, e não vaza a Cripta.
