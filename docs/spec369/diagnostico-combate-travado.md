# Diagnóstico: combate "travado" e `defeat` com o herói vivo (smoke 369, item 5)

05/11/2026. Diagnóstico só de leitura, sem correção no produto. Fontes:
- logs da Vercel do deploy `rpg-ia-master-staging-klav3zb4z` (`git_sha` a7673f55), janela 12:38–13:37 UTC, 1196 registros, sem lacunas;
- os logs do driver do smoke (`stg9.py`, `stg10.py` e `stg11.py`, com `s9/`, `s10/` e `s11/stg_log.jsonl` no scratchpad da sessão do coordenador; não versionados).

## Veredito curto

- **P2: não é bug de motor nem de concorrência. É um laço do driver do smoke em cima de um 409 que ele ignora.** Nenhuma rodada "travou" no servidor. Todas as jogadas "sem efeito" foram recusadas na borda com `409 invalid_target`. Como o turno é SSE, o HTTP volta 200 e o erro chega como evento `error`. O driver registra o erro em `res.error`, mas não tira a jogada recusada da fila. A mão não muda depois de uma recusa, então ele reenvia a mesma jogada para sempre.
- **Há um defeito real de contrato no produto (P3)** que alimentou o laço da execução 1: a mão anuncia a Carta de reação `med1_ini_pinca_no_tendao` como `jogavel: true` e `alvo: "inimigo"`, mas com `valid_targets: []`.
- **P3 (`defeat` com o herói de pé) é comportamento especificado**: é o objetivo de cena que falhou (SPEC-331 R5). Só o rótulo persistido engana; a narração já é corrigida pela SPEC-387 R20.
- **A SPEC-369 não é culpada.** Nenhum dos caminhos envolve as Cartas de Fôlego 0 nem a `lente_de_protese`. O código de alvo e do 409 vem da SPEC-363 (02/11). O dano 5 do `bas_med_golpe` só fez o Afogado chegar mais cedo à Vitalidade 0.

## Evidência por execução

### Execução 1 (jogo `5532e4d4…`, 13:18–13:22 UTC, só um inimigo: Afogado da Batalha)

| Rodada | Jogadas enviadas | Servidor |
|---|---|---|
| 1–7 | `bas_med_golpe` × 2, guarda, torniquete, pressão | 7 turnos normais (`combat.summary`); Afogado 14 → 7 → 1 → 1 → 1 → 1 → **0** |
| 8 e as 8 do "conflito 2" | `cena_lodo_espesso` → Afogado, **`med1_ini_pinca_no_tendao` → Afogado** | `sse.error` 409 `invalid_target`, `invalid_reason: no_valid_target`, `play_index: 1`, nas 9 vezes, em ~100–400 ms, sem rodar turno |

- **Vitalidade 0 não encerra o conflito, e isso é por design.** Com Vitalidade 0, cada golpe passa a abrir Ferimentos. O inimigo comum só cai quando enche o último espaço de Ferimento Crítico (`services/conflict_orchestrator.py:1644`, `death_flow.uses_full_death_flow`/`critical_spaces_full`). Até lá, só registra `sem_vitalidade` (`conflict_orchestrator.py:262-270`). `_targetable` aceita esse estado (`services/conflict_turn.py:313-324`). Na rodada 7 o Afogado recebeu Ferimento grave e leve, mas não Crítico, e por isso seguiu ativo e mirável.
- **Por que veio o 409.** `med1_ini_pinca_no_tendao` é `tipo: "reacao"` (`data/cards/posturas/medico_reacao_inicial.json`). `valid_targets_for_card`/`hand_card_targeting` devolvem `([], None)` para uma Carta que não é `ativa` (`services/combat_targeting.py:120-122` e `153-154`). Quando chega um `target_id` explícito, `check_declared_target` cai em `return "no_valid_target"` (`combat_targeting.py:220-225`), e `routes/turn.py:609-626` levanta o 409 da lista inteira. A mão da rodada 7 mostrava a Carta assim: `{"id": "med1_ini_pinca_no_tendao", "jogavel": true, "alvo": "inimigo", "valid_targets": []}`.
- **O driver (`stg9.py`) tem dois defeitos.** O primeiro: `tg = [e["id"] for e in enemies if (e.get("vit") or 1) > 0]` trata Vitalidade 0 como 1. O segundo: `t = next((x for x in tg if not vt or x in vt), None)` faz `valid_targets == []` cair no "qualquer alvo" e põe `target_id` na Carta de reação. Além disso, o driver não reage ao `res.error`.

