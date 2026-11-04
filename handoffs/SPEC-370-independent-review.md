# SPEC-370 — revisão de fauna (independent-review)

> Parecer de fauna por lote (R3). Uma seção por lote; este arquivo recebe os lotes 2–4.
> O nome pedido no spawn (`SPEC-370-lote1-independent-review.md`) não passa em
> `scripts/check_handoff_names.py:18-20` (o papel tem de ser sol/astra/terra/luna), então
> segue o nome que a própria spec fixa no R3.

## Lote 1 — Pântano da Melancolia, Brekmar, Skallgard

> **Veredito:** `APPROVED` (depois das correções de conteúdo abaixo, feitas pelo revisor)
> **Revisor:** Opus 5.5 (`spec-reviewer`, independente; `revisor_fauna: opus-370-revisor-lote1`; autor `opus-370-lote1`)
> **Data:** 2026-11-03 · **Commits revisados:** `dfd7ad67`, `489c3bd8`, `7fdfa47e` · **Correção:** `3d9cb47f`

### Escopo

`data/bestiario/fauna/{pantano_melancolia,brekmar,skallgard}.yaml` (30 + 26 + 31 = 87
entradas, 65 fichas + 22 legados) e o trecho da Víbora / migração `suprime` em
`nova_arcadia.yaml`. Checklist da SPEC-360 §3.8 (1–7) mais a SPEC-370 §3.4 (8–12), lido
contra as fichas (`data/bestiario/fichas/<r>.yaml`: anatomia, comportamento,
mecânica) e, no legado, contra `bestiary.json` (`tactical_profile.priorities[].action_hint`,
`cartas`, `resistances`, deck de fase). Ficaram fora: o motor, o avaliador e os testes
(revisão Sol).

### Achados

| ID | Sev. | Arquivo:linha (antes) | Problema | Correção |
|---|---|---|---|---|
| F-01 | P1 | `pantano_melancolia.yaml:636`, `brekmar.yaml:157`, `:202`, `:407`, `skallgard.yaml:211`, `:555` | Item 1: a `marca` mostrava o próprio corpo (nuvem do enxame, tronco de cracas, boia com dedos, volume de verrugas, tronco peludo congelado, ombro do gigante sob a neve), não um vestígio | Trocadas por vestígios: asinhas mortas na poça sem brilho; crosta de anos num casco novo; bolhas fixas contra a corrente; caranguejo preso por fios brancos; monte de geada sem pegada saindo; encosta que "respira" |
| F-02 | P1 | `pantano_melancolia.yaml:114`, `:119` vs `:257`, `:262` | Item 6 (reskin na região): Castor e Borda que Anda tinham o mesmo rumor (a borda medida mais perto da estrada) e o mesmo resto (fita de medição dos druidas) | Castor: rumor do canal represado que não baixa; resto do marco roído com marcas de dente. A Borda fica com o motivo da medição |
| F-03 | P2 | `pantano_melancolia.yaml:400`, `:584` | Item 6: quatro rastros do Pântano com o mesmo motivo, "pegadas que saem e nenhuma volta" (Regaço, Afogado, Druida, Cordão) | Regaço: passos cada vez mais curtos e arrastados até a beira; Afogado: tropa em formação na margem. Druida (levado pela mão) e Cordão (o par se separa) ficam |
| F-04 | P2 | `brekmar.yaml:516` vs `:221` | Item 6: Capangas e Sangria abriam com "Duas linhas de pegadas…" | Capangas: ronda de porta em porta raspando a soleira |
| F-05 | P2 | `skallgard.yaml:698` vs `:305` | Item 6: Urso-Titã e Montaria Cravada com a mesma marca (pinheiro arranhado no alto) | Urso: placa de neve deslizada com rasgo de quatro garras |
| F-06 | P2 | `pantano_melancolia.yaml:65`, `:70` | Item 2: Banhado é `escala: humana` ("velho largo e curvado", mãos enormes), mas o sinal falava em "pegadas enormes" e "velho imenso" | "Pegadas fundas e largas"; "velho largo e curvado" |
| F-07 | P2 | `pantano_melancolia.yaml:591`, `:639`, `:663` | R5 (item 8): contra_jogo do legado prometia o que o baralho não tem: terreno (raso × terra firme) no Afogado e na Sanguessuga, e "ferrão que corrói" no Mosquito (ataque 1d4, cartas `fuga_suja`/`lodo_melancolia`/`coro_colmeia`) | Reescritos a partir do `action_hint` e das cartas: Afogado (resistência a perfurante, implacável), Mosquito (foge ferido, coro de colmeia), Sanguessuga (`mordida_infecciosa`, persegue o mais ferido, foge ferida) |
| F-08 | P2 | `skallgard.yaml:523` | Item 3: Enegrecido que Espera (cria de apetite que "morde quem ficou parado") caçando a Pulga de Forquilha não tem apoio na ficha; a Pulga come o que apodrece, e o Enegrecido é carne morta de gangrena. Das quatro relações da Pulga, era a única sem base | Removida. A Pulga segue com 3 predadores (Ermitão, Mandrião, Lobo da Aurora), todos de porte e hábito compatíveis. E15 continua verde |
| F-09 | P2 | `brekmar.yaml:183` vs `pantano_melancolia.yaml:429` | Item 12 (entre regiões): o mesmo molde de rumor, "mandam contar X antes de…" (luzes do píer × nós da corda) | Pescador: "o bêbado que segue a luz baixa do píer não chega ao barco" |
| F-10 | P2 | `brekmar.yaml:225` | A `marca` da Sangria era uma fala de mercador, não uma marca física | Corte do mercador fechado por uma placa de casca que não é dele |

