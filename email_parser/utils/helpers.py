"""
Helper functions for email parsing.

This module contains utility functions used across the email parser,
such as email address normalization, date parsing, and ID generation.
"""
import hashlib
import re
from datetime import datetime
import pytz
from email.utils import parseaddr, getaddresses
from typing import List, Optional


def generate_id(content, file_id=None, message_index=None):
    """
    Generate a stable ID for an email using file_id and optional index.
    
    Args:
        content: Email content string
        file_id: Source file identifier
        message_index: Optional index of the message within the file (for nested messages)
        
    Returns:
        A hex digest string representing the stable ID
    """
    import hashlib
    
    # If we have file_id, use it as the primary component
    if file_id:
        # Create a base ID from the file_id
        base_id = hashlib.md5(str(file_id).encode('utf-8')).hexdigest()[:16]
        
        # TODO: Add the index to the base_id if needed or for any edge cases.
        # Make all messages from the same file have the same ID (commented out)
        # Uncomment the following code if you want different IDs for main vs nested messages
        
        # If this is a nested message, add the index
        if message_index is not None:
            # Just return the same base_id for all messages
            # This ensures all messages from the same file have the same ID
            # If you want different IDs, use the commented line below instead
            # return f"{base_id}_n{message_index}"
            pass
        
        # For all messages in the file, just use the base_id
        return base_id
    
    # Fallback to content-based hash if no file_id is provided
    # Use a sample of content for efficiency
    if len(content) > 1000:
        # Sample beginning, middle and end
        beginning = content[:300]
        middle_start = max(0, len(content) // 2 - 150)
        middle = content[middle_start:middle_start + 300]
        end = content[max(0, len(content) - 300):]
        sample = beginning + middle + end
        return hashlib.md5(sample.encode('utf-8')).hexdigest()
    
    # For smaller content, hash it directly
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def extract_email_address(addr_str: str) -> str:
    """
    Extract email address from a string that might contain a name.
    
    Args:
        addr_str: String that may contain an email address with a display name
        
    Returns:
        The extracted email address in lowercase, or empty string if none found
    """
    if not addr_str:
        return ""
    _, email_addr = parseaddr(addr_str)
    return email_addr.lower() if email_addr else ""


def normalize_addresses(header_value: str) -> list:
    """
    Normalize email addresses to lowercase and remove duplicates.
    
    Handles various header formats and extracts all email addresses.
    
    Args:
        header_value: Email header value containing one or more addresses
        
    Returns:
        List of normalized email addresses
    """
    if not header_value:
        return []
    
    # Handle different header formats
    if isinstance(header_value, str):
        # Try to extract addresses with getaddresses for better handling of complex formats
        try:
            addresses = getaddresses([header_value])
            result = [extract_email_address(addr) for _, addr in addresses if addr]
        except:
            # Fallback to simpler splitting if getaddresses fails
            result = [extract_email_address(addr) for addr in re.split(r'[;,]', header_value) if addr.strip()]
    else:
        # Some email libraries might return an object instead of a string
        result = [extract_email_address(str(addr)) for addr in header_value]
    
    # Filter out empty strings and return unique addresses
    return [addr for addr in result if addr]


def clean_body(body: str) -> str:
    """
    Remove quoted content and signatures to get the clean message body.
    
    Args:
        body: The email body content
        
    Returns:
        Cleaned body content with quotations and signatures removed
    """
    if not body:
        return ""
    
    # Handle various quoting patterns
    patterns = [
        r"(From: .*?(\n|\r\n))",
        r"(On .* wrote:)",
        r"(-+Original Message-+)",
        r"(_{2,}|={2,}|-{2,})\s*\n+",  # Common signature separators
        r"(Forwarded by .*? on .*?-{2,})",  # Forwarded message headers
        r"(From:.*?To:.*?Subject:.*?(\n|\r\n))",  # Email headers in forwarded messages
    ]
    
    clean_text = body
    
    # Apply each pattern in sequence to clean the body
    for pattern in patterns:
        parts = re.split(pattern, clean_text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if parts and len(parts) > 1:
            clean_text = parts[0]
    
    return clean_text.strip()


def extract_header_from_text(text: str, header_name: str) -> str:
    """
    Extract header value from plain text.
    
    Args:
        text: Text containing headers
        header_name: Name of the header to extract
        
    Returns:
        Extracted header value or empty string if not found
    """
    pattern = rf"{header_name}:\s*(.*?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def extract_address_from_line(line: str) -> str:
    """
    Extract email address from a line that might contain an email in angle brackets.
    
    Args:
        line: Line of text that may contain an email address
        
    Returns:
        Extracted email address or empty string if none found
    """
    # Try to find an email in angle brackets
    email_match = re.search(r'<([^>]+)>', line)
    if email_match:
        return email_match.group(1).lower()
    
    # If no angle brackets, try to find anything that looks like an email
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', line)
    if email_match:
        return email_match.group(0).lower()
    
    return ""


def extract_date(header_date: str) -> Optional[str]:
    """
    Parse and normalize date to UTC ISO-8601 format.
    
    Args:
        header_date: Date string from email header
        
    Returns:
        Normalized date string in ISO format, or None if parsing fails
    """
    if not header_date:
        return None
    
    # Special case for Enron nested email format: MM/DD/YYYY HH:MM AM/PM
    enron_pattern = r'^(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?$'
    enron_match = re.match(enron_pattern, header_date.strip())
    if enron_match:
        try:
            date_part, hour, minute, second, ampm = enron_match.groups()
            
            # Convert to 24-hour format if needed
            hour = int(hour)
            if ampm and ampm.upper() == 'PM' and hour < 12:
                hour += 12
            elif ampm and ampm.upper() == 'AM' and hour == 12:
                hour = 0
            
            # Create datetime object
            month, day, year = map(int, date_part.split('/'))
            second = int(second) if second else 0
            
            dt = datetime(year, month, day, hour, int(minute), second)
            
            # Add timezone (assuming US/Central for Enron)
            central = pytz.timezone('US/Central')
            dt = central.localize(dt)
            
            # Convert to UTC
            dt = dt.astimezone(pytz.UTC)
            
            return dt.isoformat()
        except Exception:
            pass
    
    # Common date formats in emails
    date_formats = [
        # Standard email formats
        '%a, %d %b %Y %H:%M:%S %z',
        '%d %b %Y %H:%M:%S %z',
        '%a, %d %b %Y %H:%M:%S',
        '%d %b %Y %H:%M:%S',
        
        # Enron-specific formats
        '%m/%d/%Y %I:%M:%S %p',  # MM/DD/YYYY HH:MM:SS AM/PM
        '%m/%d/%Y %H:%M:%S',      # MM/DD/YYYY HH:MM:SS (24-hour)
        '%m/%d/%Y %I:%M %p',      # MM/DD/YYYY HH:MM AM/PM (without seconds)
        '%m/%d/%Y %H:%M',         # MM/DD/YYYY HH:MM (without seconds, 24-hour)
        
        # Short date formats
        '%m/%d/%y %I:%M:%S %p',   # MM/DD/YY HH:MM:SS AM/PM
        '%m/%d/%y %H:%M:%S',      # MM/DD/YY HH:MM:SS (24-hour)
        '%m/%d/%y %I:%M %p',      # MM/DD/YY HH:MM AM/PM (without seconds)
        '%m/%d/%y %H:%M',         # MM/DD/YY HH:MM (without seconds, 24-hour)
    ]
    
    # Try each format until one works
    for fmt in date_formats:
        try:
            # Remove any trailing text after the date that might cause parsing issues
            # This helps with formats like "10/06/2000 06:59 AM To:"
            if ' To:' in header_date:
                header_date = header_date.split(' To:')[0].strip()
                
            # Handle specific Enron formats
            if 'AM' in header_date or 'PM' in header_date:
                # Extract the date part and normalize
                match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM))', header_date)
                if match:
                    header_date = match.group(1)
            
            date_str = header_date.strip()
            dt = datetime.strptime(date_str, fmt)
            
            # Add UTC timezone if not specified
            if dt.tzinfo is None:
                # Assuming Enron emails are in US Central Time
                central = pytz.timezone('US/Central')
                dt = central.localize(dt)
                # Convert to UTC
                dt = dt.astimezone(pytz.UTC)
                
            return dt.isoformat()
        except Exception:
            continue
    
    # If standard parsing fails, try to extract date using regex
    try:
        # Look for Enron-style date patterns (broader match)
        match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?', header_date)
        if match:
            date_part, hour, minute, second, ampm = match.groups()
            
            # Convert to 24-hour format if needed
            hour = int(hour)
            if ampm and ampm.upper() == 'PM' and hour < 12:
                hour += 12
            elif ampm and ampm.upper() == 'AM' and hour == 12:
                hour = 0
            
            # Create datetime object
            month, day, year = map(int, date_part.split('/'))
            second = int(second) if second else 0
            
            dt = datetime(year, month, day, hour, int(minute), second)
            
            # Add timezone (assuming US/Central for Enron)
            central = pytz.timezone('US/Central')
            dt = central.localize(dt)
            
            # Convert to UTC
            dt = dt.astimezone(pytz.UTC)
            
            return dt.isoformat()
    except Exception:
        pass
    
    # If all parsing attempts fail
    return None