### Execução 2 (jogo `315b2be7…`, 13:26–13:31 UTC, Escuta do Sinal + Necromante Renegado)

- A rodada 1 rodou normalmente. A partir da rodada 2, a mão trouxe `valid_targets: []` para todas as Cartas de ataque (`bas_med_golpe` × 2, `cena_obj_altar_afogado`): os dois inimigos ficaram fora da mira (oclusão/ocultação). O driver mandou `bas_med_golpe` no Escuta do Sinal 15 vezes, e as 15 voltaram 409 com `invalid_reason: target_hidden` e `play_index: 0`. Por isso o `mech_log` "repetido" é só a rodada 1, que não mudou.
- **Os 39 s da "rodada 4" não aconteceram no servidor.** O pedido anterior chegou ao servidor às 13:27:53. O pedido desta rodada, que no cliente somou `total_ms` 39 248, só chegou às 13:29:07.1, no `http.request`, e levou 263 ms até o 409. Os 39 s ficaram antes do servidor, na rede/borda ou no cliente, e não no motor.
- Na interface real, a carta sem alvo responde "ninguém ao alcance" e não entra na fila (`web/src/components/combat/DeckCombat.tsx:153-154`). Um 409 tira só a jogada recusada (`web/src/combat/deck.ts:234`, SPEC-363 R21). O jogador real não entra no laço: ainda tem Cartas de aliado, passar ou fugir.

### Execução 3 (jogo `5d417597…`, P3)

- Às 13:33:20 veio `combat.scene_objective_resolved` com `tipo: interromper_ritual` e `ok: false`. O objetivo pedia que o Necromante saísse até a rodada `n` (= 3), e ele ainda estava ativo: `services/scene_cards.py:623-628` registra "O ritual se completa.". `_encounter_outcome` mapeia `objective_result == "falhou"` para `"defeat"` (`agents/combat.py:2191-2192`, SPEC-331 R5). A narração já troca para `objective_failed`, "O herói segue de pé" (`agents/combat.py:2077-2082`, SPEC-387 R20), e é isso que o texto do smoke mostra.
- `enemies: []` aconteceu porque o conflito fechou e a cena foi limpa. O Necromante não morreu nem se rendeu nesse conflito. No conflito seguinte entrou outro Necromante (`enemy_necromante_renegado_1`), que levou 7 de dano e cumpriu o objetivo às 13:33:44 (`victory`). A "rendição" aparece só na prosa desse fecho.
- Houve também `combat.outcome_attribution_rejected` (`codes: V5`) no fecho do conflito 1. É o validador da atribuição na prosa, não afeta o desfecho, mas vale um olhar junto com o rótulo.

## Hipóteses do pedido

| Hipótese | Veredito | Por quê |
|---|---|---|
| (a) Fôlego 0 sem fechar a rodada ou laço de declaração | **derrubada** | Nenhuma Carta de Fôlego 0 da 369 está no baralho do Médico. Todas as jogadas travadas são 409 na borda, antes do motor. |
| (b) Concorrência/save velho entre instâncias | **derrubada** | Execução 1: 409 igual em duas instâncias (`bcfedf93` e `cc11c0dc`). Execução 2: uma instância só (`3e7ab3ac`). O estado não mudou porque o pedido foi recusado, não porque o save estava velho. |
| (c) Fim de combate com Vitalidade 0 não dispara | **derrubada como bug** | É a regra de Ferimentos: só o Crítico cheio derruba. Vale anotar a dúvida de UX: "0 de Vitalidade e de pé" pode parecer travado para o jogador. |
| (d) `action_id` repetido pelo driver | **derrubada** | `stg6.stream` gera `uuid4()` por pedido. Cada pedido teve um `action_ref` próprio nos logs. |
| (e) `defeat` para rendição/fuga | **confirmada, com outra causa** | É o `defeat` de objetivo falho (SPEC-331 R5), não rendição nem fuga. |

