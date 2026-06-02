"""
Wazzup24 API client for WhatsApp Business integration.
Handles sending messages, files, and managing the Wazzup24 API.

API Documentation: https://api-docs.wazzup24.com/
"""
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class WazzupClient:
    """Async client for Wazzup24 WhatsApp Business API."""

    BASE_URL = "https://api.wazzup24.com/v3"

    def __init__(self, api_key: str, chat_id: str):
        """
        Initialize Wazzup24 client.

        :param api_key: Your Wazzup24 API key
        :param chat_id: Your Wazzup24 chat/instance ID
        """
        self.api_key = api_key
        self.chat_id = chat_id
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def send_message(
        self,
        phone: str,
        text: str,
        quoted_message_id: Optional[str] = None,
    ) -> dict:
        """
        Send a text message via WhatsApp.

        :param phone: Recipient phone number (with country code, e.g. '79991234567')
        :param text: Message text
        :param quoted_message_id: Optional message ID to quote/reply to
        :return: API response dict
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}/message"

        # Normalize phone: remove +, spaces, dashes
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")

        payload = {
            "chatId": f"{clean_phone}@c.us",
            "content": {
                "type": "text",
                "text": text,
            },
        }

        if quoted_message_id:
            payload["quotedMessageId"] = quoted_message_id

        try:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if resp.status == 200:
                    logger.info(f"Message sent to {clean_phone}: {data.get('id', 'unknown')}")
                    return data
                else:
                    logger.error(f"Failed to send message to {clean_phone}: {resp.status} - {data}")
                    return data
        except Exception as e:
            logger.error(f"Error sending message to {clean_phone}: {e}")
            raise

    async def send_file(
        self,
        phone: str,
        file_url: str,
        caption: str = "",
        filename: str = "",
    ) -> dict:
        """
        Send a file/image via WhatsApp.

        :param phone: Recipient phone number
        :param file_url: URL of the file to send
        :param caption: Optional caption text
        :param filename: Optional filename
        :return: API response dict
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}/message"

        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")

        payload = {
            "chatId": f"{clean_phone}@c.us",
            "content": {
                "type": "file",
                "fileUrl": file_url,
                "caption": caption,
                "filename": filename,
            },
        }

        try:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if resp.status == 200:
                    logger.info(f"File sent to {clean_phone}: {data.get('id', 'unknown')}")
                    return data
                else:
                    logger.error(f"Failed to send file to {clean_phone}: {resp.status} - {data}")
                    return data
        except Exception as e:
            logger.error(f"Error sending file to {clean_phone}: {e}")
            raise

    async def send_keyboard(
        self,
        phone: str,
        text: str,
        buttons: list[dict],
    ) -> dict:
        """
        Send a message with inline keyboard buttons.

        :param phone: Recipient phone number
        :param text: Message text
        :param buttons: List of button dicts, e.g. [{"id": "btn1", "text": "Label"}]
        :return: API response dict
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}/message"

        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")

        # Wazzup24 uses a different format for keyboards
        payload = {
            "chatId": f"{clean_phone}@c.us",
            "content": {
                "type": "listMessage",
                "text": text,
                "sections": [
                    {
                        "title": "Menu",
                        "rows": buttons,
                    }
                ],
            },
        }

        try:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if resp.status == 200:
                    logger.info(f"Keyboard sent to {clean_phone}")
                    return data
                else:
                    logger.error(f"Failed to send keyboard: {resp.status} - {data}")
                    return data
        except Exception as e:
            logger.error(f"Error sending keyboard to {clean_phone}: {e}")
            raise

    async def check_status(self) -> dict:
        """
        Check the Wazzup24 instance status.

        :return: Status dict
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}/status"

        try:
            async with session.get(url) as resp:
                data = await resp.json()
                if resp.status == 200:
                    logger.info(f"Wazzup24 status: {data}")
                    return data
                else:
                    logger.error(f"Failed to get status: {resp.status} - {data}")
                    return data
        except Exception as e:
            logger.error(f"Error checking status: {e}")
            raise
