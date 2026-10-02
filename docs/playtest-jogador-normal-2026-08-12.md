# Playtest longo — jogador curioso e misto (2026-08-12)

## Objetivo e método

Diagnóstico de campanha longa com comportamento misto: explorar, conversar,
seguir pistas e missões, viajar, comprar/vasculhar, descansar, lutar quando o
mundo impõe conflito e tentar preservar a vida quando a luta degrada.

Foram executadas três campanhas isoladas em `saves_playtest/` e
`playtest_runs/`:

| run | modo | turnos | resultado principal |
|---|---:|---:|---|
| `20260812-161829-822924` | MockLLM | 200 | 0 erros/invariantes; política ingênua ficou 141 turnos em combate e restaurou 22 vezes |
| `20260812-162308-554379` | MockLLM | 200 | 0 erros/invariantes; política prudente teve 0 combates, 5 locais e 18 quests mock concluídas |
| `20260812-162429-546407` | DeepSeek real | 40 | 0 erros/invariantes; 9 locais, 1 quest ativa, 1 queda, 114 requests, US$ 0,03192 |

Os runs offline serviram para longevidade e estado. O run real foi a fonte para
coerência narrativa, grounding, latência e comportamento de provider. Os perfis
foram injetados apenas no processo do teste; nenhuma regra do jogo foi alterada.

## Resultado executivo

O motor permaneceu estável: **440 turnos**, zero exceções e zero violações
registradas. Isso não significa que a experiência esteja correta. O playtest
encontrou três defeitos de alta prioridade que os invariantes atuais não veem:

1. fuga contra perseguidor reinicia sua trilha a cada turno e pode ser
   matematicamente impossível;
2. continuar do checkpoint restaura o JSON, mas não desfaz a memória FAISS já
   gravada sobre a morte descartada;
3. um arco de região anterior pode sobreviver à viagem e transplantar locais e
   NPCs para outra região, contaminando também resumo e memória.

Há ainda problemas relevantes de resumo/contexto, feedback de recompensas e
latência. O jogo é tecnicamente resiliente, mas algumas escolhas sensatas ainda
não têm efeito confiável e uma contradição pode se tornar memória durável.

## Achados priorizados

### P0 — Fuga progressiva é reiniciada e pode nunca terminar

**Evidência:** turnos 31–36 do run real. O jogador tentou fugir seis vezes de
dois Filhotes de Baleia-Ossário. Todas as decisões foram registradas como
`kind=flee`, com destino canônico `costa_negra`, e todas resolveram
`flee_failed`; o jogador caiu no turno 36.

**Causa confirmada:** `agents/combat.py::_attempt_flee()` chama
`chase.start_chase(...)` em toda tentativa. Partindo engajado, um sucesso move a
trilha apenas de `pressionado` para `afastado`; como isso ainda não é
`escapou`, o turno termina em falha. Na tentativa seguinte a trilha volta a
`pressionado`. Contra arquétipos com `pursuit_policy=persegue`, como `bruto`, o
progresso nunca é reaproveitado.

**Impacto:** a opção explícita de recuar pode ser falsa. O jogador sacrifica a
ação, recebe todos os ataques e não consegue acumular progresso nem com
sucessos consecutivos.

**Correção a especificar:** persistir `combat.chase` entre rodadas, distinguir
“fuga em progresso” de “fuga falhou/foi alcançado” e tornar o resultado mecânico
visível. Adicionar invariante/oráculo que prove que uma sequência suficiente de
sucessos pode chegar a `escapou`.

### P0 — Checkpoint não é transacional com memória vetorial

**Evidência:** no turno 36, antes da restauração, o archivist persistiu:

`[CONFIRMADO | canonical_event | fonte conflict:conflict-t37-…] Playtest-jogador_normal_real morreu no conflito.`

Depois de “Continuar”, o save voltou vivo ao checkpoint, sem `player_downed` no
`event_log`, mas `query_session_memory("jogador morreu", game_id)` ainda devolve
essa morte como fato confirmado.

**Causa confirmada:** `resolve_death_choice()` restaura apenas o snapshot do
estado/save. O índice `data/saves_memory/{game_id}` é append-only e não possui
checkpoint, geração/epoch ou rollback. O archivist roda no mesmo turno da queda
e grava o resumo canônico antes da escolha do jogador.

