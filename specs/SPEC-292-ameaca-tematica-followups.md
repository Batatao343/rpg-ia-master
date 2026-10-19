# SPEC-292 — ameaca-tematica-followups

> **Status:** `done` — dono autorizou em 19/10/2026 tudo que não exige ação externa dele (onda 19/10).
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Depende de:** SPEC-289 (`done`), Fase 2 (`faction_intel`, não-onisciência)
> **REVIEW_REQUIRED:** false (follow-ups P2 já revistos na SPEC-289; mudança pequena e determinística)

---

## 1. Contexto & Objetivo

Follow-ups P2-2 e P2-3 de `handoffs/SPEC-289-review.md`.

- **P2-2:** com UMA criatura temática no porte (só a Faísca da Destilação em `aethelgard`
  Minion), a pressão de caça da Fase 6.3 não surtia efeito: o peso 0,1 da criatura farmada era o
  único peso e migrantes estão desligados na camada temática.
- **P2-3:** o nome canônico do combatente da fação ("Iniciado da Chama Azul") expõe a fação ao
  jogador que ainda não a conhece (`faction_intel[fid].known`), e a narração de combate recebia o
  elenco canônico sem restrição.

## 2. Requisitos

- **R1 — Pressão de caça mistura o pool (P2-2).** No sorteio ponderado temático, se a média dos
  pesos base (`hunt_pressure × faction_boost`, sem a pontuação temática) ficar abaixo de
  `MIGRANT_THRESHOLD + 0.2` (limiar da fauna rareada da 6.3), o pool regional do MESMO porte (BOSS
  fora, porte estrito) entra no sorteio com peso base ×1; as temáticas seguem ×pontuação.
  População intacta → idêntico à SPEC-289. Determinístico por `rng`/seed.
- **R2 — `public_hint` (P2-3).** `check_encounter` (ramos `looming_threat` e `controlled`) devolve
  também `public_hint`. O `hint` canônico NÃO muda (spawn, dedupe e manifesto `systemic`). Se a
  fação da criatura é desconhecida E o nome da criatura casa radicais do nome da fação,
  `public_hint = "combatente de uma ordem que você não reconhece"` e o retorno traz
  `concealed_faction`; senão `public_hint == hint`. Conhecimento = regra existente `intel[fid].known`.
- **R3 — Handoff e narração.** `encounter_handoff` carrega `public_hint`. `_narrate` recebe cláusula
  proibindo citar o nome das fações dos combatentes que o jogador não conhece (manifesto +
  `faction_intel`); conhecida → sem cláusula.
- **R4 — Compatibilidade.** `pick_encounter_enemy` sem `theme` idêntico; save sem `public_hint` → `hint`.

### Fora de escopo

Renomear a criatura em `enemies[].name`/API (segue canônico); revelar a fação segue sendo
`apply_faction_reveal`.

## 3. Design técnico

`world_utils.py`: mistura em `pick_encounter_enemy`; `concealed_faction`, `public_encounter_hint`,
`unknown_faction_names`; `check_encounter`. `agents/storyteller.py`: `encounter_handoff`.
`agents/combat.py`: `_faction_withhold_clause` + `_narrate(withhold=)`.

## 4. Plano

Testes primeiro em `tests/test_spec289_ameaca_tematica.py` (seção SPEC-292), depois implementação,
escopo verde, playtest e suíte completa.

## 5. Critérios de aceite

- [x] R1–R4 cobertos por testes
- [x] Escopo (289, 288, 287, fase2, fase63, manifesto, fase0) verde
- [x] `playtest run --profile combate --turns 200` seeds 11/22/33: 200/200, 0 erro, 0 violação
      (runs `20261019-193918-497875`, `-193933-657362`, `-193945-206367`)
- [x] Suíte completa 1x (resultado no hand-back)
- [x] Sem `with_structured_output` novo; saves antigos carregam
