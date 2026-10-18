# SPEC-217 J1 — diagnóstico dos erros conhecidos do Jev (R2)

Sem chamada live. Fontes: `docs/spec178/README.md`, `docs/spec179/README.md`,
`docs/spec180/README.md`, `evals/experiments/jev_router_ab.py` (SPEC-178),
`evals/experiments/jev_target_loot.py` (SPEC-179), `services/jev_rollout.py`.

**Raws:** `evals/runs/jev-router-ab/` e `evals/runs/jev-target-loot/` **não existem**
localmente (nem neste worktree nem no checkout principal; são gitignored e não
foram preservados). Conforme a R2, o diagnóstico usa os relatórios e o payload/
Choice efetivamente enviados (reconstruídos do código dos runners, que é
determinístico). Escolhas exatas do Jev nos casos `alias`/`enemy` da SPEC-179 não
são recuperáveis — só o fato de que A acertou e B errou.

## Erros e causas prováveis

| # | Erro observado | Payload/Choice enviado | Causa provável [H] | Resposta na estrutura J1 |
|---|---|---|---|---|
| D1 | SPEC-178 `FALO COM CORVO` → `combat_agent` 2/3 réplicas (conf. 0,30/0,27) | `state={action:"FALO COM CORVO", location_id, in_combat:false}` (sem `active_npc`), Choice de 5 opções | (a) sem lista de cena o Jev não sabe que "Corvo" é um NPC presente — "corvo" em pt-BR é também um animal; (b) texto em caixa alta lido como grito/agressão; (c) argmax usado mesmo com distribuição quase uniforme (0,27 ≈ 1/5 + ruído) | `scene` com `npc_corvo_rapido` (nome/apelidos), `action` normalizada em minúsculas, flag `verbs=["talk"]`, abstenção por `τ` (conf < τ ⇒ CLASSIFY), guarda de combate (combate só com verbo de ataque ou combate ativo) |
| D2 | Rótulos inconsistentes | `instructions` falam em `COMBAT/NPC/LOOT/STORY`; chaves são `combat_agent/npc_actor/loot/storyteller/none` | o modelo precisa mapear dois vocabulários; descrições de uma linha sem contra-exemplos | label sets `plain` (descrições coerentes com as chaves) e `rich` (com exemplos e contra-exemplos **não** tirados do DEV) |
| D3 | SPEC-179 `target.alias` (“Falo com o Corvo Cinzento”) — A acerta, Jev erra | Choice de alvo `{npc_corvo_rapido: "NPC presente: Corvo", unknown, none}`; apelidos **não** aparecem na opção nem no estado | o alias só existia no estado do jogo, não no DTO nem no rótulo | rótulo da opção inclui apelidos (`NPC Corvo; apelidos: Corvo Cinzento`) e `scene[].aliases` no estado |
| D4 | SPEC-179 `target.enemy` (“Ataco o guarda”) — A acerta, Jev erra | Choice de alvo isolada, sem rota nem `verbs`, opções `enemy_guarda`/`unknown`/`none` | alvo pedido sem contexto de intenção; `unknown` e `none` são duas abstenções quase sinônimas que dividem massa de probabilidade | rota e alvo na mesma requisição (dois estágios lógicos, uma chamada), `verbs=["attack"]`, uma só abstenção (`none`) |
| D5 | SPEC-179 `target.over20` / `target.missing_id` | não enviados ao Jev | não representáveis por desenho (>20 opções sem truncar; ator sem ID canônico) | mantidos não representáveis ⇒ CLASSIFY (sem truncar) |
| D6 | SPEC-180 `NO_GO`: só 2/16 elegíveis cabem no contrato `primary` | `primary` só aceita `storyteller`/`none` | rotas com alvo (`npc_actor`, `combat_agent`) não tinham estágio de alvo | estágio de alvo restrito aos candidatos de cena torna NPC/combate representáveis; `loot` continua fallback (o `loot_context` pelo Jev está fora de escopo) |

## Achados adicionais do payload

- `jev_router_ab._arm_b` envia `location_id` como `current_location` (nome) e o
  runner da SPEC-179 como `current_location_id`: o campo não é informativo para a
  rota e fica como está.
- Não há "último interlocutor" no DTO além de `active_npc` (nome livre). J1 envia
  `last_speaker` como **ID** de um ator da cena, resolvido em Python.
- Nenhum sinal de verbo era extraído em Python; J1 usa um léxico fechado
  (`talk/attack/trade/craft/take/move/observe/rest`) sobre texto sem acento; o
  ataque reaproveita o mesmo léxico de hostilidade explícita do router
  (`agents/router.py::_EXPLICIT_HOSTILITY_RE`) com dois verbos a mais.

## Fronteira (R12)

As features novas do `DecisionState` (`scene`, `last_speaker`, `verbs`) são
opcionais, limitadas (≤ 20 atores, ≤ 4 apelidos de ≤ 64 chars, ID no formato
identificador) e derivadas em Python do estado público com o **mesmo filtro da
SPEC-179** (`_target_options`: fora de cena, morto, oculto, `secret`, `known_by_player=false`
e ator sem ID canônico ficam fora). Unset ⇒ fora do fio; o payload do rollout de
produção (SPEC-180) não muda (teste `test_production_rollout_payload_is_unchanged`).