## Reprodução local (MockLLM, sem rede)

Arquivo `repro.py` no scratchpad (`stuck/`). Ele monta um estado com o Afogado em Vitalidade 0 e a mão `[med1_ini_pinca_no_tendao, bas_med_golpe]`:

```
afogado vit 0 targetable: True
mao: med1_ini_pinca_no_tendao tipo reacao jogavel True alvo inimigo valid_targets []
mao: bas_med_golpe tipo ativa jogavel True alvo inimigo valid_targets ['mon_afogado_da_batalha_1']
check_declared_target med1_ini_pinca_no_tendao -> no_valid_target
check_declared_target bas_med_golpe -> None
check pinca sem target_id -> None
```

Não precisei comparar com `a7673f55~N`. Os arquivos do caminho (`services/combat_targeting.py`, o trecho 409 de `routes/turn.py` e `card_piles.public_view`) não foram tocados pela 369: o último commit funcional de `combat_targeting.py` é `377d54b1` (SPEC-363, 02/11).

## Correções propostas

1. **Driver do smoke (agora, sem spec).** Escolher alvo só de `valid_targets` (`[]` significa "não jogue com alvo"). Filtrar inimigos por `vit is not None and vit > 0` só como dica, sem trocar `valid_targets` por isso. Diante de `error.code == invalid_target`, tirar a jogada de `play_index` e reenviar, como a interface faz (SPEC-363 R21). Parar depois de N recusas iguais. Reexecutar o item 4 (segundo conflito da mesma família) com o driver corrigido.
2. **Contrato da mão (produto, P3; cabe na SPEC-397 ou numa spec curta).** `card_piles.public_view` (`services/card_piles.py:756-773`) deve sair coerente com o motor:
   - Carta `tipo: "reacao"` não é jogada da mão como ação. Ela deve sair com `jogavel: false` (ou `alvo: "si"` e um motivo), ou então o motor precisa de um caminho para jogá-la. Hoje a interface mostra a Carta, e ao tocar diz "ninguém ao alcance", o que é enganoso.
   - Carta de alvo `inimigo` com `valid_targets == []` deve trazer o `invalid_reason` (`target_hidden` ou `no_valid_target`) no próprio item da mão, para a interface explicar o motivo (inimigo oculto).
   - Teste: estado com a reação na mão e com inimigos ocultos; afirmar `jogavel`/`invalid_reason` e que nenhum `target_id` aceito pela vista gera 409.
3. **Rótulo `defeat` para objetivo falho (decisão do dono ou do autor da 331).** Persistir um desfecho próprio (por exemplo `objective_failed`), ou manter `defeat` e documentar que consumidores como `_flee_alert_world` (`agents/combat.py:1699`), companion tags e telemetria devem ler `objetivo_resultado`. O que está quebrado hoje é só a leitura do smoke e de dashboards, não a narração.
4. **Dúvida de UX, sem urgência:** mostrar "de pé com 0 de Vitalidade" (ou os Ferimentos) no chip do inimigo, para que o jogador não leia o estado como travamento.
5. **Pendente, precisa reprodução com a `scene` completa:** por que os dois inimigos da execução 2 ficaram ocultos ao mesmo tempo logo na rodada 1. Se isso for comum, o Médico, cujo único ataque é Carta, fica várias rodadas sem mira. A ocultação em si não é bug: as Cartas de aliado e o passar seguem disponíveis.
