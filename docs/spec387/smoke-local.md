# Smoke local (LLM real): SPEC-387 §6 itens 5–16

Feito em 04/11/2026 (03:55–04:25 UTC) pelo agente de smoke local. Itens 1–4 (staging) são do coordenador e não estão aqui.

**Ambiente.** Cópia `git archive` de `1e2a9c3c` fora do OneDrive, `web/dist` gerado dela, `.env` copiado. Perfil `legacy`. APIs: `:8760` (preset `staging_flags.json`, cartas `on`, mais `RPG_CREATURE_ART=on`, rotas default), `:8761` (Groq 120b em CLASSIFY/FAST/SMART), `:8762` (CLASSIFY `modelo-inexistente`), `:8763` (CLASSIFY inexistente, FAST/SMART Groq 120b), `:8764` (cartas `off`, FAST inexistente). Saves de `seed_save` (MockLLM) e jogos novos criados com MockLLM; as rodadas jogadas foram contra o LLM real, mas as do meio de combate não chamam LLM. APIs mortas por PID e cópia apagada no fim.

**LLM.** DeepSeek (primário, todos os tiers) e Groq `openai/gpt-oss-120b` nas portas 8761/8763. Nenhuma queda para fallback com a rota default.

## Tabela item → resultado

| Item | Resultado | Evidência |
|---|---|---|
| 5 `2 frustrar` | **ok no registro; chip da UI não verificado (achado 2)**. 1 rodada: "Goblin está atordoado e perde o turno. Presságio frustrado: Goblin" na mensagem e no `/game/history`; sem id e sem a Carta oculta. Na UI a 390 a aba Combate só mostra o presságio da rodada seguinte; nenhum "frustrado" no painel. | `out/i5-r1.json`, `out/i5-h.json`, `out/i5ui-390.png` |
| 6 `3 eco` | **ok**. "Talho de Sangue Ralo" (6) e "Segundo Ato" (Eco) acertaram; Segundo Ato causou 6 de dano com `dano_base` 3 (bônus de Eco aplicado). A linha do registro não cita "Eco". | `out/i6-eco-r1.json` |
| 6 `3 rachadura` | **ok**. "Goblin ganha a condição Rachadura." vem **antes** do ataque do goblin; `mech_log`: `Rachadura +25 % · 7 dano` (R28). | `out/i6-rac-r1.json` |
| 7 `5 chefe_fase` | **ok**. Valerius (16 PV): rodada 1 traz "desembainha por inteiro: a guarda fecha, e a paciência acaba" e "rasga o decreto no meio e avança sem guarda alguma", na mensagem e no `/game/history` (Livro); "age de novo" seguido de um ataque básico real; 0 "Ataque sem alvo válido." | `out/i7-r1.json`, `out/i7-h.json` |
| 8 `13 voto` | **ok em parte**. Ketil na cena, presságio mirava Ketil; depois do Voto o goblin atacou "Você". A linha diz "Goblin está provocado: a próxima intenção dele mira você (com chance)", sem "muda de alvo"/"resiste" (achado 5). | `out/i8-voto-r1.json` |
| 8 `13 armadura` | **ok com ressalva (achado 6)**. Só com `ruptura: true` o Soldado ganha "Armadura Comprometida" (registro com o rótulo humano, nunca o id; `label` correto no estado, mas o `name` do estado é o id cru). Jogada sem ruptura: só dano. | `out/i8-arm-r1.json`, `out/i8-arm2-r1.json` |
| 8 `13 reacao` | **ok em parte (achado 7)**. Com `reaction_card_id` no corpo, o Goblin (1 PV) atacou, a Reação "Encaixe do Golpe" matou e o combate acabou em vitória; `mech_log` cita "Encaixe do Golpe", mas a prosa do registro diz "Você ataca Goblin com Espada Gasta". Jogar a Reação em `jogadas` devolve "Encaixe do Golpe não é uma Carta ativa." | `out/i8-rea2-r1.json`, `out/i8-rea-r1.json` |
| 8 `13 condicao_carta` | **ok**. "A condição Enredado de Goblin terminou." na rodada seguinte, sem ": … terminou" cru. | `out/i8-con-r2.json` |
| 9 `3 inelegivel` | **ok**. "Segundo Ato não está no seu baralho."; `round` continua 0, mão e Fôlego 2 intactos. | `out/i9-r1.json` |
| 9 `4` escolta | **ok no caminho feliz; falha do objetivo não verificado (achado 8)**. "Escoltado" ataca e é alvo; vitória em 2 rodadas. Com o escoltado "morto" por patch do save, o objetivo seguiu `resultado: null` e a luta acabou com a morte do herói (por custo de Vitalidade da própria Carta), sem exercitar R20. | `out/i9e-r*.json`, `out/i9f-r*.json` |
| 10 `14 entrega` | **achado (achado 3)**. "Entrego a prova da caça ao contratante": o NPC (Osshari, Brekmar) reagiu à prova, mas `quests_completed = []`, sem `quest_completed` no log e sem técnica no Acervo. | `out/i10-r1.json`, `out/i10-s2.json` |
| 11 `15 vg_ouro` | **ok (ramo sem "últimas moedas")**. Pedido "…com minhas últimas moedas" deu a confirmação em 2 passos; ao confirmar: ouro 80 → 30, "+1 Carta: Lança de Gancho". A prosa foi de números ("80 antes, 50 pelo preço, 30 depois"), sem "últimas moedas", então `trade_prose_rejected` não apareceu (0 no log). "Skallgard" só como lugar ("Na Forja dos Clãs, em Skallgard"), nunca sujeito (R35). | `out/i11-r2.json` |
| 12a Groq 120b no CLASSIFY | **ok**. `gpt-oss-120b` classificou "Ataco o goblin" e o combate abriu (1 classify + 1 fast, ~0,7 s no classify). | `out/i12a.json` |
| 12b `hostility_fallback` | **ok com condição (achado 4)**. Com CLASSIFY `modelo-inexistente` e FAST DeepSeek, a narração negou o goblin (2 jogos) e **não** abriu combate; com FAST Groq a narração citou o goblin e `hostility_fallback` abriu o combate. | `out/i12b.json`, `out/i12c.json`, `out/i12d.json` |
| 13 modo `off`, FAST inexistente | **ok**. 2 rodadas: "Goblin avança contra você. … Você erra Goblin. Goblin usa Pancada Esmagadora." sem id, sem "⚔️ •", sem nome do herói. | `out/i13-1.json`, `out/i13-2.json` |
| 14 `draft.py` | **ok**. 1 chamada SMART: pedidas 4, entregues 4, rejeitadas 0, custo estimado US$ 0,0025. `lint`: 2 verdes (`med_campo_linho_fervido`, `med_campo_caldo_de_ossos`), 2 reprovadas (orçamento/raridade). `sim lote-v2`: `tonico_de_ferro` `dominante` (+13,8 pp), as outras com `uso_alto`. `promote`: 2 promovidas, 2 recusadas (precisa de `--voz-pendente`, ausente da linha impressa; achado 9). | `draft.out`, `lint.out`, `sim.out`, `promote2.out` |
| 15 UI a 390 | **ok em parte**. "Presságio cumprido: Goblin — Investida Cega" (R30) no painel de efeitos da rodada. R32: no scroll padrão o presságio fica visível e com a rolagem no fim a barra não cobre nada. R31: a API devolve `subclass: "Mão Sombria"` para `inf_fac_mao_sombria_po_nos_olhos`, mas o Acervo da UI (390 e 1440) só mostra "preparada · ativa", sem o rótulo (achado 10). | `out/i15-vot-390.png`, `out/r32-390.png`, `out/i15-esp2-1440.png` |
| 16 varredura do histórico | **ok**. 21 campanhas, 103 entradas: 0 ids, 0 nome do herói, 0 `": … terminou"`, 0 "cumpre o presságio", 0 "Ataque sem alvo", 0 "não está na cena", 0 "⚔️". Amostra pequena (os turnos são poucos e quase todos de combate). | `scan.out`, `scan2.py` |

