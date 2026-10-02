# SPEC-175 v4 — revisão independente Sol

```yaml
spec_id: SPEC-175
review_model: gpt-6-sol
review_run_id: SPEC-175-SOL-20261001-V4-01
review_status: BLOCKED
threshold_decision: remover
```

## Parecer

O resultado numérico pré-registrado aponta para **remover o Project Index do fluxo padrão**: B tem 2/8 vitórias de custo, a localização empata em 15/16 e a mediana de calls piora 12,5%. A revisão da SPEC fica bloqueada porque o selo temporal declarado contradiz o primeiro trace e porque o isolamento de ferramentas não é verificável além do harness. A decisão de threshold é uma leitura dos 32 resultados publicados, não uma aprovação de causalidade do A/B.

## Integridade e controles

- Recalculei os SHA-256 dos bytes do pré-registro, compromisso, ground truth selado e revelado, prompts base/de condição/de sessão, attestation sem `attestation_hash` e quatro sessões. Todos batem com os valores comprometidos; o JSON canônico do ground truth tem SHA-256 `1f5ec3ce3b235271d7a2cb0e02d3fd9fdf57326554dbde9e4f2714dee63f9af3`. Os arquivos selado e revelado têm bytes idênticos. Os hashes de source tree e grafo na attestation coincidem com `project_index/manifest.json`.
- As quatro sessões completas declaram `gpt-5.6-terra`/`high`, ordens cruzadas A1/B2 B01→B08 e A2/B1 B08→B01, oito resultados cada e prompts com hashes corretos. Em todas as 32 observações, sequência e contagem de operações, soma de `source_bytes` e campos de resultado conciliam; máximos de 8 calls, 47.112 source bytes e 187,739 segundos ficam sob 12/50.000/300. A não registra consulta ao índice; as 16 tarefas B começam por `index:query` e depois fazem descoberta em source permitido.
- **Contradição de pré-selo:** `attestation.json` declara `created_at: 2026-10-01T02:20:00Z` e `sealed_before_runs: true`, mas A1 foi criada às 02:17:12Z e sua primeira descoberta ocorreu às 02:17:45Z. A sessão A1 já carrega o hash dessa attestation. O `LastWriteTimeUtc` NTFS da attestation é 02:17:02Z e o do pré-registro é 02:15:28Z, coerentes com arquivos presentes antes do trace; o reveal tem criação NTFS às 11:25Z. Esses metadados locais são mutáveis e não resolvem a contradição do campo comprometido nem provam, de forma independente, quando os bytes exatos foram selados. O diretório v4 está untracked; não há commit anterior ao run que fixe o selo.
- O harness bloqueia caminhos de docs/specs/benchmark/ground truth em `search`/`read`, impede `index` em A e exige consulta inicial em B. Os traces comprovam somente chamadas feitas **através do harness**. Prompt e harness não restringem, por permissão de sistema, outras ferramentas de leitura do agente, nem registram um transcript completo delas. Assim não posso certificar ausência de consulta externa ao harness, vazamento de ground truth, modelo/effort real ou sessões sem contexto prévio apenas pelos campos de sessão. Não há indício positivo de vazamento nos traces publicados.
- V2 `attempt-01` preserva parciais 3/0/1/0 e `attempt-02` não tem resultados; os hashes preservados batem com o manifesto de aborto. V4 preserva A2 com 7 resultados e B1 com 4, ambos interrompidos por limite de uso, com hashes corretos; reiniciaram do primeiro item e nenhum parcial entrou no denominador. Essas exclusões são de **execuções incompletas de infraestrutura**. V3 é diferente: quatro sessões chegaram a oito resultados cada e foram excluídas por indisponibilidade do reveal do ground truth v3. O pré-registro v4 declarou essa exclusão antes dos runs v4, mas ela elimina observações completas e cria risco de seleção entre tentativas. Os resultados v3 não devem ser confundidos com abortos nem usados como confirmação de v4; a lacuna de reveal deve permanecer explícita.

## Ground truth e `resolved`

Conferi os oito pares de sinais no source: `player_died`/`game_over` contra `player_downed`, coalescência transitiva de NPC, baseline e recibo após mutações, gate de recuperação antes do router, recuperação de JSON com `schema.model_validate`, round-trip dos dois campos de arte, vínculo entre principal/hash e receipt, e F16 em 320/390/768/1440 px. Os `core_files` apontam para implementações reais. Os testes de B07 incluem `tests/test_postgres_claim_idempotency.py`, que cobre o arbiter de insert da operação, mas não testa por si só principal/hash/receipt; tratei esse teste como apoio estreito de idempotência, sem atribuir-lhe prova dos dois sinais.

