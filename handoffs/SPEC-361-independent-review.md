# SPEC-361 — revisão independente (conteúdo + Sol técnico)

> **Veredito:** `CHANGES_REQUIRED` (2 achados P1, ambos pequenos; o conteúdo, ou seja catálogo e prompt, está **aprovado**)
> **Revisor:** spec-reviewer Opus (conteúdo) + Sol (técnico), agente que não escreveu o código · **Data:** 2026-11-02 · **Commit revisado:** `2a6e614d` (branch `spec-361`, base `830fb496`)

## Escopo

Revisei `git diff 830fb496..spec-361` (commits `90c98a72`, `7b437899`, `2a6e614d`, 28 arquivos).
Li por inteiro `data/bestiario/modificadores_trama.yaml`, `services/creature_gen.py` (prompt, schema,
gate, prazo, orquestrador), `services/creature_gen_eval.py`, o diff de `services/shared_pool*.py`,
`agents/bestiary.py`, `agents/combat.py`, `services/art_brief.py`, `state.py` e `config/flags.yaml`,
além de 11 fichas reais de `docs/spec361/eval-depois-2026-11-02.json`.
Ficaram fora: `mock_llm.py` (só o builder, lido por alto), os detalhes de
`scripts/bestiario/eval_geracao.py` e o smoke §6, passos 2 a 5 (são do coordenador).
A latência do DeepSeek não entra como achado; comento só o que no código piora a latência.

---

## Parte 1 — Conteúdo (catálogo de modificadores e texto do prompt)

**Veredito do conteúdo: APROVADO**, com os nits P2 abaixo. Isto cumpre a "revisão independente
do catálogo e do prompt" que estava pendente em §9 e no aceite R5/§3.4.

**Catálogo (14 modificadores).** Atende o critério do dono:
- **Corpo físico, com a corrupção no corpo.** Todos os textos de aparência e telegrafo são
  visíveis e anatômicos ("pele rachada em placas soltas, ferrugem escorrendo das juntas",
  "poeira caindo para cima em volta do corpo", "marcas de grade no couro, uma argola de ferro presa
  numa perna").
- **Nada conceitual nem mecânico.** Não há dígito nem jargão de Cartas.
- **Tom de Valoria.** Praga com "uma semana" de Benedita, Éter de fornalha rachada, borda do
  Abismo, resíduo de apetite. Os epítetos são de trama ("da Última Semana", "do Bando Morto",
  "de Arreio"), e nenhum é marcador de tamanho ou idade (U5 ok).
- **Sem reskin.** A variante é a base marcada pela história. A espécie nova continua passando pelo
  gate.
- `familias` e `proibido_com` estão coerentes: `tomado_de_apetite` não se aplica a
  `demonio_encarnado`; `afogado_e_devolvido` não se aplica a quem voa.
- `faminto_de_escassez`, `fugido_da_jaula` e `desperto_do_gelo` são os mais "genéricos de fantasia".
  Como modificador são aceitáveis, porque a base de Valoria carrega a identidade.

**Prompt (PAPEL/REGRAS, few-shot, trama, eixos livres).** Está em português, curto e concreto. Pede
família com lore, ≥ 3 partes do corpo, a proibição de "presença/sem forma", nome sem manual nem
marcador de variante, zero número, telegrafo com `{nome}` e contra-jogo pelo corpo.

Nada `hidden`/`secret` entra no prompt:
- a lore usa `query_rag(..., max_visibility="public")`;
- `motivo_trama` passa por `_sem_segredo` e remove `<`/`>`;
- a lista de demônios e emoções vem de codex `visibility: public` (conferi Veleth, Fehk, Morvath,
  Skarath e Thessavar);
- a paleta e os nomes de facção vêm das fichas da 349.

A entrada do jogador entra delimitada: `sanitize_entity_name` → `wrap_player_input`, com
`PLAYER_INPUT_RULE` no system nas duas tentativas.

As 11 fichas reais lidas são físicas, ancoradas no lugar e na trama, e sem genérico. Exemplos:
"Bexiga de Odre Podre" (os odres dos Devoradores de Sol "começaram a pesar sozinhos"), "Cobrado de
Vidro Oco" (Farol, chama negra; codex público) e "Rói-Casco de Brekmar" (junta mole na barriga como
contra-jogo).