Conferido e **mantido** (pontos que o autor pediu para olhar):

1. **`suprime` novos.** Todos são entre humanos/ordens com conflito social ou de território, nunca bicho e presa (item 10). Banhado→Casaco é guarda da linha contra saqueador do fundo ("quem vem tirar armadura do fundo ele enfrenta", ficha). Sangria→Capangas é guarda-costas de mercador contra cobrador de sindicato. Ambos aceitos. Casaco→Mula é o mais fraco (territórios quase disjuntos), mas a Mula já `foge_de` Casaco e o efeito é só `PRESA_LIBERADA`: fica.
2. **Demônio comendo humano.** Regaço→Mula se apoia na ficha: o Regaço é resíduo da Tristeza e a Mula carrega Lágrimas que fazem "a tristeza escorrer". Sino→Anzolado também: o Sino vem do resíduo da Casa das Marés, vai atrás de quem está mais sozinho, e o Anzolado é o frequentador da Casa que perdeu o tato. Cisne→Fardo (o Cisne ataca o que brilha; o Fardo carrega moeda e cálice) fica. Boia→Rato e Pescador→Cardume (o Pescador tem porte humano e o Cardume é do tamanho de um bote) são plausíveis no limite; seguem como nota, sem bloquear.
3. **Estações extras** (Mosquito, Sapo, Cágado, Lagarta, Ermitão, Lobo da Aurora, Verme, Titã): todas coerentes com a prosa (insetos no verão; degelo solta o ferro do Ermitão; a Lagarta congela no frio; aurora e neve compacta no inverno). R4: `enemy_lobo_invernal` e `enemy_yeti` carregam inverno 1,5, como em `calendar.json:45`.
4. **Cordão e Viúva** como 2 `imediato` no hub `pantano_melancolia`: está no teto do E18, mas é justificado. O Cordão se disfarça de corda-guia e a Viúva é emboscadora nos marcos (`descoberto → recua para a ocultação`). Brekmar e Skallgard têm 1 cada no hub.
5. **Víbora em NA** ("faca cravada" → "tinteiro virado"): correto. A faca continua só na `marca`, e o R2-02 da 360 fica fechado.
6. **contra_jogo do legado a partir de `action_hint`**: o método é bom e executável. `enemy_declaration` usa `alvo_vulneravel` para mirar (`services/conflict_orchestrator.py:651-656`), e os detalhes vêm das cartas (`mimetismo_morto` → o Cervo "se esconde entre os mortos"; `fenda_sonica` → o chiado do Rato e o grito do Corvo; `roubar_calor` → Lobo da Aurora; `sino_brekmar` → provocação do Cobrador; `carregar_ruina` → carga da Viúva). Só F-07 precisou de ajuste.
7. **Sinais parecidos entre regiões**: a amostra por Jaccard (NA × lote 1, mesmo tipo) tem máximo 0,31 e nenhum par com a mesma imagem, salvo F-09. O par Soldado da Legião (NA) × Afogado da Batalha (botas no mesmo passo) ficou distinto depois do F-03.

