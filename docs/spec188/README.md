# SPEC-188 — cotação explícita de imagem

Execução Sol High; revisão independente Sol High ainda pendente. Nenhuma imagem
real foi gerada, nenhum provider pago foi chamado e nenhum saldo de provider foi
recarregado. Preços comerciais e ativação permanecem sem configuração.

`POST /game/{game_id}/art/quote` publica uma cotação imutável por owner/campanha
com tipo, modelo, brief/prompt, versão de pricing, teto em `credits_milli` e
validade de no máximo cinco minutos. O cliente pode escolher o tipo e uma
oferta existente; não pode escrever saldo, modelo, preço, owner ou brief.
Reformulação gera outra cotação e exige resolução financeira da geração anterior.

`POST /game/{game_id}/art/confirm` exige `quote_id`, UUID de ação e o booleano
literal `confirmed: true`. A confirmação faz commit de estado, operação de
imagem, reserva da wallet, geração e outbox na mesma transação. Replay da
cotação devolve a mesma geração; cotação ainda não usada expirada ou de outro
owner/epoch falha antes de reservar. Saldo insuficiente retorna 402 e mantém o
estado original, sem job ou provider. O alias `/art/player/confirm` também exige
esse contrato; o contrato antigo sem cotação está encerrado.

A UI apresenta Estilhas com conversão exata de milli, teto, validade,
cancelamento e confirmação explícita em diálogo nativo. O checkbox do wizard
solicita a cotação; somente o botão do diálogo confirma. NPCs e cenas épicas
oferecem cotações por botões e preservam placeholders até uma confirmação.
`art_generations` publica somente IDs/tipo/subject do ledger owner-scoped;
confirmação e replay retornam as listas atualizadas de gerações/ofertas. Assim
NPC/cena podem consultar e apresentar imagem ou hold após reabrir a campanha,
sem carregar prompt/brief/quote privado.

## Persistência e writers

Consulta seletiva ao `project_index/state_ownership.yaml` confirmou que o mapa
curado ainda não enumera wallet/arte. Os owners foram confirmados no source:
`PostgresWallet` escreve ledger/reservas/tickets; `DynamicArtRepository` escreve
gerações/assets/usage; `PostgresTurnCoordinator.commit_game` e `TurnEffects.flush`
publicam a mutação de estado e seus efeitos. `ImageQuoteRepository` compõe os
owners e escreve somente a nova tabela de cotações.

A migration `20261012160000_image_quotes.sql` cria profiles server-side e
cotações imutáveis com triggers, RLS e grants somente ao backend. Não cria SKU,
preço, saldo ou provider ativo. Quotes históricos sobrevivem à exclusão da
campanha; a ligação composta owner/campanha impede reatribuição de geração.
Ofertas também fazem round-trip nos serializers JSON/Postgres existentes.

Configure `RPG_DYNAMIC_ART_ENABLED=1` somente em um ambiente preparado; selecione
um profile imutável de preço por `RPG_IMAGE_PRICE_PROFILE` ou pelos overrides
`RPG_IMAGE_PRICE_PROFILE_PORTRAIT` e `RPG_IMAGE_PRICE_PROFILE_SCENE`. Profiles
contêm model/size, versão de FX/pricing, limite USD com fonte e validade;
ausência, divergência, stale pricing ou expiração fecham o fluxo. Nenhum profile
comercial foi publicado nesta tarefa.

## Prova dos paths até o provider

| Path real | Gate |
|---|---|
| `api._enqueue_turn_art` → `_enqueue_art_generation` | Cria oferta; não toca runtime, wallet ou fila |
| Wizard `generate_portrait` | Solicita quote, depois exibe diálogo; não confirma automaticamente |
| Quote API | Sem chamada de provider e sem reserva |
| Confirm API → `ImageQuoteRepository.confirm` | Owner, epoch, validade, pricing e reserva antes de enqueue atômico |
| `workers.run_worker.build_handlers()['generate_dynamic_art']` | Lê geração canônica do banco, rejeita jobs antigos sem quote e fornece admission |
| `generate_dynamic_art_job` → `ImageGenerator.generate` | Admission obrigatória; verifica job/fence, quote/brief/model/type e reserva; grava um ticket antes da rede |
| `OpenAIImageGenerator.generate` → HTTP `/images/generations` ou `/images/edits` | Único adapter real; somente o worker anterior o chama no source de produção |

O payload da fila não define modelo, brief ou custo. O worker usa a geração
persistida após admission; não reaproveita `begin()` do fluxo antigo. Um ticket
e um settlement no máximo por cotação. Lock order game → job → generation
antecede os writes derivados com FKs, permitindo fencing de restore/delete.

## Falhas e reconciliação

Antes do ticket, erro de configuração/falha certamente não enviada libera a
reserva. Depois do ticket, timeout, crash ou falha DB/blob preserva o hold,
marca `external_result_uncertain` e não repete a geração. Lease abandonado é
visível como `reconcile_required`; ao reclaim, o ticket impede novo dispatch.
Restore libera apenas reservas pré-ticket e preserva os efeitos iniciados para
reconciliação. O frontend exibe saldo retido quando a liquidação é incerta.

Em sucesso, o worker persiste usage antes do processamento/blob e completa
assets + settlement atomicamente. Usage sem custo exato mantém a imagem pronta
e uma reserva `uncertain`; não inventa uma cobrança nem um refund. Custo exato
superior ao teto confirmado debita no máximo o teto e registra
`art_generations.financial_anomaly_milli`; usage técnico completo permanece no
ledger para FinOps.

