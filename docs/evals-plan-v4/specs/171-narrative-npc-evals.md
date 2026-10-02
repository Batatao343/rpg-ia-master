# SPEC-171 — Narrative e NPC Evals deterministic-first

> **Status:** `draft`
> **Depende de:** SPEC-170 `done`
> **Modelo executor mínimo:** Sol High
> **Revisão obrigatória:** **Astra**

## Objetivo

Usar estado/evidência canônica para bloquear contradições e manter judges subjetivos fora do caminho crítico até calibração.

## Blocking determinístico

- falsa morte;
- posse falsa;
- localização contraditória;
- identidade NPC;
- secret leak;
- reward/outcome contradiction;
- lifecycle/action incompatível;
- entidades fora da cena quando detectável pelo estado.

## Judge inicialmente não-blocking

- persona;
- fluidez;
- agência subjetiva;
- repetição semântica.

## Promoção de judge

Exige corpus humano rotulado, agreement, known-good/known-bad, position-swap, model/version pinned e Astra review específica.

## Aceite

- [ ] hard claims usam estado canônico;
- [ ] zero judge substituindo check determinístico;
- [ ] Astra aprova fronteira blocking/non-blocking.
