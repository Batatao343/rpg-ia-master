# SPEC-367 — Cartas: acabamento do 5º smoke real (cotação por nome parcial, chip do retrato depois de confirmar, presságio na voz do jogador, retrato de inimigo de fallback, condição de inimigo que termina, ouro na narração da compra, timeout do pool dos scripts de operação)

> **Status:** `done` (04/11, coordenador, autorização do dono "manda bala"; fechamento na nota final)
> **Criada:** 2026-11-02 · **Atualizada:** 2026-11-02
> **Épico:** SPEC-327
> **Origem:** smoke final da SPEC-364 (02/11, `main` `90cfaa18`, local `legacy` + staging `hosted-supabase`, DeepSeek `deepseek-v4-flash`, 12 turnos e 1 geração de retrato). Achados A1–A7 em [docs/spec364/smoke-final.md](../docs/spec364/smoke-final.md) § Achados. A evidência bruta fica no scratchpad do coordenador (`scratchpad/smoke5/`).
> **Depende de:** SPEC-364 na `main` (o código dela está pousado; o §6 foi registrado em `0a10a5a2`).
> **Desbloqueia:** smoke de liberação das flags de cartas sem P3 aberto do smoke 5.
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma etapa por vez · **REVIEW_MODEL:** `Sol` (Opus) · **REVIEW_REQUIRED:** `true` (oferta de efeito pago e texto de transação com ouro)
> **EVAL_AUTHORING_REQUIRED:** `false`. Esta spec não muda evaluator, expected de eval, baseline nem dataset de regressão. O golden da SPEC-330 fica byte a byte (R24).

Rótulos: **[F]** fato no source (worktree `rpg-spec-367`, `main` em `eec75ef5`) · **[H]** hipótese com evidência; a Etapa 0 ou o 1º teste confirma ou derruba · **[D]** decisão (§8).

---

## 1. Contexto & Objetivo

O smoke final da 364 passou em todos os requisitos que ocorreram. A fuga mostrou a mesma trilha em todas as
superfícies, a consulta do mercado não chamou o CLASSIFY, o débito do retrato ficou em 8 milli contra uma
cotação de 15, e as rodadas do meio da luta tiveram 0 chamadas de LLM. Sobraram **5 P3 e 2 observações**
(A1–A7). Nenhum deles move ouro ou Estilhas errado. São arestas de texto, de UX e de operação que o jogador ou o
operador vê.

O objetivo é **fechar A1–A7** com testes determinísticos para cada um e deixar o §6 curto (≤ 6 turnos), focado
só nesses achados. Os princípios continuam: **mecânica é Python** (a narração recebe os números do motor, e um
número de ouro que diverge deles é barrado); **0 chamada de LLM por rodada**; **o texto do efeito pago descreve o
que o motor de cobrança faz**; **voz do jogador** nas superfícies de combate (D-363-3: o nome próprio do herói
só aparece na crônica e no arquivista); golden da 330 intocado; nenhuma flag nova.

### 1.1 Achados e causa no source

