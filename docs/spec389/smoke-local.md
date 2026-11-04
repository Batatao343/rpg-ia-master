# Smoke local (LLM real): SPEC-389 §6 itens 2–11

Feito em 04/11/2026 pelo agente de smoke local. O item 1 (staging, S7-1) é do coordenador e não está aqui.

**Ambiente.** Cópia `git archive` de `2b17aee2` fora do OneDrive, `web/dist` gerado dela, `.env` copiado (nenhum valor impresso). Perfil `legacy`. APIs: `:8770` (preset `scripts/staging/staging_flags.json`, cartas `on`, mais `RPG_CREATURE_ART=on`, rotas default) e `:8771` (mesmo preset + `RPG_ROUTES={"classify":[["groq","modelo-inexistente"]]}`). Saves de `seed_save` (MockLLM) com os corpos de `smoke_body` (`tests/fixtures/spec368_seed.py`); as rodadas jogadas foram contra o LLM real (as do meio de combate não chamam LLM). Prints a 390 e 1440 com Playwright. APIs mortas por PID, cópia apagada no fim. Evidências brutas (JSON de resposta/estado, logs, prints) ficaram no scratchpad da sessão e não entram no repo.

**LLM.** DeepSeek em todas as chamadas (`llm_providers: {deepseek: N}`); na `:8771` o CLASSIFY `groq/modelo-inexistente` falhou como pedido (1 falha, sem candidato seguinte) e a narração foi DeepSeek. Nenhuma queda inesperada para fallback.

## Tabela item → resultado

| Item | Resultado | Evidência |
|---|---|---|
| 2 `14 entrega` | **ok**. "Entrego a prova da caça ao contratante" fechou a quest `q368` (`status completed`, `resolved_turn 5`). `turn_outcome`: `source: "quest"`, `quests_completed [q368]`, +200 XP, +20 ouro. Técnica "Madeira de Naufrágio" (`neu1_br_madeira_de_naufragio`) no Acervo: cartas 6 → 7 (`cards.card_offered source=missao picked=true`). **0** ocorrências de `replan` no log do turno (nada de `campaign.replan reason=region_change`). **Rota:** `router.decision route=npc_actor source=classify`; `speaker = {kind: npc, id: contratante, reason: direct_address}`. Fechou pela rota NPC, 1 de 1 tentativa; a rota storyteller não foi exercitada (ver achado 3). | `r2.json`, `s2-after.json`, `log2.txt` |
| 3 `2 frustrar` | **ok**. 1 rodada: "Presságio frustrado: Goblin" na mensagem e, a 390, no bloco "EFEITOS DA RODADA" da aba Combate (o painel que no 387 não listava o frustrado). | `r-i3.json`, `i3-390-Combate.png/.txt` |
| 4 `13 voto` | **ok**. "Goblin, provocado por Hi4, muda de alvo." no registro; sem "próxima intenção" depois do desvio; o goblin atacou "Você". Ressalva: nome do herói no texto (achado 1). | `r-i4.json` |
| 5 `13 armadura` (`ruptura: true`) | **ok**. `/game/state` → `combat.enemies[0].conditions` traz `name: "Armadura Comprometida"`, `id: armadura_comprometida`, `label` igual ao `name` (o `name` não é mais o id cru; R13). | `r-i5.json`, `s-i5.json` |
| 6 `13 reacao` (`reaction_card_id`) | **ok**. Registro: "Você reage com Encaixe do Golpe em Goblin: acerta — 8 de dano, ferimento grave na cabeça do Goblin."; a narração final cita a Reação ("O Encaixe do Golpe desce com a Espada Gasta e abre a cabeça do Goblin…"). Vitória, sem ids. | `r-i6.json` |
| 7 `4 falha` | **ok**. "Escoltado morre." na rodada 1; `combat.scene_objective_resolved ok=false`; a narração conta a causa ("o Escoltado não resistiu", "objetivo perdido"); herói de pé e ileso (Vitalidade 18, sem "perde os sentidos", `game_over false`). R20 da 387 agora verificado. | `r-i7.json`, `log-i7.txt` |
| 8 `12 hostil` (CLASSIFY inexistente) | **ok**. "Ataco o goblin": `router.decision route=combat_agent source=hostility_fallback fallback_reason=not_router_decision`; `combat.started`; `combat.active=true`, rodada 0. A narração DeepSeek citou o goblin com ameaça (a seed da R17 resolveu a dependência do achado 4 da 387). | `r-i8.json`, `log-i8.txt` |
| 9 `draft.py` | **ok**. 1 chamada SMART (`--postura "Médico de Campo" --subclasse boticario --n 4 --raridades comum,incomum`): pediu 4, entregou 3, 1 fora do vocabulário, custo estimado US$ 0,0026. Os 3 comandos impressos rodaram sem editar a linha (só trocando `bash scripts/dev/py.sh` pelo python do venv): `lint` 3 verdes / 0 reprovadas (antes 2 de 4 reprovadas); `sim lote-v2` sem bandeiras (deltas −10,0 / 0,0 / −7,5 pp); `promote` (linha impressa já traz `--voz-pendente`): 3 promovidas, 0 recusadas. | `draft.out`, `lint.out`, `sim.out`, `promote.out` |
| 10 UI 390 e 1440 | **ok**. Seed `6 espolio`, escolha de "Pó nos Olhos" via `POST /game/espolio`; a Ficha/Acervo mostra "Pó nos Olhos · Mão Sombria  preparada · ativa" a 390 e a 1440 (`subclass: "Mão Sombria"` na API). | `i10-390-Personagem.png/.txt`, `i10-1440-Personagem.png/.txt` |
| 11 varredura `/game/history` | **1 achado**. 10 campanhas, 38 entradas: 0 ids (regex de prefixos + qualquer `palavra_palavra` + hex de 24), 0 `": … terminou"`, 0 "cumpre o presságio", 0 "Ataque sem alvo". **1 ocorrência do nome do herói**: "Goblin, provocado por Hi4, muda de alvo." (achado 1). | `scan.py` (saída: `hero_name 1`) |