**Impacto:** storyteller, NPCs e planner podem lembrar como canônica uma linha
do tempo abandonada. O problema vale para qualquer fato indexado depois do
checkpoint, não apenas morte.

**Correção a especificar:** tratar memória derivada como parte do checkpoint.
Opções seguras: não confirmar fatos de morte antes de `accept`; versionar fatos
por epoch/checkpoint e filtrar epochs descartados; ou reconstruir o índice a
partir do ledger restaurado. Incluir RAG, crônica derivada e outros efeitos
externos no teste de rollback.

### P1 — Arco antigo contamina geografia após troca de região

**Evidência:** o plano criado em Nova Arcádia continha “O Sino Rachado, no
coração do Anel de Lama”. O jogador viajou para Brekmar no turno 17. Nos turnos
18–28, o narrador passou a afirmar que Brekmar também tinha um “Anel de Lama”,
levou o Javali Dourado para essa comparação e consolidou O Sino Rachado como
local real. O mapa canônico prova que `na_anel_lama` e
`na_taverna_javali` pertencem exclusivamente a Nova Arcádia; Brekmar tem apenas
o hub e `bk_docas_velhas` nesse recorte.

**Causa confirmada:** `_should_replan()` só invalida o plano ao trocar de região
se algum beat já deixou `pending` (ou se não houver beats). O plano de Nova
Arcádia ainda tinha o beat atual pendente, então foi reutilizado em Brekmar.

**Impacto:** uma invenção deixa de ser apenas prosa: entra no
`narrative_summary`, nos fatos de sessão e nas falas posteriores, ganhando
aparência de cânone.

**Correção a especificar:** na troca comprovada de região, replanejar antes do
storyteller ou suspender beats cujas entidades/localizações não pertencem ao
contexto atual. Preservar continuidade do arco por intenção/quest, não por
instruções geográficas literais. Criar validador de referências canônicas do
beat contra região/local atual.

### P1 — “Resumo curto” cresce sem limite e contorna o orçamento

**Evidência:** após 40 turnos, `narrative_summary` tinha **11.029 caracteres,
1.954 palavras e ~2.758 tokens estimados**. Ele recontava quase toda a campanha.

O context builder reserva 10% de 3.500 tokens para memória. Como toda a memória
é inserida como um único `ScoredFact`, o bloco excede a cota e é descartado por
inteiro (`memory_block=""`). Em seguida, o storyteller usa
`pack.memory_block or narrative_summary`, reintroduzindo o resumo completo e
furando o orçamento. O archivist também recebe o resumo inteiro diretamente a
cada compactação.

**Impacto:** custo e latência crescem com a campanha; fatos antigos dominam a
cena atual; ao mesmo tempo, outros agentes podem receber memória vazia quando o
bloco não cabe. Esse comportamento favorece a contaminação geográfica vista no
run.

**Correção a especificar:** impor teto determinístico de palavras/tokens no
resumo, separar “aqui e agora” de histórico por local/arco, fracionar memórias
em fatos ranqueáveis e remover o fallback que bypassa o budget. Testar 100+
turnos com limite constante de contexto.

### P1 — Feedback contradiz recompensas determinísticas

**Evidência:** ouro mudou mecanicamente nos turnos 2 (+5), 5 (+15), 17 (+16),
30 (+12) e 40 (+20). Nesses mesmos fluxos o storyteller tentou devolver strings
como `"15 de ouro"` em `items_gained`; o resolvedor de item rejeitou a string e
o prose guard exibiu “Nenhum outro objeto foi acrescentado” ou “nada novo foi
obtido”. O HUD recebeu o ouro, mas a narração negou a recompensa.

**Causa confirmada:** `discover_on_arrival()` já concede ouro em Python e inclui
a recompensa na nota enviada ao narrador. O modelo repete o ouro no campo
`items_gained`, que aceita apenas itens do catálogo; a barreira interpreta isso
como alegação inválida sem reconhecer que o mesmo ouro já foi concedido pelo
motor.

**Impacto:** progressão econômica silenciosa e perda de confiança entre texto e
HUD.

**Correção a especificar:** separar `gold_gained` de `items_gained` no contrato
ou retirar recompensas determinísticas dos campos livres; a resposta final deve
ser construída a partir de um ledger mecânico de deltas, com texto de fallback
coerente.

### P2 — Latência real tem cauda incompatível com conversa fluida

