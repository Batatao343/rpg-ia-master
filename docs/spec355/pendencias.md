# SPEC-355 — pendências abertas do épico de cartas (levantadas pelo coordenador, 28/10)

Dono (28/10): "pegue todos os ajustes que ainda estão em aberto, faça uma spec e execute". Fonte: handoffs e §9 das SPEC-335/336/339/341/342/345/346/347/352/353/354, ESTADO_ATUAL e memória do coordenador. Cada item tem a origem para o autor conferir no source.

## A. Balanço (arena por Postura; faixa do dono 45–85 %, teto por subclasse 75 % com as exceções aceitas na 341)
1. **Utilitárias fora da compra em combate** (SPEC-353 D6 revertido): tirar `utilitaria` da compra no combate fez o Médico de Campo +2,7 pp (54,6→57,3 %). Fazer o corte + recalibrar o Médico (cartas de onda do Médico, 1 passo, só número/custo) até ±2 pp da base. Hoje "Aguentar" aparece na mão com motivo `fora_de_combate`.
2. **Provocação na mesma rodada** (SPEC-353 D4; smoke 2 item 11): "Voto Sussurrado" acerta e o inimigo ataca outro na mesma rodada (presságio já congelado). Decidir/implementar: provocar troca o alvo do presságio congelado da rodada (com chance) — medir na arena (Devoto).
3. **Cartas fortes demais**: `san1_sil_corte_sem_aviso` (+9,1 pp dominante na held-out da 341, já no máximo de 1 passo) e `san_exp_espetaculo` (LEGADA — golden protegido; só com o protocolo de golden da 339/D7: proposta + golden regenerado em commit separado por outro agente + revisão Sol). Para a legada: confirmar a bandeira com sementes novas antes; se não confirmar, só registrar.
4. **Emboscada no pior caso** (SPEC-346 arena): com 100 % de emboscada, Corruptor 42,7 % e Arcanista 39,2 % (abaixo de 45). Medir com frequência realista de emboscada (do storyteller) e, se abaixo da faixa, dar contrapartida (ex.: mais cartas/traços de vigília por Postura usando cartas existentes; sem número novo sem arena).
5. **Cartas com 2d6** em `data/cards/exemplos.json` (`golpe_devoto`, `corte_sangrento`, `praga_lenta`, `raio_cinza`; SPEC-345 D8): rolam 2d6 de verdade pela via legada num sistema 2d10. Decidir: alinhar ao sistema (se são de exemplo/fora do jogo, tirar do baralho jogável) — conferir onde são usadas.
6. **Arena**: follow-ups da 336 — arena por substituição (troca de carta em vez de só remoção), flag de "uso" do bot rebaixada a aviso; `full_deck` ordem (conferir se a 339 já resolveu).

## B. Motor / regras
7. **R8b da 339**: buff de reação em si mesmo ainda dura 1 turno a menos (exige `source_actor_id` na condição; golden). Implementar respeitando o golden (campo fora do dicionário comparado ou protocolo de golden).
8. **Chefe abaixo de 35 % depois do anúncio** (SPEC-332 P2-7): o chefe pode cair abaixo do limiar da fase seguinte no mesmo golpe do anúncio; garantir a transição de fase coerente.
9. **Router (fallback quando os 3 CLASSIFY falham)** — limites aceitos na 346: "sem pensar ataco o saqueador" (alvo fora de cena) fica em STORY; "ataco o guarda para abrir caminho" fica em STORY; frases forçadas com criatura do bestiário abrem combate. Melhorar a heurística (verbo hostil + alvo humano/criatura mencionado na narração recente) com bateria ampliada; sem regressão nos casos seguros.
10. **Queda por Reação sem golpe final explícito** (SPEC-353 §9: `final_blows` só nos chamadores do orquestrador) — o resumo final perde a autoria nesse caso.
11. **Etapa 0(c) da 353**: confirmar a origem da "Descarga Arcana" no "Renegado (machado)" e se o 6 do Penitente foi Proteção (agora `Proteção −N` aparece no mech_log) — fechar no smoke.

## C. Conteúdo / autoria (SPEC-336)
12. `scripts/cards/gen_tiers_5_plus.py` não pode escrever sem `--force` (incidente: rodar sem args reescreveu 10 arquivos).
13. `cards_for_class("")` — comportamento indefinido com classe vazia.
14. Rótulo `armadura_comprometida` sem texto legível na UI/registro.
15. `arc1_cal_leitura` com aviso de lint `revelar intencao` (decidir: corrigir a carta de onda ou ajustar o lint com justificativa).
16. **Cartas neutras na loja e nas missões** (gancho de obtenção além do espólio).

## D. Operacional / verificação (o coordenador executa; a spec só registra critérios)
17. Smoke real final (§6 das 346/347/352/353/354) no staging com as cartas ligadas, gravando o corpo de `/game/history` (Livro).
18. Migration `20261028120000_creature_portraits.sql` no staging + bucket `rpg-shared-art` + 1–3 gerações reais de retrato (SPEC-352 §6).
19. 319 P2-1: medir `replace` do stream no combate.
