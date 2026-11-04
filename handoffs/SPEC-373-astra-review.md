# SPEC-373 — revisão astra (review): Cartas comuns de família (R14/R15)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (as 28 Cartas, R15). **O pouso continua bloqueado
> pelo P1-1** (portão R17 vermelho), que se corrige sem mexer nas Cartas.
> **Revisor:** Opus 5.5, revisor independente de conteúdo (R15) · **Data:** 2026-11-04 · **Commit revisado:** `75b73e2b`

Nome do arquivo: a spec e o pedido falam em `handoffs/SPEC-373-cartas-review.md`, mas esse nome
reprova `tests/test_handoff_names.py`, porque `cartas` não é papel válido. Usei `astra`
(revisão conceitual de conteúdo). O executor precisa atualizar a referência na spec (§2 R15, §3, §4 Etapa 8.1).

## Escopo

`git diff 9e98b241..HEAD`: `5e58c5f8` (28 Cartas `origem: cartas-373` em 8 arquivos de
`data/cards/inimigos/`, `uso-familia.json` e 3 testes) e `75b73e2b` (arena das 12 regiões).
Não revisei o motor R9/R10, os chefes (Parte A), a Parte C nem a confirmação 40–119. Esses itens ficam
com a revisão Sol. Nenhum caminho de `evals/protected-paths.txt` foi tocado (conferi `arena.py`,
`test_spec373_artefatos.py` e `docs/spec373/base/eval`).

## Veredito por Carta (R15)

Todas as 28 passam nos checks abaixo:
- vocabulário, orçamento `comum` e `budget_error is None`;
- voz e nome único no catálogo;
- redundância intra-família (sem erro e sem aviso);
- `check_raridade`, `check_color_pie`, `check_escala_principal`, `check_revelar_publico`, `check_reacao_folego` e `check_marca_dano`, todos limpos (rodados à parte);
- `power_score` ≤ o máximo da família;
- sem dano arcano/abissal/elemental e sem reforço.

A coluna "ps" traz o `power_score`. A coluna "> comum" diz se a Carta passa da comum mais forte que já existia na família (ver P2-1).

| Família | Carta | ps | > comum | Veredito |
|---|---|---|---|---|
| covarde | estocada_e_fuga | 2.0 | | APPROVED |
| covarde | chute_na_canela | 2.5 | | APPROVED |
| covarde | chutar_quem_caiu | 2.9 | sim | APPROVED_WITH_FOLLOWUPS (P2-3) |
| covarde | rato_encurralado | 2.9 | sim | APPROVED |
| covarde | fingir_de_morto | 2.6 | sim | APPROVED |
| covarde | moeda_atirada | 1.5 | | APPROVED |
| tatico | golpe_combinado | 3.9 | sim | APPROVED (sinergia com ler_a_guarda) |
| tatico | recuar_em_ordem | 2.4 | | APPROVED |
| tatico | desarme_metodico | 3.5 | sim | APPROVED |
| tatico | ler_a_guarda | 2.0 | | APPROVED |
| tatico | contra_a_parede | 4.5 | sim | APPROVED |
| tatico | respirar_e_mirar | -0.1 | | APPROVED (enchimento fraco) |
| tatico | ferro_com_ferro | 3.9 | sim | APPROVED_WITH_FOLLOWUPS (P2-2) |
| predador | morder_o_marcado | 4.9 | sim | APPROVED |
| predador | derrubar_a_presa | 4.5 | sim | APPROVED |
| predador | voltar_ao_mato | 2.5 | | APPROVED |
| predador | mordida_que_sangra | 3.3 | | APPROVED |
| bruto | agarrar_e_atirar | 5.5 | sim | APPROVED |
| bruto | raiva_de_ferido | 5.6 | sim | APPROVED_WITH_FOLLOWUPS (P2-1, `turno`) |
| bruto | cabecada | 5.5 | sim | APPROVED |
| bruto | couro_e_furia | 3.1 | | APPROVED |
| guardiao | golpe_de_broquel | 3.5 | | APPROVED |
| guardiao | cobrir_o_companheiro | 2.9 | | APPROVED |
| guardiao | resposta_da_vigia | 3.9 | | APPROVED (pune o `exposto`, que a família já aplica) |
| emboscador | golpe_e_sumico | 4.0 | sim | APPROVED |
| emboscador | veneno_de_espera | 1.8 | | APPROVED |
| conjurador | onda_de_recuo | 1.3 | | APPROVED (sem dano, `_fits_creature` não pesa) |
| morto_vivo | beber_o_calor | 1.5 | | APPROVED (ver P1-1: o ajuste não é na Carta) |

