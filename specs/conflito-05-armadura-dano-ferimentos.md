# SPEC — Conflito v2 #05: Armadura, Tipos de Dano e Ferimentos

> **Status:** `draft`
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-22
> **Depende de:** `conflito-01-virtudes-vitalidade`, `conflito-04-turnos-iniciativa-ataques`
> (ambas `done` antes de iniciar)
> **Desbloqueia:** `conflito-07` (morte precisa de Ferimentos Críticos preenchidos),
> `conflito-08` (bestiário precisa de armadura/resistências completas)
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

Hoje dano é um número que subtrai de `hp` direto (com `damage_type` afetando
DoT/condições, mas sem Proteção/Integridade/localização). `docs/valoria_conflict_migration_v2/
01_..._CONFLITOS.md` §19-22 introduz: dano-base por categoria de arma, tipos de
dano físico (Cortante/Perfurante/Impactante) e sobrenatural (Ígneo/Gélido/
Elétrico/Arcano/Corrosivo/Abissal) com efeitos específicos, Resistência/
Vulnerabilidade/Imunidade, armadura com Proteção+Integridade (reduz Gravidade,
fica Comprometida em 0), e o excedente sobre Vitalidade vira **Ferimento
localizado** (Leve/Grave/Crítico) que agrava na mesma região.

Esta spec conclui o pipeline de resolução iniciado em `conflito-04`: do "acerto
confirmado" até "Ferimento aplicado".

## 2. Requisitos

- **R1** — Dano-base por categoria de arma: Leve 1 mão = 3, Marcial 1 mão = 4,
  Versátil 2 mãos = 6, Pesada 2 mãos = 8. Armas lendárias têm limites próprios
  (leve até 6, média até 9, pesada até 12) e regras individuais, fora do limite
  comum de propriedades.
- **R2** — Tipos de dano físico: Cortante (aplica Sangramento — 1 Vitalidade ao fim
  do próximo turno, não acumula), Perfurante (reduz Proteção da armadura em 1
  naquele ataque), Impactante (armadura perde 1 Integridade adicional quando
  protege).
- **R3** — Tipos sobrenaturais: Ígneo (+2 dano imediato se ≥1 dano atravessar),
  Gélido (próximo ataque contra o alvo ganha Vantagem se ≥1 atravessar), Elétrico
  (alvo sofre Desvantagem no próximo ataque se ≥1 atravessar), Arcano (remove
  benefício temporário mágico/sobrenatural/de carta), Corrosivo (redução adicional
  de Gravidade custa 2× Integridade quando armadura compatível é usada), Abissal
  (alvo fica Exposto se ≥1 atravessar; próximo ataque ignora Resistência/
  Resistência Maior mas não Imunidade).
- **R4** — Resistência reduz 2, Resistência Maior reduz 4, Vulnerabilidade aumenta
  2, Vulnerabilidade Maior aumenta 4, Imunidade zera. Fontes iguais não acumulam;
  Resistência e Vulnerabilidade se compensam pela intensidade (não somam
  ilimitadamente).
- **R5** — Armadura: `{categoria ("leve"|"media"|"pesada"), protecao, integridade_max,
  integridade_atual, penalidade_esquiva, reducoes_maximas_por_ataque}` (tabela
  fixa: Leve 1/4/0/1, Média 2/6/-1/2, Pesada 3/8/-2/3). Proteção reduz Gravidade
  automaticamente após o acerto; jogador pode gastar Integridade pra reduzir
  categorias adicionais, respeitando `reducoes_maximas_por_ataque`. Em 0
  Integridade, fica **Comprometida** (mantém Proteção básica+penalidades, não gasta
  Integridade, perde propriedades especiais/resistências).
- **R6** — Escudo: `{categoria, protecao, integridade_max, requisito_forca,
  efeito_adicional}` (Broquel 1/3/nenhum, Comum 2/5/Força2, Pesado 3/7/Força3
  "-2 Esquiva e Desvantagem em testes de Agilidade"). Armadura e escudo **não
  somam** — jogador escolhe qual usa por ataque Defensável. Abaixo do requisito de
  Força, usuário sofre Desvantagem nos próprios ataques.
- **R7** — Ataque marcado `defensavel: bool` no schema de Carta/arma: só ataques
  Defensáveis são dificultados por Guardar e permitem uso de escudo compatível;
  não-Defensáveis ignoram esses benefícios (armadura ainda funciona se
  compatível).
- **R8** — Ordem da defesa (fixa, não reordenável por conteúdo): (1) dano+
  multiplicador de Crítico, (2) Imunidade/Resistência/Vulnerabilidade, (3)
  Proteção, (4) Integridade, (5) Vitalidade e Gravidade, (6) Ferimentos e efeitos
  secundários.
- **R9** — Excedente sobre Vitalidade é comparado aos **Limites de Gravidade**
  (`conflito-01` R5) do alvo e cria Ferimento Leve/Grave/Crítico. Ferimento tem
  região (depende de tipo de ataque/trajetória/anatomia/posição/ataque
  direcionado — direcionado sofre penalidade de acerto). Mesma região agrava:
  Leve+Leve=Grave, Leve+Grave=Crítico, Grave+Leve=Crítico. Categoria cheia escala
  pra seguinte. Todo local do corpo pode gerar Crítico — sem instakill automático
  por região.
