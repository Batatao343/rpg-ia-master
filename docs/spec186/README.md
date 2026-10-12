# SPEC-186 — Speech-to-text privado com wallet

SPEC-186 **`done`** após implementação, gates e smoke real explicitamente
autorizado pelo usuário. Revisões Sol High independentes offline e de
fechamento **APPROVED**. A dependência da SPEC-187 está concluída. O serviço
continua desativado por default; nenhuma ativação comercial ocorreu.

## Contrato HTTP e privacidade

`POST /account/transcriptions` recebe o arquivo como corpo binário, sem
multipart, exige sessão, CSRF/Origin e `x-operation-id` UUID. O owner vem da
sessão. Há rate limit próprio de cinco pedidos por minuto por owner, inclusive
entre instâncias quando o runtime usa Postgres. A resposta traz `operation_id`,
`text` e `billing_status`, com `Cache-Control: no-store`. Nunca chama o grafo,
cria turno ou preenche uma ação; o cliente decide quando enviar texto ao jogo.

Limites antes de reservar ou chamar provider: 8 MiB de bytes reais (também em
upload chunked), 15s de upload, MIME/magic e até 60s de PCM decodificado. São
aceitos `audio/wav`, `audio/x-wav`, `audio/webm`, `audio/ogg`, `audio/mp4`;
parâmetros de MIME como `codecs=opus` são permitidos. WAV precisa ser PCM
mono/stereo, 8–48kHz, 8/16/24/32 bits e ter todos os frames declarados. Um WAV
novo contém apenas os frames validados, removendo metadados/chunks extras.

WebM/Ogg/MP4 exigem `ffmpeg` no servidor ou `RPG_SPEECH_FFMPEG` apontando ao
binário confiável. A ausência falha antes da reserva. O decode local usa lista
de argumentos sem shell, `-nostdin`, protocolos `file,pipe`, primeira faixa de
áudio, 16kHz mono PCM, limite de 61s para detectar excesso e timeout de 10s.
O subprocesso é encerrado por `subprocess.run` no timeout. Nenhum URL é aceito
como input. O diretório temporário inteiro é removido no sucesso, HTTP 4xx/5xx,
timeout, cancelamento, falha do decoder, do provider ou da persistência.

Áudio e transcript não entram em DB/log/receipt. O receipt guarda apenas o
tipo e `result_retained=false`; o hash de request vincula bytes e MIME sem
armazenar o áudio. Uma chave já concluída retorna 409, pois o resultado foi
descartado. Uma chave com efeito incerto também não retranscreve. Não há
original filename na requisição do provider; o nome fixo é `recording.wav`.
Responses dos providers têm limite de 128KiB, texto máximo de 8.000 caracteres,
timeout HTTP de 20s e timeout total de 22s por tentativa, sem retries de SDK.
Erros públicos usam códigos fixos, sem bodies, chaves ou transcripts.

## Providers e custo

IDs/contratos foram reverificados em **2026-10-12**:

