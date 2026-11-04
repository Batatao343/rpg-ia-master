# SPEC-377 — revisão sol (independent-review) — item 2 (custo de Fôlego)

> Nome do arquivo: o coordenador pediu `SPEC-377-item2-sol-review.md`, mas esse nome reprova
> `scripts/check_handoff_names.py` (gate `tests/test_handoff_names.py`), e `SPEC-377-sol-review.md`
> já guarda a revisão dos itens 1/3/4. Por isso o item 2 ficou neste arquivo.
>
> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (sem P0/P1; 2 P2 baratos de teste e 4 P3 de registro)
> **Revisor:** Opus / papel Sol · **Data:** 2026-11-04 · **Commit revisado:** `86cad8fa` (sobre `55051d2d`, base `main` `4512708f`)

## Escopo

Branch `spec-377`, `main...HEAD`: `55051d2d` (Etapa 0) e `86cad8fa` (implementação). Revisei
`services/cards.py`, `services/card_effects.py`, `tests/test_spec377_folego.py`,
`tests/test_card_acervo_reparo.py`, `docs/spec377/folego_divergencias.{py,json}`,
`docs/spec377/lote-v2-{antes,depois}.json` e a nota da spec (§ Execução do item 2), contra R8–R12,
R24, D2=(a), o plano §4 item 2 e o critério de aceite do item 2. Os itens 1/3/4 ficaram fora:
já foram revisados em `handoffs/SPEC-377-sol-review.md`.

## Respostas aos pontos do coordenador

**1. Desvio 1 (implementação em `cards`, alias em `card_effects`): aceito.**
- A R11 pede "uma implementação + um alias de uma linha" e não fixa o lado. O §3, que dizia o
  contrário, é design, e o desvio está registrado na spec (§ Execução).
- O motivo é válido: `card_effects.py` está acima de 1.000 linhas e não pode crescer (gate
  `test_size_budget`). Ele encolheu 9 linhas. As constantes (`_DAMAGE_KINDS`,
  `DANO_BASE_FOLEGO_2`, `FOLEGO_MAX_CARTA`) já moravam em `cards.py`.
- Não cria ciclo: os dois imports são locais, dentro da função.
- O monkeypatch continua valendo nos dois nomes. Quem chama `fx.custo_folego` (lint, orçamento,
  `sim.py`, `gerar_mecanica.py`) resolve pelo atributo do módulo. O alias chama
  `cards.custo_folego` também pelo atributo, então um patch em `cards` chega ao lint.
- Ressalva P3-1: o §3 da spec ainda descreve o lado contrário.

