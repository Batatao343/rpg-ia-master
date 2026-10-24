# SPEC-306 — Expansão das tabelas de semente de NPC (+25 por tabela)

> **Status:** `done` (2026-10-24) — na main, revisão independente aprovada (ver handoff). smoke real §6.2 DeepSeek 24/10 (3 NPCs com RPG_SHARED_POOL=shadow e runtime isolado): cada NPC nasceu de semente única (profissão/raça/desejo/medo/contradição/maneirismo/fação) e a persona segue a semente; os 3 ficaram `held` no pool, como manda a 297. Leitura do dono das sementes (`review:"dono"`) segue pendente e bloqueia só `RPG_SHARED_POOL=on`.
> **Criada:** 2026-10-24 · **Atualizada:** 2026-10-24
> **Depende de:** SPEC-297 (semente estruturada R4–R6 + `validate_npc_seed_tables`; na `main`, `in-progress` — o código desta spec já está na `main`, só falta D8/smoke da 297, e esta spec **fecha o conteúdo** da D8).
> **Desbloqueia:** SPEC-297 D8 (revisão das tabelas) → `RPG_SHARED_POOL=on`; SPEC-304 (NPCs off-screen herdam desejo/medo da semente).
> **Tipo:** dados + testes + um script de revisão. **Não muda o motor** (`services/npc_seed.py` intocado).

---

## 1. Contexto & Objetivo

A SPEC-297 faz o motor sortear, em Python e de forma determinística, os ingredientes de todo NPC novo do pool (raça, origem, fação, profissão, desejo, medo, segredo pessoal, contradição, maneirismo). A LLM só costura o texto a partir desses rótulos (`agents/npc.py:476-498`, `services/npc_seed.py:119-148`). A variedade dos NPCs, portanto, é exatamente a variedade de `data/npc_seed_tables.json`.

Em 24/10 o dono revisou o rascunho (D8 da SPEC-297, `specs/SPEC-297-pool-compartilhado-entre-mundos.md:777-778`), aprovou e pediu **+25 entradas em cada uma das 6 tabelas** (+150 no total), fiéis à lore de Valoria.

Problemas atuais, com evidência:

| # | Problema | Evidência |
|---|---|---|
| P1 | Tabelas pequenas: professions 36, desires 20, fears 20, secrets 19, contradictions 17, mannerisms 20. `contradictions` está a 2 do mínimo de 15 do lint. | `data/npc_seed_tables.json:4-147`; `services/npc_seed.py:27` (`MIN_TABLE_ENTRIES = 15`) |
| P2 | `contradictions` e `mannerisms` não têm **nenhuma** entrada regional: um NPC de Brekmar e um de Skallgard tiram do mesmo saco. | `data/npc_seed_tables.json:107-146` (só filtros `races`) |
| P3 | Cobertura regional desigual. Profissões com 1 entrada regional (fora as restritas por raça/fação): `floresta_sussurros`, `skallgard`, `aethelgard`, `ophidia`, `montanhas_afiadas`. Segredos regionais: zero em `pantano_melancolia`, `deserto_zhur`, `floresta_sussurros`, `selva_xylos`, `aethelgard`, `pradaria_ruinas`. Desejos regionais: zero em `deserto_zhur`, `ophidia`, `costa_negra`, `brekmar`. Medos regionais: zero em `costa_negra`. | `data/npc_seed_tables.json:17-37`, `:56-62`, `:78-82`, `:101-104` |
| P4 | Tabela pobre gera NPCs parecidos e mais colisão de assinatura (re-sorteio até 5×, depois NPC só-local) e mais rejeição por near-duplicate no pool. | `services/npc_seed.py:169-184`; `specs/SPEC-297-pool-compartilhado-entre-mundos.md:749-751` |
| P5 | Nada impede, hoje, uma linha inalcançável: linha com `factions` cuja fação não pertence a nenhuma das `regions` da linha nunca é sorteada (o motor só escolhe fação da região, `npc_seed.py:109-111,129-130`, e `_allowed` exige o valor, `:89-93`). O lint não pega. | `services/content_validator.py:1314-1333` (só checa ids e tamanho) |
| P6 | Nada impede rótulo duplicado ou quase duplicado (mesmo sentido, palavras trocadas), nem rótulo universal que cita um lugar específico (ex.: "Brekmar" numa linha sem `regions`). | `services/content_validator.py:1319-1333` |
| P7 | Não existe uma forma de o dono revisar entradas novas fora do JSON cru. | — (ausência; nenhum `review`/página de revisão no repo) |

