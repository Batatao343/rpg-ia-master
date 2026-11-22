# Medição de latência do turno (L0) — 2026-11-13

Complementa [latencia-turno-2026-11-12.md](latencia-turno-2026-11-12.md). O dono autorizou a medição em 13/11 ("pode medir").
Dados brutos e scripts: [latencia-l0-2026-11-13/](latencia-l0-2026-11-13/) (`resultado.json` só tem tempos e contagens).

## Protocolo

- Staging Vercel, `d7aa4beb`, preset de flags do staging (caminho rápido ligado), DeepSeek.
- 4 sessões novas × 15 turnos = **60 turnos, 0 erros**, 6 s de "leitura" entre turnos. Por sessão: 5 cenas, 2 NPC novo, 4 conversas, 2 descansos, 1 viagem, 1 início de combate.
- Cada sessão abre como o cliente: `/game/prologue` + `/game/new`. Antes de cada turno, a mesma consulta `getOperation` que o cliente faz.
- Tempo do cliente medido nesta máquina; tempo do servidor lido dos logs `turn`, `turn_delivery` e `http.request` (juntados por ordem; o relógio local está 4,9 s atrás do servidor).
- Custo: US$ 0,19 nos 60 turnos (US$ 0,0031 por turno), mais 4 aberturas. Total estimado ≤ US$ 0,25.
- Plano Vercel: **Hobby**, **Fluid Compute ligado**, função em `gru1`. Responde a P0.2 do relatório.

## Resultado em uma tabela

Mediana, em segundos, a partir do Enter (57 turnos sem incidente):

| Tipo de turno | n | 1º texto | texto completo | pode agir de novo |
|---|---|---|---|---|
| Cena / exploração | 19 | 2,7 | 5,6 | 5,9 |
| Fala, narrador responde, com texto ao vivo | 5 | 3,6 | 6,5 | 6,7 |
| Fala, narrador responde, **sem** texto ao vivo | 8 | **7,0** | 7,0 | 7,2 |
| Fala com NPC já criado (`npc_actor`) | 9 | 4,2 | 6,1 | **10,2** |
| Descanso (vira o dia) | 8 | 2,8 | 5,8 | **10,6** |
| Início de combate | 4 | 6,7 | 7,6 | 8,4 |
| Viagem resolvida sem IA | 3 | 0,6 | 0,6 | 0,8 |
| **Todos** | 57 | 2,9 | 5,8 | 7,2 |

Comparação com 27/10 (mesmo preset): 1º texto 2,6 → 2,9 s; texto completo 6,1 → 5,8 s; pode agir 9,8–11,4 → 7,2 s (o roteiro de 27/10 tinha mais turnos com arquivista).

**Abertura do jogo (4 medições):** prólogo 8,5–11,3 s + criação da partida 15,4–22,4 s = **24 a 33 s de espera sem texto aparecendo**. É a maior espera do produto e nunca tinha sido medida.

## Para onde vai o tempo

Soma das etapas nos 57 turnos sem incidente (448 s de servidor):

| Etapa | Parte do tempo | Mediana quando acontece |
|---|---|---|
| IA escrevendo a narração | 55 % | 4,4 s por turno (2,1 s até a primeira palavra + escrita a ~470 caracteres/s) |
| Resumo de memória (arquivista, IA) | 18 % | 4,0 s, em 20 de 60 turnos |
| Entender a ação (roteador) | 9 % | 0,2 s quando resolve sem IA; **1,7 s** quando chama IA (20 de 60 turnos, quase toda fala) |
| "Outros" (carregar save, autenticar, intervalos) | 6 % | 0,5 s em todo turno |
| Fichas / virada de dia depois do texto (`enrich`) | 4 % | 4,4–5,1 s em 4 turnos (viagem a região nova, 2º descanso) |
| Salvar | 4 % | 0,25 s; 0,8–1,3 s no início de combate |
| Buscar contexto / RAG | 4 % | 0,3 s |

Fora do servidor, por turno: consulta `getOperation` antes do envio, **0,35 s** (0,24 s dentro do servidor).

## O que a medição confirmou

1. **RAG não é o gargalo no turno normal: 0,3 s, 4 % do tempo.** Confirma a SPEC-214.
2. **A espera depois do texto é de "sim ou não", não constante.** Em 39 de 60 turnos o envio libera 0,24 s depois do texto. Em 21 de 60 o jogo fica **4,4 s** travado (mediana; até 9,6 s). São os turnos em que o arquivista chama a IA: todo descanso (8/8), quase toda fala com NPC já criado (8/10), 3 de 20 cenas e a viagem a região nova (1 turno, 15,5 s até liberar; fora da tabela). No 2º descanso somam-se virada de dia + arquivista: 9 s travado.
3. **Falar com alguém é o turno mais lento para começar.** Quase toda fala paga 1,7 s de IA só para classificar a ação. Em 8 das 22 falas o texto não aparece aos poucos: chega inteiro aos 7 s. Causa conhecida no código: na "narração mediada" o filtro de segredo só roda no texto final, então nada sai ao vivo (`agents/storyteller.py:2298`, decisão da revisão da SPEC-319).
4. **Texto longo custa.** Cena tem ~1.350 caracteres e leva ~3 s para ser escrita depois da primeira palavra. Fala de NPC tem ~730 e fecha 1 s antes.

