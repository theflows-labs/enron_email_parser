"""
Header extraction module for email parsing.

This module contains functions to extract headers from various email formats,
particularly focusing on Enron-style forwarded messages.
"""
import re
from typing import Dict, Any

from email_parser.utils.helpers import (
    extract_header_from_text,
    extract_email_address,
    normalize_addresses,
    process_recipients,
    clean_body
)

# TODO: this class needs to be refactored with more logic to handle the different formats of enron emails. 
#       For example, the nested emails have a different format than the forwarded emails.
#       Also, the headers are not always in the same order.
#       So, we need to handle the different formats and extract the headers accordingly.    
#       ========== There is scope for improvement here. ==========

def extract_enron_style_headers(content: str) -> Dict[str, Any]:
    """
    Extract headers from Enron-style forwarded messages.
    
    These often have specific formats like:
    
    Format 1:
    "George Richards" <cbpres@austin.rr.com> on 09/26/2000 01:18:45 PM
    Please respond to <cbpres@austin.rr.com>
    To: "Phillip Allen" <pallen@enron.com>
    cc: "Larry Lewter" <retwell@mail.sanmarcos.net>, "Claudia L. Crocker" <clclegal2@aol.com>
    Subject: Investment Structure
    
    Format 2:
    Parking & Transportation@ENRON
    03/28/2001 02:07 PM
    Sent by: DeShonda Hamilton@ENRON
    To: Brad Alford/NA/Enron@Enron, Megan Angelos/Enron@EnronXGate, ...
    
    Args:
        content: Email content text
        
    Returns:
        Dictionary of extracted headers
    """
    headers = {
        'from': '',
        'to': [],
        'cc': [],
        'bcc': [],
        'subject': '',
        'date': '',
        'body_clean': '',
    }
    
    # Extract information from the Enron-specific forwarded message format
    lines = content.split('\n')
    
    # Track the "Sent by" information
    sent_by = None
    
    # Track multiline TO and CC fields
    in_to_field = False
    in_cc_field = False
    to_line_found = False
    cc_line_found = False
    
    # Track if this is a "Please respond to" format message
    please_respond_format = False
    
    # First pass: look for specific patterns that indicate the email format
    for i, line in enumerate(lines):
        if line.lower().strip().startswith('please respond to'):
            please_respond_format = True
            break
    
    # Second pass: extract header information based on the identified format
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        # Handle "Sent by" lines 
        if "sent by:" in line_lower:
            # Extract the actual sender from the "Sent by" line
            sent_by_match = re.search(r'Sent by: (.+?)(@ENRON|$)', line)
            if sent_by_match:
                sent_by = sent_by_match.group(1).strip()
                # Convert to email format if it's not already
                if '@' not in sent_by:
                    sent_by = sent_by.lower().replace(' ', '.') + '@enron.com'
        
        # Find the sender line (usually contains "on" followed by a date)
        elif ('<' in line and '>' in line and ' on ' in line) or ('forwarded by' in line_lower and ' on ' in line_lower):
            # Extract email from the line
            if '<' in line and '>' in line:
                email_match = re.search(r'<([^>]+)>', line)
                if email_match:
                    headers['from'] = email_match.group(1).lower()
            elif 'forwarded by' in line_lower:
                # Extract the forwarder's name
                fwd_match = re.search(r'Forwarded by ([^/]+)', line)
                if fwd_match:
                    forwarder = fwd_match.group(1).strip()
                    # Convert to email format
                    headers['from'] = forwarder.lower().replace(' ', '.') + '@enron.com'
            
            # Extract date from the line
            date_match = re.search(r' on (\d{2}/\d{2}/\d{4} \d{2}:\d{2}(?::\d{2})? [AP]M)', line)
            if date_match:
                headers['date'] = date_match.group(1)
        
        # Handle "Please respond to" line which often contains the real sender email
        elif line_lower.startswith('please respond to') and '<' in line and '>' in line:
            email_match = re.search(r'<([^>]+)>', line)
            if email_match:
                # This is likely the real sender, not the forwarder
                headers['from'] = email_match.group(1).lower()
        
        # Check for Enron internal sender format (not in forwarded by line)
        elif i < 5 and '@ENRON' in line and not headers['from'] and not line_lower.startswith(('to:', 'cc:', 'subject:')):
            # This might be the sender line in internal format
            possible_sender = line.split('@')[0].strip()
            if possible_sender and len(possible_sender) > 0:
                headers['from'] = possible_sender.lower().replace(' ', '.') + '@enron.com'
            
            # Look at the next line for a date
            if i+1 < len(lines) and re.match(r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}(?::\d{2})? [AP]M', lines[i+1].strip()):
                headers['date'] = lines[i+1].strip()
        
        # Finding the start of TO: field
        elif line_lower.startswith('to:'):
            in_to_field = True
            in_cc_field = False
            to_line_found = True
            to_line = line[3:].strip()  # Remove the "To:" prefix
            
            # If this is a "Please respond to" format, handle specifically
            if please_respond_format and '"' in to_line and '<' in to_line and '>' in to_line:
                # Extract all emails in angle brackets
                for email_match in re.finditer(r'<([^>]+)>', to_line):
                    if email_match.group(1) not in headers['to']:
                        headers['to'].append(email_match.group(1).lower())
            else:
                # Process this line's recipients with standard logic
                process_recipients(to_line, headers['to'])
        
        # Finding the start of CC: field
        elif line_lower.startswith('cc:'):
            in_to_field = False
            in_cc_field = True
            cc_line_found = True
            cc_line = line[3:].strip()  # Remove the "Cc:" prefix
            
            # If this is a "Please respond to" format, handle specifically
            if please_respond_format and '"' in cc_line and '<' in cc_line and '>' in cc_line:
                # Extract all emails in angle brackets
                for email_match in re.finditer(r'<([^>]+)>', cc_line):
                    if email_match.group(1) not in headers['cc']:
                        headers['cc'].append(email_match.group(1).lower())
            else:
                # Process this line's recipients with standard logic
                process_recipients(cc_line, headers['cc'])
        
        # Handle continuation of To: or Cc: fields (these are often wrapped across multiple lines)
        elif (in_to_field or in_cc_field) and line.strip() and not line_lower.startswith(('subject:', 'bcc:', 'from:')):
            # This is likely a continuation of the previous field
            if not line.strip().startswith('-'):  # Skip separator lines
                recipient_list = headers['to'] if in_to_field else headers['cc']
                
                # If we're in "Please respond to" format and there are angle brackets
                if please_respond_format and '<' in line and '>' in line:
                    # Extract emails in angle brackets
                    for email_match in re.finditer(r'<([^>]+)>', line):
                        if email_match.group(1) not in recipient_list:
                            recipient_list.append(email_match.group(1).lower())
                else:
                    # Standard processing
                    process_recipients(line.strip(), recipient_list)
        
        # Subject field terminating TO or CC fields
        elif line_lower.startswith('subject:'):
            in_to_field = False
            in_cc_field = False
            headers['subject'] = line[8:].strip()
    
    # If we have a "Sent by" value, use it as the true sender
    if sent_by and sent_by.strip():
        headers['from'] = sent_by
    
    # Extract body content
    # Find where the body starts (after all headers)
    body_start = -1
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        # Check if this is the last header line
        if line_lower.startswith('subject:'):
            # Look for the next non-empty line after a blank line
            for j in range(i+1, len(lines)):
                if not lines[j].strip():  # Found blank line
                    # Now find the next non-blank line
                    for k in range(j+1, len(lines)):
                        if lines[k].strip():
                            body_start = k
                            break
                    if body_start > 0:
                        break
            if body_start > 0:
                break
    
    # If we found the body start, extract all lines
    if body_start > 0:
        headers['body_clean'] = '\n'.join(lines[body_start:]).strip()
    # If not, use a best effort approach
    else:
        # Look for the first non-header section
        non_header_lines = []
        past_headers = False
        
        for line in lines:
            line_lower = line.lower().strip()
            if not past_headers:
                # Check if this looks like a header line
                if (line_lower.startswith(('subject:', 'to:', 'cc:', 'bcc:', 'from:', 'sent by:', 'date:', 'please respond to')) or
                    ('forwarded by' in line_lower) or 
                    ('@enron' in line_lower and len(line_lower) < 40)):
                    continue
                # Blank line after headers or first all-caps section header
                elif not line.strip() or re.match(r'^[A-Z][A-Z\s]+:$', line.strip()):
                    past_headers = True  # Start collecting body after this
            else:
                # Once we're past headers, collect lines
                non_header_lines.append(line)
        
        if non_header_lines:
            headers['body_clean'] = '\n'.join(non_header_lines).strip()
    
    # Second-pass check for known patterns
    # If we didn't find TO but have FROM, try harder to locate recipients
    if (not headers['to'] or len(headers['to']) == 0) and headers['from']:
        for i, line in enumerate(lines):
            line_lower = line.strip().lower()
            
            # Look for lines with "To:" that contain angle brackets (common in forwarded emails)
            if ('to:' in line_lower or line_lower.startswith('to ')) and '<' in line and '>' in line:
                # Extract the email addresses
                for email_match in re.finditer(r'<([^>]+)>', line):
                    if email_match.group(1) not in headers['to']:
                        headers['to'].append(email_match.group(1).lower())
                
            # Also look for CC lines in the same format
            elif ('cc:' in line_lower or line_lower.startswith('cc ')) and '<' in line and '>' in line:
                # Extract the email addresses
                for email_match in re.finditer(r'<([^>]+)>', line):
                    if email_match.group(1) not in headers['cc']:
                        headers['cc'].append(email_match.group(1).lower())
                        
            # And check for subject if we don't have it
            elif 'subject:' in line_lower and not headers['subject']:
                headers['subject'] = line[line_lower.find('subject:') + 8:].strip()
    
    # If we still don't have any recipients but have other indicators this is a real email,
    # check the entire content for email addresses in angle brackets
    if (not headers['to'] or len(headers['to']) == 0) and headers['from'] and headers['subject']:
        potential_recipients = []
        for line in lines:
            if '<' in line and '>' in line and '@' in line:
                for email_match in re.finditer(r'<([^>]+@[^>]+)>', line):
                    email = email_match.group(1).lower()
                    if email != headers['from'] and email not in potential_recipients:
                        potential_recipients.append(email)
        
        # Add any found emails to the TO list
        for email in potential_recipients:
            if email not in headers['to']:
                headers['to'].append(email)
    
    return headers


