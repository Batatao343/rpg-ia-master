# Longrun real pós-remediação — 2026-08-16

## Escopo

- Run: `20260816-100206-334105`
- Perfil/seed: `normal` / `46`
- Extensão: 200/200 ações com `--real`, invariantes habilitadas
- Providers: DeepSeek primário; Groq em dois fallbacks de structured output
- Limites: 120 s por fase, 900 requests, US$ 0,30
- Resultado formal: `failed` por uma invariante `error`; zero exceções, zero
  timeout e artefatos estruturalmente válidos

## Resultado executivo

| Métrica | Resultado |
|---|---:|
| Turnos | 200/200 |
| Erros de execução/observabilidade | 0 / 0 |
| Violações error/warning | 1 / 1 |
| LLM sucessos/falhas | 489 / 2 |
| Custo | US$ 0,137760 |
| Latência p50/p95 | 9,365 s / 20,109 s |
| Combate | 90 turnos (45%) |
| Conflitos start/end/replay | 12 / 11 / 0 |
| Mortes/epochs | 2 / 2 |
| Quests criada/progredida/concluída | 1 / 1 / 0 |
| Memória final | 117 inference/speculative; autoridade 0% |

O 12º conflito começou no turno 199 e ainda estava ativo no encerramento, por
isso 12 starts/11 ends não é inconsistência de lifecycle.

## Correções confirmadas

1. **Checkpoint P0 corrigido.** As mortes nas ações 61 e 87 restauraram turnos
   canônicos diferentes, avançaram para epochs 1 e 2 e retomaram com
   `combat.active=false`. Nenhum conflito foi repetido (`replayed_starts=0`).
2. **Origem por cena melhorou.** Foram sete `player_provoked` e cinco
   `regional_danger`; descansos interrompidos apareceram como perigo regional.
3. **Três relógios íntegros.** O final separa `session_action=200`, turno
   canônico 163 e `timeline_epoch=2`; `deaths=downed_count=2` após rollback.
4. **Latência melhorou.** O p95 geral caiu de 35,3 s no baseline útil anterior
   para 20,1 s. Início de combate teve p50 11,258 s e p95/máximo 19,858 s; a
   continuação teve p95 6,670 s. Não houve timeout em 36,5 minutos de parede.
5. **Fallback real funcionou.** Dois structured outputs DeepSeek inválidos
   caíram para Groq; não houve MockLLM/fallback determinístico.
6. **Quest não conclui prematuramente.** O ledger chegou a `created →
   location_reached → investigation`; combate e repetição não inventaram avanço.

## Achados

### P1 — claim persistido no índice NPC não chega ao ledger global

Nos turnos 131 e 142, `add_npc_memory` confirmou dois writes Jina com
`provenance=npc_claim`. Mesmo assim, `memory_by_provenance` permaneceu apenas
`inference` e o save final terminou 117/117 speculative.

Causa observada: `npc_actor` grava diretamente no índice privado quando o write
funciona e só preenche `pending_npc_memory` na falha. O espelhamento implementado
no archivist cobre o retry da fila, não o sucesso direto. O summary comprova dois
writes `npc_claim`, mas nenhum claim no ledger.

### P1 — fuga progride, mas invariante acusa softlock e ritmo é excessivo

No conflito iniciado no turno 151, o jogador tentou fugir onze vezes seguidas.
O chase variou entre `afastado`, `pressionado`, `alcançado` e `quase_livre`, até
`escapou` no turno 165. A invariante `combat.no_progress` disparou no turno 159
porque seu fingerprint não inclui `combat.chase`/`resolved_action.chase_track`.

Há duas ações distintas: corrigir o falso positivo da invariante e revisar o
ritmo/probabilidade ou a política após muitas tentativas de fuga.

### P1 — quest criada com atraso de um turno não é retomada pelo perfil

O pedido explícito ocorreu no turno 131 e a quest apareceu no 132. O funil mede
conversão apenas no mesmo turno, portanto reportou 0%, embora tenha havido
conversão em D+1. O perfil fez uma investigação válida no alvo, saiu, voltou em
combate e partiu novamente; não priorizou a segunda investigação, deixando a
quest ativa ao fim dos 200 turnos.

### P1 — descanso pós-fuga reabriu combate como provocação

Após escapar no turno 24, a ação `Descanso: monto acampamento...` do turno 25
foi roteada diretamente a `combat_agent`, abriu/encerrou uma nova instância no
mesmo turno e registrou `player_provoked`. A ação não foi provocação. É uma
reprodução residual envolvendo estado pós-fuga/roteamento, não herança global de
todas as origens.

### P2 — participação de combate voltou a 45%

O perfil normal passou 90/200 turnos em combate, acima do warning de 35%. Foram
12 conflitos; a perseguição de 15 rounds respondeu por parte relevante do excesso.

## Priorização sugerida

1. Espelhar também o sucesso direto de `npc_actor` no ledger global.
2. Incluir chase no fingerprint e limitar a repetição da política de fuga.
3. Fazer o perfil normal retornar ao alvo de quest ativa e medir conversão em
   uma janela de turnos, não apenas no mesmo turno.
4. Limpar/explicar estado pós-fuga antes do próximo roteamento de descanso.
5. Reavaliar frequência/duração de combate depois das correções acima.

## Remediação executada no mesmo dia

Os cinco pontos foram convertidos em specs independentes e concluídos:

- [memoria-npc-sucesso-ledger](../specs/SPEC-114-memoria-npc-sucesso-ledger.md);
- [chase-progresso-e-fuga](../specs/SPEC-100-chase-progresso-e-fuga.md);
- [quests-retomada-conversao](../specs/SPEC-119-quests-retomada-conversao.md);
- [pos-fuga-roteamento-origem](../specs/SPEC-118-pos-fuga-roteamento-origem.md);
- [ritmo-combate-normal-v2](../specs/SPEC-121-ritmo-combate-normal-v2.md).

O ator NPC agora espelha no ledger o mesmo record aceito pelo write privado. O
chase participa do fingerprint e encerra na sexta tentativa consecutiva com
destino adjacente válido. A fuga saneia inimigos/target/chase/instance/origem,
preservando apenas o recibo auditável do turno. O perfil normal navega até a
quest e investiga duas vezes; runner e summary compartilham a janela D+0..D+3.
O cooldown passou a 20 ações, com fuga desde round 3 e descanso seguro.

### Aceite pós-correção

| Métrica | Antes real | Depois mock 200t |
|---|---:|---:|
| Erros / violações | 0 / 1 error + 1 warning | 0 / 0 |
| Combate | 90/200 (45%) | 41/200 (20,5%) |
| Conflitos start/end | 12/11 | 7/7 |
| Pedido→quest | 0% medido | 4/4 (100%) |
| Quests concluídas/recompensadas | 0/0 | 15/15 |
| Claims NPC no ledger/writes | 0/2 | 9/9 |
| Rotas cobertas | 4 | 4 |

Run de aceite: `20260816-113051-596798`, 200/200, zero violação. Smoke real
dirigido confirmou ataque → `combat_agent/player_provoked`, investigação e
descanso → `storyteller`; uma conversa real escreveu +1 fato Jina e devolveu
`npc_claim/reported` com fila vazia. A tentativa adicional de campanha real
`20260816-113124-829110` não passou do startup após structured SMART inválido e
foi encerrada manualmente; por isso não entra nas métricas de aceite.

Gate final: **1480 passed, 1 skipped, 14 deselected**; Ruff verde nos arquivos
tocados.
