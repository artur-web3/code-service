"""
Telethon example - basic project structure
"""
import asyncio
import os
import re
import aiohttp
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from flask import Flask, request, jsonify
from threading import Thread

# Load environment variables (from .env file if present)
load_dotenv()

# Fetch and validate environment variables
API_ID_RAW = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_NAME = os.getenv('SESSION_NAME', 'session')
CODE_CHAT_NUMBER = os.getenv('CODE_CHAT_NUMBER', '42777')  # Chat number to receive the login code
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # URL to send the code via HTTP (for CI/CD)
LOGIN_CODE = os.getenv('LOGIN_CODE')  # Optional: pass the login code via environment variable

if not API_ID_RAW or not API_HASH or not PHONE_NUMBER:
    raise ValueError("API_ID, API_HASH, and PHONE_NUMBER must be set")

try:
    API_ID = int(API_ID_RAW)
except ValueError as exc:
    raise ValueError(f"API_ID must be an integer, got: {API_ID_RAW}") from exc

# Validate required environment variables
if not API_ID or not API_HASH:
    raise ValueError('API_ID and API_HASH must be provided in environment variables')
if not PHONE_NUMBER:
    raise ValueError('PHONE_NUMBER must be provided in environment variables')

# Global variables for authorization
auth_code_event = asyncio.Event()
received_code = None
phone_code_hash = None

# Global variables for API
latest_code = None
code_request_pending = False

# Create client
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# API Server for code requests
api_app = Flask(__name__)

@api_app.route('/request-code', methods=['POST'])
def request_code():
    """API endpoint для запроса нового кода авторизации"""
    global code_request_pending
    code_request_pending = True
    print('📤 Code request received from API')
    return jsonify({
        'status': 'ok',
        'message': 'Code request initiated. Waiting for code from Telegram...'
    }), 200

@api_app.route('/get-code', methods=['GET'])
def get_code():
    """API для получения последнего полученного кода"""
    global latest_code
    if latest_code:
        return jsonify({
            'code': latest_code,
            'status': 'ok'
        }), 200
    return jsonify({
        'error': 'Code not ready yet. Make sure to request code first.',
        'status': 'pending'
    }), 404

def run_api_server():
    """Запуск Flask API сервера"""
    api_app.run(host='0.0.0.0', port=5001, debug=False)

# Запускаем API сервер в отдельном потоке
api_thread = Thread(target=run_api_server, daemon=True)
api_thread.start()
print('✅ API server started on port 5001')


@client.on(events.NewMessage(pattern='(?i)hello|hi'))
async def handler(event):
    """New message handler"""
    await event.reply('Hi! I am a Telethon bot!')


@client.on(events.NewMessage(pattern='(?i)/start'))
async def start_handler(event):
    """Handler for /start command"""
    await event.reply('Bot is running and ready!')


