import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F

# Load environment variables
load_dotenv("local.env")
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

# Bot token and admin chat ID
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_TELEGRAM_CHAT_ID", "0"))

# Debug logging
logging.info(f"BOT_TOKEN: {BOT_TOKEN[:10]}..." if BOT_TOKEN else "BOT_TOKEN: not set")
logging.info(f"ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")

# Email settings
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "sbcargobot@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "1Qqazxsw55")
ADMIN_EMAIL = os.getenv("DEFAULT_NOTIFICATION_EMAIL", "sb@sbcargo.ru")
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() == "true"

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

# Initialize bot and dispatcher with timeout settings
bot = Bot(BOT_TOKEN, timeout=30)
dp = Dispatcher()

# Helper to notify admin chat safely
async def notify_admin(text: str) -> bool:
    if not ADMIN_CHAT_ID or ADMIN_CHAT_ID == 0:
        logging.warning("ADMIN_CHAT_ID is not set or zero; admin notification skipped")
        return False
    
    try:
        # Try to send message
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode=ParseMode.HTML)
        logging.info(f"Admin notification sent successfully to chat {ADMIN_CHAT_ID}")
        return True
    except Exception as e:
        error_msg = str(e)
        if "chat not found" in error_msg.lower():
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
    
    logging.info(f"📧 Email details:")
    logging.info(f"   📤 From: {SMTP_USER}")
    logging.info(f"   📥 To: {to_email}")
    logging.info(f"   📝 Subject: {subject}")
    logging.info(f"   📄 Body length: {len(body)} characters")
    
    # Use Gmail App Password method (proven to work)
    try:
        # Gmail settings
        smtp_server = "smtp.gmail.com"
        sender_email = SMTP_USER
        
        # Use Gmail App Password from environment (sanitize spaces)
        raw_app_password = os.getenv("GMAIL_APP_PASSWORD", SMTP_PASSWORD) or ""
        app_password = raw_app_password.replace(" ", "")
        logging.info(f"🔐 Using App Password: {app_password[:4]}****{app_password[-4:] if len(app_password) >= 8 else '****'}")
        
        # Create message
        logging.info("📝 Creating email message...")
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        
        # Try STARTTLS (587) first
        try:
            smtp_port = 587
            logging.info("🔗 Connecting to Gmail SMTP (STARTTLS)...")
            logging.info(f"   🌐 Server: {smtp_server}")
            logging.info(f"   🔌 Port: {smtp_port}")
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=20)
            server.set_debuglevel(0)
            server.ehlo()
            logging.info("🔒 Starting TLS encryption...")
            server.starttls()
            server.ehlo()
            logging.info("🔑 Authenticating with Gmail (STARTTLS)...")
            server.login(sender_email, app_password)
            logging.info("✅ Gmail authentication successful (STARTTLS)!")
        except Exception as e_starttls:
            logging.warning(f"⚠️ STARTTLS failed: {e_starttls}")
            # Try SSL (465)
            smtp_port = 465
            logging.info("🔗 Connecting to Gmail SMTP (SSL)...")
            logging.info(f"   🌐 Server: {smtp_server}")
            logging.info(f"   🔌 Port: {smtp_port}")
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20)
            server.set_debuglevel(0)
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
            resend_key = os.getenv('RESEND_API_KEY')
            if resend_key:
                logging.info("🌐 Trying HTTPS fallback via Resend API...")
                resend_url = "https://api.resend.com/emails"
                headers = {
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "from": f"KVT Bot <{SMTP_USER}>",
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
            server.sendmail(SMTP_USER, to_email, msg.as_string())
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

# FSM States
class ApplicationStates(StatesGroup):
    waiting_for_address = State()
    waiting_for_phone = State()
    waiting_for_email = State()
    waiting_for_service = State()
    waiting_for_message = State()
    # Trading house states
    waiting_for_product = State()
    waiting_for_country = State()
    waiting_for_amount = State()
    waiting_for_currency = State()
    waiting_for_trading_house_message = State()
    # Customs clearance states
    waiting_for_product_name = State()
    waiting_for_logistics_interest = State()
    waiting_for_cargo_weight = State()
    waiting_for_pickup_location = State()
    waiting_for_delivery_location = State()
    waiting_for_customs_location = State()
    waiting_for_special_conditions = State()
    waiting_for_customs_final = State()
    # Manager transfer states
    waiting_for_manager_phone = State()
    waiting_for_manager_contact = State()
    # Edit states
    waiting_for_edit_text = State()
    waiting_for_edit_field = State()


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Юр. лица и ИП")],
            [KeyboardButton(text="Физ. лица")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "Добрый день! Подскажите, пожалуйста, Вас интересуют услуги как:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )


@dp.message(ApplicationStates.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    address = message.text.strip()
    
    if len(address) < 2:
        await message.answer("❌ Пожалуйста, введите корректное обращение:")
        return
    
    await state.update_data(address=address)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Таможенное оформление")],
            [KeyboardButton(text="Логистика")],
            [KeyboardButton(text="Сертификация")],
            [KeyboardButton(text="Сопровождение ВЭД")],
            [KeyboardButton(text="Платежный агент")],
            [KeyboardButton(text="ВЭД агент")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "Какая услуга Вас интересует? Вы так же можете задать любой вопрос, просто введите его.",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_service)


@dp.message(ApplicationStates.waiting_for_phone)
async def process_phone_submission(message: Message, state: FSMContext):
    if message.text == "✅ Отправить заявку":
        logging.info("=" * 60)
        logging.info("📋 APPLICATION SUBMISSION STARTED")
        logging.info("=" * 60)
        
        # Process the application
        data = await state.get_data()
        name = data.get('address', 'Не указано')  # Используем address как имя/обращение
        address = data.get('address', 'Не указано')
        user_type = data.get('user_type', 'Неизвестно')
        selected_service = data.get('selected_service', 'Не указана')
        user_message_text = data.get('user_message', 'Не указано')
        phone = data.get('phone', 'Не указан')
        email = data.get('email', 'Не указан')
        
        # Get username for both admin notification and email
        username = message.from_user.username if message.from_user and message.from_user.username else "Не указан"
        
        logging.info("📋 Application data collected:")
        logging.info(f"   👤 Name: {name}")
        logging.info(f"   📝 Address: {address}")
        logging.info(f"   🏷️ User Type: {user_type}")
        logging.info(f"   🔧 Service: {selected_service}")
        logging.info(f"   📞 Phone: {phone}")
        logging.info(f"   👤 Username: @{username}")
        logging.info(f"   💬 Message: {user_message_text}")
        logging.info(f"   🆔 Chat ID: {message.chat.id}")
        logging.info(f"   👤 User ID: {message.from_user.id if message.from_user else 'Unknown'}")
        
        # Show processing message
        await message.answer("⏳ Обрабатываем вашу заявку...", parse_mode=ParseMode.HTML)
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
                    f"👤 <b>Username:</b> @{username}\n\n"
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
                    f"👤 <b>Username:</b> @{username}"
                )
            
            await notify_admin(text)
        
        # Send email notification (with fallback to Telegram only)
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
                <p><strong>Username:</strong> @{username}</p>
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
                <p><strong>Username:</strong> @{username}</p>
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
            
            email_sent = send_email(email_subject, email_body, "sb@sbcargo.ru")
            if email_sent:
                logging.info("✅ Email notification sent successfully!")
                logging.info("   📧 Check admin email inbox")
            else:
                logging.warning("❌ Email notification failed!")
                logging.warning("   📱 But Telegram notification was sent")
        except Exception as e:
            logging.error("💥 Failed to send email notification!")
            logging.exception(f"   🚨 Error: {e}")

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏠 Главное меню")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "✅ <b>Спасибо! Ваша заявка успешно отправлена.</b>\n\n"
            "📋 <b>Детали заявки:</b>\n"
            f"👤 Имя: {name}\n"
            f"📝 Обращение: {address}\n"
            f"📞 Телефон: {phone}\n"
            f"🔧 Услуга: {selected_service}\n"
            f"💬 Сообщение: {user_message_text}\n\n"
            "Мы свяжемся с вами в ближайшее время для уточнения деталей!",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.clear()
        return
    
    # If not "Отправить заявку", treat as phone input
    phone = message.text.strip()
    
    # Validate phone input
    if len(phone) < 10:
        await message.answer("❌ Пожалуйста, введите корректный номер телефона (минимум 10 символов):")
        return
    
    await state.update_data(phone=phone)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ <b>Телефон:</b> {phone}\n\n"
        f"📧 <b>Введите ваш email адрес:</b>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_email)


@dp.message(ApplicationStates.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    """Handle email input for regular applications"""
    
    # Check if user clicked "Отправить заявку"
    if message.text == "✅ Отправить заявку":
        logging.info("=" * 60)
        logging.info("📋 APPLICATION SUBMISSION STARTED (from email handler)")
        logging.info("=" * 60)
        
        # Process the application
        data = await state.get_data()
        name = data.get('address', 'Не указано')
        address = data.get('address', 'Не указано')
        user_type = data.get('user_type', 'Неизвестно')
        selected_service = data.get('selected_service', 'Не указана')
        user_message_text = data.get('user_message', 'Не указано')
        phone = data.get('phone', 'Не указан')
        email = data.get('email', 'Не указан')
        
        # Get username
        username = message.from_user.username if message.from_user and message.from_user.username else "Не указан"
        
        # Show processing message
        await message.answer("⏳ Обрабатываем вашу заявку...", parse_mode=ParseMode.HTML)
        
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
                    f"👤 <b>Username:</b> @{username}\n\n"
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
                    f"👤 <b>Username:</b> @{username}"
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
                    <p><strong>Username:</strong> @{username}</p>
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
                    <p><strong>Username:</strong> @{username}</p>
                </body>
                </html>
                """
            
            send_email(email_subject, email_body, "sb@sbcargo.ru")
        except Exception as e:
            logging.exception("Failed to send email notification: %s", e)
        
        # Send confirmation to user
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏠 Главное меню")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "✅ <b>Заявка успешно отправлена!</b>\n\n"
            f"📝 <b>Обращение:</b> {address}\n"
            f"📞 <b>Телефон:</b> {phone}\n"
            f"📧 <b>Email:</b> {email}\n"
            f"🔧 <b>Услуга:</b> {selected_service}\n\n"
            "Мы свяжемся с вами в ближайшее время для уточнения деталей!",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
        await state.clear()
        return
    
    # If not "Отправить заявку", treat as email input
    email = message.text.strip()
    await state.update_data(email=email)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Отправить заявку")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    data = await state.get_data()
    selected_service = data.get('selected_service', 'Не указана')
    user_message = data.get('user_message', 'Не указано')
    
    await message.answer(
        f"✅ <b>Готово к отправке!</b>\n\n"
        f"📝 <b>Обращение:</b> {data.get('address', 'Не указано')}\n"
        f"📞 <b>Телефон:</b> {data.get('phone', 'Не указан')}\n"
        f"📧 <b>Email:</b> {email}\n"
        f"🔧 <b>Услуга:</b> {selected_service}\n"
        f"💬 <b>Сообщение:</b> {user_message}\n\n"
        f"Отправить заявку?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )


@dp.message(ApplicationStates.waiting_for_service)
async def process_service_selection(message: Message, state: FSMContext):
    service_text = message.text.strip()
    
    if service_text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            parse_mode=ParseMode.HTML
        )
        return
    
    if service_text == "Таможенное оформление":
        # Customs clearance - start detailed questionnaire
        await state.update_data(selected_service=service_text)
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            f"✅ Выбрана услуга: <b>{service_text}</b>\n\n"
            f"Напишите наименование товара и его характеристики:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_product_name)
    
    elif service_text in ["Логистика", "Сертификация", "Сопровождение ВЭД", "Платежный агент", "ВЭД агент"]:
        # Regular service
        await state.update_data(selected_service=service_text)
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            f"✅ Выбрана услуга: <b>{service_text}</b>\n\n"
            f"Опишите подробнее, что именно вас интересует или задайте вопрос:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_message)
    
    elif service_text == "Торговый дом (закупка товаров)":
        # Trading house - start detailed questionnaire
        await state.update_data(selected_service=service_text)
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Одежда"), KeyboardButton(text="Электроника")],
                [KeyboardButton(text="Мебель"), KeyboardButton(text="Автозапчасти")],
                [KeyboardButton(text="Продукты питания"), KeyboardButton(text="Строительные материалы")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            f"✅ Выбрана услуга: <b>{service_text}</b>\n\n"
            f"Какой товар планируете закупить? Выберите из примеров или введите свой вариант:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_product)
    
    else:
        # It's a question - not a predefined service
        await state.update_data(selected_service="Вопрос")
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            f"✅ Ваш вопрос: <b>{service_text}</b>\n\n"
            f"Опишите подробнее, что именно вас интересует или задайте вопрос:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_message)


@dp.message(ApplicationStates.waiting_for_message)
async def process_message(message: Message, state: FSMContext):
    user_message = message.text.strip()
    
    if user_message == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            parse_mode=ParseMode.HTML
        )
        return
    
    if len(user_message) < 10:
        await message.answer("❌ Пожалуйста, опишите подробнее вашу заявку (минимум 10 символов):")
        return
    
    # Save the message and ask for phone
    await state.update_data(user_message=user_message)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    data = await state.get_data()
    selected_service = data.get('selected_service', 'Не указана')
    
    await message.answer(
        f"✅ <b>Ваше сообщение:</b>\n{user_message}\n\n"
        f"<b>Услуга:</b> {selected_service}\n\n"
        f"📞 <b>Введите ваш номер телефона для связи:</b>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_phone)


# Trading house handlers
@dp.message(ApplicationStates.waiting_for_product)
async def process_product(message: Message, state: FSMContext):
    product = message.text.strip()
    
    if product == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            parse_mode=ParseMode.HTML
        )
        return
    
    if len(product) < 2:
        await message.answer("❌ Пожалуйста, введите корректное название товара:")
        return
    
    await state.update_data(product=product)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ Товар: <b>{product}</b>\n\n"
        f"Из какой страны планируете закупать?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_country)


@dp.message(ApplicationStates.waiting_for_country)
async def process_country(message: Message, state: FSMContext):
    country = message.text.strip()
    
    if country == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            parse_mode=ParseMode.HTML
        )
        return
    
    if len(country) < 2:
        await message.answer("❌ Пожалуйста, введите корректное название страны:")
        return
    
    await state.update_data(country=country)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ Страна-производитель: <b>{country}</b>\n\n"
        f"На какую сумму планируете закупить товар/услугу?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_amount)


@dp.message(ApplicationStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    amount = message.text.strip()
    
    if amount == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Validate amount input
    try:
        # Remove spaces and common currency symbols
        clean_amount = amount.replace(" ", "").replace("$", "").replace("€", "").replace("₽", "").replace("₴", "")
        
        # Check if it's a valid number
        if not clean_amount.replace(".", "").replace(",", "").isdigit():
            await message.answer("❌ Пожалуйста, введите корректную сумму (только цифры):")
            return
        
        # Check for reasonable amount (between 100 and 10000000)
        amount_value = float(clean_amount.replace(",", "."))
        if amount_value < 100:
            await message.answer("❌ Сумма должна быть не менее 100:")
            return
        if amount_value > 10000000:
            await message.answer("❌ Сумма слишком большая, введите корректное значение:")
            return
            
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму (только цифры):")
        return
    
    await state.update_data(amount=amount)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="$"), KeyboardButton(text="€")],
            [KeyboardButton(text="₽"), KeyboardButton(text="₴")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ Планируемая сумма: <b>{amount}</b>\n\n"
        f"В какой валюте поставщик принимает оплату?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_currency)


@dp.message(ApplicationStates.waiting_for_currency)
async def process_currency(message: Message, state: FSMContext):
    currency = message.text.strip()
    
    if currency == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            parse_mode=ParseMode.HTML
        )
        return
    
    if currency not in ["$", "€", "₽", "₴"]:
        await message.answer("❌ Пожалуйста, выберите валюту из предложенных вариантов:")
        return
    
    await state.update_data(currency=currency)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Отправить заявку")],
            [KeyboardButton(text="📞 Позвать менеджера")],
            [KeyboardButton(text="✏️ Редактировать")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    data = await state.get_data()
    product = data.get('product', 'Не указан')
    country = data.get('country', 'Не указана')
    amount = data.get('amount', 'Не указана')
    
    await message.answer(
        f"✅ <b>Готово к отправке!</b>\n\n"
        f"📦 <b>Товар:</b> {product}\n"
        f"🌍 <b>Страна:</b> {country}\n"
        f"💰 <b>Сумма:</b> {amount} {currency}\n\n"
        f"Выберите действие:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_trading_house_message)


@dp.message(ApplicationStates.waiting_for_trading_house_message)
async def process_trading_house_final(message: Message, state: FSMContext):
    final_choice = message.text.strip()
    
    if final_choice == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ <b>Заявка отменена</b>\n\n"
            "Если передумаете, используйте команду /start для создания новой заявки.",
            parse_mode=ParseMode.HTML
        )
        return
    
    if final_choice == "✅ Отправить заявку":
        # Ask for phone before submission
        keyboard = ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        data = await state.get_data()
        product = data.get('product', 'Не указан')
        country = data.get('country', 'Не указана')
        amount = data.get('amount', 'Не указана')
        currency = data.get('currency', 'Не указана')
        
        await message.answer(
            f"✅ <b>Готово к отправке!</b>\n\n"
            f"📦 <b>Товар:</b> {product}\n"
            f"🌍 <b>Страна:</b> {country}\n"
            f"💰 <b>Сумма:</b> {amount} {currency}\n\n"
            f"📞 <b>Введите ваш номер телефона для связи:</b>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_phone)
    
    elif final_choice == "✏️ Редактировать":
        # Show edit options
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📦 Товар")],
                [KeyboardButton(text="🌍 Страна")],
                [KeyboardButton(text="💰 Сумма")],
                [KeyboardButton(text="💱 Валюта")],
                [KeyboardButton(text="🏠 Адрес")],
                [KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "✏️ <b>Что хотите отредактировать?</b>\n\n"
            "Выберите поле для редактирования:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_edit_field)
        return
    
    elif final_choice == "📞 Позвать менеджера":
        # Ask for phone number before calling manager
        keyboard = ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        data = await state.get_data()
        product = data.get('product', 'Не указан')
        country = data.get('country', 'Не указана')
        amount = data.get('amount', 'Не указана')
        currency = data.get('currency', 'Не указана')
        
        await message.answer(
            f"📞 <b>Позвать менеджера</b>\n\n"
            f"📦 <b>Товар:</b> {product}\n"
            f"🌍 <b>Страна:</b> {country}\n"
            f"💰 <b>Сумма:</b> {amount} {currency}\n\n"
            f"📞 <b>Введите ваш номер телефона для связи с менеджером:</b>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_manager_phone)
    
    elif final_choice == "⬅️ Назад":
        # Go back to currency selection
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="$"), KeyboardButton(text="€")],
                [KeyboardButton(text="₽"), KeyboardButton(text="₴")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        data = await state.get_data()
        amount = data.get('amount', 'Не указана')
        
        await message.answer(
            f"⬅️ <b>Возвращаемся к выбору валюты</b>\n\n"
            f"Планируемая сумма: <b>{amount}</b>\n\n"
            f"В какой валюте поставщик принимает оплату?",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_currency)
    
    else:
        await message.answer("❌ Пожалуйста, выберите один из предложенных вариантов:")


# Handle main menu button
@dp.message(F.text == "🏠 Главное меню")
async def handle_main_menu(message: Message, state: FSMContext):
    await state.clear()
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Юр. лица и ИП")],
            [KeyboardButton(text="Физ. лица")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Добрый день! Подскажите, пожалуйста, Вас интересуют услуги как:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

# Handle user type selection
@dp.message(F.text.in_(["Юр. лица и ИП", "Физ. лица"]))
async def handle_user_type(message: Message, state: FSMContext):
    user_type = message.text
    
    if user_type == "Физ. лица":
        await message.answer(
            "❌ <b>К сожалению, мы не работаем с физическими лицами</b>\n\n"
            "Наши услуги предназначены только для юридических лиц и индивидуальных предпринимателей.\n\n"
            "Если у вас есть ИП или ООО, пожалуйста, выберите соответствующий вариант.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # For "Юр. лица и ИП"
    await state.update_data(user_type=user_type)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "Как можно обращаться к вам?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_address)


# Customs clearance handlers
@dp.message(ApplicationStates.waiting_for_product_name)
async def process_product_name(message: Message, state: FSMContext):
    product_name = message.text.strip()
    
    if len(product_name) < 2:
        await message.answer("❌ Пожалуйста, введите корректное наименование товара:")
        return
    
    await state.update_data(product_name=product_name)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да"), KeyboardButton(text="Нет")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ Товар: <b>{product_name}</b>\n\n"
        f"Мы можем помочь с логистикой Вашего груза. Вам интересно наше предложение по логистике Вашего груза?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_logistics_interest)


@dp.message(ApplicationStates.waiting_for_logistics_interest)
async def process_logistics_interest(message: Message, state: FSMContext):
    interest = message.text.strip()
    
    if interest not in ["Да", "Нет"]:
        await message.answer("❌ Пожалуйста, выберите Да или Нет:")
        return
    
    await state.update_data(logistics_interest=interest)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ Логистика: <b>{interest}</b>\n\n"
        f"Напишите общий вес товара:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_cargo_weight)


@dp.message(ApplicationStates.waiting_for_cargo_weight)
async def process_cargo_weight(message: Message, state: FSMContext):
    weight = message.text.strip()
    
    if len(weight) < 1:
        await message.answer("❌ Пожалуйста, введите вес товара:")
        return
    
    await state.update_data(cargo_weight=weight)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ Вес товара: <b>{weight}</b>\n\n"
        f"Где необходимо забрать груз?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_pickup_location)


@dp.message(ApplicationStates.waiting_for_pickup_location)
async def process_pickup_location(message: Message, state: FSMContext):
    pickup = message.text.strip()
    
    if len(pickup) < 2:
        await message.answer("❌ Пожалуйста, введите место забора груза:")
        return
    
    await state.update_data(pickup_location=pickup)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ Место забора: <b>{pickup}</b>\n\n"
        f"Куда нужно доставить груз?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_delivery_location)


@dp.message(ApplicationStates.waiting_for_delivery_location)
async def process_delivery_location(message: Message, state: FSMContext):
    delivery = message.text.strip()
    
    if len(delivery) < 2:
        await message.answer("❌ Пожалуйста, введите место доставки:")
        return
    
    await state.update_data(delivery_location=delivery)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ Место доставки: <b>{delivery}</b>\n\n"
        f"Место проведения таможенного оформления, если знаете:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_customs_location)


@dp.message(ApplicationStates.waiting_for_customs_location)
async def process_customs_location(message: Message, state: FSMContext):
    customs_location = message.text.strip()
    
    await state.update_data(customs_location=customs_location)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ Место таможенного оформления: <b>{customs_location}</b>\n\n"
        f"Есть ли какие-либо особые условия? (например: нельзя штабелировать, опасный груз, подлежит контролю РСХН)",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_special_conditions)


@dp.message(ApplicationStates.waiting_for_special_conditions)
async def process_special_conditions(message: Message, state: FSMContext):
    special_conditions = message.text.strip()
    
    await state.update_data(special_conditions=special_conditions)
    
    # Get all collected data
    data = await state.get_data()
    product_name = data.get('product_name', 'Не указан')
    pickup = data.get('pickup_location', 'Не указано')
    delivery = data.get('delivery_location', 'Не указано')
    customs_location = data.get('customs_location', 'Не указано')
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Отправить заявку")],
            [KeyboardButton(text="📞 Позвать менеджера")],
            [KeyboardButton(text="✏️ Редактировать")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"<b>Давайте подытожим.</b>\n\n"
        f"📦 <b>Товар:</b> {product_name}\n"
        f"📍 <b>Забрать товар нужно из:</b> {pickup}\n"
        f"🎯 <b>Доставить в:</b> {delivery}\n"
        f"🏛️ <b>Место таможенного оформления:</b> {customs_location}\n"
        f"⚠️ <b>Особые условия:</b> {special_conditions}\n\n"
        f"Отправляю заявку или позвать менеджера?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_customs_final)


@dp.message(ApplicationStates.waiting_for_customs_final)
async def process_customs_final(message: Message, state: FSMContext):
    final_choice = message.text.strip()
    
    if final_choice == "✅ Отправить заявку":
        # Ask for phone before submission
        keyboard = ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        data = await state.get_data()
        product_name = data.get('product_name', 'Не указан')
        logistics_interest = data.get('logistics_interest', 'Не указано')
        cargo_weight = data.get('cargo_weight', 'Не указан')
        pickup = data.get('pickup_location', 'Не указано')
        delivery = data.get('delivery_location', 'Не указано')
        customs_location = data.get('customs_location', 'Не указано')
        special_conditions = data.get('special_conditions', 'Не указано')
        
        await message.answer(
            f"✅ <b>Готово к отправке!</b>\n\n"
            f"📦 <b>Товар:</b> {product_name}\n"
            f"🚛 <b>Логистика:</b> {logistics_interest}\n"
            f"⚖️ <b>Вес:</b> {cargo_weight}\n"
            f"📍 <b>Забрать из:</b> {pickup}\n"
            f"🎯 <b>Доставить в:</b> {delivery}\n"
            f"🏛️ <b>Таможня:</b> {customs_location}\n"
            f"⚠️ <b>Условия:</b> {special_conditions}\n\n"
            f"📞 <b>Введите ваш номер телефона для связи:</b>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_phone)
    
    elif final_choice == "⬅️ Назад":
        # Go back to special conditions input
        keyboard = ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            "⬅️ <b>Возвращаемся к указанию особых условий</b>\n\n"
            "Опишите, пожалуйста, особые условия (например: нельзя штабелировать, опасный груз, подлежит контролю РСХН)",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_special_conditions)
    
    elif final_choice == "✏️ Редактировать":
        # Show edit options for customs clearance
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📦 Название товара")],
                [KeyboardButton(text="🚛 Логистика")],
                [KeyboardButton(text="⚖️ Вес груза")],
                [KeyboardButton(text="📍 Откуда забрать")],
                [KeyboardButton(text="📍 Куда доставить")],
                [KeyboardButton(text="🏛️ Таможня")],
                [KeyboardButton(text="💬 Особые условия")],
                [KeyboardButton(text="🏠 Адрес")],
                [KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "✏️ <b>Что хотите отредактировать?</b>\n\n"
            "Выберите поле для редактирования:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_edit_field)
        return
    
    elif final_choice == "📞 Позвать менеджера":
        # Ask for phone number before calling manager
        keyboard = ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        data = await state.get_data()
        product_name = data.get('product_name', 'Не указан')
        logistics_interest = data.get('logistics_interest', 'Не указано')
        cargo_weight = data.get('cargo_weight', 'Не указан')
        pickup = data.get('pickup_location', 'Не указано')
        delivery = data.get('delivery_location', 'Не указано')
        customs_location = data.get('customs_location', 'Не указано')
        special_conditions = data.get('special_conditions', 'Не указано')
        
        await message.answer(
            f"📞 <b>Позвать менеджера</b>\n\n"
            f"📦 <b>Товар:</b> {product_name}\n"
            f"🚛 <b>Логистика:</b> {logistics_interest}\n"
            f"⚖️ <b>Вес:</b> {cargo_weight}\n"
            f"📍 <b>Забрать из:</b> {pickup}\n"
            f"🎯 <b>Доставить в:</b> {delivery}\n"
            f"🏛️ <b>Таможня:</b> {customs_location}\n"
            f"⚠️ <b>Условия:</b> {special_conditions}\n\n"
            f"📞 <b>Введите ваш номер телефона для связи с менеджером:</b>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_manager_phone)


# Manager transfer handlers
@dp.message(ApplicationStates.waiting_for_manager_phone)
async def process_manager_phone(message: Message, state: FSMContext):
    """Handle phone number input for manager transfer"""
    phone = message.text.strip()
    
    # Validate phone input
    if len(phone) < 10:
        await message.answer("❌ Пожалуйста, введите корректный номер телефона (минимум 10 символов):")
        return
    
    await state.update_data(manager_phone=phone)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ <b>Номер телефона:</b> {phone}\n\n"
        f"📧 <b>Введите ваш email для связи с менеджером:</b>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ApplicationStates.waiting_for_manager_contact)


@dp.message(ApplicationStates.waiting_for_manager_contact)
async def process_manager_contact(message: Message, state: FSMContext):
    """Handle contact information and send manager notification"""
    contact = message.text.strip()
    
    # Accept any input as contact (no validation)
    await state.update_data(manager_contact=contact)
    
    # Get all data
    data = await state.get_data()
    address = data.get('address', 'Не указано')
    username = message.from_user.username if message.from_user and message.from_user.username else "Не указан"
    manager_phone = data.get('manager_phone', 'Не указан')
    selected_service = data.get('selected_service', 'Не указана')
    
    # Show processing message
    await message.answer("⏳ Переводим на менеджера...", parse_mode=ParseMode.HTML)
    
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
                f"👤 <b>Username:</b> @{username}\n\n"
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
                <p><strong>Username:</strong> @{username}</p>
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
            send_email(email_subject, email_body, "sb@sbcargo.ru")
        except Exception as e:
            logging.exception("Failed to send manager call email: %s", e)
    
    else:
        # Trading house or other services
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
                f"👤 <b>Username:</b> @{username}\n\n"
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
                <p><strong>Username:</strong> @{username}</p>
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
            send_email(email_subject, email_body, "sb@sbcargo.ru")
        except Exception as e:
            logging.exception("Failed to send manager call email: %s", e)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "📞 <b>Менеджер будет с вами связываться!</b>\n\n"
        f"📞 <b>Ваш телефон:</b> {manager_phone}\n"
        f"📧 <b>Ваш email:</b> {contact}\n\n"
        "Наш специалист свяжется с вами в ближайшее время для обсуждения деталей.",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.clear()


# Diagnostic commands
@dp.message(Command("id"))
async def cmd_id(message: Message):
    chat_info = f"""
🆔 <b>Chat Information:</b>

📱 <b>Chat ID:</b> <code>{message.chat.id}</code>
👤 <b>User ID:</b> <code>{message.from_user.id if message.from_user else 'N/A'}</code>
📝 <b>Chat Type:</b> {message.chat.type}
👤 <b>Username:</b> @{message.from_user.username if message.from_user and message.from_user.username else 'Не указан'}

💡 <b>Для настройки админа:</b>
Скопируйте Chat ID и установите в docker-compose.yml:
<code>ADMIN_CHAT_ID={message.chat.id}</code>
"""
    await message.answer(chat_info, parse_mode=ParseMode.HTML)

@dp.message(Command("ping"))
async def cmd_ping(message: Message):
    await message.answer("pong")

@dp.message(Command("test_email"))
async def cmd_test_email(message: Message):
    """Test email sending functionality"""
    try:
        await message.answer("📧 Тестирую отправку email...")
        
        test_subject = "🧪 Тест отправки email"
        test_body = f"""
        <html>
        <body>
            <h2>🧪 Тест отправки email</h2>
            <p><strong>Время:</strong> {message.date}</p>
            <p><strong>Chat ID:</strong> {message.chat.id}</p>
            <p><strong>Username:</strong> @{message.from_user.username if message.from_user and message.from_user.username else 'Не указан'}</p>
            <p><strong>SMTP Host:</strong> {SMTP_HOST}</p>
            <p><strong>SMTP Port:</strong> {SMTP_PORT}</p>
            <p><strong>From:</strong> {SMTP_USER}</p>
            <p><strong>To:</strong> {ADMIN_EMAIL}</p>
            <hr>
            <p>Если вы получили это письмо, значит SMTP работает корректно!</p>
        </body>
        </html>
        """
        
        result = send_email(test_subject, test_body)
        
        if result:
            await message.answer("✅ Email отправлен успешно! Проверьте почту.")
        else:
            await message.answer("❌ Ошибка отправки email. Проверьте логи.")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка тестирования email: {e}")
        logging.exception("Test email failed: %s", e)

@dp.message(Command("smtp_info"))
async def cmd_smtp_info(message: Message):
    """Show current SMTP configuration"""
    info = f"""
📧 <b>SMTP Configuration:</b>

🏠 <b>Primary Host:</b> {SMTP_HOST}:{SMTP_PORT}
👤 <b>User:</b> {SMTP_USER}
📬 <b>Admin Email:</b> {ADMIN_EMAIL}

🔄 <b>Fallback Servers:</b>
"""
    for i, (host, port, method) in enumerate(SMTP_ALTERNATIVES, 1):
        info += f"{i}. {host}:{port} ({method})\n"
    
    await message.answer(info, parse_mode=ParseMode.HTML)

@dp.message(Command("network_test"))
async def cmd_network_test(message: Message):
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
    
    await message.answer(results, parse_mode=ParseMode.HTML)

@dp.message(Command("gmail_test"))
async def cmd_gmail_test(message: Message):
    """Test Gmail SMTP connection specifically"""
    try:
        await message.answer("🔐 Тестирую подключение к Gmail SMTP...")
        
        import smtplib
        import ssl
        
        # Prepare password (sanitize spaces)
        raw_app_password = os.getenv("GMAIL_APP_PASSWORD", SMTP_PASSWORD) or ""
        app_password = raw_app_password.replace(" ", "")
        
        # Test STARTTLS (port 587)
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
            server.ehlo()
            context = ssl.create_default_context()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, app_password)
            server.quit()
            await message.answer("✅ Gmail STARTTLS (587) - подключение успешно!")
        except Exception as e:
            await message.answer(f"❌ Gmail STARTTLS (587) failed: {e}")
        
        # Test SSL (port 465)
        try:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15, context=context)
            server.login(SMTP_USER, app_password)
            server.quit()
            await message.answer("✅ Gmail SSL (465) - подключение успешно!")
        except Exception as e:
            await message.answer(f"❌ Gmail SSL (465) failed: {e}")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка тестирования Gmail: {e}")

@dp.message(Command("api_test"))
async def cmd_api_test(message: Message):
    """Test HTTP API email service"""
    try:
        await message.answer("🌐 Тестирую HTTP API email сервис...")
        
        import requests
        
        # Test API health
        try:
            await message.answer("✅ Проверяем Gmail соединение...")
        except Exception as e:
            await message.answer(f"❌ Ошибка проверки: {e}")
            return
        
        # Test email sending
        test_subject = "🧪 Тест Gmail - KVT Bot"
        test_body = f"""
        <h2>Тестовое письмо через Gmail</h2>
        <p><strong>Время:</strong> {message.date}</p>
        <p><strong>Chat ID:</strong> {message.chat.id}</p>
        <p><strong>Метод:</strong> Gmail App Password</p>
        <hr>
        <p>✅ Если вы получили это письмо, значит Gmail работает!</p>
        """
        
        try:
            result = send_email(test_subject, test_body, ADMIN_EMAIL)
            if result:
                await message.answer("✅ Email отправлен через Gmail! Проверьте почту.")
            else:
                await message.answer("❌ Ошибка отправки через Gmail. Проверьте логи.")
        except Exception as e:
            await message.answer(f"❌ Ошибка отправки через Gmail: {e}")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка тестирования HTTP API: {e}")
        logging.exception("HTTP API test failed: %s", e)

@dp.message(Command("email_test_all"))
async def cmd_email_test_all(message: Message):
    """Test all email methods comprehensively"""
    try:
        await message.answer("🧪 Тестирую ВСЕ методы отправки email...")
        
        test_subject = "🧪 Комплексный тест email - KVT Bot"
        test_body = f"""
        <h2>📧 Комплексный тест email</h2>
        <p><strong>Время:</strong> {message.date}</p>
        <p><strong>Chat ID:</strong> {message.chat.id}</p>
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
            resend_key = os.getenv('RESEND_API_KEY')
            if resend_key:
                headers = {"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"}
                payload = {"from": f"KVT Bot <{SMTP_USER}>", "to": [ADMIN_EMAIL], "subject": f"{test_subject} (Resend)", "html": test_body}
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
            msg['From'] = SMTP_USER
            msg['To'] = ADMIN_EMAIL
            msg['Subject'] = f"{test_subject} (MailHog)"
            msg.attach(MIMEText(test_body, 'html', 'utf-8'))
            
            server = smtplib.SMTP("mailhog", 1025, timeout=5)
            server.sendmail(SMTP_USER, ADMIN_EMAIL, msg.as_string())
            server.quit()
            methods_tested.append("✅ MailHog: Success")
        except Exception as e:
            methods_tested.append(f"❌ MailHog: {str(e)[:50]}")
        
        # Show results
        results_text = "📊 <b>Результаты тестирования email:</b>\n\n" + "\n".join(methods_tested)
        
        await message.answer(results_text, parse_mode=ParseMode.HTML)
        
        # Additional info
        await message.answer(
            "💡 <b>Проверьте:</b>\n"
            "• Основную папку почты\n"
            "• Папку 'Спам'\n"
            "• MailHog: http://localhost:8025",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка комплексного тестирования: {e}")
        logging.exception("Comprehensive email test failed: %s", e)

@dp.message(Command("email_status"))
async def cmd_email_status(message: Message):
    """Show email configuration status"""
    status = f"""
📧 <b>Email Status:</b>

🔧 <b>Email Enabled:</b> {'✅ Yes' if EMAIL_ENABLED else '❌ No'}
🏠 <b>SMTP Host:</b> {SMTP_HOST}:{SMTP_PORT}
👤 <b>User:</b> {SMTP_USER}
📬 <b>Admin Email:</b> {ADMIN_EMAIL}

💡 <b>Commands:</b>
• /test_email - Test email sending (all methods)
• /email_test_all - Comprehensive email testing
• /api_test - Test Gmail email service
• /gmail_test - Test Gmail SMTP connection
• /network_test - Test network connectivity
• /test_admin - Test admin notifications
"""
    await message.answer(status, parse_mode=ParseMode.HTML)

@dp.message(Command("test_admin"))
async def cmd_test_admin(message: Message):
    """Test admin notification"""
    try:
        await message.answer("📤 Тестирую отправку уведомления админу...")
        
        test_text = f"""
🧪 <b>Тест уведомления админу</b>

📱 <b>От:</b> @{message.from_user.username if message.from_user and message.from_user.username else 'Не указан'}
🆔 <b>Chat ID:</b> {message.chat.id}
⏰ <b>Время:</b> {message.date}

✅ Если вы получили это сообщение, значит уведомления админу работают!
"""
        
        result = await notify_admin(test_text)
        
        if result:
            await message.answer("✅ Уведомление админу отправлено успешно!")
        else:
            await message.answer("❌ Ошибка отправки уведомления админу. Проверьте логи.")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка тестирования: {e}")
        logging.exception("Test admin notification failed: %s", e)

# Edit handlers
@dp.message(ApplicationStates.waiting_for_edit_field)
async def process_edit_field_selection(message: Message, state: FSMContext):
    """Handle field selection for editing"""
    field_choice = message.text.strip()
    
    if field_choice == "⬅️ Назад":
        # Return to previous state based on current service
        data = await state.get_data()
        service = data.get('service', '')
        
        if service == "Торговый дом":
            # Return to trading house final step
            product = data.get('product', 'Не указан')
            country = data.get('country', 'Не указана')
            amount = data.get('amount', 'Не указана')
            currency = data.get('currency', 'Не указана')
            
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="✅ Отправить заявку")],
                    [KeyboardButton(text="📞 Позвать менеджера")],
                    [KeyboardButton(text="✏️ Редактировать")],
                    [KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(
                f"<b>Давайте подытожим.</b>\n\n"
                f"📦 <b>Товар:</b> {product}\n"
                f"🌍 <b>Страна:</b> {country}\n"
                f"💰 <b>Сумма:</b> {amount}\n"
                f"💱 <b>Валюта:</b> {currency}\n\n"
                f"Всё верно?",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
            await state.set_state(ApplicationStates.waiting_for_trading_house_message)
        else:
            # Return to customs clearance final step
            product_name = data.get('product_name', 'Не указан')
            logistics_interest = data.get('logistics_interest', 'Не указано')
            cargo_weight = data.get('cargo_weight', 'Не указан')
            pickup = data.get('pickup_location', 'Не указано')
            delivery = data.get('delivery_location', 'Не указано')
            customs_location = data.get('customs_location', 'Не указано')
            special_conditions = data.get('special_conditions', 'Не указано')
            
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="✅ Отправить заявку")],
                    [KeyboardButton(text="📞 Позвать менеджера")],
                    [KeyboardButton(text="✏️ Редактировать")],
                    [KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(
                f"<b>Давайте подытожим.</b>\n\n"
                f"📦 <b>Товар:</b> {product_name}\n"
                f"📍 <b>Забрать товар нужно из:</b> {pickup}\n"
                f"📍 <b>Доставить товар нужно в:</b> {delivery}\n"
                f"🏛️ <b>Таможенное оформление в:</b> {customs_location}\n"
                f"⚖️ <b>Вес груза:</b> {cargo_weight}\n"
                f"🚛 <b>Логистика:</b> {logistics_interest}\n"
                f"💬 <b>Особые условия:</b> {special_conditions}\n\n"
                f"Всё верно?",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
            await state.set_state(ApplicationStates.waiting_for_customs_final)
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
        await state.update_data(editing_field=data_key)
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="❌ Отмена")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            f"✏️ <b>Редактирование:</b> {field_choice}\n\n"
            f"{prompt}",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_edit_text)
    else:
        await message.answer("❌ Неизвестное поле. Выберите из предложенных вариантов.")

@dp.message(ApplicationStates.waiting_for_edit_text)
async def process_edit_text(message: Message, state: FSMContext):
    """Handle text input for editing"""
    if message.text == "❌ Отмена":
        # Return to field selection
        data = await state.get_data()
        service = data.get('service', '')
        
        if service == "Торговый дом":
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📦 Товар")],
                    [KeyboardButton(text="🌍 Страна")],
                    [KeyboardButton(text="💰 Сумма")],
                    [KeyboardButton(text="💱 Валюта")],
                    [KeyboardButton(text="🏠 Адрес")],
                    [KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        else:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📦 Название товара")],
                    [KeyboardButton(text="🚛 Логистика")],
                    [KeyboardButton(text="⚖️ Вес груза")],
                    [KeyboardButton(text="📍 Откуда забрать")],
                    [KeyboardButton(text="📍 Куда доставить")],
                    [KeyboardButton(text="🏛️ Таможня")],
                    [KeyboardButton(text="💬 Особые условия")],
                    [KeyboardButton(text="🏠 Адрес")],
                    [KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        
        await message.answer(
            "✏️ <b>Что хотите отредактировать?</b>\n\n"
            "Выберите поле для редактирования:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_edit_field)
        return
    
    # Get the field being edited
    data = await state.get_data()
    editing_field = data.get('editing_field')
    new_value = message.text.strip()
    
    if not editing_field:
        await message.answer("❌ Ошибка: поле для редактирования не найдено.")
        return
    
    # Update the field
    await state.update_data(**{editing_field: new_value})
    
    # Show updated summary and return to final step
    service = data.get('service', '')
    
    if service == "Торговый дом":
        # Show updated trading house summary
        product = data.get('product', 'Не указан')
        country = data.get('country', 'Не указана')
        amount = data.get('amount', 'Не указана')
        currency = data.get('currency', 'Не указана')
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Отправить заявку")],
                [KeyboardButton(text="📞 Позвать менеджера")],
                [KeyboardButton(text="✏️ Редактировать")],
                [KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            f"✅ <b>Поле обновлено!</b>\n\n"
            f"<b>Давайте подытожим.</b>\n\n"
            f"📦 <b>Товар:</b> {product}\n"
            f"🌍 <b>Страна:</b> {country}\n"
            f"💰 <b>Сумма:</b> {amount}\n"
            f"💱 <b>Валюта:</b> {currency}\n\n"
            f"Всё верно?",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_trading_house_message)
    else:
        # Show updated customs clearance summary
        product_name = data.get('product_name', 'Не указан')
        logistics_interest = data.get('logistics_interest', 'Не указано')
        cargo_weight = data.get('cargo_weight', 'Не указан')
        pickup = data.get('pickup_location', 'Не указано')
        delivery = data.get('delivery_location', 'Не указано')
        customs_location = data.get('customs_location', 'Не указано')
        special_conditions = data.get('special_conditions', 'Не указано')
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Отправить заявку")],
                [KeyboardButton(text="📞 Позвать менеджера")],
                [KeyboardButton(text="✏️ Редактировать")],
                [KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
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
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.set_state(ApplicationStates.waiting_for_customs_final)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logging.info("=" * 60)
    logging.info("🚀 KVT BOT STARTING UP")
    logging.info("=" * 60)
    
    # Log configuration
    logging.info("⚙️ Bot Configuration:")
    logging.info(f"   🤖 Bot Token: {BOT_TOKEN[:10]}..." if BOT_TOKEN else "   ❌ Bot Token: NOT SET")
    logging.info(f"   👤 Admin Chat ID: {ADMIN_CHAT_ID}")
    logging.info(f"   📧 Email Enabled: {EMAIL_ENABLED}")
    logging.info(f"   📤 SMTP User: {SMTP_USER}")
    logging.info(f"   📥 Admin Email: {ADMIN_EMAIL}")
    logging.info(f"   🌐 SMTP Host: {SMTP_HOST}:{SMTP_PORT}")
    
    # Test email configuration
    if EMAIL_ENABLED:
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
    
    logging.info("🔄 Starting bot polling...")
    logging.info("=" * 60)
    
    # Configure polling with retry settings
    try:
        await dp.start_polling(
            bot,
            timeout=30,
            request_timeout=30,
            retry_after=1,
            drop_pending_updates=True
        )
    except Exception as e:
        logging.error("💥 Bot polling failed!")
        logging.error(f"   🚨 Error: {e}")
        raise


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())