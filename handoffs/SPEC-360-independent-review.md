# SPEC-360 — revisão de fauna (Nova Arcádia)

> **Veredito:** `CHANGES_REQUIRED` (conteúdo: 12 entradas a ajustar, nenhuma a refazer; nenhum achado de código)
> **Revisor:** Opus (`claude-opus-5-5`), papel `spec-reviewer` de fauna, independente do autor · **Data:** 2026-11-02 · **Commit revisado:** `31fdeee1`

## Escopo

- Branch `spec-360` (sobre `spec-349`), worktree `rpg-spec-360`, commit `31fdeee1`.
- Arquivo revisado: `data/bestiario/fauna/nova_arcadia.yaml` (38 entradas, todas `revisao: pendente`): 27 fichas da SPEC-349 e 11 legados `valoria` da região.
- Fontes cruzadas: `data/bestiario/fichas/nova_arcadia.yaml` (anatomia, comportamento e gancho de cada ficha), `data/bestiary.json` (descrição dos legados), `data/cards/inimigos/_decks.json`, `lore_nova/secrets.txt` e `data/codex/**` (só por Grep).
- Checklist aplicado: §3.8 da spec (vestígio, coerência com o corpo, cadeia alimentar, horário e estação, rumor, reskin e `imediato`), mais os critérios do dono: corpo físico com corrupção, tom de Valoria, nada genérico, sinal legível com contra-jogo e nenhum segredo vazando.
- Fora do escopo: o motor (`services/fauna.py`, `world_utils.py`, storyteller), cuja revisão é do Sol (`handoffs/SPEC-360-sol-review.md`), e o eval.
- **Campo `revisao:` não foi alterado.** A spec (§3.7, item 3) manda o revisor registrar o parecer no handoff. As correções voltam ao autor até `revisao: aprovada`. A troca para `aprovada` (com `revisor_fauna: opus-spec-reviewer`) cabe ao coordenador ou ao autor depois das correções, nas 26 entradas `ok` agora e nas outras 12 depois do ajuste.

## Parecer por criatura

Legenda: **ok** = aprovável como está · **ajustar** = correção pontual (achado na tabela abaixo) · **refazer** = nenhuma.

