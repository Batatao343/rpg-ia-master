# SPEC — Encerrar loop de Mimetismo Morto

> **Status:** `approved`
> **Criada/Atualizada:** 2026-08-20
> **Origem:** matriz A, par 4, turno 27

## 1. Problema

Dois Cervos Afogados usaram `bst_mimetismo_morto` em todas as rodadas (28 usos
por criatura), permaneceram escondidos e tornaram ataques incapazes de produzir
mudança. O combate chegou à rodada 30 e disparou `combat.no_progress`.

## 2. Requisitos

- **R1:** inimigo já `escondido` não seleciona outra Carta `efeito.kind=esconder`.
- **R2:** ele seleciona outra Carta ativa utilizável ou ataque básico, que revela
  o atacante depois da resolução.
- **R3:** regra é genérica por efeito/estado, não hardcode de criatura/Carta.
- **R4:** economia/frequência de Cartas inimigas permanece determinística.

## 3. Aceite

- [x] Unidade prova que oculto não seleciona esconder novamente.
- [ ] Combate com Cervo progride e não acumula 28 usos.
- [x] Suíte completa verde.
