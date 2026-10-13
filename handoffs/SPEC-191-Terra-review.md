# SPEC-191 — handoff para executor Terra High

**Estado em 13/10/2026:** `MODEL_HANDOFF_REQUIRED`. Terra High não está
disponível entre os modelos desta sessão. A spec proíbe substituição sem
autorização explícita do usuário; este handoff prepara a execução, sem criar
recursos remotos ou aplicar migrations.

## Dependência e autorização externa

- SPEC-191 está `approved`, mas exige SPEC-190 `done`; o fechamento de
  SPEC-190 está em revisão. Não iniciar operações remotas da SPEC-191 antes
  desse gate.
- O usuário escolheu a organização Supabase **jm0nteiroz**
  (`xhvlcfmmnzcngwhkxkqi`) para um projeto novo do `rpg-ia-master`. A
  organização está no plano Free. `supabase_get_cost` informou custo de
  criação **US$ 0/mês**; consumo posterior segue os limites do plano.
- A conexão atual enxerga essa organização, `Dashboard_Maxsystem` ativo e
  `Nexora Root Cause` inativo. `supabase_get_project` para o projeto sugerido
  anteriormente (`uzeagzcyvxzrpjgrhaql`) ainda retorna falta de permissão.
  Não usar nem modificar nenhum dos projetos existentes.
- A SPEC-191 requer aprovação externa antes de criar projeto/recurso. Quando
  dependência e modelo estiverem resolvidos, pedir confirmação de custo pelo
  conector e criar um projeto **separado**, nome sugerido
  `rpg-ia-master-staging`, região sugerida `sa-east-1`.

## Execução e evidência esperada

1. Linkar o projeto staging separado; promover todas as migrations a partir
   de zero pelo workflow reproduzível, sem mudanças manuais como fonte de
   verdade.
2. Configurar Auth, email, RLS, pgvector, Storage privado, secrets por
   ambiente, pooler e SSL. Não usar dados pessoais ou produção.
3. Criar dois usuários sintéticos de staging e demonstrar isolamento A/B em
   Auth, RLS, Storage e pgvector, inclusive signed blobs.
4. Rodar Security/Performance Advisors e registrar findings e correções;
   zero error/high não justificado.
5. Testar a mesma configuração pooler/SSL consumida pela SPEC-192.
6. Fazer backup e restore portátil em ambiente descartável com dados e
   objetos sintéticos; documentar custo/config/IDs não secretos.
7. Submeter a evidência e o diff a reviewer Sol High independente antes de
   marcar a SPEC-191 `done` e avançar à SPEC-192.

Não recarregar saldo de modelos de IA. Não executar long-runs. Durante a
implementação, usar testes focados; rodar a suíte completa no gate de commit.
