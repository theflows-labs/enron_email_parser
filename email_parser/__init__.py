"""
Email Parser: A Python package for parsing email files and extracting nested messages.

This package is designed to handle various email formats, with special 
emphasis on nested and forwarded messages in the Enron dataset.
"""

__version__ = "1.0.0"

from email_parser.parser import EmailParser
from email_parser.models import EmailData

__all__ = ['EmailParser', 'EmailData'] 