| # | Achado (prioridade) | Evidência do smoke | Causa no source |
|---|---|---|---|
| A1 | "Posso vender a Faca de pedra-sabão?" devolveu a consulta inteira, não a cotação da faca (P3, R6/R8 da 364) | `out/state-Haldor5-t2b.json` | **[F]** `_cites_inventory` (`agents/loot.py:150-161`) só casa o `item_display` inteiro ou o `short_display`. O nome salvo é "Faca de pedra-sabão usada em sacrifícios de sangue ao mar" (57 caracteres, sem separador). Então `short_name` corta em 40 caracteres e põe "…" (`inventory.py:83-87`), o que dá "Faca de pedra-sabão usada em sacrifícios…". Nem o nome inteiro nem esse corte aparecem no texto do jogador. Sem entrada citada, `_shop_question_quote` cai em `iid = _resolve_item_ref(...)` (`agents/loot.py:214`), que não acha nada no catálogo, devolve `None` (`:223`), e o chamador faz a consulta de R7. A venda afirmativa não tem esse bug: `find_entry_in_inventory` já casa por substring (`inventory.py:180-183`) |
| A2 | Depois de "Gerar", o toast confirma, mas o chip continua "Gerar retrato (até 0,015 Estilhas)" até o próximo refresh. Um 2º clique cota de novo (P3, R18 da 364, UX) | `out/stg-offer-1440-c-gerando.png`, `stg/done-offer.txt` (`1440-pos-gerar`) | **[F]** Quando a confirmação dá certo, `confirmImageQuote` atualiza só `portrait_generation_id`/`art_generations`/`art_offers` (`web/src/App.tsx:419-425`) e nunca toca `combat.enemies[*].retrato`. A oferta `retrato.gerar` continua na tela. O servidor já não ofereceria: com o registro `pending`, `portrait_for` dá `estado: "gerando"` e `gerar: None` (`services/creature_art.py:236,241`), mas essa view só chega no próximo turno. A trava contra clique duplo é `imageBusy` (`App.tsx:393`), um estado React: dois cliques no mesmo tick passam, e o botão do chip só fica desabilitado com `busy` do turno (`web/src/workspace/tabs/CombateTab.tsx:328,341`; `web/src/combat/TargetChip.tsx:49`). Nada é cobrado em dobro: com a chave tomada, a 2ª cotação dá `409 creature_portrait_exists` (`api.py:4950-4952`), e o `claim` na confirmação é o árbitro (`api.py:5083-5088,5141-5143`). O problema é só de UX: o jogador vê uma oferta que não vale mais e recebe um aviso de "outro jogador" |
| A3 | O presságio público usa o nome do herói: "Criatura hostil vai saltar sobre Smoke5A." e "o frio da cova aponta para Mirela5." (P3, voz, vizinho do R16) | `combat.pressagios_publicos[*].sinal`; `out/stg-offer-390-b-pergunta.png` | **[F]** `public_intent` passa `alvo.get("name")` cru para `sinal_for` (`services/enemy_intent.py:262,271`), que formata `{alvo}` (`:93-96`). Quando o alvo é o herói (`is_player: True`, `services/conflict_orchestrator.py:114-115`), sai o nome próprio. Sete frases do catálogo usam "de {alvo}" (`data/combat/pressagio_sinais.json:17,25,109,117,118,122,129`) e uma usa clítico com gênero ("derrubá-lo", `:113`). Com "você" no lugar do nome, essas oito ficariam agramaticais ("o joelho de você") |
| A4 | Retrato pago gerado para inimigo de fallback: a chave `tipo:fallback_criatura_hostil` ficou `ready` no pool compartilhado (P3, arte/conteúdo) | `stg/stg_log.jsonl` (oferta e geração), `fallback_criatura_hostil_1` | **[F]** Há dois caminhos que materializam `fallback_<slug>`: a trava de identidade do spawn (`agents/combat.py:707-718`) e o `except` de `generate_new_enemy` (`agents/bestiary.py:497-511`). `portrait_for` oferece `gerar` sempre que a flag está `on`, há preço e não existe arte (`services/creature_art.py:241`), sem olhar a origem. O endpoint de cotação também não olha (`api.py:4931-4964`). **[H]** A chave é `tipo:fallback_criatura_hostil`, e não `tipo:gen:…`, porque o overlay de criaturas geradas entra em `_bestiary_db` (`services/discovery.py:21-27`) e `normalize_bestiary_id` acha o id base (`:53-55`). A ferramenta de retirada existe: `scripts/retire_creature_portrait.py` (`ready` → `retired`, apaga os objetos compartilhados e libera a chave, `:18-34`). Ela só monta o runtime pelo ambiente do processo (`build_runtime()`, `:44`), sem `--env-file`. `scripts/staging/spec222_art_purge.py`, citado no prompt, é o fluxo E2E da SPEC-222 R6 (cria conta, gera arte, apaga campanha, `:1-9`) e **não** retira uma chave do pool (D-367-4) |
| A5 | "Goblin-Mineiro: cego terminou." em formato técnico, enquanto as outras linhas dizem "ganha a condição Cego." e "Sua condição Cego terminou." (P3, texto) | `out/state-Mirela5-f2.json` | **[F]** O orquestrador emite `"{nome}: {condição} terminou."` (`services/conflict_orchestrator.py:351,400,2662`). `round_log._voce` normaliza "terminou" só quando a linha começa com o nome do herói (`services/round_log.py:224-226`). Para os outros, trata "ganha condição" e "renovada" (`:228-233`), mas não "terminou". Todas as superfícies passam por `_voce`: registro (`round_log.py:346,374,376`) e linhas de status do agente (`agents/combat.py:1587-1597`) |
| A6 | Compra: "Você entrega as últimas 45 moedas…" e logo depois "Restam-lhe 5 moedas" (observação, narração) | `out/state-Haldor5-t3.json` | **[F]** O contexto do narrador já leva o saldo final: `"BUY: Carta {name}, ouro −{gold}, ouro final {total}"` (`agents/loot.py:584-588`) e `"{MODE}: …, ouro {delta}, ouro final {total}"` (`:710-721`). Mas não leva o saldo anterior, e a instrução só diz "NÃO altere números" (`:342-343`). Também não há validação da prosa: nesses dois caminhos `_narrate` é chamado sem `canonical_summary` (`:330-369`), e o texto do LLM vai direto para a tela. Uma afirmação falsa sobre o ouro ("últimas moedas", ou um número que não é preço nem saldo) passa sem barreira |
| A7 | `admin_kill_switch.py` e `art_preflight.py` contra o staging deram `PoolTimeout` intermitente; funcionaram na 2ª tentativa (observação, infra) | `stg/ks_*.txt`, `stg/preflight_*.txt` | **[F]** Os dois scripts criam `PostgresPool(dsn, max_size=2)` (`scripts/admin_kill_switch.py:64`, `scripts/staging/art_preflight.py:91`) com os defaults `min_size=0`, `timeout=5.0` e `connect_timeout=5.0` (`infrastructure/postgres.py:67-71`). Com `min_size=0`, a 1ª conexão só abre no 1º checkout, e o `PoolTimeout` de 5 s cobre a espera por essa abertura (`postgres.py:117-126`). Nenhum dos dois tenta de novo. **[H]** O handshake TLS com o pooler do Supabase a partir da estação passa de 5 s às vezes. O smoke disse "pool de tamanho 1", mas no source o tamanho é 2; a causa provável é o tempo de abertura, não o tamanho. O preflight também não fecha o pool se `store.load()` levanta (`art_preflight.py:108-116`) |

Fora dos achados: os 2 timeouts do DeepSeek no CLASSIFY do `dm_router` (A7, 1º item) já caíram no Groq pelo
`RoutedLLM`, como esperado; o roteamento fica como está.

## 2. Requisitos

Todos valem com as flags de cartas `on`, como no preset de `scripts/staging/staging_flags.json`. Em `off`, o
fluxo fica como hoje.

### A. Cotação por nome parcial do item livre (A1)

- **R1 — Casar por prefixo significativo.** `_cites_inventory(state, folded)` continua casando primeiro pelo
  nome inteiro e pelo `short_display`, como hoje. Se nenhum casar, tenta o **prefixo**. Os tokens do
  `item_display` dobrado (fold sem acento, minúsculas, sem "…", separados por espaço e pontuação, mantendo o
  hífen interno como em "pedra-sabao") geram prefixos de tamanho k, do maior para o menor, com k ≥ 2. Um prefixo
  só vale se tiver **≥ 2 tokens significativos** (≥ 3 letras e fora da lista
  `{de, da, do, das, dos, e, com, em, a, o, as, os, um, uma, para, pra, no, na}`) e aparecer no texto com borda
  de palavra (`\b…\b`). Ganha o prefixo mais longo. Se duas entradas **diferentes** do inventário casarem com o
  mesmo comprimento máximo, o resultado é `None` (ambíguo → consulta, sem cotação errada).
- **R2 — A pergunta do smoke cota.** Com "Faca de pedra-sabão usada em sacrifícios de sangue ao mar" no
  inventário, "Posso vender a Faca de pedra-sabão?" responde
  `"[SISTEMA] Faca de pedra-sabão usada em sacrifícios…: o mercador paga N moedas. Diga claramente que vende para confirmar; nada mudou."`.
  N é o `sell_price` da cotação dessa entrada, e não muda nada: nem ouro, nem inventário, nem estoque.
