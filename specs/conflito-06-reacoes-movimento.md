# SPEC — Conflito v2 #06: Reações, Ataques de Oportunidade e Movimento Tático

> **Status:** `draft`
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-22
> **Depende de:** `conflito-02-cartas-acervo-preparacao`, `conflito-03-zonas-cena-objetos`,
> `conflito-04-turnos-iniciativa-ataques` (todas `done` antes de iniciar)
> **Desbloqueia:** `conflito-08` (perfil tático decide quando reagir/Engajar),
> `conflito-09` (fuga usa Desengajar/AoO)
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

O combate atual não tem sistema de reação nem de Engajamento — ações são
sequenciais por ordem de iniciativa sem interrupção. `docs/valoria_conflict_migration_v2/
01_..._CONFLITOS.md` §16-18 introduz Cartas do tipo Reação com gatilho, cadeias de
reação limitadas (1 reação comum por personagem por cadeia), Ataques de
Oportunidade como reação universal **sem** esse limite, e as manobras de
Engajar/Desengajar/Guardar/Esconder-se/Procurar que dão sentido tático ao
posicionamento definido em `conflito-03`.

## 2. Requisitos

- **R1** — Sequência de reação: (1) ação declarada com alvos/escolhas/custos
  definidos → (2) abre-se janela de reação → (3) reações válidas escolhidas e
  pagas → (4) ação original resolvida. A declaração original não muda depois da
  janela aberta.
- **R2** — Jogador, companheiros e inimigos podem reagir. Inimigo reage conforme
  perfil tático + recursos + gatilho (pode exigir Entropia). Reações podem
  responder a reações quando o gatilho permitir.
- **R3** — Cada personagem usa no máximo **1 reação comum** por cadeia. Cadeia
  termina quando ninguém tem ou quer usar outra reação válida. A mesma Carta não
  repete na mesma cadeia salvo texto explícito nela.
- **R4** — Ordem-base de reação: alvo direto → aliados do alvo → aliados do ator →
  maior Agilidade em conflito de ordem → critério estável de desempate. Quando a
  party tem mais de uma reação válida sem conflito de ordem, o jogador escolhe.
- **R5** — Ataque de oportunidade: reação **universal** disparada por abandonar
  Engajamento sem Desengajar. **Não** conta pro limite de "1 reação comum por
  cadeia" — cada inimigo Engajado, consciente e capaz pode fazer o seu próprio.
  Vale nos dois sentidos (party contra inimigo que abandona Engajamento também).
- **R6** — Engajar: custa Pré-Ação ou Pós-Ação. Corpo a corpo comum exige Próximo +
  Engajado. Um personagem pode estar Engajado com vários inimigos simultaneamente.
- **R7** — Desengajar: custa a Ação. Encerra com segurança os Engajamentos
  escolhidos, evitando AoO.
- **R8** — Guardar: custa a Ação. Enquanto Guardando, ataques Defensáveis contra o
  personagem sofrem Desvantagem, e os ataques do próprio personagem também sofrem
  Desvantagem. Pode ser abandonado livremente antes de agir (perde a proteção).
  Não depende de escudo — postura universal.
- **R9** — Esconder-se: custa a Ação, exige fonte plausível (escuridão, fumaça,
  vegetação, multidão, cobertura, obstáculo). Ocultação é relativa por observador
  — Escondido de um, Visível para outro.
- **R10** — Sem posição conhecida: não pode atacar diretamente; pode Procurar,
  atacar área coerente, ou usar habilidade apropriada. Com posição aproximada:
  ataca com Desvantagem (acertar não remove Escondido). Procurar custa a Ação;
  encontrar deixa Visível só pra quem encontrou; alertar a party custa Pré/Pós-
  Ação e propaga posição aproximada pra todos.
- **R11** — Mudar de distância, trocar esconderijo ou ser reposicionado encerra
  Escondido (ajustes pequenos dentro do mesmo local não contam). Atacar oculto
  concede Vantagem; permanece Escondido durante toda a resolução, vira Visível
  depois (mesmo errando), salvo Carta específica.

### Fora de escopo

