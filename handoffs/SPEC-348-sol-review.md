# SPEC-348 — revisão sol (review)

> **Veredito (re-revisão, `5570a0fc`):** `CHANGES_REQUIRED` (1ª rodada em `1f059e04`: `CHANGES_REQUIRED`)
> **Revisor:** Opus · papel Sol (técnico) + Astra (semântica de lore/tom) · **Data:** 2026-10-28 · **Commit revisado:** `1f059e04` (código/lore em `36ed495a`; `1f059e04` só traz o reindex do FAISS)

## Escopo

Branch `spec-348`, `main...HEAD` (7 commits, 165 arquivos). Conferi as decisões C/G/S/E e D1–D12
(`docs/lore/decisoes-2026-10-27.md`) contra o diff de `lore_nova/*.txt`, os docs curados novos
(`story_posturas`, `pm_cripta_afogada`, `pr_solvhen`, `ma_forja_profunda`), as amostras de docs gerados
(Magda, Vane, Volkar, Eco, Arauto, Ilsa, Bertil, Sennar, Hrefna, Oriel, Mairen, Kahen), `edges.json`,
`artifacts.json`, `lore_quests.json`, `calendar.json`, `festivals.json`, `bestiary.json`, `rumors.txt`,
`scripts/lore_reanchor.py` e os testes novos e alterados. Para vazamentos fiz varredura própria de
`LEAK_PHRASES` e de termos de segredo que aparecem juntos em todos os docs públicos do Codex e em todas
as strings de `data/*.json` (world_map, seed tables, quests, artifacts, grafo). Não li lore nem codex
inteiros; não mexi em `faiss_*_index/`.

