# Telethon Auth Project

Automatic Telegram authorization with login code retrieval from a chat.

## Features

✅ Automatically fetches the login code from the specified chat (default: `42777`)  
✅ Automatic authorization on the first run  
✅ Sends the code via HTTP webhook for CI/CD workflows  
✅ Supports two-factor authentication (2FA)  
✅ Uses environment variables (works on Railway, Heroku, and similar platforms)

## Installation

### Local

```bash
pip install -r requirements.txt
cp env.example .env
# Fill .env with your values
```

### Railway / Cloud platforms

Provide the environment variables in your service settings (Railway, Heroku, etc.).

## Environment variables

### Required

- `API_ID` — Telegram app ID (get it at [my.telegram.org/apps](https://my.telegram.org/apps))
- `API_HASH` — Telegram app hash
- `PHONE_NUMBER` — Phone number in international format (e.g., `+79991234567`)

### Optional

- `SESSION_NAME` — Session file name (default: `session`)
- `CODE_CHAT_NUMBER` — Chat number to receive the login code (default: `42777`)
- `TWO_FA_PASSWORD` — Two-factor authentication password (if 2FA is enabled)
- `WEBHOOK_URL` — URL to send the code via HTTP POST (for CI/CD)
- `LOGIN_CODE` — One-time login code provided via environment (useful for Railway/CI)

## Usage

### Local run

```bash
python main.py
```

### Railway

1. Connect the repository to Railway.
2. In project settings (Environment → Variables) add:
   - `API_ID`
   - `API_HASH`
   - `PHONE_NUMBER`
   - `SESSION_NAME` (optional)
   - `CODE_CHAT_NUMBER` (optional, default `42777`)
   - `TWO_FA_PASSWORD` (if 2FA is enabled)
   - `WEBHOOK_URL` (optional, to send the code in CI/CD)
   - `LOGIN_CODE` (optional, to pass a one-time code manually)
3. Deploy the service.

## How it works

1. On first run, the bot requests a login code for the specified phone number.
2. The bot listens to messages from `CODE_CHAT_NUMBER` (default `42777`).
3. When a message like `Login code: XXXXX` arrives, the code is extracted automatically.
4. If `WEBHOOK_URL` is set, the code is sent via HTTP POST in JSON:
   ```json
   {
     "code": "40353",
     "message": "Login code: 40353",
     "phone_number": "+79991234567",
     "source": "telegram_chat_42777"
   }
   ```
5. The code is used to complete authorization.
6. The session file is saved so subsequent runs skip authorization.

## Expected message format

The bot expects a message like:
```
Login code: 40353
```
It also falls back to any 5-digit number in the message.

## Files

- `main.py` — bot entrypoint
- `requirements.txt` — Python dependencies
- `env.example` — configuration example
- `*.session` — session file (created after authorization and reused)
