# SPEC — Contrato canônico de ciclo de vida e elegibilidade de ações

> **Status:** `in-progress` — aceite local verde; smoke real dirigido pendente (B é gate global)
> **Criada/Atualizada:** 2026-08-27
> **Depende de:** `fix-vitalidade-ferimentos-terminal` (`done`)
> **Supera:** R1–R3 de `fuga-vitalidade-zero` (`done`, contrato incorreto)

## 1. Contexto & Objetivo

A matriz A encontrou oito ocorrências de Vitalidade zero fora de combate. A
invariante criada em `fuga-vitalidade-zero` chamou todo esse estado de inválido,
mas o domínio canônico afirma que Vitalidade zero, isoladamente, não é morte.
Os transcritos mostram o defeito verdadeiro: o pós-combate marcou o protagonista
inconsciente e, mesmo assim, o grafo aceitou viagem e outras ações normais.

Esta spec cria uma única política Python de fase de vida e elegibilidade. Morte,
terminal, consciência e incapacidade governam a ação; Vitalidade é recurso de
conflito, não um booleano de vida.

## 2. Requisitos

- **R1 — Fonte única:** `dead`, `death_pending`, `game_over`,
  `estado_terminal`, `last_stand_pending`, `conscious`, `incapacitated` e combate
  ativo determinam a fase. Vitalidade zero nunca equivale sozinha a morte.
- **R2 — Decisão tipada:** `evaluate_action(state, text)` retorna fase, `allowed`,
  código estável e mensagem segura.
- **R3 — Gate universal:** todo `app.invoke`, inclusive API, CLI, harness e teste
  direto, passa pelo gate antes de campaign manager/router.
- **R4 — Inconsciente fora de combate:** bloqueia viagem, social, loot e novo
  combate sem gastar turno nem chamar LLM. O estado não é mutado além da mensagem
  determinística e do resultado da interação.
- **R5 — Recuperação possível:** ator inconsciente não executa ação física, mas
  o jogador pode declarar passagem de tempo por descanso/tratamento/espera por
  socorro; o pipeline canônico resolve a recuperação. Não haverá soft-lock solo.
- **R6 — Fuga:** `can_attempt_flee` considera consciência/terminal/combat.active,
  não Vitalidade positiva. Uma ação ainda não resolvida a Vitalidade zero segue
  o fluxo canônico de Ferimentos.
- **R7 — Invariantes:** remover `player.zero_vitality_outside_terminal`; adicionar
  `player.lifecycle_incoherent` e `player.action_while_incapacitated`.
- **R8 — Compatibilidade:** saves sem flags novas assumem `conscious=True` quando
  não mortos/terminais; aliases HP continuam derivados.

### Fora de escopo

Rebalancear dano, mudar capacidades de Ferimentos ou redesenhar checkpoints.

## 3. Design técnico

- Novo `services/actor_lifecycle.py`: `ActorPhase(StrEnum)`,
  `ActionEligibility(TypedDict)`, `classify_actor(state)` e
  `evaluate_action(state, action)`; funções puras.
- Novo `agents/action_guard.py`: retorna somente update parcial. Aresta
  `START → action_guard → campaign_manager|END` em `main.py`.
- `state.py`: `last_action_outcome` opcional, persistido e exposto apenas como
  resultado estruturado seguro.
- `agents/combat.py`: fuga usa a política comum.
- `playtest/invariants.py`: coerência de fase e ação bloqueada substituem a
  inferência por Vitalidade.

## 4. Plano TDD

1. `tests/test_actor_lifecycle.py` reproduz Vitalidade 0 + consciente; Vitalidade
   0 + inconsciente; terminal; morte; fuga; ajuda/recuperação.
2. Teste de grafo prova que viagem inconsciente termina no guard, não incrementa
   relógio/turno e faz zero chamadas ao router/LLM.
3. Testes existentes de fuga são atualizados para o contrato canônico.
4. Implementar serviço, nó, fiação e invariantes; rodar suíte completa.

## 5. Critérios de aceite

### Adendo aprovado — 19/09

Recuperação usa uma gramática fechada de intenção, não a presença de “ajuda”.
Ações mistas são recusadas. Router e storyteller consomem a recuperação como
passagem de tempo/descanso no mesmo local, inclusive para incapacidade; clima
bloqueante mantém as restrições. O invariante verifica deslocamento por delta
de estado independentemente do `allowed` do guard. Regressões em
`tests/test_pre_matrix_contracts.py`; plano/gates no
[adendo pré-matriz](remediacao-local-contratos-pre-matriz.md).

- [x] Vitalidade zero consciente não é classificada como morte.
- [x] Inconsciente não viaja, conversa, saqueia nem inicia conflito.
- [x] Ação bloqueada não consome turno e não chama LLM.
- [x] Existe saída determinística de recuperação sem soft-lock.
- [x] Fuga não usa `vitalidade > 0` como gate.
- [x] Testes reproduzem os turnos 71–73 da matriz A em memória.
- [x] Suíte completa offline verde e saves antigos carregam.
- [ ] Smoke real dirigido confirma o fluxo de recuperação (§6); não exige B integral nesta spec.

## 6. Smoke real

Atualização de 17/09: validação local revisada com protocolo de reparo/recibo;
B integral bloqueada por HTTP 402 DeepSeek. Evidência histórica não certifica
o build atual; ver [fechamento local](../docs/fechamento-local-2026-09-17.md).

Na matriz B, nenhum turno deve registrar ação mecânica incompatível com a fase;
Vitalidade zero consciente pode existir sem falso positivo.
O smoke dirigido pode usar estados preparados e poucas ações: viagem bloqueada,
socorro no mesmo local, recuperação e reload. B integral permanece gate global
de `matriz-longrun-multiperfil-niveis`, não dependência de desenvolvimento.

## 7. Riscos

O maior risco é bloquear um fluxo legítimo de recuperação. Por isso a decisão é
tipada, testada por tabela e independente da linguagem livre do LLM.