| # | Id | Veredito | Nota (trecho da ficha que sustenta, ou o problema) |
|---|---|---|---|
| 1 | `mon_arame_vivo` | ok | O rastro de arame na lama e o rangido vêm de "arrasta o arame no chão", "laços enferrujados que rangem". A reação à chuva e à praga segue a ficha ("semanas de chuva, quando a Praga sobe"). A presa rato é fraca, mas aceitável: ele drena sangue por contato. |
| 2 | `mon_fole_de_costela` | ok | Os dois apitos e o chiado vêm de "duas fendas que apitam" e "fole que infla". O lenço no poste vem de "lenço molhado atado". Bom. |
| 3 | `mon_rosario_de_vertebras` | ok | O resto é a farpa de osso, e a marca é o rato com uma só mordida ("morde uma vez; depois segue a farpa"). O estalo de contas vem de "corrente de contas". Bom. |
| 4 | `mon_fila_de_grilhoes` | **ajustar** | F-04: o `resto` com rolo de contrato confunde com a Escritura. A `marca` não se lê. |
| 5 | `mon_relicario_de_osso` | ok | Lascas e estalos vêm de "lascas que voltam a crescer", "estalam ao esfriar". O rumor reproduz "quem corre... leva uma lasca". Detalhe P2: o `cheiro` diz "gosto de pedra" (F-15). |
| 6 | `mon_sangrado_da_clinica` | ok | As marcas de mãos e joelhos no alto do muro vêm de "aos saltos pelos muros". O cão branco sem sangue e o pedido de desculpa também estão na ficha. Excelente. |
| 7 | `enemy_sentinela_ferro` | ok | Os riscos na parede lisa e a libré vêm de "sobe pelas paredes lisas", "ainda usa a libré". A mancha morna é a percepção por calor. |
| 8 | `enemy_elemental_fogo_poluido` | ok | Escória com carne cozida, corpo deitado na fornalha e rumor do mestre de turno: tudo literal da ficha. A versão a manter no cluster "corpo deitado" de F-07 é esta. |
| 9 | `mon_lencol_de_chamine` | **ajustar** | F-07: a `marca` é reskin do Caído. F-03: o `foge_de` depende da presa da Gralha. |
| 10 | `mon_traca_do_sino_mudo` | ok | As asas de lata partidas em quatro vêm de "quatro lóbulos rígidos", o badalo mudo de "come o som" e os arranhões em anel de "ganchos para se pendurar". Esta é a versão a manter do sinal de "silêncio" (F-11). |
| 11 | `mon_gralha_de_crematorio` | **ajustar** | F-03: presa `mon_lencol_de_chamine` implausível. |
| 12 | `mon_porca_da_queda` | ok | Buracos de pata e chão cedido vêm de "afundam até a barriga", "onde ela se deita, o chão cede". Os dentes de toda espécie e o fedor de beco de viciado também estão na ficha. Excelente. |
| 13 | `mon_centopeia_da_torre_invertida` | **ajustar** | F-12: a `marca` repete o próprio `rastro` e é ambígua. O rumor entra no cluster do Oubliette (F-14). |
| 14 | `enemy_horror_esgoto` | ok | Lodo com vidro e osso, a grade arrancada e o fedor dos três anéis vêm de "do que os três anéis despejam", "boca que é um ralo". O horário segue "volta para baixo quando a rua acorda". |
| 15 | `enemy_polvo_esgoto` | ok | `imediato` justificado (emboscador, vem nadando pelo ar). O lodo nos varais é literal da ficha. Chuva `mais` e tempo limpo `menos`: coerente. |
| 16 | `enemy_gargula_ferro` | ok | As ventosas e o coaxar antecipado são da ficha. A presa traça é plausível para uma rã. Nota: a traça vive só no Anel de Ferro e a rã "não desce para a rua". O efeito é por região (E8), então passa. |
| 17 | `mon_sorvedouro_do_codigo` | ok | A bota de farda que para e muda de rumo, o amuleto queimado por dentro e a recitação vêm de "não corre; para, aponta", "recita o artigo". Presa Iniciado, e o Iniciado foge dele: cadeia social coerente. |
| 18 | `mon_pavio_da_lista` | **ajustar** | F-08: a `marca` de leque chamuscado no muro repete o `resto` do Fole na mesma área. O resto do conjunto é ótimo (o rastro com as quatro marcas quadradas da gaiola). |
| 19 | `mon_enxerto_da_fornalha` | **ajustar** | F-02: presa `mon_automato_fundicao` incoerente. F-13: gênero de "peitoral". F-10: o `cheiro` duplica a construção do Cão. |
| 20 | `mon_quebrado_de_vitrine` | ok | A coleira de prata com lasca de vidro, as unhas de vidro na cadeira e o canto de vidro raspando estão na ficha. |
| 21 | `mon_vira_costas_da_praca` | ok | As pegadas de lado e os casacos costurados vêm de "anda de lado", "casacos... costurados". Pressão de guerra `mais`, por causa das execuções: coerente. |
| 22 | `mon_roda_de_mandibulas` | **ajustar** | F-01: o demônio come a Porca por fome animal, sem base na ficha. |
| 23 | `mon_cavadeira_de_unhas` | **ajustar** | `imediato` justificado ("sai do piso por baixo"). F-12: o `resto` está ilegível ("lascas pretas e rachadas de terra"). O rumor entra no cluster do Oubliette (F-14). |
| 24 | `mon_convidado_de_cera` | ok | Pingos amarelos, castiçal sem vela, rosto oco encostado e joias alheias: tudo da ficha. P2 opcional: o `resto` e a `marca` usam a mesma imagem do rosto impresso. |
| 25 | `mon_escritura_rastejante` | ok | Espiral na poeira, selo partido com mordida e leitura de cláusulas: tudo da ficha. |
| 26 | `mon_portao_que_morde` | ok | Os dentes nas barras, o arrasto que para no batente e o rumor dos guardas que não são trocados são literais da ficha. |
| 27 | `enemy_golem_lixo` | **ajustar** | F-06: o `rastro` abre como o do Arame ("dois sulcos paralelos", mesma área). F-05: a `marca` de mãos entra no cluster de mãos do Anel de Lama. |
| 28 | `enemy_rato_peste_anel_lama` | ok | Fosso dos mortos, roer e bolhas: coerente com "se alimenta dos cadáveres jogados no fosso". |
| 29 | `enemy_degolador_mao_sombria` | **ajustar** | F-05: a `marca` de mão em fuligem inventa um sinal canônico da Mão Sombria que não está na lore e cai no cluster de mãos. `imediato` justificado (assassino de beco). |
| 30 | `enemy_soldado_legiao_ferro` | ok | A bota ferrada em passo marcado, o mendigo com a marca do escudo e o edital com lacre mole são ótimos. A presa Degolador é "supressão", não comida (ver F-16, nota de semântica). |
| 31 | `enemy_iniciado_chama_azul` | ok | O círculo de pedras, a pele queimada no pano e a mão queimada vêm de "queimadura auto-infligida". É a versão a manter no cluster de mãos (F-05). |
| 32 | `enemy_boss_valerius` | ok | As paredes que transpiram são **públicas** (`data/codex/locations/nova_arcadia.md:51`, `rumors/story_rumores_nova_arcadia.md:24`). Nada do segredo do pacto ou do lich vaza. |
| 33 | `enemy_boss_vibora` | ok | Nenhum sinal aponta para a identidade secreta (Velha Magda: carrinho de lixo, espetinho). "Figura miúda" na `aproximacao` (`:736`) é aceitável, porque o encontro já revelou o corpo. P2 opcional no cluster de pescoço (F-09). |
| 34 | `enemy_garrick,_o_silenciador` | **ajustar** | F-11: o `som` de "silêncio" é reskin da Traça na mesma área. F-12: o `rastro` não é um vestígio legível. |
| 35 | `mon_rato_caldeira` | ok | Pegadas queimadas na chapa e rebites roídos ainda mornos vêm de "mastiga rebites ainda quentes". |
| 36 | `mon_cao_rebite` | **ajustar** | F-10: o `resto` com "placa de metal rebitada" quase nomeia a criatura (espírito do R5) e o `cheiro` duplica o do Enxerto. |
| 37 | `mon_automato_fundicao` | ok | O círculo gasto em volta do forno, o punho afundado na porta e o pistão numa forja parada vêm de "ainda guarda seu forno". |
| 38 | `mon_locomotiva_penitente` | ok | Trilhos arrancados, minério roído e o apito com o chão tremendo antes vêm de "ganhou fome ao transportar minério". Pressão de abismo `mais`: coerente. |