- **R3 — Negativos.** "Posso vender a faca?" (1 token significativo) e "Posso vender a Faca de?" não casam por
  prefixo. Com duas entradas "Faca de pedra-sabão usada…" e "Faca de pedra-sabão lascada", a pergunta
  "Posso vender a Faca de pedra-sabão?" dá a consulta, sem cotação. A venda afirmativa
  "Vendo a Faca de pedra-sabão" segue vendendo como hoje (`find_entry_in_inventory`). R4/R6 da 364 continuam
  verdes: as 5 perguntas de catálogo seguem como consulta e nenhuma pergunta transaciona.

### B. Chip do retrato depois de confirmar (A2)

- **R4 — A oferta some na confirmação.** Quando `confirmPlayerArt` dá certo para `type: "monster"`, o estado
  local troca o `retrato` do inimigo clicado para `{...retrato, estado: "gerando", gerar: null}`. Faz o mesmo
  com todo inimigo que tenha `retrato.gerar.escopo === "tipo"` e o mesmo nome sem o sufixo numérico, porque é o
  mesmo tipo e a mesma chave. Helper puro novo em `web/src/lib/portraitOrder.ts`:
  `withPortraitPending(data, enemyId)`, imutável e com o mesmo objeto quando nada muda, como
  `withoutPortraitOffer`. O chip mostra o selo "Gerando retrato…" que já existe (`TargetChip.tsx:34`) e nenhum
  botão `[data-gen-portrait]` para esses inimigos.
- **R5 — Um pedido por vez, de forma síncrona.** `handleGeneratePortrait` usa uma trava em `useRef`
  (`portraitInFlight`), ligada antes do 1º `await` e solta no `finally`. Um 2º clique enquanto a cotação ou a
  confirmação está em voo não chama `/art/quote`. Teste: dois cliques em "Gerar" no mesmo tick produzem
  **1** cotação e **1** confirmação.
- **R6 — Falha não esconde a oferta à toa.** 402/503/erro de rede na cotação ou na confirmação mantêm o
  comportamento de hoje (aviso; a oferta só some nos casos de `shouldHidePortraitOffer`). A cópia
  "Outro jogador já está gerando este retrato…" **não muda**: o e2e da 352 a fixa (`web/e2e/spec352-retrato-pago.spec.ts:90`,
  D-367-5).

### C. Presságio na voz do jogador (A3)

- **R7 — Herói vira "você".** `public_intent` passa `alvo_nome = "você"` quando o alvo tem `is_player` verdadeiro.
  Aliados e inimigos continuam com o nome. `sinal_for` não muda de assinatura. Exemplos:
  "Um rosnado baixo, dentes à mostra: Criatura hostil vai saltar sobre você." e
  "Goblin arrasta o corpo sem pressa, e o frio da cova aponta para você."
- **R8 — O catálogo lê bem com nome e com "você" [D-367-2].** Reescrever as 8 frases agramaticais com "você"
  (`pressagio_sinais.json:17,25,109,113,117,118,122,129`) mantendo o sentido e a voz (proposta no §3.3). Atualizar
  `_meta` para dizer que `{alvo}` é o nome do alvo ou "você" quando o alvo é o herói. Lint em teste: nenhuma frase
  contém `de {alvo}`, `do {alvo}`, `da {alvo}`, `{alvo}` no início de frase nem clítico `-lo`/`-la`/`-los`/`-las`
  depois de `{alvo}`.
- **R9 — Invariante de voz no presságio.** Com os heróis "Smoke5A" e "Mirela5": nenhum `pressagios_publicos[*].sinal`
  (nem `prenuncio`) da view de `/game/state` contém o nome do herói, em 2 rodadas seguidas de uma luta com
  2 inimigos, nas famílias `fera` e `morto_inquieto` (as do smoke).

### D. Retrato de inimigo de fallback (A4)

- **R10 — Fallback não tem oferta paga.** Nova função pura `creature_art.is_fallback_enemy(enemy) -> bool`:
  verdadeira quando `enemy["id"]`, o id sem o sufixo `_N`/`_rN` ou `normalize_bestiary_id(enemy)` começam com
  `fallback_`. Para esses inimigos, `portrait_for` devolve `gerar: None`, não lê o registro do tipo nem a arte
  própria, e mostra a família curada ou o marcador. Assim, uma linha `tipo:fallback_*` que já exista no pool
  nunca é reaproveitada.
- **R11 — O servidor recusa a cotação.** `_offer_brief_for_quote` (`api.py:4931-4964`) responde
  `409 creature_portrait_not_offered` para `is_fallback_enemy`, antes de qualquer leitura do registro ou reserva.
  O front já trata 409 como aviso sem cobrança (`portraitErrorBanner` cai no texto de fallback).
- **R12 — Retirada operável a partir da estação [D-367-4].** `scripts/retire_creature_portrait.py` ganha
  `--env-file <dotenv>`, que carrega as variáveis no ambiente do processo com `override=False` **antes** de
  `build_runtime()`, sem imprimir nenhum valor, e `--dry-run`, que mostra
  `{portrait_key, status_atual, objetos}` sem mudar nada. Testes com runtime falso: `--env-file` chega a
  `build_runtime` e `--dry-run` não chama `registry.retire` nem `shared.delete`. O passo de staging (retirar
  `tipo:fallback_criatura_hostil`) fica no §6.

### E. Condição de inimigo que termina (A5)

- **R13 — Frase legível.** `round_log._voce` ganha o ramo para qualquer ator que não seja o herói:
  `"^(.+?): (.+?) terminou\.?$"` → `"A condição {Cond} de {Nome} terminou."`, com a condição em maiúscula,
  espelhando o "renovada" (`round_log.py:231-233`). Exemplo real: "Goblin-Mineiro: cego terminou." →
  "A condição Cego de Goblin-Mineiro terminou.". As linhas do herói continuam
  "Sua condição Cego terminou.". "Provocação" sai da mesma forma.
- **R14 — Superfícies e dedupe.** Numa luta semeada em que a condição Cego do inimigo termina, registro,
  `mech_log`, mensagem do turno e `/game/history` não contêm `": cego terminou"` nem `/^[^:]+: \w+ terminou/` e
  mostram a frase de R13 **uma** vez por evento. Se a Etapa 0 achar uma superfície que não passa por `_voce`
  (p. ex. `combat_preview`), ela entra pelo mesmo helper.

### F. Ouro na narração da compra e da venda (A6)

