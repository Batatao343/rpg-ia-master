# Prompt para entregar este ZIP ao coding agent

Use este pacote como o próximo plano aprovado do Valoria.

## 0. Model preflight — antes de qualquer implementação

Leia `11_HARNESS_MODEL_CONTRACT.md`, `03_MODEL_EXECUTION_POLICY.md` e `examples/spec-model-contract.yaml`.

O harness deve executar cada spec com o **modelo exato e effort exato** declarados. Não há substituição silenciosa para cima ou para baixo. Se o harness não consegue selecionar/verificar o modelo prescrito, pare com `MODEL_HANDOFF_REQUIRED`.

Reviews obrigatórios usam contexto independente no modelo exato. O coordenador atual pode continuar coordenando, mas não pode implementar uma spec em nome de outro modelo.

## 1. Estado e import

1. Leia `AGENTS.md`, `ESTADO_ATUAL.md`, `ROADMAP.md`, `REFERENCE.md`, `specs/index.yaml`, `evals/README.md`, `evals/protected-paths.txt` e as specs 169/171/174/175.
2. Confirme que o HEAD é descendente do snapshot `1beefc432cce5ded4e3468e42c5e583aa4431a44`, que `SPEC-163..SPEC-175` estão `done` e que `SPEC-176` continua livre. Se não, pare e reporte colisão/renumeração necessária.
3. Importe SPEC-176..198 preservando IDs/dependências e atualize `specs/index.yaml`.
4. Execute estritamente em ordem.

## 2. SPEC-176 é gate zero

Execute SPEC-176 isoladamente com **Sol High**. Não comece Jev enquanto CI/governance não estiver verde em checkout limpo.

Não regenere `manifest.lock.json` às cegas. Prove se o dataset atual é o aprovado; drift semântico exige tarefa/review de evaluator. `eval-governance` continua sendo approval real, nunca variável permanentemente bypassada.

Project Index pode ser regenerado somente para restaurar o freshness contract que o CI ainda verifica; após isso volta a `selective-only` conforme SPEC-175.

## 3. Jev

- Nome canônico da chave: `JEVMODEL_API_KEY` server-side. Se o `.env` local ainda usar `JEV_API_KEY`, não exponha nem copie o valor; trate como migração de config/alias temporário explicitamente testado.
- Jev é `DecisionBackend`, não `RoutedLLM`.
- Runner canônico continua MockLLM/offline e protegido.
- A/B live usa `evals/experiments/` e lê corpus/oráculos protegidos somente como ruler; `expected/oracle` nunca entram no candidato.
- SPEC-177 integra; SPEC-178 mede route; SPEC-179 mede target/loot; SPEC-180 decide rollout.
- Sem holdout privado, não alegar generalização.

## 4. Evals e long-run

Não alterar golden/regression expected, denominadores, registry, schemas, evaluator ou lock para fazer Jev/qualquer produto vencer. Mudança de evaluator é tarefa separada.

Nunca executar long-run automaticamente. Nenhuma spec deste pacote autoriza matriz 10×200 ou campanhas 100/200 turnos.

## 5. Billing/go-live

- Wallet e billing ficam fora do `GameState`.
- Jogadas normais debitam custo real silenciosamente.
- Geração de imagem é a única ação com quote explícito antes do provider. Triggers automáticos existentes podem oferecer imagem, mas não podem gastar Estilhas automaticamente.
- Custo por mensagem é enriquecimento read-only por turn/operation/usage; não persistir billing no `presentation_history`.
- Web = Stripe; Android = Google Play Billing; wallet única.
- Sem free credits, sem subscription, sem imposto na modelagem inicial.

## 6. Cloud/external actions

Não criar/mutar Supabase remoto, Vercel, Stripe live, Google Play Console ou qualquer recurso cobrável antes da spec correspondente e approval humano explícito.

SPEC-194 deve entregar integração técnica testável sem exigir Play Console; a certificação real de store/internal track fica na SPEC-198.

## 7. Fechamento de cada spec

Antes de marcar `done`:

1. cumprir todos os hard gates da própria spec;
2. registrar executor/reviewer reais conforme `11_HARNESS_MODEL_CONTRACT.md`;
3. atualizar `ESTADO_ATUAL.md` e `specs/index.yaml`;
4. garantir checkout final limpo e artefatos versionados sincronizados;
5. rodar os checks definidos na spec;
6. concluir review independente quando obrigatório;
7. não avançar com `review-pending`, `MODEL_HANDOFF_REQUIRED` ou approval externo pendente.

Objetivo imediato: CI/eval íntegro e Jev medido corretamente.

Objetivo final: beta pago pequeno no Brasil, web/Vercel + Supabase, Android/Capacitor/Google Play, wallet única em Estilhas de Éter, metering real, Stripe web, voice input, imagem paga explícita e controle de margem/custo.
