# SPEC-302 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED` (1 P1, correção pequena; o resto é P2/follow-up)
> **Revisor:** Claude Opus 5.5 / papel Sol (concorrência/estado) · **Data:** 2026-10-23 · **Commit revisado:** `e8772e4d`

## Escopo

Branch `spec-302`, `main...HEAD` (43 arquivos, +5411/−70), rebaseada sobre a SPEC-296.
Lidos: `services/world_engine.py`, `world_director.py` (gating/ciclo), `world_pressures.py`
(rng/adjacência), `faction_relations.py` (ordem de iteração), `world_perception.py`,
`agents/storyteller.py` (diff inteiro), `agents/world_simulator.py` (narrador),
`services/world_validators.py`, `event_processor.py`, `economy.py`, `world_utils.py`,
`persistence.py`, `api.py::_world_block`, `state.py`, `npc_knowledge.py`, testes `test_spec302_*`.
Fora: o playtest de letalidade (R34) não foi re-executado; usei os números da §8.2.
`evals/` não foi tocado pelo diff.

## Avaliação por foco

1. **Determinismo e idempotência: OK.** Toda aleatoriedade vem de `day_rng` (sha256), e
   toda iteração que consome rng é `sorted(...)`. Rodei 30 ações × 3 dias em 3 processos com
   `PYTHONHASHSEED` 1/2/3: o hash de `world_sim` e dos eventos deu o mesmo nos três
   (`84289e748f76227f`, 43 eventos). Repetir a chamada dá 0 ticks porque
   `day_after <= last_ticked_day`. Com o mesmo pré-estado, o retry gera os mesmos
   `event_id`, porque `_build_event` aceita o id determinístico só com `source=="engine"`.
   O checkpoint (`services/checkpoints.snapshot`) faz deepcopy do estado inteiro, então
   `world_sim` volta junto com `event_log` e `last_event_seq` fica coerente. O round-trip
   save/load passa por `_state_to_save_data`/`_raw_to_state`, compartilhados com o hosted
   via `game_serialization`, e tem teste. `WorldSimState` está no `GameState`, então o
   LangGraph não descarta a chave. Medi `world_sim` em 35,7 KB (20 seeds) e 36,5 KB (60 seeds).
2. **Regra de ouro / API: OK, com uma ressalva (P2-2).** `perceivable` cobre só (a)
   testemunho local, (b) testemunho regional e (c) rumor via `location_heard` com a 215 `on`.
   `world.news` grava o texto do template, nunca o da LLM. `_world_block` filtra `news` por
   lista branca e só expõe o rótulo vago do local atual. O teste confirma que `pressures`,
   `world_sim`, `faction_relations` e `severity` não aparecem.
3. **LLM: OK.** São no máximo 1 chamada por ação (`_narrate_world`), só sem encontro e só
   com item percebido. Há guard `isinstance` + `try`, e a saída passa por sanitize, teto de
   600 caracteres e checagem de nomes do catálogo; se falhar, cai nos templates. Nenhum
   campo da LLM muda estado. `danger_shift` só existe no caminho `off`.
4. **Diretor: OK.** O aviso exige `day - warned_day >= MIN_WARNING_DAYS` em `_try_open`.
   O teto vale ativas + anunciadas `>= MAX_ACTIVE_CRISES` em `announce`, e
   `request_crisis_slot` é a porta única. C3 e C5 dão 100 % com 20 e com 60 seeds.
   **C4 é efeito esperado da D4, não bug de calibração.** Reproduzi a tabela com 20 seeds
   (média 35,4 %, p90 41,7 %, pior 52,5 %, região máx. 21,7 %). Com 60 seeds a cauda piora:
   **média 36,1 %, p90 50,8 %, pior 62,5 %, região máx. 27,5 %**, e C1 continua em
   10/15/10/11. A métrica "≥ 1 crise em qualquer lugar do mundo" soma 12 regiões. O jogador
   só percebe a própria região e as adjacentes, e por região o teto de 35 % se mantém. O que
   pesa na cauda são `ophidia` e `costa_negra` com `surge_weight` 1,6: são regiões remotas
   que não estão entre as 4 de C1 (ver P2-4). A §8.1 e o README devem registrar os números
   de 60 seeds, porque 20 seeds subestimam a cauda.
5. **Engine-only: OK para os 2 tipos novos.** `location_state_changed` e
   `world_crisis_warning` sem `source=="engine"` são rejeitados, e `ProposedWorldEvent` não
   tem campo `source`. **Porém** a spec ampliou o que a LLM pode propor em
   `faction_relation_changed` (P1-1).
6. **Default `on` em saves antigos: em geral suave.** A inicialização acontece no dia atual,
   sem simulação retroativa, com 5 dias de calma e o `last_event_seq` ancorado. Há duas
   ressalvas: P2-1 (decay de perigo legado congelado) e P2-3 (on→off→on).
7. **Letalidade:** os números da §8.2 (M1 0,505 ≤ 0,564; M2 43; M5 0) são consistentes
   com o desenho (`danger_delta` 0 em `seguro`, clamp [0, 4]). Não re-executei.
