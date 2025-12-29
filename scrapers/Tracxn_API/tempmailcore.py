import time
import uuid
import re
from typing import Optional, Dict, Any, Union, Iterable

from temp_mail_so import TempMailSo
from config import RAPID_API_KEY, TEMPMAIL_TOKEN


class EmailInbox:
    """Wrapper around TempMailSo to create a new inbox and wait for incoming mail.

    Usage contract:
    - get_new_mailbox(domain="swiftfynd.net") -> dict: returns inbox metadata
    - get_mail(inbox_or_id, timeout=60) -> dict: waits until an email appears and
      returns the email content (first message) or raises TimeoutError.

    This class makes reasonable attempts to fetch full message content by calling
    `list_emails` and `get_email` (if available on the client).
    """

    def __init__(
        self,
        rapid_api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        client: Optional[TempMailSo] = None,
    ) -> None:
        if client is not None:
            self.client = client
        else:
            self.client = TempMailSo(
                rapid_api_key=rapid_api_key or RAPID_API_KEY,
                auth_token=auth_token or TEMPMAIL_TOKEN,
            )

    def get_new_mailbox(
        self, domain: str = "swiftfynd.net", address: Optional[str] = None, lifespan: int = 300
    ) -> str:
        """Create a new temporary inbox and return the email address.

        Args:
            domain: domain to use for the inbox (default: 'swiftfynd.net')
            address: optional local-part; if omitted a random prefix is generated
            lifespan: inbox lifetime in seconds (0 may mean permanent depending on API)

        Returns:
            The email address string (e.g., "tmp_abc123@swiftfynd.net")
        """
        if not address:
            address = f"{uuid.uuid4().hex[:14]}"

        inbox = self.client.create_inbox(address=address, domain=domain, lifespan=lifespan)
        # Store the inbox metadata for later use by get_mail
        self._last_inbox = inbox
        return f"{address}@{domain}"

    def _resolve_inbox_id(self, inbox: Union[str, Dict[str, Any]]) -> str:
        if isinstance(inbox, str):
            return inbox
        # Try common keys at top level and nested under 'data'
        if isinstance(inbox, dict):
            for key in ("id", "inbox_id", "mailbox_id"):
                if key in inbox:
                    return inbox[key]
            # Check nested under 'data' key (common API pattern)
            if "data" in inbox and isinstance(inbox["data"], dict):
                for key in ("id", "inbox_id", "mailbox_id"):
                    if key in inbox["data"]:
                        return inbox["data"][key]
        raise ValueError(f"Could not determine inbox id from provided value: {inbox}")

    def _extract_verification_code(self, email_data: Dict[str, Any]) -> Optional[str]:
        """Extract verification code from email subject or body.
        
        Args:
            email_data: Email message data dict
            
        Returns:
            Verification code string if found, None otherwise
        """
        # Common patterns for verification codes (4-8 digits)
        code_patterns = [
            r'\b(\d{4,8})\s+is\s+your\s+.*(?:verification|confirmation|code)',  # "179216 is your verification code"
            r'(?:verification|confirmation|code)[\s:]*(\d{4,8})',  # "verification code: 179216"
            r'(?:code|otp)[\s:]*(\d{4,8})',  # "code: 179216"
            r'\b(\d{6})\b',  # standalone 6-digit codes (common for OTP)
        ]
        
        # Check subject first
        subject = email_data.get('subject', '')
        if subject:
            for pattern in code_patterns:
                match = re.search(pattern, subject, re.IGNORECASE)
                if match:
                    return match.group(1)
        
        # Check body/text content
        for body_key in ('body', 'text', 'html', 'content'):
            body = email_data.get(body_key, '')
            if body:
                for pattern in code_patterns:
                    match = re.search(pattern, str(body), re.IGNORECASE)
                    if match:
                        return match.group(1)
        
        return None

    def get_mail(
        self,
        inbox: Union[str, Dict[str, Any]],
        timeout: int = 60,
        poll_interval: float = 2.0,
    ) -> str:
        """Wait until a mail arrives in the given inbox and return the verification code.

        Args:
            inbox: inbox id string, email address, or inbox metadata dict returned by create_inbox
            timeout: seconds to wait before raising TimeoutError
            poll_interval: seconds between polling attempts

        Returns:
            The verification code extracted from the email (e.g., "179216").

        Raises:
            TimeoutError: if no mail arrives within `timeout` seconds.
            ValueError: if no verification code could be extracted from the email.
        """
        # If inbox is an email address, try to use the last created inbox
        if isinstance(inbox, str) and "@" in inbox:
            if hasattr(self, '_last_inbox') and self._last_inbox:
                inbox_id = self._resolve_inbox_id(self._last_inbox)
            else:
                raise ValueError("Email address provided but no inbox metadata available. Use inbox metadata or inbox ID instead.")
        else:
            inbox_id = self._resolve_inbox_id(inbox)
        end_time = time.time() + timeout

        while time.time() < end_time:
            try:
                emails = self.client.list_emails(inbox_id=inbox_id)
            except Exception:
                # Don't fail fast for occasional transient errors; wait and retry
                emails = None

            if emails:
                # If the client returned an iterable of messages, pick the first
                if isinstance(emails, dict):
                    # Some APIs might return a dict with a 'data' or 'items' key
                    for candidate_key in ("data", "items", "emails"):
                        if candidate_key in emails and isinstance(emails[candidate_key], Iterable):
                            emails_list = list(emails[candidate_key])
                            break
                    else:
                        emails_list = [emails]
                else:
                    try:
                        emails_list = list(emails)
                    except TypeError:
                        emails_list = [emails]

                if emails_list:
                    first = emails_list[0]
                    # If full message content is not present, try to fetch it
                    if isinstance(first, dict) and not any(k in first for k in ("body", "text", "html", "raw")):
                        msg_id = first.get("id") or first.get("message_id")
                        if msg_id and hasattr(self.client, "get_email"):
                            try:
                                full = self.client.get_email(email_id=msg_id)
                                code = self._extract_verification_code(full)
                                if code:
                                    return code
                                # If no code found in full message, try the summary
                                code = self._extract_verification_code(first)
                                if code:
                                    return code
                            except Exception:
                                # fallback to checking the summary we have
                                pass
                    
                    # Try to extract code from the email summary
                    code = self._extract_verification_code(first)
                    if code:
                        return code

            time.sleep(poll_interval)

        raise TimeoutError(f"No email with verification code arrived in inbox {inbox_id} within {timeout} seconds")