- Groq primary: `whisper-large-v3-turbo`,
  [speech-to-text oficial](https://console.groq.com/docs/speech-to-text):
  US$0,04/h, mínimo faturado de 10s, attachment até 25MB. O custo é calculado
  pela duração dos frames realmente enviados, arredondado para cima a 1 nanoUSD.
- OpenAI fallback: `gpt-4o-mini-transcribe`,
  [modelo oficial](https://developers.openai.com/api/docs/models/gpt-4o-mini-transcribe)
  e [contrato HTTP](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create).
  O limite de US$0,03 por tentativa é uma **derivação**, usando contexto de
  16.000 tokens × US$1,25/M + output máximo de 2.000 × US$5/M. O request não usa
  prompt, stream nem `chunking_strategy`; a API trata o arquivo como bloco
  único nesse contrato. Usage com input inteiramente de áudio (`text_tokens=0`)
  e contadores dentro desses limites recebe custo exato. Contadores ausentes,
  inválidos ou fora do teto permanecem conservadores e não faturáveis.
- O valor divulgado de US$0,003/min para OpenAI é estimativa, e usage somente
  por duração **não** vira cobrança exata. O card de STT é separado, imutável,
  identificado por versão+hash e exige frescor de sete dias antes do dispatch.
  O card histórico dos LLMs não foi alterado.
- [Deprecations oficial](https://developers.openai.com/api/docs/deprecations):
  `gpt-4o-mini-transcribe` está anunciado para desligamento em **2027-02-26**.
  O ID exigido pela spec é mantido e configurável; outro ID precisa de card
  verificado antes de autorizar gasto, mesmo quando há chave.

Configuração server-side: `RPG_SPEECH_ENABLED=1`,
`RPG_SPEECH_PRICING_VERSION` publicado pelo operador, FX/card de pricing
frescos, saldo disponível, keys e limites. Defaults de modelos são
configuráveis por `RPG_SPEECH_GROQ_MODEL` / `RPG_SPEECH_OPENAI_MODEL`.
`RPG_SPEECH_MAX_RESERVE_MILLI` limita a reserva total (default 100). O serviço
reserva a soma dos limites arredondados de cada candidato disponível antes da
primeira chamada. Provider sem key/circuit aberto não recebe ticket nem
chamada. Após três falhas consecutivas, o circuito local abre por 60s.

Canonical owners continuam `PostgresTurnCoordinator`, `append_usage_events`
e `PostgresWallet`; este serviço apenas os compõe. A migration acrescenta
`speech_to_text` à constraint de tipo da operação, sem tabelas de gravação ou
novos grants. O mapa de ownership foi consultado seletivamente; wallet não
está mapeada nele, então owner/invariantes foram confirmados no source e SQL.

Um ticket durável precede cada dispatch, com chave `speech:<ordinal>`. Há um
event de usage por ticket, atribuído à operação/owner. Somente quando todas as
tentativas têm cobrança comprovada, o mesmo settlement soma seus custos e
libera o restante. Tentativa comprovadamente gratuita soma zero; falhas sem
usage, timeouts e cancelamentos **não** são inferidos como gratuitos. São
registrados como estimativa pelo teto e a reserva fica `uncertain`, com novo
fence e `billing_status=pending_reconciliation`. Usage por duração somente na
OpenAI segue esse caminho. Falha ao liquidar após persistir usage também
preserva a reserva, sem reenviar áudio ou liberar fundos automaticamente.

Os eventos originais são append-only: uma estimativa não pode ser sobrescrita
quando uma prova chega. Após verificação do operador, o writer canônico
`append_usage_events` pode anexar uma evidência `provider_reported` exata sob
component de reconciliação/ID único na mesma operação/owner, preservando os
fatos originais. Nunca reutilizar `(operation, component, ordinal)` com fatos
mudados. `settle_usage` então recebe exatamente um event exato por ticket:
novas evidências de tentativas antes incertas mais os events exatos originais
do fallback, com o fence atual. Prova de tentativa gratuita pode registrar
custo exato zero; não se inclui também sua estimativa original no settlement.

Liberação total por ausência de cobrança exige `reconcile_proven_no_charge`
com ator e referência de prova, conforme SPEC-184, e só serve quando não há
usage exato já conhecido. Uma falha incerta primária com fallback faturável
exato não permite liberar a reserva inteira: esse método rejeita a liberação,
e o caminho é anexar a prova primária e liquidar a composição exata. Não há
endpoint público de reconciliação. Já liquidada, uma
reserva retorna seu terminal sem nova transferência. O dashboard classifica
eventos e settlements como `voice`, com filtro de owner e sem usar GameState.

## Evidência determinística

- `tests/test_speech_to_text.py`: fake providers pt-BR/Valoria, limites antes
  de efeitos, fallback, valores de card, circuito, MockTransport dos dois
  contratos oficiais, WAV canônico, decode WebM/Ogg/MP4, timeout/cancelamento e
  limpeza mesmo quando a camada financeira falha.
- `tests/test_speech_api.py`: sessão/CSRF/Origin, owner da sessão, limiter
  próprio, corpo chunked limitado, modo desativado, redaction e zero auto-send.
- `tests/test_speech_finance_local.py`: seis testes em Postgres real com
  rollback, round-trip ledger/account, soma+replay, isolamento de owner,
  saldo/teto, timeout/cancelamento e falha de settlement após usage durável.
- Gate final focado, com Postgres local e ffmpeg real:
  `uv run --no-sync pytest tests/test_speech_to_text.py tests/test_speech_api.py
  tests/test_speech_finance_local.py --basetemp=C:\tmp\rpg_spec186_focus`
  — **44 passed**, dois warnings, 3,36s, exit 0. Os três formatos comprimidos
  WebM/Ogg/MP4 passaram no binário real.
- Gate ampliado wallet/pricing/account: **70 passed, 3 skipped** antes da
  execução do decoder fora do sandbox. Rerun das 19 verificações afetadas por
  migration local/Project Index: **19 passed**. Ruff e `git diff --check` verdes.
- Suíte Python completa `uv run --no-sync pytest` com Postgres local e ffmpeg:
  segunda execução chegou a **100%, exit 0**, sem falhas, apenas warnings.
  A combinação de `-q` local com `addopts -q` suprimiu a contagem do resumo;
  nenhum total de passed/skip é inferido. O schema local também recebeu a
  migration existente da SPEC-185 antes desse gate. Project Index regenerado
  do source final; somente artefatos derivados de índice mudaram.
- Revisão Sol High independente **APPROVED**, run
  `SPEC-186-SOL-20261012-01`, sem bloqueios;
  [parecer](../../handoffs/SPEC-186-SOL-independent-review.md).
- Fechamento documental: `tests/test_spec_index.py` **4 passed**; check do
  Project Index exit 0, `fresh_commit_drift` (source idêntico, só SHA de commit
  divergente), e `git diff --check` verde. Código/testes de produto não mudaram
  após os gates completos.

Supabase changelog e RLS oficiais consultados em 2026-10-12. Não há mudança
de Auth/Storage/Data API. CLI `supabase` indisponível neste ambiente; migration
criada seguindo a convenção local e validada em transação com rollback no
Postgres de teste, sem aplicação cloud ou edição do histórico de migrations.
Nenhum evaluator, expected, baseline ou dataset de regressão foi alterado.

## Smoke real autorizado e fechamento

O usuário autorizou os testes reais com teto de quatro chamadas/US$0,10 e
**sem recarga de providers**. Foram exatamente **quatro chamadas Groq** com
`whisper-large-v3-turbo`, passando pela wallet Postgres real. Todas terminaram
`success`/`settled`; o dashboard registrou eventos voice **2 + 1 + 1** nos três
owners de teste, e todas as reservas terminaram com saldo reservado zero.
As execuções usaram transações locais com rollback; os créditos e registros
financeiros de teste não ativaram nem alteraram contas comerciais.
Nenhum áudio/transcript foi persistido; os arquivos temporários foram
removidos. Não houve envio de ação ao jogo, long-run ou ativação comercial.

Os dois áudios sintéticos tinham **1,75s e 2,69s**. Na dupla final, as latências
medidas foram **648ms e 829ms**. O custo total normalizado pelo card publicado,
incluindo o mínimo faturado de 10s por chamada Groq, foi **US$0,000444448**;
essa é uma normalização de rate-card, **sem confirmação por invoice**.

A voz sintética flite disponível estava em inglês. As similaridades observadas
foram **0,811/0,735**, com nomes próprios parcialmente perdidos. Esses valores
descrevem apenas as frases sintéticas desse smoke: **não comprovaram precisão
pt-BR nem qualidade de nomes de Valoria**. Testes/fixtures pt-BR determinísticos
permanecem a evidência offline; o smoke comprovou o contrato live, o caminho
financeiro e a limpeza, com essa limitação de qualidade registrada.

OpenAI live: **`skipped_missing_key`**. Nenhuma chamada OpenAI ou recarga foi
feita. O fallback OpenAI continua verificado nos gates offline/MockTransport;
qualidade/latência e uso efetivo desse provider não foram medidos ao vivo.

Run live: `SPEC-186-LIVE-20261012T1518BRT`, 2026-10-12, aproximadamente
15:15–15:18 (America/Sao_Paulo). Revisor Sol High independente aprovou o fechamento (`SPEC-186-SOL-20261012-LIVE-01`)
com essas limitações, após a revisão técnica offline
`SPEC-186-SOL-20261012-01`. O [parecer com addendum](../../handoffs/SPEC-186-SOL-independent-review.md)
registra **APPROVED** para marcar `done`. O gate da suíte completa e seus
limites de contagem permanecem os registrados acima.
