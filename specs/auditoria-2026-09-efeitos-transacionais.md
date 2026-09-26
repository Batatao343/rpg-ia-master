# SPEC — Memória, arte e checkpoint atômicos ao turno

> **Status:** `done`
> **Criada:** 2026-09-22 · **Atualizada:** 2026-09-26
> **Aprovação:** usuário pediu “transforma tudo em specs e começa a executar”.
> **Depende de:** auditoria-2026-09-operacoes-turno
> **Desbloqueia:** fechamento da auditoria de consistência e frontend.

## 1. Contexto & Objetivo

rag.stage grava fato e job em transação independente antes do save; arte também é enfileirada antes do commit. discard_after existe sem integração ao restore. MemoryIntentCollector existe, mas não é usado no caminho de execução.

## 2. Requisitos

- **R1** — Em runtime durável, estado/eventos/recibo/intents de memória e jobs de arte confirmam na mesma transação.
- **R2** — Falha antes de commit deixa zero efeitos visíveis e zero chamada paga; worker só recebe intenções confirmadas.
- **R3** — Memórias recebem timeline_epoch e commit_version reais, com proveniência normalizada (mapear memory_* para colunas sem perder metadados).
- **R4** — Restore invalida fatos/derivados posteriores ao checkpoint e cancela jobs obsoletos atomicamente; fatos anteriores permanecem acessíveis.
- **R5** — Legacy não finge transação distribuída: estágio local e compensação testada, ou limitação explícita. Arte não deve bloquear confirmação de turno por indisponibilidade do provider.

### Fora de escopo

Deploy, migração de dados reais, nova campanha paga e mudança de provider. Implementar Python para domínio/infra; TypeScript apenas para interface.

## 3. Design técnico

Ligar MemoryIntentCollector à unidade de trabalho do executor; gravação SQL com conexão recebida, sem abrir transação interna. Port MemoryWriteIntent existente recebe metadados canônicos; fila de art intent inclui generation_id, game_id, owner_id, timeline_epoch e chave de dedupe. PostgresTurnCoordinator confirma intents junto com commit_game; restaurador utiliza cutoff do checkpoint, sem operações em diretórios FAISS para perfil Postgres. Ler REFERENCE e skills de banco antes de implementar schema; gerar migrações pelo fluxo do projeto.

## 4. Plano passo a passo

1. tests/test_turn_effects_atomicity.py: falhas em cada fronteira com doubles e assertions de efeitos.
2. Implementar collector/outbox e nomes de metadados.
3. tests/test_restore_pgvector_local.py: commit, checkpoint, novos fatos, restore, worker atrasado.
4. Fault injection local: queda entre INSERT e commit, replay e retry de job.

## 5. Critérios de aceite

- [x] R1–R5 demonstrados, não apenas métodos isolados.
- [x] Offline + Postgres real local verdes; saves legacy preservados.
- [x] Zero chamada paga nos testes; arte falsa verifica no-call em rollback.

## 6. Smoke test com LLM real / integração aplicável

Gate é stack local com gerador falso, não provider. Após testes de crash/rollback, não exige campanha longa para aceite transacional.

## 7. Riscos & compatibilidade

Migração pode precisar tratar commit_version NULL legado conservadoramente sem excluir dados válidos. Reservas de arte antigas não são apagadas sem reconciliação. Nenhum deploy externo.

## Execução — 26/09 (prevalece sobre as pendências históricas)

TurnEffects coleta memória e reserva/enfileiramento de arte; commit_game/commit_create publicam junto do estado/recibo. Metadados memory_* normalizados, inclusive IDs canônicos. Restore invalida memória posterior e jobs/arte obsoletos. Digest e documentos de crônica agora confirmam juntos, com epoch e fence. Fault injection Postgres confirmou rollback de memória/job; gate browser confirmou reserva de arte durável. Ainda falta injeção de falha específica após INSERT de arte e crash de processo nas fronteiras. Legacy/FAISS não oferece transação distribuída. Correção adicional: ledger e orçamento por arco preservados em GameState e save/load, com regressão curta.

Continuação: processo filho morto após INSERT de arte dentro de commit_game;
Postgres preservou versão/estado anterior e zero geração/turno/checkpoint
publicados. Teste em `test_process_crash_local.py`, sem provider. Memória/job
continuam cobertos por rollback/restore no gate local. Último gate: 24 passed.
