---
id: mon_<slug>                    # ex.: mon_devorador_de_brumas — único (lint valida)
type: monster
name: <Nome Exato>
aliases: []
tags: [<regiao>, <habitat>]       # ex.: [pantano_melancolia, aguas_rasas]
visibility: public                # public | hidden | secret
related_entities: [<location_id>] # região onde vive (id existente)
curated: true                     # OBRIGATÓRIO em arquivo manual — migrate não apaga
---

# <NOME EM CAIXA ALTA>

<o que caçadores contam sobre a criatura — aparência, sinais da presença>

<comportamento: como caça, do que foge, o que a atrai>

<stats de combate ficam em data/bestiary.json (com `regions`/`behavior`), não aqui>
