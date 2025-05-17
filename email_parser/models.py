"""
Models module for representing email data structures.

This module defines the basic data models used throughout the email parser.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


@dataclass
class EmailData:
    """
    Data class representing an email's contents and metadata.
    
    This class stores the core email data including headers, body,
    and parsed fields like sender, recipients, etc.
    """
    id: str = ""
    date: Optional[datetime] = None
    subject: str = ""
    from_addr: str = ""
    to: List[str] = field(default_factory=list)
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)
    body: str = ""
    body_clean: str = ""
    file_source: str = ""
    thread_id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailData':
        """Create an EmailData instance from a dictionary."""
        return cls(
            id=data.get('id', ''),
            date=data.get('date'),
            subject=data.get('subject', ''),
            from_addr=data.get('from', ''),
            to=data.get('to', []),
            cc=data.get('cc', []),
            bcc=data.get('bcc', []),
            body=data.get('body', ''),
            body_clean=data.get('body_clean', ''),
            file_source=data.get('file_source', ''),
            thread_id=data.get('thread_id')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the EmailData instance to a dictionary."""
        return {
            'id': self.id,
            'date': self.date,
            'subject': self.subject,
            'from': self.from_addr,
            'to': self.to,
            'cc': self.cc,
            'bcc': self.bcc,
            'body': self.body,
            'body_clean': self.body_clean,
            'file_source': self.file_source,
            'thread_id': self.thread_id
        }
    
    def generate_thread_id(self) -> str:
        """
        Generate a thread ID based on normalized subject and participants.
        
        The thread ID is created from a combination of the subject line
        (with prefixes like Re:, Fwd: removed) and the unique participants.
        This helps group related emails into conversation threads.
        """
        import re
        
        # Clean up subject by removing prefixes like Re:, Fwd:, etc.
        subject = self.subject or ''
        clean_subject = re.sub(r'^(?:re|fwd|fw|forward):\s*', '', subject.strip().lower(), flags=re.IGNORECASE)
        
        # Create a key combining subject and participants
        participants = sorted(set(filter(None, [self.from_addr] + (self.to or []))))
        thread_key = clean_subject + '|' + '|'.join(participants)
        
        # Use UUID5 with DNS namespace for consistent generation
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, thread_key)) 