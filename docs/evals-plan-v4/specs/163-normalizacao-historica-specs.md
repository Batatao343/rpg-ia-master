# SPEC-163 — Normalização e indexação histórica das specs

> **Status:** `draft`
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

- [ ] todos os arquivos de spec atuais têm ID único;
- [ ] `specs/index.yaml` é reproduzível no mesmo SHA;
- [ ] nenhum link interno para spec fica quebrado;
- [ ] `git grep` não encontra paths antigos fora do relatório de migração;
- [ ] conteúdo funcional das specs antigas não mudou;
- [ ] suíte de validação/documentação verde;
- [ ] relatório registra modelo(s) usados.