Observações sem correção: no legado, o Torcido tem cauda (ficha `brekmar.yaml:869`), então o rastro está certo. O Urso-Titã "recua ferido de morte" segue o perfil (`plano_falhou → flee`), embora a `description` diga que ele não foge; isso é dívida de lore do legado, fora da fauna.

### Correções aplicadas

`3d9cb47f`: F-01 a F-10, as 87 entradas com `revisao: aprovada` e `revisor_fauna: opus-370-revisor-lote1`, `fauna.json` e `rumor_seeds.json` regenerados e `docs/spec360/eval-skallgard.md` reescrito pelo eval (o M3 perdeu a linha do Enegrecido e o hash do M7 mudou, com as duas execuções iguais).

### Pendências

- Nota de autoria para os próximos lotes: `marca` é vestígio, não o corpo disfarçado. Disfarce (isca, tronco, lixo) vai na `aproximacao`.
- Boia→Rato e Pescador→Cardume: plausíveis no limite. Reavaliar se a 372 (tramas) precisar de cadeia mais forte em Brekmar.

### Comandos rodados

```text
scripts/fauna/lint.py --regiao {pantano_melancolia,brekmar,skallgard,nova_arcadia} → 0 erro cada
scripts/fauna/build.py → fauna.json: 125 criaturas
scripts/build_rumor_seeds.py → ok
scripts/validate_content.py → 0 ERRO(S) · 29 AVISO(S)
scripts/fauna/eval.py --regiao pantano_melancolia → todos os gates ok (M1 0,8305 / legado 0,839; M8 0,2758; M5 −0,1632)
scripts/fauna/eval.py --regiao brekmar → todos os gates ok (M1 0,7921 / 0,7938; M8 0,2773; M5 −0,1452)
scripts/fauna/eval.py --regiao skallgard → todos os gates ok (M1 0,7375 / 0,7726; M8 0,3017; M5 −0,1549)
pytest test_spec360_build test_spec312_seeds test_spec370_suprime test_spec370_caps → 33 passed
pytest -m "not slow" test_spec370_eval test_spec360_eval → passed (exit 0; os slow foram pulados)
pytest -m "not slow" test_spec370_eval test_spec360_eval → passed (os slow foram pulados)
```

## Lote 2 — Pradaria das Ruínas, Montanhas Afiadas, Aethelgard

> **Veredito:** `APPROVED` (depois das correções de conteúdo abaixo, feitas pelo revisor)
> **Revisor:** Opus 5.5 (`spec-reviewer`, independente; `revisor_fauna: opus-370-revisor-lote2`; autor `opus-370-lote2`)
> **Data:** 2026-11-03 · **Commits revisados:** `0488d235`, `b3fbdbf5`, `0350b9df` · **Correção:** `85b9615a`

### Escopo

`data/bestiario/fauna/{pradaria_ruinas,montanhas_afiadas,aethelgard}.yaml`: 33 + 33 + 30 = 96 entradas. Mesmo método do lote 1: checklist da 360 §3.8 e da 370 §3.4, lido contra a ficha e, no legado, contra `tactical_profile.priorities[].action_hint`, `cartas` e `resistances`. A leitura entre regiões usou o Jaccard por tipo de sinal nas 7 regiões com fauna; a adjacência vem de `world_pressures.region_adjacency()`.

### Achados