- **R15 — O narrador recebe o saldo antes e depois.** Os contextos de compra de Carta (`agents/loot.py:584-588`)
  e de compra/venda de item (`:710-721`) passam a levar
  `Ouro antes: {antes}. Preço: {abs(delta)}. Ouro depois: {depois}.` e a regra
  "Se o ouro depois for maior que zero, nunca diga que foram as últimas moedas nem que a bolsa ficou vazia; não
  cite outro número de moedas." Os números vêm do motor (`gold_before`/`total`, `outcome`), nunca do LLM.
- **R16 — Validação V-G do ouro [D-367-3].** Nova função pura em `services/prose_guard.py`:
  `gold_claims_ok(text, *, allowed: set[int], gold_after: int) -> bool`. Ela é falsa quando:
  - **(a)** um número em algarismos, ou por extenso de "uma"/"um" até "vinte" e as dezenas até "cem", está colado
    a `moeda(s)`, `ouro`, `peça(s) de ouro` ou `coroa(s)` (até 2 palavras de distância) e não pertence a
    `allowed = {antes, preço, depois}`;
  - **(b)** `gold_after > 0` e o texto afirma esgotamento: `últimas moedas`, `última moeda`,
    `todas as (suas) moedas`, `todo o (seu) ouro`, `bolsa vazia`, `sem (nenhuma) moeda`, `nenhuma moeda`.

  Os dois caminhos de R15 aplicam V-G ao texto do LLM. Se falhar, o texto vira `_deal_fallback(merchant_name)`
  (o mesmo fallback da 364) e o evento `loot.trade_prose_rejected` é registrado, sem o texto. A linha `[SISTEMA]`
  não muda.
- **R17 — Oráculo com o texto real.** Uma fixture (`tests/fixtures/spec367_smoke.py`) guarda a narração real do
  smoke ("Você entrega as últimas 45 moedas…", com `antes=50`, `preço=45`, `depois=5`), que V-G **rejeita**, e um
  texto correto escrito à mão ("Você conta 45 moedas sobre o balcão; restam 5 na bolsa."), que V-G **aceita**. Um
  corpus de ≥ 8 frases benignas não dispara: atmosfera sem número, "o ouro tilinta", "a última Carta da
  prateleira", preço certo, saldo certo e "todas as moedas" quando `depois == 0`.

### G. Pool dos scripts de operação (A7)

- **R18 — Abertura tolerante.** Helper novo `scripts/staging/ops_pool.py`:
  `open_ops_pool(dsn) -> PostgresPool` com `max_size=1`, `timeout=20.0` e `connect_timeout=10.0` (D-367-6), e
  `with_checkout_retry(fn, *, attempts=3, delays=(1.0, 3.0))`. O retry vale **só** para `PoolTimeout` e para
  `psycopg.OperationalError` levantado **no checkout**, quando nenhum comando chegou ao banco. Um erro durante
  `execute` não é repetido, para não duplicar a auditoria de `store.set`. Cada tentativa registra
  `ops.db_retry {attempt, error_class}` no stderr, sem DSN nem mensagem.
- **R19 — Os dois scripts usam o helper.** `admin_kill_switch.py` (`list`, `audit`, `on/off --apply`) e
  `art_preflight.py` (`peek_ceiling`, `load`, `audit`) passam a usar `open_ops_pool` + `with_checkout_retry`. O
  preflight fecha o pool em `try/finally`. Testes com um pool falso que dá `PoolTimeout` na 1ª tentativa: o
  comando conclui na 2ª, o código de saída é o mesmo de hoje, `store.set` é chamado **1** vez e, se as 3
  tentativas falham, a saída é `!= 0` com mensagem curta `error: db_unavailable`.

### H. Guardas

- **R20 — 0 LLM por rodada.** `tests/test_spec364_flee_surfaces.py` e `test_spec346_board_no_llm.py` continuam
  verdes. Nenhum requisito acrescenta chamada de LLM, porque R7/R13 são determinísticos e R16 só valida.
- **R21 — Menos ou igual LLM na loja.** R1 resolve por regex. Nada de `with_structured_output` novo; o guard de
  FallbackLLM do loot fica.
- **R22 — Sem flag nova.** `config/flags.yaml` sem diff.
- **R23 — Contrato aditivo.** O 409 `creature_portrait_not_offered` é um código novo num status que o cliente já
  trata. Nenhum campo de view muda de forma. `web/src/types.ts` só ganha o que `withPortraitPending` usar.
- **R24 — Golden e e2e intocados.** `git diff main -- tests/spec330_equivalence.py tests/fixtures/spec330_legacy_golden.json web/e2e/`
  só mostra **arquivos novos** em `web/e2e/` (nenhum spec existente alterado). Nenhuma mudança em
  `services/conflict_orchestrator.py`, `services/scene_cards.py` nem em `ct.resolve_turn` (A5 é corrigido na
  apresentação, em `round_log`).
- **R25 — Invariante de ids e voz estendido.** `tests/test_spec363_ids.py` (o teste R29 da 364) passa a incluir
  o presságio (R9) e a linha de condição de inimigo que termina (R14).

### Fora de escopo

- Trocar o texto "Outro jogador já está gerando…" (D-367-5).
- Mudar quando o spawn cai no fallback, o nome "Criatura hostil" ou o texto do jogador que induziu o fallback.
  Esta spec só tira a oferta paga e a reutilização da arte.
- Retirar outras chaves do pool além de `tipo:fallback_criatura_hostil`. Moderação ampla é da SPEC-352 R13.
- Reescrever as frases do presságio que já leem bem com "você".
- Rotear o CLASSIFY do `dm_router` fora do DeepSeek ou mudar o timeout dele (A7, 1º item).
- Pool e timeout do runtime da API (`infrastructure/runtime.py`). R18 vale só para os scripts de operação.
- Validação de número na narração do tesouro (ela já cai no resumo determinístico, `agents/loot.py:46-62`).
- Qualquer número de Carta, preço ou regra de liquidação.

## 3. Design técnico

### 3.1 Arquivos novos

- `tests/test_spec367_cites_prefix.py` (R1–R3), `tests/test_spec367_omen_voice.py` (R7–R9),
  `tests/test_spec367_fallback_portrait.py` (R10–R12), `tests/test_spec367_condition_end.py` (R13, R14),
  `tests/test_spec367_trade_gold.py` (R15–R17), `tests/test_spec367_ops_pool.py` (R18, R19),
  `tests/test_spec367_guards.py` (R22, R24).