Aplicadas sem desvio: C-01/C-02 (pacto em camadas, oculto, décimo ano), C-03, C-04, C-05, C-06, C-07
(cadeia única + D5), C-08 (Colina Cinza, D4), C-10, C-11, C-13, C-14, C-15, C-16, C-17, C-18, C-19 nas
fontes listadas, C-21, G-06, G-07, G-08, G-09/E-10, G-10, G-11, G-12, G-13, G-15, G-16 (no texto), S-03,
S-06, S-08, E-01…E-26 aprovadas e nenhuma da gaveta. A prosa nova está na voz de crônica cansada e
sem termo `[proibidos]`. Os pontos fortes são o calendário (`daily_life.txt:317+`), os mestres das
Posturas, Cripta, Solvhen, Forja e Os Quebrados.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `data/world_map.json:450` | O `lore_seed` do Farol ainda diz "suprime o despertar da Rede Carmesim… a cada cem anos um andarilho chega, mata o anterior… O Abismo cobra a vida". Isso vaza C-20/D3 por **dois** caminhos ativos: o prompt do narrador na chegada (`agents/storyteller.py:1314`, `:1320`) e a aba Mapa do jogador (`services/map_view.py:161` → `web/src/workspace/tabs/MapTab.tsx:187`), para qualquer nó visitado. A §9 adiou isso para a "spec do mapa", mas não é mudança de nó: é o mesmo vazamento que C-20 manda esconder, e o jogador vê o texto na tela. | Trocar o `lore_seed` por texto só com o lado público, por exemplo: "Ergue anti-luz sobre o gelo, e a aurora do norte muda de ritmo ao redor. Um guardião que nunca fala e que ninguém alcança. Para quê, ninguém sabe." Incluir `data/world_map.json` (`locations[*].lore_seed`) em `test_seed_gists_and_bestiary_have_no_leak_phrases`. |
| P1-2 | P1 | `data/codex/world_story/story_posturas.md:45` | Doc **público** diz "A Guilda dos Corvos a despreza: vende os marcados em vez de tratá-los." Pela C-19, o público só pode saber que "a Guilda nunca queima certos corpos"; que os marcados são entregues/vendidos (a Vane) é fato oculto (`npc_doutor_silas_vane_segredo`, segredo "Os Marcados Resistem"). A frase veio da coluna "Despreza" da §3.7 da spec, que era justificativa interna, não texto público. | Reescrever sem o destino dos corpos, por exemplo: "A Guilda dos Corvos a despreza: Benedita trata quem os Corvos já contaram como carga." Acrescentar `"vende os marcados"` / `"entrega os marcados"` ao grupo `corpos` de `LEAK_PHRASES`. |
| P1-3 | P1 | `lore_nova/npcs.txt:550` (Nehla, doc `npc_nehla_ouvido_de_aurora`) | Vazamento antigo que a varredura de C-20 deixou passar. "O que sabe" é rótulo público: "A Rede Carmesim está acelerando… Calculou uma estimativa de quando o Farol pode não ser suficiente". Isso entrega a ligação Farol → Rede e a estimativa de falha, as duas ocultas por R40/D3. A mesma estimativa foi tirada de `items.txt:171` nesta spec, então a correção ficou pela metade. Também é quase literal a assinatura `rede_carmesim` "acelerando mais rápido do que admitem". | Passar o parágrafo para `Segredo:` (vai para `npc_nehla_ouvido_de_aurora_segredo.md`). No público, deixar algo como "Mede o céu todo dia e está proibida de falar do que mede." Adicionar `"farol pode nao ser suficiente"` ao grupo `farol`. |
| P1-4 | P1 | `lore_nova/npcs.txt:1360` (Arquimaga Sylvenne, doc público) | Vazamento antigo do núcleo de C-01: "Suspeita do pacto de Valerius (sente o Éter de Daruun nele)". O doc público passa a nomear a contraparte do pacto, que R18 manda manter oculta (a assinatura `pacto com daruun` só não pega porque a ordem das palavras é outra). | Público: "Suspeita do que Valerius fez para não envelhecer." O "sente o Éter de Daruun nele" vai para um parágrafo `Segredo:`. Adicionar ao teste a checagem de `daruun` + `pacto` no mesmo parágrafo de doc público, igual à que já existe para armadura + pacto. |
| P1-5 | P1 | `lore_nova/timeline_completa.txt:436`, `lore_nova/daily_life.txt:318` × `timeline_completa.txt:308-310` | Contradição de cronologia criada pela aplicação de D1. A Era 7 diz que o Ano 1 é o começo do Protocolo dos Anões ("o registro das Landships, que começou antes da guerra"), e a guerra cai no Ano 67. Só que as Landships e o Protocolo nascem na **Era 5**, na Falha Crítica de Contenção (`:308-310`), e a própria timeline põe "Mil anos" entre a Era 5 e a Era 6 (`:324`). Do jeito que está escrito, o Protocolo teria mais de mil anos antes da guerra, e não 67. | Sem reabrir D1 (`YEAR_BASE` 112 e Ano 1 = Protocolo): dizer que a contagem é a do **Livro** do Protocolo que está aberto, por exemplo: "o Protocolo recomeça a conta a cada Livro, e o Livro aberto hoje começou sessenta e sete anos antes da guerra". Aplicar o mesmo em `daily_life.txt:318`. Se o coordenador achar que isso interpreta D1 além do que foi decidido, levar uma pergunta de uma linha ao dono. |
| P1-6 | P1 | `data/artifacts.json:355`, `data/world/lore_quests.json:40`, `data/merchants.json:11` | R36 deixou a rota impossível de cumprir e com prejuízo. Nenhum mercador, tabela de loot ou receita produz `lingote_aco_vorr`: o mercador de Skallgard vende `minerio_ferro` (`merchants.json:11`), não o lingote. A quest pede 3 unidades e não verifica estoque (`services/lore_quests.py:240-244` só valida `type == material`). Mesmo com estoque, o preço é 60 × 0,6 × 3 ≈ 108 de ouro contra uma recompensa de 15–40 (`lore_quests.json:18`). Antes era ~14 contra 15–40. | Pôr `lingote_aco_vorr` no estoque do mercador de Skallgard (e, se fizer sentido, em `recipes.json` a partir de `minerio_ferro`). Baixar `value_gold` para a faixa da recompensa (~8–12) ou a rota para `qty: 1`. Teste: a rota tem pelo menos uma fonte do item na região de origem, e 3 × preço de compra na origem fica ≤ a maior recompensa. |
| P2-1 | P2 | `lore_nova/races.txt:33` | "A coalizão venceu. Elaryin morreu três anos depois": três anos depois da vitória dá 42 anos atrás, não os 41 de C-09. `npcs.txt:85` acerta ("três anos após a fundação"). | "Elaryin morreu três anos depois da fundação de Nova Arcádia". |
| P2-2 | P2 | `lore_nova/npcs.txt` (bloco de Mairen), `data/graph/edges.json` (`e_mairen_membro_cultistas_destilacao`), `lore_nova/rumors.txt:417` | Mairen é "A QUE APRENDEU E SAIU" e "deixou" Corvane, mas o grafo a põe como `member_of cultistas_destilacao`. Além disso, o doc público diz que ela de fato cura "apodrecendo mais depressa", enquanto o rumor de origem da Postura é `truth: false`. | Escolher um lado: tirar o `member_of` (só `located_in`, como Benedita) ou dizer que ela saiu do círculo de Corvane, mas não do culto. Para o rumor: ou `truth: true` (e ajustar a confiabilidade de outro rumor novo para manter a fração), ou deixar claro no texto que o falso é a cura durar. |
| P2-3 | P2 | `lore_nova/npcs.txt:98` (TAGS do Arauto), `lore_nova/items.txt:757` | Pistas fortes deixadas no público. A tag `Aprendiz` no frontmatter de `npc_o_arauto_da_nevoa` (C-21: Arauto = aprendiz), e "Valerius a visita; o Código surgiu daí" na Armadura (liga Valerius, a armadura e o Código, que é a interface do pacto oculto). | Tirar `Aprendiz` dos TAGS do Arauto. Na armadura: "Ninguém entra na cela sem a ordem de Valerius." |
| P2-4 | P2 | `lore_nova/npcs.txt:72`, `lore_nova/secrets.txt:26` | S-03 foi aplicado ao pé da letra ("estudou por dezoito anos os dois… e é um dos dois"), mas a frase fica estranha (estudou a si mesmo por 18 anos?). E `secrets.txt:26` não diz que ele é um deles. | "estudou por dezoito anos o outro sobrevivente não simbiótico… e o próprio sangue, porque é o segundo". Repetir a informação em `secrets.txt:26`. |
| P2-5 | P2 | `data/codex/world_story/story_posturas.md:23` | "Ninguém as chama de classes" põe o vocabulário de sistema dentro do mundo, e o narrador pode repetir "classes". | Tirar a frase, ou trocar por "Ninguém as chama de escolas." |
| P2-6 | P2 | `lore_nova/timeline_completa.txt:470` | "quem assinava, nas masmorras, era a armadura": C-01 diz que a armadura é a **interface**, não quem assina, e `secrets.txt:12` diz certo ("o lugar por onde o Abismo assina e cobra"). | "o contrato passava pela armadura de Malagor, interface por onde o Abismo assina e cobra". |
| P2-7 | P2 | `tests/test_spec348_canon.py:228-239` | `test_cidades_keep_living_leader_when_aerwen_dies` é quase tautológico. Filtra a lista de arestas à mão e só confere `hasattr(npc_world, "leaders")`. Não monta projection com Aerwen morta nem chama o resolvedor de líder vivo, como pedia a Etapa 4. | Montar um `state` com `npc_lady_aerwen` morta na projection e conferir que o caminho real (`npc_world.leaders()` + o filtro de vivos que o motor usa) devolve `npc_keeper_morvan` para a fação. |
| P2-8 | P2 | `tests/test_spec348_canon.py:189`, `:341-349`, `:295` | Asserções vazias: `A or A` (`:189`), `old_enemy = 0; assert old_enemy == 0` (`:341`/`:349`) e uma cadeia de `or` frouxa (`:295`). | Remover ou trocar por checagem real, por exemplo `enemy_of` novo = 0 comparando com as arestas de `main`. |
| P2-9 | P2 | `lore_nova/npcs.txt:603` (Volkar) | "Pode até oferecer o posto a quem chegar" já dá uma pista do ciclo do guardião. Aceitável junto com S-08, mas é uma pista. | Opcional: "Quem chega pergunta o porquê do Farol e não recebe resposta." |