**Contagem:** 26 ok · 12 ajustar · 0 refazer.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| F-01 | P1 | `data/bestiario/fauna/nova_arcadia.yaml:483` | `mon_roda_de_mandibulas` (cria de apetite, Crueldade) tem `presas: [mon_porca_da_queda]`. O §3.8 item 3 veta demônio que "come" por fome animal sem base na ficha, e a ficha diz que ela sobe "quando há sangue e plateia" e que "não para enquanto houver quem olhe". Com essa cadeia, matar Rodas faz Porcas proliferarem e vice-versa, um efeito sem sentido para a criatura. | `presas: []`. A reação `carcaca_recente: mais` (`:485`) já cobre o "sangue". O E15 segue folgado (verificar com o lint). |
| F-02 | P1 | `:419`, `:423`, `:425` | `mon_enxerto_da_fornalha` com `presas: [mon_automato_fundicao]`. A ficha diz "fareja sangue e vai direto para a armadura", e o autômato não tem sangue. Os dois guardam a forja dos mesmos Encapuzados, e o autômato é um único molde abandonado ("ainda guarda seu forno"), que não deveria "proliferar" com `PRESA_LIBERADA`. | Trocar a presa por `enemy_soldado_legiao_ferro` (armadura pesada e sangue, os dois gatilhos da ficha). Isso respeita o E7, porque o soldado não come o Enxerto. Ou deixar `presas: []`. Em `:423`, "Uma peitoral" → "Um peitoral" (F-13). |
| F-03 | P1 | `:236`, `:191` | `mon_gralha_de_crematorio` (pequena, `covarde_oportunista`, "nunca luta até o fim", rouba objetos) tem `presas` com `mon_lencol_de_chamine`, uma placa de brasa do tamanho de um lençol que explode quando ferida. A ficha da Gralha não fala em caça. A presa `mon_traca_do_sino_mudo` (mariposa para um corvídeo) é plausível. | Tirar `mon_lencol_de_chamine` das presas da Gralha e o `foge_de: [mon_gralha_de_crematorio]` do Lençol (`:191`). Se o autor quiser a relação, ela cabe como necrofagia (`reage: carcaca_recente`, que a Gralha já tem). |
| F-04 | P1 | `:87`, `:90` | Na `mon_fila_de_grilhoes`, o `resto` ("rolo de contrato rasgado e pisado") descreve o material do corpo da `mon_escritura_rastejante` (rolo de pergaminho), que fica no mesmo `na_anel_ferro` e no mesmo Mercado de Carne. O jogador lê o sinal e deduz a criatura errada. A `marca` ("a tinta das marcas de dívida foi raspada por dentro, à altura do pescoço") não forma imagem. | O `resto` deve vir do corpo da Fila: por exemplo, um colar de ferro aberto com um anel de pele mineralizada, cinza como pedra, ainda preso por dentro. A `marca` deve ser legível: por exemplo, o batente do portão do pátio gasto em faixa, na altura dos ombros, por muitos corpos que passam juntos. |
| F-05 | P1 | `:648`, `:599`, `:695` | Cluster de **marca de mão** no `na_anel_lama`: Degolador (mão de fuligem no batente), Velório de Sal (duas mãos brancas no chão) e Iniciado (mão queimada na parede). Três criaturas da mesma área com o mesmo sinal-imagem (§3.8 item 6). Além disso, a do Degolador inventa um sinal canônico da Mão Sombria ("aviso que os do Anel conhecem") que não existe na lore (Grep sem resultado em `lore_nova/` e `data/codex/`). | Manter o Iniciado (literal da ficha). Trocar a `marca` do Degolador por algo do ofício sem criar canon de facção: por exemplo, uma telha solta recolocada ao contrário no beiral, ou um pano preto de máscara preso num prego do telhado. No Velório, trocar a `marca` por um vestígio de sal que não seja mão: por exemplo, um catre vazio com um contorno de sal fino no lençol, como se alguém tivesse sido velado ali e levado. |
| F-06 | P1 | `:595` vs `:21` | O `rastro` do Velório de Sal ("Dois sulcos paralelos de joelhos arrastados…") abre igual ao do Arame Vivo ("Dois sulcos finos e paralelos riscam a lama…"), e os dois têm território `na_anel_lama`. O E12 passou (Jaccard < 0,5), mas a leitura humana é a mesma. | Reescrever o do Velório a partir do sal: por exemplo, uma trilha esbranquiçada na pedra da nave alta, áspera, que range sob a bota, como chão salgado de onde a água secou. |
| F-07 | P1 | `:200` vs `:174` | As `marca` do Lençol ("como se algo quente tivesse deitado ali") e do Caído do Cadinho ("a marca de um corpo grande deitado no metal, ainda quente") repetem a imagem do corpo quente deitado, e as duas ficam no `na_anel_ferro`. Com a Pajem (`:153`, "corpo encostado", morno) e a Porca (`:266`, "molde de um corpo enorme deitado"), são quatro impressões de corpo. | Manter a do Caído (literal: "deita na boca das fornalhas"). Trocar a do Lençol por algo próprio do enxame soldado: por exemplo, antenas finas como pelo, aos montes, grudadas na fuligem da boca de um cano, ou uma carapaça de barata solta, ainda laranja por dentro. |
| F-08 | P1 | `:405` vs `:44` | A `marca` do Pavio ("muro chamuscado de azul-fosco em leque") e o `resto` do Fole ("mancha de fuligem em leque no muro, ainda morna") são o mesmo vestígio (leque no muro) na mesma área (`na_anel_ferro`). | Trocar a do Pavio pelo que só ele tem, o fogo azul que sai da boca **e** a gaiola: por exemplo, as barras de uma grade de esgoto marcadas a quente em padrão de berço, ou o chão com um retângulo de pedra vitrificada de azul onde a gaiola foi posta. |
| F-09 | P2 | `:645`, `:732`, `:752` | Cluster de **ferida no pescoço** em humanoides: Degolador (corte fino), Víbora (furo na nuca) e Garrick (garrote). Todos são justificados pela identidade, e só Degolador e Víbora dividem a área (`na_anel_lama`). | Opcional: variar o `resto` da Víbora para algo que não seja o cadáver (por exemplo, uma dívida quitada à força: o livro do agiota com a página arrancada e a faca ainda cravada no balcão). |
| F-10 | P1 | `:797`, `:799` vs `:425` | No `mon_cao_rebite`, o `resto` traz "placa de metal rebitada" junto do rastro "pegadas de cão". O E10 passa porque "rebitada" ≠ "rebite" como token, mas o par entrega o nome (espírito do R5: "o jogador deduz; quem nomeia é o encontro"). O `cheiro` ("óleo de máquina e sangue fresco no mesmo lugar") repete a construção do Enxerto ("sangue fresco e de aço recém-temperado, juntos demais"), e os dois ficam em `na_anel_ferro`. "Óleo de máquina" aparece também no Rato de Caldeira (`:776`). | `resto`: tirar "rebitada" (por exemplo, "uma placa de metal curva, com furos nas bordas, caída ao lado, ainda com pelo preso"). `cheiro`: algo do cão de patrulha (por exemplo, couro de coleira molhado e ferrugem quente de chapa), sem "óleo" e sem "sangue juntos". |
| F-11 | P1 | `:753` vs `:219` | O `som` do Garrick ("Silêncio demais: os cães param de latir…") e o da Traça (badalo mudo, "até os passos ficam abafados") são o mesmo sinal, a ausência de som, no mesmo `na_anel_ferro`. A Traça é a dona legítima ("come o som"). | Garrick: um som do ofício. Por exemplo, o rangido fino de couro sendo torcido, ou o zunido curto de um fio de aço esticado de repente, e depois nada. |
| F-12 | P2 | `:751`, `:290`, `:510` | Vestígio pouco legível. No Garrick, "pegadas… param onde alguém falou alto pela última vez" pede que o jogador saiba onde alguém falou. Na Centopeia, a `marca` "do corte em diante pegadas que sobem a parede" duplica o próprio `rastro` (furos subindo a parede) e é ambígua (pegadas de quem?). Na Cavadeira, o `resto` "lascas pretas e rachadas de terra" deveria dizer **unha**. | Garrick: pegadas que param diante de portas, coladas à soleira, como quem escuta. Centopeia: manter o corte em tesoura e trocar a segunda metade (por exemplo, o morto tem a boca e o nariz tapados com a própria mão, como quem prendeu o fôlego até o fim). Cavadeira: "lascas pretas de unha rachada, aos montes…". |
| F-13 | P2 | `:423` | "Uma peitoral de armadura" (gênero). | "Um peitoral de armadura aberto…". |
| F-14 | P2 | `:292`, `:515`, `:757`; `:155`, `:448`, `:717` | Molduras de testemunha repetidas no `rumor`. Há três "preso/fugitivo do Oubliette jura/diz" (Centopeia, Cavadeira e Garrick) e três "criada/criado do Palácio/Anel Dourado" (Pajem, Quebrado e Valerius). "Jura" aparece 9 vezes nas 38 entradas. | Variar a testemunha em pelo menos um de cada trio: por exemplo, Cavadeira → "uma mulher que lava o chão do porão de uma estalagem"; Quebrado → "um vidraceiro chamado à casa para trocar uma janela". Trocar alguns "jura" por "conta"/"garante"/"repete". |
| F-15 | P2 | `:109` | O `cheiro` do Relicário diz "gosto de pedra molhada". | "Água parada com cheiro de pedra molhada e, por cima, cera de vela velha." |
| F-16 | P2 (nota) | `:662`, `:376` | Presas "sociais": Soldado → Degolador e Sorvedouro → Iniciado. A semântica de `presas` no motor é supressão: matar Soldados libera Degoladores (ótimo, política emergente), mas suprimir Degoladores deixa a patrulha "faminta" (`PREDADOR_FAMINTO` ×0,5), o que é discutível. | Aceito como está na Fase 1. Registrar na 360-B ou 360-D se `presas` entre humanos deve usar só `PRESA_LIBERADA` (ou um campo `suprime`). |

