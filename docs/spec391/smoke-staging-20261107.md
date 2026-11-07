# SPEC-391 §6 - smoke no staging (07/11/2026)

Staging `https://rpg-ia-master-staging.vercel.app`, `/health` com `git_sha` `83675bec`, `RPG_COMBAT_REINFORCEMENTS=on` (dono: "liga", 05/11). Conta sintetica propria (`generate_link` + `/auth/verify`, helpers de `scripts/staging/s192.py`), 1 jogo, apagados no fim (`games 1`, `user 200`, `exists False`). Nada da Vercel, flags ou contas alheias foi tocado.

**Cena natural (sem semeadura).** `/game/new` (Sangromante nivel 5, Nova Arcadia, jogo `b309a9d4-f919-4e37-9ab0-4df19193aa12`), uma acao de texto ("ataco o Soldado da Legiao de Ferro") abriu o combate (`origin: player_provoked`) com 1 `enemy_soldado_legiao_ferro_1` (`lider_matilha`, elite, 12 Vit.). Dai so `/game/action` com `action_kind` attack/pass. 5 chamadas no total.

## Rodadas

| Chamada | Rodada apos | Lider | `reinforcement` / `reinforcement_warning` |
|---|---|---|---|
| attack | 1 | 8/12 | ausente |
| attack | 2 | 0/12 (elite continua agindo) | `{stage: "telegraphed", leader_id, chega_na_rodada: null}` / ausente |
| pass | 3 | 0/12 | `{stage: "called", chega_na_rodada: 4}` / `true` |
| pass | 4 | 0/12 | ausente / ausente; chegou `capanga_do_bando_r1` (Vit. 10/10) |

## Telemetria (Vercel logs, `combat.*`, `via=carta`, uma vez cada, na ordem)

`19:46:36.305 reinforcements_telegraphed` -> `19:46:44.053 reinforcements_warned` -> `19:46:46.187 reinforcements_fired`. Linhas `turn` das 3 rodadas: `llm_calls=0`, `cost_usd=0`. Abertura (4 chamadas LLM): US$ 0,00197. Custo total estimado do smoke: **~US$ 0,002** mais o `/game/new` (sem linha `turn` no recorte). Bem abaixo do teto.

## Retrato do `_r1`: FALHA (esperado "do pool", veio `marcador`)

```
capanga_do_bando_r1.retrato = {estado: "marcador", src: null, familia: "bruto", icone: "combat",
  alt: "Retrato de Capanga do bando", proprio: false,
  gerar: {preco_estilhas: 1, escopo: "tipo", preco_milli: "15"}}      # resposta de /game/action
```

`GET /game/state` depois da chegada: mesmo `marcador`, `src: null` (e `gerar` ausente). O lider tem o mesmo `marcador` (`familia: lider_matilha`).

Causa (leitura de `services/creature_art.py::portrait_for` + consulta somente leitura ao registro): o caminho do `_r1` e o mesmo dos outros inimigos, mas nao ha arte para ele. O `_r1` generico (`capanga_do_bando`) resolve a chave `tipo:...` sem linha `ready` em `app.creature_portraits` (staging tem 6 linhas `tipo:*`, 5 `ready`, nenhuma de capanga/soldado), e nao existe arte curada da familia `bruto` (`creature_family`). Ou seja: a promessa do §6 "retrato do pool" so se cumpre quando o pool/catalogo tiver arte para `bruto`/`capanga_do_bando`.

## Achados

1. **Retrato do `_r1` nao e do pool** (acima). Opcoes: curar arte da familia `bruto` (e `lider_matilha`), ou aceitar `marcador` e reescrever o criterio do §6. Nao e bug de codigo do 391.
2. **Oferta de retrato no meio do conflito.** A resposta de `/game/action` traz `retrato.gerar` (oferta de 1 Estilha) para o `_r1` ja na rodada da chegada, e o telemetria registra `creature_portrait.offer_view`. A spec 391 (R sobre retrato) diz "nunca geracao nem oferta de retrato no meio do conflito". A oferta e da SPEC-389 e e identica para todo inimigo sem arte; decidir qual regra prevalece. (Nenhuma geracao foi disparada.)
3. P3 do smoke local (payload `called` em combate encerrado) nao foi reexercitado aqui.

## Nao verificado

Cancelamento por queda/fuga do lider no staging; UI (so API/payload/logs).
