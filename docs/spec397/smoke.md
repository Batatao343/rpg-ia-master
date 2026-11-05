# SPEC-397 §5 — smoke com LLM real (itens 2a, 2b, passiva por espólio, `draft.py --n 4`)

Feito em 04/11/2026 (agente de smoke local) sobre o HEAD `2d955f0b` da branch `spec-397`.

**Ambiente.** Cópia `git archive` do HEAD fora do OneDrive, `.env` copiado (nenhum valor impresso), perfil `legacy`, flags do preset `scripts/staging/staging_flags.json` (cartas `on`), arte de criatura e dinâmica desligadas (0 retrato), rotas default. Execução em processo com `TestClient` (nenhuma porta aberta; a `:8000` ficou intocada), via `smoke/smoke397_driver.py` (jogo criado pela API real; o save recebe `encounter_surprise="enemy"` e a Carta conforme o caso; a ação "Ataco o goblin" vai ao LLM real). Corruptor nível 1. Processo órfão do próprio agente (um `python -` sem stdin) morto por PID; cópia temporária removida no fim.

**Custo.** ≈ US$ 0,02 no total (estimativa: 3 jogos novos com plano de campanha + 3 aberturas, cada turno ≈ US$ 0,0003 a 0,0007 pelo log; `draft.py`: US$ 0,0027 pelo próprio script). Teto 0,05. 0 retrato.

## Tabela

| Item | Resultado | Evidência |
|---|---|---|
| 2a Faro preparado, emboscada forçada | **ok.** `initiator=null`, `initiator_reason="ambush_negated_vigilia"`. A abertura narrada termina com "Você percebe a emboscada a tempo e não é pego de surpresa." | `smoke/2a.json` |
| 2b Faro fora de preparadas, do deck e de `known_cards` | **ok.** `initiator="enemy"`, `initiator_reason="ambush"`, `faro_known=false`. A abertura termina com "O inimigo se antecipa e ataca primeiro: você foi pego de surpresa." | `smoke/2b.json` |
| 3 Faro por `/game/espolio` com 4 preparadas | **ok.** Antes: 4 preparadas, Faro desconhecido. `POST /game/espolio` 200, log "Faro do Abismo entra no seu Acervo.". Depois: ainda 4 preparadas (`cor_toque, cor_esporos, cor_carne_docil, cor_membrana`), Faro fora de `prepared_cards` e do `deck`, em `known_cards`, e listado em `player_stats.cards` (tipo `passiva`, `prepared:false`, "+2 de Iniciativa."). Motivo `passiva_permanente` confirmado chamando `card_rewards.accept` num save real (`destino="acervo"`, `motivo="passiva_permanente"`, preparadas 7 → 7 com o baralho aberto, Faro fora). A emboscada seguinte (`encounter_surprise="enemy"`, ação real) foi anulada: `ambush_negated_vigilia`, e a abertura diz que você percebeu a tempo. | `smoke/3-espolio.json`, `smoke/3-motivo.json`, `smoke/3-emboscada.json` |
| 4 `draft.py --n 4` (Médico de Campo, boticário, comum/incomum) | **ok.** Entregou 3 (≤ 4); `AVISO: pediu 4, entregou 3`; 1 rejeitada na triagem de vocabulário (`med_torno_de_ervas`, "efeitos sem efeito principal"). `frequencia` das 3 entregues = `cena` (dentro do enum `cena/descanso_curto/descanso_longo/livre/turno`); nenhuma inventada. `lint.py`: 3 verdes, 0 reprovadas. Como o lote saiu abaixo de `n`, o aviso de "aprovadas descartadas pelo corte" não foi exercido (só o de "entregou menos"). | `smoke/draft-lote.json`, `smoke/draft-stdout.txt` |

## Achados (sem correção de produto)

1. **P3, o rótulo `passiva_permanente` não chega ao cliente pelo espólio.** `POST /game/espolio` devolve só `ok`, `log`, `player_stats` e `espolio_pendente`; `destino`/`motivo` existem no retorno de `card_rewards.accept` (`services/card_rewards.py:~419-430`) mas a rota (`routes/play.py:~202`, via `_card_reward_mutation`) não os repassa, e a oferta pendente (`public_pending`) não traz `destino`/`destino_motivo`. O rótulo de `web/src/cardRewards.ts` (`ACERVO_MOTIVO_LABEL`) só tem como origem a loja (`card_shop`, que chama `acervo_reason` em `services/card_shop.py:157,237`). Para o espólio o jogador só vê o log "entra no seu Acervo." Causa provável: o espólio nunca expôs o destino previsto; pode ser aceitável (a passiva aparece no Acervo).
2. **Observação (seed, não produto):** com o baralho `on`, `prepared_cards` do Corruptor após abrir o combate tem 7 entradas (4 de slot + básicas do baralho), então "4/4" só vale antes do primeiro conflito; no item 3 a contagem 4 → 4 foi medida antes de abrir o combate e a de 7 → 7 depois.
3. **Observação (item 4):** este lote não exercitou o corte em `n` (veio 3 de 4 pedidas), só o aviso de "menos que n"; o corte já tem teste unitário (`test_batch_is_cut_at_n`). O LLM não inventou `frequencia` desta vez.
