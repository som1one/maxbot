#!/usr/bin/env python3
"""
Отправка через Gmail с App Password
"""
import os
import smtplib
import ssl
from email.mime_text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_gmail_with_app_password():
    """Отправка через Gmail с App Password"""
    
    # НАСТРОЙКИ GMAIL
    smtp_server = "smtp.gmail.com"
    smtp_port = 587  # основной путь: STARTTLS
    sender_email = "sbcargobot@gmail.com"
    
    # Берём App Password из переменных окружения; пробелы удаляем на всякий случай
    raw_app = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("SMTP_PASSWORD") or "PASTE_16_CHAR_APP_PASSWORD"
    app_password = (raw_app or "").replace(" ", "")

    # Адрес получателя можно переопределить переменной TEST_RECIPIENT
    recipient_email = os.getenv("TEST_RECIPIENT", "farm49595@gmail.com")
    
    # Создаем сообщение
    subject = "🧪 Тест Gmail App Password - KVT Bot"
    body = """
    <h2>📧 Письмо через Gmail App Password</h2>
    <p><strong>От:</strong> sbcargobot@gmail.com</p>
    <p><strong>Кому:</strong> farm49595@gmail.com</p>
    <p><strong>Способ:</strong> Gmail App Password</p>
    <hr>
    <p>✅ Если вы получили это письмо, значит Gmail работает!</p>
    """
    
    # Подготавливаем сообщение
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html', 'utf-8'))
    
    try:
        print("🔧 Конфигурация:")
        print(f"  SMTP: {smtp_server}:{smtp_port} (STARTTLS)")
        print(f"  From: {sender_email}")
        print(f"  To:   {recipient_email}")
        print(f"  AppPassword length: {len(app_password)} (пробелы удалены)")

        if len(app_password) != 16:
            print("⚠️ App Password должен быть 16 символов без пробелов. Проверьте GMAIL_APP_PASSWORD.")

        print("🔗 Подключаюсь к Gmail по 587 + STARTTLS...")
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=20)
        server.starttls(context=ssl.create_default_context())
        server.login(sender_email, app_password)
        print("📤 Отправляю письмо...")
        server.send_message(msg)
        server.quit()
        print("✅ Письмо отправлено успешно через 587/STARTTLS!")
        print(f"📧 От: {sender_email}")
        print(f"📧 Кому: {recipient_email}")
        return True

    except Exception as e1:
        print(f"⚠️ Ошибка через 587/STARTTLS: {e1}")
        print("🔁 Пробую через 465/SSL...")
        try:
            server = smtplib.SMTP_SSL(smtp_server, 465, context=ssl.create_default_context(), timeout=20)
            server.login(sender_email, app_password)
            server.send_message(msg)
            server.quit()
            print("✅ Письмо отправлено успешно через 465/SSL!")
            print(f"📧 От: {sender_email}")
            print(f"📧 Кому: {recipient_email}")
            return True
        except Exception as e2:
            print(f"❌ Ошибка и через 465/SSL: {e2}")
            print("\n💡 Проверьте:")
            print("1. Включена ли 2FA в Gmail")
            print("2. Создан ли App Password")
            print("3. Правильно ли скопирован App Password (без пробелов)")
            print("4. Открыты ли исходящие 587/465 с сервера/контейнера")
            return False

if __name__ == "__main__":
    print("🚀 Отправка через Gmail с App Password...")
    print("\n📋 Инструкция:")
    print("1. Зайдите в Gmail: sbcargobot@gmail.com")
    print("2. Включите 2FA: Google Account → Security → 2-Step Verification")
    print("3. Создайте App Password: Google Account → Security → App passwords")
    print("4. Замените YOUR_APP_PASSWORD_HERE на реальный пароль")
    print("5. Запустите скрипт снова")
    
    send_gmail_with_app_password()