O adapter deixou de enviar `response_format` em JSON/form: esse parâmetro é
incompatível com GPT Image, que já devolve base64 por default na
[referência oficial](https://developers.openai.com/api/reference/resources/images/methods/generate?site_locale=en).
O custo normal não depende de um `provider_cost_usd` inventado: um card técnico
separado e com hash precifica tokens de texto input, imagem input e imagem
output observados; breakdown ausente/inconsistente continua inexato. A cotação
vincula também a versão desse card; modelo desconhecido, versão divergente ou
card stale fecham antes de emitir ticket.

O snapshot `gpt-image-2-2026-04-21` aparece no
[catálogo oficial](https://developers.openai.com/api/docs/models/gpt-image-2).
O card usa **Standard**, sem desconto de cache no Images API direto. O preço
de output **US$30/M** está explicitamente compartilhado por GPT Image 2/2.5 no
[guia](https://developers.openai.com/api/docs/guides/image-generation). Para
input, registramos a inferência: a
[tabela Batch](https://developers.openai.com/api/docs/pricing) publica
US$2,50/M texto e US$4/M imagem; o desconto de 50% em relação ao síncrono é
[documentado](https://developers.openai.com/api/docs/guides/batch), portanto o
Standard usado é US$5/M texto e US$8/M imagem. O JSON guarda essa derivação e
as fontes; não publica preço comercial. Não copiamos as tarifas Batch para uma
chamada síncrona. Essas tarifas/counters não foram confrontadas com invoice ou
imagem live nesta tarefa.

Reconciliação é tarefa explícita do operador: `PostgresWallet.recover` protege
o fence e nunca libera automaticamente um efeito ticketed. A liberação manual
usa `reconcile_proven_no_charge` com ator e referência de evidência do provider;
usage exato contraditório bloqueia essa liberação. Não há endpoint de refund ou
retry arbitrário do cliente. Informação financeira desconhecida continua retida
até essa prova/política; não foi publicada uma política comercial de refund.

## Evidência executada

- Gate focado final: **78 passed**, incluindo **22 testes Postgres real** com fixtures
  sintéticas em rollback, gerador fake, falhas antes/depois do ticket, uso acima
  do teto, RLS, API → commit → state round-trip, replay, saldo insuficiente,
  fencing/reclaim e restore, NPC/cena em uncertainty e refs após reopen. Inclui
  regressões de shard pricing/wallet e HTTP fake usando o adapter real com usage
  somente de tokens/details: custo **US$0,003900000** rate-card exato, settlement
  de **1 milli**, reserva final zero e replay sem segundo request. Os dois
  testes de JSON/form sem parâmetro incompatível também passaram nesse gate.
- Chromium 390/1440 final da SPEC-188: **7 passed**, com custo, cancelamento, confirmação,
  expiração, 402 com retry explícito/idempotente, hold incerto e Axe; build
  React/TypeScript verde. Inclui NPC/cena com resultado/hold após reload e quote
  atrasado com troca de campanha sem bloquear os botões da próxima sessão.
- Ruff nos módulos afetados: verde.
- Browser completo após os ajustes da revisão: **38 passed, 1 skipped**, 3,4m;
  o skip é um gate visual condicionado a pinned environment.
- Suíte Python completa final com markers padrão:
  **2.118 passed, 90 skipped, 15 deselected**, cinco warnings, **exit 0** em
  **213,41s**. `uv run --no-sync python -m pytest -x --basetemp=<TEMP>/s188-final2
  -o cache_dir=.tmp/spec188_cache --junitxml=.tmp/spec188-final.xml`;
  Python 3.13 do `.venv` principal, `UV_PROJECT_ENVIRONMENT` process-scoped,
  `PYTHONUTF8=1`, `safe.directory` process-scoped para este clone, cache/basetemp
  graváveis. Integrações locais condicionadas ao DSN ficam skipped nessa suíte;
  os **22 Postgres** foram executados no gate focado com DSN localhost e rollback.
- Índice de source regenerado para satisfazer o gate de freshness.

Integrações Postgres não receberam fatos comerciais: versões, profiles e
ajustes da wallet dos testes são sintéticos e revertidos. O smoke browser antigo
`test_audit_browser_local.py` está condicionado ao ambiente e usa o contrato
obsoleto sem quote; não foi executado nem teve expected alterado nesta tarefa.
O novo E2E cobre o contrato atual, e os testes Postgres novos cobrem a transação
real. O helper sintético antigo `tests/fakes/local_portrait.py` precisa migrar
para admission/quote antes de reutilizar aquele smoke opt-in. Essa pendência
não autoriza relaxar o gate de geração paga.

Uma execução completa anterior encontrou o contrato de privacidade das métricas
falhando por nomes de parâmetros como `{game_id}` nos templates exportados.
O middleware do produto passou a normalizar esses nomes para `{id}`; o oracle
existente permaneceu intacto. O gate menor com as rotas de imagem mais métricas
passou 18 testes, e a execução completa seguinte passou.

Uma primeira execução final parou no teste SSE existente após leitura de save
temporário receber `PermissionDenied` no Windows. Os dez testes desse arquivo
passaram isolados, e a repetição completa final passou sem mudança no oracle ou
no loader para contornar o teste. A ocorrência não foi contada como sucesso.
