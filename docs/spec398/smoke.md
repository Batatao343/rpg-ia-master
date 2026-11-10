# SPEC-398 R6 — smoke no staging (10/11/2026)

Staging `d7aa4beb` (398 + 399 + 401). Antes do smoke: `post_deploy_smoke` (sha certo, `hardened`), `vercel_smoke` (verde na 2ª tentativa: o 1º `/health` não respondeu, transitório) e `e2e_session` verdes. Cartas `on`, `RPG_FAUNA_SABER` `off`, `image_generation` `off` fora da purga. Contas sintéticas; jogos e contas apagados no fim (`users_exist_after: false` em todas).

Driver: [`smoke_r6.py`](smoke_r6.py) (corrige o laço do diagnóstico da 369):
- escolhe alvo só de `valid_targets`;
- diante de `409 invalid_target` (evento SSE `error`), tira a jogada de `play_index` e reenvia;
- para depois de 3 recusas na mesma rodada.

## Resultado

| Item | Resultado | Evidência |
|---|---|---|
| Laço do 409 (diagnóstico 369) | **ok.** 3 execuções, 0 recusas `invalid_target`. | `smoke-presagio-run1.json`, `smoke-presagio-run3.json` (`refusals_409: 0`) |
| R1 ao vivo (reação/passiva na mão) | **ok.** Nenhuma reação ou passiva saiu jogável ou sem `not_playable_from_hand`. | idem (`hand_contract_violations`) |
| Item 4 da 369 (2º conflito, mesma família) | **ok, com ressalva.** Execução 3, conflito 5 (combate novo depois da vitória do 4, mesmo arquétipo `cervo_afogado`): rodada 3 com faixa [3, 6]; com `bas_med_guarda` jogada, o `mech_log` registra "Cervo Afogado → Você · acerto · Proteção −2 · Torpor −25 % · 0 dano", abaixo do piso 3. Execução 1: faixa [4, 8], "Golpe pelas Costas … acerto · Proteção −2 · Torpor −25 % · 1 dano", abaixo do piso 4. | `smoke-presagio-run3-resumo.txt`, `smoke-presagio-run1.json` |
| Purga do retrato `unico` (SPEC-352 R14) | **ok.** Urso-Titã (Skallgard) gerado até `ready`; `DELETE /game/save/{id}` com `Idempotency-Key` → 200; 0 linhas `unico:<jogo>:` e 0 linha em `app.games` depois. Kill switch `image_generation` `on` só durante a geração, `off` no fim (`list` final: `false`). | `smoke-purga.json` |

## Ressalvas

- **Faixa na abertura do 2º conflito (por design, decisão do coordenador por delegação do dono, 10/11).** No perfil hosted a faixa não aparece na abertura do 2º conflito contra o mesmo arquétipo: o overlay do bestiário entre encontros só é lido e gravado no perfil `legacy` (`agents/combat.py:762-784`, SPEC-272, fail-closed porque o escopo não era por dono/jogo), e `RPG_FAUNA_SABER` está `off` no staging. A faixa aparece da rodada 2 em diante, quando o motor já revelou a Carta no próprio conflito. O item 4 da 369 que mostrou faixa já na abertura foi local (`legacy`). Follow-up (spec futura): levar o overlay entre encontros ao perfil hosted / ligar `RPG_FAUNA_SABER` no staging após smoke.
- **Conflitos 1→2 e 3→4 da execução 3 são o mesmo combate.** A fuga do driver falhou (`fled: false`), então o "conflito 2" e o "4" continuaram o combate anterior; só o 5 é um encontro novo. A evidência do item 4 usa o 5.
- **Checagem do driver mais estrita que o contrato.** Uma vez (execução 3, conflito 1, rodada 4) o driver marcou `bas_med_golpe` `jogavel: true`, alvo inimigo, `valid_targets: []`. A R2 pede o motivo no item, não `jogavel: false`, e para Carta `ativa` sem alvo o motor sempre devolve `invalid_reason` (`services/combat_targeting.py:170-172`); o driver não guardou o campo, então a vista exata não ficou registrada. Nenhum 409 nessa rodada.
- **Retrato órfão de 07/11 limpo.** Uma linha `unico` `retired` do smoke de 07/11 sobrou porque aquele driver apagou o jogo por SQL (o `DELETE` sem `Idempotency-Key` deu 400) e pulou a purga. Foi removida com `purge_game_portraits`; 0 linhas `unico` no staging depois.

## Custo

Uso de LLM dentro do cap diário (R$ 5, D-363-2), sem corte. 1 geração de imagem (purga).