Identidade e voz: no geral há identidade por família.
- Covarde: bate e foge, finge de morto, distrai.
- Tático: marca e depois pune o marcado; desarma; recua em ordem.
- Predador: derruba, sangra, some no mato.
- Bruto: agarra, dá cabeçada, cresce quando ferido.
- Guardião: escudo e provocação.

Os textos estão no léxico de Valoria (cinza, névoa, ruína, caserna), sem número. Não há clone exato dentro de nenhuma família.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `docs/spec373/arena-aethelgard.json` (`enemy_esqueleto_mago`); `tests/test_spec373_artefatos.py:225` | O portão R17 está vermelho: `enemy_esqueleto_mago` falha por 3,5 pp (delta do slot 11,5 > 8), acima da borda de 3. Também há 5 regressões contra a base (`esqueleto_mago` 3,5, `observador_menor` 2,0, `vinha_estranguladora` 2,5, `lamelas_de_ferrugem` 1,0, `traca_do_sino_mudo` 0,5), no limite de 5. Causa: a única diferença no baralho é `fome_dos_mortos` (buff_dano 1) → `beber_o_calor`, e ela é jogada em 32 de 244 declarações (instrumentei `enemy_declaration`). Leitura: o R9 já tinha posto a criatura na borda (L3/on 0,545 → 0,53, ou seja, delta de 7,5 com folga de 0,5 pp). A Carta só a empurrou além, e −4 pp fica em ~1 erro padrão de uma célula de 200 lutas. | **R8 no `enemy_esqueleto_mago`** (1–2 rodadas de `calibrar.py --regioes aethelgard --ids enemy_esqueleto_mago`, sentido mais fácil). Depois: entrada em `recalibradas.json`, remedir só essa criatura e registrar em §9. O `off` está em 0,475 e só sobe, então segue na faixa. **Não** mexer na Carta: ela é fraca (ps 1,5; variação média de ≈0 pp nas 3 criaturas da arena que a têm), e nerfá-la por um slot ruidoso seria ajustar conteúdo ao portão, além de obrigar a remedir todos os mortos-vivos. Com o R8, sobram 4 regressões de borda (≤ 5); as outras o R17 só pede tentar "se conseguir". |
| P2-1 | P2 | `tests/test_spec373_cartas.py:72-75` | O teto de potência compara com a Carta mais forte da família **incluindo as assinaturas**. 12 das 28 comuns passam da comum mais forte que já existia (bruto: 5.5/5.6/5.5 contra 4.5; tatico: até 4.5 contra 2.5; predador: 4.9/4.5 contra 3.5). Isso cumpre a letra do R15, mas a criatura autoral (R9) nunca recebe assinatura, e a da 332 recebe uma, telegrafada. Na arena o agregado não endureceu (−0,3 pp médio no `on` das 228 afetadas; 3 das 5 regressões são o herói vencendo **mais**), mas os casos isolados oscilam muito (`mon_gancho_de_esfola` 0,79 → 0,45 com ferro_com_ferro + golpe_combinado). | Follow-up (369 ou próxima onda de conteúdo): fixar na spec/CARTAS.md que o teto de comum é a comum mais forte. Vigiar as duas `turno` de 3+2 do tático e a `raiva_de_ferido`. Não bloqueia. |
| P2-2 | P2 | `data/cards/inimigos/tatico.json` (`ferro_com_ferro`) | Quase clone de `golpe_combinado`: mesmos kinds, números (3+2), tipo, `turno` e arma; muda só a condição (`engajado` em vez de `alvo_tem: marca`). Para um inimigo corpo a corpo, `engajado` vale quase sempre, então o custo condicional (×0,7) subprecifica a Carta. O molde "dano X + dano Y se …" em `turno` aparece 7 vezes entre as famílias. | Na próxima onda, trocar `ferro_com_ferro` por outra mecânica (guarda, contra-ataque). Exige remedir os ~4 portadores. |
| P2-3 | P2 | `data/cards/inimigos/covarde_oportunista.json` (`chutar_quem_caiu`) | O nome promete alvo caído, mas a condição é `alvo_tem: cego` (a descrição corrige para "quem não enxerga"). | Condição `enraizado` (que `chute_na_canela` aplica, dando sinergia) ou outro nome. Só texto/condição; remedir os ~5 portadores. |
| P2-4 | P2 | `tests/test_enemy_decks.py:265-270` | O teto 8–12 → 8–16 é legítimo: o R14 cresce as famílias por definição, e o arquivo não é protegido. Mas o novo teto é exatamente o máximo observado (predador 16), e o desvio não foi registrado na spec. Os picos de uso também estão no limite (predador, covarde, conjurador e bruto com `pico_comum` 15), sem folga para criatura nova. | Registrar o desvio em §9 da spec. Follow-up: margem de uso quando entrar criatura nova. |
| P2-5 | P2 | `tests/test_spec373_montagem.py:81-96` | Comparar `populacao_332` com os pools da `main` é legítimo e não afrouxa o oráculo do R9: o fixture da Etapa 0 é anterior às Cartas, a spec §7 já prevê que as comuns mudam os baralhos da 332, e a regra de montagem segue provada nas sementes 0–11. Lacuna: nada fixa agora **o que** muda na 332 com os pools cheios. | Teste complementar: com os pools cheios, toda entrada não autoral mantém as próprias Cartas, a mesma assinatura de família, a mesma contagem de comuns e as mesmas de facção; só a escolha das comuns muda. |
| P2-6 | P2 | `tests/test_spec373_cartas.py:23-27` | `_familias` duplica `_family_cards` de `tests/test_enemy_decks.py:258`. O arquivo novo `test_spec373_*` é aceitável porque a spec §3 o declara. Trocar `test_assinaturas_373_telegrafo` por `test_r14_nao_cria_assinatura_nova` também é legítimo (`S_min` = 2 em todas as famílias, então nenhuma assinatura nova). Usar `card_lint` sem `momento`/`tier` e unicidade só intra-família segue a 332 e o R15. O teste novo é **mais** rígido que o da 332 (barra aviso, não só erro). | Opcional: reutilizar o helper. |
| P2-7 | P2 | `75b73e2b` (mensagem) | A medição mesclada é sólida (ver abaixo), mas o relatório não lista **quais** 27 criaturas foram remedidas nem quais Cartas foram reajustadas depois da arena cheia. | Pôr as duas listas em §9. |

