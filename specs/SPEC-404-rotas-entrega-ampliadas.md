# SPEC-404 — Rotas de entrega ampliadas

> **Status:** `approved` (11/11, dono: "crie mais rotas de entrega também, faça uma spec para isso"; decisões D-404-* pelo coordenador, com a delegação de 09/11)
> **Criada:** 2026-11-11 · **Atualizada:** 2026-11-11
> **Depende de:** SPEC-313 (`done`, quests ancoradas em lore), SPEC-348 (`done`, rota de Vorr canônica)
> **Desbloqueia:** quests de "entregar material" fora do Pântano e de Skallgard
> **Risco:** `médio` (conteúdo de economia: materiais, estoque de mercador e uma correção pequena no menu de quests). Revisão: revisor Sonnet, como manda o AGENTS.md § Qualidade.
> **Evidência:** `test_menu_offers_route_beyond_first_three` falha hoje (o menu corta a lista antes de filtrar a região); os testes de catálogo generalizados (R4) passam a cobrir todas as rotas, e não só a de Vorr.
> **EVAL_AUTHORING_REQUIRED:** `false` (nenhum caminho de `evals/protected-paths.txt`).

## 1. Contexto & Objetivo

Hoje existem só duas rotas em `data/world/lore_quests.json` → `delivery_routes`: o musgo cinzento do Pântano para o Anel de Lama (`cha_druidas_anel_lama`) e o lingote de Vorr de Skallgard para Brekmar (`minerio_skallgard_brekmar`). Na revisão de 11/11 (SPEC-312 D1 e SPEC-313 D8), o dono aprovou as duas e pediu mais.

Uma rota só funciona quando:
- o herói consegue o material na região de origem, o que hoje exige um mercador dessa região que venda o material;
- o material é `type: material`;
- o destino existe e fica a pelo menos `DELIVERY_MIN_PERIODS` de viagem;
- um NPC da região bate com as `patron_tags`.

Só 5 regiões têm mercador: Skallgard, Nova Arcádia, Brekmar, Pântano da Melancolia e Pradaria das Ruínas. E existem só 7 materiais.

Também há um bug que impede ampliar a lista: `services/lore_quests.py:316` faz `cfg()["delivery_routes"][:maxn]` **antes** de filtrar por região. Com `MENU_MAX_PER_KIND = 3`, nenhuma rota depois da 3ª da lista jamais seria oferecida.

Objetivo: chegar a **pelo menos 10 rotas**, com pelo menos uma saindo de cada uma das 5 regiões com mercador. Cada rota fica ancorada num trecho de lore, é cumprível e dá lucro, e o menu passa a enxergar todas.

## 2. Requisitos

- **R1 — Menu sem corte prematuro.** O menu de propostas filtra as rotas (região de origem, `_route_valid`, `_patron_match`, cooldown) e **só depois** limita a `MENU_MAX_PER_KIND`. A ordem segue a do arquivo (determinística).
- **R2 — Rotas novas.** Pelo menos 8 rotas novas, totalizando ≥ 10. Pelo menos 1 rota de origem em cada região com mercador (`skallgard`, `nova_arcadia`, `brekmar`, `pantano_melancolia`, `pradaria_ruinas`). No máximo 3 rotas por origem. Os destinos variam: pelo menos 6 regiões diferentes como destino somando todas as rotas, e destino nunca na mesma região de origem.
- **R3 — Cada rota tem âncora de lore.** O campo `lore_ref` (arquivo:linhas em `lore_nova/`) contém a `lore_keyword`, e o trecho justifica *por que esse material vai para esse destino* (comércio, necessidade, facção). O `patron_tags` usa papéis/facções que existem na região de origem. Cada rota é revisada por um autor que não a escreveu.
- **R4 — Cumprível e lucrativa (todas as rotas).** Para cada rota:
  - (a) o `item_id` existe em `data/artifacts.json` com `type: material`;
  - (b) algum mercador da região de origem tem o item em `base_stock`;
  - (c) `qty × value_gold × menor price_mult` ≤ maior recompensa de `entregar_material`;
  - (d) `world_distance.travel_periods(origem_mais_próxima, to) ≥ DELIVERY_MIN_PERIODS` para alguma localização da região de origem;
  - (e) `to` existe no mapa.

  Os testes de 348 que hoje cobrem só a rota de Vorr (`test_vorr_route_is_fulfillable_and_profitable`) passam a valer para todas, num teste novo parametrizado. O teste antigo continua intocado.
- **R5 — Materiais novos (opcional, até 4).** Se a lore pedir um material que não existe, cria-se o item em `data/artifacts.json` no molde do `musgo_cinzento`, com `stackable: true`, `economy_tags`, combat/mechanics zerados e `rarity` **comum ou incomum, nunca raro** (o raro afia carta, `services/card_rewards.py:544`). O item entra no `base_stock` de um mercador da região de origem. O lint `scripts/validate_content.py` fecha com 0 ERRO.
- **R6 — Nada muda nas duas rotas atuais**, nas constantes nem nas recompensas (`rewards.entregar_material` fica `[15, 25, 40]`).
- **R7 — Saves antigos:** uma quest ativa com `anchor.type = route` cujo id existe continua resolvendo igual. Nenhum id atual é renomeado.