| ID | Sev. | Arquivo (entrada) | Problema | Correção |
|---|---|---|---|---|
| G-01 | P1 | `montanhas_afiadas.yaml` (`enemy_basilisco_caverna`), `aethelgard.yaml` (`mon_camarao_faxineiro`) | Item 1, igual ao F-01: a `marca` mostrava o corpo da criatura (a "pedra cônica a mais" e a nuvem do enxame) | Vestígios: estalagmites raspadas na base numa trilha lisa; feridas de um morto raspadas limpas, com cascas de muda listradas em volta |
| G-02 | P1 | `aethelgard.yaml` (`mon_pernalta_do_conselho`) × `pradaria_ruinas.yaml` (`mon_pernalta_das_colunas`) | Item 12: regiões vizinhas, duas criaturas de pernas de pau e o mesmo rastro, "dois furos fundos e finos a passos de gigante" | Aethelgard: redemoinhos de lodo espaçados demais, que contornam o mesmo quarteirão afundado |
| G-03 | P2 | `pradaria_ruinas.yaml` (`enemy_assassino_cinzeu`) × `nova_arcadia.yaml` (`enemy_boss_vibora`) | Item 12: as duas assassinas de regiões vizinhas usavam o mesmo molde de `aproximacao` ("de onde não havia ninguém, uma figura…") | O Cinzéu cego vira o rosto liso para o som da sua respiração (percepção da ficha) |
| G-04 | P2 | `pradaria_ruinas.yaml` (`mon_egua_de_costas`, `mon_cauda_emendada`), `montanhas_afiadas.yaml` (`mon_cabra_labirinto`) | Ponto 5 do autor: perífrases forçadas pelo E10 soavam artificiais ("animal de montaria", "animal de sela", "apêndice de osso", "bicho barbado") | "montaria", "rabo de osso" e "bode cinzento". Mantive "bicho magro de barbicha" na Cabra-Navalha, porque é natural e diferencia as duas |
| G-05 | P2 | `pradaria_ruinas.yaml` (`mon_cavaleiro_sem_rosto`) | R5: "lutar fora da linha que ele percorre" prometia efeito de terreno; o baralho tem `carregar_ruina` e `toque_gelido` | "cuidado com a carga dele, que atravessa cobertura e leva junto, e com o toque gelado" |

Conferido e **mantido** (pontos do autor):

1. **`suprime` mais fracos.**
   - Capturador/Carregador→Leitor: a rede de Groth compra e caça cativos (o Carregador é um Cinzéu comprado), e o Leitor lê cativos; é disputa entre redes de cativeiro.
   - Cavaleiro sem Rosto→Bandido: o patrulheiro morto da fronteira contra o bando de estrada. O rumor e o resto (bandido trespassado) sustentam.
   - Orc→Geodo: o bando de Gruumsha manda nas Saídas Baixas, onde vivem os refugiados, e o Geodo já `foge_de` Orc.
   - Os três são sociais ou de ordem, não tróficos (item 10).
2. **Presas no limite.** Aceitei todas:
   - Faísca→Doador: o fragmento procura recipiente e o Doador "ainda está tentando terminar".
   - Nadador→Biguá: puxa de baixo, na água rasa.
   - Véu→Mergulhador: vai até "quem tem mais coisa boa".
   - Novelo→Aspirante: as redes perdidas no raso, onde o Aspirante vive.
   - Cação→Ouriço: ele engole as pedras do fundo raso onde o ouriço forma tapetes.
   - Pernalta→Lagarto/Besouro: o resto do lagarto pregado de cima prova a relação.
   - Fuçador→Lagarto: javali é onívoro.
   - Lenço/Chicote→Cabra-Navalha: o Lenço derruba no precipício, e o resto mostra a cabra caída com marca de sucção.
   - Wyvern→cabras: o resto da cabra cortada na altura do peito.
3. **Estações extras.** Vestido de Gafanhotos e Gafanhoto de Runa no verão, Lobo da Pradaria e Queimado de Frio no inverno: coerentes com a prosa. R4: `enemy_wyvern_jovem` tem verão 1,5 (`calendar.json:46`).
4. **Territórios e horários alargados na Pradaria.** A prosa aguenta:
   - Nômade, Bandido e Capturador nos arredores de Solvhen: estrada, acampamento e mercado de cativos.
   - Necromante em Vaelorn: criptas élficas; o Desfiado o caça ali.
   - Lobo em Solvhen: o mais fraco, porque Solvhen é uma cidade viva (`lore_nova/locations.txt:393`). Os sinais falam de mato alto e de pastores, então o nó se lê como os arredores. Fica, para não mexer no M4.
5. **Perífrases**: ver G-04. "Lontra enorme" para a Ariranha é natural e ficou.

`imediato` no hub: Montanhas (Chicote e Mão da Borda) e Aethelgard (Nadador e Novelo) estão no teto de 2 do E18, todos justificados por disfarce ou tocaia. A Pradaria tem 1 (Cobra de Légua).

### Correções aplicadas

