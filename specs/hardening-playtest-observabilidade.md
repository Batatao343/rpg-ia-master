# SPEC — Hardening de observabilidade do playtest

> **Status:** `done` (2026-08-02)
> **Criada:** 2026-07-25 · **Atualizada:** 2026-08-02
> **Depende de:** `fix-playtest-decisoes-atomicas`
> **Desbloqueia:** aceite verificável do `conflito-13`

---

## 1. Contexto & Objetivo

O smoke terminou verde apesar de omitir criação/abertura, tentativas LLM falhas,
erros FAISS e divergência entre ação e efeito. Exceções de invariantes são
engolidas, morte é inferida por HP zero, o primeiro combate via storyteller não
é contado e a CLI retorna sucesso para execução abortada.

## 2. Requisitos

- **R1 — Tentativas LLM.** Telemetria registra por candidato status
  `success|build_error|invoke_error|stream_error`, tentativa de rede, latência,
  fallback e erro sanitizado; nunca prompt, resposta ou chave.
- **R2 — Startup e orçamento.** Criação/abertura ficam em
  `startup_llm_events`; tentativas de rede falhas contam no teto e no lower bound
  de custo. Falha de build não conta como request.
- **R3 — Execução real.** Cada turno registra `nodes_executed`,
  `combat_executed`, início/fim/rodada e resultado canônico, inclusive combate
  iniciado dentro do storyteller.
- **R4 — Invariantes fail-loud.** Exceção vira violação
  `invariant.crash`/`invariant.runner_crash` severity `error`, com mensagem e
  detalhes preservados no JSONL/summary/report.
- **R5 — Morte canônica.** Primeira/última morte vêm de `deaths_log`,
  `death_pending`/`game_over`; Vitalidade zero viva não conta como morte.
- **R6 — Run completa.** Manifesto registra perfis/turnos esperados e status.
  CLI retorna zero somente para execução completa, sem errors, abortos ou
  violações `error`.
- **R7 — Invariantes novas.** Cobrir ausência de progresso mecânico, ação versus
  efeito, aliases vitais, sentinelas, erro de persistência RAG e lifecycle de
  resumo.
- **R8 — RAG/embeddings.** Operações e falhas são observáveis separadamente de
  requests LLM; batching opaco não é apresentado como número de HTTP requests.
- **R9 — Integridade dos artefatos.** Completude exige `summary.json` e JSONL
  parseáveis, contagem exata de linhas/turnos e coerência com manifesto. Arquivo
  apenas existente, summary corrompido ou run legado sem manifesto não serve
  como aceite.
- **R10 — Prova de execução real.** `mock=false` não basta: run `--real` exige
  ao menos um invoke de rede bem-sucedido por campanha. Desligar invariantes
  torna a execução diagnóstica e impede status formal verde. O JSONL liga cada
  campanha ao save final e expõe reações/Ferimentos necessários para auditar a
  vertical.
- **R11 — Semântica RAG no modo offline.** O playtest mock não acessa rede nem
  FAISS, mas simula cada write RAG válido como commit bem-sucedido e observável
  (`provider=offline-simulated`, `path=memory://playtest/...`). O backend é
  efêmero por campanha, cobre aliases já importados por archivist/NPC/world
  simulator, restaura todos os símbolos ao sair e é no-op em `--real`.
- **R12 — Contadores bounded e tática.** Métricas de rejeição comparam
  identidades/conteúdo, não apenas o tamanho do buffer limitado a 100.
  `combat.last_tactics` é preservado no node observation/JSONL para provar que
  o perfil fechado realmente executou proteção, controle, fuga ou suporte.
- **R13 — Resultado por turno.** `resolved_action` vem apenas do update do
  `combat_agent` executado naquele invoke. Resultado persistido no estado nunca
  é repetido em turnos narrativos posteriores.

### Fora de escopo

- Capturar tokens que o provider não informa.
- Tornar custo estimado uma fatura exata.

## 3. Design técnico

`llm_setup.py` mantém o hook legado de sucesso e adiciona evento estruturado por
tentativa. `rag.py` expõe hook de operação. `CampaignResult` e `TurnRecord`
ganham startup, nós, detalhes de violações, estados vitais/terminais e ação
canônica. `run.meta.json` torna execução parcial detectável.

