# SPEC-175 — pré-registro v5 confirmatório

Registrado antes de qualquer sessão v5. V1–v4 ficam integralmente fora do
cálculo. Durante os runs, seus diretórios e reviews foram movidos para um local
temporário aleatório fora do workspace visível aos agentes. O ground truth v5
existe no workspace somente como ciphertext AES-256-GCM; a chave não está no
workspace nem nos prompts. O reveal será criado por decriptação somente após as
quatro sessões completas.

Os artefatos de selo (este pré-registro, compromisso, ciphertext, attestation e
prompts exatos) serão fixados em um commit Git local do diretório v5 antes da
criação das sessões. O commit e seu timestamp constituem a prova temporal; os
arquivos de sessão serão criados depois e permanecerão fora desse commit.

## Desenho e métricas congeladas

- Terra High, duas réplicas por condição: A1/B2 B01→B08; A2/B1 B08→B01.
- A usa apenas search/read do harness; B consulta o índice primeiro e confirma
  no source. Prompts proíbem qualquer outra descoberta. O harness bloqueia
  docs/specs/instruções/benchmark e grava cada operação permitida.
- Budget por tarefa: 12 calls, 50.000 source bytes, 300 segundos. Wall time é
  observacional. Nenhum run edita produto ou executa testes.
- Tarefas B01–B08: morte após downed; aliases NPC; reward/receipt; lifecycle;
  raw structured JSON; arte em save/load; replay; logout mobile.
- `resolved`: core file + os dois sinais; localization: core nos três primeiros;
  irrelevantes excluem tests; test recall normaliza `::test_name`.
- Média das réplicas por tarefa e mediana das 16 observações por condição.
  `cost_win`: B reduz calls ou bytes sem piorar a outra dimensão >10%. Redução
  global exige ≥20% numa mediana sem piora >10% na outra.

Decisão congelada:

- **Obrigatório:** B não reduz resolved/localization, não aumenta irrelevantes,
  passa a redução global e vence 6/8 tarefas.
- **Seletivo:** B não reduz resolved e vence ≥4/8, sem cumprir obrigatório.
- **Remover:** B reduz resolved, ou vence <4/8 sem ganho de localização
  suficiente para justificar a complexidade.

Sessões incompletas por infraestrutura podem reiniciar integralmente e devem
ser preservadas como aborto. Nenhuma sessão completa pode ser excluída.
