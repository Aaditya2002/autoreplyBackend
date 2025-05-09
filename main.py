from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import os
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from openai import OpenAI
import json

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Email Auto-Responder API",
    description="API for automated email responses using AI",
    version="1.0.0"
)

# Get environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# CORS middleware configuration
origins = [
    "http://localhost:3000",  # Development frontend
    "https://email-auto-responder-frontend.vercel.app",  # Production frontend
    "https://*.vercel.app"  # Allow all Vercel preview deployments
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Google OAuth2 config
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify'
]

# Get redirect URI based on environment
REDIRECT_URI = (
    "https://email-auto-responder-frontend.vercel.app/auth/callback"  # Production
    if ENVIRONMENT == "production"
    else "http://localhost:3000/auth/callback"  # Development
)

# Models
class User(BaseModel):
    id: str
    name: str
    email: str
    profile_pic: str
    manual_review: bool = True

class EmailResponse(BaseModel):
    id: str
    from_: str
    subject: str
    body: str
    ai_response: Optional[str] = None

class Settings(BaseModel):
    manual_review: bool
    response_tone: str = "professional"
    response_length: str = "medium"

# OAuth2 flow
flow = Flow.from_client_config(
    {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=SCOPES,
    redirect_uri=REDIRECT_URI
)

# Dependency to get Gmail service
async def get_gmail_service(credentials: dict):
    creds = Credentials.from_authorized_user_info(credentials)
    return build('gmail', 'v1', credentials=creds)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Routes
@app.get("/api/auth/google")
async def google_auth():
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return {"auth_url": auth_url}

@app.post("/api/auth/google/callback")
async def google_callback(request: Request):
    try:
        body = await request.json()
        code = body.get('code')
        if not code:
            raise HTTPException(status_code=400, detail="Code is required")
        
        # Exchange code for tokens
        flow.fetch_token(code=code)
        
        # Get user info directly from the credentials
        service = build('oauth2', 'v2', credentials=flow.credentials)
        user_info = service.userinfo().get().execute()
        
        # Create user object with default settings
        user = {
            "id": user_info['id'],
            "name": user_info['name'],
            "email": user_info['email'],
            "profile_pic": user_info['picture'],
            "manual_review": True,  # Default setting
            "response_tone": "professional",  # Default setting
            "response_length": "medium"  # Default setting
        }
        
        return {"user": user}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/emails")
async def get_emails(credentials: dict = Depends(get_gmail_service)):
    try:
        service = credentials
        results = service.users().messages().list(
            userId='me',
            labelIds=['INBOX', 'UNREAD'],
            q='in:primary'
        ).execute()
        
        messages = results.get('messages', [])
        email_list = []
        
        for message in messages[:5]:
            msg = service.users().messages().get(
                userId='me',
                id=message['id'],
                format='full'
            ).execute()
            
            headers = msg['payload']['headers']
            subject = next(h['value'] for h in headers if h['name'] == 'Subject')
            sender = next(h['value'] for h in headers if h['name'] == 'From')
            
            # Get message body
            if 'parts' in msg['payload']:
                parts = msg['payload']['parts']
                body = ''
                for part in parts:
                    if part['mimeType'] == 'text/plain':
                        body = part['body']['data']
                        break
            else:
                body = msg['payload']['body']['data']
            
            email_list.append({
                'id': message['id'],
                'from': sender,
                'subject': subject,
                'body': body
            })
        
        return {"emails": email_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-response")
async def generate_response(
    email_id: str,
    credentials: dict = Depends(get_gmail_service)
):
    try:
        service = credentials
        message = service.users().messages().get(
            userId='me',
            id=email_id,
            format='full'
        ).execute()
        
        headers = message['payload']['headers']
        subject = next(h['value'] for h in headers if h['name'] == 'Subject')
        
        # Get message body
        if 'parts' in message['payload']:
            parts = message['payload']['parts']
            body = ''
            for part in parts:
                if part['mimeType'] == 'text/plain':
                    body = part['body']['data']
                    break
        else:
            body = message['payload']['body']['data']
        
        # Generate AI response
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an AI email assistant for a car parking business."},
                {"role": "user", "content": f"Generate a response to this email:\n\nSubject: {subject}\n\n{body}"}
            ]
        )
        
        ai_response = response.choices[0].message.content
        
        return {
            "email_id": email_id,
            "ai_response": ai_response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send-response")
async def send_response(
    email_id: str,
    response: str,
    credentials: dict = Depends(get_gmail_service)
):
    try:
        service = credentials
        message = service.users().messages().get(
            userId='me',
            id=email_id,
            format='full'
        ).execute()
        
        headers = message['payload']['headers']
        subject = next(h['value'] for h in headers if h['name'] == 'Subject')
        sender = next(h['value'] for h in headers if h['name'] == 'From')
        
        # Create and send response
        message = {
            'raw': f"To: {sender}\r\n"
                  f"Subject: Re: {subject}\r\n"
                  f"Content-Type: text/plain; charset=utf-8\r\n"
                  f"\r\n{response}"
        }
        
        service.users().messages().send(
            userId='me',
            body=message
        ).execute()
        
        # Mark as read
        service.users().messages().modify(
            userId='me',
            id=email_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
async def get_settings():
    # In a real application, you would store these in a database
    return {
        "manual_review": True,
        "response_tone": "professional",
        "response_length": "medium"
    }

@app.post("/api/settings")
async def update_settings(settings: Settings):
    # In a real application, you would update these in a database
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port) 