**Objetivo.** Acrescentar 150 entradas curadas (25 por tabela), com mistura deliberada de universais e restritas por região/raça/fação, cada uma com a fonte da lore citada; endurecer o contrato com testes determinísticos (ids, alcance, distribuição regional mínima, deduplicação por rótulo, nomes próprios só da lore pública); e gerar uma página Markdown de revisão do dono. Princípio do projeto preservado: o motor sorteia, a LLM narra (`docs/mundo-vivo/VISAO.md` § Restrições).

## 2. Requisitos

### 2.1 Volume e compatibilidade

- **R1 — +25 por tabela.** Depois da mudança: `professions` = 61, `desires` = 45, `fears` = 45, `secrets` = 44, `contradictions` = 42, `mannerisms` = 45. Teste: contagem exata por tabela.
- **R2 — Só acréscimo.** As 132 linhas existentes ficam byte a byte iguais (id, label, filtros, ordem). As novas entram **no fim** de cada lista. Motivo: sementes já gravadas no pool (staging `shadow`) referenciam esses ids (`services/shared_pool_validators.py:190-206`) e `seed_labels` resolve rótulo por id (`services/npc_seed.py:187-210`). Teste: hash sha256 das 132 linhas originais (JSON canônico, `sort_keys=True`, na ordem atual), congelado como constante no teste a partir da `main` (`02bcf0e1`).
- **R3 — Contrato da SPEC-297 continua verde.** `validate_npc_seed_tables()` sem erros (`services/content_validator.py:1298-1340`): ids de `regions`/`races`/`factions` existem, ≥ 15 por lista, ≥ 1.000 combinações por origem, id único entre tabelas. `tests/test_spec297_npc_seed.py` inteiro passa sem alteração.

### 2.2 Schema das linhas novas

- **R4 — Campos.** Toda linha nova tem:
  - `id` — `^[a-z0-9_]+$`, ASCII, com o prefixo da tabela: `prof_` · `des_` · `fear_` · `sec_` · `con_` · `man_` (mesma convenção das existentes, `data/npc_seed_tables.json:5-146`);
  - `label` — PT-BR, começa com minúscula, sem ponto final, 8–80 caracteres, legível isolado no prompt (é o que `seed_labels` entrega à LLM);
  - filtros opcionais `regions` / `races` / `factions` (lista não vazia quando presente);
  - `source` — **obrigatório nas novas**: `"lore_nova/<arquivo>.txt:<linha>"` ou `"data/<arquivo>.json:<linha>"`, apontando o trecho que ancora a entrada (o arquivo existe e tem pelo menos aquela linha);
  - `review` — `"dono"` em toda linha nova (pendente de leitura do dono; ver R14).
  Os campos extras `source`/`review` são ignorados pelo motor (`npc_seed.py` só lê `id`, `label`, `regions`, `races`, `factions`) e pelo lint atual.
- **R5 — Ids de lore canônicos.** `regions` = `data/origins.json` `regions[].id` (`data/origins.json:119-130`, os 12 ids) — é essa a fonte que o motor usa (`services/npc_seed.py:61,71`); `data/world_map.json` não tem lista `regions`, só `region_id` por local (35 ocorrências). `races` = `data/origins.json` `races[].id` (6 ids). `factions` = chaves de `data/factions.json` (19 ids).

### 2.3 Mistura e distribuição

- **R6 — Mistura por tabela (alvo ±2 por célula, piso duro nas colunas "mín.").** Categoria de uma linha, por precedência: tem `factions` → *fação*; senão tem `races` → *raça*; senão tem `regions` → *regional*; senão *universal*.

  | Tabela | universais (mín. 6) | regionais | raça (mín. 2) | fação (mín. 1) |
  |---|---|---|---|---|
  | professions | 6 | 14 | 3 | 2 |
  | desires | 10 | 10 | 3 | 2 |
  | fears | 10 | 10 | 4 | 1 |
  | secrets | 8 | 12 | 2 | 3 |
  | contradictions | 12 | 8 | 4 | 1 |
  | mannerisms | 10 | 10 | 4 | 1 |

  Teste: entre as 25 novas de cada tabela, universais ≥ 6, restritas (qualquer filtro) ≥ 10, raça ≥ 2, fação ≥ 1.
- **R7 — Piso regional (tabelas completas, antigas + novas).** Para cada uma das 12 regiões, contando linhas cujo `regions` contém a região e que **não** têm `factions` (filtro de raça permitido):
  - `professions` ≥ 3; `desires` ≥ 2; `fears` ≥ 2; `secrets` ≥ 2;
  - `contradictions` + `mannerisms` (somadas) ≥ 2.
  Teste paramétrico por região × tabela, com mensagem que diz a região e o déficit.