---

## Parte 2 — Técnico (Sol)

Pontos conferidos e ok:
- **LLM e guard.** O LLM só é chamado via `get_llm(temperature=0.7, tier=FAST)`
  (`creature_gen.py:1353`). O guard `isinstance` está em `_resposta_para_ficha` (`:1456-1466`),
  com `try` amplo em `_invocar` (`:1358-1367`). `FallbackLLM`/`AIMessage` vira `SCHEMA` e depois
  fallback, sem exceção.
- **Número do LLM.** Nenhum número do LLM entra no template: `ficha_para_template` usa só tabelas
  Python, e `padrao`/`categoria`/`arquetipo` são filtrados por enum.
- **Fluxo.** O fluxo existente → variante → nova → fallback (mais próxima) é determinístico.
  `forcar` só vale com `RPG_CREATURE_GEN_EVAL=1`.
- **Gate.** U1–U10 + U13 + R20, sem U11/U12, filtrado pelo id novo.
- **Revisão do curador.** `promote_due` deixa a criatura com ficha em `HELD` + `aguarda_curador`.
  `apply_curator_verdicts` é o único escritor de `PROMOTED`, recusa o revisor `runtime`, ignora o
  que não está pendente e é idempotente.
- **Flags.** `RPG_CREATURE_GEN` (`release`, default `legacy`, expira 2027-02-28),
  `RPG_CREATURE_GEN_RETRY_MIN_S` (`ops`) e as demais estão registradas; o gate da 340 está verde.

Desvios da §9 que aceito (legítimos, com motivo registrado):
- **Repartição do orçamento** (lore 1 800 / eixos 4 400, total mantido em 14 000).
- **`CorrecaoFicha` curta mesclada sobre a anterior.** Revalidada inteira por
  `FichaCriaturaGerada(**{**anterior, **mudou})`.
- **Descarte de chave desconhecida e correção de enum por prefixo único.** Só forma: `_enum_proximo`
  devolve o valor original quando há ambiguidade, e aí a validação reprova.
- **Reparo de padrão em Python.** Padrão é mecânica; `lint_primeira` registra o resultado cru.
- **`promote_after` +10 anos (`CURATOR_PARK`).** Não há TTL nem limpeza de `HELD` que dependa
  desse campo; `postgres_shared_pool.due` filtra por `promote_after <= now`.
- **`RETRY_MIN_S` no lugar de "metade do prazo".**

**Validador de injeção do pool (o snake_case como injeção).** A regra `\b[a-z]+(?:_[a-z0-9]+)+\b` de
`_INSTRUCTION` **não foi afrouxada**: todo texto livre continua passando por ela. O que mudou é que
os campos enum/id da criatura (`categoria`/`arquetipo`/`estilo_ataque`/`region_tags` e os enums da
ficha) saíram da varredura de texto e passaram a ser validados por forma (`_ID_RE`) ou por enum.
Para a forma que `ficha_runtime` produz hoje, não há brecha:
- `faccao` é conferida contra o grafo (`creature_gen.py:1036-1038`);
- `detalhe` = `demonio`, que é enum;
- os textos do LLM são todos varridos.

O pulo, porém, é **por nome de chave em qualquer profundidade**, e a checagem de forma só olha 3
níveis. Fica P1-1.

**Integridade de eval (redefinição de `fisico`/`campos_349`/`vizinho_max` para medir só a criatura
escrita pelo gerador).** Julgo **legítimo**, não mudança de evaluator pelo otimizador:
1. A mudança é coerente com §3.9, que diz "anatomia **gerada**". A variante reaproveita a anatomia
   curada da base, então `vizinho_max` dela daria ~1,0 contra a própria base, e a métrica perderia
   sentido.