Sem P0. Não há `with_structured_output` novo nem valor vindo do LLM, nenhuma linha em `evals/`, nenhum
segredo em log. Writer persistente: só dados estáticos (sem mudança em save/load). `minerio_ferro` em
quest já aberta continua resolvendo, porque a instância guarda o `item_id` (conferido no §9 da spec e no
código).

### Testes antigos alterados (item 4)

Todos legítimos e declarados na spec: `test_spec303_festivals.py`/`test_spec307_festivals.py`
(`review` → `aprovado`, R45/D10), `test_spec307_calendar.py` (`year_review`, R15/D1),
`test_spec312_seeds.py` (48 sementes e 16/18/14, R46/D2), `test_fase25.py` (união com
`entities_extra.json`, desvio (2) da §9, igual ao lint/Fluxo A). Nenhum enfraquece um oráculo além do
que a decisão exige.

Os testes novos de vazamento, fatos ocultos, clusters, âncoras e expansões são oráculos reais: leem os
docs gerados e o frontmatter. As lacunas são P1-1 a P1-4: a lista `LEAK_PHRASES` e o escopo
(world_map, "O que sabe" de NPC não tocado) não pegaram esses casos. P2-7 e P2-8 são testes fracos.

### Migração (item 5)

`test_fase25::test_migracao_idempotente` passou (2× em `tmp_path`). Os docs curados novos têm
`curated: true`, e o override do testamento chegou ao frontmatter. `lore_reanchor.py --check` dá
0 âncora quebrada, `build_rumor_seeds.py --check` rc 0 e `validate_content.py` 0 ERRO / 0 AVISO.
Conferi 10 âncoras reapontadas por amostragem, todas coerentes. Ressalva já registrada na §9: o
migrate sozinho derruba as 36 entradas `mundo_vivo` de `entities.json`/`edges.json`, e
`gen_world_living_npcs.py` precisa rodar depois. Está documentado no `AUTORIA.md`, então fica como
follow-up, não como bloqueio.

