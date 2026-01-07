import imaplib
import email
from email.header import decode_header

def get_last_gmail_imap(email_address, password):
    """Get last Gmail message using IMAP"""
    
    # Connect to Gmail IMAP
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    
    # Login
    imap.login(email_address, password)
    
    # Select inbox
    imap.select("INBOX")
    
    # Search for all messages
    status, messages = imap.search(None, "ALL")
    
    # Get list of message IDs
    message_ids = messages[0].split()
    
    if not message_ids:
        print("No messages found")
        return None
    
    # Get the last message ID
    latest_email_id = message_ids[-1]
    
    # Fetch the email
    status, msg_data = imap.fetch(latest_email_id, "(RFC822)")
    
    # Parse the email
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            
            # Decode subject
            subject = decode_header(msg["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()
            
            sender = msg.get("From")
            date = msg.get("Date")
            
            print(f"From: {sender}")
            print(f"Subject: {subject}")
            print(f"Date: {date}")
            
            # Get body
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        print(f"\nBody:\n{body[:500]}...")
                        break
            else:
                body = msg.get_payload(decode=True).decode()
                print(f"\nBody:\n{body[:500]}...")
            
            return {
                'from': sender,
                'subject': subject,
                'date': date,
                'body': body
            }
    
    imap.close()
    imap.logout()

# Usage
get_last_gmail_imap("hosseinmousavi199706@gmail.com", "eawnivheoztsmoag")