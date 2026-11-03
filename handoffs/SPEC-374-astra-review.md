# SPEC-374 — revisão astra (review): texto do prompt da criatura gerada

> Nome do arquivo: `handoffs/SPEC-374-astra-review.md`. A spec cita `SPEC-374-prompt-review.md`, mas
> esse nome reprova no `scripts/check_handoff_names.py`; o coordenador atualiza a referência no pouso.
> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
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
