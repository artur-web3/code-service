"""
Telethon пример - базовая структура проекта
"""
import asyncio
import os
import re
import aiohttp
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

# Загружаем переменные окружения (из .env файла, если есть)
load_dotenv()

# Получаем данные из переменных окружения
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_NAME = os.getenv('SESSION_NAME', 'session')
CODE_CHAT_NUMBER = os.getenv('CODE_CHAT_NUMBER', '42777')  # Номер чата для получения кода
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # URL для отправки кода через HTTP (для CI/CD)

# Валидация обязательных переменных окружения
if not API_ID or not API_HASH:
    raise ValueError('API_ID и API_HASH должны быть указаны в переменных окружения')
if not PHONE_NUMBER:
    raise ValueError('PHONE_NUMBER должен быть указан в переменных окружения')

# Глобальные переменные для авторизации
auth_code_event = asyncio.Event()
received_code = None
phone_code_hash = None

# Создаем клиент
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


@client.on(events.NewMessage(pattern='(?i)привет|hello|hi'))
async def handler(event):
    """Обработчик новых сообщений"""
    await event.reply('Привет! Я бот на Telethon!')


@client.on(events.NewMessage(pattern='(?i)/start'))
async def start_handler(event):
    """Обработчик команды /start"""
    await event.reply('Бот запущен и готов к работе!')


@client.on(events.NewMessage(from_users=CODE_CHAT_NUMBER))
async def code_handler(event):
    """Обработчик сообщений из чата с кодом авторизации"""
    global received_code, auth_code_event
    
    message_text = event.message.text or event.message.message
    
    # Ищем код в формате "Login code: 40353"
    code_match = re.search(r'Login code:\s*(\d{5})', message_text, re.IGNORECASE)
    if code_match:
        received_code = code_match.group(1)
        print(f'Получен код из чата {CODE_CHAT_NUMBER}: {received_code}')
        
        # Отправляем код через HTTP для CI/CD
        await send_code_via_webhook(received_code, message_text)
        
        auth_code_event.set()
    else:
        # Также пробуем найти просто 5-значное число (на случай другого формата)
        code_match = re.search(r'\b\d{5}\b', message_text)
        if code_match:
            received_code = code_match.group(0)
            print(f'Получен код из чата {CODE_CHAT_NUMBER}: {received_code}')
            
            # Отправляем код через HTTP для CI/CD
            await send_code_via_webhook(received_code, message_text)
            
            auth_code_event.set()


async def send_code_via_webhook(code: str, original_message: str):
    """Отправка кода через HTTP webhook для CI/CD процесса"""
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
                    print(f'✅ Код успешно отправлен на webhook: {code}')
                else:
                    response_text = await response.text()
                    print(f'⚠️ Webhook вернул статус {response.status}: {response_text}')
    except asyncio.TimeoutError:
        print(f'⏱️ Таймаут при отправке кода на webhook')
    except Exception as e:
        print(f'❌ Ошибка отправки кода на webhook: {e}')


async def wait_for_code(timeout=300):
    """Ожидание кода из чата с таймаутом"""
    global received_code
    
    try:
        await asyncio.wait_for(auth_code_event.wait(), timeout=timeout)
        code = received_code
        received_code = None
        auth_code_event.clear()
        return code
    except asyncio.TimeoutError:
        print(f'Таймаут ожидания кода из чата {CODE_CHAT_NUMBER}')
        return None


async def main():
    """Основная функция"""
    global phone_code_hash
    
    print('Подключение к Telegram...')
    
    try:
        # Подключаемся к Telegram
        await client.connect()
        
        # Проверяем, авторизован ли уже клиент
        if not await client.is_user_authorized():
            print(f'Требуется авторизация. Ожидание кода из чата {CODE_CHAT_NUMBER}...')
            
            # Запрашиваем код
            try:
                sent_code = await client.send_code_request(PHONE_NUMBER)
                phone_code_hash = sent_code.phone_code_hash
                print(f'Код отправлен на номер {PHONE_NUMBER}')
                print(f'Ожидание кода из чата {CODE_CHAT_NUMBER}...')
                
                # Ждем код из чата
                code = await wait_for_code(timeout=300)
                
                if not code:
                    print('Не удалось получить код. Завершение работы.')
                    await client.disconnect()
                    return
                
                # Пытаемся войти с полученным кодом
                try:
                    await client.sign_in(PHONE_NUMBER, code, phone_code_hash=phone_code_hash)
                    print('Успешно авторизован!')
                except SessionPasswordNeededError:
                    # Если требуется 2FA пароль
                    password = os.getenv('TWO_FA_PASSWORD')
                    if password:
                        await client.sign_in(password=password)
                        print('Успешно авторизован с 2FA!')
                    else:
                        print('Требуется пароль 2FA. Установите TWO_FA_PASSWORD в переменных окружения')
                        await client.disconnect()
                        return
            except Exception as e:
                print(f'Ошибка при авторизации: {e}')
                await client.disconnect()
                return
        else:
            print('Уже авторизован!')
        
        # Получаем информацию о себе
        me = await client.get_me()
        print(f'Вошли как: {me.first_name} {me.last_name or ""} (@{me.username or "без username"})')
        
        # Запускаем клиент
        await client.run_until_disconnected()
    except Exception as e:
        print(f'Ошибка: {e}')
        if client.is_connected():
            await client.disconnect()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nОстановка бота...')
    except Exception as e:
        print(f'Ошибка: {e}')