- `tests/fixtures/spec367_smoke.py`: narração real da compra + números + texto correto (R17).
- `scripts/staging/ops_pool.py`: `open_ops_pool`, `with_checkout_retry` (R18).
- Front: `web/tests/spec367-portrait-pending.test.mjs` (R4, R5, helper puro) e
  `web/e2e/spec367-portrait-pending.spec.ts` (R4/R5 a 390 e 1440, com `page.route` para quote/confirm, como o
  e2e da 352).

### 3.2 Arquivos alterados

- `agents/loot.py`: `_cites_inventory` com prefixo (R1); contexto de R15; V-G nos dois caminhos (R16).
- `services/prose_guard.py`: `gold_claims_ok` (R16).
- `web/src/App.tsx`: `confirmImageQuote` aplica `withPortraitPending` (R4); trava `useRef` em
  `handleGeneratePortrait` (R5).
- `web/src/lib/portraitOrder.ts`: `withPortraitPending` (R4).
- `services/enemy_intent.py`: `public_intent` com "você" para `is_player` (R7).
- `data/combat/pressagio_sinais.json`: 8 frases + `_meta` (R8).
- `services/creature_art.py`: `is_fallback_enemy`; `portrait_for` sem oferta nem registro para fallback (R10).
- `api.py`: **uma** guarda em `_offer_brief_for_quote` (R11). É a única linha da 367 em `api.py`; ver §7 sobre
  a SPEC-368.
- `scripts/retire_creature_portrait.py`: `--env-file`, `--dry-run` (R12).
- `services/round_log.py`: ramo "terminou" para quem não é o herói em `_voce` (R13).
- `scripts/admin_kill_switch.py`, `scripts/staging/art_preflight.py`: usam `ops_pool` (R19).
- `tests/test_spec363_ids.py`: extensão de R25.

**Não altera** `agents/combat.py`, `services/card_piles.py` nem `data/cards/` (§7).

### 3.3 Formatos e exemplos

Prefixo (R1), com o item real do smoke:

```
item_display  = "Faca de pedra-sabão usada em sacrifícios de sangue ao mar"
tokens        = faca de pedra-sabao usada em sacrificios de sangue ao mar
texto         = "posso vender a faca de pedra-sabao?"
prefixo k=3   = "faca de pedra-sabao"   (significativos: faca, pedra-sabao → 2) → casa
prefixo k=2   = "faca de"               (significativos: faca → 1) → não vale
```

Presságio (R8): proposta de reescrita. Cada frase precisa ler bem com nome e com "você".

| Linha | Hoje | Proposta |
|---|---|---|
| 17 | O ferro range: {nome} baixa a lâmina na direção de {alvo}. | O ferro range: {nome} baixa a lâmina rumo a {alvo}. |
| 25 | Poeira sobe dos pés de {nome}; o golpe já tem o nome de {alvo}. | Poeira sobe dos pés de {nome}; o golpe já escolheu {alvo}. |
| 109 | {nome} mira em algo que não é a carne de {alvo}. | {nome} mira em {alvo}, mas não na carne. |
| 113 | {nome} baixa o focinho e cerca {alvo}, tentando derrubá-lo. | {nome} baixa o focinho e cerca {alvo}, buscando a queda. |
| 117 | O frio da cova vaza das mãos de {nome} na direção de {alvo}. | O frio da cova vaza das mãos de {nome} e rasteja até {alvo}. |
| 118 | {nome} estende dedos secos: um toque que rouba o calor de {alvo}. | {nome} estende dedos secos para {alvo}: um toque que rouba o calor. |
| 122 | O ferro de {nome} busca o joelho de {alvo}. | {nome} baixa o ferro rente ao chão: quer {alvo} de joelhos. |
| 129 | {nome} recolhe a terra em punhado, mirando os olhos de {alvo}. | {nome} recolhe a terra em punhado e espera {alvo} erguer o olhar. |

Condição (R13):

```
"Goblin-Mineiro: cego terminou."  → "A condição Cego de Goblin-Mineiro terminou."
"Mirela5: Cego terminou."         → "Sua condição Cego terminou."   (como hoje)
```

Contexto do narrador (R15), compra do smoke:

```
BUY: Carta Traje Branco, ouro −45, ouro final 5
Ouro antes: 50. Preço: 45. Ouro depois: 5.
Se o ouro depois for maior que zero, nunca diga que foram as últimas moedas nem que a bolsa ficou vazia; não cite outro número de moedas.
Mercador: Forja dos Clãs (Skallgard). Chame o mercador por esse nome; não invente outro.
```

Recusa da cotação (R11): `HTTP 409 {"detail": "creature_portrait_not_offered"}`.

## 4. Plano passo a passo

Em cada etapa: testes primeiro → código → só os testes do escopo (no máximo `-n 2`). A suíte completa roda só
no pouso, pelo coordenador. Toda etapa que toca `round_log` ou `enemy_intent` roda também
`tests/test_spec363_*.py`, `tests/test_spec364_*.py`, `tests/test_enemy_intent.py` e
`tests/test_spec353_misc.py`.

### Etapa 0 — Confirmação (sem código de produto)

1. **A1:** escrever `test_partial_name_question_quotes` e vê-lo falhar com a consulta.
2. **A4:** confirmar por que o id base `fallback_criatura_hostil` cai em `normalize_bestiary_id` (overlay) e se
   `is_important` pode mandar o fallback para uma chave `unico:` (nome ≠ rótulo). `is_fallback_enemy` cobre os
   dois casos.
3. **A5:** listar as superfícies que recebem a linha crua "X: Y terminou." (registro, status do agente,
   `mech_log`/`combat_preview`, Livro) e confirmar que todas passam por `_voce`.
4. **A7:** com um pool falso, confirmar que `PoolTimeout` sai de `_checkout` antes de qualquer `execute`
   (`postgres.py:117-126`), o que torna o retry seguro.
5. Anotar no §9.

### Etapa 1 — Cotação por prefixo (R1–R3)

1. **Testes** (`tests/test_spec367_cites_prefix.py`): `test_partial_name_question_quotes` (R2: texto exato, sem
   delta); `test_prefix_needs_two_significant_tokens`; `test_ambiguous_prefix_falls_to_observe`;
   `test_affirmative_sell_unchanged`; `test_catalog_questions_still_observe` (os 5 positivos da 364 R4).
2. **Implementação:** `agents/loot.py::_cites_inventory`.

### Etapa 2 — Voz: presságio e condição (R7–R9, R13, R14)

