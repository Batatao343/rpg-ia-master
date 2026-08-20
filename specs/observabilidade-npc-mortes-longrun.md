# SPEC — Precisão de NPC reciclado e histórico completo de mortes

> **Status:** `done`
> **Criada/Atualizada:** 2026-08-20
> **Origem:** matriz A, pares 1–2

## 1. Problema

Referências de memória como “o que Pérola disse em Brekmar” geraram 24 warnings
de NPC reciclado, embora o NPC não estivesse na cena. Em paralelo, o relatório
indicou 17 mortes no agregado do explorador, mas a tabela exibiu só a primeira.

## 2. Requisitos

- **R1:** `narrative.recycled_npc` exige uso mecânico atual: `active_npc_name` ou
  aliado transitório do combate fora da origem. Menção memorial não dispara.
- **R2:** uso remoto real continua warning; party/reintrodução legítima não.
- **R3:** summary mantém `deaths_log` completo e o Markdown lista cada morte com
  perfil, seed, turno, local e causa.
- **R4:** relatório distingue quantidade de mortes de quantidade de campanhas
  com morte.

## 3. Aceite

- [x] Menção memorial de NPC remoto não dispara; aliado remoto dispara.
- [x] Fixture com três mortes renderiza três linhas.
- [x] Suíte completa verde.
