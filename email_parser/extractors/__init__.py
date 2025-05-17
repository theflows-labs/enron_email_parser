"""
Email extractors package for the email parser.

This package contains modules for extracting various parts from emails,
such as headers and nested content.
"""

from email_parser.extractors.headers import (
    extract_enron_style_headers,
    extract_nested_email_headers,
    extract_forwarded_headers
)
from email_parser.extractors.content import (
    extract_original_email,
    extract_forwarded_full_body
)

__all__ = [
    'extract_enron_style_headers',
    'extract_nested_email_headers',
    'extract_forwarded_headers',
    'extract_original_email',
    'extract_forwarded_full_body'
] 