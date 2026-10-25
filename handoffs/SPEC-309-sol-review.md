# SPEC-309 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus 5.5 / Sol (subagente independente) · **Data:** 2026-10-24 · **Commit revisado:** `d0ff8aa1`

## Escopo

Branch `spec-309` (`a68abb89..d0ff8aa1`, diff contra a `main`, que já tem a SPEC-308).
Revisei `services/context_builder.py` (templates e `_IMPACT_BY_TYPE`), o novo
`services/perceived_world.py`, `services/world_perception.hidden_blocked_route_events`,
`agents/{archivist,storyteller,combat,npc,world_simulator}.py`, os registros de log e os
5 arquivos `tests/test_spec309_*`. Fora do escopo: smoke real (§6, fica com o coordenador)
e suíte completa.

Oráculo da 308 estendido aos templates novos e ao bloco em
`scratchpad/r309/oracle309.py`, com 4 cenários:
1. `<MUNDO_PERCEBIDO>` nas 4 audiências, com cerco não percebido em Brekmar, fome percebida
   e `companion_fate` não percebido;
2. crise aberta percebida em outro local da região, com fim não percebido;
3. morte off-screen de companheiro seguida de `quest_failed` pessoal;
4. dígitos nos templates com payloads reais.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `agents/archivist.py:196-213` (introduzido por `services/context_builder.py` R1, `quest_failed`) | **Vazamento novo da regra de ouro pela memória.** Quando o companheiro tem destino off-screen (SPEC-304), `companion_soul._fail_personal_quest` emite `quest_failed` com `source="system"` e `personal_of`. Esse evento não é "do motor", então `event_perceived` devolve `True`. O pack o esconde via `npc_world.event_hidden_from_player` (`fate_hidden`), mas `_event_memory_records` só aplica `event_perceived`. Antes da 309 o template era `""` e nada era gravado. Agora o arquivista grava `canonical_event` (confiança `confirmed`) "[turno N] Missão fracassada: A Promessa de Zedrik." enquanto o companheiro ainda aparece como fantasma na party. O RAG devolve isso ao narrador. Reproduzido no oráculo (cenário 3): `hidden_from_player=True`, pack sem o texto, registro de memória com o texto. Afeta o staging, que está com tudo `on`. | Em `_event_memory_records`, pular também `npc_world.event_hidden_from_player(state, event)`, o mesmo portão que `collect_dynamic_facts` já usa em `context_builder.py:433`. Acrescentar um teste em `test_spec309_golden_rule.py` com `RPG_NPC_WORLD=on`, `npc_sim.npcs[cid].fate_event_id` não conhecido e `quest_failed` com `personal_of`: o registro não pode aparecer. O fato não volta mais tarde quando o herói perceber (o arquivista só vê eventos novos). Isso é aceitável, porque o marco da crônica e a `npc_fate_learned` cobrem; registrar na §8. |
| P2-1 | P2 | `agents/storyteller.py:979-983` | F2: a nota diz "a rota estava BLOQUEADA… descobre ao tentar passar", mas a viagem é concluída e o herói chega ao destino. A LLM pode narrar uma travessia impossível ou um desvio inventado. **Sondagem:** não vi exploração barata. Só a aresta efetivamente percorrida (`a`↔`dest`) é descoberta, e isso custa tempo real de viagem (`travel_periods > 0`) e o deslocamento do herói. O id gravado no livro-razão é o do `route_blocked` (sem `cause_event_id`, chave própria em `event_perceived`). Por isso a crise/cerco associados **não** são revelados: `route_blocked` fica fora de `_ENGINE_TYPES` do bloco. Também não houve cadeia no oráculo. | Trocar o texto para algo coerente com a chegada, por exemplo "a estrada estava cortada/patrulhada e o comércio por ela parado; ele passou com dificuldade". Alternativa: registrar na spec que a recusa de viagem é decisão de produto separada. |
| P2-2 | P2 | `agents/storyteller.py:924-933` | Em `travel_periods == 0` (entrar em interior), `discovered_routes` é calculado e gravado no livro-razão sem nota ao narrador. Hoje é inalcançável (par cidade↔interior nunca é rota bloqueada), mas é discreto demais. | Calcular só quando `travel_periods > 0`, ou zerar `discovered_routes` no ramo `ENTROU`. |
| P2-3 | P2 | `agents/archivist.py:729-737` | R10 "nunca sobrevive": o retorno antecipado de conflito duplicado (`duplicate_conflict and not canonical_only and not new_rejections and not narrative_rejections and not new_events`) devolve sem gravar nem limpar `memory_canonical_facts`. Não duplica nada (o ledger não muda), só atrasa os fatos do dia para o próximo arquivista, com outro `source_turn`. É raro. | Incluir `and not policy_facts` na condição do atalho. |
| P2-4 | P2 | `specs/SPEC-309…md` §3.2 × §3.6.4 | `MODE_LABELS["fine"] = "multa paga"`, mas o oráculo §3.6.4 proíbe a palavra `multa` em "linha nova". O código segue a §3.2 e o `law_resolved` não entra no bloco, então os testes passam. Mesmo assim a spec se contradiz. | Ajustar o texto da §3.6.4 para restringir a proibição ao **bloco** `<MUNDO_PERCEBIDO>` e a valores (quantias). Outra opção é trocar o rótulo por "pendência quitada". |
| P2-5 | P2 | `tests/test_spec309_templates.py:150` | R21 pede "teste com um save fixture pré-302". Só há `test_legacy_payload_does_not_raise`, com payload vazio por tipo. Não há teste de `load_game_state` + `perceived_world_block` + `build_context_pack` sobre um save antigo. | Adicionar um teste curto que carrega um save sem `world_sim`/`memory_canonical_facts` e roda o bloco e o pack sem exceção. |
| P2-6 | P2 | `tests/test_spec309_prompts.py:179` | O teste de R22 compara o storyteller com e sem cerco no mesmo código, não contra o baseline. Revisando o código, não há `get_llm`/`with_structured_output` novo: `archive_due` só é ligado em viagem/descanso, que já ligavam (`storyteller.py:1950-1951`), e o `narrate_day` continua com 1 chamada. Na prática R22 está atendido; só o teste é fraco. | Opcional: fixar a contagem esperada (número absoluto) para viagem com dia virado. |

