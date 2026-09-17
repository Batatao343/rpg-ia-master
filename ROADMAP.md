# ROADMAP — RPG IA (Revisado 2026-09-17)

> **Estado atual — fechamento local, gate real pendente:** 152 specs auditadas,
> 140 `done`, 11 `in-progress` (código local implementado, B integral pendente)
> e uma `draft` (certificação cloud). B anterior: 751/2.000 turnos; interrupção
> por saldo DeepSeek, HTTP 402, confirmado novamente no preflight de 16/09.
> Nenhuma campanha real em execução. Após recarga, B reinicia do par 1 com os
> fixes atuais. Lista, evidências e comando no
> [fechamento local](docs/fechamento-local-2026-09-17.md).
>
> Revisão entregue no código: aliases de NPC em diálogo/recrutamento; proteção
> de memória geográfica, posse e identidade; semântica de queda; checkpoints,
> reparo de transições órfãs e recibo estável; replan de viagem; diversidade do
> diplomático; proteção de prosa; compatibilidade de vetor compartilhado.
> Smoke offline 10×3 sem erros/violações, conteúdo/Ruff/build frontend verdes.
> Suíte final: **1681 passed, 16 skipped, 14 deselected**; testes opt-in
> de rede/infra permanecem gates separados.
>
> [Experimento de latência](specs/latencia-turno-caminho-critico-concorrente.md)
> encerrado com **no-go** real: default sequencial, fan-out experimental,
> memória inline, sem promessa de async nativo/cancelamento HTTP. Cloud e
> sprites/som continuam fora da entrega local; nenhum deploy foi feito.
>
> **Os blocos datados abaixo são histórico**; prevalecem este resumo e as specs.

> **Matriz A concluída; remediação offline verde:** 2.000/2.000 turnos reais
> analisados em [relatório A](docs/playtest-matriz-a-2026-08-27.md). Quatro specs
> definitivas estão `in-progress` aguardando apenas a B: [ciclo de vida e ações](specs/contrato-canonico-ciclo-vida-acoes.md),
> [resultado canônico do turno](specs/resultado-canonico-turno-apresentacao.md),
> [interações com progresso](specs/interacoes-progresso-elegibilidade.md) e
> [structured output com evidência](specs/structured-output-evidencia-recuperacao.md).
> Gate: 1621 passed, 16 skipped, 14 deselected; smoke offline 30/30. Outcomes
> canônicos e de interação agora também sobrevivem save/load. A tentativa B
> `20260827-135829-799539` foi interrompida durante essa auditoria e é inválida.
> Próximo:
> B real 10×200 exatamente pareada; regressão nova exige interrupção.

> **Nova spec em revisão:** [latência do turno — caminho crítico concorrente e
> derivados assíncronos](specs/latencia-turno-caminho-critico-concorrente.md)
> (`draft`). A proposta usa a observabilidade já entregue para reduzir o caminho
> crítico sem request extra: plano+rota em fan-out/fan-in, um embedding por
> contexto, leituras independentes em paralelo, pulso de mundo sem side effects
> e memória derivada fora do request após commit canônico. Não é uma conversão
> geral para async e não cobre campanhas paralelas; essa certificação E2E será
> uma spec de go-live independente. Implementação só após aprovação e término da
> análise A.

> **Continuação A (2026-08-21):** `20260820-200416-642340` produziu quatro pares
> completos e 81 turnos do quinto antes de um `Connection error` DeepSeek. A
> coleta válida soma 800 turnos; o par combate revelou 7 violações de Vitalidade
> 0 fora do fluxo terminal. A spec
> [continuação segura](specs/playtest-matrix-continuacao.md) adiciona
> `--start-index 5` para executar somente os seis pares restantes, mantendo
> seeds/classes/níveis. As specs de timeout DeepSeek, memória fatal do explorador
> e single-flight foram validadas no real e estão `done`. Gate: 1610 testes.
> Gameplay permanece congelado até concluir e analisar toda a A; B ainda não
> começou.

> **Matriz A1 retomada:** saldo DeepSeek renovado; preset `deepseek-paid`
> exclusivo passou preflight real nos três tiers. A1/B usarão esse mesmo perfil
> com fail-closed, teto de US$ 0,25/800 requests por campanha e seeds pareadas.
> A tentativa `20260820-180632-012432` revelou excesso recuperável de beats no
> turno 2; a [normalização da borda](specs/campaign-beats-overflow-provider.md)
> está implementada. O reinício `20260820-181149-643772` revelou um
> `WorldPulse=None`; o [retry semântico](specs/structured-output-retry-provider.md)
> foi ampliado após `20260820-182003-393045` chegar a 150 turnos e encontrar dois
> `CampaignPlanModel=None` consecutivos; replay imediato passou. O limite é de
> três gerações totais no mesmo provider, coberto pelo gate de 1600 testes e
> preflight DeepSeek 3/3. A tentativa `20260820-185627-750638` completou o par
> normal 200/200, mas o explorador terminou no turno 71 por três timeouts
> independentes no limite de 12 s e repetiu cinco mortes na Fortaleza de Vorr.
> As specs [timeout isolado](specs/deepseek-paid-timeout-longrun.md),
> [memória fatal do explorador](specs/explorador-aprende-com-mortes.md) e
> [single-flight da matriz](specs/playtest-matrix-single-flight.md) estão
> implementadas, com gate de 1608 testes. A1 reinicia do par 1; os três warnings
> de NPC remoto do par normal ficam preservados para a análise formal pós-A.

> **Objetivo central:** Mundo vivo persistente com estado consultável, antes de features novas.
> 
> **Princípio:** Lore base (Codex) ≠ Eventos confirmados (event_log) ≠ Estado atual (world_projection).  
> LLM propõe. Motor Python valida e aplica. Tudo persistente e auditável.
>
> Complementa `CLAUDE.md` (arquitetura) e `ESTADO_ATUAL.md` (status).
> **Desenvolvimento é spec-driven:** o detalhe técnico de cada fase vive em `specs/` — este arquivo só resume e aponta.

---

## ✅ READY LOCAL — ciclo 10b + produto (2026-08-20)

As sete fatias locais da Fase 10b e quatro specs de produto foram implementadas
atrás de portas Python, sem provisionar serviço remoto:

1. [Tiers 5+ e níveis 9–20](specs/tiers-5-plus-classes-niveis-9-20.md) — cap real
   20, gates `tier/level_req`, 80 Cartas novas (20 tronco + 45 subclasse + 15
   Ápices), escolha explícita e irreversível de subclasse no nível 3, Maestria de
   Virtude e balanceamento tardio;
2. [Fase 8B — arte dinâmica rara](specs/fase-8b-geracao-dinamica-arte.md) — GPT
   Image 2 pinado, retrato personalizado, NPC persistente sem arte e uma cena
   épica por arco; orçamento de 4 NPC + 1 épica **por arco**, sem teto de campanha;
   escolher subclasse não gera arte/custo automaticamente, mas informa futura
   reformulação manual e cenas épicas;
3. [Crônica avançada](specs/cronica-avancada-compressao-busca-semantica.md) — raw
   imutável, digest assíncrono após 20 entradas/fechamento e busca híbrida
   semântica+lexical escopada à campanha;
4. [Playtest longo comerciante](specs/playtest-longo-perfil-comerciante.md) —
   perfil stateful e não onisciente, conservação, margem, net worth, restock e
   arbitragem regional auditáveis. Revalidação pós-upgrade: 5×200, zero erro/
   violação, 38 transações, três a cinco mercados e restock em todas as seeds
   ([relatório](docs/playtest-comerciante-2026-08-20.md)). Aceite real:
   [1×200](docs/playtest-comerciante-real-2026-08-20.md), `mock=false`, zero erro,
   US$ 0,162860; três P1 e três P2 ficaram evidenciados para specs próprias.

Fase 10b local: Supabase local, Postgres/RLS/Auth/pgvector/storage, turnos e jobs
duráveis, adapters, migração/export, backup/restore e observabilidade estão em
código e cobertos por contratos. G0–G7 estão verdes: 1565 testes offline,
`infra_local` 13, `security_local` 5, pgTAP 14/14, caos 5/5, commit DB p95
32,257 ms, backup RPO 0/RTO 36,19 s, browser desktop/390 e stack
Prometheus+Grafana+Collector+Tempo. Evidência versionada em
[docs/readiness/readiness-local.md](docs/readiness/readiness-local.md).

Pendências que exigem opt-in explícito continuam abertas: certificação remota em
Railway/Supabase. Tiers 5+, Fase 8B, Crônica avançada e comerciante estão
`done`; chamadas pagas de imagem da 8B continuam opcionais.
A certificação cloud permanece `draft`. Nenhuma chamada de imagem nem recurso
remoto/pago foi criado neste ciclo.

---

## ✅ ENTREGUE — remediação do longrun real de 200 turnos (2026-08-16)

As cinco pendências do diagnóstico abaixo foram especificadas e executadas:

1. [memoria-npc-sucesso-ledger](specs/memoria-npc-sucesso-ledger.md) — sucesso
   privado entra no ledger como relato, sem write duplicado;
2. [chase-progresso-e-fuga](specs/chase-progresso-e-fuga.md) — fingerprint do
   chase e teto determinístico de seis tentativas;
3. [quests-retomada-conversao](specs/quests-retomada-conversao.md) — BFS até o
   alvo, duas investigações e funil D+0..D+3 compartilhado;
4. [pos-fuga-roteamento-origem](specs/pos-fuga-roteamento-origem.md) — limpeza
   integral de cena e causa fechada por intenção atual;
5. [ritmo-combate-normal-v2](specs/ritmo-combate-normal-v2.md) — prudência no
   agente de teste, sem alterar dano ou encontros do produto.

Aceite `20260816-113051-596798`: 200/200 MockLLM, zero erro/violação, quatro
rotas, combate 20,5% (antes 45%), quatro conversões em quatro pedidos, 15 quests
concluídas/recompensadas e 9/9 claims NPC espelhados. Smoke real dirigido
confirmou router e write Jina/ledger. Gate: **1480 passed, 1 skipped, 14
deselected**; Ruff verde.

---

## 🧪 DIAGNÓSTICO — longrun real pós-remediação (2026-08-16)

O run `20260816-100206-334105` completou 200/200 ações reais, sem exceção ou
timeout, por US$ 0,137760. Confirmou checkpoint seguro (duas mortes, dois epochs,
zero replay), origens variadas e queda do p95 35,3→20,1 s. Detalhe em
[playtest-longrun-real-2026-08-16](docs/playtest-longrun-real-2026-08-16.md).

Achados observados naquele run, posteriormente resolvidos na entrega acima:

1. **P1:** sucesso direto de `npc_claim` fica no índice privado e não chega ao
   ledger global;
2. **P1:** fingerprint de `combat.no_progress` ignora progresso do chase; fuga
   real exigiu onze tentativas;
3. **P1:** perfil não retorna à segunda investigação da quest e funil perde
   conversão ocorrida no turno seguinte;
4. **P1:** descanso imediatamente após fuga reabriu combate como provocação;
5. **P2:** perfil normal terminou com 45% de turnos em combate.

---

## ✅ ENTREGUE — remediação do longrun de observabilidade (2026-08-13)

O relatório [playtest-longrun-observabilidade-2026-08-13](docs/playtest-longrun-observabilidade-2026-08-13.md)
combinou 114 ações úteis com LLM real em duas tentativas e uma matriz 200/200
MockLLM. Os achados foram convertidos e executados em cinco specs `done`:

1. [checkpoint-seguro-fora-combate](specs/checkpoint-seguro-fora-combate.md) —
   impede snapshot ativo e saneia slot legado;
2. [origem-combate-por-cena](specs/origem-combate-por-cena.md) — causa atual
   vence rótulo antigo e distingue descanso/viagem/provocação;
