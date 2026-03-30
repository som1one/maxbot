#!/usr/bin/env python3
"""
External Email Services - использование внешних сервисов для отправки email
"""
import requests
import os
import logging

class EmailService:
    def __init__(self):
        self.services = {
            "sendgrid": self.sendgrid_send,
            "mailgun": self.mailgun_send,
            "ses": self.ses_send,
            "resend": self.resend_send
        }
    
    def sendgrid_send(self, to_email, subject, body):
        """SendGrid API"""
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {os.getenv('SENDGRID_API_KEY')}",
            "Content-Type": "application/json"
        }
        data = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": "sbcargobot@gmail.com"},
            "subject": subject,
            "content": [{"type": "text/html", "value": body}]
        }
        return requests.post(url, json=data, headers=headers)
    
    def mailgun_send(self, to_email, subject, body):
        """Mailgun API"""
        url = f"https://api.mailgun.net/v3/{os.getenv('MAILGUN_DOMAIN')}/messages"
        auth = ("api", os.getenv('MAILGUN_API_KEY'))
        data = {
            "from": "sbcargobot@gmail.com",
            "to": to_email,
            "subject": subject,
            "html": body
        }
        return requests.post(url, auth=auth, data=data)
    
    def ses_send(self, to_email, subject, body):
        """AWS SES API"""
        import boto3
        client = boto3.client('ses', region_name='us-east-1')
        return client.send_email(
            Source="sbcargobot@gmail.com",
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Html": {"Data": body}}
            }
        )
    
    def resend_send(self, to_email, subject, body):
        """Resend API"""
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {os.getenv('RESEND_API_KEY')}",
            "Content-Type": "application/json"
        }
        data = {
            "from": "sbcargobot@gmail.com",
            "to": [to_email],
            "subject": subject,
            "html": body
        }
        return requests.post(url, json=data, headers=headers)
    
    def send_email(self, to_email, subject, body):
        """Попробовать все сервисы по очереди"""
        for service_name, service_func in self.services.items():
            try:
                result = service_func(to_email, subject, body)
                if hasattr(result, 'status_code') and result.status_code in [200, 201]:
                    logging.info(f"Email sent via {service_name}")
                    return True
            except Exception as e:
                logging.warning(f"{service_name} failed: {e}")
                continue
        
        logging.error("All email services failed")
        return False

# Использование
email_service = EmailService()