@client.on(events.NewMessage)
async def code_handler(event):
    """Handler for messages that contain login codes"""
    global received_code, auth_code_event
    
    # Get sender info for debugging
    try:
        sender = await event.get_sender()
        sender_username = getattr(sender, 'username', None)
        sender_phone = getattr(sender, 'phone', None)
        sender_id = getattr(sender, 'id', None)
    except:
        sender_username = None
        sender_phone = None
        sender_id = None
    
    message_text = event.message.text or event.message.message
    
    # Check if message is from the code sender (42777)
    is_from_code_sender = False
    if sender:
        # Check by phone number, username, or ID
        sender_phone_str = str(sender_phone) if sender_phone else ''
        sender_username_str = str(sender_username) if sender_username else ''
        sender_id_str = str(sender_id) if sender_id else ''
        
        is_from_code_sender = (
            CODE_CHAT_NUMBER in sender_phone_str or
            CODE_CHAT_NUMBER in sender_username_str or
            CODE_CHAT_NUMBER in sender_id_str
        )
    
    # Also check messages that contain "Login code:" pattern (from any sender, but usually from 42777)
    has_code_pattern = message_text and ('login code' in message_text.lower() or re.search(r'\b\d{5}\b', message_text))
    
    # Debug: log messages from 42777 or containing "code"
    if is_from_code_sender or has_code_pattern:
        print(f'DEBUG: Message from ID: {sender_id}, Username: {sender_username}, Phone: {sender_phone}')
        print(f'DEBUG: Message text: {message_text}')
        print(f'DEBUG: Looking for CODE_CHAT_NUMBER: {CODE_CHAT_NUMBER}')
        print(f'DEBUG: Is from code sender: {is_from_code_sender}')
    
    if is_from_code_sender or has_code_pattern:
        # Look for code in the format "Login code: 40353"
        code_match = re.search(r'Login code:\s*(\d{5})', message_text, re.IGNORECASE)
        if code_match:
            received_code = code_match.group(1)
            print(f'✅ Received code from {CODE_CHAT_NUMBER}: {received_code}')
            
            # Save code globally for API
            global latest_code
            latest_code = received_code
            
            # Save to file for reliability
            try:
                with open('/tmp/telegram_code_latest.txt', 'w') as f:
                    f.write(received_code)
            except Exception as e:
                print(f'⚠️ Could not save code to file: {e}')
            
            # Send code via HTTP for CI/CD
            await send_code_via_webhook(received_code, message_text)
            
            auth_code_event.set()
        else:
            # Fallback: find any 5-digit number
            code_match = re.search(r'\b\d{5}\b', message_text)
            if code_match:
                received_code = code_match.group(0)
                print(f'✅ Received code (5-digit): {received_code}')
                
                # Save code globally for API
                global latest_code
                latest_code = received_code
                
                # Save to file for reliability
                try:
                    with open('/tmp/telegram_code_latest.txt', 'w') as f:
                        f.write(received_code)
                except Exception as e:
                    print(f'⚠️ Could not save code to file: {e}')
                
                # Send code via HTTP for CI/CD
                await send_code_via_webhook(received_code, message_text)
                
                auth_code_event.set()


async def send_code_via_webhook(code: str, original_message: str):
    """Send the code via HTTP webhook for CI/CD"""
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
                    print(f'✅ Code sent to webhook: {code}')
                else:
                    response_text = await response.text()
                    print(f'⚠️ Webhook returned status {response.status}: {response_text}')
    except asyncio.TimeoutError:
        print('⏱️ Timeout while sending code to webhook')
    except Exception as e:
        print(f'❌ Error sending code to webhook: {e}')


async def wait_for_code(timeout=300):
    """Wait for a login code from the chat with timeout"""
    global received_code
    
    try:
        await asyncio.wait_for(auth_code_event.wait(), timeout=timeout)
        code = received_code
        received_code = None
        auth_code_event.clear()
        return code
    except asyncio.TimeoutError:
        print(f'Timeout while waiting for code from chat {CODE_CHAT_NUMBER}')
        return None


async def request_new_code():
    """Запрашивает новый код авторизации у Telegram"""
    global phone_code_hash
    
    try:
        print(f'📤 Requesting new code for {PHONE_NUMBER}...')
        sent_code = await client.send_code_request(PHONE_NUMBER)
        phone_code_hash = sent_code.phone_code_hash
        print(f'✅ Code request sent. Waiting for code from chat {CODE_CHAT_NUMBER}...')
        return True
    except Exception as e:
        print(f'❌ Error requesting code: {e}')
        return False


async def code_request_handler():
    """Фоновая задача для обработки запросов кода через API"""
    global code_request_pending
    
    while True:
        if code_request_pending:
            code_request_pending = False
            await request_new_code()
        await asyncio.sleep(1)  # Проверяем каждую секунду


