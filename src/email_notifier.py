import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os

def load_config():
    config_path = 'config.json'
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

from email.mime.application import MIMEApplication

def send_email_report(report_text, attachment_paths=None):
    """
    Отправляет отчет на email, используя настройки из config.json.
    
    Args:
        report_text (str): Текст отчета для отправки
        attachment_paths (str or list, optional): Путь или список путей к файлам для вложения
    """
    config = load_config()
    email_config = config.get('email', {})
    
    sender_email = email_config.get('sender_email')
    sender_password = email_config.get('sender_password')
    recipient_email = email_config.get('recipient_email')
    smtp_server = email_config.get('smtp_server', 'smtp.gmail.com')
    smtp_port = email_config.get('smtp_port', 587)
    
    if not sender_email or not sender_password or not recipient_email:
        print("⚠️ Email settings missing in config.json. Email not sent.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = "Отчет по отзывам 2GIS"

        msg.attach(MIMEText(report_text, 'plain'))
        
        if attachment_paths:
            if isinstance(attachment_paths, str):
                attachment_paths = [attachment_paths]
                
            for path in attachment_paths:
                if os.path.exists(path):
                    try:
                        with open(path, 'rb') as f:
                            part = MIMEApplication(f.read(), Name=os.path.basename(path))
                        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                        msg.attach(part)
                        print(f"Attached file: {path}")
                    except Exception as e:
                        print(f"Failed to attach file {path}: {e}")
                else:
                    print(f"Attachment not found: {path}")

        print(f"Connecting to SMTP server {smtp_server}:{smtp_port}...")
        
        if smtp_port == 465:
            # SSL connection
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            # TLS connection
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        print("Email report sent successfully!")
        
    except Exception as e:
        print(f"Failed to send email: {e}")
