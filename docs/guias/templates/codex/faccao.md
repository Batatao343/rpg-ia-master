---
id: <slug_da_faccao>              # ex.: irmandade_do_sal — único (lint valida)
type: faction
name: <Nome Exato>
aliases: []
tags: [<regiao>, <natureza>]      # ex.: [nova_arcadia, guilda]
visibility: public                # public | hidden | secret
related_entities: [<location_id>] # região onde atua (id existente)
curated: true                     # OBRIGATÓRIO em arquivo manual — migrate não apaga
---

# <NOME EM CAIXA ALTA>

Natureza: <uma linha — o que a fação é>

Objetivo declarado: <o que dizem querer>

<estrutura, símbolos, como tratam forasteiros, rivais conhecidos —
a perspectiva INTERNA (o que só membros sabem) vai em doc `perspective`
com visibility: hidden, não aqui>
