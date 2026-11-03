# SPEC-374 — revisão astra (review): texto do prompt da criatura gerada

> Nome do arquivo: `handoffs/SPEC-374-astra-review.md`. A spec cita `SPEC-374-prompt-review.md`, mas
> esse nome reprova no `scripts/check_handoff_names.py`; o coordenador atualiza a referência no pouso.
> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (rodada 4, `1ce2fd12`; o mesmo das rodadas 1 a 3)
> **Revisor:** Opus (revisão criativa do texto do prompt; não escreveu o texto) · **Data:** 2026-11-03 · **Commit revisado:** `534a642f`

## Escopo

Texto que o executor Sonnet escreveu ou mudou em `services/creature_gen.py`: `_EIXOS_LINHA` (`:929`),
`_EIXOS_LIVRE` (`:935`), a linha nova "Sem inglês de jogo e sem a palavra 'dragão'…" (`:956`), a regra
de `padrao` com `<padroes_livres>`, o texto de `linha_nucleos` (`:981`), o bloco `<padroes_livres>`
(`padroes_livres`, `:876`) e o cabeçalho de `<eixos_livres>` em `montar_prompt`/`montar_prompt_correcao`.
Lido também o prompt montado de verdade (offline) para `costa_negra` (13,6 mil caracteres com lore
fictícia) e as 22 fichas `nova` das duas rodadas medidas (`docs/spec374/eval-medido-{1,2}.json`).
Critérios: voz de Valoria, direção do dono (criaturas **físicas**, corrupção no corpo, sem clichê) e
instrução que empurre para ficha genérica. `PAPEL`, famílias e os exemplos projetados vêm da 361
(autoria Opus) e não foram reabertos.

**Sobre o veredito.** As rodadas medidas passaram (17/22) com este texto, e o R2 proíbe reajuste depois.
Nenhum achado abaixo é P0/P1: o texto não vaza número, não abre brecha para o LLM mexer em mecânica e
as fichas medidas são, em geral, boas. Por isso as propostas ficam como **follow-up**: qualquer mudança
de texto pede novas rodadas medidas (D6) numa spec nova, ou no smoke §6, por decisão do coordenador.

## Leitura das fichas medidas (5 escolhidas + o padrão das 22)

- **Boas, no tom pedido:** *Bebedor de Odre Podre* (saco de pele com boca em anel, vive dobrado no odre),
  *Rói Quilha de Fundo* (peixe de fundo com nadadeiras que viraram cotos que agarram madeira; gancho das
  tábuas roídas "sempre do lado sem lanterna"), *Veia que Anda* (mineiro com as mãos fundidas na
  picareta; gancho "a veia desceu atrás deles"), *Sino de Pele Fundida* (Aethelgard). São físicas, a
  corrupção está no corpo, o gancho prende ao lugar. Telégrafos com `{nome}` e gesto visível.
- **Fracas, e com causa no texto do prompt:**
  - *Cera de Sebo Faminta* (selva_xylos, rodada 1): o nome é o rótulo do eixo `cera_sebo`. *Colo de Turfa
    Funda*: "Massa **radial** de turfa", o rótulo `radial` copiado para a prosa. `cera_sebo` vira
    "cera de sebo" em mais três fichas (enxame do Zhur, Cobrado de Veios Frios, a ficha do Groq).
    A causa provável é o parêntese de `_EIXOS_LINHA`: "(material, locomoção e percepção dela aparecem em
    anatomia_texto)". O LLM lê isso como "escreva o rótulo no texto".
  - *cicatriz de Eco* (rodada 2, a do fallback Groq): "colmeia mental", "luz da lua", "move‑se",
    "sinalizando que a onda de mordidas está prestes a surgir". É a ficha genérica que o dono não quer.
    Passou no lint. Não é culpa do texto (outro modelo), mas mostra que o lint não pega prosa de manual.
  - *Guardião de Relevo* (pradaria): nome abstrato, não diz o que ela faz nem do que é feita.
