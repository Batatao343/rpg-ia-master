# SPEC — Conflito v2 #04: Turnos, Iniciativa e Ataques

> **Status:** `done` (2026-07-22) — motor de resolução; fiação no nó (Etapa 6) no cutover conflito-13
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-22
> **Depende de:** `conflito-01-virtudes-vitalidade`, `conflito-02-cartas-acervo-preparacao`
> (ambas `done` antes de iniciar)
> **Desbloqueia:** `conflito-05` (dano precisa do resultado do ataque),
> `conflito-06` (reações disparam sobre ataques declarados), `conflito-08`
> (IA tática decide ações dentro desta estrutura de turno)
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

Hoje o combate resolve com `roll_initiative` (d20+mod destreza, `combat_mechanics.py:324`)
e `resolve_player_action` (`:976`, pipeline "gating → recursos/cooldown → ataque
d20+attack_bonus vs AC → dano com save → condições", crítico = d20 natural 20). É
resolvido **um round por chamada do nó de combate** (`agents/combat.py:340`), com
3 chamadas de LLM por turno (spawn 1x, parse de ação todo turno, narração todo
turno) — tudo Python puro por baixo.

`docs/valoria_conflict_migration_v2/01_..._CONFLITOS.md` §11-14 substitui a
fórmula inteira: turno com **Pré-Ação/Ação/Pós-Ação**, iniciativa por **lado**
(automática se um lado iniciou claramente, senão `2d10 + maior Agilidade
consciente do lado`), ataque = `2d10 + Virtude vs Esquiva`, Crítico por **dupla**
nos dados mantidos (1-9 = Crítico ×2, 10-10 = Supercrítico ×3 — não mais "natural
20"), Vantagem/Desvantagem = `3d10` mantendo os 2 maiores/menores (uma cancela a
outra, sem acúmulo), testes gerais = `Ímpeto + Presságio + Virtude vs dificuldade`
(dados distintos de ataque).

Esta é a spec do **motor de resolução central** — a peça mais crítica do épico.

## 2. Requisitos

- **R1** — Estrutura de turno: `Pré-Ação` (manobra simples: mudar 1 estágio de
  distância, Engajar, reposicionar aliado, alertar posição aproximada, usar objeto
  simples), `Ação` (atacar, usar Carta, Guardar, Desengajar, Fugir, Esconder-se,
  Procurar, usar objeto complexo), `Pós-Ação` (mesmo cardápio da Pré-Ação).
- **R2** — Iniciativa por lado: se um lado iniciou claramente (emboscada, ataque
  deliberado, preparação bem-sucedida, invasão clara) age primeiro automaticamente
  na 1ª rodada sem disputa. Caso contrário, cada lado rola `2d10 + maior Agilidade
  entre participantes conscientes do lado`; lado vencedor age primeiro.
- **R3** — Dentro do turno da party, jogador escolhe livremente a ordem entre
  protagonista e companheiros, podendo mudar a cada rodada. Lado inimigo usa perfil
  tático (`conflito-08`) para ordem e ações.
- **R4** — Ataque = `2d10 + Virtude(arma/carta) vs Esquiva do alvo`. Mapeamento
  padrão de Virtude por tipo de arma/carta: pesada→Força, arco/adaga/rapieira→
  Agilidade, magia precisa/arcana→Mente, comando/fé/medo/presença→Carisma,
  sangue/carne/transformação→Corpo. Carta com mais de uma Virtude permitida:
  escolha feita ao preparar (`conflito-02` R9), persiste até reorganização.
- **R5** — Crítico: qualquer dupla 1-9 nos dois dados mantidos = acerto automático
  + efeito principal ×2. Dupla 10-10 = acerto automático (Supercrítico) + efeito
  principal ×3. Vale para jogador, companheiros, NPCs e inimigos igualmente. Em
  cartas com múltiplos efeitos, só o efeito marcado como principal é multiplicado.
- **R6** — Vantagem: `3d10`, mantém os 2 maiores. Desvantagem: `3d10`, mantém os 2
  menores. Vantagem e Desvantagem se cancelam mutuamente (não empilham dados
  extras além de 3d10). Crítico é verificado nos dados **mantidos**, não nos 3
  rolados.
- **R7** — Testes gerais (fora de ataque): `Ímpeto + Presságio + Virtude vs
  dificuldade` (dados distintos entre si, distintos do par de ataque). Ímpeto
  maior = consequência favorável; Presságio maior = desfavorável; empate =
  resultado puro. Dificuldades-base: Fácil 9, Comum 12, Difícil 15, Extremo 18,
  Quase impossível 21. Ataques de combate **não** usam esta matriz.
- **R8** — Ruptura em ataque concede Vantagem. Ruptura em teste geral: rola 2 dados
  de Ímpeto + 1 de Presságio, mantém o maior Ímpeto. Ruptura e Crítico acumulam
  quando coincidem.
- **R9** — Resolução transparente: toda ação resolvida expõe dados/modificadores/
  total/Esquiva/acerto-ou-falha/Crítico-ou-Supercrítico/dano inicial/resistências/
  Proteção/Integridade/dano final/Ferimentos/estados — sem esconder a matemática do
  jogador (reaproveita o espírito do `combat_suggestions`/log atual, mas expande o
  payload).

### Fora de escopo

Dano/armadura/Ferimentos em si (`conflito-05`); Reações/AoO (`conflito-06`);
comportamento tático do inimigo (`conflito-08`); interface visual (`conflito-16`).

## 3. Design técnico

**Arquivos alterados/substituídos:**
- `combat_mechanics.py` — `roll_initiative` (`:324-347`) reescrita para iniciativa
  por lado; `resolve_player_action` (`:976-1241`) e `resolve_enemy_turn`
  (`:1555`)/`choose_enemy_attack` (`:1272`) reescritos para 2d10+Virtude vs Esquiva
  com estrutura Pré/Ação/Pós; `compute_player_combat_stats` (`:792-857`, hoje
  calcula AC = `10+dex_mod+ac_bonus`) reescrita para Esquiva derivada de Agilidade.
  Todo código de crítico `== 20` é substituído pela checagem de duplas.
- `agents/combat.py` — `combat_node` (`:340-723`) resolve **por Pré-Ação/Ação/
  Pós-Ação** em vez de "1 round = 1 chamada"; as 3 chamadas de LLM por turno
  (spawn/parse/narrar) permanecem no espírito (spawn 1x fora do conflito — vira
  `conflito-11`; parse de ação todo turno; narração todo turno), mas o parse agora
  mapeia pra `{pre_acao, acao, pos_acao}` em vez de 1 ação só.

**Schemas novos:**
```python
class TurnDeclaration(TypedDict):
    pre_acao: Optional[ActionDeclaration]
    acao: ActionDeclaration
    pos_acao: Optional[ActionDeclaration]

class AttackResolution(TypedDict):
    dice_rolled: List[int]
    dice_kept: List[int]
    total: int
    esquiva_alvo: int
    resultado: Literal["erro","acerto","critico","supercritico"]
    efeito_principal_multiplicador: int
```

## 4. Plano passo a passo

### Etapa 1 — Iniciativa por lado
1. **Testes** (`tests/test_conflito_iniciativa.py`): `test_lado_iniciador_age_primeiro_sem_disputa`;
   `test_disputa_2d10_maior_agilidade`; `test_jogador_reordena_party_a_cada_rodada`.
2. **Implementação:** reescrever `roll_initiative`.

### Etapa 2 — Resolução de ataque 2d10+Virtude vs Esquiva
1. **Testes:** `test_ataque_normal_2d10_mais_virtude`; `test_critico_dupla_1a9`;
   `test_supercritico_dupla_10`; `test_efeito_principal_multiplicado_nao_secundario`.
2. **Implementação:** reescrever pipeline de ataque em `combat_mechanics.py`.

### Etapa 3 — Vantagem/Desvantagem
1. **Testes:** `test_vantagem_3d10_mantem_dois_maiores`; `test_desvantagem_3d10_mantem_dois_menores`;
   `test_vantagem_e_desvantagem_se_cancelam`.
2. **Implementação:** função de rolagem parametrizada.

### Etapa 4 — Testes gerais (Ímpeto+Presságio)
1. **Testes:** `test_impeto_maior_consequencia_favoravel`; `test_pressagio_maior_desfavoravel`;
   `test_empate_resultado_puro`; `test_dificuldades_base_corretas`.
2. **Implementação:** função separada da resolução de ataque.

### Etapa 5 — Ruptura em ataque/teste geral
1. **Testes:** `test_ruptura_ataque_concede_vantagem`; `test_ruptura_teste_geral_dois_impeto_mantem_maior`;
   `test_ruptura_e_critico_acumulam`.
2. **Implementação:** integração com `conflito-02` (declaração de Ruptura).

### Etapa 6 — Estrutura Pré-Ação/Ação/Pós-Ação no nó de combate
1. **Testes:** `test_pre_e_pos_acao_movem_dois_estagios_no_mesmo_turno` (integra
   com `conflito-03`); `test_acao_e_obrigatoria_pre_pos_opcionais`.
2. **Implementação:** `agents/combat.py` + parse de ação em 3 partes.

## 5. Critérios de aceite

- [x] Iniciativa por lado funciona (automática quando claro, disputada 2d10+Agilidade
  quando não) — `roll_initiative_by_side`.
- [x] Ataque = 2d10+Virtude vs Esquiva; Crítico/Supercrítico por dupla, não mais
  "natural 20" — `resolve_attack`/`_crit_from_kept`.
- [x] Vantagem/Desvantagem = 3d10 mantendo 2, cancelam-se mutuamente (`roll_kept`/`net_advantage`).
- [x] Testes gerais usam Ímpeto+Presságio+Virtude vs dificuldade, com consequência
  por dado maior (`general_test`).
- [x] Resolução mostra matemática completa e transparente (payload de `resolve_attack`).
- [x] `uv run pytest` verde — **1102 passed, 1 skipped** (+19 `test_conflito_iniciativa`).

## 5.1 Desvios de implementação

- **Motor ADITIVO, não reescrita in-place**: as funções novas vivem em
  `services/conflict_resolution.py` (`roll_initiative_by_side`, `resolve_attack`,
  `roll_kept`, `general_test`, `net_advantage`, `multiply_principal`,
  `virtude_para_tipo`, `compute_esquiva`). `combat_mechanics.resolve_player_action`/
  `roll_initiative`/`compute_player_combat_stats` do motor ANTIGO ficam intactas —
  reescrevê-las in-place quebraria centenas de testes do motor vivo até o cutover.
- **Etapa 6 (estrutura Pré/Ação/Pós em `agents/combat.py`) DIFERIDA para o cutover
  `conflito-13`**: é ali que o nó troca de "1 round = 1 chamada" para o pipeline
  novo e o motor antigo é removido. Aqui entregamos o núcleo puro + testes
  exaustivos (a peça de maior risco), pronto para o nó consumir no cutover.
- **Esquiva** = 10 + Agilidade; penalidade de armadura pesada entra na `conflito-05`.
- **Virtude do inimigo legado**: `virtude_value` deriva de `attributes` (clampado
  0-5) enquanto o bestiário não é reautorado (`conflito-15`).

## 6. Smoke test com LLM real

1. Combate real (DeepSeek): declarar Pré-Ação (mudar distância) + Ação (ataque com
   Carta) + Pós-Ação num turno, confirmar que o parse mapeia as 3 partes
   corretamente.
2. Forçar (via seed/mock determinístico) uma dupla 1-9 e uma dupla 10-10, confirmar
   narração cita Crítico/Supercrítico corretamente.
3. Confirmar que testes gerais fora de combate (ex. escalar um muro) não usam a
   matriz de ataque.

## 7. Riscos & compatibilidade

- É a spec de maior risco técnico do épico — reescreve o núcleo de
  `combat_mechanics.py` (1723 linhas hoje). Cobertura de teste tem que ser
  exaustiva antes de tocar em qualquer spec seguinte.
- `agents/combat.py` muda de "1 round = 1 chamada do nó" para "resolve
  Pré/Ação/Pós" — repensar quantas chamadas de LLM por turno real acontecem (custo/
  latência não pode regredir feio; hoje é ~3 chamadas/turno).
- Toda a lógica de `combat_suggestions` (chips de UI, `combat_mechanics.py:1665`)
  precisa ser refeita em cima do novo pipeline — não é 1:1 com o antigo.