## LLM, custo

- Turnos com LLM: 4 (item 2 NPC: 3 chamadas = classify + FAST + SMART; itens 6, 7: 2 cada = FAST narrador + SMART arquivista; item 8: classify falho + FAST) + 1 `draft.py` (1 SMART, sem reparo). Itens 3, 4, 5: 0 chamadas.
- Provider: DeepSeek em tudo. Custo estimado: item 2 US$ 0,0031; item 6 0,0013; item 7 0,0016; item 8 0,0006; `draft.py` 0,0026: **~US$ 0,0092**. 0 retrato pago. Latência: turno NPC 10,4 s; rodada final de combate ~5–7 s.

## Achados

1. **P3: nome do herói no registro do Voto.** "Goblin, provocado por Hi4, muda de alvo." sai na mensagem e no `/game/history`, quebrando o "0 nome do herói" do item 11. No resto do registro o herói é "Você" (a linha do R12 usa `provocado por .+`, e o teste aceita qualquer nome). Sugestão: usar "você" quando o provocador é o jogador.
2. **P3: `turn_outcome.quests_completed` com título igual ao id.** `{"id": "q368", "title": "q368"}` (o título da quest no log é "Caça"). Se a UI exibir o recibo, mostra o id. Pode ser artefato da seed (`q368` foi criada por `seed_save`); quests reais vêm com título do gerador. Conferir antes de tratar como bug.
3. **Observação (item 2): rota.** A quest fechou pela rota **NPC** (`npc_actor`, `source=classify`, `speaker.kind=npc`, `reason=direct_address`) na 1ª tentativa. Não foi exercitado se a mesma frase, sem nomear/endereçar o NPC (ou com o NPC fora de cena), chega ao `npc_actor`; só 1 turno com LLM neste item.
4. **P3 (texto): "Você está provocado: a próxima intenção dele mira Soldado (com chance)."** (item 5, depois de o Soldado jogar "Uivo de Comando"): o sujeito é o jogador, mas "dele" aponta para o Soldado; leitura ambígua.
5. **Observação:** `sim lote-v2` do lote do `draft.py` não deu `dominante`/`uso_alto` desta vez (`taxa_uso` 0,10 / 0,0 / 0,23); amostra de 3 Cartas de uma postura.

## Não verificado

- Item 1 (staging, S7-1): com o coordenador.
- Item 2: a rota storyteller para a mesma entrega (achado 3); a técnica aparece no Acervo só pela API/estado (6 → 7 cartas), sem print da UI.
- Item 11: amostra pequena (38 entradas, quase todas de combate); sem campanha longa.
