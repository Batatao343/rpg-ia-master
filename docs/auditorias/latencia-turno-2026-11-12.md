# Latência do turno: auditoria e plano de specs (2026-11-12)

> **Status:** v2, **depois da revisão cruzada** (§10). Pode virar specs na ordem do §6.
> **Pedido do dono (12/11):** "o jogo tem que ficar mais rápido; a gente está no TikTok, tem que perguntar e responder". Hipóteses dele: o RAG é consultado "de maneira burra"; deixar o RAG pré-carregado; separar memória de curto e de longo prazo.
> **Método:** três auditores Sonnet somente leitura (A: chamadas de LLM; B: RAG, memória, arquivista e banco; C: frontend, SSE e deploy), um pesquisador Sonnet na web (38 fontes), conferência do coordenador nos achados de maior peso, e um revisor independente Fable com quatro verificadores Sonnet próprios, instruído a derrubar o relatório.
> **Nada foi executado nem medido nesta auditoria.** Todo número vem de medição já gravada no repo ou de fonte externa citada.
> **`main`:** `2711a92c`. **Staging:** `d7aa4beb` (10/11).

Rótulos: **[F]** fato lido no source (`arquivo:linha`) · **[F✔]** fato conferido por duas leituras independentes (auditor + coordenador ou revisor) · **[M]** medição gravada no repo · **[D]** derivado de medições (conta, não medição direta) · **[W]** fonte externa (§9), não reconferida pelo revisor · **[H]** hipótese: falta medir.

---

## 1. Resposta curta

1. **O RAG não é o gargalo.** Montar o contexto custava 3,94 % do tempo do turno quando foi medido (17/10) **[M]**. As duas ideias do dono (RAG pré-carregado; curto × longo prazo) já foram implementadas e medidas na SPEC-214, que fechou em `NO_GO`. O conteúdo que entrou depois (rumores, tramas, fauna, quests) é Python sem LLM nem embedding **[F✔]**, então não muda o veredito. A literatura concorda: cortar metade do prompt rende 1 a 5 % de latência; cortar metade da **saída** rende cerca de 50 % **[W1]**.
2. **Antes de qualquer spec, uma pergunta decide o diagnóstico: onde o dono joga quando sente a lentidão?**
   - **Local, sem o preset do staging:** o jogo roda no caminho lento por construção. O texto só aparece no fim do turno, o classificador de intenção roda em todo turno (o Jev fica desligado) e o arquivista usa a política cara **[F✔]**.
   - **Link do staging, depois de um tempo parado ou de um deploy:** a explicação mais simples é **instância nova da Vercel**. O repo registra esperas de 19 a 59 s antes de a função começar a responder, no plano Hobby, com bundle de 319 MB **[M]**.
   - **Link do staging, já quente:** aí valem os itens abaixo.
3. **Com o servidor quente, o que pesa** (ordem a confirmar pela medição L0):
   - **(a) Fechamento do turno com o envio travado.** Depois que a narração termina, o servidor ainda roda fichas de NPC, replanejamento, arquivista e gravação, e o envio só libera no fim. A diferença entre as medianas de "narração completa" e "envio liberado" é de 3,6 a 5,2 s **[D]** num roteiro de estresse; o valor por turno comum não foi calculado e pode ser bem menor.
   - **(b) Conversa com NPC**, o tipo mais "pergunta e resposta", é o mais lento até o primeiro texto (7,6 a 9,2 s; amostra pequena) **[M]**.
   - **(c) "Carregar a mensagem inteira".** A última frase da narração fica retida até a chamada inteira terminar, incluindo os campos finais do JSON **[F✔]**; e a narração é longa (2 a 3 parágrafos mais opções, sem teto).
   - **(d) A abertura do jogo** (prólogo + primeiro turno) não tem streaming **[F✔]**.
   - **(e) Campanhas longas:** o commit reinsere o histórico de eventos inteiro a cada turno, inclusive em cada rodada de carta **[F✔]**. Custo sem teto, nunca medido em sessão longa.
4. **A última medição é de 27/10** e cerca de 430 commits tocaram o caminho do turno desde então. Parte do que falta saber já está nos logs e custa zero ler.

---

## 2. O que está medido hoje

Última medição completa: staging, DeepSeek, 60 turnos (30 com as otimizações ligadas), 27/10 ([docs/spec316/staging-measure-2026-10-27.md](../spec316/staging-measure-2026-10-27.md)) **[M]**. O roteiro é o de **estresse**: 9 de 15 turnos são dos tipos pesados (NPC novo, conversa, viagem de região, virada de dia).

| Momento do turno | p50 | p95 (n=30: é a 2ª pior observação) |
|---|---|---|
| Primeiro texto na tela (cliente) | 2,6 s | 9,8–11,8 s |
| Primeiro texto (servidor) | 2,4 s | 6,2–7,5 s |
| Narração completa | 6,1 s | — |
| Envio liberado (evento `state`) | 9,8–11,4 s | 17 s |

Leituras:
- A cauda do cliente (9,8–11,8 s) é 3 a 4 s maior que a do servidor (6,2–7,5 s): essa parte está **fora do handler** (rede, fila da plataforma, instância nova). O 11,75 s coincide com a sessão que teve um cold start.
- O "envio liberado" não melhorou com as SPEC-316 a 319: só o texto chegou antes.
- Por tipo (primeiro texto, mediana, n=2–3 por sessão): cena 2,1–2,2 s; viagem 2,2–2,3 s; descanso 2,4–4,1 s; NPC novo 2,4–4,5 s; **conversa com NPC 7,6–9,2 s**.
- No roteiro padrão (não o de estresse), 17 de 29 turnos não fizeram nenhuma chamada SMART (`specs/SPEC-318-latencia-trabalho-fora-do-caminho-critico.md:240`): no turno comum o fechamento pode ser curto. **Não há medição do intervalo por turno**, mas o servidor já o registra (`early_gain_ms`, `routes/turn.py:1568`).

