"""
HelpChain SMS Service
Handles sending notification SMS messages
"""

import requests
import logging
from flask import current_app

logger = logging.getLogger(__name__)


def send_notification_sms(phone, message):
    """
    Send SMS notification to phone number

    Args:
        phone (str): Phone number in international format
        message (str): SMS message content

    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        if not phone or not message:
            logger.warning("Missing phone or message for SMS")
            return False

        # Clean phone number
        phone = _clean_phone_number(phone)

        # Check if SMS is enabled in config
        sms_config = current_app.config.get("SMS_CONFIG", {})
        if not sms_config.get("enabled", False):
            logger.info(f"SMS disabled, would send to {phone}: {message}")
            return True  # Return True for testing when disabled

        # Choose SMS provider
        provider = sms_config.get("provider", "mock")

        if provider == "mock":
            return _send_mock_sms(phone, message)
        elif provider == "twilio":
            return _send_twilio_sms(phone, message, sms_config)
        elif provider == "nexmo":
            return _send_nexmo_sms(phone, message, sms_config)
        else:
            logger.error(f"Unknown SMS provider: {provider}")
            return False

    except Exception as e:
        logger.error(f"Failed to send SMS to {phone}: {e}")
        return False


def _clean_phone_number(phone):
    """Clean and format phone number"""
    if not phone:
        return phone

    # Remove all non-digit characters
    phone = "".join(filter(str.isdigit, phone))

    # Add country code if missing (assuming Bulgaria +359)
    if phone.startswith("0"):
        phone = "359" + phone[1:]
    elif not phone.startswith("359"):
        phone = "359" + phone

    return phone


def _send_mock_sms(phone, message):
    """Mock SMS sending for testing"""
    logger.info(f"MOCK SMS to {phone}: {message}")

    # Simulate success/failure randomly for testing
    import random

    success = random.choice([True, True, True, False])  # 75% success rate

    if success:
        logger.info("Mock SMS sent successfully")
    else:
        logger.warning("Mock SMS failed (simulated)")

    return success


def _send_twilio_sms(phone, message, config):
    """Send SMS via Twilio"""
    try:
        account_sid = config.get("twilio_account_sid")
        auth_token = config.get("twilio_auth_token")
        from_number = config.get("twilio_from_number")

        if not all([account_sid, auth_token, from_number]):
            logger.error("Twilio configuration incomplete")
            return False

        from twilio.rest import Client

        client = Client(account_sid, auth_token)

        message = client.messages.create(body=message, from_=from_number, to=phone)

        logger.info(f"Twilio SMS sent: {message.sid}")
        return True

    except ImportError:
        logger.error("Twilio not installed. Install with: pip install twilio")
        return False
    except Exception as e:
        logger.error(f"Twilio SMS failed: {e}")
        return False


def _send_nexmo_sms(phone, message, config):
    """Send SMS via Nexmo/Vonage"""
    try:
        api_key = config.get("nexmo_api_key")
        api_secret = config.get("nexmo_api_secret")
        from_number = config.get("nexmo_from_number", "HelpChain")

        if not all([api_key, api_secret]):
            logger.error("Nexmo configuration incomplete")
            return False

        # Nexmo API call
        url = "https://rest.nexmo.com/sms/json"
        data = {
            "api_key": api_key,
            "api_secret": api_secret,
            "to": phone,
            "from": from_number,
            "text": message,
        }

        response = requests.post(url, data=data, timeout=10)
        result = response.json()

        if result.get("messages", [{}])[0].get("status") == "0":
            logger.info(f"Nexmo SMS sent successfully to {phone}")
            return True
        else:
            logger.error(f"Nexmo SMS failed: {result}")
            return False

    except Exception as e:
        logger.error(f"Nexmo SMS error: {e}")
        return False


def send_bulk_sms(phone_numbers, message):
    """
    Send SMS to multiple phone numbers

    Args:
        phone_numbers (list): List of phone numbers
        message (str): SMS message

    Returns:
        dict: Results with success count and failures
    """
    results = {
        "total": len(phone_numbers),
        "successful": 0,
        "failed": 0,
        "failures": [],
    }

    for phone in phone_numbers:
        success = send_notification_sms(phone, message)
        if success:
            results["successful"] += 1
        else:
            results["failed"] += 1
            results["failures"].append(phone)

    logger.info(f"Bulk SMS sent: {results['successful']}/{results['total']} successful")
    return results


def send_urgent_sms(phone, category, address, emergency_phone=None):
    """
    Send urgent help request SMS

    Args:
        phone (str): Volunteer phone number
        category (str): Help category
        address (str): Location address
        emergency_phone (str): Emergency contact phone

    Returns:
        bool: True if sent successfully
    """
    message = f"СПЕШНО HelpChain: {category} на {address}."
    if emergency_phone:
        message += f" Тел:{emergency_phone}"

    return send_notification_sms(phone, message)


def send_volunteer_assigned_sms(phone, volunteer_name, eta=None):
    """
    Send SMS when volunteer is assigned

    Args:
        phone (str): Requester phone number
        volunteer_name (str): Volunteer name
        eta (str): Estimated time of arrival

    Returns:
        bool: True if sent successfully
    """
    message = f"HelpChain: {volunteer_name} е готов да помогне."
    if eta:
        message += f" Очаквано време: {eta}."

    return send_notification_sms(phone, message)


def send_task_completed_sms(phone, task_title):
    """
    Send SMS when task is completed

    Args:
        phone (str): Requester phone number
        task_title (str): Task title

    Returns:
        bool: True if sent successfully
    """
    message = f"HelpChain: Задачата '{task_title}' е завършена успешно."

    return send_notification_sms(phone, message)


# SMS configuration template for settings
SMS_CONFIG_TEMPLATE = {
    "enabled": False,
    "provider": "mock",  # 'mock', 'twilio', 'nexmo'
    "twilio_account_sid": "",
    "twilio_auth_token": "",
    "twilio_from_number": "",
    "nexmo_api_key": "",
    "nexmo_api_secret": "",
    "nexmo_from_number": "HelpChain",
}
