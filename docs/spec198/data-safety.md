# SPEC-198 - Rascunho de Data Safety e permissoes (Google Play)

> RASCUNHO baseado no codigo/docs reais (SPEC-186/187/188/190/194/195, `llm_setup.ROUTES`, `docs/spec197/legal/privacy-policy.md`).
> O formulario final so pode ser preenchido pelo titular, depois de fechar os `<...>` da politica de privacidade. Deve ser
> identico ao que a politica publicada diz. Itens marcados CONFIRMAR dependem de decisao externa.

## 1. Fluxos de dados reais

| Dado | Origem | Para onde vai | Retencao | Coletado / Compartilhado (Play) |
|---|---|---|---|---|
| E-mail da conta | cadastro | Supabase Auth (sa-east-1); provedor SMTP de e-mail transacional (CONFIRMAR) | enquanto a conta existir; apagado na exclusao | Coletado; compartilhado com operadores (processador) |
| Senha | cadastro | Supabase Auth (hash; nunca em texto por nos) | idem | Coletado (credencial) |
| Texto digitado nos turnos + contexto da campanha | usuario | Supabase (banco) + provedores de LLM: DeepSeek primario; Groq, MiniMax, Qwen, Anthropic, Gemini como fallback (`ROUTES`) | banco: ate exclusao; provedores: conforme termos deles (CONFIRMAR retencao/treino) | Coletado; compartilhado com processadores |
| Conteudo de jogo (personagens, cronica, memoria narrativa, vetores) | geracao | Supabase; Jina (embeddings de trechos de texto) | ate exclusao | Coletado; processador Jina |
| Audio de voz (STT) | microfone, so ao tocar em VOZ | provedor de transcricao (Groq/OpenAI, CONFIRMAR) | **apagado imediatamente apos o processamento**; nao gravado em banco/log/storage; recibo guarda so `result_retained=false` | Coletado, **efemero** (marcar "processado de forma efemera") |
| Imagens geradas (retratos/cenas) | descricao textual | provedor de imagem (CONFIRMAR) -> Supabase Storage privado | ate exclusao | Gerado; nao ha foto/arquivo do usuario |
| Historico de compras (token, order id, SKU, valor creditado) | Google Play Billing | backend (Supabase), verificacao server-side na Android Publisher API | extrato append-only, pseudonimizado por UUID apos exclusao; prazo fiscal `<definir>` | Coletado |
| Compras web (Stripe) | **somente web; o app Android nao expoe Stripe** (403 `stripe_unavailable_on_android`) | Stripe | fora do escopo do app | n/a no formulario Android |
| Logs/metricas tecnicas | servidor | Vercel / Supabase; sem conteudo de jogo nem e-mail/token | conforme plataforma `<dias>` | Coletado (diagnostico), nao vinculado a perfil de ads |
| IP / antibot | login/cadastro | Cloudflare Turnstile; rate limit por IP e e-mail em hash, expira em <=24 h | <=24 h | Coletado (seguranca) |

Nao ha SDK de analytics, anuncios, localizacao, contatos, fotos ou ID de publicidade no APK (a verificar com o relatorio de
dependencias do AAB: unicas libs sao Capacitor, AndroidX e Play Billing 9.1.0).

## 2. Respostas propostas no formulario Data Safety

- **Coleta de dados?** Sim. **Compartilha com terceiros?** Declarar compartilhamento com *service providers* (Supabase, Vercel,
  provedores de LLM/STT/imagem/embeddings, Google Play). Pelas regras do Google, transferencia a processador que atua em nome
  do desenvolvedor NAO conta como "compartilhamento" - confirmar com o jurista; na duvida, declarar.
- **Criptografia em transito:** Sim (HTTPS obrigatorio; cleartext proibido no release - gate `checkReleaseCleartext`, `usesCleartextTraffic=false`).
- **Usuario pode pedir exclusao:** Sim - no app (SPEC-190, exige senha recente) e URL web `<URL de exclusao>` (obrigatoria pela politica de contas).
- **Compromisso com a Politica de Familias:** nao aplicavel (publico geral, nao direcionado a criancas) - definir idade minima (`<18/13?>`).

Categorias Play -> itens:

| Categoria Play | Tipo | Coletado | Compartilhado | Finalidade | Opcional |
|---|---|---|---|---|---|
| Informacoes pessoais | Endereco de e-mail | Sim | Sim (operadores) | Funcionalidade do app, gerenciamento de conta | Nao |
| Informacoes pessoais | IDs de usuario (UUID da conta) | Sim | Nao | Funcionalidade, conta | Nao |
| Informacoes financeiras | Historico de compras | Sim | Nao | Funcionalidade (creditos), antifraude | Nao |
| Mensagens | Outras mensagens no app (texto dos turnos) | Sim | Sim (LLM) | Funcionalidade | Nao |
| Audio | Gravacoes de voz | Sim, **efemero** | Sim (STT) | Funcionalidade | Sim (VOZ opcional) |
| Fotos e videos | (nenhum) | Nao | Nao | - | - |
| Atividade no app | Interacoes no app / conteudo de jogo | Sim | Sim (embeddings/LLM) | Funcionalidade | Nao |
| Info e desempenho do app | Logs de falhas/diagnostico | Sim | Nao | Analise tecnica/seguranca | Nao |
| Localizacao, contatos, saude, web browsing | Nao | - | - | - | - |

## 3. Inventario de permissoes (AndroidManifest + merge)

| Permissao | Origem | Justificativa | Declaracao no Console |
|---|---|---|---|
| `INTERNET` | manifest | todo o jogo roda no backend hospedado (WebView remoto) | normal, sem declaracao |
| `RECORD_AUDIO` | manifest | entrada por voz opcional; pedida em runtime so ao tocar VOZ; audio apagado apos STT | perigosa: justificar na Data Safety (audio) e na politica de privacidade; sem formulario de permissao sensivel |
| `MODIFY_AUDIO_SETTINGS` | manifest (exigida pelo `BridgeWebChromeClient` do Capacitor junto com RECORD_AUDIO) | sem ela o pedido de microfone e negado | normal |
| `com.android.vending.BILLING` | merge da lib Play Billing 9.1.0 | compras de consumiveis (Estilhas) | normal; exige produtos in-app configurados |

Validar no AAB final: `bundletool dump manifest` (ou `aapt2`) nao deve listar nenhuma permissao alem das quatro acima
(sem `ACCESS_NETWORK_STATE` etc. extras de libs).

## 4. Pontos abertos

- Lista final de provedores de LLM/STT/imagem e retencao/treino deles (item 13/14 de external-inputs).
- URL web de exclusao de conta; texto final da politica identico ao formulario.
- Politica de IA generativa: mecanismo de denuncia/feedback no app (lacuna).
- Compras sem `obfuscatedAccountId` (promo/resgate) sao RECUSADAS (SPEC-194 item 8): documentar no suporte; decisao do usuario.
- Declaracao "app de jogo com IA": revisar texto de apresentacao contra a politica de conteudo gerado por IA.
