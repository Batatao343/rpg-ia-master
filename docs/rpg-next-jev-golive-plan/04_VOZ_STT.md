# Voz / Speech-to-Text v1

Objetivo: reduzir a fricção de digitar ações sem transformar o jogo em voice-chat completo.

## UX aprovada

- botão de microfone no composer;
- gravação máxima inicial: 60 s;
- ao parar: transcrever;
- transcript volta para o campo de texto;
- usuário pode editar;
- **nunca enviar automaticamente** ao jogo;
- arquivo de áudio não é persistido após a transcrição;
- custo entra no metering/account history.

## Routing recomendado

Primary: Groq `whisper-large-v3-turbo`.

Fallback inicial: OpenAI `gpt-4o-mini-transcribe`.

Deepgram Nova-3 pt-BR fica como candidato futuro/benchmark, não dependência v1, para evitar terceira key/SDK sem evidência de necessidade.

## Por que

O Groq já existe na stack e o modelo é multilíngue, muito rápido e barato. Fallback OpenAI já pode reutilizar a key necessária para imagem, se configurada.

## Contrato

Normalizar:

```yaml
transcription_id: uuid
owner_id: uuid
duration_ms: int
provider: groq|openai
model: string
text: string
usage_quantity: number
cost_usd: decimal
cost_basis: provider_reported|rate_card
created_at: timestamptz
```

Nenhum áudio bruto no banco/log/telemetria. Limitar MIME, bytes, duração e rate. Prompt/contexto de nomes de Valoria pode ser usado de forma curta e pública; não mandar segredos da campanha só para melhorar proper nouns.
