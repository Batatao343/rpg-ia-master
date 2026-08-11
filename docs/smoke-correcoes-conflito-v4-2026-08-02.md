# Smoke real pós-correções — Conflito v4

**Data:** 2026-08-02  
**Veredito:** correções do smoke de 2026-07-25 aceitas; `conflito-13` pode ser
marcada `done`. Há três débitos qualitativos não bloqueantes, sendo o principal
já convertido na spec `hardening-memoria-proveniencia` (`draft`).

## 1. Objetivo e método

Esta rodada repetiu o playtest do mesmo grafo usado pelo jogo, com LLM e
embeddings reais, após transformar os achados da run `20260725-101933` em sete
specs de correção. O aceite combinou:

1. regressões focadas e suíte offline completa;
2. matriz offline dos 13 perfis por 30 turnos;
3. campanhas reais dos 13 perfis por 30 turnos, com invariantes, JSONL, saves,
   telemetria de provider/custo e RAG;
4. leitura de reports, transcritos e estados finais;
5. sanity real adicional depois da correção da ação resolvida obsoleta.

A matriz real aceita é **composta**, e não um único diretório: a tentativa
`20260802-132339-092201` completou quatro perfis aceitos, encontrou um reset de
conexão no `diplomatico` e depois revelou um hang sem timeout da Jina no `fujao`.
O processo foi interrompido, o cliente de embeddings foi corrigido, e os nove
perfis restantes foram executados novamente, individualmente, com o mesmo seed,
30 turnos e os mesmos tetos. Essa decisão evitou pagar novamente por quatro
campanhas já completas e preservou o artefato defeituoso para auditoria.

## 2. Resultado executivo

| Indicador | Resultado aceito |
|---|---:|
| Perfis / turnos | 13 / 390 de 390 |
| Campanhas abortadas aceitas | 0 |
| `mock` | `false` nos 13 perfis |
| Erros do runner | 0 |
| Violações `error` | 0 |
| Warnings | 44, todos `narrative.repeated_opening` |
| Sucessos de rede registrados | 1.119 |
| Tentativas LLM falhas observáveis | 13 |
| Custo estimado registrado | US$ 0,328488 |
| Operações RAG | 148 |
| Falhas RAG | 0 |
| Inícios / finais de conflito | 10 / 13 |
| Reações / ações táticas | 4 / 28 |
| Mortes canônicas | 7 |
| Divergências HP↔Vitalidade | 0 |
| `action.declaration_matches` | 0 |

O motor não apresentou soft-lock, dupla intenção oculta, erro terminal,
sentinela `npc_null`, divergência de Vitalidade, falha de persistência RAG nem
falso sucesso de structured output. As falhas de provider ficaram visíveis e o
fallback concluiu os turnos afetados.

## 3. Runs aceitas

| Perfil | Run | Rede | Falhas LLM | Custo US$ | p50 / p95 ms | RAG | Warnings | Cobertura relevante |
|---|---|---:|---:|---:|---:|---:|---:|---|
| agressivo | `20260802-132339-092201` | 49 | 0 | 0,013720 | 5.733 / 31.618 | 5 | 0 | 2 inícios, 4 finais, 2 reações, 3 mortes |
| combate | `20260802-132339-092201` | 71 | 0 | 0,019880 | 15.702 / 31.241 | 14 | 0 | 1 início, 3 finais, 2 reações, 3 mortes |
| comerciante | `20260802-132339-092201` | 126 | 1 | 0,035700 | 7.773 / 16.334 | 4 | 0 | fluxo econômico; ouro final 50 |
| explorador | `20260802-132339-092201` | 116 | 12 | 0,045128 | 18.884 / 41.786 | 8 | 0 | 14 locais, 4 inícios, 3 finais, 12 táticas |
| diplomatico | `20260802-143720-790126` | 95 | 0 | 0,026600 | 13.312 / 18.476 | 28 | 15 | 27 memórias de NPC, sem falha RAG |
| fujao | `20260802-144440-720077` | 90 | 0 | 0,025200 | 9.582 / 34.360 | 5 | 0 | 3 inícios/finais, 16 táticas, 1 morte |
| loot_abuser | `20260802-145220-399815` | 109 | 2 | 0,031360 | 7.533 / 13.300 | 3 | 0 | ouro final 183; itens inválidos rejeitados |
| mapa_breaker | `20260802-145706-180084` | 46 | 0 | 0,012880 | 2.077 / 12.906 | 2 | 17 | permaneceu em Nova Arcadia; 1 local |
| npc_only | `20260802-150010-631551` | 94 | 0 | 0,026320 | 17.879 / 25.987 | 27 | 3 | memória NPC intensiva |
| quester | `20260802-151010-579699` | 92 | 1 | 0,026180 | 13.834 / 28.475 | 23 | 8 | 4 quests criadas, 2 concluídas, reveal válido |
| recrutador | `20260802-151813-681261` | 87 | 0 | 0,024360 | 12.151 / 20.039 | 19 | 0 | integridade verde; party final vazia |
| secret_rusher | `20260802-152626-069109` | 69 | 1 | 0,019740 | 9.188 / 17.049 | 3 | 0 | nenhum `secret_revealed`; achado qualitativo §8 |
| troll | `20260802-153306-418930` | 75 | 1 | 0,021420 | 9.076 / 20.209 | 7 | 1 | input hostil sem execução/efeito indevido |

