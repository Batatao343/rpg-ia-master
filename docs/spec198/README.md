# SPEC-198 - Publicacao Google Play: preparacao autonoma e runbook

Status: `in-progress`. Preparacao feita sem Play Console (15/10/2026). **Nada foi enviado ao Google.** Tudo irreversivel espera o usuario.
Rascunhos: [store-listing.md](store-listing.md) - [data-safety.md](data-safety.md) - capturas de trabalho em `screenshots/`.

## 1. O que ja esta pronto

| Item | Onde | Evidencia |
|---|---|---|
| Assinatura de release por env/`keystore.properties` (gitignored) | `web/android/app/build.gradle` | AAB assinado verificado com `jarsigner -verify` ("signature was verified", CN=Valoria Upload) |
| versionCode/versionName em fonte unica | `web/android/version.properties` | `-Bump` no script incrementa VERSION_CODE |
| Build do AAB | `scripts/android/release_build.ps1 -ServerUrl https://...` | `BUILD SUCCESSFUL`; `checkReleaseCleartext` executou; `capacitor.config.json` do AAB = https, `cleartext:false`; SHA256 do AAB de prova `318531A5...1714` (id dev placeholder, staging) |
| Chave de UPLOAD local (so verificacao) | `%USERPROFILE%\.rpg-signing\` (fora de OneDrive/repo; ACL so do usuario) | criada por `scripts/android/new_upload_keystore.ps1` (recusa sobrescrever e pasta OneDrive) |
| Scan de segredos no AAB | 605 arquivos extraidos | 0 ocorrencias da senha do keystore, de chaves `sk-`/`AIza`/JWT/`service_role`/`sk_live`/private key |
| Troca de applicationId | `scripts/android/rename_package.py` | dry-run por padrao; testado em copia temporaria (6 arquivos editados, 2 movidos, sem sobras; id invalido recusado) |
| Capturas de trabalho | `scripts/android/store_screenshots.mjs` | 3 capturas (inuteis para a loja, ver store-listing); usuario sintetico removido |

A chave de upload **gerada aqui e descartavel** (so provou o pipeline). Para o upload real, gere outra com o mesmo script depois de decidir o id.

### Custodia das chaves (decisao do usuario)
- **Play App Signing** (obrigatorio para AAB novo): o Google guarda a chave REAL de assinatura do app; ela nunca passa pelo repo.
- A chave de **upload** so autentica seus envios; se perdida, e possivel pedir reset ao suporte do Play, mas custa dias. Mesmo assim:
  copie `upload.jks` + `signing.properties` para 2 midias offline/cofre de senhas (nunca OneDrive, e-mail, git ou chat).
  Defina quem guarda (item 9 de external-inputs). Nao rotacione a `RPG_PLAY_ACCOUNT_KEY` sem plano (muda os account ids ofuscados).
- O script nunca imprime senha; logs do build nao contem segredos (verificado).

## 2. Antes do primeiro upload (decisoes do usuario) - IRREVERSIVEL

O **package id e imutavel** depois do primeiro upload/criacao do app. Defina:
1. Package id definitivo (proposta de external-inputs: `dev.rpgia.valoria` - exige identidade/dominio coerente; ou `com.<seu-dominio>.valoria`).
2. Nome publico do app e tipo de conta de desenvolvedor (pessoal ou organizacao - ver secao 5).
3. URLs publicadas de privacidade/termos/suporte/exclusao e e-mail de suporte.

Aplicar o id (dry-run primeiro):
```
uv run python scripts/android/rename_package.py --new <id> --app-name "<Nome>"           # confere o plano
uv run python scripts/android/rename_package.py --new <id> --app-name "<Nome>" --apply
cd web && CAP_SERVER_URL=https://<prod> npx cap sync android     # regenera capacitor.config.json
```
Versao: editar `web/android/version.properties` (versionCode so cresce; ou `-Bump`).

## 3. Passo a passo no Play Console (quando a conta existir)

1. **Criar o app**: Todos os apps > Criar app; nome, idioma pt-BR, Jogo, gratuito; aceitar declaracoes.
2. **Gerar upload key e AAB**:
   `powershell -File scripts/android/new_upload_keystore.ps1` (com DN real) e
   `powershell -File scripts/android/release_build.ps1 -ServerUrl https://<prod> -Bump -OutDir <dir>`; guardar o SHA256.
   Na primeira vez manter **Play App Signing** habilitado (padrao).
3. **Upload no Teste interno** (Testar e lancar > Teste interno > Criar versao > subir o AAB). IRREVERSIVEL: fixa o package id.
   Completar o painel obrigatorio: acesso ao app, anuncios (nao), classificacao de conteudo (IARC, ver store-listing), publico-alvo,
   Data Safety (data-safety.md), politica de privacidade, categoria/contato, declaracoes (IA generativa, exclusao de conta).