def extract_nested_email_headers(content: str) -> Dict[str, Any]:
    """
    Extract headers from Enron-style nested emails with simpler format.
    
    Simplified format often found in Enron emails:
    Jeff Richter
    12/07/2000 06:31 AM
    To: Phillip K Allen/HOU/ECT@ECT
    cc:  
    Subject: DJ Cal-ISO Pays...
    
    Args:
        content: Email content text
        
    Returns:
        Dictionary of extracted headers
    """
    headers = {
        'from': '',
        'to': [],
        'cc': [],
        'bcc': [],
        'subject': '',
        'date': '',
        'body_clean': '',
    }
    
    # Handle the specific format: Name on first line, date on second, then To:, cc:, Subject:
    lines = content.split('\n')
    
    # Try to determine if we have the specific format
    if len(lines) >= 5:
        name_line_idx = -1
        date_line_idx = -1
        to_line_idx = -1
        
        # Look for the pattern of name, date, To: in the first few lines
        for i in range(min(10, len(lines))):
            line = lines[i].strip()
            
            # First non-empty line could be a name
            if name_line_idx == -1 and line and not line.startswith(('-', 'From:', 'To:', 'cc:', 'Subject:')):
                name_line_idx = i
            # Date line should follow the name line
            elif name_line_idx != -1 and date_line_idx == -1 and re.match(r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)', line):
                date_line_idx = i
            # To: line should follow the date line
            elif date_line_idx != -1 and to_line_idx == -1 and line.lower().startswith('to:'):
                to_line_idx = i
                break
        
        # If we found the pattern, extract headers using this specific format
        if name_line_idx != -1 and date_line_idx != -1 and to_line_idx != -1:
            # Extract the name and create email
            name = lines[name_line_idx].strip()
            # Make sure the name is properly converted to an email
            if name and not '@' in name:
                headers['from'] = name.lower().replace(' ', '.') + '@enron.com'
            else:
                headers['from'] = name
            
            # Extract the date
            headers['date'] = lines[date_line_idx].strip()
            
            # Process each subsequent line for headers
            in_to_section = False
            in_cc_section = False
            to_lines = []
            cc_lines = []
            
            for i in range(to_line_idx, len(lines)):
                line = lines[i].strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Check for header markers
                if line.lower().startswith('to:'):
                    in_to_section = True
                    in_cc_section = False
                    to_lines.append(line[3:].strip())  # Add content after "To:"
                elif line.lower().startswith('cc:'):
                    in_to_section = False
                    in_cc_section = True
                    cc_lines.append(line[3:].strip())  # Add content after "cc:"
                elif line.lower().startswith('subject:'):
                    in_to_section = False
                    in_cc_section = False
                    headers['subject'] = line[8:].strip()
                    # Subject line typically ends the header section
                    break
                elif in_to_section:
                    # This is a continuation of the To: line
                    to_lines.append(line)
                elif in_cc_section:
                    # This is a continuation of the cc: line
                    cc_lines.append(line)
            
            # Process all collected To: lines
            if to_lines:
                # Join all lines and split by commas to get individual recipients
                to_text = ' '.join(to_lines)
                to_recipients = re.split(r',\s*', to_text)
                for recipient in to_recipients:
                    recipient = recipient.strip()
                    if not recipient:
                        continue
                    
                    # If it has an @ symbol, it's already an email
                    if '@' in recipient:
                        headers['to'].append(recipient.lower())
                    else:
                        # Handle Enron internal format (Name/Dept/Enron)
                        name_parts = recipient.split('/')
                        if name_parts and len(name_parts) >= 1:
                            name = name_parts[0].strip()
                            if name and not name.lower().startswith(('to:', 'cc:')):
                                headers['to'].append(name.lower().replace(' ', '.') + '@enron.com')
            
            # Process all collected cc: lines
            if cc_lines:
                # Join all lines and split by commas to get individual recipients
                cc_text = ' '.join(cc_lines)
                
                # Fix common pattern in wrapped lines where there might be 
                # unintended splits due to line breaks
                # Example: "Scott\nMills/HOU/ECT@ECT" should be "Scott Mills/HOU/ECT@ECT"
                cc_text = re.sub(r'(\w+)\s*\n\s*(\w+)', r'\1 \2', cc_text)
                
                cc_recipients = re.split(r',\s*', cc_text)
                for recipient in cc_recipients:
                    recipient = recipient.strip()
                    if not recipient:
                        continue
                    
                    # If it has an @ symbol, it's already an email
                    if '@' in recipient:
                        headers['cc'].append(recipient.lower())
                    else:
                        # Handle Enron internal format (Name/Dept/Enron)
                        name_parts = recipient.split('/')
                        if name_parts and len(name_parts) >= 1:
                            name = name_parts[0].strip()
                            if name and not name.lower().startswith(('to:', 'cc:')):
                                headers['cc'].append(name.lower().replace(' ', '.') + '@enron.com')
            
            # If we've found valid headers, return them
            if headers['from'] and headers['date'] and (headers['to'] or headers['subject']):
                # Extract body - everything after the headers
                body_start = -1
                for i in range(len(lines)):
                    if lines[i].strip().lower().startswith('subject:'):
                        # Body starts after an empty line following the subject
                        for j in range(i+1, len(lines)):
                            if not lines[j].strip() and j+1 < len(lines) and lines[j+1].strip():
                                body_start = j+1
                                break
                        break
                
                if body_start != -1:
                    headers['body_clean'] = '\n'.join(lines[body_start:]).strip()
                
                return headers
    
    # If the specific format matching didn't work, fall back to the original implementation
    
    # Specific Enron format: try direct pattern matching for the exact format
    name_date_pattern = r'^\s*([A-Za-z][\w\s]+?)\s*\n\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM))\s*\n'
    name_date_match = re.search(name_date_pattern, content, re.MULTILINE)
    
    if name_date_match:
        name, date = name_date_match.groups()
        headers['from'] = name.strip().lower().replace(' ', '.') + '@enron.com'
        headers['date'] = date.strip()
        
        # Extract other headers
        lines = content.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Look for explicit header markers
            if stripped.lower().startswith('to:'):
                # Extract email addresses
                email_parts = stripped[3:].strip().split(',')
                to_emails = []
                for part in email_parts:
                    # Try to extract email from various formats
                    if '@' in part:
                        to_emails.append(part.strip().lower())
                    else:
                        # Try to handle Enron internal format like "Name/DEPT/COMPANY@tag"
                        name_parts = part.split('/')
                        if len(name_parts) >= 1:  # Changed from 2 to 1 to be more lenient
                            name = name_parts[0].strip()
                            if '@' not in name and not name.lower().startswith('to:'):
                                # Convert internal format to email-like format
                                email = name.lower().replace(' ', '.') + '@enron.com'
                                to_emails.append(email)
                
                headers['to'] = to_emails
            
            elif stripped.lower().startswith('cc:'):
                # Extract CC emails similarly
                if len(stripped) > 3:
                    email_parts = stripped[3:].strip().split(',')
                    cc_emails = []
                    for part in email_parts:
                        if '@' in part:
                            cc_emails.append(part.strip().lower())
                        else:
                            # Try to handle Enron internal format
                            name_parts = part.split('/')
                            if len(name_parts) >= 1:  # Changed from 2 to 1
                                name = name_parts[0].strip()
                                if '@' not in name and not name.lower().startswith('cc:'):
                                    email = name.lower().replace(' ', '.') + '@enron.com'
                                    cc_emails.append(email)
                    
                    headers['cc'] = cc_emails
            
            elif stripped.lower().startswith('subject:'):
                headers['subject'] = stripped[8:].strip()
    
    # If we didn't find headers using direct pattern matching, try line-by-line approach
    if not headers['from'] or not headers['date']:
        lines = content.split('\n')
        
        # Reset line trackers
        name_line = -1
        date_line = -1
        to_line = -1
        cc_line = -1
        subject_line = -1
        body_start = -1
        
        # Specific Enron date pattern (MM/DD/YYYY HH:MM AM/PM)
        date_pattern = r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)'
        
        # Look for the pattern
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # If pattern already started, look for headers
            if name_line >= 0:
                # Next line after name should be date
                if i == name_line + 1 and re.match(date_pattern, stripped):
                    date_line = i
                    headers['date'] = stripped
                
                # Look for explicit header markers
                elif stripped.lower().startswith('to:'):
                    to_line = i
                    # Extract email addresses
                    email_parts = stripped[3:].strip().split(',')
                    to_emails = []
                    for part in email_parts:
                        # Try to extract email from various formats
                        if '@' in part:
                            to_emails.append(part.strip().lower())
                        else:
                            # Try to handle Enron internal format like "Name/DEPT/COMPANY@tag"
                            name_parts = part.split('/')
                            if len(name_parts) >= 1:
                                name = name_parts[0].strip()
                                if '@' not in name and not name.lower().startswith('to:'):
                                    # Convert internal format to email-like format
                                    email = name.lower().replace(' ', '.') + '@enron.com'
                                    to_emails.append(email)
                    
                    headers['to'] = to_emails
                
                elif stripped.lower().startswith('cc:'):
                    cc_line = i
                    # Extract CC emails similarly
                    if len(stripped) > 3:
                        email_parts = stripped[3:].strip().split(',')
                        cc_emails = []
                        for part in email_parts:
                            if '@' in part:
                                cc_emails.append(part.strip().lower())
                            else:
                                # Try to handle Enron internal format
                                name_parts = part.split('/')
                                if len(name_parts) >= 1:
                                    name = name_parts[0].strip()
                                    if '@' not in name and not name.lower().startswith('cc:'):
                                        email = name.lower().replace(' ', '.') + '@enron.com'
                                        cc_emails.append(email)
                        
                        headers['cc'] = cc_emails
                
                elif stripped.lower().startswith('subject:'):
                    subject_line = i
                    headers['subject'] = stripped[8:].strip()
                
                # Find body start after all headers are processed
                elif subject_line >= 0 and stripped == '' and i < len(lines) - 1 and lines[i+1].strip() != '':
                    body_start = i + 1
                    break
            
            # Look for name at the start of a forwarded section
            elif i > 0 and lines[i-1].strip() == '' and stripped and not stripped.startswith('-'):
                # Check if next line looks like a date
                if i < len(lines) - 1 and re.match(date_pattern, lines[i+1].strip()):
                    name_line = i
                    headers['from'] = stripped.lower().replace(' ', '.') + '@enron.com'
    
    # Finally, try to extract the date using a direct search
    if not headers['date']:
        # Look for date in the format MM/DD/YYYY HH:MM AM/PM
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM))', content)
        if date_match:
            headers['date'] = date_match.group(1).strip()
    
    # Extract body content if we found the start
    if body_start > 0:
        headers['body_clean'] = '\n'.join(lines[body_start:]).strip()
    
    return headers