Instância nova da Vercel **[M]**:

| Medição | Valor | Fonte |
|---|---|---|
| Espera antes de `sse.started` | 19–59 s | `specs/SPEC-317-latencia-classify-contexto-paralelo-cache.md:216-217` |
| `/health` | p50 35 ms, máx. 19,1 s (1 em 30) | idem |
| Ack do SSE | p95 19,3 s, máx. 58,9 s | `docs/spec213/staging-measure-2026-10-18.md:37,46` |
| Primeira request após deploy | 6,8–10 s | `docs/spec192/README.md:30` |
| Turnos com cold start em 26/10 | 5 de 15 por braço | `specs/SPEC-318-…md:218-219` |

Plano Hobby, bundle de 319 MB, região `gru1`; pré-aquecimento só existe nos planos pagos; "conferir Fluid Compute" ficou como pendência (`specs/SPEC-317-…md:228-230`).

Decomposição por fase mais recente (17/10, antes das SPEC-316 a 319): arquivista 3,36 s p50; contexto 0,41 s p50; persistência 0,21 s p50 (`docs/spec214/gate-real-2026-10-17.md:34-40`). Ficha completa de NPC: 6,3 s p50 em bancada isolada (`specs/SPEC-318-…md:135`): é maior que o arquivista e hoje roda depois da narração, antes de liberar o envio.

Referência de percepção **[W2]**: até 1 s o fluxo de pensamento não quebra; 10 s é o limite da atenção.

---

## 3. As hipóteses do dono, uma por uma

| Hipótese | Veredito | Evidência |
|---|---|---|
| "Consulta o RAG de maneira burra toda vez" | **Derrubada na maior parte.** | No turno comum de história há um embedding, reaproveitado para lore, sessão e NPC (`services/context_sources.py:49-84`) e pré-buscado em paralelo ao roteador (`services/context_prefetch.py:84-123`). Combate e rodada de carta nem consultam lore (`agents/combat.py:1080`) **[F✔]**. Fraquezas reais: +1 embedding em linha na conversa com NPC (sem pré-busca, `context_sources.py:58`), +1 no replanejamento (`agents/campaign_manager.py:186`), +1 ao criar NPC ou criatura; não há gate "esta ação precisa de lore?". O cache do índice FAISS só vale no perfil local; no hosted o lore vem do Postgres. |
| "Deixar um RAG pré-carregado na conversa" | **Já tentado: SPEC-214, `NO_GO` por medição** (18/10). | O cache de cena deu −1,2 % no turno: o arquivista invalidava o cache quase todo turno e o contexto era 3,94 % do tempo (teto de ganho ~0,4 s) **[M]**. Variante não tentada: cache de **lore** por local/região, fora da chave de memória. Ganho máximo: uma ida ao provedor de embedding por turno de história. |
| "Curto prazo vai na chamada, longo prazo chama o RAG" | **Já é assim.** | Curto prazo: últimas 3 mensagens (`agents/storyteller.py:2322`), resumo rolante, últimos 20 fatos (`services/context_builder.py:974-985`). Longo prazo: busca vetorial de lore e de sessão **[F✔]**. O ponto fraco é de **qualidade**, não de velocidade: o resumo pode ficar ~10 turnos velho, e no hosted um fato novo só entra na busca vetorial depois do job de embedding (`infrastructure/pgvector_memory.py:216-236`). |

Ressalva honesta: 3,94 % é fração do turno inteiro (~10,5 s). Contra o **primeiro texto** (2,6 s), os mesmos 0,41 s seriam ~16 % **se** a pré-busca for a perna mais longa do par "roteador + contexto" **[H]**. A L0 mede contexto contra primeiro texto. Mesmo no pior caso, o teto de ganho é ~0,4 s.

O que a literatura de memória de agentes recomenda **[W3]** não é consultar menos, é **escrever** a memória em segundo plano.

---

## 4. Onde o tempo está

Sequência de um turno de história no staging, instância quente **[F✔]**:

```
Enter
 ├─ cliente: GET /operation (serial) ............ 1 ida e volta antes do POST e do eco
 ├─ servidor: rate limit, sessão, carga do save . ~8–10 idas ao Postgres em série
 ├─ ack
 ├─ roteador: Jev (prazo 1 s) e, se não cobrir, CLASSIFY (p50 1,3 s). Em timeout do Jev, os dois somam.
 ├─ narrador em stream ........................... PRIMEIRO TEXTO (2,6 s p50)
 ├─ fim da chamada (campos finais do JSON) ....... NARRAÇÃO COMPLETA (6,1 s p50); a última frase só sai aqui
 ├─ enrich: fichas de NPC (6,3 s p50 cada) + replanejamento (se devido)
 ├─ arquivista (se a política não pular)
 ├─ commit: save inteiro + reinserção do event_log + fatos de memória + turno + recibo + uso
 └─ evento `state` ............................... ENVIO LIBERADO (10–11 s p50, 17 s p95 no roteiro de estresse)
```