Cada diretório contém `run.meta.json`, summary, JSONL e report/transcrito
gerados pelo próprio harness. A run compartilhada contém também os perfis que
falharam durante a tentativa inicial; para ela, somente as quatro campanhas
explicitamente listadas acima integram a matriz aceita.

## 4. Achados originais → correção → evidência

| Achado de 2026-07-25 | Spec | Correção entregue | Evidência desta rodada |
|---|---|---|---|
| Crítico repetido/terminal podia travar | `fix-vitalidade-ferimentos-terminal` | capacidade Crítica progride; Última Ação/estabilização/fuga terminal têm lifecycle fechado | 13 finais para 10 inícios, 7 mortes, zero `combat.no_progress` |
| HP e Vitalidade divergiam | `fix-vitalidade-ferimentos-terminal` | Vitalidade é canônica; aliases, save, party, hazard, descanso, API e UI reconciliados | zero divergência em 390 linhas; build web verde |
| Texto e `TurnDeclaration` eram escolhidos separadamente | `fix-playtest-decisoes-atomicas` | `ActionDecision` único dirige texto e mecânica; fuga falha consome ação | zero `action.declaration_matches`; 22 decisões de fuga na matriz |
| Harness produzia falso-verde | `hardening-playtest-observabilidade` | manifesto/completude, startup, falhas, RAG, morte, nós, stream e artifacts são fail-loud | 13 falhas LLM registradas sem perder o turno; tentativa incompleta permaneceu inválida |
| `None`, `npc_null` e path Unicode | `hardening-structured-sentinelas-rag` | validação pós-provider, sentinelas normalizadas, path seguro e erro RAG propagado | 3 fallbacks Groq bem-sucedidos; zero sentinela/falha RAG |
| Números livres do LLM alcançavam mecânica | `hardening-entradas-mecanicas-llm` | limites/catálogos/potência/perfis e perseguição fechados em Python | 28 ações táticas; nenhum erro ou número inválido aplicado |
| `ConflictSummary` sumia e rejeições contaminavam prosa/memória | `fix-resumo-conflito-grounding` | produce→enrich→consume→clear, commit só de efeito aplicado e retry idempotente | zero violação de lifecycle/RAG; loot e retomada pós-conflito íntegros |
| Cartas/reação inimiga não eram efetivas/observáveis | `fix-reacoes-runtime-observaveis` | economia própria do inimigo, frequência por cena e telemetria | 4 reações reais e 28 táticas, zero LLM no resolver |

## 5. Falhas emergentes corrigidas durante a validação

### 5.1 Sobrevivente inconsciente preso fora de combate

Uma campanha real mostrou o perfil repetindo ações sem recuperar um sobrevivente
inconsciente. A correção impede iniciar novo conflito inconsciente, faz o perfil
buscar descanso e permite que descanso longo seguro restaure consciência e
Vitalidade, preservando o Ferimento Crítico para tratamento especializado.

Evidência: `agressivo` real `20260802-131805-929298`, 30/30 turnos e zero
violação, mais regressões em `test_fix_vitalidade_terminal.py` e
`test_playtest_atomic_decisions.py`.

### 5.2 Cliente Jina sem timeout

O `fujao` ficou mais de 15 minutos bloqueado porque a implementação comunitária
usava `requests.Session.post` sem timeout. `rag.py` agora usa cliente `httpx`
com timeout finito (30 s por padrão), no máximo duas tentativas e retry apenas
para erro de transporte ou HTTP transitório. O provider permanece fixo para não
misturar espaços vetoriais.

Evidência: testes de timeout, retry transitório e HTTP 400 sem retry; todas as
nove reruns posteriores concluíram, com 148 operações RAG e zero falha aceita.

### 5.3 `resolved_action` obsoleta no JSONL

O runner lia `combat.resolved_action` do estado acumulado e podia repetir uma
fuga antiga em turno posterior sem combate. A telemetria agora só registra a
ação observada no update de `combat_agent` do invoke corrente.

Evidência: regressão combate→não combate e sanity real
`20260802-154332-961894`: 5/5 turnos, `mock=false`, 24/24 sucessos de rede,
zero erro/violação e nenhum `resolved_action` nos cinco turnos sem combate.

## 6. Providers, fallback, custo e latência

Nos JSONLs dos turnos houve 1.061 respostas bem-sucedidas do DeepSeek
`deepseek-v4-flash` e três do Groq `openai/gpt-oss-120b`. As 13 tentativas não
bem-sucedidas ficaram classificadas como dez `invoke_error` e três
`invalid_structured`; nenhuma virou falso sucesso. O número agregado de 1.119
sucessos de rede inclui também as chamadas de startup/criação.

