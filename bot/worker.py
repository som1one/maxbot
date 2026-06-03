import logging
import os
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiohttp
import certifi
from aiomax import Bot, buttons
from aiomax.fsm import FSMCursor
from app.config import settings
import urllib.parse
from .bitrix import send_to_bitrix24

# Use certifi CA bundle by default so Max API TLS verification works
# in environments where the system trust store is incomplete or proxied.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

# aiomax accepts keyboards as plain nested button lists.
# Keep the existing code shape from the legacy bot port by normalizing
# Markup(...) calls into a passthrough helper when the attribute is absent.
if not hasattr(buttons, "Markup"):
    buttons.Markup = lambda rows: rows

# Bot token and admin chat ID
BOT_TOKEN = settings.bot_token
ADMIN_CHAT_ID = settings.admin_chat_id

# Debug logging
logging.info(f"BOT_TOKEN: {BOT_TOKEN[:10]}..." if BOT_TOKEN else "BOT_TOKEN: not set")
logging.info(f"ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")

# Email settings
SMTP_HOST = settings.smtp_host
SMTP_PORT = settings.smtp_port
SMTP_USER = settings.smtp_user or ""
SMTP_FROM = settings.resolved_smtp_from
SMTP_PASSWORD = settings.smtp_login_password or ""
ADMIN_EMAIL = settings.default_notification_email or ""
EMAIL_ENABLED = settings.email_enabled
STARTUP_EMAIL_TEST = settings.startup_email_test

# Alternative SMTP servers for fallback
SMTP_ALTERNATIVES = [
    # Local MailHog for development/testing (highest priority)
    ("mailhog", 1025, "plain"),
    ("localhost", 1025, "plain"),
    ("127.0.0.1", 1025, "plain"),
    # Only try external if local fails
    ("smtp.gmail.com", 465, "ssl"),
    ("smtp.gmail.com", 587, "starttls")
]

# Initialize bot with Max messenger
bot = Bot(access_token=BOT_TOKEN, default_format="html")

# Helper to notify admin chat safely
async def notify_admin(text: str) -> bool:
    if not ADMIN_CHAT_ID or ADMIN_CHAT_ID == 0:
        logging.warning("ADMIN_CHAT_ID is not set or zero; admin notification skipped")
        return False
    
    try:
        # Try to send message
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
        logging.info(f"Admin notification sent successfully to chat {ADMIN_CHAT_ID}")
        return True
    except Exception as e:
        error_msg = str(e)
        if "chat not found" in error_msg.lower() or "not found" in error_msg.lower():
            logging.error(f"ADMIN_CHAT_ID {ADMIN_CHAT_ID} is invalid. Please use /id command to get correct chat ID")
        elif "forbidden" in error_msg.lower():
            logging.error(f"Bot is blocked by user with chat ID {ADMIN_CHAT_ID}")
        else:
            logging.error(f"Failed to send admin notification: {e}")
        return False

# Email sending function
def send_email(subject: str, body: str, to_email: str = ADMIN_EMAIL):
    """Send email notification using working Gmail App Password method"""
    logging.info("=" * 50)
    logging.info("📧 EMAIL SENDING STARTED")
    logging.info("=" * 50)
    
    if not EMAIL_ENABLED:
        logging.warning("⚠️ Email notifications are DISABLED")
        return False

    if not to_email:
        logging.warning("⚠️ Recipient email is not configured")
        return False

    if not SMTP_HOST:
        logging.warning("⚠️ SMTP host is not configured")
        return False
    
    logging.info(f"📧 Email details:")
    logging.info(f"   📤 From: {SMTP_FROM}")
    logging.info(f"   📥 To: {to_email}")
    logging.info(f"   📝 Subject: {subject}")
    logging.info(f"   📄 Body length: {len(body)} characters")
    
    # Use Gmail App Password method (proven to work)
    try:
        # Gmail settings
        smtp_server = SMTP_HOST
        sender_email = SMTP_USER or SMTP_FROM
        
        # Use Gmail App Password from environment (sanitize spaces)
        app_password = SMTP_PASSWORD
        logging.info(f"🔐 Using App Password: {app_password[:4]}****{app_password[-4:] if len(app_password) >= 8 else '****'}")
        
        # Create message
        logging.info("📝 Creating email message...")
        msg = MIMEMultipart()
        msg['From'] = SMTP_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        
        # Try STARTTLS (587) first
        try:
            smtp_port = SMTP_PORT if SMTP_PORT != 465 else 587
            logging.info("🔗 Connecting to Gmail SMTP (STARTTLS)...")
            logging.info(f"   🌐 Server: {smtp_server}")
            logging.info(f"   🔌 Port: {smtp_port}")
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=20)
            server.set_debuglevel(0)
            server.ehlo()
            logging.info("🔒 Starting TLS encryption...")
            server.starttls()
            server.ehlo()
            if sender_email and app_password:
                logging.info("🔑 Authenticating with Gmail (STARTTLS)...")
                server.login(sender_email, app_password)
                logging.info("✅ Gmail authentication successful (STARTTLS)!")
        except Exception as e_starttls:
            logging.warning(f"⚠️ STARTTLS failed: {e_starttls}")
            # Try SSL (465)
            smtp_port = 465 if SMTP_PORT == 465 else SMTP_PORT
            logging.info("🔗 Connecting to Gmail SMTP (SSL)...")
            logging.info(f"   🌐 Server: {smtp_server}")
            logging.info(f"   🔌 Port: {smtp_port}")
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20)
            server.set_debuglevel(0)
            if sender_email and app_password:
                logging.info("🔑 Authenticating with Gmail (SSL)...")
                server.login(sender_email, app_password)
                logging.info("✅ Gmail authentication successful (SSL)!")
        
        logging.info("📤 Sending email message...")
        server.send_message(msg)
        server.quit()
        
        logging.info("🎉 EMAIL SENT SUCCESSFULLY!")
        logging.info(f"   📧 From: {sender_email}")
        logging.info(f"   📧 To: {to_email}")
        logging.info(f"   📝 Subject: {subject}")
        logging.info("=" * 50)
        return True
        
    except Exception as e:
        logging.error("❌ GMAIL METHOD FAILED!")
        logging.error(f"   🚨 Error: {e}")
        logging.error("   💡 Troubleshooting:")
        logging.error("      1. Check if 2FA is enabled in Gmail")
        logging.error("      2. Verify App Password is created")
        logging.error("      3. Ensure App Password is correct")
        logging.error("      4. Check network connectivity")
        
        # HTTPS fallback: Resend API (works over port 443)
        try:
            import requests
            resend_key = settings.resend_api_key
            if resend_key:
                logging.info("🌐 Trying HTTPS fallback via Resend API...")
                resend_url = "https://api.resend.com/emails"
                headers = {
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "from": f"KVT Bot <{SMTP_FROM}>",
                    "to": [to_email],
                    "subject": subject,
                    "html": body
                }
                resp = requests.post(resend_url, headers=headers, json=payload, timeout=15)
                if resp.status_code in (200, 201):
                    logging.info("✅ Email sent via Resend HTTPS fallback!")
                    return True
                else:
                    logging.warning(f"❌ Resend fallback failed: {resp.status_code} - {resp.text[:200]}")
            else:
                logging.info("ℹ️ RESEND_API_KEY not set; skipping HTTPS fallback")
        except Exception as e_resend:
            logging.warning(f"❌ Resend HTTPS fallback error: {e_resend}")
        
        # Fallback to local MailHog
        logging.info("🔄 Trying MailHog fallback...")
        try:
            logging.info("🔗 Connecting to MailHog...")
            server = smtplib.SMTP("mailhog", 1025, timeout=5)
            logging.info("📤 Sending via MailHog...")
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
            server.quit()
            logging.info("✅ Email sent via MailHog fallback!")
            logging.info("   🌐 Check MailHog UI: http://localhost:8025")
            return True
        except Exception as mailhog_e:
            logging.error("❌ MailHog fallback also failed!")
            logging.error(f"   🚨 MailHog error: {mailhog_e}")
    
    # All methods failed
    logging.error("💥 ALL EMAIL METHODS FAILED!")
    logging.error("   📧 Email was NOT sent")
    logging.error("=" * 50)
    return False

# FSM States - используем строковые константы вместо StatesGroup
class ApplicationStates:
    waiting_for_address = "waiting_for_address"
    waiting_for_company = "waiting_for_company"
    waiting_for_inn = "waiting_for_inn"
    waiting_for_phone = "waiting_for_phone"
    waiting_for_email = "waiting_for_email"
    waiting_for_service = "waiting_for_service"
    waiting_for_message = "waiting_for_message"
    # Trading house states
    waiting_for_product = "waiting_for_product"
    waiting_for_country = "waiting_for_country"
    waiting_for_amount = "waiting_for_amount"
    waiting_for_currency = "waiting_for_currency"
    waiting_for_trading_house_message = "waiting_for_trading_house_message"
    # Customs clearance states
    waiting_for_product_name = "waiting_for_product_name"
    waiting_for_logistics_interest = "waiting_for_logistics_interest"
    waiting_for_cargo_weight = "waiting_for_cargo_weight"
    waiting_for_pickup_location = "waiting_for_pickup_location"
    waiting_for_delivery_location = "waiting_for_delivery_location"
    waiting_for_customs_location = "waiting_for_customs_location"
    waiting_for_special_conditions = "waiting_for_special_conditions"
    waiting_for_customs_final = "waiting_for_customs_final"
    # Manager transfer states
    waiting_for_manager_phone = "waiting_for_manager_phone"
    waiting_for_manager_contact = "waiting_for_manager_contact"
    # Edit states
    waiting_for_edit_text = "waiting_for_edit_text"
    waiting_for_edit_field = "waiting_for_edit_field"


TRADING_HOUSE_SERVICE = "Торговый дом (закупка товаров)"


# Helper function to get FSM cursor
def get_state(message) -> FSMCursor:
    """Получить FSM cursor для пользователя"""
    sender = getattr(message, "sender", None)
    recipient = getattr(message, "recipient", None)
    user_id = sender.user_id if sender else recipient.chat_id
    return FSMCursor(bot.storage, user_id)


def get_message_text(message) -> str:
    """Безопасно получить и очистить текст сообщения из Max."""
    if not message or not message.body or not message.body.text:
        return ""
    return message.body.text.strip()


