# SPEC-412 — revisão independente (Sonnet, risco médio)

Veredito: CHANGES_REQUIRED

## Achados

### P1 — cancelamento durante `await to_thread(finance.admit)` (services/speech_to_text.py:326)
Antes `admit` era síncrono (sem ponto de cancelamento). Agora, se a tarefa é cancelada (timeout/
shutdown) enquanto `admit` roda no thread, o thread termina sozinho e cria o ticket
(`effect_started`), mas: (a) o `event` daquele ordinal nunca entra em `events` (o `try/finally` que
faz `events.append` só começa depois do `admit`); (b) o `finally` externo chama `finish(events=[...anteriores])`
em OUTRO thread, concorrente com o `admit` ainda em curso: `finish` pode fazer `release_pre_effect`
(events vazio) enquanto o ticket é admitido depois. Resultado possível: ticket sem usage event ->
o sweep (`services/wallet_recovery.py`) classifica como `uncertain` e a reserva fica retida para
`admin_wallet_reconcile` manual (não há auto-refund). Não é coberto por job automático.
Correção mínima: executar o trecho financeiro blindado do cancelamento, p.ex.
`await asyncio.shield(asyncio.to_thread(...))` com `try/except CancelledError` que aguarda o futuro
interno terminar antes de seguir (e registra o evento "cancelled" do ordinal), ou agrupar
`admit` + montagem do evento num único passo não cancelável antes do `finish`. Adicionar teste:
cancelar durante `admit` lento (FakeFinance com `time.sleep`) e provar que `finish` roda depois
do `admit` terminar e com evento para o ticket.

### P2 — cancelamento durante `await to_thread(finance.begin)` (speech_to_text.py:323-324)
`begun` só vira True depois do `await`; cancelado no meio, o thread conclui `claim`+`reserve`, mas
`finish` nunca roda -> reserva presa e claim vivo. Antes impossível (sync). Rebaixado de P1 porque
`wallet_recovery` libera `reserved` sem ticket com operação não-viva após a grace (padrão 900 s,
mín. 60 s), então o dinheiro volta sozinho, com atraso. Mesma correção (shield) resolve; ou ao
menos teste + nota. A conclusão R7 do README cobre só cancelamento em `prepare_audio` e afirma
"`finish` não roda" — verdadeira só para essa fase; a seção precisa tratar begin/admit/finish.

### P2 — cancelamento durante `await to_thread(finance.finish)` (finally, :405)
O thread de `finish` termina mesmo cancelado (ok, uma vez só), mas o `billing` não é retornado e
a CancelledError mascara a SpeechError; aceitável, só documentar. Sem execução dupla.

### P3 — `from starlette.concurrency import run_in_threadpool` dentro da função (routes/billing.py:330)
Import local sem necessidade; mover para o topo (o mesmo módulo já usa `run_in_threadpool` em
`stripe_webhook`).

## Itens verificados sem achado
- Pool: `PostgresPool` usa `psycopg_pool.ConnectionPool` (thread-safe); `admin_connection` pega e
  devolve conexão por chamada; estado de `PostgresSpeechFinance` (claim/reservation) é só atributo
  do objeto, sequencial (as chamadas são aguardadas em ordem), sem `threading.local`. `rate_limiter`
  local usa `threading.Lock`.
- Contextvar: nada é setado dentro do thread e lido depois; principal chega por cópia do contexto.
  `asyncio._get_running_loop() is None` é teste válido de "fora do loop".
- Executor padrão: `min(32, cpu+4)` workers; limite 5 STT/min por dono, `RPG_SPEECH_ENABLED=0` por
  padrão, Vercel sem ffmpeg (só WAV via `wave`, rápido). Aceitável; follow-up só se STT for ligado
  em portable com muitos donos (semáforo = D2, fora de escopo).
- Contrato HTTP/ordem: inalterados; áudio inválido falha em `prepare_audio` antes de claim/reserva.
  Asserções existentes intactas; a única mudança em teste existente é a sincronização
  (`while not provider.paths`), que continua provando remoção do áudio e registro do ticket sob
  cancelamento (agora cancela depois do provider começar, equivalente ao cenário antigo). Cancelar
  antes do `begin` tem teste novo (`test_cancelar_durante_prepare...`); cancelar em begin/admit não.
- Limiar de `test_prepare_audio_nao_bloqueia_o_loop` (>=5 ticks em 0,5 s, esperado ~20-50): 5
  execuções seguidas verdes, 1 com carga concorrente verde. Robusto.
- Testes: speech_to_text, speech_api, provider_logging, bug_finops_wallet_jobs, abuse_policy,
  size_budget (`-n 2`) rc=0. `ruff check .` e `ruff format --check .` limpos. Escopo: sem mudanças em
  api.py, docs/guias, AGENTS.md.

## Rodada 2 (revisor Sonnet independente, sobre `954e4881`)

**Veredito: APPROVED_WITH_FOLLOWUPS**