- **R10** — Sangromante: pode pagar Cartas com Vitalidade até 0; déficit além disso
  vira Ferimento pelos próprios limites de Gravidade. Armadura não protege contra
  esse sacrifício voluntário.
- **R11** — Recuperação de Integridade: descanso curto recupera metade
  (arredonda pra cima), descanso longo recupera tudo. Ferimento Leve: removido
  grátis em descanso curto ou após longo. Ferimento Grave: kit/habilidade em
  descanso curto suprime consequência + agenda remoção no próximo longo (custa 1
  carga de kit). Ferimento Crítico: Médico de Campo com kit conta como
  intervenção adequada (custa 2 cargas); personagem comum com kit só estabiliza.

### Fora de escopo

Última Ação/Estado Terminal/morte (`conflito-07`); armadura/resistência específica
de cada criatura do bestiário (`conflito-15`); UI de Ferimentos localizados
(`conflito-16`).

## 3. Design técnico

**Arquivos alterados:**
- `combat_mechanics.py` — pipeline de dano pós-acerto totalmente reescrito
  (função nova `resolve_damage_and_wounds(attack_result, target, damage_type,
  weapon_or_card) -> DamageResolution` na ordem fixa R8); remove lógica atual de
  `hp -= dano` direto.
- `state.py` — `PlayerStats`/`EnemyStats` ganham `wounds: {leve: int, grave: int,
  critico: int}` (contagem preenchida por região, ver R9) e `armor: Optional[Armor]`,
  `shield: Optional[Shield]`.
- `gamedata.py` — tabelas de armadura/escudo (R5/R6), dano-base por categoria de
  arma (R1).

**Schemas:**
```python
class Armor(TypedDict):
    categoria: Literal["leve","media","pesada"]
    protecao: int
    integridade_max: int
    integridade_atual: int
    comprometida: bool

class Wound(TypedDict):
    categoria: Literal["leve","grave","critico"]
    regiao: str
    suprimida: bool  # tratada, aguardando remoção no descanso longo
```

## 4. Plano passo a passo

### Etapa 1 — Dano-base + tipos físicos
1. **Testes** (`tests/test_conflito_dano.py`): `test_dano_base_por_categoria_arma`;
   `test_cortante_aplica_sangramento`; `test_perfurante_reduz_protecao_um`;
   `test_impactante_reduz_integridade_extra`.
2. **Implementação:** `combat_mechanics.py`.

### Etapa 2 — Tipos sobrenaturais
1. **Testes:** um teste por tipo (Ígneo/Gélido/Elétrico/Arcano/Corrosivo/Abissal)
   confirmando o efeito condicionado a "≥1 dano atravessar".
2. **Implementação:** idem.

### Etapa 3 — Resistência/Vulnerabilidade/Imunidade
1. **Testes:** `test_resistencia_reduz_2`; `test_fontes_iguais_nao_acumulam`;
   `test_resistencia_e_vulnerabilidade_se_compensam`.
2. **Implementação:** idem.

### Etapa 4 — Armadura/Escudo/Integridade/Comprometida
1. **Testes:** `test_protecao_reduz_gravidade_automatico`; `test_gastar_integridade_reduz_categoria_extra`;
   `test_integridade_zero_fica_comprometida`; `test_armadura_e_escudo_nao_somam`.
2. **Implementação:** idem + `state.py`.

### Etapa 5 — Ferimentos localizados + agravamento
1. **Testes:** `test_excedente_cria_ferimento_pelos_limites_de_gravidade`
   (reusa tabela `conflito-01`); `test_mesma_regiao_agrava_leve_mais_leve_vira_grave`;
   `test_categoria_cheia_escala_para_seguinte`.
2. **Implementação:** `resolve_damage_and_wounds`.

### Etapa 6 — Sacrifício de Vitalidade (Sangromante) + recuperação
1. **Testes:** `test_sangromante_paga_com_vitalidade_ate_zero_depois_vira_ferimento`;
   `test_armadura_nao_protege_sacrificio_voluntario`; `test_descanso_curto_remove_ferimento_leve`;
   `test_ferimento_grave_precisa_kit_custa_1_carga`.
2. **Implementação:** integração com `conflito-02` (custo de Carta) e sistema de
   descanso existente.

## 5. Critérios de aceite

- [ ] Pipeline de dano segue a ordem fixa R8, transparente no log.
- [ ] Cada tipo de dano (6 sobrenaturais + 3 físicos) tem efeito correto e testado.
- [ ] Armadura/escudo não somam; Integridade zerada = Comprometida.
- [ ] Ferimento localizado agrava corretamente na mesma região.
- [ ] `uv run pytest` verde.

## 6. Smoke test com LLM real

1. Combate real: dano Cortante aplicado, confirmar narração menciona Sangramento
   no próximo turno.
2. Forçar armadura a 0 Integridade, confirmar HUD/narração trata como
   Comprometida.
3. Dois Ferimentos Leves na mesma região viram Grave — confirmar narração reflete
   a escalada.

## 7. Riscos & compatibilidade

- Depende inteiramente do resultado de ataque da `conflito-04` — não pode começar
  antes dela estar `done`.
- Bestiário atual (`data/bestiary.json`) não tem armadura/resistência tipada hoje
  — placeholder mínimo aqui, conversão completa é `conflito-15`.
- `active_conditions`/DoT existente (Sangramento é semelhante a um DoT já
  modelado) — reaproveitar a estrutura de `Condition` onde fizer sentido, evitar
  sistema paralelo.