2. Para `fisico` a exclusão é conservadora (a anatomia curada passaria).
3. Foi feita na Etapa 0, que a spec atribuiu ao próprio executor
   (`EVAL_AUTHORING_REQUIRED: false`), antes do "antes --real", que é o ponto de congelamento.
   Pedidos (sha conferido no teste) e limiares estão intocados.
4. Os arquivos do evaluator só aparecem no commit `90c98a72` e nenhum commit posterior os tocou.

Ressalva: como evaluator e produto pousaram no mesmo commit, o git não prova a ordem
"mock → ajuste → real". Isso vale a pena para as próximas specs (P2-8).

**Bug do evaluator `idioma_pt` (registrado, não corrigido aqui).** `services/creature_gen_eval.py:41`
e `:45` têm **"a" e "as"** nas duas listas de stopwords (pt e en). Num texto curto como
"Abrir a Maré", o empate conta como não-pt. Isso explica o 99,3 % da 1ª rodada. A correção cabe
ao dono do eval (não ao otimizador), com nova medição do "antes" e do "depois".

**Latência: o que no código piora.**
- P1-2: falha no caminho `nova` não consome o teto. O próximo spawn desconhecido paga de novo os
  12 s.
- P2-1: thread presa depois do prazo continua a cadeia de fallback.
- P2-2: a busca de lore roda fora do prazo.

