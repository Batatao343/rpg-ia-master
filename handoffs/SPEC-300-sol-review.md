# SPEC-300 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (spec-reviewer, papel Sol) · **Data:** 2026-10-24 · **Commit revisado:** `9c3d7288`

## Escopo

Branch `spec-300` (`git diff main...HEAD`, 40 arquivos, +4.233/−72), commit
`9c3d7288` sobre `0d70e1ea` (spec aprovada). Lido em detalhe: `services/companion_soul.py`
(writer único `apply_turn`, deriva de valores, aviso/partida/traição, missão pessoal, romance,
interfaces R26/R27), `services/companion_tags.py`, `services/companion_prompt.py`, os trechos
de `agents/turn_finalizer.py`, `agents/storyteller.py`, `agents/npc.py`, `api.py`,
`persistence.py`, `state.py`, `party.py`, `services/quest_log.py`,
`services/world_validators.py`, `services/structured_outputs.py`, `services/chronicle.py`,
`services/turn_outcome.py`, `playtest/invariants.py`, os dados `data/companion_*.json` e o
diff do `web/`. Ficou de fora: a revisão linha a linha das 134 linhas de vetores de
`data/companion_values.json` (D1 aceito como default) e a regeneração de
`data/graph/entities.json` (o campo `hook` vem de `scripts/gen_world_living_npcs.py`).
O smoke real da §6 não foi rodado (não há chave neste ambiente); continua pendente na spec.

## Verificação dos focos pedidos

1. **Writer único e determinismo.** Só `apply_turn` escreve `companion_souls`. Ele é chamado
   uma vez no `turn_finalizer`, depois do archivist e da reputação, com `{**state, **updates}`,
   dentro de `try/except` com `log_fallback`. É puro sobre cópias (`deepcopy`/`dict`). Valores,
   deltas, rótulos e o desempate (RNG com semente `(game_id, turn, "companion_voice")`) são
   determinísticos. Os ids de evento usam `uuid4`, como o `_build_event` atual.
   Save/load: `_state_to_save_data` grava e `_raw_to_state` usa `{}` como padrão; o round-trip
   e o save antigo estão testados (`test_spec300_persistence_api.py`). Os campos transitórios
   (`companion_voice_ack`, `companion_feedback`) não são persistidos. Não houve bump de schema.
   Com a flag `off`, o finalizer nem chama o writer, o bloco do prompt volta `""` e a API omite
   rótulo e feedback, o que preserva o comportamento atual byte a byte (testado).
2. **Regra de ouro e ausência de números.** Deltas, descanso, romance e missão valem só para
   `present_ids & in_party_ids` (`active_allies`), e o bloco do prompt também usa
   `active_allies`. A API expõe só `approval_label`/`bond_label` e as frases do turno, sem
   número (há um teste que varre o payload). Os rótulos são hostil/desconfiado/neutro/
   amistoso/leal, alinhados ao `NpcTier` da SPEC-298, e a frase negativa reusa
   `reputation.npc_notice_text`.
3. **Zero chamada LLM extra.** Nenhum `get_llm`/`invoke`/`with_structured_output` novo
   (teste de contagem). O bloco tem teto de 600 por companheiro e 1.200 no total via `_clip`
   + `_wrap`, e a regra de romance nunca é cortada. O ack só é gravado no caminho feliz:
   `isinstance(update, StoryUpdate)` no storyteller e o ramo de sucesso no npc_actor.
4. **Traição por traço.** `deliver` vence `steal`, e os blockers são respeitados. O roubo é
   `min(int(gold·0,25), 60)`, só fora de combate e só depois do turno de despedida (narrado ou
   expirado em 3 turnos). `deliver` só deixa `deliver_pending` e
   `pending_betrayal_deliveries`. Desvio 7: ajustar `last_turn_outcome.gold_delta` depois do
   recibo é coerente com o que o jogador vê, porque a despedida foi narrada nesse mesmo turno
   e o feedback diz "traiu a sua confiança". Restam efeitos colaterais menores (P2-2).
5. **Romance.** Fica atrás de `RPG_COMPANION_ROMANCE`. Com `off`, o estágio não avança, a
   intenção recebe recusa gentil e não entra regra de romance no prompt. O texto de
   fade-to-black é fixo e não há instrução explícita. Os traços de luto (`luto_recente`,
   `viuva_do_mar`, `marcado_pela_praga`) bloqueiam até a missão ser concluída.
6. **Eventos só do motor.** `companion_left`/`companion_betrayed`/`companion_fate` são
   rejeitados em `validate_proposal` quando `source != "engine"`. O `source` é do wrapper
   Python, já que `ProposedWorldEvent` não tem esse campo. O alvo precisa ter alma. No
   `apply_event` esses tipos não fazem nada.