## LLM, custo

- Turnos com LLM: 12 (≤ 20). Rodadas de meio de combate: 0 chamadas (`llm_calls 0`, 15 de 21 turnos da `:8760`). Rodada final 2 chamadas (FAST/narrador e SMART/arquivista, ~5,6–10 s). Turno do NPC 4 chamadas (~12 s), compra 2–3 chamadas (~5 s).
- Provider: DeepSeek em tudo (a `:8760`, `:8762`, `:8764`); Groq `gpt-oss-120b` nas `:8761`/`:8763` (free tier). `invoke_error` esperados: classify `modelo-inexistente`/FAST inexistente (<100 ms, sem fallback porque as rotas só tinham 1 candidato).
- Custo estimado: `:8760` US$ 0,0122, `:8762` 0,0065, `:8761`/`:8763` 0,0011 (tarifa Groq do cartão), `:8764` 0,0007, `draft.py` 0,0025: **~US$ 0,023**. Nenhuma imagem paga. 1 execução de `draft.py`.

## Achados

1. **Observação:** `seed_save` com o roteiro agora funciona sem ajuste de save em todas as variantes testadas (2 frustrar, 3 eco/rachadura/inelegivel, 4, 5 chefe_fase, 13 voto/armadura/reacao/condicao_carta, 14, 15). Cada `seed_save` precisa rodar com cwd na cópia (`from tests.fixtures…`). O roteiro de 13 `armadura` precisa de `"ruptura": true`, e o de `reacao` do campo `reaction_card_id` no corpo (não dá para jogar a Reação em `jogadas`); vale anotar no §6.
2. **P3: presságio frustrado não aparece no painel da UI.** O registro/Livro traz "Presságio frustrado: Goblin", mas o `/game/state` não tem campo de frustrados e o painel "Efeitos da rodada" (que mostra o "cumprido") não lista o frustrado.
3. **P2: `14 entrega` não fecha a quest.** O narrador/NPC reage à prova, mas `quests_completed` fica vazio e nenhuma técnica chega ao Acervo; o turno também fez `campaign.replan reason=region_change` e zerou o arco (`current_step` 1 → 0, `total` 3 → 5). A quest `q368` não é concluída por frase livre aqui (R23 cobre offline, por isso não é regressão da 387).
4. **P3: `hostility_fallback` depende da narração citar o goblin.** Com FAST DeepSeek a narração negou o goblin ("não existe aqui") nos 2 jogos e a luta não abriu. Comportamento defensável, mas o roteiro do §6 item 12 pode dar "não abriu" por causa do narrador, não do código.
5. **P3: texto do Voto.** "Goblin está provocado: a próxima intenção dele mira você (com chance)" aparece mesmo quando o ataque da própria rodada já foi em "Você"; o texto prometido "muda de alvo"/"resiste" não saiu.
6. **P3: `name` da condição no estado é o id** (`armadura_comprometida`, com `label` humano); a UI usa o `label`, o registro está correto, mas outras condições têm `name == label`.
7. **P3: vitória por Reação não cita a Reação na prosa** ("Você ataca Goblin com Espada Gasta"); só o `mech_log` cita "Encaixe do Golpe".
8. **Não verificado:** R20 (objetivo `proteger` falho com narração da causa); o patch de save que usei (vitalidade 0 e `status "morto"` em `party[0]`) não derrubou o escoltado de verdade.
9. **P3: a linha impressa de `promote.py` falha** sem `--voz-pendente` ("revisor_voz precisa ser um revisor real"); com a flag promoveu as 2 Cartas verdes.
10. **P3: rótulo de facção não aparece no Acervo da UI** (API correta, `subclass: "Mão Sombria"`); o chip pode estar só em outra tela (Forja/detalhe), não conferido.
11. **Observação:** `sim lote-v2` classificou `tonico_de_ferro` como `dominante` e as 2 verdes com `uso_alto`; as Cartas do `draft.py` continuam saindo com orçamento no limite (2 de 4 reprovadas no lint).

## Não verificado

- Item 5: chip da UI para o presságio frustrado (sem campo no estado).
- Item 9: falha do objetivo de escolta e a narração da causa (R20).
- Item 10: entrega da técnica (a quest não fechou).
- Item 11: ramo `trade_prose_rejected` (a prosa não disse "últimas moedas" nesta execução).
- Item 15: rótulo "Mão Sombria" na UI.
- Itens 1–4: com o coordenador (staging).