- **A rodada de carta passa pelo mesmo fluxo**, sem a chamada de narração: `getOperation`, pré-grafo, nós `enrich`/`archivist` e o commit com `_insert_events` (`web/src/combat/targeting.ts:106`, `infrastructure/postgres_turns.py:345`) **[F]**. Não chama LLM (`agents/combat.py:2527-2528`), mas "o meio do combate é rápido" **não tem medição**.
- **Todos os tiers usam o mesmo modelo**: `deepseek-v4-flash` é o primeiro candidato de CLASSIFY, FAST e SMART, com raciocínio desligado (`llm_setup.py:376-397,485-489`) **[F✔]**. O tier só muda a lista de fallback (e o timeout do CLASSIFY). Consequência: "rebaixar de SMART para FAST" não acelera nada no provedor primário.
- **Sem o preset do staging** o Jev fica `off` e o CLASSIFY roda em todo turno que passa dos gates determinísticos.

---

## 5. Achados, agrupados nas specs que eu abriria

Cada bloco é um candidato a spec. "Ganho" diz o que se sabe: **medido**, **estimado** (com a conta) ou **desconhecido**. Nenhuma estimativa deve virar critério de aceite sem a medição da L0.

### P0. Três perguntas e uma leitura de logs (custo zero, antes de tudo)

1. **Dono:** onde joga quando sente a lentidão (local × link do staging) e em que situação (primeira ação depois de um tempo parado × no meio da sessão).
2. **Painel da Vercel:** plano atual e se Fluid Compute está ligado no projeto do staging.
3. **Logs que já existem:** `early_gain_ms` por turno (intervalo real entre narração e `state`), `rpg_sse_ack_seconds` (fração de turnos com ack > 5 s), `llm_attempts` (duração por chamada, timeouts, fallback).

### L0. Medir o estado de 12/11, decomposto

- **Por quê:** a medição tem 16 dias; o intervalo de fechamento nunca foi decomposto; vários achados abaixo são [H] por falta de um número que o código já sabe produzir.
- **O que medir:**
  1. Duração **por chamada** de LLM e por nó (`enrich_ms`, `archivist_ms`, PERSISTENCE), por tipo de turno, n ≥ 10 por tipo, com conversa de NPC e rodada de carta representadas.
  2. `output_tokens` por nó e, se possível, por campo do JSON (prosa × campos de cauda); `input_tokens`.
  3. Banco: tempo por ida ao Postgres a partir de `gru1`; statements por turno; `db.commit_turn` em função de `len(event_log)` com **save sintético** (sem campanha longa real).
  4. Cliente: Enter → ack, com e sem o `getOperation`.
  5. Abertura: tempo de `/game/prologue` e de `/game/new` (sem nenhuma medição hoje).
  6. Contexto contra primeiro texto (ressalva do §3).
- **Custo:** real, DeepSeek. O A/B de 60 turnos de 18/10 custou ~US$ 0,25 (`docs/spec213/staging-measure-2026-10-18.md:91`); a L0 pede um pouco mais. **Precisa de autorização do dono** (execução paga no staging). Sem long-run.
- **Já se sabe e não precisa remedir:** fração de cache de prefixo no DeepSeek, mediana 0,015–0,052 (`specs/SPEC-317-…md:212-215`).
- **Risco:** baixo.

### L1. Cliente: ritmo de conversa

- **Achados:**
  - **C2 [F✔]** Todo turno espera `await api.getOperation(...)` (`web/src/App.tsx:487`) antes do POST e antes do eco da ação (`App.tsx:510`). Operação nova usa `crypto.randomUUID()` (`web/src/pendingOperation.ts:27-35`): o servidor não tem como conhecê-la, a consulta sempre volta "desconhecida". Vale também para cada jogada de carta.
  - **C1 [F✔]** `busy` só solta no `finally` do fluxo (`App.tsx:475,594`). Enter durante o turno é ignorado (`web/src/workspace/ChatSurface.tsx:187`); o botão fica desabilitado com "Aguardando o narrador" e há o selo "registrando…". **É comportamento aprovado:** SPEC-316 D2 ("input bloqueado até `state`") e SPEC-320 R13.
  - **C10 [F✔]** O cliente libera quando o corpo do stream fecha (`web/src/api.ts:242,257`). Hoje o servidor fecha logo após o `state` (`routes/turn.py:1872-1873`), então resolver no `state` não ganha nada sozinho: é só pré-requisito da L2.
- **L1a (sem decisão nova): pular o `getOperation` em operação recém-criada** e, só nesse caso, mostrar o eco da ação antes de qualquer rede. Quando já existia um pending (retry, reload), o fluxo atual fica como está: o eco vem depois da consulta de propósito (o ramo "concluído" restaura sem eco e o retry remove o eco órfão, `App.tsx:488-507`).
  - **Ganho:** uma ida e volta autenticada a menos em todo turno e em toda jogada de carta (valor: L0.4). **Risco:** baixo/médio; revisão por tocar a retomada da SPEC-320.
- **L1b (precisa de decisão do dono): fila de uma ação.** Enter durante o turno guarda o texto num chip "na fila"; quando o `state` chega e o pending é limpo, o cliente envia sozinho. Devolve o texto ao rascunho se houver combate, morte, erro, `replace` da narração ou "falhou depois de narrar".
  - **Por que é decisão do dono:** muda a UX aprovada na SPEC-316 D2. Não é a alternativa que ele rejeitou (liberar o envio na narração): nada vai ao servidor antes do save, que era o motivo da rejeição.
  - **Ganho:** estimado. Ler e digitar passam a se sobrepor ao fechamento do turno; a espera percebida entre turnos cai até o tamanho desse fechamento (3,6–5,2 s **[D]** no roteiro de estresse; desconhecido no turno comum). Não reduz tempo de servidor.
  - **Risco:** baixo/médio, só cliente. Armadilha conhecida: o `busy` do closure fica velho (`App.tsx:470`); o autoenvio precisa ser um efeito, não chamada direta. A fila e a L2 **se substituem** para o jogador rápido (a ação enfileirada esperaria na cerca de projeção).

