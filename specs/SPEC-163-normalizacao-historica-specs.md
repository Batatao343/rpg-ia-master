# SPEC-163 — Normalização e indexação histórica das specs

> **Status:** `done`
> **Modelo executor mínimo:** Terra High
> **Delegação recomendada:** Luna para inventário, extração de metadata, relatórios e verificação de links
> **Revisão externa:** não obrigatória; gates determinísticos prevalecem

## 1. Objetivo

Dar identidade estável a todas as specs existentes sem inventar uma ordem manual. O ID representa **ordem de criação**, enquanto `completed_order` representa **ordem comprovável de conclusão**.

## 2. Requisitos

- **R1** — inventariar todas as specs atuais, excluindo `TEMPLATE.md`;
- **R2** — descobrir o primeiro commit da linhagem de cada spec pelo histórico Git (`--follow`/rename-aware);
- **R3** — ordenar por primeiro commit; empates no mesmo commit usam slug atual em ordem lexical e registram `tie_breaker`;
- **R4** — atribuir IDs permanentes `SPEC-001...SPEC-162` sem reutilização futura;
- **R5** — descobrir o primeiro commit em que o status comprovadamente aparece como `done`; se não for possível provar, usar `completed_at: null`, nunca inferir;
- **R6** — gerar `specs/index.yaml` com id, slug, status, created commit/date, completed commit/date, completed_order, depends_on;
- **R7** — renomear arquivos para `SPEC-NNN-<slug>.md` e atualizar links/referências no repo de forma automatizada;
- **R8** — esta própria spec permanece `SPEC-163` e nunca é reordenada depois da migração;
- **R9** — gerar relatório de migração com old_path -> new_path e evidência Git.

## 3. Guardrails

- não alterar requisitos/conteúdo semântico das specs antigas;
- não mudar status histórico para “arrumar” sequência;
- não numerar por data de conclusão;
- IDs nunca mudam após atribuídos;
- qualquer lineage ambígua fica registrada, não adivinhada.

## 4. Model routing

Luna pode fazer o inventário e produzir as tabelas derivadas. Terra deve implementar/revisar o script de migração e executar renames/rewrite de referências. Escalar a Sol somente se o histórico tiver renames/merges ambíguos que o algoritmo determinístico não resolva.

## 5. Aceite

- [x] todos os arquivos de spec atuais têm ID único;
- [x] `specs/index.yaml` é reproduzível no mesmo SHA;
- [x] nenhum link interno para spec fica quebrado;
- [x] referências de produção/documentação foram reescritas; paths antigos ficam
  somente no relatório de migração, no pacote-fonte imutável e nas fixtures do migrador;
- [x] conteúdo funcional das specs antigas não mudou;
- [x] suíte de validação/documentação verde;
- [x] relatório registra modelo(s) usados.

## 6. Execução no repositório (2026-09-27)

- Etapa iniciada pelo pedido do usuário para começar a implementação do pacote v4.
- Fonte importada, com os 43 hashes do manifesto verificados: [plano v4](../docs/evals-plan-v4/README.md).
- Âncora local: `cadbdd1013022c98f506ee335fa9072efcc9df6c` (`main`); o SHA
  observado pelo pacote é histórico e não substitui o checkout atual.
- Entrega concluída: 162 specs históricas normalizadas e esta SPEC-163 indexada.
  SPEC-164–175 permanecem no pacote, sem implementação.
- `execution_model: gpt-5.6-terra`, `execution_effort: high`; inventário delegado a
  `gpt-5.6-luna` (`high`). Coordenação no agente raiz já ativo; custo não otimizado
  desse contexto, conforme exceção da política. Nenhuma revisão independente exigida.
- O migrador preserva o conteúdo das specs antigas, salvo as referências mapeadas,
  e revalida a proveniência imutável do índice contra o Git.
- Gates: verificador da migração verde; 7 testes focados verdes; Ruff verde; lint de
  conteúdo com zero erro/aviso; suíte offline completa verde com 1.807 testes
  executados, 35 skips opt-in e 15 testes reais desmarcados.
- Nenhum provider real, campanha longa, mudança de gameplay, prompt ou rota de LLM.
