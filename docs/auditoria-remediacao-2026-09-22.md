# Auditoria de 22/09 — plano aprovado de remediação

Nove specs originadas da varredura de backend/frontend. São complementos das specs anteriores, não substituem nem encerram seus gates pendentes.

**Atualização 26/09:** todas as nove foram iniciadas; contexto autenticado está
`done` e oito seguem `in-progress`. O lote de 23/09 abaixo é histórico.
[Evidências atuais e lacunas por spec](auditoria-execucao-2026-09-26.md).

## Ordem e cobertura

1. [Artes integrais, cards e visualização ampliada](../specs/auditoria-2026-09-artes-enquadramento.md)
2. [Contrato compartilhado de evidências narrativas](../specs/auditoria-2026-09-consistencia-narrativa.md)
3. [Recompensas elegíveis e contagem canônica](../specs/auditoria-2026-09-recompensas-recibos.md)
4. [Identidade e correlação na aquisição paralela de contexto](../specs/auditoria-2026-09-contexto-autenticado.md)
5. [Operações idempotentes e execução unificada do turno](../specs/auditoria-2026-09-operacoes-turno.md)
6. [Memória, arte e checkpoint atômicos ao turno](../specs/auditoria-2026-09-efeitos-transacionais.md)
7. [Renovação de leases e recuperação segura de workers](../specs/auditoria-2026-09-leases-workers.md)
8. [Sessão frontend, histórico e retrato de ponta a ponta](../specs/auditoria-2026-09-frontend-sessao.md)
9. [Gates de integração e regressões da auditoria](../specs/auditoria-2026-09-gates-integracao.md)

Primeiro lote: enquadramento CSS, identidade no contexto, elegibilidade de XP/unique e contagem do recibo. Demais mudanças seguem em lotes próprios, com gates explícitos. Nenhuma autorização de commit/push/deploy inferida.

As regressões narrativas de morte/local/resumo/crônica pertencem à spec de evidências; autenticação, histórico e retratos à spec de sessão frontend; replay/claim/executor à spec de operações; rollback/efeitos à transacional; TTL/worker à de leases. Assim nenhum achado do relatório fica sem destino.

## Evidência da auditoria (baseline, não validação dos fixes)

- 1721 passed, 16 skipped, 14 deselected; Ruff/build/conteúdo verdes.
- Raças/classes: imagens verticais em caixas 4:3 com cover; transbordamento de 16 px e legenda duplicada confirmados no browser.
- Contexto com principal: sequencial ok, paralelo Unauthorized.
- Storyteller: 150 XP sem plano; mesmo unique duas vezes.
- Recibo: segunda entrada do mesmo ID não aparece no ganho.
- Morte falsa rejeitada no ledger e mantida no resumo/crônica.
- Replay valida tarde; retry de morte não consulta recibo; rejeição deixa claim sem liberação.
- Riscos de transação/lease detectados no código; testes de crash no Postgres ainda necessários.

## Gates e custos

Testes locais não aguardam matriz longa. Não chamar LLM/geração paga neste lote. Specs com integração LLM permanecem in-progress até smoke autorizado; demais exigem integração real local apropriada. Nunca marcar gate pendente como concluído por mock.

## Primeiro lote executado — 23/09

Três specs em `in-progress`: artes, recompensas/recibos e contexto autenticado. As outras seis estão `approved`, ainda sem implementação neste lote.

- Artes: contain e proporção vertical nos cards, correção de margem e legenda duplicada. Ampliação, recuperação de erro e sizes ainda pendentes.
- Recompensas: XP apenas em beat corrente elegível; unique não se duplica por nome/ID no mesmo lote; recibo soma entradas repetidas. Smoke de grafo dedicado e provider real pendentes.
- Contexto: principal e correlação preservados por cópia independente de ContextVars; isolamento entre leitores e usuários. Integração Postgres autenticada pendente.

Testes escritos antes dos fixes reproduziram **19 falhas** nos contratos de backend e **duas falhas** visuais. Depois: **57 testes focados passaram**; suíte completa **1743 passed, 18 skipped, 14 deselected** em 308,01 s. Foram adicionados **22 testes offline e dois visuais opt-in**. Os visuais passaram separadamente em Chromium, 390/1440 px; smoke manual da aplicação também confirmou raças/classes com arquivos reais e API mock isolada, sem erros no console. Ruff, build Vite/TypeScript e lint de conteúdo passaram (conteúdo: zero erros/avisos). Aviso existente de descontinuação do wrapper FAISS permanece.

Próximos lotes: concluir R3–R5 visuais; contrato de evidência compartilhado para narração/resumo/crônica; operações e efeitos transacionais; leases; sessão frontend e gates de integração. A ordem deve respeitar as dependências de cada spec. As onze specs antigas com gates reais continuam pendentes; nenhuma foi fechada por esta auditoria. Sem chamadas pagas, commit, push ou deploy neste lote.
