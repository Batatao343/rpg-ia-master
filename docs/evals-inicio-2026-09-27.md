# Evals v4 — início da execução

O pacote [evals-plan-v4](evals-plan-v4/README.md) foi importado com os 43 hashes
do `PACKAGE_MANIFEST.json` verificados. Os 44 arquivos originais permanecem
como referência do plano, inclusive suas specs em `draft`.

## Escopo desta entrega

A primeira etapa é a [SPEC-163](../specs/SPEC-163-normalizacao-historica-specs.md):
normalizar a identidade das specs históricas antes de construir a régua de evals.
O pedido de iniciar o trabalho foi aplicado a essa etapa. As etapas seguintes
permanecem no pacote e só avançam na ordem definida, após os gates da anterior.

O checkout usado é `main`, SHA `cadbdd1013022c98f506ee335fa9072efcc9df6c`.
O SHA `b3dcc19da1768fd11f391a13b301124c825ad6e7` do pacote registra uma observação
anterior; não é a baseline atual. Esta entrega não mede scores do RPG.

## Leitura do plano contra o código

- `playtest/scenarios.py` já oferece cenários com pré-condições e oráculos;
  `playtest/invariants.py` e a telemetria devem ser reutilizados nos adapters.
- `services/narrative_evidence.py` e `services/memory_provenance.py` já possuem
  os checks do produto. Os datasets de eval precisam de labels independentes:
  executar o próprio guard para fabricar o esperado não avalia o guard.
- Um teste offline com MockLLM pode provar integração e contrato; não prova
  acurácia do provider real. Essa distinção deve aparecer nos relatórios futuros.
- O frontend já tem testes Node e integração em browser Python. A etapa 172
  adiciona uma matriz explícita de jornadas, preservando os gates existentes.
- O índice de código é navegação. Seu ganho será medido na SPEC-175, depois da
  baseline; esta etapa inicial cria somente o índice de specs.
- Holdout privado e contratos reais curtos são dependências próprias das etapas
  futuras. A ausência de um holdout não pode ser apresentada como generalização.

Não houve mudança de gameplay, prompts, providers ou critérios existentes de
aceite. Campanhas longas permanecem opt-in e não são requisito desta entrega.

## Execução e evidências

- Inventário e metadata: `gpt-5.6-luna`, effort `high`, execução
  `/root/spec_inventory`.
- Migrador e testes: `gpt-5.6-terra`, effort `high`, execução
  `/root/spec_migration`.
- Coordenação: agente raiz já ativo; custo não otimizado conforme exceção da
  política do pacote. Nenhuma escalada ou revisão independente exigida na 163.
- O sandbox não conseguia ler `web/public/art/v1`, fazendo o Git aparentar
  exclusões. O teste de integridade de arquivos/hashes passou fora do sandbox;
  os assets não foram alterados.
- Inventário confirmado: 162 specs legadas, sendo 148 `done`, 13 `in-progress`
  e uma `draft`. O repositório não é shallow. Há 36 commits de criação e 26
  grupos de specs criadas no mesmo commit; esses grupos exigem desempate lexical.
- Lint de conteúdo executado: zero erros e zero avisos, incluindo assets.

## Resultado da SPEC-163

- 162 specs históricas renomeadas para `SPEC-001`–`SPEC-162`; a SPEC-163 ficou
  fixa e foi incluída no índice.
- `specs/index.yaml` registra a âncora Git, status, criação, primeira prova de
  conclusão, `completed_order`, dependências resolvidas e texto não resolvido.
- `docs/specs-migration-report.md` preserva a correspondência completa entre
  caminhos antigos e novos com a evidência Git.
- O verificador recompõe a proveniência a partir do Git e rejeita índice
  adulterado, histórico shallow, links quebrados ou referências não migradas.
- Gates: verificador verde; 7 testes focados e Ruff verdes; conteúdo sem
  erro/aviso; suíte offline completa **1807 passed, 35 skipped, 15 deselected**.
- Nenhuma chamada de provider real, campanha longa ou alteração de produto.

## Próxima etapa

[SPEC-164](evals-plan-v4/specs/164-agents-md-model-routing.md): atualizar as
instruções operacionais para IDs, índice, integridade das evals, política de
modelos e long-run opt-in. Exige revisão Sol independente.
