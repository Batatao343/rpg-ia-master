# SPEC — Protocolo atômico de transições críticas e checkpoints estáveis

> **Status:** `done` ? aceite local e smoke real DeepSeek verdes em 2026-09-28.
> **Criada:** 2026-08-27 · **Atualizada:** 2026-09-17
> **Origem:** matriz B interrompida `20260827-141144-990850`, turnos 174–200
> **Depende de:** `contrato-canonico-ciclo-vida-acoes`, `checkpoints-morte`
> **Supera:** correção defensiva baseada somente em `action_guard`

## 1. Contexto & Objetivo

A primeira correção centralizou a elegibilidade de uma nova ação, mas deixou a
transição anterior escapar incompleta. Na B1, uma fuga terminou o combate com
`last_stand_pending=True`; o guard então bloqueou 26 ações de descanso sem que
existisse um produtor capaz de concluir a Última Ação. O plano narrativo também
ficou ancorado na região anterior, mas isso foi consequência, não causa.

Esta spec muda o ponto de controle: produtores de combate, viagem, morte e
restore devem entregar somente um estado interturno estável. Checkpoints e
commits recusam estados transitórios. O guard continua como contenção para save
legado/corrupção, com reparo determinístico explícito em vez de loop textual.

## 2. Requisitos

- **R1 — Fases estáveis vs transitórias:** `active`, `unconscious` e `dead` são
  fases interturno; `last_stand_pending`, `estado_terminal`, `death_pending` e
  combate em resolução são transições que têm um único dono e não podem ser
  gravadas como checkpoint jogável.
- **R2 — Decisão de fuga única e tipada:** elegibilidade, tentativa de perseguição
  e resultado usam um DTO fechado. O limite de tentativas só força sucesso após
  uma perseguição elegível; nunca transforma `blocked_lifecycle` em fuga.
- **R3 — Fechamento no produtor:** antes de encerrar combate ou aplicar viagem de
  fuga, o motor resolve toda Última Ação/Estado Terminal pendente. Se não puder,
  mantém o combate/transição ativa e não muda o local.
- **R4 — Commit-ready:** função pura `transition_readiness(state)` retorna
  `ready`, fase e códigos fechados. Finalizer, checkpoint e persistência de
  recibo usam o mesmo contrato.
- **R5 — Checkpoint seguro:** `should_checkpoint`, `snapshot` e `maybe_write`
  recusam qualquer transição crítica, não somente `combat.active` e
  `death_pending`.
- **R6 — Restore migration-safe:** restore limpa flags efêmeras incompatíveis de
  checkpoints antigos, reavalia consciência a partir do snapshot estável e
  nunca devolve `last_stand_pending` sem seu resolvedor.
- **R7 — Ordem no harness:** checkpoint só é atualizado depois de confirmar que
  não houve queda/morte/transição pendente; a escolha “continuar” nunca restaura
  o próprio estado derrotado.
- **R8 — Guard de contenção:** estado legado transitório fora de seu dono recebe
  um único outcome `transition_repair_required`; mensagens repetidas não contam
  como turnos e não mascaram progresso. Recuperação normal continua possível.
- **R9 — Replan após restore/fuga:** mudança canônica de local ou epoch marca
  `needs_replan`; plano incompatível não persiste depois do primeiro turno
  jogável.
- **R10 — Observabilidade:** invariantes distinguem causa raiz
  (`transition.unresolved_at_boundary`, `checkpoint.unstable`) dos sintomas de
  região/prosa e emitem um episódio, não um erro por turno bloqueado.

### Fora de escopo

Rebalancear perseguição, mudar dano climático ou remover a escolha de checkpoint.

## 3. Design técnico

- `services/actor_lifecycle.py`: `TransitionReadiness`,
  `transition_readiness`, `sanitize_interturn_state` e códigos fechados.
- `agents/combat.py`: `FleeDecision`/resultado causal; enforcement recebe apenas
  chase elegível; fechamento de lifecycle ocorre antes de `_apply_flee_travel`.
- `services/checkpoints.py`: allowlist de snapshot estável e sanitização completa
  de slots legados.
- `agents/turn_finalizer.py`: assert/receipt de boundary estável; estados de morte
  aguardando escolha são resposta terminal válida, mas não checkpoint jogável.
- `playtest/runner.py`: morte/restore antecede qualquer refresh do checkpoint.

## 4. Plano TDD

1. Reproduzir exatamente: nove tentativas de fuga, Última Ação pendente e destino
   válido; o cap não força viagem e a transição é resolvida.
2. Provar que checkpoint recusa `last_stand_pending`, terminal, dead transitório e
   combate ativo; restore legado remove cada combinação incompatível.
3. Rodar 30 ações de descanso sobre a reprodução B1: zero soft-lock, no máximo um
   diagnóstico e plano/local coerentes.
4. Cobrir morte→continue, fuga válida comum e Vitalidade zero consciente.

## 5. Critérios de aceite

### Adendo aprovado — 19/09

O contrato local inclui recuperação pelo grafo, recibo estável e save/load,
com asserts independentes de local, relógio e consciência. Não basta testar o
guard isolado. Plano/gates no
[adendo pré-matriz](SPEC-162-remediacao-local-contratos-pre-matriz.md).

- [x] Nenhum produtor encerra turno jogável com transição sem dono.
- [x] Limite de fuga não sobrepõe bloqueio de lifecycle.
- [x] Checkpoint/restore não perpetua flags efêmeras.
- [x] Reprodução curta B1 não perpetua bloqueio após a fronteira.
- [x] Região e plano são marcados para convergir após restore/fuga.
- [x] Invariantes reportam a transição órfã na fronteira, antes da cascata.
- [x] Suíte completa offline verde após a revisão de 17/09 (1681 passed).
- [x] Smoke real dirigido de transição/restore sem regressão; B integral é gate global separado.

### Revisão local de 17/09

`FleeDecision` é um `NamedTuple` que preserva desempacotamento legado e expõe
elegibilidade causal. O guard repara uma transição órfã fora de combate uma vez,
sem avançar tempo/local; a próxima ação de recuperação volta a ser possível.
O finalizer aplica `transition_readiness` e inclui a decisão no recibo; combate
ativo e escolha de morte são fronteiras válidas, mas não checkpoints jogáveis.
Regressões curtas em `tests/test_transicoes_criticas_b1.py` passaram. O gate real
continua bloqueado pelo HTTP 402 DeepSeek; ver o
[fechamento local](../docs/fechamento-local-2026-09-17.md).

## 6. Smoke real

Usar estado preparado de fuga/queda/restore e executar ações dirigidas. Confirmar zero
`transition.unresolved_at_boundary`, zero cauda de guard e zero checkpoint
instável.
O par 1 de 200 turnos pertence à matriz global; não executar campanha duplicada
como pré-requisito desta spec.

## 7. Riscos

Fechar uma transição no lugar errado pode pular a Última Ação. Por isso o motor
preserva o dono e a ordem; sanitização automática existe apenas no restore de
snapshot legado, nunca no meio de um combate vivo.


## Fechamento real ? 2026-09-28

M?ltiplos player_downed reais restauraram checkpoint e retomaram sem transition.unresolved_at_boundary ou cauda de guard.
Evid?ncia consolidada: [matriz B](../docs/playtest-matriz-b-2026-09-28.md), `20260927-214549-731406` e `20260928-084057-102826`. A matriz global incompleta permanece responsabilidade exclusiva da SPEC-128.
