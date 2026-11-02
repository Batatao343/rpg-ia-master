# SPEC-350 — revisão independente (independent-review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Claude Opus 5.5 / papel Sol + revisor de lore (R18) · **Data:** 2026-11-02 · **Commit revisado:** `6c05c925`

## Escopo

`git diff main...spec-350` (58 arquivos): `services/plot_threads.py`, `services/plot_threads_lint.py`,
`services/leak_phrases.py`, `data/world/leak_phrases.json`, `services/content_validator.py`,
`services/npc_self.py`, `services/npc_world.py`, `config/flags.yaml`, `data/world/plot_threads.json`,
`data/graph/{edges,entities_extra}.json`, `data/world/npc_world.json`, os 14 docs `npcs/tramas/`, os 17 docs
`npcs/segredos/` novos, os 3 mundo vivo promovidos, `AUTORIA.md` + template, `tests/test_spec350_*`,
`tests/test_spec348_leaks.py`. Lore conferida por amostragem (Grep + offset): Rute (`daily_life.txt:146-151`),
Thrace (`npcs.txt:1294-1302`), Pardal (`npcs.txt:1388-1396`), Elaryin (`npcs.txt:80-93`), Pó de Sonho/Fada.
Fora: índice FAISS binário (só conferido pelo registro da §9), smoke real (não repetido).

