---
id: npc_<slug_do_nome>           # ex.: npc_maera_dos_sais — precisa ser único (lint valida)
type: npc
name: <Nome Exato>
aliases: []                       # apelidos que o librarian usa p/ dedupe
tags: [<regiao>, <papel>]         # ex.: [pantano_melancolia, curandeira]
visibility: public                # public | hidden | secret
related_entities: [<location_id>] # ids existentes (lint valida)
curated: true                     # OBRIGATÓRIO em arquivo manual — migrate não apaga
---

# <NOME EM CAIXA ALTA>

Papel: <uma linha — o que este NPC é no mundo>

Aparência: <2-3 linhas>

Comportamento: <como fala, tiques, o que valoriza>

<história pública, ganchos de quest, relações conhecidas — SEGREDOS NÃO VÊM AQUI:
verdade oculta vai num doc separado `npcs/segredos/{id}_segredo.md` com
type: npc_secret e visibility: hidden (Fase 7.3)>
