import logging
import aiohttp
from app.config import settings

async def send_to_bitrix24(data: dict):
    if not settings.bitrix24_webhook:
        logging.info("Bitrix24 webhook URL is not configured. Skipping.")
        return False
        
    try:
        name = data.get('address', '')
        company = data.get('company', '')
        inn = data.get('inn', '')
        phone = data.get('phone', '')
        email = data.get('email', '')
        selected_service = data.get('selected_service', '')
        user_message_text = data.get('user_message', '')
        
        # Build comments for Bitrix24
        comments = []
        if selected_service:
            comments.append(f"Услуга: {selected_service}")
        if user_message_text:
            comments.append(f"Запрос: {user_message_text}")
            
        if selected_service == "Таможенное оформление":
            comments.append(f"Товар: {data.get('product_name', 'Не указан')}")
            comments.append(f"Логистика: {data.get('logistics_interest', 'Не указано')}")
            comments.append(f"Вес: {data.get('cargo_weight', 'Не указан')}")
            comments.append(f"Забрать из: {data.get('pickup_location', 'Не указано')}")
            comments.append(f"Доставить в: {data.get('delivery_location', 'Не указано')}")
            comments.append(f"Таможня: {data.get('customs_location', 'Не указано')}")
            comments.append(f"Условия: {data.get('special_conditions', 'Не указано')}")
        elif selected_service == "Торговый дом (закупка товаров)" or "Торговый дом" in selected_service:
            comments.append(f"Товар: {data.get('product', 'Не указан')}")
            comments.append(f"Страна: {data.get('country', 'Не указана')}")
            comments.append(f"Сумма: {data.get('amount', 'Не указана')} {data.get('currency', '')}")
            
        comments.append(f"\nИНН: {inn}")

        payload = {
            "fields": {
                "TITLE": f"Заявка из бота - {company or name}",
                "NAME": name,
                "COMPANY_TITLE": company,
                "COMMENTS": "\n".join(comments),
                "PHONE": [{"VALUE": phone, "VALUE_TYPE": "WORK"}],
                "EMAIL": [{"VALUE": email, "VALUE_TYPE": "WORK"}]
            },
            "params": { "REGISTER_SONET_EVENT": "Y" }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(settings.bitrix24_webhook, json=payload) as resp:
                if resp.status == 200:
                    logging.info("✅ Successfully sent data to Bitrix24")
                    return True
                else:
                    logging.error(f"❌ Bitrix24 error: {resp.status} - {await resp.text()}")
                    return False
    except Exception as e:
        logging.exception("❌ Failed to send data to Bitrix24")
        return False
