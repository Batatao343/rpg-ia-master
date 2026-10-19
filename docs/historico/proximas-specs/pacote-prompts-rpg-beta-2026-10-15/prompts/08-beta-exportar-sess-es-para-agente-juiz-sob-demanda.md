# PROMPT 08 — Telemetria de sessão e pacote de auditoria sob demanda

## Decisão fechada
**Não criar painel de replay humano nem auditor noturno.** Capturar dados de jogo e exportar **sob demanda** uma pasta/ZIP autossuficiente que dono possa abrir no Codex/Claude usando os créditos próprios. A exportação deve incluir instrução de auditoria local ou externa, sem chamar automaticamente modelo caro.

## Investigação
Reusar `playtest/telemetry.py`, saves, session events, logs, AI decisions, status dos agentes, event_log, action_id, traces de falha e persistência. Identificar privacidade/retention e redaction. Registrar, sob controles adequados, prompts/respostas ou **referências versionadas ao contexto** quando necessários para julgar leakage, sem duplicar gigantescopias com custo/storage injustificado.

## Contrato candidato
`manifest.json` com build SHA/schema hash/instância, `sessions/*.jsonl` com turnos ordenados e IDs de correlação, `state_deltas.jsonl`, `knowledge_visibility.jsonl`, `errors.jsonl`, `timings.jsonl`, `AUDITOR_PROMPT.md`, `README_SCHEMA.md`; incluir texto do jogador e resposta produzida se consentidos e relevantes. Distinguir **contexto visto pelo NPC** de fatos só conhecidos pelo engine; privacidade do jogador beta, política de autorização, segregação cross-account, restrição de dados pessoais/segredos, exclusão de áudio raw por padrão, expurgo/retention e custo de armazenamento.

## Saída do auditor (instruções, não execução)
`findings.json`/`report.md`: severidade, categoria, `session_id/turn_id`, evidência citável, esperado vs observado, hipótese, confiança, sugestão de eval/spec; também agrupar bugs e falsos positivos. Nunca usar judge como gate mecânico onde há oráculo determinístico.

### Contrato obrigatório deste prompt
- **Missão: investigar e escrever uma SPEC em `draft`; NÃO implementar código de produto nesta execução.** Não abrir PR de implementação, não mudar runtime, nem afirmar testes que não rodaram.
- Antes de atuar, ler `AGENTS.md`, `ESTADO_ATUAL.md`, `ROADMAP.md`, `specs/index.yaml`, `specs/TEMPLATE.md`, `docs/evals-plan-v4/08_CONTRATO_CODING_AGENT.md` e `12_MODEL_EXECUTION_POLICY.md`. Fonte canônica é o source do HEAD, não este pacote.
- Verificar specs existentes e suas dependências; **NÃO reutilizar IDs 176–198** nem assumir que SPEC-199 continua livre. Obter próximo número não usado no HEAD, registrar em `specs/index.yaml` só quando apropriado. Não duplicar SPECS já `done`/`approved`.
- Toda a proposta deve distinguir **fato observado no código**, **decisão de produto fechada**, **hipótese técnica** e **recomendação**. Citar paths/símbolos reais auditados e lacunas.
- A spec deve conter escopo/não-escopo, contratos de dados e de UI, state ownership, degradação/fallback, etapas, risco de migração/saves, criterios de aceite observáveis, comandos de testes mínimos, evidência requerida, dependências e pontos de decisão genuínos.
- Respeitar integridade de eval: uma tarefa define/fixa novos avaliadores; outra otimiza produto. Não editar evaluator, expected ou dataset protegido na mesma tarefa de implementação; quando precisar de novos evals, registrar `EVAL_AUTHORING_REQUIRED` e um handoff separado.
- Sem provider real pago, campanhas longas ou experimentos 100/200 turnos por padrão. Ações com custo exigem autorização e teto explícitos. Não consultar Project Index sem hipótese cross-file específica e verificação no source.
- Material em `design-html/` é **referência de comportamento, não especificação mecânica**. Danos, cartas extras, retratos e falas fictícias nesses HTMLs são mock; as regras vêm do repo.
- Produzir, ao final, resumo de até uma página: diagnóstico, o que a spec cobre, dependências, riscos, como aceitar/rejeitar. Parar em `draft` e aguardar aprovação da spec; não pedir aprovação para cada microefeito.
