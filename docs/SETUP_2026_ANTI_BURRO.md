# Byte Setup 2026 (Anti-Burro)

Guia objetivo para funcionar hoje, sem confundir formulario.

## Resultado esperado

- Byte entra no canal do amigo como viewer.
- Responde a `byte ...`.
- Responde curto (max 8 linhas).

## Regra importante (2026)

- Modo cloud oficial (EventSub) em canal de terceiro exige `channel:bot` do streamer.
- Sem autorizacao do streamer, use modo IRC (`TWITCH_CHAT_MODE=irc`).

## Trilha A (recomendada hoje): sem autorizacao do streamer

### 0) Pre-requisitos

1. Conta Twitch do Byte criada.
2. Projeto GCP com billing ativo.
3. `twitch` CLI instalado.

### 1) Criar app Twitch (campos exatos)

URL: `https://dev.twitch.tv/console/apps/create`

Preencha:

1. `Name`: `Byte Agent`
2. `OAuth Redirect URLs`: `http://localhost:3000/callback`
3. `Category`: `Chat Bot`
4. `Client Type`: `Confidential` (se aparecer)

Anote:

- `TWITCH_CLIENT_ID`
- `TWITCH_CLIENT_SECRET`

### 2) Gerar tokens da conta Byte (sem callback quebrado)

```bash
twitch token --user-token --dcf \
  --client-id "$TWITCH_CLIENT_ID" \
  --secret "$TWITCH_CLIENT_SECRET" \
  --scopes "chat:read chat:edit"
```

Fluxo:

1. O CLI vai mostrar URL de ativacao + codigo.
2. Abra a URL, cole o codigo, confirme.
3. Copie `Access Token` e `Refresh Token` (conta Byte).

### 3) Descobrir logins corretos

- `TWITCH_BOT_LOGIN` = login da conta Byte (minusculo, sem `#`)
- `TWITCH_CHANNEL_LOGIN` = login do canal do amigo (minusculo, sem `#`)

### 4) Configurar `.env`

```bash
GOOGLE_CLOUD_PROJECT=seu-projeto-id
TWITCH_CHAT_MODE=irc
TWITCH_OWNER_ID=seu-id-opcional
TWITCH_CLIENT_ID=seu-client-id
TWITCH_BOT_LOGIN=login_da_conta_byte
TWITCH_CHANNEL_LOGIN=login_do_canal_amigo
TWITCH_USER_TOKEN=token_da_conta_byte
TWITCH_REFRESH_TOKEN=refresh_token_da_conta_byte
TWITCH_CLIENT_SECRET=seu-client-secret
# opcional se quiser ler do Secret Manager:
# TWITCH_CLIENT_SECRET_SECRET_NAME=twitch-client-secret
TWITCH_TOKEN_REFRESH_MARGIN_SECONDS=300
TWITCH_IRC_HOST=irc.chat.twitch.tv
TWITCH_IRC_PORT=6697
TWITCH_IRC_TLS=true
BYTE_TRIGGER=byte
```

### 5) Rodar local

```bash
pip install -r bot/requirements.txt
python bot/main.py
```

### 6) Deploy Cloud Run (modo IRC)

```bash
export PROJECT_ID="seu-projeto-id"
export REGION="us-central1"
export SERVICE_NAME="byte-bot"
export TWITCH_CHAT_MODE="irc"
export TWITCH_CLIENT_ID="seu-client-id"
export TWITCH_BOT_LOGIN="login_da_conta_byte"
export TWITCH_CHANNEL_LOGIN="login_do_canal_amigo"
export TWITCH_USER_TOKEN="token_da_conta_byte"
export TWITCH_REFRESH_TOKEN="refresh_token_da_conta_byte"
export TWITCH_OWNER_ID="seu-id-opcional"

./deploy.sh
```

### 7) Teste funcional no chat

1. `byte ajuda`
2. `byte status`
3. `byte ficha tecnica de Duna Parte 2`
4. `byte qual a ficha tecnica do filme que estamos vendo?`

Esperado:

- resposta curta;
- se nao souber o filme, Byte pede titulo.

## Trilha B (oficial cloud): com autorizacao do streamer

Use quando quiser aderir ao fluxo EventSub completo.

Scopes:

- Bot: `user:read:chat user:write:chat user:bot`
- Broadcaster: `channel:bot`

Modo:

```bash
TWITCH_CHAT_MODE=eventsub
```

E variaveis:

- `TWITCH_CLIENT_ID`
- `TWITCH_BOT_ID`
- `TWITCH_CHANNEL_ID`
- segredo `twitch-client-secret` no Secret Manager

## Checklist final anti-erro

1. No modo sem streamer, `TWITCH_CHAT_MODE=irc`.
2. `TWITCH_CHANNEL_LOGIN` e o login do amigo, nao o seu.
3. `TWITCH_USER_TOKEN` e `TWITCH_REFRESH_TOKEN` sao da conta Byte.
4. Se usar refresh automatico, configure `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET` (ou Secret Manager).
5. Mensagem no chat precisa comecar com `byte`.
