# SPEC — Remediação do playtest real de 100 turnos

> **Status:** `done`
> **Criada:** 2026-08-12 · **Atualizada:** 2026-08-12
> **Depende de:** `hardening-playtest-watchdog`, `perfil-jogador-normal-invariantes`, `fase-3.3-quest-log`
> **Desbloqueia:** novo playtest longo real com validade de comportamento e prazo auditável

---

## 1. Contexto & Objetivo

O run real `20260812-215427-501557` concluiu 100 turnos, mas expôs cinco
problemas: um resultado foi aceito depois de 2.256 s apesar do teto de 120 s; o
perfil `normal` copiou instruções privadas de beats; nenhum pedido social virou
quest; combate ocupou 45% da sessão; e loot alternou da segunda para a terceira
pessoa.

Esta spec corrige o harness e o perfil sem alterar dificuldade, regras de
combate ou autoria do mundo. Mecânica, classificação e métricas permanecem em
Python; LLM continua apenas propondo quests e narrando resultados.

## 2. Requisitos

- **R1 — Prazo absoluto:** `_run_with_watchdog` deve rejeitar resultado entregue
  depois do deadline, mesmo se o processo ficou suspenso enquanto worker e
  supervisor aguardavam. O erro deve expor fase, teto e tempo observado.
- **R2 — Aborto íntegro:** resultado tardio nunca inicia outro turno nem é salvo
  como sucesso; campanha registra `timeout:` e encerra de modo auditável.
- **R3 — Visão pública:** `normal` não pode ler `campaign_plan`, copiar beat nem
  produzir ações com metalinguagem (`Descreva`, `beat`, `campaign_plan`). Deve
  agir a partir de world/player/combat/NPCs/quests e texto já narrado.
- **R4 — Conversão observável:** o perfil deve pedir tarefa concreta a NPC em
  cena; JSONL e summary devem medir pedidos explícitos, criações no mesmo turno e
  taxa de conversão. MockLLM deve exercitar a proposta via `NPCResponse`, sempre
  passando pelo `quest_log` Python.
- **R5 — Viés de combate:** `normal` mantém cobertura de combate, mas aplica
  cooldown de doze ações não-combate depois de participar de um conflito. A
  telemetria agrega percentual de turnos de combate e emite warning de campanha
  acima de 35% em runs `normal` com pelo menos 50 turnos.
- **R6 — Voz do loot:** toda referência ao protagonista como `O jogador`,
  `O personagem` ou `O herói` na prosa de loot deve ser normalizada para `Você`
  em Python, sem alterar blocos `[SISTEMA]`.
- **R7 — Oráculos:** metalinguagem privada é violação `error`; dois ou mais
  pedidos explícitos sem nenhuma quest criada em campanha longa geram warning.

### Fora de escopo

- Saldo MiniMax, chave Qwen, ordem/remoção de candidatos em `ROUTES` ou qualquer
  outra configuração de fallback real — responsabilidade operacional do usuário.
- Balancear dano, encontros, inimigos, descanso ou dificuldade do mundo.
- Criar quest deterministicamente sem proposta válida do LLM.
- Alterar frontend, saves ou schema persistente de `GameState`.

## 3. Design técnico

- `playtest/runner.py`: deadline híbrido `monotonic + wall clock`; novos campos
  `quest_requested`, `quests_before`, `quests_after`; oráculos agregados ao fim.
- `playtest/profiles.py`: `Normal` sem `campaign_plan`, pedido concreto a NPC e
  cooldown pós-combate.
- `playtest/telemetry.py`: campos por turno e bloco `experience_balance` no
  summary.
- `playtest/invariants.py`: detecção contextual de metalinguagem privada.
- `mock_llm.py`: `NPCResponse.proposed_quests` somente diante de pedido explícito.
- `services/prose_guard.py` + `agents/loot.py`: normalização de pessoa narrativa.
- `tests/test_playtest_watchdog.py`, `tests/test_perfil_normal_invariantes.py` e
  teste focado de loot cobrem as regressões.

