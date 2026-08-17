# Playtest longo real — jogador normal, pós-remediações (2026-08-12)

## Escopo

Campanha de **100 turnos** pelo perfil permanente `normal`, usando o grafo real
e somente provedores LLM de rede. O modo simulado foi proibido com
`RPG_NO_MOCK=1`; o run confirma `mock=false`. Fallback entre provedores reais
continuou habilitado, como parte da resiliência oficial do jogo.

```powershell
uv run python -m playtest run --profile normal --turns 100 `
  --seed 20260812 --real --max-requests 450 --max-cost 0.15 `
  --turn-timeout 120
```

Run: `20260812-215427-501557`. Save isolado:
`ef38b80d-905b-4e1e-8e0f-7c8201946c6d`.

## Resultado executivo

- 100/100 turnos concluídos, zero exceções, zero abortos e zero falhas de RAG.
- 282 tentativas LLM, das quais 281 chegaram à rede e 273 tiveram sucesso.
- Nenhum evento usou MockLLM ou fallback determinístico.
- Custo estimado: **US$ 0,085208**.
- Rotas: 36 storyteller, 45 combat, 12 loot e 7 NPC.
- Sete locais visitados, nível final 2, 198 de ouro, duas escolhas de progressão.
- Sete conflitos iniciados e encerrados; três mortes com restauração de
  checkpoint; 14 ações de fuga.
- p50 de 9,7 s e p95 de 43,7 s. Cinco turnos excederam 45 s e um excedeu 90 s.

O motor sobreviveu à campanha, mas o run foi corretamente marcado `failed` por
uma violação `error` de latência. Os novos achados principais são operacionais e
de validade/jogabilidade do playtest, não corrupção de estado.

## Achados novos

### P0 — o teto de 120 s não interrompeu um turno de 37,6 minutos

No turno 64, a primeira chamada FAST da DeepSeek registrou
`Request timed out` somente após **2.230.109 ms**. O turno completo levou
**2.256.298 ms**. Depois disso, a cadeia real de fallback funcionou: MiniMax
falhou, Qwen falhou e Groq respondeu; outra chamada SMART também caiu para o
Groq. O jogo continuou e completou os 100 turnos.

O runner executou esse turno sob `--turn-timeout 120`, mas não produziu
`PlaytestTimeoutError`. Houve uma lacuna de heartbeat entre 22:09 e 22:46,
compatível com suspensão do notebook ou bloqueio global do processo. Um
watchdog baseado em thread e relógio do mesmo processo não garante o teto de
parede durante esse tipo de pausa: ao retomar, o worker pode publicar o
resultado antes que a thread supervisora processe o vencimento.

**Impacto:** o teto atual protege contra uma chamada travada enquanto o processo
continua escalonando, mas não é um limite forte de tempo percebido. Runs longos
podem parecer congelados e uma requisição pode ocupar conexão por dezenas de
minutos.

**Próxima spec sugerida:** watchdog em processo isolado ou prazo absoluto
persistido, com timeout de transporte comprovadamente menor que o teto do turno,
telemetria de suspensão/lacuna de heartbeat e finalização parcial auditável.

### P1 — duas rotas configuradas de fallback real estão indisponíveis

O run encontrou falhas permanentes de configuração:

- MiniMax: HTTP 402, `insufficient_balance_error`;
- Qwen: HTTP 401, `invalid_api_key`.

O circuit breaker evitou repetir MiniMax imediatamente, e o Groq absorveu a
falha sem quebrar o turno. Ainda assim, numa indisponibilidade simultânea de
DeepSeek e Groq, a rota FAST possui dois candidatos que hoje não oferecem
redundância real.

**Ação operacional:** renovar a chave Qwen e provisionar saldo MiniMax, ou tirar
temporariamente esses candidatos das `ROUTES` para que a telemetria não trate
configurações sabidamente mortas como capacidade disponível.

### P1 — o perfil normal lê instruções internas do plano e as repete como ação

Em seis turnos, o perfil construiu ações como
`Tento cumprir o objetivo principal: Descreva...`, copiando diretamente
`campaign_plan.beats[].description`. Esse texto é uma instrução de direção ao
narrador, não uma intenção que um jogador humano poderia formular sem acesso ao
estado interno.

**Impacto:** a campanha cobre as rotas, mas superestima a capacidade de um
jogador comum de avançar beats. Também injeta linguagem de prompt no papel do
jogador e reduz a validade do teste de agência.

**Próxima spec sugerida:** o perfil deve decidir somente a partir de uma visão
pública do estado e converter o beat em intenção diegética curta, sem copiar
instruções de narração.

### P1 — nenhum rumor virou quest em 100 turnos

Apesar de sete turnos NPC, dez replans e vários ganchos explícitos — navio de
Kahen, barco encalhado, caravana desaparecida, vila vazia — o ledger terminou
com **zero quests criadas e zero concluídas**. Houve apenas um NPC materializado,
o Estivador de Brekmar; cinco buscas sociais posteriores aconteceram em cenas
sem ninguém.