3. [memoria-autoridade-quests-verificaveis](specs/memoria-autoridade-quests-verificaveis.md)
   — relatos auditáveis, expiração contextual e conclusão mecânica de objetivo;
4. [telemetria-rollback-abort](specs/telemetria-rollback-abort.md) — três relógios,
   conflitos únicos, rota timeout e prefixo abortado válido;
5. [latencia-inicio-combate](specs/latencia-inicio-combate.md) — remove invoke
   FAST exclusivo da geometria inicial.

Aceite mock `20260813-085903-974550`: 200/200, zero erro/error, seis mortes em
seis epochs, zero replay de conflito, 14 starts/14 ends, oito quests concluídas e
memória final com 100% de autoridade. Smoke real `20260813-090120-046611`: 2/2,
11 sucessos DeepSeek no jogo + quatro no startup e zero erro/violação. Gate:
**1466 passed, 1 skipped, 14 deselected**.

---

## ✅ ENTREGUE — Qualidade de campanha pós-longrun (2026-08-13)

Quatro specs transformaram as melhorias qualitativas do playtest longo em
contratos auditáveis:

1. [objetivo-publico-ciclo-quests](specs/objetivo-publico-ciclo-quests.md) —
   separa direção privada e UI; registra progresso e recompensa real da missão;
2. [ritmo-social-origem-combates](specs/ritmo-social-origem-combates.md) —
   direção social canônica sem NPC e causa persistente de cada conflito;
3. [observabilidade-latencia-nos](specs/observabilidade-latencia-nos.md) —
   latência por nó em JSONL, summary e relatório;
4. [continuidade-memoria-morte](specs/continuidade-memoria-morte.md) — schema v7,
   três relógios, histórico de restore e métricas de autoridade da memória.

Aceite: smoke MockLLM `20260813-001000-370465` 12/12 sem erro/violação, build
Vite verde e **1455 passed, 1 skipped, 14 deselected**. Nenhuma chamada LLM foi
adicionada e fallbacks permaneceram fora do escopo.

---

## ✅ ENTREGUE — Remediação do playtest real de 100 turnos (2026-08-12)

A spec [remediacao-playtest-real-100t](specs/remediacao-playtest-real-100t.md)
fechou os achados P0/P1/P2 autorizados:

1. deadline absoluto rejeita resultados tardios mesmo após suspensão;
2. perfil `normal` não lê beats privados e pede tarefas concretas;
3. telemetria mede pedido→quest e participação de combate, com warnings long-run;
4. perfil recua antes e respeita cooldown sem mudar dificuldade/encontros;
5. loot mantém segunda pessoa por normalização determinística.

Aceite mock `20260812-232004-255178` = 50/50, quatro rotas e quatro quests;
aceite real `20260812-232052-855221` = 16/16, `mock=false`, zero erro/violação,
uma quest e 31,2% combate. Gate: **1446 passed, 1 skipped, 14 deselected**;
Ruff verde. Configuração/saldo/chaves dos fallbacks reais não pertencem à spec.

---

## 🧪 DIAGNÓSTICO — campanha real de 100 turnos (2026-08-12)

O run pós-remediações `20260812-215427-501557` concluiu 100/100 turnos com
`mock=false`, zero exceções e 273 sucessos LLM de rede por US$ 0,085208. As seis
correções do ciclo anterior permaneceram válidas. O relatório
[playtest-longrun-real-2026-08-12-v2](docs/playtest-longrun-real-2026-08-12-v2.md)
registrou cinco frentes, posteriormente tratadas pela spec consolidada acima:

1. watchdog com prazo forte diante de suspensão/lacuna de heartbeat — um turno
   atravessou o teto de 120 s e terminou em 2.256 s;
2. perfil `normal` restrito à visão pública — hoje copia `Descreva...` do beat;
3. observabilidade/conversão de ganchos em quests — 0 quests em 100 turnos;
4. voz do loot em segunda pessoa;
5. matriz multi-seed antes de balancear os 45% de turnos em combate.

Operação: MiniMax respondeu 402 por saldo insuficiente e Qwen 401 por chave
inválida; Groq absorveu os fallbacks reais. Essa configuração permaneceu fora
do escopo por decisão do usuário.

---

## ✅ ENTREGUE — Correções do playtest longo de jogador normal (2026-08-12)

O diagnóstico [playtest-jogador-normal-2026-08-12](docs/playtest-jogador-normal-2026-08-12.md)
executou 440 turnos mistos (400 MockLLM + 40 DeepSeek real) e originou seis
specs, todas `done`:

1. [fuga-progressiva-persistente](specs/fuga-progressiva-persistente.md) —
   `combat.chase` persiste, chega a `escapou` e telemetria separa progresso/falha.
2. [checkpoint-transacional-memoria](specs/checkpoint-transacional-memoria.md) —
   estado e árvore FAISS inteira (inclusive NPC) fazem checkpoint/rollback juntos.
3. [replan-grounding-troca-regiao](specs/replan-grounding-troca-regiao.md) — troca
   regional sempre replana e o local do plano vem do estado canônico.
4. [resumo-curto-budget-rigido](specs/resumo-curto-budget-rigido.md) — teto de
   1.200 caracteres, memórias fracionadas e nenhum bypass do `ContextPack`.
5. [feedback-ledger-recompensas](specs/feedback-ledger-recompensas.md) — ouro não
   é item livre; confirmação visível deriva apenas do delta mecânico.
6. [perfil-jogador-normal-invariantes](specs/perfil-jogador-normal-invariantes.md)
   — 14º perfil permanente, level-up, quatro rotas, invariantes e SLO 45/90 s.

Aceite: mock `20260812-172231-913670` = 50/50, quatro rotas, três escolhas de
progressão, zero erro/violação; real `20260812-172526-505951` = 5/5, quatro rotas,
zero erro/violação, p95 37,3 s, US$ 0,00686. Gate: **1436 passed, 1 skipped,
14 deselected**; Ruff verde.

---

## ✅ ENTREGUE — Hardening de persistência e SSE (2026-08-11)

[hardening-persistencia-sse-idempotencia](specs/hardening-persistencia-sse-idempotencia.md)
separou saves vivos de checkpoints, tornou a escrita JSON atômica e a exclusão
composta (save + checkpoint + memória). Falha de disco agora é explícita.

Turnos são serializados por `game_id` no processo e deduplicados por `action_id`
persistido; stream e fallback POST compartilham o mesmo ID, e o worker conclui o
save mesmo após desconexão do consumidor. Testes usam diretórios temporários e
não poluem mais o runtime real. Telemetria de skips, DTOs de criação, CLI e CI
também foram endurecidos.

Gate: **1398 passed, 1 skipped, 14 deselected**; Ruff e conteúdo verdes; build
Vite com 454 módulos. Lock distribuído/autenticação continuam na Fase 10b.

---

## ✅ ENTREGUE — Laboratório de combate isolado (2026-08-03)

[modo-simulacao-combate](specs/modo-simulacao-combate.md) adiciona uma entrada
direta no frontend para escolher classe, nível, qualquer inimigo canônico e
quantidade. A arena reutiliza Cartas, Reações, Ruptura, Ferimentos, posições e
IA tática de produção, mas pula LLM/RAG, campanha, archivist, loot, XP e
checkpoints. O save recebe marcador próprio e a UI mostra “Laboratório”.

Smoke browser desktop/mobile 390 px: round de Carta+Reação e manobra Guardar,
console limpo e 0 violações WCAG A/AA. Gate: **1388 passed, 1 skipped,
14 deselected**; Vite/TypeScript com 454 módulos.

---

## ✅ ENTREGUE — Remediações dos relatos de gameplay (2026-08-03)

Quatro resíduos da matriz real foram formalizados e fechados:

1. [polish-prosa-v2](specs/polish-prosa-v2.md) — fronteira de saída remove
   marcadores internos/imperativos ecoados, varia abertura literalmente repetida
   sem request extra e elimina parágrafo de aquisição monetária rejeitada.
2. [hardening-playtest-watchdog](specs/hardening-playtest-watchdog.md) — teto de
   wall-clock no startup/turno real, manifesto `aborted`, recuperação de run
   stale e circuit breaker process-local para falha permanente de provider.
3. [smoke-dirigido-recrutamento-comercio](specs/smoke-dirigido-recrutamento-comercio.md)
   — cenários opt-in com pré-condições canônicas e oráculos fail-loud; Brunna
   entrou na party e a compra alterou ouro/inventário no LLM real.

4. [fix-playtest-liveness-telemetria-circuito](specs/fix-playtest-liveness-telemetria-circuito.md)
   — revisão pós-entrega corrigiu falso-aborto de runs legítimas >6 h com
   owner+heartbeat e retirou `circuit_open` de requests/custo/falhas, mantendo
   skips auditáveis em `llm_skipped`.

Evidência: runs reais `20260803-114646-799077`, `20260803-114339-651827` e
`20260803-114423-833666`, todas `mock=false`, completas e sem erro/violação;
smoke offline da correção `20260803-130102-999691`, completo e sem violações.

Gate atual do repositório: **1388 passed, 1 skipped, 14 deselected**.

---

## ✅ ENTREGUE — Migração do Sistema de Conflitos (Valoria v2)

> **Épico grande (2026-07-22).** Fonte funcional do usuário:
> `docs/valoria_conflict_migration_v2/` (4 docs: regras consolidadas, escopo,
> cenários de aceite, decisões fechadas). Substitui o combate atual (LLM narra
> turno a turno, HP/d20-vs-AC, habilidades JSON) por um **jogo tático de cartas
> 100% determinístico**: durante o conflito **não há chamada de LLM** — a LLM só
> **prepara** a cena antes (zonas, objetos, inimigos do bestiário, eventos do
> Abismo) e **narra** o resumo canônico depois, sem poder reverter fatos.

**Mudanças de núcleo:** 6 atributos → **5 Virtudes** (Mente/Agilidade/Força/
Carisma/Corpo 0-5); HP → **Vitalidade + Ferimentos localizados** (Leve/Grave/
Crítico); d20 vs AC → **2d10 + Virtude vs Esquiva** (Crítico/Supercrítico por
duplas); habilidades → **Cartas** (Acervo + preparadas 4/5/6/7, Ruptura, Cartas
de Virtude); zonas abstratas (Próximo/Distante/Separado + Protegido/Neutro/
Exposto + Visível/Escondido); reações/AoO; perfis táticos pré-gerados;
Última Ação/Estado Terminal/Cicatrizes; fuga/perseguição com trilha.

**Decisões de escopo (usuário, 2026-07-22):** (1) **cutover atômico** no fim (motor
novo isolado, troca de roteamento única na `conflito-13` — jogo fica injogável no
meio da migração, por design); (2) **corte de saves** — schema v3→v4 arquiva
personagens antigos, sem conversão de atributos→Virtudes; (3) **autoria de
conteúdo incluída** (cartas + bestiário viram specs próprias); (4) **frontend
incluído, menos prioritário** (última spec).

**16 specs ordenadas por dependência** (detalhe técnico SÓ nas specs):