### L4. Mostrar o texto assim que ele existe (NPC e narrador)

- **Achados:**
  - **[F✔]** O guard de stream nunca mostra a frase ainda aberta e segura a cauda até o `finish()`, que só roda depois de o modelo gerar os campos finais do JSON (`services/narrative_sink.py:213-215,242-243,364-368`). "Narração completa" inclui esse tempo, no narrador e no NPC.
  - **[F✔]** O guard segura o início enquanto houver menos de 120 caracteres sem quebra de linha (`narrative_sink.py:238-239`). Fala de NPC com menos de 120 caracteres só aparece no fim da chamada; fala maior começa a sair depois de 120.
  - **[F✔]** `NPCResponse.memory_update` é obrigatório (`agents/npc.py:176`) e não é lido por código de produção (deliberado: comentário em `agents/npc.py:1341-1342`). O modelo o gera em toda fala.
  - **[F]** O embedding da conversa com NPC é em linha (`context_sources.py:58`) e o leitor de sessão roda mesmo quando o gate de conhecimento descarta o resultado (`context_sources.py:122-131`, `services/context_builder.py:962`).
- **Mudança:** (1) descarregar o guard quando o campo de texto **fecha** no JSON (`services/partial_narrative.py:52` já expõe `done`), sem esperar os campos de cauda: proposta do revisor, não testada; (2) remover `memory_update` (ganho pequeno: uma frase); (3) pré-busca do embedding de NPC como **dica**, sem promover `RPG_ROUTER_DETERMINISTIC_NPC` (segue `shadow`, SPEC-317); (4) pular o leitor de sessão descartado.
- **Ganho:** estimado. (1) antecipa "narração completa" pelo tempo de geração dos campos de cauda (L0.2 dá o número) sem mudar a prosa. É o item que mais diretamente responde a "carregar a mensagem inteira".
- **Risco:** médio para (1): mexe no guard; mesmo gate da SPEC-319 D1 (`would_replace` < 5 %). Baixo para (2) e (4); (2) toca `MockLLM` e ~15 testes.

### L7. Banco no caminho do turno

- **Achados:**
  - **B4 [F✔]** `_insert_events` percorre o `event_log` **inteiro** a cada commit: para cada evento já gravado, um `INSERT … ON CONFLICT DO NOTHING` sem retorno e depois um `SELECT` de conferência (`infrastructure/postgres.py:228-258`). Duas idas ao banco por evento antigo, por turno e por rodada de carta. O log serializado não tem corte (`persistence.py:748`). Custo sem teto; medido só em sessões de 15–20 turnos. **Quem mais joga é quem mais espera.** O número de eventos por campanha é desconhecido.
  - **[F]** O save é reescrito inteiro por turno: `SELECT … FOR UPDATE`, `UPDATE` com o JSONB completo, sha256 do documento, duas cópias profundas do estado. Crescem sem teto: `event_log`, `chronicle`, `presentation_history`, `art_generation_ledger`, `memory_canonical_facts`.
  - **B2 [F✔]** No pooler transacional, cada checkout executa `SET LOCAL statement_timeout` e `SET LOCAL lock_timeout` em duas idas separadas, mais a troca de papel (`infrastructure/postgres.py:134-144`).
  - **B3/C4 [F✔]** O turno em stream carrega o save duas vezes (`routes/turn.py:1884` e `:1328`), 2 selects cada; a primeira atrasa o ack.
  - **C3 [F]** Antes do grafo: rate limit por IP (transação), sessão no Postgres, recibo, claim, teto de gasto, rate limit por dono, cota diária: 8 a 10 idas em série. A chamada HTTP ao GoTrue é cacheada 20 s por instância (`infrastructure/supabase_identity.py:350-354`).
- **Ganho:** desconhecido. Depende do tempo por ida a partir de `gru1` (L0.3). Se for 5 ms, B2/B3/C3 somam décimos de segundo; se for 30 ms, mais de 1 s. B4 é o único com crescimento ilimitado.
- **L7b (risco alto, persistência; primeiro se a L0 confirmar B4):** um único statement para os eventos, **preservando a checagem de payload divergente** (`postgres.py:257-258`). Inserir só o diff perderia essa checagem em evento antigo.
- **L7a (risco baixo/médio):** um `select set_config(...)` por checkout; reaproveitar o save do handler; cache de identidade mais longo (revogação demora mais a valer: revisar contra SPEC-219/220).

### L11. Infra: instância nova e cold start (decisão do dono)