1. **Testes:** `tests/test_spec367_omen_voice.py`: `test_hero_target_is_voce`, `test_ally_and_enemy_keep_name`,
   `test_catalog_lint_no_de_alvo` (R8; percorre todo o JSON), `test_every_phrase_formats_with_name_and_voce`,
   `test_state_view_omens_without_hero_name` (R9, TestClient, "Smoke5A"/"Mirela5", 2 rodadas).
   `tests/test_spec367_condition_end.py`: `test_enemy_condition_end_readable`, `test_hero_condition_end_unchanged`,
   `test_condition_end_once_on_all_surfaces` (R14).
2. **Implementação:** `services/enemy_intent.py`, `data/combat/pressagio_sinais.json`, `services/round_log.py`.

### Etapa 3 — Ouro na narração (R15–R17)

1. **Testes** (`tests/test_spec367_trade_gold.py`): `test_context_has_before_price_after` (Carta e item; contexto
   capturado do LLM simulado); `test_vg_rejects_smoke_text` (fixture R17); `test_vg_accepts_correct_text`;
   `test_vg_benign_corpus`; `test_vg_number_words`; `test_vg_rejection_uses_merchant_fallback` (Mock devolve o
   texto real e a mensagem final traz `_deal_fallback` + `[SISTEMA]` intacto); `test_sell_path_validated`.
2. **Implementação:** `services/prose_guard.py`, `agents/loot.py`.

### Etapa 4 — Retrato: fallback e chip (R4–R6, R10–R12)

1. **Testes:** `tests/test_spec367_fallback_portrait.py`: `test_is_fallback_enemy_variants` (id, id com `_1`,
   base no overlay); `test_portrait_for_fallback_no_offer_no_registry` (registro falso com
   `tipo:fallback_criatura_hostil` `ready` → não usado, `gerar is None`); `test_quote_refuses_fallback_409`
   (TestClient, nada reservado); `test_retire_env_file_and_dry_run`. Front
   (`web/tests/spec367-portrait-pending.test.mjs`): `withPortraitPending` marca o clicado e o irmão de mesmo
   tipo, não toca o `unico` e devolve o mesmo objeto sem mudança. E2e (`web/e2e/spec367-portrait-pending.spec.ts`,
   390 e 1440, `--workers=1`): depois de "Gerar", `[data-gen-portrait="e1"]` some e aparece "Gerando retrato…";
   duplo clique → 1 quote e 1 confirm; 503 na cotação mantém a oferta.
2. **Implementação:** `services/creature_art.py`, `api.py` (uma guarda), `scripts/retire_creature_portrait.py`,
   `web/src/lib/portraitOrder.ts`, `web/src/App.tsx`.

### Etapa 5 — Scripts de operação (R18, R19)

1. **Testes** (`tests/test_spec367_ops_pool.py`): `test_retry_on_checkout_timeout_then_ok`,
   `test_no_retry_after_execute_error`, `test_kill_switch_apply_sets_once`, `test_preflight_closes_pool_on_error`,
   `test_exhausted_retries_exit_nonzero_short_message`, `test_no_dsn_in_output`. Os testes atuais
   (`tests/test_spec196_finops.py`, `tests/test_spec363_portrait_offer.py::test_art_preflight_causes`) continuam
   verdes.
2. **Implementação:** `scripts/staging/ops_pool.py` e os dois scripts.

### Etapa 6 — Guardas (R20–R25)

1. `tests/test_spec367_guards.py` (flags sem diff; golden 330 sem diff; nenhum spec existente em `web/e2e/`
   alterado; sem diff em orquestrador/`scene_cards`). Extensão de `tests/test_spec363_ids.py` (R25).
2. Front: `npm run typecheck`, `lint`, `test`. A arena de balanço não é necessária, porque nenhuma regra de motor
   muda.
3. Expected de testes antigos que mudarem entram no §9 com o motivo. Esperado: nenhum. Se algum teste fixar uma
   das 8 frases antigas do presságio, troca só a string.

## 5. Critérios de aceite

- [x] Etapa 0 anotada no §9
- [x] A1: pergunta com nome parcial cota a entrada certa; ambíguo/curto cai na consulta; venda afirmativa e 364 R4/R6 intactas (R1–R3)
- [x] A2: oferta some e o selo "Gerando retrato…" aparece ao confirmar; duplo clique = 1 cotação/1 confirmação; falha não esconde à toa (R4–R6)
- [x] A3: presságio com "você" para o herói; catálogo sem "de {alvo}"; invariante pela API (R7–R9)
- [x] A4: fallback sem oferta e sem reutilizar `tipo:fallback_*`; cotação 409; retirada com `--env-file`/`--dry-run` (R10–R12)
- [x] A5: "A condição Cego de Goblin-Mineiro terminou.", uma vez por evento, em todas as superfícies (R13, R14)
- [x] A6: contexto com antes/preço/depois; V-G rejeita o texto real e aceita o correto; corpus benigno sem disparo (R15–R17)
- [x] A7: scripts com abertura tolerante e retry só no checkout; `set` 1 vez; pool fechado em erro (R18, R19)
- [x] 0 LLM por rodada (R20); nenhum `with_structured_output` novo (R21); sem flag nova (R22); contrato aditivo (R23)
- [x] Golden 330 e specs existentes de `web/e2e/` sem diff (R24); invariante de ids/voz estendido (R25)
- [x] `uv run pytest` verde (suíte completa, coordenador, no pouso); `npm run typecheck`, `lint`, `test` verdes
- [x] Revisão independente `Sol` sem P0/P1 aberto
- [x] **Smoke real §6 (coordenador)** executado e registrado em `docs/spec367/smoke-final.md`

## 6. Smoke test com LLM real (≤ 6 turnos; só os achados)

Local `legacy` (preset de `scripts/staging/staging_flags.json`, cartas `on`, `RPG_CREATURE_ART=on`) e staging
(`hosted-supabase`, conta sintética pelo caminho de `two_user_smoke`, limpeza no fim). DeepSeek é o primário.
Registrar em `docs/spec367/smoke-final.md` (trechos, sem segredos), com provider/modelo, chamadas e custo.

