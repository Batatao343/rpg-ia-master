# Playtest longo — 3 perfis × 100 turnos no LLM real (2026-07-14)

> Runs: `20260714-044513` (explorador) · `20260714-050009` (combate) ·
> `20260714-050339` (quester). Transcritos/reports em `playtest_runs/<id>/`.
> Roteamento: DeepSeek principal no SMART + 1º fallback do FAST (na prática o
> motor do run inteiro — MiniMax 402 caía direto nele). CLASSIFY com override
> runtime (`RPG_ROUTES`) adicionando deepseek como fallback do Groq.
> Custo total dos 3 runs: **~$0.25**. Zero erros de turno em 300 turnos.
> ⚠️ Embeddings Google 429 ("prepayment credits depleted") durante TODOS os
> runs — RAG global + memória vetorial de sessão MORTOS. A coerência observada
> veio só do `narrative_summary` do archivist.

## Números

| perfil | turnos vivos | morte | downed | replans | nível | locais | quests | violações | custo |
|---|---|---|---|---|---|---|---|---|---|
| explorador | 47/100 | t47 (Brekmar) | t43 | 5 | 3 | 23 | 0/0 | 0 | $0.100 |
| combate | 13/100 | t13 (Pântano) | t12 | 1 | 2 | 4 | 0/0 | 0 | $0.023 |
| quester | 100/100 | — | 0 | 9 | 5 | **1** | **7/7** | 1 secret_leak | $0.126 |

## O que está funcionando bem

1. **Prosa do DeepSeek é forte.** Atmosfera consistente (fuligem/ferrugem de
   Nova Arcádia, névoa do Pântano), sensorial, PT-BR sólido, ganchos no fim de
   cada turno. Nível claramente acima do observado com modelos free anteriores.
2. **Continuidade de cena em janela curta é real.** Quester turnos 1–6: beco →
   corvo → legionário se encadeiam; turnos 51–58 (arco da Thrace: cerco, fuga
   pelos esgotos, entrega de quest) são o ponto alto dos 3 transcritos.
3. **Quest com FRACASSO tratado com elegância** (t55: Bors não estava lá; Thrace
   reage narrativamente, quest fecha mesmo assim). Loop de quest do quester
   funcionou: 7 criadas, 7 completadas, level 5, 9 replans coerentes.
4. **"O Saque" disparou como projetado** nos 2 perfis que caíram: 1ª queda →
   acorda 1 dia depois em local seguro, 25% HP, ouro 0, só arma básica.
5. **Zero crash, zero violação de invariante de estado** em 300 turnos reais;
   fallback de provider (minimax 402 → deepseek) transparente, sem turno perdido.
6. **Custo viável:** ~$0.0008–0.0013/turno vivo no DeepSeek.

## Defeitos encontrados (por severidade)

### A. Harness não para no game_over — 140/300 turnos desperdiçados
Combate morreu no t13, explorador no t47; o runner seguiu até 100 repetindo o
memorial **verbatim** a cada turno (provider `mock`, rota vazia). Polui p50 de
latência (4ms/1ms), rota_top, custo médio. **Fix: abortar campanha em
`game_over` (aborted_reason="player_death").**

### B. Espiral da morte pós-Saque
Padrão idêntico nos 2 perfis: downed → acorda 25% HP/0 ouro/arma básica →
perfil volta pro perigo → morte DEFINITIVA em 2–4 turnos. A 2ª queda matar é
por design, mas o estado pós-Saque não dá chance real: sem poção, sem ouro,
sem beat de recuperação. Candidatos: (i) campaign_manager forçar beat de
recuperação pós-downed; (ii) narrador sugerir descanso explicitamente;
(iii) Saque deixar 1 consumível de cura.