**Evidência do run real:** p50 **15,304 s**, p95 **38,690 s**, pior turno
**93,978 s**. Foram 114 requests em 40 turnos (média 2,85 incluindo startup;
2,75 nos registros por turno), todos DeepSeek, sem fallback, por US$ 0,03192.

O pior turno foi NPC + archivist: router 2,1 s, NPC 8,2 s e archivist SMART
82,2 s. A entrada em combate usou sete invokes e levou 58,4 s. O streaming evita
espera totalmente cega, mas não elimina a duração percebida nem o custo de
encadear planner/router/preparação/narração/arquivista.

**Correção a especificar:** reduzir o trabalho síncrono do archivist, compactar
contexto antes da chamada, evitar SMART em turnos sem fato durável e avaliar
persistência assíncrona/adiada apenas quando preservar as garantias do save.
Adicionar SLO por rota e alerta para p95/turno.

### P2 — Invariantes medem integridade, mas não agência/coerência

Os três runs terminaram com zero violações, mesmo havendo fuga impossível,
memória de linha do tempo descartada, geografia contraditória e feedback de ouro
invertido. O resultado atual “0 violações” deve ser lido como integridade de
schema/estado, não como aceite de jogabilidade.

**Correção a especificar:** novos checks/oráculos para:

- progresso de fuga entre tentativas;
- memória vetorial compatível com o epoch/checkpoint ativo;
- entidades e locais mencionados por beats pertencentes ao contexto atual;
- deltas de ouro/item refletidos na mensagem visível;
- teto de `narrative_summary` e do prompt final;
- diversidade mínima do perfil normal (incluindo decisões de level-up).

## Observações que não foram classificadas como bug de produção

- As 18 quests offline tinham o mesmo título. O MockLLM propõe deliberadamente
  “Recuperar o medalhão perdido”; o dedupe atual compara apenas quests ativas,
  então permite repetir o título depois da conclusão. É uma fragilidade útil
  para teste, mas o run real criou uma quest própria e não reproduziu a repetição.
- A primeira política offline restaurou 22 vezes porque o harness sempre escolhe
  “Continuar” e a política não mudou de objetivo. Isso é comportamento ruim do
  perfil, não prova de bug por si só; serviu para revelar o rollback incompleto.
- Os `?` em algumas ações do transcrito vieram da codificação do script efêmero
  no PowerShell. As respostas reais permaneceram legíveis; não é defeito do
  frontend/API.
- O perfil efêmero não resolveu as escolhas pendentes de nível. Um perfil normal
  permanente deve fazê-lo; resultados de combate deste run não servem sozinhos
  para balancear classe/dificuldade.

## Ordem recomendada para specs

1. `fuga-progressiva-persistente` — restaura agência básica no combate.
2. `checkpoint-transacional-memoria` — impede fatos de linhas do tempo
   descartadas.
3. `replan-grounding-troca-regiao` — não deixa beats antigos inventarem mapa.
4. `resumo-curto-budget-rigido` — estabiliza memória, latência e contexto.
5. `feedback-ledger-recompensas` — alinha texto com ouro/item aplicados.
6. `perfil-jogador-normal-playtest` — torna o perfil misto reproduzível e amplia
   invariantes/SLOs.

## Remediação entregue em 2026-08-12

As seis recomendações viraram specs e foram implementadas na ordem acima:

- [fuga progressiva](../specs/SPEC-096-fuga-progressiva-persistente.md);
- [checkpoint transacional](../specs/SPEC-093-checkpoint-transacional-memoria.md);
- [grounding regional](../specs/SPEC-098-replan-grounding-troca-regiao.md);
- [resumo/budget](../specs/SPEC-099-resumo-curto-budget-rigido.md);
- [feedback por ledger](../specs/SPEC-095-feedback-ledger-recompensas.md);
- [perfil normal e invariantes](../specs/SPEC-097-perfil-jogador-normal-invariantes.md).

O novo perfil `normal` completou o smoke mock de 50 turnos
`20260812-172231-913670` com as quatro rotas, três escolhas de progressão e zero
erro/violação. O smoke DeepSeek real `20260812-172526-505951` completou 5/5 com
as quatro rotas, zero erro/violação, p50 19,6 s, p95 37,3 s, 24 requests e
US$ 0,00686; um structured output inválido do planner caiu corretamente para
Groq. Gate offline: **1436 passed, 1 skipped, 14 deselected**; Ruff verde.