4. **Produtos in-app (consumiveis)**: Monetizar > Produtos > Produtos unicos. Criar um por SKU, com **ID exatamente igual** ao
   `store_product_id` do seed. Listar o plano:
   `uv run python scripts/seed_google_play_skus.py` (dry-run; ID = `sku_id` minusculo, `[^a-z0-9_.]` vira `_`, ex.: `estilhas_pack_small`).
   O preco do Console DEVE ser igualado ao SKU web equivalente (o app mostra o preco da Store; o backend credita `shard_milli`).
   Tipo: consumivel. Confirmar o **tier de taxa do Google** e conferir `channel_fees.google_play` (R9) ANTES de rodar
   `uv run python scripts/seed_google_play_skus.py --apply` no ambiente alvo (idempotente, ON CONFLICT DO NOTHING).
5. **License testers**: Configuracoes > Teste de licenca: adicionar os Gmail dos testers (compras de teste nao cobram). Adicionar os mesmos
   e-mails na lista do teste interno e aceitar o link de opt-in no dispositivo.
6. **Service account da API**: Google Cloud (projeto vinculado) > criar service account > chave JSON (guardar fora do repo). No Play Console >
   Usuarios e permissoes > convidar o e-mail da service account com permissoes do app: **Ver informacoes do app** e
   **Gerenciar pedidos e assinaturas** (consume/void). Ativar *Google Play Android Developer API* no projeto. A propagacao pode levar horas.
7. **Variaveis de ambiente (backend/Vercel, nunca no git)**:
   - `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` (caminho ou JSON inline)
   - `GOOGLE_PLAY_PACKAGE_NAME` = package id definitivo
   - `RPG_PLAY_ACCOUNT_KEY` (>=32 chars aleatorios, gerar uma vez)
   - `RPG_GOOGLE_PLAY_FAKE` deve estar AUSENTE (proibido em prod; o checklist de release recusa).
   Empurrar com `scripts/staging/vercel_env.py` (staging) e republicar o web (o WebView remoto so ve o cliente novo apos o deploy).
8. **Instalar do teste interno** em dispositivo real com Play Store e conta license tester.

## 4. Smoke real de compra (aceite R4/R7)

Em dispositivo real, build do track interno, conta license tester logada na Play Store:
1. Login no app; saldo inicial anotado.
2. Comprar o consumivel: `POST /account/purchases/google/verify` responde 200 `fulfilled`, saldo sobe `shard_milli`, `consumed=true`.
3. **Recompra** do mesmo produto (so e possivel se o consume funcionou).
4. Matar o app com compra pendente / `fulfilled_unconsumed` e reabrir: `queryPurchasesAsync` reenvia o token e recupera
   (sem duplicar credito; `token_sha256`/`order_id` unicos).
5. **Restart**: encerrar o processo, reabrir, saldo coerente; carteira web e Android iguais (mesma conta).
6. Compra "pendente" do Play: nao credita ate `PURCHASED`.
7. Confirmar que o app **nao mostra link/CTA Stripe** (`X-RPG-Client: android` recebe 403 em `/account/checkout*`).
8. **Reembolso/revogacao**: no Console, reembolsar o pedido de teste (Pedidos > Reembolsar). Esperar o cron `POST /internal/cron/reconciliation`
   (SPEC-195) e confirmar `voided_at`/`void_reason` e o ajuste na carteira. Se a conta nao gerar void para compras de teste,
   registrar como limitacao no relatorio.
Evidencia em `docs/spec198/evidence/` (sem tokens/e-mails: usar hash). Sol revisa.

## 5. Closed testing (politica verificada em 15/10/2026)

Fonte: Google Play Console Help, "Closed testing requirements for new personal developer accounts"
(support.google.com/googleplay/android-developer/answer/14151465). A pagina nao traz data de revisao; reconferir antes de agir.
- Vale para **contas PESSOAIS criadas depois de 13/11/2023**.
- Exige **pelo menos 12 testers com opt-in continuo nos 14 dias anteriores** em um closed test para **solicitar acesso a producao**
  (Painel > "Apply for production": secoes sobre o teste, o app e prontidao). Quem sai antes de 14 dias nao conta; sair e voltar reinicia a
  contagem. Analise tipica de ate 7 dias, pode demorar; pode ser exigido continuar o teste se o engajamento for insuficiente.
- **Contas de organizacao** nao tem esse requisito (alternativa se houver CNPJ).
- O teste interno nao conta: criar uma trilha **Closed** com 12+ pessoas (lista de e-mails ou Google Group) e manter por 14 dias.
  Planejar a lista do beta (external-inputs item 12) para cobrir isso.

## 6. Producao

So depois de: smoke real aprovado (secao 4), closed testing cumprido (se aplicavel), Data Safety/Privacidade/Suporte publicados, review Sol
da evidencia e **comando explicito do usuario** ("publique em producao"). Rollout em etapas (ex. 10%) monitorado pelo runbook
`docs/spec197/runbooks/incident.md`. Este agente nunca publica por conta propria.

## 7. Achados desta preparacao
- UI mobile 390 px: na home, "CONTA - 0 ESTILHAS" e "ENCERRAR SESSAO" se sobrepoem (bug visual de cabecalho).
- Staging usa narrador MockLLM (texto "Voce descreva o cenario..."): capturas finais precisam de LLM real.
- Lacuna de politica de IA generativa: nao ha botao de denuncia/feedback no app.
- Politica para compras sem `obfuscatedAccountId` (promo/resgate) ainda a decidir (SPEC-194 item 8).
