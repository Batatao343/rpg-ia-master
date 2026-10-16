# SPEC-202 — handoff de autoria de eval (routing.interlocutor.*)

`evals/` NÃO foi editado (protegido). Uma ação para a governança de evals.

> Nota (revisão Astra 2026-10-16): a SPEC-202 NÃO faz bump de `SCHEMA_VERSION`
> (mudança aditiva, default no load). O caso protegido
> `state.persistence.migration-idempotent` (v8) continua correto — nenhum ajuste em
> `state_rules` é necessário.

## 1. Corpus novo `routing.interlocutor.*` (suite routing, SPEC-169)

Fixture comum: cena em `brekmar` com `Brunna Ponte-Alta` (role Barqueira) e
`Velha Magda` (role Vidente) `in_scene`; `Gorim` conhecido fora de cena
(`home_location_id=skallgard`). Esperado = saída do router ANTES da narração.

| id sugerido | input | CLASSIFY fake (route/target) | expected.route | expected.speaker_kind | expected.target | invokes |
|---|---|---|---|---|---|---|
| meta-narrador-sobre-npc | Pergunto ao narrador o que a Velha Magda sente | npc / Velha Magda | storyteller | narrator | null (mediated `npc_velha_magda`) | 0 |
| meta-vocativo | Narrador, a Brunna parece mentir? | npc / Brunna | storyteller | narrator | null | 0 |
| meta-ooc | ((fora do jogo: a Brunna é confiável?)) | npc / Brunna | storyteller | narrator | null | 0 |
| sobre-sem-verbo | O que eu sei sobre a Brunna? | npc / Brunna | storyteller | narrator | null | 0 |
| descricao-cena | Descreva quem está aqui | npc / Brunna | storyteller | narrator | null | 0 |
| vocativo-presente | Brunna, você viu o barco? | npc / Brunna | npc_actor | npc | Brunna Ponte-Alta | 1 |
| vocativo-promove-story | Magda: o que as cartas dizem? | story / null | npc_actor | npc | Velha Magda | 1 |
| pergunto-a-nome | Pergunto à Brunna sobre o barco | story / null | npc_actor | npc | Brunna Ponte-Alta | 1 |
| transcricao-pausas | é... Brunna... você viu o barco? | npc / null | npc_actor | npc | Brunna Ponte-Alta | 1 |
| nome-alucinado | Falo com Halveth | npc / Halveth | storyteller | narrator | null | 1 |
| conhecido-fora-de-cena | Falo com Gorim | npc / Gorim | npc_actor | narrator | Gorim (resposta "não está aqui") | 1 |
| papel-generico-assentamento | Falo com o taverneiro (npcs vazio) | npc / taverneiro | npc_actor | npc | taverneiro (generic_role_spawn) | 1 |
| papel-generico-ermo | idem em `deserto_zhur` | npc / taverneiro | npc_actor→storyteller | narrator | null | 1 |
| multiplos-continuidade | E o que mais? (last_speaker Brunna, turno-1) | npc / null | npc_actor | npc | Brunna Ponte-Alta | 1 |
| multiplos-sem-continuidade | E o que mais? (last_speaker Brunna, turno-5) | npc / null | storyteller | narrator | null | 1 |
| pronome-continuidade | E você? (last_npc Magda, turno-2) | story / null | npc_actor | npc | Velha Magda | 1 |
| pronome-sem-candidato | Pergunto a ela o que houve | npc / ela | storyteller | narrator | null | 1 |
| alvo-alucinado-nome-no-texto | Peço que Brunna Ponte-Alta se junte a mim (só Brunna) | npc / Corvo | npc_actor | npc | Brunna Ponte-Alta | 1 |

Negativos de falso positivo: "O narrador da taverna começa a cantar" (não é meta),
"Pergunto ao mestre Orlan sobre a espada" com NPC `Mestre Orlan` em cena (NPC, não meta),
"Bo, venha cá" com NPC `Bo` (alias < 3 letras não casa).

Candidato narrativo (P4, não gate): concordância de pronome na prosa mediada
(sem campo de dado `pronouns` nesta spec).
