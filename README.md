# Email Parser

A Python package for parsing email files and extracting nested messages, with special focus on handling the Enron email dataset format.

## Features

- Parse email files in various formats
- Extract nested and forwarded emails within message bodies
- Handle Enron-specific email formats and conventions
- Properly capture TO, CC, and BCC recipients
- Identify email threads and conversations
- Clean message bodies to remove quoted content

## Setup and Installation

### Creating a Virtual Environment

It's recommended to use a virtual environment to avoid conflicts with other Python packages:

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### Installing Requirements

Once your virtual environment is activated, install the required dependencies:

```bash
# Install from requirements.txt
pip install -r requirements.txt

# Or install the package in development mode
pip install -e .
```

Required dependencies include:
- pandas: For data manipulation and CSV handling
- python-dateutil: For parsing various date formats
- email-validator: For validating and normalizing email addresses



## Usage

### Command-Line Usage

```bash
# Parse specific files
python email_parser_cli.py --files sample_data/1_one_simple_example.csv sample_data/2_multi_simple_example.csv --output output.csv

# Parse all emails in a directory
python email_parser_cli.py --dir /path/to/emails --output results.csv

# Enable debug output
python email_parser_cli.py --files sample_data/1_one_simple_example.csv --debug
```



### As a Library

```python
from email_parser import EmailParser

# Create a parser
parser = EmailParser(debug=True)

# Parse specific files
files = ['sample_data/1_one_simple_example.csv', 'sample_data/2_multi_simple_example.csv', 'sample_data/3_one_forwarded_example.csv', 
                 'sample_data/4_multiple_forwarded_example.csv', 'sample_data/5_randon.csv']
results = parser.parse_files(files)

# Save the results
results.to_csv('parsed_emails.csv')

# Access the data
for _, row in results.iterrows():
    print(f"From: {row['from']}")
    print(f"To: {row['to']}")
    print(f"Subject: {row['subject']}")
    print(f"Body: {row['body_clean'][:100]}...")
    print("---")
```




## Package Structure

```
email_parser/
├── __init__.py         # Package initialization
├── models.py           # Data models for storing email content
├── parser.py           # Main EmailParser class
├── extractors/         # Modules for extracting parts of emails
│   ├── __init__.py
│   ├── headers.py      # Functions for extracting headers
│   └── content.py      # Functions for extracting body content
└── utils/              # Utility functions
    ├── __init__.py
    └── helpers.py      # Helper functions like ID generation, address normalization
```


## Handling Nested Messages

The package efficiently extracts nested and forwarded emails using various techniques:

1. Identifying Enron-style forwarded messages with dash separators
2. Extracting "Please respond to" format emails common in the Enron dataset
3. Handling nested message blocks with sender/recipient information
4. Parsing "Original Message" sections

## Special Handling for Enron Format

The parser has specific logic to handle Enron's internal addressing format:
- Converting `Name/Department/Enron@Enron` to `name.department@enron.com`
- Handling "Sent by:" header fields
- Processing multi-line recipient lists
- Extracting CC recipients from nested formats 