`85b9615a`: G-01 a G-05; as 96 entradas com `revisao: aprovada` e `revisor_fauna: opus-370-revisor-lote2`; `fauna.json` (221 criaturas) e `rumor_seeds.json` regenerados.

### Pendências

- Montanhas M5 −24,9 % (alerta informativo em −30 %, R17): acompanhar no M5 global da Etapa 7.
- O M1 de NA caiu de 0,7508 para 0,7366 com a Pradaria vizinha. Continua acima de 0,70 (R22), mas a folga encolhe a cada vizinho com fauna; vale para o coordenador acompanhar nos lotes 3 e 4.
- Fora da fauna: as fichas da Pradaria e de Aethelgard têm duas criaturas de pernas de pau chamadas "Pernalta". O sinal já foi diferenciado; o nome repetido é assunto da esteira de bestiário (U4).

### Comandos rodados

```text
scripts/fauna/lint.py --regiao {pradaria_ruinas,montanhas_afiadas,aethelgard,nova_arcadia} → 0 erro cada
scripts/fauna/build.py → fauna.json: 221 criaturas · build_rumor_seeds.py → ok · validate_content.py → 0 ERRO(S)
eval --regiao pradaria_ruinas → gates ok (M1 0,7504 / legado 0,7622; M8 0,3181; M5 −0,177)
eval --regiao montanhas_afiadas → gates ok (M1 0,7993 / 0,8158; M8 0,304; M5 −0,249)
eval --regiao aethelgard → gates ok (M1 0,805 / 0,8099; M8 0,2781; M5 −0,163)
eval --regiao nova_arcadia → gates ok (M1 0,7366 / 0,7433; M8 0,3127)
pytest test_spec360_build test_spec312_seeds test_spec370_suprime test_spec370_caps → 33 passed
pytest -m "not slow" test_spec370_eval test_spec360_eval → passed (exit 0; os slow foram pulados)
```

## Lote 3 — Floresta dos Sussurros, Selva de Xylos, Deserto de Zhur

> **Veredito:** `APPROVED` (depois de uma correção de conteúdo feita pelo revisor)
> **Revisor:** Opus 5.5 (`spec-reviewer`, independente; `revisor_fauna: opus-370-revisor-lote3`; autor `opus-370-lote3`)
> **Data:** 2026-11-03 · **Commits revisados:** `dd12c9a6`, `4b5fcc59`, `c6049684` · **Correção:** `e9dec3e6`

### Escopo

`data/bestiario/fauna/{floresta_sussurros,selva_xylos,deserto_zhur}.yaml` (29 + 30 + 32 = 91 entradas), mais a edição do autor no `rastro` da Pernalta do Conselho (`aethelgard.yaml`). Usei o mesmo método dos lotes 1 e 2. A leitura entre regiões cobriu as 10 regiões com fauna; pela `region_adjacency()`, a Floresta é vizinha de Aethelgard, Pântano e Selva, a Selva só da Floresta e Zhur só de NA.

O lote é o mais limpo até aqui. As `marca` agora são vestígios (rede, cova, muda, ninho) e não o corpo disfarçado; os autores seguiram a nota do lote 1.

### Achados

| ID | Sev. | Arquivo (entrada) | Problema | Correção |
|---|---|---|---|---|
| H-01 | P2 | `floresta_sussurros.yaml` (`mon_picanco_de_espinheiro`) | Item 6: o `resto` do Picanço e o da Vespa Coveira mostravam a mesma vítima, um grilo branco do tamanho de um cão. Somado ao `resto` do próprio Saltão, eram três sinais com o grilo branco na mesma região | O resto do Picanço passa a mostrar a sua outra presa (Lagarta de Visgo espetada). O grilo fica com a Vespa e com o Saltão |
| H-02 | P2 (executor) | `services/fauna_lint.py` (E9) × `tests/test_spec360_sinais.py:313-318` | O lint aceita sinal de até 160 caracteres, mas `test_bloco_ate_60_tokens` exige `len(render_block(texto)) / 4 ≤ 60`, ou seja, bloco ≤ 240 caracteres com o prefixo, o que dá uns 135 caracteres por sinal. Um sinal pode passar no lint e quebrar a suíte; a edição do autor na Pernalta do Conselho existe por causa disso | Executor: alinhar o E9 ao teto real do bloco (calcular pelo `render_block`) ou relatar no lint a medida do teste. Não é conteúdo; não mexi |
| H-03 | P1 (executor) | `tests/test_spec360_sinais.py:105-114` × `services/fauna.py` (`render_block`) × `skallgard.yaml` (`mon_escuta_do_sinal`, lote 1) | `test_bloco_sem_nome` falha: o envelope `<SINAIS_NA_CENA>` do `render_block` vira o token `sinal` no singular, e "sinal" é token proibido do nome "Escuta do Sinal". Qualquer sinal dessa criatura falha, mesmo com o texto limpo (o E10 lê o texto cru e passa). Falha desde `7fdfa47e`; não foi pega no lote 1 porque eu não rodei esse arquivo | Executor: o teste deve checar `leaked_tokens` no texto do sinal (ou no bloco sem o envelope e a `SCENE_RULE`), não no bloco inteiro. Conteúdo não resolve: o token está no envelope. Não toquei no teste (é do executor; não é protegido) |