### Medição mesclada (item 3)

A mesclagem se sustenta. O que conferi:
1. **Mecanismo.** O `fight` semeia o RNG por `(modo, nível, classe, bid, n, seed)`. O baralho depende só do `id` da instância e do `deck_seed`, que fica 0 porque o `_instances` da arena 285 não o define. Logo a célula de uma criatura não depende de nenhuma outra.
2. **Isolamento.** Nas 281 criaturas, toda criatura cujo baralho não mudou com as Cartas novas (comparando com os pools sem `cartas-373`, ids `_1.._4`) tem células bit a bit iguais às de `9e98b241`, sem exceção. Nenhuma célula `off` mudou.
3. **Reprodução.** Remedi 6 criaturas afetadas de aethelgard: `esqueleto_mago`, `golem_carne`, `doador_inacabado`, `subida_de_cracas`, `lesma_de_penacho` e `camarao_faxineiro` (sementes 0–39). Os valores bateram exatamente com os gravados.

Risco residual: não dá para provar que os 27 cobrem todo portador de Carta reajustada, porque as versões pré-ajuste não estão versionadas. Os 6 exemplos não acharam divergência.

Achado lateral: em muitas criaturas autorais as comuns de família quase nunca são jogadas. A `lesma_de_penacho` e o `camarao_faxineiro` só declaram as próprias Cartas ou o ataque. Das 228 criaturas da arena com baralho alterado, só 80 mudaram de célula. A arena mede pouco a potência das Cartas novas nesses casos, e o teto de `power_score` vira a defesa principal.

## Correções aplicadas

Nenhuma até aqui (revisão só de leitura).

## Pendências

- P1-1: executor (Terra), nesta spec, antes do pouso.
- P2-4/P2-7: executor, em §9 desta spec.
- P2-1/P2-2/P2-3/P2-5: coordenador, para a SPEC-369 ou a próxima onda de Cartas de inimigo.
- Renomear a referência `SPEC-373-cartas-review.md` → `SPEC-373-astra-review.md` na spec.

## Comandos rodados

```text
bash scripts/dev/pt.sh tests/test_spec373_cartas.py tests/test_spec373_montagem.py tests/test_enemy_decks.py tests/test_card_lint.py → 84 passed
bash scripts/dev/pt.sh tests/test_spec373_artefatos.py → 7 passed, 2 failed (regressoes_de_borda: esqueleto_mago 3.5 pp; confirmacao-40-119 ausente, esperado)
bash scripts/dev/py.sh scripts/validate_content.py → 0 erro, 29 avisos (bestiário, fora do escopo)
arena.py --regiao aethelgard --seeds 40 --ids <6 criaturas> (scratchpad) → células idênticas às gravadas
scripts ad hoc (scratchpad): power_score por Carta/família, diff de baralho com/sem cartas-373, Cartas jogadas por enemy_declaration, regressões contra a base
```
