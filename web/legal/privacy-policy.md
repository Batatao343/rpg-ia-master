---
status: final
---
# Política de Privacidade - Valoria (RPG IA)

> Última atualização: 17/10/2026. Recomenda-se revisão por assessoria jurídica.

**Controlador:** Guilherme dos Santos Medeiros, pessoa física, CPF 491.209.558-39. **Contato para privacidade e suporte (encarregado):** guilherme.smedeiros1@gmail.com.

## 1. Dados que tratamos
- **Conta:** e-mail e senha (a senha é tratada pelo Supabase Auth, nunca armazenada por nós em texto). Sessão via cookies (acesso/refresh/CSRF) estritamente necessários.
- **Jogo:** personagens, campanhas, histórico de turnos, memória narrativa (texto e vetores), crônica, preferências.
- **Texto digitado** nos turnos: enviado a provedores de IA para gerar a narração (seção 4).
- **Voz:** o áudio gravado é enviado para transcrição; **não o armazenamos em nossos servidores** (não é gravado em banco, log ou armazenamento) e fica sujeito à retenção do provedor de transcrição. A transcrição não é retida pelo recibo da operação (apenas o tipo e a marca `result_retained=false`). O texto transcrito passa a ser um turno normal do jogo.
- **Imagens:** retratos/cenas geradas por IA a partir de descrições do jogo ficam em armazenamento privado do usuário; você não envia fotos pessoais.
- **Pagamentos:** pedidos, saldo de "Estilhas", extrato (entradas append-only), identificadores de compra e eventos de pagamento sanitizados. **Dados de cartão nunca passam por nós**: são tratados pelo Stripe (web) ou pelo Google Play (Android).
- **Técnicos:** logs de erro e métricas de uso/custo sem conteúdo de jogo e sem e-mail/token; limites de taxa por IP e por e-mail normalizado (hash) com expiração em até 24 h.

## 2. Finalidades e bases legais (LGPD, art. 7)
Executar o contrato/serviço (conta, jogo, créditos); legítimo interesse (segurança, antifraude, prevenção de abuso, controle de custos); obrigação legal/regulatória (registros fiscais e financeiros); consentimento quando aplicável (ex.: acesso ao microfone, concedido no navegador/dispositivo).

## 3. Onde ficam os dados
Banco e armazenamento: Supabase, região **sa-east-1 (São Paulo)**. Aplicação: Vercel (região `gru1`, São Paulo, quando disponível). Provedores de IA e pagamento podem processar dados fora do Brasil (transferência internacional com as salvaguardas do art. 33 da LGPD).

## 4. Operadores (processadores em nosso nome)
Estes operadores tratam dados por nossa conta; para a Google Play Data Safety isso não é "compartilhamento com terceiros".

| Operador | Para que | Dados |
|---|---|---|
| Supabase | banco, autenticação, armazenamento | conta, jogo, arquivos |
| Vercel | hospedagem da aplicação | requisições, logs técnicos |
| Provedores de LLM (DeepSeek e Groq) | gerar narração | texto do turno e contexto da campanha |
| Groq (`whisper-large-v3-turbo`) | voz para texto (transcrição principal) | áudio (retenção do provedor) |
| OpenAI (`gpt-4o-mini-transcribe`, transcrição de reserva) | voz para texto | áudio (retenção do provedor) |
| OpenAI (GPT Image 2) | gerar retratos e cenas | descrição textual da aparência/cena e o retrato de referência do herói |
| Jina | embeddings da memória | trechos de texto da campanha |
| Cloudflare Turnstile | antibot em cadastro/login | sinais do navegador e IP |
| Stripe / Google Play | pagamentos | dados de compra (cartão fica com eles) |
| Provedor de e-mail transacional do serviço de autenticação | confirmação e recuperação de conta | e-mail |

Não vendemos dados pessoais. Não usamos o conteúdo das suas campanhas para treinar modelos próprios. Cada provedor de IA aplica seus próprios termos de retenção e treinamento; consulte-os se tiver dúvidas.

## 5. Retenção e exclusão
- Dados de jogo e conta: mantidos enquanto a conta existir. Apagar uma campanha apaga também as imagens geradas para ela (até o próximo ciclo de limpeza automática).
- **Exclusão de conta** (no app, exige senha recente): encerra sessões e apaga usuário, jogos, memória, crônica, jobs, arquivos, arte e o histórico técnico de uso. Permanecem, por obrigação contábil/fiscal, antifraude e defesa em disputas, **por 5 anos**, apenas registros financeiros vinculados a um identificador opaco (UUID), sem e-mail: extrato de créditos, reservas e débitos, pedidos de pagamento, estado de reconciliação e compras Google Play (sem o token de compra, que é anulado após o consumo; apenas número do pedido, produto e estado financeiro). Um registro mínimo de que a exclusão ocorreu (UUID e data) é mantido por 5 anos.
- **Exportação:** o app exporta seus dados (exige senha recente), incluindo o extrato financeiro e links temporários (5 minutos) para baixar suas imagens.
- **Metadados técnicos:** recibos de operações 90 dias; tarefas internas concluídas 30 dias; registro de consumo de IA 13 meses; avaliações financeiras agregadas 180 dias; contador técnico da cota diária 7 dias; limites de taxa até 24 h; logs da plataforma conforme o prazo padrão do provedor de hospedagem (sem conteúdo de jogo, sem e-mail/token).

## 6. Seus direitos (LGPD art. 18)
Confirmação e acesso, correção, anonimização/bloqueio/eliminação, portabilidade, informação sobre compartilhamento, revogação de consentimento e oposição. Exercício pelo app (exportar/excluir) ou por guilherme.smedeiros1@gmail.com; resposta em até 15 dias. Reclamação à ANPD: gov.br/anpd.

## 7. Cookies
Apenas cookies essenciais: sessão de acesso, refresh e token CSRF (`HttpOnly`/`Secure` onde aplicável). Sem cookies de publicidade ou analytics de terceiros. Armazenamento local do navegador guarda preferências e ações pendentes. O site não carrega recursos de terceiros para exibição (as fontes são servidas pelo próprio app), exceto o desafio antibot da Cloudflare no cadastro/login.

## 8. Segurança
Isolamento por usuário no banco (RLS), segredos fora do código, CAPTCHA, limites de taxa, trilha append-only de créditos. Nenhum sistema é totalmente seguro; incidentes relevantes serão comunicados conforme a LGPD.

## 9. Menores
O serviço é destinado a maiores de 18 anos. O cadastro exige a declaração de idade mínima.

## 10. Alterações
Mudanças relevantes serão avisadas no app/e-mail antes de entrar em vigor.