1. **Operação, antes de tudo (0 turno):**
   - `admin_kill_switch.py --dsn-env RPG_STAGING_DB_URL --env-file .env.staging list` e `art_preflight.py`, 3 vezes
     cada: nenhum `PoolTimeout` chega ao operador; se houver retry, ele aparece como `ops.db_retry` (R18, R19).
   - **Retirar o retrato de fallback [D-367-4]:**
     `retire_creature_portrait.py "tipo:fallback_criatura_hostil" --env-file .env.staging --reason "SPEC-367 A4: retrato de inimigo de fallback" --dry-run`,
     depois o mesmo comando sem `--dry-run`. Esperado: `status: retired` e `objects_failed: []`. O dono pode vetar
     esta retirada (§8); com veto, pular e anotar.
2. **Local, loja (2 turnos), herói com item livre de nome longo:**
   - "Posso vender a <3 primeiras palavras do item>?" → cotação da entrada, sem delta (R1, R2).
   - "Quero comprar a <Carta> da <mercador>" com saldo final > 0 → narração sem "últimas moedas" e sem número de
     ouro fora de {antes, preço, depois}; se V-G disparou, anotar `trade_prose_rejected` (R15, R16).
3. **Local, combate (abertura + até 2 rodadas):** presságio do chip a 390 e a 1440 com "você" e sem o nome do
   herói (R7, R9). Se uma condição de inimigo terminar, conferir a frase de R13 no registro e no Livro. Se não
   ocorrer, anotar como não verificado (R14 cobre por teste).
4. **Staging, retrato (1 turno + no máximo 1 geração):** chip "Gerar retrato (até X Estilhas)" → "Gerar" → o
   chip troca na hora para "Gerando retrato…" sem o botão, a 1440 e a 390 (R4). Um 2º clique não é possível.
   `/art/quote` foi chamado 1 vez (R5). Se a abertura cair num inimigo `fallback_*`, a oferta não aparece (R10).
   Desligar `image_generation` no fim, como nos smokes 4 e 5.
5. Varrer o `/game/history` das campanhas: 0 ids, 0 nome do herói, 0 `": … terminou"` cru (R25).

## 7. Riscos & compatibilidade

- **Sobreposição com a SPEC-368 (branch `spec-368`).** A 368 mexe em `agents/combat.py`, `api.py`,
  `services/card_piles.py` e `data/cards/`. A 367 **não toca** `agents/combat.py`, `card_piles.py` nem
  `data/cards/`: A3 entra em `enemy_intent.py` + `pressagio_sinais.json`, e A5 em `round_log.py`. Em `api.py`, a
  367 acrescenta **uma** guarda em `_offer_brief_for_quote` (R11), na área do retrato pago, longe do fluxo de
  cartas. Quem pousar depois faz o rebase (`wt.sh sync`). Se der conflito, a guarda pode mudar para
  `creature_art` (uma função chamada pelo endpoint) sem mudar o requisito. Os testes de R9/R14 leem a view pela
  API e podem precisar de rebase se a 368 mudar a forma de `combat` na view.
- **R1 pode cotar a entrada errada.** O prefixo exige 2 tokens significativos e devolve `None` quando há
  ambiguidade. O erro residual é uma **cotação** errada, nunca uma transação, porque a pergunta não transaciona
  (364 R6).
- **R8 muda o texto do conteúdo.** São 8 frases de um catálogo marcado "revisão do dono pendente". O sentido
  fica e o dono pode vetar frase a frase (D-367-2).
- **R10 tira a arte de inimigos de fallback** que hoje mostrariam a imagem `tipo:fallback_*` do pool. É
  intencional: um "Criatura hostil" genérico não deve herdar a imagem de outro.
- **R16 aumenta o fallback da narração da loja.** Um falso positivo custa só prosa (o `[SISTEMA]` não muda).
  Corpus benigno e regra (b) só com `depois > 0` limitam o alcance. Medir no §6.
- **R18 com retry:** só no checkout, sem duplicar escrita; `max_size=1` basta para scripts de uma thread.
  O timeout maior (20 s) só atrasa a falha real do operador.
- **R4 é otimista no cliente.** Se a confirmação deu certo, o servidor já está `pending`; o próximo estado
  confirma ou, se o job falhar, devolve a oferta (a regra de hoje).
- **Saves:** nada novo é persistido. **MockLLM/FallbackLLM:** guard mantido; R16 roda sobre o texto do Mock.
  **Quota/latência:** nenhuma chamada nova.

## 8. Decisões

### Do dono / coordenador (prompt de 02/11)

- Escopo fechado em A1–A7 do smoke final da 364; §6 ≤ 6 turnos só nos achados.
- A4: não oferecer retrato pago para `fallback_*`, e o coordenador retira a entrada `tipo:fallback_criatura_hostil`
  do pool do staging no smoke. **O dono pode vetar a retirada.**
- A6: mecânica é Python; a narração recebe o saldo real, e uma validação barra número de ouro divergente.
- A7: retry/timeout adequados nos scripts de operação.
- Guardas: golden 330 e `web/e2e` intocados; sem flag nova; 0 LLM por rodada.

### Do autor (valem como aprovadas; o dono pode vetar na revisão)

- **D-367-1 — Prefixo com 2 tokens significativos, nunca similaridade difusa.** É determinístico, explicável e
  devolve `None` quando há ambiguidade. A sugestão do smoke ("prefixo de ≥ 2 palavras do `short_display`") foi
  endurecida para "≥ 2 tokens significativos" porque "Faca de" casaria qualquer faca.
- **D-367-2 — Reescrever 8 frases do presságio em vez de flexionar "de você".** Flexão por regra ("de você" →
  possessivo) gera português pior que a reescrita. A tabela do §3.3 é a proposta; veto do dono troca frase a
  frase.
  **Decidido em 09/11, pelo coordenador com delegação do dono ("confio em vc nas decisoes"): ficam as 8
  reescritas do §3.3, como implementado.** Nenhuma frase foi vetada.
- **D-367-3 — V-G rejeita, não reescreve.** É o mesmo modelo de V1–V6 (`conflict_summary`): texto inválido vira
  o fallback determinístico. A regra (b) cobre o caso real ("últimas moedas" com saldo > 0), que (a) não pega,
  porque o 45 era o preço certo.
- **D-367-4 — Retirar com `retire_creature_portrait.py`, não com `spec222_art_purge.py`.** O prompt citou o
  `spec222_art_purge.py`, mas ele é o fluxo E2E da SPEC-222 R6: cria usuário, gera arte paga nova e apaga a
  campanha. Ele **não** remove uma chave do pool e ainda gastaria uma geração. A ferramenta certa é a de
  moderação da SPEC-352 R13 (`ready` → `retired` + objetos), que só ganha `--env-file`/`--dry-run` para rodar
  da estação.