Fuga/perseguição fora do combate imediato (`conflito-09`); IA de quando o inimigo
escolhe reagir/Engajar (`conflito-08` — aqui só a mecânica existe, a decisão
autônoma é da spec 08); UI de janela de reação (`conflito-16`).

## 3. Design técnico

**Arquivos novos:**
- `services/reactions.py` — `open_reaction_window(declared_action) -> ReactionChain`,
  `offer_reaction(chain, participant_id, card_id) -> bool` (valida gatilho+limite
  de 1 comum+Entropia), `resolve_chain(chain) -> List[ResolvedReaction]`,
  `trigger_opportunity_attack(scene, leaving_participant_id) -> List[ResolvedReaction]`
  (fora do limite de cadeia comum).

**Arquivos alterados:**
- `services/conflict_scene.py` (`conflito-03`) — `engage`/`disengage`/`guard`/`hide`/
  `search` como funções de manobra, consumindo Pré-Ação/Ação/Pós-Ação conforme R6-R10.
- `combat_mechanics.py` — ataques passam a checar janela de reação antes de
  resolver (integração com `open_reaction_window`).

**Schema:**
```python
class ReactionChain(TypedDict):
    triggering_action: Dict
    used_common_reaction: Set[str]  # participant_ids que já gastaram a comum
    links: List[Dict]  # sequência de reações resolvidas
    closed: bool
```

## 4. Plano passo a passo

### Etapa 1 — Janela de reação + limite de 1 comum por cadeia
1. **Testes** (`tests/test_conflito_reacoes.py`): `test_reacao_valida_antes_da_rolagem`;
   `test_um_personagem_nao_usa_duas_reacoes_comuns_na_mesma_cadeia`;
   `test_cadeia_termina_quando_ninguem_tem_reacao_valida`.
2. **Implementação:** `services/reactions.py`.

### Etapa 2 — Reação responde reação + ordem
1. **Testes:** `test_reacao_pode_responder_reacao_com_gatilho_valido`;
   `test_ordem_alvo_direto_depois_aliados_depois_agilidade`.
2. **Implementação:** idem.

### Etapa 3 — Ataques de oportunidade (sem limite de cadeia)
1. **Testes:** `test_fuga_engajado_gera_aoo_de_todos_inimigos_aptos`;
   `test_aoo_nao_conta_pro_limite_de_reacao_comum`.
2. **Implementação:** `trigger_opportunity_attack`.

### Etapa 4 — Engajar/Desengajar/Guardar
1. **Testes:** `test_engajar_custa_pre_ou_pos_acao`; `test_desengajar_custa_acao_evita_aoo`;
   `test_guardar_desvantagem_nos_dois_lados`.
2. **Implementação:** `conflict_scene.py`.

### Etapa 5 — Esconder-se/Procurar/alertar
1. **Testes:** `test_esconder_exige_fonte_plausivel`; `test_ocultacao_relativa_por_observador`;
   `test_atacar_com_posicao_aproximada_tem_desvantagem`; `test_alertar_party_propaga_posicao_aproximada`.
2. **Implementação:** idem.

## 5. Critérios de aceite

- [ ] Cadeia de reação respeita 1 comum por personagem; AoO é ilimitado à parte.
- [ ] Engajar/Desengajar/Guardar/Esconder-se/Procurar funcionam com o custo certo
  de Pré/Ação/Pós-Ação.
- [ ] Ocultação é por observador, não global.
- [ ] `uv run pytest` verde.

## 6. Smoke test com LLM real

1. Combate real: jogador foge Engajado sem Desengajar, confirmar narração
   descreve os ataques de oportunidade dos inimigos aptos.
2. Jogador se esconde e ataca — confirmar Vantagem aplicada e ocultação encerrada
   só depois da resolução.

## 7. Riscos & compatibilidade

- Reações em cadeia adicionam uma fase nova de resolução por ataque — cuidar de
  latência/número de chamadas de LLM (idealmente zero LLM extra, tudo Python; a
  LLM só narra o resultado consolidado).
- Depende de `conflito-03` (zonas/distância) e `conflito-04` (ataque) estarem
  `done` — não paralelizar com elas.