| # | Spec | Bloco funcional |
|---|---|---|
| 01 ✅ | [conflito-01-virtudes-vitalidade](specs/conflito-01-virtudes-vitalidade.md) | Virtudes, Vitalidade/Ferimentos, migração v4 (fundação de dados) — **`done`** |
| 02 ✅ | [conflito-02-cartas-acervo-preparacao](specs/conflito-02-cartas-acervo-preparacao.md) | Cartas, Acervo, Preparação, Ruptura, Cartas de Virtude — **`done`** |
| 03 ✅ | [conflito-03-zonas-cena-objetos](specs/conflito-03-zonas-cena-objetos.md) | Zonas, cena congelada, objetos, catálogo fechado de efeitos — **`done`** |
| 04 ✅ | [conflito-04-turnos-iniciativa-ataques](specs/conflito-04-turnos-iniciativa-ataques.md) | Pré/Ação/Pós, iniciativa por lado, 2d10+Virtude, Crítico por dupla — **`done`** (motor; fiação no nó → cutover 13) |
| 05 ✅ | [conflito-05-armadura-dano-ferimentos](specs/conflito-05-armadura-dano-ferimentos.md) | Tipos de dano, armadura/Integridade, Ferimentos localizados — **`done`** |
| 06 ✅ | [conflito-06-reacoes-movimento](specs/conflito-06-reacoes-movimento.md) | Reações (janela/cadeia/1 comum), AoO universal, Engajar/Desengajar/Guardar/Esconder-se/Procurar + ocultação por observador — **`done`** (motor; fiação → cutover 13) |
| 07 ✅ | [conflito-07-morte-rendicao-captura](specs/conflito-07-morte-rendicao-captura.md) | Última Ação, Estado Terminal, estabilização, Cicatriz (LLM+guard), categorias de inimigo, golpe não-letal, rendição determinística, encerramento — **`done`** (motor; fiação → cutover 13) |
| 08 ✅ | [conflito-08-comportamento-tatico-companheiros](specs/conflito-08-comportamento-tatico-companheiros.md) | Perfil tático persistido (prioridades ordenadas), validação de ordem de companheiro, controle de party, painel público + revelação progressiva de Cartas/Resistências no bestiário — **`done`** (motor; fiação → cutover 13) |
| 09 ✅ | [conflito-09-fuga-perseguicao](specs/conflito-09-fuga-perseguicao.md) | Trilha Pressionado→Escapou, condutor+Virtude, Teste de Sorte (cap ±1), abandono com simulação determinística por seed, sacrifício voluntário, ataques em perseguição — **`done`** (motor; fiação → cutover 13) |
| 10 ✅ | [conflito-10-abismo-em-conflito](specs/conflito-10-abismo-em-conflito.md) | Eventos do Abismo preparados (base na cena obrigatória), carregamento determinístico/seed por Cargas+gatilho+prioridade, proibições rígidas (R4/R6), assinatura visual fixa — **`done`** (motor; fiação → cutover 13) |
| 11 ✅ | [conflito-11-preparacao-encontro-llm](specs/conflito-11-preparacao-encontro-llm.md) | LLM prepara cena jogável; Nível do Encontro absoluto (Python, sem party), potência por categoria (`data/potency_by_level.json`), validação de catálogo/base/região, cena de segurança, ficha de combate completa do NPC — **`done`** (motor+geração; fiação de grafo → cutover 13) |
| 12 ✅ | [conflito-12-loot-resumo-narrativo](specs/conflito-12-loot-resumo-narrativo.md) | `ConflictSummary` canônico (18 campos), `loot_context` (Nível do Encontro→danger, `roll_loot` intacta), contrato de não-reversão da narrativa, fatos p/ archivist — **`done`** (motor; fiação → cutover 13) |
| 13 ✅ | [conflito-13-cutover-migracao-playtest](specs/conflito-13-cutover-migracao-playtest.md) | **`done` (2026-08-02)** — sete specs de remediação entregues; matriz real pós-fix composta, 13×30, 390/390 turnos, `mock=false`, 0 erro/violação `error`, 1.119 sucessos de rede, US$ 0,328488, 4 reações e 28 táticas. [Relatório final](docs/smoke-correcoes-conflito-v4-2026-08-02.md). |
| 14 ✅ | [conflito-14-autoria-cartas-classes](specs/conflito-14-autoria-cartas-classes.md) | 80 Cartas autorais (escala nova 2d10+Virtude, 16/classe), catálogo fechado, Ruptura+Evolução A/B nas 15 centrais, parity, `docs/CARTAS.md` — **`done`** (entra em produção no cutover 13) |
| 15 ✅ | [conflito-15-autoria-bestiario-perfis](specs/conflito-15-autoria-bestiario-perfis.md) | 84 criaturas migradas pro schema v4 (categoria/Virtudes/Vitalidade/resistências), 10 arquétipos táticos ricos, 18 Cartas de inimigo com assinatura oculta — **`done`** (ADITIVO; fiação → cutover 13) |
| 16 ✅ | [conflito-16-frontend-combate-cartas](specs/conflito-16-frontend-combate-cartas.md) | **`done` (2026-08-02)** — mão de Cartas/Reação/Ruptura, zonas, Ferimentos, conhecimento progressivo, perseguição e morte rica; build + browser desktop/mobile + smoke LLM real verdes. |
| 17 ✅ | [conflito-17-volume-conteudo-mundo-vivo](specs/conflito-17-volume-conteudo-mundo-vivo.md) | **`done` (2026-08-02)** — 153 Cartas jogador + 40 inimigo, 124 criaturas (40 novas), 36 NPCs (3×12 hubs), guardas anti-reskin e [relatório de cobertura](docs/content-coverage-2026-08-02.md). |
| Q ✅ | [hardening-memoria-proveniencia](specs/hardening-memoria-proveniencia.md) | **`done` (2026-08-02)** — ledger com proveniência/confiança/fonte, metadata FAISS, segredo fail-closed, retry idempotente, invariante e telemetria. Smoke real 3×30: 90/90, 0 erro/violação `error`, 15 writes `npc_claim`, nenhuma promoção indevida. |

**Ordem:** 01 → 02/03 (paralelizáveis após 01) → 04 → 05 → 06 → 07 → 08 → 09/10 →
11 → 12 → **13 (cutover)** → 16. Autoria (14/15) pode correr em paralelo às specs
de motor (dependem só do schema respectivo — 02 e 05/08), mas só entra em produção
depois do cutover 13.

**Progresso atual:** 01–17 e hardening de proveniência `done`; épico de Conflitos
v2 integralmente entregue. Gate atual: **1388 passed, 1 skipped, 14 deselected**.
- **01** — fundação de dados: 5 Virtudes (0-5, distribuição 4/3/2/1/1), Vitalidade
  + espaços de Ferimento por Corpo, nível máx 10 com +1 Virtude nos pares,
  migração v3→v4 (hard cutover, saves antigos arquivados), `attributes`/mana/
  stamina fora do jogador (ponte `actor_mods`). +30 `test_conflito_virtudes`.
- **02** — sistema de Cartas: `services/cards.py` (Acervo/Preparação/frequência
  por carta/Ruptura/evolução A-B), `data/cards/` exemplos (6/classe + Cartas de
  Virtude), criação com 6+4+2, level-up com escolha de Carta. Convive com o motor
  antigo (`known_abilities`) até o cutover. +25 `test_conflito_cartas`.

- **03** — cena posicional: `services/conflict_scene.py` (zonas não-grid, 3 eixos
  Distância/Postura/Ocultação, Engajamento separado, objetos interativos com
  catálogo FECHADO de efeitos `EFFECT_KINDS`, cena congelada + gatilhos de
  reforço). Aditivo puro: `combat["scene"]` convive com o dict antigo. +13
  `test_conflito_zonas`.

- **04** — motor de resolução: `services/conflict_resolution.py` (iniciativa por
  lado, ataque 2d10+Virtude vs Esquiva, Crítico/Supercrítico por DUPLA nos dados
  mantidos, Vantagem/Desvantagem 3d10-keep-2, testes gerais Ímpeto+Presságio+
  Virtude, Ruptura=Vantagem). ADITIVO (motor antigo intacto); a fiação no nó
  (Pré/Ação/Pós) + remoção do antigo vão no cutover 13. +19 `test_conflito_iniciativa`.

- **05** — dano→Ferimentos: `services/conflict_damage.py` (ordem fixa R8: dano×
  crítico → res/vuln/imunidade → Proteção → Integridade → Vitalidade/Gravidade →
  Ferimentos+secundários; 3 físicos + 6 sobrenaturais; armadura/escudo com
  Integridade/Comprometida; Ferimento localizado agrava/escala; sacrifício de
  Vitalidade do Sangromante; recuperação). Aditivo. +26 `test_conflito_dano`.

Suíte **1128 verde**. Próxima: **06 (Reações/movimento/AoO)**. As demais em `draft`.

---

## O que já foi entregue

| Fase | Status |
|---|---|
| **Fase 0** | ✅ ENTREGUE — Motor fundacional (LangGraph, agentes, combate determinístico, RAG FAISS, memória de sessão, grafo de 9 locais, relógio, viagem, fog of war, gating) |
| **Fase 1** | ✅ ENTREGUE — Frontend React+Vite (Witcher tone), HUD em abas, mapa, modos combate/exploração, crônica, typewriter effect |
| **Fase 2** | ✅ PARCIAL — Fações com objetivos/reputação, ascensão de ameaça, encontros temáticos, memória de NPC, world_simulator básico, beats de campanha |
| **Polishes** | ✅ ENTREGUE — Multi-provider LLM (Gemini/Ollama/OpenAI/Qwen), otimização 5-6→2-3 calls/turno, combate determinístico profundo |
| **DX (2026-07-02)** | ✅ ENTREGUE — Tooling do Claude Code: skills `/qa` e `/wrap-up`, `scripts/smoke_api.sh`, hook de reindex FAISS, docs de sessão enxutos (histórico → `CHANGELOG.md`), allowlist proposta (`.claude/settings.proposed.json`) |
| **Faxina (2026-07-03)** | ✅ ENTREGUE — Código morto removido: `agents/ruler_completo.py`, `engine_utils.py`, `dice_system.py` (zero importadores em produção), `COMMON_LOOT_TABLE`; testes órfãos removidos (216→211); CLAUDE.md/README corrigidos (documentavam módulos mortos) |

---

## ✅ ENTREGUE — Fase 2.5 a 2.8: Mundo vivo v1

Fundação arquitetural: mundo não muda mais por narrativa textual livre — camadas
separadas (Codex ≠ event_log ≠ projection), motor de regras sistêmico, contexto
orçamentado, estado auditável. **Todas as 4 fases entregues** (2.5b pendente só de
smoke LLM real).

> **Specs completas (fonte da verdade técnica):** [specs/fase-2.5](specs/fase-2.5-codex-world-state.md) · [specs/fase-2.6](specs/fase-2.6-structured-events.md) · [specs/fase-2.7](specs/fase-2.7-rules-engine.md) · [specs/fase-2.8](specs/fase-2.8-context-builder.md)

### Fase 2.5 — Codex estruturado + World State Graph → [spec](specs/fase-2.5-codex-world-state.md) ✅ ENTREGUE (2026-07-02)

Universo REESCRITO (`lore_nova/` — Valoria) vira Codex Markdown com frontmatter
(`data/codex/`, 635 arquivos via `scripts/migrate_lore_nova.py`) + grafo estático autoral
(`data/graph/`: 558 entidades, ~70 edges curadas, relation_types) + estado dinâmico no
save (`event_log` append-only + `world_projection` calculada). `graph_resolver` combina
base + dynamic − disabled com visibilidade; `codex_loader` ingere com metadados no FAISS;
`query_rag(max_visibility=...)` filtra segredos do contexto do narrador.

**Aceite entregue:** `get_current_controller("brekmar", projection)` responde pelo estado atual; smoke real narrou Valoria e segurou chunks `secret`.

**Adendo (2026-07-02):** `lore_nova/timeline_completa.txt` (Codex Omnia, 8 eras) ingerido em
`data/codex/timeline/` via handler `parse_timeline()`. Os 4 reveals que `secrets.txt` protege
(aprendiz→Arauto, Rei Subterrâneo, pacto Valerius↔Daruun, Rede Carmesim) ficam `hidden`; resto
`public`. Reindexado (2579 chunks). +4 testes (116 no total).

