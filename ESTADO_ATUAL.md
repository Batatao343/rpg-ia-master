# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> **06/10 — SPEC-179 em preparação offline.** Corpus experimental de 14 casos
> (10 target, 4 loot_context), hash `748ab521...89034`; pré voo identifica
> 12 representáveis e 2 não representáveis. O runner usa IDs canônicos da
> cena, exclui segredo/morto/oculto do jogador, registra fallback atual nos
> casos sem Choice Jev e preserva resposta/usage em bloqueio de custo.
> Mínimo de **26 chamadas externas** para A/B; nenhuma ocorreu nesta spec.
> O orçamento anterior de SPEC-178 não cobre esta rodada. Evidência e limites:
> `docs/spec179/README.md`. Gate offline completo no commit de freeze:
> **1.953 passed, 35 skipped, 15 deselected**; revisão Sol independente aprovada.
> SPEC-179 segue `approved` até live e revisão de
> resultado; SPEC-180 depende dela. Produção e régua protegida inalteradas.
> Freeze local `6792193`; push/PR ainda não publicados: auto-review bloqueou
> publicação desse código no GitHub público sem autorização explícita do
> payload e destino, mesmo após varredura de segredos sem achados.

> **05/10 — SPEC-178 `done`; A/B live confirmatório.** Após recarga da
> DeepSeek, o usuário ampliou o teto total para 120 chamadas/US$ 1,20. O run
> `SPEC-178-20261006T013715Z-bedc56c2` completou 3 réplicas pareadas:
> `pipeline_full` A 21/21 vs Jev 20/21; `classifier_eligible` A 48/48 vs Jev
> 46/48. Jev foi mais rápido neste conjunto (p50 265,5 vs 1.367,5 ms), mas
> divergiu duas vezes no mesmo caso de NPC. Raw/summary em
> `evals/runs/jev-router-ab/20261006T013714Z/`, hashes e relatório em
> `docs/spec178/README.md`. Foram 98 chamadas no run, **102/120 no histórico**;
> custo real `unavailable` (reserva não é cobrança). Revisor Sol independente
> **APPROVED** como evidência development/regression; **sem promoção**. A
> produção continua no CLASSIFY atual. SPEC-179 é a próxima dependência.

> **05/10 — SPEC-178 segue `blocked-by-provider` após rotação da chave.** O
> usuário confirmou a troca da chave TypeSafe. A primeira tentativa A/B depois
> disso parou na sanidade do braço CLASSIFY: DeepSeek respondeu HTTP 402
> `Insufficient Balance`; a cascata caiu para Groq e obteve decisão válida,
> mas o protocolo pré-registrado interrompe em erro de quota/configuração.
> Foram 2 chamadas nesta tentativa e 4 das 100 autorizadas no total; 96
> restam, menos que as 98 necessárias para um novo run completo. Jev não foi
> chamado após a rotação; nenhuma réplica, score ou promoção ocorreu. O estado
> bruto final está em `evals/runs/jev-router-ab/20261006T012413Z/raw-recovered.json`
> (SHA-256 `2c80eba8...633aa`); o `raw.json` original ficou stale por bloqueio
> transitório do OneDrive ao substituir o arquivo. O runner agora tenta novamente
> a substituição atômica; 9 testes focados e suíte completa verdes (**1.936
> passed, 35 skipped, 15 deselected**). Revisão Sol independente aprovada em
> `handoffs/SPEC-178-SOL-live-blocker-review.md`. Aguardam saldo DeepSeek e
> decisão do usuário sobre ampliar o limite de chamadas/custo.

> **05/10 — correção TypeSafe; SPEC-178 `blocked-by-provider`.** O usuário esclareceu
> que `JEVMODEL_API_KEY` local veio de `console.typesafe.ai`. O adapter apontava
> indevidamente para `jevmodel.org`, de onde veio o 401. Corrigido para a API
> oficial `api.typesafe.ai/v1/systemone`, com `TYPESAFE_API_KEY` canônica e
> alias para a variável local. Smoke sintético oficial: Jev `jev-1.13.0`,
> Choice válido, usage 394/58, latência 327 ms. A primeira chamada enviou a
> chave TypeSafe ao domínio errado; o usuário foi informado e vai revogar/
> substituí-la. **Nenhuma outra chamada live até confirmar a rotação.**
> O runner A/B permanece fora de produção; preflight do corpus protegido tem
> hash `ad6f48be...59b4`, 21 casos route, 16 elegíveis e 5 gates Python.
> O usuário autorizou Sol High, 100 chamadas/US$ 1; duas chamadas já ocorreram,
> restando 98. Três réplicas pareadas e revisão Sol do resultado ainda faltam;
> não há score ou promoção. SPEC-179 aguarda. Evidência: `docs/spec178/README.md`.
> Após a correção do host, `uv run pytest` terminou verde: **1.935 passed,
> 35 skipped, 15 deselected**. A revisão Sol independente aprovou a correção
> offline; o A/B live continua bloqueado pela rotação da chave.

