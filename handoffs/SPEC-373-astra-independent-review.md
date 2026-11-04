# SPEC-373 — revisão astra (independent-review): Parte C (R20/R21)

> **Veredito:** `CHANGES_REQUIRED` (por causa do P1-1, na Carta `cor1_tro_mao_adiantada`). O nerf da `bomba_estopim` v2 está aprovado.
> **Revisor:** Opus 5.5, revisor independente de voz e orçamento (R21: "autor e revisor Opus") · **Data:** 2026-11-04 · **Commits revisados:** `d34ccbc3`, `378c2658` (HEAD da branch no momento: `fb739425`)

Nome do arquivo: o pedido era `SPEC-373-opus-review.md`, mas `opus` não é papel válido em
`scripts/check_handoff_names.py` (valem sol, astra, terra e luna). Já existe `SPEC-373-astra-review.md`, que trata das 28 Cartas do R15. Por isso usei `astra` com o tipo `independent-review`.

## Escopo

- Carta nova `cor1_tro_mao_adiantada` (`data/cards/posturas/corruptor_tronco.json:91-119`) e o lote em `data/cards/_ondas.yaml:357-366`. Revisei voz, orçamento, color pie, lint, a entrada no `full_deck` e a função anti-emboscada.
- Nerf da `arc1_imp_bomba_estopim` v2 (`arcanista_cinzento_improvisador.json:185-218`) e a evidência em `docs/spec373/bomba-0-19*.json` e `bomba-lote-depois.json`.
- Ficaram fora: as Partes A e B, as 28 Cartas de família (já revisadas em `SPEC-373-astra-review.md`) e o `fb739425`.
- Nenhum caminho de `evals/protected-paths.txt` foi tocado em `d34ccbc3` nem em `378c2658`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `data/cards/posturas/corruptor_tronco.json:94,106-109`; `services/conflict_turn.py:242-258,399-402`; `services/card_deck_round.py:117-127` | **A Carta não faz nada quando é jogada.** Ela é `ativa` com efeito `buff_iniciativa`, mas esse efeito não está em `ct._ATTACK_EFFECTS`, `ct._SUPPORT_EFFECTS` nem `fx.SELF_KINDS`. Ao jogá-la, `_resolve_card` só registra "Efeito de Carta sem resolução de Ação: 'buff_iniciativa'" e retorna. No modo `on`, `resolve_player_plays` já cobrou o Fôlego (`pay_cost(..., apply=True)`) antes disso. Resultado: o jogador paga 1 Fôlego, a Carta vai para o descarte e nada acontece. Conferi o catálogo: é **a única** Carta `ativa` de jogador cujo efeito o motor não resolve. O teste do executor só confere se a Carta está no baralho e passa no lint. Também por isso o bot "não a joga" e a taxa base do Corruptor caiu de 51,9 % para 48,3 %: há 2 cópias inúteis num baralho de 24. | Escolher uma das saídas e registrar o desvio na spec: **(a)** em `conflict_turn`, pôr `buff_iniciativa` em `_SUPPORT_EFFECTS` e mapeá-lo para `"initiative"` em `stat` (l. 712-718), mais um teste que jogue a Carta e afirme a condição `initiative` +2 no ator; ou **(b)** transformar a Carta em `reacao` com `gatilho`, como a `med_dose_choque`, porque o caminho de reação já resolve `buff_iniciativa` (`conflict_orchestrator.py:1212-1217`). A (b) contraria o R21, que pede `tipo: ativa`. Nos dois casos, regravar `posturas-c-0-19.json` e a emboscada 0–19. A confirmação 260–339 já foi gasta: a regravação vai como registro para o dono, sem reajuste (R3). |
| P1-2 | P1 | `corruptor_tronco.json:113` | O `momento` descreve uma jogada que não funciona. A emboscada é anulada porque a Carta está **no baralho** (`agents/combat.py:1926-1939`), não porque foi jogada. Numa emboscada o inimigo age primeiro, e a Carta não tem efeito ao ser jogada (P1-1). A frase engana o jogador. | Depois do P1-1, reescrever para o uso real. Exemplo: "Melhor jogada na abertura de uma luta longa, quando agir antes do inimigo nas próximas rodadas vale mais que um golpe agora." A proteção contra emboscada precisa aparecer na regra ou no rótulo da Carta, não no `momento`. |
| P2-1 | P2 | `corruptor_tronco.json:112` | Voz. O conceito da Postura ("a Corrupção que antecipa") está lá e a imagem "você já está de pé quando ele chega" é boa. Os problemas: (i) "antes **do** inimigo decidir vir" deveria ser "antes **de o** inimigo decidir" (contração antes de sujeito de infinitivo; a família já escreve "antes de o golpe cair"); (ii) "vem / vir / chega" repete o mesmo movimento; (iii) é a única Carta de tronco do Corruptor em 2ª pessoa, e as outras três têm o Abismo como agente sobre o alvo ("O toque do Abismo…", "O Abismo risca…"); "você" em Carta também está em aberto para o dono (D-367-2). Lint de voz limpo, sem aviso. | Sugestão no padrão do tronco: "O Abismo sopra o passo do inimigo antes de ele dá-lo: quando ele sai da névoa, quem o espera já está de pé." Depois de editar, rodar o `card_lint` de novo. |
| P2-2 | P2 | `corruptor_tronco.json:114` | `tier: 3` numa Carta `inicial`/`comum` de `level_req` 1. É a **única** de 135 Cartas de onda nível 1 `inicial`/`comum` (as outras 134 têm tier 1). O tier foi usado para vencer a ordenação do `full_deck` (`scripts/cards/sim.py:109-114`, ordem `-tier` e depois hash). Isso tem efeitos colaterais reais: o preço na loja sobe (`card_shop.py:139-140`, `preco_por_tier`) e o default de Fôlego vira 2 se o `custo_folego` explícito for removido (`cards.py:461-464`, `card_effects.py:1603`). | Aceito como follow-up. Registrar na spec que o tier 3 é instrumental e não reflete potência. O preço da loja precisa ser uma escolha consciente. A solução estrutural fica para a 369: o `full_deck` reservar vaga por função (anti-emboscada), sem depender de tier ou slug. |
| P2-3 | P2 | `_ondas.yaml:357-366`; spec §5 R21 | Slug escolhido entre 7 candidatos para ganhar o desempate por hash nas 12 células. Não é manipulação de avaliador: o `full_deck` é ferramenta da arena, e o teste `test_corruptor_tem_buff_iniciativa_no_full_deck` trava as 12 células. Mesmo assim, a garantia é frágil. Qualquer Carta nova de tier ≥ 3 do Corruptor pode tirá-la do baralho, e a L5 `alma` já tem só 1 cópia. Fora da arena isso não importa: o baralho real vem das `prepared_cards` do jogador (`card_piles.py:89-106`). | Aceitável, com registro (já está na §9). O teste segura a regressão. Mesmo destino do P2-2. |
| P2-4 | P2 | `_ondas.yaml:358-362` | `revisor_voz: dono` com `voz_status: aprovada`, mas a `nota_voz` diz que não houve leitura. Esta revisão é a leitura independente. Depois do P1-1, o P1-2 e o P2-1, atualizar o lote. | Depois das correções: `revisor_voz` = revisor Opus (formato aceito por `card_lint.revisor_valido`) e uma `nota_voz` que cite este handoff. |
| OK-1 | — | `corruptor_tronco.json:106-109` | Orçamento. `power_score` −1,1 na faixa `comum`/Fôlego 1 [−2,0; 9,0], sem `budget_error`. A Carta fica perto do piso, o que é coerente para um efeito cujo valor está em ficar no baralho. O color pie do Corruptor não proíbe `buff_iniciativa` (nem kind, nem alvo, nem teto), e o valor 2 é igual ao da `san_conta_memorizada` e abaixo de `arc_equacao_persistente` (3) e `med_dose_choque` (4), Cartas de nível 4. Sem erro de schema, raridade, escala ou redundância. `validate_content` 0 erro (registro do executor). | — |
| OK-2 | — | `docs/spec373/*-0-19*.json`, `confirmacao-posturas-260-339.json` | Anti-emboscada **pelo critério do R22**. `todas` 47,4 % nas 0–19 (≥ 46,5) e 48,7 % na 260–339 (≥ 45,0). A `alma` ficou em 45,7 % e 43,6 %. O R22 aplica o piso de 45 % só ao total; por subclasse vale apenas o teto de 75 %, então a `alma` não reprova, mas está abaixo do piso total na confirmação e precisa constar no relatório ao dono. Ressalva: a medição vale para a presença no baralho. Com o P1-1 corrigido, a Carta passa a ter jogada útil, e a taxa base do Corruptor deve subir de 48,3 % rumo aos 51,9 % de antes, sem passar deles. | Registrar a `alma` 43,6 % no §9. |
| OK-3 | — | `arcanista_cinzento_improvisador.json:194,207`, `versao` 2 | Nerf da `bomba_estopim` correto. São 2 passos dentro do R20, na ordem da D11: primeiro a área 3→2, que sozinha deixou +10,0 pp e uso de 71 %, ainda `dominante`; depois o Fôlego 1→2. `versao` subiu uma vez. Depois do nerf, no `lote`: uso 52,7 % (≤ 60), delta −5,0 pp, sem bandeira. Arcanista `todas` 52,3 % (≥ 46,5) e `improvisador` 63,7 % (≤ 75). Na confirmação, 51,1 % e 60,8 %. `power_score` 6,0 na faixa `incomum`/Fôlego 2 [−3; 16]. O delta −5,0 com 80 lutas por braço está dentro do ruído (±~6 pp), então não é prova de que a Carta virou armadilha. Vale acompanhar na 369. O aviso de voz "sem termo de Valoria" já existia e o texto não mudou. | Follow-up na 369: se o delta continuar ≤ −5 em outra amostra, a Carta virou armadilha que o bot ainda joga em 53 % das mãos. |

