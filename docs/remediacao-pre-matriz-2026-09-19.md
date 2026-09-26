# Remediação pré-matriz — 19/09/2026

## Resultado e escopo

A auditoria identificou lacunas locais que não dependiam da LLM real. O usuário
aprovou corrigi-las antes de repetir a matriz B. O
[adendo](../specs/remediacao-local-contratos-pre-matriz.md) registra o escopo,
complementa as onze specs e separa três gates:

1. Implementação e regressões locais, sem rede/provider pago.
2. Contratos reais curtos e dirigidos por feature, ainda pendentes.
3. Matriz B global de dez campanhas × 200 turnos e relatório A/B, ainda pendentes.

O segundo gate não exige uma matriz inteira para cada feature. O terceiro não
é substituído por mocks. Nenhum critério real foi marcado como cumprido.

## Correções verificáveis

| Área | Contrato local |
|---|---|
| Recuperação | Gramática fechada recusa viagem/saque/ataque misturados com pedido de ajuda; socorro vira descanso no mesmo local. |
| Incapacidade | Descanso bem-sucedido resolve consciência/incapacidade; bloqueio climático não cura. |
| Recibo | Marcadores reservados são substituídos por recibo calculado; render idempotente; ganho de ouro não apaga negação verdadeira de item. |
| Repetição | Detector desconsidera prefixos cosméticos; fala repetida continua produzindo aviso. |
| Memória de morte | Quest/morte de NPC/outra timeline não comprovam morte do player; negações diretas permanecem válidas. |
| Posse | Sujeito direto e verbo afirmativo; negação, relato sobre NPC e oração coordenada de outro sujeito não são posse do player. |
| Identidade | Aliases persistidos e coalescência transitiva, inclusive pontes entre grupos; seis ordens de entrada e reload testados. |
| Structured output | Tool errado, schema inválido e transporte recebem códigos distintos, sem trocar rotas ou criar requests. |
| Harness | Matriz para na primeira falha; o turno problemático fica registrado e o próximo par não começa. |

`check_actor_lifecycle` observa mudança de localização independentemente da
decisão `allowed` do produto. O detector de morte não depende mais de ocorrer
um `player_downed` novo no mesmo turno. As expectativas dos novos testes são
literais/independentes; o corpus não se autovalida chamando o próprio detector.

## Evidência

- Novas regressões em `tests/test_pre_matrix_contracts.py`, executadas primeiro
  contra o código anterior: reproduziram as falhas da auditoria.
- Teste antigo de diálogo atualizado: prefixo cosmético não significa que a
  repetição desapareceu. Mantém uma única chamada simulada ao ator.
- Suíte focada, incluindo memória, aliases, ciclo de vida, provider, viagens e
  replanejamento: verde.
- Ruff nos arquivos alterados: verde.
- Smoke **offline** `20260919-150042-217978`: dez perfis × três turnos,
  30/30, zero erros e zero violações. Não é certificação real de prosa; o
  harness omite a invariante de abertura fixa do MockLLM como já fazia antes.
- Suíte completa: **1721 passed, 16 skipped, 14 deselected**, 309,18 s;
  40 testes adicionados. Um warning de descontinuação do wrapper FAISS.
- Conteúdo canônico e assets: zero erros e zero avisos.
- Inventário após o aceite local: 153 specs, 141 `done`, 11 `in-progress` e
  uma `draft`. As onze remanescentes têm gates reais explicitamente separados.

## Limites deliberados

Não houve chamada paga, recarga consultada, deploy, migração de banco remoto,
geração de imagem ou limpeza de saves. Os padrões textuais são fechados e não
constituem compreensão semântica universal. A nova gramática de recuperação
pode recusar frases livres fora das formas suportadas; a mensagem oferece
descanso/tratamento/socorro em vez de permitir uma ação física ambígua.

As dez specs funcionais permanecem `in-progress` até seus smokes reais dirigidos;
a décima primeira, da matriz, mantém o aceite real integral. O adendo local pode
ser encerrado pelo seu próprio gate offline sem esconder essas pendências.