Observação de nome: o critério de aceite de R18 cita `handoffs/SPEC-350-review.md`; este parecer usa o nome
pedido pelo coordenador (válido pelo template). Ajustar o critério ou copiar na conclusão.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/plot_threads.py:211-221` | `sheet_for_row` resolve por nome/alias **sem nenhum filtro de região ou de id canônico**. Sondado: NPC de runtime "Bento", "Caio", "Matias", "Tobias", "Pio", "Gaspar", "Aelis", "Rute" com `home_location_id: sk_porto` recebe a ficha de Nova Arcádia (desejo, medo, assunto que evita e "O que está em jogo" de outra pessoa). São nomes comuns que o LLM inventa em qualquer região; com a flag `on` o NPC errado ganha a trama, a voz e o tópico de segredo de outro. Bloqueia D6 (ligar a flag). | Só aceitar match por nome quando o `row` não tem id canônico diferente **e** a região do `row` (`home_location_id`/`location`) é a da trama da ficha (ou o `row` não tem local), ou quando `entity_identity.resolve_npc_entity_id` devolve o id do elenco. Teste: "Bento" em `sk_porto` → `None`; "Bors" em `na_anel_ferro` → Bors. |
| P1-2 | P1 | `services/npc_self.py:349-356` + fichas em `data/world/plot_threads.json` | R22 exige a linha "Há um assunto que você evita". O `_fit` corta do fim para o começo; com tags + rodapé (~105 caracteres) o orçamento útil do bloco é ~345. Sondado: a linha **some** em 8 de 39 fichas — `npc_doutor_silas_vane`, `npc_benedita_a_parteira`, `npc_bertil`, `npc_mestre_fundidor_kald`, `npc_arquimaga_sylvenne`, `npc_dama_vesperina`, `npc_lirio`, `npc_rato_de_ferro_tibb` (três delas guardam segredos da 348). O encurtamento registrado na §9 não bastou; `test_stake_line_after_identity_and_cut_by_budget` só confere o teto, não a presença. | Emitir o tópico antes da voz (cortar a voz primeiro) **ou** encurtar `voz.registro`/`fala` dessas 8; e acrescentar ao teste: para toda ficha do catálogo, `"assunto que você evita" in motivacoes`. Opcional: lint com o comprimento renderizado. |
| P1-3 | P1 | `data/codex/npcs/tramas/npc_tr_rute_corvo_veterana.md:25` | Contradiz a lore citada (R13 / rubrica 5). Lore: "A Legião marca os corpos que não são deles com tiza vermelha — **esses são os de Rute**." Doc: "marca com tiza vermelha os corpos que não são dela; **os demais** são de Rute" (inverte quem recolhe o quê). Doc público vai ao FAISS, então o narrador herda o erro. | "A Legião marca com tiza vermelha os corpos que não são dela; os marcados são de Rute." Reindex depois. |
| P2-1 | P2 | `data/codex/npcs/tramas/npc_tr_anselmo_tiza.md:31` | "Para ele, saber ler é coisa de oficial" quase entrega o segredo (não sabe ler); a rubrica 7 pede que o doc público não entregue. O lint R16c não pega porque "ler" tem < 5 letras. | Tirar a frase ou trocar por algo que não aponte para a leitura (ex.: "Para ele, papel bom é papel com selo"). |
| P2-2 | P2 | `data/world/plot_threads.json:459-471` | Pó de Sonho: `npc_pardal` (líder, aresta `leads quadrilha_telhados`) está em `borda` com `tier: ponte`, e a âncora da porta 3, `npc_velha_netta`, não está nem em `core` nem em `borda` da trama. A rubrica (d) e a 351 leem os membros pela trama. | Pardal em `core` (`tier: nucleo` ou mantém `ponte`, mas fora de `borda`); Netta em `borda`. Considerar lint: âncora de porta ∈ `core ∪ borda`. |
| P2-3 | P2 | `data/world/plot_threads.json:786` | Ysolt é Quebrada (aresta `hidden`), mas o desejo é "saber quem estava no quarto alugado onde um general élfico morreu", e a lore diz "Os Quebrados sabem quem estava no quarto" (`npcs.txt:93`). Dá para ler como membro novo que não sabe, mas fica no limite; e o desejo junto da trama do Pó insinua a causa oculta da morte de Elaryin. | Ou o desejo vira algo que ela já sabe e não pode dizer, ou o doc de segredo explica por que os Quebrados não contaram a ela. |
| P2-4 | P2 | `data/world/plot_threads.json:325,385,448,508` | 4 tramas com `secret_ids: []` apesar de a §3.6 citar segredos (aço que lembra E-05, Lista de Fornalha G-10, Coleção, causa da morte de Elaryin). Sem grupo de assinatura, R16a não guarda esses fatos; só R16c (palavras ≥ 5) protege. | Criar grupos em `leak_phrases.json` (ex.: `elaryin`: "overdose", "nao bebeu ate morrer"; `aco_lembra`) e citá-los nas tramas. Pode ir para a onda 2. |
| P2-5 | P2 | `services/plot_threads.py:345` (via `services/npc_world.py:216`) | `cast_npc_row` usa `npc_faction`, que lê `member_of` com `include_hidden=True`: Gaspar recebe `faction_id: encapuzados_fornalha` e Aelis/Ysolt `quebrados` (pertença secreta). Hoje nada consome a função; na 351 isso vai para o `row` e daí para rótulo de facção em combate (`faction_display`) e para o estado. | Na `cast_npc_row`, só arestas públicas (ou `thr.factions[0]`); teste com Gaspar. Registrar como restrição para a 351. |
| P2-6 | P2 | `services/npc_world.py:310` | O elenco entra no roster pelo id canônico, mas NPC materializado por nome ganha id `npc_<nome>` (`agents/npc.py:563`): "Rute" vira `npc_rute` ≠ `npc_tr_rute_corvo_veterana`. Os dois ficam no roster e a simulação pode mexer na Rute "fora de cena" enquanto ela está em cena. Já existia com `key_npcs`; R24 aumenta a superfície (39 ids). | Follow-up: dedupe no `_candidates` por `resolve_npc_entity_id`/`sheet_for_row`, ou a 351 semeia com `cast_npc_row` (id canônico). Medir no playtest de 50 turnos da §7. |
| P2-7 | P2 | `data/world/leak_phrases.json` / `tests/test_spec348_leaks.py:27` | O oráculo da 348 (`LEAK_PHRASES`) saiu do teste e virou dado editável pelo produto. Conferi: conteúdo idêntico ao removido (grupos e frases). O risco é para o futuro: um autor pode afrouxar a lista na mesma tarefa em que escreve conteúdo. | Teste que fixa um mínimo (contagem por grupo ou hash) ou caminho em `evals/protected-paths.txt`. |
| P2-8 | P2 | `scripts/validate_content.py:20-33` | `plot_threads` não está em `_ORDEM`; com 0 erro não aparece "[plot_threads] OK" e parece que o lint não roda (roda: `validate_plot_threads()` → 0 achados). | Acrescentar `"plot_threads"` à tupla. |
| P2-9 | P2 | `npc_tr_tobias_pena_seca.md` / `npc_tr_anselmo_tiza.md` (Como fala) | As duas vozes giram em torno de "artigo" ("Artigo nove, parágrafo dois…" × "Artigo… o artigo diz…"), na mesma região. Os dois vieram da §3.7 aprovada; o Jaccard passa. | Opcional: tirar "artigo" de um dos dois (Anselmo pode falar por ordem recebida, não por artigo). |

## Desvios do executor (§9) — julgamento

| Desvio | Julgamento |
|---|---|
| Téo com porta em `nova_arcadia` (R3 exige 2 locais) | **Aceito.** A casa dele no grafo já é `nova_arcadia`; mensageiro de telhados circula. Nota: o doc diz "Nas chaminés do Anel de Ferro", então a 351 deve abrir a porta dele no Ferro ou o doc citar a cidade alta. |
| Porta 3 do Pó de Sonho = Velha Netta (Pardal é líder, R5) | **Aceito** no conteúdo (curandeira do Lama, perto do Beco dos Desdentados, coerente). Falta pôr Netta em `borda` da trama (P2-2). |
| Canônicos sem doc de segredo como `ponte` | **Aceito.** R7 exige doc para `borda`; `ponte` é a leitura honesta de quem tem acesso ao núcleo. Netta, porém, é `ponte` e a spec §3.10 a mostrava `borda` com `segredo_doc_id`: aceitável, mas a ficha dela não tem doc de segredo para o tópico "o que ela dá aos marcados". |
| "Assunto que evita" encurtado | **Aceito no texto, insuficiente no efeito** (P1-2). |
| `secret_ids` aceitam grupos de `leak_phrases.json` | **Aceito.** Os grupos são exatamente os segredos da 348; o lint usa as frases do grupo como assinatura. Incompleto para os segredos sem grupo (P2-4). |
| `leak_phrases` em dado + serviço | **Aceito** (produção não importa de `tests/`); ver P2-7. |
| Fallback de nome de uma palavra ("Bors") | **Aceito só com o filtro de P1-1**; sem ele é a origem do bug. |

## Verificação dos pontos pedidos

1. **Vazamento:** nenhum fato oculto em campo público das tramas nem nos 14 docs públicos (lint R16 a/b/c verde; amostra manual de 14 docs × segredos). O prompt do NPC só recebe a própria ficha (desejo/medo/voz/tópico/papel da 1ª trama), nunca `pergunta`, outra trama nem o doc de segredo (`test_secret_never_literal_in_prompt`, `test_only_first_thread_stake_and_no_pergunta`). Ressalvas: P2-1, P2-3, P2-5.
2. **Flag off:** `_plot_sheet` e `_plot_region_cast` devolvem `None`/`[]` antes de qualquer leitura; `motive_lines(row, None)` = caminho antigo. Goldens e testes vizinhos intactos (229 verdes, abaixo). Aceito.
3. **ROSTER_CAP e ordem:** cap 60 intacto; elenco entra depois de party/queridos/líderes/conhecidos e antes de `key_npcs`, por id; `add` filtra mortos. Ver P2-6.
4. **GameState / save:** nenhum campo novo; `state.py` e `persistence.py` fora do diff; ficha resolvida em tempo de prompt; `visible_npc_view` sem campos da ficha (teste). Sem writer persistente novo. Aceito.
5. **Tom de Valoria:** forte. Desejos e medos verificáveis em cena, segredos como pequena traição ou decência que custa (Lalo, Rute, Téo, Caio são os melhores), vozes reconhecíveis numa fala. Sem "escolhido", sem termo proibido. Ressalvas: P1-3 (lore invertida), P2-1, P2-9; "Cê vai?" do Pio é coloquial demais para o registro geral, mas é criança: aceito.
6. **Integridade de eval:** nada em `evals/` nem em `protected-paths.txt`; `tests/test_spec348_leaks.py` só trocou a fonte do `LEAK_PHRASES` (conteúdo idêntico). Ver P2-7.
7. **Testes x critérios:** R1–R8, R15–R17, R20–R26, R28, R30 cobertos. Lacunas: presença do tópico (P1-2), match por nome fora da região (P1-1), âncora fora dos membros (P2-2), `cast_npc_row` com facção oculta (P2-5). `test_region_coverage_nova_arcadia` fica `skip` até a onda fechar (por desenho).
8. **Guards:** sem structured output novo; nenhum valor do LLM entra na ficha; `log_event` só registra o tipo da exceção.

## Rubrica R18 — por NPC (14 novos + 3 promovidos)

| NPC | Veredito | Motivo |
|---|---|---|
| Dalva Torneira | aprovado | |
| Cabo Anselmo Tiza | aprovado com ajuste | P2-1 (frase sobre ler), P2-9 |
| Rute, Corvo Veterana | **refazer** | P1-3 (inverte a regra da tiza da lore citada) |
| Tobias Pena-Seca | aprovado | P2-9 opcional |
| Pio Ferrugem | aprovado | |
| Ludovina Agulha | aprovado | |
| Gaspar Fole | aprovado | facção oculta: P2-5 |
| Lalo das Fichas | aprovado | |
| Matias Selo | aprovado | "não deve ser visto de luvas" insinua o irmão, mas o medo já é público pela §3.7 aprovada |
| Caio Pavio | aprovado | |
| Bento Juros | aprovado | |
| Aelis Sem-Ampulheta | aprovado | facção oculta: P2-5 |
| Dorotea Selo-Verde | aprovado | |
| Ysolt Fio-de-Vidro | aprovado com ajuste | P2-3 |
| Irena Prego-Frio (mv) | aprovado | |
| Mara do Sétimo Sino (mv) | aprovado | |
| Téo Chaminé (mv) | aprovado | segredo do pai é o melhor da onda |

Por trama: as 7 cumprem (a) pergunta sem resposta certa, (b) ≥ 3 portas que funcionam sozinhas, (c) instituição-armadilha no centro. (d) Pó de Sonho: P2-2 (Netta fora dos membros; Pardal líder na borda).

## Correções aplicadas

(nenhuma ainda; P1-1..P1-3 bloqueiam `done` e a decisão D6)

## Pendências

- P2-2, P2-3, P2-1, P2-8: corrigir junto com os P1 (baratos).
- P2-4: grupos de segredo novos → onda 2 ou spec de rumores (D11), dono: coordenador.
- P2-5: restrição para a SPEC-351 (`cast_npc_row` só com facção pública).
- P2-6: medir no playtest de 50 turnos da §7 antes de D6/D8.
- P2-7: decidir se `data/world/leak_phrases.json` entra em `evals/protected-paths.txt` (coordenador).

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -n 2 tests/test_spec350_{api,catalog,lint,npc_prompt,roster}.py tests/test_spec348_leaks.py → 78 passed, 1 skipped
bash scripts/dev/py.sh -m pytest -n 2 tests/test_spec304_{roster,review}.py tests/test_spec310_{no_leak,npc_prompt,npc_self,secret_topics}.py tests/test_spec348_{anchors,canon}.py tests/test_ambient_consumers.py tests/test_fase71.py tests/test_flag_registry.py → 229 passed
bash scripts/dev/py.sh scripts/validate_content.py → 0 ERRO(S); validate_plot_threads() → 0 achados
sonda sheet_for_row("Bento"/"Caio"/"Rute"/… em sk_porto) → ficha de Nova Arcádia (P1-1)
sonda npc_self_blocks para as 39 fichas → tópico cortado em 8 (P1-2); linha de trama presente em 39
```