Não há alteração de `GameState`; os novos campos existem apenas em telemetria.

## 4. Plano passo a passo

### Etapa 1 — prazo forte

1. **Testes:** simular resultado imediato com relógio de parede avançado além do
   deadline; provar `PlaytestTimeoutError` e metadados observados.
2. **Implementação:** verificar deadline também depois de retirar resultado da
   fila, usando o maior elapsed entre relógio monotônico e parede.
3. **Verificação:** testes do watchdog verdes.

### Etapa 2 — perfil público, quests e combate

1. **Testes:** beat sentinela não aparece na ação; NPC recebe pedido concreto;
   MockLLM propõe quest; cooldown impede provocação precoce; telemetria calcula
   conversão/percentual e warnings.
2. **Implementação:** ajustar `Normal`, record/summary e oráculos.
3. **Verificação:** playtest mock de 50 turnos cobre quatro rotas, cria quest e
   respeita o teto comportamental.

### Etapa 3 — voz do loot

1. **Testes:** três formas em terceira pessoa viram `Você`; `[SISTEMA]` permanece
   byte a byte.
2. **Implementação:** helper puro no prose guard aplicado à saída do loot.
3. **Verificação:** testes de loot/economia verdes.

### Etapa 4 — aceite

1. Rodar testes focados, smoke mock e `uv run pytest` completo.
2. Rodar smoke LLM real curto do perfil `normal`, sem MockLLM.
3. Atualizar spec, `ESTADO_ATUAL.md` e `ROADMAP.md`.

## 5. Critérios de aceite

- [x] Resultado posterior ao deadline vira timeout, mesmo após salto do relógio.
- [x] Perfil normal não lê/copia `campaign_plan`.
- [x] Pedido de tarefa e conversão em quest aparecem no JSONL/summary.
- [x] Run normal longo alerta combate >35% e zero conversão após ≥2 pedidos.
- [x] Loot usa segunda pessoa sem modificar `[SISTEMA]`.
- [x] Smoke mock de 50 turnos verde, quatro rotas e pelo menos uma quest.
- [x] Smoke LLM real curto executado com `mock=false`.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Nenhum `with_structured_output` novo; guards existentes preservados.
- [x] Saves antigos continuam carregando; `GameState` não muda.

## 6. Smoke test com LLM real

1. Executar `normal` por 16 turnos, `--real`, com orçamento e timeout explícitos.
2. Confirmar `mock=false`, nenhuma ação contendo metalinguagem de beat e texto de
   loot sem `O jogador/O personagem/O herói`.
3. Inspecionar `experience_balance`, quests e qualquer timeout; falha de saldo ou
   chave de candidato secundário não é defeito desta spec.

## 7. Riscos & compatibilidade

- Relógio civil pode avançar por sincronização; usar o maior elapsed privilegia
  fail-closed do harness. O jogo de produção não usa esse watchdog.
- O cooldown reduz conflito provocado pelo perfil, não encontros sistêmicos.
- NPC pode legitimamente recusar uma tarefa; por isso zero conversão é warning de
  campanha após repetição, não criação forçada nem erro por turno.
- Telemetria antiga segue legível porque consumidores usam defaults.

## 8. Evidências de conclusão

- Mock `20260812-232004-255178`: 50/50, quatro rotas, quatro quests criadas
  (três concluídas), dois pedidos explícitos com 100% de conversão, zero erro e
  zero violação `error`. O warning de 46% de combate permaneceu corretamente:
  dois encontros foram sistêmicos e a spec não mascara dificuldade do mundo.
- Real `20260812-232052-855221`: 16/16, `mock=false`, 54 sucessos de rede
  incluindo startup, zero falha/violação, uma quest criada, combate 31,2%, três
  turnos de loot sem terceira pessoa, nenhuma ação com metalinguagem e custo
  US$ 0,014.
- Qualidade: Ruff verde e `uv run pytest` = **1446 passed, 1 skipped,
  14 deselected**.
