# Playtest comerciante real — 2026-08-20

## Resultado

- Run: `20260820-112050-208317`
- Perfil/classe/seed: `comerciante:1` / Sangromante / `5100`
- Execução: `200/200`, `data_complete=true`, `mock=false`, sem aborto
- Limites: 800 invokes e US$ 0,25
- Consumo: 560 requests de rede, 548 sucessos, US$ 0,162860
- Qualidade: zero erro, zero invariante `error`, zero erro de observabilidade e
  zero invocação terminal sem sucesso; oito turnos usaram fallback real
- Latência: p50 9,490 s, p95 22,443 s e um warning em 47,143 s

O preflight inicial de 10 turnos encontrou o modelo Groq FAST removido
`llama-3.3-70b-versatile`. A rota foi atualizada para o modelo disponível
`openai/gpt-oss-120b`, provado por contrato real de `NPCResponse`; o segundo smoke
(`20260820-111828-337929`) completou 10/10 sem fallback terminal.

## Cobertura de produto

| Sinal | Resultado |
|---|---:|
| Economia | 76 turnos (38,0%) |
| Exploração | 49 (24,5%) |
| Quest | 22 (11,0%) |
| Social | 22 (11,0%) |
| Sobrevivência | 31 (15,5%) |
| Mercados / regiões | 4 / 3 |
| Transações bem-sucedidas | 2 |
| Recusas | 28 |
| Restocks observados | 1 |
| Combates iniciados/encerrados | 8/8 |
| Mortes / epochs | 2 / 3 |
| Quests criadas/concluídas | 4/1 |
| Nível / ouro / net worth finais | 4 / 168 / 533 |

Os 200 registros foram persistidos com `session_action_count=200`; os restores
explicam o turno canônico final 181. Não houve replay de conflito. A revisão
manual amostrou 21 turnos distribuídos entre início, meio e fim e todas as cinco
famílias de ação.

## Achados

### P0

Nenhum.

### P1

1. **Observação de mercado vira compra de item inexistente.** Vinte e oito ações
   públicas de consulta foram classificadas como compra: nove ocorrências de
   “Confiro novamente o estoque...”, nove de “Examino o estoque...”, quatro de
   “Reavalio os preços locais...” e seis variantes. Exemplos: turnos 10, 110,
   140 e 200. O estado permanece conservado, mas o perfil obtém somente duas
   transações reais e recebe recusas diegeticamente absurdas.
2. **NPC fora da origem entra como aliado sem recrutamento explícito.** O
   `Mercador Devorador de Sol`, cuja origem é `dz_borda_do_vazio`, protege o
   jogador no combate em `deserto_zhur` nos turnos 87, 89 e 90. O warning é
   material, não apenas ruído de telemetria.
3. **Linha de sistema usa sinal errado ao vender.** No turno 2 a mecânica remove
   corretamente uma Poção de Cura Menor e credita 30 moedas (`59 → 89`), mas a
   narração exibe `[SISTEMA] +1x Poção de Cura Menor`.

### P2

1. **Contexto residual de NPC gera warning falso.** Após conversar com Nami
   Cinza-Sal em Ophidia no turno 72, a viagem a Brekmar no turno 73 acusa NPC
   reciclado, embora Nami não apareça na ação nem na narração daquele turno.
2. **Prosa contradiz ouro autoritativo.** No turno 160 o estado registra 148
   moedas, mas o narrador afirma que há 84 na bolsa. HUD/outcome continuam
   corretos.
3. **Cauda isolada de latência.** O turno 33 levou 47,143 s, acima do warning de
   45 s; não houve turno acima do erro de 90 s e o p95 permaneceu em 22,443 s.

## Decisão

O critério formal `1×200 --real` está satisfeito: campanha completa, LLM real,
sem fallback terminal, sem erro mecânico e dentro dos dois tetos. A spec do
perfil pode virar `done`. Os três P1 e três P2 não recebem correção silenciosa
neste relatório; devem ser refinados em specs próprias antes de alterar intenção
de mercado, ciclo de cena/NPC ou apresentação narrativa.