- **Achados [M]:** tabela do §2. Plano Hobby não tem pré-aquecimento; bundle de 319 MB; a SPEC-317 já tinha apontado "spec de infra (dieta do bundle, conferir Fluid Compute, ping de aquecimento, plano)" e o `ESTADO_ATUAL.md` amarra a "spec de cold start" ao "go" da SPEC-197. O `pg_cron` do staging chama `/internal/cron/jobs` e esquenta no máximo uma instância.
- **Por que sobe de prioridade:** tráfego que vem de vídeo chega em rajada e abre várias instâncias ao mesmo tempo; para o visitante novo, a primeira ação é exatamente a que cai em instância fria.
- **Alavancas:** plano pago com pré-aquecimento; Fluid Compute (várias invocações na mesma instância **[W7]**); dieta do bundle; ping de aquecimento.
- **Quem decide:** dono (custo recorrente de plano). **Ganho:** remove esperas de 19–59 s nos turnos afetados; frequência no tráfego real desconhecida (P0.3).

### L5. Saída menor: narração no tamanho do público

- **Achados:**
  - **A9 [F✔]** Nenhuma chamada passa `max_tokens` (`llm_setup.py:504-512`). Os únicos tetos são os timeouts (12 s DeepSeek, 6,5 s CLASSIFY, 90 s nos demais).
  - **A7 [F✔]** O narrador pede 2 a 3 parágrafos (`agents/storyteller.py:2591`) e 2 a 3 opções (`storyteller.py:2211-2215`), sem limite de palavras. Instruções de `faction_impacts`, `membership_action`, `proposed_events` e `proposed_quests` aparecem no prompt (`storyteller.py:2544-2573`) e de novo nas descrições do schema (`storyteller.py:110-170`).
- **Mudança:** (1) decisão de produto: tamanho-alvo da narração por tipo de turno; (2) tirar a duplicação prompt × schema; (3) teto de tokens só se for bem folgado: com saída estruturada, truncar vira JSON inválido e fallback, e piora a cauda.
- **Ganho:** estimado, com a conta corrigida: se a geração é o que separa 2,6 s de 6,1 s, cortar um terço da saída leva a narração completa a ~4,9 s (2,6 + 3,5 × ⅔); chegar a ~4 s exigiria cortar ~60 %. E parte desse trecho são os campos de cauda, que prosa menor não encolhe (isso é da L4).
- **Risco:** médio: muda a prosa. **Decisão do dono.** O alvo sai da distribuição de tokens da L0.2.

### L3. Arquivista só quando há o que arquivar

- **Achados:**
  - **B6 [F✔]** Em `lean`, o arquivista pula: conversa de NPC sem consequência, viagem na mesma região, loot barato e turno cujo único gatilho é memória pendente de NPC ou fato canônico (`agents/archivist.py:229-261,552`). Descanso, viagem entre regiões, NPC novo, fim de combate e quest nova pagam a chamada, mesmo com fatos já determinísticos.
  - **[M]** SMART por turno: 0,41 no roteiro padrão, 0,59 no de estresse.
- **Mudança:** nos turnos com fatos já canônicos, resumo sem LLM. Existe `extractive_digest` (`services/chronicle_compression.py:51`), mas é digest de capítulo da crônica: precisa de adaptação. Trocar o tier para FAST **não** ajuda (mesmo modelo).
- **Ganho:** estimado: uma chamada de ~3,4 s p50 **[M, 17/10]** a menos nos turnos afetados. Reduz o que a L2 teria de adiar e vale nos dois cenários.
- **Risco:** médio: qualidade de resumo e fatos. Exige `evals compare` de `memory_context` sem piora (quem otimiza não edita dataset).

### L2. Liberar o envio antes do arquivista (remedição da SPEC-213 com o stream segurado)

- **Achados:**
  - **B1/A3 [F✔]** `enrich` e `archivist` são nós do grafo (`main.py:167-169`) e o `state` só sai depois do commit (`routes/turn.py:1374-1375`). O replanejamento e o arquivista podem ter segunda chamada (reforço de idioma; fallback de resumo).
  - **[M]** A SPEC-213 mediu `post_response` no Vercel sem ganho: a função congela quando o stream fecha e o trabalho escorrega para o turno seguinte (`docs/spec213/staging-measure-2026-10-18.md:51-59`). Decisão registrada: staging fica em `inline`.
- **O que há de novo (justifica remedir, não é reabrir):** emitir `state` e **manter o stream aberto** com pings até a projeção terminar. No código é `RPG_PROJECTION_MODE=post_response` mais um gerador que não retorna após o `state`. Ataca a causa medida do insucesso da 213.
- **Limites, apontados pelo revisor:**
  - Só adia o **arquivista**. Ficha de NPC e replanejamento gravam estado canônico (`npcs`, `campaign_plan`) lido pelo turno seguinte: não cabem sem um segundo commit canônico. O ganho esperado é "fração de turnos com arquivista × ~3,4 s", não o intervalo inteiro.
  - Depende de Fluid Compute (P0.2). Sem ele a instância fica ocupada até o stream fechar e o turno seguinte pode cair em instância fria.
  - Nunca rodou junto com narração antecipada e stream de tokens; na medição da 213 a crônica ficou com 0 entradas em `post_response` (`staging-measure-2026-10-18.md:73-76`).
- **Antes de escrever a spec:** teste de descarte de um dia com `scripts/staging/projection_measure.py`.
- **Risco:** alto (estado, persistência, concorrência). Revisor obrigatório. Só se a L0 mostrar que o arquivista domina o fechamento **depois** da L3.

### L6. Cauda dos providers