**Edição na Pernalta do Conselho (Aethelgard):** "que dão sempre a volta no mesmo quarteirão" virou "sempre em volta do mesmo quarteirão". O sentido e a distinção do G-02 continuam; aprovado.

Conferido e **mantido** (pontos do autor):

1. **`suprime`.** Dedos de Colheita→Virado do Avesso: colhedores defendem a mancha de fungo da qual o Virado comeu, e o Virado `foge_de` Dedos. Caçador Sem Calor→Fervente: Devorador contra o doente que os Saqueadores-de-Cristal levam para cavar, ou seja, grupo contra grupo. Os demais também são relações de ordem ou território: Caçador de Casca→intrusos; Surdo→Hospedeiro; Sentinela→Enxertadora/Surdo; Mascador de Néctar e Hospedeiro→Pressa da Seiva; Carregador de Liteira e Couro Pegado→Mãos de Cinzel; Costurado→Peito de Geodo.
2. **Presas no limite.** Todas aceitas, cada uma com base na ficha ou no resto:
   - Olho de Pétala→Preguiça: caçador de curiosidades contra bicho raro;
   - Toldo→Bugio: o Bugio vive sob a copa e foge do Toldo;
   - Urso-de-Espinha e Onça→Casuar;
   - Serpente-Raiz→Morcego: o resto do morcego com dois furos;
   - Tamanduá→Vespa Oleira: ninhos de barro abertos sob as plataformas;
   - Remendado→Laçado: caça "o que sangra", e o Laçado tem feridas que não fecham;
   - Predador Crescido→Preguiça de Pomar;
   - Lastreiro→Hiena: as duas rondam acampamentos à noite;
   - Verme→Tatu;
   - Cavador de Funil→Lambedor/Escaravelho: formiga-leão contra besouros.
3. **Estações extras.** Vespa Coveira no verão, Vespa Oleira na primavera e Varano no verão são coerentes. R4 está carregado: `enemy_verme_areia_jovem` com verão 1,5, `enemy_escorpiao_cristal` com verão 1,3 e `enemy_hospedeiro_fungico` com primavera 1,3 (`calendar.json:47-48`).
4. **Mariposa na Fronteira e horários alargados.** A prosa aguenta: a Mariposa fica só em Anoitecer e Noite, e nenhum horário contradiz o `comportamento` (os noturnos de verdade ficam na noite; os de clareira e de sol, no dia).
5. **"Saltão" repetido** (Saltão Desbotado na Floresta, Saltão de Galeria nas Montanhas): é nome de ficha, fora da fauna. As regiões não são vizinhas e os sinais não se parecem. Fica para a esteira do bestiário (U4), junto com "Pernalta" (lote 2) e "Lagarta", "Ermitão" e "Geodo", que também se repetem entre regiões.

`imediato` no hub: Floresta (Abafador e Sombra Deitada), Selva (Vinha e Vípera) e Zhur (Verme e Caçador Sem Calor) estão no teto de 2, todos de tocaia ou disfarce. Nota sem correção: o Toldo das Clareiras usa "espaço aberto" quatro vezes, porque o E10 barra "clareira"; soa um pouco duro, mas não confunde.

### Correções aplicadas

`e9dec3e6`: H-01; as 91 entradas com `revisao: aprovada` e `revisor_fauna: opus-370-revisor-lote3`; `fauna.json` regenerado (312 criaturas). `rumor_seeds.json` não mudou, porque o H-01 não toca em rumor.

