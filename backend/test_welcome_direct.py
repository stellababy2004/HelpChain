#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Директен тест на welcome имейл функцията
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime

# Зареждаме environment променливи
from dotenv import load_dotenv
load_dotenv()

def test_welcome_email():
    """Тестваме welcome имейла директно"""
    try:
        print("🔧 Тестваме welcome имейл функционалността...")
        
        # Фалшиви данни за тест
        volunteer_name = "Тест Потребител"
        volunteer_email = "stella4889@hotmail.com"  # Заменете с реален имейл за тест
        volunteer_location = "София"
        
        # Четем HTML template
        welcome_template_path = os.path.join('email_templates', 'volunteer_welcome.html')
        if os.path.exists(welcome_template_path):
            with open(welcome_template_path, 'r', encoding='utf-8') as f:
                html_body = f.read()
                # Заменяме плейсхолдърите
                html_body = html_body.replace('{{volunteer_name}}', volunteer_name)
                html_body = html_body.replace('{{volunteer_email}}', volunteer_email)
                html_body = html_body.replace('{{volunteer_location}}', volunteer_location)
        else:
            print("❌ Welcome template не е намерен!")
            return False
            
        subject = f"🎉 Добре дошли в HelpChain.bg, {volunteer_name}!"
        
        # SMTP настройки
        smtp_server = os.getenv('MAIL_SERVER', 'smtp.zoho.eu')
        smtp_port = int(os.getenv('MAIL_PORT', 465))
        smtp_username = os.getenv('MAIL_USERNAME')
        smtp_password = os.getenv('MAIL_PASSWORD')
        smtp_sender = os.getenv('MAIL_DEFAULT_SENDER')
        
        print(f"📧 SMTP сървър: {smtp_server}:{smtp_port}")
        print(f"📧 От: {smtp_sender}")
        print(f"📧 До: {volunteer_email}")
        
        # Създаваме имейл съобщението
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_sender
        msg['To'] = volunteer_email
        msg['Subject'] = Header(subject, 'utf-8').encode()
        
        # Прикачваме HTML съдържанието
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        # Изпращаме
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        print("✅ Welcome имейл изпратен успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Грешка при изпращане: {str(e)}")
        return False

if __name__ == "__main__":
    test_welcome_email()