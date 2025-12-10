"""
Telethon example - basic project structure
"""
import asyncio
import os
import re
import aiohttp
from dotenv import load_dotenv
from telethon import TelegramClient, events

# Load environment variables (from .env file if exists)
load_dotenv()

# Get data from environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_NAME = os.getenv('SESSION_NAME', 'session')
CODE_CHAT_NUMBER = os.getenv('CODE_CHAT_NUMBER', '42777')  # Chat number for receiving authorization code
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # URL for sending code via HTTP (for CI/CD)

# Validate required environment variables
if not API_ID or not API_HASH:
    raise ValueError('API_ID and API_HASH must be specified in environment variables')
if not PHONE_NUMBER:
    raise ValueError('PHONE_NUMBER must be specified in environment variables')

# Global variables for authorization
auth_code_event = asyncio.Event()
received_code = None
phone_code_hash = None

# Create client
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


@client.on(events.NewMessage(pattern='(?i)hello|hi'))
async def handler(event):
    """Handler for new messages"""
    await event.reply('Hello! I am a Telethon bot!')


@client.on(events.NewMessage(pattern='(?i)/start'))
async def start_handler(event):
    """Handler for /start command"""
    await event.reply('Bot is running and ready to work!')


@client.on(events.NewMessage(from_users=CODE_CHAT_NUMBER))
async def code_handler(event):
    """Handler for messages from authorization code chat"""
    global received_code, auth_code_event
    
    message_text = event.message.text or event.message.message
    
    # Search for code in format "Login code: 40353"
    code_match = re.search(r'Login code:\s*(\d{5})', message_text, re.IGNORECASE)
    if code_match:
        received_code = code_match.group(1)
        print(f'Code received from chat {CODE_CHAT_NUMBER}: {received_code}')
        
        # Send code via HTTP for CI/CD
        await send_code_via_webhook(received_code, message_text)
        
        auth_code_event.set()
    else:
        # Also try to find any 5-digit number (in case of different format)
        code_match = re.search(r'\b\d{5}\b', message_text)
        if code_match:
            received_code = code_match.group(0)
            print(f'Code received from chat {CODE_CHAT_NUMBER}: {received_code}')
            
            # Send code via HTTP for CI/CD
            await send_code_via_webhook(received_code, message_text)
            
            auth_code_event.set()


async def send_code_via_webhook(code: str, original_message: str):
    """Send code via HTTP webhook for CI/CD process"""
    if not WEBHOOK_URL:
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                'code': code,
                'message': original_message,
                'phone_number': PHONE_NUMBER,
                'source': 'telegram_chat_42777'
            }
            
            async with session.post(
                WEBHOOK_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    print(f'✅ Code successfully sent to webhook: {code}')
                else:
                    response_text = await response.text()
                    print(f'⚠️ Webhook returned status {response.status}: {response_text}')
    except asyncio.TimeoutError:
        print(f'⏱️ Timeout while sending code to webhook')
    except Exception as e:
        print(f'❌ Error sending code to webhook: {e}')


async def wait_for_code(timeout=300):
    """Wait for code from chat with timeout"""
    global received_code
    
    try:
        await asyncio.wait_for(auth_code_event.wait(), timeout=timeout)
        code = received_code
        received_code = None
        auth_code_event.clear()
        return code
    except asyncio.TimeoutError:
        print(f'Timeout waiting for code from chat {CODE_CHAT_NUMBER}')
        return None


async def main():
    """Main function"""
    global phone_code_hash
    
    print('Connecting to Telegram...')
    
    # Check if client is already authorized
    if not await client.is_user_authorized():
        print(f'Authorization required. Waiting for code from chat {CODE_CHAT_NUMBER}...')
        
        # Request code
        try:
            sent_code = await client.send_code_request(PHONE_NUMBER)
            phone_code_hash = sent_code.phone_code_hash
            print(f'Code sent to number {PHONE_NUMBER}')
            print(f'Waiting for code from chat {CODE_CHAT_NUMBER}...')
            
            # Wait for code from chat
            code = await wait_for_code(timeout=300)
            
            if not code:
                print('Failed to receive code. Exiting.')
                return
            
            # Try to sign in with received code
            await client.sign_in(PHONE_NUMBER, code, phone_code_hash=phone_code_hash)
            print('Successfully authorized!')
        except Exception as e:
            print(f'Authorization error: {e}')
            return
    else:
        print('Already authorized!')
    
    # Get information about ourselves
    me = await client.get_me()
    print(f'Logged in as: {me.first_name} {me.last_name or ""} (@{me.username or "no username"})')
    
    # Run client
    await client.run_until_disconnected()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nStopping bot...')
    except Exception as e:
        print(f'Error: {e}')