## Correções aplicadas

Todos os P1 e P2 corrigidos nos commits `fix(lore)` desta branch; detalhe na spec §9.1. Volkar (P2-9) também aplicado. Reindex da lore refeito e smoke da §6 executado (ver §9.1).

## Pendências

- Depois de corrigir P1-1 a P1-4: rodar o migrate, `gen_world_living_npcs.py`, o lint e **outro reindex**
  do lore. O `1f059e04` indexou o Codex com os vazamentos de Nehla, Sylvenne e Posturas.
- Smoke da §6 (RAG público × `LEAK_PHRASES`, `secret_rusher` real, Médico de Campo) segue pendente
  (MODEL_HANDOFF_REQUIRED na §9). Rodar depois do novo reindex. Acrescentar a pergunta "o que Nehla
  sabe sobre o Farol?".
- Follow-up (spec de runtime, D11): assinaturas novas em `secret_signatures.py` (Víbora, barril,
  corpos, Farol, Daruun-pacto).
- Follow-up: o migrate preservar `mundo_vivo` sem precisar de um segundo script.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest tests/test_spec348_{leaks,canon,anchors}.py -p no:xdist -o addopts="" → 66 passed
bash scripts/dev/py.sh -m pytest tests/test_fase25.py tests/test_fase73.py tests/test_spec312_seeds.py tests/test_spec303_festivals.py tests/test_spec307_calendar.py tests/test_spec307_festivals.py tests/test_spec313_catalog.py tests/test_spec306_npc_seed_expansion.py -p no:xdist -o addopts="" → 184 passed
bash scripts/dev/py.sh scripts/lore_reanchor.py --check → 0 âncora(s) quebrada(s), rc 0
bash scripts/dev/py.sh scripts/build_rumor_seeds.py --check → rc 0
bash scripts/dev/py.sh scripts/validate_content.py → 0 ERRO(S) · 0 AVISO(S)
varredura própria (scratchpad leakscan/pubscan): LEAK_PHRASES em data/*.json → só world_map:450; coocorrência em docs públicos → Nehla, Sylvenne, story_posturas:45
```

## Re-revisão — `1f059e04..5570a0fc` (2026-10-28)

**Veredito:** `CHANGES_REQUIRED` (R2-P1-1 e R2-P2-1/2 corrigidos depois: ver "Correções da re-revisão"). Resta 1 P1 novo, de cronologia. Ele foi introduzido pela correção do P1-5.

Conferido e fechado: P1-1 (`world_map.json:450` só com o lado público), P1-2 (`story_posturas.md:45`),
P1-3 (Nehla: o fato foi para `Segredo:`, o público ficou com "Mede o céu…"), P1-4 (Sylvenne sem Daruun no
público), P1-6 (`lingote_aco_vorr: 4` na Forja dos Clãs; a rota pode ser cumprida), P2-1 a P2-9.
A varredura própria refeita dá `LEAK_PHRASES` = 0 em `data/*.json` e 0 coocorrência Farol+Rede,
Daruun+Valerius ou "marcados" com Vane nos docs públicos (o Oráculo de Ferro, "o que o Farol contém",
fica como pista aceitável).

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R2-P1-1 | P1 | `lore_nova/timeline_completa.txt` (parágrafo do Livro do Protocolo, Era 7, e "Durou sessenta e seis anos" na Era 6), `lore_nova/daily_life.txt:318` × `lore_nova/npcs.txt:2459`, `lore_nova/npcs.txt:53` / `lore_nova/secrets.txt:48`, `lore_nova/secrets.txt:66` | Com o Livro aberto "quando Malagor despertou", a guerra passa a durar 66 anos (Ano 1–67). Só que o Dia Sem Sombra acontece **no instante** em que Malagor sai (`timeline:350`), ou seja, há 111 anos. Isso quebra pelo menos três passagens. (a) Sennar tem "cinquenta e muitos anos" e "viu as sombras se desconectarem quando era menino" (`npcs.txt:2459`): impossível, ele teria mais de 115. (b) Magda era "Sacerdotisa de alto nível **antes da guerra**" (`npcs.txt:53`, `secrets.txt:48`): hoje teria ~135 anos, mas é humana e descrita só como "senhora idosa". (c) Grum (humano, taverneiro na ativa) era Sargento da Guarda Real e viu o Rei morrer; funciona se o reino caiu no fim da guerra, mas fica no limite. Elaryin (elfo), os dragões, Brekmar, Ress (15 anos de Legião), a Landship (45 anos em "manutenção") e Valerius (lutou "sob Elaryin", podendo ter entrado tarde) não quebram. | Manter D1 (`YEAR_BASE` 112, Ano 1 = Livro do Protocolo) e **descolar a abertura do Livro do despertar de Malagor**: "o Livro corrente foi aberto quando o Monte da Perdição voltou a fumegar, décadas antes de Malagor sair dele". Assim a guerra volta a ser curta: Malagor e o Dia Sem Sombra perto do Ano 60, fim no 67. Tirar "Durou sessenta e seis anos…" da Era 6, ajustar `daily_life.txt:318` igual ("abriram quando o Monte voltou a fumegar") e o "a guerra começa no Ano 1" do parágrafo da Era 7. Teste: uma asserção de que o texto público não diz que a guerra começou no Ano 1. Com isso, Sennar (menino há ~52 anos) e Magda (~80) fecham. |
| R2-P2-1 | P2 | `lore_nova/npcs.txt:12` (Valerius, "História real") | "Passou a **década depois da guerra** rastreando Daruun, e no décimo ano de governo…": a década depois da guerra é 45→35, e o décimo ano de governo é há 30. R16 e `secrets.txt:12` dizem "a década seguinte" ao vácuo de Elaryin (41/40). | "Passou a primeira década de governo rastreando Daruun". |
| R2-P2-2 | P2 (follow-up) | `data/merchants.json:14`, `data/loot_tables.json:69` | Pendência apontada pelo executor. A Forja dos Clãs vende `art_coroa_pressao_rei_anao` (`unique`, épico) e o item também está no loot épico, enquanto E-08 põe a Coroa a bordo da LS-PFC-9, sob o gelo. **Não é P1:** está igual na `main`, não vaza segredo (a descrição do item é neutra) e mexer em estoque/loot é economia, fora do escopo de lore desta spec. Mesmo assim é contradição de canon que o jogador pode ver: comprar a Coroa em Skallgard. | Follow-up curto (spec de bestiário/loot G-14 ou uma bugfix): tirar a Coroa do `base_stock` da Forja e do loot `epico` e deixá-la como recompensa da Landship (quando existir). Se o coordenador quiser fechar já, remover a linha do `base_stock` é 1 linha sem efeito colateral. |

### Comandos (re-revisão)

```text
pytest tests/test_spec348_{leaks,canon,anchors}.py test_fase25 test_fase73 test_spec312_seeds test_spec313_catalog test_spec307_calendar test_spec303_festivals -p no:xdist -o addopts="" → 158 passed
lore_reanchor.py --check → 0 âncora(s) quebrada(s) · validate_content.py → 0 ERRO / 0 AVISO
leakscan (data/*.json) → 0 (fora o nome da entidade oculta do testamento) · pubscan farol+rede / daruun+valerius / marcados → sem vazamento
```

Depois de R2-P1-1 (só texto): migrate + `gen_world_living_npcs.py` + lint + reanchor + reindex. Pode entrar
como `APPROVED` sem nova rodada de revisão se a correção seguir a proposta acima e os testes focados ficarem verdes.

### Correções da re-revisão

- R2-P1-1: o Livro corrente do Protocolo abre no Ano 1, quando o Monte da Perdição volta a fumegar, décadas antes de Malagor; Malagor e o Dia Sem Sombra caem perto do Ano 60 e a guerra termina no 67 (guerra curta). Saíram "Durou sessenta e seis anos" (Era 6) e "a guerra começa no Ano 1" (Era 7); `daily_life.txt` ajustado; teste afirma que o texto público não diz que a guerra começou no Ano 1. Sennar, Magda e Grum fecham com ~52 anos desde o Dia Sem Sombra.
- R2-P2-1: Valerius passa "a primeira década de governo" rastreando Daruun.
- R2-P2-2: `art_coroa_pressao_rei_anao` fora do estoque da Forja dos Clãs e do loot épico; `test_spec298_economia_keeper` e `test_fase62` injetam a Coroa por monkeypatch para exercitar as regras de raro/único.
- Reindex da lore refeito (Jina); testes focados 991 passed.

## Fechamento (coordenador, 28/10)

R2-P1-1 foi aplicado conforme a proposta do revisor (commit `042732c6`): Livro aberto quando o Monte da Perdição
voltou a fumegar, Malagor e o Dia Sem Sombra perto do Ano 60, guerra terminando no 67. Também entraram R2-P2
(Valerius) e a saída da Coroa da loja e do loot. Os testes focados passam (`test_spec348_*`: 68), o lint dá 0
erro, `lore_reanchor --check` não acha âncora quebrada e o reindex de lore foi refeito. Pela cláusula do
revisor (linha 124): **APPROVED**.
