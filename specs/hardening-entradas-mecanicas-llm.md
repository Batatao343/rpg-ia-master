# SPEC — Entradas mecânicas fechadas vindas do LLM

> **Status:** `done` (2026-08-02)
> **Criada:** 2026-07-25 · **Atualizada:** 2026-08-02
> **Depende de:** `conflito-11`, `conflito-15`
> **Desbloqueia:** afirmação verificável de que números do conflito são Python

---

## 1. Contexto & Objetivo

Embora a resolução do conflito não chame LLM, o smoke/auditoria mostrou que
quantidade de inimigos, HP/AC/atributos/dano de cache miss e
`amount`/`duration` de preparação ainda podem vir como números livres da IA.
Isso viola o princípio “mecânica é Python”.

## 2. Requisitos

- **R1 — Quantidade limitada.** Scanner limita tipos e contagem no schema e
  aplica clamp defensivo antes de instanciar qualquer inimigo.
- **R2 — Bestiário conceitual.** LLM gera somente identidade/flavor e categorias
  fechadas; Python materializa Virtudes, Vitalidade, Integridade, dano e demais
  números por nível, arquétipo e tabelas curadas.
- **R3 — NPC completo.** NPC gerado recebe ficha v4 e perfil tático no momento
  da criação; ausência não cai silenciosamente em perfil genérico. Recrutamento
  e aliado transitório preservam/copiam essa ficha canônica e nunca rederivam
  Virtudes, Vitalidade ou Esquiva a partir de `attributes`/`combat_stats`
  numéricos livres da LLM.
- **R4 — Preparação estrita.** Efeitos usam catálogo, alvo presente e potência
  fechada. `amount`, `duration`, quantidade, DC ou custo livres são
  rejeitados/ignorados e recalculados por `potency_value`.
- **R5 — Defesa em profundidade.** Orquestrador valida/clampa novamente antes de
  aplicar efeito.
- **R6 — Conteúdo curado preservado.** Entradas já curadas do bestiário não são
  reescritas nem perdem seus números.
- **R7 — Perfil tático efetivo.** O estado da cena deriva gatilhos fechados
  (`aliado_em_perigo`, `aliado_ferido`, `vitalidade_baixa`, `encurralado`) em
  Python. Cada arquétipo materializa uma ação mecânica suportada — proteger,
  estabilizar/apoiar, flanquear/reposicionar, controlar, fugir ou atacar — sem
  interpretar texto livre da LLM nem reduzir toda prioridade a ataque básico.
- **R8 — Perseguição fechada.** Arquétipo materializa uma política categórica
  de perseguição (`persegue|nao_persegue`) consumida por `chase.will_pursue`.
  Predadores/caçadores podem alcançar o fugitivo; guardiões ligados ao posto e
  perfis sem motivo plausível não perseguem. Nenhum `action_hint` livre decide.

### Fora de escopo

- Autorar novos monstros/cartas.
- Rebalancear as tabelas de potência.

## 3. Design técnico

Schemas Pydantic usam `Field(ge/le)`, `Literal` e `extra="forbid"`.
Factories Python recebem `encounter_level` e arquétipo fechado. Preparação
serializa intenção categórica e materializa números somente depois da validação.
Perfis persistem uma chave de ação fechada; `action_hint` é apresentação, não
regra. O orquestrador deriva os gatilhos do estado canônico dos atores/cena e
traduz a chave para `TurnDeclaration`.

## 4. Plano passo a passo

1. **Testes:** contagem 1.000.000 não instancia em massa; múltiplos tipos
   respeitam teto.
2. **Implementação:** limites do scanner e spawn.
3. **Testes:** fake LLM com HP/AC/atributos 9999 não influencia ficha; NPC novo
   já tem sheet/perfil; recrutar ou materializar aliado de cena preserva a ficha
   v4 mesmo quando `attributes`/`combat_stats` carregam extremos conflitantes.
4. **Implementação:** schemas conceituais + factories.
5. **Testes:** `amount/duration=9999` e alvo fora de cena são
   rejeitados/recalculados; potência×nível é determinística.
6. **Implementação:** preparação e defesa no orquestrador.
7. **Testes/implementação:** cada arquétipo e gatilho relevante produz efeito
   mecânico distinto e suportado no fluxo real de `run_round`.
8. **Testes/implementação:** predador persegue e pode frustrar fuga; guardião
   não abandona o posto; política vem de chave fechada e existe em cache miss e
   conteúdo curado normalizado.

## 5. Critérios de aceite

- [x] Nenhum número livre da IA entra no resolver.
- [x] Spawn é limitado antes da alocação.
- [x] Cache miss gera ficha v4 e perfil determinísticos.
- [x] Recrutamento/aliado transitório não reintroduz números livres da LLM.
- [x] Efeito preparado só usa catálogo/potência/alvo válidos.
- [x] Perfis táticos exercem ações fechadas distintas no `run_round`.
- [x] Fuga não é sucesso automático: política fechada produz perseguidor e não
  perseguidor em casos naturais.
- [x] Conteúdo curado mantém compatibilidade.
- [x] Suíte completa verde.

## 6. Smoke test com LLM real

Provocar cache miss e preparação de encontro. Registrar conceito/categorias e
confirmar que todos os números finais correspondem às tabelas Python.

**Evidência (2026-08-02):** a matriz real observou 28 ações táticas em 10
inícios de conflito, sem número livre aceito, erro de resolver ou divergência de
Vitalidade; lint do conteúdo permaneceu sem erro/aviso.

## 7. Riscos & compatibilidade

Caches antigos são normalizados ao ler, sem edição destrutiva. A mudança pode
alterar balanceamento de criaturas geradas; os tiers curados permanecem iguais.