- **R8 — Cobertura por raça.** Cada um dos 6 ids de raça aparece em `races` de pelo menos 2 linhas **novas** (somando as 6 tabelas).
- **R9 — Toda linha é alcançável.** Para cada linha (antigas e novas) existe ao menos uma tupla `(region, race, faction)` com `region` ∈ 12 regiões, `race` ∈ 6 raças e `faction` ∈ `{None} ∪ compatible_factions(region)` (`services/npc_seed.py:109-111`) que passa nos três filtros. Em particular: linha com `factions` só lista fações cuja região (`factions.json` `region`, resolvida por `npc_seed._lore()["faction_region"]`, `:62-64`) está nas `regions` da linha (ou a linha não tem `regions`). Fações de regiões sem fação no motor (`floresta_sussurros`, `ophidia`, `costa_negra`) não podem ser exigidas.

### 2.4 Qualidade e fidelidade à lore

- **R10 — Sem duplicata semântica simples.** Dentro de cada tabela (antigas + novas): (a) nenhum par com rótulo normalizado igual (casefold, sem acento, espaços colapsados); (b) nenhum par com Jaccard ≥ 0,6 entre os conjuntos de tokens normalizados sem stopwords PT (`de, do, da, dos, das, o, a, os, as, um, uma, que, e, em, no, na, nos, nas, por, para, com, se, seu, sua, ao, à`); (c) nenhum par em que um conjunto de tokens (≥ 3 tokens) está contido no outro. Falso positivo legítimo vai para `_SIMILAR_OK = {(id_a, id_b): "<motivo>"}` no próprio teste, com motivo — no máximo 5 pares.
- **R11 — Nome de lugar exige filtro coerente.** Se o rótulo normalizado contém o nome normalizado de uma região (`origins.json` `regions[].name`) ou de um local de `world_map.json` com nome de ≥ 2 palavras ou ≥ 6 letras, a linha precisa ter `regions` contendo a região correspondente (via `region_id` do local). Se contém o nome de uma fação de `factions.json` (`name` sem artigo inicial), a linha precisa ter `factions` com essa fação **ou** `regions` contendo a região dela. Nenhuma linha universal cita lugar ou fação.
- **R12 — Nomes próprios só da lore pública.** Toda palavra do rótulo que começa com maiúscula (fora a posição 0) precisa aparecer, com a mesma grafia, no corpo de pelo menos um doc do Codex com `visibility: public` (lido por `services/codex_loader.parse_codex_file`, `services/codex_loader.py:27`) ou nos `name` de `origins.json`/`factions.json`. Isso barra nome inventado e nome que só existe em material `hidden`/`secret` (ex.: `lore_nova/secrets.txt`, `data/codex/npcs/segredos/`).
- **R13 — Segredo pessoal, nunca segredo do mundo.** A tabela `secrets` descreve segredos **do NPC** (escala pessoal: dívida, nome falso, doença escondida, lealdade dupla). Nenhuma linha revela verdade de lore marcada como oculta. Regra operacional para o autor das linhas: antes de escrever, consultar só as tags de `lore_nova/secrets.txt` (`Grep '^\[TAGS: '`, linhas 7–287) e não tocar nos temas listados ali; nunca usar rótulos de `NPC_SECRET_LABELS` (`services/content_validator.py:66-80`) seguidos de `:` (o validador do pool barra isso no texto gerado, `services/shared_pool_validators.py:317-320`). Verificação: revisão independente (§5) + R12.

### 2.5 Revisão do dono

- **R14 — Página de revisão gerada.** `scripts/npc_seed_review.py build` gera `docs/revisao/SPEC-306-sementes-npc.md` a partir do JSON (nunca editado à mão). Conteúdo: cabeçalho com totais por tabela/categoria e a matriz região × tabela de R7; depois, por tabela, uma tabela Markdown só com as linhas `review: "dono"`: `[ ]` · `id` · rótulo · filtros legíveis (nomes de região/raça/fação, não ids) · `source`. No fim, 10 NPCs de exemplo por região sorteados offline (`roll_npc_seed` com `game_id="review-306"`, `turn=0..9`, `location_id` = primeiro local da região) com os rótulos, para o dono "sentir" a mistura.
- **R15 — Página nunca fica velha.** `scripts/npc_seed_review.py check` sai com código 1 se o arquivo gerado difere do que `build` produziria. Teste chama a função `render_review()` e compara com o arquivo versionado.
- **R16 — Aprovação.** `scripts/npc_seed_review.py approve --ids <id ...>` ou `--all` remove o campo `review` das linhas indicadas e regrava o JSON no formato canônico (R17), com `newline="\n"` (lição CRLF de 23/10, `ESTADO_ATUAL.md` § Notas). O coordenador roda quando o dono disser "aprovo as sementes" (ou a lista de ids aprovados); ids que o dono rejeitar são **editados** (rótulo/filtro) enquanto ainda estão `review`, nunca apagados depois de aprovados (R2 passa a valer para eles).
- **R17 — Formato canônico do JSON.** Uma linha por entrada, como hoje (`data/npc_seed_tables.json:5`): `{"id": ..., "label": ..., "regions": [...], "races": [...], "factions": [...], "source": ..., "review": ...}` nessa ordem de chaves, campos ausentes omitidos, `ensure_ascii=False`, indentação de 2/4 espaços igual à atual, LF. `dump_tables(load(path)) == bytes do arquivo` (teste de round-trip). `_comment` atualizado (deixa de dizer "RASCUNHO do executor"; passa a citar SPEC-297 D8 + SPEC-306 e o significado de `source`/`review`); `version` → 2 (não é lido pelo motor; `grep version services/npc_seed.py` vazio).