async def handle_call_manager_action(message, state, service_name=None):
    """Helper to generate dynamic link with chat context and notify admin."""
    data = state.get_data() or {}
    selected_service = service_name or data.get('selected_service', 'Не указана')
    
    max_chat_url = settings.max_chat_url or "https://example.com/max-chat"
    context_parts = ["Заявка из бота:"]
    if selected_service and selected_service != 'Не указана':
        context_parts.append(f"Услуга: {selected_service}")
    if data.get('address'):
        context_parts.append(f"Обращение: {data.get('address')}")
    if data.get('phone'):
        context_parts.append(f"Телефон: {data.get('phone')}")
    if data.get('email'):
        context_parts.append(f"Email: {data.get('email')}")
    if data.get('user_message'):
        context_parts.append(f"Сообщение: {data.get('user_message')}")
    if data.get('product'):
        context_parts.append(f"Товар: {data.get('product')}")
    if data.get('country'):
        context_parts.append(f"Страна: {data.get('country')}")
    if data.get('amount'):
        curr = data.get('currency', '')
        context_parts.append(f"Сумма: {data.get('amount')} {curr}".strip())
    if data.get('product_name'):
        context_parts.append(f"Товар: {data.get('product_name')}")
    if data.get('logistics_interest'):
        context_parts.append(f"Логистика: {data.get('logistics_interest')}")
    if data.get('cargo_weight'):
        context_parts.append(f"Вес: {data.get('cargo_weight')}")
    if data.get('pickup_location'):
        context_parts.append(f"Откуда: {data.get('pickup_location')}")
    if data.get('delivery_location'):
        context_parts.append(f"Куда: {data.get('delivery_location')}")
    if data.get('customs_location'):
        context_parts.append(f"Таможня: {data.get('customs_location')}")
    if data.get('special_conditions'):
        context_parts.append(f"Условия: {data.get('special_conditions')}")
        
    context_text = "\n".join(context_parts)
    
    # Safely append query parameters
    query_string = urllib.parse.urlencode({'text': context_text})
    if "?" in max_chat_url:
        chat_url_with_context = f"{max_chat_url}&{query_string}"
    else:
        chat_url_with_context = f"{max_chat_url}?{query_string}"
        
    keyboard = buttons.Markup([
        [buttons.LinkButton("Перейти в чат", url=chat_url_with_context)]
    ])
    
    await message.send(
        f"📞 <b>Связь с менеджером</b>\n\n"
        f"Пожалуйста, нажмите на кнопку ниже, чтобы перейти в чат с нашим менеджером. "
        f"Мы уже передали ему контекст вашей заявки!",
        keyboard=keyboard,
        format="html"
    )
    
    admin_text = (
        f"📞 <b>Запрос связи с менеджером (Макс чат)</b>\n\n"
        f"Услуга: {selected_service}\n"
        f"Имя: {data.get('address', 'Не указано')}\n"
        f"Username: {get_sender_display(message)}"
    )
    import asyncio
    asyncio.create_task(notify_admin(admin_text))
    
    state.clear()


def get_sender_display(message) -> str:
    """Вернуть username с @ или человекочитаемый fallback."""
    sender = getattr(message, "sender", None)
    if sender and sender.username:
        return f"@{sender.username}"
    return "Не указан"


def get_chat_id(message):
    recipient = getattr(message, "recipient", None)
    return recipient.chat_id if recipient else None


def get_sender_id(message):
    sender = getattr(message, "sender", None)
    return sender.user_id if sender else None


def format_message_timestamp(message) -> str:
    timestamp = getattr(message, "timestamp", None)
    if not timestamp:
        return "N/A"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def is_trading_house_service(service_name: str | None) -> bool:
    return service_name == TRADING_HOUSE_SERVICE


async def send_start_menu(target, user_id: int):
    logging.info("📨 Sending start menu to user_id=%s", user_id)
    FSMCursor(bot.storage, user_id).clear()
    keyboard = buttons.Markup([
        [buttons.MessageButton("Юр. лица и ИП")],
        [buttons.MessageButton("Физ. лица")]
    ])
    
    await target.send(
        "Добрый день! Подскажите, пожалуйста, Вас интересуют услуги как:",
        keyboard=keyboard
    )
    logging.info("✅ Start menu sent to user_id=%s", user_id)


@bot.on_bot_start()
async def handle_bot_started(payload):
    logging.info("🚀 bot_started event chat_id=%s user_id=%s", payload.chat_id, payload.user_id)
    await send_start_menu(payload, payload.user_id)


@bot.on_command("start")
async def start_command(ctx):
    logging.info("⌨️ /start command chat_id=%s user_id=%s", ctx.recipient.chat_id, ctx.user_id)
    await send_start_menu(ctx, ctx.user_id)