8. **Storyteller:** no `on` o pulso é suprimido e a narração diária só sai sem encontro.
   No `off` e no `shadow` ficam o pulso legado, `append_news` (SPEC-296) e
   `advance_factions` por período. `sim_updates` e os eventos do motor estão presentes nos
   três retornos (normal, encontro e exceção).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `data/graph/relation_types.json:4-5`; `services/world_validators.py:104-106`; `services/event_processor.py:190` | Adicionar `neutral` e `allied_with` a `relation_types.json` abre os dois valores para a **proposta da LLM**, porque `_v_faction_relation_changed` só confere se a relação existe no arquivo. Confirmado: `validate_proposal({type: faction_relation_changed, payload:{relation:"neutral"}})` devolve `ok=True`, e `apply_event` apaga a aresta dinâmica `enemy_of`. Efeitos: (a) o storyteller consegue "fazer as pazes" ou criar alianças só com prosa, contra a regra "mecânica é Python"; (b) a projection diverge de `world_sim.relation_bands`. Se o sim continua em `guerra`, não há novo cruzamento e o `enemy_of` nunca volta, mas `faction_war_presence` segue somando `guerra`. | Em `validate_proposal`, rejeitar `faction_relation_changed` com `relation ∈ {"neutral","allied_with"}` quando `source != "engine"`, na mesma barreira de `_ENGINE_ONLY_TYPES`. Adicionar um teste de proposta LLM rejeitada para os dois valores. |
| P2-1 | P2 | `agents/storyteller.py:883`; `agents/world_simulator.py:164-166` | `decay_danger_overrides` (SPEC-233 R2) só roda dentro de `apply_world_pulse`, que no modo `on` não é chamado. Em save antigo migrado para `on`, overrides carimbados em `danger_shift_turns` (+1/−1 de pulsos passados) **nunca decaem**. Jogo novo não é afetado. | No ramo `on` do storyteller (ou no fim de `advance_days`), chamar `decay_danger_overrides(world)`. Teste: save com `danger_shift_turns` antigo e modo `on` faz o override decair após 10 turnos. |
| P2-2 | P2 | `api.py:2829` | `blocked_routes` expõe **todas** as rotas bloqueadas da projection. Agora o motor bloqueia rota de cerco em qualquer região, então o mapa pode revelar um cerco remoto que o herói não viu nem ouviu (regra de ouro, R31 no espírito). | Filtrar rotas com ponta em local visitado/atual ou percebido (`world.news`/`location_heard`). Alternativa: aceitar como pré-existente e registrar como follow-up da 302-D. |
| P2-3 | P2 | `services/world_engine.py:173-175` | `on`→`off`→`on` (rollback e religamento) reaproveita um `world_sim` velho. `advance_days` simula até 10 dias de "catch-up" e retoma crises ativas antigas. R30 só cobre `shadow`→`on`. | Ao reativar, se `world_sim.last_ticked_day` estiver a mais de `MAX_DAYS_PER_ACTION` do dia atual, ou se o modo gravado divergir, reinicializar (R29). Ou documentar como aceito. |
| P2-4 | P2 | `data/world/pressures.json:31-35` | A cauda de C4 passa de 50 % no p90 com 60 seeds (50,8 %; pior 62,5 %). `ophidia` e `costa_negra` com `surge_weight` 1,6 inflam as crises globais sem ajudar C1 (exceto pela adjacência de `brekmar`). | Follow-up de calibração: testar 1,0 nessas duas regiões e confirmar que C1 de `brekmar` continua ≤ 15. Atualizar §8.1/README com os números de 60 seeds. Não bloqueia: a D4 do dono prioriza o ritmo. |
| P2-5 | P2 | `agents/world_simulator.py:256` | O narrador manda **só** `SystemMessage`. Gemini e Anthropic (fallbacks) recusam prompt sem mensagem humana. O `RoutedLLM` cai para o próximo candidato e por fim nos templates, então nada quebra, mas há latência e chamadas desperdiçadas no fallback. O padrão já existia no pulso legado. | Separar em `[SystemMessage(instruções), HumanMessage(fatos)]`. |
| P2-6 | P2 | §8.3 item 11 da spec | O default do código é `on`. Se o pouso acontecer sem `RPG_WORLD_ENGINE=shadow` no staging, o staging liga o motor antes do smoke §6, contra a D5. | No `/spec-land`, conferir ou setar a env no staging antes do deploy, e registrar no hand-back do coordenador. |

## Correções aplicadas

Nenhuma (só revisão).

## Pendências

- P1-1 precisa ser corrigido pelo executor antes do pouso. Re-revisão curta: só o validator e o teste novo.
- P2-1, P2-5 e P2-6: recomendados no mesmo ciclo (são poucas linhas cada).
- P2-2 e P2-3: follow-up aceitável (dono: coordenador; destino: 302-D ou spec de mapa).
- P2-4: calibração opcional, já que a D4 cobre. Atualizar os números da §8.1.
- Smoke real §6 continua pendente (critério de aceite aberto).

## Comandos rodados

```text
pytest tests/test_spec302_*.py tests/test_ambient*.py tests/test_fase2.py tests/test_grounding_boundaries.py -n 4 → 145 passed
pytest tests -k "world or faction or economy or storyteller" -n 4 → 150 passed
py.sh docs/spec302/world_engine_sim.py --days 120 --seeds 20 → reproduz a tabela (C4 média 35,4 % / p90 41,7 % / pior 52,5 %)
py.sh docs/spec302/world_engine_sim.py --days 120 --seeds 60 → C1 10/15/10/11; C4 média 36,1 % / p90 50,8 % / pior 62,5 %; região máx. 27,5 %; C3/C5 ok; 0 inválidos
script ad hoc (scratchpad det.py) com PYTHONHASHSEED=1,2,3 → hash idêntico 84289e748f76227f (determinismo entre processos)
script ad hoc (scratchpad v.py) → validate_proposal(faction_relation_changed, relation=neutral|allied_with, sem source) = ok=True (P1-1)
```