- **D-367-5 — Manter a cópia "Outro jogador já está gerando…".** `web/e2e/spec352-retrato-pago.spec.ts:90` a
  fixa, e a guarda proíbe editar e2e existente. Com R4/R5, o próprio jogador deixa de vê-la depois do seu clique.
- **D-367-6 — Scripts com `max_size=1`, `timeout=20`, `connect_timeout=10` e 3 tentativas.** Os scripts fazem
  uma conexão por vez; o tempo maior absorve o handshake lento do pooler, e o retry só no checkout não repete
  escrita.

### Pendentes do dono

- Nenhuma bloqueia a execução. Há dois vetos possíveis: a retirada de `tipo:fallback_criatura_hostil` no staging
  (§6.1) e o texto das 8 frases do presságio (D-367-2).

## 9. Registro de implementação

**Etapa 0 (confirmações).** A1: o teste de nome parcial falhou com a consulta antes do código. A4: o
fallback chega ao jogador como `fallback_criatura_hostil[_N]`; `is_fallback_enemy` testa id, id sem
sufixo `_N`/`_rN`, `bestiary_id` e `normalize_bestiary_id`. A5: registro, linhas de status (`_normalize_status_logs`)
e `mech_log` passam por `round_log._voce`. A7: `PoolTimeout` sai do checkout antes de qualquer `execute`.

**Commits (branch `spec-367`).** (1) R1-R3 prefixo; (2) R7-R9/R13-R14 voz; (3) R15-R17 ouro; (4) R10-R12
fallback e retirada; (5) R4-R6 front; (6) R18-R19 pool de operação; (7) guardas R22/R24 e este registro.

**Desvios.**
- R16: "um/uma" só vale como cifra colado ("uma moeda"); "uma bolsa de moedas" não é cifra (evita falso
  positivo). A regra (b) aceita um número entre "últimas" e "moedas" ("últimas 45 moedas", o texto real) e
  "bolsa (palavra) vazia".
- R9: o teste usa o nó de combate real + `api._combat_block` (a view de `/game/state`), sem TestClient.
- R18: `OperationalError` só é repetido se nenhum frame de comando (`execute`...) está no traceback.
- R12: `--env-file` usa `dotenv.load_dotenv(override=False)`; `--dry-run` faz um `select` somente leitura.
- Expected de teste antigo alterado: `tests/test_spec364_market.py::_capture` (`fake` aceita `gold_check`).
  Nenhum expected de frase do presságio mudou.
- R5 e R4: a trava `portraitInFlight` (useRef) e `withPortraitPending` estão em `App.tsx`/`portraitOrder.ts`;
  o e2e novo cobre duplo clique (`dblclick`) = 1 cotação e 1 confirmação, a 390 e 1440.

**Correções da revisão Sol (9 achados, todos tratados).** P1-1: código `creature_portrait_not_offered` no catálogo
(+ `CODIGOS_DE_ERRO.md`, `errorCodes.json`, `errorMessages.ts`; o front esconde a oferta e avisa). P1-2: guarda
`test_spec367_guards.py` só na branch `spec-367` (`merge-base main HEAD`; `skip` fora). P2-1: `OperationalError` só é
repetido com detecção positiva de checkout (`getconn`/`connection`) e nenhum frame de comando/commit; teste de 1 escrita
no commit. P2-2: V-G pega número por extenso após "últimas" e "sem moedas". P2-3: R9 com Smoke5A/Mirela5, famílias
fera/morto_inquieto, ≥2 inimigos e asserção de lista não vazia. P3-1: cotação exata no teste. P3-2: `test_spec367_condition_node.py`
(API real: mech_log, registro, mensagem e Livro). P3-3: sem `except` em `is_fallback_enemy`. P3-4: `--env-file` inexistente é erro.
Evento de log novo (`loot.trade_prose_rejected`) registrado em `observability/events.py` e `EVENTOS_DE_LOG.md`.

**Fica para o smoke §6 (coordenador):** retirada de `tipo:fallback_criatura_hostil` no staging (`--dry-run` e
real), 3 execuções de `list`/`art_preflight` sem `PoolTimeout`, cotação por nome parcial e narração da compra
com LLM real, presságio com "você" no chip, chip "Gerando retrato…" no staging.

**Smoke §6, operação (03/11, coordenador):** `--env-file .env.staging` sozinho não serve fora da Vercel (o
`build_runtime` hosted exige perfil, DSN `rpg_runtime` e bind que só existem lá; caía no `FileGameStore`, sem
apagar nada). Correção: `--dsn-env RPG_STAGING_DB_URL` usa o pool de operação (`ops_pool`) e o bucket
`rpg-shared-art` com `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`, fecha o pool no fim; teste
`test_retire_dsn_env_uses_ops_pool_and_closes_it`. A chave real do retrato de fallback no pool é
`tipo:gen:criatura-hostil` (rótulo de espécie), não `tipo:fallback_criatura_hostil`; o inimigo continua com id
`fallback_criatura_hostil_1`, então o guarda de R10 vale. Retirada feita: dry-run `ready` com 2 objetos →
`status: retired`, `objects_deleted: 2`, `objects_failed: []`.

- **Fechamento:** Auditoria de fechamento (04/11, coordenador; auditor só leitura cruzou cada critério com evidência): revisão Sol final aprovada (`handoffs/SPEC-367-sol-review.md` quando existe), suíte completa verde nos pousos, smokes reais: `docs/spec363/achados-smoke3.md`, `docs/spec364/achados-smoke4.md`, `docs/spec364/smoke-final.md`, `docs/spec367/smoke-{local,staging}.md`, `docs/spec368/smoke-local.md`, `docs/spec387/smoke-{local,staging}.md`, `docs/spec389/smoke{,-local}.md`, `docs/spec390/smoke.md`. Métricas não atingidas do épico ficam registradas (D-368-1) e seguem para a SPEC-369. A1–A7 verificados em `docs/spec367/smoke-{local,staging}.md`; R4 (chip "Gerando retrato…") falhou ao vivo e foi corrigido e verificado na 387 (100 ms). Ressalva: ramo `trade_prose_rejected` (V-G) nunca disparou ao vivo, só por teste.