@bot.on_message()
async def process_address(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_address:
        return False
    
    address = get_message_text(message)
    
    if len(address) < 2:
        await message.send("❌ Пожалуйста, введите корректное обращение:")
        return True
    
    data = state.get_data() or {}
    data["address"] = address
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    await message.send(
        "Название вашей компании:",
        keyboard=keyboard
    )
    state.change_state(ApplicationStates.waiting_for_company)
    return True

@bot.on_message()
async def process_company(message):
    state = get_state(message)
    if state.get_state() != ApplicationStates.waiting_for_company:
        return False
        
    company = get_message_text(message)
    if len(company) < 2:
        await message.send("❌ Пожалуйста, введите корректное название компании:")
        return True
        
    data = state.get_data() or {}
    data["company"] = company
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    await message.send("Введите ИНН вашей компании:", keyboard=keyboard)
    state.change_state(ApplicationStates.waiting_for_inn)
    return True

@bot.on_message()
async def process_inn(message):
    state = get_state(message)
    if state.get_state() != ApplicationStates.waiting_for_inn:
        return False
        
    inn = get_message_text(message)
    if len(inn) < 9:
        await message.send("❌ Пожалуйста, введите корректный ИНН:")
        return True
        
    data = state.get_data() or {}
    data["inn"] = inn
    state.change_data(data)
    
    keyboard = buttons.Markup([
        [buttons.MessageButton("Таможенное оформление")],
        [buttons.MessageButton("Логистика")],
        [buttons.MessageButton("Сертификация")],
        [buttons.MessageButton("Сопровождение ВЭД")],
        [buttons.MessageButton("Платежный агент")],
        [buttons.MessageButton("ВЭД агент")]
    ])
    
    await message.send(
        "Какая услуга Вас интересует? Вы так же можете задать любой вопрос, просто введите его.",
        keyboard=keyboard
    )
    state.change_state(ApplicationStates.waiting_for_service)
    return True


@bot.on_message()
async def process_phone_submission(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_phone:
        return False
    text = get_message_text(message)
    if text == "✅ Отправить заявку":
        logging.info("=" * 60)
        logging.info("📋 APPLICATION SUBMISSION STARTED")
        logging.info("=" * 60)
        
        # Process the application
        data = state.get_data() or {}
        name = data.get('address', 'Не указано')  # Используем address как имя/обращение
        address = data.get('address', 'Не указано')
        user_type = data.get('user_type', 'Неизвестно')
        selected_service = data.get('selected_service', 'Не указана')
        user_message_text = data.get('user_message', 'Не указано')
        phone = data.get('phone', 'Не указан')
        email = data.get('email', 'Не указан')
        
        # Get username for both admin notification and email
        username = get_sender_display(message)
        
        logging.info("📋 Application data collected:")
        logging.info(f"   👤 Name: {name}")
        logging.info(f"   📝 Address: {address}")
        logging.info(f"   🏷️ User Type: {user_type}")
        logging.info(f"   🔧 Service: {selected_service}")
        logging.info(f"   📞 Phone: {phone}")
        logging.info(f"   👤 Username: {username}")
        logging.info(f"   💬 Message: {user_message_text}")
        logging.info(f"   🆔 Chat ID: {get_chat_id(message)}")
        logging.info(f"   👤 User ID: {get_sender_id(message) or 'Unknown'}")
        
        # Show processing message
        await message.send("⏳ Обрабатываем вашу заявку...", format="html")
        logging.info("📱 Processing message sent to user")
        
        # Notify admin chat with inline buttons
        logging.info("📤 Sending admin notification...")
        if ADMIN_CHAT_ID and ADMIN_CHAT_ID != 0:
            logging.info(f"📱 Admin Chat ID: {ADMIN_CHAT_ID}")
            
            # Check if it's customs clearance with detailed data
            if selected_service == "Таможенное оформление":
                product_name = data.get('product_name', 'Не указан')
                logistics_interest = data.get('logistics_interest', 'Не указано')
                cargo_weight = data.get('cargo_weight', 'Не указан')
                pickup = data.get('pickup_location', 'Не указано')
                delivery = data.get('delivery_location', 'Не указано')
                customs_location = data.get('customs_location', 'Не указано')
                special_conditions = data.get('special_conditions', 'Не указано')
                
                text = (
                    f"🔔 <b>Новая заявка - Таможенное оформление</b>\n\n"
                    f"👤 <b>Имя:</b> {name}\n"
                    f"📝 <b>Обращение:</b> {address}\n"
                    f"📞 <b>Телефон:</b> {phone}\n"
                    f"📧 <b>Email:</b> {email}\n"
                    f"👤 <b>Username:</b> {username}\n\n"
                    f"📦 <b>Товар:</b> {product_name}\n"
                    f"🚛 <b>Логистика:</b> {logistics_interest}\n"
                    f"⚖️ <b>Вес:</b> {cargo_weight}\n"
                    f"📍 <b>Забрать из:</b> {pickup}\n"
                    f"🎯 <b>Доставить в:</b> {delivery}\n"
                    f"🏛️ <b>Таможня:</b> {customs_location}\n"
                    f"⚠️ <b>Условия:</b> {special_conditions}"
                )
            else:
                text = (
                    f"🔔 <b>Новая заявка</b>\n\n"
                    f"🏷️ <b>Тип заявки:</b> {user_type}\n"
                    f"👤 <b>Имя:</b> {name}\n"
                    f"📝 <b>Обращение:</b> {address}\n"
                    f"📞 <b>Телефон:</b> {phone}\n"
                    f"📧 <b>Email:</b> {email}\n"
                    f"🔧 <b>Услуга:</b> {selected_service}\n"
                    f"💬 <b>Сообщение:</b> {user_message_text}\n"
                    f"👤 <b>Username:</b> {username}"
                )
            
            await notify_admin(text)
        
        # Send email notification (with fallback to admin chat only)
        email_sent = False
        try:
            email_subject = f"Новая заявка - {selected_service}"
            email_body = f"""
            <html>
            <body>
                <h2>🔔 Новая заявка</h2>
                <p><strong>Тип заявки:</strong> {user_type}</p>
                <p><strong>Имя:</strong> {name}</p>
                <p><strong>Обращение:</strong> {address}</p>
                <p><strong>Телефон:</strong> {phone}</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Услуга:</strong> {selected_service}</p>
                <p><strong>Сообщение:</strong> {user_message_text}</p>
                <p><strong>Username:</strong> {username}</p>
            </body>
            </html>
            """
            
            if selected_service == "Таможенное оформление":
                product_name = data.get('product_name', 'Не указан')
                logistics_interest = data.get('logistics_interest', 'Не указано')
                cargo_weight = data.get('cargo_weight', 'Не указан')
                pickup = data.get('pickup_location', 'Не указано')
                delivery = data.get('delivery_location', 'Не указано')
                customs_location = data.get('customs_location', 'Не указано')
                special_conditions = data.get('special_conditions', 'Не указано')
                
            email_body = f"""
            <html>
            <body>
                <h2>🔔 Новая заявка - Таможенное оформление</h2>
                <p><strong>Имя:</strong> {name}</p>
                <p><strong>Обращение:</strong> {address}</p>
                <p><strong>Телефон:</strong> {phone}</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Username:</strong> {username}</p>
                <hr>
                <h3>Детали заявки:</h3>
                <p><strong>Товар:</strong> {product_name}</p>
                <p><strong>Логистика:</strong> {logistics_interest}</p>
                <p><strong>Вес:</strong> {cargo_weight}</p>
                <p><strong>Забрать из:</strong> {pickup}</p>
                <p><strong>Доставить в:</strong> {delivery}</p>
                <p><strong>Таможня:</strong> {customs_location}</p>
                <p><strong>Условия:</strong> {special_conditions}</p>
            </body>
            </html>
            """
            
            logging.info("📧 Sending email notification...")
            logging.info(f"   📝 Subject: {email_subject}")
            logging.info(f"   📄 Body length: {len(email_body)} characters")
            
            email_sent = send_email(email_subject, email_body, ADMIN_EMAIL)
            if email_sent:
                logging.info("✅ Email notification sent successfully!")
                logging.info("   📧 Check admin email inbox")
            else:
                logging.warning("❌ Email notification failed!")
                logging.warning("   📱 But admin chat notification was sent")
        except Exception as e:
            logging.error("💥 Failed to send email notification!")
            logging.exception(f"   🚨 Error: {e}")

        keyboard = buttons.Markup([
            [buttons.MessageButton("🏠 Главное меню")]
        ])
        
        await message.send(
            "✅ <b>Спасибо! Ваша заявка успешно отправлена.</b>\n\n"
            "📋 <b>Детали заявки:</b>\n"
            f"👤 Имя: {name}\n"
            f"📝 Обращение: {address}\n"
            f"📞 Телефон: {phone}\n"
            f"🔧 Услуга: {selected_service}\n"
            f"💬 Сообщение: {user_message_text}\n\n"
            "Мы свяжемся с вами в ближайшее время для уточнения деталей!",
            keyboard=keyboard,
            format="html"
        )
        
        import asyncio
        asyncio.create_task(send_to_bitrix24(data))
        
        state.clear()
        return True
    
    # If not "Отправить заявку", treat as phone input
    phone = text
    
    # Validate phone input
    if len(phone) < 10:
        await message.send("❌ Пожалуйста, введите корректный номер телефона (минимум 10 символов):")
        return
    
    data = state.get_data() or {}
    data["phone"] = phone
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    await message.send(
        f"✅ <b>Телефон:</b> {phone}\n\n"
        f"📧 <b>Введите ваш email адрес (рабочий):</b>",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_email)
    return True


@bot.on_message()
async def process_email(message):
    """Handle email input for regular applications"""
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_email:
        return False
    
    # Check if user clicked "Отправить заявку"
    text = get_message_text(message)
    if text == "✅ Отправить заявку":
        logging.info("=" * 60)
        logging.info("📋 APPLICATION SUBMISSION STARTED (from email handler)")
        logging.info("=" * 60)
        
        # Process the application
        data = state.get_data() or {}
        name = data.get('address', 'Не указано')
        address = data.get('address', 'Не указано')
        user_type = data.get('user_type', 'Неизвестно')
        selected_service = data.get('selected_service', 'Не указана')
        user_message_text = data.get('user_message', 'Не указано')
        phone = data.get('phone', 'Не указан')
        email = data.get('email', 'Не указан')
        
        # Get username
        username = get_sender_display(message)
        
        # Show processing message
        await message.send("⏳ Обрабатываем вашу заявку...", format="html")
        
        # Notify admin chat
        if ADMIN_CHAT_ID and ADMIN_CHAT_ID != 0:
            if selected_service == "Таможенное оформление":
                product_name = data.get('product_name', 'Не указан')
                logistics_interest = data.get('logistics_interest', 'Не указано')
                cargo_weight = data.get('cargo_weight', 'Не указан')
                pickup = data.get('pickup_location', 'Не указано')
                delivery = data.get('delivery_location', 'Не указано')
                customs_location = data.get('customs_location', 'Не указано')
                special_conditions = data.get('special_conditions', 'Не указано')
                
                text = (
                    f"🔔 <b>Новая заявка - Таможенное оформление</b>\n\n"
                    f"👤 <b>Имя:</b> {name}\n"
                    f"📝 <b>Обращение:</b> {address}\n"
                    f"📞 <b>Телефон:</b> {phone}\n"
                    f"📧 <b>Email:</b> {email}\n"
                    f"👤 <b>Username:</b> {username}\n\n"
                    f"📦 <b>Товар:</b> {product_name}\n"
                    f"🚛 <b>Логистика:</b> {logistics_interest}\n"
                    f"⚖️ <b>Вес:</b> {cargo_weight}\n"
                    f"📍 <b>Забрать из:</b> {pickup}\n"
                    f"🎯 <b>Доставить в:</b> {delivery}\n"
                    f"🏛️ <b>Таможня:</b> {customs_location}\n"
                    f"⚠️ <b>Условия:</b> {special_conditions}"
                )
            else:
                text = (
                    f"🔔 <b>Новая заявка</b>\n\n"
                    f"🏷️ <b>Тип заявки:</b> {user_type}\n"
                    f"👤 <b>Имя:</b> {name}\n"
                    f"📝 <b>Обращение:</b> {address}\n"
                    f"📞 <b>Телефон:</b> {phone}\n"
                    f"📧 <b>Email:</b> {email}\n"
                    f"🔧 <b>Услуга:</b> {selected_service}\n"
                    f"💬 <b>Сообщение:</b> {user_message_text}\n"
                    f"👤 <b>Username:</b> {username}"
                )
            
            await notify_admin(text)
        
        # Send email notification
        try:
            email_subject = f"Новая заявка - {selected_service}"
            if selected_service == "Таможенное оформление":
                product_name = data.get('product_name', 'Не указан')
                logistics_interest = data.get('logistics_interest', 'Не указано')
                cargo_weight = data.get('cargo_weight', 'Не указан')
                pickup = data.get('pickup_location', 'Не указано')
                delivery = data.get('delivery_location', 'Не указано')
                customs_location = data.get('customs_location', 'Не указано')
                special_conditions = data.get('special_conditions', 'Не указано')
                
                email_body = f"""
                <html>
                <body>
                    <h2>🔔 Новая заявка - Таможенное оформление</h2>
                    <p><strong>Имя:</strong> {name}</p>
                    <p><strong>Обращение:</strong> {address}</p>
                    <p><strong>Телефон:</strong> {phone}</p>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Username:</strong> {username}</p>
                    <hr>
                    <h3>Детали заявки:</h3>
                    <p><strong>Товар:</strong> {product_name}</p>
                    <p><strong>Логистика:</strong> {logistics_interest}</p>
                    <p><strong>Вес:</strong> {cargo_weight}</p>
                    <p><strong>Забрать из:</strong> {pickup}</p>
                    <p><strong>Доставить в:</strong> {delivery}</p>
                    <p><strong>Таможня:</strong> {customs_location}</p>
                    <p><strong>Условия:</strong> {special_conditions}</p>
                </body>
                </html>
                """
            else:
                email_body = f"""
                <html>
                <body>
                    <h2>🔔 Новая заявка</h2>
                    <p><strong>Тип заявки:</strong> {user_type}</p>
                    <p><strong>Имя:</strong> {name}</p>
                    <p><strong>Обращение:</strong> {address}</p>
                    <p><strong>Телефон:</strong> {phone}</p>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Услуга:</strong> {selected_service}</p>
                    <p><strong>Сообщение:</strong> {user_message_text}</p>
                    <p><strong>Username:</strong> {username}</p>
                </body>
                </html>
                """
            
            send_email(email_subject, email_body, ADMIN_EMAIL)
        except Exception as e:
            logging.exception("Failed to send email notification: %s", e)
        
        # Send confirmation to user
        keyboard = buttons.Markup([
            [buttons.MessageButton("🏠 Главное меню")]
        ])
        
        await message.send(
            "✅ <b>Заявка успешно отправлена!</b>\n\n"
            f"📝 <b>Обращение:</b> {address}\n"
            f"📞 <b>Телефон:</b> {phone}\n"
            f"📧 <b>Email:</b> {email}\n"
            f"🔧 <b>Услуга:</b> {selected_service}\n\n"
            "Мы свяжемся с вами в ближайшее время для уточнения деталей!",
            keyboard=keyboard,
            format="html"
        )
        
        import asyncio
        asyncio.create_task(send_to_bitrix24(data))
        
        state.clear()
        return True
        
    elif text == "📞 Позвать менеджера":
        await handle_call_manager_action(message, state)
        return True
        
        await message.send(
            f"📞 <b>Связь с менеджером (обновлено)</b>\n\n"
            f"Пожалуйста, нажмите на кнопку ниже, чтобы перейти в чат с нашим менеджером. "
            f"Мы уже передали ему контекст вашей заявки!",
            keyboard=keyboard,
            format="html"
        )
        
        # Send admin notification so they also know
        admin_text = (
            f"📞 <b>Запрос связи с менеджером (Макс чат)</b>\n\n"
            f"Услуга: {selected_service}\n"
            f"Имя: {data.get('address', 'Не указано')}\n"
            f"Username: {get_sender_display(message)}"
        )
        import asyncio
        asyncio.create_task(notify_admin(admin_text))
        
        state.clear()
        return True
    
    # If not "Отправить заявку" or "Позвать менеджера", treat as email input
    email = text
    data = state.get_data() or {}
    data["email"] = email
    state.change_data(data)
    
    keyboard = buttons.Markup([
        [buttons.MessageButton("✅ Отправить заявку")],
        [buttons.MessageButton("📞 Позвать менеджера")]
    ])
    
    data = state.get_data() or {}
    selected_service = data.get('selected_service', 'Не указана')
    user_message = data.get('user_message', 'Не указано')
    
    await message.send(
        f"✅ <b>Готово к отправке!</b>\n\n"
        f"📝 <b>Обращение:</b> {data.get('address', 'Не указано')}\n"
        f"📞 <b>Телефон:</b> {data.get('phone', 'Не указан')}\n"
        f"📧 <b>Email:</b> {email}\n"
        f"🔧 <b>Услуга:</b> {selected_service}\n"
        f"💬 <b>Сообщение:</b> {user_message}\n\n"
        f"Отправить заявку?",
        keyboard=keyboard,
        format="html"
    )


@bot.on_message()
async def process_service_selection(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_service:
        return False
    service_text = get_message_text(message)
    
    if service_text == "❌ Отмена":
        state.clear()
        await message.send(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            format="html"
        )
        return
    
    if service_text == "Таможенное оформление":
        # Customs clearance - start detailed questionnaire
        data = state.get_data() or {}
        data["selected_service"] = service_text
        state.change_data(data)
        
        keyboard = buttons.Markup([
        ])
        
        await message.send(
            f"✅ Выбрана услуга: <b>{service_text}</b>\n\n"
            f"Напишите наименование товара и его характеристики:",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_product_name)
    
    elif service_text in ["Логистика", "Сертификация", "Сопровождение ВЭД", "Платежный агент", "ВЭД агент"]:
        # Regular service
        data = state.get_data() or {}
        data["selected_service"] = service_text
        state.change_data(data)
        
        keyboard = buttons.Markup([
        ])
        
        await message.send(
            f"✅ Выбрана услуга: <b>{service_text}</b>\n\n"
            f"Опишите подробнее, что именно вас интересует или задайте вопрос:",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_message)
    
    elif service_text == TRADING_HOUSE_SERVICE:
        # Trading house - start detailed questionnaire
        data = state.get_data() or {}
        data["selected_service"] = service_text
        state.change_data(data)
        
        keyboard = buttons.Markup([
            [buttons.MessageButton("Одежда"), buttons.MessageButton("Электроника")],
            [buttons.MessageButton("Мебель"), buttons.MessageButton("Автозапчасти")],
            [buttons.MessageButton("Продукты питания"), buttons.MessageButton("Строительные материалы")]
        ])
        
        await message.send(
            f"✅ Выбрана услуга: <b>{service_text}</b>\n\n"
            f"Какой товар планируете закупить? Выберите из примеров или введите свой вариант:",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_product)
    
    else:
        # It's a question - not a predefined service
        data = state.get_data() or {}
        data["selected_service"] = "Вопрос"
        state.change_data(data)
        
        keyboard = buttons.Markup([
        ])
        
        await message.send(
            f"✅ Ваш вопрос: <b>{service_text}</b>\n\n"
            f"Опишите подробнее, что именно вас интересует или задайте вопрос:",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_message)


@bot.on_message()
async def process_message(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_message:
        return False
    user_message = get_message_text(message)
    
    if user_message == "❌ Отмена":
        state.clear()
        await message.send(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            format="html"
        )
        return
    
    if len(user_message) < 10:
        await message.send("❌ Пожалуйста, опишите подробнее вашу заявку (минимум 10 символов):")
        return
    
    # Save the message and ask for phone
    data = state.get_data() or {}
    data["user_message"] = user_message
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    data = state.get_data() or {}
    selected_service = data.get('selected_service', 'Не указана')
    
    await message.send(
        f"✅ <b>Ваше сообщение:</b>\n{user_message}\n\n"
        f"<b>Услуга:</b> {selected_service}\n\n"
        f"📞 <b>Введите ваш номер телефона для связи:</b>",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_phone)


# Trading house handlers
@bot.on_message()
async def process_product(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_product:
        return False
    product = get_message_text(message)
    
    if product == "❌ Отмена":
        state.clear()
        await message.send(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            format="html"
        )
        return
    
    if len(product) < 2:
        await message.send("❌ Пожалуйста, введите корректное название товара:")
        return
    
    data = state.get_data() or {}
    data["product"] = product
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    await message.send(
        f"✅ Товар: <b>{product}</b>\n\n"
        f"Из какой страны планируете закупать?",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_country)


@bot.on_message()
async def process_country(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_country:
        return False
    country = get_message_text(message)
    
    if country == "❌ Отмена":
        state.clear()
        await message.send(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            format="html"
        )
        return
    
    if len(country) < 2:
        await message.send("❌ Пожалуйста, введите корректное название страны:")
        return
    
    data = state.get_data() or {}
    data["country"] = country
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    await message.send(
        f"✅ Страна-производитель: <b>{country}</b>\n\n"
        f"На какую сумму планируете закупить товар/услугу?",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_amount)


@bot.on_message()
async def process_amount(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_amount:
        return False
    amount = get_message_text(message)
    
    if amount == "❌ Отмена":
        state.clear()
        await message.send(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            format="html"
        )
        return
    
    # Validate amount input
    try:
        # Remove spaces and common currency symbols
        clean_amount = amount.replace(" ", "").replace("$", "").replace("€", "").replace("₽", "").replace("₴", "")
        
        # Check if it's a valid number
        if not clean_amount.replace(".", "").replace(",", "").isdigit():
            await message.send("❌ Пожалуйста, введите корректную сумму (только цифры):")
            return
        
        # Check for reasonable amount (between 100 and 10000000)
        amount_value = float(clean_amount.replace(",", "."))
        if amount_value < 100:
            await message.send("❌ Сумма должна быть не менее 100:")
            return
        if amount_value > 10000000:
            await message.send("❌ Сумма слишком большая, введите корректное значение:")
            return
            
    except ValueError:
        await message.send("❌ Пожалуйста, введите корректную сумму (только цифры):")
        return
    
    data = state.get_data() or {}
    data["amount"] = amount
    state.change_data(data)
    
    keyboard = buttons.Markup([
        [buttons.MessageButton("$"), buttons.MessageButton("€")],
        [buttons.MessageButton("₽"), buttons.MessageButton("₴")]
    ])
    
    await message.send(
        f"✅ Планируемая сумма: <b>{amount}</b>\n\n"
        f"В какой валюте поставщик принимает оплату?",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_currency)


@bot.on_message()
async def process_currency(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_currency:
        return False
    currency = get_message_text(message)
    
    if currency == "❌ Отмена":
        state.clear()
        await message.send(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            format="html"
        )
        return
    
    if currency not in ["$", "€", "₽", "₴"]:
        await message.send("❌ Пожалуйста, выберите валюту из предложенных вариантов:")
        return
    
    data = state.get_data() or {}
    data["currency"] = currency
    state.change_data(data)
    
    keyboard = buttons.Markup([
        [buttons.MessageButton("✅ Отправить заявку")],
        [buttons.MessageButton("📞 Позвать менеджера")],
        [buttons.MessageButton("✏️ Редактировать")],
        [buttons.MessageButton("⬅️ Назад")]
    ])
    
    data = state.get_data() or {}
    product = data.get('product', 'Не указан')
    country = data.get('country', 'Не указана')
    amount = data.get('amount', 'Не указана')
    
    await message.send(
        f"✅ <b>Готово к отправке!</b>\n\n"
        f"📦 <b>Товар:</b> {product}\n"
        f"🌍 <b>Страна:</b> {country}\n"
        f"💰 <b>Сумма:</b> {amount} {currency}\n\n"
        f"Выберите действие:",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_trading_house_message)


@bot.on_message()
async def process_trading_house_final(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_trading_house_message:
        return False
    final_choice = get_message_text(message)
    
    if final_choice == "❌ Отмена":
        state.clear()
        await message.send(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            format="html"
        )
        return
    
    if final_choice == "✅ Отправить заявку":
        # Ask for phone before submission
        keyboard = buttons.Markup([
        ])
        
        data = state.get_data() or {}
        product = data.get('product', 'Не указан')
        country = data.get('country', 'Не указана')
        amount = data.get('amount', 'Не указана')
        currency = data.get('currency', 'Не указана')
        
        await message.send(
            f"✅ <b>Готово к отправке!</b>\n\n"
            f"📦 <b>Товар:</b> {product}\n"
            f"🌍 <b>Страна:</b> {country}\n"
            f"💰 <b>Сумма:</b> {amount} {currency}\n\n"
            f"📞 <b>Введите ваш номер телефона для связи:</b>",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_phone)
    
    elif final_choice == "✏️ Редактировать":
        # Show edit options
        keyboard = buttons.Markup([
                [buttons.MessageButton("📦 Товар")],
                [buttons.MessageButton("🌍 Страна")],
                [buttons.MessageButton("💰 Сумма")],
                [buttons.MessageButton("💱 Валюта")],
                [buttons.MessageButton("🏠 Адрес")],
                [buttons.MessageButton("⬅️ Назад")]
            ],
        )
        
        await message.send(
            "✏️ <b>Что хотите отредактировать?</b>\n\n"
            "Выберите поле для редактирования:",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_edit_field)
        return
    
    elif final_choice == "📞 Позвать менеджера":
        await handle_call_manager_action(message, state, service_name="Торговый дом (закупка товаров)")
        return True
    
    elif final_choice == "⬅️ Назад":
        # Go back to currency selection
        keyboard = buttons.Markup([
                [buttons.MessageButton("$"), buttons.MessageButton("€")],
                [buttons.MessageButton("₽"), buttons.MessageButton("₴")]
            ],
        )
        
        data = state.get_data() or {}
        amount = data.get('amount', 'Не указана')
        
        await message.send(
            f"⬅️ <b>Возвращаемся к выбору валюты</b>\n\n"
            f"Планируемая сумма: <b>{amount}</b>\n\n"
            f"В какой валюте поставщик принимает оплату?",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_currency)
    
    else:
        await message.send("❌ Пожалуйста, выберите один из предложенных вариантов:")


# Handle main menu button
@bot.on_message()
async def handle_main_menu(message):
    text = get_message_text(message)
    if text != "🏠 Главное меню":
        return False
    
    state = get_state(message)
    state.clear()
    
    keyboard = buttons.Markup([
            [buttons.MessageButton("Юр. лица и ИП")],
            [buttons.MessageButton("Физ. лица")]
        ],
    )
    
    await message.send(
        "🏠 <b>Главное меню</b>\n\n"
        "Добрый день! Подскажите, пожалуйста, Вас интересуют услуги как:",
        keyboard=keyboard,
        format="html"
    )

# Handle user type selection
@bot.on_message()
async def handle_user_type(message):
    text = get_message_text(message)
    if text not in ["Юр. лица и ИП", "Физ. лица"]:
        return False
    
    state = get_state(message)
    user_type = text
    
    if user_type == "Физ. лица":
        await message.send(
            "❌ <b>К сожалению, мы не работаем с физическими лицами</b>\n\n"
            "Наши услуги предназначены только для юридических лиц и индивидуальных предпринимателей.\n\n"
            "Если у вас есть ИП или ООО, пожалуйста, выберите соответствующий вариант.",
            format="html"
        )
        return
    
    # For "Юр. лица и ИП"
    data = state.get_data() or {}
    data["user_type"] = user_type
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    await message.send(
        "Как можно обращаться к вам?",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_address)


# Customs clearance handlers
@bot.on_message()
async def process_product_name(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_product_name:
        return False
    product_name = get_message_text(message)
    
    if len(product_name) < 2:
        await message.send("❌ Пожалуйста, введите корректное наименование товара:")
        return
    
    data = state.get_data() or {}
    data["product_name"] = product_name
    state.change_data(data)
    
    keyboard = buttons.Markup([
            [buttons.MessageButton("Да"), buttons.MessageButton("Нет")]
        ],
    )
    
    await message.send(
        f"✅ Товар: <b>{product_name}</b>\n\n"
        f"Мы можем помочь с логистикой Вашего груза. Вам интересно наше предложение по логистике Вашего груза?",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_logistics_interest)


@bot.on_message()
async def process_logistics_interest(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_logistics_interest:
        return False
    interest = get_message_text(message)
    
    if interest not in ["Да", "Нет"]:
        await message.send("❌ Пожалуйста, выберите Да или Нет:")
        return
    
    data = state.get_data() or {}
    data["logistics_interest"] = interest
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    await message.send(
        f"✅ Логистика: <b>{interest}</b>\n\n"
        f"Напишите общий вес товара:",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_cargo_weight)


@bot.on_message()
async def process_cargo_weight(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_cargo_weight:
        return False
    weight = get_message_text(message)
    
    if len(weight) < 1:
        await message.send("❌ Пожалуйста, введите вес товара:")
        return
    
    data = state.get_data() or {}
    data["cargo_weight"] = weight
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    await message.send(
        f"✅ Вес товара: <b>{weight}</b>\n\n"
        f"Где необходимо забрать груз?",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_pickup_location)


@bot.on_message()
async def process_pickup_location(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_pickup_location:
        return False
    pickup = get_message_text(message)
    
    if len(pickup) < 2:
        await message.send("❌ Пожалуйста, введите место забора груза:")
        return
    
    data = state.get_data() or {}
    data["pickup_location"] = pickup
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    await message.send(
        f"✅ Место забора: <b>{pickup}</b>\n\n"
        f"Куда нужно доставить груз?",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_delivery_location)


@bot.on_message()
async def process_delivery_location(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_delivery_location:
        return False
    delivery = get_message_text(message)
    
    if len(delivery) < 2:
        await message.send("❌ Пожалуйста, введите место доставки:")
        return
    
    data = state.get_data() or {}
    data["delivery_location"] = delivery
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    await message.send(
        f"✅ Место доставки: <b>{delivery}</b>\n\n"
        f"Место проведения таможенного оформления, если знаете:",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_customs_location)


@bot.on_message()
async def process_customs_location(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_customs_location:
        return False
    customs_location = get_message_text(message)
    
    data = state.get_data() or {}
    data["customs_location"] = customs_location
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    await message.send(
        f"✅ Место таможенного оформления: <b>{customs_location}</b>\n\n"
        f"Есть ли какие-либо особые условия? (например: нельзя штабелировать, опасный груз, подлежит контролю РСХН)",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_special_conditions)


@bot.on_message()
async def process_special_conditions(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_special_conditions:
        return False
    special_conditions = get_message_text(message)
    
    data = state.get_data() or {}
    data["special_conditions"] = special_conditions
    state.change_data(data)
    
    # Get all collected data
    data = state.get_data() or {}
    product_name = data.get('product_name', 'Не указан')
    pickup = data.get('pickup_location', 'Не указано')
    delivery = data.get('delivery_location', 'Не указано')
    customs_location = data.get('customs_location', 'Не указано')
    
    keyboard = buttons.Markup([
        [buttons.MessageButton("✅ Отправить заявку")],
        [buttons.MessageButton("📞 Позвать менеджера")],
        [buttons.MessageButton("✏️ Редактировать")],
        [buttons.MessageButton("⬅️ Назад")]
    ])
    
    await message.send(
        f"<b>Давайте подытожим.</b>\n\n"
        f"📦 <b>Товар:</b> {product_name}\n"
        f"📍 <b>Забрать товар нужно из:</b> {pickup}\n"
        f"🎯 <b>Доставить в:</b> {delivery}\n"
        f"🏛️ <b>Место таможенного оформления:</b> {customs_location}\n"
        f"⚠️ <b>Особые условия:</b> {special_conditions}\n\n"
        f"Отправляю заявку или позвать менеджера?",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_customs_final)


@bot.on_message()
async def process_customs_final(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_customs_final:
        return False
    final_choice = get_message_text(message)
    
    if final_choice == "✅ Отправить заявку":
        # Ask for phone before submission
        keyboard = buttons.Markup([
        ])
        
        data = state.get_data() or {}
        product_name = data.get('product_name', 'Не указан')
        logistics_interest = data.get('logistics_interest', 'Не указано')
        cargo_weight = data.get('cargo_weight', 'Не указан')
        pickup = data.get('pickup_location', 'Не указано')
        delivery = data.get('delivery_location', 'Не указано')
        customs_location = data.get('customs_location', 'Не указано')
        special_conditions = data.get('special_conditions', 'Не указано')
        
        await message.send(
            f"✅ <b>Готово к отправке!</b>\n\n"
            f"📦 <b>Товар:</b> {product_name}\n"
            f"🚛 <b>Логистика:</b> {logistics_interest}\n"
            f"⚖️ <b>Вес:</b> {cargo_weight}\n"
            f"📍 <b>Забрать из:</b> {pickup}\n"
            f"🎯 <b>Доставить в:</b> {delivery}\n"
            f"🏛️ <b>Таможня:</b> {customs_location}\n"
            f"⚠️ <b>Условия:</b> {special_conditions}\n\n"
            f"📞 <b>Введите ваш номер телефона для связи:</b>",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_phone)
    
    elif final_choice == "⬅️ Назад":
        # Go back to special conditions input
        keyboard = buttons.Markup([
        ])
        await message.send(
            "⬅️ <b>Возвращаемся к указанию особых условий</b>\n\n"
            "Опишите, пожалуйста, особые условия (например: нельзя штабелировать, опасный груз, подлежит контролю РСХН)",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_special_conditions)
    
    elif final_choice == "✏️ Редактировать":
        # Show edit options for customs clearance
        keyboard = buttons.Markup([
                [buttons.MessageButton("📦 Название товара")],
                [buttons.MessageButton("🚛 Логистика")],
                [buttons.MessageButton("⚖️ Вес груза")],
                [buttons.MessageButton("📍 Откуда забрать")],
                [buttons.MessageButton("📍 Куда доставить")],
                [buttons.MessageButton("🏛️ Таможня")],
                [buttons.MessageButton("💬 Особые условия")],
                [buttons.MessageButton("🏠 Адрес")],
                [buttons.MessageButton("⬅️ Назад")]
            ],
        )
        
        await message.send(
            "✏️ <b>Что хотите отредактировать?</b>\n\n"
            "Выберите поле для редактирования:",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_edit_field)
        return
    
    elif final_choice == "📞 Позвать менеджера":
        await handle_call_manager_action(message, state, service_name="Таможенное оформление")
        return True


# Manager transfer handlers
@bot.on_message()
async def process_manager_phone(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_manager_phone:
        return False
    """Handle phone number input for manager transfer"""
    phone = get_message_text(message)
    
    # Validate phone input
    if len(phone) < 10:
        await message.send("❌ Пожалуйста, введите корректный номер телефона (минимум 10 символов):")
        return
    
    data = state.get_data() or {}
    data["manager_phone"] = phone
    state.change_data(data)
    
    keyboard = buttons.Markup([])
    
    await message.send(
        f"✅ <b>Номер телефона:</b> {phone}\n\n"
        f"📧 <b>Введите ваш email для связи с менеджером:</b>",
        keyboard=keyboard,
        format="html"
    )
    state.change_state(ApplicationStates.waiting_for_manager_contact)


@bot.on_message()
async def process_manager_contact(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_manager_contact:
        return False
    """Handle contact information and send manager notification"""
    contact = get_message_text(message)
    
    # Accept any input as contact (no validation)
    data = state.get_data() or {}
    data["manager_contact"] = contact
    state.change_data(data)
    
    # Get all data
    data = state.get_data() or {}
    address = data.get('address', 'Не указано')
    username = get_sender_display(message)
    manager_phone = data.get('manager_phone', 'Не указан')
    selected_service = data.get('selected_service', 'Не указана')
    
    # Show processing message
    await message.send("⏳ Переводим на менеджера...", format="html")
    
    # Determine service type and prepare notification
    if selected_service == "Таможенное оформление":
        product_name = data.get('product_name', 'Не указан')
        logistics_interest = data.get('logistics_interest', 'Не указано')
        cargo_weight = data.get('cargo_weight', 'Не указан')
        pickup = data.get('pickup_location', 'Не указано')
        delivery = data.get('delivery_location', 'Не указано')
        customs_location = data.get('customs_location', 'Не указано')
        special_conditions = data.get('special_conditions', 'Не указано')
        
        # Notify admin about manager call
        if ADMIN_CHAT_ID and ADMIN_CHAT_ID != 0:
            text = (
                f"📞 <b>ПОЗВАТЬ МЕНЕДЖЕРА - Таможенное оформление</b>\n\n"
                f"👤 <b>Обращение:</b> {address}\n"
                f"📞 <b>Телефон:</b> {manager_phone}\n"
                f"📧 <b>Email:</b> {contact}\n"
                f"👤 <b>Username:</b> {username}\n\n"
                f"📦 <b>Товар:</b> {product_name}\n"
                f"🚛 <b>Логистика:</b> {logistics_interest}\n"
                f"⚖️ <b>Вес:</b> {cargo_weight}\n"
                f"📍 <b>Забрать из:</b> {pickup}\n"
                f"🎯 <b>Доставить в:</b> {delivery}\n"
                f"🏛️ <b>Таможня:</b> {customs_location}\n"
                f"⚠️ <b>Условия:</b> {special_conditions}\n\n"
                f"🔔 <b>КЛИЕНТ ПРОСИТ СВЯЗАТЬСЯ С МЕНЕДЖЕРОМ!</b>"
            )
            await notify_admin(text)
        
        # Send email notification
        try:
            email_subject = "📞 Позвать менеджера - Таможенное оформление"
            email_body = f"""
            <html>
            <body>
                <h2>📞 ПОЗВАТЬ МЕНЕДЖЕРА - Таможенное оформление</h2>
                <p><strong>Обращение:</strong> {address}</p>
                <p><strong>Телефон:</strong> {manager_phone}</p>
                <p><strong>Email:</strong> {contact}</p>
                <p><strong>Username:</strong> {username}</p>
                <hr>
                <h3>Детали заявки:</h3>
                <p><strong>Товар:</strong> {product_name}</p>
                <p><strong>Логистика:</strong> {logistics_interest}</p>
                <p><strong>Вес:</strong> {cargo_weight}</p>
                <p><strong>Забрать из:</strong> {pickup}</p>
                <p><strong>Доставить в:</strong> {delivery}</p>
                <p><strong>Таможня:</strong> {customs_location}</p>
                <p><strong>Условия:</strong> {special_conditions}</p>
                <hr>
                <p><strong>🔔 КЛИЕНТ ПРОСИТ СВЯЗАТЬСЯ С МЕНЕДЖЕРОМ!</strong></p>
            </body>
            </html>
            """
            send_email(email_subject, email_body, ADMIN_EMAIL)
        except Exception as e:
            logging.exception("Failed to send manager call email: %s", e)
    
    else:
        # Trading house or other services
        data = state.get_data() or {}
        user_message_text = data.get('user_message')
        
        if user_message_text:
            # Regular service
            if ADMIN_CHAT_ID and ADMIN_CHAT_ID != 0:
                text = (
                    f"📞 <b>ПОЗВАТЬ МЕНЕДЖЕРА - {selected_service}</b>\n\n"
                    f"👤 <b>Обращение:</b> {address}\n"
                    f"📞 <b>Телефон:</b> {manager_phone}\n"
                    f"📧 <b>Email:</b> {contact}\n"
                    f"👤 <b>Username:</b> {username}\n\n"
                    f"💬 <b>Запрос:</b> {user_message_text}\n\n"
                    f"🔔 <b>КЛИЕНТ ПРОСИТ СВЯЗАТЬСЯ С МЕНЕДЖЕРОМ!</b>"
                )
                await notify_admin(text)
            
            try:
                email_subject = f"📞 Позвать менеджера - {selected_service}"
                email_body = f"""
                <html>
                <body>
                    <h2>📞 ПОЗВАТЬ МЕНЕДЖЕРА - {selected_service}</h2>
                    <p><strong>Обращение:</strong> {address}</p>
                    <p><strong>Телефон:</strong> {manager_phone}</p>
                    <p><strong>Email:</strong> {contact}</p>
                    <p><strong>Username:</strong> {username}</p>
                    <hr>
                    <h3>Детали заявки:</h3>
                    <p><strong>Запрос:</strong> {user_message_text}</p>
                    <hr>
                    <p><strong>🔔 КЛИЕНТ ПРОСИТ СВЯЗАТЬСЯ С МЕНЕДЖЕРОМ!</strong></p>
                </body>
                </html>
                """
                send_email(email_subject, email_body, ADMIN_EMAIL)
            except Exception as e:
                logging.exception("Failed to send manager call email: %s", e)
        else:
            # Trading house
            product = data.get('product', 'Не указан')
            country = data.get('country', 'Не указана')
            amount = data.get('amount', 'Не указана')
            currency = data.get('currency', 'Не указана')
            
            # Notify admin about manager call
            if ADMIN_CHAT_ID and ADMIN_CHAT_ID != 0:
                text = (
                    f"📞 <b>ПОЗВАТЬ МЕНЕДЖЕРА - {selected_service}</b>\n\n"
                    f"👤 <b>Обращение:</b> {address}\n"
                    f"📞 <b>Телефон:</b> {manager_phone}\n"
                    f"📧 <b>Email:</b> {contact}\n"
                    f"👤 <b>Username:</b> {username}\n\n"
                    f"📦 <b>Товар:</b> {product}\n"
                    f"🌍 <b>Страна:</b> {country}\n"
                    f"💰 <b>Сумма:</b> {amount} {currency}\n\n"
                    f"🔔 <b>КЛИЕНТ ПРОСИТ СВЯЗАТЬСЯ С МЕНЕДЖЕРОМ!</b>"
                )
                await notify_admin(text)
            
            # Send email notification
            try:
                email_subject = f"📞 Позвать менеджера - {selected_service}"
                email_body = f"""
                <html>
                <body>
                    <h2>📞 ПОЗВАТЬ МЕНЕДЖЕРА - {selected_service}</h2>
                    <p><strong>Обращение:</strong> {address}</p>
                    <p><strong>Телефон:</strong> {manager_phone}</p>
                    <p><strong>Email:</strong> {contact}</p>
                    <p><strong>Username:</strong> {username}</p>
                    <hr>
                    <h3>Детали заявки:</h3>
                    <p><strong>Товар:</strong> {product}</p>
                    <p><strong>Страна:</strong> {country}</p>
                    <p><strong>Сумма:</strong> {amount} {currency}</p>
                    <hr>
                    <p><strong>🔔 КЛИЕНТ ПРОСИТ СВЯЗАТЬСЯ С МЕНЕДЖЕРОМ!</strong></p>
                </body>
                </html>
                """
                send_email(email_subject, email_body, ADMIN_EMAIL)
            except Exception as e:
                logging.exception("Failed to send manager call email: %s", e)
    
    keyboard = buttons.Markup([
            [buttons.MessageButton("🏠 Главное меню")]
        ],
    )
    
    await message.send(
        "📞 <b>Менеджер будет с вами связываться!</b>\n\n"
        f"📞 <b>Ваш телефон:</b> {manager_phone}\n"
        f"📧 <b>Ваш email:</b> {contact}\n\n"
        "Наш специалист свяжется с вами в ближайшее время для обсуждения деталей.",
        keyboard=keyboard,
        format="html"
    )
    state.clear()


# Diagnostic commands
@bot.on_message(detect_commands=True)
async def cmd_id(message):
    text = get_message_text(message)
    if not text.startswith("/id"):
        return False
    chat_info = f"""
🆔 <b>Chat Information:</b>

📱 <b>Chat ID:</b> <code>{get_chat_id(message)}</code>
👤 <b>User ID:</b> <code>{get_sender_id(message) or 'N/A'}</code>
📝 <b>Chat Type:</b> {message.recipient.chat_type if message.recipient else 'N/A'}
👤 <b>Username:</b> {get_sender_display(message)}

💡 <b>Для настройки админа:</b>
Скопируйте Chat ID и установите в docker-compose.yml:
<code>ADMIN_MAX_CHAT_ID={get_chat_id(message)}</code>
"""
    await message.send(chat_info, format="html")

@bot.on_message(detect_commands=True)
async def cmd_ping(message):
    text = get_message_text(message)
    if not text.startswith("/ping"):
        return False
    await message.send("pong")

@bot.on_message(detect_commands=True)
async def cmd_test_email(message):
    text = get_message_text(message)
    if not text.startswith("/test_email"):
        return False
    """Test email sending functionality"""
    try:
        await message.send("📧 Тестирую отправку email...")
        
        test_subject = "🧪 Тест отправки email"
        test_body = f"""
        <html>
        <body>
            <h2>🧪 Тест отправки email</h2>
            <p><strong>Время:</strong> {format_message_timestamp(message)}</p>
            <p><strong>Chat ID:</strong> {get_chat_id(message)}</p>
            <p><strong>Username:</strong> {get_sender_display(message)}</p>
            <p><strong>SMTP Host:</strong> {SMTP_HOST}</p>
            <p><strong>SMTP Port:</strong> {SMTP_PORT}</p>
            <p><strong>From:</strong> {SMTP_FROM}</p>
            <p><strong>To:</strong> {ADMIN_EMAIL}</p>
            <hr>
            <p>Если вы получили это письмо, значит SMTP работает корректно!</p>
        </body>
        </html>
        """
        
        result = send_email(test_subject, test_body)
        
        if result:
            await message.send("✅ Email отправлен успешно! Проверьте почту.")
        else:
            await message.send("❌ Ошибка отправки email. Проверьте логи.")
            
    except Exception as e:
        await message.send(f"❌ Ошибка тестирования email: {e}")
        logging.exception("Test email failed: %s", e)

@bot.on_message(detect_commands=True)
async def cmd_smtp_info(message):
    text = get_message_text(message)
    if not text.startswith("/smtp_info"):
        return False
    """Show current SMTP configuration"""
    info = f"""
📧 <b>SMTP Configuration:</b>

🏠 <b>Primary Host:</b> {SMTP_HOST}:{SMTP_PORT}
👤 <b>User:</b> {SMTP_FROM}
📬 <b>Admin Email:</b> {ADMIN_EMAIL}

🔄 <b>Fallback Servers:</b>
"""
    for i, (host, port, method) in enumerate(SMTP_ALTERNATIVES, 1):
        info += f"{i}. {host}:{port} ({method})\n"
    
    await message.send(info, format="html")

@bot.on_message(detect_commands=True)
async def cmd_network_test(message):
    text = get_message_text(message)
    if not text.startswith("/network_test"):
        return False
    """Test network connectivity to SMTP servers"""
    import socket
    
    results = "🌐 <b>Network Test Results:</b>\n\n"
    
    for host, port, method in SMTP_ALTERNATIVES[:5]:  # Test first 5 servers
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                results += f"✅ {host}:{port} - <b>Reachable</b>\n"
            else:
                results += f"❌ {host}:{port} - <b>Unreachable</b>\n"
        except Exception as e:
            results += f"❌ {host}:{port} - <b>Error: {str(e)[:50]}</b>\n"
    
    await message.send(results, format="html")

@bot.on_message(detect_commands=True)
async def cmd_gmail_test(message):
    text = get_message_text(message)
    if not text.startswith("/gmail_test"):
        return False
    """Test Gmail SMTP connection specifically"""
    try:
        await message.send("🔐 Тестирую подключение к Gmail SMTP...")
        
        import smtplib
        import ssl
        
        # Prepare password (sanitize spaces)
        app_password = SMTP_PASSWORD
        
        # Test STARTTLS (port 587)
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
            server.ehlo()
            context = ssl.create_default_context()
            server.starttls(context=context)
            server.ehlo()
            if SMTP_USER and app_password:
                server.login(SMTP_USER, app_password)
            server.quit()
            await message.send("✅ Gmail STARTTLS (587) - подключение успешно!")
        except Exception as e:
            await message.send(f"❌ Gmail STARTTLS (587) failed: {e}")
        
        # Test SSL (port 465)
        try:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15, context=context)
            if SMTP_USER and app_password:
                server.login(SMTP_USER, app_password)
            server.quit()
            await message.send("✅ Gmail SSL (465) - подключение успешно!")
        except Exception as e:
            await message.send(f"❌ Gmail SSL (465) failed: {e}")
            
    except Exception as e:
        await message.send(f"❌ Ошибка тестирования Gmail: {e}")

@bot.on_message(detect_commands=True)
async def cmd_api_test(message):
    text = get_message_text(message)
    if not text.startswith("/api_test"):
        return False
    """Test HTTP API email service"""
    try:
        await message.send("🌐 Тестирую HTTP API email сервис...")
        
        import requests
        
        # Test API health
        try:
            await message.send("✅ Проверяем Gmail соединение...")
        except Exception as e:
            await message.send(f"❌ Ошибка проверки: {e}")
            return
        
        # Test email sending
        test_subject = "🧪 Тест Gmail - KVT Bot"
        test_body = f"""
        <h2>Тестовое письмо через Gmail</h2>
        <p><strong>Время:</strong> {format_message_timestamp(message)}</p>
        <p><strong>Chat ID:</strong> {get_chat_id(message)}</p>
        <p><strong>Метод:</strong> Gmail App Password</p>
        <hr>
        <p>✅ Если вы получили это письмо, значит Gmail работает!</p>
        """
        
        try:
            result = send_email(test_subject, test_body, ADMIN_EMAIL)
            if result:
                await message.send("✅ Email отправлен через Gmail! Проверьте почту.")
            else:
                await message.send("❌ Ошибка отправки через Gmail. Проверьте логи.")
        except Exception as e:
            await message.send(f"❌ Ошибка отправки через Gmail: {e}")
            
    except Exception as e:
        await message.send(f"❌ Ошибка тестирования HTTP API: {e}")
        logging.exception("HTTP API test failed: %s", e)

@bot.on_message(detect_commands=True)
async def cmd_email_test_all(message):
    text = get_message_text(message)
    if not text.startswith("/email_test_all"):
        return False
    """Test all email methods comprehensively"""
    try:
        await message.send("🧪 Тестирую ВСЕ методы отправки email...")
        
        test_subject = "🧪 Комплексный тест email - KVT Bot"
        test_body = f"""
        <h2>📧 Комплексный тест email</h2>
        <p><strong>Время:</strong> {format_message_timestamp(message)}</p>
        <p><strong>Chat ID:</strong> {get_chat_id(message)}</p>
        <p><strong>Тест:</strong> Все методы отправки</p>
        <hr>
        <p>✅ Если вы получили это письмо, значит email работает!</p>
        <p>🔧 Проверьте папку "Спам" если письмо не пришло.</p>
        """
        
        # Test all methods
        methods_tested = []
        
        # Method 1: Gmail App Password
        try:
            result = send_email(f"{test_subject} (Gmail)", test_body, ADMIN_EMAIL)
            if result:
                methods_tested.append("✅ Gmail App Password: Success")
            else:
                methods_tested.append("❌ Gmail App Password: Failed")
        except Exception as e:
            methods_tested.append(f"❌ Gmail App Password: {str(e)[:50]}")
        
        # Method 2: Resend HTTPS fallback (if key configured)
        try:
            import os, requests
            resend_key = settings.resend_api_key
            if resend_key:
                headers = {"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"}
                payload = {"from": f"KVT Bot <{SMTP_FROM}>", "to": [ADMIN_EMAIL], "subject": f"{test_subject} (Resend)", "html": test_body}
                resp = requests.post("https://api.resend.com/emails", headers=headers, json=payload, timeout=10)
                if resp.status_code in (200,201):
                    methods_tested.append("✅ Resend HTTPS: Success")
                else:
                    methods_tested.append(f"❌ Resend HTTPS: {resp.status_code}")
            else:
                methods_tested.append("ℹ️ Resend HTTPS: skipped (no API key)")
        except Exception as e:
            methods_tested.append(f"❌ Resend HTTPS: {str(e)[:50]}")
        
        # Method 3: MailHog fallback
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = SMTP_FROM
            msg['To'] = ADMIN_EMAIL
            msg['Subject'] = f"{test_subject} (MailHog)"
            msg.attach(MIMEText(test_body, 'html', 'utf-8'))
            
            server = smtplib.SMTP("mailhog", 1025, timeout=5)
            server.sendmail(SMTP_FROM, ADMIN_EMAIL, msg.as_string())
            server.quit()
            methods_tested.append("✅ MailHog: Success")
        except Exception as e:
            methods_tested.append(f"❌ MailHog: {str(e)[:50]}")
        
        # Show results
        results_text = "📊 <b>Результаты тестирования email:</b>\n\n" + "\n".join(methods_tested)
        
        await message.send(results_text, format="html")
        
        # Additional info
        await message.send(
            "💡 <b>Проверьте:</b>\n"
            "• Основную папку почты\n"
            "• Папку 'Спам'\n"
            "• MailHog: http://localhost:8025",
            format="html"
        )
        
    except Exception as e:
        await message.send(f"❌ Ошибка комплексного тестирования: {e}")
        logging.exception("Comprehensive email test failed: %s", e)

@bot.on_message(detect_commands=True)
async def cmd_email_status(message):
    text = get_message_text(message)
    if not text.startswith("/email_status"):
        return False
    """Show email configuration status"""
    status = f"""
📧 <b>Email Status:</b>

🔧 <b>Email Enabled:</b> {'✅ Yes' if EMAIL_ENABLED else '❌ No'}
🏠 <b>SMTP Host:</b> {SMTP_HOST}:{SMTP_PORT}
👤 <b>User:</b> {SMTP_FROM}
📬 <b>Admin Email:</b> {ADMIN_EMAIL}

💡 <b>Commands:</b>
• /test_email - Test email sending (all methods)
• /email_test_all - Comprehensive email testing
• /api_test - Test Gmail email service
• /gmail_test - Test Gmail SMTP connection
• /network_test - Test network connectivity
• /test_admin - Test admin notifications
"""
    await message.send(status, format="html")

@bot.on_message(detect_commands=True)
async def cmd_test_admin(message):
    text = get_message_text(message)
    if not text.startswith("/test_admin"):
        return False
    """Test admin notification"""
    try:
        await message.send("📤 Тестирую отправку уведомления админу...")
        
        test_text = f"""
🧪 <b>Тест уведомления админу</b>

📱 <b>От:</b> {get_sender_display(message)}
🆔 <b>Chat ID:</b> {get_chat_id(message)}
⏰ <b>Время:</b> {format_message_timestamp(message)}

✅ Если вы получили это сообщение, значит уведомления админу работают!
"""
        
        result = await notify_admin(test_text)
        
        if result:
            await message.send("✅ Уведомление админу отправлено успешно!")
        else:
            await message.send("❌ Ошибка отправки уведомления админу. Проверьте логи.")
            
    except Exception as e:
        await message.send(f"❌ Ошибка тестирования: {e}")
        logging.exception("Test admin notification failed: %s", e)

# Edit handlers
@bot.on_message()
async def process_edit_field_selection(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_edit_field:
        return False
    """Handle field selection for editing"""
    field_choice = get_message_text(message)
    
    if field_choice == "⬅️ Назад":
        # Return to previous state based on current service
        data = state.get_data() or {}
        service = data.get('selected_service', '')
        
        if is_trading_house_service(service):
            # Return to trading house final step
            product = data.get('product', 'Не указан')
            country = data.get('country', 'Не указана')
            amount = data.get('amount', 'Не указана')
            currency = data.get('currency', 'Не указана')
            
            keyboard = buttons.Markup([
                    [buttons.MessageButton("✅ Отправить заявку")],
                    [buttons.MessageButton("📞 Позвать менеджера")],
                    [buttons.MessageButton("✏️ Редактировать")],
                    [buttons.MessageButton("⬅️ Назад")]
                ]
            )
            
            await message.send(
                f"<b>Давайте подытожим.</b>\n\n"
                f"📦 <b>Товар:</b> {product}\n"
                f"🌍 <b>Страна:</b> {country}\n"
                f"💰 <b>Сумма:</b> {amount}\n"
                f"💱 <b>Валюта:</b> {currency}\n\n"
                f"Всё верно?",
                keyboard=keyboard,
                format="html"
            )
            state.change_state(ApplicationStates.waiting_for_trading_house_message)
        else:
            # Return to customs clearance final step
            product_name = data.get('product_name', 'Не указан')
            logistics_interest = data.get('logistics_interest', 'Не указано')
            cargo_weight = data.get('cargo_weight', 'Не указан')
            pickup = data.get('pickup_location', 'Не указано')
            delivery = data.get('delivery_location', 'Не указано')
            customs_location = data.get('customs_location', 'Не указано')
            special_conditions = data.get('special_conditions', 'Не указано')
            
            keyboard = buttons.Markup([
                    [buttons.MessageButton("✅ Отправить заявку")],
                    [buttons.MessageButton("📞 Позвать менеджера")],
                    [buttons.MessageButton("✏️ Редактировать")],
                    [buttons.MessageButton("⬅️ Назад")]
                ]
            )
            
            await message.send(
                f"<b>Давайте подытожим.</b>\n\n"
                f"📦 <b>Товар:</b> {product_name}\n"
                f"📍 <b>Забрать товар нужно из:</b> {pickup}\n"
                f"📍 <b>Доставить товар нужно в:</b> {delivery}\n"
                f"🏛️ <b>Таможенное оформление в:</b> {customs_location}\n"
                f"⚖️ <b>Вес груза:</b> {cargo_weight}\n"
                f"🚛 <b>Логистика:</b> {logistics_interest}\n"
                f"💬 <b>Особые условия:</b> {special_conditions}\n\n"
                f"Всё верно?",
                keyboard=keyboard,
                format="html"
            )
            state.change_state(ApplicationStates.waiting_for_customs_final)
        return
    
    elif field_choice == "📞 Позвать менеджера":
        await handle_call_manager_action(message, state)
        return
    
    # Map field names to data keys and next states
    field_mapping = {
        "📦 Товар": ("product", "Введите название товара:", ApplicationStates.waiting_for_product),
        "🌍 Страна": ("country", "Введите страну:", ApplicationStates.waiting_for_country),
        "💰 Сумма": ("amount", "Введите сумму:", ApplicationStates.waiting_for_amount),
        "💱 Валюта": ("currency", "Введите валюту:", ApplicationStates.waiting_for_currency),
        "🏠 Адрес": ("address", "Введите ваш адрес:", ApplicationStates.waiting_for_address),
        "📦 Название товара": ("product_name", "Введите название товара:", ApplicationStates.waiting_for_product_name),
        "🚛 Логистика": ("logistics_interest", "Нужна ли логистика?", ApplicationStates.waiting_for_logistics_interest),
        "⚖️ Вес груза": ("cargo_weight", "Введите вес груза:", ApplicationStates.waiting_for_cargo_weight),
        "📍 Откуда забрать": ("pickup_location", "Откуда забрать товар?", ApplicationStates.waiting_for_pickup_location),
        "📍 Куда доставить": ("delivery_location", "Куда доставить товар?", ApplicationStates.waiting_for_delivery_location),
        "🏛️ Таможня": ("customs_location", "Где таможенное оформление?", ApplicationStates.waiting_for_customs_location),
        "💬 Особые условия": ("special_conditions", "Есть ли особые условия?", ApplicationStates.waiting_for_special_conditions)
    }
    
    if field_choice in field_mapping:
        data_key, prompt, next_state = field_mapping[field_choice]
        data = state.get_data() or {}
        data["editing_field"] = data_key
        state.change_data(data)
        
        keyboard = buttons.Markup([
                [buttons.MessageButton("❌ Отмена")]
            ],
        )
        
        await message.send(
            f"✏️ <b>Редактирование:</b> {field_choice}\n\n"
            f"{prompt}",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_edit_text)
    else:
        await message.send("❌ Неизвестное поле. Выберите из предложенных вариантов.")

@bot.on_message()
async def process_edit_text(message):
    state = get_state(message)
    current_state = state.get_state()
    
    if current_state != ApplicationStates.waiting_for_edit_text:
        return False
    """Handle text input for editing"""
    if get_message_text(message) == "❌ Отмена":
        # Return to field selection
        data = state.get_data() or {}
        service = data.get('selected_service', '')
        
        if is_trading_house_service(service):
            keyboard = buttons.Markup([
                    [buttons.MessageButton("📦 Товар")],
                    [buttons.MessageButton("🌍 Страна")],
                    [buttons.MessageButton("💰 Сумма")],
                    [buttons.MessageButton("💱 Валюта")],
                    [buttons.MessageButton("🏠 Адрес")],
                    [buttons.MessageButton("⬅️ Назад")]
                ]
            )
        else:
            keyboard = buttons.Markup([
                    [buttons.MessageButton("📦 Название товара")],
                    [buttons.MessageButton("🚛 Логистика")],
                    [buttons.MessageButton("⚖️ Вес груза")],
                    [buttons.MessageButton("📍 Откуда забрать")],
                    [buttons.MessageButton("📍 Куда доставить")],
                    [buttons.MessageButton("🏛️ Таможня")],
                    [buttons.MessageButton("💬 Особые условия")],
                    [buttons.MessageButton("🏠 Адрес")],
                    [buttons.MessageButton("⬅️ Назад")]
                ]
            )
        
        await message.send(
            "✏️ <b>Что хотите отредактировать?</b>\n\n"
            "Выберите поле для редактирования:",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_edit_field)
        return
    
    if get_message_text(message) == "📞 Позвать менеджера":
        await handle_call_manager_action(message, state)
        return
    data = state.get_data() or {}
    editing_field = data.get('editing_field')
    new_value = get_message_text(message)
    
    if not editing_field:
        await message.send("❌ Ошибка: поле для редактирования не найдено.")
        return
    
    # Update the field
    data = state.get_data() or {}
    data[editing_field] = new_value
    state.change_data(data)
    
    # Show updated summary and return to final step
    service = data.get('selected_service', '')
    
    if is_trading_house_service(service):
        # Show updated trading house summary
        product = data.get('product', 'Не указан')
        country = data.get('country', 'Не указана')
        amount = data.get('amount', 'Не указана')
        currency = data.get('currency', 'Не указана')
        
        keyboard = buttons.Markup([
                [buttons.MessageButton("✅ Отправить заявку")],
                [buttons.MessageButton("📞 Позвать менеджера")],
                [buttons.MessageButton("✏️ Редактировать")],
                [buttons.MessageButton("⬅️ Назад")]
            ],
        )
        
        await message.send(
            f"✅ <b>Поле обновлено!</b>\n\n"
            f"<b>Давайте подытожим.</b>\n\n"
            f"📦 <b>Товар:</b> {product}\n"
            f"🌍 <b>Страна:</b> {country}\n"
            f"💰 <b>Сумма:</b> {amount}\n"
            f"💱 <b>Валюта:</b> {currency}\n\n"
            f"Всё верно?",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_trading_house_message)
    else:
        # Show updated customs clearance summary
        product_name = data.get('product_name', 'Не указан')
        logistics_interest = data.get('logistics_interest', 'Не указано')
        cargo_weight = data.get('cargo_weight', 'Не указан')
        pickup = data.get('pickup_location', 'Не указано')
        delivery = data.get('delivery_location', 'Не указано')
        customs_location = data.get('customs_location', 'Не указано')
        special_conditions = data.get('special_conditions', 'Не указано')
        
        keyboard = buttons.Markup([
                [buttons.MessageButton("✅ Отправить заявку")],
                [buttons.MessageButton("📞 Позвать менеджера")],
                [buttons.MessageButton("✏️ Редактировать")],
                [buttons.MessageButton("⬅️ Назад")]
            ],
        )
        
        await message.send(
            f"✅ <b>Поле обновлено!</b>\n\n"
            f"<b>Давайте подытожим.</b>\n\n"
            f"📦 <b>Товар:</b> {product_name}\n"
            f"📍 <b>Забрать товар нужно из:</b> {pickup}\n"
            f"📍 <b>Доставить товар нужно в:</b> {delivery}\n"
            f"🏛️ <b>Таможенное оформление в:</b> {customs_location}\n"
            f"⚖️ <b>Вес груза:</b> {cargo_weight}\n"
            f"🚛 <b>Логистика:</b> {logistics_interest}\n"
            f"💬 <b>Особые условия:</b> {special_conditions}\n\n"
            f"Всё верно?",
            keyboard=keyboard,
            format="html"
        )
        state.change_state(ApplicationStates.waiting_for_customs_final)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logging.info("=" * 60)
    logging.info("🚀 KVT BOT STARTING UP (Max Messenger)")
    logging.info("=" * 60)
    
    # Log configuration
    logging.info("⚙️ Bot Configuration:")
    logging.info(f"   🤖 Bot Token: {BOT_TOKEN[:10]}..." if BOT_TOKEN else "   ❌ Bot Token: NOT SET")
    logging.info(f"   👤 Admin Chat ID: {ADMIN_CHAT_ID}")
    logging.info(f"   📧 Email Enabled: {EMAIL_ENABLED}")
    logging.info(f"   📤 SMTP User: {SMTP_USER or 'not set'}")
    logging.info(f"   🪪 SMTP From: {SMTP_FROM}")
    logging.info(f"   📥 Admin Email: {ADMIN_EMAIL}")
    logging.info(f"   🌐 SMTP Host: {SMTP_HOST}:{SMTP_PORT}")

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")

    original_handle_update = bot.handle_update

    async def traced_handle_update(update: dict):
        update_type = update.get("update_type")
        if update_type == "message_created":
            message = update.get("message", {})
            body = message.get("body", {})
            recipient = message.get("recipient", {})
            sender = message.get("sender", {})
            logging.info(
                "📩 update=message_created chat_id=%s user_id=%s text=%r",
                recipient.get("chat_id"),
                sender.get("user_id"),
                body.get("text"),
            )
        elif update_type == "bot_started":
            logging.info("📩 update=bot_started payload=%s", update)
        else:
            logging.info("📩 update=%s", update_type)
        return await original_handle_update(update)

    bot.handle_update = traced_handle_update
    
    # Test email configuration
    if EMAIL_ENABLED and STARTUP_EMAIL_TEST and ADMIN_EMAIL:
        logging.info("📧 Testing email configuration...")
        test_result = send_email(
            "🧪 Bot Startup Test",
            "<h2>Bot Startup Test</h2><p>Bot is starting up successfully!</p>",
            ADMIN_EMAIL
        )
        if test_result:
            logging.info("✅ Email test successful!")
        else:
            logging.warning("⚠️ Email test failed - check configuration")
    
    logging.info("🔄 Starting Max bot polling...")
    logging.info("=" * 60)
    
    # Start Max bot polling
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        session = aiohttp.ClientSession(
            headers={"Authorization": bot.access_token},
            connector=connector,
        )
        await bot.start_polling(session=session)
    except Exception as e:
        logging.error("💥 Bot polling failed!")
        logging.error(f"   🚨 Error: {e}")
        raise


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
