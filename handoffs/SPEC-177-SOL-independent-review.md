# SPEC-177 — revisão independente Sol High

## Identidade e decisão

```yaml
spec_id: SPEC-177
reviewer:
  model: gpt-6.1-sol
  effort: high
  task_session_id: /root/spec176_reviewer
  selection_evidence: seleção do harness informada pelo coordenador
  independent_from_executor: true
reviewed_branch: spec-177-jev-adapter
base_sha: 239c1f194b4aea6b5ceeb304e5a268d14ef9599b
decision: APPROVED
decision_scope: technical_local_patch
recorded_at: '2026-10-03'
```

**APPROVED técnico local** após as correções descritas abaixo. A revisão foi
feita em contexto separado do executor, sem alterações de código, specs,
índice ou evidência do executor. O coordenador informou aprovação expressa do
usuário para substituir o executor Terra High por Sol High nesta spec. Este
parecer registra a revisão Sol exigida; não constitui promoção de Jev.

O patch ainda estava sem commit na revisão. A identidade dos arquivos
aprovados foi conferida novamente ao registrar este parecer:

| Arquivo | SHA-256 |
| --- | --- |
| services/jev_decision.py | 13019676eb76122fc2ff69f85b55f82b3e849609ca4de05bb4f5fc3968245c41 |
| tests/test_jev_decision_backend.py | a5bf421ad9537733264de6bf7cbb8af8f1f177641145bcef12ca1a553fc4b994 |
| tests/fixtures/jev_decision_success.json | f7dc0abc413609128e29a7ca371fa3236bce004a9b301f25a12f12c312c11c5d |

## Escopo

Revisados a SPEC-177, o contrato de modelos, o adapter, testes/fixture,
alterações de .env.example, pyproject.toml e uv.lock e a ausência de diff nos
paths de produção e eval protegidos. O contrato HTTP foi conferido em
[Jev API documentation](https://jevmodel.org/docs/) em 2026-10-02: endpoint,
Bearer auth, shapes Choice/Noul/Score, limites publicados, usage, idempotency
e retry de 429/502. A semântica dos timeouts foi conferida na
[documentação HTTPX](https://www.python-httpx.org/advanced/timeouts/).

A implementação mantém seam server-side próprio, DTO limitado, erros tipados,
identidade de modelo retornada e telemetria sem corpo completo ou segredo.
Não integra Jev em RoutedLLM nem altera a route de produção. A configuração
canônica é JEVMODEL_API_KEY; variável legada isolada pede migração, e valores
conflitantes falham fechado. A fixture é sintética/offline e não foi tratada
como prova de resposta live.

## Gaps encontrados e correções verificadas

O primeiro parecer foi CHANGES_REQUESTED por três reproduções offline:

1. **Deadline total insuficiente.** Um transporte de 50 ms retornava uma
   decisão válida com orçamento de 10 ms. HTTPX configura timeouts por
   operação, não um prazo total.
2. **Coerção de resposta incompatível.** noul=true virava 1.0;
   input_tokens="136" e output_tokens=true viravam 136 e 1.
3. **Mutabilidade após validação.** frozen=True não congela dicts/listas;
   alterar questions permitia enviar dez perguntas sem revalidar o budget.

Correções aprovadas:

- `_StrictWireModel` usa strict=True em respostas e usage, rejeitando as
  coerções reproduzidas e preservando os erros tipados.
- `wire_body()` revalida uma cópia destacada do request; `decide()` fixa o
  body e o snapshot antes do transporte e usa os mesmos dados nos retries e
  na validação da resposta. Mutação posterior não muda o payload enviado.
- `_call_with_deadline()` cobre HTTP, JSON parse e validação dentro do worker;
  o caller espera somente pelo orçamento restante e rejeita resposta tardia.

A primeira correção do deadline introduziu threads sobreviventes sem limite
e manteve o parse no caller. Reproduzi três workers ativos após três timeouts
e parse de 80 ms devolvendo timeout somente após 82 ms com orçamento de 10 ms.
O segundo parecer pediu correção desses problemas. A versão aprovada mantém
lock por backend e semáforo global, ambos ocupados até o worker sair:

- no máximo uma operação em voo por backend e oito globalmente;
- timeout deixa a operação em quarentena, sem permitir novas threads naquele
  backend enquanto a anterior estiver ativa;
- o finally do worker libera ambos os limites;
- falha ao iniciar a thread libera os limites e vira erro de transporte;
- close marca o backend fechado, fecha client próprio e bloqueia novos calls.

## Verificação

O reviewer executou independentemente:

```powershell
uv run --no-sync pytest tests/test_jev_decision_backend.py -q --basetemp <workspace>/.tmp/spec177-review-targeted --tb=short
git diff 239c1f1 -- agents/router.py llm_setup.py evals
git diff --check
```

Resultado: **22 testes focados verdes, exit 0**, incluindo HTTP/timeout,
strict response, budget, mutação, estabilidade dos retries, parse dentro do
deadline, quarentena/cleanup e bloqueio após close. O único warning foi a
depreciação preexistente de langchain-community. O reviewer usou Python 3.13
via uv com ambiente virtual e cache do workspace. Tentativas anteriores do
mesmo comando falharam no setup por permissão do Temp e por parent ausente
de basetemp; nenhuma dessas tentativas foi tratada como gate de produto.

O diff de agents/router.py, llm_setup.py e evals ficou vazio; diff-check
passou. Os hashes acima foram reconferidos ao registrar este arquivo.
O executor informou Ruff verde; o reviewer não repetiu Ruff nem a suíte
completa, e esta aprovação não declara seus resultados por inferência.

## Limites preservados

Timeout limita a espera do caller e **não cancela o provider**. O worker pode
sobreviver ao prazo, mas permanece limitado e em quarentena até terminar.
Sua resposta tardia não vira decisão válida nem gera nova operação automática.
Um retry lógico externo deve reutilizar explicitamente a mesma Idempotency-Key;
o adapter já reutiliza a key nos retries internos permitidos. Não se deve
inferir ausência de cobrança apenas de um timeout local.

Não houve provider real, smoke live, promoção, threshold, alteração da régua
ou long-run nesta revisão. A aprovação cobre o patch identificado, após
fechar todos os findings locais. A conclusão da spec ainda depende dos demais
gates e da documentação final exigidos pelo executor/coordenador.
