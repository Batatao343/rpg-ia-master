# SPEC — Playtest real LLM-only deve falhar fechado

> **Status:** `done`
> **Criada/Atualizada:** 2026-08-20
> **Origem:** matriz A1 interrompida `20260820-155300-494278`

## 1. Problema

O primeiro par A1 completou 200 turnos, mas 707 de 796 tentativas LLM falharam.
Em 146 turnos não houve nenhum sucesso de rede; os guards resilientes do produto
mantiveram o jogo rodando com respostas determinísticas. Isso é correto para o
jogador, mas invalida um experimento explicitamente solicitado como LLM-only.

O preflight prova contrato e disponibilidade pontual, não reserva capacidade
diária. Portanto o harness precisa falhar fechado durante a campanha.

## 2. Requisitos

- **R1:** eventos de uma invocação roteada são agrupados por `attempt_index`; a
  invocação é terminal quando nenhum candidato do grupo termina em `success`.
- **R2:** matrix real exige zero invocação terminal no startup e em cada turno.
- **R3:** primeira invocação terminal grava o turno auditável, aborta a campanha
  e impede que a matrix inicie o próximo par.
- **R4:** campanhas offline e o produto normal preservam a resiliência atual;
  fail-closed é política exclusiva do experimento real LLM-only.
- **R5:** manifesto registra a política estrita e validação de completude a trata
  como requisito, sem expor mensagem sensível do provider.

## 3. Aceite

- [x] Unidade agrupa fallback bem-sucedido como sucesso da mesma invocação.
- [x] Unidade acusa grupo sem sucesso, inclusive circuit/build error.
- [x] Matrix real passa a flag estrita e para antes do segundo par.
- [x] Matrix offline curta e suíte completa verdes.
- [x] Execução real sem capacidade aborta no primeiro turno afetado e não inicia o par seguinte.