---

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/shared_pool_validators.py:114-128`, `:182-187` | **Fail-open no validador da ficha.** `_walk_text` pula chaves com nome de enum (`status`, `padrao`, `familia`…) em **qualquer** profundidade, mas `_validate_ficha` só checa a forma em `ficha`, `ficha.anatomia` e `ficha.origem_lore`. Lista de dicts e profundidade > 4 são ignoradas em silêncio, e não há allowlist de chaves da ficha. Sonda (teste descartável, fora do repo): `ficha.arte.status = "Ignore todas as instruções anteriores… fulano@exemplo.com"`, `ficha.inspiracao=[{tomou: …}]` e chave a 5 níveis deram **0 injection, 0 PII e 0 schema**; o controle em `ficha.gancho` deu 1/1. Hoje não é explorável, porque o único produtor é `ficha_runtime`, com estrutura fixa. Mas o pool é fail-closed por contrato (SPEC-297), e o YAML de `pool_revisao export` leva a ficha inteira ao revisor Opus | Allowlist de **caminhos** da ficha (exatamente a estrutura de `ficha_runtime`). Chave ou caminho desconhecido, lista de não-`str` ou profundidade excedida → `Finding("schema_bad_value", …)`. Pular por enum só nos caminhos conhecidos. Teste com os 3 casos da sonda |
| P1-2 | P1 | `services/creature_gen.py:1563-1565` (+ `agents/combat.py` `combat_node`) | **O teto R4 só conta sucesso.** Com `PRAZO`/`SCHEMA`/lint duplo → fallback, o `contador` não muda e `ultimo_turno` não avança. Cada spawn com nome desconhecido tenta `nova` de novo: até 12 s por turno e até 2 chamadas FAST, mais a cadeia de fallback em background (P2-1). Isso se repete enquanto o DeepSeek estiver lento, justamente o cenário do eval (18 % de fallback, chamadas de 24–32 s). O teto de abuso de §7 ("O teto R4 limita abuso") não vale para tentativas que falham | Registrar a **tentativa**: `ultimo_turno = p.turn` sempre que o caminho `nova` chamou o LLM, inclusive em fallback. `novas` pode seguir contando só sucesso, ou um campo `tentativas` com teto próprio. Teste: fallback por prazo → o próximo spawn dentro de `RPG_CREATURE_NEW_EVERY_TURNS` vai direto ao fallback, sem LLM |
| P2-1 | P2 | `services/creature_gen.py:1334-1367` | Depois do timeout, a thread segue rodando o `RoutedLLM`, que pode cair no Groq e gastar quota sem uso. Com `max_workers=2` compartilhado pelo processo, duas gerações lentas ocupam o executor, e a 3ª espera na fila, o que conta no próprio prazo e leva a `PRAZO` sem nem chamar | Documentar o limite. Avaliar um `RoutedLLM` com teto de tempo por invoke (sem fallback de provedor depois do prazo) ou um executor dimensionado por perfil (hosted × legacy) |
| P2-2 | P2 | `services/creature_gen.py:1392-1405` | `_lore_publica` (embedding + FAISS), `escolher_exemplos` e `eixos_livres` rodam **antes** de `t0`: ficam fora do prazo de 12 s e somam ao turno | Iniciar `t0` antes da lore, ou dar à lore um teto curto próprio |
| P2-3 | P2 | `services/shared_pool.py:540` | `cg._todas_fichas.cache_clear()` não relê o disco, porque `_docs_regioes` (lru_cache) segura os YAMLs. "A curada que pousou depois vence" só vale com processo novo | Limpar também `_docs_regioes` (e `_regiao_doc`), ou documentar que o job roda em processo novo |
| P2-4 | P2 | `agents/bestiary.py:506` × `agents/combat.py:715` | `geracao.nome` grava `name` cru, e a trava compara com `sanitize_entity_name(name)`. Nome que o sanitizador altera (corte em 60, caracteres removidos) cai em `spawn_identity_mismatch` → genérico | Gravar `sanitize_entity_name(name) or "Criatura"` no bestiário, ou comparar cru com cru |
| P2-5 | P2 | `tests/test_spec361_integracao.py:129-151` | O round-trip save/load de `world.creature_gen` só cobre o campo **ausente**. Falta o caso preenchido (writer novo no estado persistido) | Teste: `combat_node` grava `{novas, ultimo_turno}` → `save_game_state` → `load_game_state` → `PedidoCriatura.from_spawn(...).contador` igual |
| P2-6 | P2 | `data/bestiario/modificadores_trama.yaml` (gatilhos) + `creature_gen.py:1292` | **Conteúdo.** A detecção roda sobre `pedido + motivo_trama`, que inclui os últimos 240 chars da narração. Gatilhos comuns em cena humana ("veterano", "covil", "ninho", "faminto", "afogado", "possuido", "domado") podem trocar a criatura pedida por uma variante de outra base da região (a afinidade sozinha chega ao `LIMIAR_BASE`) | Detectar o modificador só em `pedido` + beat/arco, sem "Última cena". Ou exigir o gatilho no pedido para os gatilhos genéricos. Teste com uma narração que cita "veterano" |
| P2-7 | P2 | `config/flags.yaml:897` | A nota de `RPG_CREATURE_GEN_DEADLINE_S` ainda diz "a 2ª tentativa só começa antes da metade", texto superado pelo desvio `RETRY_MIN_S` | Atualizar a nota |
| P2-8 | P2 | `services/creature_gen_eval.py:41`, `:45`, `:108` | (Para o dono do eval, não para o otimizador.) (a) "a" e "as" nas duas listas de stopwords. (b) `gerados` exclui os `nova` que caíram em fallback: o denominador de `fisico`/`campos_349` varia entre rodadas (sobrevivência), o que precisa ficar explícito no `.md`. (c) Etapa 0 em commit próprio nas próximas specs, para provar a ordem do congelamento | Corrigir em tarefa separada de autoria de eval (de preferência já com o arquivo em `evals/protected-paths.txt`, como decidido na 360 D6), com nova medição do "antes" e do "depois" |

## Correções aplicadas

Nenhuma até aqui (revisão só de leitura). O executor corrige P1-1 e P1-2 com teste. P2-1 a P2-7
podem ir no mesmo ciclo ou virar follow-up. P2-8 é do dono do eval.

## Pendências

- Smoke §6, passos 2 a 5 (`uvicorn`, fallback de provedor, pool + Opus): coordenador.
- Limiares não batidos na 2ª rodada real (`lint_primeira`, `lint_final`, `fallback`): decisão do
  dono sobre prazo e rota (§9 a/b/c). Corrigir P1-2 não muda o eval, mas tira o custo repetido no
  jogo.
- P2-8: tarefa de autoria de eval separada (o otimizador não toca no evaluator).

## Comandos rodados

```text
git diff 830fb496..spec-361 --stat → 28 arquivos, +7236/-44
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -W ignore -n 2 tests/test_spec361_{eval,gate,variantes,caminho,prompt,integracao,pool}.py tests/test_spec297_{validators,promotion,generation,reuse,review_fixes}.py tests/test_encounter_identity_repro.py tests/test_spec344_prompt_guard.py tests/test_spec346_spawn_hint.py tests/test_spec346_spawn_count_narration.py → 183 passed (rc=0)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -W ignore tests/test_flag_registry.py tests/test_spec297_flag_off.py → 18 passed (rc=0)
sonda descartável no scratchpad (fora do repo) sobre validate_injection/validate_pii/validate_schema → 3 bypasses confirmados (P1-1)
```

---

## Rodada 2 — HEAD `be32795f` ("substituta enquanto gera", R33 job `creature_gen`)

> **Veredito da rodada 2:** `APPROVED_WITH_FOLLOWUPS` **para pousar com `RPG_CREATURE_GEN=legacy`
> (off)**. Ligar a flag (`on`) fica **bloqueado** até resolver R2-P1-1, R2-P1-2 e as pendências de
> eval abaixo. Com `legacy`, o código novo fica dormente:
> - `drenar_local` não acha job e só faz um lease vazio;
> - a allowlist `FICHA_PATHS` e o gate do curador só valem para documento com `ficha`.
>
> **Revisor:** spec-reviewer Opus + Sol (independente) · **Data:** 2026-11-02 · **Commit:** `be32795f`

### Correções da rodada 1, conferidas

| Item | Status | Evidência |
|---|---|---|
| P1-1 | **Fechado** | `FICHA_PATHS` (`services/shared_pool_validators.py:93+`): caminho desconhecido → `schema_unknown_field`; tipo errado → `schema_bad_value`. As **3 sondas viraram teste** (`tests/test_spec361_pool.py`, `test_ficha_caminho_desconhecido_fail_closed`, parametrizado: `ficha.arte.status`, lista de dicts em `ficha.inspiracao` e profundidade em `ficha.anatomia.x`), mais `test_ficha_tipo_errado_em_caminho_conhecido` |
| P1-2 | **Fechado** | Com a substituta, o teto R4 conta o **agendamento**, dê certo ou não (`gerar(no_turno=True)`; `test_teto_conta_tentativa_que_falhou`) |
| P2-1 | Fechado | `llm_spend_guard_scope`: a thread que passou do prazo não abre outro provedor |
| P2-2 | Fechado | `t0` antes da preparação |
| P2-3 | Fechado | `recarregar_fichas()`, chamado 1 vez por rodada do `promote_due` |
| P2-4 | Fechado | Nome sanitizado dos dois lados (`test_trava_identidade_nome_sanitizado`) |
| P2-5 | Fechado | `test_round_trip_creature_gen_preenchido` |
| P2-6 | Fechado | Modificador detectado só em pedido + última fala do jogador (`texto_do_jogador`; `test_gatilho_so_da_acao_do_jogador`) |
| P2-7 | Fechado | Notas de `config/flags.yaml` atualizadas |
| P2-8 | Aberto | É do dono do eval; o avaliador e os limiares não foram tocados (conferido no diff) |

### Corretude do job: o que está certo

- **Dedupe e idempotência.** A chave é `creature:{game_id}:{regiao}:{slug(pedido)}`.
  - No `InlineJobQueue` (legacy), o dedupe vale para sempre no processo e o lease é feito sob
    `RLock`. Dois `drenar_local` concorrentes não rodam o mesmo job (não roda duas vezes).
  - No Postgres, `on conflict (kind,dedupe_key)` evita o segundo enfileiramento.
  - Dois jogos com o mesmo pedido geram dois jobs e duas criaturas (o id leva o hash do
    `game_id`). Com o pool desligado, `ja_gerada` reaproveita a do overlay do mesmo dono; com o
    pool ligado, o dedupe fica no `promote_due`. Aceitável.
- **Falha.** O handler não grava nada em fallback, e a substituta já jogou. `agendar` e
  `drenar_local` nunca levantam.
- **Entrada do job.**
  - `pedido` chega já sanitizado (`from_spawn` → `sanitize_entity_name`) e volta a ser cortado
    em `pedido_de`.
  - No prompt, continua dentro de `wrap_player_input` + `PLAYER_INPUT_RULE`.
  - `motivo_trama` já saiu de `_sem_segredo`.
  - O log leva só status e códigos.
  - O `owner_id` é explícito no `save_enemy`/`submit`, o que dá o escopo certo fora do request.
- **`run_worker`.** `build_handlers` registra `creature_gen`, e `test_spec196_finops` /
  `test_art_worker_reconciliation` seguem verdes. Não existe teste que garanta o registro
  (R2-P2-3).

### Achados da rodada 2

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R2-P1-1 | P1 (bloqueia `on`) | `agents/bestiary.py:227` × `services/creature_gen.py` (`ja_gerada`) | **Com o pool ligado, a criatura gerada nunca é reaproveitada.** O job submete ao pool (HELD) e não grava no overlay. `_pool_creature_template` monta `geracao = {caminho, spec, estado}` **sem `pedido`**, então `ja_gerada` não acha a criatura. Sonda (fora do repo, `pool_on` + `_gerar_e_drenar` + 2º `generate_new_enemy` com o mesmo pedido no turno 30): saiu `caminho: substituta` de novo, sem `pool_entry_id`. Cada novo encontro reagenda (no-op pelo dedupe) **e gasta o teto R4**, e o jogador nunca vê a criatura que pediu | Não gravar o texto do pedido no documento do pool (o validador de texto literal do jogador barraria). Gravar uma chave opaca, por exemplo `geracao_chave = sha256(fold(pedido)+regiao)[:16]` (ident na `FICHA_PATHS`/allowlist), no documento e no template, e fazer `ja_gerada` comparar pela chave. Alternativa: índice local pedido→id no overlay do dono também com o pool ligado. Teste: o caminho da sonda dá `existente` com `pool_entry_id` |
| R2-P1-2 | P1 (bloqueia `on` no legacy) | `api.py:6781-6786` (dentro do `with lock:` de `:6728`) | **`drenar_local(1)` roda sob o lock do jogo.** A narração já saiu, mas o job (prazo de 30 s) segura `_game_lock(game_id)`. A **próxima ação do mesmo jogo espera até ~30 s** (`lock_wait_ms`), e a projeção `post_response` (arquivista) só roda depois. Isso desfaz a decisão do dono ("o turno nunca espera a geração") no legacy, que é o perfil local de jogo. O lock também é do jogo A, mas o job drenado pode ser de outro jogo | Tirar do lock. Por exemplo, no `_worker` do SSE, depois de `_execute_action` retornar, ou numa thread daemon com 1 em voo por processo. O job não toca no estado do jogo, então não precisa do lock. Teste com um handler lento falso: a 2ª ação do mesmo jogo não espera o job |
| R2-P2-1 | P2 | `workers/drain.py:14` × `prazo_s()` = 30 s | `MIN_JOB_WINDOW_S = 15` < prazo do job de 30 s. No cron/serverless, um `creature_gen` iniciado com 15 s de janela pode ser morto pela plataforma. Com `max_attempts=1` vira `dead`, e a chamada paga se perde | Passar a janela restante ao handler (`prazo = min(prazo_s(), restante - margem)`) ou dar janela mínima por kind (≥ 35 s para `creature_gen`) |
| R2-P2-2 | P2 | `services/creature_gen_jobs.py:86` | O comentário "gerar de novo é decisão do próximo spawn" não vale no Postgres: o dedupe por `(kind, dedupe_key)` é permanente e não há `revive_dead_job` para este kind. Um job que morreu nunca mais é gerado para aquele jogo + pedido. Como comportamento é aceitável (teto R4), mas o texto engana | Corrigir o comentário, ou usar `revive_dead_job` com cooldown se o dono quiser uma nova tentativa |
| R2-P2-3 | P2 | `workers/run_worker.py:223` | Nenhum teste garante `"creature_gen" in build_handlers()` nem um round-trip `agendar → worker → persistir_nova` com a fila do perfil DB (só o legacy via `drenar_local` tem teste) | Teste do registro + 1 teste com a fila local/DB |
| R2-P2-4 | P2 | `services/creature_gen_jobs.py:47` | O payload do job guarda as **3 últimas falas cruas** do jogador (`player_inputs`) em `app.jobs.payload`. Isso é texto livre, com risco de PII, retido além do turno, e só é usado em `name_typed_by_player` | Guardar só os shingles `fold` necessários; no mínimo cortar cada fala e documentar a retenção |

### Eval da rodada 2 (`docs/spec361/eval-depois-2026-11-02c.json`)

`lint_primeira` 54,5 % (limiar 70 %) e `latencia_nova_p95` 19,1 s (limiar 15 s).

**Julgamento:** é aceitável **pousar com `legacy`**, com os dois itens como **pré-condição para
ligar**. Motivos:
- com a flag desligada, nada disso chega ao jogador;
- o executor não tocou no avaliador nem nos limiares (conferido no diff).

As duas métricas pedem tratamentos diferentes:
- **`latencia_nova_p95`** mudou de sentido: o limiar de 15 s foi pensado para o **turno**, e
  agora a métrica mede o **job** fora do turno, que tem prazo próprio de 30 s. Quem decide se o
  limiar continua, ou se vira "turno com zero LLM de geração + job p95 ≤ prazo", é o dono ou o
  autor do eval (junto com P2-8). O otimizador não pode decidir isso.
- **`lint_primeira`** abaixo do limiar nas 3 rodadas (63,6 / 45,5 / 54,5 %) é o sinal de produto
  que importa. Com o job fora do turno, a 2ª tentativa sempre cabe (`lint_final` sobe), mas a
  qualidade de primeira continua sendo trabalho de prompt e eixos livres antes de ligar.

**Pré-condições para `RPG_CREATURE_GEN=on`** (registrar na §8 D11 da spec):
1. R2-P1-1 e R2-P1-2 corrigidos;
2. decisão do dono/autor do eval sobre o limiar de latência (turno × job) e a correção de
   `idioma_pt` (P2-8);
3. `lint_primeira` ≥ 70 % numa rodada real, ou o dono aceitar explicitamente o desvio;
4. smoke §6, passos 2–5.

### Comandos rodados (rodada 2)

```text
git diff b6656d04..be32795f --stat → 14 arquivos, +1273/-120
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -W ignore -n 2 tests/test_spec361_{eval,gate,variantes,caminho,prompt,integracao,pool}.py tests/test_spec297_{validators,promotion,generation}.py tests/test_encounter_identity_repro.py tests/test_flag_registry.py → ~156 passed (rc=0)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -W ignore tests/test_art_worker_reconciliation.py tests/test_spec196_finops.py → passed, 1 skipped (rc=0)
sonda descartável (scratchpad, apagada): pool on → job → 2º encontro com o mesmo pedido = "substituta" de novo (R2-P1-1)
```
