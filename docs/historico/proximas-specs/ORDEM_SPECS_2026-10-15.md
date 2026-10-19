# Ordem final de implementação — SPEC-199..236 (2026-10-15)

> Fonte única da ordem das 38 specs `draft` (onda "beta desktop" 199–217, segurança 218–225, bugs 226–236).
> Cabeçalhos `Depende de`/`Desbloqueia` de todas as 38 specs e `depends_on`/`depends_on_raw` em
> `specs/index.yaml` (só 199..236) foram reescritos para refletir esta ordem (marca "ordem final 2026-10-15").
> SPEC-197 (`in-progress`) e SPEC-198 (`approved`) não foram editadas; aparecem só como destino.
> Status de todas segue `draft`. Nada implementado.

## (a) Princípio de priorização

1. **Correção antes de feature.** Nenhuma feature nova é construída sobre um motor com bug de severidade A. Exemplos:
   o "turn_outcome" da 199 sobre XP inflado, o desfecho da 203 sobre uma morte com aliados errada, a 213/214
   reprojetando um arquivista que congela.
2. **Dinheiro e exposição antes de convidar gente.** A 218 é a única alta da auditoria de segurança. A 236 corrige
   o custo fantasma de US$ 1 por falha e o override do teto. As duas abrem a fila, junto com a ação operacional dos
   rate cards (seção e).
3. **Um dono por arquivo quente.** Specs que tocam o mesmo arquivo ficam em sequência; o resto roda em paralelo.
   - `agents/router.py`: 229 → 202.
   - `agents/combat.py` e motor de conflito: 231 → 232 → 203/205.
   - `agents/npc.py`: 230 → 202/223 → 215.
   - `event_processor`/`quest_log`: 226 → 223 → 215.
   - `persistence.py`: 228 → 227 (D-C) → cadeia de schema.
   - `api.py` é tocado por quase tudo: PRs pequenos e rebase de quem entrar depois.
4. **Medir antes de otimizar.** As otimizações de latência (213, 214, 217) só entram se o baseline da 200 justificar.
   Nenhuma delas bloqueia a SPEC-212.
5. **O menor executor que dá conta**, conforme o cabeçalho de cada spec: Terra para fix mecânico e Sol para
   arquitetura. Astra faz review adversarial onde há credencial, schema ou isolamento.
6. **Gate de fechamento sempre igual:** `uv run pytest` verde, smoke da §6 da spec e ESTADO_ATUAL/ROADMAP
   atualizados.

## (b) Tabela ordenada

Legenda do tipo: **seg** = segurança, **bug** = correção, **feat** = feature/UX, **ops** = medição/diagnóstico.

Severidade:
- seg e bug: alta (A) / média (M) / baixa (B), conforme a auditoria.
- feat e ops: P0 = no caminho da 212; P1 = depois da 212 ou opcional; P2 = condicional.