### Fase 2.5b — Valoria nos dados mecânicos + combate com comportamento → [spec](specs/fase-2.5b-valoria-dados-mecanicos.md) ✅ IMPLEMENTADA (2026-07-02; falta só o smoke real de LLM)

Dados mecânicos realinhados a Valoria com IDs do grafo: mapa (12 regiões + 18 sublocais,
grafo conexo), 18 fações com goal/ascension, 6 raças jogáveis com **traits mecânicos**
(bônus/resistências/saves aplicados em Python), bestiário curado (84 entradas com
`regions` + `behavior`) e `entities_extra.json` (curadoria que o migrate não sobrescreve).
**Combate com personalidade (R8-R10):** perfis `tatico/feroz/covarde/implacavel` — guardas
escolhem ataque e fogem por moral; urso-titã luta até a morte com frenesi; fugitivo gera
alerta de mundo que volta como reforço. Encontros sorteiam criatura concreta do bestiário
por região/fação (menos 1 chamada LLM). `world_lore.txt` removido.

### Fase 2.6 — Structured world changes → [spec](specs/fase-2.6-structured-events.md) ✅ ENTREGUE (2026-07-02)

LLM não altera mundo por narrativa livre: storyteller propõe eventos estruturados
(Pydantic), combate gera `npc_killed` determinístico; `world_validators` valida contra o
grafo e `event_processor` aplica na projection (via archivist, todo fim de turno).
`services/` ganhou `structured_outputs.py`, `world_validators.py`, `event_processor.py`.
177 testes offline. Smoke real Gemini ✅ (secret_revealed com id canônico validado; turno banal vazio).

**Aceite:** ✅ nenhuma mudança persistente sem validação; evento rejeitado não quebra o jogo.

### Fase 2.7 — Rules engine sistêmica → [spec](specs/fase-2.7-rules-engine.md) ✅ ENTREGUE (2026-07-02)

Entidades com componente `power_vacuum_trigger` (overlay `data/graph/components.json`,
migration-safe) disparam regras genéricas declarativas (`data/graph/world_rules.json`)
executadas sem eval (paths + ops whitelisted em `services/rule_engine.py`). Modelo HÍBRIDO:
estrutura (líder/controle/rival) derivada dos edges do grafo; componente só carrega
delta/sucessor/override. Cascata (líder morre → fação desestabiliza → controle do local
muda → rival ocupa) roda no `event_processor` após cada `apply_event`, auditável no
`event_log` com `source="rule_engine"` e profundidade limitada a 2 (anti-loop).



**Aceite:** ✅ matar qualquer chefe de fação destabiliza sistemicamente (2 líderes testados);
zero ifs por NPC em `services/`/`agents/`; op/regra malformada não quebra o turno.

### Fase 2.8 — Context builder com orçamento de tokens → [spec](specs/fase-2.8-context-builder.md) ✅ ENTREGUE (2026-07-03)

`build_context_pack(state, query, purpose, budget)` ranqueia fatos dinâmicos
(relevância/local/entidade/impacto/recência), respeita budget por seção e monta o bloco
`<ESTADO_ATUAL_DO_MUNDO>` (estado vivo ANTES de lore base). storyteller, npc_actor,
combat e campaign_manager consomem o builder. 100% determinístico (zero LLM extra).

**Aceite:** ✅ contexto nunca excede orçamento (teste 200 fatos); 50 eventos em 1 local →
só top relevantes no prompt; segredo não revelado não vaza; 216 testes offline verdes.
Smoke LLM real pendente de quota (fase determinística, sem `with_structured_output` novo).


---

## ✅ ENTREGUE — Fase 3: Clareza de campanha (Jogador entende o mundo)

**Objetivo:** Transformar estado abstrato em interface legível. Jogador sabe onde está, o que descobriu, quem odeia ele, quais objetivos estão abertos.

**Fatiamento em 4 specs** (decidido 2026-07-03):

- [x] **3.1 — Diário + Crônica** → [spec](specs/fase-3.1-diario-cronica.md) `done` (2026-07-03) —
  milestones determinísticos do event_log + prosa de menestrel, capítulos por arco
  (`arc_title` no campaign_plan); trivial fica na memória, importante na crônica.
  Smoke com LLM real ok (planner mapeia e persiste `arc_title` no Gemini)
- [x] **3.2 — Conhecimento revelável** → [spec](specs/fase-3.2-conhecimento-revelavel.md) `done` (2026-07-03) —
  Codex do jogador como VIEW derivada do save (visited/intel/npcs/revealed_facts, zero
  estado novo) + bestiário progressivo com contadores determinísticos (4 graus: rumores →
  encontrada → estudada → dominada); docs `hidden`/`secret` nunca aparecem. Zero LLM.
- [x] **3.3 — Quest log** → [spec](specs/fase-3.3-quest-log.md) `done` (2026-07-03) —
  main quest = view do campaign_plan (arc_title); side quests propostas pelo LLM e
  validadas pelo motor; conclusão via pipeline 2.6 (reusa `quest_completed`, sem schema
  novo); NPC-origem canônico morto → quest falha sistemicamente; marker no mapa. Smoke
  com LLM real ok (criação + conclusão mapeadas corretamente nos dois agentes)
- [x] **3.4 — Visualização de estado** → [spec](specs/fase-3.4-visualizacao-estado.md) `done` (2026-07-03) —
  overlays do mapa derivados do event_log/projection (controle recente, ameaças,
  looming_threat, fog of war respeitado) + timeline de reputação por facção (evento novo
  `reputation_changed` no log, gerado 100% em Python — zero LLM; estabilidade só
  qualitativa, número interno nunca exposto)

**Fase 3 completa (2026-07-03).** Critério de aceite atingido: jogador sabe quem é, onde está, o que aconteceu, quem são aliados/inimigos, quais objetivos pode perseguir.

---

## ✅ ENTREGUE — Fase 4: Gameplay Core (sistemas de RPG)

> Origem: auditoria de jogabilidade de 2026-07-03. Constatações: `XP_TABLE` sem consumidor
> (xp nunca incrementa — **não existe progressão**), buffs/passivas são só texto (dano/AC
> nunca leem `active_conditions`), party só existe no schema, craft/shop/loot 100% na mão
> do LLM, poção inutilizável em combate, inventário inicial com nomes livres que o
> `ARTIFACTS_DB` não resolve, spawn narrativo sem teto de CR.
>
> **7 specs escritas (2026-07-03), todas `draft` aguardando aprovação** — links abaixo.
> Ordem: **4.1 → 4.1b (Fable) → 4.2 → 4.3 → 4.4 → 4.5 → 4.6** (4.2 e 4.3 podem paralelizar; 4.4 depende da 4.3; 4.5 da 4.2; 4.6 de 4.1+4.2+4.5).

Resumo por fatia (detalhe técnico SÓ nas specs — fonte única):

- **4.1 — Progressão** [✅ `done` → spec](specs/fase-4.1-progressao.md) —
  XP determinístico (kill por tier / beat / quest), level up com curvas por classe,
  árvore com ramos = subclasses mutuamente exclusivas, ids canônicos + backfill,
  `/game/levelup` + modal no frontend, `level_up` na crônica com gate anti-LLM.

- **4.1b — Árvores de Valoria** [✅ `done` 2026-07-04 → spec](specs/fase-4.1b-arvores-valoria.md) —
  executada por Fable: 10 classes × 2 ramos ancorados nos pilares do mundo, 111
  habilidades (66 novas) com impacto mecânico, anti-spoiler ok, apêndice A preenchido.
- **4.2 — Buffs mecânicos** [✅ `done` → spec](specs/fase-4.2-buffs-mecanicos.md) —
  condições tipadas lidas em dano/AC/acerto/save; stun/root/fear reais dos dois lados;
  9/10 passivas data-driven (Sapador declarativo, documentado).
- **4.3 — Inventário/equipamento** [✅ `done` → spec](specs/fase-4.3-inventario-equipamento.md) —
  inventário `{id, qty}` + slots (combate lê só slots); poção usável em combate;
  3 bugs fechados (arma inicial, item narrado, capitalização); `/game/equip` + HUD.
 
- **4.4 — Economia determinística** [✅ `done` → spec](specs/fase-4.4-economia-deterministica.md) —
  `services/economy.py`; preço = raridade × região × reputação em Python; mercadores
  persistentes com restock; craft com receita/local; drop tables; `TradeIntent` matou
  o `TransactionResult`.
- **4.5 — Party** [✅ `done` → spec](specs/fase-4.5-party-aliados.md) —
  recrutamento com gate determinístico (relationship ≥7, teto 3); N vs N no mesmo
  motor; alvo tático; morte de companion vira npc_killed; 4v5 sem crash testado.
 
- **4.6 — Dificuldade/IA/morte** [✅ `done` → spec](specs/fase-4.6-dificuldade-ia-morte.md) —
  clamp+piso por orçamento de pontos; 19 inimigos com habilidades mecânicas; 7 bosses
  com fases; morte com fecho de saga + save-memorial (409).

**Status da Fase 4 (2026-07-05): ✅ COMPLETA — 7 specs `done`** (313 → 461 testes
offline + smoke com LLM real executado; 4 bugs de integração achados e corrigidos
no smoke). Pendente só playtest de balanceamento. Próxima: **Fase 5**.

**Critério de aceite da Fase 4:** personagem sobe de nível e aprende habilidade nova; buff de habilidade muda número de dano observável; poção usada em combate cura; craft falha sem ingrediente; mercador de Skallgard vende coisa diferente do de Nova Arcádia; combate 4 (party) vs 5 (orcs) resolve sem crash; morte tem narrativa.

---

## 🎮 Roteamento multi-provider + Fase 5 → ✅ AMBOS ENTREGUES (2026-07-06)

> Decisão 2026-07-06: **roteamento-multi-provider entrou ANTES da Fase 5** — o
> jogo vira produto pago (chave por provider), então o playtest/telemetria da
> Fase 5 rodou já sobre as rotas novas e mede provider/modelo/custo.
> Fase 5 concluída na sequência (ver seção "Fase 5 — Agentic playtest" acima).

- [x] **Roteamento multi-provider** ([spec](specs/roteamento-multi-provider.md),
  `done` 2026-07-06 — **smoke real OK**): 3 tiers (`CLASSIFY`/`FAST`/`SMART`) +
  `ROUTES` (tier → lista de candidatos `(provider, modelo)`) + fallback em tempo
  de invoke via `RoutedLLM`; providers OpenAI-compat (Groq/Qwen/MiniMax/DeepSeek)
  reusam `_build_openai`, Anthropic builder próprio (extra `--extra anthropic`).
  Hook `set_llm_telemetry_hook` alimenta a 5.3. Convenção CRÍTICA intacta.
  656 offline verdes; smoke real = turno vivo com narração + campanha + fallback
  + telemetria. ROUTES final: CLASSIFY `groq gpt-oss-20b→gemini-flash-lite`, FAST
  `minimax→qwen→groq llama-3.3-70b→gemini-flash`, SMART `deepseek→groq
  gpt-oss-120b→anthropic→gemini-pro` — **Groq grátis em TODOS os tiers** (o fix
  `method="function_calling"` p/ providers OpenAI-compat venceu o strict
  json_schema; ver ESTADO_ATUAL). Contas minimax/qwen pendentes de saldo/key do
  usuário — fallback cobre (deepseek respondeu vivo no playtest real de 2026-07-07).

## Fase 5 — Agentic playtest + telemetria → ✅ ENTREGUE (2026-07-06)

> 3 specs `done`. Ordem seguida: **5.1 → 5.2 → 5.3**. +43 testes
> (`test_fase51/52/53.py`) → **699 testes offline verdes** + smoke real executado.

**Objetivo (atingido):** Agentes testadores jogam campanhas automáticas offline
(MockLLM = custo zero). Detectam inconsistências, medem estado, embasam balanceamento.

