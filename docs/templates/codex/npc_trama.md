---
# TEMPLATE de NPC de trama (SPEC-350). Copie para data/codex/npcs/tramas/<id>.md
# e preencha. Nome do arquivo = id. `curated: true` é obrigatório.
id: npc_tr_exemplo_da_silva
type: npc
name: Exemplo da Silva
aliases: [Exemplo]
tags: [nova_arcadia, trama]
visibility: public
curated: true
related_entities: [<faccao_ou_local>, <location_id>]
home_location_id: <location_id>
role: <ofício em poucas palavras>
faction: <faction_id>   # remova a linha se não houver facção pública
---

# Exemplo da Silva

Papel: <ofício e onde trabalha; 1–2 frases>.

Aparência: <2 frases concretas; nada de "olhos misteriosos">.

Como fala: <registro> e uma fala curta entre aspas, que o jogador possa reconhecer sozinha.

Onde achar: <lugar e hora> e o que a pessoa pede a quem aparece (a porta da trama, em 3ª pessoa).

<!--
DOC DE SEGREDO (arquivo à parte): data/codex/npcs/segredos/<id>_segredo.md

---
id: <id>_segredo
type: npc_secret
name: Exemplo da Silva — Segredos
aliases: []
tags: [nova_arcadia, trama]
visibility: hidden
related_entities: [<id>]
---

# EXEMPLO DA SILVA — O QUE NÃO É DITO

Segredo: <uma pequena traição ou um pequeno ato de decência que custa algo; o fato inteiro>.

REGRAS: o doc público nunca traz o fato; a ficha em data/world/plot_threads.json só
guarda o TÓPICO que ele evita (<= 60 caracteres). Registre também a entidade em
entities_extra.json, as arestas em edges.json e a agenda em npc_world.json.
-->