### C. Combate zumbi — `combat.active` nunca limpa
Quester: combate abriu no t42 e ficou ativo **até o t100** (59 turnos) com o
router mandando storyteller/npc_actor normalmente. Explorador: viajou 2×
DURANTE combate ativo (t41→t42→t43) com sangramento e levou o golpe final "à
distância". **Fix: (i) viagem com combate ativo = fuga (mecânica existe) ou
bloqueio; (ii) expirar combate se N turnos sem rota de combate.**

### D. Vazamento de segredo via campaign_manager (canal novo)
Quester t14: o BEAT já continha "o pacto de Valerius com Daruun é a ponta do
iceberg" — o quester ecoa o beat como ação e o narrador confirma. Com o RAG
morto, o segredo veio do CONTEXTO do planner (não do FAISS) — o filtro
`max_visibility` não cobre o campaign_manager. 1 violação `knowledge.secret_leak`.

### E. "Ninguém responde." — turno jogado fora
7+ turnos do quester: ação NPC sem NPC em cena → resposta seca de 1 linha.
Pior: nos t96/97/99 **Gorim (aliado do grupo) estava na cena narrada** e o gate
`in_scene` não o enxerga. Fix: (i) party membro conta como in_scene;
(ii) sem NPC → rotear pra storyteller com dica do objetivo em vez do stock.

### F. Beat em inglês
t60: "Explore the mysteries of Nova Arcádia." — campaign_manager vazou inglês.
Forçar PT-BR no prompt do planner.

### G. Encontro reciclado
"Sobrevivente moribundo" apareceu 3× em 6 turnos (caverna, Profundezas de
Morrakh, Anel Dourado) com a MESMA fala (mina/colmeia). Cache de NPC/bestiário
reinjetando template sem cooldown/dedupe por localização.

### H. Polish de prosa
- Aberturas de combate repetitivas: "O ar fétido ... queima nas narinas" 3×
  seguidas (combate t8–t11).
- Voz muda pra 3ª pessoa nas narrações de morte/downed ("o herói", "o
  viajante") vs "você" no resto do jogo.
- Menu de opções explícito no fim do turno (ótimo p/ jogabilidade) aparece
  inconsistentemente.

### I. Telemetria
- Rota gravada vazia em turnos de combate e pós-morte → `routes` subconta
  (combate registrou só `storyteller: 6` num run de combate).
- Métricas de latência/custo deviam excluir turnos pós-morte (ver A).
- `fell_back_turns` alto (72/100) por 402 permanente do MiniMax — candidato a
  circuit breaker (desabilitar candidato na sessão após 402).

## O que senti falta (imersão/jogabilidade)

1. **O mundo não puxa o jogador.** Quester passou 100 turnos em Nova Arcádia
   (1 local!) — as 7 quests todas locais; mapa de 35 nós subutilizado. Quests
   deviam apontar para fora da cidade.
2. **Exploração não recompensa.** Explorador visitou 23 locais: 0 quests
   geradas, ouro 0, level 3. Sem loot de exploração, sem descoberta mecânica —
   só prosa. O codex/bestiário progressivo não virou recompensa sentida.
3. **Economia invisível.** Ouro final 0/0/50 nos 3 runs; nenhuma compra/venda
   espontânea. (Viés de perfil, mas 300 turnos sem economia aparecer é sinal.)
4. **Aliados sem presença mecânica.** Gorim/Korvus aparecem na prosa mas não
   existem pro gate de NPC nem (aparentemente) pro combate.

## Recomendações priorizadas

1. Abortar run no game_over (harness, barato, corrige metade da poluição). [A/I]
2. Ciclo de vida do combate: viagem = fuga; expirar combate órfão. [C]
3. Beat de recuperação pós-downed OU consumível de cura no Saque. [B]
4. npc_actor sem NPC → storyteller com contexto do objetivo; party in_scene. [E]
5. Visibilidade + PT-BR no campaign_manager. [D/F]
6. Cooldown/dedupe de encontro por localização. [G]
7. Recarregar créditos Google (embeddings) — sem isso memória longa e lore RAG
   ficam mortos em produção; ou migrar embeddings (re-indexar tudo).
