# Telethon Auth Project

Automatic Telegram authorization with code retrieval from chat.

## Features

✅ **Automatic code retrieval** from specified chat (default "42777")  
✅ **Automatic authorization** on first run  
✅ **Code sending via HTTP webhook** for CI/CD processes  
✅ **Environment variables support** (Railway, Heroku and other platforms)

## Installation

### Local installation

```bash
pip install -r requirements.txt
cp env.example .env
# Fill .env with your data
```

### Railway / Cloud platforms

Simply specify environment variables in your service settings (Railway, Heroku, etc.).

## Environment Variables

### Required

- `API_ID` — Telegram application ID (get it at [my.telegram.org/apps](https://my.telegram.org/apps))
- `API_HASH` — Telegram application Hash
- `PHONE_NUMBER` — Phone number in international format (e.g.: `+99991234567`)

### Optional

- `SESSION_NAME` — Session file name (default: `session`)
- `CODE_CHAT_NUMBER` — Chat number for receiving authorization code (default: `42777`)
- `WEBHOOK_URL` — URL for sending code via HTTP POST (for CI/CD processes)

## Usage

### Local run

```bash
python main.py
```

### Railway

1. Connect repository to Railway
2. In project settings (Environment → Variables) add:
   - `API_ID`
   - `API_HASH`
   - `PHONE_NUMBER`
   - `SESSION_NAME` (optional)
   - `CODE_CHAT_NUMBER` (optional, default `42777`)
   - `WEBHOOK_URL` (optional, for sending code in CI/CD)
3. Deploy

## How it works

1. On first run, bot requests authorization code to specified phone number
2. Bot automatically monitors messages from chat with number `CODE_CHAT_NUMBER` (default "42777")
3. When message arrives in format `Login code: XXXXX`, code is extracted automatically
4. If `WEBHOOK_URL` is specified, code is sent via HTTP POST request in JSON format:
   ```json
   {
     "code": "40353",
     "message": "Login code: 40353",
     "phone_number": "+99991234567",
     "source": "telegram_chat_42777"
   }
   ```
5. Code is used to complete authorization
6. Session file is saved, and on subsequent runs authorization is not required

## Code message format

Bot expects message in format:
```
Login code: 40353
```

Also supports searching for any 5-digit number in the message.

## Files

- `main.py` — main bot code
- `requirements.txt` — Python dependencies
- `env.example` — configuration example
- `*.session` — session file (created after authorization, saved between runs)