7. **Desvio 6 (`quest_log`).** O filtro `not q.get("personal_of")` só afeta missões pessoais.
   Quests comuns não carregam o campo e seguem o caminho antigo, e os testes de quest
   passaram. Uma proposta de `quest_completed` da LLM para `pq_*` agora falha em
   `has_completion_proof`, que é o comportamento desejado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | services/companion_soul.py:622 | O reencontro aplica `min(40, aprovação+10)` a toda alma `departed`, inclusive `dismissed` (o jogador dispensou). Um companheiro "leal" (80) que foi dispensado e volta cai para 40, ou seja, "neutro". A R17 fala de quem "partiu"; a punição de quem foi dispensado não está decidida. | Aplicar o teto só a `departed == "left"`; para `dismissed`, manter a aprovação (ou registrar a decisão na spec). |
| P2-2 | P2 | services/companion_soul.py:872 | O ouro roubado ajusta `gold_delta` depois que o `receipt_id` foi calculado com o delta original; a quest pessoal concluída e os eventos `companion_*` também ficam fora de `quests_completed`/`event_ids` do recibo. Não quebra a contabilidade do saldo (o `player.gold` está certo e o baseline do próximo turno vê tudo), mas o recibo fica internamente incoerente com o próprio hash. | Ou recalcular `receipt_id`/`event_ids` quando `gold_taken`, ou documentar na spec que o hash cobre só o estado anterior ao writer. Teste: recibo pós-traição com `event_ids` contendo o `companion_betrayed`. |
| P2-3 | P2 | services/companion_soul.py:830 | `int(gold*0.25)` com ouro negativo dá um "roubo" negativo, e o jogador ganharia ouro. Hoje o ouro não fica negativo, mas falta o clamp defensivo. | `taken = max(0, min(...))`. |
| P2-4 | P2 | services/companion_soul.py:682 e :797-804 | Aviso e partida pendente rodam para todo `in_party_ids`, inclusive quem está em `waiting_at`. Se o dia vira, um companheiro ausente pode ficar `departure_pending` e sair pelo ramo `stale` (3 turnos) sem a despedida ter sido narrada, porque o bloco só cobre os presentes. O mesmo vale para turnos só de combate/loot, onde o bloco não entra. A R15 pede que "o jogador vê a despedida antes de a party mudar"; o `companion_feedback` mitiga, mas não é narração. | Executar a partida de quem está ausente só quando ele volta a estar presente (ou registrar na spec que o ramo `stale` é aceito, com feedback). |
| P2-5 | P2 | services/companion_soul.py:527 | `_rest_turn` olha só a regex da ação (`is_rest`). Descanso bloqueado pelo clima (`rest_block`) ou ação de descanso roteada para outro nó também contam em `rests_together`/`romance_rests`. | Reusar o sinal real do storyteller (relógio avançou por descanso) ou filtrar `rest_block`. |
| P2-6 | P2 | services/companion_soul.py:640 | Companheiro removido da party por morte em combate (e não marcado `dead` na party) vira `departed="dismissed"`, não `"dead"`. Isso não afeta a mecânica, mas a memória da relação fica com o motivo errado. | Conferir `npcs[...].alive`/`npc_killed` ao classificar a saída. |

Não há P0 nem P1. Também não encontrei segredo em log (os `log_event` carregam só o
nome do evento) nem mudança em `evals/`.

## Correções aplicadas

Nenhuma até aqui (o revisor só edita este arquivo).

## Pendências

- P2-1…P2-6: follow-ups do executor da SPEC-300 (podem entrar antes do pouso ou numa spec
  de ajuste). P2-4 é o mais próximo de afetar a experiência, então convém decidir antes de
  pôr `on` no staging.
- Smoke real §6 (DeepSeek, cenário `companheiro`, incluindo a leitura humana do
  fade-to-black no passo 5) segue obrigatório para `done`.
- Playtest `--all --turns 50` e perfil `combate` (M1/M5) não foram rodados nesta revisão;
  ficam com o coordenador no pouso.

## Comandos rodados

```text
git diff main...HEAD --stat → 40 arquivos, +4233/−72
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec300_*.py → todos passaram (106), exit 0
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 -rf tests -k "party or companion or npc or quest or finalizer" → exit 0, 0 falhas (alguns skipped)
```

Nota: uma primeira tentativa com `-n auto` derrubou um worker por falta de RAM ("node down").
Refeita com `-n 2`, ficou verde.