def extract_forwarded_headers(content: str) -> Dict[str, Any]:
    """
    Extract headers from forwarded message text.
    
    First tries Enron-specific format, then falls back to generic extraction.
    
    Args:
        content: Email content text
        
    Returns:
        Dictionary of extracted headers
    """
    # First try Enron-specific format
    if '---------------------- Forwarded by' in content or '"' in content and '<' in content and '>' in content and ' on ' in content:
        return extract_enron_style_headers(content)
    
    # Try the simpler Enron nested format with name and date at the top
    if re.search(r'\n\w+\s+\w+\n\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+[AP]M\n', content, re.MULTILINE):
        headers = extract_nested_email_headers(content)
        # If we found date and other headers, return them
        if headers['date'] and (headers['from'] or headers['to'] or headers['subject']):
            return headers
    
    # If not Enron format, try generic header extraction
    headers = {
        'from': '',
        'to': [],
        'cc': [],
        'bcc': [],
        'subject': '',
        'date': '',
        'body_clean': '',
    }
    
    # Look for the Enron-style name and date pattern at the beginning
    name_date_pattern = r'^\s*([A-Za-z][\w\s]+?)\s*\n\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM))\s*\n'
    name_date_match = re.search(name_date_pattern, content, re.MULTILINE)
    if name_date_match:
        name, date = name_date_match.groups()
        # Make sure the name is properly converted to an email
        if name and not '@' in name.strip():
            headers['from'] = name.strip().lower().replace(' ', '.') + '@enron.com'
        else:
            headers['from'] = name.strip()
        headers['date'] = date.strip()
        
        # Look for To: and cc: lines after the date
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.strip().lower().startswith('to:'):
                to_text = line[3:].strip()
                if to_text:
                    # Extract email addresses
                    to_parts = re.split(r',\s*', to_text)
                    for part in to_parts:
                        if '@' in part:
                            headers['to'].append(part.strip().lower())
                        elif '/' in part:  # Enron format
                            name_parts = part.split('/')
                            if name_parts and len(name_parts) >= 1:
                                headers['to'].append(name_parts[0].strip().lower().replace(' ', '.') + '@enron.com')
            
            elif line.strip().lower().startswith('cc:'):
                cc_text = line[3:].strip()
                if cc_text:
                    # Extract email addresses
                    cc_parts = re.split(r',\s*', cc_text)
                    for part in cc_parts:
                        if '@' in part:
                            headers['cc'].append(part.strip().lower())
                        elif '/' in part:  # Enron format
                            name_parts = part.split('/')
                            if name_parts and len(name_parts) >= 1:
                                headers['cc'].append(name_parts[0].strip().lower().replace(' ', '.') + '@enron.com')
            
            elif line.strip().lower().startswith('subject:'):
                headers['subject'] = line[8:].strip()
    
    # If we found any headers with the name/date pattern, return them
    if headers['from'] and headers['date']:
        # Extract body - everything after the headers
        body_start = 0
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.strip().lower().startswith('subject:'):
                body_start = i + 1
                break
        
        if body_start > 0 and body_start < len(lines):
            # Skip any blank lines after the Subject
            while body_start < len(lines) and not lines[body_start].strip():
                body_start += 1
            
            if body_start < len(lines):
                headers['body_clean'] = '\n'.join(lines[body_start:]).strip()
        
        return headers
    
    # Extract common headers using standard patterns
    headers['from'] = extract_header_from_text(content, "From")
    to_str = extract_header_from_text(content, "To")
    headers['to'] = normalize_addresses(to_str) if to_str else []
    
    cc_str = extract_header_from_text(content, "Cc")
    headers['cc'] = normalize_addresses(cc_str) if cc_str else []
    
    bcc_str = extract_header_from_text(content, "Bcc")
    headers['bcc'] = normalize_addresses(bcc_str) if bcc_str else []
    
    headers['subject'] = extract_header_from_text(content, "Subject")
    
    # Try different ways to extract the date
    headers['date'] = extract_header_from_text(content, "Date")
    if not headers['date']:
        # Look for date in Enron format: MM/DD/YYYY HH:MM AM/PM
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM))', content)
        if date_match:
            headers['date'] = date_match.group(1)
    
    # Extract body - everything after the headers block
    body = ""
    header_block_end = 0
    
    # Find where the headers end and the body begins
    header_pattern = r"(From:.*?(\n|\r\n))(To:.*?(\n|\r\n))(?:(?:Cc:.*?(\n|\r\n))?)?(?:(?:Bcc:.*?(\n|\r\n))?)?(?:(?:Subject:.*?(\n|\r\n)))?(?:(?:Date:.*?(\n|\r\n)))?"
    match = re.search(header_pattern, content, re.IGNORECASE | re.DOTALL)
    
    if match:
        header_block_end = match.end()
        body = content[header_block_end:].strip()
    else:
        # Fallback method: look for each header and find the last one
        headers_to_check = ["From:", "To:", "Cc:", "Bcc:", "Subject:", "Date:"]
        last_pos = -1
        
        for header in headers_to_check:
            pattern = rf"{header}\s*(.*?)(?:\n|$)"
            match = re.search(pattern, content, re.IGNORECASE)
            if match and match.end() > last_pos:
                last_pos = match.end()
        
        if last_pos > 0:
            body = content[last_pos:].strip()
    
    # If we didn't find a header block, just clean the whole content
    if not body and content:
        body = clean_body(content)
    
    headers['body_clean'] = body
    return headers 