## Achados transversais (fora das 38 entradas)

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| X-01 | P1 (processo) | `scripts/check_handoff_names.py:18-20`; `tests/test_handoff_names.py` | O nome que a spec manda para este parecer (`handoffs/SPEC-360-fauna-review-nova_arcadia.md`, §2 R7, §3.1) **não casa** com o `PATTERN` do lint de handoff (`SPEC-NNN[-papel]-tipo.md`). Com este arquivo commitado, o `test_handoff_names` fica vermelho na suíte completa. | O coordenador decide antes do pouso entre (a) ampliar o `PATTERN` para aceitar `-fauna-review-<regiao>` (vale para a 360-B, uma por região) e (b) renomear para `SPEC-360-independent-review.md` e atualizar a spec. O revisor não edita o lint (escopo). |
| X-02 | P2 (follow-up 360-C) | entradas `fonte: legado` (`:628`, `:651`, `:674`, `:698`, `:718`, `:738`, `:758`, `:780`, `:803`, `:823`, `:845`) | O `contra_jogo` dos 11 legados promete efeitos mecânicos ("longe do calor eles ficam lentos", "parada, ela não vira", "com tocha acesa eles se espalham") que nenhum deck sustenta. Nenhum desses ids tem deck em `data/cards/inimigos/_decks.json`. Na Fase 1 é texto inerte, mas a 360-C vai **revelar** o contra-jogo ao jogador. | Na 360-C, só revelar o `contra_jogo` de legado que tenha mecânica correspondente, ou reescrevê-lo como conselho tático sem prometer efeito. |
| X-03 | P2 (fora da 360, já na `main`) | `data/codex/monsters/mon_mao_sombria_agentes.md:15` (`visibility: public`) | O codex **público** diz "sob a Velha Magda", e a identidade da Víbora é segredo (`lore_nova/secrets.txt:43-46`, `data/codex/secrets/secret_identidade_vibora.md`). O vazamento é anterior (commit `07973b8a`) e não é do bloco de fauna. | Abrir follow-up de lore/segredos (348/350): trocar por "sob uma liderança que ninguém nomeia". |