**Fatias:**

- [x] **5.1 — Harness + 10 perfis** ([spec](specs/fase-5.1-playtest-harness.md)):
  `playtest/runner.py` (`run_campaign` via `app.invoke`, mesmo caminho da API) +
  10 perfis determinísticos em Python (`next_action(state, rng) -> str`, seed
  reproduz a campanha): agressivo, explorador, comerciante, diplomático, troll,
  mapa_breaker, combate, npc_only, loot_abuser, secret_rusher. `--real` opt-in.
  Saves isolados (`saves_playtest/`). Teste permanente na suíte (10 turnos).
- [x] **Playtest longo comerciante — aceite completo**
  ([spec](specs/playtest-longo-perfil-comerciante.md)): política stateful que
  observa só o mercado atual; 5×200 revalidados em 2026-08-20 com 1.000/1.000,
  zero erro/violação e 38 transações. O 1×200 real `20260820-112050-208317`
  completou com `mock=false`, zero erro e US$ 0,162860.
- [x] **Remediação do comerciante real — implementação offline verde**
  ([spec](specs/remediacao-playtest-comerciante-real.md)): consulta read-only,
  ledger visual, isolamento de cena/NPC, saldo narrativo e fallback FAST.
  Aceite real será absorvido pela matriz A abaixo.
- [ ] **Matriz pareada multiperfil/multinível 10×200 A/B — em execução**
  ([spec](specs/matriz-longrun-multiperfil-niveis.md)): `start_level` canônico,
  10 pares fixos em cinco classes e níveis 1–20. A0 foi um diagnóstico parcial
  de 678 turnos, pois 8/10 pares bateram o cap por capacidade de provider
  ([relatório](docs/playtest-matriz-a0-2026-08-20.md)). Quatro specs `approved`
  corrigem [capacidade/preflight](specs/matriz-a-capacidade-provider.md),
  [Mimetismo Morto](specs/combate-mimetismo-morto-loop.md),
  [fuga a Vitalidade zero](specs/fuga-vitalidade-zero.md) e
  [observabilidade](specs/observabilidade-npc-mortes-longrun.md). Preflight real
  dos três tiers, suíte de 1600 testes e smoke offline 10×3 estão verdes;
  pendem A1 real completa, specs/fixes dos achados e B pareada com stop em
  regressão nova.

  **A1 interrompida por capacidade:** `20260820-155300-494278` concluiu apenas o
  par normal e revelou 707 falhas em 796 tentativas, com 146 turnos sem sucesso
  LLM. O resultado foi invalidado e os nove pares seguintes não rodaram
  ([diagnóstico](docs/playtest-matriz-a1-capacidade-2026-08-20.md)). A spec
  [LLM-only fail-closed](specs/playtest-real-llm-fail-closed.md) agora aborta no
  primeiro invoke terminal. Três correções A0 ficaram `done` (Mimetismo, fuga a
  Vitalidade 0, observabilidade); o gate tem 1594 testes e smoke 30/30. A1 foi
  retomada com DeepSeek. A tentativa seguinte encontrou no turno 2 um
  payload de seis beats, agora normalizado em Python para os cinco primeiros
  pela spec `campaign-beats-overflow-provider`. O reinício seguinte achou um
  structured output `None` isolado no simulador. Após duas falhas seguidas no
  turno 150 do run posterior, o limite passou a três gerações totais no mesmo
  provider, sem retry HTTP. A1 reinicia desde o par 1.
- [x] **5.2 — Invariantes de estado** ([spec](specs/fase-5.2-invariantes.md)):
  `playtest/invariants.py` — `check_all(state, prev_state)` puro plugado no
  runner. HP válido, ouro ≥ 0, item único sem dupe, NPC morto não fala, fação
  derrotada não controla, relógio monotônico, segredo oculto não vaza
  (assinaturas curadas dos docs `hidden`). `assert_invariants` reusável.
- [x] **5.3 — Telemetria + relatório** ([spec](specs/fase-5.3-telemetria-relatorio.md)):
  `playtest/telemetry.py` (JSONL por turno + `summary.json`) + `playtest/report.py`
  (`aggregate` + `render_markdown` + `--baseline`) + `playtest/pricing.py` (custo
  estimado); grava provider/modelo/custo/`fell_back` por turno (hook do roteamento);
  tetos `--max-requests`/`--max-cost` protegem o `--real`.

**CLI:** `uv run python -m playtest run --all --turns 50` · `... report <run_id>`.

