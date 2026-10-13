# SPEC-188 — revisão independente Sol High

- `decision`: **APPROVED**
- `review_model`: Sol
- `review_effort`: High
- `review_run_id`: `SPEC-188-SOL-20261013-INDEPENDENT-01`
- Contexto independente: `/root/spec188_reviewer_sol`
- Commit revisado: `a82adea3333284003629bd106bf58f1eb1440154`
- Base: `ab081be12ea0782c60ce37fe67fa569c06269c38` (SPEC-187)
- Achados abertos: **nenhum**

## Contratos verificados

A revisão conferiu a spec aprovada, o contrato de modelos, o diff e o source
relevantes, o handoff de implementação e a evidência final. O worktree estava
limpo no congelamento do commit revisado. O reviewer não implementou correções,
não alterou evaluators/datasets e não executou chamadas de provider.

O único caminho de produção até `ImageGenerator.generate` passa por confirmação
explícita, reserva atômica, job canônico, validação de quote/owner/model/brief/epoch
e ticket persistido antes da rede. Os triggers de NPC/cena publicam ofertas e não
reservam saldo nem chamam provider automaticamente. O payload da fila não escolhe
modelo, brief ou preço. Os checks de ownership e as permissões/RLS da migration
foram conferidos no source.

A expiração do quote define a janela de confirmação. Uma confirmação válida
fixa o teto de débito e a reserva; a execução posterior não exige que essa
janela de aceite continue aberta. O dispatch exige o vínculo canônico entre
quote, geração e reserva, além do fence do job e do card técnico autorizado.

Replay, reclaim e resultado externo incerto não autorizam segunda geração.
Falhas pré-ticket liberam a reserva; efeitos iniciados preservam hold e exigem
reconciliação explícita. Restore respeita essa distinção. Settlement verifica
owner, operação, cardinalidade e identidade dos tickets/usage, limita o débito
ao quote e registra excesso para FinOps. Saldo insuficiente impede enqueue e
provider na transação de confirmação.

## Achados resolvidos

1. **P2 — NPC/cena sem resultado ou hold visível.** O cliente descartava IDs de
   gerações de tipos diferentes de player. `GameResponse.art_generations` e as
   respostas de confirmação/replay agora preservam referências públicas; os
   cards consultam status/assets/finance e permanecem disponíveis após reopen.
2. **P2 — busy permanente após invalidar sessão.** O `finally` condicionado à
   sessão deixava `imageBusy=true` quando uma resposta chegava atrasada. Todas
   as invalidações de sessão agora limpam quote, busy e error; respostas antigas
   não publicam estado na campanha nova.
3. **P1 — parâmetro HTTP incompatível com GPT Image.** O adapter enviava
   `response_format=b64_json`, incompatível com o modelo GPT Image pinado.
   O parâmetro foi removido tanto de generations/JSON quanto de edits/form.
4. **P2 — sucesso normal do provider não liquidava.** O rate card anterior não
   precificava tokens de imagem e os testes de settlement injetavam custo USD
   sintético. Um card técnico separado, versionado e vinculado por hash ao
   quote agora precifica o breakdown documentado de texto/imagem. Contadores
   ausentes ou inconsistentes continuam inexatos e mantêm hold.

O adapter e os contadores foram confrontados com a
[referência oficial Images](https://developers.openai.com/api/reference/resources/images/methods/generate).
O card usa preços Standard de texto input, imagem input e imagem output, sem
desconto de cache na Images API direta. A derivação dos inputs a partir do
desconto Batch de 50% está explicitamente registrada; as fontes são a
[página de pricing](https://developers.openai.com/api/docs/pricing), o
[guia de geração](https://developers.openai.com/api/docs/guides/image-generation)
e o [guia Batch](https://developers.openai.com/api/docs/guides/batch).

## Gates finais

- Python completa: **2.118 passed, 90 skipped, 15 deselected**, cinco warnings,
  **exit 0**, 213,41s. O reviewer leu `.tmp/spec188-final.xml` diretamente:
  `errors=0`, `failures=0`, `tests=2208`, `skipped=90`, `time=213.369`.
- Focados: **78 passed**, incluindo **22 testes Postgres real** com fixtures
  sintéticas em rollback. Os casos Postgres são condicionados ao DSN e ficam
  skipped no full default; sua execução verde pertence ao gate focado.
- HTTP fake usando adapter/worker reais até Postgres: usage somente de tokens
  documentados produziu custo exato de card **US$0,003900000**, settlement de
  **1 milli**, reserva final zero e replay sem segundo request.
- Chromium SPEC-188: **7 passed**, cobrindo custo, cancelamento, confirmação,
  expiração, 402/retry explícito, NPC/cena após reload e troca de campanha com
  resposta de quote atrasada.
- Chromium completo: **38 passed, 1 skipped**, 3,4m; o skip é um gate visual
  condicionado ao ambiente pinado.
- Build React/TypeScript, Ruff e freshness do índice: **verdes**.

Os resultados de execução dos gates focados/browser/build/Ruff/freshness foram
fornecidos pelo executor/coordenador e conferidos com o handoff e a documentação.
O full final foi verificado adicionalmente pelo XML. Uma falha temporária de
PermissionDenied no teste SSE existente não reproduziu em dez testes isolados
nem no full final; não foi suprimida ou contada como sucesso.

## Limites da aprovação

- Nenhuma imagem paga, chamada LLM live, recarga de provider ou ativação
  comercial foi executada nesta revisão/validação da SPEC-188.
- O custo do card técnico não foi validado por invoice ou geração live. A
  inferência de preços de input está documentada; o snapshot é pinado e o
  dispatch rejeita card desconhecido, divergente ou stale antes do ticket.
- Usage desconhecido/inconsistente mantém hold até evidência ou política
  explícita de reconciliação; aprovação não autoriza refund ou retry cego.
- Os novos casos Postgres usam transações/savepoints e replay sequencial.
  Não houve novo stress com duas conexões; locks, unique constraints e fences
  foram auditados no source.
- O smoke browser opt-in antigo conserva o contrato anterior sem quote e
  requer migração da fixture antes de ser reutilizado. Seu expected não foi
  relaxado; os novos gates cobrem o contrato atual.

**APPROVED** para a implementação e os contratos determinísticos do commit
revisado. A aprovação não constitui validação live ou ativação comercial.
