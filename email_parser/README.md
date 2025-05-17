# Email Parser Module Documentation

## Overview

The email_parser module provides a robust solution for parsing email files, extracting nested/forwarded messages, and organizing them into structured data. It's particularly optimized for handling the Enron email dataset format but works with standard email formats as well.

## Core Components

### EmailParser Class

The main parser class responsible for processing email files and extracting both primary and nested/forwarded messages.

#### Key Methods

- **__init__**: Initializes the parser with optional debug mode for verbose logging.
- **parse_files**: Processes multiple email files, extracts all message data, and returns results as a DataFrame.
- **_parse_single_file**: Handles a single file, supporting both CSV files with 'file' and 'message' columns and raw email files.
- **_extract_email_fields**: Extracts metadata from an email message object, handling both multipart and single-part messages.
- **_extract_nested_email**: Uses multiple strategies to identify and extract forwarded or nested emails from message content.
- **_handle_please_respond_format**: Specialized handler for the "Please respond to" format common in Enron emails.
- **_create_nested_email_dict**: Organizes extracted data from nested emails into a structured dictionary.
- **_get_nested_body_content**: Extracts the most complete version of a nested email's body content.
- **_extract_nested_email_fallback**: Provides an alternative method for extracting nested emails when primary methods fail.
- **_generate_thread_id**: Creates consistent thread IDs to group related messages based on subject and participants.
- **_parse_email_content**: Processes an email's raw content string to extract the main message and any nested messages.
- **find_email_files**: Static method to recursively find all potential email files in a directory.

## Extractors Module

This module contains specialized functions for extracting different components from email content.

### Headers Module

- **extract_enron_style_headers**: Extracts headers from the specialized Enron email format, including handling for internal email address formats (Name/Department/Enron@Enron).
- **extract_forwarded_headers**: Handles common forwarding header formats including "Original Message" and "Forwarded by" patterns.

### Content Module

- **extract_original_email**: Identifies and extracts sections of text that appear to be forwarded/nested emails using common patterns and separators.
- **extract_forwarded_full_body**: Attempts to extract the complete body text of a forwarded email while preserving its structure.

## Utils Module

Contains helper functions that support the email parsing process.

### Helper Functions

- **generate_id**: Creates stable, deterministic IDs for emails based on their content.
- **normalize_addresses**: Standardizes email addresses from various formats, including complex forms like "John Doe" <john.doe@example.com> and Enron-specific Name/Dept/Company@Company format.
- **extract_email_address**: Extracts and cleans a single email address from text containing address information.
- **clean_body**: Removes quoted text, signatures, forwarded message markers, and other noise from email bodies.
- **extract_date**: Parses various date formats found in emails into a standardized ISO format.
- **process_recipients**: Handles lists of recipients, normalizing and extracting proper email addresses.

## Data Models

### EmailData

A structured data model for storing parsed email information with the following fields:
- id: Unique identifier for the email
- date: ISO format date string
- subject: Email subject line
- from_addr: Sender email address
- to_addrs: List of recipient email addresses
- cc_addrs: List of CC recipient email addresses
- bcc_addrs: List of BCC recipient email addresses
- body_clean: Cleaned email body
- thread_id: Thread identifier for grouping related emails
- file_source: Source file path

## Processing Flow

1. **Email Loading**: Files are loaded either as raw email files or from CSV files with message content.
2. **Primary Parsing**: The main message is parsed to extract headers and body content.
3. **Body Cleaning**: The message body is cleaned to remove quotes, signatures, and other noise.
4. **Nested Message Detection**: The parser searches for patterns indicating forwarded or nested messages.
5. **Nested Message Extraction**: When found, forwarded messages are extracted and processed as separate emails.
6. **Data Organization**: All extracted messages are organized into a consistent structure.
7. **Thread Identification**: Related messages are grouped by generated thread IDs.
8. **Output Generation**: Results are returned as a pandas DataFrame with full metadata.

## Special Handling Features

- **Enron-Specific Formats**: Custom handling for the unique email formats in the Enron dataset.
- **Multiple Forwarding Styles**: Support for various forwarding formats and conventions.
- **Address Normalization**: Robust handling of complex and varied email address formats.
- **Nested Content Extraction**: Advanced techniques to extract complete nested messages, even from partial forwards.
- **Fallback Methods**: Multiple extraction approaches ensure maximum data recovery.

```python
class EmailParser:
    def __init__(self, debug=False):
        """
        Initialize the email parser.
        
        Args:
            debug (bool): Enable debug output for verbose logging of parsing errors and progress
        """
```

```python
def parse_files(self, file_paths):
    """
    Parse multiple email files and extract data including nested messages.
    
    This method processes each file in the provided list, extracts all emails (including
    nested/forwarded messages), and returns them as a DataFrame with full metadata.
    
    Args:
        file_paths (list): List of file paths to parse. Can be CSV files with 'file' and 
                          'message' columns or raw email files.
        
    Returns:
        pandas.DataFrame: DataFrame with parsed email data containing columns:
            - id: Unique identifier for each message
            - date: Parsed timestamp in ISO format
            - subject: Email subject line
            - from: Sender email address (normalized)
            - to: List of recipient email addresses (normalized)
            - cc: List of CC recipient email addresses (normalized)
            - bcc: List of BCC recipient email addresses (normalized)
            - body_clean: Email body with quotations removed
            - thread_id: Generated identifier for conversation threads
            - file_source: Source file with optional nested message indicator
    """