def process_recipients(recipient_line: str, recipient_list: list) -> None:
    """
    Process a line containing email recipients and add them to the recipient list.
    Handles various Enron email formats.
    
    Args:
        recipient_line: Line containing recipients
        recipient_list: List to append the extracted email addresses to
    """
    if not recipient_line:
        return
    
    # First try to extract standard email format with angle brackets
    standard_emails = []
    email_matches = re.finditer(r'<([^>]+)>', recipient_line)
    for match in email_matches:
        email = match.group(1).lower()
        if '@' in email:
            standard_emails.append(email)
    
    # If we found standard emails, use them
    if standard_emails:
        recipient_list.extend(standard_emails)
    else:
        # Otherwise split and process each address separately
        # This handles Enron's internal format with commas as separators
        for part in re.split(r',\s*', recipient_line):
            part = part.strip()
            if not part:
                continue
                
            # Check for direct email format
            if '@' in part and not part.endswith('@Enron') and not part.endswith('@ECT'):
                recipient_list.append(part.lower())
            else:
                # Handle Enron internal format (Name/Department/Enron@Enron)
                # Extract just the name part before any slashes
                name_parts = part.split('/')
                if name_parts and len(name_parts) >= 1:
                    name = name_parts[0].strip()
                    if name and not name.lower().startswith(('to:', 'cc:')):
                        # Convert Enron internal format to email format
                        recipient_list.append(name.lower().replace(' ', '.') + '@enron.com') 