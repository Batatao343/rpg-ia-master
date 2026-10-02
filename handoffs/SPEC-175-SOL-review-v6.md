---
spec_id: SPEC-175
review_model: gpt-6-sol
review_run_id: SPEC-175-SOL-20261001-V6-01
review_status: APPROVED
threshold_decision: remover
---

# Revisão independente da execução confirmatória v6

**Parecer.** Aprovo a conclusão delimitada pelo pré-registro v6: remover o Project Index do fluxo padrão/contexto dos coding agents. Isso não exige apagar `project_index/**`; a consulta explícita pode continuar disponível. A condição B não venceu custo em nenhuma das oito tarefas e não melhorou a localização. A melhora em `resolved` e em arquivos irrelevantes é real no escore estrito abaixo, mas não satisfaz os thresholds congelados para uso obrigatório ou seletivo.

## Integridade e desenho

- Recalculei SHA-256 dos bytes do pré-registro, compromisso, ciphertext, prompts base/de condição/de sessão, attestation e quatro sessões. Os dez hashes de artefatos selados, o self-hash da attestation (`e4de94d4…74b36e`), o plaintext revelado (`1194c5cd…c3a3d6`) e seu JSON canônico (`1f5ec3ce…e63f9af3`) conferem com os compromissos. O grafo, serializado com chaves ordenadas, e a árvore dos `included_files` do manifesto reproduzem os hashes `6c313519…07a16` e `c1149edc…a2f20a`.
- O repositório Git aninhado v6 tem HEAD `aa50ca35af7e0f7c3785e7405b04c23ee68ab326`, datado de **2026-10-01 17:35:52 UTC**. Seus 12 blobs incluem exatamente os artefatos anteriores à execução: `.gitignore`, pré-registro, compromisso, ciphertext, attestation, três prompts comuns/de condição e quatro prompts de sessão. Comparei cada blob com o arquivo atual; todos coincidem, e a árvore de trabalho aninhada está limpa. O registro do selo é de 17:35:53 UTC; a primeira sessão foi criada às 17:36:11 UTC e o primeiro trace começou às 17:36:53 UTC. `ground-truth.json` e os atestados dos agentes foram criados após o último encerramento, às 17:51:30 UTC. Datas de Git e NTFS são evidência local, não carimbo externo imutável; o vínculo decisivo é que o commit fixa os bytes exatos antes dos timestamps registrados das sessões.
- O ciphertext comprometido declara AES-256-GCM, nonce de 12 bytes e AAD `SPEC-175-v5-ground-truth` porque o artefato selado foi reutilizado de v5. O hash do ciphertext v5 e v6 é idêntico. A chave não consta do material v6 visível e o compromisso prévio fixa tanto seu hash quanto o hash do plaintext; sem a chave fora do workspace, esta revisão não repetiu a decriptação. O reveal coincide byte a byte com o hash comprometido. A attestation registra que predecessores ficaram fora do workspace dos agentes durante os runs; seus diretórios reaparecem agora como histórico. Os quatro prompts selados proíbem lê-los e proíbem qualquer descoberta fora do harness.
- As quatro sessões são completas: oito resultados cada, **32/32 observações**, sem exclusão v6. A1/B2 percorrem B01→B08 e A2/B1 percorrem B08→B01. Todas declaram o mesmo `gpt-5.6-sol`/`high`, source/graph hashes e budgets de 12 calls, 50.000 bytes e 300 segundos por tarefa. A substituição de Terra indisponível por Sol High ocorreu no pré-registro, antes da criação das sessões, simetricamente nas quatro condições; é tier superior permitido pela política, com custo de execução não otimizado. Os prompts têm o mesmo texto base e diferem somente na condição, ID e ordem. `fork_turns=none` é o controle declarado para os agentes novos; os arquivos de sessão, por si, não provam a configuração interna do orquestrador.
- Reconciliados diretamente dos traces: sequência, `discovery_calls`, soma de `source_bytes`, resultado final, hashes de prompt, ordem e timestamps. Em A não há operação de índice. As 16 tarefas B começam por `index:query` e seguem com descoberta de source pelo harness. Todos os paths/operações registrados respeitam a allowlist; máximo observado: 12 calls, 49.875 source bytes e 121,123 segundos, sob os tetos. Os atestados finais registram oito tarefas concluídas, ausência de edits/testes e uso do harness ou do lifecycle exigido. A formulação de A2/B1 é resumida, portanto esses atestados não são um transcript completo de ferramentas nem prova absoluta da ausência de consulta não registrada, vazamento ou retenção de contexto. Não encontrei evidência positiva de nenhum desses desvios. A conclusão depende da execução controlada documentada, não de uma alegação de isolamento por permissão de sistema.