| Onda | SPEC | Título | Tipo | Sev/Prio | Depende de | Paraleliza com | Executor/Review | Gate de saída |
|---|---|---|---|---|---|---|---|---|
| 0 | — | Rate cards de imagem/STT (vencem 2026-10-19) | ops | **urgente** | — | tudo | dono + Terra | card novo publicado OU kill switch imagem/STT ligado (seção e) |
| 1 | 218 | Fail-closed de perfil/config em deploy exposto | seg | **alta** | — | toda a onda 1 | Terra / Astra (req) | boot recusa `legacy`/flags fracas em processo exposto; smoke staging |
| 1 | 236 | FinOps/wallet/jobs: custo fantasma, teto cross-day, reservas órfãs | bug | A | — | toda a onda 1 | Sol / Sol (req; Astra recom. R1/R2/R5) | falha sem `usage` ≠ US$ 1; teto re-dispara; PG local verde |
| 1 | 227 | Economia/inventário: venda, craft, equipamento, únicos | bug | A | — | 226, 228–231, 234, 235 | Terra / Sol (req) | exploit de ouro infinito com teste vermelho → verde |
| 1 | 228 | Morte sem checkpoint, ordem save/checkpoint, `needs_replan`, schema mais novo | bug | A | — | 226, 227, 229–231, 234, 235 | Terra / Sol (req) | R9 recusa save vN+1 **antes de qualquer bump**; saves v0..v8 carregam |
| 1 | 226 | Contabilidade de recompensas/XP | bug | A | — | 227–231, 234, 235 | Terra / Sol (req) | XP 1× por fato; baseline de XP registrado |
| 1 | 229 | Parsers de intenção: viagem/fuga/router | bug | A | — | 226–228, 230, 231 | Terra / Sol | "Entro na taverna"/"Vou ao X" viajam; "recuperar" ≠ fuga |
| 1 | 230 | NPC: guard de geração, ciclo de vida, relação em Python | bug | A | — | 226–229, 231 | Terra / Sol | guard de `FallbackLLM`; NPC morto fora de cena/party |
| 1 | 231 | Combate: morte com aliados, companheiro, `scene_allies` | bug | A | — | 226–230, 234, 235 | Terra / Sol (req) | estabilização por aliado; fichas de `scene_allies` persistem |
| 1 | 234 | Memória/RAG: arquivista resiliente, segredos por ID, pin | bug | A | — | 226–231, 235 | Terra / Sol (req) | falha de índice não congela o ledger/resumo |
| 1 | 235 | API/frontend: soft-lock do pending, 422 legível, export unicode | bug | A | — | 226–231, 234 | Terra / Sol (req) | campanha não trava em pending no perfil durável |
| 1 | 201 | Diagnóstico UX + matriz de efeitos (só leitura) | ops | P0 | — | toda a onda 1 | Terra / Sol | matriz aprovada (destrava 204/208) |
| 1 | 200 | Baseline de latência (ack/TTFMC/TTLT) | ops | P0 | — (recom. após 235) | toda a onda 1 | Terra / Sol (req) | baseline publicado com `phase_ms`; decide 213/214/217 |
| 2 | 232 | Motor de conflito: condições/passivas/Reações inertes, custo, DoT + **ex-199 R12** | bug | A | 231 | 199, 233, 206, 202, 204, 219–222, 225 | Sol / Sol (req) | cartas com efeito real; cura sem alvo não cura inimigo |
| 2 | 199 | XP e números fora da prosa (sem R12) | feat | P0 | 226 | 232, 233, 206, 202, 204 | Terra / Sol | zero `[RESULTADO] +N XP` na prosa; evento estruturado |
| 2 | 202 | Interlocutor automático narrador × NPC | feat | P0 | 228, 229, 230 | 199, 232, 233, 206, 204 | Sol / Astra (req) | 1º bump de schema da cadeia; eval de roteamento |
| 2 | 204 | Shell chat + contexto: split e abas | feat | P0 | 201, 235 | 199, 202, 232, 233, 206 | Sol / Sol (req) | F01–F16 verdes; 390/1440 sem overflow |
| 2 | 206 | Taxonomia de conhecimento visível ao jogador | feat | P0 | 234 | 199, 202, 204, 232, 233 | Sol / Astra (req) | rótulos de certeza; `known_secrets` escrito |
| 2 | 233 | Mundo: perigo efetivo, luz, clima, exceção do storyteller | bug | M | — | onda 2 inteira | Terra / Sol | perigo efetivo único usado por encontro e mapa |
| 2 | 219 | Cota de custo por owner, rate limit, IP real atrás de proxy | seg | M (custo alto) | 218 | 220–222, 225 | Terra / Sol (req) | turno sem cota por owner = 429; IP real medido no staging |
| 2 | 220 | Sessão: revogação no logout, 401 consistente, lockout, OIDC | seg | M | — | 219, 221, 222, 225 | Terra / Sol (req) | refresh revogado no logout; zero 500 |
| 2 | 221 | `/metrics` autenticado, no-store/HSTS/CSP, teto de body | seg | M | — | 219, 220, 222, 225 | Terra / Sol | `/metrics` fechado; headers verificados no staging |
| 2 | 222 | Privacidade/LGPD: logs, exclusão/export completos | seg | M | — | 219–221, 225 | Terra / Sol (req) | zero `print()` com conteúdo de jogo; delete cobre as 3 tabelas e os blobs |
| 2 | 225 | Supply chain, CI, release, compras de teste do Play | seg | B | — | qualquer onda | Luna / Sol | workflows com pins/permissões; gitleaks |
| 3 | 203 | Manifesto do encontro, elenco fixo, desfecho | feat | P0 | 199, 228, 231 | 223, 207, 224 | Sol / Astra (req) | 2º bump de schema; desfecho determinístico |
| 3 | 207 | Export de sessão para auditoria beta | feat | P0 | 200, 206, 228 | 203, 223, 224 | Sol / Astra (req) | 3º bump de schema; pacote só do dono |
| 3 | 223 | Autoridade mecânica do LLM + prompt injection | seg | M | 226, 230 | 203, 207, 224 | Terra / Sol (req) + eval | `quest_completed` exige prova; corpus de injeção |
| 3 | 224 | RLS efetivo (`SET LOCAL ROLE`) + Storage sem escrita do cliente | seg | M (fecha R-05) | 218 | 203, 207, 223 | Terra / Astra (req) | rebase sobre `8570d62`; prova A/B de isolamento; janela de deploy |
| 4 | 205 | Combate por gesto: carta, mira, alvo direto | feat | P0 | 199, 203, 204, 232 | 213 (se liberada) | Terra / Sol (req) | jogar Carta sem digitar; E2E Chromium |
| 5 | 208 | Design system de efeitos (implementação) | feat | P0 | 201, 204, 205 | — | Terra / Sol | teto de bundle; reduced-motion |
| 6 | 209 | Menu Combate/deck + Personagem | feat | P0 | 203, 204, 205, 208, 227 | 210, 211 | Terra / Sol | deck e ficha a partir de estado íntegro |
| 6 | 210 | Menu Mapa e viagem como turno | feat | P0 | 204, 208, 229, 233 | 209, 211 | Terra / Sol | `GET /game/map` sem vazar locais não descobertos |
| 6 | 211 | Menus Codex/Bestiário como dossiês | feat | P0 | 204, 206, 208 | 209, 210 | Terra / Sol (req) | escape de `mdLite`; nomes ocultos não listados |
| 7 | 212 | **Beta de gameplay desktop (gate)** | feat | P0 (marco) | 199–207, 209–211, 218, 219, 226–235 | — | Terra / Sol (req) | jornada vertical + evidência via 207; go D6 |
| P1 | 213 | Arquivista: canônico síncrono, projeções fora do hot path | feat | P1 | 200, 228, 234 | 205–211 (se o baseline mandar) | Sol / Astra (req) | só com gate da 200; 4º bump de schema |
| P1 | 214 | Memória hierárquica / cache de cena | feat | P1 | 200, 213, 234 | — | Sol / Astra (req) | gate da 200 |
| P1 | 216 | Mobile single-pane | feat | P1 | 204, 205, 212 | 213/214 | Terra / Sol | evidência mobile para a 198 |
| P2 | 215 | Conhecimento por NPC e propagação | feat | P2 | 202, 206, 214, 223, 230 | 216 | Sol / Astra (req) | 5º bump de schema; eval de vazamento |
| P2 | 217 | Reavaliação condicional do Jev | ops | P2 (condicional) | 200, 214 | — | Sol / Astra (req) | só com as pré-condições da §1 |

