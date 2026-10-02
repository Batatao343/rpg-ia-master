# Auditoria — execução e evidências de 26/09

As nove specs estão `done`. Em 28/09, narrativa e recompensas passaram o
contrato DeepSeek dirigido: beat elegível concedeu exatamente 150 XP e o
`last_turn_outcome` confirmou o mesmo delta. STORY/NPC/LOOT/memória também
foram exercitados na matriz B real sem alegação crítica inválida. Evidência:
[matriz B](playtest-matriz-b-2026-09-28.md).

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

- `uv run pytest`: **1800 passed, 35 skipped, 15 deselected**, 285,46 s,
  após o ajuste final de lock; um aviso existente de descontinuação FAISS.
- `npm.cmd test`: **5 passed** (CSRF/cookies, refresh concorrente, erro de
  refresh, identidade da operação após reload e falha de armazenamento).
- `npm.cmd run build`: TypeScript/Vite verdes, 461 módulos.
- `uv run ruff check .`: verde; validador de conteúdo: zero erros/avisos.
- `uv run python scripts/audit_local_gate.py`: **25 passed, zero skipped**,
  82,03 s, após fault injection e correção do deadlock.
- GitHub `validate` do commit funcional `c7eb25c`: **success**, run
  `36263493848`, 1m01s (pytest, Node, build, Ruff e conteúdo).
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
| Artes | Concluída: troca de asset/cenário após falha passou no browser |
| Narrativa | Contrato real curto (local/unificação/corpus concluídos) |
| Recompensas | Contrato real curto (grafo/finalizer/save concluídos) |
| Contexto | Concluída: isolamento real local comprovado |
| Operações | Concluída: matriz, desconexão e concorrência na API verdes |
| Efeitos transacionais | Concluída: INSERT de arte/crash/rollback verdes |
| Leases | Concluída: kill/restart e reconciliação documentada |
| Frontend sessão | Concluída: rede/401/troca durante resposta verdes |
| Gates | Concluída: CI infra 36263717580 verde e promovido a push/PR |

O workflow `audit-local.yml` foi manual até sua primeira certificação remota.
Após o run remoto verde, foi promovido a gate automático de `push` e PR da
`main`. Antes disso, o usuário autorizou commit e
push de todas as alterações do projeto para `main`; publicação Git não é deploy
da aplicação. A suíte de cliente foi
adicionada ao workflow obrigatório existente. Execução local usa recursos do
computador, sem contratação cloud ou chamada paga. GitHub Actions tem suas
próprias quotas: não se promete custo remoto zero.

O contrato curto DeepSeek foi preparado com rota única, sem fallback ou imagem,
e limite técnico de três tentativas estruturadas. A plataforma recusou iniciar
o request externo sem autorização específica para o envio do prompt/estado
sintético ao DeepSeek e sem um teto de custo garantido pelo provider. Portanto
zero request/custo foi realizado; esse gate não foi marcado como concluído.

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
