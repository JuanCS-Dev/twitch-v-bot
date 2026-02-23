# HF Spaces Secrets Configuration Report

To resolve the 403/404 errors and ensure the bot connects correctly, update your Hugging Face Space secrets with the following values.

## 🔑 Required Secrets

| Secret Name | Value | Description |
| :--- | :--- | :--- |
| `NEBIUS_API_KEY` | `v1.CmMK...` (Mantive o do seu .env) | Chave para inferência de IA. |
| `TWITCH_BOT_LOGIN` | `byte_agent` | Login da conta do Bot. |
| `TWITCH_USER_TOKEN` | `0adcmvbuy7cnbozleagl0n84aldzlz` | Novo User Access Token (Refrescado agora). |
| `TWITCH_REFRESH_TOKEN` | `gzm7qa74us9b45xupqrkvdqw1j3m55pa013cr53rvjybl0kerr` | Refresh Token para renovação automática. |
| `TWITCH_CLIENT_ID` | `1pntcif6b76jjho6206aqguc4k2b8g` | ID do seu app na Twitch. |
| `TWITCH_CLIENT_SECRET` | `jq3a9rojx603eibhu09bj3n9ciydj7` | Secret do seu app na Twitch. |
| `TWITCH_OWNER_ID` | `1372298411` | Seu ID de usuário (Broadcaster). |
| `TWITCH_BOT_ID` | `1447301105` | ID de usuário do bot. |
| `TWITCH_CHANNEL_ID` | `1372298411` | ID do canal onde o bot atuará. |
| `TWITCH_CHANNEL_LOGIN` | `juancs_dev` | Login do canal sem #. |
| `TWITCH_CHAT_MODE` | `irc` | Modo de conexão. |
| `BYTE_DASHBOARD_ADMIN_TOKEN` | (Use o seu atual ou `test-token`) | Senha de acesso ao dashboard. |

---

## 🎬 Ativando Clip Pipeline (Opcional)

Os tokens acima permitem o **Chat**, mas o scope `clips:edit` não está presente. Se você quiser que o Byte crie clips automaticamente, faça o seguinte no seu terminal local:

1. Execute o comando:
   ```bash
   twitch token -u -s "chat:read chat:edit clips:edit"
   ```
2. Um link será aberto no seu navegador. Autorize.
3. Copie o novo `Access Token` e `Refresh Token` que aparecerão no terminal.
4. Atualize as secrets `TWITCH_USER_TOKEN` e `TWITCH_REFRESH_TOKEN` no Hugging Face.

---

## 🚀 Como Aplicar
1. Vá em **Settings** do seu Space no Hugging Face.
2. Na seção **Variables and Secrets**, atualize cada um dos valores acima.
3. O Space deve reiniciar automaticamente com as novas configurações.
