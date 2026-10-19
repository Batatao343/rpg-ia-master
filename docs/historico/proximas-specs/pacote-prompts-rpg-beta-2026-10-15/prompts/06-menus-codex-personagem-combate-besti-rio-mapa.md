# PROMPT 06 — Telas contextuais completas, não HUDs pequenos

## Objetivo
Elaborar spec de telas de consulta reais, que podem ocupar 50% ou 100% do workspace, sem trocar o chat por login/roteador.

## Menu a menu
- **Codex:** dossiês NPC com fatos conhecidos, suspeitas, eventos relevantes, relação atual, o que NPC sabe/acredita sobre jogador com visibilidade **filtrada**, encontros importantes; não repetir últimos logs.
- **Personagem:** atributos/recursos/equipamento/ficha, escolhas, histórico de evolução, arte do protagonista.
- **Combate fora de combate:** coleção, deck/preparação e passivas/reações se o backend permitir; ações só onde regras autorizam.
- **Bestiário:** encontros, ilustrações, descobertas graduais, níveis de certeza, não revelar desconhecidos.
- **Mapa:** regiões e interiores conhecidos, fog of war, viagens/risco/distância conforme estado canônico.

## Integração de imagens
Mapear assets do repo por ID canônico: cena, retrato de NPC, criatura, carta, região, personagem. Carregamento progressivo e fallback; CDN/assets assinados podem expirar; testes no momento do reload; não inferir presença de imagens que não foram geradas.

## Aceite
Cada menu usável como tela inteira; no split não exigir scroll aninhado excessivo; informações corretas após turno, reload, mudança de save e atualização assíncrona. Documentar `last_updated/version` sem tratar projeção desatualizada como fato inexistente.

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