### Fora de escopo

- Qualquer mudança em `services/npc_seed.py` (sorteio, `FACTION_CHANCE`, pesos, `MAX_REROLLS`, raças não jogáveis, raridade por linha). O motor continua tratando todas as linhas igualmente, inclusive as `review: "dono"` (ver D1).
- Mudar os limites do lint (`MIN_TABLE_ENTRIES`, `MIN_COMBINATIONS_PER_ORIGIN`).
- Prompt de geração do NPC (`agents/npc.py:_pool_generation_prompt`) e validadores do pool.
- Novas tabelas (ex.: aparência, voz, nome) ou novos campos na `NpcSeed`.
- Ligar `RPG_SHARED_POOL=on` (decisão separada, depois de D8 + smoke da SPEC-297).
- Coerência raça × fação não humana (ex.: NPC humano sorteado com fação `goblins_mineiros`): é comportamento do motor; vira follow-up se o dono quiser (D2).
- Página de revisão dentro do app web; a revisão é um Markdown no repo.
- Remover/renomear linhas existentes.

## 3. Design técnico

### 3.1 Arquivos

- **Alterado — `data/npc_seed_tables.json`:** +150 linhas (25 por tabela, no fim de cada lista), `_comment` e `version` (R17). Nenhuma linha antiga muda.
- **Novo — `scripts/npc_seed_review.py`:** CLI `build | check | approve | sample`. Funções puras importáveis:
  - `load_tables(path: str = SEED_TABLES_PATH) -> dict`
  - `dump_tables(tables: dict) -> str` — formato canônico (R17)
  - `classify(row: dict) -> Literal["universal", "regional", "raca", "facao"]` — precedência de R6
  - `regional_matrix(tables: dict) -> dict[str, dict[str, int]]` — região → tabela → contagem de R7
  - `render_review(tables: dict) -> str` — conteúdo de `docs/revisao/SPEC-306-sementes-npc.md` (R14), determinístico (sem data/hora no corpo; a data vem do `version`/commit)
  - `approve(tables: dict, ids: set[str] | None) -> dict` — remove `review` (None = todas)
  - `sample(region: str, n: int) -> list[dict[str, str]]` — `seed_labels(roll_npc_seed(...))` offline
  Só lê dados; zero LLM, zero rede. Roda via `bash scripts/dev/py.sh scripts/npc_seed_review.py …`.
- **Novo — `docs/revisao/SPEC-306-sementes-npc.md`:** gerado por `build` (R14/R15).
- **Novo — `tests/test_spec306_npc_seed_expansion.py`:** R1–R12, R15, R17 (detalhe na §4).
- **Alterado (pequeno) — `services/content_validator.py` `validate_npc_seed_tables`:** acrescenta como `error` só as invariantes baratas e não heurísticas, para valerem em edições futuras via `scripts/validate_content.py`: prefixo de id por tabela (R4), rótulo normalizado duplicado na mesma tabela (R10a) e linha inalcançável (R9). Jaccard (R10b/c), R11 e R12 ficam **só no teste** (heurísticos ou caros: leem o Codex). Não muda nenhum limite.

### 3.2 Exemplos de formato (ids e filtros reais; rótulos ilustrativos — o executor escreve os definitivos)