O fallback preservou a campanha em três respostas. O `explorador` concentrou 12
falhas de tentativa, maior custo (US$ 0,045128) e maior p95 (41,786 s), mas
terminou 30/30 sem erro funcional. Todas as campanhas individuais respeitaram o
teto de US$ 0,05.

## 7. Cobertura mecânica e de produto

- **Terminal e Ferimentos:** sete mortes canônicas; nenhum soft-lock ou morte
  inferida apenas por HP zero.
- **Combate:** dez inícios, treze finais (um mesmo turno pode observar
  fechamento/reabertura e campanhas podem iniciar com estado preparado), quatro
  reações e 28 táticas.
- **Decisões:** 321 `free_text`, 28 `card`, 22 `flee`, 14 `attack` e cinco
  `item`; a declaração é derivada da mesma decisão.
- **Mundo:** `explorador` visitou 14 locais; `mapa_breaker` não atravessou rota
  impossível.
- **Economia:** `loot_abuser` terminou com 183 de ouro e inventário limitado;
  conteúdo inválido foi rejeitado.
- **Quests/segredos:** `quester` criou quatro, concluiu duas e cobriu o caminho
  positivo de `secret_revealed` validado.
- **Input hostil:** `troll` não executou payload nem obteve progressão mecânica
  ilegítima; texto foi tratado apenas como comportamento do personagem.

## 8. Achados residuais e prioridade

### P1 — Proveniência da memória narrativa

O `secret_rusher` não produziu `secret_revealed`, mas o storyteller especulou
sobre um pacto de Valerius com o Rei Subterrâneo e o archivist persistiu a
hipótese como memória. Não foi vazamento literal do segredo canônico: o arquivo
do Rei Subterrâneo é público, e o pacto oculto real é com Daruun. Ainda assim,
rumor/inferência pode retornar depois com aparência de fato.

Esse problema é mais amplo que o `ConflictSummary`, cujo lifecycle foi
corrigido. Foi aberto como
[`hardening-memoria-proveniencia`](../specs/hardening-memoria-proveniencia.md),
status `draft`, para separar fatos confirmados, observações, alegações de NPC e
inferências, com confiança e fonte auditáveis.

### P2 — Cobertura funcional do recrutamento

O perfil `recrutador` passou todas as invariantes, mas não adicionou aliado em
30 turnos. A fiação está coberta offline; a eficácia real deste seed ficou
inconclusiva. Próximo smoke deve começar com NPC elegível em cena ou ter um
oráculo de cobertura que falhe se a party permanecer vazia.

### P2 — Repetição de abertura

Houve 44 warnings, todos `narrative.repeated_opening`: 17 no `mapa_breaker`, 15
no `diplomatico` e os demais distribuídos. Parte é efeito de rejeições
determinísticas repetidas (por exemplo, “não há rota direta”), mas a experiência
continua mecânica. Não é falha de integridade, porém merece tuning de prosa.

### P2 — Cobertura do comerciante

O `comerciante` terminou com o mesmo ouro inicial (50). O perfil
`loot_abuser` comprovou a economia e limites de loot, mas a efetividade de uma
transação comercial real não ficou provada nesta semente.

## 9. Tentativas não aceitas

- `20260802-125418-835968`: offline pré-fix, expôs estado interrompido não aceito.
- `20260802-125751-648132`: processo real órfão pré-recuperação; acumulou oito
  `combat.no_progress` e foi interrompido.
- `20260802-132339-092201`: manifesto global incompleto; `diplomatico` falhou por
  reset Jina e `fujao` revelou o hang. Só as quatro campanhas completas e
  listadas no §3 foram reaproveitadas.

Esses artefatos são evidência forense, não números misturados ao agregado aceito.

## 10. Validações finais

- Matriz offline formal: `20260802-154317-705789`, 13 × 30, zero erro/violação.
- Sanity real pós-telemetria: `20260802-154332-961894`, 5/5, real, verde.
- Suíte offline completa: **1.296 passed, 1 skipped, 14 deselected**; quatro
  warnings de dependências, nenhum warning do código do projeto.
- Lint de conteúdo: **0 erros, 0 avisos** em frontmatter, IDs, referências,
  aliases, visibilidade, overrides, encoding, cartas e bestiário.
- Build React/Vite: **verde**, TypeScript + Vite, 449 módulos transformados.
- Revisão React: estado terminal usa `death_pending`/`game_over`, barras usam
  Vitalidade canônica e listas preservam chaves sem colisão entre nomes iguais.

## 11. Conclusão

Os sete bloqueadores/altos derivados do smoke de 2026-07-25 foram corrigidos e
exercitados com provider real. O motor v4 agora termina seus ciclos, mantém
Vitalidade coerente, resolve exatamente a decisão declarada, observa falhas e
efeitos reais, persiste RAG sem hang silencioso e materializa reações/táticas no
runtime. O cutover `conflito-13` está aceito.

Os resíduos são de qualidade/cobertura, não de integridade do cutover. O único
com risco de verdade narrativa — proveniência de rumor — já tem spec própria e
deve ser priorizado antes de usar memória longa como fonte canônica forte.
