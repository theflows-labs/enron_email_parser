#!/usr/bin/env python3
"""
Command-line interface for the Email Parser package.

This script provides a command-line interface to parse email files
using the email_parser package.
"""
import os
import argparse
import pandas as pd
from email_parser import EmailParser, EmailData

def main():
    """Process command line arguments and run the email parser."""
    parser = argparse.ArgumentParser(description='Parse email files and extract nested messages')
    
    # Add command line arguments
    parser.add_argument('--files', nargs='+', help='Specific email files to parse')
    parser.add_argument('--dir', help='Directory containing email files to parse')
    parser.add_argument('--output', default='sample_data/parsed_emails.csv', help='Output CSV file path')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    # Create the parser instance
    email_parser = EmailParser(debug=args.debug)
    
    # Determine which files to parse
    files = []
    if args.files:
        files = args.files
    elif args.dir:
        files = email_parser.find_email_files(args.dir)
    else:
        # Default to example files if no arguments provided
        files = ['sample_data/1_one_simple_example.csv', 'sample_data/2_multi_simple_example.csv', 'sample_data/3_one_forwarded_example.csv', 
                 'sample_data/4_multiple_forwarded_example.csv', 'sample_data/5_randon.csv']
    
    # Check if files were found
    if not files:
        print("No files found or specified!")
        return
    
    print(f"Parsing {len(files)} email files...")
    
    # Parse the emails
    df = email_parser.parse_files(files)
    
    # Save to CSV
    df.to_csv(args.output, index=False)
    
    # Print debug info if requested
    if args.debug:
        print("\nSample of parsed data:")
        cols = ['id', 'from', 'to', 'cc', 'subject', 'date']
        print(df[cols].head())
    
    # Print statistics
    print(f"Processed {len(df)} emails (including {len(df) - len(files)} nested emails)")
    print(f"Output saved to {args.output}")
    
    # Print some stats
    thread_count = df['thread_id'].nunique()
    print(f"Found {thread_count} unique conversation threads")

if __name__ == "__main__":
    main() 