```json
{"id": "prof_lavador_das_chamines", "label": "lavador de roupa da Rua das Chaminés", "regions": ["nova_arcadia"], "source": "lore_nova/daily_life.txt:98", "review": "dono"},
{"id": "des_ser_lider_de_caca", "label": "liderar a próxima grande caçada do vilarejo", "races": ["race_osshari"], "source": "lore_nova/races.txt:296", "review": "dono"},
{"id": "fear_parar_na_selva", "label": "dormir parado e acordar com raízes no corpo", "regions": ["selva_xylos"], "source": "lore_nova/locations.txt:171", "review": "dono"},
{"id": "sec_deve_ao_navio", "label": "deve uma decisão ao navio das docas centrais e ainda não pagou", "regions": ["brekmar"], "factions": ["poder_kahen"], "source": "lore_nova/locations.txt:431", "review": "dono"},
{"id": "con_sem_dor_cuidadoso", "label": "não sente dor, mas trata cada ferida alheia com cuidado exagerado", "races": ["race_cinzeus"], "source": "lore_nova/races.txt:235", "review": "dono"},
{"id": "man_lenco_molhado", "label": "leva um lenço molhado ao rosto mesmo longe das fundições", "regions": ["nova_arcadia"], "source": "lore_nova/locations.txt:59", "review": "dono"}
```

(Os exemplos acima passam por R11: "Rua das Chaminés" exige `nova_arcadia`; o de Brekmar não nomeia Kahen, mas tem `factions` coerente com a região, `data/factions.json:213-217`.)

### 3.3 Âncoras de lore por região/raça/fação (ponto de partida do executor)

Ler **só** as linhas citadas (Read com offset/limit) ou Grep; nunca o arquivo de lore inteiro (AGENTS.md § O que NÃO fazer). Cada entrada nova cita uma destas fontes (ou outra encontrada por Grep) em `source`.

| Região / grupo | Âncoras (escala de gente comum) | Fonte |
|---|---|---|
| `nova_arcadia` | três anéis e identificação na entrada; escambo × moeda de Valerius; Tosse de Ferro e lenço molhado; Anel de Lama fora do Código; cotidiano (lavador, parteira, criada, nobre em declínio, guarda de nobre, criança de rua, viciado em pó); fações `legiao_ferro`, `mao_sombria`, `filhos_chama_azul` | `lore_nova/locations.txt:17-19,28,59,73`; `lore_nova/daily_life.txt:6-176`; `lore_nova/factions.txt:12,35,56` |
| `pantano_melancolia` | estacas que medem a borda (cresce ~5 m/ano); chá dos Druidas; espólio da batalha final na lama; vontade de deitar na água; fações `druidas_ciclo_cinzento`, `druidas_renegados` | `lore_nova/locations.txt:101,111,114,116`; `lore_nova/factions.txt:430,449` |
| `deserto_zhur` | lentes de obsidiana; miragens de parentes mortos; Tempestades de Navalha; escorpiões de cristal; o som sem nome da borda sul; `tribos_devoradores_sol` | `lore_nova/locations.txt:127-135`; `lore_nova/daily_life.txt:278`; `lore_nova/factions.txt:491` |
| `floresta_sussurros` | vozes de mortos conhecidos; Pó de Sonho (fungo vermelho); Urso-de-Espinha e feridas que não fecham; fronteira com Xylos que criaturas não cruzam | `lore_nova/locations.txt:146-152` |
| `selva_xylos` | chuva ácida e metal corroído; ciclo acelerado (parar atrai raízes); cidades nas copas; resina dos Hospedeiros; Néctar da Fúria; o limite que se move; `colmeia_hospedeiros` | `lore_nova/locations.txt:166-171,187,198,201,210`; `lore_nova/daily_life.txt:266`; `lore_nova/factions.txt:469` |
| `skallgard` | seis meses de noite e aurora verde; clãs tecnológicos × de combate; desprezo por "vidas quentes"; Vrel aceitos nos conselhos; estátuas conscientes de Vorr; óleo de leviatã como combustível; caçador do ermo, leitora da Câmara do Sinal; `clas_combate`, `renegados_ermo` | `lore_nova/locations.txt:221-227,329`; `lore_nova/races.txt:197`; `lore_nova/daily_life.txt:194,206`; `lore_nova/factions.txt:150,192` |
| `aethelgard` | O Lago e os mergulhadores; peixes cujas escamas induzem visões; plantas que perturbam a magia; Afogados em rotas regulares; a entrada seca que só poucos velhos conhecem; `cultistas_destilacao` | `lore_nova/locations.txt:239-253`; `lore_nova/daily_life.txt:290`; `lore_nova/factions.txt:513` |
| `ophidia` | "ninguém vem de Ophidia" — o NPC *jura* que veio; mapas contraditórios; ilhas que mudam de posição; barcos que somem do registro; mercado de informação em Brekmar | `data/origins.json:126`; `lore_nova/locations.txt:283-293` |
| `costa_negra` | caranguejeiros e as cicatrizes de explosão de gás; tocha na abertura errada; âmbar cinza; óleo e osso de leviatã para quilhas; Éter cristalizado; o Trono "não terminou de morrer"; Sombra de Leviatã | `lore_nova/locations.txt:308,320,327-338`; `lore_nova/daily_life.txt:302` |
| `montanhas_afiadas` | passagens sem pedágio (postos que sumiram); rotas que mudam e saídas a dezenas de km; guias Cinzéus; Orcs e Goblins das saídas baixas; A Boca; rumor do Oubliette; `bandos_orc_saidas_baixas`, `goblins_mineiros`, `ultimos_anoes_reino` | `lore_nova/locations.txt:353-367`; `lore_nova/daily_life.txt:218`; `lore_nova/factions.txt:374,393,410` |
| `pradaria_ruinas` | fundações que afloram; frases Cinzéus em pedra; Vaelorn (mercado mágico, arquivo de memória); Solvhen (silêncio); nômade: ameaça ou comércio; espectros das ruínas; `bandos_nomades`, `mercadores_escravos_pradaria`, `cidades_estado_sobreviventes_vaelorn_solvhen` | `lore_nova/locations.txt:379-407`; `lore_nova/daily_life.txt:230`; `lore_nova/factions.txt:315,334,354` |
| `brekmar` | sem leis, reputação como regulador; Kahen arbitra do navio; hub do que o Código de Ferro proíbe; Osshari nas docas, Vrel vendendo informação; estratificação por reputação marítima; Casa das Marés; `poder_kahen`, `grupos_piratas_rivais`, `osshari_brekmar` | `lore_nova/locations.txt:429-450`; `lore_nova/daily_life.txt:242,254`; `lore_nova/factions.txt:214,252,274,293` |
| `race_anoes_fuligem` | protocolo e registro; Landships (código LS-PFC, sem nomes); reuniões de análise de falha; luto sem vocabulário; respirador e óculos | `lore_nova/races.txt:111-143` |
| `race_vrel` | acordar com memória de batalha não travada; falar uma língua por algumas horas; sobrescrever memórias alheias; solitários; funcionários de Landship | `lore_nova/races.txt:176-195` |
| `race_cinzeus` | sem dor física (quebra osso sem saber); escreve nas paredes; túmulos com canções acrescentadas por gerações | `lore_nova/races.txt:235-247` |
| `race_osshari` | padrão de escamas único; pinturas por contexto; fome de intensidade; liderança por caça; Osshari de mar × de rio | `lore_nova/races.txt:286-306` |
| `race_elfos` | a Ampulheta (morte súbita); Fome de Sentir; memória individual acima de tudo; condescendência com Vrel | `data/origins.json:28,34`; `lore_nova/races.txt:77` |
| `race_humanos` | Inundação; Improviso; culturas (Andarilhos, Piratas) | `data/origins.json:9,15`; `lore_nova/races.txt:341-352` |

