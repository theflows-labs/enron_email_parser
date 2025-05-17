"""
Content extraction module for email parsing.

This module contains functions to extract forwarded or nested email content
from email bodies, including identifying and parsing quoted content.
"""
import re
from typing import List

from email_parser.utils.helpers import clean_body


def extract_original_email(body: str) -> List[str]:
    """
    Extract forwarded/nested email content from an email body.
    
    This function looks for various patterns that indicate forwarded
    or nested email content within the body text.
    
    Args:
        body: Email body text
        
    Returns:
        List of extracted forwarded email content strings
    """
    if not body:
        return []
    
    forwarded_emails = []
    
    # Look for the standard Enron forwarded message marker
    try:
        # Find the start markers for forwarded emails
        forward_markers = []
        
        # Pattern 1: Standard dashed line with "Forwarded by" text
        pattern1 = r"-+\s*Forwarded by.+?-+\s*\n\n"
        for match in re.finditer(pattern1, body, re.MULTILINE | re.DOTALL):
            forward_markers.append(match.end())
        
        # Pattern 2: From: header in the middle of the body
        pattern2 = r"\n\nFrom:"
        for match in re.finditer(pattern2, body):
            forward_markers.append(match.end() - 5)  # Start after the newlines but before "From:"
        
        # Pattern 3: "Original Message" divider
        pattern3 = r"-+\s*Original Message\s*-+\s*\n"
        for match in re.finditer(pattern3, body, re.MULTILINE):
            forward_markers.append(match.end())
        
        # Pattern 4: Names with dates in Enron format
        pattern4 = r"\n\n([A-Za-z][A-Za-z\s]+)\n(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\s+[AP]M)\nTo:"
        for match in re.finditer(pattern4, body, re.MULTILINE):
            # Start at the beginning of the name
            forward_markers.append(match.start() + 2)  # +2 to skip the newlines
        
        # Sort markers by position
        forward_markers.sort()
        
        # Extract content between markers
        for i in range(len(forward_markers)):
            start = forward_markers[i]
            
            # Find the next marker or the end of the body
            if i < len(forward_markers) - 1:
                end = forward_markers[i + 1]
            else:
                end = len(body)
            
            # Extract the content between markers
            content = body[start:end].strip()
            
            # If we have actual content, add it to our list
            if content and len(content) > 20:  # Skip very short segments
                forwarded_emails.append(content)
    except Exception as e:
        print(f"Error extracting forwarded emails: {e}")
    
    # Look for common forwarded message patterns if we didn't find any yet
    if not forwarded_emails:
        try:
            # More forgiving pattern to find forwarded content
            forward_patterns = [
                r"(?:-{2,}|={2,})\s*Forwarded\s+by.+?(?:-{2,}|={2,}).+?$",
                r"(?:-{2,}|={2,})\s*Original\s+Message\s*(?:-{2,}|={2,}).+?$",
                r"From:.+?(?:\n|\r\n)To:.+?(?:\n|\r\n)(?:Cc:.+?(?:\n|\r\n))?(?:Subject:.+?(?:\n|\r\n))",
                r"On.+?wrote:"
            ]
            
            for pattern in forward_patterns:
                matches = re.finditer(pattern, body, re.MULTILINE | re.DOTALL)
                for match in matches:
                    # Extract content starting from the match
                    start = match.start()
                    end = len(body)
                    
                    # Look for a potential end marker (another forwarded message or end of text)
                    for end_pattern in forward_patterns:
                        end_match = re.search(end_pattern, body[start + 10:], re.MULTILINE | re.DOTALL)
                        if end_match:
                            # Only use this as an end if it's different from our start pattern
                            if end_match.group() != match.group():
                                end = start + 10 + end_match.start()
                                break
                    
                    content = body[start:end].strip()
                    if content and len(content) > 20 and content not in forwarded_emails:
                        forwarded_emails.append(content)
        except Exception as e:
            print(f"Error in forwarded pattern: {e}")
    
    # Look for Enron's internal format as well (nested messages)
    if not forwarded_emails:
        try:
            # More flexible pattern to match the Allan Severude format
            # Name on first line
            # Date on second line (MM/DD/YYYY HH:MM AM/PM)
            # To: with recipients (possibly spanning multiple lines)
            # cc: with recipients (possibly spanning multiple lines)
            # Subject: line
            nested_pattern = r"\n\n([A-Za-z][A-Za-z\s]+)\n(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM))\n(?:To:|cc:|Subject:)"
            
            nested_matches = re.finditer(nested_pattern, body, re.MULTILINE)
            
            for match in nested_matches:
                # Extract the entire message including headers and content 
                # by finding where this match appears in the body
                start_idx = match.start() + 2  # +2 to skip the newlines at the start
                
                # Find the next message start or the end of the body
                next_match = re.search(nested_pattern, body[start_idx + 10:], re.MULTILINE)
                if next_match:
                    next_match_idx = start_idx + 10 + next_match.start()
                else:
                    next_match_idx = len(body)
                
                # Extract the full nested message
                nested_message = body[start_idx:next_match_idx].strip()
                if nested_message and len(nested_message) > 30:
                    forwarded_emails.append(nested_message)
        except Exception as e:
            print(f"Error in nested pattern: {e}")
    
    return forwarded_emails


