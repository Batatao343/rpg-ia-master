# Auditoria — execução e evidências de 26/09

As nove specs têm implementação iniciada. Contexto autenticado está `done`;
as outras oito seguem `in-progress`, com lacunas específicas registradas nelas.
Não confundir código implementado com todos os critérios de aceite certificados.

## Alterações verificadas

- Narração: evidência compartilhada para mensagem/resumo/crônica/contexto,
  sem promover propostas pendentes a fatos; auditoria limitada persistida.
- Operações: caminho comum POST/SSE, replay vinculado ao pedido original,
  liberação de claim em erro e renovação da reserva enquanto executa.
- Persistência: memória e intenções de arte na transação do turno; restore
  invalida derivados posteriores; crônica confirma digest e memória juntos.
- Workers: reserva serial de um job, heartbeat, fencing na publicação,
  nenhuma repetição automática da geração quando o resultado é incerto.
- Frontend: CSRF no streaming, refresh single-flight, operação pendente
  persistida, histórico paginado, descarte de respostas de outra sessão,
  ampliação acessível e consulta/exibição do retrato com URL assinada.

O teste de retrato completo encontrou dois bugs que os testes isolados não
mostravam: `art` faltava no CHECK de operações; ledger/orçamento de arte não
atravessavam GameState/save/load. Ambos foram corrigidos. A migração
`20260926132501_audit_art_operation_kind.sql` foi criada pela CLI e aplicada
apenas na stack local, sem reset nem remoção de dados. Security advisors no
nível error: zero achados. Políticas de acesso não foram alteradas.

## Evidências e comandos

- `uv run pytest`: **1776 passed, 26 skipped, 14 deselected**, 261,64 s,
  após o ajuste de persistência; um aviso existente de descontinuação FAISS.
- `npm.cmd test`: **5 passed** (CSRF/cookies, refresh concorrente, erro de
  refresh, identidade da operação após reload e falha de armazenamento).
- `npm.cmd run build`: TypeScript/Vite verdes, 461 módulos.
- `uv run ruff check .`: verde; validador de conteúdo: zero erros/avisos.
- `uv run python scripts/audit_local_gate.py`: **16 passed, zero skipped**,
  48,75 s, depois das correções de migração e persistência de arte.
- JUnit local: `readiness_artifacts/audit/results.xml` (gitignored).

O gate integrado cobre Postgres/pgvector, contexto serial/paralelo/async,
rollback e restore, lease >2 TTL, segundo worker, publicação com token antigo,
crônica, enquadramento 390/1440 e navegador autenticado. O retrato é gerado por
FakeImageGenerator, mas upload/assinatura/consulta/exibição usam a infraestrutura
local real. POST após SSE não duplica o histórico; payload divergente retorna 409.
Os blobs sintéticos desses testes são removidos ao final; contas sintéticas
permanecem apenas na autenticação local.

## Aceites ainda abertos

| Spec | Falta para encerramento |
| --- | --- |
| Artes | Falha de imagem seguida de troca de asset/cenário no browser |
| Narrativa | Unificação dos guards legados de memória, corpus ampliado, grafo/save/load e contrato real curto |
| Recompensas | Smoke dirigido de grafo e contrato real curto |
| Contexto | Concluída: isolamento real local comprovado |
| Operações | Morte/equip/levelup e desconexão/concorrência na API |
| Efeitos transacionais | Falha específica na reserva de arte e crash nas fronteiras |
| Leases | Kill/restart de processo e procedimento de reconciliação |
| Frontend sessão | Rede/expiração/troca de campanha durante resposta |
| Gates | Primeiro CI remoto, promoção de infra a obrigatório e artifacts completos |

O workflow `audit-local.yml` é manual até sua primeira certificação remota.
Não foi disparado durante a validação. Depois, o usuário autorizou commit e
push de todas as alterações do projeto para `main`; publicação Git não é deploy
da aplicação. A suíte de cliente foi
adicionada ao workflow obrigatório existente. Execução local usa recursos do
computador, sem contratação cloud ou chamada paga. GitHub Actions tem suas
próprias quotas: não se promete custo remoto zero.

Revisão das capturas finais: em 390 px o botão fixo de logout se sobrepõe aos
controles do topo. Correção de layout e teste de sobreposição permanecem na
spec frontend-sessao. O screenshot desktop capturou o modal de level-up; o
retrato foi validado por presença/dimensões naturais no DOM, não por essa captura.

Legacy mantém suas limitações: FAISS/arquivos não são uma transação distribuída
e o ledger de replay é limitado. Os onze gates reais anteriores e a matriz B
não foram encerrados por esta auditoria. Nenhuma campanha LLM real está rodando.

## Retomada

Ler os adendos de 26/09 nas nove specs. Para a stack já provisionada:
`uv run python scripts/audit_local_gate.py` inicia API mock isolada em 8767,
executa os testes e encerra somente o processo filho. Não iniciar worker de
imagem real. Smoke pago segue pendente de autorização de orçamento.