**Cadeia de `SCHEMA_VERSION`** (escrita nas specs 202, 203, 207, 213, 215, 227 e 228):

> 228 R9 (guard, sem bump) → [227 só se D-C = migração; o default não faz bump] → 202 → 203 → 207 → 213 → 215

Nenhuma outra spec entre 199 e 236 muda o save:
- 228 R7 (`needs_replan`) usa default.
- 231 usa `combat["scene_allies"]`, que já existe.

## (c) Caminho crítico

**Até a SPEC-212 (beta jogável desktop):** 7 specs em série no trecho mais longo.

```
226 ─► 199 ─┐
231 ─► 232 ─┼─► (203: 199+228+231) ─► 205 ─► 208 ─► 209 ─► 212
201 ─┐      │
235 ─┴─► 204┘
228 ─► 202 ─────────────────────────────────────────────────┘ (202 também precisa de 229 e 230)
234 ─► 206 ─► 207 (com 200 e 228) / 211 ─────────────────────┘
229 + 233 ─► 210 ──────────────────────────────────────────┘
218 ─► 219 ────────────────────────────────────────────────┘
```

- **Cadeia mais longa:** 226 → 199 → 203 → 205 → 208 → 209 → 212. O ramo 231 → 232 precisa estar pronto antes da 205.
- **Ramos laterais que não podem atrasar:** 235 → 204, 234 → 206 → 211/207 e 229 + 233 → 210.

**Até a SPEC-197 (beta pago fechado), supondo D6 = sim:**
- 212 `done`.
- Specs de segurança e dinheiro: 218, 219, 220, 221, 222, 223, 225 e 236. A 224 entra se o dono exigir o R-05
  fechado (ver seção d).