> **03/10 — SPEC-177 `done`; PR #13 publicado e CI verde.**
> Adapter Jev server-side em `services/jev_decision.py`, com Choice/Noul/Score
> tipados, DTO mínimo, idempotência, timeout total com limite de workers,
> erros fechados e telemetria sem payload/segredo. Nenhuma rota de produção
> mudou. Usuário autorizou Sol High no lugar de Terra High; revisão Sol
> independente **APPROVED** em `handoffs/SPEC-177-SOL-independent-review.md`.
> **22 testes focados** e suíte completa **1.920 passed, 35 skipped,
> 15 deselected** no clone com temp ASCII; governance, índice e Ruff verdes.
> Commit `31ec777` publicado em [PR #13](https://github.com/Batatao343/rpg-ia-master/pull/13),
> empilhado sobre PR #12; `validate` 37142521573 e `eval-gates` 37142521566
> terminaram `success`.
> Sem `JEVMODEL_API_KEY` no início da execução, smoke live opt-in não ocorreu. A SPEC-178 exige A/B
> real com três réplicas e ainda depende da chave, além de autorização
> específica para substituir Terra High. Evidência: `docs/spec177/README.md`.
> **SPEC-178 `MODEL_HANDOFF_REQUIRED`:** handoff preparado em
> `handoffs/SPEC-178-terra-review.md`. A chave Jev foi detectada depois como
> presente no `.env`, sem ler seu valor; chamadas live e substituição Sol High
> para esta spec aguardam autorização expressa.

> **02/10 — SPEC-176 `done`; pacote v5 importado (176–198).** A
> correção local de integridade classificou `STALE_LOCK` por LF/CRLF: 27 casos
> narrative/NPC idênticos à evidência aprovada; o relock canônico mudou somente
> esse hash. `.gitattributes` fixa LF para régua/source; Project Index gerado do
> source final tem 5.516 nós/14.089 arestas e continua selective-only. Focused:
> **80 verdes**; CLI sete suites: **86/86**, sem error/skip; smoke backend:
> **14 perfis × 3 turnos**, zero erro/violações. Gate completo no clone:
> **1.898 passed, 35 skipped, 15 deselected** (317,92 s). Baseline v1 permanece histórica e incompatível por hashes
> CRLF (dataset e artifacts); nenhum delta A/B é válido contra v1. Evidências:
> `docs/spec176/README.md`, `dataset-audit.json` e handoff Sol. Executor atestado
> `gpt-6.1-sol/high`, tarefa `/root/spec176_executor`; revisão independente Sol
> **APPROVED técnico local** em `/root/spec176_reviewer`. O owner aprovou o
> environment `eval-governance`; `validate` 37011116395, `audit-local`
> 37011116477 e `eval-gates` 37011116324 terminaram `success` no commit
> `e621fe0` do [PR #12](https://github.com/Batatao343/rpg-ia-master/pull/12).
> A variável temporária `EVALUATOR_CHANGE_APPROVED` foi removida após o gate.
> SPEC-177 é a próxima; depende de executor Terra High, indisponível nesta
> sessão sem substituição expressamente aprovada. Patch está na branch remota.
> As artes preexistentes do workspace foram preservadas. Nenhum provider,
> gameplay/prompt, cloud ou long-run foi alterado/executado. Este bloco prevalece
> sobre os históricos abaixo.

> **01/10 — plano de evals v4 concluído; SPEC-175 `done`.** O benchmark A/B
> confirmatório v6 foi selado antes dos runs, ocultou o ground truth por
> AES-256-GCM, executou 4 sessões/32 observações e passou revisão Sol no run
> `SPEC-175-SOL-20261001-V6-01`. Localização empatou em 16/16, mas a condição
> com Project Index teve **0/8 vitórias de custo** e piorou as medianas de calls
> (5→8), bytes lidos (24.676→30.999,5) e wall time (38,907s→58,2535s). Decisão:
> retirar o índice do contexto/fluxo padrão e mantê-lo apenas para consultas
> explícitas, seletivas e confirmadas no source. Evidência completa em
> `docs/project-index-benchmark/v6/` e `handoffs/SPEC-175-SOL-review-v6.md`.
> Gate final: **1.895 passed, 35 skipped, 15 deselected**; Project Index fresco
> em **5.507 nós/14.056 arestas**. SPEC-104 cloud permanece `draft`/on hold;
> nenhum provider pago ou long-run foi executado. Este bloco prevalece sobre os
> históricos abaixo.

> **30/09 — SPEC-174 `done`; SPEC-175 em execução.** A baseline v1 preserva 86
> casos determinísticos e F01–F16: todos os hard gates verdes, hashes/ambiente/
> evaluator registrados, comparação de validação com deltas zero. Provider real
> foi omitido pela restrição de custo existente e long-run foi excluído pela
> spec; nenhum target ou dado foi inventado. Evidência em
> `docs/eval-baselines/v1/`. A etapa final mede A/B do Project Index com tarefas
> históricas e decisão pré-registrada; SPEC-104 cloud segue on hold. Este bloco
> prevalece sobre os históricos abaixo.

> **30/09 — SPEC-173 `done`; SPEC-174 em execução.** O CI agora tem gate
> determinístico sempre ativo e jobs seletivos backend/frontend, proteção por
> Environment para régua/datasets, holdout privado somente agregado, contrato
> real manual com teto duro de 20 requests/US$ 0,20 e smoke post-deploy
> read-only com verificação de SHA. Smokes locais: 7 suites de produto verdes,
> frontend 16/16 e playtest 14 perfis x 3 turnos com zero erro/violação. Nenhum
> provider pago foi executado. A SPEC-174 mede a baseline v1 sem mudar produto,
> sem targets inventados e sem long-run; SPEC-104 cloud segue on hold. Este
> bloco prevalece sobre os históricos abaixo.

> **30/09 — SPEC-173 em execução.** Após fechar a SPEC-172 com 16/16 jornadas e
> gate offline verde, a etapa ativa implementa gates CI seletivos, proteção da
> régua, artifacts compatíveis e workflows manuais para provider/holdout/smoke.
> Nenhum long-run ou provider real será disparado nesta implementação; SPEC-104
> cloud segue on hold. Este bloco prevalece sobre os históricos abaixo.

> **30/09 — SPEC-172 `done`; SPEC-173 é a próxima etapa.** Frontend evals agora
> executam F01–F16 em Playwright/Chromium com API determinística, guards globais
> de pageerror/console/rede/5xx, axe e viewports 320/390/768/1440. Smoke
> canônico: **16/16**, pass rate `1.0` e zero erros inesperados, overflow e
> violações a11y serious/critical. A execução encontrou e corrigiu cinco falhas
> reais: bootstrap de auth vazando requests protegidos, fim de SSE sem narração,
> mapa não interativo, contraste 3,77:1 e HUD móvel sem controle de fechar.
> Registry/lock 1.6.0; build, Node e Ruff verdes. Gate final: **1.883 passed,
> 35 skipped, 15 deselected**. Zero provider pago/cloud/long-run; SPEC-104 cloud
> continua on hold. Este bloco prevalece sobre os históricos abaixo.

> **30/09 — SPEC-171 `done`; SPEC-172 está em execução.** Narrative/NPC evals
> têm 27 casos determinísticos para morte, posse, localização, identidade,
> segredo, reward/outcome, presença em cena, ação e lifecycle. O evaluator mede
> decisão, reason e output sanitizado fixture-authored; mutações separam vazamento
> real, substituição neutra e supressão indevida. Smoke v3: claim accuracy `1.0`,
> hard contradictions `0`, NPC identity errors `0`; zero provider/judge. Persona
> segue não bloqueante e sem calibração. Astra aprovou
> `SPEC-171-ASTRA-20260930-01`. Gate final: **1.878 passed, 35 skipped, 15
> deselected**; Project Index **5.420 nodes/13.866 edges**. SPEC-104 cloud segue
> on hold. Este bloco prevalece sobre os históricos abaixo.

> **29/09 — SPEC-170 `done`; SPEC-171 está em execução.** Memory/RAG/context
> agora separa `store -> retrieve -> context -> generation` em 27 casos públicos,
> com adapters nos caminhos reais, trace por evidence ID, Recall@1/3/5, MRR,
> inclusão/descarte de contexto e hard gates de secret/forbidden leak e budget.
> Smoke final `spec170-memory-context-smoke-v3`: 27/27 verde; R@1 `0.5833`,
> R@3/5 `1.0`, MRR `0.8333`, context R@5/write precision `1.0`, leaks/budget
> zero. Astra aprovou `SPEC-170-ASTRA-20260929-01`. Vetores são fixtures offline
> e generation cobre o guard determinístico, não qualidade semântica/prosa. Gate
> final: **1.866 passed, 35 skipped, 15 deselected**. Project Index: **5.399
> nodes/13.814 edges**. SPEC-104 cloud permanece on hold. Este bloco prevalece
> sobre os históricos abaixo.

> **29/09 — SPEC-169 `done`; SPEC-170 está em execução.** Routing/action evals
> agora têm corpus fechado de 25 casos, decisão estruturada pré-narração,
> target exato/conjunto aceito, variantes metamórficas, negativos, diagnóstico
> de structured output e matriz de confusão. Smoke CLI offline: `route_accuracy`,
> `target_accuracy` e `exact_match` em `1.0`, matriz diagonal; zero provider.
> Gate final: **1.851 passed, 35 skipped, 15 deselected**, Ruff verde. Project
> Index: 5.358 nodes/13.713 edges. Revisão por escalada não foi necessária porque
> `RouteType` não mudou. SPEC-104 cloud permanece on hold. Este bloco prevalece
> sobre os históricos abaixo. A SPEC-170 iniciou a separação de
> store/retrieve/context/generate e exige revisão independente Astra.

> **28/09 — SPEC-168 `done`; SPEC-169 é a etapa ativa.** O corpus estruturado de
> state/rules usa `ProjectionEvaluator` e compara só campos declarados. São 12
> casos para eventos, regras, economia/inventário/item único, quests/recompensas,
> lifecycle/death/restore, combate, migração, save/load e replay, além do adapter
> de invariantes existente. Métricas do smoke: `state_transition_pass_rate=1.0`
> e `exact_match=1.0`. Gate final: **1.845 passed, 35 skipped, 15 deselected**,
> zero falhas. Revisão por escalada não foi necessária; zero provider/judge/
> long-run. SPEC-104 cloud permanece on hold. Este bloco prevalece abaixo.

> **28/09 — SPEC-167 `done`; SPEC-168 é a etapa ativa.** O harness em `evals/`
> executa datasets travados sem API key, usa registry explícito de adapters,
> mantém expected/oracle fora da visão do produto, reutiliza invariantes de
> `playtest/`, contabiliza result/error/skip e grava JSON/Markdown endereçáveis.
> Comparação falha fechado por ruler/dataset/config incompatível; identidade do
> produto inclui HEAD, hash dos bytes Git-visible e dirty state. Sol aprovou no
> run `SPEC-167-SOL-20260928-02`. Gate final: **1.841 passed, 35 skipped, 15
> deselected**, zero falhas. SPEC-104 cloud segue on hold; nenhum provider real
> ou long-run. Este bloco prevalece sobre os históricos abaixo.

> **28/09 — SPEC-166 `done`; SPEC-167 é a etapa ativa.** O Project Index local
> entrega grafo determinístico por AST Python, mapa file-only TS/JS, proveniência
> e confidence, ownership/eval maps curados, exclusão de conteúdo privado/gerado,
> freshness por source-tree hash e CLI bounded. Relações HTTP são explicitamente
> `static_best_effort` para não alegar autoridade em Python dinâmico. Sol aprovou
> no run `SPEC-166-SOL-20260928-06` após testes adversariais de staleness, imports,
> schema e bindings FastAPI. Gate final: **1.832 passed, 35 skipped, 15
> deselected**, zero falhas. SPEC-104 cloud segue `draft`/on hold; nenhum provider
> real ou long-run foi usado. Este bloco prevalece sobre os históricos abaixo.

> **28/09 — SPEC-165 `done`; SPEC-166 é a etapa ativa.** A governança em `evals/`
> congela datasets, registry e todo o bundle da régua por SHA-256; compara
> seleção/configuração de baseline; contabiliza resultado/erro/skip; protege os
> próprios controles; proíbe judge blocking até meta-eval; e mantém holdout fora
> do repo público. Astra aprovou no run `SPEC-165-ASTRA-20260928-03` após duas
> rodadas adversariais. Gate: **1825 passed, 35 skipped, 15 deselected**. SPEC-104
> cloud segue `draft`/on hold. Este bloco prevalece sobre os históricos abaixo.

> **28/09 — SPEC-164 `done`; SPEC-165 é a etapa ativa.** `AGENTS.md` agora
> roteia retomada por SPEC-ID, índice/project index, integridade de eval,
> ownership, fluxo deterministic-first, long-run opt-in e menor modelo suficiente.
> Os 9 testes focados passaram; suíte completa: **1809 passed, 35 skipped, 15
> deselected**. A revisão independente Sol foi aprovada no run
> `SPEC-164-SOL-20260928-02`, após corrigir a antiga criação de specs sem ID.
> SPEC-165 (governança de evals) foi desbloqueada. SPEC-104 cloud continua
> deliberadamente `draft`/on hold. Este bloco prevalece sobre os históricos abaixo.

> **28/09 — contratos reais concluídos; matriz B em 1.951/2.000.** Doze specs
> funcionais (SPEC-141/142/144–147/149–152/154/161) passaram seus smokes
> DeepSeek e agora estão `done`. Contrato dirigido: beat elegível concedeu 150
> XP com outcome consistente. Matriz B: campanhas 1–9 completas, zero erros,
> zero violações `error` e zero invocações terminais; campanha 10 parou em
> 151/200 por HTTP 402 `Insufficient Balance`. Total estimado: US$ 1,17628 e
> 4.201 requests. O usuário dispensou a repetição do par 10 após informar que os
> US$ 5 adicionados foram consumidos; SPEC-128 encerrada `done` com a limitação
> explícita. Achados: custo estimado subcontado, prefixo NPC duplicável e warnings
> de repetição NPC ausentes do summary. [Evidência](docs/playtest-matriz-b-2026-09-28.md).
> Gate offline final: **1807 passed, 35 skipped, 15 deselected**.
> Este bloco prevalece sobre os históricos abaixo.

> **27/09 — evals v4: SPEC-163 `done`.** As 162 specs históricas receberam IDs
> estáveis `SPEC-001`–`SPEC-162` pela ordem comprovada de criação no Git; a ordem
> de conclusão permanece separada. A [SPEC-163](specs/SPEC-163-normalizacao-historica-specs.md)
> e o [índice reproduzível](specs/index.yaml) registram status, commits, datas,
> dependências e ambiguidades. [Plano e evidências](docs/evals-inicio-2026-09-27.md).
> Verificador da migração, 7 regressões e Ruff verdes; lint de conteúdo sem
> erros/avisos; suíte final **1807 passed, 35 skipped, 15 deselected**. Nenhum
> provider real ou long-run. SPEC-164 é a próxima etapa; baseline ainda não foi
> medida. Este bloco prevalece sobre os históricos abaixo.

> **CONTINUAÇÃO 26/09 — testes adversos e correções.** Sete eixos `done`:
> artes, contexto, operações, efeitos, leases, frontend e gates. Dois permanecem
> `in-progress`: narrativa/recompensas aguardam contrato DeepSeek explicitamente
> autorizado.
> Recuperação de imagem/cenário após erro validada em Chromium 390/1440.
> Logout integrado ao topo; retomada de ação tolera confirmação perdida sem
> duplicar turno. Guard de memória/contexto agora respeita hipóteses/boatos sem
> permitir segredos; corpus ampliado: 38 testes verdes. Corrigida resposta de
> estado atrasada na retomada e perda de archived/archived_reason em save/load.
> Três testes de crash real locais verdes (job, INSERT de arte, retorno do
> gerador falso). Suíte final: **1800 passed, 35 skipped, 15 deselected**,
> 285,46 s; skips/deseleções são gates opt-in. Build/Node/Ruff/conteúdo verdes.
> Gate final: **25 passed, zero skipped**, com JSON/screenshots/JUnit. A matriz
> expôs e corrigiu perda de arquivamento e deadlock por ordem de locks. Nenhum
> provider pago. [Reconciliação](docs/RECONCILIACAO_ARTE.md)
> documenta contenção segura; importação administrativa ainda não implementada.
> Commit funcional `c7eb25c` publicado na main; CI `validate` verde. CI infra
> **verde** (run 36263717580, 3m27s) e promovido a push/PR da main.
> Este bloco prevalece sobre as pendências históricas abaixo.

> **RETOMADA 2026-09-26 — execução da auditoria, com gates locais reais.**
> [Relatório atual e pendências exatas](docs/auditoria-execucao-2026-09-26.md).
> Nove specs iniciadas: contexto autenticado `done`; oito `in-progress`.
> Implementados guard narrativo, executor/replay, outbox, restore de derivados,
> heartbeat/fencing, sessão/histórico e exibição de retrato. Gate integrado:
> **16 passed, zero skipped** em Postgres/Auth/Storage/browser locais, com
> narrador/gerador falsos. Retrato confirmado → URL assinada → ficha/reload;
> SSE → replay POST sem duplicação; payload divergente → 409.
> Corrigidos dois bugs extras: CHECK de operações sem `art` e perda de ledger/
> orçamento de arte no grafo/save/load. Migração aplicada somente local.
> **1776 passed, 26 skipped, 14 deselected**, 261,64 s, após ajuste de save/load.
> Build e 5 testes cliente verdes;
> Ruff e conteúdo verdes. CI infra configurado como manual, ainda não rodado.
> Restam fault injections específicas, unificação de guards e contratos reais;
> detalhes no relatório/specs, inclusive logout sobreposto ao topo mobile.
> Nenhum custo de provider ou deploy. Usuário autorizou publicar o trabalho
> na main ao final desta validação; isso não encerra as specs pendentes.
> Este resumo substitui os estados de 23/09 e históricos abaixo.

> **RETOMADA 2026-09-23 — auditoria convertida em nove specs aprovadas; primeiro lote executado.**
> [Índice, cobertura e evidências](docs/auditoria-remediacao-2026-09-22.md).
> Três specs novas estão `in-progress` (artes, recompensas/recibos, contexto
> autenticado); seis permanecem `approved`, ainda não implementadas.
> Retratos de raça/classe agora cabem inteiros, sem figura fora do card ou
> legenda duplicada; retratos narrativos usam contain. XP exige beat elegível,
> unique não duplica por aliases no mesmo lote, recibos somam entradas repetidas.
> Fontes de contexto preservam principal/correlação com ContextVars isoladas.
>
> **Validação:** 1743 passed, 18 skipped, 14 deselected (308,01 s); 22 testes
> offline novos. Dois testes visuais novos opt-in passaram separadamente em
> Chromium (390/1440 px), com smoke da aplicação e artes reais sobre API mock
> isolada. Ruff/build/conteúdo verdes; zero erro/aviso de conteúdo.
> Pendente: ampliação/fallback/sizes das artes, evidência narrativa compartilhada,
> operações/transações/leases, sessão frontend e gates; smoke Postgres do contexto
> e smoke dirigido de recompensas não executados. Onze specs anteriores ainda
> têm gates reais pendentes. Nenhuma chamada paga, commit, push ou deploy.
> Este resumo prevalece sobre as contagens e estados históricos abaixo.

> **RETOMADA 2026-09-19 — remediação local antes da matriz B.** A revisão profunda
> encontrou contratos incompletos apesar da suíte verde anterior. O usuário
> aprovou corrigir primeiro as reproduções locais e separar os gates.
> [Spec/adendo](specs/SPEC-162-remediacao-local-contratos-pre-matriz.md) e
> [relatório](docs/remediacao-pre-matriz-2026-09-19.md).
>
> Recuperação agora tem intenção fechada: “pedir ajuda” não libera viagem/ataque;
> socorro usa descanso no mesmo local e incapacidade pode ser recuperada.
> Recibos são calculados, nunca validados por marcador de texto. Memória separa
> sujeito/negação/posse e exige evidência terminal do player para morte. Aliases
> transitivos de NPC sobrevivem à coalescência e ao reload. Prefixos cosméticos
> não escondem repetição da fala. Erros de schema/tool/transporte são distintos.
> A matriz para no primeiro turno inválido e não inicia o próximo par.
>
> **Gates agora separados:** testes locais → contratos reais curtos por feature
> → matriz B global de 2.000 turnos. As dez specs funcionais não exigem mais uma
> B inteira como seu smoke individual; a spec da matriz mantém esse aceite.
> Nenhuma validação real foi declarada concluída. Nenhuma chamada paga, recarga
> consultada ou ação cloud nesta revisão. Os últimos dados de saldo (HTTP 402)
> são históricos de 16/09, não uma consulta nova.
>
> Smoke offline `20260919-150042-217978`: **30/30** turnos, zero erros/violações;
> Ruff e validador de conteúdo verdes (zero erro/aviso). Suíte completa:
> **1721 passed, 16 skipped, 14 deselected** (309,18 s), com **40 testes novos**.
> Inventário: **153 specs — 141 `done`, 11 `in-progress`, uma `draft`**.
> O adendo local está `done`; as onze pendências reais estão discriminadas no
> relatório, não mascaradas pela contagem offline.

> **RETOMADA 2026-09-17 — fechamento local; aceite real bloqueado por saldo.**
> Inventário auditado: **152 specs — 140 `done`, 11 `in-progress`, uma `draft`**.
> As onze têm implementação local e aguardam B real integral; não estão
> certificadas pelo smoke offline. A B anterior parou em **751/2.000 turnos**
> (três campanhas completas), HTTP 402 DeepSeek. O preflight de 16/09 confirmou
> o mesmo bloqueio. **Nenhuma matriz real está rodando.** Após recarga, reiniciar
> B do par 1, não reutilizar campanhas antigas como aceite do build alterado.
> Relatório, lista exata de specs, evidências e comando:
> [fechamento local de 17/09](docs/fechamento-local-2026-09-17.md).
>
> Correções: identidade NPC por aliases no ator/recrutamento e save/load;
> grounding de local, inventário e identidade na memória; queda distinta de morte;
> checkpoint estável, reparo único de transição órfã e readiness no recibo;
> replan em todos os caminhos de viagem entre regiões; diplomático sem loop de
> perguntas e diálogo com proteção de abertura/aspas; vetor compartilhado
> validado por modelo/dimensão. Regressões curtas e smoke **10×3 offline** verdes
> (`20260917-112524-245088`), zero erros/violações. Validador de conteúdo sem
> erros/avisos, Ruff verde e build TypeScript/Vite verde (457 módulos).
> **Suíte completa final: 1681 passed, 16 skipped, 14 deselected**, em 399,43 s;
> um aviso de descontinuação do wrapper FAISS, sem falhas. Os testes opt-in
> de rede/infra não são substituídos por essa execução offline.
>
> Latência: experimento concluído com **no-go** no R29 real; produção permanece
> `RPG_TURN_EXECUTION=sequential`. Fan-out LLM é experimental; arquivista continua
> inline. `ainvoke` usa `to_thread`, sem cancelamento nativo de HTTP.
> [Spec corrigida](specs/SPEC-143-latencia-turno-caminho-critico-concorrente.md).
> Idempotência de claim Postgres foi corrigida e teve gate infra local 13/13 em
> 28/08; não foi realizado deploy. Cloud permanece `draft`, dependente de
> autorização/contas/orçamento. Fase 9 (sprites/som) não tem spec aprovada.
>
> **As sessões abaixo são histórico.** Datas, contagens e pendências antigas
> não substituem este resumo nem os estados atuais dos arquivos em `specs/`.

> **🧪 SESSÃO 58 (2026-08-27): matriz A fechada, quatro contratos corrigidos,
> matriz B real é o próximo gate.** A baseline válida reúne **10×200 = 2.000
> turnos**, zero erro de turno, 12 violações `error`, 193 warnings, 5.205 sucessos
> LLM em 5.224 tentativas e US$ 1,46272. Relatório e seleção exata dos runs:
> [playtest-matriz-a-2026-08-27](docs/playtest-matriz-a-2026-08-27.md).
>
> A auditoria mostrou quatro recorrências de correções antigas incompletas. As
> specs [ciclo de vida](specs/SPEC-141-contrato-canonico-ciclo-vida-acoes.md),
> [resultado canônico](specs/SPEC-144-resultado-canonico-turno-apresentacao.md),
> [interações/progresso](specs/SPEC-142-interacoes-progresso-elegibilidade.md) e
> [structured output com evidência](specs/SPEC-145-structured-output-evidencia-recuperacao.md)
> estão `in-progress`: implementação offline concluída, aguardando somente a B.
> O grafo agora barra ação incompatível pela fase do ator (Vitalidade 0 sozinha
> não é morte), finaliza ledger antes da apresentação, compartilha elegibilidade
> trait-aware com os perfis e recupera JSON raw válido sem nova request. As
> sequências reincidentes viraram testes curtos; suite completa: **1621 passed,
> 16 skipped, 14 deselected**. Ruff verde. Smoke offline pareado **30/30**:
> `20260827-123929-428917`.
>
> Próximo comando formal: matriz B real 10×200, `deepseek-paid`, 800 requests e
> US$ 0,25 por campanha. Qualquer regressão nova interrompe o ciclo para decisão
> do usuário. A primeira tentativa B (`20260827-135829-799539`) foi interrompida
> deliberadamente no par 1: a inspeção do save mostrou que outcomes canônicos e
> progresso de interação ainda não sobreviviam reload. `persistence.py` agora
> persiste ambos, com regressão save→load e default `{}` legado; esse run é
> inválido e não entra na comparação. A spec de latência permanece `draft`.

> **📝 SESSÃO 57 (2026-08-27): spec de latência intraturno em `draft`.** A
> [spec de caminho crítico concorrente](specs/SPEC-143-latencia-turno-caminho-critico-concorrente.md)
> separa latência de uma interação, throughput entre campanhas e latência
> percebida pelo SSE. Com base em 2.000 turnos válidos da matriz A, especifica
> fan-out/fan-in seguro de plano+rota, embedding único com buscas de contexto
> paralelas, `WorldPulse` puro, paridade `RoutedLLM.invoke/ainvoke` e finalização
> canônica antes de derivar memória em worker. Não foi implementada: aguarda
> aprovação. A concorrência E2E entre jogos
> distintos continua reservada a uma spec própria de go-live. Gate documental:
> **1620 passed, 16 skipped, 14 deselected**.
>
> A décima campanha A foi reiniciada isoladamente como
> `20260827-114435-548287` (loot_abuser, Sangromante nível 20, seed 6209), após a
> tentativa anterior falhar no turno 75 por `CampaignPlanModel=None`. Ela estava
> concluída em 200/200, zero erro e duas repetições de abertura.

> **▶ SESSÃO 56 (2026-08-21): continuação da matriz A.** O run
> `20260820-200416-642340` completou os pares 1–4 (800 turnos) e parou no turno
> 81 do par 5 por um `Connection error` isolado do DeepSeek; o fail-closed impediu
> os pares seguintes. A evidência já contém um achado real: 7 ocorrências de
> `player.zero_vitality_outside_terminal` no perfil combate. O explorador
> pós-fix completou 200/200, com três mortes em locais distintos e nenhuma
> reincidência em Vorr; timeout isolado e single-flight também foram validados,
> fechando suas três specs como `done`.
>
> A spec `playtest-matrix-continuacao` adiciona `--start-index 5`: cria outro
> manifesto só para os pares 5–10, sem tocar nos quatro summaries válidos, e
> reinicia o comerciante desde o turno 1 com Corruptor/nível 9/seed 6204. Não há
> mudança de gameplay antes de completar a coleta A. Gate: **1610 passed, 16
> skipped, 14 deselected**. Depois da continuação, os dois run IDs serão
> agregados por índice/seed para análise, specs e correções antes da B integral.

> **▶ RETOMADA DA SESSÃO 55 (2026-08-20): DeepSeek recarregado.** A tentativa
> `20260820-185627-750638` validou o par normal em **200/200**, com 542 sucessos
> reais, custo US$ 0,15344, zero erro/invariante `error`/erro de observabilidade;
> houve três warnings do mesmo NPC remoto, reservado à análise formal da A. O
> explorador chegou a 71 turnos, mas três invocações independentes expiraram no
> antigo timeout DeepSeek de 12 s no turno 71. Antes disso, nove mortes revelaram
> reincidência em local fatal (cinco seguidas na Fortaleza de Vorr). As specs
> `deepseek-paid-timeout-longrun`, `explorador-aprende-com-mortes` e
> `playtest-matrix-single-flight` implementam, respectivamente: janela isolada
> de 40 s sem mudar produção; `location_id` no histórico e filtro prudente do
> perfil; lock atômico local que impede matrizes concorrentes. Gate offline:
> **1608 passed, 16 skipped, 14 deselected**. A1 deve reiniciar do par 1.
>
> **Histórico da retomada:** O preset
> `deepseek-paid` isola `deepseek-v4-flash` nos tiers CLASSIFY/FAST/SMART, sem
> misturar provider ou MockLLM. Preflight real estruturado passou 3/3 após a
> recarga. A primeira retomada A1 (`20260820-180632-012432`) foi corretamente
> interrompida no turno 2: o DeepSeek devolveu 6 beats e o teto Pydantic de 5
> rejeitou toda a resposta. A spec `campaign-beats-overflow-provider` agora
> limpa vazios/espaços e retém os cinco primeiros em Python; menos de três segue
> inválido. Gate pós-fix: **1597 passed, 16 skipped, 14 deselected**. O reinício
> `20260820-181149-643772` encontrou no turno 1 um `WorldPulse=None` isolado
> após seis sucessos reais. A spec `structured-output-retry-provider` agora
> regenera structured output inválido no mesmo provider. O run
> `20260820-182003-393045` avançou 150 turnos limpos (374 sucessos, zero
> violação/observabilidade, 7/7 combates encerrados), mas duas gerações SMART
> consecutivas retornaram `CampaignPlanModel=None`. Replay do mesmo save passou
> imediatamente; o teto agora é de três gerações totais. Falha HTTP/quota segue
> fail-fast, sem fallback determinístico. Gate: **1600 passed, 16 skipped, 14
> deselected** e preflight DeepSeek 3/3. Também foi encerrado um processo Groq
> órfão; o single-flight correspondente agora está implementado. A1
> reinicia do par 1; B repetirá exatamente pares, níveis, seeds e tetos.

> **🚧 SESSÃO 55 (2026-08-20): ciclo pareado 10×200 em execução.** Os seis
> achados do comerciante real ganharam a spec
> `remediacao-playtest-comerciante-real`: observação de mercado é read-only,
> ledger de venda usa delta negativo de item, viagem limpa a cena antes de
> encontros, contexto/aliados filtram NPC remoto, ouro narrado é reconciliado e
> FAST tenta Groq logo após DeepSeek (timeout próprio default 12 s). O warning
> `narrative.recycled_npc` agora exige uso observável, eliminando flag residual.
>
> A spec `matriz-longrun-multiperfil-niveis` adicionou `start_level=1..20` pelo
> pipeline oficial de XP, resolução determinística de subclasse/escolhas, preparo
> de Cartas e Ápice. `matrix-suite` fixa 10 perfis × 5 classes × níveis
> 1/3/5/7/9/11/13/15/18/20 × seeds 6200–6209 e persiste a configuração no
> manifesto. Smoke offline **10×3 = 30/30** (`20260820-134015-951254`) e suíte
> completa **1578 passed, 16 skipped, 14 deselected** verdes. Próximo passo:
> matriz A real 10×200; depois specs/fixes e matriz B exatamente pareada. Pela
> condição do usuário, qualquer regressão nova em B interrompe o ciclo.
>
> **A0 virou diagnóstico de capacidade:** run `20260820-134236-013629` completou
> somente 2/10 campanhas (678 turnos); oito bateram o teto porque providers sem
> saldo/quota empurraram o fallback, e o cap fechou apenas após o turno corrente.
> O run revelou quatro correções agora implementadas: preflight real + preset
> Groq-only com pacing; structured output OpenAI-compat seguro após `AIMessage`;
> Mimetismo Morto não se repete quando o inimigo já está oculto; fuga a
> Vitalidade 0 não evita o fluxo terminal; e relatório/NPC reciclado ganharam
> precisão. Detalhe: [diagnóstico A0](docs/playtest-matriz-a0-2026-08-20.md).
>
> Preflight real passou nos tiers CLASSIFY/FAST/SMART; smoke offline pós-fix
> `20260820-155100-829869` fez **30/30**, sem erro/violação. Suíte completa:
> **1591 passed, 16 skipped, 14 deselected**. A0 não é baseline; falta executar
> A1 completa e, depois dos achados/fixes, a B pareada.
>
> **A1 foi interrompida por perda de capacidade LLM:** run
> `20260820-155300-494278` persistiu 1/10 pares. O normal chegou a 200 turnos,
> mas teve somente 89 sucessos em 796 tentativas; 707 falharam por cota diária/
> rate/tool call e 146 turnos ficaram sem sucesso de rede. Guards do produto
> mantiveram a campanha viva, portanto o resultado NÃO é baseline LLM-only.
> O processo foi abortado antes dos outros nove pares. Relatório:
> [A1 capacidade](docs/playtest-matriz-a1-capacidade-2026-08-20.md).
>
> A spec `playtest-real-llm-fail-closed` agora agrupa tentativas por invoke e
> aborta a matriz no primeiro grupo sem `success`, sem iniciar o par seguinte;
> produto/offline mantêm resiliência. A1 confirmou as correções Python: combates
> em 6/4 rodadas, dois casos de Vitalidade 0 resolvidos por restore, duas mortes
> completas no relatório e zero warning de NPC reciclado. Gate: **1594 passed,
> 16 skipped, 14 deselected**; smoke offline pós-fix 10×3 = 30/30
> (`20260820-171103-075466`). Para retomar A1/B falta capacidade externa:
> recarregar um provider barato ou instalar/configurar LLM local; Ollama/LM
> Studio não estão instalados.

> **✅ SESSÃO 54 (2026-08-20): comerciante 1×200 real concluído.** O preflight
> encontrou a rota FAST do Groq apontando para `llama-3.3-70b-versatile`, modelo
> removido; ela agora usa `openai/gpt-oss-120b`, coberto por regressão offline e
> contrato real de `NPCResponse`. O smoke corrigido fez 10/10 sem fallback
> terminal.
>
> Run `20260820-112050-208317`: **200/200**, `data_complete=true`, `mock=false`,
> zero erro/invariante `error`/erro de observabilidade e zero invocação terminal;
> 548 sucessos reais, oito fallbacks entre providers e custo **US$ 0,162860** de
> US$ 0,25. Mix: economia 38%, exploração 24,5%, quest 11%, social 11% e
> sobrevivência 15,5%; 4 mercados, 3 regiões, 1 restock, 8/8 combates encerrados
> e 2 restores seguros. A spec comerciante virou `done`.
>
> A auditoria de 21 turnos abriu evidência para três P1 (observação de mercado
> parseada como compra, NPC remoto como aliado sem recrutamento e sinal visual
> errado ao vender) e três P2 (contexto NPC residual, ouro divergente na prosa e
> uma cauda de 47,1 s). Foram especificados/corrigidos na sessão 55 acima.
> Relatório: [playtest real comerciante](docs/playtest-comerciante-real-2026-08-20.md).
> Gate final: `uv run pytest` = **1565 passed, 16 skipped, 14 deselected**.

> **✅ SESSÃO 53 (2026-08-20): prontidão local G0–G7 certificada.** As sete
> fatias locais da Fase 10b e o plano mestre viraram `done`; certificação cloud
> continua isolada em `draft`, sem provisionamento. Supabase Local passou
> `infra_local` **13/13**, `security_local` **5/5** e pgTAP **14/14**. Carga real
> em dois processos confirmou 12 commits, dedupe exatamente uma vez, 12 jobs e
> commit p95 **32,257 ms**; caos convergiu 5/5. Backup DB+Auth+Storage foi
> restaurado após reset explícito com RPO 0 e RTO **36,19 s**.
>
> Observabilidade opcional agora é Prometheus+Grafana+OTel Collector+Tempo:
> scrape `up`, dashboard provisionado, cinco traces consultáveis e sete alertas
> validados com fixtures fire/resolve. Browser Python passou duas vezes em
> desktop/390 px; foram corrigidos bootstrap auth com 401, `aria-label` inválido,
> favicon 404 e medição flakey durante animação. O longrun pós-upgrade repetiu
> **5×200 comerciante = 1.000/1.000**, zero erro/violação e 38 transações. Um
> `WinError 5` real no catálogo de NPC ganhou retry exponencial + regressão.
>
> Supply chain: `uv lock --upgrade`, `pip-audit` e `npm audit` com **0
> vulnerabilidades**, scanner de segredos com **0 findings**, Ruff/conteúdo/Vite
> verdes. Gate final: `uv run pytest` = **1564 passed, 16 skipped, 14
> deselected**. Relatório: [readiness-local](docs/readiness/readiness-local.md).
> Produto: tiers 5+/níveis 9–20, Fase 8B e Crônica avançada estão `done` no
> aceite local. Restam apenas dois opt-ins: comerciante 1×200 real (custo LLM) e
> certificação cloud Railway/Supabase.

> **✅ SESSÃO 52 (2026-08-19): implementação local-first + quatro specs de produto.**
> A fatia local da Fase 10b agora possui perfis `legacy/local/hosted`, contratos
> de GameStore/JobQueue/BlobStore/VectorMemory/RuntimeCatalog, Supabase local com
> Postgres+RLS+Auth+pgvector+storage, turnos/receipts idempotentes, workers,
> transferência preview-first, recovery de operações, backup/restore e telemetria
> redigida. Smoke local real de infraestrutura confirmou Auth→novo jogo→SSE→retry
> e isolamento A/B; `pytest -m infra_local` = **11 passed**.
>
> Produto: progressão vai ao nível 20, com **80 Cartas tardias**, Maestria,
> Ápices e escolha explícita/irreversível de subclasse no nível 3; Fase 8B tem
> briefs ancorados, budgets raros por arco, fila/assets idempotentes e snapshot
> `gpt-image-2-2026-04-21`; Crônica avançada preserva raw, comprime em job e busca
> híbrida por owner/campanha; o comerciante ganhou política stateful, livro de
> cotações e telemetria econômica.
>
> Aceite comerciante `20260819-004210-869761`: **5×200 = 1.000/1.000 turnos**,
> `data_complete=true`, zero erro/violação, 36 transações, 4–5 mercados,
> 3–4 regiões e cinco restocks. Foram corrigidos dano climático pré-fuga sem
> fluxo terminal e aprendizado do destino fatal após rollback. Relatório:
> [playtest-comerciante-2026-08-19](docs/playtest-comerciante-2026-08-19.md).
>
> Gates finais: conteúdo e Ruff verdes; Vite (457 módulos) verde; browser em
> 390 px sem overflow/console error; `uv run pytest` = **1548 passed, 12 skipped,
> 14 deselected**. Specs de produto permanecem `approved` somente pelos smokes
> pagos deliberadamente não executados (imagem/LLM real). Certificação Railway/
> Supabase remoto continua `draft`: nenhum serviço externo foi provisionado.

> **📝 SESSÃO 51 (2026-08-18): decisão explícita de subclasse adicionada às specs.**
> O nível 3 agora é o momento formal proposto para escolher, antes da Carta do
> nível, uma das três subclasses da Postura. Níveis 1–2 oferecem somente tronco;
> depois da confirmação irreversível, apenas tronco + ramo escolhido ficam
> elegíveis. `player.subclass` será autoridade em runtime; inferência pela
> primeira Carta fica restrita à migration idempotente de saves legados, que
> preserva inclusive Acervos antigos com ramos misturados sem permitir novas
> aquisições rivais.
>
> A Fase 8B também fecha a interação visual: retrato inicial usa raça e
> classe-base; `subclass_chosen` gera zero job e zero custo. A subclasse entra
> apenas numa reformulação manual ainda disponível e nas futuras cenas épicas,
> usando vocabulário visual público curado. Specs seguem `draft`; nenhum código,
> migration, imagem ou chamada paga foi executado nesta sessão. Gate:
> `git diff --check` verde e `uv run pytest` = **1480 passed, 1 skipped,
> 14 deselected** (4 warnings de dependências).

> **📝 SESSÃO 50 (2026-08-17): quatro specs de produto, sem implementação.**
> Foram especificadas as quatro pendências priorizadas com o usuário:
> [tiers 5+ / níveis 9–20](specs/SPEC-127-tiers-5-plus-classes-niveis-9-20.md),
> [Fase 8B — arte dinâmica rara](specs/SPEC-125-fase-8b-geracao-dinamica-arte.md),
> [Crônica avançada](specs/SPEC-124-cronica-avancada-compressao-busca-semantica.md) e
> [playtest longo comerciante](specs/SPEC-126-playtest-longo-perfil-comerciante.md), todas
> `draft`. Nenhuma mecânica, migration, dependência ou chamada paga foi executada.
>
> Decisões fechadas: cap real 20 + **80 Cartas** tardias (20 tronco/45 subclasse/
> 15 Ápices); Virtudes seguem no teto 5 e ganham Maestria nos níveis 12/16/20;
> GPT Image 2 usa snapshot pinado e geração apenas para jogador, NPC persistente
> sem arte e um épico por arco; orçamento visual é **por arco** (4 NPC + 1 épica,
> cooldown 15), sem teto de campanha; cenas com o herói reutilizam seu retrato e
> prompts possuem envelope explícito de anatomia/pose natural. Crônica preserva
> raw e busca só a campanha atual, sem resposta generativa. Comerciante vira
> stateful/não onisciente e será validado em 5×200 offline + 1×200 real.
>
> Dependências deliberadas: 8B aguarda fundação/fila/storage 10b; Crônica
> assíncrona aguarda fundação/fila e usa pgvector após a 10b.5. Classes e harness
> comerciante podem avançar antes. Gates: links locais modificados válidos,
> `git diff --check` verde e `uv run pytest` = **1480 passed, 1 skipped,
> 14 deselected** (4 warnings de dependências).

> **🚀 SESSÃO 49 (2026-08-17): lote pronto publicado na `main`.**
> A publicação reúne as remediações das campanhas longas das sessões 39–46,
> seus serviços/testes/relatórios e as nove specs `draft` da Fase 10b, incluindo
> Railway como alvo futuro e Render como contingência. O push também sincroniza
> os 21 commits que a `main` local já mantinha à frente de `origin/main`.
> Gates imediatamente anteriores ao commit: `uv run pytest` = **1480 passed,
> 1 skipped, 14 deselected**; Ruff **verde**; `npm.cmd run build` **verde**.
> “Publicar na main” aqui significa versionar e enviar o código-fonte ao GitHub;
> nenhum projeto Railway/Render/Supabase nem recurso pago foi provisionado.
> O primeiro CI Linux do push expôs ambiente incompleto: `uv sync` não instalava
> os extras que três testes de roteamento exercitam. `validate.yml` passou a usar
> `uv sync --extra openai --extra anthropic`, cobrindo tanto os providers
> OpenAI-compat primários quanto o fallback Anthropic num ambiente limpo.

> **📝 SESSÃO 48 (2026-08-16): alvo de hospedagem escolhido, sem deploy.**
> A [certificação cloud](specs/SPEC-104-fase-10b-certificacao-cloud-portavel.md) agora
> registra **Railway como alvo primário e Render como contingência**. A decisão
> aproveita a arquitetura existente: um serviço público `api-web` serve
> `web/dist` + FastAPI na mesma origem e um serviço privado `worker` reutiliza a
> mesma imagem com outro comando. Isso acomoda SSE/turnos LLM longos e polling
> de jobs como processos Docker normais; Vercel fica como benchmark opcional
> enquanto Services estiver em Private Beta. Supabase Local e as portas
> Postgres/OIDC/S3 continuam inalterados. Nenhum serviço, conta ou recurso remoto
> foi criado; a decisão ainda depende dos gates e orçamento da spec `draft`.
> Links locais **235/235** e `git diff --check` verdes. `uv run pytest` final:
> **1480 passed, 1 skipped, 14 deselected**; uma execução anterior oscilou por
> `WinError 5` no rename temporário do teste SSE, que passou isolado e na
> repetição integral sem qualquer alteração de código.

> **📝 SESSÃO 47 (2026-08-16): Fase 10b local-first especificada, sem implementação.**
> O projeto inteiro foi mapeado para a transição de laboratório local até
> produção: além de JSON/FAISS e locks por processo, a auditoria incluiu os
> overlays mutáveis de NPC, bestiário, artefatos e conhecimento revelado, o
> cliente sem identidade, assets, jobs, backup e operação.
>
> Foram criadas **9 specs `draft`**: o
> [plano mestre](specs/SPEC-108-fase-10b-plano-mestre-local-first.md) + oito fatias em
> ordem — [fundação/adapters](specs/SPEC-105-fase-10b-fundacao-local-portas-adapters.md),
> [Postgres](specs/SPEC-109-fase-10b-postgres-persistencia-transacional.md),
> [turnos/fila](specs/SPEC-111-fase-10b-turnos-duraveis-concorrencia-fila.md),
> [Auth/RLS](specs/SPEC-103-fase-10b-auth-rls-isolamento.md),
> [pgvector](specs/SPEC-107-fase-10b-pgvector-memoria-transacional.md),
> [storage](specs/SPEC-110-fase-10b-storage-assets-portavel.md),
> [operação/backup/caos](specs/SPEC-106-fase-10b-observabilidade-backup-caos.md) e
> [certificação cloud futura](specs/SPEC-104-fase-10b-certificacao-cloud-portavel.md).
>
> Decisões: Supabase Local como ensaio zero-custo, mas domínio atrás de portas
> Python e perfil Postgres+pgvector/OIDC/S3 portátil; JSON+FAISS permanecem para
> CLI/testes; sem dual-write permanente; sem transação aberta durante LLM; fato
> de memória confirma com o turno e embedding vira job recuperável; Postgres é a
> primeira fila/coordenação; arte curada continua estática. **Railway é o alvo
> primário da futura certificação externa e Render a contingência:** `api-web`
> serve `web/dist`+FastAPI na mesma origem, enquanto `worker` reutiliza a mesma
> imagem com outro comando. Vercel fica como benchmark opcional. Serviços
> Railway/Render/Supabase remotos só entram na última spec após aprovação e
> orçamento. **Nada foi
> implementado/provisionado:** zero container iniciado, migration/dependência/
> código funcional alterado ou deploy realizado. Links 9/9 e `git diff --check`
> verdes; `uv run pytest` = **1480 passed, 1 skipped, 14 deselected**.

> **✅ SESSÃO 46 (2026-08-16): cinco remediações do longrun real `done`.**
> Os achados da sessão 45 viraram as specs
> [memória NPC](specs/SPEC-114-memoria-npc-sucesso-ledger.md),
> [chase/fuga](specs/SPEC-100-chase-progresso-e-fuga.md),
> [retomada/conversão de quests](specs/SPEC-119-quests-retomada-conversao.md),
> [estado/origem pós-fuga](specs/SPEC-118-pos-fuga-roteamento-origem.md) e
> [ritmo normal v2](specs/SPEC-121-ritmo-combate-normal-v2.md), todas `done`.
>
> Sucesso direto de memória privada agora espelha o mesmo `npc_claim/reported`
> no ledger sem segundo write; chase entra no fingerprint e fuga tem teto local
> de seis tentativas; fuga limpa toda a cena transitória sem apagar o recibo do
> turno; descanso/viagem são STORY e só hostilidade explícita vira provocação.
> O perfil normal navega por BFS até quests, faz duas investigações distintas,
> mede conversão D+0..D+3, usa cooldown 20, foge desde round 3 e busca abrigo.
>
> Aceite MockLLM `20260816-113051-596798`: **200/200**, zero erro/violação,
> quatro rotas, combate **20,5%** (antes 45%), 7/7 conflitos encerrados, quatro
> pedidos→4 conversões e 15 quests concluídas/recompensadas; memória final com
> 9 `npc_claim` no ledger para 9 writes. Smoke LLM real dirigido: ataque →
> COMBAT/provocação, investigação/descanso → STORY; conversa NPC gravou Jina
> e retornou `npc_claim/reported`, fila vazia. Gate: **1480 passed, 1 skipped,
> 14 deselected**; Ruff verde nos arquivos tocados. Uma tentativa adicional de
> campanha real 30t (`20260816-113124-829110`) ficou presa no startup após
> structured SMART inválido e foi encerrada manualmente; não compôs o aceite.

> **🧪 SESSÃO 45 (2026-08-16): longrun real pós-remediação.** Run
> `20260816-100206-334105`, perfil `normal`, seed 46: **200/200**, `mock=false`,
> zero exceções/timeout/erro de observabilidade, 489/491 sucessos LLM, dois
> fallbacks DeepSeek→Groq, US$ 0,137760, p50 9,365 s/p95 20,109 s. O run formal
> ficou `failed` por 1 `error` de invariante e teve 1 warning.
>
> Checkpoint/origem/relógios passaram: duas mortes em epochs distintos,
> `replayed_starts=0`, restore sempre fora de combate, origens 7 provocação/5
> perigo regional e final ação 200/turno canônico 163/epoch 2. Latência caiu
> contra o baseline (p95 35,3→20,1 s); start de combate p95 19,858 s.
>
> Achados: sucesso direto de dois `npc_claim` Jina não entrou no ledger global
> (final 117/117 inference/speculative); chase progrediu e escapou após onze
> tentativas, mas `combat.no_progress` gerou falso positivo por ignorar o track;
> quest criada em D+1 chegou a uma investigação e não foi retomada pelo perfil;
> descanso pós-fuga reabriu combate como `player_provoked`; combate ocupou 45%.
> Relatório: [playtest-longrun-real-2026-08-16](docs/playtest-longrun-real-2026-08-16.md).
> Nenhuma correção de código foi aplicada nesta sessão de diagnóstico. Gate:
> **1466 passed, 1 skipped, 14 deselected**.

> **✅ SESSÃO 44 (2026-08-13): remediação do longrun de observabilidade `done`.**
> Cinco specs fecharam P0/P1/P2: [checkpoint seguro](specs/SPEC-101-checkpoint-seguro-fora-combate.md),
> [origem por cena](specs/SPEC-117-origem-combate-por-cena.md),
> [memória/quests verificáveis](specs/SPEC-113-memoria-autoridade-quests-verificaveis.md),
> [telemetria de rollback/abort](specs/SPEC-123-telemetria-rollback-abort.md) e
> [latência do início de combate](specs/SPEC-112-latencia-inicio-combate.md).
>
> Checkpoint ativo é recusado e slot legado é saneado; a causa da cena nova
> vence rótulo histórico; alegações de NPC entram no ledger como `reported` e
> especulação velha sai do prompt; missão no alvo conclui após duas investigações
> distintas via evento Python. Morte expõe os três relógios, `death_history` não
> retrocede, conflitos têm ID por instância/epoch e timeout preserva prefixo/nós.
> A geometria base do combate passou a ser Python, removendo um invoke FAST.
>
> Aceite mock `20260813-085903-974550`: **200/200**, zero erro/error, seis mortes
> em seis epochs, zero replay, 14 conflitos iniciados/14 encerrados, oito quests
> criadas/concluídas, memória com 100% de autoridade e `combat_agent` p95 127 ms.
> Smoke real `20260813-090120-046611`: 2/2, `mock=false`, 11 sucessos de rede
> DeepSeek + quatro no startup, zero erro/violação/observabilidade, p95 19,9 s.
> Gate: **1466 passed, 1 skipped, 14 deselected**. Avisos esporádicos WinError 5
> no rename atômico do save sob OneDrive tiveram retry e não abortaram o run.

> **🧪 SESSÃO 43 (2026-08-13): longrun das novas observabilidades.** Run real
> `20260813-002535-998525`: 80 turnos úteis + timeout tardio na linha 81 após
> suspensão do notebook, zero violações, 225/227 sucessos LLM, US$ 0,06384,
> p50 9,1 s/p95 35,3 s e 33,3% combate. Run mecânico
> `20260813-011902-138686`: 200/200, zero erros, mas warning de 68% combate.
>
> As métricas novas revelaram um **P0**: checkpoint pode ser gravado com combate
> ativo e aprisionar o jogador em morte→restore (27 mortes; checkpoint 70→morte
> 73 repetido dez vezes). P1: toda origem ficou `player_provoked`, inclusive
> descanso/viagem; memória real terminou 27/27 especulativa apesar de writes
> canônicos/relatos; uma quest progrediu mas não concluiu após retomadas. P2:
> morte mistura relógios, `downed_count` some no rollback, encerramentos inflam e
> linha abortada degrada o contrato JSONL. Diagnóstico completo em
> [playtest-longrun-observabilidade-2026-08-13](docs/playtest-longrun-observabilidade-2026-08-13.md).
> Nenhuma mecânica foi alterada nesta sessão; achados aguardam specs.
> Segunda tentativa real `20260813-012402-094797`: 34 úteis + timeout após nova
> suspensão, zero violações/mortes, p95 29,0 s, 106/109 sucessos e US$ 0,033944.
> Total real observado: **114 ações úteis, 331/336 sucessos, US$ 0,097784**;
> nenhuma campanha real chegou a 200 por suspensão recorrente desta máquina.

> **✅ SESSÃO 42 (2026-08-13): melhorias pós-longrun `done`.** Quatro specs
> fecharam os oito pontos da análise: [objetivo público + ciclo de quests](specs/SPEC-115-objetivo-publico-ciclo-quests.md),
> [direção social + origem de combates](specs/SPEC-122-ritmo-social-origem-combates.md),
> [latência por nó](specs/SPEC-116-observabilidade-latencia-nos.md) e
> [continuidade/memória/morte](specs/SPEC-102-continuidade-memoria-morte.md).
>
> Beats e clímax privados não saem mais pela API nem orientam NPCs; a view pública
> usa side quest ativa ou arco/local. Quests têm ledger `created →
> location_reached → completed`, recompensa Python idempotente de 20 ouro além do
> XP e funil no playtest. Combates preservam origem causal fechada e ausência de
> NPC dá destino real adjacente, sem inventar interlocutor.
>
> Saves v7 separam `session_action_count`, `world.turn_count` canônico e
> `timeline_epoch`; restore conserva histórico da morte e informa exatamente o
> que mantém/reverte na API e no modal. Memória agora agrega confiança,
> autoridade e inferências especulativas antigas, sem promover repetição por si.
> JSONL/summary/report medem latência count/média/p50/p95/max por nó sem chamadas
> extras. Smoke MockLLM `20260813-001000-370465`: 12/12, zero erro/violação;
> build Vite verde. Gate: **1455 passed, 1 skipped, 14 deselected**.

> **✅ SESSÃO 41 (2026-08-12): remediação P0/P1/P2 do playtest real `done`.** A
> spec [remediacao-playtest-real-100t](specs/SPEC-120-remediacao-playtest-real-100t.md)
> entregou prazo absoluto no watchdog (resultado tardio após suspensão é
> rejeitado), perfil `normal` restrito à visão pública, pedido diegético de tarefa
> com funil observável até quest, cooldown/retirada prudente e voz de loot em
> segunda pessoa. Summary/JSONL agora medem `% combate`, pedidos e conversões;
> campanhas normais longas alertam combate >35% e ≥2 pedidos sem quest.
>
> Smoke mock `20260812-232004-255178`: 50/50, quatro rotas, quatro quests (três
> concluídas), zero erro/error; warning útil de 46% combate por encontros
> sistêmicos. Smoke real `20260812-232052-855221`: 16/16, `mock=false`, 54
> sucessos de rede incluindo startup, zero falha/violação, uma quest, 31,2%
> combate, loot sem terceira pessoa, US$ 0,014. Ruff verde; gate:
> **1446 passed, 1 skipped, 14 deselected**. MiniMax/Qwen e demais fallbacks
> operacionais ficaram fora do escopo por decisão do usuário.

> **🧪 SESSÃO 40 (2026-08-12): campanha LLM real pós-remediações — diagnóstico.**
> Run `20260812-215427-501557`: perfil `normal`, **100/100 turnos**, `mock=false`,
> 282 tentativas LLM/281 de rede/273 sucessos, zero exceções, zero abortos e
> US$ 0,085208. Cobriu as quatro rotas, sete locais, sete conflitos, duas escolhas
> de progressão e três restores de morte. As seis correções anteriores se
> mantiveram: fuga chegou a `escapou`, rollback não reteve mortes, grounding
> regional correto, resumo 1.191/1.200 chars e feedback mecânico coerente.
>
> O run ficou `failed` por **1 SLO error**: turno 64 levou 2.256 s; a DeepSeek só
> devolveu timeout após 2.230 s e o watchdog em thread não impôs os 120 s durante
> uma lacuna de heartbeat/suspensão. Novos achados: MiniMax sem saldo (402), Qwen
> com chave inválida (401), perfil copia instrução interna `Descreva...` do beat,
> zero quests em 100 turnos apesar de muitos ganchos, combate ocupou 45% da sessão
> e loot alterna para terceira pessoa. Diagnóstico completo:
> [playtest-longrun-real-2026-08-12-v2](docs/playtest-longrun-real-2026-08-12-v2.md).
> Nenhuma correção/spec nova foi criada nesta sessão; recomendações aguardam
> priorização. Gate offline: **1436 passed, 1 skipped, 14 deselected**.

> **✅ SESSÃO 39 (2026-08-12): seis remediações do playtest normal `done`.** Os
> achados da sessão 38 viraram specs e código: fuga retoma `combat.chase` e mede
> `flee_progress`; checkpoint restaura JSON + árvore FAISS inteira (raiz/NPC,
> disco e harness); troca regional sempre replana e o planner grava localização
> canônica; `narrative_summary` tem teto de **1.200 chars**, memória é fracionada
> e não há bypass do budget; recompensas são confirmadas pelo delta Python e
> moeda livre não passa como item.
>
> O harness ganhou o 14º perfil, `normal`: mistura viagem, exploração, NPC,
> missão, loot/comércio, descanso e combate prudente, além de resolver escolhas
> pendentes via `progression.apply_choice`. Novos invariantes cobrem resumo,
> grounding, feedback, fuga; latência real gera warning >45 s e error >90 s.
> Telemetria agrega diversidade, escolhas e SLO.
>
> Aceite mock `20260812-172231-913670`: **50/50**, quatro rotas, três escolhas,
> zero erro/violação. Smoke DeepSeek `20260812-172526-505951`: **5/5**, quatro
> rotas, zero erro/violação, p50 19,6 s/p95 37,3 s, 24 requests, US$ 0,00686;
> fallback Groq absorveu 1 structured inválido do planner. Ruff verde. Gate:
> `uv run pytest` = **1436 passed, 1 skipped, 14 deselected**. Specs funcionais:
> **99 `done`**. Relatório atualizado em
> [playtest-jogador-normal-2026-08-12](docs/playtest-jogador-normal-2026-08-12.md).
>
> **Próxima:** nenhuma spec funcional aprovada ficou pendente; escolher o
> próximo item de produto/ROADMAP.

> **🧪 SESSÃO 38 (2026-08-12): playtest longo de jogador normal — diagnóstico.**
> Foram simulados **440 turnos** (2×200 MockLLM + 40 DeepSeek real) com políticas
> mistas de exploração, conversa, missão, viagem, loot, descanso, combate e fuga.
> Os três runs terminaram com **0 exceções e 0 violações formais**. Run real
> `20260812-162429-546407`: 9 locais, 1 quest ativa, 1 queda, 114 requests
> DeepSeek, US$ 0,03192, p50 15,3 s e p95 38,7 s.
>
> A estabilidade escondeu **3 defeitos prioritários**: (P0) fuga contra
> perseguidor reinicia a trilha a cada turno e pode ser impossível; (P0)
> continuar do checkpoint restaura o save, mas deixa no FAISS a morte descartada
> como fato `CONFIRMADO`; (P1) plano de Nova Arcádia sobreviveu à viagem para
> Brekmar e transplantou “Anel de Lama”/“Sino Rachado”, contaminando resumo e
> memória. Também foram confirmados resumo sem teto (11.029 caracteres em 40
> turnos, com bypass do budget), feedback que nega ouro já concedido e cauda de
> latência de até 94 s.
>
> Relatório e reproduções: [playtest-jogador-normal-2026-08-12](docs/playtest-jogador-normal-2026-08-12.md).
> **Naquele momento nenhuma regra foi alterada:** os achados aguardavam specs na ordem
> fuga → checkpoint/memória → grounding regional → resumo/budget → feedback →
> perfil misto/invariantes. Gate final: `uv run pytest` = **1409 passed,
> 1 skipped, 14 deselected** (4 warnings de dependências).

> **✅ SESSÃO 37 (2026-08-12): Fase 8A `done` — arte dentro do jogo.** O
> handoff correto `VALORIA_GAME_ART_HANDOFF` foi validado (68/68 PNGs e SHA do
> ZIP `8f1574b...09bd1`). `scripts/import_visual_assets.py` gerou um catálogo de
> **45 assets** e **90 WebPs** (16,6 MB): 6 raças, 5 classes, 22 locais exatos e
> 12 NPCs. Os 35 locais do mapa ficam cobertos por 22 exatos + 13 fallbacks
> regionais explícitos; Vrethis foi preservado como fonte não mapeada, e NPCs
> secretos nunca entram no catálogo público.
>
> Backend: `services/visual_catalog.py` e `entity_identity.py` resolvem cena,
> aliases e primeira aparição somente por estado/ID; save schema **v6** persiste
> vistos + ledger visual de 64 ações. POST e SSE têm paridade e retry UUID devolve
> a mesma cue. Frontend: capas em raça/classe, cena do local e retrato no mesmo
> bloco narrativo, com alt/dimensões, fallback, reduced motion e passe a 390 px.
> O lint de conteúdo agora verifica identidade, visibilidade, hash, bytes, teto e
> cobertura visual. Operação/proveniência: `docs/ARTE_VISUAL.md`.
>
> Smoke real/browser: game `8afdb0d3-427b-442d-a2b1-2a514f2a3267`
> (`simulated=false`, removido após o teste), Nova Arcádia e Grum renderizados;
> retry `59b1ee90-1ded-4135-a257-d515aff3877c` manteve turno 2, mensagem e cue.
> Desktop/390 px sem erro de página. Gates: lint **0 erros/0 avisos**, Ruff verde,
> build Vite verde; `uv run pytest` = **1409 passed, 1 skipped, 14 deselected**
> (4 warnings de dependências). Specs funcionais: **93 `done`**.

> **✅ SESSÃO 36 (2026-08-12): Fase 8A especificada e `approved`.** A
> spec [fase-8-ancoras-visuais-contextuais](specs/SPEC-094-fase-8-ancoras-visuais-contextuais.md)
> mapeia a integração das imagens no onboarding (raça/classe), na cena do local e
> na primeira aparição de NPC. A decisão visual é determinística por ID canônico,
> visibilidade e estado persistido; não haverá escolha de arquivo pela LLM nem
> parsing de nomes dentro da prosa.
>
> O desenho inclui catálogo público, importador Python/Pillow com SHA-256 e WebP,
> save v6 com ledger visual idempotente, paridade POST/SSE, fallback honesto,
> acessibilidade e orçamento de bytes. A Fase 8 anterior foi dividida: 8A usa
> arte curada já existente; geração runtime de item/monstro/NPC vira 8B futura.
>
> **Auditoria do pacote:** 5/5 capas de classe, 33 locais e 8/15 NPCs aprovados
> têm PNG recuperável com hash exato. Das seis raças jogáveis, só Humano e Cinzéu
> têm ao menos uma variante recuperável com SHA aprovado; Elfo, Anão da Fuligem,
> Vrel e Osshari usarão um PNG compartilhado `AGUARDANDO ARTE`, com composição no
> tom artístico do projeto e texto aplicado por Python/Pillow. A spec proíbe
> associação automática por nome/semelhança; uma arte real verificada substitui
> o placeholder apenas pelo catálogo.
> A fonte do placeholder foi gerada e preservada em
> `assets/visual/system/aguardando-arte-source.png` (1024×1536; SHA-256
> `6e22252aa9b9610cee908358e6978028e84ff7401ecf79d55c79f1605132e51f`).
>
> **Estado:** somente documentação/spec; implementação ainda não iniciada. Gate desta
> sessão: `uv run pytest` = **1398 passed, 1 skipped, 14 deselected** (4 warnings
> de dependências). Specs funcionais: **92 `done` + 1 `approved`**.

> **✅ SESSÃO 35 (2026-08-11): hardening de persistência/SSE `done`.** A spec
> [hardening-persistencia-sse-idempotencia](specs/SPEC-086-hardening-persistencia-sse-idempotencia.md)

> corrigiu o vazamento de `*.checkpoint.json` na listagem/latest, exclusão agora
> remove save+checkpoint+memória e JSON usa temp+`fsync`+`os.replace`. Falha de
> escrita deixou de responder sucesso falso na API/CLI.
>
> Turnos do mesmo `game_id` são serializados no processo e `action_id` UUID fica
> num ledger limitado no save. Stream e fallback POST compartilham o ID; o worker
> SSE é dono do lock/save e conclui mesmo se o consumidor desconectar. Telemetria
> da API não cobra mais `build_error`/`circuit_open`; criação rejeita classe/raça/
> região fora dos catálogos. O lint Ruff encontrou e corrigiu `CLASSES` sem import
> no wizard CLI.
>
> A suíte inteira agora isola `saves/` e `data/saves_memory/` em `tmp_path`.
> Os **1.390 arquivos históricos** (431 checkpoints; majoritariamente fixtures
> `Streamer`) foram preservados porque podem estar misturados a campanhas reais;
> não houve limpeza destrutiva. CI ganhou Ruff, lint de conteúdo e build web.
>
> **Gate:** `uv run pytest` = **1398 passed, 1 skipped, 14 deselected**; Ruff
> verde; conteúdo **0 erros/0 avisos**; Vite **454 módulos**; `git diff --check`
> verde. Specs funcionais: **92 `done`**, nenhuma aprovada pendente.

> **✅ SESSÃO 34 (2026-08-03): laboratório de combate no frontend `done`.** A
> spec [modo-simulacao-combate](specs/SPEC-090-modo-simulacao-combate.md) criou entrada
> “Simular combate” nas telas iniciais, configuração de classe/nível/inimigo/
> quantidade e arena direta usando a UI tática e o motor determinístico reais.
>
> O modo `combat_simulation` persiste por UUID, mas pula campaign planning,
> preparação/narração LLM, RAG, archivist, loot, XP e checkpoints. Cartas,
> Reações, Ruptura, manobras, Vitalidade, Ferimentos, zonas e IA inimiga seguem
> os mesmos serviços de produção; texto livre degrada para ataque básico sem
> provider. Saves de laboratório recebem selo próprio e podem ser reiniciados.
>
> **Smoke browser:** `9f3193bd-2f42-4ad9-a24d-a76661846960`; desktop confirmou
> Sangromante nível 3 × 2 Cães de Rebite com Carta+Reação e estado mecânico;
> mobile 390×844 confirmou carrossel, topbar e Guardar. Console/page errors = 0;
> axe WCAG A/AA = 0 violações. **Gate:** `uv run pytest` = **1388 passed,
> 1 skipped, 14 deselected**; build Vite = 454 módulos; lint = 0/0.

> **✅ SESSÃO 33 (2026-08-03): revisão geral encontrou e corrigiu 2 bugs do
> hardening de playtest.** A spec
> [fix-playtest-liveness-telemetria-circuito](specs/SPEC-080-fix-playtest-liveness-telemetria-circuito.md)
> foi criada `approved`, executada testes-first e fechada `done`.
>
> **Bug 1 — falso stale:** recovery usava apenas `created_at`; uma matriz real
> legítima de 8,4 h podia virar `aborted` quando outra run começasse após 6 h.
> Manifesto v3 agora grava owner (`pid`, `host`) + `heartbeat_at`; CLI toca o
> heartbeat por turno. PID vivo no host atual sempre vence idade; host remoto
> com heartbeat recente também. PID morto/heartbeat antigo e v2 legado ainda
> são recuperados como `aborted/stale_running_manifest`.
>
> **Bug 2 — telemetria falsa:** `circuit_open` era contado como request/custo e
> falha embora pulasse a rede. Agora normaliza `network_attempted=false`, não
> entra em provider/custo/network/failure e fica auditável em `llm_skipped`
> (inclusive startup).
>
> **Smoke:** `20260803-130102-999691` = 2/2 offline, manifesto schema v3 com
> owner/heartbeat e `complete`. **Gate:** `uv run pytest` = **1382 passed,
> 1 skipped, 14 deselected**; compileall e `git diff --check` verdes.
> Nenhuma spec funcional aprovada ficou pendente.

> **✅ SESSÃO 32 (2026-08-03): remediações dos relatos de gameplay `done`.**
> Três specs novas foram aprovadas e executadas em ordem:
> [polish-prosa-v2](specs/SPEC-091-polish-prosa-v2.md),
> [hardening-playtest-watchdog](specs/SPEC-088-hardening-playtest-watchdog.md) e
> [smoke-dirigido-recrutamento-comercio](specs/SPEC-092-smoke-dirigido-recrutamento-comercio.md).
>
> **Prosa:** a fronteira Python remove `Contexto do local`, `[ECOS DO MUNDO]`
> e imperativos ecoados; repetição literal recebe transição neutra determinística
> sem nova request. O smoke também encontrou ouro fantasma: o parágrafo monetário
> rejeitado agora é removido mesmo com `15` no schema e “quinze” na prosa, e a
> correção visível deixou de usar `[SISTEMA]` (a auditoria permanece em
> `narrative_rejections`). Invariante nova: `narrative.meta_leak` (`error`).
>
> **Harness real:** `--turn-timeout` cobre startup e turno; timeout aborta a
> campanha e fecha manifesto `aborted`. Runs `running` antigas viram `aborted`
> após 6 h; a órfã `20260803-014405-602783` foi recuperada com
> `stale_running_manifest`. Falha permanente de provider abre circuit breaker
> até a próxima campanha e registra outcome `circuit_open`.
>
> **Smokes reais:** prosa `20260803-114646-799077` = 3/3, zero marcador/erro/
> violação, p95 16,4 s, US$ 0,0039; recrutamento `20260803-114339-651827` =
> Brunna Ponte-Alta na party; comércio `20260803-114423-833666` = Poção de Cura
> Menor e ouro 200→140. Os dois cenários têm oráculos `error` e rodam via
> `--scenario recrutamento|comercio`, sem aumentar `--all`.
>
> **Gate:** `uv run pytest` = **1377 passed, 1 skipped, 14 deselected**.
> Nenhuma spec funcional aprovada ficou pendente.

> **✅ SESSÃO 31 (2026-08-02): volume do Mundo Vivo `done`; épico v2 fechado.**
> A spec
> [conflito-17-volume-conteudo-mundo-vivo](specs/SPEC-078-conflito-17-volume-conteudo-mundo-vivo.md)
> elevou o acervo para **153 Cartas de jogador + 40 inimigas**, o bestiário para
> **124 criaturas** (40 novas) e o elenco para **36 NPCs novos** (3 por cada um
> dos 12 hubs). As 15 subclasses têm 5–6 Cartas próprias e Superior; toda região
> tem ≥6 criaturas com Lacaio + Elite/Chefe. Guardas anti-reskin e relatório de
> cobertura agora fazem parte do lint.
>
> **Dados/RAG:** 36 documentos curados com papel/facção/gancho, entidades e
> arestas `located_in`; Codex Jina reindexado (2.239 chunks), consulta de NPC novo
> confirmada. Lint = **0 erros/0 avisos**. Relatório:
> [`docs/content-coverage-2026-08-02.md`](docs/content-coverage-2026-08-02.md).
>
> **Smoke real:** run `20260803-025211-710980` = 3/3 turnos, 4 locais/3 regiões,
> `mock=false`, 0 erro/violação, 18 requests Groq (16 sucessos), US$ 0,010528.
> Smoke dirigido confirmou `mon_guardiao_basalto` com Cartas regionais e Brunna
> Ponte-Alta na rota NPC. **Gate:** `uv run pytest` = **1358 passed, 1 skipped,
> 14 deselected**.
>
> **Próxima:** nenhuma spec funcional aprovada ficou pendente; escolher o próximo
> item de produto/ROADMAP antes de abrir uma nova spec.

> **✅ SESSÃO 30 (2026-08-02): frontend tático de Cartas `done`.** A spec
> [conflito-16-frontend-combate-cartas](specs/SPEC-077-conflito-16-frontend-combate-cartas.md)
> entregou contrato API e UI React para mão preparada, custo/frequência/Ruptura,
> escolha de Reação, zonas, Vitalidade/Ferimentos, conhecimento progressivo do
> inimigo, perseguição e morte rica. O level-up legado também foi alinhado às
> escolhas v4 de Carta/evolução/Virtude.
>
> **Smoke browser + real:** build Vite (453 módulos), desktop e mobile 390 px,
> console limpo e axe WCAG 2 A/AA com 0 violações. Campanha real
> `1d9ba1e6-1483-49d5-af01-890c21dea5a1`, `simulated=false`: criação → Carta +
> Reação → Ferimentos → morte/loot → narrativa e, em novo encontro, fuga com
> trilha `escapou`. DeepSeek primário e fallback Groq funcionaram sem erro de
> turno. **Gate:** `uv run pytest` = **1353 passed, 1 skipped, 14 deselected**.
>
> **Próxima spec por ordem:**
> [conflito-17-volume-conteudo-mundo-vivo](specs/SPEC-078-conflito-17-volume-conteudo-mundo-vivo.md).

> **✅ SESSÃO 29 (2026-08-02): proveniência de memória `done`.** A spec
> [hardening-memoria-proveniencia](specs/SPEC-085-hardening-memoria-proveniencia.md)
> fechou o ledger narrativo: `canonical_event | player_observation | npc_claim |
> inference | legacy_unverified`, confiança derivada pelo motor, fonte/turno,
> metadata no FAISS, retry idempotente e contexto rotulado. Inferência da LLM é
> sempre `speculative`; fala de NPC é `reported`; apenas fonte mecânica aplicável
> pode ser `confirmed`. Assinatura `hidden/secret` sem `secret_revealed` aceito
> para o mesmo ID não entra no contexto.
>
> **Smoke real aceito (3×30):** `secret_rusher`
> `20260802-184026-492723`, `diplomatico` `20260802-234057-869414` e `npc_only`
> `20260802-235207-031964` = 90/90 turnos, `mock=false`, zero erro/violação
> `error`, 226/227 invokes, US$ 0,06370 e 0 falhas RAG. O `npc_only` provou 15
> writes `npc_claim`; nenhum rumor/inferência virou `confirmed`.
>
> **Achado operacional:** uma run real ficou presa no fallback SMART porque
> Anthropic/Gemini não recebiam `LLM_TIMEOUT_SECONDS`. Os builders agora usam
> `timeout`/`request_timeout`, com regressão dedicada; a repetição fechou 30/30.
> **Gate:** `uv run pytest` = **1349 passed, 1 skipped, 14 deselected**.
>
> **Próxima spec por ordem:**
> [conflito-16-frontend-combate-cartas](specs/SPEC-077-conflito-16-frontend-combate-cartas.md),
> seguida de `conflito-17-volume-conteudo-mundo-vivo`.

> **✅ SESSÃO 28 (2026-08-02): `conflito-13` E REMEDIAÇÕES `done`.** Os achados
> do smoke real `20260725-101933` viraram sete specs, foram corrigidos e aceitos
> numa nova matriz real de 13 perfis × 30 turnos. Relatório completo:
> [`docs/smoke-correcoes-conflito-v4-2026-08-02.md`](docs/smoke-correcoes-conflito-v4-2026-08-02.md).
>
> **Evidência aceita:** matriz offline `20260802-154317-705789` = 390/390,
> zero erro/violação. Matriz real composta = 390/390, `mock=false`, 0 erro, 0
> violação `error`, 1.119 sucessos de rede, 13 falhas LLM observáveis,
> US$ 0,328488, 148 operações RAG/0 falha, 10 inícios/13 finais de conflito,
> 4 reações, 28 táticas, 7 mortes e zero divergência HP↔Vitalidade. Sanity
> pós-fix de telemetria `20260802-154332-961894` = 5/5 e 24/24 sucessos de rede.
>
> **Correções centrais:** Vitalidade/terminal canônicos; decisão atômica no
> playtest; manifesto e telemetria fail-loud; structured output/sentinelas/path
> Unicode endurecidos; entradas mecânicas fechadas em Python; lifecycle do
> `ConflictSummary`; reações inimigas efetivas. Durante a validação também foram
> corrigidos o deadlock de sobrevivente inconsciente, o cliente Jina sem timeout
> e o vazamento de `resolved_action` antiga no JSONL.
>
> **Pendências naquele fechamento:** a proveniência de memória (fechada na
> sessão 29), smoke dirigido de recrutamento/transação comercial e 44 warnings
> de abertura repetida. `conflito-16` e `conflito-17` ainda eram `draft`.
>
> **Verificação final desta sessão:** `uv run pytest` = **1296 passed, 1 skipped,
> 14 deselected**; lint de conteúdo = **0 erro/0 aviso**; build TypeScript/Vite
> verde (449 módulos). Revisão React também confirmou Vitalidade/estado terminal
> canônicos e eliminou colisão de keys nas listas de party/inimigos.

## Histórico — handoff da sessão 25 (antes do cutover)

> **⚠️ RETOMANDO DA SESSÃO 24?** EM CURSO o **épico Migração do Sistema de
> Conflitos (Valoria v2)** — 16 specs `conflito-01..16` em `specs/` (fonte
> funcional em `docs/valoria_conflict_migration_v2/`). Substitui o combate atual
> por um jogo tático de cartas 100% determinístico; **cutover atômico** só na
> `conflito-13` (jogo fica injogável no meio, por design). **`conflito-01`
> (fundação de dados) `done`** + **`conflito-02` (Cartas) `done`**.
> **01:** 5 Virtudes (0-5), Vitalidade/Ferimentos por Corpo, nível máx 10,
> migração v3→v4 (saves antigos ARQUIVADOS — corte deliberado), `attributes`/
> mana/stamina fora do jogador via ponte `actor_mods` (+30 testes).
> **02:** sistema de Cartas (`services/cards.py` — Acervo/Preparação/frequência/
> Ruptura/evolução A-B; `data/cards/` exemplos; criação 6+4+2; level-up escolhe
> Carta), convive com `known_abilities` até o cutover (+25 testes).
> **03:** cena posicional (`services/conflict_scene.py` — zonas não-grid, eixos
> Distância/Postura/Ocultação, Engajamento separado, objetos com catálogo FECHADO
> de efeitos, cena congelada + reforços), aditivo puro em `combat["scene"]` (+13).
> **04:** motor de resolução (`services/conflict_resolution.py` — iniciativa por
> lado, ataque 2d10+Virtude vs Esquiva, Crítico/Super por dupla, Vantagem 3d10,
> testes gerais Ímpeto+Presságio, Ruptura=Vantagem). ADITIVO — fiação no nó
> (Pré/Ação/Pós) + remoção do motor antigo vão no **cutover conflito-13** (+19).
> **05:** dano→Ferimentos (`services/conflict_damage.py` — ordem fixa R8: dano×
> crítico → res/vuln/imunidade → Proteção → Integridade → Vitalidade/Gravidade →
> Ferimentos; 3 físicos + 6 sobrenaturais; armadura/escudo/Comprometida; Ferimento
> localizado agrava/escala; sacrifício Sangromante; recuperação). Aditivo (+26).
> **06:** Reações/movimento tático (`services/reactions.py` — janela sobre ação
> declarada, cadeia com limite de 1 reação COMUM por personagem, reação-responde-
> reação, ordem alvo→aliados→Agilidade, Ataque de Oportunidade UNIVERSAL fora do
> limite; `conflict_scene.py` ganhou orçamento por turno Pré/Ação/Pós + manobras
> Engajar/Desengajar/Guardar/Esconder-se/Procurar/alertar + ocultação RELATIVA por
> observador `hidden_from`/`approx_from`). Aditivo — fiação no cutover 13 (+18).
> **07:** morte rica (`services/death_flow.py` — último Crítico dispara Última
> Ação com Vantagem extrema/ignora recursos ausentes/pode Ruptura → Estado
> Terminal → morte imediata sem aliado ou até 2 estabilizações (kit/Médico/poção
> = auto metade Vitalidade); Cicatriz OBRIGATÓRIA via LLM+guard `FallbackLLM`;
> consciência pós-conflito por Ferimento; categorias de inimigo Lacaio/Padrão/
> Elite/Chefe/Nomeado; golpe não-letal; rendição 100% determinística por perfil;
> encerramento sem interpretação livre). Aditivo — cutover 13 reconcilia com
> `checkpoints.py`/`death_pending` (+20).
> **08:** perfil tático (`services/tactical_profile.py` — `TacticalProfile` de
> prioridades ORDENADAS; `pick_action` decide IA de inimigo por precedência sem
> LLM em combate; `validate_companion_order` valida ordem contra Restrição/
> resistência Flexível/Resistente/Absoluta/Autônoma sem crashar; controle de party
> por perda-de-comando explícita; `generate_tactical_profile` 1× via LLM+guard,
> cacheado) + info revelada (`services/bestiary_knowledge.py` — painel só-público
> R7, revelação de Cartas/Resistências que PERSISTE no bestiário via overlay
> `data/runtime/`, exclusiva de variante fica oculta). Aditivo — remoção de
> `get_behavior` e fiação no cutover 13 (+16).
> **09:** fuga/perseguição (`services/chase.py` — trilha Pressionado→Afastado→
> Quase Livre→Escapou derivada da distância; perseguidor só segue se o
> `TacticalProfile` mandar; condutor sempre o protagonista + Virtude por
> abordagem; Teste de Sorte 1d10 por companheiro com cap ±1; abandono separa o
> NPC e resolve o destino por SIMULAÇÃO determinística por seed ∈ {fuga/captura/
> rendição/esconderijo/combate/morte/reencontro}; sacrifício voluntário só com
> traço; ataques em perseguição). Aditivo — substitui `combat_flee_*` no cutover
> 13 (+17).
> **10:** Abismo em conflito (`services/abyss_events.py` — eventos preparados pela
> LLM ANTES do combate com `base_na_cena` OBRIGATÓRIA; carregamento 100%
> determinístico/seed em combate por Cargas+gatilho+prioridade+usos, ZERO LLM;
> proibições rígidas R4/R6 — não desfaz sucesso, não controla mente, não cria/
> agrava Ferimento direto, catálogo fechado da conflito-03; assinatura visual fixa
> + gasto de Carga reportado). Camada COMPLEMENTAR aos gatilhos de classe (não
> substitui). Aditivo — consumidor de `abyss_charge` no cutover 13 (+13).
> **11:** preparação de encontro (`services/encounter_preparation.py` +
> `data/potency_by_level.json` — Nível do Encontro ABSOLUTO em Python puro, sem
> nível de party; potência por categoria Fraco/Moderado/Forte/Devastador × nível;
> `validate_preparation` exige catálogo fechado + base narrativa por objeto + base
> na cena por evento do Abismo; seleção de criatura por região; `prepare_encounter`
> via LLM+guard → `fallback_safe_scene` determinística quando a cadeia falha;
> `build_npc_combat_sheet` dá ficha de combate completa ao NPC). Aditivo — mudança
> de GRAFO no cutover 13 (+11).
> **12:** loot + resumo canônico (`services/conflict_summary.py` —
> `ConflictSummary` de 18 campos montado do estado FINAL já resolvido SEM LLM
> [mortos/rendidos/fugitivos/capturados/inconscientes/Ferimentos/Cicatrizes/
> Cartas+resistências reveladas/objetos usados/fatos de relação/loot/party];
> `loot_context` passa o Nível do Encontro como `danger` com `economy.roll_loot`
> INTACTA; `validate_narrative_consistency` proíbe reverter morte→fuga/soltar
> capturado/restaurar cenário sem novo acontecimento; `summary_facts` p/ archivist).
> Aditivo — consumo em loot/archivist no cutover 13 (+7).
> **13 (CUTOVER, `in-progress`):** decisão R6 fechada = **Opção A** (death_flow
> resolve Última Ação/Estado Terminal/estabilização no conflito; só a morte REAL
> aciona `death_pending`/tela Continuar-Aceitar da sessão 23; sobreviver aplica
> Cicatriz e o combate segue). **Etapa 1 (auditoria MORRE/SOBREVIVE de
> `combat_mechanics.py` + `tests/test_cutover_audit.py`) `done`.** **Etapa 2
> (`services/conflict_turn.py` — `TurnDeclaration` + orquestrador de turno Pré/Ação/
> Pós compondo os motores 01-12, 100% determinístico) `done` (+7).** FALTA o "big
> bang": reescrever `combat_node`+`main.py` pro motor novo, remover as funções
> d20+AC, reescrever o playtest (declaração estruturada) e auditar ~199 testes de
> combate — leva a suíte ao vermelho, exige passo dedicado (não iniciado).
> **DECISÃO DO USUÁRIO (2026-07-23):** o "big bang" do cutover fica ADIADO. Antes
> dele, fazer **conflito-14 (autoria de Cartas)** e **conflito-15 (autoria de
> bestiário/perfis)** — rodam em paralelo, NÃO quebram nada, mantêm o repo verde.
> **14 `done`** (80 Cartas autorais na escala nova, 16/classe: 7 tronco + 3×3
> subclasse; catálogo fechado `CARD_EFFECT_KINDS`; Ruptura+Evolução A/B nas 15
> centrais; parity `dano_base/custo ∈ [1.5,4.0]`; `docs/CARTAS.md`;
> `scripts/gen_cards_v4.py`; +16 testes). **15 `done`** (84 criaturas migradas pro
> schema v4 via `scripts/migrate_bestiary_v4.py` — categoria canônica, Virtudes
> 0-5, Vitalidade×Corpo, resistências tipadas, 10 arquétipos táticos ricos com
> regra de fuga/rendição, 18 Cartas de inimigo com assinatura OCULTA por criatura;
> ADITIVO — motor antigo intacto; +17 testes). Lint da Fase 7 estendido
> (`validate_cards`/`validate_bestiary`). **PRÓXIMA: o cutover `conflito-13`**
> (big bang) agora que 14/15 fecharam. **Suíte 1273 verde.** Última atualização:
> 2026-07-23 (sessão 25).
> Ordem completa no ROADMAP § Migração. Histórico anterior: abaixo e `CHANGELOG.md`.

---

## TL;DR — sessão 23 (2026-07-20): letalidade v2 + specs do run + parity de classes

Run de validação `20260720-093014` fechado (17 campanhas reais, 0 erro, $1.74).
Achado dominante nos logs: **combate/explorador morrem por AUSÊNCIA de recovery**
(HP travado ~40% por 5–7 turnos; viagem não cura; descanso em zona de perigo vira
combate) — não por dano alto. Quester sobrevive só evitando luta.

**Decisões do usuário → entregas:**
1. **[letalidade-early-game-v2](specs/SPEC-056-letalidade-early-game-v2.md) Etapa 2
   IMPLEMENTADA** (`approved`) — 4 alavancas determinísticas: (1) **descanso/viagem
   recuperam** — descanso de early-game (nível ≤3) em zona não-apex de perigo ≤3
   NÃO sorteia encontro (`world_utils.recovery_rest_safe` + fio no storyteller) +
   cooldown de encontro +2 turnos no early-game; (2) **+1 poção inicial** por classe
   (Médico=3), via gerador; (3) **+HP base** nas frágeis (Arcanista 22→26,
   Sangromante/Corruptor/Médico →30, Devoto →40), via gerador; (4) **+dano de
   early-game** runtime (`combat_mechanics.early_game_damage_bonus`: +2 nível 1–2,
   +1 nível 3, 0 do 4+, só o herói). **+9 testes.**
2. **[fix-explorador-loop-navegacao](specs/SPEC-061-fix-explorador-loop-navegacao.md)
   `done`** (B) — perfil Explorador oscilava cidade↔interior quando tudo já foi
   visitado (interior tem 1 saída) → bounce + `loot-exploracao` nunca dispara. Fix
   = memória anti-backtrack + fronteira primeiro (`_recent`, reset por campanha no
   runner). **+6 testes.**
3. **[checkpoints-morte](specs/SPEC-060-checkpoints-morte.md) `in-progress`** (C) — 8
   decisões RESOLVIDAS (§2.1; memorial = escolha voluntária na tela de morte,
   nunca imposto; sem permadeath; restore do início se sem checkpoint). **FUNDAÇÃO
   + VERTICAL DE MORTE `done`:** `services/checkpoints.py` + `persistence`
   refatorado (fonte única + `save/load/has_checkpoint`); combat→`death_pending`
   (sem Saque; `_narrate_fall` + evento `player_downed`); `main.py` gate;
   `runner` auto-restore + `deaths_log`; `api` (`maybe_write` + checkpoint inicial
   + `POST /game/death` + 409 com queda pendente + `GameResponse.death_pending`);
   `DeathModal` no frontend (`npm run build` verde) + prompt CLI. **HIGIENE `done`:**
   "O Saque" + `pos-saque` INTEGRALMENTE aposentados (`apply_downed`/`death_outcome`/
   `_death_template`/`_narrate_downed`/beat de recuperação/`downed_grace`/invariantes
   `check_downed`+`check_downed_recovery`/campo `downed_grace_until_day` removidos;
   `test_pos_saque` deletado). **Spec C `done`.** **Smoke real** (run
   `20260721-042146`, combate 25t, DeepSeek $0.051, 0 erro): morreu 4× (1ª t13),
   **auto-restaurou e seguiu até t25** (antes abortava no t13) — vertical validado
   no LLM real. Bug pego pelo smoke: `vitals.dead_no_game_over` falso-disparava na
   morte (hp=0 vem com `death_pending`) → corrigido + teste.
4. **Fix D — `secret_leak` ignora segredo já conhecido pelo jogador**
   (`services/secret_signatures.revealed_corpus` inclui `narrative_summary` +
   `player.known_secrets`): a Velha Magda revelara o pacto ao player; a narração
   repetindo virava falso-positivo. **+4 testes.**

5. **Parity ESTÁTICA das habilidades `done`** (pedido do usuário: "nenhuma muito
   mais forte que a outra") —
   [balanceamento-classes-pos-playtest §10](specs/SPEC-049-balanceamento-classes-pos-playtest.md).
   Insight: parity MECÂNICA é número → medida direto do catálogo
   (`player_abilities.json`), **sem playtest**. Métrica = dano-efetivo/custo-real
   (`custo = Entropia + self_harm/2`; conta DoT/efeito). Achado: roster **bem
   balanceado por papel** (tank Devoto baixo por design; DoT do Corruptor
   compensa dado com DoT; Médico baixo é lacuna de medição — cura não pontua, NÃO
   buffar). Falso-alarme corrigido: "Toque Cru" parecia 7.0/E mas tem
   `self_harm:4` (glass-cannon). **Único outlier real: `fervor_ritual`** (2d6 vs
   2d8 dos irmãos) → fix `2d6→2d8` no gerador. **+2 testes-guarda de parity**
   (`test_arvores_classes`: banda 1.5–4.0 dano/E p/ dano puro; trava do fix).

**Suíte: 1001 → 1039 → 1019 → 1020 offline verdes** (+38 do trabalho novo, −20 da
higiene do Saque, +1 do fix do smoke; 1 skip). `npm run build` verde. Baseline de letalidade mudou (A) → run
`20260720-093014` STALE p/ decidir NÚMEROS de Entropia/Carga; tuning dos 8 knobs
pede rodada real DEDICADA pós-A (parity de dano já resolvida).

**Próximos passos:** (1) rodada real pós-A p/ o tuning dos knobs de Entropia/Carga
(o baseline mudou); (2) medir se as 4 alavancas de A reduziram a letalidade de
fato (comparar `first_death_turn` com `20260720-093014`).

---

## TL;DR — sessão 22 (2026-07-20): 5 specs do playtest longo IMPLEMENTADAS

Análise do run `20260719-160014` + decisões do usuário → 5 specs `approved` e
implementadas (TDD, suíte **970 → 1001 offline verdes**, +31; 1 skip):

1. **[playtest-agente-curioso-entropia](specs/SPEC-059-playtest-agente-curioso-entropia.md)
   `done` — o BLOQUEADOR do balanceamento.** Raiz achada: os perfis de combate
   só mandavam "Ataco X" → as 101 habilidades NUNCA rodavam → Entropia travava em
   16/16 (flooding=100%/starvation=0% era artefato disso + do snapshot). Fix em 2
   frentes: (a) **agente curioso** — `Agressivo`/`Combate`/`Recrutador` leem
   `known_abilities` e nomeiam habilidade de Entropia ("Uso {nome} em {alvo}"),
   curam com HP baixo, descansam em zona segura; (b) **telemetria de GASTO** —
   `combat_mechanics.resolve_player_action` carimba `_last_entropy_spent`/
   `_last_ability_id`/`_last_used_active` (transitório); runner lê gated por rota;
   `summary.entropy` reescrito (spent_total, %ativa, starvation/flooding
   redefinidos por gasto, não snapshot); report ganhou `%ativa`/`gasto/turno`.
2. **[npc-in-scene-viagem](specs/SPEC-058-npc-in-scene-viagem.md) `done`** — os 43
   `recycled_npc`: fuga de combate aplicava viagem SEM `reset_scene` → flag zumbi.
   Fix: [combat.py:726](agents/combat.py) reseta cena na fuga; invariante mede
   vazamento real (`npcs_for_context`), não flag crua; party excluída.
3. **[aliados-em-combate](specs/SPEC-055-aliados-em-combate.md) `done`** — motor de combate
   já incluía party ativa; faltava ponte NPC-amigo-em-cena → combatente. Novo
   `party.scene_allies` (in_scene + rel≥6 + fação não-hostil → aliado TRANSITÓRIO,
   não vira party permanente, dano reflete no NPC); `combat_party` na iniciativa/
   resolução; `encounter_budget` conta transitórios; invariante `combat.phantom_ally`.
   **Perfil `recrutador` novo** (faz o máx. de amigos).
4. **[loot-exploracao](specs/SPEC-057-loot-exploracao.md) `done`** — explorar recompensa
   (escada de raridade): novo `services/exploration.py` reusa `economy.roll_loot`
   (raridade por perigo, claim de único); achado na 1ª visita (fog of war) NUNCA
   único; **baú curado** (`treasure` no world_map: `pm_profundezas`,
   `ae_ruinas_submersas`) one-shot via `world.looted_locations`, pode ter único.
   Fiado no storyteller (nota no prompt + claim no pending).
5. **[letalidade-early-game-v2](specs/SPEC-056-letalidade-early-game-v2.md) `approved`
   (medir→decidir)** — sem código novo: instrumentação já existe; a Etapa 1
   (baseline com agente corrigido) É o playtest desta sessão; tuning decidido
   DEPOIS com o usuário.

**Em curso:** playtest real de 17 campanhas (15 balanceamento das 5 classes ×
{combate,explorador,quester} + 1 comerciante + 1 recrutador) p/ validar as
mudanças e gerar os novos achados. **Backlog `comerciante`** endereçado no run.

---

## TL;DR — Em que pé está

**Sessão 2026-07-19 (20): REVISÃO DE CÓDIGO/ROADMAP — 3 specs novas, 2 `done` +
1 instrumentada.** Auditoria do épico de classes (sessão 19) achou bugs que o
mock/testes de unidade escondiam:

1. **[fiacao-regras-orfas-classes](specs/SPEC-050-fiacao-regras-orfas-classes.md) `done`
   — 3 mecânicas de classe estavam MORTAS** (função pronta + testada em unidade,
   NUNCA chamada pelo fluxo de jogo): (a) **taunt do Devoto** — `pick_target`
   ignorava a condição `control:"taunt"`; o tank não tankava. (b)
   **Transformação do Corruptor** — `apply_transformacao` sem callsite; única
   consequência de Carga que não rodava. (c) **Purga da Carga do Médico** —
   efeito `reduce_ally_abyss` descartado em silêncio por `_split_typed_effects`.
   Fix + **R4 anti-órfão**: `combat_mechanics.HANDLED_KINDS` + teste que varre
   os JSONs gerados e exige handler p/ todo kind/trigger (teria pego os 3).
   **+11 testes.**
2. **[isolar-cache-runtime](specs/SPEC-051-isolar-cache-runtime.md) `done` — bug
   recorrente das sessões 15/16.** `bestiary.json`/`npc_database.json`/
   `custom_artifacts.json` eram gravados em runtime nos arquivos versionados
   (exigia `git checkout` manual; run real gravou "Afogado" e derrubou testes).
   Agora: overlay gitignored `data/runtime/` (`gamedata.runtime_cache_path`,
   env resolvida no call), curadoria READ-ONLY (vence no merge); suíte→tmp,
   playtest→`saves_playtest/runtime/`. `git rm --cached data/npc_database.json`.
   **+8 testes; suíte e playtest deixam `data/` limpo.**
3. **[balanceamento-classes-pos-playtest](specs/SPEC-049-balanceamento-classes-pos-playtest.md)
   `in-progress` — instrumentação `done`, tuning adiado.** Harness ganhou
   `--class`, telemetria de Entropia/Carga por turno e seção **Classes** no
   report. Baseline mock (40 campanhas, 0 erro) + real parcial capturados. Os 8
   knobs `[BALANCEAR]` PERMANECEM marcados: mock não mede economia de Entropia
   (só ataque básico → flooding 100% é artefato) e o real ficou fino (combate
   morre nível 1). Tuning exige rodada real dedicada e mais longa. **+8 testes.**
4. **Tarefas menores do backlog:** **traits lote 2** (40→**80** em
   `data/traits.json`, regiões subrepresentadas reforçadas); **curadoria da Rede
   Carmesim** (pendência da Fase 7) — decisão: nome/monitoramento = conhecimento
   comum do norte, iminência/natureza = `hidden`; suavizado o over-share real em
   `factions.txt` ("O segredo:" num doc `public`), migrate + **reindex do lore**
   (2203 chunks, vazamento sumiu) + assinatura de iminência em
   `secret_signatures`. `validate.yml` verde no último push (confirmado via `gh`).
5. **Suíte: 918 → 945 offline verdes** (+27) + 1 skip.

**Trabalho concorrente (enquanto rodava o playtest longo de balanceamento) —
auditoria de mecânica-morta + 2 decisões do usuário:**
6. **Auditoria "dado declara capacidade, motor não fia" além das classes** (o
   padrão dos 3 bugs). Scan estático de funções públicas sem callsite de
   produção: 9 candidatas → maioria falso-positivo (Pydantic validator, cache-
   clearers do runner) ou stub trivial. **1 achado real:** o **gating narrativo
   por classe** (`agents/class_themes.py`) estava MORTO desde a deleção do Ruler
   (faxina 2026-07-03), mas CLAUDE.md ainda o anunciava.
7. **Gating de classe APOSENTADO** (decisão do usuário: "mecânica é toda Python
   agora, gate por LLM não faz falta"). Removido `agents/class_themes.py` + 2
   testes + stub `archive_narrative`; `class_themes.json` fica só p/ flavor do
   prólogo; CLAUDE.md corrigido.
8. **[weather-global-vivo](specs/SPEC-052-weather-global-vivo.md) `in-progress`** (o
   usuário QUIS: "acho bem legal ter e que impactasse no jogo"). A máquina de
   clima GLOBAL estava 90% pronta (tick+efeitos fiados) mas nada iniciava
   eventos. Novo trigger **determinístico** em `advance_weather`
   (`maybe_start_global_weather`: chance base 6% + 3%/perigo, sem canal LLM);
   Tempestade de Éter / Noite Sem Estrelas agora varrem Valoria e impactam
   combate/percepção/descanso/viagem. **+7 testes.** Suíte **945 → 950**.
9. **[itens-vivos-e-luz](specs/SPEC-053-itens-vivos-e-luz.md) `in-progress`** (3 perguntas
   do usuário: itens aplicam habilidades? passivas? tem luz? — **as 3 eram
   NÃO**). Fiado: **passiva de item** entra em `player_passives` (era ignorada);
   **item ativo ofensivo** (`use_item_in_combat` com alvo — stun/sono/dot/medo no
   inimigo com save); **sistema de LUZ** (`light_level`: noite/masmorra sem luz
   penaliza percepção −3 e acerto −1; tocha/lanterna anula; cidade iluminada).
   **+22 itens** ancorados na lore (4 luz, 9 passivas, 6 ativos, 3 suportes);
   bloco `<AMBIENTE_DE_LUZ>` no narrador + chip de luz no HUD. Bug colateral:
   `corda` tinha passiva-string (filtrado). **+20 testes. Suíte 950 → 970.**
   Falta só o smoke real (adiado — Jina em uso pelo playtest).

---

## TL;DR — sessão 19 (épico de classes)

**Sessão 2026-07-19 (19): SISTEMA DE CLASSES REFATORADO — 5 POSTURAS DIANTE DO
ABISMO** ([spec `done`](specs/SPEC-048-refatoracao-sistema-classes.md); mecânica em
[docs/CLASSES.md](docs/CLASSES.md), narrativa em
[docs/CLASSES_NARRATIVA.md](docs/CLASSES_NARRATIVA.md)):
1. **10 classes → 5 classes × 3 subclasses.** Devoto do Abismo (tank/ama) ·
   Sangromante (dano/negocia) · Corruptor (DoT/trabalha junto) · Arcanista
   Cinzento (dist/manipula) · Médico de Campo (suporte/nega). Cada classe é uma
   postura filosófica diante do Abismo.
2. **Dois recursos novos.** **Entropia** = pool único (substitui mana+stamina do
   jogador; recompõe INTEGRAL no descanso). **Carga do Abismo** = longo prazo (não
   cai no descanso; patamares leve/moderado/severo). `state.py`/creator/api/runner
   backfillam `entropy`/`max_entropy`/`abyss_charge`.
3. **Gatilhos + regras + consequências por classe (100% Python, `combat_mechanics`).**
   Gatilhos: on_damage_taken/on_self_harm/on_decay_nearby/on_channel/on_ally_suffer
   (`apply_entropy_trigger`, respeita `per_turn_cap`/round). Regras especiais:
   taunt-escala-com-Entropia / blood_leak / boiler (caldeira estoura) / reduce_ally_abyss
   (só Médico). Consequências: Insônia (descanso rende menos) / Cicatriz (−max_hp
   permanente) / Transformação (debuff por domínio) / Dependência (custo dobra) /
   Recidiva (oculta até colapso). Fiados no loop de combate + `apply_rest`.
4. **Árvore MÍNIMA jogável (41 habilidades).** `scripts/gen_classes_v2.py` gera
   `classes.json`+`player_abilities.json` **alinhados ao schema do motor** (effects
   `kind`, cura via `damage_type:"Cura"`). A árvore RICA (~100 hab, passivas) é a
   spec #2 `arvores-habilidade-classes` (Fable).
5. **Migração `_migrate_v2_to_v3` (schema v3):** classe antiga → nova + backfill de
   Entropia + descarte de habilidades mortas. Saves antigos ficam órfãos (arquivar).
6. **HUD:** barra Entropia (roxo-abissal) + chip Carga do Abismo por patamar; Médico
   oculta o número (Recidiva). `npm run build` verde.
7. **Testes:** 881 → **898 offline verdes** (+34 `test_classes_refactor`; ~40 testes
   de classes antigas migrados/reescritos: passivas extintas viraram gatilhos de
   Entropia). Playtest runner default = Devoto do Abismo (sobrevive no mock).
8. **Smoke real 4/4** (DeepSeek): Sangromante criado no LLM real com Entropia
   mapeada (16/16) + mana/stamina 0; auto-dano somou Entropia+Carga; descanso
   recompôs Entropia sem baixar Carga; Devoto apanhou → on_damage_taken.

**Segunda spec do épico — [arvores-habilidade-classes](specs/SPEC-047-arvores-habilidade-classes.md)
`done` (mesma sessão, autoria em Fable):**
9. **Árvore RICA: 101 habilidades** (41 ativas + **35 passivas + 25 utilitárias**),
   geradas por `scripts/gen_classes_v2.py`. Cada tronco: 2 ativas + 2 utilitárias
   do doc-fonte + 1 passiva; cada uma das 15 subclasses: 2 ativas encadeadas +
   2 passivas + 1 utilitária.
10. **Passiva na árvore funciona:** `ability_kind` no schema;
    `combat_mechanics.player_passives` (classe + aprendidas) em TODOS os callsites
    do jogador; 5 triggers novos: `entropy_max_bonus` (no `apply_choice`) ·
    `entropy_on_kill` · `entropy_cost_reduction` (piso 1) · `charge_discount`
    (piso 0) · `carga_embrace` (patamar de Carga vira bônus). Inimigo NÃO ganha
    passiva de árvore (teste dedicado).
11. **Utilitária = capacidade fora de combate:** `out_of_combat`
    {label/scope/prompt_hint}; gate determinístico + bloco `<CAPACIDADES_DO_HEROI>`
    no prompt do storyteller (`utility_context_block`). Passiva/utilitária FORA
    dos chips e do catálogo do parser de combate; HUD com selo ✦/⚒ (ficha +
    LevelUpModal).
12. **Suíte:** 898 → **918 offline verdes** (+20 `test_arvores_classes`).
    **Smoke real 4/4:** elegibilidade lvl2 com utilitárias/passivas; `juros_do_corpo`
    somou "+1 passiva" no dano; `cofre_de_sangue` subiu max_entropy 16→19; o
    storyteller REAL narrou "Avaliação de Preço" citando a capacidade injetada;
    `reduce_ally_abyss` purgou Carga de aliado.

**🏁 O ÉPICO DO SISTEMA DE CLASSES ESTÁ 100% `done` (as 2 specs).** Próximo
natural: balanceamento dos números `[BALANCEAR]` após playtest; tiers 5+
(nível 9–20) de fast-follow.

---

## TL;DR — sessões anteriores

**Sessão 2026-07-17 (18): 10 SPECS APROVADAS + ORDEM + EMBEDDINGS MULTI-PROVIDER** —
1. **Todas as specs pendentes viraram `approved` com ordem de dev cravada no
   header de cada uma.** Duas fases:
   - **Sistema de classes (2 specs, ordem #1→#2):**
     [refatoracao-sistema-classes](specs/SPEC-048-refatoracao-sistema-classes.md) →
     [arvores-habilidade-classes](specs/SPEC-047-arvores-habilidade-classes.md)
     (a 2ª depende do motor de Entropia/Carga da 1ª).
   - **Playtest longo (8 specs, ordem #1→#8):**
     [embeddings-provider](specs/SPEC-039-embeddings-provider.md) →
     [playtest-stop-gameover](specs/SPEC-042-playtest-stop-gameover.md) →
     [combate-lifecycle](specs/SPEC-038-combate-lifecycle.md) →
     [pos-saque-recuperacao](specs/SPEC-044-pos-saque-recuperacao.md) →
     [npc-fallback-sem-alvo](specs/SPEC-041-npc-fallback-sem-alvo.md) →
     [beats-visibilidade-ptbr](specs/SPEC-037-beats-visibilidade-ptbr.md) →
     [encontros-dedupe](specs/SPEC-040-encontros-dedupe.md) →
     [polish-prosa](specs/SPEC-043-polish-prosa.md).
2. **[embeddings-provider](specs/SPEC-039-embeddings-provider.md) `done`:** `rag.py`
   ganhou cadeia multi-provider
   `EMBEDDING_ROUTES = [jina, openai, ollama, gemini]` (Gemini é o ÚLTIMO
   fallback). Cada índice FAISS grava `embeddings_meta.json` e fica **PINADO**
   ao provider que o gerou (nunca mistura vetores); provider indisponível →
   índice DESATIVADO com warning (nunca crash). `RPG_EMBEDDINGS=<p>` força.
   `get_embeddings_for(p)` abre índice pinado; write deriva provider de
   `_resolve_provider()` (puro, sem global vazável). `codex_loader.ingest_codex`
   grava meta também. **+12 `test_embeddings_provider`**; seam de
   `test_npc_memory` migrado p/ `_EMBEDDING_BUILDERS` (pin não passa mais por
   `get_embeddings`). `.env.example` ganhou `JINA_API_KEY`/`RPG_EMBEDDINGS`.
   **RAG VIVO:** re-index real com Jina executado (lore 2203 chunks + regras,
   meta jina); smoke §6 3/3 (queries PT-BR sem 429 + memória de sessão).
   ⚠️ Free tier Jina = **100k tokens/min**: re-index do Codex esgota o minuto,
   regras precisaram de ~70s de espera (não é erro).
3. **[playtest-stop-gameover](specs/SPEC-042-playtest-stop-gameover.md) `done`:**
   harness agora PARA no `game_over` (turno da morte é o
   último; `aborted_reason="player_death (turno N)"`) — antes rodava 140/300
   turnos mortos poluindo p50/rotas/custo. **Rota fiel:** `_run_turn` captura a
   decisão do `dm_router` via streaming multi-modo (`updates`+`values`), não o
   `next` final (combate/loot sobrescreviam); combate ativo na entrada = rota
   `combat_agent`. Fallback pro `invoke` quando o grafo não tem `.stream`
   (wrappers de teste). `telemetry` ganhou `death_location`/`death_cause`;
   `report` ganhou seção **Mortes** (turno/local/causa). **+8
   `test_playtest_harness`.** Validação mock: 12 perfis × 50t = **552 turnos
   vivos, 0 rota vazia** (antes o perfil `combate` registrava só storyteller).
   ⚠️ Fix colateral: run mock agora desliga embeddings reais
   (`_offline_embeddings`) — com Jina viva no `.env`, o archivist batia na API a
   cada turno (rede/rate limit → timeout). **Smoke §6 real 3/3:** combate morreu
   no t14, run PAROU (aborted player_death), routes com combat_agent=6, p50=14s
   sem turnos de 1ms, $0.04 (deepseek 49 + groq 5).
4. **[combate-lifecycle](specs/SPEC-038-combate-lifecycle.md) `done`:**
   o router ganhou **gate determinístico de combate**
   (`_combat_gate`): com `combat.active`, viagem NÃO teleporta — vira tentativa
   de fuga (R1: flag `combat_flee_attempt`+destino; sucesso aplica
   `apply_travel` no mesmo turno, enredado falha e inimigos agem); npc/loot são
   bloqueados → `combat_agent` (R2); combate órfão (idle_turns) expira em 3
   turnos (R3). `combat_node` zera `idle_turns` e SEMPRE zera `active` no fim
   (R5 — antes fuga com inimigo vivo deixava flag zumbi). Nova invariante
   `combat.zombie` (R4, `error`, idle≥5). `state.py` documenta `combat.idle_turns`
   + `combat_flee_attempt`/`combat_flee_destination`. **+10
   `test_combat_lifecycle`.** Harness mock 12×50t: **492 turnos, 0 combat.zombie,
   maior sequência de combate ativo = 4t (era 59)**. Smoke §6 real: "Viajo para
   X" em combate → narrou FUGA e viajou só após escapar (nunca teleporte),
   combate limpo.
5. **[pos-saque-recuperacao](specs/SPEC-044-pos-saque-recuperacao.md) `done`:** o Saque
   deixa de ser espiral de morte. `apply_downed` agora deixa **1 poção de cura**
   (R1) + marca `downed_recente` (R4) + **carência de 1 dia** no local seguro
   (`downed_grace_until_day`, R2: storyteller não sorteia encontro em zona segura
   durante a carência; ir pro perigo cancela). `campaign_manager` prefixa um
   **beat de recuperação determinístico** ("Recupere forças em {local}", R3);
   `apply_rest` remove a marca; storyteller ganha cláusula de prompt de
   recuperação (R4). Invariante `downed.no_recovery_path` (R5, warning).
   **+13 `test_pos_saque`.** Harness 3 seeds: 0 violações, sobrevivência muito
   além do baseline 1-4t. Smoke real: poção+beat+narração ✓.
6. **[npc-fallback-sem-alvo](specs/SPEC-041-npc-fallback-sem-alvo.md) `done`:** rota NPC
   sem alvo não devolve mais "Ninguém responde." (o quester perdia 7+ turnos).
   `npc_layers.npcs_in_scene` resolve alvo (NPC em cena → aliado presente, R1);
   sem candidato → `npc_actor` delega ao `storyteller` (nova aresta condicional
   em main.py) que narra a ausência + gancho (R2); pergunta sobre missão injeta
   o beat atual no contexto do NPC (R4, `_mission_hint_block`). **+9
   `test_npc_fallback`.** Mock quester/npc_only 50t: **0 "Ninguém responde"**.
   Smoke real: aliado cita objetivo; sozinho → gancho rico.
7. **[beats-visibilidade-ptbr](specs/SPEC-037-beats-visibilidade-ptbr.md) `done`:**
   segredo não vaza mais pelo BEAT + beats sempre pt-BR. Novo módulo
   `services/secret_signatures.py` (R1: assinaturas + rumor público + heurística
   de idioma) consumido pelo invariante E pelo planner. `campaign_manager`
   sanitiza beat/climax/arc_title (R2), re-tenta 1x se detectar inglês e mantém
   plano anterior na 2ª falha (R4), com instrução anti-segredo no prompt (R3).
   Invariante `knowledge.secret_leak` agora checa o texto dos BEATS (R5).
   **Achado F resolvido:** o "beat em inglês" era o **fallback template** (estava
   em inglês) — traduzido. **+11 `test_beats_visibilidade`.** Smoke real: 3
   planos pt-BR sem segredo.
8. **[encontros-dedupe](specs/SPEC-040-encontros-dedupe.md) `done`:** NPC gerado não
   vira mais carrossel de template ('Sobrevivente moribundo' em 3 locais em 6
   turnos). `npc_layers.npcs_for_context` filtra o contexto do narrador por
   vínculo de local (`home_location_id`) + in_scene/party (R1) — usado pelo
   storyteller e pelo `context_builder`; `_with_new_npc` carimba
   `created_turn`/`last_seen_turn`. R3: storyteller não repete o mesmo template
   de encontro 2× no mesmo local (`world.last_encounter_id`). Invariante
   `narrative.recycled_npc` (R4). **+7 `test_encontros_dedupe`.** Smoke real: NPC
   gerado preso ao local (não vaza p/ outro).
9. **[polish-prosa](specs/SPEC-043-polish-prosa.md) `done`:** três tiques de prosa do
   playtest resolvidos. Novo `services/prose_guard.py` (aberturas, repeats,
   openings_clause, log). Storyteller e combat recebem as 2 últimas aberturas e
   pedem variação (R1); morte/downed exigem 2ª pessoa, proibindo "o herói/
   viajante/aventureiro" (R2); storyteller fecha com 2-3 opções "— …" + "Ou
   outra ação" fora de combate (R3); telemetria `rpg.prose` de repetição (R4);
   invariante `narrative.repeated_opening` (R5, filtrada em mock no runner).
   **+8 `test_prose_guard`.** Smoke real: 4 aberturas distintas + menu; downed
   em 2ª pessoa.
10. **Pós-review (2026-07-18):** (a) **archivist fix** — `important_facts` como
    dict não perde mais memória (`field_validator`; +5 `test_archivist_facts`;
    smoke real 3 turnos ok); (b) **NPC relocável** — re-introdução em outro local
    relocaliza o `home_location_id` (viajar junto/mandado em missão); seguro pois
    R1 já bloqueia reuso passivo; (c) **sistema de classes Etapa 1/8 `done`** —
    recurso Entropia (+5 `test_classes_refactor`).
11. **Suíte:** 862 → **881 offline verdes** + 1 skip.

**🏁 AS 8 SPECS DO PLAYTEST LONGO ESTÃO `done`** + archivist fix + NPC relocável.

**Próximo — ÉPICO DO SISTEMA DE CLASSES (retomar em sessão limpa):** leia
**[docs/HANDOFF-sistema-classes.md](docs/HANDOFF-sistema-classes.md)** — Etapa
1/8 done; Etapa 2 pronta em `scripts/gen_classes_v2.py` (aplicar derruba 41
testes em 10 arquivos, inventariados no handoff); faltam etapas 2-8. Depois:
[arvores-habilidade-classes](specs/SPEC-047-arvores-habilidade-classes.md) (árvore rica,
autoria em Fable).

---

**Sessão 2026-07-17 (17): CRIAÇÃO DE PERSONAGEM IMERSIVA ENTREGUE** —
1. **[onboarding-valoria](specs/SPEC-046-onboarding-valoria.md) `done`:** criação virou
   wizard de 5 passos com lore curado — `data/onboarding.json` (intro de
   Valoria + 12 regiões + 10 classes + 6 raças; cards de região com
   `name`/`bonus` espelhados de `origins.json`, teste anti-drift),
   `GET /data/onboarding`, `CreateScreen.tsx` reescrito (cards clicáveis,
   stepper com navegação livre, fallback pro form clássico se o endpoint
   faltar). Smoke de UI: **15/15 checks** via Playwright (estado preservado ao
   voltar, "Pular introdução", mobile 390px sem overflow). Autoria dos cards:
   `docs/AUTORIA.md` § Fluxo D.
2. **[inicio-personalizado](specs/SPEC-045-inicio-personalizado.md) `done`:**
   `POST /game/prologue` (1 chamada SMART + guard → template determinístico,
   nunca 500; entra no rate-limit) gera prólogo confirmável;
   `/game/new` com `scenario` (re-validado na borda — 422 p/ excedente) semeia
   `campaign_plan` pessoal que sobrevive ao 1º invoke, capítulo 1 da crônica
   com o arco pessoal, NPCs `in_scene`/`known_by_player` (alvo válido da rota
   NPC no turno 1) e a `HumanMessage` de abertura com o brief da cena. Passo 6
   do wizard: loading temático + **Refinar** + **Começar a jornada**. Sem
   scenario = fluxo clássico byte a byte (CLI intacta).
3. **Achado do smoke real (padrão p/ TODO schema novo de structured output):**
   `max_length` duro no schema voltado ao LLM derruba TODOS os candidatos por
   validação — DeepSeek escreveu `climax` > 300, Anthropic `attitude` livre
   ("ambígua e transacional"), Groq 400 `tool_use_failed` — e o guard caía
   sempre no template. Fix: schema do LLM com tamanho só na *description*;
   truncagem/normalização determinística em `_normalize`; limites ESTRITOS só
   na borda da API (`StartScenarioIn`). **MockLLM não pega isso** (fixture
   sempre válida) — validar schema novo com chave real segue obrigatório.
4. **Suíte:** 769 → **792 offline verdes** (+10 `test_onboarding`, +13
   `test_prologue`; 1 skip pré-existente). `npm run build` verde. Smoke real
   §6 no DeepSeek executado (~$0.02): arco "O Nome Manchado" com 2 NPCs,
   abertura NA cena do brief, NPC semeado responde no turno 1.

**Sessão 2026-07-14→16 (16): DEEPSEEK PRIMÁRIO + PLAYTEST LONGO + 8 SPECS** —
1. **Roteamento:** DeepSeek agora é o candidato Nº 1 em **TODOS os tiers**
   (`llm_setup.ROUTES`; decisão do usuário pós-playtest — prosa muito melhor,
   ~$0.001/turno). Groq free segue de fallback vivo em todos.
2. **Playtest longo REAL** (explorador/combate/quester × 100 turnos, ~$0.25,
   zero erro de turno): análise completa em
   **[docs/playtest-longrun-2026-07-14.md](docs/playtest-longrun-2026-07-14.md)**.
   Destaque: quester 7/7 quests, level 5, arco da Thrace excelente — mas 1
   local em 100 turnos. 7 defeitos priorizados (harness sem stop no game_over,
   espiral pós-Saque, combate zumbi 59 turnos, segredo vazando via beat,
   "Ninguém responde." com aliado em cena, beat em inglês, NPC reciclado).
3. **Todos os achados viraram specs `draft` (aguardando aprovação):**
   [playtest-stop-gameover](specs/SPEC-042-playtest-stop-gameover.md) ·
   [combate-lifecycle](specs/SPEC-038-combate-lifecycle.md) ·
   [pos-saque-recuperacao](specs/SPEC-044-pos-saque-recuperacao.md) ·
   [npc-fallback-sem-alvo](specs/SPEC-041-npc-fallback-sem-alvo.md) ·
   [beats-visibilidade-ptbr](specs/SPEC-037-beats-visibilidade-ptbr.md) ·
   [encontros-dedupe](specs/SPEC-040-encontros-dedupe.md) ·
   [polish-prosa](specs/SPEC-043-polish-prosa.md) ·
   [embeddings-provider](specs/SPEC-039-embeddings-provider.md).
4. **Embeddings:** Google 429 "prepayment credits depleted" desde 2026-07-14 —
   RAG global + memória de sessão MORTOS. Pesquisa feita (DeepSeek NÃO tem
   embeddings): recomendação = **Jina v3** ($0.02/M + 10M tokens grátis,
   PT-BR forte) com opção local Ollama `bge-m3` — spec embeddings-provider.

5. **Criação de personagem imersiva (2026-07-16): 2 specs `approved`** —
   viraram `done` na sessão 17 (ver TL;DR acima).

**Histórico recente** (detalhe SÓ no `CHANGELOG.md`):
- 2026-07-13 (15): ciclo de produto EXECUTADO — balanceamento-early-game
  ("O Saque" + tuning nível 1 + replan por região) · streaming-turno-sse ·
  polish-sessao, todas `done`; 729 → 769 offline verdes
- 2026-07-13 (14): sync de docs + auditoria A1–A8 corrigida (729 verdes) +
  3 specs do ciclo refinadas com o usuário e `approved`
- 2026-07-13 (13): fix-playtest-achados `done` — 6 defeitos do transcrito real +
  fuga do jogador implementada; 715 verdes; perfis 11º/12º (`quester`/`fujao`)
- 2026-07-06/07 (12): **Fase 5 inteira** (harness 12 perfis + invariantes +
  telemetria); suíte `-m llm_playtest` (4 VITAIS × 30t); bugs reais: rota NONE,
  vazamento do Verme (curado), teto de sobrevivência no budget
- 2026-07-06 (11): **roteamento multi-provider** — `RoutedLLM`/`ROUTES`, Groq
  grátis em TODOS os tiers (`function_calling`), telemetria por invoke
- 2026-07-06 (10): Fase 10 local (UUID/migrations/CORS/rate-limit/log) + Fase 11
  (9 contratos LLM reais) + mapa interiores + NPCs 3 camadas
- 2026-07-05 (9/8): Fase 7 (autoria+validação) · Fase 6 (conteúdo sistêmico)
- 2026-07-04/05 (7): Fase 4 (gameplay core, 7 specs)

**⚠️ Saves pré-2.5b:** carregam sem crash (migrations), mas locais/fações antigos
não existem mais no mapa — sessões antigas ficam narrativamente órfãs. Arquivar.

---

## Como rodar (ambiente deste Windows)

`python` global é 3.14 (WindowsApps) — **errado** (projeto exige 3.13). Use sempre `uv`.

`uv` **não está no PATH** — fica em `%APPDATA%\Python\Python314\Scripts`. Em PowerShell:

```powershell
$env:Path = "$env:APPDATA\Python\Python314\Scripts;$env:Path"
uv sync                              # cria .venv com Python 3.13
copy .env.example .env               # cole GOOGLE_API_KEY no .env (NUNCA na .env.example)
uv run pytest                        # 1564 passed, 16 skipped, 14 deselected (LLM/infra real opt-in)
uv run pytest -m llm_contract -v -s  # 9 contratos contra o Gemini REAL (~13 req; requer chave)
uv run pytest -m llm_playtest -v -s  # Fase 5: 4 perfis VITAIS × 30 turnos no LLM REAL (RPG_PLAYTEST_TURNS encurta)
uv run python game_engine.py         # CLI
uv run uvicorn api:app --port 8000   # API + frontend web (http://localhost:8000)
uv run python -m playtest run --all --turns 50   # Fase 5: harness offline (MockLLM, 14 perfis)
uv run python -m playtest report <run_id>        # Fase 5: relatório agregado
uv run python -m playtest transcript <run_id>    # transcrito ação→narração (julgar prompt)
uv run python rag.py                 # reindexar lore (data/codex/) + regras (data/rules.txt)
uv run python scripts/migrate_lore_nova.py  # regerar Codex de lore_nova/ (SOBRESCREVE curadoria)
bash scripts/smoke_api.sh [porta]    # smoke da API (health, map, /game/new, /game/action)
```

**Frontend:** `cd web && npm install && npm run build` → gera `web/dist` (servido na
raiz). Dev: `npm run dev` (:5173 com proxy para :8000).

**LLM providers:** default = `ROUTES` multi-provider com fallback —
**DeepSeek `deepseek-v4-flash` é o primário em TODOS os tiers**. O alias
`deepseek-chat` foi substituído após HTTP 400 no smoke de 2026-07-24; V4 roda
com thinking desabilitado e timeout OpenAI-compat configurável por
`LLM_TIMEOUT_SECONDS` (default 90s). No run 13×30: ~$0,00080/turno estimado;
Groq free é o fallback vivo. `LLM_PROVIDER=gemini` força
só-Gemini; sem chave nenhuma → MockLLM (jogável sem rede). Contas: minimax 402,
qwen 401 — OPCIONAL resolver (assumem quando tiverem saldo/key; não é bug).
Ver `.env.example`.

**Quota:** Gemini free = 20 req/dia por modelo; Groq free = 100k tokens/dia (esgota
numa sessão real longa — espalhar por dias ou tier pago). `get_llm()` é fail-fast
(`max_retries=0`). **MockLLM esconde bugs de mapeamento** — validar nós novos com
chave real.

---

## O que funciona

- Criação de personagem (CLI + `/game/new`) — resiliente sem chave
- Loop completo: `campaign_manager → dm_router → (storyteller|combat|npc|loot) → archivist → save`
- **Combate:** IA identifica/narra; Python resolve tudo (`combat_mechanics.py`) —
  iniciativa, DoT/condições, custos, cooldowns, saves + perfis de comportamento (2.5b)
  + fuga do jogador real (fix-playtest)
- **Mundo:** mapa de Valoria 35 nós (30 + 5 interiores), relógio, viagem (fog of war),
  descanso, gating por classe; raças com traits mecânicos (2.5b); clima mecânico (6.5)
- **Fase 2/2.5:** fações com objetivos/reputação/ascensão, memória de NPC, Codex
  Valoria + grafo (558 entidades) + `event_log`/`world_projection` + RAG com
  visibilidade (`secret`/`hidden` não vaza)
- **Fase 3 (completa):** crônica por capítulos, codex do jogador + bestiário
  progressivo, quest log, visualização de estado (controladores/ameaças/reputação)
- **Fase 4 (completa):** progressão/XP/level-up (111 habilidades, 20 ramos), buffs
  mecânicos, inventário `{id,qty}`+slots, economia determinística, party,
  dificuldade/morte digna (memorial 409)
- **Fase 6 (completa):** economia viva (rotas/escassez), 20 itens únicos (claim
  engine), migração de monstros, encontros sistêmicos, clima com efeito
- **Fase 7 (completa):** lint de conteúdo + CI, curadoria migration-safe
  (`codex_overrides.yaml`), segredos de NPC em docs `hidden`
- **Fase 5 (completa):** playtest agêntico (`playtest/`, 14 perfis), invariantes
  por turno, telemetria JSONL + relatório com custo, `--real` com tetos,
  `transcript` por turno
- **Fase 10 local + Fase 11:** UUID/migrations/CORS/rate-limit/log JSON; 9 contratos
  LLM reais (`-m llm_contract`)
- **Roteamento multi-provider:** 3 tiers, fallback vivo, Groq grátis em todos;
  NPCs 3 camadas com traits
- **Ciclo de produto (sessão 15):** "O Saque" (1ª queda ≠ memorial) + tuning de
  spawn nível 1 + replan por região; streaming SSE do turno (fases + chunks +
  fallback) com custo real no log; tela de saves (listar/continuar/excluir),
  chips mecânicos de combate, export/busca da crônica, onboarding, mobile 390px
- **Criação imersiva (sessão 17):** wizard 5 passos com lore curado de Valoria
  (`data/onboarding.json` + `GET /data/onboarding`) + prólogo confirmável
  (`POST /game/prologue`) que semeia arco pessoal, NPCs da história e cena de
  abertura no `/game/new` — fluxo sem scenario/CLI intactos
- Multi-provider LLM + typewriter no frontend React; memória híbrida (resumo + RAG
  por sessão); persistência JSON por `game_id`

---

## Convenção CRÍTICA de resiliência

`FallbackLLM.with_structured_output(X).invoke()` devolve `AIMessage`, **não** instância
de `X`. Acessar `resultado.campo` **estoura** sem guard.

**Regra obrigatória em todo nó com `with_structured_output`:**
1. `try/except` no acesso aos campos, **ou**
2. `isinstance(resultado, SeuModelo)` antes de usar.

Auditoria 2026-07-13: **12/12 sites de produção blindados** (verificado).

---

## Bugs conhecidos

Bugs históricos: TODOS fechados (4 da sessão 2026-06-26 → Fases 4.3/4.6 e spec
npcs-3-camadas; 6 do transcrito real → fix-playtest-achados; 8 da auditoria de
segurança → sessão 14, tabela completa no `CHANGELOG.md`).

**Corrigido (2026-07-18):** o archivist recebia `MemoryUpdate.important_facts`
como lista de **dicts** (`{fato,type}`/`{role,content}`) e caía no fallback de
texto, PERDENDO os fatos do turno. Fix: `field_validator(mode="before")` coage
dict→string antes da validação (`+5 test_archivist_facts`). Smoke real: 3 turnos,
fatos salvos limpos, zero erro.

**Refino (2026-07-18) — NPC preso ao local (spec encontros-dedupe):** o vínculo
NÃO engaiola o NPC quando faz sentido sair — viajar junto (recrutar→party) ou
ser re-introduzido em outro local pela narrativa/player (relocaliza o
`home_location_id`). Seguro porque o R1 já bloqueia o reuso PASSIVO.

**Pendências abertas (não são bugs de código):**

- Onze specs aguardam a matriz B integral com LLM real e relatório A/B;
  bloqueio atual: saldo DeepSeek (HTTP 402). Lista e retomada no
  [fechamento local](docs/fechamento-local-2026-09-17.md).
- [Playtest longo do perfil comerciante](specs/SPEC-126-playtest-longo-perfil-comerciante.md)
  — **concluído**, inclusive 1×200 real em 20/08; não confundir esse aceite com
  o par comerciante da nova matriz B, ainda pendente.
- [Certificação cloud portátil](specs/SPEC-104-fase-10b-certificacao-cloud-portavel.md)
  — `draft`; Railway/Supabase remoto exigem autorização, contas e orçamento.
- Fase 9 (sprites/som) segue como backlog de produto, ainda sem spec aprovada.
- O import de FAISS via `langchain-community` emite aviso de descontinuação na
  suíte. Avaliar migração do adapter em spec própria; não alterar índices/saves
  nem presumir compatibilidade de um substituto sem testes de recuperação.
- 1 flaky isolado na suíte (sessão 8; 3 runs verdes depois — observar)
- ~~Action `validate.yml`~~ ✅ verde (confirmado via `gh run list`).
- ~~Lote 2 de traits~~ ✅ 80 traits (sessão 20).
- ~~Curadoria Rede Carmesim~~ ✅ resolvida (sessão 20): over-share em
  `factions.txt` suavizado + reindex; nome=público, iminência=`hidden`.
- ~~Cache runtime gravado em `data/`~~ ✅ isolado em `data/runtime/` (sessão 20,
  spec isolar-cache-runtime).
- **Achados do playtest longo (sessão 16)** — 7 defeitos/melhorias priorizados
  em [docs/playtest-longrun-2026-07-14.md](docs/playtest-longrun-2026-07-14.md):
  harness sem stop no game_over · espiral pós-Saque · combate zumbi (59 turnos
  ativo) / viagem durante combate · vazamento de segredo via beat do
  campaign_manager · "Ninguém responde." com aliado em cena · beat em inglês ·
  encontro reciclado. **Todos viraram specs `draft` em 2026-07-16** (ver TL;DR).
- **Embeddings:** ✅ RESOLVIDO (spec embeddings-provider `done`). Jina é o
  primário; índices lore/regras re-indexados com meta jina, RAG vivo. Free tier
  Jina = 100k tokens/min (re-index do Codex esgota o minuto — espaçar). Trocar
  provider = re-rodar `uv run python rag.py`.

Fechadas na sessão 15: confirmação real do Verme ✔ · mortes nível 1 do
`combate`/`agressivo` ✔ (spec balanceamento; nota: 2ª queda DELIBERADA sem cura
segue matando — por design) · replan em toda viagem ✔ · **spec 2.5b virou
`done`** (2026-07-14: smoke real §6 3/3 — raça Cinzéu com traits, viagem com
lore de Skallgard, tático foge com HP baixo + alerta; era a última spec não-done).

## Limitações conhecidas

- **Perfil legacy:** continua serializado por processo e sem login por design.
  Perfis `local/portable/hosted` usam operação/lease/fencing Postgres e owner.
- **Cloud não certificada:** Auth/RLS/OIDC/S3 foram provados localmente, mas rede,
  proxy, limites e restore em Railway/Supabase remoto ainda não foram medidos.
- **Runtime legado local:** `saves/` ainda contém fixtures históricas misturadas a
  campanhas reais; a suíte não cria novas desde a sessão 35, mas limpeza requer
  seleção humana ou ferramenta de migração com preview.
- **Saves antigos** carregam via `schema_version` + `_MIGRATIONS` (v0→v2);
  pré-2.5b ficam narrativamente órfãos — arquivar
- **Free tier não sustenta playtest real longo** — Groq 100k tokens/dia; espalhar
  por dias ou tier pago
- **Latência real:** p50 ≈ 15s, p95 33-46s por turno — o custo do LLM continua,
  mas o streaming SSE (spec `done`) mostra fase em <1s e narra em chunks; a
  espera cega acabou

---

## Checklist ao começar a próxima tarefa

0. Feature/fase nova? **Spec primeiro** — `specs/` (CLAUDE.md § spec-driven)
1. `/qa` verde antes de mexer
2. Nó novo com `with_structured_output`? Guard de fallback (seção CRÍTICA)
3. Mudou schema do player/estado? Atualizar `state.py` + `game_engine.py` + `api.py` + creator
4. Novo agente no grafo? Conectar ao `archivist` no fim (REFERENCE.md)
5. Editou `lore_nova/`, `data/codex/` ou `data/rules.txt`? Rodar `uv run python rag.py`
6. Mecânica nova (números)? Python determinístico, não LLM
7. **Ao finalizar:** `/wrap-up` — suíte completa verde + ESTADO_ATUAL.md + ROADMAP.md + commit