## O que a medição derrubou ou mudou

1. **Regravar o histórico de eventos (L7b) não pesou.** Nenhum dos 60 turnos gerou evento (`event_log` vazio, 0 linhas em `app.game_events`); salvar ficou em 0,22–0,35 s do 1º ao 15º turno, sem crescer. O risco continua existindo em campanha com muito combate, mas não explica a lentidão do jogo comum. Sai da frente da fila até haver medição com combate.
2. **"Servidor dormindo: 19 a 59 s" estava mal atribuído.** Hoje houve 9 esperas de 19,3–21,7 s e 1 de 39 s na consulta antes do turno. Os logs mostram que o pedido chegou à Vercel 19,0 s **depois** de sair desta máquina, na mesma instância já quente, e foi atendido em 0,25–0,5 s. A demora é entre esta máquina e a borda da Vercel, não no servidor. Os "19 s", "39 s" e "58,9 s" das medições de outubro têm o mesmo número de base. O que é subida real de instância nova apareceu 2 vezes e custou **~6,8 s**. Ver "Em aberto".
3. **Com o servidor quente, não houve nenhum turno com espera para começar** (ack ≤ 0,27 s nos 60).

## Achados novos

1. **Abertura do jogo: 24–33 s sem texto** (acima).
2. **Embedding externo com espera de 30 s.** Em 2 turnos seguidos (20:30–20:32 UTC) o provedor de embeddings (Jina) travou e o 1º texto saiu aos **49 s** e aos **24 s** (etapa de contexto: 45,7 s e 19,9 s). Log: `provider.attempt` `embedding` `timeout` 30.016 ms; `context.prefetch_miss` `TimeoutError`. O limite é `EMBEDDING_TIMEOUT_SECONDS=30` com 2 tentativas (`rag.py:474-475`). É raro (2 de 60), mas é o pior caso medido e tem relação com a intuição do dono sobre o RAG: a busca não é lenta, mas espera demais quando o fornecedor falha. Dois turnos depois, o pós-texto (`enrich`) levou 26 s com 3 chamadas de IA somando 18,5 s; causa não isolada.
3. **Deadlock entre o job de memória e o salvamento do turno** (1 vez): `job.failed` `DeadlockDetected` em `embed_memory` no mesmo instante de um `turn.commit_game` de 1,1 s. O job repete sozinho; o turno só atrasou.
4. **Início de combate salva 3–5× mais devagar** (0,75–1,3 s contra 0,25 s).

## Ordem revista dos candidatos

| Ordem | Candidato | O que a medição diz |
|---|---|---|
| 1 | **L8 abertura do jogo** | 24–33 s sem texto; sobe para o topo |
| 2 | **Limite curto no embedding** (novo) | remove o pior caso (24–49 s); mudança pequena |
| 3 | **L4 texto ao vivo nas falas** | 8 de 22 falas só mostram texto aos 7 s |
| — | **Classificação da fala sem IA** (SPEC-317, não promovida) | 1,7 s em 20 de 60 turnos. **Dono, 13/11: não reabrir** (o atalho erra pedido de favor e sondagem em 7 % das falas; a mecânica deixa de rodar) |
| 5 | **L3 arquivista sem IA** / **L1b fila de ação** | 4,4 s travado em 1 de cada 3 turnos |
| 6 | **L5 narração menor** | a escrita é 55 % do tempo; ~1 s a menos por 1/3 de texto |
| 7 | **L1a tirar o `getOperation`** | 0,35 s por turno |
| — | **L11 plano pago** | perde a principal evidência; subida real ~6,8 s e rara nesta medição |
| — | **L7b histórico de eventos** | sem peso medido; aguarda medição com combate |

## Em aberto

- **Origem da espera de ~19 s entre esta máquina e a Vercel.** Reproduzida fora do jogo: em 40 conexões novas ao staging (socket puro, 6,5 s entre elas), 39 levaram ~0,14 s e **1 travou 19,0 s**: DNS 11 ms, TCP 25 ms, e o aperto de mão TLS ficou parado até cair com `ConnectionResetError`. A nova tentativa do cliente passa, o que dá os 19,4 s vistos. Na medição foram 10 em 60. Não se sabe se quem derruba é a rede/máquina local (antivírus, roteador, operadora) ou a borda da Vercel: falta repetir de outra rede. Enquanto isso, tempos de "ack" e de `/health` medidos desta máquina acima de ~19 s não contam como cold start. Um navegador reaproveita a conexão por mais tempo, então sofre menos; quanto, não foi medido. Uma observação a mais, de 22/11: uma chamada desta máquina a `api.github.com` (cliente `gh`) falhou com `net/http: TLS handshake timeout`, e a repetição passou. Um segundo cliente `gh`, na mesma hora, teve o mesmo erro e também passou na repetição. São dois casos, e é o mesmo sintoma contra um destino que não é a Vercel, o que aponta para a rede ou a máquina local.
- Tokens por campo da resposta (prosa × campos técnicos): o log não registra; precisa de instrumentação (spec).
- Rodadas de carta e combate longo: fora desta medição.
- Navegador real (Enter → tela) e rede móvel: não medidos.