Verificado sem achado: nenhum sinal ou rumor cita segredo `hidden`/`secret` (Valerius lich/pacto, identidade da Víbora, Praga de laboratório). Os rumores não têm números. `imediato` aparece em 3/38 (Bagre, Cavadeira e Degolador), todos emboscadores justificados, bem abaixo do teto do E14. Os horários não contradizem a prosa de nenhuma ficha (P5). As estações dadas (Arame, Lençol, Gralha, Caído, Bagre, Rã, Rato da Peste e Rato de Caldeira) batem com a prosa ou são neutras.

## Correções aplicadas

Nenhuma pelo revisor (o revisor não edita conteúdo). O autor aplica F-01…F-15 e roda o lint, o `build.py` e o teste de frescor.

**Autor (02/11, rodada de correções):** F-01…F-15 aplicados como pedido, inclusive o F-09 opcional (Víbora: livro do agiota). Uma divergência pontual: no F-12 da Cavadeira, "unha" é token do nome (`Cavadeira de Unhas`, o E10 singulariza), então o `resto` virou "Pontas de dedo quebradas, pretas de terra…". Arquivo renomeado de `SPEC-360-fauna-review-nova_arcadia.md` para este nome (X-01). As 38 entradas seguem `revisao: pendente` até a releitura (o autor não se autoaprova). Detalhe na §9 da spec. Depois, o coordenador ou o autor marca `revisao: aprovada` e `revisor_fauna: opus-spec-reviewer` nas 38 entradas. Se o autor divergir de algum P1, rebater neste arquivo.

## Pendências

- F-16 → 360-B/360-D (semântica de presa social).
- X-01 → coordenador, antes do pouso (nome do handoff × lint).
- X-02 → 360-C (revelação do contra-jogo de legado).
- X-03 → follow-up de lore (codex público vaza a identidade da Víbora; anterior à 360).

## Comandos rodados

```text
bash scripts/dev/py.sh scripts/check_handoff_names.py → EXIT 1 (este arquivo fora do PATTERN; ver X-01)
bash scripts/dev/py.sh scripts/fauna/lint.py --regiao nova_arcadia → nova_arcadia: 0 erro(s)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_spec360_schema_lint.py tests/test_spec360_build.py tests/test_spec360_sinais.py → 43 passed (exit 0)
```
