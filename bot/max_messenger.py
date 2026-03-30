"""
Абстракция для работы с мессенджером Max
Этот модуль предоставляет универсальный интерфейс для работы с различными мессенджерами
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv("local.env")


@dataclass
class MaxMessage:
    """Класс для представления сообщения из мессенджера Max"""
    message_id: str
    chat_id: str
    user_id: str
    text: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timestamp: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class MaxKeyboard:
    """Класс для представления клавиатуры"""
    buttons: List[List[str]]
    resize_keyboard: bool = True
    one_time_keyboard: bool = False


class MaxMessengerClient(ABC):
    """Абстрактный базовый класс для клиента мессенджера Max"""
    
    def __init__(self, token: str, api_url: Optional[str] = None):
        self.token = token
        self.api_url = api_url
        self.logger = logging.getLogger(__name__)
    
    @abstractmethod
    async def send_message(
        self,
        chat_id: str,
        text: str,
        keyboard: Optional[MaxKeyboard] = None,
        parse_mode: Optional[str] = None
    ) -> bool:
        """Отправить сообщение"""
        pass
    
    @abstractmethod
    async def get_updates(self) -> List[MaxMessage]:
        """Получить обновления (новые сообщения)"""
        pass
    
    @abstractmethod
    async def start_polling(self, handler):
        """Начать опрос обновлений"""
        pass
    
    @abstractmethod
    def parse_message(self, raw_data: Dict[str, Any]) -> MaxMessage:
        """Парсинг сырых данных в MaxMessage"""
        pass


class MaxMessengerAPI(MaxMessengerClient):
    """
    Реализация клиента для мессенджера Max
    Этот класс нужно адаптировать под конкретный API мессенджера Max
    """
    
    def __init__(self, token: str, api_url: Optional[str] = None):
        super().__init__(token, api_url)
        # Настройки из переменных окружения
        self.api_url = api_url or os.getenv("MAX_API_URL", "https://api.max.com/v1")
        self.timeout = int(os.getenv("MAX_API_TIMEOUT", "30"))
        
    async def send_message(
        self,
        chat_id: str,
        text: str,
        keyboard: Optional[MaxKeyboard] = None,
        parse_mode: Optional[str] = None
    ) -> bool:
        """Отправить сообщение через API Max"""
        try:
            import aiohttp
            
            url = f"{self.api_url}/messages/send"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode or "HTML"
            }
            
            if keyboard:
                payload["keyboard"] = {
                    "buttons": keyboard.buttons,
                    "resize_keyboard": keyboard.resize_keyboard,
                    "one_time_keyboard": keyboard.one_time_keyboard
                }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        self.logger.info(f"Message sent to {chat_id}")
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to send message: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return False
    
    async def get_updates(self) -> List[MaxMessage]:
        """Получить обновления через API Max"""
        try:
            import aiohttp
            
            url = f"{self.api_url}/updates"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "timeout": self.timeout,
                "offset": getattr(self, "_last_update_id", 0)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.timeout + 10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        messages = []
                        
                        if "result" in data:
                            for update in data["result"]:
                                if "message" in update:
                                    msg = self.parse_message(update["message"])
                                    messages.append(msg)
                                    self._last_update_id = update.get("update_id", 0)
                        
                        return messages
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to get updates: {response.status} - {error_text}")
                        return []
                        
        except Exception as e:
            self.logger.error(f"Error getting updates: {e}")
            return []
    
    async def start_polling(self, handler):
        """Начать опрос обновлений"""
        import asyncio
        
        self.logger.info("Starting Max messenger polling...")
        
        while True:
            try:
                updates = await self.get_updates()
                for message in updates:
                    await handler(message)
                
                # Небольшая задержка между запросами
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(5)  # Задержка при ошибке
    
    def parse_message(self, raw_data: Dict[str, Any]) -> MaxMessage:
        """Парсинг сырых данных в MaxMessage"""
        # Адаптируйте эту функцию под формат данных вашего API Max
        return MaxMessage(
            message_id=str(raw_data.get("message_id", "")),
            chat_id=str(raw_data.get("chat", {}).get("id", "")),
            user_id=str(raw_data.get("from", {}).get("id", "")),
            text=raw_data.get("text", ""),
            username=raw_data.get("from", {}).get("username"),
            first_name=raw_data.get("from", {}).get("first_name"),
            last_name=raw_data.get("from", {}).get("last_name"),
            timestamp=raw_data.get("date"),
            raw_data=raw_data
        )


# Глобальный экземпляр клиента (будет инициализирован в worker.py)
max_client: Optional[MaxMessengerClient] = None


def get_max_client() -> MaxMessengerClient:
    """Получить глобальный экземпляр клиента Max"""
    global max_client
    if max_client is None:
        token = os.getenv("MAX_BOT_TOKEN", os.getenv("BOT_TOKEN", ""))
        api_url = os.getenv("MAX_API_URL")
        max_client = MaxMessengerAPI(token, api_url)
    return max_client