- **Achados:**
  - **A2 [F✔]** Timeout de 12 s (DeepSeek FAST/SMART), 6,5 s (CLASSIFY), 90 s (fallback Groq) (`llm_setup.py:501-503,588-596`); o circuito só abre por erro permanente, nunca por timeout (`llm_setup.py:560-584`).
  - **A8 [F]** Teto de 2 chamadas simultâneas por provider no processo, configurável por env; o stream ocupa o slot inteiro (`llm_setup.py:49-55,1487-1529`). A geração de criatura só disputa slot no perfil local (no hosted é job).
  - **A6** Um cliente por (provider, modelo, temperatura) (`llm_setup.py:551,603-614`) **[F✔]**. "Refaz TLS a cada turno" é suposição sem evidência **[H]**.
- **Contra-evidências [M]:** o hedge de 6 s teve **zero disparos** em 27/10 (o primeiro token do narrador não passou de 6 s na amostra). E há narrador com 13,4 s de máximo e 0 tentativas falhas: o timeout de 12 s provavelmente não é teto de relógio em stream. **O peso de A2 na cauda é [H]** até a L0 dizer que fração das chamadas estoura. O "p99 de 6,0 s" do CLASSIFY (`docs/spec363/classify_latency.json`) é um único ponto (n=22).
- **Mudança:** depende da L0. Candidatos: circuito por timeouts repetidos; timeouts por percentil medido; cliente HTTP único por provider. Não é o hedge da SPEC-319.

### L8. Primeira impressão (do link ao primeiro texto)

- **Achados:**
  - **C7/A13 [F✔]** `/game/prologue` é uma chamada SMART sem stream (`services/prologue.py:432,518`), passo obrigatório do wizard; `/game/new` roda `game_graph.invoke` completo, sem SSE, sem narração antecipada e sem fases (`routes/turn.py:290`). Há mensagens de espera ("O destino tece seu prólogo…", "Forjando…", `web/src/components/CreateScreen.tsx:138-141`), mas o texto chega de uma vez. Com cenário, a abertura não replaneja e o arquivista tende a pular o LLM no turno 0. **Sem medição.**
  - **C8 [F✔]** Bundle web único (o único `import()` dinâmico é nativo); `getAuthConfig` e `getSaves` em série no bootstrap (`App.tsx:161,192`).
- **Mudança:** abertura pelo mesmo SSE do turno; code splitting das telas fora do chat; bootstrap em paralelo.
- **Ganho:** desconhecido (L0.5). **Risco:** alto na abertura por SSE (`commit_create`, idempotência de criação); baixo no bundle.

### L9. Combate: abertura e desfecho

- **Achados:**
  - **A4 [F✔]** Na abertura, a preparação de cena (FAST sem stream, schema grande) roda antes da narração de entrada (`agents/combat.py:1036-1046,3022,3658`). Gatilho: `abyss_tier != "nenhum"` (limiar padrão 1, configurável por classe) ou categoria elite/chefe/nomeado. A entrada não lê a cena para escrever, mas o `manifest` dos guards é montado com `scene=t.scene` (`combat.py:3075`): reordenar exige desfazer essa dependência. Sem flag para desligar.
  - **A12 [F✔]** Em vitória, o desfecho fica retido até o loot narrar (`services/turn_delivery.py:13,52-53`).
- **Mudança:** narrar a entrada primeiro e preparar a cena depois (reordenação sequencial, não paralelismo: não esbarra no `NO-GO` da SPEC-143); entregar o desfecho antes do loot.
- **Ganho:** estimado: primeiro texto do combate uma chamada FAST antes. O tabuleiro e o `state` continuam esperando a preparação.
- **Risco:** médio no código; combate exige `spec-reviewer`.

### L10. Defaults: não é spec nova, é decisão pendente da SPEC-384 D2

- **Achado [F✔]:** `RPG_EARLY_NARRATIVE=shadow`, `RPG_TOKEN_STREAM=shadow`, `RPG_ARCHIVE_POLICY=legacy` são os defaults do código (`config/flags.yaml:44-48,337-339,1083-1085`); só `scripts/staging/staging_flags.json` liga. Sem o preset, o SSE descarta os deltas e a narração sai depois do grafo e do commit (`routes/turn.py:1848-1858`).
- **Já decidido / pendente:** as duas flags `shadow` estão na tabela da SPEC-384 D2 com recomendação `on` e **aguardam a marcação do dono** (`specs/SPEC-384-poda-decisoes-dono-flags-perfis.md:395-396`); a execução foi definida como spec própria. `ARCHIVE_POLICY` foi decidida como "`legacy` na main" na SPEC-318 D4: promover para `lean` é reabrir essa decisão, e cabe ao dono.
- **Correção de leitura:** o estado default **não** é o braço "OFF" medido em 27/10 (que também desligou `NPC_TWO_PHASE`, `REPLAN_AFTER` e usou `DAY_DIGEST=llm`). Não há medição do estado default; ele fica entre os dois braços, com CLASSIFY em todo turno.

---

## 6. Ordem recomendada

