# SPEC-187 — handoff para executor Terra High

**12/10/2026 — substituição autorizada explicitamente pelo usuário:** executor
Sol High no lugar de Terra High. O bloqueio de modelo abaixo é histórico;
implementação/evidência em `docs/spec187/README.md`. A spec não exige reviewer
independente. Uso de tier superior para execução bounded registrado como custo
não otimizado; nenhuma recarga de provider autorizada ou executada.

**Fechamento:** SPEC-187 `done`; 18 Node, 11 browser e suíte Python completa
2.094 passed / 65 skipped / 15 deselected verdes. Evidência acima.

## Registro histórico do bloqueio

SPEC-187 exige executor **Terra / High**. Terra High não está disponível entre
os modelos de execução desta sessão e a substituição é proibida sem aprovação
explícita do usuário. Este handoff registra o inventário Luna permitido pela
spec; nenhuma implementação foi feita.

## Dependência e contexto

- SPEC-186 está `done` em `d2c687c`.
- SPEC-187 está `approved` e cobre entrada de voz web/mobile, transcript
  editável e adapter substituível por implementação nativa somente se um teste
  Android futuro exigir.
- O endpoint STT é `POST /account/transcriptions`; transcript é efêmero e não
  deve chamar `/game/action` automaticamente.

## Seams exatos

- `web/src/components/PlayScreen.tsx`: `input` em `useState`, `submit()` faz
  trim/clear e chama `onAction`; o formulário `.actionbar` atualmente contém
  apenas input textual e `Agir`. Não há recorder, visibility ou cleanup hoje.
- `web/src/App.tsx`: `handleAction` é o único fluxo de envio; mantém pending
  operation, fallback SSE/POST e guards por `session.current`. STT deve somente
  atualizar o composer e preservar o Send explícito.
- `web/src/api.ts` e `web/src/http.ts`: `http()` assume JSON para mutações,
  inclui credentials e CSRF; upload binário precisa de função raw dedicada,
  com `X-Operation-Id` UUID, `Content-Type` de áudio e resposta JSON.
- `api.py:1652`: endpoint exige auth/CSRF, limite 8 MiB, timeout de stream 15 s,
  rate limit 5/min e devolve `{operation_id, text, billing_status}`.
- `services/speech_to_text.py`: MIME aceitos são `audio/wav`, `audio/x-wav`,
  `audio/webm`, `audio/ogg`, `audio/mp4`; duração decodificada máxima 60 s;
  WebM/Ogg/MP4 dependem de ffmpeg server-side.
- `web/e2e/fixtures.ts`: `DeterministicBackend` intercepta `/account/*`, guarda
  requests e permite delays/aborts. É o seam para `/account/transcriptions`,
  `navigator.mediaDevices.getUserMedia` e fake `MediaRecorder` determinístico.
- `web/e2e/critical-journeys.spec.ts`: helpers `openGame`, `submitAction`,
  `assertA11y`; já cobre teclado, Axe, overflow e viewports 320/390/768/1440.
- `web/e2e/account.spec.ts`: matriz existente em 390/1440 e Axe serious/critical.
- `web/playwright.config.ts`: Chromium, `pt-BR`, reduced motion, sem retries.
- `web/src/styles.css:623`: `.actionbar`; `:994`: regras mobile, sticky actionbar,
  safe-area inset e input 16px para evitar zoom iOS.

## Matriz browser/a11y recomendada

| Caso | Matriz | Oráculo |
| --- | --- | --- |
| Idle/record/stop | 390 e 1440; mouse e touch | estados idle/recording/uploading/transcribing/error, contador, Stop e label acessível |
| Stop → transcript | 390 e 1440 | input recebe texto editável; nenhuma chamada `/game/action` antes de Send |
| Edição/Send | teclado e touch | texto editado é o enviado exatamente uma vez; Enter só envia texto não vazio |
| Permission denied | 390 e 1440 | alerta claro; input textual continua habilitado |
| STT failure | 390 e 1440 | erro não envia ação e não perde texto já digitado/transcript |
| Hard stop | fake timer em 60 s | recorder para uma vez; upload único; sem duplicate stop |
| Background | `visibilitychange(hidden)` e `pagehide` | captura para e todas as tracks são liberadas; sem upload/send inadvertido |
| Unmount | navegação/reload/unmount | recorder/tracks liberados; callbacks tardios não alteram componente desmontado |
| Keyboard | Tab, Enter, Space | ordem e foco visíveis; Record/Stop operáveis sem mouse |
| Mobile | 390 px | sem overlap com actionbar/safe-area e sem overflow horizontal |
| A11y | 390 e 1440 | Axe sem violações serious/critical; live status/error anunciado |

## MIME e adapter

O adapter deve escolher MIME por `MediaRecorder.isTypeSupported()` e preservar
o `Blob.type`; não presumir um único formato entre navegadores. WebM/Ogg/MP4
com parâmetros de codec são aceitos porque o backend canonicaliza o MIME antes
da validação. O fake deve cobrir formato aceito, formato não suportado e
ausência de `MediaRecorder`/`getUserMedia`. Não introduzir dependência nativa
Capacitor antes da SPEC-193.

## Menor gate determinístico sugerido

1. `cd web && npm run build`.
2. `cd web && npm run test`.
3. `cd web && npx playwright test e2e/voice-input.spec.ts` (ou os casos
   SPEC-187 adicionados ao journey), com 390 e 1440, fake recorder e route stub.
4. `uv run pytest tests/test_eval_frontend.py tests/test_frontend_accessibility_contracts.py -q`.

Somente ampliar para `uv run pytest` após os gates focados verdes. Long-runs e
chamadas STT reais não são necessários para esta spec.