async def main():
    """Main entrypoint"""
    global phone_code_hash
    
    print('Connecting to Telegram...')
    
    try:
        # Disconnect if already connected
        if client.is_connected():
            print('Disconnecting existing connection...')
            try:
                await client.disconnect()
            except:
                pass
        
        # Connect to Telegram
        print('Establishing connection...')
        try:
            # Try to connect with a timeout
            await asyncio.wait_for(client.connect(), timeout=30.0)
            if not client.is_connected():
                print('Connection failed - client is not connected')
                return
            print('Connected successfully!')
        except asyncio.TimeoutError:
            print('Connection timeout after 30 seconds!')
            print('Possible issues:')
            print('  - Check your internet connection')
            print('  - Telegram might be blocked in your region')
            print('  - Try using a VPN if needed')
            return
        except Exception as e:
            print(f'Connection error: {e}')
            import traceback
            traceback.print_exc()
            return
        
        # Check if client is already authorized
        print('Checking authorization status...')
        is_authorized = await client.is_user_authorized()
        
        if not is_authorized:
            print(f'Authorization required. Waiting for code from chat {CODE_CHAT_NUMBER}...')
            
            # Request code
            try:
                print(f'Requesting login code for {PHONE_NUMBER}...')
                try:
                    sent_code = await asyncio.wait_for(client.send_code_request(PHONE_NUMBER), timeout=30)
                    phone_code_hash = sent_code.phone_code_hash
                    print(f'Code sent to number {PHONE_NUMBER}')
                except asyncio.TimeoutError:
                    print('Timeout while requesting code. Check your internet connection.')
                    await client.disconnect()
                    return
                
                # If code is provided via LOGIN_CODE env (useful for Railway/CI)
                if LOGIN_CODE:
                    code = LOGIN_CODE.strip()
                    print('Using code from environment variable LOGIN_CODE')
                else:
                    # Try to get code from chat first, with a short timeout
                    print(f'Waiting for code from chat {CODE_CHAT_NUMBER} (or press Enter to enter manually)...')
                    try:
                        code = await asyncio.wait_for(wait_for_code(timeout=30), timeout=30)
                    except asyncio.TimeoutError:
                        code = None
                    
                    # If no code from chat, ask user to enter manually
                    if not code:
                        print('No code received from chat. Please enter it manually.')
                        # Use asyncio.to_thread for non-blocking input (Python 3.9+)
                        # Fallback to regular input for older Python versions
                        try:
                            code = await asyncio.to_thread(input, 'Enter the login code: ')
                        except AttributeError:
                            # Python < 3.9 fallback
                            code = input('Enter the login code: ')
                        code = code.strip()
                
                if not code:
                    print('No code provided. Stopping.')
                    await client.disconnect()
                    return
                
                # Try signing in with received code
                try:
                    await client.sign_in(PHONE_NUMBER, code, phone_code_hash=phone_code_hash)
                    print('Authorized successfully!')
                except SessionPasswordNeededError:
                    # 2FA password required
                    password = os.getenv('TWO_FA_PASSWORD')
                    if password:
                        await client.sign_in(password=password)
                        print('Authorized successfully with 2FA!')
                    else:
                        print('2FA password required. Set TWO_FA_PASSWORD in environment variables')
                        await client.disconnect()
                        return
            except Exception as e:
                print(f'Error during authorization: {e}')
                await client.disconnect()
                return
        else:
            print('Already authorized!')
        
        # Get account info
        print('Fetching account information...')
        me = await client.get_me()
        print(f'Logged in as: {me.first_name} {me.last_name or ""} (@{me.username or "no username"})')
        
        # Start background task for handling code requests
        asyncio.create_task(code_request_handler())
        print('✅ Code request handler started')
        
        # Run client
        print('Bot is running. Press Ctrl+C to stop.')
        await client.run_until_disconnected()
    except Exception as e:
        print(f'Error: {e}')
        if client.is_connected():
            await client.disconnect()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nStopping bot...')
    except Exception as e:
        print(f'Error: {e}')

