"""
Parser module for processing email files.

This module contains the main EmailParser class that handles
parsing email files and extracting nested/forwarded messages.
"""
import os
import re
import email
from pathlib import Path
from datetime import datetime
from email import policy
from email.parser import BytesParser
import pandas as pd
from io import BytesIO

from email_parser.models import EmailData
from email_parser.utils.helpers import (
    generate_id, 
    extract_email_address, 
    normalize_addresses,
    clean_body,
    extract_date,
    process_recipients
)
from email_parser.extractors.headers import (
    extract_enron_style_headers,
    extract_forwarded_headers
)
from email_parser.extractors.content import (
    extract_original_email,
    extract_forwarded_full_body
)

class EmailParser:
    """
    Email parser for handling Enron dataset emails and extracting nested content.
    
    This class is responsible for parsing email files and identifying
    nested/forwarded messages within them.
    """
    
    def __init__(self, debug=False):
        """
        Initialize the email parser.
        
        Args:
            debug: Enable debug output for verbose logging
        """
        self.debug = debug
    
    def parse_files(self, file_paths):
        """
        Parse email files and extract data including nested messages.
        
        Args:
            file_paths: List of file paths to parse
            
        Returns:
            DataFrame with parsed email data
        """
        emails_data = []
        
        for file_path in file_paths:
            try:
                emails = self._parse_single_file(file_path)
                emails_data.extend(emails)
            except Exception as e:
                if self.debug:
                    print(f"Error processing file {file_path}: {e}")
        
        if not emails_data:
            if self.debug:
                print("Warning: No emails were successfully parsed")
            return pd.DataFrame(columns=['id', 'date', 'subject', 'from', 'to', 'cc', 'bcc', 'body_clean', 'thread_id', 'file_source'])
        
        # Create DataFrame and assign thread IDs
        df = pd.DataFrame(emails_data)
        df['thread_id'] = df.apply(self._generate_thread_id, axis=1)
        
        return df
    
    def _parse_single_file(self, file_path):
        """
        Parse a single file and extract all emails.
        
        Args:
            file_path: Path to the file (expected to be a CSV file with 'file' and 'message' columns)
            
        Returns:
            List of dictionaries with email data
        """
        emails_data = []
        
        # Handle CSV files
        if file_path.endswith('.csv'):
            try:
                # Read the CSV file
                df = pd.read_csv(file_path)
                
                # Verify required columns exist
                if 'file' not in df.columns or 'message' not in df.columns:
                    raise ValueError(f"CSV file {file_path} must contain 'file' and 'message' columns")
                
                # Process each row (pandas automatically skips the header)
                for _, row in df.iterrows():
                    file_id = row['file']
                    message_content = row['message']
                    
                    try:
                        # Parse the email content directly
                        parsed_emails = self._parse_email_content(message_content, file_id)
                        emails_data.extend(parsed_emails)
                    except Exception as e:
                        if self.debug:
                            print(f"Error processing message {file_id} from CSV: {e}")
                
                return emails_data
            except Exception as e:
                if self.debug:
                    print(f"Error processing CSV file {file_path}: {e}")
                return []
        else: # TODO need to test non csv based files more. 
            # For non-CSV files, read content and process
            try:
                with open(file_path, 'r', errors='ignore') as f:
                    content = f.read()
                
                # Process as a single email
                return self._parse_email_content(content, file_path)
            except Exception as e:
                if self.debug:
                    print(f"Error processing file {file_path}: {e}")
                return []
    
    def _extract_email_fields(self, message):
        """
        Extract relevant fields from an email message.
        
        Args:
            message: Email message object
            
        Returns:
            Dictionary with extracted fields
        """
        # Extract and parse the date
        date = extract_date(message.get('date', ''))
        
        # Extract the body content
        if message.is_multipart():
            body_parts = []
            for part in message.walk():
                if part.get_content_type() == 'text/plain':
                    try:
                        body_parts.append(part.get_content())
                    except:
                        # Skip parts that can't be decoded
                        pass
            body = '\n'.join(body_parts)
        else:
            try:
                body = message.get_content()
            except:
                # Fallback for messages that can't be decoded properly
                body = message.get_payload(decode=True)
                if isinstance(body, bytes):
                    try:
                        body = body.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            body = body.decode('latin1')
                        except:
                            body = str(body)
        
        # Clean the body to remove quoted content
        body_clean = clean_body(body)
        
        # Extract the email addresses
        from_addr = normalize_addresses(message.get('from', ''))[0] if normalize_addresses(message.get('from', '')) else ''
        to_addr = normalize_addresses(message.get('to', ''))
        cc_addr = normalize_addresses(message.get('cc', ''))
        bcc_addr = normalize_addresses(message.get('bcc', ''))
        
        return {
            'date': date,
            'subject': message.get('subject', ''),
            'from': from_addr,
            'to': to_addr,
            'cc': cc_addr,
            'bcc': bcc_addr,
            'body': body,
            'body_clean': body_clean,
        }
    
    def _extract_nested_email(self, forwarded_content, file_id, idx, parent_subject):
        """
        Extract data from a nested/forwarded email.
        
        Args:
            forwarded_content: Content of the forwarded email
            file_id: Identifier for the source (for tracking purposes)
            idx: Index of the nested email in the parent
            parent_subject: Subject of the parent email
            
        Returns:
            Dictionary with nested email data or None if extraction fails
        """
        try:
            # First try Enron-specific header extraction
            nested_headers = extract_enron_style_headers(forwarded_content)
            
            # Handle the "Please respond to" format (previously only for file 117)
            if "Please respond to <" in forwarded_content and "To: \"" in forwarded_content:
                self._handle_please_respond_format(forwarded_content, nested_headers)
            
            # Check if we got meaningful data from the header extractor
            if nested_headers['from'] or (nested_headers['to'] and len(nested_headers['to']) > 0) or nested_headers['subject']:
                return self._create_nested_email_dict(
                    forwarded_content, 
                    nested_headers, 
                    file_id, 
                    idx, 
                    parent_subject
                )
            
            # If the Enron-specific extractor didn't work well, try the standard approach
            fwd_fields = extract_forwarded_headers(forwarded_content)
            
            # Get full body content
            body_clean = self._get_nested_body_content(fwd_fields, forwarded_content, file_id)
            
            # Create a unique ID for this nested email
            nested_id = generate_id(forwarded_content, file_id, idx)
            
            # Parse date to ISO format if present
            parsed_date = extract_date(fwd_fields['date']) if fwd_fields['date'] else None
            
            # Create the nested email data
            nested_data = {
                'id': nested_id,
                'date': parsed_date,
                'subject': fwd_fields['subject'] or parent_subject,
                'from': extract_email_address(fwd_fields['from']),
                'to': fwd_fields['to'],
                'cc': fwd_fields['cc'],
                'bcc': fwd_fields['bcc'],
                'body_clean': body_clean,
                'file_source': f"{file_id}-nested-{idx}",
            }
            
            # Return if we have meaningful content
            if (nested_data['body_clean'] and len(nested_data['body_clean']) > 10) or nested_data['from'] or (nested_data['to'] and len(nested_data['to']) > 0):
                return nested_data
                
        except Exception as e:
            if self.debug:
                print(f"Error extracting nested email: {e}")
            
            # Try with pseudo-email method as fallback
            try:
                return self._extract_nested_email_fallback(forwarded_content, file_id, idx, parent_subject)
            except Exception as inner_e:
                if self.debug:
                    print(f"Fallback parsing also failed: {inner_e}")
        
        return None
    
    def _handle_please_respond_format(self, forwarded_content, nested_headers):
        """
        Handle "Please respond to" email format.
        
        Extracts recipient information from emails that follow the pattern:
        "Name" <email> on date
        Please respond to <email>
        To: "Name" <email>
        cc: "Name" <email>, "Name" <email>
        
        Args:
            forwarded_content: Content of the forwarded email
            nested_headers: Headers dictionary to modify
        """
        # Extract TO field with name in quotes and email in angle brackets
        to_match = re.search(r'To:\s+"[^"]+"\s+<([^>]+)>', forwarded_content)
        if to_match:
            nested_headers['to'] = [to_match.group(1).lower()]
        
        # Extract CC fields using a multi-step approach
        cc_emails = []
        
        # Step 1: Use a multi-line regex to find the entire CC section from cc: to the next header
        cc_section_pattern = r'cc:\s+(.*?)(?=\n\w+:|Subject:|$)'
        cc_section_match = re.search(cc_section_pattern, forwarded_content, re.DOTALL | re.IGNORECASE)
        
        if cc_section_match:
            cc_section = cc_section_match.group(1)
            
            # Step 2: Find all quoted names in the CC section
            quoted_names = re.findall(r'"([^"]+)"', cc_section)
            
            # Step 3: For each quoted name, find the corresponding email
            for name in quoted_names:
                # First look directly after the name for an angle-bracketed email
                email_pattern = f'"{re.escape(name)}"\\s*<([^>]+)>'
                email_match = re.search(email_pattern, forwarded_content)
                
                if email_match:
                    cc_emails.append(email_match.group(1).lower())
                else:
                    # If not found, look for the name and then scan ahead for the next angle-bracketed email
                    name_pos = forwarded_content.find(f'"{name}"')
                    if name_pos != -1:
                        subsequent_text = forwarded_content[name_pos:name_pos + 200]  # Look ahead up to 200 chars
                        subsequent_email = re.search(r'<([^>]+@[^>]+)>', subsequent_text)
                        if subsequent_email:
                            cc_emails.append(subsequent_email.group(1).lower())
        
        # If we found any CC emails, update the headers
        if cc_emails:
            nested_headers['cc'] = cc_emails
        
        # Fallback: If the above didn't work, extract all angle-bracketed emails in the CC section
        if not cc_emails and cc_section_match:
            cc_section = cc_section_match.group(1)
            email_matches = re.findall(r'<([^>]+@[^>]+)>', cc_section)
            if email_matches:
                nested_headers['cc'] = [email.lower() for email in email_matches]
        
        # Additional fallback: If still no CC emails, look for a cc: line followed by quoted names
        # and then try to find emails for those names anywhere in the content
        if not nested_headers.get('cc'):
            cc_line_match = re.search(r'cc:\s+"([^"]+)"', forwarded_content)
            if cc_line_match:
                name = cc_line_match.group(1)
                
                # Look for all angle-bracketed emails in the content
                all_emails = re.findall(r'<([^>]+@[^>]+)>', forwarded_content)
                
                # Filter out the from and to emails
                from_match = re.search(r'"[^"]+"\s+<([^>]+)>\s+on', forwarded_content)
                to_match = re.search(r'To:\s+"[^"]+"\s+<([^>]+)>', forwarded_content)
                
                excluded_emails = []
                if from_match:
                    excluded_emails.append(from_match.group(1).lower())
                if to_match:
                    excluded_emails.append(to_match.group(1).lower())
                
                # Add all other emails to the CC list
                cc_emails = [email.lower() for email in all_emails if email.lower() not in excluded_emails]
                
                if cc_emails:
                    nested_headers['cc'] = cc_emails
    
    def _create_nested_email_dict(self, content, headers, file_id, idx, parent_subject):
        """
        Create a dictionary for a nested email from headers.
        
        Args:
            content: Full content of the nested email
            headers: Extracted headers
            file_path: Path to the original email file
            idx: Index of the nested email in the parent
            parent_subject: Subject of the parent email
            
        Returns:
            Dictionary with nested email data
        """
        nested_id = generate_id(content, file_id, idx)
        parsed_date = extract_date(headers['date']) if headers['date'] else None
        
        # Try to get the full body content
        body_clean = headers.get('body_clean', '')
        if not body_clean:
            body_clean = clean_body(content)
        
        return {
            'id': nested_id,
            'date': parsed_date,
            'subject': headers['subject'] or parent_subject,
            'from': headers['from'],
            'to': headers['to'],
            'cc': headers['cc'],
            'bcc': headers['bcc'],
            'body_clean': body_clean,
            'file_source': f"{file_id}-nested-{idx}",
        }
    
    def _get_nested_body_content(self, headers, content, file_path):
        """
        Get the body content for a nested email.
        
        Args:
            headers: Extracted headers
            content: Full content of the nested email
            file_path: Path to the original email file
            
        Returns:
            Cleaned body content
        """
        try:
            # Try to read the raw file to get full content if available
            with open(file_path, 'r', errors='ignore') as f:
                raw_content = f.read()
            
            # Get the enhanced body content
            if headers['from'] and headers['from'] in raw_content:
                # If we found the sender in the raw content, try to extract the full body
                return extract_forwarded_full_body(raw_content, file_path)
            else:
                return headers.get('body_clean', '') or clean_body(content)
        except Exception:
            return headers.get('body_clean', '') or clean_body(content)
    
    def _extract_nested_email_fallback(self, content, file_path, idx, parent_subject):
        """
        Fallback method to extract nested email data.
        
        Args:
            content: Content of the nested email
            file_path: Path to the original email file
            idx: Index of the nested email in the parent
            parent_subject: Subject of the parent email
            
        Returns:
            Dictionary with nested email data
        """
        # Create a pseudo-email to parse
        pseudo_content = f"From: Unknown\nTo: Unknown\nSubject: Unknown\nDate: Unknown\n\n{content}"
        forwarded_msg = email.message_from_string(pseudo_content, policy=policy.default)
        
        # Extract fields from the forwarded message
        fwd_fields = self._extract_email_fields(forwarded_msg)
        
        # Create a unique ID for this nested email
        nested_id = generate_id(content)
        
        # Add the nested email to our dataset
        return {
            'id': nested_id,
            'date': fwd_fields['date'],
            'subject': fwd_fields['subject'] or parent_subject,
            'from': fwd_fields['from'],
            'to': fwd_fields['to'],
            'cc': fwd_fields['cc'],
            'bcc': fwd_fields['bcc'],
            'body_clean': fwd_fields['body_clean'] or clean_body(content),
            'file_source': f"{file_path}-nested-{idx}",
        }
    
    def _generate_thread_id(self, row):
        """
        Generate a thread ID based on normalized subject and participants.
        
        Args:
            row: DataFrame row containing email data
            
        Returns:
            Thread ID string
        """
        import uuid
        import re
        
        # Clean up subject by removing prefixes like Re:, Fwd:, etc.
        subject = row['subject'] or ''
        clean_subject = re.sub(r'^(?:re|fwd|fw|forward):\s*', '', subject.strip().lower(), flags=re.IGNORECASE)
        
        # Create a key combining subject and participants
        participants = sorted(set(filter(None, [row['from']] + (row['to'] or []))))
        thread_key = clean_subject + '|' + '|'.join(participants)
        
        # Use UUID5 with DNS namespace for consistent generation
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, thread_key))
    
    @staticmethod
    def find_email_files(directory):
        """
        Find all email files in a directory (recursively).
        
        Args:
            directory: Directory to search in
            
        Returns:
            List of file paths
        """
        email_files = []
        for root, _, files in os.walk(directory):
            for file in files:
                # Skip obviously non-email files
                if file.endswith(('.py', '.md', '.txt', '.json')):  # TODO: add more file types to skip as needed or have strict 
                    continue
                    
                # Add file to list
                email_files.append(os.path.join(root, file))
        
        return email_files

    def _parse_email_content(self, content, file_id):
        """
        Parse an email from its content string.
        
        Args:
            content: String containing the email content
            file_id: Identifier for the source (for tracking purposes)
            
        Returns:
            List of dictionaries with email data
        """
        emails_data = []
        
        # Parse the email content as a message object
        msg = email.message_from_string(content, policy=policy.default)
        
        # Process the main email
        msg_id = generate_id(content, file_id)
        
        email_fields = self._extract_email_fields(msg)
        
        # Create the main email record
        email_data = {
            'id': msg_id,
            'date': email_fields['date'],
            'subject': email_fields['subject'],
            'from': email_fields['from'],
            'to': email_fields['to'],
            'cc': email_fields['cc'],
            'bcc': email_fields['bcc'],
            'body_clean': email_fields['body_clean'],
            'file_source': file_id,
        }
        
        emails_data.append(email_data)
        
        # Extract and process nested/forwarded emails
        forwarded_emails = extract_original_email(email_fields['body'])
        
        if self.debug:
            print(f"\nFound {len(forwarded_emails)} nested emails in {file_id}")
        
        for idx, forwarded_content in enumerate(forwarded_emails):
            nested_email = self._extract_nested_email(forwarded_content, file_id, idx, email_fields['subject'])
            if nested_email:
                emails_data.append(nested_email)
        
        return emails_data 