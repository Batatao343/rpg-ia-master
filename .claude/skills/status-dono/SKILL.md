---
name: status-dono
description: Responde "em que momento estamos / o que eu (dono) preciso fazer" — lista curta de bloqueios humanos com a ação concreta de cada um, a partir de ESTADO_ATUAL.md e dos cabeçalhos das specs. Use em "/status-dono", "o que eu tenho que fazer", "me fala em que pé estamos".
---

# /status-dono

1. Leia só as seções "Estado em 10 linhas", "Bloqueios no dono" e "Notas da onda em
   curso" do `ESTADO_ATUAL.md` (não abra `docs/historico/`).
2. `uv run --frozen python scripts/spec_index.py summary` e, para cada spec
   `in-progress`, o parágrafo de Status do cabeçalho (`grep -m1 -A2 "Status" specs/SPEC-NNN-*.md`).
3. Se houver run de CI esperando o dono: `gh run list --limit 5` (status `waiting`).

Responda em pt-BR, em até 12 linhas:
- **Onde estamos** (2 linhas: sha da `main`, o que acabou de pousar).
- **O que só você pode fazer** — lista numerada, cada item com o verbo e o lugar
  ("aprovar o run X em <link>", "colar a chave Y no .env.staging", "decidir Z").
- **O que eu faço em seguida** sem depender de você (1–3 itens).
Sem jargão interno; sem repetir histórico.