- **R20 persistente em `costa_negra`** (1ª tentativa nas duas rodadas). O termo não ficou gravado (ver
  P2-6 do parecer Sol). Suspeita: a lista de proibidos vai **sem acento** (`critico`, `genio`,
  `observador`, `elemental`, `mumia`) e contém palavras comuns do português ("momento crítico",
  "um observador"). O LLM não liga "critico" a "crítico".

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção (texto proposto) |
|---|---|---|---|---|
| P2-1 | P2 | `services/creature_gen.py:929-934` (`_EIXOS_LINHA`) | O parêntese "material, locomoção e percepção dela aparecem em anatomia_texto" faz o LLM copiar o rótulo do enum para a prosa e para o nome ("Cera de Sebo Faminta", "Massa radial"). Isso é taxonomia, não corpo, e puxa a ficha para o genérico. | `"Eixos: escolha UMA linha de <eixos_livres> e escreva só o número dela em linha_eixos; o motor grava os seis eixos. O corpo tem de caber na linha, mas em matéria que se toca e não em rótulo: o material vira o que a mão sente (cera_sebo é banha que escorre e endurece; escoria_fuligem é casca de forno que esfarela), a locomoção vira o jeito de andar e a percepção vira o órgão que sente. Nunca copie as palavras da linha no nome nem no texto."` |
| P2-2 | P2 | `services/creature_gen.py:956` | "Sem inglês de jogo" é vago e repete a lista que vem logo abaixo. A lista vai sem acento e com palavras comuns do português que o LLM usa sem perceber. "dragão" aparece três vezes no prompt (família, Nome, esta linha). | Trocar a linha por: `"A lista de palavras que reprovam vale com ou sem acento e em qualquer campo, gancho e arte incluídos: «crítico», «gênio», «observador», «elemental» e «múmia» também reprovam. Também não escreva «dragão»: o sangue antigo se descreve pelo que fez no corpo."` Tirar "dragão" do exemplo da regra do Nome (já coberto aqui). |
| P2-3 | P2 | `services/creature_gen.py:981-997` (`linha_nucleos`) | A lista sai normalizada (`tubarao`, `hospede`, sem acento) e inclui ruído: `que` (de "O Que Come nas Praias") e `filhote` (já proibido no nome pela regra). O LLM compara "Tubarão" com "tubarao" pior do que com a palavra como foi escrita. | Mostrar a 1ª palavra **como está no nome**, sem artigo, e pular as que já estão na regra do Nome ou têm menos de 4 letras: `"Já começam nome na região (escolha outra primeira palavra): Acendedor, Andarilho, Balsa, …, Tubarão, Ventre."` O gate continua usando `bl.nucleo_nome`. |
| P2-4 | P2 | `services/creature_gen.py:876-907` (`padroes_livres`) e regra `padrao:` | "prefira um de <padroes_livres>" empurra uma sequência escolhida por hash, sem relação com o comportamento que o LLM escreveu, e as duas listas saem iguais quando nada colide (~170 caracteres repetidos que saem da lore). | Regra: `"padrao: de duas a quatro intenções na ordem em que ela age, coerentes com comportamento e telegrafo; se uma de <padroes_livres> servir, use-a."` Bloco: quando as listas forem iguais, `"qualquer categoria: …"`. |
| P2-5 | P2 | `services/creature_gen.py:935-939` (`_EIXOS_LIVRE`) | Região saturada: o texto está correto e coerente com U2/U3 (`MAX_EIXOS_IGUAIS`). Só falta a mesma proibição de copiar rótulo do P2-1. | Acrescentar no fim: `"Descreva o corpo pela matéria e pelo gesto, sem repetir os nomes dos eixos no texto."` |
| P2-6 | P2 | lint (fora do texto) | A ficha do Groq mostra que o gate não pega prosa de manual ("colmeia mental", "sinalizando que", "prestes a"). Não é achado de texto. | Follow-up para o smoke §6.5 ou para a revisão Opus do pool (361 R21+): olhar as fichas `provider != deepseek` com mais cuidado. |

Nada a corrigir em: cabeçalho de `<eixos_livres>` ("devolva o número em linha_eixos"), instrução da
correção curta ("troque linha_eixos por outra linha… e ajuste o texto do corpo à nova linha"), voz
das regras (seca, pt-BR, sem adjetivo vazio) e ausência de qualquer pedido de número. Nada no texto
novo vaza segredo ou instrução do jogador (o `PLAYER_INPUT_RULE` e o `wrap_player_input` seguem no lugar).

## Correções aplicadas