| Ordem | Item | Por quê nesta posição | Risco | Quem decide |
|---|---|---|---|---|
| 0 | **P0** perguntas + leitura de logs | custo zero; separa "preset", "instância fria" e "fechamento do turno" | nenhum | dono responde |
| 1 | **L0** medição reduzida | dimensiona todo o resto | baixo | dono autoriza o gasto |
| 1 (paralelo) | **L1a** pular `getOperation` em operação nova | não depende de medição; vale para cartas | baixo/médio | coordenador |
| 1 (paralelo) | **L1b** fila de uma ação | ataca "perguntar e responder" sem tocar o servidor | baixo/médio | **dono** (muda a 316 D2) |
| 1 (paralelo) | **L10** marcar a tabela da 384 D2 | decisão já preparada | baixo | **dono** |
| 2 | **L4** texto assim que existe | mexe em "mensagem inteira" e em NPC sem mudar a prosa | médio | coordenador + revisor |
| 2 | **L7b**, depois **L7a** | único custo sem teto; afeta cartas; só se a L0 confirmar | alto / médio | coordenador + revisor |
| 3 | **L11** infra | precisa estar resolvida **antes** do tráfego do TikTok | baixo | **dono** (plano) |
| 3 | **L5** saída menor | alvo definido pela distribuição de tokens | médio | **dono** (tamanho da narração) |
| 4 | **L3** arquivista | menor risco que a L2 e reduz o que ela adiaria | médio | coordenador + eval |
| 5 | **L2** envio antes do arquivista | só se a L0 e o teste de descarte justificarem | alto | coordenador + revisor |
| 6 | **L6** cauda · **L8** abertura · **L9** combate | ganho localizado; L8 sobe se a L0.5 mostrar abertura longa | médio / alto | coordenador + revisor |

Decisões que só o dono pode tomar, juntas:
1. Onde joga quando sente a lentidão (P0.1).
2. Autorizar a medição L0 (~US$ 0,25–0,50 no staging).
3. Fila de uma ação (L1b): muda a UX aprovada na SPEC-316 D2.
4. Marcar `RPG_EARLY_NARRATIVE` e `RPG_TOKEN_STREAM` na tabela da SPEC-384 D2; dizer se `lean` vira default (SPEC-318 D4).
5. Tamanho-alvo da narração (L5).
6. Plano da Vercel e aquecimento (L11).

---

## 7. O que não recomendo

- **Refazer RAG ou memória para ganhar velocidade.** `NO_GO` medido (SPEC-214) e a literatura concorda **[W1][W3]**. Há ganho de **qualidade** a buscar na memória, em outra frente.
- **Trocar o modelo do narrador agora.** Não há avaliação de prosa em pt-BR para nenhum candidato **[W4]**, e os números de primeiro token publicados misturam modos com e sem raciocínio. Seria um A/B próprio, com leitura humana, depois da L5.
- **Chamadas de LLM em paralelo no mesmo provider** (SPEC-143, `NO-GO`), **hedge no mesmo provider** (SPEC-319: zero disparos), **`post_response` como está** (SPEC-213), **CLASSIFY no Groq** e **rota NPC determinística** (SPEC-317: concordância 93,1–93,75 %, abaixo do gate).
- **Mexer no typewriter.** Com tokens reais o cursor acompanha o recebido sem atraso, o envio nunca espera a revelação e o `state` corta o que falta (`web/src/hooks/useTypewriter.ts:83-89,102`) **[F✔]**. Só texto sem stream (a abertura) leva até 2,5 s, e isso se resolve na L8.
- **Execução especulativa enquanto o jogador digita.** Só protótipos de pesquisa **[W5]**.

---

## 8. O que esta auditoria não sabe

1. Onde o dono joga quando sente a lentidão (P0.1).
2. Se o staging usa Fluid Compute; se o `pg_cron` roda em produção (P0.2).
3. O intervalo por turno entre narração e `state`, e sua decomposição (P0.3, L0.1).
4. Tempo por ida ao Postgres a partir da função (L0.3).
5. Número de eventos por campanha e tamanho real do save (B4).
6. Tokens de saída por campo; tempo da abertura; peso do bundle web.
7. Fração das chamadas de LLM que estoura o timeout; semântica exata do timeout do cliente em stream.
8. Quantos checkouts de conexão por turno (a estimativa "10 a 14" não foi verificada; antes do grafo são 8 a 10 idas).
9. Por que a conversa com NPC foi excluída da pré-busca (`context_sources.py:58`): pode haver motivo.
10. Latência do DeepSeek por horário e por região: sem fonte confiável.
11. As fontes externas não foram reabertas pelo revisor.

---

## 9. Fontes externas (acesso em 2026-11-12)

A internet só inspira; nenhum número externo é critério de aceite. Os trechos vieram de resumo automático das páginas, não são citação literal garantida. O revisor não reabriu estas fontes.