- Itens próprios da 197 do risk register, que são do dono:
  - R-01 Turnstile real e R-02 SMTP.
  - R-03 backups/PITR e R-06 Vercel pago.
  - R-07 projeto de produção e R-09 Stripe live.
  - R-10 páginas legais e R-11 limites de gasto nos providers.
  - R-12 crons agendados, R-13 smoke com dois usuários e R-14 aprovação do gate.

**Até a SPEC-198 (Play):**
- Specs: 197, 222 (Data Safety), 225 (compras de teste do Play) e 236.
- 216 é **recomendada** antes de abrir o teste público no Play. Não bloqueia o track interno.

## (d) Decisões do dono que bloqueiam cada onda

Toda spec tem defaults recomendados na §8. O dono só precisa intervir onde quiser fugir do default. As
decisões que **mudam escopo ou ordem**:

**Onda 0**
- Renovar os rate cards (custo real atualizado) ou ligar o kill switch de imagem/STT até a 236.

**Onda 1**
- 218 D-C: `/docs` em staging. 218 D-D: kill switch de compras.
- 236 D-A: piso de US$ 1 na reserva. 236 D-B: janela do rate card.
- 227 D-B: criação em nível alto. 227 D-C: **sem bump de schema (default)**.
- 228 D-A: sem ponto de retorno. 228 D-C: save mais novo → **409 (default)**.
- 226 D-A: XP de abate com reforços.
- 229 D-A: topônimo desconhecido. 229 D-B: fuga só estruturada.
- 230 D-A: teto de relação por turno. 230 D-B: companheiro morto na party.
- 231 D-B: quem pode estabilizar.
- 234 D-A: entidade-alvo `pacto_valerius`.
- 235 D-B: descartar pendente.
- 200 P1: meta numérica de TTFMC/TTLT. 200 P5: experimento com provider real. D3: streaming real de tokens.
- 201 Q2 = D7: arsenal visual original ou o do pacote.

**Onda 2**
- 199 D-B: linhas `[SISTEMA]` do loot ficam como estão; o recibo na UI vira spec futura.
- 232 D-B: passivas no motor de Cartas.
- 233 D-A: decaimento do perigo. 233 D-B: luz em masmorra.
- 202 P1–P4: ambiguidade, papel genérico, pronome, janela de continuidade.
- 204 P1 = D1: agrupamento das abas. 204 P2 = D2: indicador global.
- 206 Q1–Q3: notas de memória, `known_secrets`, selo "stale".
- 219 D-A: números da cota. 219 D-D: cobrança por turno.
- 220 D-B: OIDC agora ou fail-closed.
- 221 D-A: HSTS preload.
- 222 D-A: export com blobs. 222 D-B: prazos. 222 D-D: idade mínima.
- 225 D-A: Vite 6/7.

**Onda 3**
- 203 D-B: fauna atraída pelo tumulto. 203 D-C: "Continuar" consome turno.
- 207 D4: consentimento, retenção e redaction.
- 223 D-A: rigor da prova de quest. 223 D-B: catálogo por tenant.
- 224: o R-05 "mitigado" (rpg_runtime + `runtime_all`) basta para o beta pago fechado? **Recomendação: sim para a
  beta fechada, não para produção aberta.** Também 224 D-A (role admin) e D-C (`SET ROLE` por transação).

**Ondas 4 a 6**
- 205 P1–P4: confirmação de ataque, atalhos, alvo de suporte.
- 208 itens 1–6: teto de bundle, dependência nova, som, piso do reduced-motion.
- 209: reorganizar fora de zona segura, `apex`.
- 210: viagem a adjacente não visitado.
- 211: fusão de abas (D1), arte de criatura.

**Onda 7**
- D-212-1 a D-212-4.
- **D6: o beta desktop é pré-requisito do beta pago?** Recomendado sim, e esta ordem assume sim.

**P1/P2**
- 213 P1–P5 (inclui D5: `validate_narrative` fora do hot path).
- 214 P1–P4.
- 215 D0–D3.
- 217: critérios de descarte.

## (e) Itens operacionais urgentes fora de spec

1. **Rate cards de imagem e STT vencem em 2026-10-19** (achado 08-06, janela fixa de 7 dias). Depois disso, todo
   efeito caro novo fica bloqueado, porque a SPEC-196 bloqueia em vez de cobrar zero.
   - Ação até 18/10: publicar novas versões dos rate cards com preços conferidos nas páginas dos providers e manter
     o registro do card.
   - Alternativa consciente: ligar os kill switches de imagem e de fallback STT (SPEC-196) via `scripts/admin_kill_switch.py`.
   - A correção estrutural (janela configurável + alerta antecipado) é a 236 R7, que fica na onda 1.
