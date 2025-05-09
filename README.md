# AI-Powered Email Auto-Responder for Car Parking Business

## Overview
This Python script automatically reads customer emails from Gmail, generates AI-powered responses using OpenAI GPT-4, and replies to customers. It is designed for car parking businesses to handle repetitive customer queries efficiently.

## Features
- Secure Gmail integration (IMAP/SMTP, OAuth2 or App Passwords)
- AI-generated responses using GPT-4
- Customizable with business FAQs and example responses
- Manual review mode (optional)
- Local logging of all interactions
- Error handling and clear logging

## Setup Instructions

### 1. Clone the Repository
```
git clone <repo-url>
cd <repo-folder>
```

### 2. Install Dependencies
```
pip install -r requirements.txt
```

### 3. Configure Credentials
- Create a `.env` file with the following:
  - `EMAIL_ADDRESS=your_gmail_address@gmail.com`
  - `EMAIL_PASSWORD=your_app_password_or_leave_blank_for_oauth2`
  - `OPENAI_API_KEY=your_openai_api_key`
  - `MANUAL_REVIEW=true` (set to `false` to auto-send replies)
- For OAuth2, follow Google documentation to obtain `credentials.json` and place it in the project folder.

### 4. Add FAQs
- Edit `sample_faqs.json` to include your business's common questions and answers.

### 5. Run the Script
```
python email_auto_responder.py
```

## Usage
- The script checks for new emails every minute.
- For each new email, it generates a reply using GPT-4 and either sends it automatically or waits for manual review.
- All emails and responses are logged locally.

## Notes
- This is a proof-of-concept. For production, enhance security, error handling, and scalability.
- Requires a Gmail account with IMAP enabled and either OAuth2 credentials or an App Password.

## License
MIT 