### Pendências

- H-02 (executor): alinhar o limite de tamanho do E9 ao `test_bloco_ate_60_tokens`.
- **H-03 (executor, P1): `test_bloco_sem_nome` vermelho por causa do envelope do bloco; corrigir antes do pouso.**
- O M1 de NA continua em 0,7366, sem mudança neste lote (Zhur não tirou folga de NA).

### Comandos rodados

```text
scripts/fauna/lint.py --regiao {floresta_sussurros,selva_xylos,deserto_zhur,aethelgard} → 0 erro cada
scripts/fauna/build.py → fauna.json: 312 criaturas · build_rumor_seeds.py → ok · validate_content.py → 0 ERRO(S)
eval --regiao floresta_sussurros → gates ok (M1 0,787 / legado 0,7886; M8 0,2794; M5 −0,149)
eval --regiao selva_xylos → gates ok (M1 0,791 / 0,7977; M8 0,3071; M5 −0,173)
eval --regiao deserto_zhur → gates ok (M1 0,8185 / 0,8336; M8 0,2913; M5 −0,177)
eval --regiao nova_arcadia → gates ok (M1 0,7366 / 0,7433)
pytest -m "not slow" test_spec360_build test_spec312_seeds test_spec370_suprime test_spec370_caps test_spec360_sinais test_spec370_eval test_spec360_eval → só test_bloco_sem_nome falhou (H-03); test_bloco_ate_60_tokens passou
```

## Lote 4 — Costa Negra, Ophidia

> **Veredito:** `APPROVED` para o conteúdo, depois das correções abaixo, feitas pelo revisor. O M1 de Ophidia continua abaixo do gate por causa do motor, não do conteúdo; já está decidido pelo dono e vai para o executor.
> **Revisor:** Opus 5.5 (`spec-reviewer`, independente; `revisor_fauna: opus-370-revisor-lote4`; autor `opus-370-lote4`)
> **Data:** 2026-11-03 · **Commits revisados:** `188f150f`, `1cdd3482` · **Correção:** `656c0fdd`

### Escopo

Os arquivos são `data/bestiario/fauna/{costa_negra,ophidia}.yaml`, com 29 + 27 = 56 entradas. Usei o mesmo método dos lotes anteriores. Pela `region_adjacency()`, Costa Negra e Ophidia só são vizinhas de Brekmar, então a leitura entre regiões comparou as duas com o Brekmar.

Com este lote, as 12 regiões ficam sem nenhuma entrada `pendente`.

Ophidia está com M1 de 0,6229. A causa é o motor: a região tem 1 nó só, e a presença nova vira luta sem deixar sinal antes. O dono já decidiu que, em região de 1 nó, a presença nova sempre deixa sinal antes de poder virar luta, e o executor implementa isso depois desta revisão. Por isso julguei só o conteúdo.

### Achados

| ID | Sev. | Arquivo (entrada) | Problema | Correção |
|---|---|---|---|---|
| I-01 | P1 | `ophidia.yaml` (`mon_turu_de_casco`) × `brekmar.yaml` (`mon_broca_de_costado`) | Item 12, regiões vizinhas. O autor já tinha reescrito rastro, resto e marca do Turu, e eles ficaram distintos (barco oco por dentro × casco furado de dentro para fora). Mas a `aproximacao` ainda repetia a imagem da Broca, "cabeça de conchas girando" | Agora é "ponta dura e serrilhada, e atrás dela um corpo branco e mole do comprimento de um homem" |
| I-02 | P2 | `costa_negra.yaml` (`mon_andarilho_de_cracas`) × `brekmar.yaml` (`mon_craca_de_amarra`) | Item 12, regiões vizinhas: a `marca` do Andarilho ("cones novos onde não havia") repetia a da Craca de Brekmar ("crosta de cones grossa como de anos") | Agora são pedras de deitar riscadas por nadadeiras gastas, sem nenhum bicho deitado nelas |
| I-03 | P2 | `ophidia.yaml` (`mon_cobra_de_sangria`) | Ponto 4 do autor: "bichos compridos listrados" e "bichos do mar listrados" soavam forçados | Troquei por "serpentes listradas" e "serpentes do mar listradas"; serpente não é token do nome, e o E10 passa |
| I-04 | P2 | `ophidia.yaml` (`mon_caranguejo_cinza`) × `costa_negra.yaml` (`mon_caranguejo_mare`) | A `aproximacao` dos dois caranguejos legados tinha o mesmo molde ("da toca/crânio sai um bicho de casca… ergue garras"). As regiões não são vizinhas, mas a troca custa pouco | O de Ophidia sai de lado de trás da mureta, coberto de pó vulcânico, e as garras soltam vapor |