**Pontos conferidos sem achado:**
- **Regra de ouro no bloco.** Oráculo: 0 ocorrência de Brekmar/"sitiad"/Zedrik nas 4 audiências; a fome percebida aparece em story/combat/day; npc mostra só o local e a estação. O fim de crise não percebido mantém "Pelo que o herói soube, Fortaleza de Vorr está sitiada." (sem vazamento por ausência); o fim percebido some. O bloco não lê `world_sim.crises`. Os modos `shadow`/`off` cortam as linhas 1–3. O "Brekmar" que aparece no pack vem das arestas estáticas e públicas do lore (`controls`/`located_in`), não do motor.
- **Templates.** Sem dígito fora de `[turno N]` em cerco, fim de estado, aviso de guerra com fação, crime com heat/bounty e law_resolved. Fação nunca é nomeada. Chave desconhecida vira `""`. O texto de crime é neutro (D2). `unique_item_claimed` com outro holder vira `""`.
- **Memória do dia (D1).** Só o texto de `world_perception.render` entra; a prosa da LLM fica fora. `_DIGEST_MEMORY_TYPES` evita duplicar com o evento. A limpeza de R10 vale nos dois retornos de sucesso. Em `both_paths_failed` a allowlist é mantida, o que está certo porque o ledger não foi gravado.
- **Orçamento.** `MAX_LINES=4`, `MAX_TOKENS=120` via `estimate_tokens`, corte do fim (menor prioridade). Bloco vazio vira `""`.
- **Determinismo e guards.** Nada de `random`/LLM/RAG em `perceived_world`. Erro vira `""` + `log_fallback`, e os eventos foram registrados em `observability/events.py` e `EVENT_DE_LOG`. O `narrate_day` mantém o guard `isinstance` e o guard de nomes. Nenhum segredo vai a log. `evals/` não foi tocado. Nenhum campo novo no `GameState`: `memory_canonical_facts` já tinha round-trip em `persistence.py`.

## Correções aplicadas

Aplicadas P1-1 (`event_hidden_from_player` em `_event_memory_records`; o fato não volta depois, coberto por crônica e `npc_fate_learned`), P2-1/P2-2 (nota da rota coerente com a chegada; sem descoberta em interior), P2-3 (`not policy_facts` no atalho), P2-4 (spec §3.6.4), P2-5 (teste de save antigo). P2-6 fica como follow-up.

## Pendências

- P1-1 obrigatório antes do pouso.
- P2-1..P2-6: o coordenador decide entre corrigir no mesmo ciclo ou abrir follow-up. P2-1 e P2-3 são triviais.
- Smoke real §6, com o coordenador.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_spec309_*.py tests/test_spec308_*.py tests/test_context*.py tests/test_archivist*.py tests/test_ambient*.py tests/test_fase28.py tests/test_npc_knowledge.py → 205 passed, 3 skipped, exit 0 (5,1 s)
bash scripts/dev/py.sh scratchpad/r309/oracle309.py → bloco OK nas 4 audiências; fim não percebido mantém a linha; P1-1 reproduzido (quest_failed pessoal vira memória com fate oculto)
bash scripts/dev/py.sh scratchpad/r309/pack.py → "Brekmar" no pack só em arestas estáticas de lore; nenhum "sitiad"
```
