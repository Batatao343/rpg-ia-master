# SPEC-302 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (re-revisão do delta `e8772e4d..20cdc4c5`; veredito inicial era `CHANGES_REQUIRED` por P1-1, agora corrigido)
> **Revisor:** Claude Opus 5.5 / papel Sol (concorrência/estado) · **Data:** 2026-10-23 · **Commit revisado:** `e8772e4d` (1ª passada) → `20cdc4c5` (final)

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

| F-1 | P2 | `world_utils.py:665` (`decay_danger_overrides`), chamado agora por `agents/storyteller.py:556-561` | **Introduzido pela correção do P2-1.** No modo `on`, `decay_danger_overrides` calcula `cur = _effective_danger(world, loc_id)` com o default `with_state=True`. Isso grava o `danger_delta` do estado de local **dentro** do override, e o delta acaba contado duas vezes. Reproduzido: base 1, override 2 carimbado, delta de estado +2 → o override **sobe** para 3 em vez de descer. Só afeta save antigo com override carimbado num local que esteja em crise. O efeito é limitado (clamp 4) e desfaz-se depois que a crise acaba, a −1 a cada 10 turnos. | Trocar por `_effective_danger(world, loc_id, with_state=False)` dentro de `decay_danger_overrides` (uma linha) e adicionar um teste com `location_danger_delta`. Pode entrar antes do pouso sem nova revisão. |
| F-2 | P2 | `data/world/pressures.json:32` (`brekmar` 2,5) | A C1 de `brekmar` fica no limite e depende do conjunto de seeds: **15 com 60 seeds e 16 com 20 seeds** (fora de [10, 15]). O peso 2,5 não fecha a meta com folga, só a deixa no limite. A frequência por região continua sã (região máx. 27,5 % ≤ 35 %; C3/C5 = 100 %). | Aceitável pela D4. Registrar na spec que C1 de `brekmar` = 15–16 conforme o conjunto de seeds. Se o playtest real mostrar `brekmar` "parado", subir para ~3,0 ou reduzir `REGION_COOLDOWN_DAYS` só lá (calibração na 302-B/D). |

## Correções aplicadas

Commit `20cdc4c5` (`tests/test_spec302_review_fixes.py`, 7 testes):

- **P1-1 corrigido.** `validate_proposal` rejeita `faction_relation_changed` com `neutral`/`allied_with` quando `source != "engine"`. O validador lê `payload.relation` ou `detail`, então a burla pelo `detail` também fica fechada. Há teste parametrizado.
- **P2-1 corrigido**, mas a correção introduziu o F-1 (acima).
- **P2-2 corrigido.** `blocked_routes` só sai quando uma das pontas é local visitado ou atual. O ajuste de `test_fase61::test_world_block_expoe_blocked_routes` **preserva a intenção** do teste original: a rota ainda é exposta quando o herói conhece a ponta (agora com `visited: [BREKMAR]`). O teste ganhou o caso negativo (sem ponta conhecida, lista vazia), o que reforça o contrato em vez de enfraquecê-lo. Ressalva aceitável: o cerco de um local visitado mas distante aparece no mapa mesmo sem percepção. É conhecimento geográfico do herói, não pressão.
- **P2-3 corrigido.** O sim é reinicializado quando `day_before - last_ticked_day > MAX_DAYS_PER_ACTION`. Conferi que só a viagem e o descanso avançam o relógio (`advance_clock` em `world_utils`), e a fuga do combate usa `apply_travel`. Por isso o reset só dispara depois de um período longo com o motor desligado, nunca no jogo normal.
- **P2-4 corrigido.** `ophidia`/`costa_negra` passaram para 1,0. A §8.1 e o README agora usam 60 seeds. Ver F-2 sobre `brekmar` 2,5.
- **P2-5 corrigido.** O prompt agora é `[SystemMessage(instruções), HumanMessage(fatos)]`.
- **P2-6** fica com o coordenador no `/spec-land` (env do staging).

## Pendências

- F-1: correção de uma linha, recomendada antes do pouso (sem re-revisão).
- F-2: anotar na spec a sensibilidade da C1 de `brekmar` ao conjunto de seeds e recalibrar em spec filha se o playtest pedir.
- P2-6: setar `RPG_WORLD_ENGINE=shadow` no staging antes do deploy (D5).
- Smoke real §6 continua pendente (critério de aceite aberto).

## Comandos rodados

```text
# 1ª passada (e8772e4d)
pytest tests/test_spec302_*.py tests/test_ambient*.py tests/test_fase2.py tests/test_grounding_boundaries.py -n 4 → 145 passed
pytest tests -k "world or faction or economy or storyteller" -n 4 → 150 passed
py.sh docs/spec302/world_engine_sim.py --days 120 --seeds 20 → C4 média 35,4 % / p90 41,7 % / pior 52,5 %
py.sh docs/spec302/world_engine_sim.py --days 120 --seeds 60 → C1 10/15/10/11; C4 36,1 % / 50,8 % / 62,5 %; região máx. 27,5 %
script ad hoc PYTHONHASHSEED=1,2,3 → hash idêntico 84289e748f76227f (determinismo entre processos)
script ad hoc → validate_proposal(relation=neutral|allied_with, sem source) = ok=True (P1-1)
# re-revisão (20cdc4c5)
pytest tests/test_spec302_*.py tests/test_fase61.py tests/test_ambient*.py tests/test_fase2.py tests/test_grounding_boundaries.py tests/test_bug_mundo_perigo_luz_clima.py -n 4 → 178 passed
py.sh docs/spec302/world_engine_sim.py --days 120 --seeds 60 → C1 10/15/10/11,5; C4 34,5 % / 47,5 % / 62,5 %; região máx. 27,5 %; C3/C5 ok; 0 inválidos
py.sh docs/spec302/world_engine_sim.py --days 120 --seeds 20 → C1 brekmar = 16 (fora de [10,15]); C4 33,4 % / 41,7 % / 51,7 %
script ad hoc (decay em modo on com location_danger_delta) → override 2 → 3 (F-1)
```