2. **Saldo/limites dos providers** (R-11 da 197): o DeepSeek já parou campanhas por HTTP 402. Configurar limite de
   gasto e alerta de saldo antes de qualquer playtest real das ondas 1–2.
3. **Crons de FinOps/watchdog e `retry_unconsumed` do Google** (R-12): agendar no `pg_cron` do staging. Sem isso, as
   correções da 236 (varredura de reservas órfãs) não rodam.
4. **Produção:** repetir `scripts/staging/runtime_role.py` + `vercel_env.py` quando o projeto de produção existir
   (R-05). Isso não substitui a SPEC-224.
5. **Higiene do working tree:** `docs/PROXIMA_ONDA_RPG_PROMPTS_ARSENAL_VISUAL_2026-10-15.zip` está untracked.
   Versionar fora do repo ou ignorar antes do próximo push. O CI do Project Index exige rebuild limpo.

## (f) Fusões, splits e fronteiras de escopo

| Par | Decisão |
|---|---|
| 226 × 199 | **Ordem 226 → 199.** A 226 decide QUANTO XP é dado; a 199 decide ONDE o XP aparece (fora da prosa). Sem fusão. |
| 199 R12 × 232 | **Feito: R12 (carta benéfica sem alvo cura o inimigo) e a Etapa 5b saíram da 199 e foram para a 232.** A 232 já mexe em `_default_card_target` (BUG-02-20), precede a 205 e roda na onda 2. A 199 fica só com XP. |
| 223 × 199/203 | Fronteira: 223 = prova determinística de eventos propostos pelo LLM (`quest_completed` etc.) + delimitação da entrada; 199 = apresentação; 203 = elenco/desfecho do combate. **Ordem 226 → 223** (mesmos `event_processor`/`quest_log`) e **230 → 223** (`agents/npc.py`). A 223 não bloqueia a 212; bloqueia a 197. |
| 234 × 213/214 | **234 primeiro** (corrige o hot path atual); 213/214 reprojetam depois. A 234 também destrava a 206. |
| 229 × 202 | Ambas em `agents/router.py`: **229 → 202**. A 229 faz a pré-classificação determinística; a 202 só resolve o interlocutor depois disso. |
| 235 × 204/200 | **235 → 204** (o shell parte de um pending confiável). A 200 é independente, mas é **recomendado** medir depois da 235. |
| 227 × 199 D-B | Fronteira: 227 = motor de economia; o recibo/ledger de economia na UI (199 D-B) **não está em nenhuma spec**, fica para spec futura. A 227 destrava a 209. |
| 231/232 × 203/205 | **231 → 232** (mesmos arquivos). **203 depende de 231**, **205 depende de 232**. A 203 e a 232 podem rodar em paralelo: conflito só em `agents/combat.py`, quem entrar depois rebaseia. |
| 228 × 213/203 | **228 primeiro:** o R9 recusa save mais novo antes de qualquer bump de schema. É dependência dura de 202, 203, 207 e 213. |
| 218/224 × 197 | A 218 é gate de release da 197 e não conflita com o checklist já feito (`d0efb5f`). **A 224 precisa de rebase:** o commit `8570d62` (R-05 da 197) já criou o `rpg_runtime` sem BYPASSRLS, mas com policies `runtime_all`, que deixam o RLS por owner inerte. A 224 fica com `SET LOCAL ROLE rpg_api` por request, pool admin separado e Storage. Nota gravada no cabeçalho da 224. |
| 220 / 221 | **Dependências falsas removidas** do índice (220 ↛ 219, 221 ↛ 218), como o texto das próprias specs já dizia. |
| IDs errados (218–236) | Corrigidos nos cabeçalhos: 226 (SPEC-023 → 010), 229 ("SPEC-010 fase-0" → Fase 0 pré-specs; não existe spec), 230 (036 → 028), 231 (070 → 068), 233 (019 → 020 encontros), 234 (012 → 005), 235 (152 → 157; slugs de 086/111 completados). |
| Splits sugeridos | (1) **236 R7** (janela do rate card) pode virar hotfix isolado se o dono não renovar os cards até 18/10. (2) A **212** usa a 207 como evidência, mas não precisa de 213/214. (3) As **P1/P2** (213–217) não entram na 212. **Nenhuma fusão recomendada:** os pares acima têm executores/reviewers diferentes ou arquivos sequenciais. |