def extract_forwarded_full_body(content: str, file_path: str) -> str:
    """
    Extract the complete body content from a forwarded email.
    
    Attempts to identify and extract the actual message content by
    finding section markers or identifying the start after headers.
    
    Args:
        content: Forwarded email content
        file_path: Path to the original email file
        
    Returns:
        Clean body content
    """
    # Try to identify the start of the actual content after headers
    # Common section markers in business emails
    section_markers = [
        "STRUCTURE:", 
        "INTRODUCTION:", 
        "SUMMARY:", 
        "BACKGROUND:", 
        "OVERVIEW:",
        "ANALYSIS:",
        "REPORT:",
        "DETAILS:"
    ]
    
    # Check if any section marker exists in the content
    for marker in section_markers:
        if marker in content:
            # Extract from the marker to the end (or until a clear endpoint)
            start_idx = content.find(marker)
            # Look for typical email endings
            end_markers = [
                " - winmail.dat",
                "\n\n-----Original Message",
                "\n\n-----Forwarded",
                "\n------ End of Forwarded Message"
            ]
            
            end_idx = len(content)
            for end_marker in end_markers:
                pos = content.find(end_marker, start_idx)
                if pos != -1 and pos < end_idx:
                    end_idx = pos
            
            return content[start_idx:end_idx].strip()
    
    # If no section markers found, try to find the body after common header patterns
    lines = content.split('\n')
    
    # Look for a blank line after headers (From:, To:, Subject:, etc.)
    in_headers = False
    body_start_idx = -1
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        # Mark that we're in the header section
        if line_lower.startswith(("from:", "to:", "cc:", "subject:", "date:")) or \
           ('"' in line and '<' in line and '>' in line and ' on ' in line):
            in_headers = True
        # Look for the first non-empty line after a blank line following headers
        elif in_headers and line_lower == "":
            # Check if the next line is not empty and not a header
            if i+1 < len(lines) and lines[i+1].strip() and \
               not lines[i+1].lower().strip().startswith(("from:", "to:", "cc:", "subject:", "date:")):
                body_start_idx = i+1
                break
    
    if body_start_idx >= 0:
        body_content = lines[body_start_idx:]
        return '\n'.join(body_content).strip()
    
    # If all else fails, just return everything after common forwarding patterns
    for i, line in enumerate(lines):
        if 'forwarded by' in line.lower() and i+3 < len(lines):
            # Skip the forwarding header (typically 3 lines)
            return '\n'.join(lines[i+3:]).strip()
    
    # Final fallback: just return the original content cleaned
    return clean_body(content) 