No modo mock, `_offline_embeddings` instala um backend de escrita em memória
por entrada no context manager. Leituras continuam sem embeddings; writes de
sessão/NPC preservam o contrato booleano e emitem o mesmo evento normalizado do
backend real, sem criar índice. A troca inclui os aliases diretos já resolvidos
em `agents.archivist`, `agents.npc` e `agents.world_simulator`; o `finally`
restaura as referências originais para campanhas seguintes e para `--real`.

## 4. Plano passo a passo

1. **Testes:** fail→fallback, build skip e startup entram na telemetria/teto.
   Um stream que produz chunk e depois lança emite apenas `stream_error`, nunca
   sucesso antecipado.
2. **Implementação:** hooks e modelo de eventos.
3. **Testes:** exceção de invariante falha; detalhes sobrevivem; morte não usa
   HP; storyteller→combat aparece nos nós.
4. **Implementação:** runner, telemetry, report e invariantes.
5. **Testes:** CLI/manifest falham em erro, aborto, summary ausente ou campanha
   incompleta.
6. **Implementação:** códigos de saída e relatório de completude.
7. **Testes/implementação:** corromper summary/JSONL, truncar linhas, desligar
   invariantes e simular `--real` sem sucesso de rede deve reprovar; save,
   reações e Ferimentos ficam rastreáveis.
8. **Regressão offline:** provar write de sessão/NPC sem FAISS, eventos de
   sucesso, aliases importados, isolamento entre campanhas e ausência da
   cascata `rag.persistence_error` → `summary.lifecycle`.
9. **Regressões bounded:** rejeição nova com buffer 100→100 incrementa a
   métrica; táticas do combat node atravessam JSONL/report.
10. **Regressão temporal:** fuga/ataque anterior + turno sem combat node gera
    `resolved_action={}` na nova linha JSONL.

## 5. Critérios de aceite

- [x] `attempts = successes + failures`; startup real > 0 por campanha.
- [x] Nenhuma exceção de invariante/RAG some.
- [x] Métricas usam nós executados e morte canônica.
- [x] JSONL preserva severity/message/details.
- [x] CLI não produz falso verde.
- [x] 13 perfis × turnos esperados e 13 summaries são verificáveis.
- [x] Artefatos são parseados e coerentes; run real tem prova de rede.
- [x] Run formal exige invariantes e liga JSONL ao save/efeitos do conflito.
- [x] Stream parcial não produz falso sucesso; rejeição em buffer cheio conta.
- [x] JSONL expõe `last_tactics`/ações táticas realmente executadas.
- [x] Ação resolvida antiga não reaparece em turno sem combate.
- [x] Mock simula writes RAG observáveis sem rede/FAISS, não vaza estado entre
  campanhas e não altera `--real`.
- [x] Suíte completa verde.

## 6. Smoke test com LLM real

Rodar sanity com fallback induzido e depois a matriz 13×30. Conferir manifesto,
startup, tentativas falhas/sucesso, RAG, nós, morte e código de saída.

**Evidência (2026-08-02):** a matriz real composta persistiu 13 summaries e
390 turnos, `mock=false`, 1.119 sucessos de rede, 13 tentativas LLM falhas
observáveis e zero erro/violação `error`. O relatório registra também as runs
interrompidas, que não foram aceitas como falso-verde.

## 7. Riscos & compatibilidade

O hook legado permanece para API/testes. Erros são truncados e sanitizados. O
teto pode terminar no máximo o turno já iniciado, explicitado no relatório.

**Desvio encontrado na validação offline (2026-07-25).** A implementação
anterior de `_offline_embeddings` devolvia `None` para embeddings, mas deixava
os writers reais ativos. A run `20260725-135640-889075` acumulou 1.745
`rag.persistence_error`; no `fujao`, 23 `summary.lifecycle` foram uma cascata do
commit RAG artificialmente recusado e do resumo corretamente retido para retry.
Os artefatos ficam como evidência forense, porém essa run não vale como aceite
formal nem como medida desses dois defeitos de produto. Uma nova run formal
offline é necessária após o hardening.