Regra aplicada sem completar a resposta com conhecimento do reviewer ou com o nome de um teste: pelo menos um `core_file` **na lista de arquivos** e os dois `resolution_signals` **na frase de resolução**. Uma referência genérica a save/load não afirma declaração no schema; “aliases coalescem” não afirma ponte transitiva; “recibo canônico” não afirma sua derivação após mutações. `P` = passou; `F` = falhou, com motivo sucinto.

| Tarefa | A1 | A2 | B1 | B2 |
| --- | --- | --- | --- | --- |
| B01 | F: não exige evento terminal | F: nenhum core file | P | F: não exige evento terminal |
| B02 | F: omite grupos transitivos | F: omite grupos transitivos | F: omite grupos transitivos | F: merge de duplicatas não cobre ponte transitiva |
| B03 | F: omite derivação após mutações | F: omite validação contra baseline e momento do recibo | F: omite momento do recibo | F: omite checagem de alegação contra baseline |
| B04 | F: omite fase terminal/bloqueio antes do router | F: omite fase terminal | F: omite recuperação e fase terminal | P |
| B05 | F: “JSON válido” não afirma validação Pydantic | P | F: omite validação tipada e ausência de nova request | P |
| B06 | P | F: omite declaração dos campos | F: omite declaração dos campos | F: omite declaração dos campos |
| B07 | F: omite escopo de principal | F: omite escopo de principal | F: omite escopo e receipt antes de mutação | F: omite escopo de principal |
| B08 | F: não afirma ausência do logout fixo durante play | P | F: omite controle único e F16/viewports | F: omite F16/viewports |

Totais `resolved`: **A 3/16; B 3/16**. O empate depende da leitura estrita e consistente acima; a decisão `remover` também decorre, independentemente dessa métrica, de menos de quatro vitórias de custo sem ganho de localização.

## Recálculo das métricas e threshold

Reproduzi a agregação de Luna diretamente dos resultados/traces: localização A/B **15/16 / 15/16**; arquivos irrelevantes **10 / 9** (médias 0,625 / 0,5625); recall médio dos testes **0,5833 / 0,4167**; medianas de calls **4 / 4,5**; de source bytes **25.142 / 10.115,5**; de wall time observacional **17,9655 / 28,419 s**. A queda de 59,77% nos bytes vem com aumento de 12,5% em calls, acima do limite de 10%; o gate global falha. Aplicando a média das duas réplicas por tarefa, apenas **B02 e B04** satisfazem `cost_win`; B03/B05/B06/B07/B08 economizam bytes com aumento excessivo de calls, e B01 piora ambos.

`obrigatório` falha por 2/8 < 6/8 e pelo gate global; `seletivo` falha por 2/8 < 4/8. A cláusula de remoção aplica-se literalmente: com 2/8 vitórias, B não oferece ganho de localização suficiente para justificar a complexidade, pois o número de acertos é **idêntico** em A e B. Não imponho um novo limiar de localização pós-hoc. Wall time é observacional e também piora em B; a métrica de bytes não contabiliza o texto devolvido pelo próprio índice (`index.output_bytes`), como previsto pelo trace de `source_bytes`.

## Reparo mínimo para aprovar uma conclusão confirmatória

Se existir prova independente anterior a **02:17:45Z** dos bytes exatos de pré-registro, compromisso, attestation e prompts, e um transcript completo que mostre todas as ferramentas usadas pelos agentes e sua ausência de acesso ao ground truth, anexá-los sem reescrever v4; registrar em errata por que `created_at` ficou no futuro. Sem essa prova preexistente, criar **v5** com selo imutável anterior ao primeiro run (por exemplo, commit com pré-registro, ground truth selado/compromisso, attestation e hashes de prompts), timestamp coerente e isolamento por permissões ou auditoria completa de ferramentas. Executar quatro sessões novas de Terra High nas ordens congeladas, revelar depois e recalcular todos os resultados sem excluir sessões completas. Preservar v1–v4, incluindo os quatro resultados completos v3 como tentativa excluída por reveal indisponível, explicitamente distinguida dos abortos parciais. Não corrigir v4 retroativamente nem selecionar somente runs favoráveis.