### Fora de escopo

- Mercadores novos em regiões sem comércio (Zhur, Xylos, Ophidia, Costa Negra, Aethelgard, Floresta, Montanhas). Eles abririam rotas dessas origens e viram spec própria (follow-up F1).
- Material obtido por saque de criatura.
- Mudar a fórmula de prazo ou de recompensa.
- Escolta e outros tipos de quest.
- Material raro.

## 3. Design técnico

- **`services/lore_quests.py`:** no laço de rotas do menu (`:316`), trocar o slice-antes-do-filtro por filtro-e-depois-limite (contador até `maxn`). Nenhuma outra mudança de lógica.
- **`data/world/lore_quests.json` → `delivery_routes`:** rotas novas no formato existente:

  ```json
  {"id": "<origem>_<material>_<destino>", "origin_region": "<region_id>", "to": "<location_id>",
   "item_id": "<artifact_id>", "qty": 2, "patron_tags": ["..."],
   "lore_ref": "lore_nova/<arquivo>.txt:<a>-<b>", "lore_keyword": "<palavra no trecho>"}
  ```

- **`data/artifacts.json`** (só se R5) e **`data/merchants.json`** (`base_stock` de mercador existente, sem mudar `price_mult`).
- **`tests/test_spec404_delivery_routes.py`** (novo): R1, R2, R4 parametrizado por rota e R7.
- **`docs/guias/AUTORIA.md`:** uma linha sobre como criar rota (os 5 checks do R4).

## 4. Plano passo a passo

### Etapa 1 — Menu (R1)

1. **Teste:** `test_menu_offers_route_beyond_first_three` monta um `cfg` com 4 rotas, sendo que só a 4ª é da região do herói, e asserta que ela aparece no menu. Hoje falha.
2. **Implementação:** filtro e depois limite.
3. **Verificação:** testes `tests/test_spec313_*` verdes (`-n 2`).

### Etapa 2 — Autoria das rotas (R2, R3, R5)

1. **Testes:** `test_routes_cover_all_merchant_regions`, `test_route_destinations_spread`, `test_every_route_fulfillable_and_profitable[...]` e `test_route_lore_keyword_in_range[...]`.
2. **Conteúdo:**
   - ler `lore_nova/` com `Grep` mais recorte (nunca o arquivo inteiro) atrás de comércio entre regiões: aço, ervas, cordas, kits, sal, vidro, resinas, couro;
   - escrever as rotas e, se preciso, até 4 materiais;
   - registrar na §6 uma tabela rota → trecho de lore → por quê.
3. **Verificação:** `scripts/validate_content.py` com 0 ERRO, mais os testes acima.

### Etapa 3 — Revisão e pouso

Revisor Sonnet confere R3 (lore coerente, sem nome secreto, patrono plausível) e R4. Depois, a suíte completa no pouso, rodada pelo coordenador.

## 5. Critérios de aceite

- [ ] R1: rota depois da 3ª aparece no menu (teste novo verde; falhava antes)
- [ ] ≥ 10 rotas; 5 regiões de origem; ≥ 6 regiões de destino
- [ ] Todas cumpríveis e lucrativas (R4 parametrizado verde)
- [ ] `validate_content.py` 0 ERRO; nenhum material `raro` novo
- [ ] Duas rotas atuais, constantes e recompensas intactas
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Saves antigos continuam carregando (R7)
- [ ] Revisão Sonnet APPROVED

## 6. Smoke test com LLM real

Opcional (o conteúdo é determinístico; o LLM só narra). No staging com `RPG_LORE_QUESTS=on`:
1. Ir a Brekmar ou à Pradaria e falar com um NPC que bate com a rota nova.
2. Confirmar que a proposta "levar N X a Y" aparece.
3. Aceitar, comprar o material e entregar no destino.
4. Conferir que o ouro e a narração saem coerentes.

## 7. Decisões (coordenador, delegação do dono)

- **D-404-1:** a origem fica restrita às 5 regiões que já têm mercador. Rotas de outras regiões exigem mercador novo (F1).
- **D-404-2:** material novo só comum ou incomum, para não inflar o afiamento de carta.
- **D-404-3:** recompensa e prazo seguem a fórmula atual (banda por distância), sem constante nova.
- **D-404-4:** as rotas entram sem revisão nominal do dono. O resumo vai para ele no hand-back e o veto continua possível.

## 8. Follow-ups

- **F1:** mercadores nas 7 regiões sem comércio, abrindo rotas de origem nelas.