P1 e P2 da rodada 1 corrigidos. Nenhum bug financeiro encontrado ao tentar quebrar a correção.

### Verificação dos pontos pedidos

1. `_run_financial` (`services/speech_to_text.py:296-313`): a task interna é criada uma vez; em
   `CancelledError` o laço espera `future` até `done()`, e um segundo cancel durante a espera cai no
   `continue` (o laço reentra). O cancel original é re-levantado no fim, nunca engolido. Se o thread
   levantar exceção durante a espera, propaga o `CancelledError` e a exceção é marcada como
   recuperada (`future.exception()`), sem "never retrieved". Sem caminho que engula o cancel.
2. Pontos de await de `transcribe_audio`: `prepare_audio` (sem finance ainda, `begun=False`, `finish`
   não roda), `begin`, `admit`, provider, `finish` no `finally`. Em todos, `finish` só roda depois de
   `begin`/`admit` terminarem (a espera do shield garante o happens-before: o loop só lê
   `gate.begun`/`admitted` depois de o thread concluir), roda no máximo 1× (um só ponto de chamada,
   dentro do `finally`) e roda sempre que `begun` é True. Cancel dentro do `finally` (durante
   `finish`) espera o thread e re-levanta; `finish` não repete. Entre o retorno de `begin` e a linha
   seguinte não há await. Sem corrida de leitura.
3. Evento `unknown`: o código antigo (`main`) criava o mesmo `speech_event(... "unknown", {})` antes
   do provider e o anexava no `finally` interno em desconexão durante o provider; `fill_missing_event`
   reproduz exatamente isso para o cancel entre `admit` e o provider. `PostgresSpeechFinance.finish`
   (`infrastructure/speech_finance.py`): evento não `billing_exact` -> `wallet.recover`
   -> `pending_reconciliation` (retém fundos para reconciliação, não reembolsa). Mesmo tratamento
   do caso antigo; coerente.
4. Shutdown: a espera é limitada pelo tempo das chamadas `finance.*` (statement_timeout do role,
   60 s segundo a nota do revisor anterior); não é infinita. Aceitável; é o custo de não cortar
   transação financeira.
5. Testes: `GatedFinance` registra `log` de start/end e `overlap`; `test_cancelar_durante_admit...`
   asserta a sequência completa (finish só depois de `admit:end`), unicidade de `finish`
   e correspondência ticket <-> evento (ordem, não só contagem). `release.wait(10)` é limitado e
   dentro de `assert` (falha em vez de pendurar). 10 execuções seguidas dos 4 testes de cancelamento:
   todas verdes; 1 com outro pytest em paralelo: verde.
6. `routes/billing.py`: import de `run_in_threadpool` movido para o topo; o import local removido de
   `stripe_webhook` era idêntico, sem mudança de comportamento. README R7 presente.
7. Regras: `ruff check .` e `ruff format --check .` limpos no repo; `size_budget` verde; funções
   novas curtas; nada em `api.py`, `docs/guias/*`, `AGENTS.md`. Testes: speech_to_text, speech_api,
   provider_logging, bug_finops_wallet_jobs, abuse_policy, size_budget (`-n 2`) rc=0.
   (Observação de harness: duas instâncias de pytest simultâneas com `test_size_budget` colidiram no
   diretório `pt-*` temporário e uma falhou com FileNotFoundError; isolada passa. Artefato de rodar
   dois pytest ao mesmo tempo, não do código.)

### Achados

- **P2 (follow-up, não financeiro)** `services/speech_to_text.py:~360`: `prepare_audio` roda em
  `asyncio.to_thread` e NÃO é protegido como o financeiro. No cancel (cliente desconecta), o
  `with tempfile.TemporaryDirectory` sai enquanto o thread (ffmpeg, até 10 s) ainda escreve em
  `temp`. Efeito: ffmpeg órfão e remoção do diretório sob arquivo aberto (no Windows,
  `PermissionError` no cleanup pode substituir o `CancelledError`; no Linux pode sobrar arquivo ou
  "Directory not empty"). Antes da spec o código era síncrono e o problema não existia. O teste
  `test_cancelar_durante_prepare...` usa `slow_prepare` fake que nem toca o diretório, então não
  cobre isso. Correção barata: aplicar o mesmo shield-e-espera a `prepare_audio` (reutilizar
  `_run_financial` renomeado para algo genérico) antes de sair do `with`.
- **P3** `tests/test_speech_to_text.py:~658`: `while not finance.entered.is_set(): await asyncio.sleep`
  sem teto; se o código regredir e a fase nunca entrar, o teste pendura. Sugestão: limitar por
  `asyncio.timeout(5)`.
- **P3**: falta teste de duplo cancel e de exceção do thread financeiro durante a espera; a lógica
  está correta por leitura, mas sem cobertura.
- **P3**: exceção do thread financeiro engolida em cancelamento (`future.exception()` sem log).
  Um `logger.warning` ajudaria a depuração; não afeta a corretude.