Conferido e **mantido** (pontos do autor):

1. **`suprime`.** Todos são relações de ordem ou de comércio, não de caça.
   - Caldeireiro→Saqueador: o resto mostra o ladrão de barril cozido.
   - Esfolado de Sal→Saqueador de Marfim: Osshari contra quem segue mapas Osshari roubados, como dizem o rumor e a descrição do Saqueador.
   - Vigia de Cor Errada→Trépano/Doente: a tripulação pirata contra os barcos do sindicato.
   - Trépano→Doente: comércio de amostras de sangue.
   - Acendedor→Contrabandista: o mais fraco, mas é rivalidade de carga entre piratas e a Mão Sombria, e o Contrabandista `foge_de` Acendedor.
2. **Presas.**
   - Gaivota→Carrapato de Osso tem base: ave que mergulha "sobre qualquer coisa que se mova entre as carcaças", contra um bicho pequeno que sai dos furos das ossadas.
   - As demais também têm apoio na ficha ou no resto: O Que Come→Filhote; Estrela→Caranguejo/Barata (ela abre o que tem casca); Tubarão→Andarilho/Bruxa (e Touro, cujo resto é o elefante-marinho mordido); Leviatã→Nadador Escaldado; Sereia→Ossada de Pomes; Moreia→Lagarto; Vela→Ossada/Cobra; Caranguejo de Cinza→Turu.
3. **`imediato` em Ophidia.** Desbotado da Névoa (tomado por tronco no raso) e Escorpena de Basalto (peixe-pedra) estão justificados. São 2 no único nó, o teto do E18.
4. **Outras perífrases do E10.** "água parada" (Saltador de Poça, Escorpena), "lascas brancas" (Carrapato), "garras de recife" (Sereia) e "marujo" (Vigia) soam naturais; só "bichos compridos" foi trocado (I-03).
5. **Turu × Broca.** No sinal, a reescrita do autor resolve, com o acabamento do I-01. Na ficha, porém, os dois continuam quase o mesmo bicho (verme de navio com cabeça de duas conchas serrilhadas), e isso é assunto da esteira do bestiário (U3/U4). O mesmo vale para Andarilho de Cracas × Craca de Amarra, que compartilham a larva que endurece, e para a "luz falsa" do Acendedor de Naufrágios × Pescador de Lanterna (Brekmar), que ficou distinta no sinal.

### Correções aplicadas

`656c0fdd`: I-01 a I-04. As 56 entradas estão com `revisao: aprovada` e `revisor_fauna: opus-370-revisor-lote4`. `fauna.json` (368 criaturas) e `rumor_seeds.json` foram regenerados.

### Pendências

- Executor (decisão do dono): em região de 1 nó, a presença nova deixa sinal antes de poder virar luta. Depois disso, rodar de novo o eval de Ophidia e o `--todas`; o `eval-global.md` deste commit ainda é o do autor do lote.
- H-03 (lote 3) continua: `test_bloco_sem_nome` falha só no `mon_escuta_do_sinal`, por causa do envelope do bloco.

### Comandos rodados

```text
scripts/fauna/lint.py --regiao {costa_negra,ophidia} → 0 erro cada
scripts/fauna/build.py → fauna.json: 368 criaturas · build_rumor_seeds.py → ok · validate_content.py → 0 ERRO(S)
eval --regiao costa_negra → gates ok (M1 0,8238 / legado 0,8515; M8 0,2863; M5 −0,199)
eval --regiao ophidia → M1 0,6229 (falha; motor, decisão do dono), M4 N/A, demais ok (M8 0,2121; M5 −0,190)
pytest -m "not slow" test_spec360_build test_spec312_seeds test_spec370_suprime test_spec370_caps test_spec360_sinais → só test_bloco_sem_nome (H-03, mon_escuta_do_sinal)
```
