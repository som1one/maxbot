#!/usr/bin/env python3
"""
Email Utilities - различные способы отправки email
"""
import smtplib
import requests
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

class EmailSender:
    def __init__(self):
        self.smtp_user = os.getenv("SMTP_USER", "sbcargobot@gmail.com")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "1Qqazxsw55")
        self.admin_email = os.getenv("DEFAULT_NOTIFICATION_EMAIL", "sb@sbcargo.ru")
        self.email_enabled = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
    
    def send_via_http_api(self, subject: str, body: str, to_email: str):
        """Отправка через HTTP API"""
        try:
            api_url = "http://email-api:8001/send-email"
            data = {
                "to": to_email,
                "subject": subject,
                "body": body,
                "from_email": self.smtp_user,
                "from_password": self.smtp_password
            }
            
            response = requests.post(api_url, json=data, timeout=10)
            if response.status_code == 200:
                logging.info("Email sent via HTTP API")
                return True
        except Exception as e:
            logging.warning(f"HTTP API failed: {e}")
        return False
    
    def send_via_smtp(self, subject: str, body: str, to_email: str):
        """Отправка через SMTP"""
        try:
            # Prepare message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            text = msg.as_string()
            
            # Try different SMTP servers
            smtp_configs = [
                ("smtp.gmail.com", 587, "starttls"),
                ("smtp.gmail.com", 465, "ssl"),
                ("smtp.mail.ru", 465, "ssl"),
                ("smtp.yandex.ru", 465, "ssl"),
                ("mailhog", 1025, "plain")
            ]
            
            for host, port, method in smtp_configs:
                server = None
                try:
                    logging.info(f"Trying {method} connection to {host}:{port}")
                    
                    if method == "ssl":
                        server = smtplib.SMTP_SSL(host, port, timeout=10)
                    elif method == "starttls":
                        server = smtplib.SMTP(host, port, timeout=10)
                        server.ehlo()
                        server.starttls()
                        server.ehlo()
                    else:  # plain
                        server = smtplib.SMTP(host, port, timeout=10)
                        server.ehlo()
                    
                    if method != "plain":
                        server.login(self.smtp_user, self.smtp_password)
                    
                    server.sendmail(self.smtp_user, to_email, text)
                    server.quit()
                    logging.info(f"Email sent via {host}:{port}")
                    return True
                    
                except Exception as e:
                    logging.warning(f"SMTP {host}:{port} failed: {e}")
                    if server:
                        try:
                            server.quit()
                        except:
                            pass
                    continue
        except Exception as e:
            logging.warning(f"SMTP method failed: {e}")
        return False
    
    def send_via_external_service(self, subject: str, body: str, to_email: str):
        """Отправка через внешние сервисы"""
        try:
            # SendGrid
            sendgrid_data = {
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": self.smtp_user},
                "subject": subject,
                "content": [{"type": "text/html", "value": body}]
            }
            
            sendgrid_url = "https://api.sendgrid.com/v3/mail/send"
            sendgrid_headers = {
                "Authorization": f"Bearer {os.getenv('SENDGRID_API_KEY', '')}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(sendgrid_url, json=sendgrid_data, headers=sendgrid_headers, timeout=10)
            if response.status_code in [200, 201]:
                logging.info("Email sent via SendGrid")
                return True
        except Exception as e:
            logging.warning(f"SendGrid failed: {e}")
        
        try:
            # Mailgun
            mailgun_url = f"https://api.mailgun.net/v3/{os.getenv('MAILGUN_DOMAIN', '')}/messages"
            mailgun_auth = ("api", os.getenv('MAILGUN_API_KEY', ''))
            mailgun_data = {
                "from": self.smtp_user,
                "to": to_email,
                "subject": subject,
                "html": body
            }
            
            response = requests.post(mailgun_url, auth=mailgun_auth, data=mailgun_data, timeout=10)
            if response.status_code in [200, 201]:
                logging.info("Email sent via Mailgun")
                return True
        except Exception as e:
            logging.warning(f"Mailgun failed: {e}")
        
        return False
    
    def send_email(self, subject: str, body: str, to_email: str = None):
        """Основная функция отправки email с множественными fallback"""
        if not self.email_enabled:
            logging.info("Email notifications are disabled")
            return False
        
        if to_email is None:
            to_email = self.admin_email
        
        logging.info(f"Attempting to send email to {to_email} from {self.smtp_user}")
        
        # Method 1: HTTP API
        if self.send_via_http_api(subject, body, to_email):
            return True
        
        # Method 2: Direct SMTP
        if self.send_via_smtp(subject, body, to_email):
            return True
        
        # Method 3: External services
        if self.send_via_external_service(subject, body, to_email):
            return True
        
        logging.error("All email methods failed")
        return False

# Глобальный экземпляр
email_sender = EmailSender()
