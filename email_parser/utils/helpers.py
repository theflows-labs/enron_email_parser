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
        # # If this is a nested message, add the index
        # if message_index is not None:
        #     # Format: base_id + '_n' + index (n for nested)
        #     return f"{base_id}_n{message_index}"
        
        # For the main message in the file, just use the base_id
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
    
    # Common date formats in emails
    date_formats = [
        '%a, %d %b %Y %H:%M:%S %z',
        '%d %b %Y %H:%M:%S %z',
        '%a, %d %b %Y %H:%M:%S',
        '%d %b %Y %H:%M:%S',
        '%m/%d/%Y %I:%M:%S %p',  # MM/DD/YYYY HH:MM:SS AM/PM (Enron format)
    ]
    
    # Try each format until one works
    for fmt in date_formats:
        try:
            # Limit to first 31 chars which should contain the date part
            date_str = header_date[:31] if len(header_date) > 31 else header_date
            dt = datetime.strptime(date_str, fmt)
            
            # Add UTC timezone if not specified
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pytz.UTC)
            else:
                # Convert to UTC
                dt = dt.astimezone(pytz.UTC)
                
            return dt.isoformat()
        except:
            continue
    
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