# SPEC — Decisões atômicas no playtest

> **Status:** `done` (2026-08-02)
> **Criada:** 2026-07-25 · **Atualizada:** 2026-08-02
> **Depende de:** `fix-vitalidade-ferimentos-terminal`
> **Desbloqueia:** métricas e invariantes confiáveis no smoke real

---

## 1. Contexto & Objetivo

O runner escolhe texto com `next_action()` e, separadamente, consome o RNG outra
vez para criar `TurnDeclaration`. Assim, “bebo poção”, “fujo” ou “viajo” pode
resolver mecanicamente como Carta/ataque. No smoke, 71 de 75 textos em combate
não descreviam a ação realmente executada, e o perfil `fujao` nunca exercitou a
perseguição.

## 2. Requisitos

- **R1** — Cada turno nasce de um único `ProfileDecision` com `text`, `mode`,
  `declaration` e destino de fuga opcionais, validados como combinação exclusiva.
- **R2** — O texto é renderizado da própria declaração; Carta/item/alvo no texto
  e na mecânica são idênticos.
- **R3** — Fuga/viagem em combate usa `mode=flee`, declaração nula e o fluxo de
  perseguição. Sucesso não é garantido, tentativa mecânica é.
- **R4** — Cura escolhe um item real do inventário e o resolve como item; ataque
  e Carta carregam IDs reais.
- **R5** — Runner chama `profile.decide()` uma vez. `next_action()` fica somente
  como wrapper de compatibilidade e não é usado pelo harness.
- **R6** — O motor expõe `combat.last_player_action` canônico com tipo, IDs,
  alvo, sucesso e dados de fuga.
- **R7** — Invariante `action.declaration_matches` é erro quando intenção,
  declaração e efeito divergem.
- **R8** — Fuga consome a ação independentemente do resultado. Se a perseguição
  falhar, inimigos ainda resolvem seus turnos, mas o parser/declaração normal do
  jogador não roda e nenhum ataque/Carta/item oculto é executado.

### Fora de escopo

- Alterar a dificuldade da perseguição.
- Transformar fuga em `TurnStep`; ela permanece um fluxo entre rodadas.

## 3. Design técnico

`playtest/profiles.py` define `ProfileDecision` e `decide(state, rng)`.
`playtest/runner.py` injeta texto/declaração/flags a partir do mesmo objeto.
`services/conflict_turn.py`, `services/conflict_orchestrator.py` e
`agents/combat.py` propagam o resultado canônico em `combat`.

## 4. Plano passo a passo

1. **Testes:** determinismo por seed, exclusividade do schema, Carta/item/fuga e
   todos os perfis produzem decisão coerente.
2. **Implementação:** decisão atômica e compatibilidade.
3. **Testes:** runner chama uma vez; `fujao` tenta fuga; explorador não ataca ao
   pedir viagem; item é consumido e Carta resolvida com o mesmo ID; fuga
   malsucedida não chama `_parse_turn_declaration` nem produz ataque do herói.
4. **Implementação:** fiação runner→motor→resultado.
5. **Testes/implementação:** invariante e contadores requested/resolved/flee.

## 5. Critérios de aceite

- [x] Zero escolha independente de texto e declaração.
- [x] `fujao` e explorador exercitam tentativa real de fuga.
- [x] Poção/Carta/alvo pedidos são os resolvidos.
- [x] Fuga falha consome a ação e não executa uma segunda intenção escondida.
- [x] `action.declaration_matches=0` no smoke.
- [x] Suíte completa verde.

## 6. Smoke test com LLM real

Rodar perfis `fujao`, `combate`, `explorador` e `curioso` por turnos suficientes
para entrar em combate; confirmar tentativas/efeitos no JSONL e no transcrito.

**Evidência (2026-08-02):** 390 turnos reais sem
`action.declaration_matches`; decisões e ações resolvidas são registradas no
mesmo objeto. Sanity real `20260802-154332-961894` confirmou que turno sem
`combat_agent` não reaproveita ação resolvida anterior.

## 7. Riscos & compatibilidade

`next_action()` segue disponível a callers externos. A decisão de cura depende
da migração de Vitalidade e por isso esta spec roda depois dela.