As tentativas anteriores ficam como histórico: v1 foi bloqueada por ausência de trace e problemas factuais de ground truth; v2 preserva abortos sem quatro sessões completas; v3 possui quatro sessões completas, excluídas por indisponibilidade do reveal e **não** classificadas como aborto de infraestrutura; v4 possui quatro sessões completas, mas a revisão anterior bloqueou sua prova temporal, além de preservar dois abortos parciais por limite de uso; v5 foi invalidada antes de completar o conjunto (A1=5, A2=4, B1=B2=0 tarefas). O pré-registro v6 excluiu v1–v5 antes de qualquer run v6. Nenhum resultado completo v6 foi descartado, e nenhum número anterior entra nesta decisão.

## Escore semântico de `resolved`

Regra congelada aplicada a **cada** resposta: ao menos um `core_file` comprometido em `result.files` **e** ambos os sinais comprometidos explicitamente em `result.resolution`. `tests`, nomes dos arquivos e meu conhecimento do código não completam omissões da frase. Todos os resultados têm ao menos um core file; a variação abaixo é semântica. `P` = passou, `F` = falhou.

| Tarefa | A1 | A2 | B1 | B2 | Motivo decisivo dos `F` |
| --- | :---: | :---: | :---: | :---: | --- |
| B01 | P | P | P | P | — |
| B02 | P | P | F | P | B1 não afirma coalescência **transitiva** de aliases. |
| B03 | F | F | F | P | A1/A2 removem alegações sem afirmar comparação da alegação ao delta basal; B1 não afirma que o recibo é derivado após as mutações. B2 afirma checagem dos deltas e recibo calculado no finalizador a partir das mudanças de estado. |
| B04 | F | F | F | F | Nenhuma frase cobre conjuntamente o bloqueio das fases **terminal e death_pending antes do router**, além da elegibilidade restrita de recuperação. |
| B05 | F | F | P | P | A1/A2 não dizem que a validação Pydantic do JSON recuperado ocorre **sem outra request**. |
| B06 | P | F | P | P | A2 cita `visual_seen_entity_ids`/`visual_cue_ledger`, não os dois campos comprometidos de arte. |
| B07 | F | F | F | P | A1/A2/B1 omitem escopo do principal. B2 vincula `owner`/hash e afirma retorno do receipt imutável já concluído no replay exato. |
| B08 | F | F | F | F | A1/B2 descrevem layout responsivo, mas não afirmam que **F16** prova ausência de overlap em todos os viewports alvo; A2/B1 também não cobrem a ausência explícita do logout fixo durante play. |

Totais: **A 5/16; B 9/16**. Interpretações mais generosas das frases limítrofes não alteram a decisão: o critério de custo permanece em 0/8 e a localização permanece empatada.

## Métricas recalculadas e threshold

Usei os 32 resultados e seus traces, sem o resumo mecânico como entrada. `localization_hit_before_edit` é um core file entre os três primeiros caminhos listados; arquivos de teste não contam como irrelevantes; recall remove o sufixo `::test_name`; medianas de 16 observações usam a média dos dois centrais. Wall time é observacional e `source_bytes` não inclui bytes devolvidos pelo próprio índice.

| Condição | N | Localização | Irrelevantes total / média | Recall médio de testes | Mediana calls | Mediana source bytes | Mediana wall s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 16 | 16/16 | 18 / 1,1250 | 0,6042 | 5 | 24.676 | 38,907 |
| B | 16 | 16/16 | 12 / 0,7500 | 0,6458 | 8 | 30.999,5 | 58,2535 |

| Tarefa | A calls | B calls | A bytes | B bytes | `cost_win` |
| --- | ---: | ---: | ---: | ---: | :---: |
| B01 | 5,5 | 10 | 45.170,5 | 38.177,5 | não |
| B02 | 3,5 | 8 | 44.938 | 45.503 | não |
| B03 | 6 | 10,5 | 32.319 | 25.457 | não |
| B04 | 6,5 | 7,5 | 23.252,5 | 20.445,5 | não |
| B05 | 3,5 | 6,5 | 11.753,5 | 30.999,5 | não |
| B06 | 2 | 7 | 21.717 | 9.015 | não |
| B07 | 4,5 | 7 | 31.266,5 | 44.914 | não |
| B08 | 6 | 10 | 10.820 | 21.700,5 | não |

As médias das duas réplicas dão **0/8** vitórias: mesmo onde B lê menos bytes, calls pioram mais que os 10% permitidos. As medianas globais de B pioram **60,0% em calls** e **25,63% em source bytes**, logo o gate de redução ≥20% sem piora >10% falha. `obrigatório` falha pelo gate e por 0/8 < 6/8; `seletivo` falha por 0/8 < 4/8. Pela cláusula congelada de remoção, 0/8 sem qualquer ganho de localização leva a **remover do fluxo padrão/contexto**. O resultado não autoriza inferir que o índice é inútil para toda tarefa futura: esta é a decisão operacional para o conjunto histórico e orçamento pré-registrados.
