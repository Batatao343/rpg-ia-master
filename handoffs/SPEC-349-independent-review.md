# SPEC-349 — revisão de unicidade (independent-review)

> **Veredito:** `CHANGES_REQUIRED`. Falta só a troca de uma frase no Relicário (texto exato em C-1).
> Feita essa troca, o veredito passa a `APPROVED_WITH_FOLLOWUPS` sem nova rodada de revisão.
> Brasa Profunda e Polvo dos Destroços ficam para decisão do coordenador.
> **Revisor:** Opus (spec-reviewer, revisor de unicidade independente; o autor é `fable`) · **Data:** 2026-10-28
> **Commits revisados:** rodada 1 `49406083` · rodada 2 `8d37329c` · rodada 3 `70838d74` (branch `spec-349`)

## Escopo

As 27 fichas não-retro de `data/bestiario/fichas/nova_arcadia.yaml`: 21 `nova`, 3 `reinventada` e
3 `adotada`. Revisei pelo checklist §3.9, junto com os docs Codex gerados e
`docs/arte/bestiario-349/nova_arcadia.md`.

| Rodada | Commit | O que foi revisto |
|---|---|---|
| 1 | `49406083` | As 29 fichas iniciais |
| 2 | `8d37329c` | Os cortes (Costurador, Vela, Abraço), o Quebrado novo e 9 reescritas |
| 3 | `70838d74` | As 5 CHANGES de conteúdo e os P2 do Relicário, do Pavio e da Escritura |

**Contra o que comparei:**
- as 12 fichas `retro`;
- os docs `data/codex/monsters/*.md` com tag `nova_arcadia`, lidos só os parecidos;
- as 27 fichas entre si.

As refs seguem a lore da SPEC-348 (D-A).

**Fora do escopo:**
- mecânica numérica;
- Cartas (`data/cards/criaturas/` ainda não existe);
- arena;
- a parte técnica do gate, que é da revisão Sol.

**Legenda dos itens:**
- 1 = não é reskin;
- 2 = identidade em uma frase;
- 3 = é de Valoria;
- 4 = física e luta;
- 5 = sem vazamento.

`ok` = passa; `X` = falha; `~` = passa com nota (P2).

## Decisões

### D-A. Refs pela lore da SPEC-348: ACEITO, com condição

Conferi 14 refs em `C:\Users\guilh\AppData\Local\Temp\claude\rpg-spec-348\lore_nova\` (commit
`042732c6`) e todas batem. Exemplos:

| Ref | O que tem na lore da 348 |
|---|---|
| `npcs.txt:214` | Natureza de Maalrek |
| `npcs.txt:244` | Solvhara |
| `timeline:398` | a Praga em Nova Arcádia |
| `timeline:386` | a Praga dos Ossos |
| `locations.txt:372` | Oubliette → Montanhas |
| `daily_life.txt:320` | Sino Mudo |
| `factions.txt:155-161` | Os Quebrados |

**Condição:**
- a 349 pousa depois da 348;
- no `wt.sh sync` as refs são conferidas de novo;
- follow-up no U10: a linha citada tem de conter o `detalhe` ou um termo-âncora.

### D-B. Brasa Profunda e Polvo dos Destroços: decisão do coordenador

A objeção da rodada 2 continua de pé e não foi reavaliada, como o executor pediu.

**As duas:**
- são lore de outras regiões: `creatures.txt:310`, Reino Subterrâneo, e `creatures.txt:1436-1444`, costa;
- chegam por ganchos que a lore não tem;
- colidem com ondas futuras no U1 global.

**Cada uma:**
- a Brasa é, no corpo, o elemental de fogo de manual;
- o Polvo não tem física quebrada, então falha a família `besta_entropia`.

**Alternativa:** reinventar os slots ou adotar `mon_prisioneiro_do_nivel_dez` (`creatures.txt:802`).

## Tabela final (27 fichas)

| id | nome | status | 1 | 2 | 3 | 4 | 5 | veredito | motivo (1 linha) |
|---|---|---|---|---|---|---|---|---|---|
| mon_arame_vivo | Arame Vivo | nova | ok | ok | ok | ok | ok | APPROVED | Praga de Ferro no último estágio; a única criatura que drena por contato com arame |
| mon_fole_de_costela | Fole de Costela | nova | ok | ok | ok | ok | ok | APPROVED | Operário-fole com corpo próprio; não é a Tosse-Viva |
| mon_rosario_de_vertebras | Rosário de Vértebras | nova | ok | ok | ok | ok | ok | APPROVED | A única criatura de medula/ossos; a farpa é única |
| mon_fila_de_grilhoes | Fila de Grilhões | nova | ok | ok | ok | ok | ok | APPROVED | O único guardião que intercepta pelos aliados, agora que o Velório saiu desse espaço |
| mon_relicario_de_osso | Relicário da Catedral | nova | ok | ok | X | ok | ok | CHANGES (1 frase) | Contradiz a lore pública: "não entregam os seus mortos ao fogo dos Corvos", mas a lore diz que "a Guilda dos Corvos entra regularmente para recolher os mortos" (`locations.txt`, Catedral). Ver C-1 |
| mon_sangrado_da_clinica | Sangrado da Clínica | nova | ok | ok | ok | ok | ~ | APPROVED | Sangria pela lanceta, sem Frankenstein, sem "pele comprada" e sem Vane. P2-e: tirar "procuram no pescoço dos outros", que puxa para vampiro |
| mon_lencol_de_chamine | Lençol de Chaminé | nova | ok | ok | ok | ok | ok | APPROVED | A única criatura que explode ao cair |
| mon_traca_do_sino_mudo | Traça do Sino Mudo | nova | ok | ok | ok | ok | ok | APPROVED | Come o som; o Sino Mudo é lore da 348 |
| mon_gralha_de_crematorio | Gralha de Crematório | nova | ok | ok | ok | ok | ok | APPROVED | A única ladra de Carta preparada |
| mon_porca_da_queda | Porca da Queda | nova | ok | ok | ok | ok | ok | APPROVED | A única criatura "pesada do jeito errado", amarrada à Queda |
| mon_centopeia_da_torre_invertida | Centopeia da Torre Invertida | nova | ok | ok | ok | ok | ok | APPROVED | A única que "cai para cima" e volta pelo lado não defendido |
| mon_sorvedouro_do_codigo | Sorvedouro do Código | nova | ok | ok | ok | ok | ok | APPROVED | É o preço do Inquisidor; drena Entropia |
| mon_pavio_da_lista | Pavio da Lista | nova | ok | ok | ok | ok | ok | APPROVED | Gaiola-berço nas costas de um carregador; a dor é o combustível. O "rodas" saiu |
| mon_enxerto_da_fornalha | Enxerto da Fornalha | nova | ~ | ok | ok | ok | ok | APPROVED | A lâmina caça o metal mais grosso e se fere. O Sangue-de-Aço está em `related_entities` e o texto copiado saiu. P2-f: convive no papel `quebra_defesa` com o Portão |
| mon_quebrado_de_vitrine | Quebrado de Vitrine | nova | ok | ok | ok | ok | ok | APPROVED | Elfo de exibição sentado, com veios de vidro nas rachaduras (lore da 348), que canta e dá Fôlego. Não é mais o Pajem |
| mon_vira_costas_da_praca | Vira-Costas da Praça | nova | ok | ok | ok | ok | ok | APPROVED | Cria de Fehk; a única criatura "de costas" |
| mon_roda_de_mandibulas | Roda de Mandíbulas | nova | ok | ok | ok | ok | ok | APPROVED | Chefe único (Maalrek, Fosso dos Cães) |
| mon_cavadeira_de_unhas | Cavadeira de Unhas | nova | ok | ok | ok | ok | ok | APPROVED | O Desespero que cava; sai por baixo |
| mon_convidado_de_cera | Convidado de Cera | nova | ok | ok | ok | ok | ok | APPROVED | Tranca a Carta mais cara (contra-jogo: jogue barato) |
| mon_escritura_rastejante | Escritura Rastejante | nova | ok | ok | ok | ok | ok | APPROVED | Taxa de Fôlego por cláusula; o contra-jogo agora é oposto ao do Convidado |
| mon_portao_que_morde | Portão que Morde | nova | ok | ok | ok | ok | ok | APPROVED | Só quem passa pelo vão perde a defesa pelo resto do combate |
| enemy_sentinela_ferro | Pajem de Obsidiana | reinventada | ok | ok | ok | ok | ok | APPROVED | Criado-parede do Palácio, guarda que devolve cortes |
| enemy_gargula_ferro | Rã de Lótus | reinventada | ok | ok | ok | ok | ok | APPROVED | Sem cuspe: coaxa antes do golpe e protege o aliado. Não é mais o Sapo-Boi-Ácido |
| enemy_golem_lixo | Velório de Sal | reinventada | ~ | ok | ok | ok | ok | APPROVED | Não intercepta mais; o sal conserva (sem cura, sem mover). P2-g sobre Fôlego e papel |
| enemy_horror_esgoto | Coisa do Esgoto | adotada | ok | ok | ok | ok | ok | APPROVED | Adoção correta (`creatures.txt:798`) |
| enemy_elemental_fogo_poluido | Brasa Profunda | adotada | ~ | ok | X | ~ | ok | decisão do coordenador | Ver D-B |
| enemy_polvo_esgoto | Polvo dos Destroços | adotada | ~ | ~ | X | ok | ok | decisão do coordenador | Ver D-B |

**Contagem:** 24 APPROVED · 1 CHANGES (1 frase) · 2 para decisão do coordenador. Total: 27.

**Cotas (lint: 39 fichas, 0 erro):**

| Cota | Contagem |
|---|---|
| novas | 21 |
| corpo_reescrito | 6 |
| besta_entropia | 5 |
| humanoide_preco | 4 |
| demonio_encarnado | 6 |

## Cortes e trocas recomendadas

Não restam cortes nem trocas. Os cortes da rodada 1 (Costurador, Vela, Abraço) e as reescritas das
rodadas 2 e 3 resolveram todos os pares, exceto Brasa e Polvo (D-B).

## Correções de texto

| ID | Sev. | Arquivo:trecho | Problema | Correção |
|---|---|---|---|---|
| C-1 | P1 | `data/codex/monsters/mon_relicario_de_osso.md` e ficha (`anatomia.texto`, `gancho`) | "Os leprosos e os rejeitados… não entregam os seus mortos ao fogo dos Corvos: dão à água" contradiz o canon público: os Corvos entram regularmente para recolher os mortos da Catedral. Também aproxima o tema "mortos que escapam do crematório", que é vizinho do segredo Corvos↔Vane | Trocar por: **"Os Corvos recolhem os mortos da Catedral, mas não os que caem na nave: a água chega antes."** Ajustar o gancho da mesma forma. O revisor pré-aprova este texto, sem nova rodada |
| P2-e | P2 | ficha `mon_sangrado_da_clinica` `anatomia.texto`: "procuram no pescoço dos outros o que não tem mais" | Homem pálido, sem sangue, que olha o pescoço alheio puxa para vampiro, que está no léxico de proibidos | "procuram nos outros o que não tem mais" |
| P2-f | P2 | Enxerto × Portão | Os dois quebram defesa de metal. Dá para aceitar: o papel é o mesmo, mas o Enxerto escolhe o alvo mais blindado e o efeito é temporário, enquanto o Portão só pega quem passa pelo vão e o efeito é permanente | Manter os telegrafos distintos na Etapa 5 |
| P2-g | P2 | ficha `enemy_golem_lixo` `mecanica_assinatura` | O "perde Fôlego a cada rodada" encosta no Arame Vivo, que drena Fôlego por contato. O papel `guarda_protetor` sem intercepto fica sem tradução mecânica | Ficar só com "sem cura + sem mover" como identidade. Se sobrar orçamento, dar um efeito sobre Ferimentos em vez de Fôlego. Sol confere o papel |
| P2-h | P2 | `mon_relicario_de_osso.md` e `enemy_golem_lixo.md`: "os Corvos entram de passo leve" | A mesma frase aparece nos dois docs | Tirar de um deles. Com C-1, sai do Relicário |
| rod. 1–2 | P2 | P2-2 (suborno do Sorvedouro), P2-7 (dentes do Portão), P2-8 (silhueta da Porca), P2-9/P2-d (rosto liso: Velório, Pajem, Convidado) | — | Opcionais |

**Vazamento.** O grep de vane, daruun, magda, testamento, caixa e pacto não achou nada nos docs novos.
Nenhuma frase da `LEAK_PHRASES` da 348 aparece. Vane não aparece mais em nenhuma ficha, doc ou arte.

## Correções aplicadas

| Rodada | Commit | O que mudou |
|---|---|---|
| 2 | `8d37329c` | Cortes: Costurador, Vela e Abraço. Nova: Quebrado. Reescritas: Relicário, Pavio, Escritura, Fila, Arame, Rã e Velório |
| 3 | `70838d74` | Remendado virou Sangrado da Clínica. Velório sem intercepto. Enxerto racha a peça mais blindada, sem texto copiado e com `mon_sangue_de_aco`. Rã vira suporte, sem cuspe. Quebrado sentado, com veios nas rachaduras. P2 do Relicário (cor, lepra), do Pavio e da Escritura |

## Pendências

- O executor aplica o texto de C-1 no Relicário: ficha, Codex e, se houver menção, o doc de arte. Com
  isso as 25 fichas aprovadas podem ir para `revisao: aprovada`. Hoje todas estão `pendente`.
- O coordenador decide Brasa Profunda e Polvo dos Destroços (D-B).
- Follow-ups técnicos (Sol/Terra):
  - U10: a linha citada na ref contém o `detalhe` (D-A), conferido de novo no `wt.sh sync`.
  - Um possível U14: similaridade entre as frases de `mecanica_assinatura` e `contra_jogo`.
  - Conferir o papel `guarda_protetor` do Velório (P2-g).

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest tests/test_spec349_bestiary_lint.py -q -p no:warnings -p no:cacheprovider → 20 passed (rodadas 1, 2 e 3)
bash scripts/dev/py.sh scripts/bestiario/lint.py --regiao nova_arcadia --sem-revisao → r3: 39 fichas · 0 erro · 10 avisos (U3 entre retros)
sed -n '<linha>p' rpg-spec-348/lore_nova/<arquivo> → 14 refs batem (D-A); trecho da Catedral confirma a contradição de C-1
leitura das fichas e dos Codex gerados das 8 fichas tocadas na rodada 3; grep "passo leve" → 2 docs (P2-h)
grep -i vane|daruun|magda|testamento|caixa|pacto nos docs novos → 0 vazamento
```

## Rodada 4 (28/10) — slots refeitos: Caído do Cadinho e Bagre de Varal

Revisor de unicidade independente (Opus, `spec-reviewer`; o autor das fichas é `opus`, outro agente).
Commit revisado: `439811f7`. Escopo: só as 2 fichas novas, comparadas com as 25 não-retro, as 12
retro e os docs `monsters/` com tag `nova_arcadia` parecidos (Enguia-da-Lama, Peixe-Cego-das-
Profundezas, Coisa-do-Esgoto, Sangue-de-Aço, Fole de Costela, Lençol de Chaminé). Refs conferidas na
lore da 348: `locations.txt:61`, `:75`, `:96`, `timeline_completa.txt:396`, `:398`, `creatures.txt:800`.
As 6 batem.

### `enemy_elemental_fogo_poluido` — Caído do Cadinho: **CHANGES**

| # | Item | Veredito | Motivo |
|---|---|---|---|
| 1 | Não é reskin | CHANGES | O corpo junta o Fole de Costela (operário de fundição, escória preta, curvado, braços longos, Anel de Ferro, mesma ref `locations.txt:61`) com a paleta do Lençol de Chaminé (casca preta com brasa laranja por dentro, no mesmo anel) |
| 2 | Identidade em uma frase | APPROVED | "O que esfria até travar e parte a própria crosta para voltar" é só dele. Nenhuma outra ficha tem relógio próprio de endurecer |
| 3 | É de Valoria | CHANGES | A origem é forte: Ferrugem do Sangue + queda na panela, que a lore tem (`locations.txt:61`, `timeline:396-398`). Mas a imagem de placas pretas rachadas com luz vermelha nas juntas é o golem de magma de manual, o mesmo problema da Brasa (D-B) por outro caminho. O `evitar` da arte não segura, porque o `visual` descreve justamente isso |
| 4 | Física e luta | APPROVED | Bruto lento que endurece; contra-jogo legível (recuar, ou bater na janela de carne viva) |
| 5 | Sem vazamento | APPROVED | Ferrugem do Sangue e Aço de Sangue são canon público. Malagor e o dragão não aparecem |

**Correção (o revisor pré-aprova este texto, sem nova rodada).** Tirar a incandescência e os braços
longos. O calor fica no vapor e na carne crua, na linha do Lycan (placas sobre músculo exposto), e
não na luz:

- `anatomia.texto`: trocar "e entre elas o músculo continua vermelho de brasa, sem pele, sem nunca
  esfriar de todo. Os braços ficaram compridos e pesados, com os dois punhos fundidos num bloco só."
  por **"e entre elas o músculo fica à mostra, sem pele, vermelho-escuro e molhado, fumegando como
  carne tirada do caldeirão; não brilha, ferve. Os dois braços engrossaram e terminam num bloco só,
  os punhos fundidos um no outro, que ele levanta junto como um malho."**
- `silhueta`: **"Um homem largo e curvado sob telhas pretas rachadas, fumegando pelas juntas, com os
  dois braços acabando num malho só."**
- `lore`: "com o músculo aceso por baixo" → **"com o músculo cru, fervendo por baixo"**.
- `aparencia`: "músculo vermelho de brasa à mostra entre elas; braços longos com os punhos fundidos
  num bloco" → **"músculo vermelho-escuro, sem pele e fumegante à mostra entre elas; os dois braços
  terminam num bloco só, os punhos fundidos como um malho"**.
- `arte.visual`: "músculo vermelho-alaranjado incandescente e úmido, sem pele. Braços longos demais,
  os dois punhos fundidos num bloco de metal." → **"músculo vermelho-escuro, cru e molhado, sem pele,
  soltando vapor, sem luz própria. Os dois braços grossos terminam num único bloco de gusa, os punhos
  fundidos."**
- `arte.composicao`: "as placas das costas já cinzentas de frio e as da frente ainda acesas" →
  **"as placas das costas já cinzentas e secas, as da frente ainda fumegando"**.
- `arte.evitar`: acrescentar **"Rachaduras que brilham, magma, golem de pedra."**
- `telegrafo` (P2): "finca os punhos no próprio peito" → **"finca o bloco dos punhos no próprio
  peito"**, para não contradizer os punhos fundidos.
- Regenerar o Codex (`gerar_docs`) e a entrada do doc de arte.

Com isso, o Fole fica com o peito-fole e o tiro, o Lençol com a brasa presa, e o Caído com a crosta
que fecha. Família, material e anel continuam iguais aos do Fole. Pela silhueta e pela mecânica dá
para aceitar.

**P2, opcional:** o `gancho` usa "o lote sai leve", que é o nome do conceito 54, cortado por
encostar no Aço de Sangue. Aqui a frase funciona, porque é o contrário do Aço de Sangue (o metal não
fica com o corpo). Pode ficar.

### `enemy_polvo_esgoto` — Bagre de Varal: **APPROVED**

| # | Item | Veredito | Motivo |
|---|---|---|---|
| 1 | Não é reskin | APPROVED | Contra Enguia-da-Lama e Peixe-Cego: o bolsão de água no ar e a escala de homem tiram de "peixe cego do pântano". Contra o Rosário (serpentiforme, nada, Anel de Lama): a silhueta e a percepção são outras |
| 2 | Identidade em uma frase | APPROVED | "Peixe sem pele que nada pelo ar entre os varais e afoga de pé" não cabe em mais ninguém. O limite de 1 Carta por rodada é um eixo que nenhuma outra ficha usa. Arame drena Fôlego, Fila intercepta, Traça bloqueia o tipo, Convidado tranca uma Carta, Escritura dobra o custo |
| 3 | É de Valoria | APPROVED | Água do Pântano, onde "os rios perderam direção" (`locations.txt:96`), pelos esgotos que descem para ele (`creatures.txt:800`), nas ruas-canal da chuva (`:75`). É física quebrada, que a D-B cobrava. As placas de osso sobre o músculo seguem o Lycan, e o bagre de couraça é real |
| 4 | Física e luta | APPROVED | Emboscador de cima, diferente da Cavadeira, que vem de baixo. O contra-jogo "rasgar a água, não o peixe" é bom e legível |
| 5 | Sem vazamento | APPROVED | Nada de segredo. O "lava" que o grep acha é o verbo, não a rocha |

**P2, opcional:** acrescentar `lore_nova/timeline_completa.txt:380` ("Objetos flutuam") às `refs`,
para ancorar a água que não cai no fenômeno do Éter e não só no Pântano.

### Comandos (rodada 4)

```text
bash scripts/dev/py.sh scripts/bestiario/lint.py --regiao nova_arcadia --sem-revisao → 39 fichas · 0 erro · 10 avisos (os mesmos U3/U4 entre retros da r3)
sed -n '<N>p' rpg-spec-348/lore_nova/{locations,timeline_completa,creatures}.txt → 6 refs batem
grep -iE "vane|daruun|magda|testamento|caixa|pacto|malagor|dragão|lava|magma|polvo|tentác" nos 2 Codex → só "lava" (verbo)
```

### Rodada 4: correções aplicadas (executor, 28/10)

- Caído do Cadinho: o texto pré-aprovado entrou em `anatomia.texto`, `silhueta`, `lore`, `aparencia`, `arte` (visual, composição, evitar) e `telegrafo`. Na `aparencia`, saiu "grossas" para caber em 300 chars. O Codex e o doc de arte foram regenerados.
- Bagre de Varal: P2 aplicado (`timeline_completa.txt:380` nas `refs`).
- As duas fichas estão `revisao: aprovada`.



---

# Revisão da região: aethelgard (arquivo original handoffs/SPEC-349-astra-review.md)

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


---

# Revisão da região: costa_negra (arquivo original handoffs/SPEC-349-astra-independent-review.md)

# SPEC-349 · Costa Negra — revisão de unicidade (independent-review)

> **Veredito final (rodada 2, `d4c58b93`):** `APPROVED_WITH_FOLLOWUPS`. 22 `APPROVED`, nenhum CORTE.
> Ficam duas correções de uma linha, que não pedem nova rodada (R2-1 e R2-2), e um P2 de arte (R2-3).
> **Rodada 1 (`0bfcefa1`):** `CHANGES_REQUIRED`, com **9 `APPROVED` e 13 `CHANGES`**. A contagem "10/12" que
> constava antes estava errada: Acendedor e Rancor (só texto) também eram CHANGES, e o Forrado era APPROVED.
> **Revisor:** Opus (spec-reviewer, revisor de unicidade independente; o autor é `opus`, outro agente) · **Data:** 2026-11-01
> **Commits revisados:** rodada 1 `0bfcefa1` · rodada 2 `d4c58b93` (branch `bst-costa_negra`)

## Escopo

As 22 fichas `nova` de `data/bestiario/fichas/costa_negra.yaml` e o doc de conceitos
`docs/spec349/conceitos-costa_negra.md`. Revisei pelo checklist §3.9.

**Contra o que comparei:**
- as 7 `retro` da Costa;
- os 44 docs `data/codex/monsters/` com a tag `costa_negra`, lidos só os parecidos (Coração-Que-Bate-Ainda,
  Canto-do-Trono, O Que Se Vestiu de Leviatã, Enguia-do-Cais, Caranguejeiro, Caranguejo-Rei-de-Carcaça,
  Coral-de-Osso, O Que Come nas Praias, Náufragos, Tripulação-Amaldiçoada, Polvo-dos-Destroços);
- `lore_nova/creatures.txt:1490-1600`, `races.txt:282-290`, `npcs.txt` (Lyss, Dorrhen, Maalrek, Veth, Vhrak),
  `items.txt:1331`, `locations.txt:308-343` e `:467`;
- `nova_arcadia.yaml` e `pantano_melancolia.yaml`, por nome, silhueta e frase da mecânica de assinatura.

**Fora do escopo:** números, Cartas, arena e a parte técnica do gate (revisão Sol).

**Lint:** `lint.py --regiao costa_negra --sem-revisao` → 29 fichas, 0 erro, 0 aviso.

**Legenda do checklist:** 1 = não é reskin · 2 = identidade em uma frase · 3 = é de Valoria ·
4 = física e luta · 5 = sem vazamento.

## Parecer por criatura

| # | Criatura | 1 | 2 | 3 | 4 | 5 | Veredito | Motivo (e correção mínima, se CHANGES) |
|---|---|---|---|---|---|---|---|---|
| 1 | Escama Revirada | ✗ | ✓ | ✓ | ✓ | ✓ | **CHANGES** | A mecânica (`:88-91`, "quem o acerta corpo a corpo leva de volta as escamas") é a do Pajem de Obsidiana (NA, "quando ferido, as placas se soltam e cortam quem está perto"). Também repete o "devolve ao atacante" do Rancor, na mesma região. **Correção:** as escamas não voltam no atacante: caem na água em volta e o raso vira chão de lascas, que corta quem se mover ali na rodada seguinte. Ele amolece a cada chuva, como já está. Contra-jogo: tirá-lo da água rasa ou bater de pancada larga. |
| 2 | Ferida de Coral | ✗ | ✗ | ✓ | ✓ | ✓ | **CHANGES** | Repete o Jardineiro de Tumores (Pântano): o Jardineiro "planta um esporo no Ferimento que abre" e "quem chega perto ganha um corte, e no corte, uma semente"; aqui é "deixa uma muda de coral no Ferimento". Até a imagem do jardineiro se repete (`:161` "como quem rega uma planta", `:190` "como quem planta"). **Correção:** a muda **trava o membro** em vez de marcar e crescer em dano. A cada rodada sem arrancar, o coral fecha uma junta do alvo: primeiro ele perde a Reação, depois a Carta de arma daquele braço. Tirar "rega/planta" de `comportamento` e `lore`. |
| 3 | Compassado do Trono | ✓ | ✓ | ✗ | ✓ | ✓ | **CHANGES** | O cânone (Canto-do-Trono, `creatures.txt:1532`) diz que o Trono respira em ciclos de **seis horas**. A ficha alterna batida e pausa **a cada rodada**, "no ritmo do Trono" (`:248-249`, telegrafo `:262` "o Trono vai inspirar"). O ritmo fica incoerente. A silhueta "parado, de peito aberto" também esbarra no Sorvedouro do Código (NA, "legionário de peito aberto… parado"). **Correção:** o Canto deixou o coração dele lento, e o coração bate sozinho a cada N rodadas: "o ritmo é o do coração que o Trono lhe deixou". Telegrafo: "o coração do {nome} incha: vai bater". Em `arte.evitar`, acrescentar "não é o Sorvedouro do Código: sem luz no peito, só o coração e as costelas em porta". |
| 4 | Forrado de Leviatã | ✓ | ✓ | ✓ | ✓ | ✓ | APPROVED | É a referência dos Lycans: placas de osso enraizadas sobre músculo exposto. Não é o Carrapato de Osso (miúdo, cava, veste fragmentos) nem O Que Se Vestiu de Leviatã (anima um esqueleto inteiro); segue o cânone da Tripulação-Amaldiçoada. O "placa que cresce a cada golpe segurado" separa da Fila de Grilhões. Ajuste de texto, sem bloquear: `:330` e `:340` dizem "o mais duro de Valoria"; o cânone diz "o mais resistente para construção" (`locations.txt:336`). |
| 5 | Hóspede do Estômago (chefe) | ✓ | ✓ | ✗ | ✓ | ✓ | **CHANGES** | Não é reskin do Coração-Que-Bate-Ainda: o Hóspede anda, tem braços de Osshari e engole. Mas, como está, cria um **segundo** órgão vivo no Trono ("estômago que ainda trabalhava", `:386`), e o Codex público diz que o Coração "pode ser o último órgão vivo" e que "tenta regenerar um corpo". **Correção (só lore):** o estômago foi **refeito** pelo Coração, com carniça, na tentativa de voltar a ter corpo, e fechou-se sobre o arpoador. Isso entra em `anatomia.texto`, `gancho` e `lore`, sem nova mecânica. Para ficar com o engolir sem disputa, ver Ventre (18) e Esfolado (13). |
| 6 | Barata das Costelas | ✓ | ✓ | ✓ | ✓ | ✓ | APPROVED | Bola de isópode que desce a encosta e fica de barriga para cima. A Roda de Mandíbulas (NA) também rola, mas é outro corpo e outra mecânica. É legível em arte. |
| 7 | Estrela de Alavanca | ✓ | ✓ | ✓ | ✓ | ✓ | APPROVED | Abre o escudo como mexilhão, ao longo de várias rodadas; o contra-jogo é largar o escudo. Os quebra-defesa NA/Pântano (Enxerto, Portão, Cisne) fazem outra coisa. Braços de vértebra são de Valoria. |
| 8 | Andarilho de Cracas | ✓ | ✓ | ✓ | ✓ | ✓ | **CHANGES** | O corpo é ótimo (lobo-marinho cego guiado pela colônia). A mecânica (`:643-646`, "crosta na armadura, cada camada custa Fôlego para se mexer, só sai raspada") repete o Velório de Sal (NA, "cobre de sal… não troca de lugar, perde Fôlego a cada rodada em que não a quebra"). **Correção:** usar a Sacculina que a própria ficha cita. Na 3ª camada de larva, a colônia **pega** o alvo, e na rodada seguinte ele se move para onde o Andarilho quiser. Raspar antes da 3ª camada zera a contagem. |
| 9 | Touro de Banha | ✓ | ✓ | ✓ | ✓ | ✓ | APPROVED | Elefante-marinho de banha, de pele rachada e nariz que virou aríete: físico e legível. Fica com o "ruge e varre a linha" (o Remo precisa sair desse espaço, ver 17). |
| 10 | Saltador de Poça | ✓ | ✓ | ✓ | ✓ | ✓ | APPROVED | O morde-e-volta lembra o Patinador de Óleo (Pântano), mas o contra-jogo é outro: entrar na poça ou secá-la, em vez de atirar de longe. O corpo (olhos em haste de osso) é único. P2 opcional: dar uma função aos olhos em haste. |
| 11 | Bruxa de Carcaça | ✓ | ✓ | ✓ | ✓ | ✓ | APPROVED | Não é a Enguia-do-Cais (que morde pés nas docas de Brekmar): é um peixe-bruxa de dentro da carne podre, com muco. O Bagre de Varal (NA) também sufoca, mas limita Cartas; aqui o muco custa Fôlego até ser limpo, e a âncora da carcaça é própria. |
| 12 | Iguana de Salmoura | ✓ | ✓ | ✓ | ✓ | ✓ | APPROVED | Artilharia covarde do alto da costela; a cegueira é de alvo único e passa com água doce. O Fole de Costela (NA) cega em área por uma rodada. A imagem é limpa. |
| 13 | Esfolado de Sal | ✗ | ✓ | ✓ | ✓ | ✓ | **CHANGES** | O conceito é forte e muito de Valoria (Osshari anestesiado; escama é identidade, `races.txt:286`). A mecânica (`:1029-1031`, "o alvo perde Vitalidade a cada rodada e ele recupera o mesmo tanto") é a do Hóspede (5), na mesma região, e a do Musaranho (Pântano). Junto com a Escama, eram dois Osshari na água com mecânica derivada de escama/ferida. **Correção:** "Sal na ferida: o Ferimento que ele abre ocupa **dois** espaços de Ferimento enquanto arder; lavar com água doce (ação) devolve a um". Sem roubo de vida. |
| 14 | Provador de Ophidia | ✓ | ✓ | ✓ | ✓ | ✓ | APPROVED | O ciclo de três venenos, com a cor no queixo como presságio, é único. Liga Mão Sombria, Brekmar e Ophidia (`locations.txt:467`) sem abrir o mistério de Ophidia. A pele de vidro em placas lembra o Pajem; as veias coloridas separam os dois na arte. |
| 15 | Caldeireiro de Óleo | ✗ | ✓ | ✓ | ✓ | ✓ | **CHANGES** | A silhueta "homem curvado carregando X às costas" (`:1169`) seria a terceira: Pavio da Lista (NA, gaiola) e Jardineiro de Tumores (Pântano, canteiro). **Correção:** tirar o caldeirão das costas e pôr a corrupção no corpo, como pede o dono. A crosta de sebo dos antebraços derrete quando ele mete os braços no fogo da banha e pinga óleo fervente em volta. Silhueta: "um homem de braços amarelos e brilhantes até os ombros, pingando, de pé numa poça que fumega". Contra-jogo: molhar ou esfriar os braços, ou lutar fora da poça. |
| 16 | Acendedor de Naufrágios | ✓ | ✓ | ✓ | ✓ | ✓ | **CHANGES** (texto) | É único: o engano da lanterna e o olho de Éter, mais o croque. Só corrigir o nome em `arte.composicao` (`:1292`, "o Acende-Naufrágio" → "o Acendedor"). |
| 17 | Remo Acorrentado | ✗ | ✓ | ✓ | ✓ | ✓ | **CHANGES** | Mesma vaga tática do Touro (elite, `bruto_de_linha`, `bruto`) e quase a mesma mecânica: telegrafa numa rodada e varre todos à frente na outra (`:1335-1336`). A alternância parado/batida também repete o Compassado. **Correção:** o golpe é de **alvo único e acelera**. Cada rodada seguida em que rema, o golpe sobe um grau ("o tambor acelera"), e um barulho fora do ritmo ou uma interrupção o zera. O corpo (remo, corrente na carne, joelhos de banco) é bom e fica. |
| 18 | Ventre Partilhado (Lyss) | ✗ | ✓ | ✓ | ✓ | ✓ | **CHANGES** | Tom adequado: nada de sexualização, e o `evitar` é explícito. Mas tem dois choques: (a) a mecânica "puxa para o ventre, preso não age" (`:1415-1416`) repete o engolir do Hóspede, na mesma região, e o "preso não age" do Regaço da Margem (Pântano, também elite controlador de cria); (b) a silhueta "quatro braços estendidos para a frente" (`:1403`) é a do Regaço ("quatro braços abertos esperando um abraço"). **Correção:** a mecânica vira **costura**, que é o "um desaparece dentro do outro" de Lyss. O Ventre costura a pele no alvo, e enquanto estiverem costurados metade do dano que ele recebe passa ao alvo, que não se afasta. Cortar a costura custa um Ferimento ao próprio alvo. Silhueta: usar a do `lore` ("de longe, um homem carregando outro no colo"), sem os quatro braços. Corrigir também a frase quebrada de `:1432` ("Quem os Osshari de Brekmar ouvem falar disso…"). |
| 19 | Balsa de Último Dia (Dorrhen) | ✓ | ✓ | ✓ | ✓ | ✓ | APPROVED | É o desespero que se destrói para bater; o contra-jogo é "aguente". É a única sacrificial que gasta o corpo a cada golpe e não ao morrer. A anatomia é diferente da Cavadeira de Unhas (Dorrhen, NA). É legível. |
| 20 | Gancho de Esfola (Maalrek) | ✗ | ✓ | ✓ | ✓ | ✓ | **CHANGES** | O corpo (ganchos de esfola como pernas) é ótimo e não é o Cordão de Medida (Skarath devolve a jogada; corda entre estacas). A mecânica (`:1563-1564`, "gancho preso; cada Ferimento novo fortalece") repete duas fichas: o marcador que fica até arrancar (Casaco de Sanguessugas, Rosário de Vértebras e Ferida de Coral, na mesma região) e o "escala com Ferimentos" da Roda de Mandíbulas, outra cria de Maalrek. **Correção:** é um dilema de esfola. Com o gancho cravado, o alvo que se mover ou recuar **se rasga** (ganha Ferimento); se ficar parado, a criatura puxa uma tira (perde Fôlego). Cortar a corda de tendão encerra. |
| 21 | Raspadeira de Barbatana (Veth) | ✗ | ✓ | ✓ | ✓ | ✓ | **CHANGES** | "Inutiliza a Carta preparada mais forte nesta luta" (`:1642`) é o Convidado de Cera (NA, **também Veth**, "tranca a Carta mais cara por duas rodadas") somado ao Podador do Ciclo (Pântano, "melhor Carta perdida até o fim"). **Correção:** passar a mecânica para o objeto físico, que é o que a ficha descreve (raspa o fio da espada, `:1676`). A cada rodada grudada, os ataques com a arma do alvo perdem um grau, até ele gastar uma ação limpando ou afiando. Quando ninguém mais tem nada melhor, ela pula para quem tiver. |
| 22 | Rancor de Pinças (Vhrak) | ✓ | ✓ | ✗ | ✓ | ✓ | **CHANGES** (texto) | Não é reskin dos Caranguejeiros nem do Caranguejo-Rei, que são um bicho vivo e um rei de carcaça. Aqui é um monte sem cabeça de cascas mortas dos dois lados. O rancor por atacante, com o contra-jogo de dividir os golpes, é único e Vhrak puro. Choque com o cânone: `:1725` e `:1735` dizem "tribos de Caranguejeiros", e o Codex frisa "NÃO são pessoas; são fauna" (`creatures.txt`, Caranguejeiro). **Correção:** "tribos" → "bandos" nos dois lugares. |

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `costa_negra.yaml:166-171` | Ferida de Coral repete o Jardineiro de Tumores | muda que trava a junta (ver 2) |
| P1-2 | P1 | `costa_negra.yaml:1413-1417, 1403` | Ventre repete o engolir do Hóspede e a mecânica e a silhueta do Regaço | costura com dano partilhado e silhueta do colo (ver 18) |
| P1-3 | P1 | `costa_negra.yaml:1027-1031` | Esfolado tem o mesmo roubo de vida do Hóspede | Ferimento salgado ocupa dois espaços (ver 13) |
| P1-4 | P1 | `costa_negra.yaml:1332-1336` | Remo repete o rugido e a varrida do Touro | golpe único que acelera (ver 17) |
| P1-5 | P1 | `costa_negra.yaml:1639-1644` | Raspadeira repete o Convidado de Cera (mesmo demônio) | degrada a arma física (ver 21) |
| P1-6 | P1 | `costa_negra.yaml:86-91` | Escama repete o Pajem de Obsidiana | chão de lascas no raso (ver 1) |
| P2-1 | P2 | `costa_negra.yaml:1560-1565` | Gancho é marcador genérico e escala como a Roda (Maalrek) | dilema mover/rasgar (ver 20) |
| P2-2 | P2 | `costa_negra.yaml:641-646` | Andarilho repete a crosta do Velório de Sal | controle Sacculina na 3ª camada (ver 8) |
| P2-3 | P2 | `costa_negra.yaml:1169` | Caldeireiro é a 3ª silhueta de "carga às costas" | óleo dos próprios braços (ver 15) |
| P2-4 | P2 | `costa_negra.yaml:248, 262` | Compassado: ciclo de 6 h tratado como ritmo por rodada | ritmo do coração (ver 3) |
| P2-5 | P2 | `costa_negra.yaml:386, 407` | Hóspede abre um 2º órgão vivo contra o Codex | o estômago foi refeito pelo Coração (ver 5) |
| P2-6 | P2 | `costa_negra.yaml:1725, 1735` | Rancor chama Caranguejeiros de "tribos" | "bandos" |
| P2-7 | P2 | `costa_negra.yaml:1292, 1432` | nome errado ("Acende-Naufrágio") e frase quebrada no Ventre | corrigir o texto |

Não encontrei segredo vazado: o que o texto público cita de Coração, Canto, Ophidia, Durrak e
da natureza Osshari já é público no Codex e na lore. Nenhuma criatura é perigo conceitual. Todas
são físicas e lutam.

## Rodada 2 (`d4c58b93`)

Revisei só as 13 fichas alteradas, a partir de `git diff 0bfcefa1 d4c58b93 -- data/bestiario/fichas/costa_negra.yaml`,
e conferi no arquivo os campos que o diff não tocou. A troca do papel do Esfolado (`drenador` → `perseguidor_marca`)
está coerente com a mecânica nova. O lint continua verde.

| # | Criatura | Veredito | Conferência |
|---|---|---|---|
| 1 | Escama Revirada | APPROVED | Virou o raso de lascas: deixa de ser o Pajem e o Rancor. P2 em R2-3. |
| 2 | Ferida de Coral | APPROVED | A muda trava a junta (Reação, depois Carta de arma). A linguagem de jardineiro saiu; não é mais o Jardineiro de Tumores. |
| 3 | Compassado do Trono | APPROVED | O coração bate lento por conta própria, deixado assim pelo Canto, e o ciclo de 6 h não vira ritmo de rodada. O `evitar` agora cita o Sorvedouro. Correção pendente em R2-1. |
| 5 | Hóspede do Estômago | APPROVED | O estômago foi refeito pelo Coração-Que-Bate-Ainda: coerente com o Codex público, sem segredo. Não bloqueia: `anatomia.texto` ficou com uma linha longa sem quebra (~linha 130 do diff). |
| 8 | Andarilho de Cracas | APPROVED | Na 3ª camada a colônia guia o alvo (Sacculina); separa do Velório de Sal. |
| 13 | Esfolado de Sal | APPROVED | A ferida salgada conta como duas; sem roubo de vida. Não é mais o Hóspede nem o Musaranho. |
| 15 | Caldeireiro de Óleo | APPROVED | O óleo sai do sebo dos próprios braços, sem carga às costas; separa do Pavio e do Jardineiro, e a corrupção fica no corpo. |
| 16 | Acendedor de Naufrágios | APPROVED | Nome corrigido. |
| 17 | Remo Acorrentado | APPROVED | Golpe de alvo único que acelera com o tambor; sai do espaço do Touro e do Compassado. |
| 18 | Ventre Partilhado | APPROVED | A costura com dano partilhado é Lyss pura e não é o Regaço nem o Hóspede. A silhueta "do colo" está certa, e a frase da lore foi corrigida. Correção pendente em R2-2. |
| 20 | Gancho de Esfola | APPROVED | O dilema rasgar-ou-parar é único; não é marcador genérico nem a Roda. |
| 21 | Raspadeira de Barbatana | APPROVED | Degrada o fio da arma física; separa do Convidado de Cera e do Podador. |
| 22 | Rancor de Pinças | APPROVED | "tribos" → "bandos" nos dois lugares. |

As 9 aprovadas na rodada 1 (Forrado, Barata, Estrela, Touro, Saltador, Bruxa, Iguana, Provador, Balsa)
seguem `APPROVED`; o Forrado já recebeu o ajuste "mais resistente".

### Pendências de uma linha (não pedem nova rodada)

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R2-1 | P1 | `costa_negra.yaml:282-283` | O `telegrafo` do Compassado é um bloco `>-` com o texto entre aspas, e as aspas entram na string (o YAML carrega `'"As costelas…"'`). O presságio sairia com aspas na tela. | Voltar para uma linha: `telegrafo: "As costelas do {nome} se abrem mais um palmo: o coração vai bater."` |
| R2-2 | P1 | `costa_negra.yaml:1510-1511` (e `:1499-1500`) | `arte.visual` ainda manda desenhar "os quatro braços estendidos para a frente, mãos abertas", que é a silhueta do Regaço que a rodada 1 tirou; `aparencia` ainda diz "quatro mãos estendidas para a frente". A arte gerada contradiria a silhueta nova. | Em `arte.visual`: "os braços do de cima pousados nos ombros do de baixo, como quem é carregado no colo". Em `aparencia`: trocar "quatro mãos estendidas para a frente" por "como um homem carregando outro no colo". |
| R2-3 | P2 | `costa_negra.yaml:137` | A composição da Escama ainda mostra o coletor "cobrindo o rosto da chuva de escamas", que era a mecânica antiga. | "…e recua olhando os pés, as escamas caindo no raso em volta". |

## Pendências

- O autor aplica as 12 CHANGES na ficha. A spec e as outras regiões não mudam.
- A conferência (rodada 2) é só das 12, com a mesma checklist.
- A seção "Cortes do revisor" do doc de conceitos fica sem C-R: não houve corte.

## Comandos rodados

```text
bash scripts/dev/py.sh scripts/bestiario/lint.py --regiao costa_negra --sem-revisao → 29 fichas · 0 erro · 0 aviso
grep nome/silhueta/frase em nova_arcadia.yaml e pantano_melancolia.yaml → comparação de identidade e de mecânica
leitura seletiva de data/codex/monsters/*costa_negra* e lore_nova (linhas citadas) → coerência de cânone
```


---

# Revisão da região: deserto_zhur (arquivo original handoffs/SPEC-349-astra-review.md)

# SPEC-349 — revisão astra (unicidade, onda deserto_zhur, rodadas 1 e 2)

> **Veredito:** `APPROVED` (rodada 2; a rodada 1 foi `CHANGES_REQUIRED`, mantida abaixo como histórico)
> **Revisor:** Opus (papel Astra, revisor de unicidade; não é o autor) · **Data:** 2026-11-01 · **Commit revisado:** `d780660a` (branch `bst-deserto_zhur`)

> Nome do arquivo: pedido pelo coordenador. O padrão de `scripts/check_handoff_names.py` não aceita
> `-deserto_zhur-unicidade-`. Ao integrar, mover o conteúdo para `handoffs/SPEC-349-independent-review.md`
> (onde o R10 diz que o parecer fica) ou para `SPEC-349-astra-review.md`.

## Escopo

- `data/bestiario/fichas/deserto_zhur.yaml`: as 26 fichas que não são retro (21 `nova`, 4 `reinventada`,
  1 `adotada`), comparadas com as 6 retro da região.
- `docs/spec349/conceitos-deserto_zhur.md`: os 52 conceitos e os cortes do autor.
- Comparadas também com `nova_arcadia.yaml` e `pantano_melancolia.yaml` (nome, silhueta, texto,
  assinatura e `origem_lore` dos demônios) e com os docs anteriores com a tag `deserto_zhur` em
  `data/codex/monsters/` (Homem-de-Vidro, Lagarto-Espelho, Coisa-da-Borda-Sul, Cristal-de-Urath,
  Os Reis-Enterrados, A Prole-de-Urath, Devoradores de Sol guerreiros, Tempo-Morto, Bebedores-de-Memória,
  O Que Caiu com a Lua, Besouro-de-Espelho, Abutre-de-Sal, Camelo-de-Cristal, Lince, Vento-com-Vozes,
  Saqueadores, Miragem-de-Vaelith, Eco-da-Lua, Cobra-Chocalho, Serpente-do-Crepúsculo).
- Segredos conferidos: `lore_nova/secrets.txt:279-282` (O Que Caiu com a Lua, Harradin) e
  `factions.txt:505`.
- Ficaram de fora: números do bestiário, Cartas, lint técnico (é do Sol). Não rodei pytest
  (por pedido); o lint determinístico, segundo o coordenador, já passa.

## Checklist §3.9 por criatura

Legenda: 1 não é reskin · 2 frase única na região · 3 é de Valoria · 4 é física e luta · 5 sem segredo.

| # | Criatura (status) | 1 | 2 | 3 | 4 | 5 | Veredito | Motivo / correção |
|---|---|---|---|---|---|---|---|---|
| 1 | Andarilho de Duas Idades (nova) | ok | ok | ok | ok | ok | **APPROVED** | Dá corpo à frase pública do Tempo-Morto ("envelhecem ou rejuvenescem em partes do corpo") sem repetir doc nenhum. Contra o Lambedor: drena outra coisa (fecha o próprio Ferimento e deixa o alvo entorpecido, enquanto o Lambedor tira Fôlego), com outro corpo, outra categoria e outro gatilho (a pegada da mão de criança contra o hálito de quem dorme). |
| 2 | Esfolado da Tempestade (nova) | ok | ok | ok | ok | ok | **APPROVED** | Contra o Homem-de-Vidro: ele é uma estátua cristalizada, lenta e frágil, que refrata luz; o Esfolado é carne viva sem pele, com lascas que lixam num sentido só. Material, cor e golpe são outros. Ver a sugestão S1 (a mecânica fica perto da do Mãos de Cinzel). |
| 3 | Provador da Borda (nova) | ok | ok | ok | ok | ok | **CHANGES** | O peito aberto em leque de costelas repete um motivo (correção obrigatória 3). Quanto ao segredo, está ok: o "som tem gosto" já é público na Coisa-da-Borda-Sul, e a ficha não diz de onde o som vem. Harradin aparece sem nada do `secrets.txt`. |
| 4 | Peito de Geodo (nova) | ok | ok | ok | ok | ok | **APPROVED** | Contra o Cristal-de-Urath: ele é um fenômeno mental (orgulho); aqui é o cristal *dentro do corpo*, disparado como pregos. É a única ficha que fica com as costelas abertas, porque é a identidade dela. Ver S2 (Sorvedouro do Código, de Nova Arcádia). |
| 5 | Fervente de Ferrugem (nova) | ok | ok | ok | ok | ok | **APPROVED** | É uma ponte nova entre a Praga do Ferro e Zhur, com corpo legível. Ver S3 (o papel de sacrificial explodindo ao cair é o mesmo da Mula de Lágrimas). |
| 6 | Carregador de Liteira (reinv. `enemy_mumia_de_po`) | ok | ok | ok | ok | ok | **APPROVED** | Sai da múmia de verdade (madeira dos varais, coleira, sem faixas). É o servo dos Reis-Enterrados, não uma cópia deles: os Reis são espectros, ele é físico e persegue. |
| 7 | Varano Vidrado (nova) | ok | ok | ok | ok | ok | **APPROVED** | Contra o Lagarto-Espelho: pequeno e quase invisível lá, enorme e com ciclo de calor aqui. É a criatura que ancora o couro dos Devoradores e o Couro Pegado. É o lagarto que **fica** (ver a correção 5). |
| 8 | Tatu de Navalha (nova) | ok | ok | ok | ok | ok | **APPROVED** | A bola de cintas com lâminas é legível. Contra a Roda de Mandíbulas (Nova Arcádia): bola contra roda, lacaio batedor contra bruto, e outra mecânica. |
| 9 | Lambedor de Hálito (nova) | ok | ok | ok | ok | ok | **APPROVED** | O beber o hálito de quem dorme é único. Ver S4: é o 3º besouro de Zhur, e o conceito 27 foi cortado justamente por ser "segundo escaravelho". |
| 10 | Lastreiro da Cratera (nova) | ok | ok | ok | ok | ok | **APPROVED** | Silhueta muito boa. "Cratera onde algo respira devagar" já está no doc **público** de O Que Caiu com a Lua, e a ficha não diz o que dorme lá. Contra o Bagre de Varal: são flutuadores diferentes (bexiga presa a lastro contra peixe na bolha). |
| 11 | Cavador de Funil (nova) | ok | ok | ok | ok | ok | **APPROVED** | Contra o Verme de Vidro: os dois ficam sob a areia, mas o Cavador é fixo e faz a parede escorrer (controlador), e o Verme nada e engole (emboscador). O `evitar` já separa os dois. |
| 12 | Saltador de Palafita (nova) | ok | ok | ok | ok | ok | **APPROVED** | As canelas de vidro e o bando chamado no grito são legíveis. Fica distante do Lince e do Sapo-Boi. |
| 13 | Verme de Vidro (adotada → `enemy_verme_areia_jovem`) | ok | ok | ok | ok | ok | **APPROVED** | Fiel a `creatures.txt:1140`. O gancho separa este verme do Ancião. O `evitar` cita Shai-Hulud. |
| 14 | Pipa de Costelas (reinv. `enemy_djinn_menor`) | ok | ok | ok | ok | ok | **APPROVED** | Tira o djinn do espírito e faz dele um bicho de pele e papo. As costelas são varetas de voo, não um peito aberto, então não entra na correção 3. |
| 15 | Braceiro da Borda Sul (reinv. `enemy_aranha_de_cristal`) | **não** | ok | ok | ok | ok | **CHANGES** | "Oito braços humanos pálidos" repete o Fardo de Espólio do Pântano (oito braços humanos de pele branca de afogado) e deixa um eco de aranha no slot (correção 6). O segredo está ok: não explica o som, e o "também tem bichos" o separa da Coisa-da-Borda-Sul. |
| 16 | Costurado de Lentes (nova) | ok | ok | ok | ok | ok | **APPROVED** | O papel de marcador em cima dos cristais é próprio. Ver S5: o texto da retro Devorador de Sol (Zhur) já é "lentes de obsidiana costuradas na pele". |
| 17 | Couro Pegado (nova) | ok | ok | ok | ok | ok | **APPROVED** | O couro que cria raiz, troca de pele e vira anteparo do tamanho de uma porta é novo. Ver S6 (arte contra o Esfolado). |
| 18 | Mãos de Cinzel (nova) | ok | ok | ok | ok | ok | **APPROVED** | Cunhas de Éter e escutar a racha. Ver S1. |
| 19 | Aguadeiro de Bucho (nova) | **não** | ok | ok | ok | ok | **CHANGES** | A silhueta é a da Mula de Lágrimas do Pântano ("homem magro de barriga enorme, mãos sobre a barriga", com líquido dentro). É a correção 2. |
| 20 | Caçador Sem Calor (nova) | ok | ok | ok | ok | ok | **APPROVED** | Usa a regra pública da miragem (não tem calor) para dar um corpo de verdade. Bom. |
| 21 | Altivo do Vidro (nova, Urath) | ok | ok | ok | ok | ok | **CHANGES** | Contra o Trono, o par é complementar e bom (o que não ajoelhou contra os que ajoelharam), com anatomias diferentes. Mas a "gola de costelas em leque" entra no motivo da correção 3 e aparece na silhueta. |
| 22 | Despenseiro de Espinhos (nova, Maalrek) | **não** | ok | ok | ok | ok | **CHANGES** | É o segundo lagarto grande e quadrúpede de dorso vidrado da onda (com o Varano), e o terceiro lagarto da região (com o Lagarto-Espelho). A ideia (despensa viva + canaletas) é ótima; o bicho não. É a correção 5. |
| 23 | Lacrador de Saídas (nova, Dorrhen) | ok | ok | ok | ok | ok | **APPROVED** | O Desespero vira paredes físicas que fecham a saída, e a contra-jogada (a parede está mole) é a lição do demônio. Bem melhor que o conceito 48. |
| 24 | Juntador de Cacos (nova, Daruun) | **não** | **não** | ok | ok | ok | **CHANGES** | É a 3ª cria de Daruun nas ondas e a 2ª com o mesmo encaixe e a mesma ideia do Fardo de Espólio (`saqueador`/`covarde_oportunista`/`lacaio`, "não larga o que pegou"). Também é o 2º roedor da onda (com o Saltador). É a correção 1. |
| 25 | Nó de Rixa (nova, Vhrak) | ok | ok | ok | ok | ok | **APPROVED** | Corpo acoplado legível, ligado à guerra que vem entre os clãs. O Gêmeo de Inveja foi bem cortado. Ver S7 (mecânica perto da Roda de Mandíbulas). |
| 26 | Trono de Ajoelhados (reinv. `enemy_boss_general_escorpiao`, Urath) | **não** | ok | ok | ok | ok | **CHANGES** | Contra os Reis-Enterrados está ok: lá é espectro em trono, aqui é um monte físico com cavaleiro. Contra a Fila de Grilhões (Nova Arcádia), porém, os dois são compostos de gente, são `guarda_protetor` e "puxam o alvo para dentro do corpo". O "quem dobra é puxado para a base, e o monte cresce" é a mecânica da Fila. É a correção 4. |

Resultado: 19 APPROVED e 7 CHANGES (Provador, Braceiro, Aguadeiro, Altivo, Despenseiro, Juntador, Trono).

## Correções obrigatórias (rodada 2)

Cada correção atualiza `texto`, `silhueta`, `aparencia`, `arte` e, quando mudar, `mecanica_assinatura`
e `telegrafo`. Depois, rodar de novo `lint.py --vagas` e o lint da região (U2/U3/U12), porque algumas
mudam eixos.

1. **Juntador de Cacos (`deserto_zhur.yaml:1816-1891`): trocar o demônio e a ideia.** Daruun (Cobiça,
   "guarda") já tem cria lacaio covarde na NA (Escritura Rastejante) e no Pântano (Fardo de Espólio,
   saqueador que não solta o que pegou). Passar para **Veth (Inveja)**, que ainda não está em Zhur
   (o conceito 50 a deixou de fora) e diz "não quer o que o outro tem, quer que o outro não tenha"
   (`npcs.txt:250`). A ideia vira **estragar em vez de guardar**: furar cantil e odre, roer correia,
   trincar a lente. No deserto, isso mata. A assinatura deixa de ser "perde um item até o Juntador
   morrer" e vira "inutiliza um item ou o Fôlego de água do alvo". Tirar as costas de moedas coladas
   (o tesouro acumulado é o Fardo). O corpo pode continuar pequeno, mas tem de ler diferente do
   Saltador (sem roedor de pé, sem orelhas grandes).
2. **Aguadeiro de Bucho (`:1444-1513`): tirar o reservatório da barriga.** A barriga enorme segurada
   pelas mãos é a Mula de Lágrimas. O reservatório também não pode ir para as costas (Jardineiro de
   Tumores, Pavio da Lista) nem para a corcova (Camelo-de-Cristal, conceito 28). Sugestão: **braços-odre**.
   A pele dos dois antebraços foi costurada em odres compridos e moles que pendem até os joelhos, e ele
   espreme um deles como gaita de foles para dar de beber. Silhueta: "um homem magro com dois braços
   inchados e moles pendurados até os joelhos". Ele não luta, e isso combina com o suporte. Atualizar o
   nome se "Bucho" deixar de fazer sentido.
3. **Motivo "costelas abertas em leque": ficar só no Peito de Geodo.** Hoje aparece em quatro fichas:
   Provador (`:247`, `:250`), Altivo (`:1609`, `:1611`), Peito de Geodo e o Fole de Costela de Nova
   Arcádia ("barril de costelas abertas").
   - **Provador:** a língua sai pela boca rasgada até a garganta. Sem esterno partido e sem costelas.
     Silhueta sugerida: "homem magro de cócoras com o queixo partido em duas abas e uma língua
     cinzenta pendendo até a cintura".
   - **Altivo:** trocar a gola de costelas por outro crescimento de osso para cima, como fêmures e
     tíbias alongados (fica alto como sobre pernas de pau, de osso exposto) e o crânio esticado para
     trás, sem costela à mostra. A silhueta continua "alta, esticada, rosto para o céu", sem a gola.
4. **Trono de Ajoelhados (`:1993-2004`): tirar o "puxar para a base / o monte cresce"** da
   `comportamento`, da `mecanica_assinatura.frase` e das `acoes`. Essa é a mecânica da Fila de
   Grilhões. A segunda cláusula da assinatura passa a ser do cavaleiro. Por exemplo: "quem já estava
   de joelhos recebe a Mão do Alto" (golpe direto do de cima) ou "fica sem reação na rodada". Ficam o
   monte que anda, o cavaleiro e o ajoelhar.
5. **Despenseiro de Espinhos (`:1663-1740`): deixar de ser lagarto de dorso de vidro.** A ideia fica
   (despensa viva nas costas, canaletas, Maalrek paciente); muda o bicho. Opções que não colidem com
   nenhuma ficha nem doc:
   - (a) **ave corredora grande, sem voo**, que leva o picanço ao pé da letra, com penas do dorso
     viradas em espinhos e a presa espetada. Muda o `plano_corporal` da vaga 18, então rodar `--vagas`.
   - (b) **mamífero tipo texugo/ratel do tamanho de um touro**, com pelos-guarda virados em espinhos
     de osso. Neste caso `material: osso` em vez de `vidro_cristal`, e o `evitar` deixa claro que não é
     porco-espinho (Cavadeira de Unhas).

   Evitar quelônio (Cágado de Geada), porco (Porca da Queda) e hiena (retro). Se o vidro sair, a cota
   de no máximo ⅓ de vidro melhora.
6. **Braceiro da Borda Sul (`:1163-1217`): parar de ser "oito braços humanos pálidos".** O número, a
   palidez e o braço humano repetem o Fardo de Espólio, e oito membros no slot da Aranha de Cristal
   lembram a aranha que o `evitar` quer afastar. Sugestão: **dois braços só, do comprimento de mastros,
   com três cotovelos cada** e as mãos-remo. A silhueta vira "duas mãos enormes agarrando a beirada de
   um penhasco", que é mais legível e mais única. O tronco, as orelhas e a assinatura (quebrar a
   beirada) ficam. Ajustar o `telegrafo` ("as oito mãos").

Também obrigatório, para o coordenador ou o autor (eu não edito): preencher o §3 "Cortes do revisor"
em `docs/spec349/conceitos-deserto_zhur.md` com os motivos acima e, depois da rodada 2, gravar
`revisao: aprovada` nas fichas.

## Cortes do autor: algum deveria ter ficado?

- Nenhum conceito cortado deveria voltar como está. Os motivos dos cortes conferem.
- A exceção é parcial: o **demônio** do conceito 50 (Veth) deveria ter ficado, no lugar do Daruun
  do Juntador (correção 1). O corpo do 50 não deveria voltar, porque o acoplado já é do Nó de Rixa.
- O motivo do corte do conceito 27 ("segundo escaravelho") vale também contra o Lambedor, que ficou.
  Não peço troca, porque o Lambedor tem silhueta e ação próprias, mas o critério ficou desigual (S4).

## Sugestões opcionais

- **S1. Esfolado × Mãos de Cinzel:** os dois são `padrao`/`quebra_defesa`/`bruto` e tiram proteção. A
  diferença hoje é só de duração (o Esfolado abre o próximo golpe de qualquer um; o Mãos deixa uma
  rachadura que dura). Para separar mais, o Esfolado poderia virar agarrão com desgaste por rodada, ou
  punir quem bate "a favor das lascas".
- **S2. Peito de Geodo × Sorvedouro do Código (NA, "peito aberto onde a luz fria se acumula"):** no
  `arte.evitar`, acrescentar "funil ou crosta no esterno; postura ereta". A pose curvada segurando as
  costelas é o que separa os dois.
- **S3. Fervente × Mula de Lágrimas:** os dois são lacaios sacrificiais que explodem ao cair. Aceito
  porque o papel é esse, mas a cena de escavação do Fervente repete a do Mãos de Cinzel. Trocar a
  composição do Fervente por estrada ou acampamento.
- **S4. Lambedor:** registrar no doc de conceitos por que ele não cai na regra do "segundo escaravelho"
  (a silhueta de pernas altas não é escaravelho).
- **S5. Costurado × retro Devorador de Sol ("lentes costuradas na pele"):** no `arte.evitar`,
  acrescentar "Devorador comum de lentes só nos olhos". A arte tem de mostrar dezenas de discos e a
  palma apontada.
- **S6. Couro Pegado × Esfolado:** os dois são "homem escamado". Manter na arte o contraste ocre-placa
  do Couro Pegado contra o vermelho-lasca do Esfolado.
- **S7. Nó de Rixa × Roda de Mandíbulas:** as duas assinaturas são golpe em área que cresce com
  Ferimentos, e as duas criaturas são `bruto_de_linha`. Sugestão: as metades se batem quando ele é
  golpeado (dano refletido para quem estiver dos dois lados).

## Correções aplicadas

(o executor preenche na rodada 2)

## Pendências

- Integrar este parecer em `handoffs/SPEC-349-independent-review.md` (R10) ou renomear para passar
  em `check_handoff_names.py`.
- Rodada 2 (a última): revisar só as 7 fichas com CHANGES e, se mudarem eixos, a tabela `vagas:`.

## Comandos rodados

```text
git diff main...HEAD --stat → 73 arquivos (onda zhur + base da esteira)
grep nome/silhueta/texto/frase/origem_lore nas 3 fichas de região → comparações acima
sed nos docs data/codex/monsters/* com a tag deserto_zhur → 20 docs anteriores lidos (só o corpo)
grep secrets.txt:275-282, factions.txt:505 → nada do segredo vaza; "algo respira devagar" é público
(pytest não rodado, por instrução)
```

---

## Rodada 2 (final) — 2026-11-01

Conferi só as 7 fichas que mudaram: `mon_provador_da_borda`, `enemy_aranha_de_cristal`,
`mon_aguadeiro_de_bucho`, `mon_altivo_do_vidro`, `mon_despenseiro_de_espinhos`, `mon_furador_de_odres`
(no lugar do Juntador) e `enemy_boss_general_escorpiao`. Comparei cada uma com a própria região, com
Nova Arcádia, com o Pântano e com o Codex de Zhur. Não rodei pytest nem lint (por instrução). O
executor informa que `--vagas` está verde e que o lint da região só acusa os 5 U1 dos slots, que são
esperados.

| Criatura | Correção | 1 | 2 | 3 | 4 | 5 | Veredito | Nota |
|---|---|---|---|---|---|---|---|---|
| Provador da Borda | 3 | ok | ok | ok | ok | ok | **APPROVED** | O peito não abre mais: o queixo se parte em duas pinças de osso e a língua sai da garganta. O `evitar` cita "peito aberto". O som da borda continua sem explicação. |
| Braceiro da Borda Sul | 6 | ok | ok | ok | ok | ok | **APPROVED** | Ficou com dois braços de três cotovelos, e a silhueta é "duas mãos enormes na beirada". Se afasta do Fardo de Espólio e da aranha do slot. Os "braços de muitas juntas" do Regaço da Margem estão num corpo sentado e de outra escala; aceito. |
| Aguadeiro de Bucho | 2 | ok | ok | ok | ok | ok | **APPROVED** | Os antebraços viraram odres e a barriga é normal, então não lê mais como a Mula de Lágrimas. Nenhuma outra ficha das três regiões tem braço-odre. O nome "Bucho" segue coerente (são buchos de varano). |
| Altivo do Vidro | 3 | ok | ok | ok | ok | ok | **APPROVED** | A gola de costelas saiu; agora tem canelas como pernas de pau e uma crista no crânio. Ver a nota R2-a (Saltador). |
| Despenseiro de Espinhos | 5 | ok | ok | ok | ok | ok | **APPROVED** | Virou ave corredora sem voo, com penas transformadas em espinhos. Não existe ave corredora nas três regiões nem no Codex (o Abutre-de-Sal voa; o Cisne de Pátina é ave d'água). A despensa viva e Maalrek continuam. |
| Furador de Odres (Veth) | 1 | ok | ok | ok | ok | ok | **APPROVED** | Estraga sem guardar. Cada Veth fica com um alvo próprio: o da NA (Convidado de Cera) tranca a Carta mais cara, este fura o cantil de quem tem mais. É o jeito certo de repetir o demônio. Não é roedor de pé nem tem orelhas grandes, então se separa do Saltador. Ver a nota R2-b. |
| Trono de Ajoelhados | 4 | ok | ok | ok | ok | ok | **APPROVED** | O "puxar para a base" e o "monte cresce" saíram das quatro partes (assinatura, comportamento, ações, `como_se_luta`). A segunda cláusula agora é a mão do alto castigando quem já está de joelhos. Não repete mais a Fila de Grilhões. |

Resultado final da onda: as 26 fichas não-retro estão **APPROVED**. As fichas já podem receber
`revisao: aprovada`, com `revisor_unicidade` diferente do autor. Também conferi que os cortes estão
registrados no §3 de `docs/spec349/conceitos-deserto_zhur.md`.

Notas opcionais (nenhuma bloqueia):
- **R2-a:** o motivo "canela alongada" agora aparece duas vezes na região: o Saltador (varetas de vidro,
  roedor pequeno) e o Altivo (hastes de osso, humanoide alto). A escala, o material e a família são
  diferentes, e as silhuetas não se confundem. Se quiser mais distância, no `arte.evitar` do Altivo
  acrescentar "pernas finas de vidro".
- **R2-b:** as composições do Furador e do Lambedor de Hálito são a mesma cena ("acampamento de
  caravana de madrugada, viajantes dormindo"). Para variar, trocar a do Furador por uma sela de camelo
  em parada de dia, ou um poço.
- Continuam valendo as opcionais da rodada 1 que não foram aplicadas: S1 (mecânicas do Esfolado e do
  Mãos de Cinzel), S4 (o Lambedor como terceiro besouro), S6 (contraste de arte entre o Couro Pegado e
  o Esfolado) e S7 (assinaturas do Nó de Rixa e da Roda de Mandíbulas).

Ainda pendente do coordenador: integrar este parecer em `handoffs/SPEC-349-independent-review.md`
ou renomear o arquivo, porque o nome atual não passa em `check_handoff_names.py`.


---

# Revisão da região: floresta_sussurros (arquivo original handoffs/SPEC-349-floresta_sussurros-review.md)

# SPEC-349 — revisão de unicidade, onda Floresta dos Sussurros (review)

> **Veredito (rodada 2, `c6ef0ff1`):** `APPROVED_WITH_FOLLOWUPS` para as 25 (ver § Rodada 2). Rodada 1: `CHANGES_REQUIRED`. 6 fichas com CHANGES (4 P1, 2 P2) e 19 APPROVED, 8 delas com
> follow-up de texto curto. Aplicadas as 6 CHANGES e os follow-ups F1 (Preguiça) e F2 (Toldo), o
> veredito passa a `APPROVED_WITH_FOLLOWUPS`. Basta conferir o diff dessas fichas, sem nova rodada
> completa.
> **Revisor:** Opus (spec-reviewer, revisor de unicidade independente; o autor das fichas é outro agente Opus) · **Data:** 2026-11-01
> **Commit revisado:** `87e1a1d2` (branch `bst-floresta_sussurros`)

## Escopo

Revisei as 25 fichas não-retro de `data/bestiario/fichas/floresta_sussurros.yaml` (21 `nova` e 4
`reinventada`) pelo checklist §3.9, junto com `docs/spec349/conceitos-floresta_sussurros.md`.

Comparei com:
- as 4 fichas retro da região (Urso-de-Espinha, Serpente-Raiz, Mariposa do Sussurro, Caçador de Casca);
- os 30 docs `data/codex/monsters/` que citam a floresta, lidos só nos trechos parecidos (Ave-Imóvel,
  Colhedores-de-Pó, Perdidos-Permanentes, Caçador-de-Costas, Javali-de-Casca, Lobo-de-Olhar-Errado,
  Coletor-de-Galhos, Filho-de-Thessavar, Aranha-da-Névoa-Negra);
- as 27 fichas de Nova Arcádia e as 22 do Pântano, pelas frases de `mecanica_assinatura`, as
  silhuetas e os ganchos das crias;
- a definição das famílias em `data/codex/world_story/story_corpos_do_abismo.md:30-40`.

Conferi a lore no checkout principal (`lore_nova/`, SPEC-348): `npcs.txt` (Solveth :402-410, Vestra
:1546-1552, Quell :1619-1625, Thessavar :182, Urath :163, Maalrek :214, Veleth :351),
`timeline_completa.txt:146,196,198,260`, `creatures.txt:828,874,921,933,943`,
`locations.txt:149,155`, `items.txt:770,796,830` e `races.txt:379-401`. `secrets.txt` não cita a
floresta, Thessavar, Vestra, Quell nem o Pó, e nenhum texto público entrega segredo.

Ficaram fora: números, Cartas (Etapa 5), a arena e o doc de arte gerado.

**A régua desta revisão.** A família Besta Torta é definida em `story_corpos_do_abismo.md:32` assim:
"a física do bicho cede antes do corpo: ele pesa o que não devia, cai para o lado errado, come o
som, chega antes de chegar". Um animal real só aumentado não cumpre isso. O Bugio Invertido cumpre
à risca, e por isso a gravidade ao contrário dele não é perigo conceitual.

## Tabela por criatura

| # | Criatura (id) | Veredito | Motivo |
|---|---|---|---|
| 1 | Lixado da Fronteira (`mon_lixado_da_fronteira`) | APPROVED | Bate com a lore de Solveth ("carne vira pó cinza", `npcs.txt:408`). Quebrar a Defesa já existe no Portão que Morde (NA), mas aqui as mãos se gastam a cada agarrão, e isso só ele tem. Silhueta legível. |
| 2 | Abafador de Candeias (`mon_abafador_de_candeias`) | **CHANGES (P1)** | "Os golpes dele não são vistos chegando" é a mesma regra da Onça Vazada ("bote sem presságio") e da Arraia de Lodo (Pântano, presságio turvo). Ver C-2. |
| 3 | Fechado de Escápulas (`mon_fechado_de_escapulas`) | APPROVED | Melhor Reescrito da onda para a referência do dono: placa óssea sobre músculo exposto. Interpor-se é o papel do `guarda_protetor`; a fresta exposta quando ele abre para bater é só dele. |
| 4 | Virado do Avesso (`mon_virado_do_avesso`) | APPROVED (F3) | A lore do Pó ("mostrou o lado de dentro") é excelente e fiel a `creatures.txt:874`. O revide por golpe parece o do Pajem de Obsidiana (NA); fica distinto se a Etapa 5 contar revides por golpe, não por dano. |
| 5 | Calado das Guelras (`mon_calado_das_guelras`) | **CHANGES (P1)** | A frase junta três regras alheias: bate e volta (Saltão, na região, e Patinador de Óleo, no Pântano), "não é visto chegando" (Onça e Abafador) e "quem gastou mais Fôlego", que na prática vira o mesmo gatilho do Morcego. Ver C-1. |
| 6 | Saltão Desbotado (`enemy_aranha_lobo`) | APPROVED | É o batedor da região que pula a linha da frente e morde quem está atrás. Cegueira e falta de cor vêm do escuro (`creatures.txt:828`). A inspiração está registrada com a distância. |
| 7 | Casuar de Elmo Fundo (`enemy_urso_coruja_mutante`) | APPROVED | O casco crescido sobre os olhos é uma marca no corpo. O chute em quem se moveu, mesmo sendo criatura aliada, é regra só dela. A pose numa perna lembra a Ave-Imóvel, mas fica no plano visual. |
| 8 | Preguiça da Pradaria (`mon_ent_dormindo`) | APPROVED (F1, aplicar) | Corpo e gancho bons, e é ela quem fica com a âncora da pradaria da Era 0. A frase, porém, usa "faz barulho" (o gatilho do Morcego) e "preso até se soltar" (Lagarta, Picanço, Romeiro de Âmbar). Ver F1. |
| 9 | Morcego Rasteiro (`mon_morcego_rasteiro`) | APPROVED (F6) | Orelhas maiores que as asas e o andar nos punhos dão uma marca de corpo legível. Fica com o "barulho" da região. |
| 10 | Besouro do Estalo (`mon_besouro_do_estalo`) | **CHANGES (P1)** | A própria ficha o chama de "besouro comum grande demais" (`:867`). A física dele não cede em nada. O gancho dos ruídos curtos da floresta já é da Ave-Imóvel (Codex, `mon_ave_imovel.md:17`), e o jato em cone é genérico. Ver C-3. |
| 11 | Onça Vazada (`mon_onca_vazada`) | APPROVED | É a melhor Besta Torta da onda: os furos no lugar das rosetas são legíveis, físicos e de Valoria, e o coração aparece num dos furos. Fica com a regra do bote sem presságio. |
| 12 | Lagarta de Visgo (`mon_lagarta_de_visgo`) | **CHANGES (P2)** | A regra "não se move nem troca de arma até se soltar" é a do Romeiro de Âmbar (Pântano). O gancho da pradaria da Era 0 é o da Preguiça, e o próprio autor cortou o Bisão por esse motivo. Ver C-6. |
| 13 | Toldo das Clareiras (`mon_toldo_das_clareiras`) | APPROVED (F2, aplicar) | Chefe legível, e o gancho das clareiras é forte. Uma frase contradiz a lore: "por isso a floresta não tem céu", quando quem fecha a luz são as árvores de Thessavar (`timeline:146,198`). Ver F2. |
| 14 | Vespa Coveira (`mon_vespa_coveira`) | APPROVED (F4) | Fica com a regra de arrastar para fora da luta. O corpo ainda é só uma *Pepsis* aumentada. Ver F4. |
| 15 | Bugio Invertido (`mon_bugio_invertido`) | **CHANGES (P2)** | O corpo é canônico ("cai para o lado errado"), mas a regra "fica fora do alcance dos aliados até cair de volta" repete a da Vespa: duas criaturas que tiram o herói da luta. Ver C-5. |
| 16 | Dedos de Colheita (`mon_dedos_de_colheita`) | **CHANGES (P1)** | Forma par com o Mascador: dois Cobrados de revelação que mexem com Cartas ocultas, e o Ouvinte da Raiz foi cortado por esse mesmo motivo. Além disso, a lore diz que Vestra "colhe de luvas", contra `npcs.txt:1548` ("dedos manchados de vermelho do fungo", Mão-vermelha). Ver C-4. |
| 17 | Olho de Pétala (`mon_olho_de_petala`) | APPROVED | Fiel a `creatures.txt:943` e `items.txt:796`; a dúvida sobre se mais alguém olha pela flor fica só sugerida. Ignorar escuro e cobertura é regra só dele. A arte é legível. |
| 18 | Mapa de Cicatrizes (`mon_mapa_de_cicatrizes`) | APPROVED | Fiel a Quell (`npcs.txt:1621-1623`). É o único suporte que reposiciona criaturas pelo flanco, e as cicatrizes que andam formam uma imagem forte. |
| 19 | Ressecado da Travessia (`mon_ressecado_da_travessia`) | APPROVED | Fiel aos Hospedeiros (`races.txt:391`) e à fronteira (`locations.txt:155`). Como drenador, difere da Sombra Deitada: bebe só de quem já está ferido, e as placas se fecham. |
| 20 | Mascador de Raiz (`mon_mascador_de_raiz`) | APPROVED (depende de C-4) | Fiel a `items.txt:830` (a raiz serve à "magia de verdade e revelação" e escapa ao ocultamento). Fica com a revelação de Carta da região. |
| 21 | Sombra Deitada (`enemy_sombra_espreitadora`) | APPROVED (F5) | A planária de boca no ventre tem corpo novo e explica o mecanismo da cria. A emboscada no chão lembra a Serpente-Raiz (retro), mas a regra (dreno que cresce) e o corpo diferem. O gancho repete o do Ermitão. Ver F5. |
| 22 | Ermitão de Carcaça (`mon_ermitao_de_carcaca`) | APPROVED (F5, F7) | Troca de carcaça no meio da luta: uma das melhores ideias da onda. O contra-jogo "não deixar corpos perto" repete o da Coisa do Esgoto (NA); o "acertar na troca" é o diferencial e deve vir primeiro. |
| 23 | Desafiante Rubro (`mon_desafiante_rubro`) | APPROVED | `timeline_completa.txt:196` diz exatamente que a magia de sangue de Zhur é resíduo de Urath e entra pelas raízes da borda. O duelo, com golpes de terceiros reduzidos no vidro, é regra só dele. |
| 24 | Enrolado da Clareira (`mon_enrolado_da_clareira`) | APPROVED (F8) | A regra é única: a luz dispara a rolagem e o escuro deixa o ventre aberto. Mas "roda de carroça que rola pela fila" é a imagem da Roda de Mandíbulas (NA, `:1013`), e "a vergonha esconde a cara" é a leitura de Veleth já usada no Mãos no Rosto (Pântano). |
| 25 | Picanço de Espinheiro (`mon_picanco_de_espinheiro`) | APPROVED (F6) | A despensa viva é forte e é a cara de Maalrek (`npcs.txt:214`). Fica com a regra "preso e sangrando" da região. O telégrafo "para quem sangra" é o terceiro sobre sangue, depois da Vespa e do Ressecado. |

## CHANGES (priorizados)

| ID | Sev. | Arquivo:linha | Problema | Correção mínima |
|---|---|---|---|---|
| C-1 | P1 | `floresta_sussurros.yaml:403-407` (Calado) | A frase junta três regras de outras criaturas: bate e volta (Saltão `:489-491`, Patinador de Óleo do Pântano `:381`), "não é visto chegando" (Onça `:905-907`, Abafador `:170-172`) e o alvo "quem gastou mais Fôlego", que na Etapa 5 colapsa com o "quem fez mais barulho" do Morcego. Nenhuma das três é só dele. | Usar o que só o corpo dele dá, o faro de respiração e o bando. Texto sugerido: "O bando inteiro corre para quem tem menos Fôlego sobrando, quem está arfando, e cada Calado a mais no mesmo alvo bate mais forte." Tirar o bate e volta e o "não é visto". Contra-jogo: "guardar Fôlego quando eles estão perto; as fendas do pescoço são moles". Ajustar `comportamento`, `como_se_luta` e `padrao` (sem `mover` de recuo). |
| C-2 | P1 | `:170-173` (Abafador) | O efeito do escuro ("os golpes dele não são vistos chegando") é a regra da Onça e da Arraia de Lodo (Pântano `:1561`). A identidade dele é roubar a luz; o efeito tem de sair disso. | Texto sugerido: "Vai sempre em quem carrega a luz e a apaga no abraço: até alguém gastar uma jogada para reacender, os ataques à distância do grupo não têm alvo." O contra-jogo atual (luz no chão, duas luzes) continua servindo. A Onça fica com o bote sem presságio. |
| C-3 | P1 | `:808-813`, `:825-831`, `:867` (Besouro) | É um besouro-bombardeiro real só aumentado, e a ficha diz isso em "é um besouro comum grande demais". Nada da física dele cede (`story_corpos_do_abismo.md:32`). O gancho, os ruídos curtos da floresta, já é da Ave-Imóvel no Codex. O jato em cone é genérico. | Dar a ele a física torta "chega antes de chegar": o estouro soa uma rodada antes do jato. Texto sugerido: "O estalo marca o chão onde o jato vai cair; na rodada seguinte o vapor fervente cai ali, e quem não saiu leva." Na anatomia, uma linha: "o estouro sai da câmara antes da mistura ferver, e o jato vem depois, no lugar onde o som estourou". Trocar o gancho dos ruídos pelo do estalo adiantado e tirar "besouro comum" do `evitar`. |
| C-4 | P1 | `:1299-1302`, `:1314-1318` (Dedos) | (a) Faz par com o Mascador (`:1604-1607`): a mesma fonte de revelação mexendo com Carta oculta, e o Ouvinte da Raiz foi cortado por isso. Para um `sacrificial`, a regra ainda dá ao jogador mais vantagem que custo. (b) Contradiz a lore: "Vestra colhe de luvas" contra os dedos vermelhos e o nome Mão-vermelha (`npcs.txt:1548`). | (a) Tirar a revelação da regra e deixá-la como narração. Texto sugerido: "Quebra os próprios dedos no rosto do herói e deixa os talos cravados: cada Carta que o herói jogar dá Entropia até ele gastar uma jogada para arrancá-los; o colhedor sai da luta." Contra-jogo: derrubá-lo antes, cobrir o rosto, arrancar logo. (b) Trocar por "Vestra, que tem os dedos vermelhos e sabe o preço, manda colher de luvas." |
| C-5 | P2 | `:1221-1225` (Bugio) | "Fora do alcance dos aliados até cair de volta" repete a Vespa (`:1144-1146`, "o arrasta para fora da luta"). São duas criaturas que tiram o herói da luta, e o coordenador pediu para cortar exatamente esse par. O corpo e a lore do Bugio ficam como estão. | Trocar a remoção por reposicionamento. Texto sugerido: "Agarra o último da linha e o solta para cima; na rodada seguinte ele cai de volta na frente da linha, longe dos aliados e no meio das criaturas." Contra-jogo atual (andar junto, golpe na cauda) continua. A Vespa fica com a regra de tirar o herói da luta. |
| C-6 | P2 | `:980-987` (Lagarta) | A regra de prender pés e mãos é a do Romeiro de Âmbar (Pântano `:137`: "não troca de lugar nem recua até quebrá-lo"). O gancho da pradaria da Era 0 é o da Preguiça, e o Bisão foi cortado por esse mesmo motivo (doc de conceitos, #27). Ao lado da Preguiça e do Picanço, é a terceira criatura da região que prende. | Mudar o alvo da cola. Texto sugerido: "O leque cola o alvo ao que estiver do lado, um aliado ou o tronco: dois heróis colados dividem cada golpe que um deles leva e só se movem juntos." Contra-jogo: fogo ou água quente, não andar lado a lado. Trocar o gancho para o fundo úmido debaixo das folhas, ligado à fauna primordial do escuro (`creatures.txt:828`), sem pradaria. |

## Follow-ups (não bloqueiam; F1 e F2 devem ir junto com as CHANGES)

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| F1 | P2 (aplicar) | `:663-666` (Preguiça) | "Ou faz barulho perto" usa o gatilho do Morcego, e "preso até se soltar" é a regra de Lagarta, Picanço e Romeiro. | Gatilho só de posição: "quem passa à frente dela". Trocar o "preso" por uma regra de guarda, por exemplo: "puxado contra o peito, vira escudo: os golpes dos aliados nela acertam primeiro o preso." |
| F2 | P2 (aplicar) | `:1053-1054` (Toldo) | "Por isso a floresta não tem céu" contradiz `timeline:146,198`: quem fecha a luz são as árvores de Thessavar. | Trocar por "por isso nem as clareiras têm céu". |
| F3 | P2 | `:327-329` (Virado) | O revide por golpe parece o do Pajem de Obsidiana (NA `:1391`) e o do Vira-Costas. | Na Etapa 5, contar revides por número de golpes, nunca por dano, e manter "muitos golpes pequenos" na frase. |
| F4 | P2 | `:1127-1132` (Vespa) | É uma *Pepsis* aumentada, sem física torta. | Uma linha de "pesa o que não devia", por exemplo: "voa com um homem inteiro preso nas patas como se levasse uma folha". |
| F5 | P2 | `:1694-1696`, `:1773-1775`, `:1226-1228`, `:254-256` | Quatro ganchos dizem "onde ninguém olha / nada quer ser visto" (Sombra, Ermitão, Bugio, Fechado), e os da Sombra e do Ermitão são quase a mesma frase. | Reescrever os ganchos do Ermitão e do Bugio com outra âncora, por exemplo bicho morto que não fede no caso do Ermitão. |
| F6 | P2 | `:2018` (Picanço), `:746-747` (Morcego) | Há três telégrafos de "seguir quem sangra" (Vespa, Ressecado, Picanço), e o "barulho" do Morcego ainda não tem definição em regra de jogo. | Picanço: telégrafo com o espeto ou a despensa, não com sangue. Etapa 5: "barulho" = Cartas jogadas na rodada, diferente do "se mexeu" do Casuar e do "Fôlego restante" do Calado de C-1. |
| F7 | P2 | `:1772` (Ermitão) | O contra-jogo "não deixar corpos perto" repete a Coisa do Esgoto (NA `:1470`). | Pôr primeiro o "acertá-la na troca, nua e mole". |
| F8 | P2 | `:1908-1913`, `:1940` (Enrolado) | "Roda de carroça" rolando pela fila é a imagem da Roda de Mandíbulas (NA). | Usar outra escala, como "do tamanho de uma mó de moinho" ou "de um barril deitado", também na `description`. |

## Correções aplicadas

(o executor preenche)

## Pendências

- Se o coordenador preferir **cortar** em vez de corrigir, os conceitos que cabem nas vagas são
  estes. No lugar da Lagarta (vaga 12, controlador lacaio), nenhum dos cortados cabe sem cair em
  outro par, e por isso recomendo corrigir. No lugar do Besouro (vaga 10, artilharia lacaio), o
  Ouriço de Breu (#32) funcionaria se perder o "sugar luz" do Abafador e virar artilharia de
  espinhos ocos com física torta.
- Para o gate (já pedido na onda 1, pendência (b)): os pares desta onda passaram no U6 e no U7
  porque as frases de mecânica não são comparadas entre fichas e entre regiões. Um U14 sobre
  `mecanica_assinatura.frase`, `contra_jogo` e `gancho`, com comparação entre regiões, teria
  pegado C-1, C-6 e F5.

## Comandos rodados

```text
bash scripts/dev/py.sh scripts/bestiario/lint.py --regiao floresta_sussurros --sem-revisao → 29 fichas · 4 erros (só U1 dos 4 slots, esperado) · 0 avisos
```

## Rodada 2 (commit `c6ef0ff1`, 2026-11-01)

**Veredito final: `APPROVED_WITH_FOLLOWUPS` para as 25 fichas.** Não há bloqueio.

Conferi o diff `87e1a1d2..c6ef0ff1` de `floresta_sussurros.yaml`:

- **C-1 (Calado).** O alvo passou a ser o herói com menos Fôlego, e cada Calado a mais bate mais forte. Saíram o recuo e o "não é visto". Resolvido.
- **C-2 (Abafador).** Enquanto ninguém gasta uma jogada para reacender, os ataques de longe ficam sem mira. Não colide mais com a Onça nem com a Arraia, e combina com o Olho de Pétala, que atira no escuro. Resolvido.
- **C-3 (Besouro).** O estalo vem antes do vapor e marca o chão; o vapor cai ali na rodada seguinte. A física torta está agora na anatomia, no gancho e na arte, e o gancho deixou de usar os ruídos que são da Ave-Imóvel. Resolvido. É uma das melhores ideias da onda.
- **C-4 (Dedos).** Os talos cravados cobram Entropia por Carta até serem arrancados, e a revelação saiu da regra. A lore de Vestra agora bate com `npcs.txt:1548`. Resolvido.
- **C-5 (Bugio).** Quem é solto cai de volta na frente da linha, no meio das criaturas. A regra virou reposicionamento e o par com a Vespa sumiu. Resolvido.
- **C-6 (Lagarta).** A cola une dois heróis, que dividem os golpes e se movem juntos. O gancho saiu da pradaria e a fonte passou a `abismo`. Resolvido.
- **F1, F2, F4, F7 e F8** aplicados. O F5 foi aplicado à Sombra e ao Ermitão, e o telégrafo do Picanço agora fala do espetado.

Ficam como follow-up, sem bloquear:
- **F3 (Virado).** Na Etapa 5, contar revides por número de golpes, não por dano.
- **F6 (Morcego).** Na Etapa 5, definir "barulho" como Cartas jogadas na rodada.
- **F5 residual (Bugio).** O gancho do Bugio (`:1226-1228`) ainda diz "onde ninguém olha". Agora são só dois ganchos assim, o do Bugio e o do Fechado; vale reescrever o do Bugio quando passar por ali.

Quando o integrador gravar, o campo `revisao` das 25 fichas pode ir para `aprovada`.

```text
bash scripts/dev/py.sh scripts/bestiario/lint.py --regiao floresta_sussurros --sem-revisao → 29 fichas · 0 erros · 0 avisos (rodado na árvore de trabalho, que tem uma alteração não commitada em floresta_sussurros.yaml; os 4 U1 dos slots não aparecem nela)
```


---

# Revisão da região: montanhas_afiadas (arquivo original handoffs/SPEC-349-astra-review.md)

# SPEC-349 — Montanhas Afiadas: revisão de unicidade (rodada 1 de 2)

> **Veredito:** `CHANGES_REQUIRED`
> 10 APPROVED e 17 CHANGES.
> - 9 são reskin ou premissa repetida de onda anterior, e precisam de reescrita de corpo, mecânica ou origem.
> - 8 são ajustes pontuais: silhueta, motivo visual ou mecânica que repete outra criatura da própria região.
>
> Nenhuma ficha precisa ser cortada sem conserto: cada uma tem uma correção proposta abaixo.
> **Revisor:** `opus-spec-reviewer` (Opus, spec-reviewer; o autor é outro agente Opus) · **Data:** 2026-11-01
> **Commit revisado:** `b7e989c3` (branch `bst-montanhas_afiadas`)

## Escopo

Fichas revisadas: as 27 não-retro de `data/bestiario/fichas/montanhas_afiadas.yaml`. São 20 `nova` e
7 `reinventada`. Também li os 61 conceitos de `docs/spec349/conceitos-montanhas_afiadas.md`. Os
critérios foram SPEC-349 §2.B (R8–R12), §3.4 (U1–U13) e o checklist §3.9.

**Contra o que comparei:**
- (a) as 27 entre si e com as 6 retro;
- (b) os 33 docs legados de `data/codex/monsters/` com a tag `montanhas_afiadas`, entre eles a
  Águia-das-Lascas, o Poço-de-Gravidade, o Coro-Soterrado, o Eco-Predador, a Toupeira, o
  Verme-Mastigador, o Filho-do-Rei, a Tribo-do-Eco, a Última-Sentinela e o Carneiro-Trovão;
- (c) as fichas não-retro de `nova_arcadia.yaml` (NA) e de `pantano_melancolia.yaml` (PM).

**Segredos:** procurei em todo o texto público (`lore`, `aparencia`, `como_se_luta`, `description`,
`gancho`, `arte`) e no doc de arte. Nada entrega o contrato da Forja Profunda nem o Verme-Primordial;
as menções à Forja ficam nas pistas permitidas de `secrets.txt:445`. G-17 aparece só como fala de
acampamento (Costura de Rancor), o que está correto. Há um detalhe no Braços de Tenaz, registrado como
P2 dentro do item C-12.

**Fora do escopo:**
- números e mecânica fina (Etapa 5);
- Cartas;
- docs Codex gerados, além da conferência de segredo.

**Nome do arquivo:** segue o pedido do coordenador. Ele não segue o padrão de
`scripts/check_handoff_names.py`; se o lint de nomes reclamar, renomeie ou registre a exceção.

## Achados transversais (valem para várias fichas)

- **T1 — "tirar a proteção do jogador" aparece três vezes na região.**
  - Braços de Tenaz arranca peça de armadura e escudo.
  - Língua de Lima lixa armadura e escudo.
  - Tesoura de Cordada corta a correia: "uma proteção deixa de valer".

  Fora da região, o Enxerto da Fornalha (NA) racha a peça e o Cisne de Pátina (PM) tira um grau de
  defesa. Na região, só uma das três pode manter esse efeito. Proposta: fica a Tesoura, porque cortar
  correia e corda é a identidade dela. Tenaz e Língua mudam de mecânica.
- **T2 — o motivo "mãos de mortos" repete entre as Crias.**
  - A Mão da Borda usa a mão humana como isca. Esse é o motivo dela, e ela o mantém.
  - Costura de Rancor: mãos de Goblin agarrando o tronco.
  - Tampão da Câmara: braços saindo do vão.
  - Mastro de Troféus: anda sobre as mãos.
  - Pisador do Salão: os pés são mãos anãs.

  Fora da região, o motivo já está na Cavadeira de Unhas (NA), no Fardo de Espólio (PM), no Regaço da
  Margem (PM) e no Cordão de Medida (PM). Em arte, as Crias da região ficam parecendo uma família só.
  Mastro e Pisador perdem as mãos como locomoção (C-15, C-17). Costura e Tampão mantêm, porque ali os
  braços servem à função.
- **T3 — o bafo e o fôlego repetem como sentido e como contra-jogo.**
  - Lenço do Desfiladeiro: o contra-jogo é cobrir a boca.
  - Saltão de Galeria: o contra-jogo é cobrir boca e nariz ou prender a respiração.
  - Queimado de Frio: percebe pela respiração.

  O Saltão muda (C-7).
- **T4 — R9:** a seção "3. Cortes do revisor" de `docs/spec349/conceitos-montanhas_afiadas.md` está
  "Pendente". Este parecer não edita aquele doc. O autor ou o coordenador deve transcrever para lá a
  tabela de CHANGES abaixo, com o motivo de cada uma.

## Parecer por criatura

| # | id · nome | Veredito | Motivo | Correção proposta |
|---|---|---|---|---|
| 1 | `mon_deitado_na_parede` · Deitado na Parede (`:70`) | **CHANGES** (leve) | **Conceito:** o peso que puxa de lado, o sangue acumulado num flanco e a queda de lado são únicos, e a ligação com o Poço-de-Gravidade é boa. **Problema:** a silhueta e a anatomia repetem a imagem do **Pajem de Obsidiana** (NA `:1393`). No Pajem: "Um criado de libré parado numa parede vertical do corredor"; "Sobe pelas paredes lisas como se fossem chão". No Deitado: "Um homem de pé na parede do corredor"; "Fica de pé na parede como os outros ficam no chão". Os dois têm o mesmo plano (`bipede_ereto`) e a mesma locomoção (`escala_paredes`). Na arte, as duas imagens viram a mesma. | **Silhueta e arte:** deixar de mostrar "de pé na parede" e ler pelo peso torto. O corpo fica pendurado de lado como num gancho invisível, com o flanco roxo e inchado virado para o "chão" dele. Cabelo, braços e mochila caem todos na mesma direção, que é a parede. **Texto:** tirar a frase "como os outros ficam no chão" de `anatomia.texto` e de `lore`. Acrescentar um detalhe que o Pajem não tem, como objetos soltos da cena (pedrinhas, a lanterna da vítima) caindo para o mesmo lado perto dele. |
| 2 | `mon_geodo_da_praga` · Geodo da Praga (`:149`) | **CHANGES** | **Reskin mecânico e de eixos da Mula de Lágrimas** (PM `:1019`). **Eixos:** mesma tripla (`bipede_ereto`, `vidro_cristal`, `sacrificial`) e mesmo arquétipo. **Mecânica:** a mesma explosão ao morrer, que pune quem mata de perto. Na Mula: "quem o matou de perto perde mais". No Geodo: "matá-lo de perto custa caro". **Contexto:** o Lençol de Chaminé (NA) também estoura ao cair. O próprio autor cortou o Engolidor de Brasa por repetir a Mula e manteve este, que repete mais. | **Mantém** a causa, que é o melhor achado da ficha: a Praga de Ferro cristaliza no frio e forma nós de geodo. **Muda** o papel e a mecânica: nada de explosão na morte. Duas opções: (a) **relógio**: perto de calor, um nó amadurece por rodada; maduro, ele o parte com a mão e usa a cavidade de cristal como soco cortante, e o golpe cresce com o número de nós abertos. O contra-jogo é tirá-lo do fogo. (b) **`saqueador`**: arranca o próprio nó e o troca com os Goblins, fugindo; os Goblins aparecem na rodada seguinte. Trocar também o material ou o plano para sair da tripla da Mula: por exemplo `bipede_curvado`, ou `sal_mineral` com os cristais como detalhe. |
| 3 | `mon_cauda_de_atalaia` · Cauda de Atalaia (`:232`) | **APPROVED** | Corpo e uso são únicos: o morto Cinzéu pendurado pela cauda de osso que continuou crescendo e açoita de cima. A ficha bate com a lore (cauda com osso na ponta usada em combate, `races.txt`; sem dor). Não colide com a Águia-das-Lascas (pedra que cai), com o Leque (passada rente) nem com a Centopeia (NA). | — |
| 4 | `mon_queimado_de_frio` · Queimado de Frio (`:311`) | **CHANGES** | **Reskin do Caído do Cadinho** (NA `:1549`). **Corpo:** os dois são `bipede_curvado` de `escoria_fuligem`, com placas pretas rachadas e músculo vermelho vivo nas frestas. No Caído: "músculo continua vermelho... sem pele". No Queimado: "carvão por fora... músculo vermelho e úmido". **Impulso:** o mesmo, procurar calor e encostar ou abraçar corpos quentes. **Mecânica:** a mesma crosta, que fecha quando ele se aquece. **Contato:** o frio que passa por contato repete o Cágado de Geada (PM: "a geada sobe pela mordida"). **Molde:** "morto de frio que caça calor" é molde de manual. | **Mantém** o morto pela geada nas passagens. **Muda** o corpo inteiro: nada de placa preta nem de vermelho por baixo. Exemplo: pele branco-cerosa e translúcida, cheia de bolhas de líquido turvo (a bolha da geladura), cílios e barba presos em gelo, pontas dos dedos pretas só nas falanges. O material passa a ser outro, por exemplo `cera_sebo`; conferir U2 e U3 contra o Estaqueiro (PM). **Muda** a mecânica: nem drenar calor pelo contato nem fechar crosta. Exemplo: ele **apaga o fogo**. Abraça a fonte de calor (tocha, pote de Brasa, quem está ao lado da fogueira) e a cena perde a luz e o calor; quem cai inconsciente no frio sofre mais. A percepção deixa de ser `respiracao` (T3) e passa a `calor`. |
| 5 | `enemy_observador_menor` · Olhos em Volta (`:394`) | **CHANGES** (leve) | **Conceito:** bom e sem segredo. O "algo imenso em qualquer direção" vem de `creatures.txt:41` e de `locations.txt:370`, que são públicos. **Problema:** a mecânica sobrepõe a da **Rã de Lótus** (NA `:2013`). As duas são suporte que anula a vantagem de abertura do jogador: a Rã avisa o primeiro ataque, o Olhos impede flanco e surpresa. | Mecânica nova, coerente com "vê tudo": **expõe a jogada**. Enquanto ele estiver de pé, a Carta preparada do jogador fica visível para os inimigos, e o primeiro inimigo que age escolhe a Reação certa contra ela. Esse efeito é o inverso da Arraia de Lodo (PM), que turva o presságio. O contra-jogo (luz súbita nos olhos que não fecham) continua. |
| 6 | `enemy_wyvern_jovem` · Leque de Costelas (`:480`) | **APPROVED** | Corpo torto legível: costelas soltas da coluna, abertas em leque e afiadas pelo vento. O corte em linha na altura do peito é único. Não é wyvern com outro nome. O R12 foi registrado (Draco) com distância boa. | P2: a frase final "já está do outro lado antes do troco" é idêntica à do Saltão. Fica com o Leque, e o Saltão muda (C-7). |
| 7 | `mon_saltao_de_galeria` · Saltão de Galeria (`:999`) | **CHANGES** | **Mecânica:** o bate-e-volta ("morde e já está do outro lado") repete o Leque (região) e o **Patinador de Óleo** (PM `:383`: "ataca e volta para longe na mesma rodada"). **Contra-jogo:** cobrir boca e nariz é o mesmo do Lenço (T3). **Família:** é um grilo de caverna grande sem nada de Besta Torta no corpo, ao contrário da definição de `story_corpos_do_abismo.md` ("a física do bicho cede antes do corpo"). | **Mantém** o grilo cego de antenas longas e o bando no teto. **Muda** (a) a mecânica para **amontoamento**: cada Saltão que já está agarrado no alvo deixa o próximo salto mais pesado, e com três ele derruba o alvo, que perde a rodada. O contra-jogo é sacudir ou queimar os que estão agarrados. **Muda** (b) a percepção: tirar `respiracao` e usar, por exemplo, `vibracao` das antenas tocando o chão (conferir U3). **Muda** (c) o corpo, para dar um traço torto: o salto pesa menos do que devia, e ele pousa no teto e fica lá como se caísse para cima. Também vale um corpo de pernas com uma articulação a mais, que se dobra ao contrário. |
| 8 | `enemy_minotauro_esqueleto` · Boi de Canga (`:569`) | **APPROVED** | Boi de mina cego com a canga coberta de carne e chifres gastos em placas; a arremetida presa ao trilho é única. Não repete o Carneiro-Trovão (avalanche), a Cabra-Navalha nem a Porca da Queda (NA). O R12 foi registrado (pôneis de mina). | — |
| 9 | `enemy_mimico_bau` · Morador do Caldeirão (`:657`) | **CHANGES** | **Molde de manual:** "objeto que morde quem mexe nele" é o próprio mímico, só mudado de lugar. O texto diz: "Quem procura coisa útil num caldeirão anão leva a pinça". **Silhueta:** objeto carregado com patas saindo por baixo, próxima do **Fardo de Espólio** (PM `:1644`: "escudo velho que anda de lado sobre oito braços"). **Mecânica:** a retaliação ("quem bate leva a pinça de volta") é genérica e já está no Vira-Costas e no Pajem (NA). **Família:** não há nada torto além do tamanho. | **Mantém** o ermitão no caldeirão anão e a dependência do calor das bigornas, que é uma pista permitida. **Muda:** tirar a emboscada de objeto disfarçado e a retaliação. A identidade passa a ser o **calor carregado**: o caldeirão está cheio de brasa e escória do fogão de pedra. **Mecânica:** recolhido, o ferro em brasa queima quem o toca com arma de metal, e a arma fica inutilizável por uma rodada. A cada rodada longe das bigornas o ferro esfria e a defesa cai; ele volta à bigorna para reaquecer, e esse é o relógio da luta. **Torto:** o ventre, mole do calor, fundiu-se ao ferro do fundo, e ele não pode trocar de casa. O R12 do ermitão continua. |
| 10 | `enemy_basilisco_caverna` · Caramujo de Estalagmite (`:745`) | **CHANGES** | **Mecânica igual à do Romeiro de Âmbar** (PM `:139`). No Romeiro: "o âmbar endurece... não troca de lugar até quebrá-lo com um golpe". No Caramujo: "fica preso no lugar até quebrar a crosta". **Molde do slot:** o lore e a composição mantêm o jardim de estátuas do basilisco ("montes de pedra com forma de gente sentada"). | **Mantém** a casca de estalagmite e a gosma que vira pedra, que são imagem forte e não têm cópia. **Muda** a mecânica: a pedra prende a **arma**, não o pé. Quem golpeia o pé mole com lâmina fica com a lâmina presa na crosta, que endurece; a Carta de arma não pode ser jogada até ele soltar a arma, gastando a rodada. O contra-jogo é usar pancada ou haste, e não lâmina. **Tira** de `lore`, `gancho` e `arte` os "montes de pedra com forma de gente". Troque por um detalhe próprio, como ferramentas e lanternas anãs presas na pedra do rastro dele. Conferir U13 contra a Gralha (NA, que rouba Carta). |
| 11 | `enemy_morcego_vampiro` · Lenço do Desfiladeiro (`:834`) | **CHANGES** | **Mecânica igual à do Casaco de Sanguessugas** (PM `:1096`). No Casaco: "fica presa e bebe Fôlego a cada rodada até ser arrancada". No Lenço: "perde ar e força a cada rodada até que alguém o arranque". **Silhueta:** o pano voador que envolve a cara da vítima é o *cloaker* de manual (e o *facehugger*), e `inspiracao: []` não registra a fonte (R12). **Contra-jogo:** repete o do Saltão (T3). | **Mantém** a membrana com mãozinhas nas bordas, que é o traço próprio. **Registra** em `inspiracao` a fonte (*cloaker*/manta de manual) com `distancia`. **Muda** a mecânica para uma de **posição na trilha estreita**: quem está coberto não vê onde pisa. Se atacar ou se mover na rodada, arrisca cair da trilha (perde a rodada e leva dano de queda); se ficar parado, perde só a ação. Isso conversa com o gancho e o lore ("quem cai de uma trilha estreita por falta de ar"), sem repetir o dreno por rodada. |
| 12 | `mon_bexiga_de_respiro` · Bexiga de Respiro (`:917`) | **APPROVED** | O flutuador que sobe no ar dos respiros anões, com coração e nervos visíveis e uma coroa de olhos, é único na região. Os fios que amortecem o braço não repetem nenhum efeito das ondas anteriores. O R12 foi registrado (caravela-portuguesa). | — |
| 13 | `mon_rolador_de_escarpa` · Rolador de Escarpa (`:1078`) | **APPROVED** | Usar a encosta como arma é próprio das Montanhas, e o gancho ("nem toda pedra que desce caiu sozinha") é ótimo. Distinto da Roda de Mandíbulas (NA), que morde em volta da fila; o Rolador quebra a guarda pela linha da encosta. | P2: na arte, evitar que a bola eriçada lembre a Roda. As placas de pederneira e as bordas lascadas devem dominar a imagem. |
| 14 | `mon_chicote_de_fenda` · Chicote de Fenda (`:1157`) | **APPROVED** | Corpo-tábua na fenda vertical, chicotes que tateiam e bote de braços de espinhos de dentro da pedra. É distinto da Aranha-de-Pedra (sem teia e sem camuflagem, como registrado). O "toca e depois golpeia" encosta na Centopeia (NA), que marca e volta, mas o bote de dentro da fenda o diferencia. | P2: pôr na frase da mecânica que o bote **puxa o alvo contra a parede**. Isso separa de vez da Centopeia. |
| 15 | `mon_ladrao_de_lume` · Ladrão de Lume (`:1239`) | **APPROVED** | Roubar a luz e deixar a cena inteira no escuro é efeito de cena, diferente da Gralha (NA, que rouba uma Carta). Tem traço torto: a luz o machuca e ele vai atrás dela. A ligação com a Brasa-Profunda e os guias é de Valoria. | — |
| 16 | `enemy_troll_ponte` · Ponte de Ombros (`:1319`) | **APPROVED** | O Orc que virou passagem é um Cobrado legível e de Valoria (pedágio de Gruumsha). Lutar em cima dele é mecânica única, e o slot do troll foi reinventado sem resto de manual. | — |
| 17 | `mon_bracos_de_tenaz` · Braços de Tenaz (`:1403`) | **CHANGES** | **Enxerto da Fornalha** (NA `:869`): os dois são Cobrados de braço de ferro longo demais que quebram armadura. No Enxerto: "um braço de ferro longo demais"; "racha a peça". No Tenaz: "braços de ferro tão compridos que se arrastam"; "arranca peça de armadura". **Armador de Fosso:** os dois são Cobrados que trocaram as mãos por ferramenta. **T1:** a terceira criatura da região que tira proteção. | **Mantém** o ferreiro dos Últimos Anões na Forja. **Muda** a silhueta: os braços não ficam mais compridos. As tenazes saem do punho, na medida dos braços anões, que já chegam ao chão. O preço passa a ser o **calor**: antebraços com pele de escória vitrificada que segura ferro em brasa sem luva, e as tenazes vivem rubras. **Muda** a mecânica para **desarme quente**: a tenaz fecha na arma ou no escudo do alvo e o aquece, e o item fica inutilizável até esfriar (duas rodadas) ou até ser largado. **P2 (segredo):** tirar "nem para quem" de `lore` e `comportamento`. "Não diz o que forja" basta; o "para quem" aponta direto para o contrato. A pista do tamanho das peças segue permitida (`secrets.txt:445`). |
| 18 | `mon_mapa_de_cicatriz` · Mapa de Cicatriz (`:1482`) | **CHANGES** (leve) | **Conceito:** ótimo e de Valoria. É o guia de tatuagens de rota (Vel-Tharn, `npcs.txt:802`) que a montanha reescreveu, e a mecânica de desviar o movimento é única. **Problema:** a silhueta repete o **Sangrado da Clínica** (NA `:1861`), um homem riscado por inteiro como documento. No Sangrado: "riscado de cortes como um livro de contas". No Mapa: "o corpo inteiro riscado de cordões em relevo como uma parede de mapa". O autor cortou o "Livro de Pele" por isso e manteve a mesma imagem. | **Silhueta:** concentrar o relevo no braço e na mão que apontam. O braço ficou rígido e estendido como agulha de bússola, com os três dedos fundidos num ponteiro, e os cordões convergem para ele. O resto do corpo fica com tatuagens planas, que pulsam. **Texto:** tirar "do pescoço aos tornozelos" e "corpo inteiro riscado". A silhueta passa a ser "um guia de braço esticado e duro apontando, que não abaixa". |
| 19 | `mon_armador_de_fosso` · Armador de Fosso (`:1560`) | **APPROVED** | O Goblin-mineiro dos ganchos e molas que arma travas anãs é distinto da Goblins-Mineiros (legado), por ser especializado e Cobrado. A mão-ferramenta fica com ele, e o Tenaz muda (C-17). | P2: a armadilha disparada por movimento lembra o cordão do Estaqueiro Afogado (PM). Manter na frase o "recuar pelo caminho de onde veio", que é o diferencial. |
| 20 | `mon_cosido_do_fundo` · Cosido do Fundo (`:1638`) | **CHANGES** (leve) | **Costura de Rancor:** os dois são da facção dos bandos Orc e usam o mesmo motivo, "costurado com tendão", dentro da região. Os nomes têm a mesma raiz: *Cosido* e *Costura*. **Mastro de Troféus:** os dois escolhem quem sangra pela percepção `sangue_cheiro`. As mecânicas diferem (perseguir sem largar × segurar), e por isso a correção é leve. | **Troca** o método de selar os olhos: piche quente da boca das passagens ou cera de vela de mina derramada nas órbitas, com crosta preta e dura. **Renomeia** para tirar a raiz *cos-*, por exemplo "Olhos de Piche". **Opcional:** trocar a percepção para `som` ou `vibracao` (o cego que ouve a pedra), conferindo U3, para separar do Mastro. Se mantiver o faro, o contra-jogo com Líquen-de-Brasa queimando segue bom. |
| 21 | `mon_costura_de_rancor` · Costura de Rancor (`:1717`) | **APPROVED** | Chefe de Vhrak legível: tronco de Orc sobre uma massa de Goblins, e as partes se agridem. O G-17 aparece só como fala de acampamento, como pedido. Ficar mais forte enquanto cai tem a virada única da autoagressão, o que o separa do Banhado do Centro (PM). Mantém o motivo de mãos e de costura; os outros cedem (C-15, C-17, C-20). | — |
| 22 | `mon_tampao_da_camara` · Tampão da Câmara (`:1797`) | **CHANGES** | **Premissa repetida da cria de Dorrhen da onda 1**, a **Cavadeira de Unhas** (NA `:1090`). Na Cavadeira: "O Desespero dos que cavam a parede da cela com as unhas". No Tampão: "o Desespero de quem cavou a saída até morrer... unhas gastas até o osso de cavar pedra". É a mesma ideia de demônio, o desespero de cavar para sair com as unhas. **Lore legado:** encosta no Coro-Soterrado (grupo soterrado por deslizamento). | **Mantém** o corpo, que é forte e único: a porta entupida de gente com braços para os dois lados, que tapa a saída. **Muda** a origem: nada de cavar e nada de unhas. Em vez disso, o Desespero de **um grupo inteiro que tentou passar pela mesma porta ao mesmo tempo** quando o teto veio, esmagado no vão. **Tira** "unhas gastas até o osso de cavar pedra" da anatomia; os braços ficam de mãos inchadas e roxas de esmagamento. **Tira** também o deslizamento que fecha a câmara com gente dentro, porque esse é o Coro-Soterrado. O gatilho passa a ser a corrida para a saída. |
| 23 | `mon_tesoura_de_cordada` · Tesoura de Cordada (`:1876`) | **CHANGES** | **Corpo do Rosário de Vértebras** (NA `:197`): os dois são `serpentiforme` de `osso`, e os dois são uma corrente de ossos encaixados como elos ou contas. **Silhueta do Cordão de Medida** (PM `:1329`). No Cordão: "corda grossa esticada... com nós que parecem punhos". Na Tesoura: "uma corda de escalada com um nó a mais". | **Mantém** a Inveja das cordadas e o corte de corda, correia e fivela, que fica como o único efeito T1 da região. **Muda** o plano corporal: nada de serpentiforme nem de corrente. Exemplo: um corpo curto feito de **duas escápulas e dois maxilares articulados como as lâminas de uma tesoura de tosquia abertas**, sobre patas finas de costela, com as pontas cravadas na pedra. **Silhueta:** "uma tesoura aberta do tamanho de um cão, presa na parede ao lado da corda". Conferir U2 e U3 (`quadrupede` ou `hexapode_ou_mais`, `osso`, `saqueador`). |
| 24 | `mon_mastro_de_trofeus` · Mastro de Troféus (`:1953`) | **CHANGES** (leve) | **Conceito:** ótimo e único. É o troféu de traidor de Gruumsha que copia o rosto do sofredor mais próximo. **Problema:** a locomoção "anda sobre as mãos de baixo, como uma lagarta de dedos" soma ao motivo T2 da região, junto com o Pisador e a Costura, e lembra a Cavadeira de Unhas (NA). | **Muda** a locomoção: o mastro **se arrasta pela estaca da base**, que ele crava e arranca do chão a cada passo como um bastão. Também vale **andar sobre os maxilares pregados na base**, que mordem o chão para puxar. As mãos ficam só no alto, para agarrar. Ajustar `silhueta` ("anda sobre as mãos da base"), `anatomia.texto` e `arte`. |
| 25 | `mon_mao_da_borda` · Mão da Borda (`:2032`) | **CHANGES** | **Mesma premissa da cria de Skarath do Pântano**, o **Cordão de Medida** (PM `:1329`). No Cordão: "o resíduo tomou os tendões dos que soltaram a mão de alguém para se salvar". Na Mão: "o resíduo da Traição se junta onde alguém soltou a mão de outro na beira de um penhasco". É a mesma frase de origem para o mesmo demônio. | **Mantém** o corpo, que é bom e único: o disco de couro com braços de ventosa e a mão limpa de isca. Mantém também a mecânica de atacar quem ajuda. **Muda** a origem para outra traição das passagens. Exemplo: o **guia que cobrou e largou o cliente numa borda** no meio da descida. A Traição se demora na confiança de quem esperou o guia voltar, e o resíduo toma o que ficou na borda. Tirar "soltou a mão" de `anatomia.texto`, `lore` e `gancho`. |
| 26 | `mon_lingua_de_lima` · Língua de Lima (`:2113`) | **CHANGES** (leve) | **Conceito:** ótimo. A Vergonha de Veleth apaga os registros da queda, e o gancho com Durgrim é bom. **Problema:** a mecânica "lixa armadura e escudo" é o T1 dentro da região e repete a degradação de defesa do Cisne de Pátina (PM `:1484`) e do Enxerto (NA). | **Muda** a mecânica para o que o conceito pede, **apagar**: cada lambida remove do alvo o último efeito ativo a favor dele, seja bênção, Reação armada, preparo ou bônus de Virtude da rodada. "Apaga o que estava escrito". Conferir U13 contra a Mãos no Rosto (PM), que cala a Virtude: o efeito aqui é remover um efeito já ativo, não bloquear um efeito futuro. O contra-jogo (pegá-lo longe da parede) continua. |
| 27 | `mon_pisador_do_salao` · Pisador do Salão (`:2194`) | **CHANGES** (leve) | **Conceito:** ótimo e único. É a primeira cria de Urath da esteira; pisa em quem está abaixo e derruba quem sobe. **Problema:** "Os pés são mãos anãs abertas" soma ao motivo T2. | **Muda** os pés para algo de Urath ou do Reino que não seja mão. Por exemplo, cada perna termina num **crânio anão emborcado**, que bate no chão polido como um casco, ou numa bigorna-sapata de osso fundido. Ajustar `anatomia.texto`, `aparencia` e `arte`. Na lore, a frase dos Elfos (`races.txt:96`) é pública, o que está correto. |

## Resumo das CHANGES (para o autor)

| id | Tipo | Núcleo da correção |
|---|---|---|
| `mon_geodo_da_praga` | reskin (Mula de Lágrimas) | papel e mecânica novos (relógio dos nós ou saqueador); sair da tripla da Mula |
| `mon_queimado_de_frio` | reskin (Caído do Cadinho, Cágado) | corpo de bolhas de geladura e gelo; mecânica "apaga o fogo"; percepção `calor` |
| `enemy_mimico_bau` | molde de manual (mímico) + Fardo | sem disfarce de objeto; caldeirão em brasa, desarme por calor e relógio de reaquecer |
| `enemy_basilisco_caverna` | mecânica igual (Romeiro) + estátuas | a pedra prende a lâmina, não o pé; tirar as estátuas de gente |
| `enemy_morcego_vampiro` | mecânica igual (Casaco) + *cloaker* sem R12 | registrar R12; mecânica de queda na trilha |
| `mon_saltao_de_galeria` | mecânica e contra-jogo repetidos | amontoamento que derruba; percepção sem respiração; traço torto |
| `mon_bracos_de_tenaz` | silhueta e mecânica (Enxerto) + T1 | braços sem alongar, preço do calor, desarme quente; tirar "nem para quem" |
| `mon_tampao_da_camara` | premissa de Dorrhen repetida (Cavadeira) | corrida para a porta esmagada; sem unhas nem cavar |
| `mon_tesoura_de_cordada` | corpo (Rosário) + silhueta (Cordão) | corpo-tesoura de escápulas e maxilares, não serpentiforme |
| `mon_mao_da_borda` | premissa de Skarath repetida (Cordão) | origem: guia que largou o cliente na borda |
| `mon_deitado_na_parede` | silhueta (Pajem) | ler pelo peso torto, não "de pé na parede" |
| `enemy_observador_menor` | mecânica ≈ Rã de Lótus | expõe a Carta preparada do jogador |
| `mon_mapa_de_cicatriz` | silhueta (Sangrado) | relevo só no braço-ponteiro |
| `mon_cosido_do_fundo` | motivo e raiz de nome (Costura) | olhos selados com piche; renomear |
| `mon_mastro_de_trofeus` | T2 (mãos) | anda pela estaca ou pelos maxilares |
| `mon_lingua_de_lima` | T1 (armadura) | mecânica de apagar o último efeito ativo |
| `mon_pisador_do_salao` | T2 (mãos) | pés de crânio ou de bigorna-sapata |

Depois das correções:
- rodar de novo `lint.py --regiao montanhas_afiadas` (U2, U3, U6, U13), porque eixos vão mudar no Geodo, no Queimado, no Saltão, na Tesoura e talvez no Cosido;
- atualizar o tabuleiro `vagas:` no mesmo commit;
- regerar os docs Codex e o doc de arte;
- transcrever os motivos para a seção 3 do doc de conceitos (T4).

A rodada 2 revisa só as 17 CHANGES.

## Correções aplicadas

(nenhuma; aguardando o autor)

## Pendências

- O nome deste arquivo foge do padrão de `check_handoff_names.py`. O coordenador decide se renomeia.
- Os campos `revisor_unicidade: opus-spec-reviewer` e `revisao: aprovada` só entram nas fichas depois da rodada 2.

## Comandos rodados

```text
bash scripts/dev/py.sh scripts/bestiario/lint.py --regiao montanhas_afiadas --sem-revisao
  → 33 fichas · 7 erro(s) · 1 aviso(s). Os 7 erros são o U1 resolve_bestiary_name nos slots, esperado
    antes de gerar_docs; o aviso é o U4 cabra/cabra entre duas retro (legado).
grep de segredo (contrato|verme|forjam para|selou|Coroa de Pressão|teme) na ficha, nos conceitos e
  no doc de arte → nenhuma ocorrência em texto público.
```

---

## Rodada 2 (final)

> **Veredito da rodada 2:** `CHANGES_REQUIRED`, com correções mínimas e exatas, aplicáveis sem nova
> rodada.
> - 12 das 17 passaram a APPROVED.
> - 5 ainda pedem CHANGES. Em três delas (Morador, Caramujo, Geodo) a colisão nasceu das correções
>   que eu mesmo propus na rodada 1: o T1 de "tirar a proteção" virou um "inutilizar a arma ou
>   depender do calor" repetido na região. A falha foi minha, e a correção vai abaixo.
>
> Aplicadas as cinco correções abaixo ao pé da letra, o veredito final é **`APPROVED`** para as 27, e
> o autor pode gravar `revisor_unicidade: opus-spec-reviewer` e `revisao: aprovada`.
> **Commit revisado:** `b534eb23` · **Data:** 2026-11-01

O lint deu `33 fichas · 7 erro(s) · 1 aviso(s)`. Os 7 erros são o U1 `resolve_bestiary_name` dos
slots, porque `data/bestiary.json` foi restaurado, e podem ser ignorados como combinado; o aviso é o U4
das duas cabras retro. O doc antigo `mon_cosido_do_fundo.md` não existe mais, e o
`mon_vedado_de_piche.md` foi gerado. As duas observações do autor foram aceitas: o Queimado pune quem
fica parado em vez de apagar o fogo, e os papéis novos (Lenço `emboscador`, Queimado `controlador`,
Geodo `bruto_de_linha`) passam.

| # | Criatura | R2 | Motivo |
|---|---|---|---|
| 1 | Deitado na Parede | **CHANGES** | Só a `silhueta` mudou. `anatomia.texto` (`:91`), `comportamento` (`:95`), `lore` (`:122-123`), `aparencia` (`:125`) e `arte.visual` (`:134`) continuam com "de pé na parede como os outros ficam no chão" e "perpendicular ao chão", que é a imagem do Pajem. |
| 2 | Geodo da Praga | **CHANGES** (mínima) | O corpo novo é bom e a tripla saiu da Mula. **Problema:** o contra-jogo "tirá-lo de perto do fogo" repete o do Morador do Caldeirão na mesma região ("afastá-lo das bigornas"). O Caído do Cadinho (NA) também depende de calor. |
| 4 | Queimado de Frio | **CHANGES** (mínima) | O corpo de bolhas, cera e gelo está resolvido. **Problema:** o "abraço que prende quem descansa e o deixa sem agir" repete o **Regaço da Margem** (PM: "acolhe o alvo no colo... não age; quem se debate sai, quem descansa fica"). |
| 5 | Olhos em Volta | APPROVED | A Carta preparada à mostra é única, e é o inverso da Arraia de Lodo. |
| 7 | Saltão de Galeria | **CHANGES** (só texto) | A mecânica de amontoamento e o "cai para cima" estão bons. **Problema:** `lore` (`:1057`) abre com a mesma frase do Deitado ("há câmaras em que o peso não puxa para baixo"), e o `gancho` repete a ideia. Duas criaturas da região ficam com a mesma origem. |
| 9 | Morador do Caldeirão | **CHANGES** | A mecânica "queima a arma de metal que o toca, inútil por uma rodada" é o efeito do **Braços de Tenaz** ("o item fica inútil até esfriar") e do **Caramujo** (a arma fica presa). São três criaturas da região com "sua arma não serve", e o Tenaz é o dono natural desse efeito. |
| 10 | Caramujo de Estalagmite | **CHANGES** (mínima) | A lâmina presa e o rastro de ferramentas estão bons. **Problema:** o efeito "a Carta de arma não pode ser jogada até gastar uma rodada" é o mesmo do Tenaz (ver #9). |
| 11 | Lenço do Desfiladeiro | APPROVED | O risco de queda para quem se move coberto é único. O R12 foi registrado com distância. É o inverso do Queimado (um pune mover, o outro pune parar), o que funciona bem junto. |
| 17 | Braços de Tenaz | APPROVED | Silhueta própria e desarme quente. O "nem para quem" saiu. Ele fica como o único "item inutilizado" da região. |
| 18 | Mapa de Cicatriz | APPROVED | O relevo só no braço-ponteiro ficou longe do Sangrado. |
| 20 | Vedado de Piche | APPROVED | A máscara de piche, o nome e o id são novos. Não há mais costura nem raiz *cos-*. |
| 22 | Tampão da Câmara | APPROVED | A corrida para a porta não tem unhas nem cavar, e o gatilho é outro que o do Coro-Soterrado. |
| 23 | Tesoura de Cordada | APPROVED | O corpo-tesoura de escápulas e maxilares não é serpentiforme nem corda. |
| 24 | Mastro de Troféus | APPROVED | A estaca e os laços de tendão tiraram as mãos. |
| 25 | Mão da Borda | APPROVED | A origem nova é o guia que larga o cliente. Ele encosta no Mapa de Cicatriz (outro guia que falha), mas um é o cliente traído e o outro é o guia corrompido, e a lore já marca "nem todo guia é Cinzéu". Aceito. |
| 26 | Língua de Lima | APPROVED | "Apaga o último efeito a favor" é único e fiel à Vergonha. |
| 27 | Pisador do Salão | APPROVED | Os pés de crânio anão tiraram as mãos. |

### Correções mínimas exatas (aplicar e fechar, sem nova rodada)

**C2-1 · `mon_deitado_na_parede`**
- `anatomia.texto`: trocar "Fica de pé na parede como os outros ficam no chão, com os dedos das mãos abertos em garra contra a pedra." por "Vive tombado contra a parede, pendurado de lado como roupa num prego torto, com os dedos das mãos abertos em garra contra a pedra."
- `comportamento`: trocar "perpendicular ao chão," por "tombado de lado,".
- `lore`: trocar "Os Deitados andam pelas paredes das câmaras idênticas como os outros andam no chão." por "Os Deitados vivem tombados nas paredes das câmaras idênticas, como roupa pendurada de lado."
- `aparencia`: trocar "Explorador humano de pé numa parede, perpendicular ao chão;" por "Explorador humano tombado de lado contra uma parede, pendurado como roupa num prego torto;".
- `arte.visual`: trocar "de pé numa parede vertical como se fosse chão." por "tombado de lado contra uma parede vertical, pendurado como roupa num prego torto."
- Regerar o doc de arte e o Codex.

**C2-2 · `mon_geodo_da_praga`**
- `contra_jogo`: trocar o texto inteiro por "Golpear o nó que está inchando antes que amadureça: partido verde, ele só sangra e não vira caco; quem o parte assim tira dele um punho."
- `mecanica_assinatura.frase` continua igual. O calor fica como o gatilho do relógio na lore, mas o contra-jogo deixa de ser "afastar do calor".

**C2-3 · `mon_queimado_de_frio`**
- `mecanica_assinatura.frase`: "Pune quem para: quem se defende ou espera na rodada tem as pernas agarradas e endurece de frio, e na rodada seguinte não pode jogar Carta de defesa nem de Reação; quem se move não é alcançado."
- `comportamento`: trocar "deita sobre quem está parado e o abraça, e o frio do corpo dele entra nas juntas da vítima até ela não conseguir dobrar os braços." por "agarra as pernas de quem está parado, e o frio do corpo dele entra nas juntas da vítima até ela não conseguir erguer a guarda."
- `lore`: trocar "e deitam por cima" por "e agarram as pernas".
- `telegrafo`: "{nome} se arrasta até os pés de quem está parado e estende as mãos brancas devagar."
- Conferir U13 contra o Cágado de Geada (PM), que tira a Carta de ataque: aqui o efeito é a Carta de defesa e de Reação, e a assinatura difere.

**C2-4 · `mon_saltao_de_galeria`** (só texto)
- `lore`: trocar a primeira frase por "Nas galerias de cima da Boca há grilos de caverna que pesam ao contrário: o corpo deles cai para cima, e eles vivem de patas no teto."
- Na sequência, trocar "Vivem de patas no teto, do tamanho de cães, cegos," por "São do tamanho de cães, cegos,".
- `gancho`: "Nas galerias da Boca há grilos que caem para cima; vivem no teto e caem em cima da gente, um por vez, até ser demais."
- `anatomia.texto`: trocar "Nas câmaras de peso torto, o corpo aprendeu a cair para cima:" por "O corpo pesa ao contrário e cai para cima:".

**C2-5 · `enemy_mimico_bau` (Morador) e `enemy_basilisco_caverna` (Caramujo)**
- **Morador**, `mecanica_assinatura.frase`: "Recolhido no caldeirão, aguenta o golpe; cada golpe no ferro derrama brasa no chão em volta, e quem estiver ao lado dele na rodada seguinte se queima. Longe das bigornas a brasa acaba e a defesa cai."
- **Morador**, `comportamento`: trocar "Encosta o ferro em brasa em quem chega perto e se recolhe quando é atacado." por "Se recolhe quando é atacado, e cada pancada no ferro sacode brasa para fora da borda."
- **Morador**, `contra_jogo`: "Afastá-lo das bigornas e golpeá-lo de longe ou com haste, sem ficar ao lado dele; frio, o caldeirão escurece e o ventre preso ao fundo fica sem defesa."
- **Morador**, `lore`: trocar "e encostam o ferro rubro em quem chega perto" por "e, golpeados, sacodem brasa no chão em volta".
- **Caramujo**, `mecanica_assinatura.frase`: "A gosma vira pedra em volta da lâmina que o golpeia: o dono larga a arma, que fica na pedra até o fim da luta, ou é arrastado até o pé dele na rodada seguinte."
- **Caramujo**, `comportamento`: trocar "Enquanto o dono puxa, o caramujo chega." por "Ou o dono larga a arma, ou o caramujo o puxa até o pé."
- A arma que fica para trás é a mesma que a lore já descreve (ferramentas presas no rastro).
- Conferir U13 depois. As três assinaturas passam a ser distintas: Tenaz inutiliza o item por um tempo, o Caramujo faz o jogador escolher entre perder a arma e ser arrastado, e o Morador cria uma zona de brasa no chão.

### Comandos rodados (rodada 2)

```text
bash scripts/dev/py.sh scripts/bestiario/lint.py --regiao montanhas_afiadas --sem-revisao
  -> 33 fichas · 7 erro(s) [U1 resolve_bestiary_name dos slots, bestiary.json restaurado] · 1 aviso (U4 cabras retro)
grep de frases antigas (de pé na parede, perpendicular, emborcado, forma de gente, cosid, mãos de baixo
  [só na Costura, aceito], mãos anãs, soltou a mão, unhas gastas, nó a mais, nem para quem, peso não puxa)
  -> o resto está só no Deitado (C2-1) e no Saltão (C2-4)
```


---

# Revisão da região: ophidia (arquivo original handoffs/SPEC-349-astra-review.md)

# SPEC-349 — revisão de unicidade (onda 12 · Ophidia)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (spec-reviewer, papel de unicidade §3.9; não é o autor) · **Data:** 2026-11-01 · **Commit revisado:** `8225f263` (branch `bst-ophidia`)
>
> Nome do arquivo: veio do coordenador. Ele **não passa** em `scripts/check_handoff_names.py`
> (padrão `SPEC-NNN[-papel]-tipo.md`). Antes do pouso, renomear ou juntar ao
> `handoffs/SPEC-349-independent-review.md`.

## Escopo

- `data/bestiario/fichas/ophidia.yaml`: 20 fichas `status: nova` e 7 retro, que só têm eixos.
- `docs/spec349/conceitos-ophidia.md`: 46 conceitos e os cortes do autor.
- Comparei contra: as 27 fichas de Nova Arcádia e as 30 do Pântano (nome, silhueta, família, eixos
  e a frase da `mecanica_assinatura`), o Codex `data/codex/monsters/` com a tag ophidia (7 docs),
  os nomes em `data/bestiary.json` e a lore (`creatures.txt:1621-1646`, `locations.txt:278-296`,
  `items.txt:1338-1655`, `rumors.txt:248-253`, `factions.txt:562-578` na `main`). Também o segredo
  E-14 em `main:lore_nova/secrets.txt:389-397`.
- Ficaram fora: os números (Etapa 5), a voz (D7) e a parte técnica (é do Sol). Os `refs` conferi por
  amostra na `main`: Vhrak, Skarath, Dorrhen e Veth estão em `npcs.txt:229/336/276/261`, e
  `items`, `rumors` e `locations` resolvem. No worktree essas linhas caem em outros trechos, como a
  própria convenção já registra.

## Parecer por criatura (§3.9: 1 reskin · 2 frase exclusiva · 3 é de Valoria · 4 física e luta · 5 sem segredo)

| # | Criatura | 1 | 2 | 3 | 4 | 5 | Veredito | Motivo · correção |
|---|---|---|---|---|---|---|---|---|
| 1 | Nadador Escaldado | ok | ok | ok | ok | ok | **APPROVED** | O corpo cozido e sem pele é inédito. Nota: o ciclo "perde força longe do calor" lembra o Caído do Cadinho (`nova_arcadia.yaml:1585`). A diferença está boa (racha em vez de travar), e convém mantê-la assim na Etapa 5. |
| 2 | Ossada de Pomes | ok | ok | ok | ok | ok | **APPROVED** | O osso de pomes que boia e assobia é exclusivo. A iniciativa lembra de leve o Sangrado da Clínica, mas a mecânica difere. |
| 3 | Cabeleira de Vidro | **falha** | ok | ok | ok | ok | **CHANGES** | A mecânica repete o Pajem de Obsidiana (`nova_arcadia.yaml:1428`): mesma família, mesmo material vidro, "quem bate de perto leva o corte de volta" e o contra-jogo "de longe". **Correção:** fazer o perigo vir do **vento**. Quem fica a sotavento leva os fios soltos toda rodada, sem contato; só o golpe de perto vindo de barlavento é seguro. Assim o espinho reativo vira um quebra-cabeça de posição. Tirar também o recurso "os mapas não concordam em nada, menos nisso" (`:275-276`), que repete o do Mastro (#19); fica só no chefe. |
| 4 | Vazado da Maré | ok | ok | ok | ok | ok | **APPROVED** | A arma que prende no furo é guarda com assinatura própria. Usa a Água-que-Some (`items.txt:1625`) sem resolvê-la. |
| 5 | Desbotado da Névoa | ok | ok | ok | ok | ok | **APPROVED** | Nota de arte: o ponto focal deve ser o **coração**, não os olhos, para não ler como a Arraia de Lodo ("só se vê quando um olho gira", Pântano). |
| 6 | Turu de Casco | ok | ok | **fraco** | ok | ok | **CHANGES** | É o *Teredo* em escala de homem. Não tem "física quebrada" nem corrupção no corpo (§1, família 2), e a referência das ondas 1 e 2 tem gancho físico em todas as Bestas. **Correção:** o que ele digere **não sai**: nem serragem, nem fezes, nem resto, e o corpo não engorda. A madeira entra e deixa de estar em qualquer lugar. Isso amarra o "sem destroços" sem responder ao mistério. Tirar a "serragem molhada" da `arte.visual` (`:533`). |
| 7 | Vela sem Barco | ok | ok | **fraco** | ok | ok | **CHANGES** | É uma caravela-portuguesa com cor errada. O engano de "parecer barco" já vem do bicho real, que leva nome de navio. **Correção:** dar a ela uma física quebrada: **veleja contra o vento** (ou parada no vento). É por isso que, de longe, é tomada por barco manobrando para a ilha. Na mecânica, ela se aproxima mesmo quando o vento afastaria. |
| 8 | Lagarto Espirrador | ok | ok | **fraco** | ok | ok | **CHANGES** (leve) | É a iguana-marinha quase literal, e a única torção é o que ela come. **Correção:** pôr a entropia no espirro ou no corpo. O pó de cor errada **não assenta**: fica parado no ar como uma cortina onde foi espirrado, e quem atravessa erra. Assim a artilharia vira negação de área, e o bando inteiro não fica só "espirra junto". |
| 9 | Bucho de Praia | ok | ok | **fraco** | ok | ok | **CHANGES** | É um pepino-do-mar gigante com túbulos de Cuvier, sem nada quebrado. **Correção:** os fios **encurtam quando puxados**, e quem força se prende mais. Soltam quando o preso fica parado uma rodada. É legível e muda o contra-jogo. |
| 10 | Cobra de Sangria | ok | ok | ok | ok | ok | **APPROVED** | Presa invertida, bolsa e volta para o oeste: um corpo reescrito com propósito alheio. Os boatos usados são públicos (`rumors.txt:253`). |
| 11 | Escorpena de Basalto | ok | ok | **falha** | ok | ok* | **CHANGES** | É o peixe-pedra, até no "anda sobre as nadadeiras" (*Inimicus* faz isso de verdade). Fica sem nada de Valoria no corpo. **Correção:** o veneno **nunca é o mesmo duas vezes**: o mesmo peixe faz dormir, doer ou nada, por espinho (sorteio determinístico na Etapa 5). Isso amarra `items.txt:1342` ("efeitos imprevisíveis") e mantém o mistério. *No item 5 está ok, mas a lore (`:927`) faz o vendedor dizer que "o de verdade" sai dele: deixar claro que é argumento de venda, por exemplo "o de verdade, diz quem vende". |
| 12 | Tatuzinho de Afogado | ok | ok | **fraco** | ok | ok* | **CHANGES** | É um isópode menor que um *Bathynomus* real (25 cm). **Correção:** a bola **rola para cima**, contra a inclinação da praia e contra a maré, na direção de quem sangra. Usa a locomoção `rola` e se lê na arte. *O mistério precisa de dúvida no fim: "Desde então, ninguém no Cais pergunta mais pelos corpos" (`:1010`) e o gancho "achou uma resposta" (`:992`) fecham a questão. Trocar por algo que a deixe aberta, como "a rede tinha passado perto, não dentro". |
| 13 | Doente de Encomenda | ok | ok | ok | ok | ok* | **APPROVED** (com ajuste) | É forte e é de Brekmar. *E-14: a lore libera o "pagam mais por quem está doente" (`secrets.txt:397`), mas a ficha diz que ele pegou **a Ferrugem** *porque* Ophidia paga, e isso aproxima demais "Ophidia ↔ Praga". **Ajuste:** a escolha da Ferrugem é do sindicato ("a doença mais fácil de pegar no Cais e a que demora mais para matar"), e o emissário paga por "doente", sem nome (`:1054`, `:1086-1087`). |
| 14 | Puxado do Oeste | ok | ok | ok | ok | ok | **APPROVED** | Agulha-bússola no corpo, empurra para a água. Vende o "inalcançável" (`factions.txt:572`). Nota: é o único elo público Mercadores ↔ Ophidia, e o E-14 liga os Mercadores às amostras. Não pôr amostras, sangue ou catálogo em nada dele. |
| 15 | Vigia de Cor Errada | ok | ok | ok | ok | ok | **APPROVED** | O vigia de cabeça para baixo e olhos de fumaça é exclusivo. **P2:** tirar o "pescoço entorta para o oeste" (`:1215`, `:1246`), porque o oeste já é traço do Puxado e da Cobra. Os olhos e os pés de gancho bastam. |
| 16 | Trépano de Borda | ok | **falha** | ok | ok | **risco** | **CHANGES** | (a) A mecânica "perde uma Carta preparada" repete a Gralha de Crematório (rouba a preparada) e cai junto da Rêmora (#20). (b) Com a Cobra, faz a segunda criatura que "coleta sangue e leva". (c) "Para quem mais trabalham, eles não dizem" (`:1331-1332`) acena para um empregador oculto na mesma onda que pôs os Mercadores em Ophidia: é a metade do E-14 que não pode aparecer. **Correção:** cortar essa frase. A mecânica passa a tirar a **Vitalidade máxima** (o cilindro de osso) até o descanso, e o frio de Éter dele cresce com isso. Nada de cartas e nada de fuga. |
| 17 | Arpéu de Braços | **falha** | ok | ok | ok | ok | **CHANGES** | A "corda viva de tendões trançados" é o material e o desenho do Cordão de Medida (Pântano, `:1344-1345`), e o próprio autor cortou o #45 por isso. **Correção:** a corda vira um **cabo de abordagem de cânhamo de verdade**, encharcado, que a carne do nó engoliu e puxa. Sem tendão. O resto (âncora de quatro antebraços, "preso só ataca") fica. |
| 18 | Mão de Socorro | **falha** | **falha** | ok | ok | ok | **CHANGES** (substituir o conceito) | Reskin conceitual do Cordão de Medida: **mesmo demônio** (Skarath) e mesmos eixos (`padrao`/`emboscador`/`tatico`/`carne_exposta`/`calor`). É a mesma ideia de "apoio falso estendido a quem precisa, que puxa para o fundo", feita de membros de afogados. O Cordão chega a terminar "numa mão aberta". Fere o R29 e o próprio critério do autor no #45. **Correção:** outro conceito de Traição, com plano e material novos. Sugestão: uma cria que **senta no banco do bote como remador**, de costas para a proa, conta como "do lado do jogador" na 1ª rodada (não pode ser alvo) e dá o primeiro golpe pelas costas, ignorando a defesa. Outra saída: trocar de demônio itinerante ainda livre (Daruun, Veleth ou Maalrek, sem repetir plano/material das crias deles nas ondas 1 e 2). |
| 19 | Mastro dos Últimos | ok | ok | ok | ok | ok | **APPROVED** | É o melhor chefe da onda: a silhueta lê de longe e "anda caindo" é novo. É diferente da Fila de Grilhões, que é horizontal e guarda. **P2:** a lore afirma como fato o que fica "nas praias das ilhas" (`:1566-1567`), um lugar de onde ninguém volta. Pôr no condicional ("o que dizem que ele deixou"). O fecho pelos desenhos já faz isso bem. |
| 20 | Rêmora de Convés | ok | **falha** | ok | ok | ok | **CHANGES** | A mecânica é a do Convidado de Cera, cria do **mesmo** demônio (Veth, `nova_arcadia.yaml:1195`): ele tranca a Carta mais cara, ela inutiliza a preparada mais forte. **Correção:** "quer que o outro não tenha" passa a negar **ganhos**. Enquanto está grudada, toda cura, reforço ou Fôlego recuperado do alvo vai para ela, que engorda. Morta, não devolve nada. Corpo e palato ficam como estão. |

**Contagem:** 9 APPROVED (um com ajuste no texto), 11 CHANGES e nenhum CORTE seco. A #18 pede
**conceito novo** na mesma vaga, ou em vaga de outro demônio itinerante.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `ophidia.yaml:1454-1473` | A Mão de Socorro é reskin conceitual do Cordão de Medida (Skarath, Pântano). | Conceito novo (ver #18). |
| P1-2 | P1 | `ophidia.yaml:1629-1631` | A mecânica da Rêmora é a do Convidado de Cera (Veth, NA). | Negar ganhos, não cartas (#20). |
| P1-3 | P1 | `ophidia.yaml:253-256` | A mecânica da Cabeleira é a do Pajem de Obsidiana. | Perigo pelo lado do vento (#3). |
| P1-4 | P1 | `ophidia.yaml:1380`, `:1426` | A corda de tendões do Arpéu é o material do Cordão de Medida. | Cabo de cânhamo engolido (#17). |
| P1-5 | P1 | `ophidia.yaml:461-1034` | 5 das 7 Bestas são o bicho real em escala (Turu, Vela, Bucho, Escorpena, Tatuzinho) e a 6ª (Lagarto) só muda a comida. Falta a "física quebrada" da família 2 (§1). | Um gancho físico por criatura (#6–#9, #11, #12), uma frase na anatomia e a mesma ideia na mecânica. |
| P1-6 | P1 | `ophidia.yaml:1308-1311`, `:1331-1332` | Trépano: mecânica de Carta repetida e aceno ao empregador oculto (E-14). | Vitalidade máxima e cortar a frase (#16). |
| P2-1 | P2 | `ophidia.yaml:1054`, `:1086` | Doente: "Ferrugem *porque* Ophidia paga" aperta o E-14. | A escolha da doença fica com o sindicato (#13). |
| P2-2 | P2 | `ophidia.yaml:1006-1010`, `:992` | O Tatuzinho fecha o mistério dos corpos. | Deixar a dúvida no fim (#12). |
| P2-3 | P2 | `ophidia.yaml:271-276` × `:1568-1570` | O recurso "todos os mapas concordam só nisso" aparece duas vezes. | Fica só no Mastro. |
| P2-4 | P2 | `ophidia.yaml:1215` | O "puxado para o oeste" aparece em três corpos (Puxado, Vigia, Cobra). | Tirar do Vigia. |
| P2-5 | P2 | onda inteira | Cinco efeitos de "prender" (Vela, Bucho, Arpéu, Mastro, Vazado). | Na Etapa 5, cada um com status distinto: queimadura em área, aperto por força, só-atacar, agarrão colateral e penalidade na arma. Nenhum pode repetir "não se move" puro. |
| P2-6 | P2 | `ophidia.yaml:263` | "cabelo de Pele" se lê como "pele" (de corpo). | Escrever "cabelo-de-Pelé (Pele, deusa havaiana)". |

## Cortes do autor e a contagem

- **Os cortes se justificam em quase tudo.** Destaques: #6 e #10 (o Caído do Cadinho e o Banhado
  ficam protegidos), #22 (não explica a Sereia), #27 (não responde "O Que Move as Ilhas"), #42
  (o Abraço de Rivais já tinha sido cortado duas vezes) e #46 (Urath tem lugar fixo).
- **Há uma incoerência.** O #45 caiu por "corda/tábua de carne = Cordão de Medida", mas o #38
  (Arpéu) manteve a corda de tendões e o #39 (Mão de Socorro) manteve o conceito do Cordão. O
  critério do autor estava certo; faltou aplicá-lo às duas que ficaram.
- **Os 20 se sustentam** como piso, desde que a #18 receba conceito novo e não seja só cortada.
  Cortar sem repor deixa a onda em 19, abaixo da cota (§1, meta 20–25). As outras 10 CHANGES são
  ajustes de anatomia e mecânica dentro da mesma vaga e não mexem nos eixos do tabuleiro. A #16 e a
  #20 mudam só a mecânica.
- **Mistério e E-14.** O conjunto respeita "não ter resposta": as explicações concorrentes são
  sempre atribuídas a alguém. As exceções são o Tatuzinho e a frase do Mastro (P2). Nenhum campo
  público explica o veneno nem liga os Mercadores às amostras, e o risco está nos três acenos
  somados (Doente, Trépano, Puxado), resolvidos por P1-6 e P2-1.

## Correções aplicadas

Nenhuma (só leitura). Depois da correção do autor, voltam para mim as #3, #6–#9, #11, #12, #16,
#17, #18 e #20. Só então o campo `revisao` vira `aprovada`.

## Pendências

- Nome deste arquivo fora do padrão de `check_handoff_names.py`: o coordenador renomeia ou junta.

## Comandos rodados

```text
grep nome/silhueta/familia/frase em nova_arcadia.yaml e pantano_melancolia.yaml → comparação de eixos e mecânicas
git show main:lore_nova/secrets.txt (389-397) → texto do E-14 e "como usar sem revelar"
git show main:lore_nova/{npcs,items,rumors,locations,factions}.txt (linhas dos refs) → refs conferidos por amostra
lint/pytest → não rodados (lint já verde segundo o coordenador; revisão só de leitura)
```

---

## Rodada 2 (commits `5733f4dc` e `6e3ab486`)

> **Veredito da rodada 2:** `CHANGES_REQUIRED`, só pela criatura nova (Ninho dos Mergulhadores).
> As 13 correções da rodada 1 estão **APPROVED**.
> O nome do arquivo agora é `SPEC-349-astra-review.md`, que passa no `check_handoff_names.py`. A
> nota de nome lá no topo ficou obsoleta.

Conferido: `git diff 8225f263 -- data/bestiario/fichas/ophidia.yaml` (+185/−157). O grep
confirma que não restam "Para quem mais trabalham", "tendões trançados" nem pescoço voltado
para o oeste no Vigia. O ref do Ninho, `npcs.txt:197`, cai na Natureza de Daruun na `main`
("espera que venham").

| # | Criatura | Rodada 2 | Nota |
|---|---|---|---|
| 3 | Cabeleira de Vidro | **APPROVED** | Agora o perigo é de posição, pelo vento, e não se confunde mais com o Pajem. P2 (não bloqueia): a lore ainda abre com "os mapas trazem, quase todos, o desenho do mesmo homem" (`:272-276`), o mesmo recurso do Mastro. Se o autor quiser, troca por "um desenho que se repete em mais mapas do que deveria". |
| 5 | Desbotado da Névoa | **APPROVED** | O coração virou o ponto focal da arte. |
| 6 | Turu de Casco | **APPROVED** | "Nada sai, e ele não engorda": tem física quebrada e o mistério continua aberto. |
| 7 | Vela sem Barco | **APPROVED** | Veleja contra o vento, a fuga a favor do vento é alcançada, e a arte mostra isso pela fumaça e pelas cristas das ondas. |
| 8 | Lagarto Espirrador | **APPROVED** | A cortina de pó que não assenta é negação de área própria. |
| 9 | Bucho de Praia | **APPROVED** | Os fios que encurtam quando puxados mudam o contra-jogo, e o preso solta ficando quieto. |
| 11 | Escorpena de Basalto | **APPROVED** | O veneno sorteado pela semente e sem repetição seguida é de Valoria. "Argumento de vendedor" deixa o boato aberto. |
| 12 | Tatuzinho de Afogado | **APPROVED** | A bola que rola para cima é legível, e a dúvida voltou ("uma rede roída não explica um barco inteiro"). |
| 13 | Doente de Encomenda | **APPROVED** | "Doente, sem dizer de quê", e a Ferrugem fica como escolha do sindicato. O E-14 não aperta mais. |
| 15 | Vigia de Cor Errada | **APPROVED** | O pescoço estica para a frente e não aponta mais para o oeste. |
| 16 | Trépano de Borda | **APPROVED** | Tira Vitalidade máxima até o descanso, sem Carta e sem fuga, e o aceno ao empregador saiu. |
| 17 | Arpéu de Braços | **APPROVED** | O cabo de cânhamo engolido pela pele está claro na arte e no `evitar`. |
| 19 | Mastro dos Últimos | **APPROVED** | Agora fica no condicional. |
| 20 | Rêmora de Convés | **APPROVED** | Nega ganhos (cura, reforço e Fôlego). Ficou distinta do Convidado de Cera. |
| 18 | **Ninho dos Mergulhadores** (novo, Daruun) | **CHANGES** | Ver abaixo. |

### Ninho dos Mergulhadores: o que falta

A ideia da isca é boa e é de Ophidia: a pedra de cor errada **verdadeira** num mercado de
fraudes, e Daruun, que "espera que venham". Mesmo assim, ela repete o **Fardo de Espólio**, cria
do **mesmo demônio** no Pântano (`pantano_melancolia.yaml`, Daruun):

1. **Material.** Os dois são feitos de membros de quem morreu na água por cobiça. O Fardo tem
   "oito braços de afogado, cada mão aperta o que achou"; o Ninho, "braços e pernas de
   mergulhadores trançados". É também a terceira cria da onda feita de membros de afogados, depois
   do Arpéu e do Mastro.
2. **Mecânica.** O Fardo "cobra pedágio: no início da rodada o alvo escolhe pagar Fôlego ou deixar
   o Fardo curar"; o Ninho, "a cada rodada preso, o jogador escolhe pagar em ouro ou levar um golpe
   inteiro". É o mesmo pedágio por rodada com escolha binária, e a Escritura Rastejante (Daruun,
   Nova Arcádia) também cobra por rodada.

O comparativo do autor ficou só nos eixos (serpentiforme/couro e hexápode/carne). O §3.9, item 1,
olha também o conceito e a mecânica.

**Correção mínima.** Manter a pedra verdadeira, o recife e o "espera que venham", e mudar duas
coisas:

- **Material:** nada de membros. Uma opção: os **pulmões** dos mergulhadores, sacos cinzentos e
  inflados presos ao recife em volta da pedra, que se fecham sobre quem mete a cabeça ou o braço e
  sugam o ar. Assim o preço vira o fôlego de quem mergulha. Outra: o que for, desde que não sejam
  braços, mãos nem corpos agarrados. Atenção ao clichê da ostra com pérola e do mímico (§1, P1).
- **Mecânica:** nada de pedágio por rodada. Uma opção: o aperto **cresce com o que o preso
  carrega de valor**, seja ouro ou itens; quem larga o que tem dentro do ninho sai. É Cobiça pura e
  troca o "pagar para sair" por "largar para sair". Ajustar `contra_jogo`, `como_se_luta`,
  `description` e `telegrafo` de acordo.

Feito isso, a vaga 18 volta para mim só para conferir o Ninho.

### Contagem

São 20 novas, dentro da cota. Nenhum corte. Depois da correção do Ninho, o campo `revisao` pode
virar `aprovada` nas 20.


---

# Revisão da região: pradaria_ruinas (arquivo original handoffs/SPEC-349-astra-review.md)

# SPEC-349 (onda 3: Pradaria das Ruínas): revisão de unicidade

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (`spec-reviewer`, revisor de unicidade, §3.9) · **Data:** 2026-11-01 · **Commit revisado:** `02006968`

## Escopo

- Branch `bst-pradaria_ruinas`, commit `02006968`: `data/bestiario/fichas/pradaria_ruinas.yaml` (21 novas, o slot `enemy_esqueleto_legiao_antiga` e 11 fichas retro) e `docs/spec349/conceitos-pradaria_ruinas.md`.
- Comparei com: os nomes, as descrições e as frases de assinatura de `nova_arcadia.yaml` e `pantano_melancolia.yaml`; os 36 docs `data/codex/monsters/*` com a tag `pradaria_ruinas`; e a lore (somente leitura): `races.txt` (Elfos, Cinzéus, Lycans), `npcs.txt` (demônios, Grum), `secrets.txt` e `factions.txt:348-354`.
- Ficou de fora: os números, o baralho, a arena e a qualidade da prosa. Esta revisão é só de unicidade (§3.9, itens 1 a 5) e de vazamento de segredo.
- Direção do dono, que não reabro: ameaças físicas; 4 famílias; nada de reskin, nem variante de matilha, solitária ou meio-humana; nada de Lycan, Vampiro, Orc, Goblin ou dragão como criatura nova; nenhum segredo no texto público.

## Resumo por criatura

| # | Criatura | Veredito | Pedido |
|---|---|---|---|
| 1 | Vertedor de Areia | APPROVED (1 correção factual) | Em `:78`, "as quatro mãos de dedos longos" deve virar "as mãos de quatro dedos longos". Elfo tem 4 dedos (`races.txt:41`), não 4 mãos, e o texto alimenta a arte. |
| 2 | Vidrado da Colina | **CHANGES (P1)** | Vazamento de segredo e assinatura repetida da Pajem de Obsidiana (achados P1-1 e P1-2). |
| 3 | Costas de Alicerce | APPROVED | Nenhum. |
| 4 | Osso que Pegou | **CORTE** | É um Lycan por contágio, e a assinatura repete o Caído do Cadinho (achado P1-3). |
| 5 | Fuçador da Semente | APPROVED | Nenhum. |
| 6 | Nadador de Pedra | APPROVED | Nenhum. |
| 7 | Cobra de Légua | CHANGES | O gancho repete o da Serpente-da-Grama-Alta do Codex (achado P2-1). |
| 8 | Rodante de Espinhos | **CHANGES** | A assinatura é a do Rosário de Vértebras (NA), com o mesmo contra-jogo (achado P1-4). |
| 9 | Pernalta das Colunas | APPROVED | Nenhum. |
| 10 | Lagarto de Mudas | APPROVED | Nenhum. |
| 11 | Bode sem Freio | **CORTE** (ou reescrita total) | O aríete é de manual, e o "embalo que não acaba" divide a identidade com o Rodante (achado P1-5). |
| 12 | Carregador de Ganchos | CHANGES | "Puxa e prende" repete a Fila de Grilhões (NA) e o prender da Cobra (achado P2-2). |
| 13 | Leitor de Cativos | **CHANGES** | "Desfaz a jogada preparada" é a Gralha de Crematório (NA), com o mesmo contra-jogo (achado P1-6). |
| 14 | Profanador Cravejado | CHANGES | O ciclo roubar, fugir e devolver ao cair é o da Gralha de Crematório (achado P2-3). |
| 15 | Pulmão de Frases | **CORTE** | É o Eremita-Louco somado ao Pó-Sussurrante do Codex, no corpo do Fole de Costela (achado P1-7). |
| 16 | Desfiado de Vaelorn | APPROVED | Nenhum. |
| 17 | Atirador de Olhos Vítreos | APPROVED | Nenhum. |
| 18 | Égua de Costas | **CHANGES** | A assinatura é o Regaço da Margem (cria de Solvhara no Pântano), e a volta da égua morta é o Corcel-Espectral (achado P1-8). |
| 19 | Cabeça Acima | APPROVED | Opcional: tirar o "devolve com força maior" (lembra o Vira-Costas). |
| 20 | Chifres Travados | **CHANGES** | O giro que atinge todos em volta é a assinatura da Roda de Mandíbulas, chefe de NA (achado P1-9). |
| 21 | Costura das Duas Cidades | CHANGES | O habitat `pr_solvhen` contraria a regra de segredo do próprio autor (achado P2-4). |
| 22 | Capim de Couraça (slot) | CHANGES | A assinatura de resistir a lâmina é a do Curtido da Turfeira (slot do Pântano); o vento, que é a identidade da criatura, não está na carta (achado P2-5). |

Placar: 9 APPROVED (Vertedor incluído, com a correção) · 10 CHANGES · 3 CORTES.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `pradaria_ruinas.yaml:153`, `:174`, `:185`, `:188-192`, `:20` (paleta) | **Vazamento de segredo.** O "Reino da Colina Cinza", a "Guarda Real" e o reino humano que Malagor queimou só existem em `secrets.txt:66` e na "História real" de Grum (`npcs.txt:35`), que são justamente a base do segredo do testamento e da herdeira (`secrets.txt:319`, `npcs.txt:2425`). Nenhum doc público de `data/` cita a Colina Cinza. Hoje, a `description`, a `lore`, o `gancho` e a paleta expõem ao jogador o reino, a guarda e a noite da queda. | Desnomear em todo o texto público, inclusive `aparencia`, `arte` e paleta: "uma guarnição humana que estava no alto de um morro da Pradaria quando Malagor passou". Sem "Colina Cinza", "Reino", "Guarda Real" ou "último Rei". O nome "Vidrado da Colina" pode ficar, porque "colina" sozinha é genérica. Manter a âncora só em `refs`. |
| P1-2 | P1 | `pradaria_ruinas.yaml:167-172` | A assinatura (lâmina solta lascas que cortam quem bateu, pancada trinca) e o contra-jogo (impacto, não lâmina) repetem a **Pajem de Obsidiana** (NA): "quem o golpeia de perto leva o corte das placas de volta" e "golpes de impacto, não de lâmina". O material também é vidro. | Tornar assinatura o que só ele tem: o **reflexo do sol no vidro**. Por exemplo: de frente e com sol, quem o ataca erra ou perde a precisão, e ele sempre se vira para o lado do sol. O contra-jogo fica: atacar de costas para o sol, à noite, ou sujar ou quebrar a face da garrafa. Tirar as lascas que voltam. A pancada pode continuar como fraqueza secundária, sem ser a carta. |
| P1-3 | P1 | `pradaria_ruinas.yaml:293-368` | **Osso que Pegou → CORTE.** O contágio Lycan é "farpas de osso injetadas" (`races.txt:525`). A criatura é um humano em quem "as farpas pegaram" ossos de Lycan, com fome de osso (o frenesi de cálcio dos Lycans, `races.txt:522`) e "sem ciclo". Ou seja, um Lycan permanente: Lycan como criatura nova, numa variante meio-humana, as duas coisas vetadas pelo dono. O próprio autor cortou o #7 como "Lycan de quatro patas". Além disso, a assinatura (a armadura cresce a cada rodada, então é preciso acabar depressa pelo músculo exposto) é a do **Caído do Cadinho** (NA), e o visual de placas sobre músculo exposto já aparece no Caído do Cadinho, no Bagre de Varal e no Banhado do Centro. | Cortar e repor a vaga 4 (elite, bruto de linha, Reescrito, Pradaria aberta) com um corpo que não seja placas sobre músculo. Depois, rodar `--vagas` de novo. Sementes possíveis: (a) um Andarilho que dormiu ferido na **Grama-Navalha** (Codex), e as lâminas de capim duro brotaram pelas feridas dos antebraços e das costas, como foices que ceifam a linha (assinatura: corte em arco que pega dois alvos; o fogo queima as lâminas); (b) um nômade que dormiu sobre uma "colina que anda" (**Caçador-Antes-dos-Nomes**, público) e acordou com o torrão e o capim do dorso do bicho crescidos sobre os ombros (é bruto pelo peso de chão; cuidar para não colidir com a turfa do Pântano). O gancho do Osso Pintado pode migrar para a nova criatura, sem Lycan. |
| P1-4 | P1 | `pradaria_ruinas.yaml:623-628` | A assinatura do Rodante (o espinho cravado marca, os outros acertam mais fácil, e o contra-jogo é arrancar mesmo perdendo a vez) é **literalmente** a do **Rosário de Vértebras** (NA): "deixa uma farpa de osso no alvo, e todo ataque seguinte contra quem carrega a farpa acerta mais fácil; contra-jogo: arrancar a farpa (gastar a ação)". | Ancorar a assinatura no que é dele, a audição e a direção contra o vento. Por exemplo: **persegue o barulho**, de modo que quem jogou carta de ataque ou pesada na rodada vira o alvo de todos os Rodantes, e quem se defende ou espera não é perseguido. Outra opção: chega sempre pelo lado de onde vem o vento, o que anula a defesa preparada para a frente. Tirar a marca por espinho. |
| P1-5 | P1 | `pradaria_ruinas.yaml:812-883` | **Bode sem Freio → CORTE.** É o carneiro de investida de manual: bate em linha reta, rompe defesa e fica tonto na parede. A física quebrada, um embalo que não diminui, divide a identidade com o Rodante, que rola contra o vento e morro acima sem perder velocidade. Os contra-jogos são gêmeos ("chão plano e fechado, sem embalo" e "parede atrás de você"). A frase "o bicho cujo embalo não acaba" serve para os dois, e por isso o item 2 do §3.9 falha. A ligação de lore também é fraca (só `creatures.txt:440`). | Cortar e repor a vaga 11 (lacaio, quebra-defesa, Besta Torta). Se o autor preferir reescrever, a regra é **sem embalo e sem investida**. Semente de reescrita: a cunha de chifre nunca para de crescer e **crava**, de modo que o bode morde ou fura o escudo e não solta, e se o alvo largar a defesa ele sai com ela. Semente de troca: uma ave-martelo das colunas que bate duas vezes no mesmo ponto da defesa até rachar. Também é preciso que não colida com a Pernalta (ave). |
| P1-6 | P1 | `pradaria_ruinas.yaml:995-999` | O Leitor "lê a jogada preparada: ela é desfeita", com o contra-jogo "não preparar nada perto dele". É a **Gralha de Crematório** (NA): "rouba a Carta preparada; contra-jogo: não preparar nada enquanto ela ronda". Na própria região, a Costura também "desfaz a defesa e o reforço". | Tirar o "desfeita". A assinatura deve ser o que é só do Vrel, a **memória compartilhada**: enquanto os palpos seguram a cabeça do alvo, os Vrel em campo sabem a próxima jogada dele (ganham uma Reação gratuita contra ela, ou o presságio deles se ajusta a ela), e o alvo seguro perde Fôlego (ele é drenador). Contra-jogo: tirar o preso do alcance ou cortar os palpos. |
| P1-7 | P1 | `pradaria_ruinas.yaml:1113-1185` | **Pulmão de Frases → CORTE.** O ataque (o pó das frases, que paralisa quem respira, e "os locais cobrem o rosto") é o **Pó-Sussurrante** do Codex, quase palavra por palavra. O portador ("vive nas ruínas e acredita guardá-las") é o **Eremita-Louco das Ruínas** do Codex. O plano de corpo (peito que vira fole e solta nuvem, controlador) é o **Fole de Costela** (NA). Nada nele é próprio. | Cortar e repor a vaga 15 (lacaio, controlador, Cobrado). Semente: **Cinzéu de cauda-laço**. Os guerreiros Cinzéus usam a cauda como membro de combate (`races.txt:232`); num eremita sem dor, o Éter alongou a cauda numa chicotada de vértebras que **derruba**: o alvo perde o movimento da próxima rodada, mas não é preso. Assim não colide com Cobra nem Carregador, e também não com o Chicote Cru cortado, que era serpentiforme. |
| P1-8 | P1 | `pradaria_ruinas.yaml:1369-1374`, `:1356`, `:1376` | A assinatura da Égua (encosta, deita o peso, o alvo fica preso e sem fôlego até não levantar) é a do **Regaço da Margem**, a cria de Solvhara no Pântano ("embala quem deita até não levantar"), e ecoa o Velório de Sal (NA, Tristeza, imobiliza). Três crias da Tristeza com a mesma imobilização são reskin. A ficção do cavalo morto que volta é o **Corcel-Espectral** do Codex, e o gancho parafraseia o Cavalo-Selvagem-Cinza. | O corpo pode ficar: a cabeça virada para trás tem silhueta ótima. Trocar a assinatura por uma que nasça dessa cabeça. Proposta: **coice para trás**. Ela só olha de onde veio, então ataca quem se afasta, recua ou passa por trás, e nunca quem está à frente. É o luto que não deixa ir, e o contra-jogo passa a ser ficar de frente para ela. Para a ficção, trocar a égua morta por uma égua **viva** que ficou ao lado do dono morto e cujo pescoço torceu de tanto olhar para trás, onde ele caiu. Isso evita o Corcel-Espectral. Reescrever o gancho sem a frase do Codex. |
| P1-9 | P1 | `pradaria_ruinas.yaml:1517-1521` | O giro dos dois corpos, que atinge todos em volta, é a mesma assinatura da **Roda de Mandíbulas** (NA, também chefe): "uma volta inteira em torno da fila: cada cabeça morde um alvo diferente". Os dois são chefes que fazem dano em área girando. | Tirar a assinatura dos **dois corpos opostos**, que é a identidade da criatura. Proposta: **cabo de guerra**. A cada rodada o nó é arrastado para o lado do corpo menos ferido e atropela quem está desse lado. Ferir os dois corpos por igual trava o nó e o deixa exposto. A segunda metade atual (quando um corpo cai, o outro acelera) pode ficar. |
| P2-1 | P2 | `pradaria_ruinas.yaml:556-558` | O gancho ("os locais nunca saem das trilhas conhecidas; uma das razões é a cobra") repete a última frase da **Serpente-da-Grama-Alta** do Codex. Isso põe a Cobra no lugar narrativo da Serpente. O corpo e a assinatura são próprios, e a `lore` já marca a diferença ("há cobras de veneno… e há esta"). | Reescrever o gancho com uma razão que seja só dela. Por exemplo, a história de que já seguiram uma a manhã toda sem achar o fim, que hoje está no `comportamento`, ou o costume dos Andarilhos de cortar a cabeça sem procurar o resto. |
| P2-2 | P2 | `pradaria_ruinas.yaml:918-922` | "Fisga, puxa para junto e o fisgado não se afasta enquanto a corrente estiver presa." A primeira metade é a **Fila de Grilhões** (NA: "puxa o alvo para junto de si e, enquanto ele está preso à fila…"), e o autor já cortou o #11 por isso. A segunda metade (preso) é o mesmo verbo da Cobra de Légua, na mesma região. | Tirar o "não se afasta" e usar os **muitos ganchos**. Proposta: atira vários de uma vez e puxa dois alvos para junto dele, um contra o outro, o que amontoa a fila e serve de deslocamento, sem amarra. O contra-jogo de cortar a corrente continua válido. |
| P2-3 | P2 | `pradaria_ruinas.yaml:1070-1074` | O ciclo de arrancar uma peça, fugir cavando e só devolver ao cair, com o contra-jogo "derrubá-lo antes que fuja", tem a mesma estrutura da **Gralha de Crematório** (NA: "rouba a Carta… se a Gralha cai antes de fugir, a Carta volta; matá-la antes de ela sair do alcance"). A metade própria dele é cravar a peça na pele e endurecer. Visual: a "pele rachada como porcelana com luz violeta" repete o Vertedor (mesma região) e o Quebrado de Vitrine (NA), e a "gola de cristal turvo" lembra o Sorvedouro do Código. | Fazer a assinatura ser a **pele cravejada**: cada peça arrancada vira defesa nele, e um golpe pode **arrancar uma peça da pele**, o que fere, devolve o item e baixa a defesa. Tirar o "foge cavando e devolve ao cair". Recomendado: tirar a porcelana e a gola e deixar a leitura nas joias afundadas sob a carne fechada, que é a silhueta única dele. |
| P2-4 | P2 | `pradaria_ruinas.yaml:1601`, `:1621`, `:53` (vaga 21) | O doc de conceitos (§ intro) diz "nenhuma Cria de Apetite tem Solvhen como habitat", por causa do segredo de Solvhen como sonho de Solvhara (`npcs.txt:244`). A Costura (cria de Veth) tem `habitat: [pr_vaelorn, pr_solvhen]`. Cria de demônio dentro de Solvhen é um fio que o jogador puxa até a "dona do conforto". | Trocar `pr_solvhen` por `pradaria_ruinas` (as "estradas entre as cidades" já cabem na Pradaria aberta), na ficha e na vaga 21. O texto "entre Vaelorn e Solvhen" pode ficar. A assinatura, que desfaz o que está de pé sem tomar nada, é distinta o bastante do Convidado de Cera (NA, que tranca a carta mais cara) e aprovo. |
| P2-5 | P2 | `pradaria_ruinas.yaml:1672-1677`, `:1678-1680` | A carta se chama "passo do vento", mas a frase é sobre lâmina e ponta passarem pelo capim. Resistir a lâmina é a assinatura do **Curtido da Turfeira** (slot do Pântano: "a lâmina escorrega e o corte não abre") e também a da Pajem e a do Vidrado. O gancho e a lore ("andam contra quem estiver no campo", mortos da batalha do Céu Vermelho) encostam no **Soldado-Sem-Guerra** do Codex ("atacando qualquer um que cruze o campo"). | Assinatura **do vento**: ele só avança e bate nas rodadas em que o vento sopra a favor (alternância telegrafada), e quem fica a favor do vento o obriga a andar contra, ou seja, a perder a ação. O fogo continua como fraqueza. No gancho e na lore, dizer que ele não defende campo nenhum: é um corpo que o vento empurra. Isso já está no `comportamento` e deve ir para a frente. |

### Observações sem pedido (para o autor ponderar)

- **Cabeça Acima e Pernalta** dividem o eixo "altura nas ruínas, ponto fraco embaixo". O corpo (ave e humanoide) e a assinatura separam bem os dois. Só é preciso cuidar que a arte do Cabeça Acima não fique "figura magra altíssima" igual à Pernalta.
- **Desfiado**: o custo próprio do salto lembra o Pavio e o Enxerto (NA, que se ferem). O núcleo, porém (pagou para não sentir dor e os Ferimentos não o atrasam), é dele e tem lore exata (`races.txt:75`). Aprovado.
- **Nadador de Pedra** é o espelho deliberado da Cavadeira de Unhas (NA): nada na pedra e não na terra, e a onda desloca todos. Aprovado. O gancho cita só "alguma coisa da pradaria", sem se dizer a Coisa-nos-Alicerces, e está correto.
- **Costas de Alicerce** cita a Coisa-nos-Alicerces, que é `public` no Codex. Não vaza nada.
- **Vertedor**: a ampulheta usada é a da vida élfica, que é pública (`races.txt:45`). Não toca a Ampulheta de Vaelorn nem a Aerwen. OK.
- **Atirador**: o texto diz "enxerga o calor", e o eixo é `luz`. É coerente com a fraqueza (fogo e luz o cegam) e não peço mudança.
- Muitos ganchos parafraseiam a última frase do doc do Codex de origem (Chifres → Auroque-Ruína, Égua → Cavalo-Selvagem-Cinza, Cobra → Serpente). Como âncora isso é bom. Só vira problema quando a criatura nova toma o papel narrativo do doc (Cobra, Égua).

## Cortes e substitutos sugeridos

| Corte | Vaga | Substituto sugerido |
|---|---|---|
| Osso que Pegou | 4 (elite, bruto de linha, Reescrito) | Andarilho da Grama-Navalha (lâminas de capim duro crescidas nas feridas) ou o nômade do torrão da colina que anda. Nenhum conceito cortado no doc serve: #6 e #7 caem no mesmo veto da Praga dos Ossos, e #10 e #11 já colidiam com NA. |
| Bode sem Freio | 11 (lacaio, quebra-defesa, Besta Torta) | Reescrita do bode como "cunha que crava e arranca a defesa", sem embalo, ou ave-martelo de golpe duplo no mesmo ponto. Dos cortados, o #19 (Lesma de Argamassa) só serviria se o autor resolver a lentidão e a colisão de "pedra" com o Nadador. Não recomendo. |
| Pulmão de Frases | 15 (lacaio, controlador, Cobrado) | Cinzéu de cauda-laço, que derruba sem prender (`races.txt:232`). O #45 (Chicote Cru) foi cortado por ser serpentiforme e de Maalrek; esta é outra ideia, num corpo Cinzéu bípede. |

Depois dos cortes e das trocas de assinatura, rodar de novo `lint.py --vagas` e `--regiao pradaria_ruinas` (U2, U3, U7 e U13) e devolver a ficha para uma segunda leitura só das 13 criaturas marcadas.

## Correções aplicadas

Nenhuma ainda (o autor aplica).

## Pendências

- O autor (Opus) aplica os 3 cortes e as 10 mudanças. O revisor de unicidade relê só essas 13 criaturas.
- O nome deste arquivo segue o pedido do coordenador, não o padrão `<papel>-<tipo>` de `scripts/check_handoff_names.py`. Se o lint reclamar, o coordenador renomeia.

## Comandos rodados

```text
bash scripts/dev/py.sh scripts/bestiario/lint.py --regiao pradaria_ruinas --sem-revisao → 33 fichas · 1 erro (U1 do slot, esperado) · 7 avisos (só entre fichas retro)
grep visibility nos docs Codex da região (Coisa-nos-Alicerces, Semente-do-Vazio etc.) → todos public
grep "Colina Cinza" em lore_nova/ e data/ → só npcs.txt:35, npcs.txt:2425 e secrets.txt:66/319; nenhum doc público
```

---

## Rodada 2 (commit `885593f9`, última)

> **Veredito da rodada 2:** `CHANGES_REQUIRED`, mínimo, só em 2 criaturas. As outras 11 estão aprovadas.

Escopo: `git diff 02006968..885593f9 -- data/bestiario/fichas/pradaria_ruinas.yaml`. Revi as 3 novas (Vestido de Gafanhotos, Besouro de Alavanca e Cauda Emendada), o Vidrado reescrito (agora Vidrado do Morro) e as 9 alteradas pedidas na rodada 1.

| Criatura | Veredito R2 | Motivo / pedido |
|---|---|---|
| Vertedor de Areia | APPROVED | A anatomia foi corrigida ("as mãos de quatro dedos longos"). |
| Vidrado do Morro (`mon_vidrado_do_morro`) | APPROVED | `grep "Colina Cinza"` na ficha deu 0. O texto público fala só de "um morro" e de "guardas", e a paleta foi generalizada. A âncora secreta ficou só em `refs`. A assinatura "sol no peito" é própria, e o contra-jogo (sol nas costas, noite ou nuvem) também. |
| **Vestido de Gafanhotos** (nova, vaga 4) | **CHANGES** | O corpo (enxame de Gafanhoto-de-Bronze vestindo um lavrador) é bom e não é Lycan. A assinatura, porém, junta duas que já existem: "cada golpe que leva solta uma revoada que morde quem bateu" é dano de volta reativo, o mesmo eixo da **Pajem de Obsidiana** (NA), que barrei no Vidrado na rodada 1; e "a armadura afina a cada golpe" é o **Banhado do Centro** (Pântano: "cada golpe que recebe arranca uma placa: perde defesa"). Também não dá para "jogar parte do enxame num alvo para morder por rodadas", porque esse é o **Casaco de Sanguessugas** (Pântano). **Mínimo:** a assinatura deve vir do fato de que *o enxame é a criatura e o homem é só o vestido*. Proposta: **quando ele cai, o enxame sai e se agarra no inimigo vivo mais próximo, que ganha a armadura de cascas**. Fogo ou fumaça no corpo caído impede a migração. Tirar o "morde quem bateu" e o "afina a cada golpe". O contra-jogo de fogo continua. |
| **Besouro de Alavanca** (nova, vaga 11) | **CHANGES** | Física, legível e boa. Mas "a armadura do alvo fica aberta **pelo resto da luta**" é o efeito do **Portão que Morde** (NA): "quebra a defesa dele em metal ou couro para o resto do combate". **Mínimo:** tirar a permanência. A placa sai **torta e pendurada**: o alvo pode gastar a ação para encaixá-la de volta, e enquanto não encaixa, cada besouro abre mais. Isso mantém o "em grupo" e o "fere pouco", que são dele. Alternativa, também aceita: a alavanca age na **cobertura**, e não na armadura. Ele vira a laje, a tampa ou o escudo plantado atrás do qual o alvo estava, e o alvo perde essa proteção. |
| Cauda Emendada (nova, vaga 15) | APPROVED | É a semente da rodada 1, bem resolvida: derruba sem prender e foge saltando. Não colide com a Cobra nem com o Carregador. Observação sem pedido: "vértebras de mortos emendadas" é também a imagem do Rosário de Vértebras (NA). Na arte, a leitura deve ser *a cauda de um Cinzéu, longa demais*, e não um colar de vértebras. O `evitar` já ajuda. O habitat `pr_solvhen` está OK, porque não é cria. |
| Cobra de Légua | APPROVED | O gancho agora é dela (o pastor que seguiu o corpo da manhã à tarde). |
| Rodante de Espinhos | APPROVED | A assinatura "rola para quem fez barulho" é própria. A marca por farpa (Rosário) saiu. |
| Carregador de Ganchos | APPROVED | Agora é "tranco que entrega a presa aos caçadores", sem amarra. Ficou distinto da Fila de Grilhões e da Cobra. |
| Leitor de Cativos | APPROVED | Lê e conta ao agrupamento, sem desfazer nada, e o contra-jogo é trocar de plano. Ao escrever a carta (Etapa 5), não usar "o inimigo defende de graça o 1º ataque", que é a **Rã de Lótus** (NA). O efeito deve ser a resposta dos Vrel *mostrada no presságio*. |
| Profanador Cravejado | APPROVED | Relíquias como armadura que se arranca. O ciclo da Gralha saiu, e a porcelana e a gola também. |
| Égua de Costas | APPROVED | Coice em quem se afasta ou passa por trás, e égua viva junto ao dono morto. Saiu do Regaço e do Corcel-Espectral. |
| Cabeça Acima | APPROVED | Tirou o "devolve com força maior". A fixação no agressor é dele. |
| Chifres Travados | APPROVED | Cabo de guerra entre os dois corpos. O giro (Roda de Mandíbulas) saiu. |
| Costura das Duas Cidades | APPROVED | `pr_solvhen` saiu da ficha e da vaga 21. |
| Capim de Couraça (slot) | APPROVED | A assinatura do vento entrou no lugar da resistência a lâmina. O gancho não defende campo, então ficou distinto do Soldado-Sem-Guerra. |

### Achados da rodada 2

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-R2-1 | P1 | `pradaria_ruinas.yaml:325-329`, `:316-319`, `:338`, `:350-352` | A assinatura do Vestido é dano de volta (Pajem, NA) mais armadura que afina por golpe (Banhado, Pântano). | O enxame migra para o inimigo vivo mais próximo quando ele cai, e o fogo impede. Ajustar `frase`, `comportamento`, `description`, `como_se_luta` e `telegrafo`, se preciso. |
| P1-R2-2 | P1 | `pradaria_ruinas.yaml:847-850`, `:863`, `:874` | "Armadura aberta pelo resto da luta" é o Portão que Morde (NA). | Placa torta reparável com uma ação, acumulando por besouro, ou alavanca sobre a cobertura. |

Depois dessas duas correções, as 22 estão aprovadas pela unicidade. Não precisa de rodada 3 de leitura completa. Basta o coordenador conferir as duas `frase` contra esta tabela e rodar o lint de novo.

### Comandos rodados (rodada 2)

```text
git diff 02006968..885593f9 -- data/bestiario/fichas/pradaria_ruinas.yaml → 3 novas + 10 alteradas lidas
bash scripts/dev/py.sh scripts/bestiario/lint.py --regiao pradaria_ruinas --sem-revisao → 33 fichas · 1 erro (U1 do slot, esperado) · 7 avisos (retro)
grep -c "Colina Cinza" data/bestiario/fichas/pradaria_ruinas.yaml → 0
```


---

# Revisão da região: selva_xylos (arquivo original handoffs/SPEC-349-astra-review.md)

# SPEC-349 — revisão de unicidade (onda Selva de Xylos, rodadas 1 e 2)

> **Veredito (rodada 2, final):** `APPROVED_WITH_FOLLOWUPS` (22/22 APPROVED; 1 follow-up P2 de nome). Rodada 1: `CHANGES_REQUIRED` (13 APPROVED · 9 CHANGES).
> **Revisor:** Opus (spec-reviewer, papel de unicidade §3.9) · **Data:** 2026-11-01 · **Commit revisado:** `a3343d60` (r1) · `8649e747` (r2)
>
> Atenção ao nome do arquivo: o coordenador pediu este nome, mas ele **não passa** em
> `tests/test_handoff_names.py` (o padrão é `SPEC-NNN[-sol|astra|terra|luna]-<tipo>.md`).
> Antes do pouso: renomear o arquivo, fundi-lo num handoff válido ou incluí-lo em `LEGACY`.

## Escopo

Revisei as 21 fichas novas e o slot adotado `enemy_vinha_estranguladora` em
`data/bestiario/fichas/selva_xylos.yaml`, além de `docs/spec349/conceitos-selva_xylos.md`.
Comparei com as 8 retro da região, com a seção da Selva em `lore_nova/creatures.txt:982-1125`
(que gera os docs `monsters/`), com `races.txt:378-430` (Hospedeiros) e `races.txt:509-530`
(Lycans), `secrets.txt:96-104`, `locations.txt:150-215`, `npcs.txt` (Thessavar, Maalrek, Veth,
Dorrhen), `items.txt` (Resina-Viva, Néctar), `rumors.txt:335`, e com os nomes, silhuetas e
`mecanica_assinatura` de `nova_arcadia.yaml` e `pantano_melancolia.yaml`.
Fora do escopo: os números (Etapa 5), a arena e o lint, que segundo o coordenador já está verde.
Não rodei pytest.

## Vereditos por criatura

| id | Veredito | Motivo |
|---|---|---|
| mon_lamelas_de_ferrugem | CHANGES | O corpo repete o Arame Vivo (NA): doente terminal da Ferrugem, curvado, com as veias do pescoço e dos braços projetadas para fora da pele e as mãos rígidas. É a terceira aplicação da fórmula "doente da Ferrugem + material da região", depois de Arame Vivo e Romeiro de Âmbar. Além disso, a prosa pública fica a um passo do segredo C-07 (ver S-1). |
| mon_ariete_de_medula | CHANGES | A cunha de crânio é única. Mas a lore, o gancho e o comportamento ("antes nunca subiam, agora sobem", fuga do fundo) repetem o Escavador quase palavra por palavra, e o motivo da fuga aparece em 4 fichas. Precisa de um impulso próprio. |
| mon_lacado_de_hifas | APPROVED | Os laços brancos de hifa sobre a ferida de Morrakh e a marca em quem rompe um laço não existem em nenhuma outra ficha. Ver nota N-1 (sobreposição leve com o Sangrado da Clínica). |
| mon_recusado_do_ciclo | APPROVED | Morto seco que a selva recusa, com um círculo de chão nu onde não há cura. A identidade é única e está bem ancorada no rumor. P2: o eixo `material: cinza` rotula como cinza um corpo que só tem cor de cinza (ver N-2). |
| mon_remendado_de_osso | CHANGES | Com "crânio de predador sobre o rosto", placas sobre músculo, "fome de osso" e salto de predador, a ficha vira um Lycan com corpo de Hospedeiro, ou seja, a variante "meio-humana" de Lycan que a direção do dono proíbe. Também encosta no Hospedeiro-Profundo ("a colmeia os chama, eles não respondem"). A ideia das camadas de osso e pele é boa e deve ficar. |
| mon_tamandua_de_ponte | APPROVED | Fica pendurado sob as pontes e puxa a vítima com uma língua de 10 m. Silhueta e mecânica são únicas, e a lore das pontes está correta (`races.txt:418`). |
| mon_lagarta_da_hora | APPROVED | A metamorfose inteira acontece dentro da luta, em 3 fases. É única. A mariposa final lembra de leve a Traça do Sino Mudo (NA), mas o papel e a leitura são outros. |
| mon_preguica_de_pomar | CHANGES | A mecânica duplica a do Oco da Fronteira na mesma região: aliados escondidos que não podem ser alvo e papel `guarda_protetor` nos dois. Como a Cria do Oculto tem mais direito a "esconder", a Preguiça é quem muda. |
| mon_coandu_de_rebrota | APPROVED | Artilharia covarde com munição que rebrota. Não tem par nas três ondas. |
| mon_vespa_oleira | APPROVED | Potes de barro nas juntas que travam a Reação. É única. O pote de argila do Turno Vencido (Pântano) é outro uso. |
| mon_escavador_das_camaras | CHANGES | O corpo (pangolim cego, branco, do tamanho de uma casa) é ótimo. A assinatura do chefe, porém, soma duas assinaturas de NA: "chão cede" da Porca da Queda e "some e sai por baixo de quem não espera" da Cavadeira de Unhas. Um chefe precisa de carta própria. |
| enemy_vinha_estranguladora (Serpente Cipó Constritora) | CHANGES (leve) | É fiel a `creatures.txt:1109`. Porém as "tiras de pele velha penduradas" são o traço da Serpente-de-Mil-Peles, o mesmo motivo que o autor usou para cortar o conceito 8. |
| mon_viuvo_do_esporo | APPROVED | Metade do corpo com o fungo da esposa morta e golpes em dois tempos. É única, e a lore do casamento ritual e dos olhos dourados está correta (`races.txt:398-413`). |
| mon_surdo_da_colmeia | CHANGES (leve) | A identidade é única e o rumor da audição perdida está correto. O fato errado: "carne viva" permanente contradiz `races.txt:405` ("o fungo regenera ativamente o tecido danificado... em horas"). |
| mon_mascador_de_nectar | APPROVED | Mascar o Néctar até cair a gengiva, lâminas nos cotos e lutar uma rodada a mais depois de cair. A lore está certa: pasta na gengiva, Clãs de Combate de Skallgard no norte, Brekmar e Nova Arcádia. Nota: "cada Ferimento fortalece" ecoa o Tritão de Sobra, mas a escala (força, não número de golpes) e o "mais um pouco" o separam. |
| mon_enxertadora_da_uniao | APPROVED | Cultista que costura retalhos de Hospedeiro e um retalho que drena. Bate com os Cultistas-da-Colmeia de `creatures.txt` sem repeti-los. Ela fica com o motivo da costura (ver Manto). |
| mon_pressa_da_seiva | CHANGES | A mecânica é a soma de duas assinaturas já usadas: "age duas vezes na rodada" do Sangrado da Clínica (NA) e "perde Vitalidade por rodada, o tempo luta contra ele" do Musaranho de Dente Vermelho (Pântano). Até o contra-jogo é o do Musaranho. |
| mon_provador_de_cores | APPROVED | Pele em mapa de cores e cuspe anunciado pela cor. É única e respeita "só os Hospedeiros conhecem o código" (`creatures.txt:1107`). |
| mon_manto_de_alheios | CHANGES | Repete a Cria de Veth da onda NA (Convidado de Cera, "joias alheias", tranca "a Carta mais cara"). Os dois miram "o melhor que o jogador tem". O material (retalhos de pele com fungo de Hospedeiro morto, costurados) também é o da Enxertadora. Pela lore, Veth "não quer o que o outro tem; quer que o outro não tenha" (`npcs.txt:262`); roubar e usar é cobiça, não inveja. |
| mon_isca_amarrada | APPROVED | Trouxa pendurada que sangra e fortalece a fauna, e o contra-jogo é cortar a corda. Vem direto dos Garimpeiros-de-Resina ("às vezes os usam como isca") e de Maalrek. É única. |
| mon_oco_da_fronteira | APPROVED | Tronco morto da floresta andando na linha da fronteira, com alguém dentro. Os fatos estão certos: a selva nasceu da borda da floresta de Thessavar e as criaturas não cruzam (`locations.txt:155-164`). Fica com a mecânica de esconder. |
| mon_tropel_sem_saida | APPROVED | É a fuga feita corpo, com pernas que correm para lados opostos, e o efeito é físico (arrasta e tira ação). Não repete a anatomia da Cavadeira de Unhas, a outra Cria de Dorrhen. |

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `selva_xylos.yaml:72-79,116-119` (Lamelas) | Reskin do Arame Vivo (`nova_arcadia.yaml:63-69`): curvado, veias do pescoço e dos braços projetadas para fora da pele, mãos rígidas. | Tirar o eixo "veias" e as "mãos rígidas". Por exemplo: lamelas em prateleiras (orelha-de-pau) nascendo em degraus no tronco e nas costas, com a pele rachada entre elas e a silhueta de um tronco caído. Outra saída é cortar a vaga e reaproveitar um conceito cortado que não use a Ferrugem. |
| P1-2 | P1 | `selva_xylos.yaml:390-397,427-435,442-452` (Remendado) | Funciona como Lycan Hospedeiro: crânio de predador sobre o rosto, "fome de osso", comparação direta com o Lycan. | Tirar o crânio de predador e a fome de osso, manter o rosto do Hospedeiro e deixar o osso só nas camadas de livro molhado. A lore deve parar de contrastar com o Lycan (basta a Praga dos Ossos). Diferenciar do Hospedeiro-Profundo deixando a colmeia de fora ou dando outro motivo. |
| P1-3 | P1 | `selva_xylos.yaml:651-655` (Preguiça) | `mecanica_assinatura` igual à do Oco (`:1657-1660`): aliado que não pode ser alvo. | Mudar a carta da Preguiça para algo do pomar. Exemplos: a fruta das costas madura a cada rodada e cai em quem está embaixo, ou cura um aliado se não for derrubada; ou ela intercepta para si o golpe contra o aliado agarrado nela. Evitar o estouro, que é da Fruta-Bomba. |
| P1-4 | P1 | `selva_xylos.yaml:885-889` (Escavador) | A assinatura do chefe soma a Porca da Queda (`nova_arcadia.yaml:597`) e a Cavadeira de Unhas (`:1120`). | Ancorar a carta no que só ele tem: a bola de escamas, quase imune, e o desenrolar que expõe a barriga, combinados com a luz que o paralisa (por exemplo, um momento de luz forte ou fogo o tira da bola). O "chão cede" pode ficar secundário; tirar o "sai onde ninguém esperava". |
| P1-5 | P1 | `selva_xylos.yaml:1349-1354` (Pressa) | A carta soma Sangrado (`nova_arcadia.yaml:1892`) e Musaranho (`pantano_melancolia.yaml:735`), e o contra-jogo é o do Musaranho. | Manter o envelhecimento, mas trocar a ação dupla. Exemplo: a cada rodada ele pula uma fase da vida (jovem, rápido e frágil; depois velho, lento e de golpe pesado), e o jogador escolhe em que fase enfrentá-lo. O contra-jogo não pode ser "esperar". |
| P1-6 | P1 | `selva_xylos.yaml:1487-1493,1504-1507` (Manto) | Repete a mecânica da Cria de Veth em NA (`nova_arcadia.yaml:1194`) e usa o mesmo material da Enxertadora. | Inveja segundo a lore é "que o outro não tenha". Exemplo: ela apaga ou estraga o reforço mais brilhante do jogador sem usá-lo, ou bate mais forte em quem tiver mais reforços do que ela. Trocar a pele costurada por cordões e colares de crescimentos e enfeites comprados (sem costura), para não repetir a Enxertadora. |
| P2-1 | P2 | `selva_xylos.yaml:164-166,176-179,191-195` (Aríete) | "Antes nunca subiam, agora sobem" e a fuga do fundo repetem o Escavador (`:877-878,891-892,905-909`). O motivo do rumor `rumors.txt:335` aparece em Aríete, Recusado, Escavador e Tropel. | Dar ao Aríete outro impulso. Exemplo: a cunha cresce e dói, e ela investe contra troncos e pontes para quebrar o osso que a sufoca. O gancho do "fundo" fica com o Escavador e o Tropel. |
| P2-2 | P2 | `selva_xylos.yaml:956-957,987-988,998` (Serpente) | As tiras de pele velha são o traço da Serpente-de-Mil-Peles (`creatures.txt:1004`). | Trocar por escamas que imitam folhas ou raízes aéreas, ou simplesmente remover. |
| P2-3 | P2 | `selva_xylos.yaml:1104-1105,1136,1140` (Surdo) | A carne viva permanente contradiz a regeneração do fungo (`races.txt:405`). | Uma frase basta: a pele fecha lisa e sem crescimento e ele volta a arrancá-la, ou o fungo já não regenera nele desde que perdeu a voz. |
| S-1 | P2 | `selva_xylos.yaml:73-77,110-115,94-97,103` (Lamelas) | Segredo C-07: a ficha mostra a Praga de Ferro virando cogumelo no calor ("como guelras de cogumelo", "como cogumelo em tronco caído"). Nenhum texto afirma a equivalência, então é insinuação, que o dono aceita. Mesmo assim, é a criatura que demonstra o segredo, e `inspiracao.distancia` diz literalmente "fica em segredo". | No retrabalho do P1-1: tirar "cogumelo" de `lore`/`description`/`gancho` (pode ficar só na arte) e remover "fica em segredo" da `distancia` (se `inspiracao` for para o doc de arte, a frase anuncia que há um segredo). |
| N-1 | nota | `selva_xylos.yaml:242-243,269` (Laçado) | O farejar de sangue e as feridas abertas ecoam o Sangrado da Clínica (NA). | Opcional: tirar "fareja sangue" da prosa (o eixo continua) e deixar o laço como o centro. |
| N-2 | nota | `selva_xylos.yaml:31,305` (Recusado) | `material: cinza` rotula o material como cinza, mas o corpo só tem cor de cinza. | Avaliar `carne_exposta` ou outro material seco, se o tabuleiro permitir. Não bloqueia. |

## Pares suspeitos de reskin

- **Na região:** Preguiça × Oco (mecânica), Manto × Enxertadora (material e costura), Aríete × Escavador (lore e gancho).
- **Com outras ondas:** Lamelas × Arame Vivo (NA), Remendado × Lycan (lore), Escavador × Porca da Queda e Cavadeira de Unhas (NA), Pressa × Sangrado da Clínica (NA) e Musaranho (Pântano), Manto × Convidado de Cera (NA, mesmo demônio), Serpente-Cipó × Serpente-de-Mil-Peles (doc).
- **Inconsistência no doc de conceitos:** o conceito 7 ("Onça de Placas") caiu por ser "Lycan de outro bicho", mas o Aríete é exatamente uma besta com a Praga dos Ossos. A cunha o salva; sugiro reescrever o motivo do corte (o problema da Onça era ser variante do Predador Crescido).

## Lore conferida (sem erro além do P2-3)

Hospedeiros: olhos dourados, coral, sem dor, casamento ritual, perda da colmeia fora da selva, pontes de cipó tratado. Néctar: pasta na gengiva, vem do interior, vale fortunas em Brekmar e Nova Arcádia. Clãs de Combate: Skallgard, norte. Resina-Viva: componente de regeneração (`items.txt:911`). Chá da Praga de Ferro com plantas da borda (`locations.txt`). Fronteira floresta × selva. Câmaras de raízes de Morrakh. Garimpeiros que usam isca. Cultistas que capturam viajantes. Natureza de Veth, Maalrek, Thessavar e Dorrhen. Nenhum texto público revela o pacto de Valerius.

## Correções aplicadas

(Para o executor: preencher na rodada 2.)

## Pendências

Rodada 2: revisar só P1-1 a P1-6 e P2-1 a P2-3. Ao fechar, gravar `revisao` nas fichas.

## Comandos rodados

```text
git log --oneline -1 → a3343d60
grep nome/silhueta/description/frase em nova_arcadia.yaml e pantano_melancolia.yaml → pares acima
sed creatures.txt:978-1130, races.txt:378-430/509-530, secrets.txt:96-104, locations.txt:150-215, npcs.txt (Veth/Maalrek/Thessavar/Dorrhen), items.txt:905-994, rumors.txt:333-338
(sem pytest, a pedido)
```

## Rodada 2 (commit `8649e747`, 2026-11-01)

Escopo: só os 9 itens marcados, conferidos pelo diff `a3343d60..8649e747` de `selva_xylos.yaml`.

| id | Veredito | Conferência |
|---|---|---|
| mon_lamelas_de_ferrugem | APPROVED | O corpo dobrado em ângulo reto com prateleiras em degraus nas costas não repete o Arame Vivo; as veias e as mãos rígidas saíram. "Cogumelo" saiu de lore, description e gancho, e "fica em segredo" saiu da distancia. "Como as que crescem num tronco caído" insinua o fungo, o que o dono aceita. |
| mon_ariete_de_medula | APPROVED | O novo impulso (a cunha que cresce e sufoca, e ela investe contra o que é duro) é próprio dela. O motivo "fundo/sobem" saiu, e o gancho dos pilares rachados é bom. |
| mon_remendado_de_osso | APPROVED | Saíram o crânio de predador, a fome de osso, o contraste com o Lycan e a colmeia. O rosto humano calmo sobre o corpo em camadas é uma leitura nova. Caçar o que sangra encosta de leve no Laçado, mas o motivo (amolecer a pele) é outro. |
| mon_preguica_de_pomar | APPROVED | O pomar que amortece os golpes dados nos aliados e rebrota se separa do esconder do Oco e da argila do Turno Vencido. O contra-jogo de queimar o pomar é coerente. |
| mon_escavador_das_camaras | APPROVED | A carta agora é dele: bola quase imune, luz ou fogo o desenrola e expõe a barriga. Saíram a Porca e a Cavadeira. O padrão e o telégrafo novos estão coerentes. |
| enemy_vinha_estranguladora | APPROVED | A pele velha saiu. As saliências em forma de raízes aéreas reforçam a imitação de cipó. Continua fiel a `creatures.txt:1109`. |
| mon_surdo_da_colmeia | APPROVED | A pele fecha lisa em horas e ele a arranca de novo, o que fica coerente com `races.txt:405`. |
| mon_pressa_da_seiva | APPROVED | A troca de idade a cada rodada, com o contra-jogo de escolher a fase, não é o Sangrado nem o Musaranho, e o "esperar" saiu. |
| mon_manto_de_alheios | APPROVED | O monte de colares sem costura e sem pele deixa de repetir a Enxertadora. "Apagar sem usar" e "bater mais em quem tem mais aceso" seguem a Veth da lore e saem do eixo do Convidado de Cera. **Follow-up P2:** o `nome` "Manto" já não descreve o corpo (agora é um monte). Sugiro renomear antes de gerar o Codex, por exemplo para "Monte de Alheios" ou "Colar de Alheios", ajustando id e carta junto. Não bloqueia. |

Rodada 2 fechada: as 22 fichas recebem APPROVED, e o executor grava `revisao` nas fichas. A única pendência é o follow-up P2 do nome do Manto, a cargo do executor ou do coordenador, nesta mesma onda.

```text
git diff a3343d60 8649e747 -- data/bestiario/fichas/selva_xylos.yaml → 9 fichas conferidas
(sem pytest, a pedido)
```


---

# Revisão da região: skallgard (arquivo original handoffs/SPEC-349-astra-review.md)

# SPEC-349 — revisão de unicidade, onda Skallgard (rodada 1 de 2)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (spec-reviewer, unicidade; não é o autor das fichas) · **Data:** 2026-11-01 · **Commit revisado:** `4d787133` (branch `bst-skallgard`)

## Escopo

Revisei as 20 fichas novas e os 3 slots reinventados de `data/bestiario/fichas/skallgard.yaml`
(linhas 60–1850) e `docs/spec349/conceitos-skallgard.md`, aplicando o checklist da §3.9 e as regras U
da §3.4. Comparei com:

- as 8 fichas retro da região;
- `nova_arcadia.yaml` e `pantano_melancolia.yaml`, só nos campos nome, anatomia, silhueta e mecânica;
- os 47 docs `data/codex/monsters/` com a tag `skallgard`;
- `lore_nova/creatures.txt`, `locations.txt:228-232`, `races.txt:88,344`, `npcs.txt`
  (Vhrak, Maalrek, Veth, Dorrhen, Skarath) e `secrets.txt:79-90, 368-373`.

Ficaram fora: números, baralho e arena (Etapa 5) e a prosa do doc de arte, além do que não afeta a
unicidade. Não rodei pytest.

Os 5 critérios do checklist: **1** não é reskin · **2** identidade em uma frase · **3** é de Valoria ·
**4** é física e luta · **5** não vaza segredo.

## Veredito por criatura

| # | id · nome | 1 | 2 | 3 | 4 | 5 | Veredito | Motivo |
|---|---|---|---|---|---|---|---|---|
| 1 | `mon_parado_do_sopro` · Parado do Sopro | ✗ | ✗ | ✓ | ✓ | ✓ | **CHANGES** | Mesma âncora, material e imagem do Colecionador de Poses: carne em vidro limpo com o músculo parado no meio do gesto, entre as estátuas do Sopro, na Fortaleza. Um é "uma estátua presa a um vivo"; o outro, "um corpo de estátuas". É variante da mesma ideia. |
| 2 | `mon_levantado_de_rubi` · Levantado de Rubi | ✓ | ✓ | ✗ | ✓ | ✓ | **CHANGES** (P2) | O corpo e a mecânica são únicos. O gancho diz que a Rede "aprendeu", e o Codex afirma que ela "não tem mente, não tem intenção" (`mon_rede_carmesim.md`). |
| 3 | `mon_queimado_de_breu` · Queimado de Breu | ✗ | ✗ | ✓ | ✓ | ✗ | **CHANGES** | A cegueira com caça pelo som e o contra-jogo do silêncio são a identidade dos Caçadores-Cegos. O vigia sem rosto que fica nas encostas do Farol, de costas para a torre, é o Guardião-Sem-Rosto em negativo. Os dois juntos ainda insinuam o segredo do ciclo do guardião (`secrets.txt:84`). |
| 4 | `mon_parelha_carmesim` · Parelha Carmesim | ✓ | ✓ | ✓ | ✓ | ✓ | **APPROVED** | Parelha morta ainda atrelada, correndo a última rota. A Rede como causa já aparece no Levantado, mas o corpo, o papel e a mecânica (atropelar a fila e o tirante do cão-guia) são outros. |
| 5 | `mon_desfiado_da_aurora` · Desfiado da Aurora | ✓ | ✓ | ✓ | ✓ | ✓ | **APPROVED** | Encarna a consequência que o Codex descreve para a Aurora-Viva sem repetir o lençol de luz. A tira que queima até a neve funda é dano por rodada, de recurso diferente da sanguessuga do Casaco (Pântano). |
| 6 | `mon_ermitao_de_escotilha` · Ermitão de Escotilha | ✗ | ✓ | ✓ | ✓ | ✗ | **CHANGES** (P0) | Vazamento: nome "Escotilha", cúpula de ferro rebitado anão com vigia, "tanto ferro anão debaixo do gelo" e "os Anões mudam de assunto" põem a Landship que falta sob o gelo de Skallgard. Os dois últimos aparecem como fato no gancho (l. 480) e no lore (l. 495-499). Mecânica: o bicho de casco que prende e corta a Carta de ataque é o Cágado de Geada (Pântano), e na região colide com o Ferreiro. |
| 7 | `mon_carrapato_de_montaria` · Carrapato de Montaria | ✗ | ✗ | ✗ | ✓ | ✓ | **CHANGES** | Divide a âncora (ferida dos ganchos do Urso-Titã) com a Montaria Cravada. O corpo é um carrapato grande sem marca do Abismo; o próprio `evitar` admite "só que grande". O "crava e bebe" lembra a sanguessuga do Casaco. A mecânica de levar o sangue para curar o inimigo mais forte é boa e fica. |
| 8 | `mon_lagarta_sete_invernos` · Lagarta de Sete Invernos | ✓ | ✓ | ✗ | ✓ | ✓ | **CHANGES** (P2) | A alternância congela/debate-se é própria, distinta do Caído do Cadinho, que endurece aos poucos. Mas o corpo é a lagarta-lanosa real ampliada; a única marca de Valoria é "o Abismo a fez do tamanho de um tronco". |
| 9 | `mon_mandriao_dois_bicos` · Mandrião de Dois Bicos | ✓ | ✓ | ✓ | ✓ | ✓ | **APPROVED** | Bico partido em dois, que é deformidade legível; alvo só o recém-ferido. O gancho a separa do Corvo-da-Aurora e do Falcão-Carniceiro: não espera o morto. |
| 10 | `mon_montaria_cravada` · Montaria Cravada | ✓ | ✓ | ✓ | ✓ | ✓ | **APPROVED** | Não é variante do Urso-Titã retro: a retro é o colosso que não recua; esta é o vínculo de dor (`creatures.txt:70`) virado carne num corpo duplo. Elite, perseguidor e mecânica de dois corpos. Fica dona exclusiva da âncora dos ganchos (ver #7). |
| 11 | `mon_ferreiro_chama_fria` · Ferreiro de Chama Fria | ✓ | ✓ | ✓ | ✓ | ✓ | **APPROVED** | "Não pega em arma, desfaz a dos outros" é lore própria dos tecnológicos. Quebrar a arma espelha o Enxerto e o Portão, que quebram a armadura, mas não repete nenhum. Fica como a única negação de Carta de ataque da região depois do ajuste do #6. |
| 12 | `mon_lascador_morno` · Lascador Morno | ✓ | ✓ | ✓ | ✓ | ✓ | **APPROVED** | Garimpeiro ilegal com mãos de cristal. A troca aleatória da Carta, vinda da morte alheia, não existe em outra ficha. Atirar lascas de cristal lembra o Relicário (NA), mas o corpo e o efeito são outros. |
| 13 | `mon_escuta_do_sinal` · Escuta do Sinal | ✓ | ✓ | ✓ | ✓ | ✓ | **APPROVED** | Único convocador das três ondas. As cornetas aparafusadas no crânio são legíveis em arte. "Segunda frequência" já é público (`creatures.txt:251`). |
| 14 | `mon_caldeira_de_peito` · Caldeira de Peito | ✓ | ✓ | ✓ | ✓ | ✓ | **APPROVED** | "Não pega em arma, é a arma" e a caldeira do Ventre no peito; empurra e queima. É dona da armação de ferro (ver #23). |
| 15 | `mon_andas_de_caribu` · Andas de Caribu | ✓ | ✓ | ✓ | ✓ | ✓ | **CHANGES** | O corpo é ótimo, mas a mecânica (arranca o item e foge; se não cair em N rodadas, some com ele) é o molde da Gralha de Crematório (NA). Também é o terceiro ladrão no conjunto Gralha/Fardo/retro. |
| 16 | `mon_ticao_do_juramento` · Tição do Juramento | ✓ | ✓ | ✗ | ✓ | ✓ | **CHANGES** (P2) | A âncora (fogueira do Juramento, Vhrak) e a mecânica são próprias. O crânio de cabra é clichê de diabrete e não é fauna da tundra; nenhuma ficha ou doc de Skallgard cita cabra. |
| 17 | `mon_colecionador_de_poses` · Colecionador de Poses | ✓ | ✓ | ✓ | ✓ | ✓ | **APPROVED** | Chefe. Fica dono da âncora das estátuas do Sopro. Forçar a repetir a última Carta difere do Cordão de Medida (Pântano), que devolve a Carta contra o alvo, e do Convidado (NA), que tranca a mais cara. |
| 18 | `mon_feltro_do_ventre` · Feltro do Ventre | ✗ | ✓ | ✓ | ✓ | ✓ | **CHANGES** | As "oito mãos" num saqueador rasteiro repetem o Fardo de Espólio (Pântano, saqueador de oito braços). A "pele lisa como cera fria", junto com o sebo, ecoa o Convidado de Cera, a cria de Veth em NA. A mecânica (tomar o reforço do jogador) é única e fica. |
| 19 | `mon_rosto_nas_costas` · Rosto nas Costas | ✗ | ✗ | ✓ | ✓ | ✓ | **CHANGES** | É o Vira-Costas da Praça (NA) invertido: corpo virado do avesso, frente/nuca trocada e braços dobrados para trás. A mecânica também é "ataque-me primeiro": o Vira-Costas absorve até ser atacado, o Rosto pune quem ataca outro. |
| 20 | `mon_enegrecido_da_porta` · Enegrecido da Porta | ✗ | ✓ | ✓ | ✓ | ✓ | **CHANGES** | É a segunda cria de Dorrhen feita de dedos e mãos humanos; a primeira é a Cavadeira de Unhas (NA). É também o terceiro amálgama de mãos e pés, com o Relicário da Catedral (NA). O próprio doc cortou o "Cavador de Neve" por isso (#55) e manteve o material. A mecânica (fecha a saída e cobre os outros) fica. |
| 21 | `enemy_lobo_invernal` · Pulga de Forquilha | ✓ | ✓ | ✗ | ✓ | ✓ | **CHANGES** (P2) | Saltar por cima da guarda é próprio, distinto da Centopeia (NA) e do Patinador (Pântano). Mas o corpo é o colêmbolo real ampliado: nenhuma deformidade do Abismo, e o gancho só diz que "cresceu". |
| 22 | `enemy_yeti` · Corcova Fervente | ✓ | ✓ | ✓ | ✓ | ✓ | **APPROVED** | A corcova que guarda o calor que o Abismo tira é uma boa leitura de `creatures.txt:64`. O `evitar` já o separa do Touro-Almiscarado e do Mamute. Nota P2: a explosão que queima todos em contato lembra o Lençol de Chaminé (NA); a diferença é que aqui acontece em vida e muda o ritmo do bicho. Aceito. |
| 23 | `mon_jotun_cinza` · Crescido do Clã | ✓ | ✗ | ✓ | ✓ | ✓ | **CHANGES** | A ideia (especiação que não para) é forte, mas o corpo se apoia numa armação de ferro dos tecnológicos presa ao tronco, a mesma da Caldeira de Peito. É o terceiro corpo de tecnológico com metal aparafusado, com o Escuta e a Caldeira, e a mecânica depende da armação. |

**Contagem:** 10 APPROVED e 13 CHANGES (6 só de texto ou anatomia, P2). Nenhum CORTE: todas as
correções cabem na ficha, e cortar derrubaria a onda abaixo do piso de 20 novas (R21).

## Achados e correções mínimas

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P0-1 | P0 | `skallgard.yaml:443-520` (nome l.445; gancho l.480-482; lore l.494-499; description l.492; aparencia l.501; arte l.510) | Vaza a localização da Landship que falta (E-08, `secrets.txt:368-373`): "Escotilha", cúpula com vigia, "tanto ferro anão debaixo do gelo", "Anões mudam de assunto" | **Renomear** sem "Escotilha" (o id muda junto). Trocar a casca: em vez da cúpula com vigia e tampa, uma peça de guerra pública e solta, como o elmo ou o escudo-torre de um Anão das batalhas Cinzéus × Anões no norte (Codex `mon_rede_carmesim.md`). Tirar de todos os campos "ferro anão debaixo do gelo/perto dos rios" e "Anões mudam de assunto"; tirar a escotilha também de `inspiracao.distancia` (l.488) e do telegrafo. |
| P1-1 | P1 | `skallgard.yaml:474-479` (Ermitão, mecânica) | "Prende a mão e corta a Carta de ataque até soltar" é o Cágado de Geada (Pântano) e colide com o Ferreiro (#11) | Trocar o efeito, por exemplo: cada Ermitão fechado numa mão ocupa 1 espaço da mão do alvo até ser virado (o bando acumula). Nada de Carta de ataque, movimento ou Fôlego. |
| P1-2 | P1 | `skallgard.yaml:60-135` (Parado) | Variante do Colecionador: Sopro, estátuas, vidro e músculo parado no gesto | Manter a mecânica e o lado envelhecido. O lado parado deixa de ler como estátua: em vez da casca de vidro, carne que não muda (ferida do dia ainda fresca e aberta, sangue vermelho vivo, neve que não derrete sobre ela, sem gelo). Material sai de `vidro_cristal`, por exemplo `carne_exposta`; relinte U2/U3. Tirar `sk_fortaleza_vorr` do habitat e o "para diante das estátuas, comparando" (comportamento, lore, composição de arte); o Parado anda pelo Ermo onde o Sopro passou. |
| P1-3 | P1 | `skallgard.yaml:214-290` (Queimado) | Reskin de Caçadores-Cegos (cego, caça pelo som, silêncio defende) e do Guardião-Sem-Rosto (sentinela sem rosto que fica no Farol); insinua o ciclo do guardião | (a) Ele **enxerga**, e só no escuro que faz: os olhos ficam, pretos e grandes. Mudar `percepcao: som` para outro eixo e relintar; tirar orelhas crescidas, "vem pelo som" e "em silêncio" do contra-jogo e do como_se_luta. (b) Deixa de ser "vigia" que "fica nas encostas de costas para a torre": vira quem cruzou a encosta (carreteiro, cortador de gelo dos clãs) e voltou para Skallgard com a anti-luz na pele. Tirar "deixam de voltar e ficam nas encostas" (lore l.265) e a silhueta "vigia de capuz… buraco no formato de gente". |
| P1-4 | P1 | `skallgard.yaml:523-600` (Carrapato) | Mesma âncora da Montaria (ganchos do Urso-Titã); carrapato real ampliado | Trocar o hospedeiro para a manada do Ermo, Mamute-da-Névoa ou Caribu-Cinza (fiel à inspiração do carrapato-de-inverno). Tirar Urso-Titã, ganchos e cavaleiros de anatomia, gancho, comportamento, refs e `related_entities`. Pôr uma marca do Abismo no corpo, por exemplo: o sangue que bebe não coagula nem congela e brilha morno na barriga, porque o frio do Abismo não o toca. A mecânica fica. |
| P1-5 | P1 | `skallgard.yaml:1168-1173` (Andas, mecânica) | Molde da Gralha de Crematório: rouba, foge, temporizador | Assinatura tirada das andas, sem roubo temporizado. Por exemplo: chuta de cima, por cima da defesa da fila, e na neve funda escolhe a distância a cada rodada; derrubar as andas (contra-jogo atual) o põe de joelhos. Se o roubo ficar, que seja só sabor no comportamento, fora da carta-assinatura. |
| P1-6 | P1 | `skallgard.yaml:1372-1449` (Feltro) | "Oito mãos" = Fardo de Espólio (Pântano); "cera fria" + sebo = Convidado de Cera (Veth, NA) | Trocar as oito mãos por um modo de agarrar sem mãos, por exemplo franjas de feltro com farpas de cobre que se fecham como ventosas. Tirar "como cera fria" e o sebo como material de pele. A boca vertical e a mecânica ficam. Atualizar silhueta (l.~1395), aparencia, arte e `evitar`. |
| P1-7 | P1 | `skallgard.yaml:1450-1525` (Rosto nas Costas) | Vira-Costas invertido no corpo e na tática "ataque-me primeiro" | Novo corpo, sem frente/costas trocadas nem braços para trás. Sugestão ancorada na trégua de Skarath: um corpo crescido do aperto de mãos do Juramento, dois antebraços fundidos num punho que não solta, com a mão livre armada. Nova mecânica fora do "ataque-me primeiro", por exemplo: trégua falsa, em que ele não ataca enquanto o jogador não o ataca e, na primeira rodada em que o jogador fica sem defesa preparada, golpeia pelas costas em dobro. Nome novo se o rosto sair. |
| P1-8 | P1 | `skallgard.yaml:1526-1602` (Enegrecido) | Segunda cria de Dorrhen de dedos (Cavadeira de Unhas) e terceiro amálgama de mãos e pés (Relicário) | Manter a ideia (o amputado do frio deixado sem saída deita na porta) e a mecânica. O corpo não pode ser feito de mãos, pés ou dedos. Por exemplo: um único amputado que o desespero fez crescer, com os cotos queimados de frio, pretos e endurecidos como casco, e o tronco alargado para tampar a passagem. Tirar "mãos e pés" do nome, da silhueta e do `evitar`. |
| P1-9 | P1 | `skallgard.yaml:1764-1850` (Crescido) | Armação de ferro dos tecnológicos = a da Caldeira; terceiro tecnológico aparafusado | Trocar a armação por algo dos clãs de combate, sem metal aparafusado: talas de osso de mamute e cintas de couro cru apertadas nos membros, ou correntes de arpão. A mecânica passa a "enquanto as talas aguentam". Pode manter que os dois clãs precisam um do outro, mudando quem faz o quê. |
| P2-1 | P2 | `skallgard.yaml:173-175` (Levantado, gancho) | "a Rede aprendeu" contradiz o Codex ("não tem mente") | Reescrever sem intenção. Por exemplo: "A Rede Carmesim reanima o que morreu no seu alcance. No Levantado ela não parou no corpo: o cristal que nasceu dentro dele faz o mesmo com quem cai perto." |
| P2-2 | P2 | `skallgard.yaml:601-679` (Lagarta) | Animal real ampliado, sem marca do Abismo | Marca no corpo: cada inverno em que congelou deixou um anel morto, preto e duro, que ela arrasta. São sete, e a parte morta não degela, de modo que a "rodada congelada" se lê no corpo. A mecânica fica. |
| P2-3 | P2 | `skallgard.yaml:1603-1681` (Pulga) | Colêmbolo real ampliado, sem deformidade | Marca do Abismo, por exemplo: a forquilha cresceu demais e não dobra inteira, e cada salto a racha e a remenda com quitina nova (estalo audível, um telegrafo legível). Ligar o gancho ao calor do Ventre ou às Veias-de-Calor, e não só a "cresceu". |
| P2-4 | P2 | `skallgard.yaml:1219-1292` (Tição) | Crânio de cabra: clichê de diabrete, fora da fauna da tundra | Trocar por crânio de caribu ou de foca roído do banquete (anatomia, silhueta, aparencia, arte). |

## Respostas às perguntas do coordenador

- **Montaria Cravada é variante do Urso-Titã retro?** Não. A ficha retro é o bicho selvagem que não
  recua; a Montaria é o vínculo de dor do Codex virado num corpo duplo, com outra categoria, outro
  papel e outra mecânica. Fica, com exclusividade da âncora dos ganchos (por isso P1-4).
- **Mesma âncora em duas criaturas:**
  - Ganchos do Urso-Titã: Montaria e Carrapato → P1-4.
  - Estátuas do Sopro: Colecionador e Parado → P1-2.
  - Armação de ferro: Caldeira e Crescido → P1-9.
  - Rede reanimando: Levantado e Parelha → **aceito**. É a causa regional, como a Praga de Ferro em
    NA; corpo e mecânica são diferentes.
  - Cristal-Sanguíneo: Levantado e Lascador → **aceito**. Um é o cristal num morto; o outro, o preço
    de um vivo.
- **Mecânicas parecidas:**
  - Corte de Carta de ataque: Ermitão, Ferreiro e o Cágado do Pântano → P1-1.
  - Roubo temporizado: Andas e a Gralha de NA → P1-5.
  - "Ataque-me primeiro": Rosto e o Vira-Costas de NA → P1-7.
  - Dreno de Fôlego: nenhuma ficha da onda drena Fôlego como assinatura. O Enegrecido cobra Fôlego
    por tentativa de fuga, o que é aceitável.
  - Perda de movimento: nenhuma usa; mantenham assim nas correções.
  - Marca: só a Montaria, que é perseguidor_marca por papel, o que é aceitável.
  - Repetir Carta: só o Colecionador, distinto do Cordão do Pântano.
- **Segredos:**
  - Farol → Rede: nenhum campo público afirma a ligação. "A aurora muda de ritmo ao redor dele" é
    público (`locations.txt:230`). O risco do Queimado é a inferência sobre o ciclo do guardião
    (P1-3), não a ligação com a Rede.
  - Landship: vaza no Ermitão (P0-1).

## Pendências e notas

- Depois das correções: rodar `lint.py --regiao skallgard --sem-revisao` de novo. P1-2 e P1-3 mudam
  eixos (material e percepção), e P1-7 provavelmente muda `plano_corporal`, o que reabre U2/U3/U12.
  A rodada 2 revisa só as 13 fichas em CHANGES.
- O autor registra as decisões no §3 de `docs/spec349/conceitos-skallgard.md`.
- **Fora do escopo desta onda (para o coordenador):** o worktree tem
  `data/codex/monsters/mon_gigantes.md` com "Construíram o Farol da Chama Negra para conter a Rede
  Carmesim". Isso é a ligação Farol → Rede em texto público. O checkout principal já corrigiu
  (Grep sem ocorrência na `main`); confirmar que o `wt.sh sync` traz a correção antes do pouso.
- Os 3 erros U1 de `resolve_bestiary_name` nos slots são esperados, como dito no brief.

## Comandos rodados

```text
bash scripts/dev/py.sh scripts/bestiario/lint.py --regiao skallgard --sem-revisao → 31 fichas · 3 erros (U1 dos slots, esperados) · 2 avisos (retro)
bash scripts/dev/py.sh <scratchpad>/dump.py skallgard|nova_arcadia|pantano_melancolia → extração de nome/anatomia/silhueta/mecânica para comparação
```

---

## Rodada 2 (última) — commit `8c9e9672`

> **Veredito da rodada 2:** `CHANGES_REQUIRED`, com **um único ajuste de texto** (P1-R2-1, abaixo). Feito o
> ajuste, a onda está **APPROVED** sem rodada 3: o coordenador confere pelo diff. As outras 22 fichas estão
> aprovadas como estão.
> **Revisor:** Opus (spec-reviewer, unicidade) · **Data:** 2026-11-01

Revisei só as 13 fichas que estavam em CHANGES; as 10 aprovadas na rodada 1 não foram reabertas. Rodei o
lint da região: 31 fichas, 3 erros U1 esperados (slots) e 2 avisos (retro). Varri o arquivo atrás de
resíduos: não sobrou "escotilha", "vigia", "mudam de assunto", Urso-Titã ou ganchos no Carrapato,
Fortaleza ou estátua no corpo do Parado, nem "armação" fora da Caldeira.

| # | id · nome | Veredito R2 | Nota |
|---|---|---|---|
| 1 | `mon_parado_do_sopro` · Parado do Sopro | **APPROVED** | Lado parado é carne viva e jovem, com a ferida fresca e sem casca. Habitat só `skallgard`; o `evitar` barra estátua, cristal e casca. Separado do Colecionador. |
| 2 | `mon_levantado_de_rubi` · Levantado de Rubi | **APPROVED** | O gancho agora segue o Codex ("não tem mente"). |
| 3 | `mon_queimado_de_breu` · Queimado de Breu | **APPROVED** | Enxerga só luz (`percepcao: luz`) e o contra-jogo virou "chegar sem tocha", não mais o silêncio dos Caçadores-Cegos. Deixou de ser sentinela: volta e caça nas trilhas, sem inferência sobre o ciclo do guardião. |
| 6 | `mon_ermitao_de_elmo` · Ermitão de Elmo | **APPROVED** | O vazamento sumiu: o elmo vem das batalhas Cinzéus × Anões nas passagens, que é público, e não há escotilha, vigia nem Anões evasivos. Ocupar 1 espaço da mão é a única redução de mão das três ondas. |
| 7 | `mon_carrapato_de_mamute` · Carrapato de Mamute | **APPROVED** | O hospedeiro passou ao Mamute-da-Névoa, então os ganchos ficam só com a Montaria. A boca em cada ponta é deformidade legível e ilustra a mecânica (bebe de um, cura outro). |
| 8 | `mon_lagarta_sete_invernos` · Lagarta de Sete Invernos | **APPROVED** | Os sete anéis mortos que ela arrasta dão a marca do Abismo e se leem na silhueta. |
| 15 | `mon_andas_de_caribu` · Andas de Caribu | **CHANGES** (P1-R2-1) | O roubo saiu, e o chute por cima da defesa preparada é bom. Mas a 2ª metade da assinatura ("escolhe a distância… na rodada seguinte só um ataque à distância o alcança") repete o Patinador de Óleo (Pântano: "só quem atira de longe o alcança"), agora com o mesmo papel, `batedor_rapido`. |
| 16 | `mon_ticao_do_juramento` · Tição do Juramento | **APPROVED** | O crânio agora é de caribu. |
| 18 | `mon_feltro_do_ventre` · Feltro do Ventre | **APPROVED** | Sem mãos e sem cera: faixa de feltro com farpas de cobre, enrolada no cano. Nota P2 de arte, opcional: o plano e o material (`serpentiforme` + `couro_tecido`) são os da Escritura Rastejante (NA, Daruun). A silhueta difere (faixa farpada enrolada num cano × rolo de papel no chão), mas vale pôr "rolo, pergaminho" no `evitar`. |
| 19 | `mon_aperto_da_tregua` · Aperto da Trégua | **APPROVED** | Corpo e mecânica novos: pune a rodada sem defesa, o que não é mais "ataque-me primeiro". Nota P2 de arte, opcional: o Cordão de Medida, a cria de Skarath do Pântano, também usa mãos de confiança, com nós de punhos de dedos entrelaçados. Para manter a distância visual, a arte do Aperto mostra o aperto de palma (não os dedos entrelaçados) e evita a leitura de corda. |
| 20 | `mon_enegrecido_da_porta` · Enegrecido da Porta | **APPROVED** | Um só amputado, com os cotos crescidos em tocos e sem amálgama de mãos e pés. Separado da Cavadeira e do Relicário. |
| 21 | `enemy_lobo_invernal` · Pulga de Forquilha | **APPROVED** | A forquilha atravessa a barriga, que fica aberta (deformidade), e o gancho agora a liga às saídas de vapor do Ventre. |
| 23 | `mon_jotun_cinza` · Crescido do Clã | **APPROVED** | As talas de osso de mamute com couro cru dos clãs de combate substituíram a armação, que fica só na Caldeira. O novo gancho ("o único fraco que eles carregam") é forte. |

### Ajuste restante (mínimo)

| ID | Sev. | Arquivo | Problema | Correção |
|---|---|---|---|---|
| P1-R2-1 | P1 | `skallgard.yaml`, `mon_andas_de_caribu`: `mecanica_assinatura.frase`, `como_se_luta` e `telegrafo`, se citarem | A cláusula "escolhe a distância na neve funda; na rodada seguinte só ataque à distância o alcança" é o Patinador de Óleo (Pântano). | Cortar essa cláusula da assinatura e de onde ela se repetir. A carta-assinatura fica só com "chuta de cima com a ponta de osso: o golpe passa por cima da defesa preparada". O afastamento pela neve pode ficar como sabor no `comportamento` e no lore, sem efeito mecânico. Relintar U7/U13 (assinatura e tupla do padrão). |

As duas notas P2 de arte (Feltro × Escritura e Aperto × Cordão) não bloqueiam.

### Comandos rodados (R2)

```text
bash scripts/dev/py.sh scripts/bestiario/lint.py --regiao skallgard --sem-revisao → 31 fichas · 3 erros (U1 dos slots, esperados) · 2 avisos (retro)
grep de resíduos (escotilha|vigia|mudam de assunto|armação|Urso no Carrapato|Fortaleza no Parado) → só "armação" na Caldeira, como esperado
```

---

# Revisão cruzada entre regiões (2026-11-02, HEAD `d0315445`)

**Revisor:** Opus (não escreveu nenhuma das criaturas). **Veredito: `CHANGES_REQUIRED`.**
**Colisões:** 14 P0 · 10 P1 · 12 P2. **Trocas exatas:** 24 fichas (abaixo, campo a campo).

## Escopo e método

- As 281 fichas não-retro das 12 regiões (`status` nova/reinventada/adotada), extraídas por script
  (id, região, família, demônio, nome, 5 eixos + papel, `mecanica_assinatura.frase`, `contra_jogo`,
  `telegrafo`, `silhueta`, `aparencia`, `anatomia.texto`, `arte.visual`). Os YAML não foram lidos inteiros.
- Comparação lida à mão por família e por demônio (todas as frases e contra-jogos), mais Jaccard
  (`card_lint.similarity`) entre regiões em frase/contra/silhueta/telegrafo/anatomia/aparência e núcleo
  de nome (`name_tokens(nome)[0]`) entre regiões. O Jaccard léxico quase não pegou nada (máx. 0,40 no
  telegrafo): **as repetições abaixo são de ideia, não de palavra**, e por isso escaparam de U6/U13/R29.
- Lore conferida em `lore_nova/npcs.txt` e `timeline_completa.txt` do checkout principal (13 demônios).
- Pares só entre retro foram ignorados.

## Achados do gate

| ID | Sev. | Achado |
|---|---|---|
| G1 | — | `scripts/bestiario/lint.py`: 368 fichas · 0 erro · 29 avisos. **Os 29 (U3/U4) são todos retro×retro** (Brekmar 8, Nova Arcádia 10, Pradaria 8, Montanhas 1, Ophidia 1, Skallgard 2, Aethelgard 1). Descartados: nenhum envolve criatura nova. |
| G2 | P0 | **Os metadados trocados para zerar o R29 não batem com a prosa em 3 de 5 casos**: Altivo do Vidro `bipede_curvado` (prosa e arte dizem "de pé muito reto", "como pernas de pau"); Cabeça Acima `segmentado` (a prosa é um humanoide ereto de pescoço longo); Rixa Costurada `ferro_ferrugem` (dois homens de carne colados; só as facas são de ferro). Os pares que o R29 apontou eram mesmo a mesma ideia (Pernalta × Altivo × Cabeça Acima: Urath em ossos altos; Rixa × Chifres: Vhrak em dois rivais fundidos). O conflito foi escondido, não resolvido. Correção: reescrita do corpo (T9, T10, T11). |
| G3 | P1 | Mastro dos Últimos `couro_tecido`: a prosa é carne de gente (os farrapos são roupa). A Costura de Rancor `composto` **bate** com a prosa (Orc sobre um monte de Goblins) e fica. Mastro: T12 (material `sal_mineral` com crosta de sal na base, honesta na prosa). |
| G4 | P1 | **R27: `npc_fehk` tem 1 cria** (Vira-Costas). O gate não acusou porque `data/bestiario/_esteira.yaml` **não existe**, e o R27 de `lint_global` só roda com ele (`services/bestiary_lint.py:639-655`). A T13 (Enegrecido → Fehk) fecha a cobertura; o coordenador precisa criar o `_esteira.yaml` (R27, spec §E) para o gate valer. Crias hoje: daruun 3, dorrhen 9, fehk 1, lyss 3, maalrek 8, morvath 2, skarath 5, solvhara 3, thessavar 4, urath 7, veleth 3, veth 9, vhrak 7. Depois das trocas: daruun 4, dorrhen 8, fehk 2, maalrek 7. |

## Tabela de colisões

| # | Par / grupo (região) | Sev. | O que se repete | Decisão |
|---|---|---|---|---|
| C1 | Provador de Ophidia (costa) × Provador de Cores (selva) | P0 | Mesmo núcleo de nome, mesmo corpo (provador de venenos de pele mudada), mesma mecânica (a cor anuncia o veneno do próximo cuspe) e mesmo contra (ler a cor) | Fica o **Provador de Cores** (o código das Rãs-Veneno-de-Cor é lore da Selva). Muda o da Costa → **T1** |
| C2 | Desbotado da Névoa (ophidia) × Nadador Transparente (aethel) | P0 | Afogado transparente de coração visível, invisível na água, 1º golpe sem aviso, contra "turvar a água / tirá-lo para a areia" | Fica o **Nadador Transparente** (reinvenção da onda 1, Oghma). Muda o Desbotado → **T2** |
| C3 | Atirador de Olhos Vítreos (pradaria) × Olho de Pétala (floresta) | P0 | Atirador de olho enxertado que acerta através de escuro e cobertura; luz forte o cega | Fica o **Olho de Pétala** (Flor-Olho, único `hospedeiro_parasita` humano). Muda o Atirador → **T3** |
| C4 | Iguana de Salmoura (costa) × Lagarto Espirrador (ophidia) | P0 | O mesmo bicho (lagarto negro que espirra sal da glândula do focinho), o mesmo papel `artilharia`, os mesmos eixos de corpo (quadrúpede, pequeno, escala paredes) e o mesmo efeito (o alvo erra mais) | Fica o **Lagarto Espirrador** (cortina de área). Muda a Iguana → **T4** |
| C5 | Mascador de Raiz (floresta) × Olhos em Volta (montanhas) [+ Leitor de Cativos, pradaria, P2] | P0 | "A Carta preparada fica à mostra e os inimigos se preparam contra ela", frase quase literal | Fica o **Olhos em Volta** (o corpo de olhos justifica). Muda o Mascador → **T5** |
| C6 | Costura das Duas Cidades (pradaria) × Monte de Alheios (selva), ambos Veth | P0 | "Apaga/desfaz o reforço do alvo sem tomar nada para si", efeito idêntico; e o nome "Costura" repete com a Costura de Rancor | Fica o **Monte de Alheios**. Muda a Costura → **T6** (nome e mecânica) |
| C7 | Ventre Partilhado (costa, Lyss) × Novelo de Anzóis (aethel, Maalrek) [+ Casco de Costelas, P2] | P0 | "Prende um alvo; metade do dano que a criatura recebe vai para o preso" | Fica o **Novelo** (é o espelho de quem sofre, que é Maalrek na lore). Muda o Ventre → **T7** |
| C8 | Despenseiro de Espinhos (deserto) × Picanço de Espinheiro (floresta), ambos Maalrek [+ Mastro de Troféus, C17] | P0 | O mesmo comportamento animal (a despensa do picanço: presa viva espetada em espinhos) e a mesma mecânica (o preso sangra a cada rodada até ser solto) | Fica o **Picanço** (é o próprio picanço). O Despenseiro vira cria de **Daruun** (consome e redistribui) → **T8** |
| C9 | Rixa Costurada (brekmar) × Chifres Travados (pradaria), ambos Vhrak [+ Costura de Rancor, C16] | P0 | Dois rivais fundidos de frente pela arma da briga (facas / chifres); o R29 pegou e o metadado foi trocado sem mudar a prosa (G2) | Ficam os **Chifres Travados** (chefe, cabo de guerra limpo). A Rixa vira um corpo só → **T9** |
| C10 | Altivo do Vidro (deserto) × Pernalta do Conselho (aethel), ambos Urath [+ Andas de Caribu, P2] | P0 | Figura alta sobre canelas/pernas de osso "como andas", que não olha para baixo; metadado trocado sem mudar a prosa (G2) | Fica a **Pernalta** (golas do conselho, onda 1). O Altivo mantém a mecânica e troca o corpo → **T10** |
| C11 | Tampão da Câmara (montanhas) × Enegrecido da Porta (skallgard) × Lacrador de Saídas (deserto), os três Dorrhen | P0 | "Fecha a saída: ninguém foge da luta" (Tampão e Enegrecido começam com a mesma frase) | Fica o **Lacrador** (o vidro mole na 1ª rodada é contra exclusivo). O Tampão muda o efeito → **T14**; o Enegrecido vira cria de **Fehk** (fecha G4) → **T13** |
| C12 | Mapa de Cicatrizes (floresta) × Mapa de Cicatriz (montanhas) | P0 | Nomes quase iguais (só o plural os separa no U1); mesmo corpo-ideia (rotas cortadas/tatuadas na pele) e mesmos eixos de corpo (`bipede_ereto/couro_tecido/humana`, percepção `eter`) | Fica o **Mapa de Cicatrizes**. O de Montanhas troca o nome (o braço-marco já é corpo próprio) → **T15** |
| C13 | Queimado de Breu (skallgard) × Abafador de Candeias (floresta) [+ Ladrão de Lume, P2] | P0 | Apaga a luz e "os ataques à distância erram / não têm em quem mirar" | Fica o **Abafador**. Muda o Queimado → **T16** |
| C14 | Feltro do Ventre (skallgard, Veth) × Véu Faminto (aethel, Lyss) [+ Rêmora de Convés, P2] | P0 | "Toma para si o reforço do alvo" | Fica o **Véu** (guarda no nó, e cortar devolve). Muda o Feltro → **T17** |
| C15 | Cabeça Acima (pradaria) × Desafiante Rubro (floresta) × Carranca de Proa (brekmar), os três Urath | P1 | Os três fixam um só alvo e ignoram o resto; a Cabeça Acima ainda é o 3º "Urath alto de osso" (G2) | Ficam o **Desafiante** e a **Carranca**. Cabeça Acima: corpo reescrito para bater com `segmentado` e mecânica sem fixação → **T11** |
| C16 | Costura de Rancor (montanhas) × Chifres Travados (pradaria), ambos Vhrak | P1 | "As duas partes se odeiam" e o mesmo contra ("feri-la por igual nas duas partes" × "alternar até ficarem iguais") | Ficam os **Chifres**. A Costura mantém o corpo (Orc sobre Goblins é outra imagem) e troca nome e mecânica → **T18** |
| C17 | Mastro de Troféus (montanhas, Maalrek) × Picanço / Despenseiro | P1 | "Agarra o ferido, que sangra a cada rodada enquanto preso" | O Mastro passa a usar o espelho de Maalrek (o rosto no topo já está no corpo) → **T19** |
| C18 | Virado do Avesso (floresta) × Altivo do Vidro (deserto) × Rancor de Pinças (costa) [+ Vira-Costas, Pajem de Obsidiana, P2] | P1 | "Devolve o golpe a quem bateu" | Ficam o **Rancor** (escala por atacante: ódio, Vhrak) e o **Altivo** (ofensa cobrada: orgulho, Urath). Muda o **Virado** (sem demônio) → **T20** |
| C19 | Ferreiro de Chama Fria (skallgard) × Braços de Tenaz (montanhas) | P1 | Ferreiro humanoide que agarra a arma do alvo e a inutiliza; contra "cabo/haste de madeira" nos dois | Ficam os **Braços de Tenaz**. Muda o Ferreiro → **T21** |
| C20 | Aperto da Trégua (skallgard) × Mão Estendida (brekmar), ambos Skarath | P1 | Corpo de aperto de mão / mão estendida, "oferece trégua" e pune quem confia | Os dois corpos ficam (um oferece a mão, o outro é a mão); o **Aperto** troca a mecânica para um pacto que só vale para um lado → **T22** |
| C21 | Guia Avesso (deserto) × Mão Estendida (brekmar), ambos Skarath | P1 | Gesto de confiança → na rodada seguinte, um golpe que ignora a defesa | Fica a **Mão Estendida**. O Guia troca o efeito → **T23** |
| C22 | Barata das Costelas (costa) × Rolador de Escarpa (montanhas) [+ Tatu de Navalha, Enrolado da Clareira, Escavador das Câmaras, P2] | P1 | Bola que desce a encosta e fica de barriga para cima; contra "sair da linha da encosta" (Jaccard 0,33, o mais alto do lote) | Fica o **Rolador**. A Barata passa a ricochetear entre costelas → **T24** |
| C23 | Mastro dos Últimos (ophidia) × Tampão da Câmara (montanhas), ambos Dorrhen | P1 | Massa de desesperados agarrados; metadado trocado (G3) | As silhuetas são distintas (coluna × porta). Fica o corpo, com crosta de sal real na base → **T12** |
| C24 | Fehk sem segunda cria (G4) | P1 | R27 | **T13** |

**P2 (não bloqueiam; registrar para a próxima rodada da esteira):**

| # | Par / grupo | Nota |
|---|---|---|
| P2-1 | Vira-Costas (NA, Fehk) × Tição do Juramento (skallgard) × Pajem de Obsidiana (NA) | Revide em outras formas (absorve por todos; atiça o revide de outro inimigo; espinho de contato). Efeitos distintos; manter. |
| P2-2 | Andas de Caribu (skallgard) × Pernalta do Conselho (aethel) | Ambos altos sobre osso; famílias e quadros diferentes (capuz de caribu, neve). Na `arte.evitar` do Andas: "golas altas, braços até a água". |
| P2-3 | Pernalta das Colunas (pradaria) × Pernalta do Conselho (aethel) | Mesmo núcleo de nome; os contra-jogos dizem a mesma coisa (pernas finas que quebram). Sugestão: renomear a ave (ex.: "Garça das Colunas"). |
| P2-4 | Casco de Costelas (brekmar) × Novelo de Anzóis | "Golpe na criatura também fere o engolido" (todo × metade). Chefe e escala distintos; aceitar. |
| P2-5 | Tamanduá de Ponte (selva) × Carregador de Ganchos (pradaria) | Puxa o isolado para junto do grupo; contra "ficar perto". O Carregador já diz "não prende"; aceitar. |
| P2-6 | Forrado de Leviatã (costa) × Couro Pegado (deserto) × Fechado de Escápulas (floresta) × Costas de Alicerce (pradaria) | Intercepta o golpe pelo aliado com uma placa. É o verbo do papel `guarda_protetor`, e as placas mudam (osso que cresce, escama, escápula, laje). Na arte do Couro Pegado: evitar "placa de osso no antebraço". |
| P2-7 | Fervente de Ferrugem (deserto) × Corcova Fervente (skallgard) × Lençol de Chaminé (NA) × Mula de Lágrimas (pântano) | Estoura e fere quem está em contato. É o verbo do papel `sacrificial`; o token "Fervente" repete. |
| P2-8 | Banhado do Centro (pântano) × Raspadeira de Barbatana (costa) | A arma perde grau até ser limpa ou afiada. Gatilhos distintos (tocar nele × ela gruda na arma). |
| P2-9 | Lagarta de Sete Invernos (skallgard) × Lagarta da Hora (selva) [+ Lagarta de Visgo] | Lagarta com fase em que quase nada a fere. Sugestão: renomear a de Skallgard. |
| P2-10 | Ermitão de Carcaça (floresta) × Ermitão de Elmo (skallgard); Preguiça da Pradaria (floresta) × Preguiça de Pomar (selva) | Mesmo bicho e mesmo núcleo de nome (e as duas preguiças são `guarda_protetor`). Renomear uma de cada par; a "da Pradaria" vive na Floresta e confunde com a região `pradaria_ruinas`. |
| P2-11 | Contra-jogo "poucos golpes e fortes" (Virado, Cabeça Acima, Mascador de Néctar, Fervido da Corrente, Lamelas de Ferrugem) e "fique parado" (Casuar, Rodante, Verme de Vidro, Nadador de Pedra, Lenço, Ouriço, Bucho, Tropel) | Contra-jogo repetido em muitas regiões. Para a próxima onda: um U14 que compare `contra_jogo` entre regiões (já sugerido na §9 da spec). |
| P2-12 | Núcleos de nome entre regiões: Mão ×5, Nadador ×3, Provador ×3 (2 depois de T1), Lagarta ×3, Mastro ×2, Saltão ×2, Lambedor ×2, Cobra ×2 etc. | O U4 é só por região; entre regiões não é regra. Fica como nota. |

## Trocas exatas

Convenção: cada bloco lista só os campos que mudam; o que não aparece fica como está. Quando há
renome, trocar também `id`, `mecanica_assinatura.carta` e o `vaga`/`nome` correspondente onde a região
os repetir, e fazer `grep` do nome antigo na própria ficha (`lore`, `gancho`) e em `docs/`. Toda troca
pede relint (`lint.py --regiao <r>`): U6 (anatomia/silhueta/gancho), U9 (≥ 3 partes), U13 (telegrafo
< 0,5) e R29. As crias com demônio trocado (T8, T13) mudam `origem_lore.detalhe` e a `ref` do demônio;
as linhas citadas são do checkout principal (`lore_nova/npcs.txt:197` = Natureza de Daruun, `:306` =
Natureza de Fehk), mesma convenção das ondas.

### T1 · costa_negra · `mon_provador_de_ophidia` → **Contrabandista Vítreo** (`mon_contrabandista_vitreo`)

- `mecanica_assinatura.carta`: `cri_contrabandista_vitreo_sangue_que_corta`
- `anatomia.texto`: Um provador de venenos da Mão Sombria que provou tanto do que vem de Ophidia que o corpo parou de aceitar remédio. A pele do rosto, do pescoço e das mãos virou vidro em placas lisas, e por baixo delas o sangue engrossou e escureceu até brilhar como piche com areia. As duas palmas estão abertas em talhos fundos que nunca fecham, de bordas de vidro, de tanto ele cortá-las para pingar o próprio sangue na língua e saber o que comprou. A língua é preta e rachada, as unhas caíram, e as veias dos antebraços saltam duras como arame.
- `silhueta`: Um homem magro de pele em placas de vidro, de palmas abertas para a frente, pingando um sangue preto e brilhante.
- `aparencia`: Homem magro de pele virada vidro em placas lisas no rosto, no pescoço e nas mãos, sangue preto e espesso brilhando por baixo, palmas abertas em talhos fundos de borda de vidro, língua preta rachada, dedos sem unhas, veias saltadas nos antebraços.
- `arte.visual`: Humano adulto magro em roupas escuras de contrabandista; rosto, pescoço e mãos cobertos de placas de vidro translúcido e liso, com sangue escuro quase preto visível por baixo; as duas palmas voltadas para a frente, abertas em cortes fundos de bordas vítreas, pingando gotas pretas e brilhantes; língua preta à mostra; dedos sem unhas; veias grossas saltadas nos antebraços. Sem manchas coloridas na pele nem bochechas infladas (essa leitura é do Provador de Cores, Selva).
- `mecanica_assinatura.frase`: Sacode o sangue das palmas abertas sobre um alvo à distância: o sangue gruda e corta o remédio, e na rodada seguinte nenhuma cura vale no atingido; quem já estava sob um efeito de cura o perde.
- `contra_jogo`: Curar antes de ele sacudir as palmas, ou limpar o sangue com água e areia, gastando a ação; de perto ele não tem tempo de abrir as mãos e luta só com a faca.
- `telegrafo`: {nome} abre as duas palmas para você, e o sangue preto escorre até a ponta dos dedos.
- `description`: Um provador de venenos da Mão Sombria de pele virada vidro e sangue preto e espesso, que sacode o sangue das palmas e corta o efeito de qualquer remédio.
- `como_se_luta`: Sacode de longe o sangue das palmas, e o atingido não se cura na rodada seguinte. Limpe o sangue com água e areia, cure antes, ou feche a distância.
- `comportamento`: trocar "Cada cuspe é um veneno diferente, e ele cheira o sangue do alvo para saber qual vem a seguir." por "Não cospe: sacode o sangue das palmas, e onde ele cai nenhum remédio pega."
- `lore`: trocar "e a pele deles vai virando vidro, com as cores do arquipélago correndo por baixo." por "e a pele deles vai virando vidro, com o sangue cada vez mais preto por baixo."
- eixos: sem mudança.

### T2 · ophidia · `mon_desbotado_da_nevoa` (nome e id ficam)

- `mecanica_assinatura.carta`: `cri_desbotado_da_nevoa_tornozelo_no_fundo`
- `anatomia.texto`: Um tripulante que atravessou a névoa colorida e saiu dela sem cor e sem firmeza. A cor saiu da pele e o osso amoleceu: o corpo inteiro ficou branco e encharcado como pão deixado na água, inchado ao dobro, de carne mole que afunda ao toque e não volta. Os dedos das mãos cresceram compridos e grossos, de juntas frouxas, e fecham como laço. Os olhos ficaram vermelhos, a única cor do corpo. Deitado de costas no fundo do raso, ele parece um tronco claro, e sente pela barriga cada passo que entra na água.
- `silhueta`: Um corpo branco e inchado deitado de costas no fundo do raso, com dois olhos vermelhos abertos e dedos compridos fechados em laço.
- `aparencia`: Corpo humano branco e encharcado, inchado ao dobro e mole como pão na água, sem cor nenhuma além dos olhos vermelhos; dedos compridos e grossos de juntas frouxas; deitado de costas no fundo do raso.
- `arte.visual`: Humano adulto deitado de costas sob um palmo de água clara sobre areia escura; pele branca opaca, encharcada e inchada, carne mole com marcas de dedos que não voltam; sem cabelo; olhos vermelhos abertos olhando para cima; mãos de dedos longos e grossos abertos em garra para a superfície. Nada transparente, sem coração nem órgãos visíveis (essa leitura é do Nadador Transparente, Aethelgard).
- `mecanica_assinatura.frase`: Deitado no fundo do raso, segura pelo tornozelo quem pisa perto e pesa como afogado: enquanto segura, o preso luta com água pela cintura, não troca de lugar e seus golpes saem fracos; um segundo herói puxando junto solta o preso na hora.
- `contra_jogo`: Andar pela areia seca em vez do raso; se alguém for preso, outro herói gasta a ação puxando junto, ou corta os dedos frouxos, que soltam como massa.
- `telegrafo`: A água rasa perto de você fica turva de um branco leitoso, e dois pontos vermelhos se abrem no fundo.
- `description`: Um tripulante que a névoa de Ophidia deixou branco, inchado e mole como pão na água, que fica deitado no fundo do raso e segura o tornozelo de quem pisa nele.
- `como_se_luta`: Segura pelo tornozelo quem pisa no raso e o deixa preso, de golpes fracos. Ande pela areia seca; preso, um companheiro puxa junto ou corta os dedos.
- `comportamento`: Fica deitado de costas no fundo do raso, parado, e é tomado por tronco claro até se mexer; sente pela barriga quem entra na água. Segura quem vem buscar um bote ou um corpo e não larga sozinho.
- `lore`: trocar "pele, carne e cabelo transparentes como água. Dentro do mar só se vê o coração deles batendo." por "brancos e moles como pão deixado na água, inchados, de olhos vermelhos. No fundo do raso parecem troncos."
- eixos: sem mudança.

### T3 · pradaria_ruinas · `mon_atirador_de_olhos_vitreos` → **Arqueiro de Tendão** (`mon_arqueiro_de_tendao`)

- `mecanica_assinatura.carta`: `cri_arqueiro_de_tendao_corda_de_carne`
- `anatomia.texto`: Um arqueiro dos Cavaleiros-Cinza que, no mercado de Vaelorn, trocou o arco de madeira por um enxerto. O antebraço esquerdo foi aberto do cotovelo ao punho: os dois ossos cresceram em hastes curvas de Éter cristalizado, translúcidas e foscas, que saem da carne em cima e embaixo como as pontas de um arco. A corda é o próprio tendão do braço, puxado para fora da carne e preso nas duas pontas; a pele em volta do corte nunca fechou e tem crostas de cristal. Cada disparo puxa o tendão um pouco mais para fora. A mão direita, a da puxada, tem os dedos calejados até o osso.
- `silhueta`: Um arqueiro de capa cinza sem arco nas mãos, com o próprio antebraço esquerdo aberto em arco de cristal e a corda saindo da carne.
- `aparencia`: Arqueiro de capa cinza cujo antebraço esquerdo virou arco: duas hastes curvas de cristal de Éter saindo da carne aberta, o tendão do braço esticado como corda entre elas, crostas de cristal em volta do corte, dedos da mão direita calejados até o osso.
- `arte.visual`: Humano adulto magro de capa cinza esfarrapada dos Cavaleiros-Cinza, de pé no capim alto; o antebraço esquerdo, erguido à frente, está aberto do cotovelo ao punho, e dele saem duas hastes curvas de cristal translúcido e fosco formando um arco; entre as pontas, uma corda de tendão vermelho-pálido que sai de dentro da carne; crostas de cristal nas bordas do corte; a mão direita puxa o tendão até a orelha, com um estilhaço de cristal por flecha. Olhos humanos comuns, sem enxerto no rosto.
- `mecanica_assinatura.frase`: Cada disparo puxa o tendão mais para fora: o primeiro tiro é fraco e cada um seguinte bate mais forte; no quarto o tendão estala, e ele passa a rodada seguinte sem atirar, sangrando do braço.
- `contra_jogo`: Aguentar os primeiros tiros abrigado e chegar perto na rodada em que o tendão estala; ou cortar a corda de tendão de perto, com qualquer lâmina.
- `telegrafo`: {nome} puxa o tendão até a orelha, e o braço-arco range e solta lascas de cristal.
- `description`: Um arqueiro dos Cavaleiros-Cinza de antebraço aberto em arco de cristal e corda de tendão, cujos tiros ficam mais fortes a cada disparo até o tendão estalar.
- `como_se_luta`: Atira mais forte a cada disparo e, no quarto, o tendão estala e ele fica uma rodada sem arco. Abrigue-se dos primeiros e chegue perto no estalo, ou corte o tendão.
- `comportamento`: Fica para trás, a pé, no capim alto, enquanto os outros Cavaleiros-Cinza cobram a passagem, e atira sem parar até o tendão estalar; então recua para amarrá-lo de novo.
- `gancho`: Os Cavaleiros-Cinza são o bando mais organizado das rotas; os mais velhos dizem que os arqueiros deles não perdem o arco desde que passaram a comprá-lo em Vaelorn, dentro do próprio braço.
- `lore`: trocar de "Alguns arqueiros deles trocaram os olhos" até o fim por: "Alguns arqueiros deles trocaram o arco, no mercado de Vaelorn, por um enxerto: o antebraço aberto, os ossos crescidos em hastes de Éter cristalizado, o tendão puxado para fora como corda. O tiro fica mais forte a cada disparo, até o tendão estalar. Os que escaparam contaram os tiros."
- eixos: sem mudança.

### T4 · costa_negra · `mon_iguana_de_salmoura` → **Petrel de Papo Cheio** (`mon_petrel_de_papo_cheio`)

- eixos: `plano_corporal: alado` (era `quadrupede`); o resto fica (`couro_tecido/pequena/escala_paredes/calor`, `artilharia`). Atualizar a linha da `vaga: 12`. Conferido: U2 único na Costa; U3 contra a Gaivota Ladra (retro) = 3 eixos.
- `mecanica_assinatura.carta`: `cri_petrel_de_papo_cheio_oleo_do_papo`
- `anatomia.texto`: Uma ave do mar do tamanho de um gato, de penas cinza coladas pelo próprio óleo, que faz ninho nas frestas das costelas do Cemitério. O Éter da água que ela bebe a vida inteira inchou a bolsa de óleo do estômago, que cresceu para fora do pescoço num saco de pele fina e amarelada, maior que a cabeça, onde se vê o óleo balançando. Pesada demais para voar longe, anda pelos ossos agarrada com garras compridas e o bico em gancho, de asas abertas só para se equilibrar. O peito é careca de tanto óleo escorrer por ele.
- `silhueta`: Aves cinzentas agarradas às costelas brancas, cada uma com um saco amarelo de óleo pendurado do pescoço, maior que a cabeça.
- `aparencia`: Ave do mar cinzenta do tamanho de um gato, penas coladas de óleo, saco de pele fina e amarelada pendurado do pescoço com óleo balançando dentro, garras compridas agarradas ao osso, bico em gancho, peito careca.
- `arte.visual`: Bando de aves marinhas do porte de um gato, plumagem cinza empapada e colada, agarradas com garras longas a uma costela branca de leviatã; de cada pescoço pende um papo inchado, translúcido e amarelado, maior que a cabeça, com líquido oleoso visível; bicos curvos em gancho; asas meio abertas para equilíbrio; peito sem penas. Não é lagarto: sem focinho encrostado nem espirro (essa leitura é do Lagarto Espirrador, Ophidia).
- `mecanica_assinatura.frase`: Esvazia o papo num jato de óleo fedido sobre um alvo à distância: o óleo gruda nas mãos, e até o alvo gastar uma ação esfregando-as com areia, a próxima Carta de defesa dele vale metade, porque a arma e a proteção escorregam.
- `contra_jogo`: Esfregar as mãos com areia seca logo depois do jato; o papo vazio leva duas rodadas para encher, e uma ave de papo vazio cai do osso com qualquer pancada.
- `telegrafo`: O papo de {nome} incha e balança, e a ave estica o pescoço na sua direção.
- `description`: Uma ave do mar de papo inchado de óleo pelo Éter do Cemitério, pesada demais para voar, que cospe óleo fedido em quem chega perto do ninho.
- `como_se_luta`: Cospe óleo nas mãos do alvo, e a próxima defesa dele escorrega. Esfregue as mãos com areia; de papo vazio ela cai do osso com uma pancada.
- `comportamento`: Ficam agarradas no alto das costelas, junto aos ninhos. Quando alguém chega perto, esvaziam o papo em quem está embaixo e esperam que ele encha de novo. Não descem para brigar.
- `gancho`: No Cemitério até a água é carregada de Éter; as aves que a bebem a vida inteira guardam no papo mais do que óleo de peixe.
- `lore`: Fazem ninho nas frestas das costelas, cinzentas sobre o osso branco, e daqui de baixo parecem musgo. Quem passa embaixo descobre que não são. O óleo que cospem fede por dias e faz a mão escorregar no cabo. Os Osshari andam com as mãos enroladas em pano sob as costelas por causa delas.

### T5 · floresta_sussurros · `mon_mascador_de_raiz` (nome e id ficam; a carta `o_que_se_esconde` passa a bater com o efeito)

- `mecanica_assinatura.frase`: Masca a raiz e vê o que se esconde: enquanto ele mascar, nenhum herói fica escondido, nenhuma emboscada pega e nenhum ataque vem pelas costas das criaturas em volta dele.
- `contra_jogo`: Cortar a raiz entre ele e o chão o cala por uma rodada; ou derrubá-lo de longe, que ele não sai do lugar, antes de tentar surpreender alguém.
- `telegrafo`: {nome} masca mais depressa, e os olhos dele vão direto para onde você está escondido.
- `description`: Um mago de revelação de mandíbula presa à Raiz-Que-Lembra, ajoelhado há anos, que vê quem se esconde e o sopra às criaturas.
- `como_se_luta`: Enquanto masca, ninguém se esconde nem pega uma criatura de surpresa. Corte a raiz para calá-lo, ou derrube-o de longe.
- `comportamento`: trocar "e vê o que quem chega pretende fazer: as mãos, os bolsos, a próxima ideia." por "e vê onde quem chega está: atrás da árvore, no escuro, nas costas das criaturas."
- `lore`: trocar "Os que ficaram veem o que quem chega pretende fazer e contam" por "Os que ficaram veem onde quem chega se esconde e contam".

### T6 · pradaria_ruinas · `mon_costura_das_duas_cidades` → **Retalho das Duas Cidades** (`mon_retalho_das_duas_cidades`)

- `mecanica_assinatura.carta`: `cri_retalho_das_duas_cidades_cada_um_por_si`
- `mecanica_assinatura.frase`: Desfaz a ajuda: a defesa, a cura ou a Reação que um herói joga em favor de outro se desfaz antes de valer enquanto ele estiver de pé; o que cada herói joga para si mesmo vale inteiro.
- `contra_jogo`: Cada um se proteger sozinho enquanto ele vive, e derrubá-lo primeiro pela costura do meio, onde as duas metades se repelem e a carne rasga.
- `telegrafo`: As duas mãos de {nome} se esticam ao mesmo tempo, cada uma para um de vocês, uma de cada cor.
- `description`: Uma cria da Inveja entre Vaelorn e Solvhen, um corpo de dois lados costurados, um de Elfo e outro de Cinzéu, que desfaz a ajuda que um companheiro dá ao outro.
- `como_se_luta`: Desfaz o que um herói joga para proteger ou curar outro. Cada um se cuida sozinho até derrubá-lo pela costura do meio.
- `comportamento`: trocar "Arranca de quem enfrenta o que ele preparou para se proteger e foge assim que o arranca." por "Perto dele, a ajuda que um dá ao outro se desfaz antes de chegar."
- `lore`: trocar "Ele desfaz a guarda de quem enfrenta e foge, sem levar nada." por "Perto dele, o que um faz pelo outro se desfaz na mão, e cada um fica sozinho."
- anatomia e eixos: sem mudança. (A Mão da Borda, Skarath, *agarra* quem ajuda; aqui a ajuda só se desfaz.)

### T7 · costa_negra · `mon_ventre_partilhado` (nome e id ficam)

- `mecanica_assinatura.carta`: `cri_ventre_partilhado_carta_a_carta`
- `mecanica_assinatura.frase`: Costura a pele do alvo à sua e o consome devagar: a cada rodada costurado, uma Carta da mão do alvo some até o fim da luta e a criatura fecha um Ferimento próprio; cortar a costura custa um Ferimento ao próprio alvo.
- `contra_jogo`: Cortar a costura cedo e aceitar a ferida, antes de a mão esvaziar; ou não deixar que encoste, porque ela é lenta e só costura quem toca.
- `description`: Uma cria de Lyss feita de dois náufragos, um afundando na barriga do outro, que costura a própria pele à da presa e a consome, Carta a Carta.
- `como_se_luta`: Costura a pele do alvo à sua e lhe come uma Carta da mão a cada rodada. Corte a costura cedo, ao custo de uma ferida, ou não a deixe encostar.
- `comportamento`: trocar "Quem fica costurado sente na própria carne o que acertam nela." por "Quem fica costurado vai sendo puxado para dentro, um pouco a cada rodada."
- `telegrafo`, anatomia e eixos: sem mudança.

### T8 · deserto_zhur · `mon_despenseiro_de_espinhos` (nome e id ficam) — passa de Maalrek a **Daruun**

- `origem_lore`: `detalhe: npc_daruun`; `refs`: trocar `lore_nova/npcs.txt:210` por `lore_nova/npcs.txt:197` (manter `factions.txt:522`). R29: nenhuma outra cria de Daruun é `bipede_ereto/vidro_cristal`.
- `mecanica_assinatura.carta`: `cri_despenseiro_de_espinhos_passa_adiante`
- `anatomia.texto`: Uma ave corredora sem voo, mais alta que um homem a cavalo, de pernas grossas e garras de três dedos, pescoço comprido e pelado e bico curvo em gancho. As penas das costas e dos tocos de asa endureceram em espinhos de vidro compridos e curvos, apontados para cima, numa sela de pontas. É ali que ela guarda o que toma: odres, bolsas, facas, pedaços de arreio, tudo espetado e balançando, nada vivo. O papo, sob o bico, é largo e solto como um saco, e ela o enche e o esvazia sem engolir.
- `silhueta`: Uma ave alta de pescoço comprido e pernas grossas, com as costas eriçadas de espinhos de vidro carregados de odres e bolsas espetados.
- `aparencia`: Ave corredora sem voo, alta, de pernas grossas e pescoço nu, bico em gancho e papo largo e solto, costas eriçadas numa sela de espinhos de vidro curvos com odres, bolsas, facas e arreios espetados.
- `arte.visual`: Ave corredora sem voo, mais alta que um homem a cavalo, pernas grossas de três dedos, pescoço longo e nu, bico curvo em gancho, papo largo e solto sob o bico; nas costas, uma sela de espinhos de vidro curvos apontados para cima, com odres de couro, bolsas, facas e pedaços de arreio espetados neles. Nenhuma presa viva espetada (a despensa de presas é do Picanço de Espinheiro, Floresta).
- `mecanica_assinatura.frase`: Arranca com o bico o melhor que o alvo tem à mão (um consumível, a arma ou o reforço que ele acendeu) e o espeta nas costas; na rodada seguinte o passa a outra criatura da cena, que passa a usá-lo. Derrubada, tudo o que está espetado volta ao dono.
- `contra_jogo`: Não levar nada valioso à mão perto dela, ou derrubá-la pelas pernas grossas, que não têm espinho, antes que ela passe adiante o que tomou.
- `telegrafo`: {nome} abaixa o pescoço, abre o papo e mira o que você tem na mão.
- `description`: Uma ave corredora sem voo, de penas das costas endurecidas em espinhos de vidro, que arranca o que os vivos carregam e o passa a quem estiver com ela.
- `como_se_luta`: Arranca o melhor que você tem à mão e o passa a outra criatura. Não carregue o valioso à vista; derrubada pelas pernas, devolve tudo.
- `comportamento`: Não mata o que encontra. Arranca, carrega e passa adiante: o odre de um viajante vai parar no bico de outro bicho, a faca na mão de um Devorador. Leva a sela cheia para a borda sul e volta vazia.
- `gancho`: Daruun consome e redistribui, e tudo tem de passar por suas mãos; nos poços onde os Devoradores trocam cativos por água, o resíduo dele tomou o corpo da ave que levava as sobras de um lado para o outro.
- `lore`: Para os Devoradores de Sol tudo se troca: água por informação, cativo por água. Nos poços onde fazem essas trocas, uma ave corredora levava as sobras de um lado para o outro, e o resíduo de Daruun, que não tem poder próprio e vive do que passa pelas mãos, tomou-lhe o corpo. Hoje ela arranca o que os vivos carregam, espeta nas costas e entrega a outro. Os Devoradores não a caçam. Dizem que ela aprendeu com eles.
- eixos: sem mudança. (A Gralha de Crematório, NA, também rouba e devolve ao cair; aqui o que é roubado vai para outra criatura, e é isso que as separa.)

### T9 · brekmar · `mon_rixa_costurada` → **Estivador das Facas** (`mon_estivador_das_facas`)

- eixos: `plano_corporal: bipede_ereto` (era `acoplado`), `material: ferro_ferrugem` (agora verdadeiro), `escala: grande` (era `humana`; com `humana` daria 4 eixos iguais ao Anzolado da Casa), `locomocao: anda`, `percepcao: visao`, `papel_tatico: bruto_de_linha`. Atualizar a `vaga: 18`. Conferido: U2 único em Brekmar, U3 ≤ 3, R29 livre entre as crias de Vhrak.
- `mecanica_assinatura.carta`: `cri_estivador_das_facas_rixa_em_volta`
- `anatomia.texto`: Um estivador de sindicato que levou uma faca em cada noite de guerra entre os três e nunca deixou que tirassem nenhuma. O Ódio não as deixou cair: a carne cresceu em volta de cada lâmina, e a ferrugem delas passou para a carne, que endureceu em crostas vermelho-escuras como casco de ferro velho. São dezenas de facas, ganchos de estiva e pregos, de cabo para fora, em fileiras nas costas, nos ombros e nos antebraços, como uma crista de lâminas. Ficou mais alto e mais largo do que era. As mãos são grossas e cheias de cortes, e ainda seguram o gancho de estiva.
- `silhueta`: Um homem largo e alto com uma crista de cabos de faca e ganchos enferrujados saindo das costas e dos braços.
- `aparencia`: Estivador enorme de carne endurecida em crostas de ferrugem, dezenas de facas, ganchos e pregos cravados de cabo para fora em fileiras pelas costas, ombros e antebraços, mãos grossas cortadas, gancho de estiva na mão.
- `arte.visual`: Humano adulto muito largo e alto, roupas de estivador em farrapos; pele vermelho-escura endurecida em crostas de ferrugem; dezenas de facas, ganchos de estiva e pregos cravados no corpo de cabo para fora, em fileiras pelas costas, ombros e antebraços, como uma crista eriçada; mãos grossas cobertas de cortes segurando um gancho de estiva; rosto de raiva. Um só corpo: nada de dois corpos fundidos (essa leitura é dos Chifres Travados, Pradaria).
- `mecanica_assinatura.frase`: Onde ele está, a rixa pega: no fim de cada rodada, toda criatura encostada a outra perto dele, herói ou inimigo, dá um golpe de raspão no vizinho; a cada golpe trocado assim, a próxima pancada dele sai mais forte.
- `contra_jogo`: Lutar com espaço entre os heróis enquanto ele estiver de pé; ou levá-lo para o meio dos outros inimigos, onde a rixa fere os dele e não os seus.
- `telegrafo`: Os cabos de faca nas costas de {nome} se eriçam, e quem está perto sente a mão fechar na arma sem querer.
- `description`: Um estivador de sindicato de carne virada ferrugem em volta das facas que nunca tirou, que faz brigar entre si todos os que estão perto dele.
- `como_se_luta`: No fim de cada rodada, todos os que estão encostados perto dele trocam golpes, e ele fica mais forte. Deixe espaço entre os heróis, ou leve-o para o meio dos dele.
- `comportamento`: Anda devagar pelas ruas onde houve a briga e para onde há gente junta. Ataca quem estiver mais perto, mas o pior não é o golpe dele: perto dele, quem está lado a lado começa a brigar.
- `lore`: trocar "Às vezes dois mortos de lados opostos, cada um com a faca no peito do outro, levantam colados de frente, e a briga continua com quatro braços. Os sindicatos mandam gente buscar os seus de manhã, e às vezes os dois mandam buscar a mesma coisa." por "Há um estivador que levou uma faca de cada lado em cada uma dessas noites e não deixou tirar nenhuma, e a ferrugem passou para a carne. Onde ele para, quem está lado a lado começa a brigar, e os sindicatos já perderam gente para os próprios companheiros."

### T10 · deserto_zhur · `mon_altivo_do_vidro` (nome, id, mecânica e eixos ficam: `bipede_curvado/osso` passa a ser verdade na prosa)

- `anatomia.texto`: Um cativo dos Devoradores que tocou o resíduo de Urath no vidro e não caiu de joelhos como os outros. O orgulho do demônio tomou o esqueleto e o empurrou para a frente: a espinha arqueou para trás como um arco retesado, e o esterno cresceu para fora numa placa de osso branco, larga e lisa, estufada como peito de pombo, que rasgou a pele e vai à frente dele. As costelas se abriram em leque atrás dela, e o músculo vermelho aparece entre elas. A cabeça caiu para trás sobre os ombros e travou, com o rosto para o céu. As pernas são as de um homem, de joelhos travados e expostos. Não consegue olhar para baixo.
- `silhueta`: Uma figura de costas arqueadas para trás como um arco, peito de osso estufado para a frente e o rosto virado para o céu.
- `aparencia`: Figura de espinha arqueada para trás, esterno crescido numa placa de osso branco estufada para a frente, costelas abertas em leque com músculo vermelho entre elas, cabeça caída para trás com o rosto para o céu, joelhos travados e expostos.
- `arte.visual`: Humanoide grande, um palmo acima de um homem, de pé com a espinha muito arqueada para trás; o esterno projetado para a frente numa placa de osso branco, larga e lisa, que rasga a pele do peito; costelas abertas em leque, com músculo vermelho visível entre elas; cabeça caída para trás, travada, rosto voltado para o céu, olhos abertos; braços abertos e pendentes; pernas humanas de comprimento normal, joelhos travados e nus. Sem pernas de pau nem canelas alongadas (essa leitura é da Pernalta do Conselho, Aethelgard).
- `contra_jogo`: Não bater na placa do peito, que devolve; rasteiras e golpes nos joelhos travados o pegam por baixo, onde ele não olha, e quem bate de cima recebe de volta.
- `description`: Um cativo de espinha arqueada para trás pelo resíduo de Urath, de peito de osso estufado e rosto travado para o céu, que devolve cada golpe.
- `lore`: trocar "Nesses o orgulho toma os ossos e os empurra para cima até rasgar a pele. Andam de queixo para o céu," por "Nesses o orgulho toma o peito, estufa o osso para a frente até rasgar a pele e arqueia a espinha para trás. Andam de rosto para o céu,".
- `como_se_luta`: trocar "Não vê o chão; rasteiras e golpes nos joelhos o pegam por baixo." por "Não vê o chão; rasteiras e golpes nos joelhos travados o pegam por baixo."

### T11 · pradaria_ruinas · `mon_cabeca_acima` (nome, id e eixos ficam: `segmentado/osso/enorme` passa a ser verdade na prosa)

- `mecanica_assinatura.carta`: `cri_cabeca_acima_cabeca_baixa`
- `anatomia.texto`: Uma cria do Orgulho que tomou os ossos de um duelista élfico enterrado na arena da sua cidade. A espinha do morto não parou de crescer: virou uma corrente de vértebras grossas, comprida como três homens deitados, e de cada vértebra saem duas costelas curvas que pisam o chão como patas. A metade de trás se arrasta baixa no capim; a da frente se ergue reta no ar, e no alto dela vai o crânio, com o diadema do morto fundido ao osso da testa. Os braços do duelista ficaram presos logo abaixo do crânio, compridos, de quatro dedos de osso polido. Entre as vértebras há pouca carne, pálida e esticada, e tendões grossos que puxam a frente para cima. Nunca abaixa a cabeça.
- `silhueta`: Uma corrente comprida de vértebras sobre patas de costela, com a metade da frente erguida no ar e um crânio coroado no alto.
- `aparencia`: Corrente de vértebras grossas de três homens de comprimento sobre pares de costelas curvas, metade da frente erguida reta, crânio élfico com diadema fundido no alto, dois braços longos de quatro dedos de osso polido logo abaixo, pouca carne pálida esticada entre as vértebras.
- `arte.visual`: Criatura de osso enorme: uma coluna vertebral grossa de uns seis metros, cada vértebra com um par de costelas curvas fazendo de patas; a metade de trás rente ao capim, a metade da frente erguida na vertical; no topo, um crânio élfico de traços angulosos com um diadema de ouro fundido no osso da testa, voltado para o horizonte; logo abaixo do crânio, dois braços humanos muito longos terminando em quatro dedos de osso polido; carne pálida e escassa e tendões grossos esticados entre as vértebras. Nada de figura humana alta de pé (essa leitura é da Pernalta do Conselho).
- `mecanica_assinatura.frase`: Golpes fracos não o ferem; só o golpe forte entra, e cada golpe forte faz a frente erguida descer um anel; com três, a cabeça toca o chão, e ele passa a rodada seguinte se reerguendo, sem atacar e sem defesa.
- `contra_jogo`: Guardar força e bater pouco e forte, três vezes, até a cabeça tocar o chão, e então bater no crânio; golpes miúdos se perdem nas vértebras.
- `telegrafo`: {nome} ergue mais um anel de vértebras, e o diadema sobe acima de todos vocês.
- `description`: Uma cria do Orgulho nas arenas élficas em ruína, uma corrente de vértebras sobre patas de costela com a frente erguida e a cabeça coroada acima de todas, que nem sente golpe fraco.
- `como_se_luta`: Só o golpe forte o fere, e cada um baixa a cabeça dele um anel; com três, ela toca o chão e ele perde a rodada. Bata pouco e forte.
- `comportamento`: Fica nas arenas e praças das ruínas élficas, com a frente erguida acima de tudo, e não se digna a sentir golpe fraco. Cada golpe de verdade o faz baixar a cabeça, e baixar a cabeça é o que ele não suporta.
- `lore`: trocar "A espinha esticou, o pescoço cresceu, e a cabeça fica acima de tudo. Golpe fraco não o ofende; só o forte, e esse ele cobra." por "A espinha não parou de crescer, as costelas viraram patas, e a cabeça fica acima de tudo. Golpe fraco não o ofende; só o forte o faz baixar a cabeça, e isso ele não perdoa."

### T12 · ophidia · `mon_mastro_dos_ultimos` (só material e prosa da base)

- eixo: `material: sal_mineral` (era `couro_tecido`). Conferido: U2 único em Ophidia; U3 ≤ 3 (com `cinza` daria 4 contra a Fumaça de Cor Errada); R29 livre entre as crias de Dorrhen.
- `anatomia.texto`: trocar "A base é feita dos que chegaram primeiro, de pele cinzenta e costas largas como raiz;" por "A base é feita dos que chegaram primeiro, encrostados de sal até a cintura, a pele virada crosta branca e dura de anos de borrifo, de costas largas como raiz;"
- `aparencia`: trocar "base de pele cinzenta e costas largas" por "base encrostada de sal branco e duro, de costas largas".
- `arte.visual`: trocar "base larga de corpos cinzentos curvados como raízes" por "base larga de corpos cobertos de crosta de sal branco, curvados como raízes".

### T13 · skallgard · `mon_enegrecido_da_porta` → **Enegrecido que Espera** (`mon_enegrecido_que_espera`) — passa de Dorrhen a **Fehk**

- `origem_lore`: `detalhe: npc_fehk`; `refs`: trocar `lore_nova/npcs.txt:276` por `lore_nova/npcs.txt:306` (manter `creatures.txt:198` e `races.txt:344`).
- `papel_tatico`: `controlador` (era `guarda_protetor`; atualizar a `vaga: 20`). Conferido: U2 único em Skallgard. Se a cota U12 de `guarda_protetor` de Skallgard cair abaixo do mínimo, manter `guarda_protetor`: a mecânica trava quem chega perto e serve de guarda de área.
- `mecanica_assinatura.carta`: `cri_enegrecido_que_espera_hora_certa`
- `mecanica_assinatura.frase`: O herói mais perto dele começa cada rodada parado: não se move nem recua, e acha que foi escolha; quem o ataca nessa rodada se solta para a seguinte, e quem só se defende continua parado.
- `contra_jogo`: Atacar em vez de esperar: quem bate nele sacode o torpor. E fogo, que a carne morta de geada não aguenta.
- `telegrafo`: {nome} ergue a cabeça devagar para quem está mais perto, e a respiração dele fica calma, quase sensata.
- `description`: Cria de Fehk num caçador que o frio deixou sem mãos e sem pés porque ficou parado esperando a hora certa; os cotos pretos cresceram em tocos, e quem chega perto dele também para.
- `como_se_luta`: Deixa parado o herói mais perto dele; quem o ataca se solta, quem só se defende fica. Bata em vez de esperar, e use fogo.
- `comportamento`: Fica onde os amputados do frio são deixados para trás, nas bordas de Skallgard, deitado e calmo. Não corre atrás de ninguém: quem chega perto para, e ele morde quem ficou parado.
- `gancho`: No Norte o fraco não sobrevive ao inverno, e isso é tido por correto; ninguém volta para buscar os que ficaram. Fehk é a razão excelente para não voltar.
- `lore`: Os Nascidos do Gelo acham correto que o fraco não sobreviva ao inverno. Quem perde as mãos e os pés para o frio é deixado nas bordas da cidade, e ninguém volta para buscá-lo, por razões que todos acham sensatas. Fehk, a Covardia, vive dessas razões. O que ele deixou ali tomou um desses corpos antes da morte: um caçador que, numa nevasca, achou mais sensato esperar a hora certa do que andar, e esperou até as mãos e os pés ficarem pretos. Os cotos cresceram em vez de cair, e o corpo inchou até o tamanho de um urso. O Enegrecido não persegue. Quem chega perto dele começa a achar que o melhor é não se mexer.
- anatomia: sem mudança. (O Queimado de Frio, Montanhas, pune quem *para*; este faz parar. Nota P2.)

### T14 · montanhas_afiadas · `mon_tampao_da_camara` (nome e id ficam)

- `mecanica_assinatura.carta`: `cri_tampao_da_camara_aperto_do_vao`
- `mecanica_assinatura.frase`: Respira e aperta: a cada duas rodadas o tampão incha e esmaga todos os que estão encostados nele ou nas bordas do vão, e os braços puxam para junto dele quem chega perto; quem fica a dois passos não é alcançado.
- `contra_jogo`: Ficar fora do alcance dos braços e bater de longe ou com haste; cortar os braços das bordas faz ele escorregar do vão e parar de inchar.
- `description`: Cria do Desespero feita dos corpos esmagados na porta quando o teto cedeu; entope a porta e esmaga contra as bordas quem chega perto.
- `como_se_luta`: Incha a cada duas rodadas e esmaga quem está encostado; os braços puxam quem chega perto. Fique a dois passos e corte os braços das bordas.
- `comportamento`: trocar "Aparece na saída por onde se entrou, e a câmara fica fechada. Não persegue: tapa." por "Aparece na porta por onde se entrou. Não persegue: incha e aperta."
- `telegrafo`, anatomia e eixos: sem mudança.

### T15 · montanhas_afiadas · `mon_mapa_de_cicatriz` → **Marco que Aponta** (`mon_marco_que_aponta`)

- `mecanica_assinatura.carta`: `cri_marco_que_aponta_passo_errado`
- Só nome, id e carta. Fazer `grep -n "Mapa de Cicatriz\b"` na ficha de Montanhas e trocar onde aparecer por extenso (`description`, `lore`). A mecânica e o corpo (braço duro como marco de estrada) já são próprios.

### T16 · skallgard · `mon_queimado_de_breu` (nome e id ficam)

- `mecanica_assinatura.carta`: `cri_queimado_de_breu_bebe_a_luz`
- `mecanica_assinatura.frase`: Bebe a luz: ataca uma vez por rodada para cada luz acesa na cena (tocha, lanterna, fogueira), sempre em quem a carrega ou está mais perto dela; sem luz nenhuma, fica cego e só bate em quem encosta nele.
- `contra_jogo`: Apagar as luzes antes que ele chegue e lutar no escuro, de perto; com uma só luz acesa ele bate uma vez só.
- `telegrafo`: As lanternas perto de {nome} se inclinam para ele, e a crosta preta do peito começa a brilhar fosco.
- `description`: Caçador que chegou perto demais da chama negra do Farol e voltou; onde a anti-luz bateu, a pele virou uma crosta preta e fosca, e cada luz acesa perto dele é mais um golpe.
- `como_se_luta`: Bate uma vez para cada luz acesa na cena, em quem a carrega. Apague as luzes e lute de perto, no escuro.
- anatomia, eixos, `comportamento` e `lore`: sem mudança ("a luz morre devagar" segue verdade: ele a bebe).

### T17 · skallgard · `mon_feltro_do_ventre` (nome e id ficam)

- `mecanica_assinatura.carta`: `cri_feltro_do_ventre_o_vizinho_paga`
- `mecanica_assinatura.frase`: Enrola-se num herói e faz o vizinho pagar: todo Fôlego que o enrolado recuperar sai do herói mais perto dele; o Feltro não fica com nada.
- `contra_jogo`: Afastar-se de quem está enrolado até soltá-lo, e queimar ou cortar o feltro rente ao corpo; sozinho, o enrolado não tem de quem tirar.
- `description`: Cria de Veth feita do feltro dos canos do Ventre, com franjas de farpas de cobre; esfria o que envolve e faz o vizinho pagar pelo calor de quem envolve.
- `como_se_luta`: Enrolado num herói, tira do vizinho todo Fôlego que o enrolado recupera. Afaste-se do enrolado e queime o feltro.
- `telegrafo`, anatomia, eixos, `comportamento` e `lore`: sem mudança.

### T18 · montanhas_afiadas · `mon_costura_de_rancor` → **Peso dos Vencidos** (`mon_peso_dos_vencidos`)

- `mecanica_assinatura.carta`: `cri_peso_dos_vencidos_soco_de_cima`
- `mecanica_assinatura.frase`: O Orc soca de cima com o peso do monte inteiro: o golpe acerta um alvo e derruba quem estiver de pé logo ao lado dele. Cada pata de Goblin cortada tomba o monte para aquele lado; com três cortadas do mesmo lado, ele cai e passa a rodada seguinte se levantando, sem golpe.
- `contra_jogo`: Cortar as patas de Goblin sempre do mesmo lado até o monte tombar, e então bater no Orc caído; quem fica de frente e colado ao vizinho leva o soco e a queda.
- `telegrafo`: O Orc de {nome} ergue os dois punhos, e todas as mãos de baixo se fincam no chão ao mesmo tempo.
- `description`: Cria do Ódio nas Saídas Baixas, um tronco de Orc costurado sobre um monte de Goblins mortos que lhe servem de patas e o carregam odiando-o.
- `como_se_luta`: Soca de cima e derruba quem está ao lado do alvo. Corte as patas de um lado só: com três cortadas ele tomba e perde uma rodada.
- `comportamento`: trocar "quando ferida, as duas partes se voltam uma contra a outra e batem mais forte em tudo, inclusive em si mesmas." por "o Orc soca para baixo com o peso de todos, e as mãos de baixo o carregam aonde ele quer, odiando-o."
- `lore`: trocar "A coisa anda atrás de briga, e quando ferida as partes dela brigam entre si." por "A coisa anda atrás de briga, e os de baixo a carregam porque não conseguem largá-la."
- anatomia e eixos: sem mudança (`composto` bate com a prosa).

### T19 · montanhas_afiadas · `mon_mastro_de_trofeus` (nome e id ficam)

- `mecanica_assinatura.carta`: `cri_mastro_de_trofeus_rosto_do_ferido`
- `anatomia.texto`: trocar "e as tiras de tendão de cima se esticam como laços para agarrar." por "e as tiras de tendão de cima balançam soltas, batendo nos troféus."
- `mecanica_assinatura.frase`: No alto aparece o rosto do herói mais ferido: enquanto o rosto estiver lá, os golpes desse herói no Mastro saem pela metade, e cada Ferimento aberto que ele tiver deixa o Mastro mais duro contra os outros.
- `contra_jogo`: Fechar as feridas do copiado, ou tirá-lo de perto, apaga o rosto; os inteiros batem na estaca da base, que é o que o sustenta.
- `telegrafo`: O rosto no alto de {nome} se mexe e fica parecido com o de quem mais sangra.
- `description`: Cria da Crueldade nas Saídas Baixas, um mastro de troféus que avança cravando a própria estaca e mostra no alto o rosto do ferido, ficando mais duro quanto mais ele sofre.
- `como_se_luta`: Mostra no alto o rosto do mais ferido; os golpes desse herói saem fracos e cada ferida dele o endurece. Feche as feridas do copiado e deixe os inteiros baterem na estaca.
- `comportamento`: trocar "Laça o ferido com as tiras de tendão e segura, sem matar, e o rosto no alto vai ficando mais nítido enquanto a vítima sofre." por "Não laça nem segura: põe-se diante do ferido, e o rosto no alto vai ficando mais nítido, igual ao dele, enquanto ele sofre."
- `lore`: trocar "e laça com tiras de tendão, e no topo" por "e no topo".

### T20 · floresta_sussurros · `mon_virado_do_avesso` (nome e id ficam)

- `mecanica_assinatura.carta`: `cri_virado_do_avesso_dor_que_acelera`
- `mecanica_assinatura.frase`: Sente tudo, e a dor o acelera: cada golpe que leva lhe dá uma ação a mais na rodada seguinte, até três; uma rodada inteira sem levar golpe o acalma e zera a conta.
- `contra_jogo`: Bater uma vez por rodada, forte, ou deixá-lo uma rodada sem golpe para que se acalme; fogo e frio nos nervos à flor o fazem encolher e perder a rodada.
- `description`: Um viciado em Pó de Sonho de corpo virado do avesso, músculo por fora e nervos à flor, que a cada golpe recebido fica mais rápido e mais desesperado.
- `como_se_luta`: Cada golpe que leva lhe dá mais uma ação na rodada seguinte. Bata uma vez e forte, ou deixe-o se acalmar; fogo e frio nos nervos o fazem encolher.
- `comportamento`: trocar "Mas sente tudo, e qualquer golpe que o acerte é devolvido no mesmo instante, com a força de quem não aguenta mais uma dor." por "Mas sente tudo, e cada golpe que o acerta o faz se mexer mais depressa, de dor."
- `lore`: trocar "Não atacam primeiro, mas cada golpe que levam devolvem na hora," por "Não atacam primeiro, mas cada golpe que levam os faz ir mais depressa,".
- `telegrafo`, anatomia e eixos: sem mudança.

### T21 · skallgard · `mon_ferreiro_chama_fria` (nome e id ficam)

- `mecanica_assinatura.carta`: `cri_ferreiro_chama_fria_mao_no_cabo`
- `mecanica_assinatura.frase`: Agarra a mão de quem segura metal, e a chama fria a gela no cabo: até descongelar perto de fogo, o alvo não larga nem troca o que segura e só pode jogar Cartas daquela arma ou daquele escudo.
- `contra_jogo`: Quem foi pego aquece a mão numa chama, a sua ou a de um companheiro; e ele não larga a Fornalha: atraído para longe dela, as chamas dos pulsos se apagam.
- `telegrafo`: As chamas azuis nos pulsos de {nome} crescem, e ele estende a mão para a sua.
- `description`: Ferreiro da Fornalha de Vorr com as mãos pretas da chama-fátua azul e veios de liga nos dedos; gela no cabo a mão de quem segura metal.
- `como_se_luta`: Gela a mão do alvo no cabo da arma, que fica presa até descongelar no fogo. Aqueça a mão numa chama e afaste-o da Fornalha.
- `comportamento`: trocar "Agarra a arma de quem entra, e o metal fica azul e quebradiço na mão dele." por "Agarra a mão de quem entra armado, e a mão fica azul e presa ao cabo."
- `lore`: trocar "agarra a de quem entra, e a lâmina sai da mão dele azul e quebradiça." por "agarra a mão de quem entra, e ela fica azul e presa ao cabo até ver fogo." e trocar "o único tecnológico que já desarmou um deles" por "o único tecnológico que já fez um deles largar a luta sem largar a arma".

### T22 · skallgard · `mon_aperto_da_tregua` (nome e id ficam)

- `mecanica_assinatura.carta`: `cri_aperto_da_tregua_pacto_de_um_lado`
- `mecanica_assinatura.frase`: Agarra um herói pelo pulso num aperto de clã e o põe em paz com ele: enquanto o aperto durar, esse herói não pode atacar o Aperto, e o Aperto o ataca à vontade; outro herói que golpeie as mãos unidas desfaz o pacto.
- `contra_jogo`: Um companheiro golpeia o aperto das mãos, de preferência com fogo, que racha a carne; e ninguém aperta a mão que ele estende.
- `description`: Cria de Skarath feita de dois braços de clãs rivais presos num aperto de mãos; prende quem lhe aperta a mão num pacto que só vale para um lado.
- `como_se_luta`: Prende um herói num aperto que o impede de atacá-lo, e bate nele à vontade. Outro herói desfaz o pacto golpeando as mãos unidas, de preferência com fogo.
- `comportamento`: trocar "e espera o outro baixar a guarda." por "e espera que alguém lhe aperte a mão."
- `telegrafo`, anatomia, eixos e `lore`: sem mudança (a trégua do Fogo Alto segue como origem).

### T23 · deserto_zhur · `mon_guia_avesso` (nome e id ficam)

- `mecanica_assinatura.carta`: `cri_guia_avesso_mao_que_vira`
- `mecanica_assinatura.frase`: Põe a mão no ombro de quem estiver mais perto: na rodada seguinte, a primeira Carta de ataque do tocado acerta o companheiro mais perto dele em vez da criatura que ele escolheu.
- `contra_jogo`: Não deixar que toque: quem recua quando a mão vem, ou luta longe dele, não é virado. Tocado, jogar defesa em vez de ataque na rodada seguinte; e os joelhos dobram para trás, então um golpe de frente nas canelas o derruba.
- `description`: Um guia de caravana que vendeu a sua aos Devoradores e voltou do avesso, de cabeça virada para as costas e pele de sal, que põe a mão no ombro de quem confia e o faz golpear o companheiro.
- `como_se_luta`: Põe a mão no ombro, e na rodada seguinte o primeiro ataque do tocado acerta um companheiro. Recue quando a mão vem; tocado, defenda em vez de atacar.
- `comportamento`: trocar "põe a mão no ombro de quem confiou e, no passo seguinte, o golpe vem dessa mesma mão." por "põe a mão no ombro de quem confiou e, no passo seguinte, é a mão do próprio companheiro que bate."
- `telegrafo`, anatomia, eixos e `lore`: sem mudança.

### T24 · costa_negra · `mon_barata_das_costelas` (nome e id ficam)

- `mecanica_assinatura.carta`: `cri_barata_das_costelas_ricochete`
- `mecanica_assinatura.frase`: Rola e quica entre as costelas: acerta um alvo, ricocheteia no osso e acerta outro, até três, e para de barriga para cima onde terminar, aberta por uma rodada.
- `contra_jogo`: Lutar em areia aberta, longe das costelas, onde ela não tem em que quicar; e bater na rodada em que ela para virada.
- `description`: Um isópode do fundo do mar do tamanho de um barril, de placas afiadas, que se enrola e quica entre as costelas batendo em quem estiver no caminho.
- `como_se_luta`: Rola e quica entre as costelas, acertando até três alvos, e para virada uma rodada. Lute longe das costelas e bata quando ela estiver de barriga para cima.
- `telegrafo`, anatomia, eixos, `comportamento` (já diz "quicando nas costelas") e `lore`: sem mudança.

## Depois de aplicar

1. `bash scripts/dev/py.sh scripts/bestiario/lint.py` (global) e `--regiao` em cada uma das 8 regiões tocadas (todas menos Aethelgard, Nova Arcádia, Pântano e Selva): 0 erro; U6/U13 abaixo dos limiares; R29 sem aviso para as crias de Urath, Vhrak, Dorrhen e Maalrek.
2. Regerar Codex, doc de arte e `appearance` (`scripts/bestiario/gerar_docs.py`) e conferir que nenhum nome antigo sobrou (`Provador de Ophidia`, `Atirador de Olhos Vítreos`, `Iguana de Salmoura`, `Costura das Duas Cidades`, `Rixa Costurada`, `Costura de Rancor`, `Mapa de Cicatriz`, `Enegrecido da Porta`).
3. Criar `data/bestiario/_esteira.yaml` (G4) para o R27 rodar; com T8 e T13 ele passa (Fehk com 2 crias, anatomias `bipede_curvado/couro_tecido` × `quadrupede/carne_exposta`).
4. Esta revisão não pede nova rodada cruzada se as trocas forem aplicadas como estão; mudança de texto além delas volta para revisão.

## Comandos rodados (revisão cruzada)

```text
bash scripts/dev/py.sh <scratchpad>/ext.py           → 281 fichas não-retro extraídas (tabela compacta)
bash scripts/dev/py.sh - (Jaccard entre regiões)      → frase ≥0,28: 0 · contra ≥0,28: 1 (Barata×Rolador 0,33) · silhueta ≥0,33: 0 · telegrafo ≥0,33: 6 (máx. 0,40) · anatomia ≥0,22: 2
bash scripts/dev/py.sh scripts/bestiario/lint.py     → 368 fichas · 0 erro · 29 avisos (todos retro×retro)
bash scripts/dev/py.sh - (U2/U3/R29 dos eixos novos) → T8, T9, T10, T12, T13 sem colisão (Mastro com `cinza` dava U3=4; trocado por `sal_mineral`); T4 conferido à mão (U3=3 com a Gaivota Ladra)
```

Sem pytest (revisão de conteúdo); nenhuma ficha editada.

---

# Etapa 8 — revisão técnica (Sol)

> **Veredito:** `CHANGES_REQUIRED` (2 × P1, ambos pequenos; nenhum P0)
> **Revisor:** spec-reviewer (Opus, papel Sol) · **Data:** 2026-11-02 · **Commit revisado:** `830fb496` (branch `spec-349`, base `main` `15364c20`)

## Escopo

Etapas 5–7 (mecânica, baralho, arena, integração) e o sync com a `main`. A unicidade e a prosa já estavam revisadas acima e não foram refeitas. Revisados `scripts/bestiario/{gerar_mecanica,arena,calibrar,lint}.py`, `services/content_validator.py`, os testes novos `tests/test_spec349_*.py`, os testes de produto alterados, o `tests/fixtures/spec349_legado_snapshot.json` e os dados gerados: `data/bestiary.json`, `data/cards/criaturas/*.json`, `data/cards/inimigos/_decks.json` e `data/world/rumor_seed_overrides.json`. Os dados foram conferidos por script de comparação, sem leitura integral.

## O que está correto (conferido)

- **O gerador é determinístico e idempotente.** Reexecutei `gerar()` nas 12 regiões em memória (com `_write` capturado). O resultado ficou byte a byte igual aos 12 `data/cards/criaturas/*.json` commitados e às entradas de `bestiary.json`; o `_decks.json` também bate. Nenhuma criatura ficou sem mecânica.
- **Arena determinística.** Duas reexecuções seguidas, com as mesmas seeds, deram números idênticos. A contagem dos JSON commitados confere com a §9: 281 criaturas, 259 na faixa nos dois modos, 255 pelo veredito. A lista dos 22 fora da faixa está completa e com os valores certos (9 chefes). O delta de 8 pp só vale quando o slot estava na faixa antes, e os 4 que estouram o delta são os citados: Ent, Basilisco, Morcego e Esqueleto da Legião.
- **Cartas de criatura.** São 689 Cartas, todas com `kind` no catálogo fechado (`fx.all_kinds`). As condições aplicadas (`enraizado`, `cego`, `armadura_comprometida`, `desarmado_risco` e outras) existem em `combat_mechanics.NAMED_CONDITIONS` ou em `card_effects._CONTROL_BY_NAME`. `armadura_comprometida` é a única que nenhuma Carta antiga usava, mas está em `combat_mechanics.py:202`. Nenhum `dano_tipo` é novo. As linhas `aprox:` só usam a gramática existente, então nenhum efeito fora do motor foi introduzido. Orçamento, voz e nomes passam em `test_cartas_criaturas_lint`.
- **Slots (R3).** Os 32 slots alterados mantêm `id`, `categoria`, `arquetipo`, `virtudes`, `max_vitalidade`, `ferimento_espacos`, `regions`, `faction` e `behavior.profile` iguais aos da `main`. Em `attacks[]` só muda o `name`. Em `tactical_profile.priorities` só muda o `action_hint`. O único outro campo alterado é `type`, só em `enemy_aranha_de_cristal`, que passou a `BOSS`; `type` não está na lista congelada do R3. São 13 chefes (11 novos + Aranha + General), todos com fases 60/40 e `baralho_extra` oculto. Em `_decks.json` só a chave `fases` mudou: as 12 fases da `main` foram mantidas, e só as do General e da Aranha foram reescritas.
- **Sync com a `main`.** As 92 entradas legadas que não são slot estão idênticas à `main`. As mudanças da `main` desde a base antiga (SPEC-348 na descrição da Víbora; SPEC-355 com 5 arquétipos/Cartas de conjurador e `attacks.type: magic` em Djinn/Observador/Cultista) foram todas preservadas: no Djinn e no Observador, que são slots, só o `name` do ataque mudou. `rumor_seed_overrides.json` não perdeu nem alterou nenhum override da `main` (+3 novos).
- **Fixture (integridade de eval).** A alteração de `895db007` troca só `arquetipo` em 5 entradas `valoria` (Arpoador, Devorador, Orc, Pirata, Renegado), e os valores são exatamente os de `aee8750e` (SPEC-355) na `main`. O snapshot continua batendo com a `main` em todos os campos testados. É um reflexo da reclassificação feita na `main`, não um afrouxamento. `evals/` não foi tocado.
- **Testes alterados.**
  - `test_conflito_autoria_bestiario`: a varredura recursiva é mais estrita.
  - `test_boss_phases`: `== 12` virou `>= 12`, mas o loop continua exigindo 2 fases válidas para todo chefe.
  - `test_spec349_onda_nova_arcadia`: `cid in CUR` só exclui criaturas novas, que não são legado. `test_todas_classificadas` garante que as 124 legadas estão no `CUR`.
  - `test_enemy_decks` (teto de 15 só para a população da 332): é um afrouxamento real de um invariante de produto. Está registrado (§9 desvio 2 e follow-up 8a, coordenador 02/11) e tem uma trava nova (`<= 36`, uso atual 31). Os 32 slots continuam contados no teto de 15. Aceito como follow-up para a SPEC-336.
- **Compatibilidade 332/346.** Com `on`, `test_padrao_e_assinatura_validos` cobre as 281 criaturas (assinatura na rodada certa, telegrafo 1 rodada antes) e `test_chefe_fases` cobre os 13 chefes. A arena roda as 281 em `off` e `on`. Fiz uma checagem ad hoc de save/load (`persistence.save_game_state`/`load_game_state`) com instâncias de `mon_roda_de_mandibulas`, `enemy_gargula_ferro` e `mon_cavador_de_funil` em `enemies` e `bestiary_knowledge[enemy_gargula_ferro]`, nos modos `off` e `on`: o round-trip ficou idêntico.
- **LLM.** Nenhum `with_structured_output`/`get_llm` novo e nenhum segredo em log. `ruff` limpo nos arquivos novos.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `docs/spec349/arena-*.json`/`.md`; `specs/SPEC-349-bestiario-valoria-esteira.md:483`, `:619-663` | **Os números da arena estão defasados em relação ao HEAD.** A arena foi medida antes do rebase sobre a `main` (SPEC-362: Vitalidade do Arcanista 8, um dos 5 heróis da arena; SPEC-355/358 no motor) e antes de `895db007` (4 criaturas passaram a ataque `ranged`). A arena é determinística, mas os valores mudam no HEAD: `mon_cavador_de_funil` de 44/89 % para 46,5/88,5 % (`off` entra na faixa); `mon_convidado_de_cera` de 44/83 % para 41/83,5 %; `enemy_polvo_esgoto` de 44/71 % para 43,5/72,5 %; `mon_roda_de_mandibulas` de 62,5/50,5 % para 65/53,5 %; `enemy_aranha_de_cristal` de 53,5/28 % para 53/28,5 %. A lista "22 fora" e as contagens 259/255 do critério de aceite não valem para o código que vai pousar. | Reexecutar `scripts/bestiario/arena_todas.sh` no HEAD (~1 h). Remedir o baseline dos 32 slots com o `bestiary.json` da `main` atual no mesmo motor, senão o delta compara motores diferentes. Atualizar a tabela, a lista e o critério na §9. Aplicar ajuste só se alguma criatura cruzar a faixa, registrando em `_ajustes.yaml`. |
| P1-2 | P1 | `tests/test_spec349_*.py` (ausente); critério `specs/SPEC-349-…md:488` | O critério exige um teste de round-trip com save que tem `enemy_gargula_ferro` em `bestiary_knowledge`, e nenhum teste o cobre. A checagem ad hoc da revisão passa, mas não fica na suíte. | Adicionar o teste: um estado com 1 inimigo novo (de `ensure_combat_sheet`) + 1 slot em `enemies` e `bestiary_knowledge[enemy_gargula_ferro]`, `save_game_state` → `load_game_state` sob o `tmp_path` do conftest, conferindo `bestiary_knowledge`, `cartas`, `tactical_profile`, `max_vitalidade` e `appearance`. |
| P2-1 | P2 | `scripts/bestiario/arena.py:72` | `abs(w - base) * 100 > 8` com float: 0,535 → 0,455 dá `8.000000000000002`, e o Esqueleto da Legião Antiga (Δ −8,0 pp, que é ≤ 8) aparece como reprovado ("delta 8.0 pp > 8"). Com isso a contagem certa seria 256, não 255. | `round(abs(w - base) * 100, 1) > DELTA_MAX_PP`. |
| P2-2 | P2 | `specs/SPEC-349-…md:663` | Sinais errados: Basilisco `off` é −12 (não +12) e Esqueleto da Legião `off` é −8 (não +8). | Corrigir junto com o P1-1. |
| P2-3 | P2 | `data/bestiary.json` (16 slots); R3 em `specs/SPEC-349-…md:71` | O R3 pede Cartas próprias "com o mesmo `kind` de efeito … da carta substituída". Em 16 dos 32 slots um `kind` antigo some, por exemplo: `enemy_lobo_invernal` perde `dot`/`marca`, `enemy_aranha_lobo` perde `aplicar_condicao`/`esconder`, `enemy_sombra_espreitadora` perde `esconder` e `mon_jotun_cinza` perde `empurrao`. O desvio não está registrado. O equilíbrio é medido pelo delta da arena, mas o R3 literal não é cumprido. | Registrar na §9 como decisão (a mecânica segue a ficha reinventada e o equilíbrio é aferido pelo delta da arena) ou ajustar as Cartas. |
| P2-4 | P2 | `services/content_validator.py:1229` | `validate_bestiary_identity` chama `bl.lint_global(por_regiao)` sem `esteira=`. Assim o R27 (cobertura dos 13 demônios) não roda no `validate_content`/`test_fase71`, e nenhum pytest roda o R27, embora as 12 regiões já estejam `pousada` (o R27 só passa a falhar nesse estado). Hoje só `scripts/bestiario/lint.py` checa: 0 erro. | Ler `data/bestiario/_esteira.yaml` e repassar, como no `lint.py:51-58`, ou criar um teste `lint_global(..., esteira=...)` sem erro. |
| P2-5 | P2 | `tests/test_spec349_mecanica.py:182-184` | A docstring diz que o `type` do slot `enemy_aranha_de_cristal` "não muda (R3)" e fica fora de `_BOSS_TYPES`. Desde `950fa5b1` ele é `BOSS`. | Atualizar a docstring. |
| P2-6 | P2 | `tests/fixtures/spec349_legado_snapshot.json` (5 entradas SPEC-355) | A atualização trocou só `arquetipo`. O campo `cartas` dessas 5 entradas ainda é `bst_descarga_arcana`, enquanto a `main` tem outra Carta. Nenhum teste lê esse campo, então não há impacto, mas o snapshot fica incoerente com a origem declarada. | Atualizar também `cartas` dessas 5 entradas a partir da `main`, ou anotar no `_meta`/§9 que `cartas` não é campo congelado. |

## Pendências (aceitas, não bloqueiam)

- O teto de 15 usos por Carta de família vale só para a população da 332, e a trava `<= 36` vale para a esteira. Dono: SPEC-336 (crescer os pools de família).
- 9 chefes ficam abaixo de 45 % no `on`, por causa do baralho de família e das 2 ações por rodada. Já registrado na §9 (follow-up 8b).
- 4 slots genéricos ainda sem reinvenção (`enemy_lobo_sombrio`, `enemy_carniçal`, `enemy_esqueleto`, `enemy_goblin`). Estão listados no `PAINEL.md` e ficam inalterados, iguais à `main`.
- Os 145 efeitos aproximados (`aprox:`) são uma demanda de motor futura (tabela da §9).

## Comandos rodados

```text
bash scripts/dev/py.sh <scratchpad>/idem.py        → gerar() nas 12 regiões em memória: 0 diferença (cartas, bestiário, _decks)
bash scripts/dev/py.sh <scratchpad>/cmp.py/cmp2.py → snapshot × main × branch: 92 legadas idênticas; 32 slots só com campos de texto/Cartas/tactical; frozen iguais
bash scripts/dev/py.sh <scratchpad>/arena_chk.py   → 281 criaturas · 259 em faixa nos 2 modos · 255 veredito · 22 fora (bate com a §9)
bash scripts/dev/py.sh scripts/bestiario/arena.py --regiao deserto_zhur --seeds 40 --ids enemy_aranha_de_cristal,mon_cavador_de_funil  (2×) → idêntico entre si; difere do commitado (P1-1)
bash scripts/dev/py.sh scripts/bestiario/arena.py --regiao nova_arcadia --seeds 40 --ids mon_convidado_de_cera,enemy_polvo_esgoto,mon_roda_de_mandibulas → difere do commitado (P1-1)
bash scripts/dev/py.sh <scratchpad>/rt_check.py    → save/load com criaturas novas + bestiary_knowledge, off e on: ok
bash scripts/dev/py.sh scripts/bestiario/lint.py   → 368 fichas · 0 erro · 29 avisos
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_spec349_{mecanica,bestiary_lint,curadoria_legado,onda_nova_arcadia}.py tests/test_enemy_decks.py tests/test_conflito_autoria_bestiario.py tests/test_boss_phases.py tests/test_spec312_seeds.py tests/test_fase71.py tests/test_conflito_volume_conteudo.py tests/test_spec348_leaks.py → 812 passed
bash scripts/dev/py.sh -m ruff check scripts/bestiario services/bestiary_lint.py services/content_validator.py tests/test_spec349_*.py → All checks passed
```

Para virar `APPROVED`: P1-1 (arena e baseline remedidos no HEAD, §9 atualizada) e P1-2 (teste de round-trip). Os P2 podem entrar no mesmo commit, mas não bloqueiam.

---

# Etapa 8 — rodada 2 (Sol)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** spec-reviewer (Opus, papel Sol) · **Data:** 2026-11-02 · **Commit revisado:** `cb0e03a6` (rebaseado na `main` `48cd2b45`, com a SPEC-350)

## P1/P2 da rodada 1

| ID | Status | Conferência |
|---|---|---|
| P1-1 | resolvido | Arena e baseline remedidos no HEAD. Reexecutei 3 criaturas no HEAD (`mon_besouro_do_estalo` 75/85,5 %, `mon_isca_amarrada` 43/76,5 %, `enemy_esqueleto_legiao_antiga` 48,5/41,5 %) e os valores são idênticos aos commitados. A recontagem dos JSON dá 281 criaturas, 253 na faixa nos dois modos, 247 pelo veredito e 28 fora, como na §9. Não reproduzi o baseline da `main`, porque isso exigiria um worktree da `main` com `arena.py`; os valores mudaram pouco e de forma coerente com a deriva do motor. |
| P1-2 | resolvido | `tests/test_spec349_mecanica.py:240-273`: round-trip `off`/`on` com Roda de Mandíbulas e `enemy_gargula_ferro`, inclusive em `bestiary_knowledge`. Verde. |
| P2-1 | resolvido | `arena.py:72` usa `round(…, 1)`. |
| P2-2 | resolvido, mas a §9 nova tem sinais errados de novo | Ver P2-R2-2. |
| P2-3 | resolvido | Nenhum dos 32 slots perde um `kind` de efeito da Carta substituída. Conferido com script de comparação contra a `main`: 0 faltando. |
| P2-4 | resolvido | `content_validator.py` lê `_esteira.yaml` e repassa ao `lint_global`. |
| P2-5, P2-6 | resolvidos | Docstring corrigida; `cartas` do snapshot atualizado. |

## Arena: de 22 para 28 fora (pedido do coordenador)

Comparei criatura a criatura a arena da rodada 1 (`408ec5ec`) com a do HEAD, separando as 16 criaturas cuja mecânica mudou (P2-3) das outras 265:

- **P2-3 (16 slots):** efeito líquido zero. Uma criatura sai da faixa (`enemy_esqueleto_legiao_antiga`, `on` 49,5 % → 41,5 %) e uma entra (`enemy_esqueleto_mago`, `off` 43 % → 47,5 %). A variação média é de 3,1 pp, com máximo de 12 pp.
- **Rebase (mecânica intacta):** 6 criaturas saem da faixa e nenhuma entra. A variação média é de 1,3 pp, com máximo de 5 pp. Todas estavam na borda: `mon_besouro_do_estalo` `on` 85 → 85,5 %; `mon_mapa_de_cicatrizes` `off` 45,5 → 41 %; `mon_desafiante_rubro` `on` 45 → 44 %; `enemy_troll_ponte` `off` 46,5 → 44,5 %; `mon_isca_amarrada` `off` 47,5 → 43 %; `mon_ticao_do_juramento` `off` 46,5 → 42,5 %.

**Conclusão:** a piora vem da deriva do motor depois do sync (SPEC-350/355/362 no herói e no motor), não da correção P2-3. É ruído de borda (|Δ| ≤ 5 pp) em criaturas que já estavam a 0–2,5 pp do limite. Acho aceitável como exceção nominal, desde que o critério de aceite reflita os números novos (P2-R2-1). Não recomendo recalibrar agora: a calibração seguiria o motor, que ainda muda com o épico de cartas. Os 6 slots que estouram o delta estão todos na faixa absoluta e entram como follow-up.

## Teste da SPEC-289 (integridade)

A mudança é legítima e não esconde nenhuma regressão da lógica da 289. Rodei o arquivo novo sem a fixture e o arquivo da `main` contra o HEAD. As falhas são todas de "a única temática da esfera" ou de um conjunto exato:
- o Alambique de Carne é combatente da Destilação, temático de verdade;
- o Pajem de Obsidiana, slot reinventado, passou a ser elite temático da Chama Azul;
- a Quimera virou Ariranha e saiu do tema.

A fixture mantém a população anterior à esteira, inclusive os 32 slots com nomes novos, então a lógica de escolha continua coberta pelos mesmos casos. O teste novo cobre a população cheia, com uma garantia mais fraca: "sempre dentro do tema" em vez de "conjunto exato". Remover o Pajem só para exercer o fallback de porte é correto: o ramo continua testado.

**Ressalva (P2-R2-3):** a mesma fixture também tira das asserções o **Camarão Faxineiro**, que só entra no tema da Destilação por coincidência de radical (`_theme_stems`: "Camarão" → `camara`, igual ao "câmara" do texto de Corvane). Na população real, um encontro de ameaça do culto da Destilação pode sortear um camarão faxineiro como "criatura temática". O teste novo aceita isso porque `theme(entry) > 0`. É um falso positivo de produto que a 289 já permitia e a 349 expôs. Não bloqueia, mas precisa de follow-up, e a §9 item 10 deveria tratá-lo como falso positivo e não como "temática legítima".

## Sync

- `data/graph/entities_extra.json`: 96 → 348 entidades. Nenhuma removida em relação à `main`. As 29 alteradas são todas slots `generico` renomeados. A `main` não mexeu nesse arquivo desde a base anterior.
- `rumor_seed_overrides.json`: 51 → 54, nenhum override da `main` removido ou alterado.
- `faiss_lore_index` (`e32601a5`): reindexado depois do rebase. O `index.pkl` contém os docs da SPEC-350 (`npc_tr_anselmo_tiza`) e os da 349 (`mon_roda_de_mandibulas`, `mon_besouro_do_estalo`), então nada da 350 se perdeu.
- `_decks.json` e as entradas legadas de `bestiary.json`: não foram alterados pela 350; as conclusões da rodada 1 continuam válidas.

## Achados da rodada 2

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-R2-1 | P2 | `specs/SPEC-349-bestiario-valoria-esteira.md:483`, `:488` | O critério de aceite ainda diz "259/281 … 255/281". O critério de saves continua `[ ]`, embora o teste exista e passe. | Trocar para 253/281 e 247/281 e marcar o critério de saves. |
| P2-R2-2 | P2 | `specs/SPEC-349-…md:669` | Sinais errados: Verme de Vidro `off` é **+8,5** (53 → 61,5 %) e Basilisco `on` é **+11,5** (54 → 65,5 %). | Corrigir os sinais. |
| P2-R2-3 | P2 | `world_utils.py:819-834` (`_theme_stems`); §9 item 10 | O Camarão Faxineiro casa com o tema da Destilação só por radical (`camara`), um falso positivo exposto pela esteira. | Follow-up: stop-list ou exigir um radical de substantivo da facção/ameaça. Registrar como falso positivo na §9 e no hand-back (spec de mundo/ameaça). |

## Pendências (aceitas)

- 28 criaturas fora de 45–85 % e 6 slots acima do delta de 8 pp: exceções nominais da §9, a reavaliar quando o motor de cartas estabilizar.
- As pendências da rodada 1 continuam: teto de família na SPEC-336, chefes no `on` e os 4 slots ainda genéricos.

## Comandos rodados

```text
bash scripts/dev/py.sh <scratchpad>/cmp_arena.py   → rodada 1 × HEAD: P2-3 líquido 0 (1 sai, 1 entra); rebase 6 saem (|Δ| médio 1,3 pp, máx. 5)
bash scripts/dev/py.sh <scratchpad>/arena_chk.py   → 281 · 253 nos 2 modos · 247 veredito · 6 slots acima do delta
bash scripts/dev/py.sh scripts/bestiario/arena.py --seeds 40 --ids mon_besouro_do_estalo,mon_isca_amarrada,enemy_esqueleto_legiao_antiga → idêntico ao commitado
bash scripts/dev/py.sh <scratchpad>/r3b.py         → 0 slots perdendo kind
pytest (scratchpad) test_spec289 sem fixture + versão da main → falhas só de "conjunto exato"/"única temática" (Alambique, Pajem, Camarão)
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_spec349_{mecanica,bestiary_lint,curadoria_legado,onda_nova_arcadia}.py tests/test_enemy_decks.py tests/test_conflito_autoria_bestiario.py tests/test_boss_phases.py tests/test_spec312_seeds.py tests/test_fase71.py tests/test_conflito_volume_conteudo.py tests/test_spec348_leaks.py tests/test_spec289_ameaca_tematica.py → 835 passed
```