**Refinamentos do harness (sessão 22, 2026-07-20):** perfil **`recrutador`** (13º —
faz o máx. de amigos, exercita party+aliados-em-combate); perfis de combate agora
USAM habilidade de Entropia + curam com HP baixo (agente curioso — antes só "Ataco
X" e a economia de Entropia nunca era exercitada); **telemetria de GASTO de
Entropia** por turno (spent/turno, %ativa, starvation/flooding redefinidos por
gasto e não snapshot) → **tuning dos 8 knobs `[BALANCEAR]` agora é decidível**.
Ver [spec](specs/playtest-agente-curioso-entropia.md).

**Sessão 23 (2026-07-20) — letalidade v2 + parity de habilidades:** run de
validação `20260720-093014` (17 campanhas reais, 0 erro, $1.74) fechou o baseline;
achado = letalidade é **falta de recovery**, não dano. Entregue:
[letalidade-early-game-v2](specs/letalidade-early-game-v2.md) Etapa 2 (descanso/
viagem recuperam no early-game + cooldown de encontro +2 + poção inicial + HP base
+ dano low-level); fix `secret_leak` (segredo conhecido pelo player ≠ vazamento);
**parity ESTÁTICA das habilidades** ([balanceamento §10](specs/balanceamento-classes-pos-playtest.md)
— roster balanceado por papel; só `fervor_ritual` era outlier → `2d6→2d8` + teste-
guarda). [fix-explorador-loop-navegacao](specs/fix-explorador-loop-navegacao.md)
`done` (perfil não oscila mais). [checkpoints-morte](specs/checkpoints-morte.md) **`done`**:
combat→`death_pending` (sem Saque), `POST /game/death` (Continuar do checkpoint /
Aceitar→memorial), harness auto-restore, `DeathModal` no frontend; memorial vira
escolha voluntária, sem permadeath. **"O Saque"/`pos-saque` INTEGRALMENTE
aposentados** (higiene: funções órfãs + invariantes + `test_pos_saque` removidos).
**1019 testes offline; `npm run build` verde.**

**Achados (mock — NÃO produção; report marca `mock: true`) da rodada `--all
--turns 50 --seed 42`:** 10/10 perfis com `erros=0` e `violações=0/0` (motor
sólido); `agressivo` morre no nível 1 (letal cedo sob combate mock); `explorador`
visita 13 locais / nível 3; `loot_abuser` acumula 297 ouro; **nenhum perfil
completa quest** (created=1/completed=0 em todos).

**Achados investigados a fundo → CORRIGIDOS (2026-07-07):**
- **Quests nunca fechavam.** Pipeline de conclusão está SÃO (já testado). Causa:
  nenhum perfil perseguia quest + o MockLLM só CRIAVA, nunca completava. Fix: perfil
  **`quester`** (11º perfil) + **MockLLM propõe `quest_completed`** ~50% quando há
  quest ativa no prompt → harness fecha quest offline (`test_quester_fecha_quest...`).
- **Letalidade viagem×combate.** Sem assimetria estrutural (mesmo `encounter_budget`;
  surpresa = ±5 init). Causa: a base de perigo do budget ignorava sub-nível
  (nível-1 @danger-4 = budget 11 ≈ 2 elites = one-shot vs 1 minion no perigo certo).
  Fix: **teto de sobrevivência** `cap = 5 + 3×nível + 2×aliados` — perigo alto segue
  duro mas não é sentença de morte no sub-nível; bosses ignoram budget.
- **Bugs de conteúdo/motor achados pelo playtest REAL e corrigidos:** rota `NONE →
  KeyError` no troll (router normaliza NONE→STORY); **vazamento do Verme-Primordial**
  (bug de parse do migrate dumpava o bestiário inteiro num doc público de 1613 linhas
  + doc de fação nomeava o segredo + Legião afirmava o pacto Valerius↔Daruun) — tudo
  curado na fonte + Verme `hidden` + reindex; RAG público verificado limpo.

**Suíte:** 43 → +4 → **703 testes offline verdes** (após os fixes acima).

**Ciclo `fix-playtest-achados` ([spec](specs/fix-playtest-achados.md) `done`, 2026-07-13):**
o novo `playtest transcript <run_id>` (ação→narração por turno) expôs 6 defeitos que o
mock escondia, todos corrigidos + smoke real: R1 beats em INGLÊS → força pt-BR; R2 NPC
repetia fala verbatim → `<SUA_ULTIMA_FALA>`+anti-repetição; R3 perfil `quester` colava
prosa do beat → objetivo curto; R4 morto continuava jogando (só a API barrava) → gate de
`game_over` no grafo + invariante; R5 nível-1 one-shot por elite em viagem → perigo
efetivo por nível (`forced_encounter_danger`, 5 zonas `apex` não escalam) + **fuga do
jogador (estava vestigial) implementada de verdade** (perfis `fujao`/`quester`). **715
testes offline verdes.**

---

## ✅ ENTREGUE — Ciclo de produto (2026-07-13) — 3 specs `done`

> Decisão da sessão 14 (pós-auditoria): antes de Fase 8 (arte) ou 10b (público),
> atacar **retenção e experiência**. **Executado na sessão 15 — as 3 specs
> viraram `done` (769 testes offline verdes; registro de execução no §8 de cada spec).**

1. ✅ **Balanceamento do early game + pacing** → [spec](specs/balanceamento-early-game.md) —
   baseline mock+real gravado ANTES do tuning; knobs: máx 1 elite no nível 1 +
   piso de HP nas classes frágeis (cap novo de budget pulado — dados não pediam);
   **derrota narrada "O Saque"** entregue (1ª queda fora de apex/boss = acorda
   1 dia depois saqueado, únicos voltam ao pool, 2ª queda = memorial; invariante
   5.2 nova vigia downed ilegal); **replan só quando o ARCO muda** (região nova
   + beat concluído; intervalo 10→15): replans do explorador **50 → 4 (−92%)**.
   Bônus: `secret_rusher` 30t REAL confirmou o fix do Verme (0 vazamentos).
2. ✅ **Streaming do turno (SSE) + custo em produção** → [spec](specs/streaming-turno-sse.md) —
   `POST /game/action/stream` (fases reais do grafo + narrativa em chunks +
   keepalive); smoke real: **`accepted` 0.09s / `route` 0.66s num turno de 20s**;
   frontend com indicador de fase + typewriter dirigido pelo servidor + fallback
   automático pro POST; log `rpg.turn` agora tem custo/providers reais (dev-only).
3. ✅ **Polish de sessão** → [spec](specs/polish-sessao.md) — tela "Continuar
   jornada" (lista/continua/exclui com confirmação; memorial em modo leitura),
   **chips de COMBATE 100% mecânicos** (`combat_suggestions` pura; smoke real
   confirmou name→id), export .txt + busca local da crônica, onboarding do 1º
   turno, passe mobile 390px (smoke Playwright 14/14, overflow-x 0).

**Decisões de refinamento (2026-07-13, com o usuário):**
- **Pós-ciclo (arte Fase 8 vs público 10b): DECIDIR DEPOIS**, com dados do
  playtest do ciclo — nenhum compromisso agora.
- **Backlog v2 enxugado (YAGNI):** sobrevive só **Crônica avançada** (compressão
  de capítulo + busca RAG — ver Backlog § Melhorias da Crônica). DESCARTADOS de
  vez: chips de exploração via LLM, dificuldade configurável. (O "prólogo
  guiado" foi REVIVIDO em 2026-07-16 por decisão do usuário — virou a spec
  `inicio-personalizado`, ver seção abaixo.)

---

## Achados do playtest longo REAL (2026-07-14) — insumo pra decisão pós-ciclo

> 3 perfis × 100 turnos no DeepSeek (agora principal no SMART + 1º fallback do
> FAST). ~$0.25, zero erro de turno. Análise completa + recomendações
> priorizadas: **[docs/playtest-longrun-2026-07-14.md](docs/playtest-longrun-2026-07-14.md)**.

- **Prosa/imersão do DeepSeek: salto claro** (arco da Thrace no quester = ponto
  alto; 7/7 quests, level 5). Custo ~$0.001/turno.
- Defeitos priorizados — **8 specs `approved` (2026-07-17) com ordem de dev
  cravada** (embeddings + métricas primeiro):
  1. [embeddings-provider](specs/embeddings-provider.md) — cadeia
     jina → openai → ollama → **gemini (último fallback; caro demais p/
     primário)**; provider fixado por índice via meta.
     **✅ `done` (2026-07-17): 804 verdes; re-index real com Jina + smoke §6
     3/3; RAG vivo.**
  2. [playtest-stop-gameover](specs/playtest-stop-gameover.md) — harness para
     na morte + telemetria de rota fiel (achados A+I).
     **✅ `done` (2026-07-18): 812 verdes; 552 turnos mock 0 rota vazia; smoke
     real 3/3 (combate parou no t14, combat_agent contado, p50=14s).**
  3. [combate-lifecycle](specs/combate-lifecycle.md) — viagem=fuga, combate
     órfão expira (achado C).
     **✅ `done` (2026-07-18): 822 verdes; 492 turnos mock 0 combat.zombie
     (combate ativo ≤4t vs 59); smoke real (viagem=fuga narrada, nunca teleporte).**
  4. [pos-saque-recuperacao](specs/pos-saque-recuperacao.md) — poção + carência
     + beat de recuperação (achado B).
     **✅ `done` (2026-07-18): 835 verdes; 3 seeds 0 violações de recuperação;
     smoke real (poção+beat+narração).**
  5. [npc-fallback-sem-alvo](specs/npc-fallback-sem-alvo.md) — fim do "Ninguém
     responde."; party em cena (achado E).
     **✅ `done` (2026-07-18): 844 verdes; quester/npc_only mock 0 "Ninguém
     responde"; smoke real (aliado cita objetivo, sozinho → gancho).**
  6. [beats-visibilidade-ptbr](specs/beats-visibilidade-ptbr.md) — sanitizador
     de segredo + PT-BR nos beats (achados D+F).
     **✅ `done` (2026-07-18): 855 verdes; módulo secret_signatures compartilhado;
     achado F era o fallback template em inglês (traduzido); smoke real 3 planos
     pt-BR sem segredo.**
  7. [encontros-dedupe](specs/encontros-dedupe.md) — NPC gerado com vínculo de
     local + cooldown (achado G).
     **✅ `done` (2026-07-18): 862 verdes; contexto filtrado por local; smoke real
     (NPC gerado não vaza p/ outro local).**
  8. [polish-prosa](specs/polish-prosa.md) — anti-repetição, 2ª pessoa na
     morte, menu de opções (achado H).
     **✅ `done` (2026-07-18): 870 verdes; smoke real (aberturas distintas + menu;
     downed em 2ª pessoa).**

> **🏁 As 8 specs do playtest longo estão `done` (2026-07-18).** Todos os 7
> defeitos do playtest 2026-07-14 fechados, cada um com smoke LLM real.
- Faltas de gameplay sentidas: quests não puxam pro mundo (quester: 1 local em
  100 turnos), exploração sem recompensa mecânica (23 locais, 0 quests, 0 ouro),
  economia invisível, aliados sem presença mecânica.
- ✅ Embeddings: resolvido pela spec embeddings-provider (Jina primário; RAG
  vivo). Google (429) virou último fallback.

## Criação de personagem imersiva — ✅ ENTREGUE 2026-07-17 (2 specs `done`)

> Pedido do usuário: jogador precisa de **afinidade com o personagem**. Hoje a
> criação é form seco; a backstory não influencia nada além de atributos. Meta:
> overview curado de Valoria + descrição livre → início de campanha sob medida
> (cena, missão pessoal e NPCs da história). Detalhe técnico SÓ nas specs.

1. [onboarding-valoria](specs/onboarding-valoria.md) `done` — wizard rico de 5
   passos com lore curado (`data/onboarding.json`: intro do mundo + 12 regiões
   + 10 classes + 6 raças) + `GET /data/onboarding`. Zero LLM, cobertura
   testada; smoke de UI 15/15 (Playwright, incl. 390px).
2. [inicio-personalizado](specs/inicio-personalizado.md) `done` —
   `POST /game/prologue` (1 chamada SMART + guard) gera prólogo confirmável;
   `/game/new` com `scenario` semeia `campaign_plan` pessoal + crônica + NPCs
   `in_scene` + cena de abertura. Sem scenario = fluxo atual intacto (CLI
   incluso). Smoke real §6 no DeepSeek executado — achado importante na spec:
   limites duros no schema do LLM derrubavam todos os providers (fix:
   truncagem em Python + `StartScenarioIn` estrito só na borda).

## Sistema de Classes — ✅ ENTREGUE 2026-07-19 (Cinco Posturas diante do Abismo)

> Decisão do usuário: substituir as **10 classes** por **5 classes × 3 subclasses**,
> cada uma uma **postura filosófica diante do Abismo** (não uma profissão). Detalhe
> técnico só na spec; referência viva em [docs/CLASSES.md](docs/CLASSES.md) (mecânica)
> e [docs/CLASSES_NARRATIVA.md](docs/CLASSES_NARRATIVA.md) (história).

1. [refatoracao-sistema-classes](specs/refatoracao-sistema-classes.md) `done` —
   Devoto do Abismo · Sangromante · Corruptor · Arcanista Cinzento · Médico de
   Campo. Recursos novos: **Entropia** (pool único, substitui mana+stamina do
   jogador; recompõe integral no descanso) + **Carga do Abismo** (longo prazo, não
   cai no descanso, patamares leve/moderado/severo). Gatilho + regra especial +
   consequência por classe, 100% Python (`combat_mechanics`). Árvore MÍNIMA jogável
   (41 hab, `scripts/gen_classes_v2.py`); migração `_migrate_v2_to_v3`; HUD com barra
   Entropia + chip Carga. 898 offline verdes + smoke real 4/4.
2. [arvores-habilidade-classes](specs/arvores-habilidade-classes.md) `done`
   (2026-07-19, autoria em **Fable**) — árvore RICA: **101 habilidades** (41
   ativas + 35 passivas + 25 utilitárias). `ability_kind` no schema;
   `player_passives` funde passivas aprendidas em todos os callsites do jogador;
   5 triggers novos (entropy_max_bonus/on_kill/cost_reduction, charge_discount,
   carga_embrace); utilitárias no contexto do storyteller
   (`utility_context_block` — gate determinístico, LLM narra); HUD com selo ✦/⚒.
   918 offline verdes + smoke real 4/4 (narrador citou a capacidade injetada).
   Fast-follow [tiers 5+ e níveis 9–20
   (`done`)](specs/tiers-5-plus-classes-niveis-9-20.md) — cap 20, gates reais,
   escolha explícita de subclasse e 80 Cartas tardias entregues.

## Revisão pós-épico — ✅ 2026-07-19 (sessão 20)

> Auditoria de código do épico de classes (sessão 19) + varredura de pendências
> de ROADMAP/backlog. 3 specs novas; 2 `done`, 1 instrumentada. 918 → **945
> offline verdes**.

1. [fiacao-regras-orfas-classes](specs/fiacao-regras-orfas-classes.md) `done` —
   **3 mecânicas de classe estavam mortas** (função testada em unidade, nunca
   chamada pelo jogo): taunt do Devoto (`pick_target` ignorava `control:"taunt"`),
   Transformação do Corruptor (`apply_transformacao` sem callsite), Purga da Carga
   do Médico (`reduce_ally_abyss` descartado por `_split_typed_effects`). Fix +
   **`HANDLED_KINDS`** (teste anti-órfão dado↔motor que teria pego os 3). +11 testes.
2. [isolar-cache-runtime](specs/isolar-cache-runtime.md) `done` — cache runtime
   (`bestiary`/`npc_database`/`custom_artifacts`) sai dos arquivos versionados p/
   overlay gitignored `data/runtime/` (curadoria READ-ONLY, vence no merge). Fecha
   a pendência do `git checkout` manual (sessões 15/16). +8 testes.
3. [balanceamento-classes-pos-playtest](specs/balanceamento-classes-pos-playtest.md)
   `done` — instrumentação (`--class`, telemetria Entropia/Carga,
   seção Classes no report); baseline mock (40 campanhas) + real capturados. Os 8
   knobs foram avaliados no ciclo posterior documentado na spec; a nota de
   tuning pendente deste histórico foi superada. +8 testes na instrumentação.
4. **Backlog fechado:** traits lote 2 (40→**80**); curadoria da Rede Carmesim
   (pendência Fase 7 — nome/monitoramento = comum do norte, iminência = `hidden`;
   over-share em `factions.txt` suavizado + reindex do lore, 2203 chunks).

**Trabalho concorrente (enquanto rodava o playtest longo de balanceamento):**
5. **Auditoria de mecânica-morta** além das classes (scan de funções sem
   callsite). Achado real: **gating narrativo por classe** morto desde a deleção
   do Ruler → **APOSENTADO** (decisão do usuário: mecânica é Python) + docs
   corrigidos + stub `archive_narrative` removido.
6. [weather-global-vivo](specs/weather-global-vivo.md) `done` — a máquina
   de clima GLOBAL estava sem trigger; novo gatilho determinístico em
   `advance_weather` (Tempestade de Éter/Noite Sem Estrelas varrem e impactam).
   +7 testes.
7. [itens-vivos-e-luz](specs/itens-vivos-e-luz.md) `done` — 3 lacunas
   confirmadas (itens não aplicavam passivas; sem item ofensivo ativo; sem luz):
   passiva de item fiada em `player_passives`, `use_item_in_combat` com alvo
   (stun/sono/dot/medo com save), **sistema de LUZ** (`light_level`), **+22
   itens** ancorados na lore + bloco de narração + chip no HUD. +20 testes.
   Suíte **918 → 970 verdes** na sessão. Smoke real dessas 3 specs adiado
   (Jina em uso pelo playtest).

## ✅ ENTREGUE — Polish de frontend + fim do playtest longo (2026-07-20, sessão 21)

Handoff detalhado: **[docs/HANDOFF-sessao-21.md](docs/HANDOFF-sessao-21.md)**.

1. **[polish-frontend-imersao](specs/polish-frontend-imersao.md) `done`** —
   auditoria visual (Edge headless) das telas-herói. Leitura como diário iluminado
   (sem eyebrow "Narrador" repetido; capitular por cena + fleuron `❧` + glow de
   tocha); bug de camada corrigido (`atmosphere`/`ember-canvas` → `z-index:-1`, a
   criação escurecia); `.create__frame` lê como pergaminho iluminado; 8 abas em 2
   linhas (não corta "Codex"); criação mobile top-align + `width:100%`. Puro
   apresentação (0 mudança de estado); gate = `npm run build` verde. Mobile a
   reverificar em device real.
2. **Playtest longo `run_id 20260719-160014` TERMINOU** — 15 campanhas (5 classes
   × combate/explorador/quester), ~8,4h, 0 erro de turno, ~$1.28 (deepseek). ⚠️
   **Achado:** telemetria de Entropia degenerada (`flooding=100%`/`starvation=0%`
   uniforme) → **os 8 knobs `[BALANCEAR]` seguem indecidíveis**; próximo passo é
   redefinir a métrica (`playtest/telemetry.py`) ou minerar o jsonl. Combate morre
   cedo (7–30t); quester sobrevive (até 70t sem morte). `recycled_npc=43` warnings
   (investigar `encontros-dedupe` em run longo). Jina agora livre.

## Backlog — Features após Fase 5

### Bugs críticos (sessão 2026-06-26)

- [x] ~~**NPC errado responde** fala destinada a outro~~ → fechado por construção na
  spec **npcs-3-camadas** (gate `in_scene`: NPC fora de cena responde "não está aqui" sem LLM)
- [x] ~~Inventário / capitalização~~ → movidos para **Fase 4.3**
- [x] ~~Morte sem narrativa~~ → movido para **Fase 4.6**

### ✅ ENTREGUE — Melhorias de Personagens (NPCs) — Sistema de 3 camadas (2026-07-06)

> **Spec `done`:** [specs/npcs-3-camadas-traits.md](specs/npcs-3-camadas-traits.md)
> — 3 camadas (sessão → conhecidos → em cena), gate determinístico do
> npc_actor ("X não está aqui" sem LLM — fecha o bug "NPC errado responde"),
> `data/traits.json` (80 traits — lotes 1 e 2 entregues; sorteio
> seeded, DC modifiers em 6.4/4.4),
> revelação progressiva por interações, aba Personagens. Detalhe SÓ na spec.

Depende de Fase 2.5+ estar estável (world_projection, revealed_facts).

### ~~Encontros sistêmicos~~ → promovido para **Fase 6.4** ([spec](specs/fase-6.4-encontros-sistemicos.md))


### ~~Clima com efeito real~~ → promovido para **Fase 6.5** ([spec](specs/fase-6.5-clima-com-efeito.md))


### ~~Economia regional~~ → fundida na **Fase 6** (era duplicata; base determinística é a spec 4.4)

---

## ✅ ENTREGUE — Fase 6 — Conteúdo sistêmico (evolução da economia 4.4)

> **Priorizada antes da Fase 5** (decisão 2026-07-05).
> **STATUS 2026-07-05: ✅ FASE 6 COMPLETA — 6.1–6.5 `done`** (461 → 520 testes
> offline + smoke com LLM real; 3 fixes de robustez achados no smoke). Specs:
> [6.1 — Economia viva (rotas/escassez/eventos)](specs/fase-6.1-economia-viva.md) ·
> [6.2 — Itens únicos](specs/fase-6.2-itens-unicos.md) ·
> [6.3 — Migração de monstros](specs/fase-6.3-migracao-de-monstros.md) ·
> [6.4 — Encontros sistêmicos](specs/fase-6.4-encontros-sistemicos.md) ·
> [6.5 — Clima com efeito real](specs/fase-6.5-clima-com-efeito.md)
> (6.4/6.5 absorvem os itens homônimos do backlog — eram conteúdo sistêmico.)
> Ordem: **6.1 → 6.2 → 6.3 → 6.4 → 6.5** (6.3 usa rotas da 6.1; 6.4 usa sorteio
> da 6.3; 6.5 modifica a detecção da 6.4).

Depende da **Fase 4.4** (economia determinística) — Fase 6 é a evolução dela com
estado do mundo dinâmico. Absorve o item "Economia regional" do backlog (era duplicata).

> **Já coberto em outro lugar (não refazer aqui):**
> preço por controle de facção hostil + reputação → spec 4.4 (R4/R6);
> quest falha quando NPC-origem morre → ✅ entregue na 3.3;
> contexto muda quando facção perde local → ✅ entregue na 2.8;
> reforços/ameaça regional afetam encontros → ✅ parcial na 2.5b (`threat_alerts`).

**Entregas (o que sobrava de verdade — tudo feito):**

- [x] Rotas comerciais: fluxo de itens por conexões do mapa (bloqueio de rota corta oferta) — 6.1
- [x] Estoques reagem a EVENTOS do event_log (`route_blocked/cleared` no pipeline 2.6) — 6.1
- [x] `economy_tags` avançadas: produtor local ×0.6 / isolado ×1.8 por ALCANÇABILIDADE (BFS) — 6.1
- [x] Itens `unique` (um por mundo, claim engine no event_log, gates em loot/loja/craft/narrado) — 6.2
- [x] Migração real de monstros: pressão de caça com decay + fação no controle mudam a composição das tabelas — 6.3

**Critério de aceite:** ✅ Bloquear um porto → peixe some de lojas, preço explode — rastreável no event_log (validado no smoke real da sessão 8).

---

## ✅ ENTREGUE — Fase 7 — Pipeline de autoria + validação

Depende de Codex estruturado (Fase 2.5) estar estável.

**Objetivo:** Evitar inconsistência conforme conteúdo cresce. Documentos, IDs, relacionamentos validados automaticamente. Paga os 3 débitos técnicos da Fase 2.5 (encoding, curadoria sobrescrita, NPC público+segredo).

> **FASE 7 COMPLETA (2026-07-05)** — 7.1/7.2/7.3 `done`, 581 testes offline,
> lint verde no repo, reindex feito, smoke real de não-vazamento executado.

**Fatias:**

- [x] **7.1 — Validadores de conteúdo + CI** ([spec](specs/fase-7.1-validadores-conteudo.md)):
  `services/content_validator.py` puro — frontmatter (id/type/name/tags/visibility, id = nome do arquivo),
  ids únicos (codex + entities_extra + components), referências (edges → entidade existente, constraints
  de `relation_types.json`, `related_entities` órfão), aliases sem duplicação (normalizado sem acento),
  visibilidade (secret não vaza em doc public), encoding UTF-8 (débito 2.5). CLI
  `scripts/validate_content.py` (exit 1 com erro) + teste-gate sobre os dados reais do repo +
  GitHub Action rodando `uv run pytest` em PR (fecha "CI hook antes de merge").
- [x] **7.2 — Pipeline de autoria: curadoria preservada, templates, reindex com gate**
  ([spec](specs/fase-7.2-autoria-curadoria.md)): `data/codex_overrides.yaml` — patches de frontmatter
  por id aplicados pelo `migrate_lore_nova.py` no fim da geração (curadoria sobrevive à regeração —
  débito 2.5); arquivos manuais com `curated: true` não são apagados pelo script (entidade em
  `entities_extra.json`, padrão 2.5b); templates Markdown por tipo em `docs/templates/codex/`
  (local, facção, raça, NPC, monstro, artefato); `rag.py` roda o lint 7.1 ANTES de reindexar e
  aborta com erro (fecha "comando para reindexar"); workflow documentado em `docs/AUTORIA.md`.
- [x] **7.3 — Separação público/segredo nos NPCs** ([spec](specs/fase-7.3-npc-segredos.md)):
  migrate divide cada NPC por rótulo de parágrafo (lista curada: "História real", "Motivação real",
  "O pacto e seus efeitos"...) → doc paralelo `npcs/segredos/{npc_id}_segredo.md` com
  `visibility: hidden` (débito 2.5 — hoje `codex_body`/RAG entregam o pacto de Valerius ao narrador);
  lint anti-regressão (rótulo secreto em doc public = ERRO); regeneração + auditoria manual + reindex.

**Critério de aceite:** Adicionar NPC novo segue template, é validado automaticamente, entra em entities.json com IDs únicos — e segredo de NPC não chega ao narrador público. ✅ **Validado em smoke real 2026-07-05** (NPC de teste via template sobreviveu ao migrate e passou no lint; narrador Gemini descreveu Valerius só pela persona pública, zero Daruun/pacto; `query_rag` public não devolve chunks de segredo).

**Curadoria entregue (sessão 20):** Rede Carmesim pode ser conhecida pelo nome e monitorada no norte; a iminência do despertar permanece `hidden`. O over-share foi suavizado e o lore reindexado; esta pendência histórica está encerrada.

**Vazamento achado pelo playtest real e CORRIGIDO (Fase 5, 2026-07-07):** perguntar
direto "conte sobre o Rei Subterrâneo" fez o narrador surfacear o **Verme-Primordial
das Raízes do Mundo** (segredo `hidden`, turno 13 do `secret_rusher`). Raiz =
curadoria, NÃO motor: o doc de fação `data/codex/factions/ultimos_anoes_reino.md`
(`visibility: public`) NOMEAVA o Verme-Primordial na linha "Conhecimento:" → RAG
público surfaceia e o narrador repete. **Fix aplicado:** suavizada a linha na FONTE
`lore_nova/factions.txt` (Durgrim só SUSPEITA que o Rei teme "algo que dorme mais
fundo", sem nomear o Verme) + `migrate` (idempotente, 2 arquivos) + `rag.py`
reindexado (2587 chunks). Verificado: `query_rag(public)` p/ "Rei Subterrâneo" NÃO
retorna mais assinatura do Verme. Confirmação final = re-rodar `secret_rusher --real`
30 turnos (deferido — Groq esgotado hoje; a cerca já está no índice).

---

## Fase 8 — Arte contextual

### 8A — Âncoras visuais curadas → [spec](specs/fase-8-ancoras-visuais-contextuais.md) `done` (2026-08-12)

Integra o pacote visual já produzido por catálogo canônico: capa nos seis cards de
raça e nas cinco classes, cena derivada de `current_location_id` e retrato na
primeira aparição estruturada de NPC. Identidade, visibilidade, fallback,
persistência e idempotência ficam em Python; React só apresenta o DTO.

Entregue: import fail-closed dos 68 PNGs do handoff; catálogo público com 45
assets (6 raças, 5 classes, 22 locais e 12 NPCs), 90 WebPs responsivos sem
metadata e cobertura de 35/35 locais por arte exata ou fallback regional. Save
v6 guarda primeira aparição/idempotência; API, POST/SSE e React exibem cena e
retrato no mesmo turno. O placeholder `AGUARDANDO ARTE` fica pronto como reserva,
mas não é usado: o pacote correto trouxe as seis raças aprovadas.

### 8B — Arte dinâmica rara → ✅ [spec `done`](specs/fase-8b-geracao-dinamica-arte.md)

Retrato personalizado na criação, NPC nomeado/persistente sem arte e uma cena
épica por arco (boss significativo; sem boss, conclusão). GPT Image 2 usa snapshot
pinado e âncoras aprovadas; Python decide brief, gatilho, orçamento, identidade e
storage. Limites: 4 NPCs + 1 épica por arco, cooldown de 15 turnos, sem teto de
campanha; jogador tem uma geração inicial + uma reformulação. Prompt de cena usa
pose curada e constraints explícitas contra anatomia/pegada/membros antinaturais.
O retrato inicial usa raça + classe-base; a escolha de subclasse no nível 3 não
gera novo job, mas seu vocabulário visual curado entra em reformulação manual
ainda disponível e em cenas épicas posteriores.
Tudo é privado, assíncrono e idempotente; turno nunca espera. Fundação, fila,
BlobStore, worker e testes fake/local foram entregues; geração paga é opt-in.

---

## Fase 9 — Sprites, som e polish audiovisual

Depende de: arte de itens pronta, Fase 6+ estável.

**Entregas:**

- [ ] Sprites por bioma (sourcear/gerar)
- [ ] Sprites por tipo de local
- [ ] Música por região
- [ ] Efeitos de combate
- [ ] Paleta visual consistente
- [ ] Transições smooth entre cenas

**Nota:** Som/sprite melhoram imersão, mas não corrigem consistência. Prioridade baixa até mundo estar sólido.

---

## Fase 10 — Hardening técnico e escala — fatia local ✅ ENTREGUE (2026-07-06)

> **Spec `done`:** [specs/fase-10-hardening-tecnico.md](specs/fase-10-hardening-tecnico.md)
> — game_id UUID anti-traversal (`persistence.save_path`), `schema_version` +
> pipeline de migrations (v0→v1 consolida backfills 3.1/4.1/4.3/4.5; v1→v2 =
> camadas de NPC), CORS por env, rate limit mínimo, log JSON por turno.
> Postgres/pgvector/auth/fila = **Fase 10b** (só com usuários externos).

Antes de abrir para usuários externos.

**Problemas atuais após a fatia local:**

- Saves/checkpoints ainda são JSON locais, embora já tenham schema v7,
  migrations e escrita atômica
- Memória de sessão/NPC ainda é FAISS mutável no disco
- Quatro overlays de runtime ainda escrevem JSON local (NPC, bestiário,
  artefatos e conhecimento revelado)
- Sem autenticação ou isolamento por usuário
- Concorrência serializada apenas dentro de um processo
- Sem object storage/fila durável e sem restore/caos multiworker comprovados

**Entregas:**

- [x] Validar `game_id` como UUID (prevenir path traversal) — 2026-07-06
- [x] Adicionar `schema_version` em saves (migrations para antigas) — 2026-07-06
- [x] Adicionar rate limiting (mínimo, por IP em memória) — 2026-07-06
- [x] Logs estruturados (JSON por turno, base da observabilidade) — 2026-07-06
- [x] **Auditoria 2026-07-13 (achados A1–A8) — TODOS corrigidos na mesma data**
  (+14 testes `tests/test_audit_fixes.py`; detalhe em ESTADO_ATUAL § Bugs conhecidos):
  `level` validado no `/game/new` (fechava ouro negativo); gate `game_over` + rate
  limit em `/game/equip`+`/game/levelup`; `save_game_state` via `save_path()`/
  sanitização; flag `simulated` = `llm_setup.is_simulated()` (todas as keys);
  bind default `127.0.0.1` (`RPG_HOST` p/ expor); 500 sem `str(e)`; teto em
  `input_text`; poda do dict do rate limit
### Fase 10b — local-first, sem deploy — ✅ fatia local `done` (2026-08-20)

O mapa completo está na
[spec-mãe](specs/fase-10b-plano-mestre-local-first.md). Supabase Local é o alvo
primário de ensaio, mas todos os serviços ficam atrás de portas Python e têm
perfil portátil Postgres+pgvector/OIDC/S3. Para a futura certificação externa,
**Railway foi escolhida como alvo primário e Render como contingência**: o
primeiro corte mantém `web/dist` + FastAPI no mesmo serviço público e roda o
worker numa segunda instância da mesma imagem. JSON+FAISS permanecem para CLI e
suíte; nenhum diretório histórico será apagado automaticamente.

1. [Fundação local + portas/adapters](specs/fase-10b-fundacao-local-portas-adapters.md) `done`
2. [Postgres híbrido + migração verificável](specs/fase-10b-postgres-persistencia-transacional.md) `done`
3. [Turnos duráveis + idempotência multiworker + fila](specs/fase-10b-turnos-duraveis-concorrencia-fila.md) `done`
4. [Auth local + RLS + isolamento](specs/fase-10b-auth-rls-isolamento.md) `done`
5. [Memória transacional em pgvector](specs/fase-10b-pgvector-memoria-transacional.md) `done`
6. [Storage portátil para assets dinâmicos](specs/fase-10b-storage-assets-portavel.md) `done`
7. [Observabilidade + backup/restore + carga/caos](specs/fase-10b-observabilidade-backup-caos.md) `done`
8. [Certificação cloud portátil — futura](specs/fase-10b-certificacao-cloud-portavel.md) `draft`

**Decisões:** não manter dual-write permanente; não segurar transação durante
LLM; Postgres é a primeira fila/coordenação (Redis só com evidência); arte curada
continua estática; fato de memória confirma com o turno e embedding pode ser job;
Railway/Render/Supabase remotos só entram na última spec, após aprovação e
orçamento; Vercel permanece benchmark opcional, não dependência.

**Publicação (2026-08-17):** o lote funcional das sessões 39–46 e estas nove
specs foram sincronizados na `main` após 1480 testes offline, Ruff e build Vite
verdes. Isso publica somente o repositório; a infraestrutura externa continua
sem provisionamento e depende de aprovação específica da última spec. O CI de
checkout limpo instala explicitamente os extras `openai` e `anthropic` cujos
builders são cobertos pela suíte de roteamento.

**Critério de aceite 10b:** cada campanha pertence a exatamente um usuário (que
pode ter várias campanhas); zero acesso cruzado; commit de turno exatamente uma
vez; restore comprovado; perfil hosted sem filesystem persistente; migração e
export entre providers verificáveis.

---

## ✅ ENTREGUE — Fase 11 — LLM contract tests (2026-07-06)

> **Spec `done`:** [specs/fase-11-llm-contract-tests.md](specs/fase-11-llm-contract-tests.md)
> — `uv run pytest -m llm_contract -v -s`: 9 contratos (router×2, StoryUpdate
> banal sem alucinação, combate, NPC não-onisciente, TradeIntent, e2e+archivist,
> loot, fallback offline), todos VERDES contra Gemini real em 2026-07-06;
> `tests/test_real_llm.py` migrado/removido; fora do CI padrão (addopts).

**Objetivo:** Validar providers reais (não apenas MockLLM) respeitam contratos (structured output, fallback, schemas).

**Casos mínimos:**

- Router classifica corretamente
- Storyteller respeita contexto
- Combat action é válido
- NPC conversation respeita fatos ocultos
- World change é estruturado e validável
- Archivist resume sem perder crítico
- Fallback funciona quando provider falha

**Nota:** Opcional no CI padrão, mas importante antes de releases.

---

## Backlog adicional — Features menores (ordem livre)

### ~~Sistema de Aliados (Party)~~ → promovido para **Fase 4.5**

### Melhorias da Crônica

> Refinamento 2026-07-13: único item de backlog v2 MANTIDO (os demais foram
> descartados — ver § Próximo ciclo). Search local + download .txt saem na
> spec polish-sessao; ficam aqui os avançados:

- [x] ~~**Arcos:** arc_title + chapters~~ → ✅ entregue na **Fase 3.1**
- [x] **Compressão + busca semântica:** [spec `done` de Crônica avançada](specs/cronica-avancada-compressao-busca-semantica.md)
  — raw imutável; digest assíncrono ao fechar/>20 entradas; endpoint
  `POST /game/chronicle/search` híbrido, sem LLM generativa por consulta.
- [x] ~~**Frontend restante:** search + download .txt~~ → na spec **polish-sessao** (busca local + export)

### ~~Lore Multi-Índice~~ → OBSOLETO

Superado pela Fase 2.5: Codex em `data/codex/` com metadados `type`/`tags`/`visibility`
por chunk (timeline separada, secrets como `hidden`). `world_lore.txt` não existe mais.

### ✅ ENTREGUE — Mapa robusto — restante (2026-07-06)

> **Spec `done`:** [specs/mapa-sublocais-viagem-variavel.md](specs/mapa-sublocais-viagem-variavel.md)
> — `travel_times` por conexão (default 1; intra-cidade 0 sem virar relógio),
> nós `kind: interior` (masmorras/tavernas com danger próprio, abrigo de
> clima, fora do mapa-mundi), 4-6 interiores curados. Detalhe SÓ na spec.

Mapa de Valoria (35 nós: 30 + 5 interiores). Entregue pela spec acima:

- [x] Sub-locais (interiores: masmorras/tavernas com danger próprio, abrigo de clima)
- [x] Tempo de viagem variável por conexão (intra-cidade 0, travessias longas 2-3)
- [x] ~~`economy_tags` por local~~ → absorvido pela **spec 4.4** (R2: `craft_tags` + `economy_tags` nos 30 nós)

### ~~Sistema de crafting~~ → promovido para **Fase 4.4**

### Atmosfera sonora

Depende de sourcing CC0. **Defer até tudo jogável.**

- [ ] Áudio por região e período
- [ ] Efeitos de combate
- [ ] Sourcing de packs CC0

---

## Princípios de desenvolvimento

- **Estado antes de features.** Mundo vivo e auditável > mais features.
- **Lore base ≠ Estado vivo.** Codex é canônico. Campanha muda via events + rules, não sobrescrita de lore.
- **LLM propõe, motor aplica.** Nunca confiar em sinal/valor do LLM sem validar. Tudo estruturado ou rejeitado.
- **Mecânica é Python.** IA narra; números resolvem determinístico (combate, economia, mundo).
- **Regras genéricas, não hardcode.** Morte de qualquer líder dispara mesma regra. Tags + componentes = zero ifs por NPC.
- **MockLLM esconde bugs.** Validar nós novos com chave real (respeitando quota Gemini).
- **Fatiar fino.** Cada fase é testável, jogável, com invariantes claros.

---

## Resumo executivo

### Mudança de direção

Antes: "mais features, sprites depois".  
**Agora:** "estado sólido, depois tudo mais cresce nele".

### Ordem crítica

1. **Fases 2.5-2.8** ✅ ENTREGUES: Codex, event_log, world_projection, rules engine, context builder.
2. **Fase 3** ✅ ENTREGUE (2026-07-03): Clareza de campanha — diário/crônica, codex do jogador, quest log, visualização de estado.
3. **Fase 4** ✅ COMPLETA (2026-07-05, 7 specs `done` + smoke real): Gameplay Core.
4. **Fase 6** ✅ COMPLETA (2026-07-05, specs `done` com smoke real): economia viva, 20 itens únicos, migração de monstros, encontros sistêmicos, clima mecânico.
5. **Fase 7** ✅ COMPLETA (2026-07-05, 3 specs `done` + smoke real): lint de conteúdo + CI, curadoria migration-safe + templates, segredos de NPC separados.
6. **Roteamento multi-provider** ✅ ENTREGUE (2026-07-06, smoke real): 3 tiers + rotas com fallback (produto pago).
7. **Fase 5** ✅ ENTREGUE (2026-07-06, 3 specs `done` + smoke real): agentic playtest + invariantes + telemetria (699 testes).
8. **Fase 11** ✅ ENTREGUE (2026-07-06): 9 contratos LLM verdes contra Gemini real (`-m llm_contract`).
9. **Ciclo fix-playtest-achados** ✅ ENTREGUE (2026-07-13): 6 defeitos do transcrito real + fuga do jogador (715 testes).
10. **Auditoria de segurança** ✅ ENTREGUE (2026-07-13): 8 achados A1–A8 corrigidos + regressão (729 testes).
11. **Fase 8A/8B + Fase 10b local** ✅ ENTREGUES; próxima infraestrutura é a
    certificação cloud opt-in. Sprites/som da Fase 9 seguem no backlog.

Sem 2.5-2.8, as features de economia/craft/encontros ficariam acopladas, contraditórias e não-testáveis — fundação entregue; Fases 4/6/7 construíram gameplay, conteúdo sistêmico e pipeline de autoria em cima dela.

### Métrica de sucesso

- ✅ Fase 2.8: campanha 50 turnos sem contradição; event log rastreável; contexto nunca explode.
- ✅ Fase 4: progressão + buff observável + poção em combate + craft com receita + mercadores distintos + 4v5 + morte com narrativa (smoke real 2026-07-05).
- ✅ Fase 6: porto bloqueado → escassez rastreável no event_log (smoke real 2026-07-05).
- ✅ Fase 7: NPC novo via template validado automaticamente; segredo de NPC não chega ao narrador (smoke real 2026-07-05).
- ✅ Fase 5: 10 perfis × 50 turnos automatizados sem quebrar invariantes (`erros=0`, `violações=0`);
  telemetria por turno com provider/custo; relatório agregado + baseline (smoke real 2026-07-06).
