#!/usr/bin/env python3
"""
Email Sender Bot - альтернативный способ отправки email через Telegram Bot API
"""
import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import logging

# Настройки
EMAIL_BOT_TOKEN = os.getenv("EMAIL_BOT_TOKEN", "")  # Токен бота для отправки email
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
EMAIL_SERVICE_URL = os.getenv("EMAIL_SERVICE_URL", "https://api.emailjs.com/api/v1.0/email/send")

# Инициализация
bot = Bot(EMAIL_BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("send_email"))
async def send_email_via_api(message: types.Message):
    """Отправка email через внешний API"""
    try:
        # Данные для отправки
        email_data = {
            "service_id": "gmail",
            "template_id": "template_123",
            "user_id": "user_123",
            "template_params": {
                "to_email": "sb@sbcargo.ru",
                "from_name": "KVT Bot",
                "subject": "Новая заявка",
                "message": "Тестовое сообщение от бота"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(EMAIL_SERVICE_URL, json=email_data) as response:
                if response.status == 200:
                    await message.answer("✅ Email отправлен через API!")
                else:
                    await message.answer(f"❌ Ошибка API: {response.status}")
                    
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