Isso não viola o schema, mas representa uma falha de conversão de conteúdo em
objetivos acompanháveis. A sessão produz rumores e direção narrativa, porém não
dá ao jogador um compromisso visível no diário.

**Próxima spec sugerida:** medir `hook -> proposed quest -> quest registrada` e
definir um gate conservador para transformar pedidos/promessas explícitos em
quest, sem converter todo rumor ambiental.

### P2 — combate domina o comportamento misto

Foram 45 turnos na rota de combate, 46 execuções do agente, 14 fugas e três
mortes. A Vitalidade média pós-combate ficou em 19,8%. Os sete conflitos
ocuparam, respectivamente, 8, 12, 6, 2, 8, 2 e 8 turnos. No Deserto de Zhur
houve 17 turnos de combate.

O perfil é prudente e conseguiu escapar no turno 90, mas a experiência ficou
mais letal e combativa do que “curiosa e mista”. Isso pode ser balanceamento do
mundo, efeito do perfil investigar uma ameaça a cada oito passos, ou ambos; o
run isolado não basta para alterar números.

**Próximo experimento sugerido:** matriz de três seeds com o mesmo perfil,
comparando encontros por região, turnos por conflito, mortes, fuga e proporção
de rotas antes de propor tuning.

### P2 — texto de loot ainda fala do jogador em terceira pessoa

Sete narrações de loot começam com “O jogador...”, enquanto storyteller e
combate usam segunda pessoa. O resultado mecânico está correto e o bloco
`[SISTEMA]` confirma o delta, mas a troca de pessoa quebra a voz narrativa.

**Próxima spec sugerida:** estender o prose guard à voz do loot e cobrir as
formas “O jogador”, “o personagem” e equivalentes, preservando mensagens de
sistema.

## Falhas de provider absorvidas

Além das indisponibilidades acima:

- turno 32: DeepSeek SMART retornou structured output inválido para
  `CampaignPlanModel`; Groq concluiu o replan;
- turnos 64–65: quatro falhas DeepSeek, uma MiniMax, duas Qwen e um skip por
  circuito aberto; Groq concluiu cinco chamadas de fallback.

Distribuição dos 282 eventos: DeepSeek 268 sucessos e 5 falhas, Groq 5 sucessos,
MiniMax 1 falha + 1 skip, Qwen 2 falhas. Não houve Gemini, Anthropic, MockLLM ou
`FallbackLLM` determinístico.

## Regressões não reproduzidas

As seis remediações do playtest anterior se mantiveram:

- fuga progressiva chegou a `afastado -> quase_livre -> escapou`;
- três restores de checkpoint não deixaram morte do protagonista na memória
  final;
- o plano final ficou ancorado na região atual de Nova Arcádia;
- `narrative_summary` terminou com 1.191 caracteres, abaixo do teto de 1.200;
- loot e ouro foram confirmados por mensagens de sistema coerentes;
- as quatro rotas e escolhas de progressão foram efetivamente exercitadas.

Vitalidade zero sem `death_pending` nos turnos 47, 89–93 também não é, por si,
um bug: no sistema v4, morte depende do último Ferimento Crítico/flag `dead`, e
Vitalidade zero ainda permite Última Ação, fuga e viagem. As mortes reais dos
turnos 48, 52 e 75 abriram `death_pending` e restauraram corretamente.

## Ordem recomendada

1. `watchdog-prazo-forte-suspensao` — segurança operacional do harness.
2. `perfil-normal-visao-publica` — validade do agente de playtest.
3. `ganchos-para-quests-observavel` — progressão narrativa rastreável.
4. `loot-voz-segunda-pessoa` — consistência de prosa.
5. matriz de balanceamento de encontros — medir antes de decidir tuning.

Nenhuma dessas recomendações foi implementada neste diagnóstico.

## Remediação entregue

Os achados autorizados foram implementados pela spec
[remediacao-playtest-real-100t](../specs/remediacao-playtest-real-100t.md):

- watchdog rejeita resultado entregue depois do deadline absoluto, inclusive
  após salto do relógio/suspensão;
- perfil `normal` usa somente visão pública, pede tarefa concreta e mede a
  conversão do pedido em quest;
- cooldown e retirada prudente reduzem provocação/duração de combate sem alterar
  encontros ou dificuldade do mundo;
- summary/JSONL expõem percentual de combate e funil de quests, com warnings de
  campanha;
- loot normaliza a voz do protagonista para segunda pessoa em Python.

Smokes: mock `20260812-232004-255178` (50/50, quatro quests, quatro rotas) e real
`20260812-232052-855221` (16/16, `mock=false`, zero erro/violação, uma quest,
31,2% combate, US$ 0,014). Gate final: 1446 testes verdes. Saldo, chaves e ordem
dos fallbacks reais continuam fora do escopo por decisão do usuário.
