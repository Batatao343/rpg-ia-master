# SPEC-393 §6 - smoke real local (LLM real)

Feito em 04/11/2026. Base: HEAD da branch `spec-393` (`3dd07bf2`), cópia `git archive` fora do OneDrive, `.env` copiado (nenhum valor impresso), perfil `legacy`, flags de Cartas do preset de staging, DeepSeek (rotas default). Saves de `tests/fixtures/spec368_seed.py` (seed com MockLLM), ações contra o LLM real, in-process via `TestClient` (sem uvicorn; a :8000 de outra sessão ficou intocada). Sem geração de retrato. Cópia apagada no fim.

## Tabela item -> resultado -> evidência

| Item | Resultado | Evidência |
|---|---|---|
| 1 Morte com `accept` (R1) | **FALHA PARCIAL (3/3 jogos)**. `/game/history` traz o encerramento ("Você aceita o fim. A Roda do Abismo se cala, e a sua história descansa aqui, guardada na crônica como memorial.") e já não tem a pergunta, `game_over=true`. Mas a `message` da resposta de `POST /game/death` (`accept`) **continua sendo a prosa de morte terminando em "Voltar ao último respiro seguro, ou aceitar o fim aqui?"**. Causa provável: `format_response` -> `services/turn_outcome.py:player_facing_message` devolve `last_turn_outcome["player_message"]` antes das mensagens; `apply_accept_text` só troca `messages` e `presentation_history`. | 3 jogos Médico de Campo Vit 1 vs 2 goblins (morte na 2ª rodada), `accept`. |
| 1b Prosa de morte real e guard (R3) | **ok**. 3 prosas reais do DeepSeek aceitas (parte/gravidade coerentes com o registro: "ferimento crítico no braço", "ferimentos críticos nos braços"); **0 eventos `combat.death_prose.fallback`**, ou seja o guard não rejeitou nenhuma. Num 4º jogo o resumo estourou o orçamento de 6 s (`combat.outcome_narration_budget_exceeded`) e entrou o texto determinístico ("Você tomba. Você carrega ferimento crítico no braço, ferimento grave na perna, ferimento leve na cabeça.") - esse caminho não passa pelo guard. Ramo de rejeição do guard não exercido com LLM real. | idem |
| 2 Vitória com dois inimigos na mesma rodada (R2) | **ok**. 2 goblins Vit 1, duas Cartas na mesma rodada. Caminho determinístico (orçamento estourou em 1 de 3 jogos): "Seu golpe termina o serviço: Goblin 1 e Goblin 2 tombam." Nos outros 2 jogos o texto foi prosa do LLM, que cita os dois goblins (a frase de golpe final só entra no caminho determinístico). Observação: nas prosas do LLM, ela diz que o Goblin 2 "já tinha tombado" antes, embora ambos caíssem na mesma rodada (deriva do modelo, não do produto). | 3 jogos |
| 3 "Compro a <Carta> com minhas últimas moedas" (R4) | **ok**. Nome lido da prateleira do próprio jogo (Skallgard): "Aguardente de Líquen"; ouro 80 -> 30 (-50), Carta no baralho, linha `[SISTEMA] +1 Carta: Aguardente de Líquen | Ouro −50 (total 30)`; prosa do mercador citou "restam-te 30 moedas" e passou o V-G (sem `trade_prose_rejected`). Eventos `cards.card_offered`/`card_picked` source `loja`. | 1 jogo |

## Custo

Estimado < US$ 0,02 (4 jogos de morte + 3 de vitória + 1 de compra; 1 a 2 chamadas DeepSeek de resumo por desfecho, compra 1 narração). Não medido por log. 0 retrato.

## Achados

1. **P2 (R1 incompleto): `message` do `POST /game/death accept` ainda é a pergunta.** O history está certo, a resposta imediata não. Corrigir também `last_turn_outcome["player_message"]` em `services/death_ending.py:apply_accept_text` (ou fazer `player_facing_message` ignorar o campo quando `game_over` por memorial). Falta teste de API que afirme a `message` da resposta, não só o history.
   - Corrigido em 17a45893 (apply_accept_text também troca last_turn_outcome.player_message; teste de API afirma o message).
2. Guard de prosa de morte: sem falso positivo em 3 prosas reais; ramo de rejeição só provado por teste.
3. Frase de golpe final só aparece quando a narração do desfecho cai no fallback determinístico; com LLM aceito, a prosa é do modelo.
