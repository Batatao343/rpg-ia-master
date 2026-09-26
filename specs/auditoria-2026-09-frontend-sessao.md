# SPEC — Sessão frontend, histórico e retrato de ponta a ponta

> **Status:** `done`
> **Criada:** 2026-09-22 · **Atualizada:** 2026-09-26
> **Aprovação:** usuário pediu “transforma tudo em specs e começa a executar”.
> **Depende de:** operacoes-turno para recuperação durável; efeitos-transacionais para arte
> **Desbloqueia:** fechamento da auditoria de consistência e frontend.

## 1. Contexto & Objetivo

SSE omite CSRF; refresh existe só no backend; novo UUID após tentativa manual perde identidade da ação. Abrir save mostra só última mensagem. Retrato é encomendado sem polling/exibição. Botão Nova pode mudar de tela durante operação.

## 2. Requisitos

- **R1** — POST/SSE compartilham headers/credentials/erros tipados. Refresh em 401 é single-flight e limitado a uma repetição; falha encaminha a login, preservando rascunho.
- **R2** — Persistir operação pendente antes de enviar (game_id, operation_id, payload, request_hash, created_at). Retry/reload reutiliza ID e consulta resultado; nunca reenviar automaticamente operação paga incerta com ID novo.
- **R3** — Resposta atrasada não altera campanha atual: session generation token e cancelamento da apresentação. Troca/logout não perde resultado que o servidor já confirmou.
- **R4** — Retomar histórico paginado por mensagens/turnos, deduplicado por identidade e epoch; restore remove linha do tempo desfeita. Não apresentar só a última fala como histórico completo.
- **R5** — Retrato: status → polling limitado/backoff → asset autorizado → HUD/ampliação. Estados pending/ready/failed/rejected/disabled claros; nenhuma regeneração automática.
- **R6** — Contratos de UI usam estado canônico para tipo de mensagem/erro/recibo, não heurística por emoji ou aspas. Modais, foco e teclado acessíveis.

### Fora de escopo

Deploy, migração de dados reais, nova campanha paga e mudança de provider. Implementar Python para domínio/infra; TypeScript apenas para interface.

## 3. Design técnico

web/src/api.ts: HttpError(status, code, detail), helper de headers e refresh; hooks useGameSession/usePendingOperation/useGeneratedPortrait (apresentação necessariamente TS). Python fornece GET de status de operação escopado e histórico paginado, além do status de arte já existente. Validar schema de estado persistido do cliente, limpar tokens/rascunhos por usuário no logout. Nenhum token de acesso em localStorage; no cliente somente cookies HttpOnly e identificadores não secretos. API do retrato deve retornar URLs assinadas renováveis, sem prompt privado. Schema de histórico: {entries:[{id:str,turn:int,epoch:int,role:str,text:str}], next_cursor:str|null}.

## 4. Plano passo a passo

1. Testes cliente offline com fetch falso: CSRF SSE, 401 concorrente, retry de ID, status terminal e resposta tardia.
2. Rotas Python: ownership/histórico/paginação/operação, sem expor memória privada.
3. Browser local autenticado: login → ação SSE → reload → histórico → retrato falso ready.
4. Falhas de rede/expiração e acessibilidade; suite/build verdes.

## 5. Critérios de aceite

- [x] R1–R6 implementados com testes.
- [x] Smoke browser autenticado desktop/mobile e stack local verdes.
- [x] Retrato pronto realmente aparece; nenhum custo automático extra.

## 6. Smoke test com LLM real / integração aplicável

Gerador de imagem e narrador falsos; autenticação/API/browser reais locais. Smoke pago de qualidade de arte pertence à Fase 8B, não a esta integração.

## 7. Riscos & compatibilidade

Não confundir desconectar cliente com cancelar execução durável. Histórico contém dados do jogador; owner obrigatório. Evitar nova biblioteca de estado até necessidade demonstrada.

## Execução — 26/09 (prevalece sobre as pendências históricas)

Achado visual adicional: botão fixo de logout sobrepõe Ficha/Nova no viewport
390 px. Corrigir posicionamento e adicionar asserção de sobreposição; o teste
de ausência de overflow não detecta esta classe de falha.

HTTP/SSE com CSRF, cookies e refresh single-flight; operação persistida antes do envio; geração de sessão invalida callbacks atrasados; histórico paginado e epoch; retrato com polling/backoff, URL assinada e ampliação. Cinco testes Node verdes. Browser autenticado 390/1440 confirmou cadastro, diálogo/foco, retrato sintético via Storage real local, SSE, replay e histórico após reload. Correção adicional de save/load do ledger/orçamento de arte e migração do kind art. Ainda faltam fault injections no navegador: desconexão/expiração durante resposta e troca de campanha com resposta atrasada. Não afirmar cobertura completa de R1–R6 pelo caminho feliz.

Continuação: logout movido para o topo, com teste de ausência de sobreposição;
banner de operação pendente afastado do input. Browser 390/1440 passou com perda
das confirmações SSE e POST após commit, retomada por recibo e histórico único.
Novo guard revalida sessão após await de getState no replay. Teste de refresh
401 acrescentado ao gate. Fault injection segura uma resposta de estado da
campanha anterior, expira a autenticação, abre outra campanha e só então libera
a resposta: o game_id atual permanece o novo. Gate final: **25 passed** em
390/1440, com screenshots e JSON de execução; nenhum provider pago.