- **[W1]** OpenAI, guia de otimização de latência: "cutting 50% of your output tokens may cut ~50% of your latency"; cortar 50 % do prompt rende 1–5 %; streaming é a técnica de maior impacto na espera percebida; "don't default to an LLM". https://developers.openai.com/api/docs/guides/latency-optimization (sem data). Confiança alta.
- **[W2]** Nielsen, limites de tempo de resposta (0,1 s / 1 s / 10 s). https://www.nngroup.com/articles/response-times-3-important-limits/ (1993, rev. 2014). Confiança alta.
- **[W3]** Escrita de memória em segundo plano: Letta, "sleep-time compute" (https://letta.com/blog/sleep-time-compute); LangMem, "hot path" × "background" (https://langchain-ai.github.io/langmem/background_quickstart). Mem0 (https://arxiv.org/abs/2504.19413) e Zep (https://arxiv.org/abs/2501.13956) ganham latência por mandar menos contexto que o histórico inteiro, o que o projeto já faz. Confiança média.
- **[W4]** Preços e velocidade de alternativas: páginas de preço dos provedores, catálogo do Groq, Artificial Analysis. Datas ausentes e modos não comparáveis; **nenhuma avaliação de prosa pt-BR encontrada**. https://api-docs.deepseek.com/quick_start/pricing · https://artificialanalysis.ai/leaderboards/models · https://console.groq.com/docs/models. Confiança média para preço, baixa para comparação de latência.
- **[W5]** Execução especulativa durante a digitação: PredGen (https://arxiv.org/html/2506.15556v2), LiveMind. Protótipos. Confiança baixa.
- **[W6]** Cache de contexto do DeepSeek: automático, por prefixo, "best-effort"; a documentação fala de preço, não promete latência. https://api-docs.deepseek.com/guides/kv_cache (sem data). Confiança alta.
- **[W7]** Vercel: Fluid Compute (concorrência na mesma instância, pré-aquecimento nos planos pagos), `waitUntil` (limitado à duração máxima da função, sem retry), runtime Python sem tree-shaking, cold start proporcional ao tamanho da função. https://vercel.com/docs/fluid-compute (2026-08-24) · https://vercel.com/docs/functions/runtimes/python (2026-08-12). Confiança alta.
- **[W8]** Supabase em serverless: pooler em modo transação, cliente em escopo de módulo. https://supabase.com/docs/guides/database/connecting-to-postgres (sem data). Confiança alta.
- **[W9]** Dean e Barroso, "The Tail at Scale" (CACM, 2013), via resumo. Base teórica para hedge entre providers **diferentes**, que o projeto não testou. Confiança média (primário não abriu).

Não encontrado: latência do DeepSeek por horário/região; efeito de JSON mode no primeiro token; cold start numérico de Python na Vercel; estudo "máquina de escrever × token imediato"; posts de engenharia de jogos narrativos com IA sobre quando consultar memória.

---

## 10. Revisão cruzada (12/11)

Revisor independente Fable, somente leitura, com quatro verificadores Sonnet (dois por vez), instruído a derrubar o relatório v1. Veredito: **"pode virar specs com correções; não precisa ser refeito"**. O coordenador conferiu no source os pontos do revisor que mais mudavam o texto (SPEC-316 D2, tabela da SPEC-384 D2, números de instância nova na SPEC-317, `early_gain_ms`, retenção da última frase) e aceitou todas as correções.

**Confirmado por leitura independente:** B4 (reinserção do `event_log`), C1/C2/C10 (cliente), B1/A3 (o que roda antes do `state`), A2 (timeouts e circuito), B2 (`SET LOCAL` por checkout), campo `memory_update` morto, defaults das flags, A7, A12, B3/C4, `NO_GO` da SPEC-214 com seus números, congelamento da SPEC-213, SMART por turno, concordâncias da SPEC-317. Typewriter descartado como causa.

**Corrigido da v1 para a v2:**

| Item | v1 dizia | v2 diz |
|---|---|---|
| "Envio travado 4 a 5 s" | medição | derivado: diferença de medianas 3,6–5,2 s no roteiro de estresse; por turno não calculado |
| Enter "ignorado em silêncio" | sem aviso | botão desabilitado com rótulo e selo; comportamento aprovado (316 D2, 320 R13) |
| L5 | um terço a menos de saída → ~4 s | → ~4,9 s; ~4 s exigiria −60 % |
| Cold start | 6,8–10 s, posição 4–5 | instância nova: 19–59 s registrados; vira L11, posição 3, e hipótese principal da P0 |
| Sem preset = braço OFF medido | sim | não: default ≠ OFF; sem medição do estado default |
| L10 | spec nova, "uma linha por flag", coordenador decide | decisão pendente do dono na SPEC-384 D2; `lean` reabre a 318 D4 |
| L1 | fila decidida pelo coordenador | L1b é decisão do dono (316 D2); L1a separada |
| L2 | teto ~4 s, posição 3 | só adia o arquivista; depende de Fluid; teste de descarte antes; posição 5, depois da L3 |
| L3 "ou tier FAST" | opção | removida: FAST e SMART são o mesmo modelo |
| A4 | entrada "não usa nenhum campo da cena" | o `manifest` dos guards usa a cena; reordenar exige desfazer isso |
| A5 hold de 120 | fala só aparece no fim | só para fala < 120 caracteres sem quebra de linha |
| A9 | "único teto é 12 s" | 12 s DeepSeek, 6,5 s CLASSIFY, 90 s demais |
| B6 | `lean` pula 3 classes | 4 classes |
| C7 | indicador genérico | há mensagens próprias; o texto ainda chega de uma vez |
| C3 | GoTrue quase sempre chamado | cacheado 20 s por instância; a query de sessão roda sempre |
| A8 | criatura disputa slot | só no perfil local |
| "um embedding por turno" | sempre | 1 no turno comum; +1 em NPC, replan, criação |
| Cartas | "meio do combate já é rápido" | sem LLM, mas paga o fluxo inteiro; sem medição |
| Cache de prefixo | desconhecido | já medido: 0,015–0,052 |
| Custo da L0 | US$ 0,10–0,20 | ~US$ 0,25–0,50; save sintético em vez de campanha longa |
| "~350 commits" | — | ~430 nos caminhos do turno |

**Acrescentado pelo revisor:** última frase retida até o fim da chamada (base da L4); ficha de NPC de 6,3 s p50 dentro do fechamento; save reescrito inteiro por turno; rodada de carta no fluxo completo; escritas extras antes do `state`; `_pre_drain_in_turn` pode rodar projeção com LLM antes do grafo (`routes/turn.py:1004,1206-1217`); plano Hobby e Fluid como alavancas.

**Continua não verificado:** os itens do §8. Nenhum `D-NN` de `docs/guias/DECISOES_FIXAS.md` é contrariado; SPEC-143, SPEC-214, hedge da 319 e R1/R2 da 317 são respeitados.
