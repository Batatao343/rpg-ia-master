# Smoke: chefe `unico` entre contas no staging (SPEC-347 / SPEC-352)

Data: 07/11/2026. Staging `rpg-ia-master-staging` (git_sha 83675bec). Driver: `stg12.py` (fora do repo, no scratchpad), 2 contas sintéticas, 1 jogo por conta.
Evidência pequena: `chefe-unico-result.json` (hashes curtos; sem id de jogo, cookie, token ou chave crua).

## Comportamento esperado (lido no código antes do teste)

- `services/creature_art.py::portrait_key`: criatura importante (chefe, NPC, nome próprio) sem `pool_entry_id` recebe `unico:{game_id}:{espécie}:{nome}`; as comuns recebem `tipo:...`.
- `services/creature_portraits.py::visibility_for`: `unico:{game}` é `visibility=game`; `effective_visible` só devolve a linha ao `origin_game_id`. `tipo:*` é `shared`.
- O bucket usa o hash da chave (`shared/creatures/<hash12>/...`), então o `game_id` não aparece no Storage.
- Logo: o retrato pago de um chefe na conta A não aparece no jogo da conta B; o de uma criatura comum (`tipo:`) aparece (reuso já provado nos smokes 4 e 367).

## Tabela

| # | Verificação | Resultado |
|---|---|---|
| 1 | Chefe real aberto no jogo A (Skallgard, "Urso-Titã", `categoria=chefe`) traz oferta `retrato.gerar` com `escopo: "unico"` (preço 15 milli) | passou |
| 2 | Jogo B (outra conta, mesma região) abre combate com outra criatura (`escopo: "tipo"`); sem retrato de A | passou |
| 3 | A cota, confirma e paga 1 retrato; `pronto` em 97 s, `proprio: true`, `gerar: null`, `src` assinada do bucket `rpg-shared-art` | passou |
| 4 | Linha em `app.creature_portraits`: `scope=unico`, `status=ready`, `visibility=game`, `store=shared`, `origin_game_id`=jogo A, `pool_entry_id` nulo; chave de bucket = hash12 da chave (`622f6cc91493`), sem game_id | passou |
| 5 | `PostgresPortraitRegistry.get_many([chave], game_id=A)` devolve 1 linha; com `game_id=B` devolve 0 (banco real do staging) | passou |
| 6 | B lê o estado do jogo de A (`GET /game/state?game_id=A`): 404, sem corpo de retrato | passou |
| 7 | Estado de B depois da geração: inalterado (marcador, oferta `tipo`, `src` nulo) | passou |
| 8 | Débito: 8 milli (reserva 15 milli, pico 15, saldo 311 -> 303), 1 reserva; cotação 15 | passou (8 <= 15) |
| 9 | Mesma criatura (mesmo nome/espécie) aparecendo em B | não verificado ao vivo: B nunca recebeu o Urso-Titã. A chave de B levaria o game_id de B, então é distinta por construção (itens 4 e 5 provam o filtro) |

## Custo

- 1 retrato pago (teto 2). Débito do jogador: 8 milli (cotação 15 milli). O custo do provedor de imagem em US$ não é medido pelo app; fica muito abaixo do teto de US$ 0,30 para uma geração.
- 3 execuções do driver: as duas primeiras pararam antes de pagar (timeout transitório do pool admin no crédito da carteira; nenhuma região ofereceu `unico` sem nomear o chefe). Só a 3ª gerou.

## Kill switch e limpeza

- `image_generation`: `on`/`off` por execução (3 ciclos, ator `coordenador-claude`); `off` no `finally`. Confirmado com `list`: `image_generation=false`, `stt_fallback_expensive=false`. Último evento do `audit`: `enabled=false` às 19:54:34 UTC.
- Contas A e B apagadas: `user_exists=false` nas duas (em todas as execuções). Jogos apagados.
- Sobra: a linha `unico:` e os 2 objetos em `rpg-shared-art` ficaram, porque o driver apagou o jogo por SQL (o `DELETE /game/save/{id}` do hosted exige `Idempotency-Key` UUID; o driver não mandou e recebeu 400). Retirado com `scripts.retire_creature_portrait` (`--dry-run` mostrou 2 objetos; aplicado: `objects_deleted=2, failed=[]`). A linha ficou `status=retired`, com o jogo de origem inexistente.

## Achados

1. A ressalva "chefe `unico` entre contas" fecha ao vivo: isolamento por jogo comprovado no banco real e na API (itens 4 a 7). O que não foi exercitado é a mesma criatura nos dois jogos (item 9).
2. Para abrir um chefe no nível 1 basta nomeá-lo na primeira ação ("Procuro o Urso-Titã e o ataco de frente", Skallgard). Sem nomear, 5 regiões deram só `tipo`.
3. Não exercitado: R14 da SPEC-352 (purga da linha `game` e dos objetos ao apagar o jogo pelo caminho da API). Um próximo smoke que apague o jogo com `Idempotency-Key` fecharia isso. Apagar o jogo por SQL deixa linha e objetos órfãos (esperado, é caminho de operador).
4. O `crédito` de carteira pelo `PostgresWallet(open_ops_pool)` pode estourar `PoolTimeout` (pool admin de tamanho 1) numa primeira tentativa; um retry com pool novo resolveu (afeta só drivers de smoke).
