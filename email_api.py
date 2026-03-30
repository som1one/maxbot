#!/usr/bin/env python3
"""
Simple Email API - HTTP сервис для отправки email
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

app = FastAPI()

# Настройки SMTP
SMTP_CONFIGS = [
    {"host": "smtp.gmail.com", "port": 587, "use_tls": True},
    {"host": "smtp.gmail.com", "port": 465, "use_ssl": True},
    {"host": "smtp.mail.ru", "port": 465, "use_ssl": True},
    {"host": "smtp.yandex.ru", "port": 465, "use_ssl": True},
]

class EmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    from_email: str = "sbcargobot@gmail.com"
    from_password: str = os.getenv("SMTP_PASSWORD", "1Qqazxsw55")

@app.post("/send-email")
async def send_email(request: EmailRequest):
    """Отправка email через Gmail App Password (рабочий метод)"""
    
    try:
        # Gmail settings using App Password
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = request.from_email
        
        # Use Gmail App Password from environment
        app_password = os.getenv("GMAIL_APP_PASSWORD", request.from_password)
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = request.to
        msg['Subject'] = request.subject
        msg.attach(MIMEText(request.body, 'html', 'utf-8'))
        
        logging.info("🔗 Подключаюсь к Gmail...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Enable encryption
        server.login(sender_email, app_password)  # Use App Password
        
        logging.info("📤 Отправляю письмо...")
        server.send_message(msg)
        server.quit()
        
        logging.info("✅ Email sent successfully via Gmail App Password!")
        logging.info(f"📧 От: {sender_email}")
        logging.info(f"📧 Кому: {request.to}")
        
        return {
            "status": "success",
            "message": "Email sent via Gmail App Password",
            "method": "Gmail App Password"
        }
        
    except Exception as e:
        logging.error(f"❌ Gmail App Password method failed: {e}")
        logging.error("💡 Проверьте:")
        logging.error("1. Включена ли 2FA в Gmail")
        logging.error("2. Создан ли App Password")
        logging.error("3. Правильно ли скопирован App Password")
        
        # Fallback to local MailHog
        try:
            logging.info("Trying local MailHog as fallback")
            server = smtplib.SMTP("mailhog", 1025, timeout=5)
            server.sendmail(request.from_email, request.to, msg.as_string())
            server.quit()
            logging.info("✅ Email sent via local MailHog")
            return {
                "status": "success",
                "message": "Email sent via MailHog",
                "method": "MailHog"
            }
        except Exception as mailhog_e:
            logging.warning(f"MailHog fallback failed: {mailhog_e}")
    
    raise HTTPException(status_code=500, detail="All email methods failed")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
