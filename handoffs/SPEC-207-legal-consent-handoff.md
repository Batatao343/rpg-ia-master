# Handoff SPEC-207 → SPEC-197: consentimento do export de sessão para auditoria

> Origem: SPEC-207 R16. Este arquivo **não** altera a SPEC-197 nem `docs/spec197/legal/*`.
> Cabe ao dono da SPEC-197 (e à revisão jurídica dela) incorporar, adaptar ou recusar o texto.

## O que a funcionalidade faz (fatos para o texto legal)

- O próprio titular, autenticado e após confirmar a senha (prova recente, ~5 min), pode baixar
  um `.zip` de UMA campanha sua (`POST /game/{id}/audit-export`). Só nos perfis com conta.
- Finalidade declarada: o titular analisa a sessão com o próprio assistente/agente de código,
  com créditos próprios. O jogo **não** envia o pacote a terceiros nem chama IA para auditar.
- Conteúdo: texto digitado pelo jogador (com e-mail/telefone/URLs com token substituídos por
  `[REDACTED:*]`), narração exibida, mudanças de estado do jogo por turno, referências
  (ids/hashes) do contexto usado pela IA, erros técnicos por código fechado, tempos e custo
  técnico por turno. Inclui **segredos do mundo do jogo** (spoilers) marcados
  “privado — referência de auditoria”.
- Não contém: e-mail, IP, user-agent, ids de conta, cookies/tokens, chaves, URLs assinadas,
  áudio ou transcrição de voz, dados de pagamento/carteira, prompts ou respostas brutas da IA.
- Retenção no servidor: **nenhuma** (gerado em memória e entregue no download). Se um dia houver
  armazenamento temporário, o limite é 24 h e cai na exclusão de conta (`users/<owner>/`).
- Após o download, o arquivo fica sob controle do titular; se ele o entregar a um serviço de
  terceiros (ex.: um agente de IA), passa a valer a política desse serviço.

## Texto sugerido (pt-BR) — Política de Privacidade, seção “Seus dados”

> **Exportação de sessão para auditoria.** Você pode baixar, a qualquer momento e mediante
> confirmação de senha, um pacote com o registro técnico de uma das suas campanhas
> (o que você escreveu, o que foi narrado, as mudanças no jogo, erros e tempos de resposta).
> Removemos do pacote dados da sua conta — como e-mail, identificadores, endereço IP e dados de
> pagamento — e trechos do seu texto que pareçam e-mail, telefone ou link com credenciais.
> O pacote é gerado apenas quando você pede e não fica guardado em nossos servidores. Ele pode
> conter revelações do enredo do jogo (spoilers). Se você compartilhar o arquivo com outra
> pessoa ou com um serviço de terceiros, o tratamento passa a seguir as regras de quem o recebe.

## Texto sugerido — microcopy de consentimento antes do download (já na UI)

> “Gera um arquivo .zip com o transcrito, as mudanças de estado, erros e tempos de cada turno,
> para você analisar com seu próprio assistente de código. Dados da conta (e-mail, ids,
> pagamentos) não entram. Atenção a spoilers: segredos do mundo vêm marcados como
> ‘privado — referência de auditoria’.”

## Pontos para a revisão jurídica decidir

1. Base legal (LGPD art. 18, II/V — acesso/portabilidade a pedido do titular) e se basta o
   aviso acima ou se é preciso aceite explícito (checkbox) antes do primeiro download.
2. Se o scrubber automático é suficiente como medida para PII que o próprio jogador digitou.
3. Se a exportação deve ser listada nos Termos como recurso “beta”.
