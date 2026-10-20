# Mundo vivo — visão, diagnóstico e decisões do dono (2026-10-20)

Fonte das specs da iniciativa "mundo vivo". Detalhe técnico mora em cada spec.

## Diagnóstico (auditoria de 2026-10-19/20, 5 frentes)

O motor tem muitos sistemas, mas pouco conectados. O mundo **reage** ao jogador
e quase não **vive** sozinho. Várias peças estão prontas, mas desligadas ou sem
chamador. Os playtests mostram prosa boa, mas viagem só troca o cenário e NPCs e
fações não se movem entre turnos.

- **Tempo:** relógio, fações, clima e pulso do mundo só andam em viagem e
  descanso (`world_utils.advance_clock`, `agents/storyteller.py` ~532-796).
- **Fações:** 19 fações, só com progresso linear. Não guerreiam nem se aliam, e
  o jogador não tem contra-jogo. São só 6 `world_rules`, com 1 tipo de
  componente.
- **Locais:** não têm estado próprio (cerco, festa, praga, escassez). Não há
  calendário. Há só 2 baús em 35 locais, e o achado ambiental só ocorre na 1ª
  visita.
- **Quests:** nascem do texto do LLM, não do estado do mundo. Não têm prazo.
- **Combate:**
  - Cerca de 87% dos combates (lacaio/padrão) acontecem em "sala vazia"
    (`fallback_safe_scene`).
  - Os perfis táticos só fazem atacar, fugir ou se render.
  - Nenhum inimigo tem vulnerabilidade, sentidos ou hábitos.
  - `register_flee_alert` (fuga → retorno com reforços) não tem chamador, e
    `fire_reinforcement` também não.
  - O loot é genérico, não vem do inimigo. Rendição não gera prisioneiro.
- **NPCs:**
  - SPEC-215 (propagação de notícias) está `off` em staging e prod.
  - Dos traços, só o contexto `persuasao` é usado.
  - A relação com o NPC não mexe em preço nem acesso.
  - A reputação é ±12 decidida por palavra-chave.
  - NPCs não têm agenda nem vida off-screen.
  - Companheiros são só ficha de combate.
- **Narração:**
  - Clima local, perigo e saídas não chegam ao prompt (só o clima global).
  - As opções de ação são inventadas pelo LLM, não vêm da cena.
  - Rumores somem no turno seguinte.
  - Arte dinâmica `off`, sem variantes de noite ou clima, e sem som.
- **Lore sem mecânica:** raça (só ficha), Código de Ferro (0 referências no
  código), Éter/Abismo regional, religiões, crafting (6 receitas) e segredos
  (4).

## Decisões do dono

1. **Tudo importa:** o mundo anda sozinho, lembra do jogador, tem cenas táteis
   e companheiros com alma.
2. **Tempo:** continua passando só ao **dormir e viajar**. O mundo simula **1x
   por dia de jogo virado**. Nada de custo de tempo por ação.
3. **Diretor de mundo:**
   - Um **motor determinístico** rola eventos com modificadores, propõe
     eventos/crises e move NPCs (agenda, viagem, troca de lado, morte
     off-screen).
   - Uma **LLM ocasional** (≤ 1 chamada por dia de jogo) só **narra** o que o
     motor decidiu. A LLM nunca decide.
   - O motor tem de se comportar como um mundo, não como uma máquina de crises.
4. **Ritmo:** ecossistema mais curva de tensão.
   - Cada região tem pressões (ex.: fome, guerra, praga, fé) que sobem e descem
     por causas, com evento só ao cruzar um limiar.
   - Por cima, um orçamento global de tensão (calmo → tensão → crise →
     recuperação) limita as crises simultâneas.
5. **Dureza:** o mundo é duro, mas telegrafado. Quest com prazo falha, NPC
   querido pode morrer, cidade pode cair, sempre com aviso antes (rumor,
   sinal).
6. **Reputação em 4 níveis:** por NPC, por fação, por local (fama) e por
   raça/origem (reação conforme a lore).
7. **Visibilidade:** rótulos vagos ("desconfiado / amigável / leal") e
   mudanças ("Brenna não gostou disso"), sem números.
8. **Companheiros:** autonomia alta, com aviso. Opinam, discordam e têm missão
   pessoal. Com aprovação em queda, avisam e depois saem (ou traem, se o traço
   permitir).
9. **Ordem:** Onda 0 (religações) → **C. Sociedade viva** → **A. Mundo
   autônomo** → **D. Presença e sentidos** → **B. Combate vivo**. Os quatro
   pilares serão feitos.

## Onda 0 — religar o que já existe

1. SPEC-215: `RPG_NPC_KNOWLEDGE` em `shadow` → `on` no staging, medido por
   playtest.
2. Chamar `register_flee_alert` quando um inimigo foge (fuga → retorno com
   reforços).
3. Bloco de ambiente (clima local, período, perigo, luz, saídas) no
   storyteller, no `npc_actor` e na narração de combate.
4. Traços nos contextos de DC `comercio`, `intimidacao` e `insight`.
5. Persistir o pulso do mundo como `world.news` (últimos N), injetar no
   contexto e mostrar na UI.

## Restrições permanentes

- Mecânica em Python, determinística por seed. A LLM propõe ou narra, o motor
  aplica.
- "O mundo não escala com o herói."
- Sem regressão nas metas de letalidade da SPEC-285.
- Não onisciência: o jogador só vê o que o personagem saberia.
