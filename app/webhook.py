"""
Wazzup24 Webhook handler for receiving incoming WhatsApp messages.
This module provides endpoints for Wazzup24 to send webhook notifications.
"""
import logging
from typing import Any

from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/wazzup")
async def wazzup_webhook(request: Request) -> dict[str, Any]:
    """
    Receive webhook notifications from Wazzup24.
    
    Wazzup24 sends POST requests with message data in JSON format.
    This endpoint acknowledges the webhook and processes incoming messages.
    
    Expected payload format from Wazzup24:
    {
        "type": "incoming_message",
        "chatId": "79991234567@c.us",
        "timestamp": 1234567890,
        "body": {
            "type": "textMessage",
            "text": "Hello"
        },
        "id": "message_id"
    }
    """
    try:
        body = await request.json()
        logger.info(f"Received Wazzup24 webhook: {body}")
        
        # Extract key fields
        webhook_type = body.get("type", body.get("event", "unknown"))
        chat_id = body.get("chatId", "")
        message_id = body.get("id", body.get("messageId", ""))
        
        # Extract phone number from chatId (format: "79991234567@c.us")
        phone = ""
        if chat_id:
            phone = chat_id.split("@")[0]
        
        logger.info(
            f"Webhook type: {webhook_type}, "
            f"Chat: {chat_id}, "
            f"Phone: {phone}, "
            f"Message ID: {message_id}"
        )
        
        # Process different webhook types
        if webhook_type in ["incoming_message", "message", "incoming"]:
            await _process_incoming_message(body, phone)
        elif webhook_type in ["outgoing_message", "outgoing"]:
            await _process_outgoing_message(body, phone)
        elif webhook_type in ["status", "message_status"]:
            await _process_message_status(body, phone)
        else:
            logger.info(f"Unhandled webhook type: {webhook_type}")
        
        # Always return 200 OK to acknowledge receipt
        return {
            "status": "ok",
            "message": "Webhook received",
            "webhook_type": webhook_type,
        }
        
    except Exception as e:
        logger.error(f"Error processing Wazzup24 webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")


@router.get("/wazzup")
async def wazzup_webhook_verify(request: Request) -> dict[str, str]:
    """
    Verify webhook endpoint for Wazzup24.
    Wazzup24 may send a GET request to verify the webhook URL.
    """
    logger.info("Wazzup24 webhook verification request received")
    return {
        "status": "ok",
        "message": "Webhook endpoint is active",
        "url": str(request.url),
    }


async def _process_incoming_message(data: dict, phone: str) -> None:
    """Process incoming message from WhatsApp user."""
    body = data.get("body", data.get("message", {}))
    message_text = ""
    
    if isinstance(body, dict):
        message_text = body.get("text", body.get("caption", ""))
    elif isinstance(body, str):
        message_text = body
    
    logger.info(
        f"Incoming message from {phone}: {message_text[:100]}..."
        if len(message_text) > 100
        else f"Incoming message from {phone}: {message_text}"
    )
    
    # Here you can integrate with your bot logic
    # For example, forward to the Max bot or process directly


async def _process_outgoing_message(data: dict, phone: str) -> None:
    """Process outgoing message sent via WhatsApp."""
    logger.info(f"Outgoing message to {phone}")


async def _process_message_status(data: dict, phone: str) -> None:
    """Process message status update (sent, delivered, read)."""
    status = data.get("status", "unknown")
    logger.info(f"Message status update for {phone}: {status}")
