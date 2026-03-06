import requests
import json
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class PhilSMSService:
    def __init__(self):
        self.api_url = settings.PHILSMS_API_URL
        self.token = settings.PHILSMS_API_TOKEN
        self.sender_id = settings.PHILSMS_SENDER_ID
        self.message_type = settings.PHILSMS_MESSAGE_TYPE

    def send_sms(self, phone_number, message):
        # Clean phone number to format 63XXXXXXXXXX
        phone = self._clean_phone(phone_number)

        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        payload = {
            'recipient': phone,
            'sender_id': self.sender_id,
            'type': self.message_type,
            'message': message,
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()

            if result.get('status') == 'success':
                logger.info(f"SMS sent to {phone}: {message[:30]}...")
                return True, result
            else:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"SMS API error: {error_msg}")
                return False, error_msg

        except requests.exceptions.RequestException as e:
            logger.error(f"SMS request failed: {e}")
            return False, str(e)

    def _clean_phone(self, phone):
        """Convert Philippine mobile number to 63 format."""
        # Remove all non-digits
        digits = ''.join(filter(str.isdigit, phone))
        # If it starts with 0, replace with 63
        if digits.startswith('0'):
            digits = '63' + digits[1:]
        # If it's 10 digits (e.g., 9123456789), add 63
        elif len(digits) == 10:
            digits = '63' + digits
        # If it already starts with 63, keep as is
        return digits