Nenhuma (o revisor não edita produto; aplicar o texto acima pede novas rodadas medidas).

## Pendências

- P2-1 a P2-5: follow-up de texto numa spec nova (ou junto do smoke §6), com 2 rodadas medidas pelo
  protocolo D6 depois da mudança. Prioridade: P2-1 e P2-2 (atacam o genérico e o R20 que sobrou).
- P2-6: coordenador, no smoke §6.5.

## Comandos rodados

```text
py.sh (offline, RPG_FORCE_MOCK=1) montar_prompt(costa_negra, eixos_livres, padroes_livres) → 13 603 caracteres; blocos lidos inteiros
py.sh leitura de docs/spec374/eval-medido-{1,2}.json → 22 fichas nova (nome, anatomia, telegrafo, gancho, códigos)
py.sh léxico do gate (bl.lexico + card_lint.lexico) → 57 termos, todos sem acento
```

## Rodada 2 (2026-11-03, texto `80ed7ee2`, medido em `7828e73b`)

**Veredito da rodada 2:** `APPROVED_WITH_FOLLOWUPS`. Os itens P2-1 a P2-5 foram aplicados com o texto
proposto, com fidelidade. A regra de `padrao` e a lista única de `padroes_livres` também entraram. O
protocolo passou (16/22), e nada no texto vaza número, segredo ou instrução.

Leitura das 22 fichas `nova` v2 (todas DeepSeek):

- **Rótulo copiado caiu.** "cera de sebo" literal aparece em 2 das 22 fichas, contra cerca de 5 na v1, e
  nenhum outro rótulo de eixo (`radial`, `escala_paredes`, `medo_emocao`, etc.) aparece no texto.
  **R20 sumiu** das falhas de 1ª tentativa, inclusive em `costa_negra`. As falhas que sobraram são
  U13/U5 (padrão e silhueta), que não são de texto. Fichas boas e físicas: *Chupador de Odres*,
  *Veia que Mastiga* ("a Praga de Ferro o reescreveu em veio"), *Maré Que Sobe*,
  *Bexiga de Pânico* ("cheio de ar que não é ar"), *Coro Seco*.
- **Achado novo, e a causa é a minha proposta (R2-P2-1).** Os dois exemplos entre parênteses de
  `_EIXOS_LINHA` viraram fórmula. "banha … que escorre e endurece" aparece quase igual em 4 fichas
  (*Escumalha do Cadinho*, *Colo de Turfa Funda* v2, *Guardiã de Cera Fundida*, *Enxame de Cera Mente*),
  e "pó de forno" vem da imagem dada para `escoria_fuligem` (*Bebedor de Odres* v2). O rótulo saiu, mas
  a imagem do prompt entrou no lugar. É o clichê que o dono não quer, agora vindo do próprio prompt. E
  o nome ainda sai do material em *Guardiã de Cera Fundida* e *Enxame de Cera Mente*.

| ID | Sev. | Arquivo:linha | Problema | Correção (texto proposto) |
|---|---|---|---|---|
| R2-P2-1 | P2 | `services/creature_gen.py` `_EIXOS_LINHA` | Os exemplos concretos dentro da regra são copiados para a prosa ("banha que escorre e endurece", "pó de forno"). Fichas diferentes passam a soar iguais. | Tirar os dois exemplos e pedir imagem própria: `"Eixos: escolha UMA linha de <eixos_livres> e escreva só o número dela em linha_eixos; o motor grava os seis eixos. O corpo tem de caber na linha, mas em matéria que se toca e não em rótulo: o material vira o que a mão sentiria, a locomoção vira o jeito de andar e a percepção vira o órgão que sente, com imagem tirada do lugar e do pedido. Nunca copie as palavras da linha no nome nem no texto, e o nome não é o material."` |
| R2-P2-2 | P2 | regra `Nome:` | Dois nomes ainda são "<coisa> de <material>". | Já coberto pela última frase do R2-P2-1 ("o nome não é o material"). |

Como na rodada 1: aplicar este texto pede novas rodadas medidas (D6). Não bloqueia o pouso. Fica como
follow-up numa spec de texto ou junto do smoke §6, a critério do coordenador.

Comandos da rodada 2:

```text
git diff 1026cfcd..HEAD -- services/creature_gen.py → texto aplicado conforme o parecer
py.sh leitura de eval-medido-v2-{1,2}.json → 22 fichas nova; busca de rótulos de eixo nos textos → só "cera de sebo" ×2
```

## Rodada 3 (2026-11-03, v3 revertida `b30a5bdc`; frase nova de `_EIXOS_LINHA` em `a8d19167`)

**Veredito da rodada 3:** `APPROVED_WITH_FOLLOWUPS`.

- **A minha proposta R2-P2-1 foi medida e perdeu.** O texto sem exemplos (`cf710d21`) deu 13/22 na v3, e o executor reverteu conforme o R2. Com rodadas de n = 11, a diferença para a v2 (16/22) está dentro da variância já vista (o ajuste oscilou de 7 a 10 de 11), então a conclusão não é firme. Mesmo assim, retiro a proposta como está: os exemplos ficam, e a repetição "banha que escorre e endurece" passa a ser custo aceito, a vigiar na revisão Opus do pool.
- **Frase nova:** "o material da linha é a matéria que domina o corpo (corpo de sal exige uma linha com sal_mineral)".
  - O conteúdo está certo. Diz ao LLM a mesma coisa que a U14 cobra, que é a ligação certa entre prompt e gate.
  - Citar `sal_mineral` como valor de linha não fere o "nunca copie as palavras da linha": é instrução de escolha, não de prosa.
  - Mas a costura deixou a frase torta. Ficou "O corpo tem de caber na linha: o material da linha é … (…), mas em matéria que se toca e não em rótulo: o material vira …", com três dois-pontos, e o "mas em matéria" não se liga a nada. A locomoção `nada`, a outra metade da U14, não é dita.
  - Não muda número nem abre brecha. É P2.

| ID | Sev. | Arquivo:linha | Problema | Correção (texto proposto) |
|---|---|---|---|---|
| R3-P2-1 | P2 | `services/creature_gen.py:933-941` (`_EIXOS_LINHA`) | Sintaxe quebrada depois da inserção, e a metade da U14 sobre locomoção não aparece. | `"Eixos: escolha UMA linha de <eixos_livres> e escreva só o número dela em linha_eixos; o motor grava os seis eixos. Escolha a linha pelo corpo que você vai descrever: o material da linha é a matéria que domina o corpo (um corpo de sal pede uma linha com sal_mineral), e locomoção nada quer dizer que ela vive e se move na água. No texto, essa matéria vira o que a mão sente (cera_sebo é banha que escorre e endurece; escoria_fuligem é casca de forno que esfarela), a locomoção vira o jeito de andar e a percepção vira o órgão que sente. Nunca copie as palavras da linha no nome nem no texto."` Como antes, aplicar pede novas rodadas medidas, então fica como follow-up. |
| R3-P2-2 | P2 | `scripts/bestiario/pool_revisao.py` (Composição) | Visto pelo lado do texto da arte: a Composição com "Lábios (Costa Negra), luz baixa" põe o ilustrador num lugar sem sentido. Detalhe e correção no R3-P1-1 do parecer Sol. | Ver o parecer Sol. |

Comandos da rodada 3:

```text
git diff 7cc69618..HEAD -- services/creature_gen.py → só a frase de material e "U2/U3/U14" na correção
py.sh (offline) lugar_do_texto sobre fichas_aprovadas() → 277/281 com "lugar"; amostra com azul/lábios/que/S
```

## Rodada 4 (2026-11-03, `a3ee74f8`)

**Veredito da rodada 4:** `APPROVED_WITH_FOLLOWUPS`. O texto do R3-P2-1 entrou igual ao proposto: a
sintaxe está corrigida e a metade da U14 sobre nadar foi incluída. Também não vaza número nem segredo.

A v5 (informativa) deu 12/22, contra 13/22 da v4. Pela variância já vista com n = 11, é empate, e o
`lint_final` (1,0) e o `fallback` (0) melhoraram nas duas rodadas. Manter a frase é razoável. A
Composição da arte agora só usa lugar de verdade (ver o parecer Sol, rodada 4), o que fecha o R3-P2-2
deste parecer. Os follow-ups de texto que restam são os já registrados: a fórmula "banha que escorre" e
o nome tirado do material, a vigiar na revisão Opus do pool.
