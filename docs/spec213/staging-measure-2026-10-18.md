# SPEC-213 — `inline` × `post_response` no staging com LLM real (2026-10-18)

**Decisão: o staging fica em `inline`.** No Vercel, `post_response` não tira o arquivista do caminho do
jogador. O trabalho só passa para o turno seguinte. Os derivados chegam corretos, mas a latência que o
jogador percebe não melhora, e a cauda piora. O ganho que a SPEC-213 mede offline/legacy depende de o
processo continuar rodando depois da resposta. A função serverless não garante isso.

## Execução

* Staging `rpg-ia-master-staging` (Vercel Hobby `gru1`, `hosted-supabase`, RLS por request). Supabase
  `uzeagzcyvxzrpjgrhaql`, com a migration `20261016121500_archive_projection_operations.sql` já aplicada.
* Mesmo código nos três deploys. Commit `2578fad` = `main` `0c8d4cd` mais tooling, runtime idêntico, com
  `/health` mostrando o sha:
  1. `inline`: `h5gb3zw2t`, com `--projection-mode inline` (variável ausente).
  2. `post_response`: `6chmu6bvf`, com `--projection-mode post_response`.
  3. Volta a `inline`: `7a5dzhdfc`, que é o deploy atual. O rollback apagou `RPG_PROJECTION_MODE@production`.
* Tooling: `scripts/staging/vercel_env.py --projection-mode {inline,post_response}` e
  `scripts/staging/projection_measure.py`.
* Sessões: 4 sessões de 15 turnos SSE, duas por modo, alternando `inline`, `post_response`, `post_response` e
  `inline`, num total de **30 turnos por modo**. Cada sessão usou 1 usuário sintético (login com cookie, CSRF e
  captcha) e 1 jogo novo (Devoto do Abismo, nível 1). As ações eram de exploração, diálogo e comércio. Entre os
  turnos houve **8 s de leitura**, simulando um jogador humano. LLM: DeepSeek `deepseek-v4-flash`, com 0
  tentativas falhas e 0 fallbacks.
* O arquivista (chamada SMART) disparou em cerca de 10 a 12 de cada 15 turnos.
* Fontes:
  * cliente: marcas do SSE (`accepted`, primeiro chunk, `done`, `state`, close);
  * servidor: `audit_trace.timing` do save (fases da SPEC-200 e `lock_wait_ms`);
  * banco: `app.jobs` (`project_archive`), `projection_state` e `app.memory_documents`.
* Evidência: `evidence/staging_{inline,inline_2,post_response,post_response_2}.json`, sem ids, texto ou
  segredos.

## Latência (ms, n = 30 por modo)

| Medida | inline p50 / p95 / média | post_response p50 / p95 / média |
|---|---|---|
| **Cliente: fim da narração (`done`), o que o jogador espera** | **11 125 / 25 477 / 12 546** | **10 938 / 28 346 / 14 159** |
| Cliente: ack (`accepted`) | 255 / 19 318 / 1 689 | 342 / 19 370 / 4 820 (máx. 58 906) |
| Servidor: soma das fases | 10 046 / 18 969 / 10 749 | 9 622 / 15 489 / 9 241 |
| Servidor: fases menos narrador | 5 540 / 7 567 / 4 911 | 5 060 / 7 401 / 4 511 |
| fase `archivist` | 3 352 / 4 825 / 2 668 | **7 / 18 / 8** |
| `lock_wait_ms` (espera antes do turno) | 64 / 72 / 64 | **3 048 / 4 633 / 2 189** |
| fase `other` (inclui a espera) | 292 / 358 / 298 | 3 334 / 4 907 / 2 488 |
| narrador (LLM, ruído dominante) | 4 080 / 16 378 / 5 838 | 4 209 / 9 975 / 4 730 |

* Diferença no p50 visível ao jogador: −187 ms (−1,7 %), dentro do ruído do narrador. O p95 sobe +2,9 s e a
  média sobe +1,6 s, puxados por um ack de 58,9 s.