## Correções aplicadas

Nenhuma até aqui (revisão só de leitura).

## Pendências

- P1-1 e P1-2: executor da 373, antes do pouso. Se a correção for a (a), o teste novo vai em `tests/test_spec373_cartas.py` (jogar a Carta e afirmar a condição `initiative`).
- P2-1 e P2-4: mesmo executor e mesmo commit da correção. Após a edição, uma releitura curta de voz (Opus) basta.
- P2-2, P2-3 e o follow-up do OK-3: SPEC-369 (a escrever), vaga por função no `full_deck` e uma segunda amostra da `bomba_estopim`.
- `alma` 43,6 % na confirmação: registrar no §9 para o dono.

## Comandos rodados

```text
bash scripts/dev/pt.sh tests/test_spec373_cartas.py tests/test_card_lint.py tests/test_spec355_emboscada.py tests/test_spec341_balanco.py -n 2 -q → rc=0 (97 passed)
card_lint.lint_card + power_score/budget_band (script no scratchpad) → Mão Adiantada -1,1 em [-2; 9], sem aviso de voz; bomba 6,0 em [-3; 16]
varredura: Cartas ativas de jogador com efeito fora de _ATTACK_EFFECTS|_SUPPORT_EFFECTS → 1: ['cor1_tro_mao_adiantada']
sim.full_deck("Corruptor", L, sub), L∈{1,3,5} × 4 subclasses → presente nas 12 células (2 cópias; L5 alma 1)
contagem tier em Cartas de onda nível 1 inicial/comum → tier 1: 134, tier 3: 1 (esta)
```
