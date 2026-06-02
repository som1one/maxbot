import logging
import smtplib
import ssl
from email.mime.text import MIMEText

from .config import settings


def send_email(subject: str, body: str, to: str) -> bool:
    if not settings.email_enabled:
        logging.info("Email notifications are disabled; skipping backend email send")
        return False

    if not to:
        logging.warning("Notification email is not configured; skipping backend email send")
        return False

    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = settings.resolved_smtp_from
    message["To"] = to

    password = settings.smtp_login_password
    timeout = 20

    try:
        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=timeout)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
            if settings.smtp_user and password:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()

        try:
            if settings.smtp_user and password:
                server.login(settings.smtp_user, password)
            server.sendmail(settings.resolved_smtp_from, [to], message.as_string())
            return True
        finally:
            server.quit()
    except Exception:
        logging.exception("Backend email delivery failed")
        return False
