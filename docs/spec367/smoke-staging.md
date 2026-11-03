# Smoke staging: SPEC-367 §6.1/§6.4/§6.5 e SPEC-368 §6 item 11 (LLM real)

Feito em 03/11/2026, das 19:10 às 21:37 UTC, pelo coordenador.

**Staging.** `hosted-supabase`, `/health` com `git_sha` `9e5f43d9` (367 + 368 na `main`). Deploy com o preset
`scripts/staging/staging_flags.json` (cartas `on`). Migrations 34/34 em sincronia. Os 3 smokes pós-deploy
(`post_deploy_smoke`, `vercel_smoke`, `e2e_session`) passaram.

**Contas.** Contas sintéticas pelo caminho de `two_user_smoke` (`User` + `credit_verified_purchase` sintético).
Todas foram apagadas no fim (`users_exist_after: [false, false]`), e os jogos também.

**Turnos.** 4 aberturas de combate com LLM real, de 12,3 a 13,7 s cada, com 4 chamadas `llm:turn` por abertura.
Houve 2 gerações de retrato pagas (8 milli cada).

**Evidência.** Fica no scratchpad da sessão do coordenador, em `smoke6stg/`:
- `stg/stg_log_run1.jsonl` e `stg/stg_log.jsonl`
- `stg/done-offer.txt`
- `out/*.png`
- `probe/`
- `stg/ks_*.txt`
- `retire_*.txt`

## Tabela

| Item | Resultado | Evidência |
|---|---|---|
| 367 §6.1 `list` 3× (R18/R19) | **ok**. 3 execuções com saída 0, 0 `PoolTimeout` e nenhum retry necessário | `ks_list_{1,2,3}.txt` |
| 367 §6.1 `art_preflight` 3× | **ok** quanto ao pool: 0 `PoolTimeout`. Saída 1 com `causa: manual_off`, porque `image_generation` estava desligado de propósito | `preflight_{1,2,3}.txt` |
| 367 §6.1 retirada do retrato de fallback (A4) | **ok, depois de uma correção**. `--env-file .env.staging` sozinho não monta o runtime hosted fora da Vercel: caía no `FileGameStore` e não apagava nada. A correção é `--dsn-env RPG_STAGING_DB_URL` (`848a63cb`, `b278f6af`). A chave real é `tipo:gen:criatura-hostil`, não `tipo:fallback_criatura_hostil`. O dry-run mostrou `ready` com 2 objetos; a retirada deu `status: retired`, `objects_deleted: 2`, `objects_failed: []` | `retire_dry.txt`, `retire_apply.txt`, nota no §9 da 367 |
| 367 R10 (sem oferta para `fallback_*`) | **ok**. Nas 4 aberturas, `fallback_criatura_hostil_1` veio com `gerar: null`, inclusive ao lado de inimigos com oferta | `fallback_seen` nos logs |
| 367 §6.4 R4 (chip troca na hora para "Gerando retrato…") | **achado S6-3**. 400 ms depois do clique em "Gerar" a 1440, o chip ainda mostrava "Gerar retrato (até 0,015 Estilhas)" e aceitava clique (`aria-disabled`, não `disabled`). Só depois da resposta do `/art/confirm` virou `gerando`. O pendente é aplicado só depois do confirm (`App.tsx` `confirmImageQuote`), não no clique | `done-offer.txt` (`1440-logo-apos-gerar`), `out/stg-1440-c-gerando.png` |
| 367 R5 (2º clique não gera 2ª cotação) | **ok**: `/art/quote` foi chamado 1 vez, `/art/confirm` 1 vez | `1440-quote-calls: 1` |
| 367 R4 a 390 (estado `gerando` visível no celular) | **ok**. Recarregada a 390 depois da confirmação, a tela mostra o retrato `gerando` | `390-depois` |
| 367 §6.5 / R25 (varredura de `/game/history`) | **ok** nas 3 campanhas do staging: 0 nome do herói, 0 ids, 0 ": … terminou" cru | `history` nos logs |
| 368 item 11: "Agora não" | **ok**. Depois de "Agora não" a 390, houve 0 requisições `/art/*` e a oferta voltou | `390-agora-nao.art_requests_after_no: 0` |
| 368 item 11: duas confirmações concorrentes com `action_id` distintos | **ok**: a 1ª deu 200 `pending`, a 2ª 409 `operation_in_progress`. Um único débito de 8 milli (teto 15, liberados 7), reserva `settled` e reserva aberta 0 | `concurrent_confirms`, `portrait_ready` (B) |
| 368 item 11: débito = custo liquidado ≤ cotação (D-364-1) | **ok** nas 2 gerações: 8 ≤ 15 milli, pico reservado 15, 0 reservado no fim | `portrait_ready` (A e B) |
| 368 item 11: `image_generation` ligado só durante o item | **ok**. Ligado e desligado 3 vezes (run 1, sonda, run 2). `list` no fim: `"image_generation": false` | `ks_on*.txt`, `ks_off*.txt` |
| 368 item 11: importar imagem pelo script; chefe `unico:{game}` isolado entre duas contas | **não verificado ao vivo**. Nenhum chefe apareceu nas aberturas. Cobertos por teste (`test_spec352_*`) | — |

## Achados

- **S6-1 (P1): Carta de Cena aparece com o id cru e custo 0 no staging.** A mão a 1440 mostrou
  `CENA_POCO_NEGRA_04930…` com custo 0 (`out/stg-1440-a-chip.png`).
  - Causa: a Carta temporária de objeto só existe no catálogo em memória do processo
    (`services/cards.py` `_TEMP_CARDS`, registrado em `scene_cards.sync_hand`). Na Vercel, o `/game/state`
    seguinte pode cair em outra instância, que não tem o registro.
  - A validação da jogada (`cards.py:564`, `card_id in _TEMP_CARDS`) também depende do mesmo processo, então a
    jogada provavelmente é recusada numa instância fria.
  - Correção pedida: reconstruir as Cartas de objeto a partir da cena (estado salvo) na view e na validação, e
    não depender do cache do processo.
- **S6-2 (P2): a oferta de retrato some de forma intermitente.** Na mesma partida, 5 carregamentos seguidos
  (1440, 390, 1440, 1280, 1440) mostraram a oferta só no 1º e no 5º. Em 4 leituras do `/game/state` pelo cliente
  Python ela sempre estava lá.
  - Não depende da largura da tela: varia por instância.
  - Causas prováveis no código: `_portrait_price_estilhas` guarda `None` por 60 s quando o `peek_ceiling` falha
    (cache de falha); `_portrait_registry` devolve `None` em `registry_read_failed`.
  - As duas falhas apagam a oferta sem retry. Pedir: não guardar falha em cache (ou TTL curto), 1 retry de
    checkout, e medir `creature_portrait.price_peek_failed`/`registry_read_failed`.
- **S6-3 (P2): o chip não troca para "Gerando retrato…" no clique (R4 da 367 não atendido ao vivo).** Pedir:
  marcar o pendente de forma otimista no clique em "Gerar" (e desfazer no erro), com o botão `disabled` de verdade.
- **S6-4 (P3): "Criatura hostil" de fallback em 3 das 4 aberturas** (Pântano da Melancolia e Floresta dos
  Sussurros, com `RPG_CREATURE_GEN` off). O nome genérico aparece demais para um caminho de fallback. Investigar por
  que o spawn cai no fallback nessas regiões.
