from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="email_parser",
    version="1.0.0",
    author="Enron Email Parser Team",
    author_email="jay@theflows.ai",
    description="Parse and extract nested/forwarded emails, optimized for the Enron dataset",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/theflows-labs/enron_email_parser",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "pandas>=1.0.0",
        "pytz>=2020.1",
    ],
    entry_points={
        "console_scripts": [
            "email-parser=email_parser_cli:main",
        ],
    },
) 