**2. Desvio 2 (aviso `redundancia` e o teste alterado): não viola a integridade; recomendo aceitar
o aviso brando, mas apertar o teste (P2-1).**
- **Não é W5.** `tests/test_card_acervo_reparo.py` não está em `evals/protected-paths.txt`.
- **Não é W3 no sentido estrito.** O item 2 não é refatoração pura: a própria spec diz que "W2/W3
  não bastam". A W3 manda parar, registrar e reportar quando surge asserção nova. O executor
  registrou na spec e o coordenador reportou agora. O fato [R] do plano §4.2 ("o lint dessas 2
  Cartas também não [muda]") só valia para o orçamento (`budget_error`), não para a
  `signature`. Isso precisa ficar registrado (P3-2).
- **O aviso é verdadeiro.** No jogo, `cor_toque`/`toque_corrosivo` sempre custaram 1 Fôlego. A
  semelhança mecânica com `cor1_bio_mofo_quente` (dot, 0 Entropia, 1 Fôlego) já existia, e o
  lint só não a via. Medi a onda 1 inteira: o aviso aparece **só** em `cor1_bio_mofo_quente`,
  com 2 entradas, e é `warn`, não erro (momento 0,12 < 0,6).
- **Há precedente de aceitar esse aviso.** A onda 1 já convive com vários `redundancia` brandos
  contra o legado: `arc1_cal_estilhaco`, `arc1_imp_bomba_estopim`, `arc1_des_brasa`,
  `san1_sil_pe_de_pluma`, `san1_exp_aplauso_de_ferro` e outros. Os testes desses lotes não
  exigem zero aviso.
- **As alternativas são piores:**
  - (b) tirar o custo da `signature` muda o critério de redundância nas ~1.500 Cartas. É regra
    de lint nova, fora do escopo, e pediria spec própria;
  - (c) mudar a Carta (frequência, números ou `momento`) é conteúdo/balanço. A R24 proíbe isso
    aqui; o lugar seria a SPEC-369 ou uma spec de conteúdo.
- **Tratamento certo:** manter o aviso e trocar o filtro por uma asserção **exata**. Ver P2-1.

**3. W5/eval: nada protegido muda.** Detalhe na seção "Resposta ao item 3" abaixo.

**4. Paridade, R24 e testes:** todos verdes. Detalhe em "Comandos rodados".
- Paridade do jogo: 0 diferenças entre o `cards.custo_folego` da `main` e o novo, em 24.128
  variantes. Entram o JSON bruto, o catálogo, `materialize`, e `effective_card` com e sem
  Ruptura e com evolução A/B.
- Paridade do lint: só `cor_toque`/`toque_corrosivo` mudam (0→1), em todos os modos, como a R9
  previa.
- R24: sem diff em `scripts/cards/sim.py`, `docs/spec335/arena_posturas.py`, `data/cards/**`
  (inclui `_orcamento.json`) e `evals/`.

## Resposta ao item 3 (W5 / `/eval-publish`)

**Nada protegido muda, e não há o que publicar por `/eval-publish`.**

- `evals/protected-paths.txt` não lista `scripts/cards/sim.py`, nem `docs/spec358/**`, nem
  fixture de Cartas. A única fixture de Cartas protegida é `tests/fixtures/spec330_legacy_golden.json`,
  que não está no diff.
- `scripts/ci_eval_scope.classify` (a mesma regra de CI que `eval_publish.py` usa) sobre os
  9 arquivos do diff devolve `protected_files: []` e `protected: False`. O `eval-governance`
  não seria acionado, e o `eval_publish.py` não teria run pendente nem link de aprovação a
  mostrar.
- O protocolo `lote-v2` não tem baseline versionada:
  - `tests/fixtures/spec358_sim_v1_golden.json` é do v1 e não contém `cor_toque` nem
    `toque_corrosivo`;
  - nenhum dataset de `evals/datasets/regression` cita Cartas, `custo_folego` ou `lote-v2`.
- Na prática, a W5 vira **registro da evidência e conferência por um agente que não é o
  executor**. Esta revisão fez essa conferência: reproduzi os dois arquivos.
  - `lote-v2-depois.json` sai igual ao rodar `folego_divergencias.py --lote-v2` no HEAD.
  - `lote-v2-antes.json` sai igual com `fx.custo_folego` trocado pela regra antiga do lint, em
    memória. A única diferença são as linhas de log no stderr.
  - Resultado: `cor_toque` não muda (0,925, delta +2,5); `toque_corrosivo` vai de vitoria_ref
    0,875 para 0,887 e de delta +1,2 para 0,0. As duas Cartas ficam sem bandeira, e a faixa da
    referência vai de (0,7) para (−2,9).
- **O que o coordenador faz:**
  - não rodar `/eval-publish` para este item;
  - reescrever o critério de aceite do item 2 (spec:388–389) e a linha "Pendente (W5)"
    (spec:505) para dizer que o `lote-v2` antes/depois foi registrado em
    `docs/spec377/lote-v2-{antes,depois}.json` e reproduzido pela revisão independente
    (este handoff), sem caminho protegido;
  - tirar "item 2 pendente do dono: publicar `lote-v2`" do cabeçalho de status e do
    `docs/spec377/README.md`, onde também há "Item 2 (Fôlego) pendente".

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `tests/test_card_acervo_reparo.py:220-224,234` | O filtro `_redundante_dot_legado` casa por substring da mensagem (`"de {cid} "`) e só descarta avisos. Se `cor1_bio_mofo_quente` deixar de colidir, ou se outra Carta do lote 4 passar a colidir com essas duas, o teste não percebe. O relaxamento é aberto, quando devia ser uma asserção exata. | Trocar por uma asserção positiva no lote 4. Os avisos `redundancia` devem ser exatamente `{("cor1_bio_mofo_quente", "cor_toque"), ("cor1_bio_mofo_quente", "toque_corrosivo")}`, e qualquer outro `warn` continua proibido. Assim, se a colisão crescer ou sumir, o teste falha e força a revisão. Registrar como mudança de teste declarada na tabela da spec (padrão do P1-1 da linha 492). |
| P2-2 | P2 | `tests/test_card_acervo_reparo.py:299,443` | O mesmo filtro foi aplicado aos lotes 5 (Médico de Campo) e 6 (neutras). `check_redundancy` só compara Cartas da mesma `classe`, então Cartas Corruptor nunca entram ali. É código morto que afrouxa dois testes sem motivo, e medi que esses lotes não emitem o aviso. | Restaurar nos lotes 5 e 6 a asserção original (`assert not [i for i in issues if i.level == "warn"]`). |
| P2-3 | P2 | `tests/test_spec377_folego.py:19-28` | `test_paridade_catalogo_com_jogo` só compara com o oráculo nos 2 ids divergentes. Nas outras ~1.506 Cartas, só verifica a faixa 0..3. Não prova que "o jogo não muda". A prova real foi minha sonda (0 diferenças em 24.128 variantes), que não fica no repositório. | Follow-up barato: congelar no teste a regra antiga do jogo (cópia literal de `main:services/cards.py:447-468`) como oráculo e comparar com `cards.custo_folego` no catálogo inteiro e em `effective_card` com Ruptura e evolução A/B. A alternativa é um fixture `{id: custo}` gerado pela Etapa 0. A SPEC-380 R2.5 cobre os casos de eval, não esta paridade. |
| P3-1 | P3 | `specs/SPEC-377-…md:287-289` (§3, item 2) | O §3 ainda diz que a implementação mora em `card_effects` e que `cards.custo_folego` é o alias. O desvio só aparece no § Execução. | Ajustar o §3, ou marcar ali "desvio, ver § Execução do item 2". |
| P3-2 | P3 | `specs/SPEC-377-…md:337` | O fato [R] "o lint dessas 2 Cartas também não [muda]" só vale para o orçamento. A `signature` muda e gera o aviso `redundancia`. | Anotar a correção ao lado do [R], indo além do § Execução. |
| P3-3 | P3 | `docs/spec377/folego_divergencias.py:92`; `docs/spec377/` | A chave `ref_custo_folego` guarda o resumo da referência (`id`, `efeito`, `power_score`, `faixa`), não o custo, que não é gravado. Também falta o `.md` que a R10 pedia, e o JSON não segue o formato do §3 (sem `motivo`, sem `lote_v2` por entrada). | Renomear a chave para `referencia` numa próxima rodada da Etapa 0 (não é preciso regerar agora). O README de `docs/spec377/` pode fazer o papel do `.md`, com uma linha sobre o modo (iii) e o motivo (b). Aceitar o formato atual como desvio menor. |
| P3-4 | P3 | `tests/test_spec377_folego.py:15` | `test_uma_implementacao` depende do texto da docstring (`startswith("Alias")`). | Opcional: monkeypatch de `cards.custo_folego` e checar que `fx.custo_folego` segue o patch. Isso prova o alias pelo comportamento. |

Sem achado nas verificações pedidas no checklist:
- guard de structured output e valor de LLM: não se aplicam, não há LLM no caminho;
- writer persistente: nenhum;
- segredo em log: nenhum;
- `evals/` protegido: não foi tocado;
- função nova > 60 linhas: nenhuma;
- `dup_helpers --diff`: nenhuma função nova com nome repetido;
- `size_budget`: verde, e `card_effects.py` encolheu;
- `except` largo novo: nenhum (o `except (TypeError, ValueError)` é estreito e anterior ao diff);
- fora do escopo: nada; as mudanças de teste são as dos P2-1/P2-2.

## Correções aplicadas

Nenhuma ainda. O revisor não edita produto nem testes.

## Pendências

- P2-1/P2-2: executor, nesta branch, antes do pouso. É barato, e o P2-2 é só reverter duas linhas.
- P2-3: executor, nesta branch ou na SPEC-380.
- P3-1..P3-4 e a reescrita do critério W5 (item 3 acima): coordenador ou executor, no pouso.
- Conteúdo: decidir se `cor_toque`/`toque_corrosivo` devem se afastar mecanicamente de Mofo
  Quente (hoje diferem só na frequência, `livre` × `cena`, que a `signature` não vê). Destino:
  SPEC-369 (balanço) ou uma spec de conteúdo. Fora da 377 (R24).

## Comandos rodados

```text
git diff main...HEAD --stat → 9 arquivos; nenhum em sim.py/arena_posturas.py/data/cards/evals
git diff --stat main...HEAD -- scripts/cards/sim.py docs/spec335/arena_posturas.py data/cards evals → vazio (R24 ok)
bash scripts/dev/pt.sh tests/test_card_piles.py tests/test_card_effects_grammar.py tests/test_card_sim_v2.py tests/test_card_acervo_reparo.py tests/test_card_lint.py tests/test_spec377_folego.py tests/test_card_sim.py tests/test_spec355_conteudo.py tests/test_size_budget.py -n 2 → rc=0 (todos verdes, 1 skip)
scratchpad/cmp377.py (custo do jogo na main × novo; lint na main × novo; bruto/catálogo/materialize/effective_card ruptura×evo A/B) → 24.128 variantes; jogo 0 diferenças; lint só cor_toque/toque_corrosivo 0→1
docs/spec377/folego_divergencias.py --lote-v2 <tmp> (HEAD) → igual a lote-v2-depois.json
scratchpad/antes377.py (fx.custo_folego = regra antiga do lint, em memória) → igual a lote-v2-antes.json
lint da onda 1 inteira (warns) → redundancia nova só em cor1_bio_mofo_quente (×cor_toque, ×toque_corrosivo); outros redundancia brandos já existiam
scripts/ci_eval_scope.classify(diff) → protected_files=[], protected=False
scripts/dev/dup_helpers.py --diff main...HEAD → nenhuma função nova com nome já usado
```
