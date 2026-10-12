# SPEC-187 — Entrada de voz no composer

## Contrato implementado

`web/src/voice/recorder.ts` fornece o adapter substituível, com negociação de
WebM/Opus, Ogg/Opus e MP4 por `MediaRecorder.isTypeSupported`. O recorder pede
apenas áudio; libera todas as tracks ao parar, cancelar ou falhar, inclusive
quando a permissão chega depois do cancelamento. O controller determinístico
mantém `idle/recording/uploading/transcribing/error`, contador e hard stop de
60 segundos. Não há dependência nativa; um adapter futuro pode implementar a
mesma interface se os testes Android da SPEC-193 exigirem.

O hook limpa captura, timers e upload em `visibilitychange(hidden)`, `pagehide`,
unmount e mudança de campanha. Uma geração descarta callbacks atrasados.
Background em idle não altera o status. Erro do recorder chega imediatamente
ao controller, encerra a captura e permite tentar novamente.

O fluxo é **Voz → Parar (ou 60s) → transcript editável → Agir explícito**.
Texto digitado antes ou durante a gravação/STT é preservado; o transcript é
acrescentado ao texto atual. STT nunca chama `onAction`. Agir/Enter com texto
cancela uma captura/transcrição pendente e envia somente a edição atual.
Permissão negada, navegador/formato incompatível e falha de STT mantêm o input
habilitado; restrições anteriores de fim de jogo continuam válidas.

Upload usa um Blob binário em `POST /account/transcriptions`, com o MIME real,
cookies, `X-CSRF-Token` e `X-Operation-Id` UUID. `XMLHttpRequest.upload.load`
marca a passagem de uploading para transcribing; não há replay automático de
operação cobrada. Cancelar o cliente interrompe a captura/request e descarta
o resultado; não promete desfazer uma operação já aceita no servidor.
Áudio/transcript não entram em localStorage, IndexedDB, save ou histórico
antes de Agir. A transcrição permanece desativada por default no backend.

## Evidência determinística

- `npm.cmd test`: **18 testes Node verdes**, incluindo fluxo/erro/cancelamento,
  hard stop, permissão pendente, MIME, cleanup de tracks e upload binário com
  CSRF/cookies/operação. Não altera evaluator, expected ou dataset protegido.
- `uv run --no-sync pytest tests/test_eval_frontend.py
  tests/test_frontend_accessibility_contracts.py`: **6 passed**.
- `npm.cmd run build`: TypeScript e build Vite verdes.
- `node node_modules/@playwright/test/cli.js test e2e/voice-input.spec.ts`:
  **11 passed (1.6m)**, em Chromium com viewports 390 e 1440, teclado/touch,
  Axe sem violações serious/critical, edição durante STT, envio explícito,
  permission denied, falha STT, hard stop, background/pagehide, cancelamento,
  unmount, permissão tardia, mudança de sessão e recorder nativo.
- `uv run --no-sync pytest -x --basetemp=C:/tmp/rpg_spec187_final
  -o cache_dir=C:/tmp/rpg_spec187_final_cache`: **2.094 passed, 65 skipped,
  15 deselected**, 5 warnings, **exit 0**, 476,52s. Configuração padrão exclui
  somente os testes live opt-in de contratos/playtest; integrações locais
  condicionadas ao ambiente permanecem skipped conforme seus próprios gates.
  Usa `.venv` Python 3.13 do repositório principal, `PYTHONUTF8=1` e
  `GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=safe.directory`,
  `GIT_CONFIG_VALUE_0=<path exato do clone>` por processo.
- Project Index gerado do source final: **fresh**, 6.172 nós / 15.870 arestas;
  consultado/regerado seletivamente para resolver o gate de freshness.

As tentativas iniciais da suíte completa foram interrompidas por um erro de
ambiente: Git rejeitava o clone por ownership diferente sob execução fora do
sandbox. A exceção `safe.directory` foi limitada ao clone via variáveis de
processo; cache e basetemp usam paths ASCII graváveis. Após essa correção,
**29 testes de memory-context/CI/index passaram**; o teste restante do índice
acusou freshness durante o último ajuste de source e o índice foi regerado.
Nenhum evaluator ou dataset foi modificado para resolver essas falhas.

A fixture Playwright observa corpo binário, MIME e headers. Como a interceptação
segura o progresso da rede até `fulfill`, o cenário com resposta atrasada emite
o evento de upload concluído depois de receber o corpo; testes Node verificam
separadamente esse contrato. Outro cenário usa **MediaRecorder nativo do
Chromium** com um tom Web Audio, gerando um Blob real e verificando track ended;
apenas a resposta STT é uma fixture, sem chamada a provider.

## Disponibilidade de smoke manual

Não houve operador para um smoke manual com fala humana nesta execução,
nem dispositivo Android para teste. O áudio manual curto, condicionado à
disponibilidade pela spec, não foi realizado. O teste nativo usa um tom
sintético e não mede precisão pt-BR.
Chrome/Chromium é o navegador executado; compatibilidade física Safari/iOS e
Android permanece dependente de testes nesses dispositivos. Nenhuma chamada
paga, recarga de provider ou ativação comercial foi feita nesta tarefa.

## Modelo

Executor Sol High substituiu Terra High com autorização explícita do usuário
em 12/10/2026 após `handoffs/SPEC-187-Terra-review.md`. Uso de tier superior para
implementação bounded registrado como custo não otimizado. A spec não exige
review independente; não é declarada uma revisão de modelo inexistente.
