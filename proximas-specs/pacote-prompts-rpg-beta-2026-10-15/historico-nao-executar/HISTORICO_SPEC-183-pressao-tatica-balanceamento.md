# SPEC-183 — Pressão tática, respostas inimigas e variedade de ações

> **Status:** `draft` · **Criada:** 2026-10-12 · **Prioridade:** P1  
> **Depende de:** SPEC-179 e SPEC-180 `done` · **Escopo:** motor determinístico e balanceamento aferido por simulação dirigida.

## 1. Contexto & objetivo

A vitória obtida repetindo Golpe do Convite e sem sofrer dano pode ser um encontro trivial, problema de AI inimiga, apresentação pobre de riscos ou bug na resolução. Não presumir qual sem logs. Tornar decisões táticas significativas sem fabricar dano ou punir automaticamente um jogador competente.

## 2. Requisitos

- **R1:** telemetria deterministicamente calcula por encontro: dano causado/sofrido, ataques tentados/acertados, turno até vitória, variedade de ações, energia consumida/recuperada, manobras efetivas, reações disparadas, oponentes ativos por round, dificuldade e margem de vitória.
- **R2:** cenários de teste incluem 1v1 básico, grupo misto (bandido/corvo), inimigo de longo alcance, alvo com cobertura, inimigos que flanqueiam/engajam, reação defensiva e fuga. Para cada um, confrontar logs do motor com HP/ferimentos/status reais.
- **R3:** motor aplica ataques inimigos/reação/dano quando mecanicamente devidos; zero dano é resultado admissível de esquiva/sorte/controle, mas toda sequência de ataques inimigos deve ter causa e rastreabilidade.
- **R4:** repetição da mesma ação não deve ser proibida artificialmente; criar situações onde alvo, distância, guarda, reação, custo, frequência e ameaça de múltiplos inimigos tornem outra ação situacionalmente superior.
- **R5:** não mexer em dados de cards, IA tática ou dificuldade sem reproduzir problema e mostrar ganho em métricas mantendo invariantes de morte/loot/eventos/XP. Nenhum target escolhido depois de ver resultado.

## 3. Design técnico

Mapear primeiro `services/conflict_orchestrator.py`, `services/tactical_profile.py`, `services/conflict_damage.py`, `services/conflict_turn.py`, `playtest/invariants.py`, `tests/test_conflito_tatica.py`, `tests/test_conflito_dano.py`, `tests/test_balance_early.py`. Reutilizar simulador `web/src/components/CombatSimulatorScreen.tsx` para UX de decisão e não atribuir a LLM o cálculo de dano. Avaliar custo real `Entropia` e efeitos da carta, não a aparência de seu nome.

## 4. Etapas (testes primeiro)

1. Executar baseline local curta e reproduzir zero-dano/spam com seed fixa, registrando logs de decisão inimiga e regra de acerto.
2. Localizar problema (dados, IA, resolução, composição do encontro ou apenas visibilidade) e escrever teste known-bad.
3. Alterar um subsistema coerente; comparar seed pareada contra baseline e regressões de classes.
4. Testar visualização do feedback em combate real e reporte humano do motivo das escolhas.

## 5. Aceite

- [ ] Ataques de inimigos e ausência de dano possuem trilha mecânica verificável.
- [ ] Cenários táticos com distância/cobertura e múltiplos inimigos mostram escolhas com impactos diferentes sem depender de prosa.
- [ ] Nenhuma morte, XP, loot, status ou evento duplicado/revertido.
- [ ] Regressões do motor e do simulador verdes; resultado de baseline/candidato publicado sem ajustar dataset/evaluator.

## 6. Riscos

Não exigir que o jogador sempre sofra dano ou que todas as lutas exijam múltiplas cartas. O objetivo é coerência, agência e dificuldade graduada, com vitórias fáceis possíveis quando a ficção e as regras justificarem.