Temas adultos (vício, tráfico de pessoas, "mão de obra não especializada" dos Anões, `lore_nova/races.txt:134-136`) entram só em escala pessoal e tom sóbrio (D3).

## 4. Plano passo a passo

> Ambiente: worktree `C:\Users\guilh\AppData\Local\Temp\claude\rpg-spec-306`; Python sempre `bash scripts/dev/py.sh …`. Máquina com pouca RAM: rodar **só** os arquivos de teste desta spec + `tests/test_spec297_npc_seed.py`, nunca a suíte inteira (o coordenador roda 1× no `/spec-land`).

### Etapa 1 — Testes do contrato (vermelhos)

1. **Testes** (`tests/test_spec306_npc_seed_expansion.py`):
   - `test_table_sizes_after_expansion` — R1 (contagens exatas).
   - `test_original_rows_untouched` — R2: primeiras 36/20/20/19/17/20 linhas de cada tabela, JSON canônico, sha256 == constante gravada a partir da `main` `02bcf0e1` (calcular uma vez nesta etapa e colar no teste).
   - `test_new_rows_schema` — R4: prefixo, regex do id, label (minúscula inicial, sem ponto final, 8–80), `source` com arquivo existente e linha ≤ nº de linhas do arquivo, `review == "dono"`.
   - `test_new_rows_mix` — R6 (pisos), `test_race_coverage_new_rows` — R8.
   - `test_regional_floor[region-table]` — R7, paramétrico (12 × 5), mensagem com déficit.
   - `test_every_row_reachable` — R9 (antigas e novas).
   - `test_no_semantic_duplicates` — R10 (a/b/c) com `_SIMILAR_OK` (≤ 5 pares, motivo obrigatório).
   - `test_place_names_require_filters` — R11.
   - `test_proper_nouns_from_public_codex` — R12.
   - `test_validator_green` — R3 (`validate_npc_seed_tables()` sem erro) + `test_validator_flags_unreachable_and_dup_label` (tabela sintética em `tmp_path` com linha `factions=["legiao_ferro"]`, `regions=["brekmar"]` e dois rótulos iguais → erros esperados).