* O custo foi transferido, não removido: o `archivist` some do turno, mas reaparece como espera no turno
  seguinte. Em 18 de 30 turnos `post_response`, `lock_wait_ms` passou de 1 s, ficando em 2,2 a 4,9 s. Nessas
  esperas, `_await_projection_db` aguardava o job `project_archive` do turno anterior, ainda `running`. O
  tempo é aproximadamente o de uma chamada SMART.
* Por quê: depois que o stream fecha, a Vercel congela a instância e a thread que drena o job pós-resposta
  para no meio da chamada LLM. Ela só retoma quando chega a próxima requisição. O tempo entre `created` e
  `succeeded` do job foi de p50 11,8 a 12,1 s, maior que os 8 s de leitura somados aos cerca de 3 s do SMART.
  Um job chegou a 66,8 s, na mesma sessão do ack de 58,9 s. Na média, o ganho líquido no servidor é de cerca
  de 0,4 s por turno.
* Essas medições não estão cobertas:
  * um pré-aquecimento ou `waitUntil` real, que não existe no runtime Python da Vercel usado aqui;
  * um worker dedicado drenando `app.jobs` continuamente. O cron `/internal/cron/jobs` roda por minuto e não
    acompanha o ritmo do jogador.

## Corretude (`post_response`, 2 sessões, 23 jobs)

| Verificação | Resultado |
|---|---|
| Turnos 200, sem `error`, narração não vazia, `turn_count` consecutivo | ok (30/30) |
| `canonical_version` estritamente monotônica nas respostas | ok. Respostas trazem `pending` e depois `completed` |
| Os derivados chegam (sem `pending_derived`; summary/memory/chronicle `completed` com `projected_version == canonical_version` = 15) | ok, já no primeiro snapshot depois do último turno (0,5 s) |
| Jobs `project_archive` | 11 e 12, todos `succeeded`, `attempts` máx. 1, 0 erros, 0 `dead`/`retry`, chaves de dedupe distintas = n |
| Sem duplicação de memória (`app.memory_documents` linhas = `content_sha256` distintos) | ok (17/17, 22/22) |
| Cerca do próximo turno | ok. O turno seguinte espera o job `running` (R10) e então commita, sem conflito nem turno perdido |
| Reload (`GET /game/state`) | 200. Projeção `completed` na versão canônica e capítulos da crônica servidos |

* **Ressalva sobre a crônica.** Nas duas sessões `post_response`, a crônica teve 0 entradas. Nas `inline`,
  teve 3 e 1, só marcos (`milestone`). Nenhuma das 4 sessões teve prosa: o LLM não devolveu
  `chronicle_entry` e não houve rejeição de evidência. Os marcos vêm do caminho canônico, igual nos dois
  modos, e dependem dos eventos da sessão. A diferença é de conteúdo, não do modo.
* A primeira versão da verificação exigia entradas maiores que 0 e por isso marcou `false` nos JSONs de
  `post_response`. A verificação foi corrigida no script para "capítulos servidos + projeção `completed` na
  versão canônica".
* O fallback por cron não foi exercitado: a própria API concluiu todos os jobs.

## Rollback / reativação

* Estado atual (`inline`): `uv run python -m scripts.staging.vercel_env --projection-mode inline`, seguido de
  `vercel deploy --prod -e GIT_SHA=<sha>`.
* Para reativar `post_response`: o mesmo comando com `--projection-mode post_response` e um novo deploy.
  **Não recomendado no Vercel** sem worker contínuo.

## Gasto e limpeza

* DeepSeek: cerca de US$ 0,25 em 60 turnos, 4 jogos novos e cerca de 45 chamadas SMART. A estimativa usa a
  medição de 17/10 (US$ 0,0038 por turno) mais o arquivista. O ledger foi apagado em cascata junto com os
  jogos.
* Jina ficou no free tier. O teto `RPG_DAILY_SPEND_CAP_BRL=5` e o cap de texto continuaram ligados.
* Jogos e usuários sintéticos foram apagados. O sweep encontrou 0 sobras, e restaram 0 jobs `project_archive`
  e 0 jogos `spec192-*`.
