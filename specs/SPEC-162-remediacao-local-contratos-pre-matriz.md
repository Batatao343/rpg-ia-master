# SPEC — Remediação local dos contratos antes da matriz B

> **Status:** `done` — aceite local em 19/09; gates reais das specs originais permanecem pendentes
> **Criada:** 2026-09-19
> **Aprovação:** usuário aprovou o plano da auditoria de 19/09.

## 1. Objetivo e precedência

Corrigir as lacunas reproduzidas na revisão das onze specs em andamento antes
de consumir outra campanha real. Este adendo refina seus critérios técnicos;
não cancela nem declara cumprido o aceite real da matriz B.

## 2. Contratos aprovados

1. **Ciclo de vida:** recuperação fora de combate é intenção fechada Python,
   nunca uma palavra-chave que libera viagem/saque/ataque. Router e executor
   respeitam a decisão. Espera por socorro usa o descanso canônico, preservando
   restrições ambientais; recuperação de incapacidade tem saída explícita.
2. **Resultado canônico:** marcador textual `[RESULTADO]` não é evidência de
   recibo. O renderer substitui blocos reservados pelo recibo calculado, de
   modo idempotente; negações são reconciliadas por categoria, não por qualquer
   ganho. Não se promete compreensão semântica universal da prosa.
3. **Interações:** métricas de repetição ignoram transições cosméticas inseridas
   pelo motor. Repetir o conteúdo continua observável, mesmo que a abertura
   renderizada varie; zero requests adicionais para mascarar repetição.
4. **Structured output:** ferramenta errada, JSON incompatível, erro de parser,
   ausência de chamada e transporte são distinguíveis em fixtures. Não alterar
   provider, fallback, orçamento ou ativar JSON mode automaticamente.
5. **Transições/checkpoint:** teste integrado de recuperação, recibo e save/load
   verifica local/relógio/consciência contra expectativas independentes.
6. **Queda/morte:** morte afirmada do protagonista exige evento terminal do
   protagonista na timeline aplicável ou memorial; evento de quest não serve.
   Negação de morte não pode ser tratada como afirmação. Detector continua
   fechado às construções documentadas, sem inferência genérica.
7. **Locais:** corpus fechado inclui pertencimento, viagem e negação explícita;
   mapas canônicos são autoridade. Não ampliar a promessa para toda frase livre.
8. **Inventário:** reconhecer sujeito direto e posse afirmativa; não confundir
   negação, fala sobre NPC ou nomes sobrepostos. Inventário atual prevalece.
9. **NPC:** persistir aliases e coalescer componentes transitivos, inclusive
   referência-ponte que une dois grupos já encontrados. Repetir normalização
   não altera o resultado; preservar identidade antiga e dinâmica recente.
10. **Replan:** manter regressões existentes de viagem/combate e rodar junto
    aos novos testes; não mudar a mecânica sem novo defeito demonstrado.
11. **Matriz:** primeiro erro de turno/invariante interrompe a campanha, e
    erro/incompletude/erro de observabilidade impede o próximo par, preservando
    diagnóstico e artefatos. Warning é evidência a
    revisar, não é convertido em sucesso narrativo. Comparação real A/B e
    cobertura de 2.000 turnos permanecem pendentes.

## 3. Plano e gates separados

1. Escrever regressões independentes para os casos da auditoria e confirmar
   falhas antes do fix.
2. Corrigir mecanismos Python e executar testes focados.
3. Rodar suíte offline completa, lint e smoke curto do grafo/harness.
4. Atualizar as onze specs, ROADMAP e ESTADO com evidências locais.
5. Em etapa posterior autorizada: contratos curtos no provider, depois B
   integral no build estável. Esta execução NÃO chama LLM paga nem faz deploy.

## 4. Aceite local deste adendo

- [x] Reproduções falham antes e passam depois, sem LLM/rede.
- [x] Recuperação não autoriza ação física enquanto inconsciente.
- [x] Recibo vem do estado; repetição cosmética continua detectável.
- [x] Memória não usa quest como prova de morte nem confunde sujeito/negação.
- [x] Aliases transitivos sobrevivem à normalização e persistência.
- [x] Erros estruturados têm causas distintas; matriz para na primeira falha.
- [x] Suíte completa, lint e smoke offline verdes.
- [x] Critérios locais e reais separados nas specs e no handoff.

Evidência: **1721 passed, 16 skipped, 14 deselected**, 309,18 s; 40 testes novos.
Ruff e conteúdo verdes. Smoke offline `20260919-150042-217978`, 30/30 sem erros
ou violações. [Relatório](../docs/remediacao-pre-matriz-2026-09-19.md).

## 5. Limites

Este adendo pode terminar sem matriz porque seu produto é a correção Python e
a evidência local. As dez specs funcionais anteriores mantêm sua certificação
real pendente; `matriz-longrun-multiperfil-niveis` exige a execução real em si.
Saldos, cloud e mudanças de escopo de async/arte não fazem parte desta entrega.