2. **Verificação:** os testes de contagem/mix/piso falham; R2, R9–R12 já passam nas 132 linhas atuais (se R11/R12 acusarem linha antiga, **não** editar a linha — registrar no hand-back e pôr em `_SIMILAR_OK`/allowlist análoga com motivo; decisão do dono).

### Etapa 2 — Script de revisão e formato canônico

1. **Testes** (`tests/test_spec306_npc_seed_review.py`):
   - `test_dump_roundtrip_is_byte_identical` — R17 (no arquivo atual da `main` e no expandido).
   - `test_classify_precedence` — R6 (linha com `factions`+`regions` = fação; `races`+`regions` = raça).
   - `test_regional_matrix_counts` — tabela sintética pequena.
   - `test_render_review_lists_only_pending_and_is_deterministic` — duas chamadas iguais; linha sem `review` não aparece na seção de pendentes; filtros aparecem por **nome** ("Brekmar", "Osshari").
   - `test_review_page_is_fresh` — R15: `render_review(load_tables())` == `docs/revisao/SPEC-306-sementes-npc.md`.
   - `test_approve_removes_review_only_for_ids` — R16; `approve(..., None)` limpa todas; demais campos intactos.
2. **Implementação:** `scripts/npc_seed_review.py` (§3.1), escrita com `open(..., "w", encoding="utf-8", newline="\n")`.
3. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_spec306_npc_seed_review.py -q`.

### Etapa 3 — Dados (+150 linhas)

1. Para cada tabela, nesta ordem: `contradictions` (mais perto do piso), `mannerisms`, `secrets`, `fears`, `desires`, `professions`. Antes de escrever uma tabela: Grep das âncoras de §3.3 (só as linhas citadas) + Grep das tags de `lore_nova/secrets.txt` (R13). Escrever as 25 linhas no fim da lista, com `source` e `review: "dono"`, cobrindo primeiro os déficits de R7 (P3) e depois a mistura de R6.
2. Rodar após cada tabela: `bash scripts/dev/py.sh -m pytest tests/test_spec306_npc_seed_expansion.py -q -x` (falha só das tabelas ainda não feitas) e `bash scripts/dev/py.sh scripts/npc_seed_review.py check` — formatar com `dump_tables` se o round-trip falhar.
3. Atualizar `_comment` e `version` (R17).
4. **Verificação:** `tests/test_spec306_*.py` + `tests/test_spec297_npc_seed.py` verdes; `bash scripts/dev/py.sh scripts/validate_content.py` sem erro novo.

### Etapa 4 — Lint permanente e página

1. **Implementação:** extensão de `validate_npc_seed_tables` (§3.1: prefixo, rótulo duplicado, alcance). Os testes de Etapa 1 (`test_validator_*`) passam.
2. `bash scripts/dev/py.sh scripts/npc_seed_review.py build` → `docs/revisao/SPEC-306-sementes-npc.md`; `check` sai 0.
3. **Verificação:** `tests/test_spec306_*.py`, `tests/test_spec297_npc_seed.py`, testes do `content_validator` que citam `npc_seed` (Grep `validate_npc_seed_tables` em `tests/`). Nada além disso localmente.

### Etapa 5 — Revisão independente e hand-back

1. Revisor (outro agente, Opus) lê **a página** `docs/revisao/SPEC-306-sementes-npc.md` + amostra de `source` (≥ 20 linhas conferidas contra o trecho citado) e marca: fidelidade à lore, R13 (nada de segredo do mundo), tom. Registro em `handoffs/SPEC-306-review.md`.
2. Hand-back do executor: contagens, matriz R7, linhas antigas que R11/R12 acusaram (se houver), link da página.

## 5. Critérios de aceite

- [x] R1: tabelas com 61/45/45/44/42/45 entradas.
- [x] R2: 132 linhas originais idênticas (hash).
- [x] R4–R9: schema, mistura, piso regional (matriz 12 × 5 sem déficit), cobertura por raça, todas as linhas alcançáveis.
- [x] R10–R12: sem duplicata semântica simples; nome de lugar/fação com filtro coerente; nomes próprios só da lore pública.
- [x] R13: revisão independente confirma que nenhum `secrets` revela segredo de lore (`handoffs/SPEC-306-review.md`).
- [x] R14–R17: `docs/revisao/SPEC-306-sementes-npc.md` gerada e fresca; `approve` funciona; JSON canônico (round-trip) e LF.
- [x] `validate_npc_seed_tables()` e `scripts/validate_content.py` sem erro; `tests/test_spec297_npc_seed.py` verde sem alteração.
- [x] `uv run pytest` verde (suíte completa offline, **rodada pelo coordenador** no `/spec-land`).
- [x] Guard de FallbackLLM: n/a (nenhum `with_structured_output` novo).
- [x] Saves antigos continuam carregando: n/a para saves; sementes já gravadas no pool continuam resolvendo rótulo (R2).
- [x] Smoke §6 executado.
- [x] Dono leu a página (linhas `review: "dono"` aprovadas via `approve`, ou ajustadas) — **não bloqueia `done`** desta spec (D1); bloqueia `RPG_SHARED_POOL=on`.

## 6. Smoke test

A mudança é de dados, mas os rótulos vão para o prompt da LLM (`agents/npc.py:487,497`), então há um smoke real curto.

1. **Offline (obrigatório, zero custo):** `bash scripts/dev/py.sh scripts/npc_seed_review.py sample --region <r> --n 10` para `brekmar`, `skallgard`, `ophidia` e `selva_xylos`. Conferir a olho: nenhuma combinação absurda (ex.: profissão de deserto em Skallgard), mistura de universais e regionais, sem rótulo repetido nas 10.
2. **Real (3 requests, DeepSeek, staging-like local):** com `RPG_SHARED_POOL=shadow` e um `game_id` de teste, chamar `generate_new_npc` 3 vezes em locais de regiões diferentes (um de `brekmar`, um de `skallgard`, um de `pradaria_ruinas`), escolhendo `turn` para que a semente tenha ao menos uma linha nova (conferir com `roll_npc_seed` antes). Verificar: persona usa profissão/desejo/maneirismo da semente; `segredo_pessoal` não aparece na descrição pública (validador do pool, `services/shared_pool_validators.py:317-320`, sem achado); zero `FallbackLLM`. Custo esperado: < US$ 0,01.
3. Registrar no cabeçalho da spec: regiões, ids novos sorteados, resultado.

## 7. Riscos & compatibilidade

- **Determinismo muda de valor, não de propriedade.** Com listas maiores, `rng.choice` (`services/npc_seed.py:136`) devolve outra linha para o mesmo `(game_id, turn, location_id, slot)`. Mesma entrada continua dando a mesma semente (teste da 297), mas uma semente calculada antes do pouso não é reproduzida depois. Nada no produto recalcula sementes antigas: a `NpcSeed` é gravada na entrada do pool e só os ids são revalidados (`shared_pool_validators.py:190-206`), e R2 garante que eles continuam existindo.
- **Colisão de assinatura cai.** Mais combinações por origem → menos re-sorteio (R6 da 297) e menos NPC só-local. Ganho, não risco.
- **Linhas `review: "dono"` vivas antes da leitura do dono.** Em staging `shadow` elas já aparecem em NPCs novos. Mitigação: revisão independente obrigatória (Etapa 5) e decisão D1.
- **Heurística de duplicata** (R10b/c) pode dar falso positivo; válvula `_SIMILAR_OK` limitada a 5 pares com motivo.
- **R12 lê o Codex inteiro no teste** (só parse de frontmatter + corpo, sem FAISS): alguns segundos; aceitável numa suíte que já roda `validate_content`.
- **CRLF:** o script grava com `newline="\n"`; o teste de round-trip pega regressão.
- **MockLLM/FallbackLLM:** sem impacto (nenhum caminho LLM novo).
- **Quota/latência:** zero no jogo (rótulos curtos; o bloco de semente no prompt cresce poucos tokens).

## 8. Decisões que o dono precisa tomar (defaults propostos)

- **D1 — Linhas novas valem antes da sua leitura?** Default: **sim** — entram no sorteio assim que pousam (o motor não muda, e hoje o pool só está em `shadow` no staging); sua leitura da página bloqueia só o `RPG_SHARED_POOL=on`. Alternativa: só pousar depois da sua leitura.
- **D2 — Fações não humanas (`bandos_orc_saidas_baixas`, `goblins_mineiros`) em linhas de semente?** O motor pode sortear um NPC de raça jogável com essas fações. Default: **não** usar essas duas fações em linhas novas e abrir follow-up de motor se você quiser coerência raça × fação.
- **D3 — Temas adultos** (vício em pó de sonho, tráfico de pessoas na Pradaria, servidão nas Landships). Default: **permitidos** em escala pessoal e tom sóbrio, sem descrição gráfica.
- **D4 — Origem `ophidia`:** default **as entradas tratam a origem como alegação** ("jura que veio de Ophidia"), coerente com `data/origins.json:126`.
- **D5 — Aprovação em bloco:** quando você disser "aprovo as sementes" (ou listar ids), o coordenador roda `npc_seed_review.py approve`. Ids que você recusar são reescritos antes da aprovação, nunca apagados depois.
