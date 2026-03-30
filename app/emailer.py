import smtplib
from email.mime.text import MIMEText
from .config import settings


def send_email(subject: str, body: str, to: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to

    if settings.smtp_user and settings.smtp_password:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        try:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, [to], msg.as_string())
        finally:
            server.quit()
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.sendmail(settings.smtp_from, [to], msg.as_string())
