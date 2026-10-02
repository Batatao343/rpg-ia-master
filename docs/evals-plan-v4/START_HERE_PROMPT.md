# Prompt inicial para o coding agent

Use este texto ao entregar o ZIP ao agente:

```text
Você recebeu o pacote rpg-evals-plan-v4 para o repositório rpg-ia-master.

Sua missão é executar as novas specs em ordem estrita conforme SPEC_EXECUTION_ORDER.md.

Antes de editar qualquer coisa:
1. leia README.md;
2. leia SPEC_EXECUTION_ORDER.md;
3. leia 12_MODEL_EXECUTION_POLICY.md;
4. leia 00_ESTADO_ATUAL.md e o AGENTS.md atual do repositório;
5. comece exclusivamente pela SPEC-163.

Regras:
- não pule specs;
- não crie SPEC-176 antecipadamente;
- use o menor modelo permitido pela política;
- tarefas mecânicas devem ser delegadas a Luna quando o ambiente permitir;
- implementação bounded deve preferir Terra;
- Sol e Astra só entram nos casos/checkpoints definidos;
- se o modelo requerido não estiver disponível, produza MODEL_HANDOFF_REQUIRED e pare no checkpoint;
- nunca finja revisão independente com o mesmo contexto;
- long-run é opt-in e NÃO deve ser executado sem pedido explícito do usuário ou spec futura explicitamente aprovada;
- não mude gameplay/prompts/model routing do RPG para melhorar baseline durante a construção da régua;
- source code é a fonte final; project_index é navegação;
- preserve todo histórico Git e referências durante a normalização das specs;
- antes de marcar uma spec done, cumpra os gates e reviews exigidos.

Ao concluir cada spec:
- registre modelo/effort usados;
- registre escaladas e motivo;
- registre comandos e resultados;
- atualize o índice de specs;
- apresente resumo curto do que mudou, gates, riscos e próxima spec.
```
